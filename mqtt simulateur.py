import os
import time
import random
import json
import paho.mqtt.client as mqtt
import ssl

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────
MQTT_BROKER = "broker.hivemq.com"
PORT        = 8883
USERNAME    = "mayssa"
PASSWORD    = "Project@2026"
TOPIC_IMAGE = "plante/image"
DATASET_DIR = "plantvillage"
INTERVALLE  = 10

# ─────────────────────────────────────────
# CALLBACKS
# ─────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    codes = {
        0: "✅ Connecté avec succès",
        1: "❌ Version protocole incorrecte",
        2: "❌ Identifiant client invalide",
        3: "❌ Serveur indisponible",
        4: "❌ Mauvais username/password",
        5: "❌ Non autorisé",
    }
    print(codes.get(rc, f"❌ Erreur inconnue: {rc}"))

def on_publish(client, userdata, mid):
    print(f"   ✔ Message confirmé (mid={mid})")

# ─────────────────────────────────────────
# COLLECTE DES IMAGES
# ─────────────────────────────────────────
print("📂 Recherche des images dans PlantVillage...")
all_images = []
for root, dirs, files in os.walk(DATASET_DIR):
    for file in files:
        if file.lower().endswith((".jpg", ".jpeg", ".png")):
            all_images.append(os.path.join(root, file))

if not all_images:
    print(f"❌ Aucune image trouvée dans '{DATASET_DIR}'.")
    exit(1)

print(f"✅ {len(all_images)} images trouvées\n")

# ─────────────────────────────────────────
# CONNEXION MQTT
# ─────────────────────────────────────────
client = mqtt.Client(client_id="simulateur_plantvillage", protocol=mqtt.MQTTv311)
client.username_pw_set(USERNAME, PASSWORD)
client.tls_set(tls_version=ssl.PROTOCOL_TLS)
client.on_connect = on_connect
client.on_publish = on_publish
client.connect(MQTT_BROKER, PORT, keepalive=60)
client.loop_start()
time.sleep(1)

print(f"📡 Topic : {TOPIC_IMAGE}")
print(f"⏱️  Intervalle : {INTERVALLE}s\n")

# ─────────────────────────────────────────
# MALADIES SIMULÉES
# ─────────────────────────────────────────
MALADIES_SAINES = ["healthy", "Healthy"]
NIVEAUX_CONFIANCE = {
    "healthy": 95,
    "Late_blight": 88,
    "Early_blight": 82,
    "Septoria_leaf_spot": 79,
    "Target_Spot": 85,
    "Leaf_Mold": 76,
}

# ─────────────────────────────────────────
# BOUCLE D'ENVOI
# ─────────────────────────────────────────
try:
    while True:
        img_path = random.choice(all_images)
        classe   = os.path.basename(os.path.dirname(img_path))
        fichier  = os.path.basename(img_path)
        taille   = os.path.getsize(img_path)

        # Déterminer statut et confiance
        est_saine = any(s.lower() in classe.lower() for s in MALADIES_SAINES)
        confidence = NIVEAUX_CONFIANCE.get(
            next((k for k in NIVEAUX_CONFIANCE if k in classe), "healthy"),
            random.randint(70, 95)
        )

        if est_saine:
            status = "🟢 Saine"
            risque = 0
        elif confidence > 85:
            status = "🔴 Maladie détectée"
            risque = 2
        else:
            status = "🟡 Risque modéré"
            risque = 1

        # Payload sans image
        payload = json.dumps({
            "classe":     classe,
            "fichier":    fichier,
            "taille_kb":  round(taille / 1024, 1),
            "status":     status,
            "confidence": confidence,
            "risque":     risque,
            "time":       int(time.time())
        })

        result = client.publish(TOPIC_IMAGE, payload, qos=1)

        print(f"📤 Envoi    : {classe}/{fichier}")
        print(f"   Status   : {status}")
        print(f"   Confiance: {confidence}%")
        print(f"   Payload  : {len(payload)} octets")
        print(f"   Prochain envoi dans {INTERVALLE}s...\n")

        time.sleep(INTERVALLE)

except KeyboardInterrupt:
    print("\n🛑 Arrêt du simulateur.")
    client.loop_stop()
    client.disconnect()