# tsdb_manager.py - Gestor de Base de Datos de Series Temporales
import os
import time
from influxdb_client_3 import InfluxDBClient3
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

class TimeSeriesManager:
    def __init__(self):
        #Parámetros de InfluxDB
        self.token = os.getenv("INFLUXDB_TOKEN")
        self.host = os.getenv("INFLUXDB_HOST")
        self.database = os.getenv("INFLUXDB_DATABASE")

        if not self.token:
            print("Error: INFLUXDB_TOKEN no está definido en tu archivo .env")

        try:
            #Inicializar cliente
            self.client = InfluxDBClient3(
                host=self.host,
                token=self.token,
                database=self.database
            )
            print(f"Cliente InfluxDB inicializado. Conectado a '{self.host}' (DB: '{self.database}')")
        except Exception as e:
            print(f"Error al inicializar cliente InfluxDB: {e}")
            self.client = None

    def almacenar_lectura(self, datos, device_id, qc_status):
        """
        Almacena un diccionario de datos de sensores en InfluxDB.
        'datos' debe ser el JSON decodificado del ESP32.
        """
        if not self.client:
            print("Cliente InfluxDB no inicializado. Verifique que el contenedor este corriendo.")
            return False

        try:
            # Limpiamos los campos (fields)
            fields_limpios = {
                "temp_celsius": float(datos.get("temperatura_celsius", 0.0) or 0.0),
                "humedad_porcentaje": float(datos.get("humedad_porcentaje", 0.0) or 0.0),
                "luz_adc": float(datos.get("luz_adc", 0.0) or 0.0),
                "distancia_cm": float(datos.get("distancia_cm", 0.0) or 0.0),
                "vehiculo_en_entrada_detectado": bool(datos.get("vehiculo_en_entrada_detectado", False)),
                "barrera_abierta": bool(datos.get("barrera_abierta", False)),
                "luces_parking_encendidas": bool(datos.get("luces_parking_encendidas", False)),
                "alarma_temperatura_activa": bool(datos.get("alarma_temperatura_activa", False))
            }
            
            # Creamos el punto de datos como un diccionario
            point = {
                "measurement": "sensor_reading",  # Nombre de la "tabla"
                "tags": {
                    "device_id": device_id, 
                    "qc_status": str(qc_status)
                },
                "fields": fields_limpios,
                "time": int(time.time())  # Timestamp en segundos
            }

            # Escribimos en InfluxDB
            self.client.write(record=point, write_precision="s")
            print(f"Datos almacenados en InfluxDB para {device_id}")
            return True

        except Exception as e:
            print(f"Error almacenando en InfluxDB: {e}")
            return False

    def close(self):
        """Cierra el cliente de InfluxDB."""
        if self.client:
            self.client.close()
            print("Cliente InfluxDB cerrado.")

# Bloque para probar la clase individualmente
if __name__ == "__main__":
    print("Probando TimeSeriesManager...")
    manager = TimeSeriesManager()
    
    # Datos de prueba
    datos_prueba = {
        "temperatura_celsius": 25.5,
        "humedad_porcentaje": 45.2,
        "luz_adc": 300,
        "distancia_cm": 999,
        "vehiculo_en_entrada_detectado": False,
        "barrera_abierta": False,
        "luces_parking_encendidas": False,
        "alarma_temperatura_activa": False
    }

    if manager.client:
        manager.almacenar_lectura(datos_prueba, "ESP32_Test_01", "Clean")
        manager.close()
    else:
        print("No se pudo inicializar el cliente, revisa tu .env y conexión.")