import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression

class MachineLearningEngine:
    def procesar_datos(self, datos_historicos, n_clusters=3):
        """
        Recibe los datos históricos y aplica:
        1. Clustering (K-Means): Agrupa por clima similar (Temp vs Humedad).
        2. Inferencia (Regresión Lineal): Predice la temperatura futura.
        """
        if not datos_historicos:
            return {"error": "No hay datos suficientes para analizar"}

        # Convertimos la lista de diccionarios a un DataFrame (tabla)
        df = pd.DataFrame(datos_historicos)
        
        # --- 1. CLUSTERING (Agrupamiento) ---
        # Usamos Temperatura y Humedad para encontrar patrones
        X = df[['temp_celsius', 'humedad_porcentaje']].values
        
        # Seguridad: Si hay menos datos que clusters, ajustamos a 1 cluster
        if len(df) < n_clusters:
            n_clusters = 1
            
        # Algoritmo K-Means
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        df['cluster'] = kmeans.fit_predict(X)
        
        # --- 2. INFERENCIA (Predicción) ---
        # Usamos Regresión Lineal para predecir la temperatura basada en el tiempo
        df['indice_tiempo'] = range(len(df))
        
        X_reg = df[['indice_tiempo']].values
        y_reg = df['temp_celsius'].values
        
        model = LinearRegression()
        model.fit(X_reg, y_reg)
        
        # Predecir los siguientes 5 puntos en el futuro
        ultimo_indice = df['indice_tiempo'].max()
        futuro_X = np.array([[ultimo_indice + i] for i in range(1, 6)])
        predicciones = model.predict(futuro_X)
        
        # Preparamos el resultado para enviarlo a la web
        return {
            "status": "success",
            "datos_analizados": df.to_dict(orient='records'),
            "prediccion_futura": predicciones.tolist(),
            "mensaje": "Análisis completado exitosamente"
        }
    
    