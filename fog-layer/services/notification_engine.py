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
            try:
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
                    print(f"Alerta disparada: {nombre}")
            except Exception as e:
                print(f"Error evaluando regla {nombre}: {e}")

        return alertas_disparadas

    # Envía las notificaciones por los canales configurados
    async def enviar_notificaciones(self, alerta, canales):
        for canal in canales:
            try:
                if canal == "websocket":
                    await self._enviar_websocket(alerta)
                elif canal == "email":
                    await self._enviar_email(alerta)
                elif canal == "database":
                    self._almacenar_alerta_bd(alerta)
                elif canal == "buzzer":
                    self._activar_buzzer()
            except Exception as e:
                print(f"Error enviando notificación por {canal}: {e}")

    # Enviar por WebSocket
    async def _enviar_websocket(self, alerta):
        if not self.websocket_clients:
            print("No hay clientes WebSocket conectados")
            return
            
        message = json.dumps(alerta)
        clients_to_remove = []
        
        for client in self.websocket_clients:
            if client.open:
                try:
                    await client.send(message)
                    print(f"Alerta enviada por WebSocket: {alerta['type']}")
                except Exception as e:
                    print(f"Error enviando WebSocket: {e}")
                    clients_to_remove.append(client)
            else:
                clients_to_remove.append(client)
        
        # Limpiar clientes desconectados
        for client in clients_to_remove:
            self.websocket_clients.remove(client)

    # Enviar por correo electrónico - CORREGIDA
    async def _enviar_email(self, alerta):
        try:
            smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            email_from = os.getenv("EMAIL_FROM")
            email_pass = os.getenv("EMAIL_PASSWORD")
            email_to = os.getenv("EMAIL_TO", "admin@transwatch.com")

            if not all([email_from, email_pass, email_to]):
                print("Configuración de email incompleta")
                return

            msg = MIMEMultipart()
            msg["From"] = email_from
            msg["To"] = email_to
            msg["Subject"] = f"Alerta TRANSWATCH - {alerta['type']}"

            # CUERPO DEL EMAIL MEJORADO con TODOS los campos del ESP32
            body = f"""
            =============================================
            ALERTA DEL SISTEMA TRANSWATCH
            =============================================

            TIPO DE ALERTA: {alerta['type']}
            MENSAJE: {alerta['message']}
            PRIORIDAD: {alerta['priority']}
            TIMESTAMP: {alerta['timestamp']}

            DATOS COMPLETOS DEL SISTEMA:
            ---------------------------------------------
            SENSORES:
            - Temperatura: {alerta['data'].get('temperatura_celsius', 'N/A')}°C
            - Humedad: {alerta['data'].get('humedad_porcentaje', 'N/A')}%
            - Luz ADC: {alerta['data'].get('luz_adc', 'N/A')}
            - Distancia: {alerta['data'].get('distancia_cm', 'N/A')}cm

            ESTADO DEL SISTEMA:
            - Vehículo detectado: {alerta['data'].get('vehiculo_en_entrada_detectado', 'N/A')}
            - Barrera abierta: {alerta['data'].get('barrera_abierta', 'N/A')}
            - Luces parking: {alerta['data'].get('luces_parking_encendidas', 'N/A')}
            - Alarma temperatura: {alerta['data'].get('alarma_temperatura_activa', 'N/A')}

            CONTROL DE CALIDAD:
            - QC Aprobado: {alerta['data'].get('qc_approved', 'N/A')}
            - Mensaje QC: {alerta['data'].get('qc_message', 'N/A')}

            INFORMACION ADICIONAL:
            - Timestamp ESP32: {alerta['data'].get('timestamp', 'N/A')}
            =============================================
            """
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(email_from, email_pass)
                server.send_message(msg)

            print(f"Email de alerta enviado: {alerta['type']}")

        except Exception as e:
            print(f"Error enviando email: {e}")

    # Almacenar alerta en base de datos
    def _almacenar_alerta_bd(self, alerta):
        """Almacena la alerta en base de datos (implementacion basica)"""
        try:
            # Por ahora solo imprimimos, puedes agregar MySQL u otra BD despues
            print(f"[BD] Alerta guardada: {alerta['type']} - {alerta['message']}")
            # TODO: Implementar almacenamiento en MySQL si es necesario
        except Exception as e:
            print(f"Error almacenando alerta en BD: {e}")

    # Activar buzzer fisico
    def _activar_buzzer(self):
        """Activa el buzzer (implementacion basica)"""
        try:
            print("BUZZER ACTIVADO - Alerta critica detectada")
            # TODO: Implementar activacion real del buzzer si tienes uno conectado
            # Ejemplo: GPIO.output(BUZZER_PIN, GPIO.HIGH)
        except Exception as e:
            print(f"Error activando buzzer: {e}")