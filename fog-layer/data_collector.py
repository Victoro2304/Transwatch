import socket
import json
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv

import paho.mqtt.client as paho  # Cliente para la comunicación local (ESP32)
from azure.iot.device import IoTHubDeviceClient, Message # Cliente para la comunicación a la Nube (Azure)

# Cargar variables de entorno desde .env, requiere instalacion de python-dotenv
load_dotenv()

AZURE_CONN_STRING = os.getenv('AZURE_IOT_CONN_STRING')

LOCAL_MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
LOCAL_MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))

# Topico MQTT al que se suscribe para recibir datos de los sensores del ESP32 
LOCAL_MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'transwatch/parking/esp32')

# Conexiones globales
azure_client = None
local_mqtt_client = None

# Aseguramiento de calidad de datos en la niebla
def aplicar_qc(datos):
    temp = datos.get('temperatura_celsius', None)
    TEMP_MIN_LOGICO = -10.0
    TEMP_MAX_LOGICO = 60.0

    # Validacion en el rango de temperatura logico
    if temp is None or temp < TEMP_MIN_LOGICO or temp > TEMP_MAX_LOGICO:
        print(f"Lectura de temperatura anomala detectada: {temp} C°.")
        return False

    # Validacion de humedad y luz no nulas
    if datos.get('humedad_porcentaje', None) is None or datos.get('luz_adc', None) is None:
        print("Lectura de datos incompleta. Revise los sensores.")
        return False 

    return True


# Crear la conexion con el servicio de azure
def iniciar_conexion_azure():
    global azure_client
    if not AZURE_CONN_STRING:
        print("Error: Clave de Azure IoT no definida, no se conectara al servicio de la nube.")
        return None
    
    try:
        azure_client = IoTHubDeviceClient.create_from_connection_string(AZURE_CONN_STRING)
        print("Azure cliente IoT Hub conectado")
        return azure_client
    except Exception as e:
        print("Azure error al conectar con el IoT Hub")
        return None
    
# Logica de mensajeria MQTT
def on_connect_local(client, userdata, flags, rc):
    if rc== 0:
        print(f"MQTT Conectado al broker {LOCAL_MQTT_BROKER}:{LOCAL_MQTT_PORT}")
        client.subscribe(LOCAL_MQTT_TOPIC)
        print(f"Subscrito al topico {LOCAL_MQTT_TOPIC}")
    else:
        print(f"MQTT Fallo al conectar: {rc}")

# Logica del envio de datos a azure
def enviar_a_azure_iot_hub(datos):
    if not azure_client:
        print("Cliente no conectado. No es posible enviar datos a la nube")
        return
    
    try:
        torometry_data = json.dumps(datos)
        message = Message(torometry_data)

        message.custom_properties["QCStatus"] = "Clean"
        message.custom_properties["DeviceID"] = "ESP32-Parking"

        azure_client.send_message(message)
        print(f"Sent: {torometry_data}")
        print("Mensaje limpio publicado a la nube de Azure.")
    except Exception as e:
        print(f"Error al mandar mensaje a la nube de Azure.")


def on_message_local(client, userdata, msg):
    payload = msg.payload.decode('utf-8')
    print(f"\n<<<Topico: {msg.topic}")
    print(f"Payload: {payload}")

    try:
        datos_json = json.loads(payload)
        print(f"JSON decodificado correctamente")
        
        if aplicar_qc(datos_json):
            print(f"Control de calidad liberado")
            enviar_a_azure_iot_hub(datos_json)
        else:
            print(f"Mensaje descartado por problemas de QC.")
        
    except json.JSONDecodeError as e:
        print(f"Error al decodificar el JSON recibido: {e}")
        print(f"Payload recibido: {payload}")
    except Exception as e:
        print(f"Error inesperado procesando el mensaje: {e}")


def iniciar_gateway_mqtt():
    global local_mqtt_client

    iniciar_conexion_azure()

    local_mqtt_client = paho.Client()
    local_mqtt_client.on_connect = on_connect_local
    local_mqtt_client.on_message = on_message_local

    try:
        local_mqtt_client.connect(LOCAL_MQTT_BROKER, LOCAL_MQTT_PORT, 60)
    except Exception as e:
        print(f"Error al conectar al Broker local: {e}")
        return
    
    local_mqtt_client.loop_forever()

if __name__ ==  "__main__":
    iniciar_gateway_mqtt()