// --- VARIABLES DE ESTADO ---
let ws = null;
let chart = null;

// Contadores para KPIs
let stats = {
    totalMsgs: 0,
    passedMsgs: 0,
    entriesToday: 0,
    lastEntryTime: "--:--",
    tempSum: 0,
    tempCount: 0
};

// Estado previo para detectar entradas de vehículos
let lastVehicleState = false;

// --- INICIALIZACIÓN ---
function initChart() {
    const ctx = document.getElementById('businessChart').getContext('2d');
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Temperatura (°C)',
                    data: [],
                    borderColor: '#e74c3c', // Rojo suave
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    yAxisID: 'y',
                    tension: 0.4,
                    fill: true
                },
                {
                    label: 'Humedad (%)',
                    data: [],
                    borderColor: '#3498db', // Azul
                    backgroundColor: 'rgba(52, 152, 219, 0.1)',
                    yAxisID: 'y1',
                    tension: 0.4,
                    fill: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                y: { type: 'linear', display: true, position: 'left', title: {display: true, text: 'Temp (°C)'} },
                y1: { type: 'linear', display: true, position: 'right', grid: {drawOnChartArea: false}, title: {display: true, text: 'Humedad (%)'} }
            }
        }
    });
}

function switchTab(tabId) {
    document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    
    // Activar botón correspondiente
    const btnIndex = ['operator', 'admin', 'tech'].indexOf(tabId);
    document.querySelectorAll('.nav-btn')[btnIndex].classList.add('active');
}

// --- LÓGICA DE WEBSOCKET ---
function connectWS() {
    ws = new WebSocket('ws://localhost:8765');

    ws.onopen = () => {
        document.getElementById('connection-status').className = 'status-badge status-connected';
        document.getElementById('connection-status').innerHTML = '<i class="fas fa-wifi"></i> Conectado';
        console.log("WS Conectado");
    };

    ws.onclose = () => {
        document.getElementById('connection-status').className = 'status-badge status-disconnected';
        document.getElementById('connection-status').innerHTML = '<i class="fas fa-times-circle"></i> Desconectado';
        setTimeout(connectWS, 3000);
    };

    ws.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data);

            // Manejar Alertas
            if (payload.type === 'alert') {
                renderAlert(payload.data);
            } 
            // Manejar Telemetría (JSON completo)
            else if (payload.temperatura_celsius !== undefined) {
                processTelemetry(payload);
            }
        } catch (e) {
            console.error("Error parseando mensaje:", e);
        }
    };
}

// --- PROCESAMIENTO CENTRAL DE DATOS ---
function processTelemetry(data) {
    const now = new Date().toLocaleTimeString();

    // 1. ACTUALIZAR OPERADOR
    updateOperatorView(data);

    // 2. ACTUALIZAR TÉCNICO
    updateTechView(data, now);

    // 3. ACTUALIZAR ADMINISTRADOR (Estadísticas acumuladas en sesión)
    updateAdminLogic(data, now);
    
    // 4. ACTUALIZAR GRÁFICO
    updateChart(now, data.temperatura_celsius, data.humedad_porcentaje);
}

function updateOperatorView(data) {
    // Barrera
    const elBarrera = document.getElementById('op-barrera');
    if (data.barrera_abierta) {
        elBarrera.textContent = "ABIERTA";
        elBarrera.style.color = "#27ae60"; // Verde
    } else {
        elBarrera.textContent = "CERRADA";
        elBarrera.style.color = "#c0392b"; // Rojo
    }

    // Vehículo
    const elVehiculo = document.getElementById('op-vehiculo');
    if (data.vehiculo_en_entrada_detectado) {
        elVehiculo.textContent = "VEHÍCULO DETECTADO";
        elVehiculo.style.color = "#f39c12"; // Naranja
    } else {
        elVehiculo.textContent = "LIBRE";
        elVehiculo.style.color = "#27ae60"; // Verde
    }

    // Ambiente
    document.getElementById('op-temp').textContent = data.temperatura_celsius.toFixed(1) + " °C";
    document.getElementById('op-hum').textContent = "Humedad: " + data.humedad_porcentaje.toFixed(1) + " %";
}

function updateTechView(data, timestamp) {
    // KPI: Calidad de Datos
    stats.totalMsgs++;
    const qcApproved = data.qc_approved !== false; // Asumir true si no viene
    if (qcApproved) stats.passedMsgs++;

    const qcRate = ((stats.passedMsgs / stats.totalMsgs) * 100).toFixed(1);
    document.getElementById('tech-qc-rate').textContent = qcRate + "%";
    document.getElementById('tech-total-msgs').textContent = stats.totalMsgs;
    document.getElementById('tech-rejected-msgs').textContent = (stats.totalMsgs - stats.passedMsgs);

    // Bitácora de Fallos
    if (!qcApproved) {
        const logDiv = document.getElementById('tech-qc-log');
        const msg = document.createElement('div');
        msg.textContent = `[${timestamp}] Fallo: ${data.qc_message || 'Desconocido'}`;
        msg.style.borderBottom = "1px solid #eee";
        logDiv.prepend(msg);
    }

    // KPI: Actuadores (Iconos)
    toggleActuator('icon-barrier', data.barrera_abierta, 'actuator-on', 'actuator-off');
    toggleActuator('icon-light', data.luces_parking_encendidas, 'actuator-on', 'actuator-off');
    toggleActuator('icon-buzzer', data.alarma_temperatura_activa, 'actuator-alert', 'actuator-off');

    // Log Crudo 
    const rawLog = document.getElementById('tech-raw-log');
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    const qcClass = qcApproved ? '' : 'log-error';
    // Mostrar datos clave en una línea para fácil lectura
    entry.innerHTML = `<span class="${qcClass}">[${timestamp}] QC:${qcApproved?'OK':'FAIL'} | T:${data.temperatura_celsius} | H:${data.humedad_porcentaje} | D:${data.distancia_cm}</span>`;
    
    rawLog.insertBefore(entry, rawLog.firstChild);
    if (rawLog.children.length > 50) rawLog.removeChild(rawLog.lastChild);
}

function toggleActuator(id, state, classOn, classOff) {
    const el = document.getElementById(id);
    if (state) {
        el.classList.remove(classOff);
        el.classList.add(classOn);
    } else {
        el.classList.remove(classOn);
        el.classList.add(classOff);
    }
}

function updateAdminLogic(data, timestamp) {
    // Detectar entrada 
    if (data.vehiculo_en_entrada_detectado && !lastVehicleState) {
        stats.entriesToday++;
        stats.lastEntryTime = timestamp;
        document.getElementById('admin-total-entries').textContent = stats.entriesToday;
        document.getElementById('admin-last-entry').textContent = stats.lastEntryTime;
    }
    lastVehicleState = data.vehiculo_en_entrada_detectado;

    // Promedio Temp (Acumulado sesión)
    if (data.temperatura_celsius) {
        stats.tempSum += data.temperatura_celsius;
        stats.tempCount++;
        const avg = (stats.tempSum / stats.tempCount).toFixed(1);
        document.getElementById('admin-avg-temp').textContent = avg + " °C";
    }
}

function updateChart(label, temp, hum) {
    if (!chart) return;
    
    chart.data.labels.push(label);
    chart.data.datasets[0].data.push(temp);
    chart.data.datasets[1].data.push(hum);

    // Mantener últimos 20 puntos
    if (chart.data.labels.length > 20) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
        chart.data.datasets[1].data.shift();
    }
    chart.update('none'); // Animación suave
}

function renderAlert(alertData) {
    const list = document.getElementById('alerts-list');
    const item = document.createElement('div');
    
    let typeClass = 'alert-info';
    let icon = 'fa-info-circle';
    
    if (alertData.priority === 'high') { typeClass = 'alert-warning'; icon = 'fa-exclamation-triangle'; }
    if (alertData.priority === 'critical') { typeClass = 'alert-critical'; icon = 'fa-fire'; }

    item.className = `alert-item ${typeClass}`;
    item.innerHTML = `
        <div style="font-weight:bold;"><i class="fas ${icon}"></i> ${alertData.message}</div>
        <small>${new Date().toLocaleTimeString()} - Prioridad: ${alertData.priority}</small>
    `;
    
    list.insertBefore(item, list.firstChild);
    if (list.children.length > 10) list.removeChild(list.lastChild);
}

// Arranque
window.addEventListener('load', () => {
    initChart();
    connectWS();
});