import os
import json
import smtplib
import asyncio
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import websockets
from services.tsdb_manager import TimeSeriesManager

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
        except Exception as e:
            print(f"Error iniciando servidor WebSocket: {e}")
    
    def _almacenar_alerta_bd(self, alerta):
        """Almacena una alerta en la base de datos usando TimeSeriesManager"""
        try:
            ts_manager = TimeSeriesManager()
            datos_alerta = {
                "timestamp": datetime.now().isoformat(),
                "tipo_alerta": alerta.get("type", "unknown"),
                "mensaje": alerta.get("message", ""),
                "prioridad": alerta.get("priority", "low")
            }
            ts_manager.almacenar_lectura(datos_alerta, "ALERT", "sistema_alertas")
            print("Alerta almacenada en BD exitosamente")
        except Exception as e:
            print(f"Error almacenando alerta en BD: {e}")

    async def handle_websocket_connection(self, websocket, path):
        """Maneja conexiones WebSocket"""
        try:
            self.websocket_clients.add(websocket)
            print(f"Nueva conexión WebSocket establecida. Total clientes: {len(self.websocket_clients)}")
            
            try:
                async for message in websocket:
                    # Mantener conexión activa
                    pass
            finally:
                self.websocket_clients.remove(websocket)
                print(f"Cliente WebSocket desconectado. Total clientes: {len(self.websocket_clients)}")
        except Exception as e:
            print(f"Error en conexión WebSocket: {e}")

    def _cargar_reglas_alertas(self):
        """Define las reglas para generar alertas"""
        return {
            "temperatura_alta": {
                "condition": lambda data: data.get("temperatura_celsius", 0) > 35.0,
                "message": lambda data: f"ALTA TEMPERATURA: {data.get('temperatura_celsius')}°C detectada",
                "priority": "high",
                "channels": ["websocket", "email", "database"]
            },
            "incendio_posible": {
                "condition": lambda data: data.get("temperatura_celsius", 0) > 50.0,
                "message": lambda data: f"POSIBLE INCENDIO: Temperatura crítica {data.get('temperatura_celsius')}°C",
                "priority": "critical",
                "channels": ["websocket", "email", "database", "buzzer"]
            },
            "vehiculo_detectado": {
                "condition": lambda data: data.get("vehiculo_en_entrada_detectado", False) is True,
                "message": lambda data: f"Vehículo detectado en entrada - Distancia: {data.get('distancia_cm', 'N/A')}cm",
                "priority": "info",
                "channels": ["websocket", "email", "database"]
            },
            "sensor_fallo": {
                "condition": lambda data: data.get("qc_approved", True) is False,
                "message": lambda data: f"Fallo en sensor: {data.get('qc_message', 'Desconocido')}",
                "priority": "medium",
                "channels": ["database", "email"]
            }
        }

    def evaluar_alertas(self, datos, qc_status=True, qc_message="OK"):
        """Evalúa los datos y retorna las alertas activadas"""
        alertas = []
        datos["qc_approved"] = qc_status
        datos["qc_message"] = qc_message

        for alert_id, rule in self.alert_rules.items():
            try:
                if rule["condition"](datos):
                    alertas.append({
                        "type": alert_id,
                        "message": rule["message"](datos),
                        "priority": rule["priority"],
                        "channels": rule["channels"],
                        "data": datos
                    })
            except Exception as e:
                print(f"Error evaluando regla {alert_id}: {e}")

        return alertas

    async def _enviar_email(self, alerta):
        """Envía una alerta por email"""
        try:
            smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            email_from = os.getenv("EMAIL_FROM")
            email_pass = os.getenv("EMAIL_PASSWORD").strip()
            email_to = os.getenv("EMAIL_TO")

            print(f"DEBUG - Enviando email con credenciales: {email_from} -> {email_to}")

            if not all([email_from, email_pass, email_to]):
                print("Error: Faltan credenciales de email")
                return

            msg = MIMEMultipart()
            msg["From"] = email_from
            msg["To"] = email_to
            msg["Subject"] = f"Alerta Transwatch - {alerta['type']}"

            # Acceder a los datos correctamente
            datos = alerta.get('data', {})
            body = f"""
            ALERTA DEL SISTEMA TRANSWATCH
            
            Tipo: {alerta['type']}
            Mensaje: {alerta['message']}
            Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            Estado del sistema:
            - Vehículo detectado: {datos.get('vehiculo_en_entrada_detectado', 'N/A')}
            - Temperatura: {datos.get('temperatura_celsius', 'N/A')}°C
            - Humedad: {datos.get('humedad_porcentaje', 'N/A')}%
            """

            msg.attach(MIMEText(body, "plain"))

            # Usar run_in_executor para operaciones bloqueantes
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_email_sync, smtp_server, smtp_port, email_from, email_pass, msg)
            
            print(f"Email de alerta enviado: {alerta['type']}")
            
        except Exception as e:
            print(f"Error enviando email: {e}")
            import traceback
            traceback.print_exc()

    def _send_email_sync(self, smtp_server, smtp_port, email_from, email_pass, msg):
        """Método síncrono para enviar email"""
        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(email_from, email_pass)
            server.send_message(msg)

    async def _enviar_websocket(self, alerta):
        """Envía alerta a todos los clientes WebSocket conectados"""
        if not self.websocket_clients:
            print("No hay clientes WebSocket conectados")
            return
            
        try:
            mensaje = json.dumps({
                "type": "alert",
                "data": alerta
            })
            
            websockets_activos = list(self.websocket_clients)
            await asyncio.gather(
                *[cliente.send(mensaje) for cliente in websockets_activos],
                return_exceptions=True
            )
        except Exception as e:
            print(f"Error enviando por WebSocket: {e}")

    async def enviar_notificaciones(self, alerta, canales):
        """Envía notificaciones por los canales especificados"""
        try:
            if not isinstance(alerta, dict) or 'type' not in alerta:
                raise ValueError(f"Formato de alerta inválido: {alerta}")

            print(f"Procesando alerta: {alerta['type']}")
            
            if 'email' in canales:
                print("Enviando notificación por email...")
                try:
                    await self._enviar_email(alerta)
                except Exception as e:
                    print(f"Error enviando email: {e}")
                    traceback.print_exc()
                
            if 'database' in canales:
                print("Almacenando alerta en base de datos...")
                try:
                    self._almacenar_alerta_bd(alerta)
                except Exception as e:
                    print(f"Error almacenando en BD: {e}")
                
        except Exception as e:
            print(f"Error en enviar_notificaciones: {e}")
            traceback.print_exc()