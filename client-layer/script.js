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
                y: { type: 'linear', display: true, position: 'left', title: { display: true, text: 'Temp (°C)' } },
                y1: { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'Humedad (%)' } }
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
    initAzureService();
});

// --- FUNCIONES DE INTELIGENCIA ARTIFICIAL ---

function requestAnalysis() {
    const start = document.getElementById('ai-start-date').value;
    const end = document.getElementById('ai-end-date').value;
    const clusters = document.getElementById('ai-clusters').value;

    if (!start || !end) {
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
                y: { title: { display: true, text: 'Temperatura (°C)' } }
            }
        }
    });

    alert("Análisis completado. Revisa las gráficas.");
}

// FUNCIONES AZURE STORAGE

/**
 * Inicializa el servicio Azure Storage via servidor Express
 */
function initAzureService() {

    // Test de conectividad con el servidor
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

/**
 * Actualiza el indicador de estado de Azure en la UI
 */
function updateAzureStatus(type, message) {
    const statusDiv = document.getElementById('azure-status');
    const statusText = document.getElementById('azure-status-text');

    if (!statusDiv || !statusText) return;

    statusText.textContent = message;

    // Cambiar color según el tipo
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

/**
 * Carga datos históricos de Azure por rango de fechas
 * Función llamada desde el botón "Cargar Datos" en la vista de Administrador
 */
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

        // Llamar al servidor Express
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

        // Mostrar datos en la UI
        displayAzureData(data);

        // Opcionalmente: actualizar gráfico con datos históricos
        updateChartWithAzureData(data);

    } catch (error) {
        console.error('Error cargando datos de Azure:', error);
        updateAzureStatus('error', `Error: ${error.message}`);
        alert(`Error al cargar datos: ${error.message}\n\nVerifica que el servidor Express esté corriendo en puerto 3000`);
    }
}

/**
 * Carga el último registro disponible en Azure
 */
async function loadLatestAzureData() {
    try {
        updateAzureStatus('loading', 'Buscando el registro más reciente...');

        // Llamar al servidor Express
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

/**
 * Muestra los datos de Azure en formato tabla/lista
 */
function displayAzureData(data) {
    const previewDiv = document.getElementById('azure-data-preview');

    if (!previewDiv) return;

    if (data.length === 0) {
        previewDiv.innerHTML = '<div style="color: #999; text-align: center;">No hay datos para mostrar</div>';
        return;
    }

    // Crear tabla HTML con los datos
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

/**
 * Actualiza el gráfico de tendencias con datos históricos de Azure
 */
function updateChartWithAzureData(data) {
    if (!chart) return;

    // Limpiar datos actuales
    chart.data.labels = [];
    chart.data.datasets[0].data = [];
    chart.data.datasets[1].data = [];

    // Agregar datos de Azure
    data.slice(0, 50).forEach(item => {
        const timestamp = item._timestamp ? new Date(item._timestamp).toLocaleTimeString() : 'N/A';
        chart.data.labels.push(timestamp);
        chart.data.datasets[0].data.push(item.temperatura_celsius || null);
        chart.data.datasets[1].data.push(item.humedad_porcentaje || null);
    });

    chart.update();

    console.log(`Gráfico actualizado con ${data.length} puntos de Azure`);
}