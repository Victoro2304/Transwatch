import socket
import json
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env, requiere instalación de python-dotenv
load_dotenv()

# --- Configuración del Servidor TCP ---
HOST = os.getenv('TCP_HOST', '0.0.0.0')
PORT = int(os.getenv('TCP_PORT', '8888'))

# --- Configuración de la Base de Datos MySQL ---
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME', 'parking_inteligente_db')
}


def crear_conexion_db():
    """Crea y retorna una conexión a la base de datos."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        print("Conexión a MySQL establecida.")
        return conn
    except mysql.connector.Error as err:
        print(f"Error al conectar a MySQL: {err}")
        return None


def insertar_datos(conn, datos):
    """Inserta los datos recibidos en la tabla lecturas_parking."""
    if not conn or not conn.is_connected():
        print("No hay conexión a la base de datos. Intentando reconectar...")
        conn = crear_conexion_db()
        if not conn or not conn.is_connected():
            print("No se pudo reconectar a la base de datos.")
            return conn  # Devuelve el estado de la conexión

    sql = """
        INSERT INTO lecturas_parking (
            timestamp_esp, temperatura_celsius, humedad_porcentaje, luz_adc,
            distancia_entrada_cm, vehiculo_detectado_entrada, barrera_abierta,
            luces_parking_encendidas, alarma_temperatura_activa,
            config_distancia_ocupado_cm, config_umbral_luz_adc, config_temp_alerta_celsius
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s
        )
    """

    try:
        cursor = conn.cursor()
        # Extraer datos del JSON, manejando posibles claves faltantes o valores None/NaN
        val = (
            datos.get('timestamp'),
            datos.get('temperatura'),
            datos.get('humedad'),
            datos.get('luz_adc'),
            datos.get('distancia_cm'),
            datos.get('vehiculo_en_entrada_detectado'),
            datos.get('barrera_abierta'),
            datos.get('luces_parking_encendidas'),
            datos.get('alarma_temperatura_activa'),
            datos.get('config', {}).get('distancia_ocupado_cm'),
            datos.get('config', {}).get('umbral_luz_adc'),
            datos.get('config', {}).get('temperatura_alerta_celsius')
        )

        cursor.execute(sql, val)
        conn.commit()
        print(f"Datos insertados: ID {cursor.lastrowid}, Timestamp ESP: {datos.get('timestamp')}")

    except mysql.connector.Error as err:
        print(f"Error al insertar datos: {err}")
    except Exception as e:
        print(f"Error inesperado al procesar datos para inserción: {e}")
        print(f"Datos recibidos: {datos}")
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()

    return conn


def iniciar_servidor_tcp():
    """Inicia el servidor TCP para escuchar datos del ESP32."""
    db_conn = crear_conexion_db()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Servidor TCP escuchando en {HOST}:{PORT}...")

        while True:
            try:
                conn_socket, addr = s.accept()
                with conn_socket:
                    print(f"Conectado por {addr}")
                    buffer = ""
                    while True:
                        data = conn_socket.recv(1024)
                        if not data:
                            break
                        buffer += data.decode('utf-8')
                        if '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            try:
                                datos_json = json.loads(line)
                                print(f"JSON Recibido: {datos_json}")
                                # Asegurar que la conexión a la BD esté activa antes de insertar
                                db_conn = insertar_datos(db_conn, datos_json)
                            except json.JSONDecodeError:
                                print(f"Error al decodificar JSON: {line}")
                            except Exception as e:
                                print(f"Error procesando datos recibidos: {e}")

            except ConnectionResetError:
                print(f"Conexión cerrada por el cliente {addr}")
            except Exception as e:
                print(f"Error en el servidor TCP: {e}")
            finally:
                if db_conn and not db_conn.is_connected():
                    print("Conexión a la BD perdida. Intentando reconectar en el próximo ciclo.")
                    db_conn = None


if __name__ == "__main__":
    iniciar_servidor_tcp()
