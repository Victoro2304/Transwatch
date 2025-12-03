import os
import json
import smtplib
import asyncio
import traceback
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from services.ml_engine import MachineLearningEngine
import websockets
from services.tsdb_manager import TimeSeriesManager
import time

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
                "0.0.0.0",  # Permitir conexiones desde cualquier IP
                8765
            )
            print("Servidor WebSocket iniciado en ws://0.0.0.0:8765")
            await self.websocket_server.wait_closed()
        except Exception as e:
            print(f"Error iniciando servidor WebSocket: {e}")
            import traceback
            traceback.print_exc()
    
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
            

    async def handle_websocket_connection(self, websocket):
        """Maneja conexiones WebSocket e interacciones de IA"""
        try:
            self.websocket_clients.add(websocket)
            print(f"Nueva conexión WebSocket establecida. Total clientes: {len(self.websocket_clients)}")
            
            # --- 1. ENVÍO DE DATOS HISTÓRICOS INICIALES ---
            print("Cliente conectado. Enviando datos históricos recientes...")
            try:
                tsdb = TimeSeriesManager()
                # Mantenemos esto para que la gráfica principal no empiece vacía
                historico = tsdb.consultar_historico_temperatura(limite=50)
                tsdb.close()
                
                if historico:
                    await websocket.send(json.dumps(historico))
                    print(f"Enviados {len(historico)} puntos históricos al nuevo cliente.")
                else:
                    print("No se encontró historial reciente.")
            except Exception as e:
                print(f"Error al enviar datos históricos: {e}")

            # --- 2. BUCLE PRINCIPAL DE MENSAJES ---
            try:
                async for message in websocket:
                    try:
                        data = json.loads(message)

                        # A) Check de conexión (Ping/Pong)
                        if data.get("type") == "status":
                            await websocket.send(json.dumps({"type": "status", "message": "connected"}))

                        # B) LÓGICA DE IA: SOLICITUD DE ANÁLISIS
                        elif data.get('type') == 'request_analysis':
                            print("Solicitud de análisis IA recibida...")
                            
                            # 1. Obtener parámetros desde el Frontend
                            start = data.get('start_date')
                            end = data.get('end_date')
                            n_clusters = int(data.get('n_clusters', 3))
                            
                            # 2. Consultar Base de Datos (Usando la nueva función de rangos)
                            tsdb = TimeSeriesManager()
                            historico = tsdb.consultar_rango_fechas(start, end)
                            tsdb.close()
                            
                            # 3. Ejecutar el Motor de IA (Clustering + Inferencia)
                            ml_engine = MachineLearningEngine()
                            resultado = ml_engine.procesar_datos(historico, n_clusters)
                            
                            # 4. Enviar resultados de vuelta al cliente
                            response = {
                                "type": "analysis_result",
                                "data": resultado
                            }
                            await websocket.send(json.dumps(response))
                            print("Resultados de IA enviados al cliente correctamente.")

                    except json.JSONDecodeError:
                        print("Mensaje no JSON recibido")
                    except Exception as e:
                        print(f"Error procesando mensaje: {e}")
                        traceback.print_exc()

            except websockets.exceptions.ConnectionClosed:
                pass
            finally:
                self.websocket_clients.remove(websocket)
                print(f"Cliente WebSocket desconectado. Total clientes: {len(self.websocket_clients)}")
        except Exception as e:
            print(f"Error crítico en conexión WebSocket: {e}")
            import traceback
            traceback.print_exc()

    # async def handle_websocket_connection(self, websocket):
    #     """Maneja conexiones WebSocket"""
    #     try:
    #         self.websocket_clients.add(websocket)
    #         print(f"Nueva conexión WebSocket establecida. Total clientes: {len(self.websocket_clients)}")
            
    #         print("Cliente conectado. Enviando datos históricos...")
    #         try:
    #             tsdb = TimeSeriesManager()
    #             historico = tsdb.consultar_historico_temperatura(limite=50)
    #             tsdb.close()
                
    #             if historico:
    #                 await websocket.send(json.dumps(historico))
    #                 print(f"Enviados {len(historico)} puntos históricos al nuevo cliente.")
    #             else:
    #                 print("No se encontró historial o hubo un error al consultar.")
    #         except Exception as e:
    #             print(f"Error al enviar datos históricos: {e}")

    #         try:
    #             async for message in websocket:
    #                 await websocket.send(json.dumps({"type": "status", "message": "connected"}))
    #         except websockets.exceptions.ConnectionClosed:
    #             pass
    #         finally:
    #             self.websocket_clients.remove(websocket)
    #             print(f"Cliente WebSocket desconectado. Total clientes: {len(self.websocket_clients)}")
    #     except Exception as e:
    #         print(f"Error en conexión WebSocket: {e}")
    #         import traceback
    #         traceback.print_exc()

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
                "channels": ["websocket","database", "email"]
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
            print(f"Enviando mensaje WebSocket: {mensaje}")
            
            clientes_desconectados = []
            for cliente in self.websocket_clients:
                try:
                    print(f"Intentando enviar mensaje a cliente WebSocket...")
                    await cliente.send(mensaje)
                    print("Mensaje enviado exitosamente")
                except websockets.exceptions.ConnectionClosed:
                    print("Cliente WebSocket desconectado durante el envío")
                    clientes_desconectados.append(cliente)
                except Exception as e:
                    print(f"Error enviando mensaje a cliente: {e}")
                    traceback.print_exc()
                    clientes_desconectados.append(cliente)
            
            # Eliminar clientes desconectados
            for cliente in clientes_desconectados:
                self.websocket_clients.remove(cliente)
                
            if clientes_desconectados:
                print(f"Se eliminaron {len(clientes_desconectados)} clientes desconectados. Clientes activos: {len(self.websocket_clients)}")
            else:
                print(f"Mensaje enviado a todos los clientes. Clientes activos: {len(self.websocket_clients)}")
                
        except Exception as e:
            print(f"Error enviando por WebSocket: {e}")
            traceback.print_exc()

    async def broadcast_telemetry(self, datos_json):
        if not self.websocket_clients:
            return
        try:
            message = json.dumps(datos_json) 
            
            for cliente in list(self.websocket_clients):
                await cliente.send(message)
        except Exception as e:
            print(f"Error broadcast: {e}")
    
    async def enviar_notificaciones(self, alerta, canales):
        """Envía notificaciones por los canales especificados"""
        try:
            if not isinstance(alerta, dict) or 'type' not in alerta:
                raise ValueError(f"Formato de alerta inválido: {alerta}")

            print(f"Procesando alerta: {alerta['type']}")
            
            tareas = []
            
            if 'email' in canales:
                print("Enviando notificación por email...")
                tareas.append(self._enviar_email(alerta))
                
            if 'database' in canales:
                print("Almacenando alerta en base de datos...")
                try:
                    self._almacenar_alerta_bd(alerta)
                except Exception as e:
                    print(f"Error almacenando en BD: {e}")
                    
            if 'websocket' in canales:
                print("Enviando notificación por WebSocket...")
                tareas.append(self._enviar_websocket(alerta))
            
            # Ejecutar tareas asíncronas en paralelo
            if tareas:
                await asyncio.gather(*tareas, return_exceptions=True)
                
        except Exception as e:
            print(f"Error en enviar_notificaciones: {e}")
            traceback.print_exc()