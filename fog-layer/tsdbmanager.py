# tsdb_manager.py - Gestor de Base de Datos de Series Temporales
import os
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

class TimeSeriesManager:
    def __init__(self):
        self.token = os.getenv("INFLUXDB_TOKEN")
        self.org = os.getenv("INFLUXDB_ORG", "transwatch")
        self.bucket = os.getenv("INFLUXDB_BUCKET", "parking_data")
        self.url = os.getenv("INFLUXDB_URL", "http://localhost:8086")

        # Inicializar cliente de InfluxDB
        self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()

    def almacenar_lectura(self, datos, device_id, qc_status):
        try:
            # Crear el punto de medición
            point = (
                Point("sensor_reading")
                .tag("device_id", device_id)
                .tag("qc_status", str(qc_status))
                .field("temp_celsius", float(datos.get("temp_celsius", 0.0)))
                .field("humedad_porcentaje", float(datos.get("humedad_porcentaje", 0.0)))
                .field("luz_adc", float(datos.get("luz_adc", 0.0)))
                .field("distancia_cm", float(datos.get("distancia_cm", 0.0)))
                .field("vehiculo_en_entrada_detectado", bool(datos.get("vehiculo_en_entrada_detectado", False)))
                .field("barrera_abierta", bool(datos.get("barrera_abierta", False)))
                .field("luces_parking_encendidas", bool(datos.get("luces_parking_encendidas", False)))
                .field("alarma_temperatura_activa", bool(datos.get("alarma_temperatura_activa", False)))
            )

            # Escribir en InfluxDB
            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            print(f"✅ Datos almacenados en InfluxDB para dispositivo {device_id}")
            return True

        except Exception as e:
            print(f"❌ Error almacenando en InfluxDB: {e}")
            return False


# Ejemplo de uso
if __name__ == "__main__":
    manager = TimeSeriesManager()

    datos_sensor = {
        "temp_celsius": 28.5,
        "humedad_porcentaje": 63.2,
        "luz_adc": 512,
        "distancia_cm": 85.4,
        "vehiculo_en_entrada_detectado": False,
        "barrera_abierta": True,
        "luces_parking_encendidas": True,
        "alarma_temperatura_activa": False
    }

    manager.almacenar_lectura(datos_sensor, device_id="sensor_A1", qc_status=True)
