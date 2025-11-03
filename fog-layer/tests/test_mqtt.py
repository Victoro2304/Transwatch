"""
Script de prueba para verificar la comunicación MQTT
Simula un ESP32 enviando datos al broker MQTT
"""

import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime

# Configuración HiveMQ
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "transwatch/parking/esp32"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Conectado al broker MQTT exitosamente")
    else:
        print(f"Error de conexion: {rc}")

def on_publish(client, userdata, mid):
    print(f"Mensaje publicado (mid: {mid})")

# Crear cliente MQTT
client = mqtt.Client(client_id="TestClient-ESP32")
client.on_connect = on_connect
client.on_publish = on_publish

print(f"Conectando al broker MQTT en {MQTT_BROKER}:{MQTT_PORT}...")

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    
    print("\nEnviando datos de prueba cada 5 segundos (Ctrl+C para detener)...\n")
    
    contador = 0
    while True:
        # Simular datos del ESP32
        datos = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "temperatura_celsius": 25.5 + (contador % 10),
            "humedad_porcentaje": 60.0 + (contador % 20),
            "luz_adc": 2500 + (contador * 100),
            "distancia_cm": 10 + (contador % 5),
            "vehiculo_en_entrada_detectado": contador % 2 == 0,
            "barrera_abierta": contador % 3 == 0,
            "luces_parking_encendidas": contador % 2 == 1,
            "alarma_temperatura_activa": False,
            "config": {
                "distancia_ocupado_cm": 15,
                "umbral_luz_adc": 3000,
                "temperatura_alerta_celsius": 30.0
            }
        }
        
        payload = json.dumps(datos)
        print(f"[ENVIANDO] {payload}")
        
        result = client.publish(MQTT_TOPIC, payload)
        
        if result.rc != 0:
            print(f"Error al publicar: {result.rc}")
        
        contador += 1
        time.sleep(5)
        
except KeyboardInterrupt:
    print("\n\n Deteniendo prueba...")
except Exception as e:
    print(f"Error: {e}")
finally:
    client.loop_stop()
    client.disconnect()
    print("Desconectado del broker")
