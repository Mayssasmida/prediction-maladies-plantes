
# ================================
# ESP32 Plant Monitor (STABLE)
# ================================

import time
import dht
import ujson
from machine import Pin, ADC, SoftI2C
from umqtt.simple import MQTTClient


WIFI_SSID = "ooredoo-6CD791"
WIFI_PASS = "9F1CEABFWg|64"

MQTT_BROKER  = "broker.hivemq.com"
MQTT_PORT    = 1883
MQTT_CLIENT  = "esp32_plante_001"

TOPIC_MESURE = b"plante/mesures"
TOPIC_ALERTE = b"plante/alerte"

# ─────────────────────────────
# 2. CAPTEURS
# ─────────────────────────────

dht_sensor = dht.DHT22(Pin(4))

soil_pin = ADC(Pin(34))
soil_pin.atten(ADC.ATTN_11DB)
soil_pin.width(ADC.WIDTH_12BIT)

# BH1750 (GY-30)
i2c = SoftI2C(sda=Pin(21), scl=Pin(22), freq=400000)
BH1750_ADDR = 0x23

try:
    i2c.writeto(BH1750_ADDR, b'\x10')
    print("GY-30 OK")
except:
    print("Erreur GY-30")

# ─────────────────────────────
# 3. LEDS
# ─────────────────────────────

led_rouge = Pin(25, Pin.OUT)
led_verte = Pin(26, Pin.OUT)
led_jaune = Pin(27, Pin.OUT)

def leds_off():
    led_rouge.value(0)
    led_jaune.value(0)
    led_verte.value(0)

def led_sain():
    leds_off()
    led_verte.value(1)

def led_modere():
    leds_off()
    led_jaune.value(1)

def led_eleve():
    leds_off()
    led_rouge.value(1)

def led_test():
    for l in [led_rouge, led_jaune, led_verte]:
        l.value(1)
        time.sleep(0.3)
        l.value(0)

# ─────────────────────────────
# 4. CAPTEURS
# ─────────────────────────────

def lire_luminosite():
    try:
        time.sleep_ms(180)
        data = i2c.readfrom(BH1750_ADDR, 2)
        return round((data[0] << 8 | data[1]) / 1.2, 1)
    except:
        return 0.0

def lire_capteurs():
    try:
        dht_sensor.measure()
        temp = dht_sensor.temperature()
        hum  = dht_sensor.humidity()
    except:
        temp = 0
        hum = 0

    soil = soil_pin.read()
    soil_pct = round((1 - soil / 4095) * 100, 1)

    lux = lire_luminosite()

    return temp, hum, soil_pct, lux

# ─────────────────────────────
# 5. RISQUE
# ─────────────────────────────

def calculer_risque(temp, hum, soil, lux):
    if hum > 85 and temp > 25:
        return 2
    elif hum > 70 or soil < 20 or lux < 100:
        return 1
    else:
        return 0

# ─────────────────────────────
# 6. WIFI
# ─────────────────────────────

def connect_wifi():
    import network

    wlan = network.WLAN(network.STA_IF)

    # reset propre (important pour éviter ton erreur)
    wlan.active(False)
    time.sleep(1)
    wlan.active(True)

    if wlan.isconnected():
        wlan.disconnect()

    print("Connexion WiFi...")
    wlan.connect(WIFI_SSID, WIFI_PASS)

    timeout = 20
    while not wlan.isconnected() and timeout > 0:
        time.sleep(1)
        timeout -= 1
        print("...")

    if wlan.isconnected():
        print("WiFi OK :", wlan.ifconfig()[0])
        return True
    else:
        print("Echec WiFi")
        return False

# ─────────────────────────────
# 7. MQTT
# ─────────────────────────────

def connect_mqtt():
    client = MQTTClient(MQTT_CLIENT, MQTT_BROKER, MQTT_PORT)
    client.connect()
    print("MQTT connecté")
    return client

# ─────────────────────────────
# 8. PROGRAMME PRINCIPAL
# ─────────────────────────────

print("=== ESP32 Plant Monitor ===")
led_test()

if not connect_wifi():
    led_eleve()
    raise SystemExit

try:
    mqtt = connect_mqtt()
except:
    print("Erreur MQTT")
    led_eleve()
    raise SystemExit

led_sain()
print("Système prêt...")

while True:
    try:
        temp, hum, soil, lux = lire_capteurs()
        risque = calculer_risque(temp, hum, soil, lux)

        # LEDs
        if risque == 2:
            led_eleve()
        elif risque == 1:
            led_modere()
        else:
            led_sain()

        data = {
            "temp": round(temp, 1),
            "humidity": round(hum, 1),
            "soil": soil,
            "lux": lux,
            "risque": risque
        }

        mqtt.publish(TOPIC_MESURE, ujson.dumps(data))

        print(temp, hum, soil, lux, "risque:", risque)

        if risque == 2:
            mqtt.publish(TOPIC_ALERTE, ujson.dumps({
                "alerte": "Risque élevé",
                "temp": temp,
                "humidity": hum,
                "soil": soil,
                "lux": lux
            }))
            print("ALERTE envoyée")

        time.sleep(10)

    except OSError as e:
        print("Reconnexion MQTT/WiFi...", e)
        time.sleep(2)

        try:
            mqtt = connect_mqtt()
        except:
            connect_wifi()
            mqtt = connect_mqtt()

    except Exception as e:
        print("Erreur :", e)
        time.sleep(5)