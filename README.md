# Transwatch

> Sistema de Monitoreo Inteligente para Estacionamientos y Casetas de Tráfico

Transwatch es un proyecto IoT integral que proporciona visualización de datos y gestión de información enfocada en estacionamientos y casetas de tráfico, ofreciendo evaluación de tráfico, consideraciones ambientales y soporte con iluminación y sensores.

---

## 📋 Tabla de Contenidos

- [Arquitectura del Proyecto](#arquitectura-del-proyecto)
- [Estructura de Carpetas](#estructura-de-carpetas)
- [Capas del Sistema](#capas-del-sistema)
- [Tecnologías Utilizadas](#tecnologías-utilizadas)
- [Instalación y Configuración](#instalación-y-configuración)
- [Uso](#uso)

---

## 🏗️ Arquitectura del Proyecto

Transwatch está diseñado siguiendo una arquitectura IoT de 5 capas:

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                         │
│  Dashboard Web - Visualización y Control del Usuario   │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ HTTP REST API
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    CLOUD LAYER                          │
│  Azure Storage - Almacenamiento Persistente de Datos   │
│  Azure IoT Hub - Ingesta de Telemetría                 │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ Azure SDK / MQTT
                          ▼
┌─────────────────────────────────────────────────────────┐
│                     FOG LAYER                           │
│  Procesamiento Local - Edge Computing - ML Engine      │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ MQTT/Serial
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  PHYSICAL LAYER                         │
│   Arduino - Sensores - Actuadores - Hardware IoT       │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 Estructura de Carpetas

```
Transwatch/
│
├── client-layer/               # Capa de Presentación
│   ├── index.html             # Dashboard principal
│   ├── script.js              # Lógica del frontend
│   ├── styles.css             # Estilos de la interfaz
│   └── src/                   # Servidor backend Express
│       ├── server.js          # API REST para Azure Storage
│       ├── package.json       # Dependencias Node.js
│       └── .env               # Variables de entorno (no incluido en Git)
│
├── fog-layer/                  # Capa de Procesamiento Edge
│   ├── data_collector.py      # Recolector de datos MQTT
│   ├── gui_parking.py         # Interfaz gráfica del sistema
│   ├── docker-compose.yml     # Configuración de contenedores
│   ├── services/              # Servicios del sistema
│   │   ├── ml_engine.py       # Motor de Machine Learning
│   │   ├── notification_engine.py  # Sistema de notificaciones
│   │   └── tsdb_manager.py    # Gestor de base de datos temporal
│   ├── quality/               # Control de calidad
│   │   └── qc.py              # Validación de datos
│   └── tests/                 # Pruebas y testing
│       ├── test_mqtt.py       # Pruebas de MQTT
│       └── recolector_datos.py # Pruebas de recolección
│
├── physical-layer/             # Capa Física
│   └── Proyecto_Final.ino     # Código Arduino para sensores/actuadores
│
├── .gitignore                 # Archivos ignorados por Git
├── LICENSE                    # Licencia del proyecto
└── README.md                  # Este archivo
```

---

## 🔧 Capas del Sistema

### **1. Physical Layer (Capa Física)**

**Hardware:**
- Arduino Uno/Mega
- Sensor Ultrasónico HC-SR04 (Detección de vehículos)
- Sensor DHT11/DHT22 (Temperatura y Humedad)
- Servo Motor (Control de barrera)
- LEDs de señalización

**Responsabilidades:**
- Captura de datos ambientales
- Detección de presencia vehicular
- Control de actuadores (barrera, iluminación)
- Comunicación serial con Fog Layer

**Tecnología:** C/C++ (Arduino IDE)

---

### **2. Fog Layer (Capa de Procesamiento Edge)**

**Componentes:**
- **Data Collector:** Recopila datos desde Arduino vía MQTT
- **ML Engine:** Análisis predictivo con scikit-learn
- **TSDB Manager:** Gestión de base de datos InfluxDB
- **Notification Engine:** Sistema de alertas
- **Quality Control:** Validación y limpieza de datos

**Responsabilidades:**
- Procesamiento en tiempo real
- Almacenamiento en InfluxDB (Time Series Database)
- Análisis de clustering y predicciones
- Sincronización con Azure IoT Hub
- WebSocket para comunicación con Client Layer

**Tecnologías:**
- Python 3.x
- MQTT (Mosquitto)
- InfluxDB 3.x
- scikit-learn, pandas, numpy
- WebSocket

---

### **3. Cloud Layer (Capa de Nube)**

**Componentes:**
- **Azure Storage Account:** Almacenamiento persistente de datos históricos
- **Azure IoT Hub:** Ingesta de telemetría desde dispositivos IoT
- **Container Storage:** Organización jerárquica de archivos JSON por fecha/hora

**Responsabilidades:**
- Almacenamiento escalable de datos históricos
- Recepción de telemetría desde Fog Layer vía MQTT
- Proveer datos históricos al Client Layer mediante API REST
- Garantizar disponibilidad y durabilidad de datos
- Control de acceso mediante SAS Tokens

**Tecnologías:**
- Azure Storage (almacenamiento de archivos)
- Azure IoT Hub (ingesta de telemetría)
- SAS Token (autenticación segura)
- Estructura de datos: JSON con formato NDJSON

**Estructura de Almacenamiento:**
```
Container: datatranswatch
└── iot-student-transwatch/
    └── 01/
        └── YYYY/
            └── MM/
                └── DD/
                    └── HH/
                        └── mm.json
```

---

### **4. Client Layer (Capa de Presentación)**

**Frontend:**
- Dashboard interactivo HTML5/CSS3/JavaScript
- Visualización con Chart.js
- Tabs por rol: Operador, Administrador, Técnico, Análisis IA
- Integración con Azure Storage para datos históricos

**Backend (Express Server):**
- API REST para comunicación con Azure Storage
- SDK de Azure (@azure/storage-blob) para acceso a la nube
- Endpoints para descarga de datos históricos
- Autenticación con SAS Token
- Parsing de formato NDJSON y decodificación Base64
- Servicio de archivos estáticos

**Responsabilidades:**
- Visualización en tiempo real (WebSocket)
- Consulta de datos históricos (Azure Storage)
- Control de dispositivos
- Generación de reportes

**Tecnologías:**
- HTML5, CSS3, JavaScript (Vanilla)
- Node.js + Express.js
- Azure Storage SDK
- Chart.js para gráficas
- WebSocket para tiempo real

---

## 🛠️ Tecnologías Utilizadas

| Capa | Tecnología | Propósito |
|------|------------|-----------|
| **Physical** | Arduino C/C++ | Control de hardware |
| **Fog** | Python 3.x | Procesamiento de datos |
| **Fog** | InfluxDB | Base de datos temporal |
| **Fog** | MQTT | Protocolo de comunicación |
| **Fog** | scikit-learn | Machine Learning |
| **Cloud** | Azure Storage | Almacenamiento persistente |
| **Cloud** | Azure IoT Hub | Ingesta de telemetría |
| **Cloud** | SAS Token | Autenticación segura |
| **Client** | Node.js + Express | Backend API |
| **Client** | @azure/storage-blob | SDK de Azure |
| **Client** | HTML/CSS/JS | Frontend Web |
| **Client** | Chart.js | Visualización de datos |

---

## 🚀 Instalación y Configuración

### **Requisitos Previos**

- Python 3.8+
- Node.js 16+
- Arduino IDE
- Docker (opcional, para InfluxDB)
- Cuenta de Azure (para almacenamiento en nube)

### **1. Configurar Physical Layer**

```bash
# Abrir Arduino IDE
# Cargar physical-layer/Proyecto_Final.ino
# Conectar Arduino y subir el sketch
```

### **2. Configurar Fog Layer**

```bash
cd fog-layer

# Instalar dependencias Python
pip install -r requirements.txt  # (crear si no existe)
pip install scikit-learn pandas numpy paho-mqtt influxdb-client-3

# Configurar InfluxDB (si usas Docker)
docker-compose up -d

# Ejecutar data collector
python data_collector.py
```

### **3. Configurar Client Layer**

```bash
cd client-layer/src

# Instalar dependencias Node.js
npm install

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales de Azure

# Iniciar servidor
npm start
```

### **4. Configurar Azure Storage**

1. Crear Storage Account en Azure Portal
2. Generar SAS Token con permisos de lectura
3. Configurar CORS en Azure Storage
4. Copiar credenciales a `client-layer/src/.env`

---

## 💻 Uso

### **Iniciar el Sistema Completo**

1. **Physical Layer:** Conectar Arduino y mantener encendido
2. **Fog Layer:** 
   ```bash
   python data_collector.py
   ```
3. **Client Layer:**
   ```bash
   cd client-layer/src
   npm start
   ```
4. Abrir navegador en `http://localhost:3000`

### **Dashboard Web**

- **Vista Operador:** Monitoreo en tiempo real de sensores
- **Vista Administrador:** Datos históricos desde Azure
- **Vista Técnico:** Configuración de sistema
- **Vista Análisis IA:** Clustering y predicciones

---

## 📊 Flujo de Datos

```
Arduino Sensors → Serial/MQTT → Python Data Collector → InfluxDB (Local)
                                         ↓
                                  Azure IoT Hub (MQTT)
                                         ↓
                              Azure Storage (Container)
                                         ↓
                         Express Server (@azure/storage-blob SDK)
                                         ↓
                              Web Dashboard (Frontend)
```

**Descripción del Flujo:**

1. **Physical → Fog:** Sensores Arduino envían datos vía Serial/MQTT
2. **Fog → Local DB:** Python almacena en InfluxDB para análisis en tiempo real
3. **Fog → Cloud:** Python envía telemetría a Azure IoT Hub
4. **Cloud Storage:** Azure IoT Hub almacena datos en Azure Storage (formato NDJSON)
5. **Cloud → Client:** Express Server consulta Azure Storage mediante SDK oficial
6. **Client → User:** Dashboard muestra datos históricos al usuario

---

## 👥 Equipo

**Equipo 1** - Proyecto IoT

---

## 📄 Licencia

Este proyecto está bajo la licencia especificada en el archivo [LICENSE](LICENSE).

---

## 🤝 Contribuciones

Este es un proyecto educativo. Para contribuir, contacta al equipo del proyecto.

---

**Transwatch** - Sistema de Monitoreo Inteligente © 2025