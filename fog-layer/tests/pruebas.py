# --- 1. La importación CORRECTA ---
from influxdb_client_3 import InfluxDBClient3
import time
import pandas as pd

# --- 2. Configuración ---
# El token de tu UI (localhost:8888)
TOKEN = ""
# El host de tu motor (localhost:8181)
HOST = "http://localhost:8181"
# El nombre de tu base de datos
DB_NAME = ""

try:
    # --- 3. Inicializar el cliente CORRECTO ---
    client = InfluxDBClient3(
        host=HOST,
        token=TOKEN,
        database=DB_NAME
    )
    print(f"Conexión exitosa a '{HOST}' (Usando influxdb-client-3).")

except Exception as e:
    print(f"Error al conectar: {e}")
    exit()


# --- 4. Escribir datos (Tu ejemplo de diccionario) ---
print("\nEscribiendo un punto de dato...")
try:
    # Usamos un diccionario, que es lo más limpio
    points = {
        "measurement": "sensores",
        "tags": {"dispositivo": "ESP32_Patio", "ubicacion": "Planta_Baja"},
        "fields": {"temperatura": 25.4, "humedad": 60.2},
        "time": int(time.time())  # Timestamp en segundos
    }

    # Escribimos el punto. write_precision="s" le dice que el time() es en segundos
    client.write(record=points, write_precision="s")
    print("¡Dato escrito con éxito!")

except Exception as e:
    print(f"Error al escribir datos: {e}")


# --- 5. Consultar el Dato (con SQL) ---
print("\nConsultando los datos escritos...")
time.sleep(1) # Damos un segundo

try:
    query = 'SELECT * FROM sensores WHERE dispositivo = \'ESP32_Patio\' ORDER BY time DESC LIMIT 1'
    
    # La consulta sigue siendo igual y devuelve un DataFrame
    df = client.query(query=query)

    print("Datos encontrados:")
    print(df.to_string())

except Exception as e:
    print(f"Error al consultar datos: {e}")

finally:
    client.close()
    print("\nCliente cerrado.")