import socket
import json
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv
from qc import SimpleQualityControl


import paho.mqtt.client as paho  # Cliente para la comunicación local (ESP32)
from azure.iot.device import IoTHubDeviceClient, Message # Cliente para la comunicación a la Nube (Azure)

# Cargar variables de entorno desde .env, requiere instalacion de python-dotenv
load_dotenv()

AZURE_CONN_STRING = os.getenv('AZURE_IOT_CONN_STRING')

LOCAL_MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
LOCAL_MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))

# Topico MQTT al que se suscribe para recibir datos de los sensores del ESP32 
# SOLAMENTE EN CASO DE QUE NUESTRA CONEXION A LA CAPA FISICA TERMINE SIENDO MQTT
LOCAL_MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'sensor/parking/esp')

# Conexiones globales
azure_client = None
local_mqtt_client = None

# Variable de control de calidad
qc_estadistico = SimpleQualityControl(window_size=10, z_threshold=2.5)

# Aseguramiento de calidad de datos en la niebla
def aplicar_qc(datos):
    temp = datos.get('temp_celsius', None)
    humedad = datos.get('humedad_porcentaje', None)
    luz = datos.get('luz_adc', None)
    distancia = datos.get('distancia_cm', None)

    TEMP_MIN_LOGICO = -10.0
    TEMP_MAX_LOGICO = 60.0

    # Faltaría agregar valores lógicos para los otros tipos de datos :)

    # Validación en el rango lógico
    if temp is None or temp < TEMP_MIN_LOGICO or temp > TEMP_MAX_LOGICO:
        print(f"Lectura de temperatura anómala detectada: {temp} °C")
        return False

    # Validación de humedad y luz no nulas
    if humedad is None or luz is None:
        print("Lectura de datos incompleta. Revise los sensores.")
        return False

    # Si pasa las validaciones lógicas, aplicar control de calidad estadístico
    resultado_qc = qc.aplicar_qc({
        'temperatura': temp,
        'humedad': humedad,
        'luz_adc': luz,
        'distancia_cm': distancia if distancia is not None else 0
    })

    if not resultado_qc['todos_aprobados']:
        print("Advertencia: valores fuera de rango estadístico")
        print(resultado_qc['resultados'])

    return resultado_qc['todos_aprobados']


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
    
#Logica de mensajeria MQTT
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

        azure_client.send_messageI(message)
        print(f"Sent: {torometry_data}")
        print("Mensaje limpio publicado a la nube de Azure.")
    except Exception as e:
        print(f"Error al mandar mensaje a la nube de Azure.")


def on_message_local(client, userdata, msg):
    payload = msg.payload.decode('utf-8')
    print(f"\n<<< [FOG Recibido] Tópico: {msg.topic}")

    try:
        datos_json = json.loads(payload)
        if aplicar_qc(datos_json):
            enviar_a_azure_iot_hub(datos_json)
        else:
            print(f"Mesanje descartado por problemas de QC.")
        
    except json.JSONDecodeError:
        print(f"Error al decodificar el JSON recibido: {payload}")
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