// client-layer/script.js

// --- VARIABLES DE ESTADO ---
let ws = null;
let clusterChart = null;
let inferenceChart = null;

// Objeto para guardar las instancias de los gráficos del admin
let adminCharts = {
    hourly: null,
    daily: null,
    env: null,
    realtime: null
};

// Contadores para KPIs en tiempo real (Sesión actual)
let stats = {
    totalMsgs: 0,
    passedMsgs: 0,
    entriesToday: 0,
    lastEntryTime: "--:--",
    tempSum: 0,
    tempCount: 0
};

// Estado previo para detectar flancos (entradas de vehículos)
let lastVehicleState = false;

// --- INICIALIZACIÓN DE GRÁFICOS (ADMINISTRADOR) ---
function initAdminCharts() {
    // 1. GRÁFICO DE FLUJO POR HORA
    const ctxHourly = document.getElementById('hourlyFlowChart').getContext('2d');
    adminCharts.hourly = new Chart(ctxHourly, {
        type: 'bar',
        data: {
            labels: ['08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00'],
            datasets: [{
                label: 'Vehículos Promedio',
                data: [], 
                backgroundColor: 'rgba(52, 152, 219, 0.6)',
                borderColor: 'rgba(52, 152, 219, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, title: { display: true, text: 'Cantidad' } } }
        }
    });

    // 2. GRÁFICO DE ENTRADAS DIARIAS
    const ctxDaily = document.getElementById('dailyEntriesChart').getContext('2d');
    adminCharts.daily = new Chart(ctxDaily, {
        type: 'bar',
        data: {
            labels: [], 
            datasets: [{
                label: 'Total Entradas',
                data: [],
                backgroundColor: 'rgba(46, 204, 113, 0.6)',
                borderColor: 'rgba(46, 204, 113, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true } }
        }
    });

    // 3. GRÁFICO AMBIENTAL (SEMANAL - HISTÓRICO)
    const ctxEnv = document.getElementById('environmentalChart').getContext('2d');
    adminCharts.env = new Chart(ctxEnv, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Temp Promedio (°C)',
                    data: [],
                    borderColor: '#e74c3c',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    yAxisID: 'y',
                    tension: 0.3,
                    fill: true
                },
                {
                    label: 'Humedad Promedio (%)',
                    data: [],
                    borderColor: '#3498db',
                    backgroundColor: 'rgba(52, 152, 219, 0.1)',
                    yAxisID: 'y1',
                    tension: 0.3,
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
                y1: { type: 'linear', display: true, position: 'right', grid: {drawOnChartArea: false}, title: {display: true, text: '% Humedad'} }
            }
        }
    });

    // 4. GRÁFICO AMBIENTAL (TIEMPO REAL - NUEVO)
    const ctxRealtime = document.getElementById('realtimeEnvChart').getContext('2d');
    adminCharts.realtime = new Chart(ctxRealtime, {
        type: 'line',
        data: {
            labels: [], // Se llenará en vivo
            datasets: [
                {
                    label: 'Temperatura Vivo (°C)',
                    data: [],
                    borderColor: '#e67e22', // Naranja fuerte
                    borderWidth: 2,
                    pointRadius: 2,
                    yAxisID: 'y',
                    tension: 0.4,
                    fill: false
                },
                {
                    label: 'Humedad Vivo (%)',
                    data: [],
                    borderColor: '#1abc9c', // Verde agua
                    borderWidth: 2,
                    pointRadius: 2,
                    yAxisID: 'y1',
                    tension: 0.4,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false, // Desactivar animación para mejor rendimiento en vivo
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: { title: { display: true, text: 'Hora Actual' } },
                y: { type: 'linear', display: true, position: 'left', title: {display: true, text: 'Temp (°C)'} },
                y1: { type: 'linear', display: true, position: 'right', grid: {drawOnChartArea: false}, title: {display: true, text: '% Humedad'} }
            }
        }
    });
}

// --- CARGA DE DATOS REALES (INFLUXDB -> API) ---
async function loadRealData() {
    try {
        const response = await fetch('http://localhost:5000/api/estadisticas');
        
        if (!response.ok) {
            throw new Error(`Error HTTP: ${response.status}`);
        }

        const data = await response.json();
        console.log("✅ Datos históricos recibidos:", data);

        // ACTUALIZAR GRÁFICO 1: FLUJO POR HORA
        if (data.flujo_hora) {
            adminCharts.hourly.data.labels = data.flujo_hora.labels;
            adminCharts.hourly.data.datasets[0].data = data.flujo_hora.valores;
            adminCharts.hourly.update();

            const maxTraffic = Math.max(...data.flujo_hora.valores);
            const peakIndex = data.flujo_hora.valores.indexOf(maxTraffic);
            const peakLabel = data.flujo_hora.labels[peakIndex] || "--:--";
            document.getElementById('admin-peak-hour').textContent = peakLabel;
        }

        // ACTUALIZAR GRÁFICO 2: ENTRADAS DIARIAS
        if (data.entradas_diarias) {
            adminCharts.daily.data.labels = data.entradas_diarias.labels;
            adminCharts.daily.data.datasets[0].data = data.entradas_diarias.valores;
            adminCharts.daily.update();

            const hoy = data.entradas_diarias.valores[data.entradas_diarias.valores.length - 1] || 0;
            document.getElementById('admin-entries-today').textContent = hoy;
            stats.entriesToday = hoy;
        }

        // ACTUALIZAR GRÁFICO 3: AMBIENTAL SEMANAL (Histórico)
        if (data.ambiental) {
            adminCharts.env.data.labels = data.ambiental.labels;
            adminCharts.env.data.datasets[0].data = data.ambiental.temp;
            adminCharts.env.data.datasets[1].data = data.ambiental.hum;
            adminCharts.env.update();

            const temps = data.ambiental.temp;
            if (temps.length > 0) {
                const avgTemp = (temps.reduce((a, b) => a + b, 0) / temps.length).toFixed(1);
                document.getElementById('admin-weekly-avg').textContent = avgTemp + " °C";
            }
        }

    } catch (error) {
        console.error("Error cargando datos históricos:", error);
    }
}

// --- GESTIÓN DE PESTAÑAS ---
function switchTab(tabId) {
    document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');

    const btnIndex = ['operator', 'admin', 'tech', 'ai_analytics'].indexOf(tabId);
    if (btnIndex >= 0) {
        document.querySelectorAll('.nav-btn')[btnIndex].classList.add('active');
    }
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

            // 1. Manejar Alertas
            if (payload.type === 'alert') {
                renderAlert(payload.data);
            }
            // 2. Manejar Telemetría (JSON completo)
            else if (payload.temperatura_celsius !== undefined) {
                processTelemetry(payload);
            }
            // 3. Manejar Resultados de Inteligencia Artificial
            else if (payload.type === 'analysis_result') {
                renderMLCharts(payload.data);
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

    // 3. ACTUALIZAR ADMINISTRADOR (KPIs)
    updateAdminCards(data, now);

    // 4. ACTUALIZAR ADMINISTRADOR (GRÁFICO EN VIVO)
    updateRealtimeAdminChart(now, data.temperatura_celsius, data.humedad_porcentaje);
}

// --- NUEVA FUNCIÓN PARA EL GRÁFICO ADMIN EN VIVO ---
function updateRealtimeAdminChart(label, temp, hum) {
    if (!adminCharts.realtime) return;

    // Agregar nuevos datos
    adminCharts.realtime.data.labels.push(label);
    adminCharts.realtime.data.datasets[0].data.push(temp);
    adminCharts.realtime.data.datasets[1].data.push(hum);

    // Limitar a los últimos 20 puntos para que se vea el efecto de desplazamiento
    const MAX_POINTS = 20;
    if (adminCharts.realtime.data.labels.length > MAX_POINTS) {
        adminCharts.realtime.data.labels.shift();
        adminCharts.realtime.data.datasets[0].data.shift();
        adminCharts.realtime.data.datasets[1].data.shift();
    }

    // Actualizar gráfico
    adminCharts.realtime.update();
}

function updateOperatorView(data) {
    const elBarrera = document.getElementById('op-barrera');
    if (data.barrera_abierta) {
        elBarrera.textContent = "ABIERTA";
        elBarrera.style.color = "#27ae60"; 
    } else {
        elBarrera.textContent = "CERRADA";
        elBarrera.style.color = "#c0392b"; 
    }

    const elVehiculo = document.getElementById('op-vehiculo');
    if (data.vehiculo_en_entrada_detectado) {
        elVehiculo.textContent = "VEHÍCULO DETECTADO";
        elVehiculo.style.color = "#f39c12"; 
    } else {
        elVehiculo.textContent = "LIBRE";
        elVehiculo.style.color = "#27ae60"; 
    }

    document.getElementById('op-temp').textContent = data.temperatura_celsius.toFixed(1) + " °C";
    document.getElementById('op-hum').textContent = "Humedad: " + data.humedad_porcentaje.toFixed(1) + " %";
}

function updateTechView(data, timestamp) {
    stats.totalMsgs++;
    const qcApproved = data.qc_approved !== false; 
    if (qcApproved) stats.passedMsgs++;

    const qcRate = ((stats.passedMsgs / stats.totalMsgs) * 100).toFixed(1);
    document.getElementById('tech-qc-rate').textContent = qcRate + "%";
    document.getElementById('tech-total-msgs').textContent = stats.totalMsgs;
    document.getElementById('tech-rejected-msgs').textContent = (stats.totalMsgs - stats.passedMsgs);

    if (!qcApproved) {
        const logDiv = document.getElementById('tech-qc-log');
        const msg = document.createElement('div');
        msg.textContent = `[${timestamp}] Fallo: ${data.qc_message || 'Desconocido'}`;
        msg.style.borderBottom = "1px solid #eee";
        logDiv.prepend(msg);
    }

    toggleActuator('icon-barrier', data.barrera_abierta, 'actuator-on', 'actuator-off');
    toggleActuator('icon-light', data.luces_parking_encendidas, 'actuator-on', 'actuator-off');
    toggleActuator('icon-buzzer', data.alarma_temperatura_activa, 'actuator-alert', 'actuator-off');

    const rawLog = document.getElementById('tech-raw-log');
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    const qcClass = qcApproved ? '' : 'log-error';
    entry.innerHTML = `<span class="${qcClass}">[${timestamp}] QC:${qcApproved ? 'OK' : 'FAIL'} | T:${data.temperatura_celsius} | H:${data.humedad_porcentaje} | D:${data.distancia_cm}</span>`;

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

function updateAdminCards(data, timestamp) {
    // KPI: Entradas Hoy (Incrementar si hay flanco positivo)
    if (data.vehiculo_en_entrada_detectado && !lastVehicleState) {
        stats.entriesToday++;
        document.getElementById('admin-entries-today').textContent = stats.entriesToday;
    }
    lastVehicleState = data.vehiculo_en_entrada_detectado;
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
    initAdminCharts();
    loadRealData(); // Cargar datos históricos desde API
    connectWS();
    initAzureService();
});

// --- FUNCIONES DE INTELIGENCIA ARTIFICIAL (MANTENIDAS) ---

function requestAnalysis() {
    const start = document.getElementById('ai-start-date').value;
    const end = document.getElementById('ai-end-date').value;
    const clusters = document.getElementById('ai-clusters').value;

    if (!start || !end) {
        alert("Por favor selecciona un rango de fechas válido.");
        return;
    }

    const payload = {
        type: "request_analysis",
        start_date: new Date(start).toISOString(),
        end_date: new Date(end).toISOString(),
        n_clusters: clusters
    };

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(payload));
        console.log("Petición de análisis enviada al Fog Layer...");
    } else {
        alert("Error: No hay conexión con el servidor (WebSocket desconectado).");
    }
}

function renderMLCharts(data) {
    if (data.error) {
        alert("Error del servidor: " + data.error);
        return;
    }

    const records = data.datos_analizados;
    const predicciones = data.prediccion_futura;

    const ctxCluster = document.getElementById('clusterChart').getContext('2d');
    const colors = ['#e74c3c', '#3498db', '#2ecc71', '#f1c40f', '#9b59b6'];
    const datasets = [];

    const uniqueClusters = [...new Set(records.map(r => r.cluster))];

    uniqueClusters.forEach((cId, index) => {
        const clusterPoints = records
            .filter(r => r.cluster === cId)
            .map(r => ({ x: r.temp_celsius, y: r.humedad_porcentaje }));

        datasets.push({
            label: `Grupo ${cId + 1}`,
            data: clusterPoints,
            backgroundColor: colors[index % colors.length],
            pointRadius: 5,
            type: 'scatter'
        });
    });

    if (clusterChart) clusterChart.destroy();
    clusterChart = new Chart(ctxCluster, {
        data: { datasets: datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { title: { display: true, text: 'Temperatura (°C)' }, type: 'linear', position: 'bottom' },
                y: { title: { display: true, text: 'Humedad (%)' } }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            return `T: ${context.parsed.x}°C, H: ${context.parsed.y}%`;
                        }
                    }
                }
            }
        }
    });

    const ctxInf = document.getElementById('inferenceChart').getContext('2d');
    const datosReales = records.map(r => r.temp_celsius);
    const labels = records.map((r, i) => `T-${i}`); 

    const datosPrediccion = Array(labels.length).fill(null);
    const labelsExtendidos = [...labels];

    datosPrediccion[labels.length - 1] = datosReales[datosReales.length - 1];

    predicciones.forEach((valor, i) => {
        labelsExtendidos.push(`Futuro +${i + 1}`);
        datosPrediccion.push(valor);
    });

    if (inferenceChart) inferenceChart.destroy();
    inferenceChart = new Chart(ctxInf, {
        type: 'line',
        data: {
            labels: labelsExtendidos,
            datasets: [
                {
                    label: 'Histórico Real',
                    data: datosReales,
                    borderColor: '#34495e',
                    backgroundColor: 'rgba(52, 73, 94, 0.2)',
                    tension: 0.3,
                    fill: true
                },
                {
                    label: 'Predicción AI',
                    data: datosPrediccion,
                    borderColor: '#e67e22',
                    borderDash: [5, 5], 
                    pointBackgroundColor: '#e67e22',
                    tension: 0.1,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { title: { display: true, text: 'Temperatura (°C)' } }
            }
        }
    });

    alert("Análisis completado. Revisa las gráficas.");
}

// FUNCIONES AZURE STORAGE (MANTENIDAS)
function initAzureService() {
    fetch('http://localhost:3000/api/health')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'ok' && data.azure === 'connected') {
                updateAzureStatus('success', 'Conectado exitosamente a Azure vía servidor Express');
                console.log('Servidor Express conectado a Azure');
            } else {
                updateAzureStatus('error', 'Servidor conectado pero Azure no disponible');
            }
        })
        .catch(error => {
            updateAzureStatus('error', 'No se puede conectar al servidor Express. ¿Está corriendo en puerto 3000?');
            console.error('Error conectando al servidor:', error);
        });
}

function updateAzureStatus(type, message) {
    const statusDiv = document.getElementById('azure-status');
    const statusText = document.getElementById('azure-status-text');

    if (!statusDiv || !statusText) return;

    statusText.textContent = message;

    if (type === 'success') {
        statusDiv.style.background = '#e6f4ea';
        statusDiv.style.color = '#1e8e3e';
        statusDiv.style.borderLeft = '4px solid #1e8e3e';
    } else if (type === 'error') {
        statusDiv.style.background = '#fce8e6';
        statusDiv.style.color = '#d93025';
        statusDiv.style.borderLeft = '4px solid #d93025';
    } else if (type === 'loading') {
        statusDiv.style.background = '#e8f4fd';
        statusDiv.style.color = '#0078d4';
        statusDiv.style.borderLeft = '4px solid #0078d4';
    } else {
        statusDiv.style.background = '#f5f5f5';
        statusDiv.style.color = '#666';
        statusDiv.style.borderLeft = '4px solid #ccc';
    }
}

async function loadAzureHistoricalData() {
    const startInput = document.getElementById('azure-start-date').value;
    const endInput = document.getElementById('azure-end-date').value;

    if (!startInput || !endInput) {
        alert('Por favor selecciona un rango de fechas válido');
        return;
    }

    const startDate = new Date(startInput);
    const endDate = new Date(endInput);

    if (startDate > endDate) {
        alert('La fecha de inicio debe ser anterior a la fecha de fin');
        return;
    }

    try {
        updateAzureStatus('loading', `Buscando datos entre ${startDate.toLocaleString()} y ${endDate.toLocaleString()}...`);

        const response = await fetch(`http://localhost:3000/api/files/range?start=${startDate.toISOString()}&end=${endDate.toISOString()}`);
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Error desconocido');
        }

        const data = result.data;

        if (data.length === 0) {
            updateAzureStatus('info', 'No se encontraron datos en el rango especificado');
            displayAzureData([]);
            return;
        }

        updateAzureStatus('success', `${data.length} registros cargados exitosamente desde Azure`);
        displayAzureData(data);

    } catch (error) {
        console.error('Error cargando datos de Azure:', error);
        updateAzureStatus('error', `Error: ${error.message}`);
        alert(`Error al cargar datos: ${error.message}\n\nVerifica que el servidor Express esté corriendo en puerto 3000`);
    }
}

async function loadLatestAzureData() {
    try {
        updateAzureStatus('loading', 'Buscando el registro más reciente...');

        const response = await fetch('http://localhost:3000/api/files/latest');
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Error desconocido');
        }

        const latestData = result.data;

        if (!latestData) {
            updateAzureStatus('info', 'No se encontraron datos en Azure');
            displayAzureData([]);
            return;
        }

        updateAzureStatus('success', 'Último registro cargado exitosamente');
        displayAzureData([latestData]);

    } catch (error) {
        console.error('Error cargando último registro:', error);
        updateAzureStatus('error', `Error: ${error.message}`);
    }
}

function displayAzureData(data) {
    const previewDiv = document.getElementById('azure-data-preview');

    if (!previewDiv) return;

    if (data.length === 0) {
        previewDiv.innerHTML = '<div style="color: #999; text-align: center;">No hay datos para mostrar</div>';
        return;
    }

    let html = '<table style="width: 100%; border-collapse: collapse; font-size: 0.85em;">';
    html += '<thead><tr style="background: #0078d4; color: white; text-align: left;">';
    html += '<th style="padding: 8px;">Fecha/Hora</th>';
    html += '<th style="padding: 8px;">Temp (°C)</th>';
    html += '<th style="padding: 8px;">Humedad (%)</th>';
    html += '<th style="padding: 8px;">Distancia (cm)</th>';
    html += '<th style="padding: 8px;">Vehículo</th>';
    html += '<th style="padding: 8px;">Barrera</th>';
    html += '</tr></thead><tbody>';

    data.slice(0, 100).forEach((item, index) => {
        const rowColor = index % 2 === 0 ? '#f9f9f9' : '#ffffff';
        const timestamp = item._timestamp ? new Date(item._timestamp).toLocaleString() : 'N/A';
        const vehiculo = item.vehiculo_en_entrada_detectado ? 'Sí' : 'No';
        const barrera = item.barrera_abierta ? 'Abierta' : 'Cerrada';

        html += `<tr style="background: ${rowColor};">`;
        html += `<td style="padding: 8px; border-bottom: 1px solid #eee;">${timestamp}</td>`;
        html += `<td style="padding: 8px; border-bottom: 1px solid #eee;">${item.temperatura_celsius?.toFixed(1) || 'N/A'}</td>`;
        html += `<td style="padding: 8px; border-bottom: 1px solid #eee;">${item.humedad_porcentaje?.toFixed(1) || 'N/A'}</td>`;
        html += `<td style="padding: 8px; border-bottom: 1px solid #eee;">${item.distancia_cm?.toFixed(0) || 'N/A'}</td>`;
        html += `<td style="padding: 8px; border-bottom: 1px solid #eee;">${vehiculo}</td>`;
        html += `<td style="padding: 8px; border-bottom: 1px solid #eee;">${barrera}</td>`;
        html += '</tr>';
    });

    html += '</tbody></table>';

    if (data.length > 100) {
        html += `<div style="text-align: center; padding: 10px; color: #666; background: #fff3cd;">
            Mostrando los primeros 100 de ${data.length} registros
        </div>`;
    }

    previewDiv.innerHTML = html;
}