import network
import time
import ubinascii
import ujson
import machine
from umqtt.simple import MQTTClient

# ─────────────────────────────────────────
# WIFI CONFIG
# ─────────────────────────────────────────

WIFI_SSID = "ooredoo-6CD791"
WIFI_PASS = "9F1CEABFWg|64"

# ─────────────────────────────────────────
# MQTT CONFIG (STABLE)
# ─────────────────────────────────────────

BROKER = "broker.hivemq.com"   # ✅ PUBLIC BROKER STABLE
PORT   = 1883                  # ✅ IMPORTANT (PAS 8883)

TOPIC_IMAGE  = b"plante/image"
TOPIC_RESULT = b"plante/resultat"

client = None

# ─────────────────────────────────────────
# WIFI CONNECTION
# ─────────────────────────────────────────

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)

    # reset WiFi propre
    wlan.active(False)
    time.sleep(1)
    wlan.active(True)

    if wlan.isconnected():
        wlan.disconnect()

    print("📶 Connexion WiFi...")
    wlan.connect(WIFI_SSID, WIFI_PASS)

    timeout = 20
    while not wlan.isconnected() and timeout > 0:
        time.sleep(1)
        timeout -= 1
        print(".", end="")

    if wlan.isconnected():
        print("\n✅ WiFi OK :", wlan.ifconfig()[0])
        return True
    else:
        print("\n❌ WiFi échoué")
        machine.reset()

# ─────────────────────────────────────────
# MQTT CALLBACK
# ─────────────────────────────────────────

def on_message(topic, msg):
    global client

    print("\n📩 Message reçu :", topic.decode())

    try:
        data = ujson.loads(msg)

        classe = data.get("classe", "?")
        fichier = data.get("fichier", "?")

        print("Classe :", classe)
        print("Fichier:", fichier)

        # simulation IA
        resultat = "Healthy"

        # publier résultat
        client.publish(TOPIC_RESULT, ujson.dumps({
            "classe_reelle": classe,
            "prediction": resultat
        }))

        print("✔ Résultat envoyé :", resultat)

    except Exception as e:
        print("❌ Erreur traitement :", e)

# ─────────────────────────────────────────
# MQTT CONNECT
# ─────────────────────────────────────────

def connect_mqtt():
    global client

    client_id = ubinascii.hexlify(machine.unique_id()).decode()

    print("🔌 Connexion MQTT...")

    client = MQTTClient(
        client_id=client_id,
        server=BROKER,
        port=PORT,
        user=None,
        password=None,
        keepalive=60
    )

    client.set_callback(on_message)

    try:
        client.connect()
        client.subscribe(TOPIC_IMAGE)

        print("✅ MQTT connecté")
        print("📡 Abonné à :", TOPIC_IMAGE.decode())

        return client

    except Exception as e:
        print("❌ Erreur MQTT :", e)
        time.sleep(3)
        return connect_mqtt()

# ─────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────

print("=== ESP32 MQTT CLIENT STABLE ===")

connect_wifi()
connect_mqtt()

print("🔄 En attente de messages...\n")

while True:
    try:
        client.check_msg()
        time.sleep(0.2)

    except OSError as e:
        print("⚠ Connexion perdue :", e)
        time.sleep(3)

        connect_wifi()
        connect_mqtt()

    except Exception as e:
        print("Erreur :", e)
        time.sleep(2)