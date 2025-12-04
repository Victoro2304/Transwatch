const express = require('express');
const cors = require('cors');
const dotenv = require('dotenv');
const { BlobServiceClient, StorageSharedKeyCredential } = require('@azure/storage-blob');

// Cargar variables de entorno
dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middlewares
app.use(cors());
app.use(express.json());
app.use(express.static('../'));

// Configuración de Azure
const accountName = process.env.AZURE_STORAGE_ACCOUNT_NAME;
const sasToken = process.env.AZURE_SAS_TOKEN;
const containerName = process.env.AZURE_CONTAINER_NAME;
const filePrefix = process.env.FILE_PREFIX || 'iot-student-transwatch/01';

// Crear cliente de Azure Storage con SAS Token
const blobServiceClient = new BlobServiceClient(
    `https://${accountName}.blob.core.windows.net${sasToken}`
);

const containerClient = blobServiceClient.getContainerClient(containerName);

/**
 * GET /api/health
 * Verifica que el servidor y Azure estén funcionando
 */
app.get('/api/health', async (req, res) => {
    try {
        // Test de conexión con Azure
        const exists = await containerClient.exists();

        res.json({
            status: 'ok',
            server: 'running',
            azure: exists ? 'connected' : 'container not found',
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({
            status: 'error',
            message: error.message
        });
    }
});

/**
 * GET /api/files/list
 * Lista todos los archivos con un prefijo específico
 * Query params: ?prefix=ruta&maxResults=100
 */
app.get('/api/files/list', async (req, res) => {
    try {
        const prefix = req.query.prefix || filePrefix;
        const maxResults = parseInt(req.query.maxResults) || 100;

        console.log(`Listando archivos con prefijo: ${prefix}`);

        const blobs = [];

        for await (const blob of containerClient.listBlobsFlat({ prefix })) {
            blobs.push({
                name: blob.name,
                size: blob.properties.contentLength,
                lastModified: blob.properties.lastModified,
                contentType: blob.properties.contentType
            });

            if (blobs.length >= maxResults) break;
        }

        console.log(`Encontrados ${blobs.length} archivos`);

        res.json({
            success: true,
            count: blobs.length,
            blobs: blobs
        });

    } catch (error) {
        console.error('Error listando archivos:', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

/**
 * GET /api/files/download
 * Descarga y retorna el contenido de un archivo JSON
 * Query params: ?path=ruta/al/archivo.json
 */
app.get('/api/files/download', async (req, res) => {
    try {
        // El path completo viene del query parameter
        const blobPath = req.query.path;

        if (!blobPath) {
            return res.status(400).json({
                success: false,
                error: 'Se requiere el parámetro "path"'
            });
        }

        console.log(`Descargando archivo: ${blobPath}`);

        const blobClient = containerClient.getBlobClient(blobPath);
        const downloadResponse = await blobClient.download();

        // Convertir stream a texto
        const downloaded = await streamToBuffer(downloadResponse.readableStreamBody);
        const jsonData = parseAzureIoTJson(downloaded.toString());

        res.json({
            success: true,
            data: jsonData,
            metadata: {
                blobName: blobPath,
                size: downloadResponse.contentLength,
                lastModified: downloadResponse.lastModified
            }
        });

    } catch (error) {
        console.error('Error descargando archivo:', error);
        res.status(404).json({
            success: false,
            error: error.message
        });
    }
});

/**
 * GET /api/files/range
 * Busca archivos JSON en un rango de fechas
 * Query params: ?start=2025-12-03T00:00:00&end=2025-12-03T23:59:59
 */
app.get('/api/files/range', async (req, res) => {
    try {
        const { start, end } = req.query;

        if (!start || !end) {
            return res.status(400).json({
                success: false,
                error: 'Se requieren parámetros start y end'
            });
        }

        const startDate = new Date(start);
        const endDate = new Date(end);

        console.log(`Buscando datos entre ${startDate.toISOString()} y ${endDate.toISOString()}`);

        const results = [];
        const days = getDaysInRange(startDate, endDate);

        for (const day of days) {
            const year = day.getFullYear();
            const month = String(day.getMonth() + 1).padStart(2, '0');
            const dayNum = String(day.getDate()).padStart(2, '0');

            const dayPrefix = `${filePrefix}/${year}/${month}/${dayNum}/`;

            // Listar blobs de ese día
            for await (const blob of containerClient.listBlobsFlat({ prefix: dayPrefix })) {
                const blobDate = extractDateFromBlobName(blob.name);

                if (blobDate >= startDate && blobDate <= endDate) {
                    try {
                        // Descargar el blob
                        const blobClient = containerClient.getBlobClient(blob.name);
                        const downloadResponse = await blobClient.download();
                        const downloaded = await streamToBuffer(downloadResponse.readableStreamBody);
                        const jsonData = parseAzureIoTJson(downloaded.toString());

                        results.push({
                            ...jsonData,
                            _blobName: blob.name,
                            _timestamp: blob.properties.lastModified
                        });

                        // Limitar a 200 registros para no sobrecargar
                        if (results.length >= 200) break;

                    } catch (err) {
                        console.warn(`Error procesando ${blob.name}:`, err.message);
                    }
                }
            }

            if (results.length >= 200) break;
        }

        console.log(`Recuperados ${results.length} registros`);

        res.json({
            success: true,
            count: results.length,
            data: results
        });

    } catch (error) {
        console.error('Error en búsqueda por rango:', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

/**
 * GET /api/files/latest
 * Obtiene el último registro disponible
 */
app.get('/api/files/latest', async (req, res) => {
    try {
        console.log('Buscando último registro...');

        const blobs = [];

        for await (const blob of containerClient.listBlobsFlat({ prefix: filePrefix })) {
            blobs.push({
                name: blob.name,
                lastModified: blob.properties.lastModified
            });

            if (blobs.length >= 100) break; // Solo revisar los últimos 100
        }

        if (blobs.length === 0) {
            return res.json({
                success: true,
                data: null,
                message: 'No se encontraron datos'
            });
        }

        // Ordenar por fecha (más reciente primero)
        blobs.sort((a, b) => b.lastModified - a.lastModified);
        const latestBlob = blobs[0];

        // Descargar el más reciente
        const blobClient = containerClient.getBlobClient(latestBlob.name);
        const downloadResponse = await blobClient.download();
        const downloaded = await streamToBuffer(downloadResponse.readableStreamBody);
        const textContent = downloaded.toString();

        // Intentar parsear JSON con manejo de errores mejorado
        let jsonData;
        try {
            jsonData = parseAzureIoTJson(textContent);
        } catch (parseError) {
            console.error(`Error parseando JSON del archivo: ${latestBlob.name}`);
            console.error(`Contenido recibido (primeros 500 chars): ${textContent.substring(0, 500)}`);
            throw new Error(`El archivo ${latestBlob.name} no contiene JSON válido. Error: ${parseError.message}`);
        }

        console.log(`Último registro: ${latestBlob.name}`);

        res.json({
            success: true,
            data: {
                ...jsonData,
                _blobName: latestBlob.name,
                _timestamp: latestBlob.lastModified
            }
        });

    } catch (error) {
        console.error('Error obteniendo último registro:', error);
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});


// AUXILIARES PARA AZURE

/**
 * Parsea JSON de Azure IoT Hub que puede tener metadata adicional
 */
function parseAzureIoTJson(textContent) {
    // Azure puede guardar múltiples objetos JSON separados por líneas
    // Tomar solo la primera línea si hay varias
    const lines = textContent.trim().split('\n');
    const firstLine = lines[0];

    const parsedData = JSON.parse(firstLine);

    // Azure IoT Hub guarda los datos con metadata adicional
    // Los datos reales pueden estar en "Body" codificado en Base64
    if (parsedData.Body) {
        try {
            // El Body viene en Base64, decodificarlo
            const decodedBody = Buffer.from(parsedData.Body, 'base64').toString('utf-8');
            // Parsear el JSON decodificado
            return JSON.parse(decodedBody);
        } catch (err) {
            console.error('Error decodificando Body de Azure:', err.message);
            // Si falla, intentar usar el Body directamente
            return typeof parsedData.Body === 'string'
                ? JSON.parse(parsedData.Body)
                : parsedData.Body;
        }
    }

    // Si no hay Body, usar el objeto completo
    return parsedData;
}

/**
 * Convierte un stream a buffer
 */
async function streamToBuffer(readableStream) {
    return new Promise((resolve, reject) => {
        const chunks = [];
        readableStream.on('data', (data) => {
            chunks.push(data instanceof Buffer ? data : Buffer.from(data));
        });
        readableStream.on('end', () => {
            resolve(Buffer.concat(chunks));
        });
        readableStream.on('error', reject);
    });
}

/**
 * Genera array de días entre dos fechas
 */
function getDaysInRange(start, end) {
    const days = [];
    const current = new Date(start);
    current.setHours(0, 0, 0, 0);

    const endDate = new Date(end);
    endDate.setHours(0, 0, 0, 0);

    while (current <= endDate) {
        days.push(new Date(current));
        current.setDate(current.getDate() + 1);
    }

    return days;
}

/**
 * Extrae la fecha de un nombre de blob
 * Estructura: iot-student-transwatch/01/YYYY/MM/DD/HH/mm.json
 */
function extractDateFromBlobName(blobName) {
    try {
        const parts = blobName.split('/');

        if (parts.length < 7) {
            return new Date(0);
        }

        const year = parseInt(parts[2]);
        const month = parseInt(parts[3]) - 1;
        const day = parseInt(parts[4]);
        const hour = parseInt(parts[5]);
        const minute = parseInt(parts[6].replace('.json', ''));

        return new Date(year, month, day, hour, minute);

    } catch (error) {
        return new Date(0);
    }
}


app.listen(PORT, () => {

    console.log('=================================');
    console.log('Transwatch Server');
    console.log('=================================');
    console.log(`Servidor corriendo en: http://localhost:${PORT}`);
    console.log(`Container de azure: ${containerName}`);
    console.log('=================================');

});
