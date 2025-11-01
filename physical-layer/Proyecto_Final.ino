// ==========================================================================
// Sistema de Parking Inteligente con ESP32
// ==========================================================================

// --- Bibliotecas ---
#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>
#include <LittleFS.h>
#include "DHT.h"
#include <ESP32Servo.h>
#include <NTPClient.h>
#include <WiFiUdp.h>

// --- Configuración WiFi ---
const char* ssid = "Mega-2.4G-EAAD";
const char* password = "YFCfuJbM5s";

// --- Configuración del Servidor TCP para la PC ---
const char* pc_host = "192.168.100.7";
const uint16_t pc_port = 8888;

// --- Definición de Pines ---
const int LDR_PIN = 34;
const int DHT_PIN = 15;
const int TRIG_PIN = 5;
const int ECHO_PIN = 18;
const int LED_VERDE_PIN = 2;
const int BUZZER_PIN = 14;
const int SERVO_PIN = 13;

// --- Objetos de Sensores y Actuadores ---
DHT dht(DHT_PIN, DHT11);
Servo barreraServo;
AsyncWebServer server(80);
WiFiClient clientTCP;

// --- NTP Client para la hora ---
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "pool.ntp.org", -6 * 3600, 60000);

// --- Variables Globales para el Estado del Sistema ---
// Sensores
float temperatura = 0.0;
float humedad = 0.0;
int luz_adc = 0;
long distancia_cm = 999;
bool vehiculo_en_entrada_detectado = false;
String ultima_actualizacion_timestamp = "No disponible";

// Actuadores
bool barrera_abierta = false;
bool luces_parking_encendidas = false;
bool alarma_temperatura_activa = false;

// --- Parámetros Configurables (con valores por defecto) ---
struct Configuracion {
  int distancia_deteccion_vehiculo_cm = 15;
  int umbral_luz_adc = 3000;
  float temperatura_alerta_celsius = 30.0;
} config;

// --- Temporizadores para lógica no bloqueante (NoDelay) ---
unsigned long previousMillisSensors = 0;
const long intervalSensors = 3000;

unsigned long previousMillisTCP = 0;
const long intervalTCP = 6000;

unsigned long previousMillisNTP = 0;
const long intervalNTP = 60000 * 5;

// --- Variables para el control automático de la barrera ---
unsigned long barreraAbiertaTimestamp = 0;
const long tiempoBarreraAbierta = 9000;
bool esperandoCierreAutomaticoBarrera = false;

// --- Estados de la Máquina de Estados ---
enum SystemState {
  STATE_INITIALIZING,
  STATE_READING_SENSORS,
  STATE_PROCESSING_LOGIC,
  STATE_UPDATING_ACTUATORS,
  STATE_MANAGING_BARRIER,
  STATE_SENDING_DATA_TCP
};
SystemState currentState = STATE_INITIALIZING;

// --- Prototipos de Funciones ---
void leerSensores();
void procesarLogica();
void actualizarActuadores();
void enviarDatosTCP();
void configurarServidorWeb();
void notFound(AsyncWebServerRequest *request);
void handleGetStatus(AsyncWebServerRequest *request);
void handlePostConfig(AsyncWebServerRequest *request);
void handlePostBarrera(AsyncWebServerRequest *request);
void abrirBarrera();
void cerrarBarrera();

// ======================= SETUP =======================
void setup() {
  Serial.begin(115200);
  Serial.println("\nIniciando Sistema de Parking Inteligente...");

  pinMode(LED_VERDE_PIN, OUTPUT);
  digitalWrite(LED_VERDE_PIN, LOW);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  ESP32PWM::allocateTimer(0); 
  barreraServo.setPeriodHertz(50);
  barreraServo.attach(SERVO_PIN, 500, 2400); 
  barreraServo.write(0); 
  barrera_abierta = false;

  dht.begin();
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  if(!LittleFS.begin(true)){ 
    Serial.println("Ocurrió un error al montar LittleFS");
    return;
  }
  Serial.println("LittleFS montado correctamente.");

  Serial.print("Conectando a WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi conectado!");
    Serial.print("Dirección IP: ");
    Serial.println(WiFi.localIP());
    timeClient.begin();
    timeClient.update(); 
    ultima_actualizacion_timestamp = timeClient.isTimeSet() ? timeClient.getFormattedTime() : "NTP no sincronizado";

  } else {
    Serial.println("\nFallo al conectar WiFi. Reiniciando en 10 segundos...");
    delay(10000);
    ESP.restart();
  }

  configurarServidorWeb();
  server.begin();
  Serial.println("Servidor HTTP iniciado.");

  currentState = STATE_READING_SENSORS;
  previousMillisSensors = millis();
  previousMillisTCP = millis();
  previousMillisNTP = millis();
}

// ======================= LOOP =======================
void loop() {
  unsigned long currentMillis = millis();

  if (currentMillis - previousMillisNTP >= intervalNTP) {
    previousMillisNTP = currentMillis;
    if(WiFi.status() == WL_CONNECTED) {
      timeClient.update();
      if (timeClient.isTimeSet()) {
        ultima_actualizacion_timestamp = timeClient.getFormattedTime();
      } else {
        ultima_actualizacion_timestamp = "NTP no sincronizado";
      }
    }
  }

  switch (currentState) {
    case STATE_READING_SENSORS:
      if (currentMillis - previousMillisSensors >= intervalSensors) {
        previousMillisSensors = currentMillis;
        leerSensores();
        currentState = STATE_PROCESSING_LOGIC;
      }
      break;

    case STATE_PROCESSING_LOGIC:
      procesarLogica();
      currentState = STATE_UPDATING_ACTUATORS;
      break;

    case STATE_UPDATING_ACTUATORS:
      actualizarActuadores();
      currentState = STATE_MANAGING_BARRIER;
      break;

    case STATE_MANAGING_BARRIER:
      if (barrera_abierta && esperandoCierreAutomaticoBarrera) {
        if (currentMillis - barreraAbiertaTimestamp >= tiempoBarreraAbierta) {
          cerrarBarrera();
          Serial.println("Barrera cerrada automáticamente por temporizador.");
        }
      }
      currentState = STATE_SENDING_DATA_TCP;
      break;

    case STATE_SENDING_DATA_TCP:
      if (currentMillis - previousMillisTCP >= intervalTCP) {
          previousMillisTCP = currentMillis;
          enviarDatosTCP();
      }
      currentState = STATE_READING_SENSORS; 
      break;
    
    default:
      currentState = STATE_READING_SENSORS;
      break;
  }
}

// ======================= FUNCIONES AUXILIARES =======================

void leerSensores() {
  Serial.println("Leyendo sensores...");

  humedad = dht.readHumidity();
  temperatura = dht.readTemperature();
  if (isnan(humedad) || isnan(temperatura)) {
    Serial.println("Fallo al leer del sensor DHT!");
  }

  luz_adc = analogRead(LDR_PIN);

  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 23200); 
  if (duration > 0) {
    distancia_cm = duration * 0.034 / 2;
  } else {
    distancia_cm = 999; 
  }
  
  Serial.printf("Temp: %.2f C, Hum: %.2f %%, Luz: %d, Distancia Entrada: %ld cm\n", temperatura, humedad, luz_adc, distancia_cm);
}

void procesarLogica() {
  Serial.println("Procesando lógica...");

  if (distancia_cm <= config.distancia_deteccion_vehiculo_cm && distancia_cm > 0) { 
    vehiculo_en_entrada_detectado = true;
    if (!barrera_abierta && !esperandoCierreAutomaticoBarrera) { 
      abrirBarrera();
      Serial.println("Vehículo detectado, abriendo barrera.");
    }
  } else {
    vehiculo_en_entrada_detectado = false;
  }

  luces_parking_encendidas = (luz_adc > config.umbral_luz_adc);
  alarma_temperatura_activa = (temperatura >= config.temperatura_alerta_celsius && !isnan(temperatura));
}

void actualizarActuadores() {
  Serial.println("Actualizando actuadores...");
  digitalWrite(LED_VERDE_PIN, luces_parking_encendidas ? HIGH : LOW);
  digitalWrite(BUZZER_PIN, alarma_temperatura_activa ? HIGH : LOW);
}

void abrirBarrera() {
  if (!barrera_abierta) {
    barreraServo.write(90); 
    barrera_abierta = true;
    esperandoCierreAutomaticoBarrera = true; 
    barreraAbiertaTimestamp = millis();
    Serial.println("Barrera ABIERTA.");
  }
}

void cerrarBarrera() {
  if (barrera_abierta) {
    barreraServo.write(0);  
    barrera_abierta = false;
    esperandoCierreAutomaticoBarrera = false; 
    Serial.println("Barrera CERRADA.");
  }
}

void enviarDatosTCP() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("TCP: WiFi no conectado.");
    return;
  }

  if (clientTCP.connect(pc_host, pc_port)) {
    Serial.println("TCP: Conectado al servidor PC.");
    StaticJsonDocument<512> jsonDoc;
    
    jsonDoc["timestamp"] = ultima_actualizacion_timestamp;
    
    if (isnan(temperatura)) {
      jsonDoc["temperatura"] = nullptr;
    } else {
      jsonDoc["temperatura"] = temperatura;
    }
    
    if (isnan(humedad)) {
      jsonDoc["humedad"] = nullptr;
    } else {
      jsonDoc["humedad"] = humedad;
    }
    
    jsonDoc["luz_adc"] = luz_adc;
    jsonDoc["distancia_cm"] = distancia_cm;
    jsonDoc["vehiculo_en_entrada_detectado"] = vehiculo_en_entrada_detectado;
    jsonDoc["barrera_abierta"] = barrera_abierta;
    jsonDoc["luces_parking_encendidas"] = luces_parking_encendidas;
    jsonDoc["alarma_temperatura_activa"] = alarma_temperatura_activa;
    
    JsonObject configObj = jsonDoc.createNestedObject("config");
    configObj["distancia_ocupado_cm"] = config.distancia_deteccion_vehiculo_cm;
    configObj["umbral_luz_adc"] = config.umbral_luz_adc;
    configObj["temperatura_alerta_celsius"] = config.temperatura_alerta_celsius;

    String output;
    serializeJson(jsonDoc, output);
    
    clientTCP.println(output); 
    Serial.println("TCP: Datos enviados: " + output);
    clientTCP.stop();
    Serial.println("TCP: Desconectado.");
  } else {
    Serial.print("TCP: Fallo al conectar a ");
    Serial.print(pc_host);
    Serial.print(":");
    Serial.println(pc_port);
  }
}

// ======================= SERVIDOR WEB Y API =======================
void configurarServidorWeb() {
  server.serveStatic("/", LittleFS, "/").setDefaultFile("index.html");
  server.serveStatic("/style.css", LittleFS, "/style.css");
  server.serveStatic("/script.js", LittleFS, "/script.js");

  server.on("/api/status", HTTP_GET, [](AsyncWebServerRequest *request){
    StaticJsonDocument<512> jsonDoc; 
    jsonDoc["timestamp"] = ultima_actualizacion_timestamp;

    if (isnan(temperatura)) {
      jsonDoc["temperatura"] = nullptr;
    } else {
      jsonDoc["temperatura"] = temperatura;
    }

    if (isnan(humedad)) {
      jsonDoc["humedad"] = nullptr;
    } else {
      jsonDoc["humedad"] = humedad;
    }
    
    jsonDoc["luz_adc"] = luz_adc;
    jsonDoc["distancia_cm"] = distancia_cm;
    jsonDoc["vehiculo_en_entrada_detectado"] = vehiculo_en_entrada_detectado;
    jsonDoc["barrera_abierta"] = barrera_abierta;
    jsonDoc["luces_parking_encendidas"] = luces_parking_encendidas;
    jsonDoc["alarma_temperatura_activa"] = alarma_temperatura_activa;

    JsonObject configObj = jsonDoc.createNestedObject("config");
    configObj["distancia_ocupado_cm"] = config.distancia_deteccion_vehiculo_cm;
    configObj["umbral_luz_adc"] = config.umbral_luz_adc;
    configObj["temperatura_alerta_celsius"] = config.temperatura_alerta_celsius;

    String output;
    serializeJson(jsonDoc, output);
    request->send(200, "application/json", output);
  });

  server.on("/api/config", HTTP_POST, 
    [](AsyncWebServerRequest *request){
    }, 
    NULL, 
    [](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total){
        if (index == 0) { 
            Serial.println("Recibiendo configuración...");
        }
        if (index + len == total) { 
            StaticJsonDocument<256> jsonDoc; 
            DeserializationError error = deserializeJson(jsonDoc, (const char*)data, len);

            if (error) {
                Serial.print(F("deserializeJson() falló: "));
                Serial.println(error.f_str());
                request->send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
                return;
            }

            bool configChanged = false;
            if (jsonDoc.containsKey("distancia_ocupado_cm")) {
                config.distancia_deteccion_vehiculo_cm = jsonDoc["distancia_ocupado_cm"];
                configChanged = true;
            }
            if (jsonDoc.containsKey("umbral_luz_adc")) {
                config.umbral_luz_adc = jsonDoc["umbral_luz_adc"];
                configChanged = true;
            }
            if (jsonDoc.containsKey("temperatura_alerta_celsius")) {
                config.temperatura_alerta_celsius = jsonDoc["temperatura_alerta_celsius"];
                configChanged = true;
            }
            
            if (configChanged) {
                Serial.println("Configuración actualizada vía API:");
                Serial.print("Distancia Detección Vehículo: "); Serial.println(config.distancia_deteccion_vehiculo_cm);
                Serial.print("Umbral Luz: "); Serial.println(config.umbral_luz_adc);
                Serial.print("Umbral Temperatura: "); Serial.println(config.temperatura_alerta_celsius);
                request->send(200, "application/json", "{\"message\":\"Parámetros actualizados correctamente\"}");
            } else {
                request->send(200, "application/json", "{\"message\":\"No se realizaron cambios en los parámetros\"}");
            }
        }
    }
  );

  server.on("/api/barrera", HTTP_POST, 
    [](AsyncWebServerRequest *request){}, 
    NULL, 
    [](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total){
        if (index + len == total) {
            StaticJsonDocument<128> jsonDoc;
            DeserializationError error = deserializeJson(jsonDoc, (const char*)data, len);

            if (error) {
                request->send(400, "application/json", "{\"error\":\"Invalid JSON\"}");
                return;
            }

            const char* accion = jsonDoc["accion"]; 

            if (accion) { 
                if (strcmp(accion, "abrir") == 0) {
                    abrirBarrera(); 
                    request->send(200, "application/json", "{\"message\":\"Comando de abrir barrera recibido\"}");
                } else if (strcmp(accion, "cerrar") == 0) {
                    cerrarBarrera(); 
                    request->send(200, "application/json", "{\"message\":\"Comando de cerrar barrera recibido\"}");
                } else {
                    request->send(400, "application/json", "{\"error\":\"Acción no válida para la barrera\"}");
                }
            } else {
                 request->send(400, "application/json", "{\"error\":\"Falta el campo 'accion' en el JSON\"}");
            }
        }
    }
  );

  server.onNotFound(notFound);
}

void notFound(AsyncWebServerRequest *request) {
    request->send(404, "text/plain", "No encontrado");
}

