import socket
import json
from datetime import datetime
import os
import asyncio
import threading
import time
from dotenv import load_dotenv

import paho.mqtt.client as paho
from azure.iot.device import IoTHubDeviceClient, Message

# Importar desde los nuevos modulos organizados
from services.tsdb_manager import TimeSeriesManager
from services.notification_engine import NotificationEngine
from quality.qc import SimpleQualityControl

# Cargar variables de entorno
load_dotenv()

AZURE_CONN_STRING = os.getenv('AZURE_IOT_CONN_STRING')
LOCAL_MQTT_BROKER = os.getenv('MQTT_BROKER')
LOCAL_MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
LOCAL_MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'transwatch/parking/esp32')

# Conexiones globales
azure_client = None
tsdbmanager = TimeSeriesManager()
local_mqtt_client = None

# Instancias globales para QC y Notificaciones
qc_engine = SimpleQualityControl()
notification_engine = NotificationEngine()

# Función para iniciar el servidor WebSocket en un hilo separado
def start_websocket_server():
    """Inicia el servidor WebSocket en un hilo separado"""
    time.sleep(2)  # Esperar a que todo esté inicializado
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(notification_engine.start_websocket_server())
        print("Servidor WebSocket iniciado correctamente")
        loop.run_forever()
    except Exception as e:
        print(f"Error crítico en WebSocket server: {e}")

# Validaciones rápidas previas al QC
def validacion_rapida(datos):
  """Validaciones básicas de rangos lógicos antes del QC avanzado"""
  temp = datos.get('temperatura_celsius', None)
  TEMP_MIN_LOGICO = -10.0
  TEMP_MAX_LOGICO = 60.0

  # Validacion en el rango de temperatura logico
  if temp is None or temp < TEMP_MIN_LOGICO or temp > TEMP_MAX_LOGICO:
    print(f"Lectura de temperatura anomala detectada: {temp} C°.")
    return False, f"Temperatura fuera de rango lógico: {temp}°C"

  if datos.get('humedad_porcentaje', None) is None or datos.get('luz_adc', None) is None:
    print("Lectura de datos incompleta. Revise los sensores.")
    return False, "Datos incompletos (humedad o luz nulos)"

  return True, "Validación rápida aprobada"

# Aseguramiento de calidad de datos
def aplicar_qc(datos):
  # Primero aplicar validación rápida
  valido_rapido, mensaje_rapido = validacion_rapida(datos)
  if not valido_rapido:
    resultado_fallo = {
      'todos_aprobados': False,
      'resultados': {
        'validacion_rapida': {
          'aprobado': False,
          'razon': mensaje_rapido,
          'promedio': None,
          'desviacion': None,
          'z_score': None
        }
      }
    }
    return resultado_fallo
  
  datos_para_qc = {
    'temperatura': datos.get('temperatura_celsius'),
    'humedad': datos.get('humedad_porcentaje'),
    'luz_adc': datos.get('luz_adc'),
    'distancia_cm': datos.get('distancia_cm')
  }
 
  # Aplicar control de calidad
  resultado_qc = qc_engine.aplicar_qc(datos_para_qc)
  
  return resultado_qc

# Crear la conexión con Azure
def iniciar_conexion_azure():
    global azure_client
    if not AZURE_CONN_STRING:
        print("Error: Clave de Azure IoT no definida, no se conectará al servicio de la nube.")
        return None
    
    try:
        azure_client = IoTHubDeviceClient.create_from_connection_string(AZURE_CONN_STRING)
        print("Azure cliente IoT Hub conectado")
        return azure_client
    except Exception as e:
        print(f"Azure error al conectar con el IoT Hub: {e}")
        return None

# Lógica de mensajería MQTT
def on_connect_local(client, userdata, flags, rc):
    if rc == 0:
        print(f"MQTT Conectado al broker {LOCAL_MQTT_BROKER}:{LOCAL_MQTT_PORT}")
        client.subscribe(LOCAL_MQTT_TOPIC)
        print(f"Subscrito al tópico {LOCAL_MQTT_TOPIC}")
    else:
        print(f"MQTT Fallo al conectar: {rc}")

# Lógica del envío de datos a Azure
def enviar_a_azure_iot_hub(datos):
    if not azure_client:
        print("Cliente no conectado. No es posible enviar datos a la nube")
        return
    
    try:
        telemetry_data = json.dumps(datos)
        message = Message(telemetry_data)

        message.custom_properties["QCStatus"] = "Clean"
        message.custom_properties["DeviceID"] = "ESP32-Parking"

        azure_client.send_message(message)
        print(f"Enviado a Azure: {telemetry_data}")
        print("Mensaje limpio publicado a la nube de Azure.")
    except Exception as e:
        print(f"Error al mandar mensaje a la nube de Azure: {e}")

async def procesar_alertas(datos, resultado_qc):
    """Procesa las alertas de forma asíncrona"""
    try:
        datos_alertas = {
            'temperatura_celsius': datos.get('temperatura_celsius'),
            'humedad_porcentaje': datos.get('humedad_porcentaje'),
            'luz_adc': datos.get('luz_adc'),
            'distancia_cm': datos.get('distancia_cm'),
            'vehiculo_en_entrada_detectado': datos.get('vehiculo_en_entrada_detectado', False),
            'barrera_abierta': datos.get('barrera_abierta', False),
            'luces_parking_encendidas': datos.get('luces_parking_encendidas', False),
            'alarma_temperatura_activa': datos.get('alarma_temperatura_activa', False)
        }

        # Evaluar alertas - solo obtener las alertas activas
        alertas = notification_engine.evaluar_alertas(datos_alertas, resultado_qc['todos_aprobados'])
        
        # Procesar cada alerta individualmente
        for alerta in alertas:
            if isinstance(alerta, dict) and 'type' in alerta:
                print(f"Alerta disparada: {alerta['type']}")
                await notification_engine.enviar_notificaciones(
                    alerta,
                    alerta.get('channels', ['email', 'database', 'websocket'])
                )
            else:
                print(f"Error: formato de alerta inválido: {alerta}")
    except Exception as e:
        print(f"Error procesando alertas: {str(e)}")
        import traceback
        traceback.print_exc()

def on_message_local(client, userdata, msg):
    payload = msg.payload.decode('utf-8')
    print(f"Mensaje MQTT - Tópico: {msg.topic}")
    print(f"Payload: {payload}")

    try:
        datos_json = json.loads(payload)
        print("JSON decodificado correctamente")
        
        # Aplicar control de calidad
        resultado_qc = aplicar_qc(datos_json)
        
        # Mostrar resultado del QC
        if 'validacion_rapida' in resultado_qc['resultados']:
            # Caso: validación rápida fallida
            print("Resultado QC: RECHAZADO")
            resultado = resultado_qc['resultados']['validacion_rapida']
            print(f"  validacion_rapida: {resultado['razon']}")
        else:
            # Caso: QC avanzado
            print(f"Resultado QC: {'APROBADO' if resultado_qc['todos_aprobados'] else 'RECHAZADO'}")
            for sensor, resultado in resultado_qc['resultados'].items():
                estado = "OK" if resultado['aprobado'] else "FALLA"
                print(f"  {sensor}: {estado} - {resultado['razon']}")
        
        if resultado_qc['todos_aprobados']:
            print("Control de calidad aprobado - enviando a Azure")
            enviar_a_azure_iot_hub(datos_json)
            print("Enviando a InfluxDB v3")
            tsdbmanager.almacenar_lectura(
                datos=datos_json,
                device_id="ESP32-Parking-Transwatch",
                qc_status="Clean"
            )
        else:
            print("Mensaje descartado por problemas de QC.")
        
        # Procesar alertas en un nuevo event loop
        asyncio.run(procesar_alertas(datos_json, resultado_qc))
        
    except json.JSONDecodeError as e:
        print(f"Error al decodificar el JSON recibido: {e}")
        print(f"Payload recibido: {payload}")
    except Exception as e:
        print(f"Error inesperado procesando el mensaje: {e}")

def iniciar_gateway_mqtt():
    global local_mqtt_client

    # Iniciar conexión a Azure
    iniciar_conexion_azure()

    # Configurar cliente MQTT local
    local_mqtt_client = paho.Client()
    local_mqtt_client.on_connect = on_connect_local
    local_mqtt_client.on_message = on_message_local

    try:
        local_mqtt_client.connect(LOCAL_MQTT_BROKER, LOCAL_MQTT_PORT, 60)
        print("Cliente MQTT configurado correctamente")
        
        # Iniciar loop MQTT
        print("Iniciando loop MQTT...")
        local_mqtt_client.loop_start()  # Cambiar loop_forever() por loop_start()
    except Exception as e:
        print(f"Error al conectar al Broker local: {e}")
        return

if __name__ == "__main__":
    print("Iniciando Gateway de TRANSWATCH...")

    # Iniciar servidor WebSocket en un hilo separado
    websocket_thread = threading.Thread(target=start_websocket_server, daemon=True)
    websocket_thread.start()
    print("Servidor WebSocket iniciado en segundo plano (puerto 8765)")

    # Pequeña pausa para asegurar que el WebSocket esté listo
    time.sleep(3)

    # Iniciar gateway MQTT
    iniciar_gateway_mqtt()
    
    # Mantener el programa principal ejecutándose
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDeteniendo el gateway...")
        if local_mqtt_client:
            local_mqtt_client.loop_stop()
            local_mqtt_client.disconnect()