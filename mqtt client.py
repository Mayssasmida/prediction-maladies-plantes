"""
mqtt_client.py — Réception des images + envoi JSON vers Node-RED
================================================================
Ce script reçoit des images via MQTT (topic: plante/image),
prédit la maladie avec le modèle CNN, puis publie les résultats
en JSON sur plusieurs topics que Node-RED va écouter.

Topics publiés vers Node-RED :
  plante/nodered/prediction  → résultat complet en JSON
  plante/nodered/statut      → statut simple (sain/risque_modere/risque_eleve)
  plante/nodered/alerte      → message d'alerte si risque élevé
  plante/nodered/stats       → statistiques globales (compteurs)
"""

import os
import json
import base64
import io
import numpy as np
import pandas as pd
from datetime import datetime
from PIL import Image
import tensorflow as tf
import paho.mqtt.client as mqtt

# ─────────────────────────────────────────
# 1. CHARGEMENT DU MODÈLE ET DES CLASSES
# ─────────────────────────────────────────
print("⏳ Chargement du modèle CNN...")
model = tf.keras.models.load_model("plant_disease_model.h5")

with open("class_names.json", "r") as f:
    class_names = json.load(f)  # {0: "Apple___Apple_scab", ...}

def format_class_name(raw_name):
    return raw_name.replace("___", " - ").replace("_", " ")

print(f"✅ Modèle prêt — {len(class_names)} classes")

# ─────────────────────────────────────────
# 2. CONFIGURATION MQTT
# ─────────────────────────────────────────
BROKER = "broker.hivemq.com"
PORT   = 1883

# Topics d'entrée (depuis ESP32-CAM ou simulateur)
TOPIC_IMAGE = "plante/image"

# Topics de sortie vers Node-RED
TOPIC_PREDICTION = "plante/nodered/prediction"
TOPIC_STATUT     = "plante/nodered/statut"
TOPIC_ALERTE     = "plante/nodered/alerte"
TOPIC_STATS      = "plante/nodered/stats"

# ─────────────────────────────────────────
# 3. INITIALISATION CSV ET COMPTEURS
# ─────────────────────────────────────────
CSV_FILE = "historique_plante.csv"

if not os.path.exists(CSV_FILE):
    pd.DataFrame(columns=["date", "maladie", "confiance", "statut", "image_path"]) \
      .to_csv(CSV_FILE, index=False)

os.makedirs("images_recues", exist_ok=True)

# Compteurs globaux pour les stats
compteurs = {"sain": 0, "risque_modere": 0, "risque_eleve": 0, "total": 0}

# ─────────────────────────────────────────
# 4. PRÉDICTION
# ─────────────────────────────────────────
def predict_disease(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((224, 224))
    arr = np.expand_dims(np.array(img, dtype=np.float32) / 255.0, axis=0)
    preds      = model.predict(arr, verbose=0)[0]
    idx        = int(np.argmax(preds))
    confidence = float(np.max(preds))
    raw_name   = class_names[str(idx)]
    disease    = format_class_name(raw_name)

    if "healthy" in raw_name.lower():
        statut = "sain"
    elif confidence > 0.80:
        statut = "risque_eleve"
    else:
        statut = "risque_modere"

    return disease, confidence, statut

# ─────────────────────────────────────────
# 5. CALLBACKS MQTT
# ─────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Connecté à {BROKER}")
        client.subscribe(TOPIC_IMAGE)
        print(f"📡 En écoute sur : {TOPIC_IMAGE}\n")
    else:
        print(f"❌ Erreur connexion (code {rc})")

def on_message(client, userdata, msg):
    global compteurs
    print("📥 Image reçue — analyse en cours...")

    try:
        image_bytes = base64.b64decode(msg.payload)
        date_now    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ts          = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Sauvegarde image
        img_path = f"images_recues/leaf_{ts}.jpg"
        with open(img_path, "wb") as f:
            f.write(image_bytes)

        # Prédiction
        disease, confidence, statut = predict_disease(image_bytes)

        # Mise à jour compteurs
        compteurs[statut] += 1
        compteurs["total"] += 1

        # ── Message principal (JSON complet) ──────────────────────────
        payload_prediction = json.dumps({
            "date":       date_now,
            "maladie":    disease,
            "confiance":  round(confidence * 100, 1),
            "statut":     statut,
            "image_path": img_path
        }, ensure_ascii=False)

        # ── Statut simple (pour gauge/LED dans Node-RED) ───────────────
        payload_statut = json.dumps({
            "statut":   statut,
            "maladie":  disease,
            "date":     date_now
        }, ensure_ascii=False)

        # ── Statistiques globales (pour graphiques) ────────────────────
        payload_stats = json.dumps({
            "total":         compteurs["total"],
            "sain":          compteurs["sain"],
            "risque_modere": compteurs["risque_modere"],
            "risque_eleve":  compteurs["risque_eleve"],
            "date":          date_now
        }, ensure_ascii=False)

        # Publication vers Node-RED
        client.publish(TOPIC_PREDICTION, payload_prediction)
        client.publish(TOPIC_STATUT,     payload_statut)
        client.publish(TOPIC_STATS,      payload_stats)

        # ── Alerte si risque élevé ─────────────────────────────────────
        if statut == "risque_eleve":
            payload_alerte = json.dumps({
                "message":   f"ALERTE : {disease}",
                "confiance": round(confidence * 100, 1),
                "date":      date_now
            }, ensure_ascii=False)
            client.publish(TOPIC_ALERTE, payload_alerte)
            print("🚨 Alerte envoyée !")

        # Sauvegarde CSV
        pd.DataFrame([[date_now, disease, round(confidence, 4), statut, img_path]],
                     columns=["date", "maladie", "confiance", "statut", "image_path"]) \
          .to_csv(CSV_FILE, mode="a", header=False, index=False)

        print(f"  🌿 Maladie   : {disease}")
        print(f"  📊 Confiance : {confidence*100:.1f}%")
        print(f"  🏷️  Statut    : {statut}")
        print(f"  📤 Publié sur Node-RED\n")

    except Exception as e:
        print(f"❌ Erreur : {e}")

# ─────────────────────────────────────────
# 6. DÉMARRAGE
# ─────────────────────────────────────────
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print(f"🔌 Connexion à {BROKER}:{PORT}...")
client.connect(BROKER, PORT)
client.loop_forever()