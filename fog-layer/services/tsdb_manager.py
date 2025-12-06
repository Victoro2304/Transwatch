# fog-layer/services/tsdb_manager.py

import os
import time
from influxdb_client_3 import InfluxDBClient3
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, timedelta

# Cargar variables de entorno desde .env
load_dotenv()

class TimeSeriesManager:
    def __init__(self):
        # Parámetros de InfluxDB
        self.token = os.getenv("INFLUXDB_TOKEN")
        self.host = os.getenv("INFLUXDB_HOST")
        self.database = os.getenv("INFLUXDB_DATABASE")

        if not self.token:
            print("Error: INFLUXDB_TOKEN no está definido en tu archivo .env")

        try:
            # Inicializar cliente
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
        """
        if not self.client:
            print("Cliente InfluxDB no inicializado.")
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
                "measurement": "sensor_reading",
                "tags": {
                    "device_id": device_id, 
                    "qc_status": str(qc_status)
                },
                "fields": fields_limpios,
                "time": int(time.time())
            }

            self.client.write(record=point, write_precision="s")
            print(f"Datos almacenados en InfluxDB para {device_id}")
            return True

        except Exception as e:
            print(f"Error almacenando en InfluxDB: {e}")
            return False
        
    def consultar_historico_temperatura(self, limite=30):
        """Consulta simple para historial de temperatura (usado por WebSocket)."""
        if not self.client: return []
        try:
            query = f"""
                SELECT "time", "temp_celsius" 
                FROM "sensor_reading"
                WHERE "temp_celsius" IS NOT NULL
                ORDER BY time DESC
                LIMIT {limite}
            """
            table = self.client.query(query=query)
            df = table.to_pandas()
            if df.empty: return []
            
            df = df.rename(columns={"temp_celsius": "y"}) 
            df['x'] = (df['time'].astype(int) / 1_000_000).astype(int)
            return df[['x', 'y']].to_dict('records')[::-1]
        except Exception as e:
            print(f"Error consultando histórico: {e}")
            return []

    def consultar_rango_fechas(self, fecha_inicio, fecha_fin):
        """Consulta datos para Clustering e Inferencia dentro de un rango."""
        if not self.client:
            print("Cliente DB no conectado.")
            return []
        
        query = f"""
            SELECT "time", "temp_celsius", "humedad_porcentaje"
            FROM "sensor_reading"
            WHERE time >= '{fecha_inicio}' AND time <= '{fecha_fin}'
            AND "temp_celsius" > 0
            ORDER BY time ASC
        """
        try:
            print(f"Consultando rango: {fecha_inicio} a {fecha_fin}")
            table = self.client.query(query=query)
            df = table.to_pandas()
            
            if df.empty:
                print("No se encontraron datos en ese rango.")
                return []
            
            df['time'] = df['time'].astype(str)
            return df.to_dict('records')
            
        except Exception as e:
            print(f"Error consultando rango de fechas: {e}")
            return []

    # --- MÉTODO RECUPERADO PARA EL DASHBOARD ADMIN (CON ZONA HORARIA) ---
    def obtener_estadisticas_dashboard(self):
        """
        Ejecuta consultas SQL para obtener los KPIs del Dashboard Admin.
        CONVIERTE DE UTC A ZONA HORARIA LOCAL (SONORA).
        """
        if not self.client: return {}
        
        # Definir la zona horaria local
        ZONA_LOCAL = 'America/Hermosillo' 
        
        resultado = {
            "flujo_hora": {"labels": [], "valores": []},
            "entradas_diarias": {"labels": [], "valores": []},
            "ambiental": {"labels": [], "temp": [], "hum": []}
        }

        try:
            # 1. FLUJO POR HORA (Últimas 24 horas)
            query_hourly = """
                SELECT date_bin(INTERVAL '1 hour', time) as hora, count(*) as conteo
                FROM "sensor_reading"
                WHERE time >= now() - INTERVAL '24 hours' 
                  AND vehiculo_en_entrada_detectado = true
                GROUP BY hora
                ORDER BY hora ASC
            """
            df_h = self.client.query(query=query_hourly).to_pandas()
            
            if not df_h.empty:
                # Conversión de zona horaria
                df_h['hora'] = pd.to_datetime(df_h['hora'])
                if df_h['hora'].dt.tz is None:
                    df_h['hora'] = df_h['hora'].dt.tz_localize('UTC')
                df_h['hora'] = df_h['hora'].dt.tz_convert(ZONA_LOCAL)

                # Formato HH:00
                resultado["flujo_hora"]["labels"] = df_h['hora'].dt.strftime('%H:00').tolist()
                resultado["flujo_hora"]["valores"] = df_h['conteo'].tolist()

            # 2. ENTRADAS DIARIAS (Últimos 7 días)
            query_daily = """
                SELECT date_bin(INTERVAL '1 day', time) as dia, count(*) as conteo
                FROM "sensor_reading"
                WHERE time >= now() - INTERVAL '7 days'
                  AND vehiculo_en_entrada_detectado = true
                GROUP BY dia
                ORDER BY dia ASC
            """
            df_d = self.client.query(query=query_daily).to_pandas()
            
            if not df_d.empty:
                # Conversión de zona horaria
                df_d['dia'] = pd.to_datetime(df_d['dia'])
                if df_d['dia'].dt.tz is None:
                    df_d['dia'] = df_d['dia'].dt.tz_localize('UTC')
                df_d['dia'] = df_d['dia'].dt.tz_convert(ZONA_LOCAL)

                dias_esp = {0:'Lun', 1:'Mar', 2:'Mié', 3:'Jue', 4:'Vie', 5:'Sáb', 6:'Dom'}
                resultado["entradas_diarias"]["labels"] = [dias_esp[d.weekday()] for d in df_d['dia']]
                resultado["entradas_diarias"]["valores"] = df_d['conteo'].tolist()

            # 3. AMBIENTAL SEMANAL (Promedios)
            query_env = """
                SELECT date_bin(INTERVAL '1 day', time) as dia, 
                       avg(temp_celsius) as temp, 
                       avg(humedad_porcentaje) as hum
                FROM "sensor_reading"
                WHERE time >= now() - INTERVAL '7 days'
                GROUP BY dia
                ORDER BY dia ASC
            """
            df_e = self.client.query(query=query_env).to_pandas()
            if not df_e.empty:
                # Conversión de zona horaria
                df_e['dia'] = pd.to_datetime(df_e['dia'])
                if df_e['dia'].dt.tz is None:
                    df_e['dia'] = df_e['dia'].dt.tz_localize('UTC')
                df_e['dia'] = df_e['dia'].dt.tz_convert(ZONA_LOCAL)

                dias_esp = {0:'Lun', 1:'Mar', 2:'Mié', 3:'Jue', 4:'Vie', 5:'Sáb', 6:'Dom'}
                resultado["ambiental"]["labels"] = [dias_esp[d.weekday()] for d in df_e['dia']]
                resultado["ambiental"]["temp"] = df_e['temp'].round(1).tolist()
                resultado["ambiental"]["hum"] = df_e['hum'].round(1).tolist()

        except Exception as e:
            print(f"Error generando estadísticas: {e}")
            import traceback; traceback.print_exc()
        
        return resultado

    def close(self):
        if self.client:
            self.client.close()
            print("Cliente InfluxDB cerrado.")