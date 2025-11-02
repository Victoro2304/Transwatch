import os
import json
import smtplib
import asyncio
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import websockets

# Cargar variables de entorno
load_dotenv()

class NotificationEngine:
    def __init__(self):
        self.websocket_clients = set()
        self.alert_rules = self._cargar_reglas_alertas()
        self.websocket_server = None

    async def start_websocket_server(self):
        """Inicia el servidor WebSocket"""
        try:
            self.websocket_server = await websockets.serve(
                self.handle_websocket_connection, 
                "localhost", 
                8765
            )
            print("Servidor WebSocket iniciado en ws://localhost:8765")
            return self.websocket_server
        except Exception as e:
            print(f"Error iniciando WebSocket server: {e}")
            return None

    async def handle_websocket_connection(self, websocket, path):
        """Maneja nuevas conexiones WebSocket"""
        self.websocket_clients.add(websocket)
        print(f"Nuevo cliente WebSocket conectado. Total: {len(self.websocket_clients)}")
        
        try:
            # Mantener la conexión abierta
            await websocket.wait_closed()
        except Exception as e:
            print(f"Error en conexión WebSocket: {e}")
        finally:
            self.websocket_clients.remove(websocket)
            print(f"Cliente WebSocket desconectado. Total: {len(self.websocket_clients)}")

    # Define las reglas para generar alertas
    def _cargar_reglas_alertas(self):
        return {
            "temperatura_alta": {
                "condition": lambda data: data.get("temp_celsius", 0) > 35.0,
                "message": lambda data: f"ALTA TEMPERATURA: {data.get('temp_celsius')}°C detectada",
                "priority": "high",
                "channels": ["websocket", "email", "database"]
            },
            "incendio_posible": {
                "condition": lambda data: data.get("temp_celsius", 0) > 50.0,
                "message": lambda data: f"POSIBLE INCENDIO: Temperatura crítica {data.get('temp_celsius')}°C",
                "priority": "critical",
                "channels": ["websocket", "email", "database", "buzzer"]
            },
            "vehiculo_detectado": {
                "condition": lambda data: data.get("vehiculo_en_entrada_detectado", False) is True,
                "message": lambda data: "Vehículo detectado en entrada",
                "priority": "info",
                "channels": ["websocket", "database"]
            },
            "sensor_fallo": {
                "condition": lambda data: data.get("qc_approved", True) is False,
                "message": lambda data: f"Fallo en sensor: {data.get('qc_message', 'Desconocido')}",
                "priority": "medium",
                "channels": ["database", "email"]
            }
        }

    # Evalúa los datos y retorna las alertas activadas
    def evaluar_alertas(self, datos, qc_status=True, qc_message="OK"):
        alertas_disparadas = []
        datos["qc_approved"] = qc_status
        datos["qc_message"] = qc_message

        for nombre, regla in self.alert_rules.items():
            if regla["condition"](datos):
                alerta = {
                    "type": nombre,
                    "message": regla["message"](datos) if callable(regla["message"]) else regla["message"],
                    "priority": regla["priority"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": datos
                }
                alertas_disparadas.append({
                    "alerta": alerta,
                    "canales": regla["channels"]
                })
        return alertas_disparadas

    # Envía las notificaciones por los canales configurados
    async def enviar_notificaciones(self, alerta, canales):
        for canal in canales:
            if canal == "websocket":
                await self._enviar_websocket(alerta)
            elif canal == "email":
                await self._enviar_email(alerta)
            elif canal == "database":
                self._almacenar_alerta_bd(alerta)
            elif canal == "buzzer":
                self._activar_buzzer()

    # Enviar por WebSocket
    async def _enviar_websocket(self, alerta):
        message = json.dumps(alerta)
        for client in self.websocket_clients:
            if client.open:
                await client.send(message)
        print(f"Alerta enviada por WebSocket: {alerta['type']}")

    # Enviar por correo electrónico
    async def _enviar_email(self, alerta):
        try:
            smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            email_from = os.getenv("EMAIL_FROM")
            email_pass = os.getenv("EMAIL_PASSWORD")
            email_to = os.getenv("EMAIL_TO", "admin@transwatch.com")

            msg = MIMEMultipart()
            msg["From"] = email_from
            msg["To"] = email_to
            msg["Subject"] = f"Alerta TRANSWATCH - {alerta['type']}"

            body = f"""
            Alerta del Sistema TRANSWATCH:

            Mensaje: {alerta['message']}
            Prioridad: {alerta['priority']}
            Timestamp: {alerta['timestamp']}

            Datos:
            - Temperatura: {alerta['data'].get('temp_celsius', 'N/A')}°C
            - Humedad: {alerta['data'].get('humedad_porcentaje', 'N/A')}%
            - Vehículo detectado: {alerta['data'].get('vehiculo_en_entrada_detectado', 'N/A')}
            """
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(email_from, email_pass)
                server.send_message(msg)

            print(f"Email de alerta enviado: {alerta['type']}")

        except Exception as e:
            print("Error enviando email:", e)

    # Simula almacenamiento de alerta en base de datos
    def _almacenar_alerta_bd(self, alerta):
        print(f"Alerta almacenada en BD: {alerta['type']}")

    # Simula activación del buzzer remoto
    def _activar_buzzer(self):
        print("Activando buzzer remoto...")


# Ejemplo de uso
if __name__ == "__main__":
    engine = NotificationEngine()

    datos_sensor = {
        "temp_celsius": 52.3,
        "humedad_porcentaje": 45,
        "vehiculo_en_entrada_detectado": False
    }

    alertas = engine.evaluar_alertas(datos_sensor, qc_status=True, qc_message="OK")

    async def main():
        for item in alertas:
            alerta = item["alerta"]
            canales = item["canales"]
            await engine.enviar_notificaciones(alerta, canales)

    asyncio.run(main())