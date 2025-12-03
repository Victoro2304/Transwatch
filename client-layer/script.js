// --- VARIABLES DE ESTADO ---
let ws = null;
let chart = null;
let clusterChart = null;
let inferenceChart = null;

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
    
    const btnIndex = ['operator', 'admin', 'tech', 'ai_analytics'].indexOf(tabId);
    
    // Agregamos seguridad por si acaso
    if(btnIndex >= 0) {
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

    // ws.onmessage = (event) => {
    //     try {
    //         const payload = JSON.parse(event.data);

    //         // Manejar Alertas
    //         if (payload.type === 'alert') {
    //             renderAlert(payload.data);
    //         } 
    //         // Manejar Telemetría (JSON completo)
    //         else if (payload.temperatura_celsius !== undefined) {
    //             processTelemetry(payload);
    //         }
    //         // ... código existente ...
    //         else if (payload.temperatura_celsius !== undefined) {
    //             processTelemetry(payload);
    //         }
            
    //         else if (payload.type === 'analysis_result') {
    //             renderMLCharts(payload.data);
    //         }
    //     } catch (e) {
    //         console.error("Error parseando mensaje:", e);
    //     }
    // };
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
            // 3. Manejar Resultados de Inteligencia Artificial (NUEVO)
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

// --- FUNCIONES DE INTELIGENCIA ARTIFICIAL ---

function requestAnalysis() {
    const start = document.getElementById('ai-start-date').value;
    const end = document.getElementById('ai-end-date').value;
    const clusters = document.getElementById('ai-clusters').value;

    if(!start || !end) {
        alert("Por favor selecciona un rango de fechas válido.");
        return;
    }

    // Convertir fechas al formato ISO que espera el backend
    // Agregamos segundos para completar el formato
    const payload = {
        type: "request_analysis",
        start_date: new Date(start).toISOString(),
        end_date: new Date(end).toISOString(),
        n_clusters: clusters
    };
    
    if(ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(payload));
        console.log("Petición de análisis enviada al Fog Layer...");
    } else {
        alert("Error: No hay conexión con el servidor (WebSocket desconectado).");
    }
}

function renderMLCharts(data) {
    if(data.error) { 
        alert("Error del servidor: " + data.error); 
        return; 
    }
    
    const records = data.datos_analizados;
    const predicciones = data.prediccion_futura;

    // --- 1. GRÁFICO CLUSTERING (Scatter Plot) ---
    const ctxCluster = document.getElementById('clusterChart').getContext('2d');
    
    // Preparar colores para los grupos
    const colors = ['#e74c3c', '#3498db', '#2ecc71', '#f1c40f', '#9b59b6'];
    const datasets = [];
    
    // Identificar cuántos grupos únicos devolvió el algoritmo
    const uniqueClusters = [...new Set(records.map(r => r.cluster))];
    
    uniqueClusters.forEach((cId, index) => {
        // Filtramos los puntos que pertenecen a este grupo
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

    if(clusterChart) clusterChart.destroy();
    clusterChart = new Chart(ctxCluster, {
        data: { datasets: datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { title: {display: true, text: 'Temperatura (°C)'}, type: 'linear', position: 'bottom' },
                y: { title: {display: true, text: 'Humedad (%)'} }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `T: ${context.parsed.x}°C, H: ${context.parsed.y}%`;
                        }
                    }
                }
            }
        }
    });

    // --- 2. GRÁFICO INFERENCIA (Línea de Predicción) ---
    const ctxInf = document.getElementById('inferenceChart').getContext('2d');
    
    // Datos Reales (Histórico)
    const datosReales = records.map(r => r.temp_celsius);
    const labels = records.map((r, i) => `T-${i}`); // Etiquetas simples de tiempo

    // Datos Futuros (Predicción)
    // Rellenamos con 'null' la parte histórica para que la línea naranja empiece al final
    const datosPrediccion = Array(labels.length).fill(null);
    const labelsExtendidos = [...labels];
    
    // Conectar el último punto real con la primera predicción visualmente
    datosPrediccion[labels.length - 1] = datosReales[datosReales.length - 1];

    predicciones.forEach((valor, i) => {
        labelsExtendidos.push(`Futuro +${i+1}`);
        datosPrediccion.push(valor);
    });

    if(inferenceChart) inferenceChart.destroy();
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
                    borderDash: [5, 5], // Línea punteada
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
                y: { title: {display: true, text: 'Temperatura (°C)'} }
            }
        }
    });
    
    alert("Análisis completado. Revisa las gráficas.");
}