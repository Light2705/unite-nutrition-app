import streamlit as st
import pandas as pd
import sqlite3
import os
import re
from datetime import datetime, timedelta
import google.generativeai as genai
import json

# --- 1. CONFIGURACIÓN DE IA (GEMINI) ---
API_KEY = "AIzaSyC1FBPL-7rf7DskWE1tOWIyne7aoNoKxwE"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 2. CONFIGURACIÓN DE RUTAS Y BASE DE DATOS ---
def get_local_time():
    # Ajuste para hora Perú (UTC-5)
    return datetime.utcnow() - timedelta(hours=5)

if os.path.exists(os.path.join(os.path.expanduser("~"), "Downloads")):
    BASE_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
else:
    BASE_DIR = os.getcwd()

DB_PATH = os.path.join(BASE_DIR, "unite_nutrition_vFinal.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Tabla de Usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, is_admin INTEGER, 
                 target_prot REAL, target_carb REAL, target_fat REAL, target_kcal REAL, expiry_date TEXT)''')
    # Maestro de Alimentos
    c.execute('''CREATE TABLE IF NOT EXISTS master_food
                 (food_name TEXT PRIMARY KEY, p100 REAL, c100 REAL, g100 REAL, k100 REAL, category TEXT)''')
    # Log de comidas
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, 
                 food_desc TEXT, prot REAL, carb REAL, fat REAL, kcal REAL, status TEXT, meal_time TEXT)''')
    # Biometría
    c.execute('''CREATE TABLE IF NOT EXISTS biometrics 
                 (username TEXT, date TEXT, weight REAL, sleep INTEGER, stress INTEGER, 
                 PRIMARY KEY (username, date))''')
    
    # Usuario Admin por defecto
    c.execute("INSERT OR IGNORE INTO users VALUES ('erick', 'erickale2005', 1, 0, 0, 0, 0, '2099-12-31')")
    conn.commit()
    conn.close()

init_db()

# --- 3. LÓGICA DE PROCESAMIENTO IA ---
def procesar_texto_con_ia(texto_usuario):
    prompt = f"""
    Eres un experto en nutrición peruana para la marca 'Unite Nutrition'. 
    Analiza: "{texto_usuario}".
    REGLAS:
    1. Extrae alimentos y cantidades. Si no hay cantidad, asume porciones estándar peruanas (ej. 1 filete = 150g, 1 taza arroz = 150g).
    2. Usa valores nutricionales precisos para: Proteína, Carbohidratos, Grasas y Kcal.
    3. Devuelve ESTRICTAMENTE un JSON con esta estructura:
    [
      {{"alimento": "nombre", "gramos": 100, "p": 20.0, "c": 0.0, "f": 5.0, "kcal": 125}}
    ]
    Si el texto es incoherente, devuelve []. No escribas nada de texto adicional, solo el JSON.
    """
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Limpieza de markdown por si la IA lo incluye
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text)
    except:
        return None

# --- 4. INTERFAZ DE USUARIO ---
st.set_page_config(page_title="Unite Nutrition App", page_icon="🚀", layout="wide")

# Estilos personalizados
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #3e445b; }
    </style>
    """, unsafe_allow_html=True)

if 'user' not in st.session_state:
    st.title("🏋️ Unite Nutrition - Login")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        conn = sqlite3.connect(DB_PATH)
        res = pd.read_sql("SELECT * FROM users WHERE username=? AND password=?", conn, params=(u, p))
        conn.close()
        if not res.empty:
            st.session_state.user = res.iloc[0]['username']
            st.session_state.admin = res.iloc[0]['is_admin']
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
else:
    # --- BARRA LATERAL ---
    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3003/3003164.png", width=100)
    st.sidebar.title(f"Hola, {st.session_state.user}")
    
    opciones = ["Mi Diario", "Historial", "Mi Perfil"]
    if st.session_state.admin:
        opciones = ["Gestión de Clientes", "Maestro de Alimentos"] + opciones
    
    menu = st.sidebar.radio("Navegación", opciones)
    
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state.user
        st.rerun()

    # --- LÓGICA DE NAVEGACIÓN ---
    conn = sqlite3.connect(DB_PATH)

    if menu == "Mi Diario":
        hoy = get_local_time().strftime('%Y-%m-%d')
        st.title("📓 Diario de Nutrición")
        
        # 1. INPUT MÁGICO CON IA
        with st.expander("✨ Registro Mágico con IA", expanded=True):
            st.write("Escribe lo que comiste y yo calculo los macros.")
            col_ia1, col_ia2 = st.columns([3, 1])
            with col_ia1:
                input_ia = st.text_area("Ejemplo: 'Comí 150g de lomo saltado con bastante arroz y una ensalada'", key="ia_input")
            with col_ia2:
                momento = st.selectbox("Momento", ["Desayuno", "Almuerzo", "Cena", "Snacks"])
                btn_ia = st.button("🚀 Registrar con IA")
            
            if btn_ia and input_ia:
                with st.spinner("Analizando tu comida..."):
                    datos = procesar_texto_con_ia(input_ia)
                    if datos:
                        for item in datos:
                            conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)",
                                         (st.session_state.user, hoy, f"{item['gramos']}g {item['alimento']}", item['p'], item['c'], item['f'], item['kcal'], 'Validado (IA)', momento))
                        conn.commit()
                        st.success("✅ ¡Registrado correctamente!")
                        st.rerun()
                    else:
                        st.error("No entendí bien. Intenta poner cantidades más claras.")

        st.divider()

        # 2. MÉTRICAS DEL DÍA
        user_data = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
        logs_hoy = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
        
        sum_p = logs_hoy['prot'].sum()
        sum_c = logs_hoy['carb'].sum()
        sum_f = logs_hoy['fat'].sum()
        sum_k = logs_hoy['kcal'].sum()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Proteína", f"{sum_p:.1f}g", f"Meta: {user_data['target_prot']}g")
        m2.metric("Carbos", f"{sum_c:.1f}g", f"Meta: {user_data['target_carb']}g")
        m3.metric("Grasas", f"{sum_f:.1f}g", f"Meta: {user_data['target_fat']}g")
        m4.metric("Calorías", f"{int(sum_k)}", f"Meta: {int(user_data['target_kcal'])}")

        # 3. TABLA DE REGISTROS DE HOY
        st.subheader("Comidas registradas")
        if not logs_hoy.empty:
            st.dataframe(logs_hoy[['meal_time', 'food_desc', 'prot', 'carb', 'fat', 'kcal']], use_container_width=True)
            id_borrar = st.selectbox("Selecciona ID para borrar", logs_hoy['id'])
            if st.button("Eliminar Registro"):
                conn.execute("DELETE FROM logs WHERE id=?", (id_borrar,))
                conn.commit()
                st.rerun()
        else:
            st.info("Aún no has registrado nada hoy.")

    elif menu == "Maestro de Alimentos":
        st.title("📂 Base de Datos de Alimentos")
        with st.form("nuevo_alimento"):
            st.write("Agregar nuevo alimento al sistema")
            c1, c2, c3 = st.columns(3)
            n_name = c1.text_input("Nombre")
            n_cat = c2.selectbox("Categoría", ["Proteínas", "Carbohidratos", "Grasas", "Vegetales", "Suplementos"])
            n_p = c3.number_input("Prot / 100g", 0.0)
            n_c = c1.number_input("Carb / 100g", 0.0)
            n_f = c2.number_input("Fat / 100g", 0.0)
            n_k = c3.number_input("Kcal / 100g", 0.0)
            if st.form_submit_button("Guardar Alimento"):
                conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (n_name, n_p, n_c, n_f, n_k, n_cat))
                conn.commit()
                st.success("Alimento guardado")
        
        df_master = pd.read_sql("SELECT * FROM master_food", conn)
        st.dataframe(df_master, use_container_width=True)

    elif menu == "Gestión de Clientes":
        st.title("👥 Panel de Coach")
        clientes = pd.read_sql("SELECT username, target_prot, target_carb, target_fat, target_kcal, expiry_date FROM users WHERE is_admin=0", conn)
        
        selected_u = st.selectbox("Selecciona un alumno para editar sus metas", clientes['username'].tolist())
        
        with st.form("edit_metas"):
            curr = clientes[clientes['username'] == selected_u].iloc[0]
            col1, col2 = st.columns(2)
            new_p = col1.number_input("Proteína Meta", value=curr['target_prot'])
            new_c = col2.number_input("Carbo Meta", value=curr['target_carb'])
            new_f = col1.number_input("Grasa Meta", value=curr['target_fat'])
            new_k = col2.number_input("Kcal Meta", value=curr['target_kcal'])
            new_exp = st.date_input("Vencimiento de Membresía", value=datetime.strptime(curr['expiry_date'], '%Y-%m-%d'))
            
            if st.form_submit_button("Actualizar Alumno"):
                conn.execute("UPDATE users SET target_prot=?, target_carb=?, target_fat=?, target_kcal=?, expiry_date=? WHERE username=?",
                             (new_p, new_c, new_f, new_k, new_exp.strftime('%Y-%m-%d'), selected_u))
                conn.commit()
                st.success("Datos actualizados")
        
        st.subheader("Visualizar progreso del alumno")
        df_logs_u = pd.read_sql("SELECT date, SUM(kcal) as kcal FROM logs WHERE username=? GROUP BY date", conn, params=(selected_u,))
        st.line_chart(df_logs_u.set_index('date'))

    elif menu == "Historial":
        st.title("📊 Mi Progreso")
        df_hist = pd.read_sql("SELECT date, SUM(prot) as P, SUM(carb) as C, SUM(fat) as G, SUM(kcal) as Kcal FROM logs WHERE username=? GROUP BY date ORDER BY date DESC", conn, params=(st.session_state.user,))
        st.table(df_hist)

    conn.close()
