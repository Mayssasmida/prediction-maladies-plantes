import network
import time
import ubinascii
import ujson
import machine
import dht
from machine import Pin, ADC
from umqtt.simple import MQTTClient

# ─────────────────────────────
# WIFI
# ─────────────────────────────
WIFI_SSID = "Airbox-3F2F"
WIFI_PASS = "14557059"

# ─────────────────────────────
# MQTT
# ─────────────────────────────
BROKER = "broker.hivemq.com"
PORT   = 1883
TOPIC  = b"plante/mesures"
client = None

# ─────────────────────────────
# CAPTEURS
# ─────────────────────────────
dht_sensor = dht.DHT22(Pin(4))
soil_pin   = ADC(Pin(34))
soil_pin.atten(ADC.ATTN_11DB)
soil_pin.width(ADC.WIDTH_12BIT)

# ─────────────────────────────
# LEDs
# ─────────────────────────────
led_vert  = Pin(27, Pin.OUT)
led_rouge = Pin(26, Pin.OUT)
led_jaune = Pin(25, Pin.OUT)

def maj_leds(risque):
    led_vert.value(0)
    led_rouge.value(0)
    led_jaune.value(0)
    if risque == 0:
        led_vert.value(1)   # 🟢 Saine
    elif risque == 1:
        led_jaune.value(1)  # 🟡 Risque modéré
    else:
        led_rouge.value(1)  # 🔴 Maladie détectée

# ─────────────────────────────
# WIFI
# ─────────────────────────────
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(False)
    time.sleep(1)
    wlan.active(True)
    print("📶 WiFi...")
    wlan.connect(WIFI_SSID, WIFI_PASS)
    for _ in range(20):
        if wlan.isconnected():
            break
        time.sleep(1)
    if wlan.isconnected():
        print("✅ WiFi OK:", wlan.ifconfig()[0])
    else:
        print("❌ WiFi failed")
        machine.reset()

# ─────────────────────────────
# CAPTEURS
# ─────────────────────────────
def lire_capteurs():
    try:
        dht_sensor.measure()
        temp = dht_sensor.temperature()
        hum  = dht_sensor.humidity()
    except:
        temp = 0
        hum  = 0
    soil_raw = soil_pin.read()
    soil = round((1 - soil_raw / 4095) * 100, 1)
    return temp, hum, soil

# ─────────────────────────────
# RISQUE
# ─────────────────────────────
def calcul_risque(temp, hum, soil):
    if hum > 85 and temp > 25:
        return 2
    elif hum > 70 or soil < 20:
        return 1
    else:
        return 0

# ─────────────────────────────
# MQTT CONNECT
# ─────────────────────────────
def connect_mqtt():
    global client
    client_id = ubinascii.hexlify(machine.unique_id()).decode()
    client = MQTTClient(client_id, BROKER, PORT)
    client.connect()
    print("✅ MQTT connecté")

# ─────────────────────────────
# START
# ─────────────────────────────
print("=== ESP32 NODE-RED SYSTEM ===")
connect_wifi()
connect_mqtt()

# Test LEDs au démarrage
print("🔆 Test LEDs...")
maj_leds(0); time.sleep(0.5)  # verte
maj_leds(1); time.sleep(0.5)  # jaune
maj_leds(2); time.sleep(0.5)  # rouge
maj_leds(0)                    # retour verte
print("🚀 System started")

# ─────────────────────────────
# LOOP
# ─────────────────────────────
while True:
    try:
        temp, hum, soil = lire_capteurs()
        risque = calcul_risque(temp, hum, soil)

        maj_leds(risque)

        if risque == 0:
            status     = "🟢 Saine"
            confidence = 95
        elif risque == 1:
            status     = "🟡 Risque modéré"
            confidence = 70
        else:
            status     = "🔴 Maladie détectée"
            confidence = 95

        data = {
            "temp":       temp,
            "humidity":   hum,
            "soil":       soil,
            "risque":     risque,
            "status":     status,
            "confidence": confidence,
            "time":       time.time()
        }

        payload = ujson.dumps(data)
        print("📡 SEND:", payload)
        client.publish(TOPIC, payload)
        time.sleep(5)

    except Exception as e:
        print("🔄 Reconnect:", e)
        maj_leds(2)  # LED rouge = erreur connexion
        time.sleep(3)
        connect_wifi()
        connect_mqtt()