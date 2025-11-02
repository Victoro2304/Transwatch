# qc_simple.py - Control de Calidad Simplificado

class SimpleQualityControl:
    def __init__(self, window_size=10, z_threshold=2.5):
        self.window_size = window_size
        self.z_threshold = z_threshold
        self.sensor_data = {
            'temperatura': [],
            'humedad': [],
            'luz_adc': [],
            'distancia_cm': []
        }

    def aplicar_qc(self, datos):
        resultados = {}

        for sensor, valor in datos.items():
            if sensor not in self.sensor_data:
                continue

            ventana = self.sensor_data[sensor]

            # Si no hay suficientes datos, aceptar el valor
            if len(ventana) < 5:
                ventana.append(valor)
                resultados[sensor] = {
                    'aprobado': True,
                    'razon': 'Datos insuficientes'
                }
                continue

            # Calcular media y desviación estándar
            promedio = sum(ventana) / len(ventana)
            desviacion = (sum((x - promedio) ** 2 for x in ventana) / len(ventana)) ** 0.5

            # Calcular z-score
            z = 0 if desviacion == 0 else abs(valor - promedio) / desviacion
            aprobado = z <= self.z_threshold

            resultados[sensor] = {
                'aprobado': aprobado,
                'razon': 'Dentro del rango normal' if aprobado else f'Valor fuera de rango (z={z:.2f})',
                'promedio': round(promedio, 2),
                'desviacion': round(desviacion, 2)
            }

            # Mantener el tamaño máximo de la ventana
            if len(ventana) >= self.window_size:
                ventana.pop(0)
            ventana.append(valor)

        # Verifica que temperatura y humedad sean válidos
        sensores_criticos = ['temperatura', 'humedad']
        todos_aprobados = all(
            resultados.get(s, {}).get('aprobado', True)
            for s in sensores_criticos
        )

        return {
            'todos_aprobados': todos_aprobados,
            'resultados': resultados
        }
