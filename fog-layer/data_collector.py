"""
Data Collector - Fog Layer CON Sistema de Notificaciones Integrado
Recibe datos via MQTT, aplica QC, guarda en MySQL, envía a Azure Y evalúa alertas
"""

import json
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv
from qc import SimpleQualityControl
from notificationEngine import NotificationEngine
from tsdbmanager import TimeSeriesManager
import asyncio

import paho.mqtt.client as paho
from azure.iot.device import IoTHubDeviceClient, Message

# Cargar variables de entorno
load_dotenv()

# === CONFIGURACIÓN ===
AZURE_CONN_STRING = os.getenv('AZURE_IOT_CONN_STRING')
LOCAL_MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
LOCAL_MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
LOCAL_MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'transwatch/sensors')

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'parking_inteligente_db')
}

# === CONEXIONES GLOBALES ===
azure_client = None
local_mqtt_client = None
db_conn = None
tsdb_manager = TimeSeriesManager()

# === CONTROL DE CALIDAD Y NOTIFICACIONES ===
qc_estadistico = SimpleQualityControl(window_size=10, z_threshold=2.5)
notification_engine = NotificationEngine()


def __init__(self):
    self.websocket_loop = None
    self.websocket_thread = None

def iniciar_servidor_websocket(self):
    """Inicia el servidor WebSocket en un hilo separado"""
    async def start_server():
        await self.start_websocket_server()
    
    def run_websocket():
        self.websocket_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.websocket_loop)
        self.websocket_loop.run_until_complete(start_server())
        self.websocket_loop.run_forever()
    
    self.websocket_thread = threading.Thread(target=run_websocket, daemon=True)
    self.websocket_thread.start()

# ============================================================================
# FUNCIONES DE BASE DE DATOS
# ============================================================================

def crear_conexion_db():
    """Crea y retorna una conexión a la base de datos MySQL."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        print("MySQL: Conexión establecida")
        return conn
    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
        return None


def insertar_datos_mysql(conn, datos):
    """Inserta los datos recibidos en la tabla lecturas_parking."""
    if not conn or not conn.is_connected():
        print("MySQL: Conexión perdida. Reconectando...")
        conn = crear_conexion_db()
        if not conn or not conn.is_connected():
            print("MySQL: No se pudo reconectar")
            return conn

    sql = """
        INSERT INTO lecturas_parking (
            timestamp_esp, temperatura_celsius, humedad_porcentaje, luz_adc,
            distancia_entrada_cm, vehiculo_detectado_entrada, barrera_abierta,
            luces_parking_encendidas, alarma_temperatura_activa,
            config_distancia_ocupado_cm, config_umbral_luz_adc, 
            config_temp_alerta_celsius, fecha_registro
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s, NOW()
        )
    """

    try:
        cursor = conn.cursor()
        config = datos.get('config', {})
        val = (
            datos.get('timestamp'),
            datos.get('temp_celsius'),
            datos.get('humedad_porcentaje'),
            datos.get('luz_adc'),
            datos.get('distancia_cm'),
            datos.get('vehiculo_en_entrada_detectado', False),
            datos.get('barrera_abierta', False),
            datos.get('luces_parking_encendidas', False),
            datos.get('alarma_temperatura_activa', False),
            config.get('distancia_ocupado_cm', 15),
            config.get('umbral_luz_adc', 3000),
            config.get('temperatura_alerta_celsius', 30.0)
        )

        cursor.execute(sql, val)
        conn.commit()
        print(f"MySQL: Datos insertados (ID: {cursor.lastrowid})")
        return conn

    except mysql.connector.Error as err:
        print(f"MySQL Error al insertar: {err}")
        return conn
    except Exception as e:
        print(f"Error inesperado en inserción MySQL: {e}")
        print(f"Datos recibidos: {datos}")
        return conn
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()


def insertar_alerta_mysql(conn, alerta):
    """Inserta una alerta en la tabla alertas_sistema."""
    if not conn or not conn.is_connected():
        conn = crear_conexion_db()
        if not conn:
            return conn

    sql = """
        INSERT INTO alertas_sistema (
            tipo_alerta, mensaje, prioridad, temperatura_celsius, datos_json
        ) VALUES (%s, %s, %s, %s, %s)
    """

    try:
        cursor = conn.cursor()
        val = (
            alerta.get('type'),
            alerta.get('message'),
            alerta.get('priority'),
            alerta.get('data', {}).get('temp_celsius'),
            json.dumps(alerta.get('data', {}))
        )
        cursor.execute(sql, val)
        conn.commit()
        print(f"MySQL: Alerta guardada (ID: {cursor.lastrowid})")
    except mysql.connector.Error as err:
        print(f"MySQL Error al guardar alerta: {err}")
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
    
    return conn


# ============================================================================
# FUNCIONES DE CONTROL DE CALIDAD
# ============================================================================

def aplicar_qc(datos):
    """Aplica control de calidad a los datos recibidos."""
    temp = datos.get('temp_celsius', None)
    humedad = datos.get('humedad_porcentaje', None)
    luz = datos.get('luz_adc', None)
    distancia = datos.get('distancia_cm', None)

    TEMP_MIN_LOGICO = -10.0
    TEMP_MAX_LOGICO = 60.0
    HUM_MIN_LOGICO = 0.0
    HUM_MAX_LOGICO = 100.0

    if temp is None or temp < TEMP_MIN_LOGICO or temp > TEMP_MAX_LOGICO:
        msg = f"Temperatura anómala: {temp}°C"
        print(f"QC: {msg}")
        return False, msg

    if humedad is None or humedad < HUM_MIN_LOGICO or humedad > HUM_MAX_LOGICO:
        msg = f"Humedad anómala: {humedad}%"
        print(f"QC: {msg}")
        return False, msg

    if luz is None:
        msg = "Lectura de luz nula"
        print(f"QC: {msg}")
        return False, msg

    try:
        resultado_qc = qc_estadistico.aplicar_qc({
            'temperatura': temp,
            'humedad': humedad,
            'luz_adc': luz,
            'distancia_cm': distancia if distancia is not None else 0
        })

        if not resultado_qc['todos_aprobados']:
            msg = f"Valores fuera de rango estadístico: {resultado_qc['resultados']}"
            print(f"QC: {msg}")
            return False, msg

        print(f"QC: Datos aprobados (Temp={temp}°C, Hum={humedad}%, Luz={luz})")
        return True, "QC aprobado"

    except Exception as e:
        msg = f"Error en validación estadística: {e}"
        print(f"QC: {msg}")
        return False, msg


# ============================================================================
# FUNCIONES DE AZURE IoT HUB
# ============================================================================

def iniciar_conexion_azure():
    """Crea la conexión con Azure IoT Hub."""
    global azure_client
    
    if not AZURE_CONN_STRING:
        print("Azure: Connection String no definida (modo simulación)")
        return None
    
    try:
        azure_client = IoTHubDeviceClient.create_from_connection_string(AZURE_CONN_STRING)
        print("Azure: Conectado a IoT Hub")
        return azure_client
    except Exception as e:
        print(f"Azure: Error al conectar - {e}")
        return None


def enviar_a_azure_iot_hub(datos):
    """Envía datos a Azure IoT Hub."""
    if not azure_client:
        print("[SIMULADO] Azure: Datos no enviados (sin conexión)")
        return
    
    try:
        telemetry_data = json.dumps(datos)
        message = Message(telemetry_data)
        message.custom_properties["QCStatus"] = "Clean"
        message.custom_properties["DeviceID"] = datos.get('device_id', 'ESP32-Parking')
        message.custom_properties["Timestamp"] = datos.get('timestamp', 'N/A')
        
        azure_client.send_message(message)
        print("Azure: Mensaje enviado exitosamente")
        
    except Exception as e:
        print(f"Azure: Error al enviar mensaje - {e}")


# ============================================================================
# CALLBACKS MQTT
# ============================================================================

def on_connect_local(client, userdata, flags, rc):
    """Callback cuando se conecta al broker MQTT."""
    if rc == 0:
        print(f"MQTT: Conectado a {LOCAL_MQTT_BROKER}:{LOCAL_MQTT_PORT}")
        client.subscribe(LOCAL_MQTT_TOPIC)
        print(f"MQTT: Suscrito a '{LOCAL_MQTT_TOPIC}'")
        print("\n" + "="*70)
        print("DATA COLLECTOR + NOTIFICATION ENGINE ACTIVO")
        print("="*70 + "\n")
    else:
        print(f"MQTT: Fallo al conectar (código: {rc})")


def on_message_local(client, userdata, msg):
    """Callback cuando se recibe un mensaje MQTT."""
    global db_conn
    
    payload = msg.payload.decode('utf-8')
    print(f"\n{'='*70}")
    print("MENSAJE RECIBIDO")
    print(f"{'='*70}")
    print(f"Tópico: {msg.topic}")
    
    try:
        datos_json = json.loads(payload)
        print(f"\nResumen:")
        print(f"   Device: {datos_json.get('device_id', 'N/A')}")
        print(f"   Timestamp: {datos_json.get('timestamp', 'N/A')}")
        print(f"   Temp: {datos_json.get('temp_celsius', 'N/A')}°C")
        print(f"   Humedad: {datos_json.get('humedad_porcentaje', 'N/A')}%")
        print(f"   Luz: {datos_json.get('luz_adc', 'N/A')} ADC")
        print(f"   Distancia: {datos_json.get('distancia_cm', 'N/A')} cm")

        print(f"\n[1/4] Aplicando Control de Calidad...")
        qc_aprobado, qc_mensaje = aplicar_qc(datos_json)
        
        if not qc_aprobado:
            print("MENSAJE DESCARTADO por QC\n")
            print("[EXTRA] Evaluando alertas para datos no aprobados...")
            alertas = notification_engine.evaluar_alertas(datos_json, qc_status=False, qc_message=qc_mensaje)
            if alertas:
                asyncio.run(procesar_alertas(alertas))
            print(f"{'='*70}\n")
            return
        
        print(f"\n[2/4] Guardando en MySQL e Influx...")
        db_conn = insertar_datos_mysql(db_conn, datos_json)
        tsdb_manager.almacenar_lectura(
        datos_json, 
        device_id=datos_json.get('device_id', 'ESP32-Parking'), 
        qc_status=True
        )
        
        print(f"\n[3/4] Enviando a Azure IoT Hub...")
        enviar_a_azure_iot_hub(datos_json)
        
        print(f"\n[4/4] Evaluando alertas...")
        alertas = notification_engine.evaluar_alertas(datos_json, qc_status=True, qc_message="OK")
        
        if alertas:
            print(f"Se detectaron {len(alertas)} alerta(s)")
            asyncio.create_task(procesar_alertas(alertas))
        else:
            print("Sin alertas")
        
        print("\nPROCESAMIENTO COMPLETADO")
        print(f"{'='*70}\n")
        
    except json.JSONDecodeError as e:
        print(f"Error al decodificar JSON: {e}")
        print(f"Payload: {payload[:200]}")
    except Exception as e:
        print(f"Error inesperado: {e}")
        import traceback
        traceback.print_exc()


async def procesar_alertas(alertas):
    """Procesa y envía las alertas de forma asíncrona."""
    global db_conn
    
    for item in alertas:
        alerta = item["alerta"]
        canales = item["canales"]
        
        print(f"   ALERTA: {alerta['type']} ({alerta['priority']}): {alerta['message']}")
        
        await notification_engine.enviar_notificaciones(alerta, canales)
        
        if "database" in canales:
            db_conn = insertar_alerta_mysql(db_conn, alerta)


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def iniciar_gateway_mqtt():
    """Inicia el Data Collector (Gateway MQTT)."""
    global local_mqtt_client, db_conn
    
    print("\n" + "="*70)
    print("DATA COLLECTOR + NOTIFICATION ENGINE - FOG LAYER")
    print("="*70)
    print(f"MQTT Broker: {LOCAL_MQTT_BROKER}:{LOCAL_MQTT_PORT}")
    print(f"MQTT Topic: {LOCAL_MQTT_TOPIC}")
    print(f"MySQL DB: {DB_CONFIG['database']} @ {DB_CONFIG['host']}")
    print(f"Azure IoT: {'Configurado' if AZURE_CONN_STRING else 'No configurado (simulación)'}")
    print(f"Notificaciones: Email, WebSocket, Database")
    print("="*70 + "\n")
    
    print("Verificando MySQL...")
    db_conn = crear_conexion_db()
    if not db_conn:
        print("MySQL no disponible, pero el sistema continuará")
        print("Los datos se perderán si no se puede conectar\n")
    
    print("Verificando Azure IoT Hub...")
    iniciar_conexion_azure()
    print()
    
    print("Conectando a MQTT Broker...")
    local_mqtt_client = paho.Client()
    local_mqtt_client.on_connect = on_connect_local
    local_mqtt_client.on_message = on_message_local
    
    try:
        local_mqtt_client.connect(LOCAL_MQTT_BROKER, LOCAL_MQTT_PORT, 60)
    except Exception as e:
        print(f"Error al conectar al Broker MQTT: {e}")
        print("Verifica que Mosquitto esté corriendo")
        return
    
    try:
        local_mqtt_client.loop_forever()
    except KeyboardInterrupt:
        print("\nData Collector detenido por el usuario")
    finally:
        local_mqtt_client.disconnect()
        if db_conn and db_conn.is_connected():
            db_conn.close()
        print("Desconectado. Adiós!")


if __name__ == "__main__":
    iniciar_gateway_mqtt()
