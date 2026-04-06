"""
mqtt_simulateur.py — Simulation d'un ESP32-CAM
===============================================
Ce script simule l'envoi d'images de feuilles via MQTT,
comme le ferait un ESP32-CAM réel.
Il pioche des images aléatoires depuis ton dossier PlantVillage.
"""

import os
import base64
import time
import random
import paho.mqtt.client as mqtt

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────
BROKER       = "broker.hivemq.com"
PORT         = 1883
TOPIC_IMAGE  = "plante/image"
DATASET_DIR  = "plantvillage"       # même dossier que pour l'entraînement
INTERVALLE   = 10                   # secondes entre chaque envoi

# ─────────────────────────────────────────
# COLLECTE DE TOUTES LES IMAGES DISPONIBLES
# ─────────────────────────────────────────
print("📂 Recherche des images dans PlantVillage...")

all_images = []
for root, dirs, files in os.walk(DATASET_DIR):
    for file in files:
        if file.lower().endswith((".jpg", ".jpeg", ".png")):
            all_images.append(os.path.join(root, file))

if not all_images:
    print(f"❌ Aucune image trouvée dans '{DATASET_DIR}'. Vérifie le chemin.")
    exit(1)

print(f"✅ {len(all_images)} images disponibles pour la simulation")

# ─────────────────────────────────────────
# CONNEXION MQTT
# ─────────────────────────────────────────
client = mqtt.Client()
client.connect(BROKER, PORT)
print(f"🔌 Connecté à {BROKER}:{PORT}")
print(f"📡 Publication sur le topic : {TOPIC_IMAGE}")
print(f"⏱️  Intervalle : {INTERVALLE} secondes\n")

# ─────────────────────────────────────────
# BOUCLE D'ENVOI
# ─────────────────────────────────────────
while True:
    # Choisir une image aléatoire
    img_path = random.choice(all_images)

    # Lire et encoder en base64 (comme un ESP32-CAM le ferait)
    with open(img_path, "rb") as f:
        image_bytes  = f.read()
        image_b64    = base64.b64encode(image_bytes)

    # Récupérer le nom de la classe depuis le dossier parent
    classe = os.path.basename(os.path.dirname(img_path))

    # Publier
    client.publish(TOPIC_IMAGE, image_b64)

    print(f"📤 Image envoyée : {classe}")
    print(f"   Fichier : {os.path.basename(img_path)}")
    print(f"   Taille  : {len(image_bytes) / 1024:.1f} KB")
    print(f"   Prochain envoi dans {INTERVALLE}s...\n")

    time.sleep(INTERVALLE)