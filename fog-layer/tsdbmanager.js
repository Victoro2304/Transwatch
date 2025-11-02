// tsdbManager.js - Gestor de Base de Datos de Series Temporales (versión JavaScript)
import 'dotenv/config';
import { InfluxDB, Point } from '@influxdata/influxdb-client';

export class TimeSeriesManager {
  constructor() {
    this.token = process.env.INFLUXDB_TOKEN;
    this.org = process.env.INFLUXDB_ORG || 'transwatch';
    this.bucket = process.env.INFLUXDB_BUCKET || 'parking_data';
    this.url = process.env.INFLUXDB_URL || 'http://localhost:8086';

    this.client = new InfluxDB({ url: this.url, token: this.token });
    this.writeApi = this.client.getWriteApi(this.org, this.bucket, 'ns');
    this.queryApi = this.client.getQueryApi(this.org);
  }

  async almacenarLectura(datos, device_id, qc_status) {
    // Crea un punto para InfluxDB
    const point = new Point('sensor_reading')
      .tag('device_id', device_id)
      .tag('qc_status', qc_status)
      .floatField('temperature', datos.temperatura)
      .floatField('humidity', datos.humedad)
      .floatField('light_level', datos.luz_adc)
      .floatField('distance', datos.distancia_cm)
      .booleanField('vehicle_detected', datos.vehiculo_en_entrada_detectado)
      .booleanField('barrier_open', datos.barrera_abierta)
      .booleanField('lights_on', datos.luces_parking_encendidas)
      .booleanField('alarm_active', datos.alarma_temperatura_activa);

    try {
      this.writeApi.writePoint(point);
      await this.writeApi.flush(); // fuerza el envío
      console.log(`✅ Datos almacenados en InfluxDB para dispositivo ${device_id}`);
      return true;
    } catch (error) {
      console.error('❌ Error almacenando en InfluxDB:', error);
      return false;
    }
  }
}
