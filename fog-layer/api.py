# fog-layer/api.py

from flask import Flask, jsonify
from flask_cors import CORS
from services.tsdb_manager import TimeSeriesManager

app = Flask(__name__)
# Habilitar CORS para permitir peticiones desde tu frontend (client-layer)
CORS(app) 

# Instancia del gestor de BD
tsdb = TimeSeriesManager()

@app.route('/api/estadisticas', methods=['GET'])
def obtener_estadisticas():
    print("Recibida petición de estadísticas dashboard...")
    try:
        datos = tsdb.obtener_estadisticas_dashboard()
        return jsonify(datos)
    except Exception as e:
        print(f"Error en API estadísticas: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Iniciando servidor API en puerto 5000...")
    # Escucha en todas las interfaces para que docker o hosts externos conecten
    app.run(host='0.0.0.0', port=5000, debug=True)