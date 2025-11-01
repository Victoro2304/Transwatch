import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import requests
import json
import mysql.connector
from datetime import datetime, timedelta
from PIL import Image, ImageTk 
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env, requiere instalacion de python-dotenv
load_dotenv()

# Para los gráficos
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.dates as mdates

# --- Configuración ---
ESP32_IP = os.getenv('ESP32_IP', '192.168.100.65')
ESP32_API_URL = f"http://{ESP32_IP}/api"

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME', 'parking_inteligente_db')
}

# --- Variables Globales para la GUI ---
root = None
lbl_temperatura_val = None
lbl_humedad_val = None
lbl_luz_val = None
lbl_distancia_val = None
lbl_vehiculo_val = None
lbl_barrera_val = None
lbl_luces_val = None
lbl_alarma_val = None
lbl_db_timestamp_val = None
entry_distancia_ocupado = None
entry_umbral_luz = None
entry_umbral_temperatura = None
canvas_parking = None
rect_plaza = None 
rect_barrera = None 
oval_luz_parking = None
oval_alarma_temp = None

stats_canvas_widget = None
stats_toolbar = None
entry_fecha_inicio = None
entry_fecha_fin = None

# --- Funciones de Base de Datos ---
def crear_conexion_db():
    """Crea y retorna una conexión a la base de datos."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Error al conectar a MySQL: {err}")
        messagebox.showerror("Error de Base de Datos", f"No se pudo conectar a MySQL: {err}")
        return None

def obtener_ultimo_estado_db():
    """Obtiene el registro más reciente de la base de datos."""
    conn = crear_conexion_db()
    if not conn:
        return None
    datos = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM lecturas_parking ORDER BY fecha_registro DESC LIMIT 1")
        datos = cursor.fetchone()
    except mysql.connector.Error as err:
        print(f"Error al leer de la BD (último estado): {err}")
    finally:
        if conn and conn.is_connected():
            if 'cursor' in locals() and cursor:
                 cursor.close()
            conn.close()
    return datos

def obtener_datos_rango_fecha(fecha_inicio_str, fecha_fin_str):
    """Obtiene datos de la BD para un rango de fechas."""
    conn = crear_conexion_db()
    if not conn:
        return []

    try:
        start_date = datetime.strptime(fecha_inicio_str, "%Y-%m-%d").strftime("%Y-%m-%d 00:00:00")
        end_date = datetime.strptime(fecha_fin_str, "%Y-%m-%d").strftime("%Y-%m-%d 23:59:59")
    except ValueError:
        messagebox.showerror("Error de Formato", "Formato de fecha incorrecto. Use AAAA-MM-DD.")
        return []

    datos_rango = []
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT fecha_registro, temperatura_celsius, humedad_porcentaje, luz_adc 
            FROM lecturas_parking 
            WHERE fecha_registro BETWEEN %s AND %s 
            ORDER BY fecha_registro ASC
        """
        cursor.execute(query, (start_date, end_date))
        datos_rango = cursor.fetchall()
    except mysql.connector.Error as err:
        print(f"Error al leer datos por rango de fecha: {err}")
        messagebox.showerror("Error de Base de Datos", f"Error al obtener datos para estadísticas: {err}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
    return datos_rango


# --- Funciones de API REST (ESP32) ---
def obtener_parametros_esp32():
    """Obtiene los parámetros de configuración actuales del ESP32."""
    try:
        response = requests.get(f"{ESP32_API_URL}/status", timeout=5)
        response.raise_for_status()
        data = response.json()
        return data.get('config')
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error de API", f"No se pudo obtener parámetros del ESP32: {e}")
        return None

def enviar_parametros_esp32(params):
    """Envía los nuevos parámetros de configuración al ESP32."""
    try:
        response = requests.post(f"{ESP32_API_URL}/config", json=params, timeout=5)
        response.raise_for_status()
        messagebox.showinfo("Éxito", "Parámetros actualizados en ESP32.")
        return True
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error de API", f"No se pudo enviar parámetros al ESP32: {e}")
        return False

def controlar_barrera_api(accion):
    """Envía un comando para abrir o cerrar la barrera al ESP32."""
    try:
        response = requests.post(f"{ESP32_API_URL}/barrera", json={"accion": accion}, timeout=5)
        response.raise_for_status()
        messagebox.showinfo("Control Barrera", f"Comando '{accion}' enviado a la barrera.")
        actualizar_datos_gui() 
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error de API", f"No se pudo controlar la barrera: {e}")

# --- Funciones de la GUI ---
def actualizar_datos_gui():
    """Actualiza los labels de la GUI con los datos más recientes de la BD."""
    global lbl_temperatura_val, lbl_humedad_val, lbl_luz_val, lbl_distancia_val
    global lbl_vehiculo_val, lbl_barrera_val, lbl_luces_val, lbl_alarma_val, lbl_db_timestamp_val

    datos = obtener_ultimo_estado_db()
    if datos:
        lbl_temperatura_val.config(text=f"{datos.get('temperatura_celsius', 'N/A')} °C")
        lbl_humedad_val.config(text=f"{datos.get('humedad_porcentaje', 'N/A')} %")
        lbl_luz_val.config(text=str(datos.get('luz_adc', 'N/A')))
        lbl_distancia_val.config(text=f"{datos.get('distancia_entrada_cm', 'N/A')} cm")
        
        vehiculo_txt = "Detectado" if datos.get('vehiculo_detectado_entrada') else "Libre"
        lbl_vehiculo_val.config(text=vehiculo_txt, fg="orange" if datos.get('vehiculo_detectado_entrada') else "green")

        barrera_txt = "Abierta" if datos.get('barrera_abierta') else "Cerrada"
        lbl_barrera_val.config(text=barrera_txt, fg="green" if datos.get('barrera_abierta') else "red")

        luces_txt = "Encendidas" if datos.get('luces_parking_encendidas') else "Apagadas"
        lbl_luces_val.config(text=luces_txt, fg="#FFBF00" if datos.get('luces_parking_encendidas') else "grey")
        
        alarma_txt = "ACTIVA" if datos.get('alarma_temperatura_activa') else "Inactiva"
        lbl_alarma_val.config(text=alarma_txt, fg="red" if datos.get('alarma_temperatura_activa') else "green")

        actualizar_representacion_grafica(datos)

        if datos.get('fecha_registro'):
            fecha_dt = datos['fecha_registro']
            if isinstance(fecha_dt, datetime):
                 lbl_db_timestamp_val.config(text=fecha_dt.strftime('%Y-%m-%d %H:%M:%S'))
            else:
                 lbl_db_timestamp_val.config(text=str(fecha_dt))
        else:
            lbl_db_timestamp_val.config(text="N/A")

    if root: 
        root.after(3000, actualizar_datos_gui)

def cargar_parametros_actuales():
    """Carga los parámetros desde el ESP32 y los muestra en las entradas."""
    global entry_distancia_ocupado, entry_umbral_luz, entry_umbral_temperatura
    
    params = obtener_parametros_esp32()
    if params:
        entry_distancia_ocupado.delete(0, tk.END)
        entry_distancia_ocupado.insert(0, str(params.get('distancia_ocupado_cm', '')))
        
        entry_umbral_luz.delete(0, tk.END)
        entry_umbral_luz.insert(0, str(params.get('umbral_luz_adc', '')))
        
        entry_umbral_temperatura.delete(0, tk.END)
        entry_umbral_temperatura.insert(0, str(params.get('temperatura_alerta_celsius', '')))
    else:
        messagebox.showwarning("Advertencia API", "No se pudieron cargar los parámetros del ESP32.\nIntentando cargar desde la última lectura de la BD.")
        datos_db = obtener_ultimo_estado_db()
        if datos_db and datos_db.get('config_distancia_ocupado_cm') is not None:
            entry_distancia_ocupado.delete(0, tk.END)
            entry_distancia_ocupado.insert(0, str(datos_db.get('config_distancia_ocupado_cm', '')))
            entry_umbral_luz.delete(0, tk.END)
            entry_umbral_luz.insert(0, str(datos_db.get('config_umbral_luz_adc', '')))
            entry_umbral_temperatura.delete(0, tk.END)
            entry_umbral_temperatura.insert(0, str(datos_db.get('config_temp_alerta_celsius', '')))
        else:
            messagebox.showinfo("Información", "No hay datos de configuración previos en la BD.")

def guardar_parametros():
    """Toma los valores de las entradas y los envía al ESP32."""
    try:
        distancia = int(entry_distancia_ocupado.get())
        umbral_luz_val = int(entry_umbral_luz.get())
        umbral_temp = float(entry_umbral_temperatura.get())

        params = {
            "distancia_ocupado_cm": distancia,
            "umbral_luz_adc": umbral_luz_val,
            "temperatura_alerta_celsius": umbral_temp
        }
        enviar_parametros_esp32(params)
    except ValueError:
        messagebox.showerror("Error de Entrada", "Por favor, ingrese valores numéricos válidos para los parámetros.")
    except Exception as e:
        messagebox.showerror("Error", f"Ocurrió un error al guardar parámetros: {e}")

def actualizar_representacion_grafica(datos):
    """Actualiza los elementos en el canvas según los datos."""
    if not canvas_parking or not root or not datos:
        return

    if datos.get('vehiculo_detectado_entrada'):
        canvas_parking.itemconfig("plaza_bg", fill="lightcoral") 
        canvas_parking.itemconfig("plaza_txt", text="VEHÍCULO", fill="darkred")
    else:
        canvas_parking.itemconfig("plaza_bg", fill="lightgreen") 
        canvas_parking.itemconfig("plaza_txt", text="LIBRE", fill="darkgreen")

    if datos.get('barrera_abierta'):
        canvas_parking.coords(rect_barrera, 160, 175, 160, 75) 
        canvas_parking.itemconfig(rect_barrera, fill="green")
    else:
        canvas_parking.coords(rect_barrera, 160, 175, 280, 175)
        canvas_parking.itemconfig(rect_barrera, fill="red")

    canvas_parking.itemconfig(oval_luz_parking, fill="#FFBF00" if datos.get('luces_parking_encendidas') else "grey")
    canvas_parking.itemconfig(oval_alarma_temp, fill="red" if datos.get('alarma_temperatura_activa') else "grey")

def generar_grafico_estadisticas():
    """Obtiene datos del rango de fechas y muestra un gráfico de temperatura."""
    global stats_canvas_widget, stats_toolbar

    fecha_inicio_str = entry_fecha_inicio.get()
    fecha_fin_str = entry_fecha_fin.get()

    if not fecha_inicio_str or not fecha_fin_str:
        messagebox.showwarning("Entrada Requerida", "Por favor, ingrese fecha de inicio y fin.")
        return

    datos_grafico = obtener_datos_rango_fecha(fecha_inicio_str, fecha_fin_str)

    if not datos_grafico:
        messagebox.showinfo("Sin Datos", "No se encontraron datos para el rango de fechas seleccionado.")
        return

    if stats_canvas_widget:
        stats_canvas_widget.get_tk_widget().destroy()
    if stats_toolbar:
        stats_toolbar.destroy()
    
    fechas = [item['fecha_registro'] for item in datos_grafico if item['temperatura_celsius'] is not None]
    temperaturas = [item['temperatura_celsius'] for item in datos_grafico if item['temperatura_celsius'] is not None]

    if not fechas or not temperaturas:
        messagebox.showinfo("Sin Datos Válidos", "No hay datos de temperatura válidos para graficar en el rango seleccionado.")
        return

    fig = Figure(figsize=(6, 4), dpi=100)
    plot = fig.add_subplot(111)
    
    plot.plot(fechas, temperaturas, marker='o', linestyle='-', color='blue')
    plot.set_title('Temperatura vs. Tiempo')
    plot.set_xlabel('Fecha y Hora')
    plot.set_ylabel('Temperatura (°C)')
    plot.grid(True)
    fig.autofmt_xdate()
    
    plot.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))


    # Incrustar el gráfico en Tkinter
    stats_canvas_widget = FigureCanvasTkAgg(fig, master=stats_frame)
    stats_canvas_widget.draw()
    stats_canvas_widget.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    stats_toolbar = NavigationToolbar2Tk(stats_canvas_widget, stats_frame)
    stats_toolbar.update()
    stats_canvas_widget._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)


def crear_interfaz_grafica():
    """Crea y configura la interfaz gráfica principal."""
    global root, lbl_temperatura_val, lbl_humedad_val, lbl_luz_val, lbl_distancia_val
    global lbl_vehiculo_val, lbl_barrera_val, lbl_luces_val, lbl_alarma_val, lbl_db_timestamp_val
    global entry_distancia_ocupado, entry_umbral_luz, entry_umbral_temperatura
    global canvas_parking, rect_plaza, rect_barrera, oval_luz_parking, oval_alarma_temp
    global stats_frame, entry_fecha_inicio, entry_fecha_fin # Hacer stats_frame global

    root = tk.Tk()
    root.title("Panel de Control - Parking Inteligente")
    root.geometry("850x750")

    # --- Frame Principal ---
    main_frame = ttk.Frame(root, padding="10 10 10 10")
    main_frame.pack(expand=True, fill=tk.BOTH)

    # --- Columna Izquierda (Estado y Controles) ---
    left_column_frame = ttk.Frame(main_frame)
    left_column_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ns")

    # --- Sección de Estado Actual ---
    estado_frame = ttk.LabelFrame(left_column_frame, text="Estado Actual del Sistema (desde BD)", padding="10")
    estado_frame.pack(fill=tk.X, pady=5)

    ttk.Label(estado_frame, text="Temperatura:").grid(row=0, column=0, sticky="w", pady=2)
    lbl_temperatura_val = ttk.Label(estado_frame, text="-- °C", width=15, anchor="w")
    lbl_temperatura_val.grid(row=0, column=1, sticky="w", pady=2)

    ttk.Label(estado_frame, text="Humedad:").grid(row=1, column=0, sticky="w", pady=2)
    lbl_humedad_val = ttk.Label(estado_frame, text="-- %", width=15, anchor="w")
    lbl_humedad_val.grid(row=1, column=1, sticky="w", pady=2)

    ttk.Label(estado_frame, text="Nivel de Luz (ADC):").grid(row=2, column=0, sticky="w", pady=2)
    lbl_luz_val = ttk.Label(estado_frame, text="--", width=15, anchor="w")
    lbl_luz_val.grid(row=2, column=1, sticky="w", pady=2)

    ttk.Label(estado_frame, text="Distancia Entrada:").grid(row=3, column=0, sticky="w", pady=2)
    lbl_distancia_val = ttk.Label(estado_frame, text="-- cm", width=15, anchor="w")
    lbl_distancia_val.grid(row=3, column=1, sticky="w", pady=2)
    
    ttk.Label(estado_frame, text="Vehículo en Entrada:").grid(row=4, column=0, sticky="w", pady=2)
    lbl_vehiculo_val = tk.Label(estado_frame, text="Desconocido", width=15, anchor="w")
    lbl_vehiculo_val.grid(row=4, column=1, sticky="w", pady=2)

    ttk.Label(estado_frame, text="Barrera:").grid(row=5, column=0, sticky="w", pady=2)
    lbl_barrera_val = tk.Label(estado_frame, text="Desconocido", width=15, anchor="w")
    lbl_barrera_val.grid(row=5, column=1, sticky="w", pady=2)

    ttk.Label(estado_frame, text="Luces Parking:").grid(row=6, column=0, sticky="w", pady=2)
    lbl_luces_val = tk.Label(estado_frame, text="Desconocido", width=15, anchor="w")
    lbl_luces_val.grid(row=6, column=1, sticky="w", pady=2)

    ttk.Label(estado_frame, text="Alarma Temperatura:").grid(row=7, column=0, sticky="w", pady=2)
    lbl_alarma_val = tk.Label(estado_frame, text="Desconocido", width=15, anchor="w")
    lbl_alarma_val.grid(row=7, column=1, sticky="w", pady=2)

    ttk.Label(estado_frame, text="Último Registro BD:").grid(row=8, column=0, sticky="w", pady=2)
    lbl_db_timestamp_val = ttk.Label(estado_frame, text="--", width=20, anchor="w")
    lbl_db_timestamp_val.grid(row=8, column=1, sticky="w", pady=2)

    # --- Sección de Parámetros Configurables ---
    config_frame = ttk.LabelFrame(left_column_frame, text="Configuración de Parámetros (vía API ESP32)", padding="10")
    config_frame.pack(fill=tk.X, pady=10)

    ttk.Label(config_frame, text="Distancia Detección (cm):").grid(row=0, column=0, sticky="w", pady=3, padx=5)
    entry_distancia_ocupado = ttk.Entry(config_frame, width=10)
    entry_distancia_ocupado.grid(row=0, column=1, sticky="ew", pady=3, padx=5)

    ttk.Label(config_frame, text="Umbral Luz (ADC):").grid(row=1, column=0, sticky="w", pady=3, padx=5)
    entry_umbral_luz = ttk.Entry(config_frame, width=10)
    entry_umbral_luz.grid(row=1, column=1, sticky="ew", pady=3, padx=5)

    ttk.Label(config_frame, text="Umbral Temp. Alarma (°C):").grid(row=2, column=0, sticky="w", pady=3, padx=5)
    entry_umbral_temperatura = ttk.Entry(config_frame, width=10)
    entry_umbral_temperatura.grid(row=2, column=1, sticky="ew", pady=3, padx=5)
    
    config_frame.columnconfigure(1, weight=1) 

    btn_frame_config = ttk.Frame(config_frame)
    btn_frame_config.grid(row=3, column=0, columnspan=2, pady=10)

    btn_cargar_params = ttk.Button(btn_frame_config, text="Cargar Parámetros", command=cargar_parametros_actuales)
    btn_cargar_params.pack(side=tk.LEFT, padx=5)
    btn_guardar_params = ttk.Button(btn_frame_config, text="Guardar Parámetros", command=guardar_parametros)
    btn_guardar_params.pack(side=tk.LEFT, padx=5)

    # --- Sección de Control Manual Barrera ---
    control_frame = ttk.LabelFrame(left_column_frame, text="Control Manual de Barrera (vía API ESP32)", padding="10")
    control_frame.pack(fill=tk.X, pady=10)

    btn_abrir_barrera = ttk.Button(control_frame, text="Abrir Barrera", command=lambda: controlar_barrera_api("abrir"))
    btn_abrir_barrera.pack(side=tk.LEFT, padx=5, pady=5, expand=True, fill=tk.X)
    btn_cerrar_barrera = ttk.Button(control_frame, text="Cerrar Barrera", command=lambda: controlar_barrera_api("cerrar"))
    btn_cerrar_barrera.pack(side=tk.LEFT, padx=5, pady=5, expand=True, fill=tk.X)

    # --- Columna Derecha (Representación Gráfica) ---
    right_column_frame = ttk.Frame(main_frame)
    right_column_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
    
    representacion_frame = ttk.LabelFrame(right_column_frame, text="Representación del Sistema", padding="10")
    representacion_frame.pack(expand=True, fill=tk.BOTH)
    
    canvas_parking = tk.Canvas(representacion_frame, width=300, height=300, bg="lightgrey") # Tamaño fijo inicial
    canvas_parking.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

    # Dibujar elementos estáticos del parking
    canvas_parking.create_rectangle(50, 200, 250, 300, fill="lightgreen", outline="black", tags="plaza_bg")
    rect_plaza = canvas_parking.create_text(150, 250, text="ENTRADA LIBRE", font=("Arial", 14, "bold"), fill="darkgreen", tags="plaza_txt")
    canvas_parking.create_rectangle(140, 150, 160, 200, fill="darkgrey", outline="black", tags="barrera_base") 
    rect_barrera = canvas_parking.create_line(160, 175, 280, 175, width=10, fill="red", tags="barrera_brazo") 
    canvas_parking.create_text(30, 30, text="Luces Parking:", anchor="w", font=("Arial", 10))
    oval_luz_parking = canvas_parking.create_oval(150, 20, 180, 50, fill="grey", outline="black")
    canvas_parking.create_text(30, 70, text="Alarma Temp:", anchor="w", font=("Arial", 10))
    oval_alarma_temp = canvas_parking.create_oval(150, 60, 180, 90, fill="grey", outline="black")

    # --- Sección de Estadísticas (Abajo, ocupando ambas columnas) ---
    stats_frame = ttk.LabelFrame(main_frame, text="Estadísticas", padding="10")
    stats_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

    # Controles para la fecha
    date_controls_frame = ttk.Frame(stats_frame)
    date_controls_frame.pack(pady=5)

    ttk.Label(date_controls_frame, text="Fecha Inicio (AAAA-MM-DD):").pack(side=tk.LEFT, padx=5)
    entry_fecha_inicio = ttk.Entry(date_controls_frame, width=12)
    entry_fecha_inicio.pack(side=tk.LEFT, padx=5)
    entry_fecha_inicio.insert(0, (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"))

    ttk.Label(date_controls_frame, text="Fecha Fin (AAAA-MM-DD):").pack(side=tk.LEFT, padx=5)
    entry_fecha_fin = ttk.Entry(date_controls_frame, width=12)
    entry_fecha_fin.pack(side=tk.LEFT, padx=5)
    entry_fecha_fin.insert(0, datetime.now().strftime("%Y-%m-%d"))

    btn_generar_grafico = ttk.Button(date_controls_frame, text="Generar Gráfico Temperatura", command=generar_grafico_estadisticas)
    btn_generar_grafico.pack(side=tk.LEFT, padx=10)

    main_frame.columnconfigure(0, weight=1) 
    main_frame.columnconfigure(1, weight=1)
    main_frame.rowconfigure(0, weight=3)
    main_frame.rowconfigure(1, weight=2)

    # Cargar datos iniciales
    cargar_parametros_actuales() # Carga los parámetros del ESP32 al iniciar
    actualizar_datos_gui()

    root.mainloop()

if __name__ == "__main__":
    crear_interfaz_grafica()
