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
    return datetime.utcnow() - timedelta(hours=5)

if os.path.exists(os.path.join(os.path.expanduser("~"), "Downloads")):
    BASE_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
else:
    BASE_DIR = os.getcwd()

DB_PATH = os.path.join(BASE_DIR, "unite_nutrition_vFinal.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, is_admin INTEGER, 
                 target_prot REAL, target_carb REAL, target_fat REAL, target_kcal REAL, expiry_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS master_food
                 (food_name TEXT PRIMARY KEY, p100 REAL, c100 REAL, g100 REAL, k100 REAL, category TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, 
                 food_desc TEXT, prot REAL, carb REAL, fat REAL, kcal REAL, status TEXT, meal_time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS biometrics 
                 (username TEXT, date TEXT, weight REAL, sleep INTEGER, stress INTEGER, 
                 PRIMARY KEY (username, date))''')
    c.execute("INSERT OR IGNORE INTO users VALUES ('erick', 'erickale2005', 1, 0, 0, 0, 0, '2099-12-31')")
    conn.commit()
    conn.close()

init_db()

# --- 3. LÓGICA DE PROCESAMIENTO IA (VERSION BLINDADA) ---
def procesar_texto_con_ia(texto_usuario):
    prompt = f"""
    Eres un experto en nutrición peruana. Analiza: "{texto_usuario}".
    Extrae alimentos y cantidades. Si no hay cantidad, asume porciones estándar (ej. 1 filete = 150g).
    Devuelve ÚNICAMENTE un JSON con este formato:
    [
      {{"alimento": "nombre", "gramos": 100, "p": 20.0, "c": 0.0, "f": 5.0, "kcal": 125}}
    ]
    No incluyas explicaciones, solo el JSON.
    """
    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        
        # Limpieza profunda: extrae solo lo que esté entre los primeros [ y los últimos ]
        match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        if match:
            json_text = match.group(0)
            return json.loads(json_text)
        return None
    except Exception as e:
        print(f"Error IA: {e}")
        return None

# --- 4. INTERFAZ ---
st.set_page_config(page_title="Unite Nutrition App", page_icon="🚀", layout="wide")

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
    # BARRA LATERAL
    st.sidebar.title(f"Hola, {st.session_state.user}")
    opciones = ["Mi Diario", "Historial", "Mi Perfil"]
    if st.session_state.admin:
        opciones = ["Gestión de Clientes", "Maestro de Alimentos"] + opciones
    menu = st.sidebar.radio("Navegación", opciones)
    
    if st.sidebar.button("Cerrar Sesión"):
        del st.session_state.user
        st.rerun()

    conn = sqlite3.connect(DB_PATH)

    if menu == "Mi Diario":
        hoy = get_local_time().strftime('%Y-%m-%d')
        st.title("📓 Diario de Nutrición")
        
        # INPUT MÁGICO
        with st.expander("✨ Registro Mágico con IA", expanded=True):
            input_ia = st.text_area("¿Qué comiste?", key="ia_input")
            momento = st.selectbox("Momento", ["Desayuno", "Almuerzo", "Cena", "Snacks"])
            if st.button("🚀 Registrar con IA"):
                if input_ia:
                    with st.spinner("Calculando..."):
                        datos = procesar_texto_con_ia(input_ia)
                        if datos:
                            for item in datos:
                                conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)",
                                             (st.session_state.user, hoy, f"{item['gramos']}g {item['alimento']}", item['p'], item['c'], item['f'], item['kcal'], 'Validado (IA)', momento))
                            conn.commit()
                            st.success("✅ ¡Registrado!")
                            st.rerun()
                        else:
                            st.error("La IA no pudo procesar el texto. Prueba con algo más simple.")

        # MÉTRICAS
        user_data = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
        logs_hoy = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Proteína", f"{logs_hoy['prot'].sum():.1f}g", f"Meta: {user_data['target_prot']}g")
        m2.metric("Carbos", f"{logs_hoy['carb'].sum():.1f}g", f"Meta: {user_data['target_carb']}g")
        m3.metric("Grasas", f"{logs_hoy['fat'].sum():.1f}g", f"Meta: {user_data['target_fat']}g")
        m4.metric("Calorías", f"{int(logs_hoy['kcal'].sum())}", f"Meta: {int(user_data['target_kcal'])}")

        st.subheader("Registros de hoy")
        st.dataframe(logs_hoy[['meal_time', 'food_desc', 'prot', 'carb', 'fat', 'kcal']], use_container_width=True)
        if not logs_hoy.empty:
            id_borrar = st.selectbox("ID para borrar", logs_hoy['id'])
            if st.button("Eliminar Registro"):
                conn.execute("DELETE FROM logs WHERE id=?", (id_borrar,))
                conn.commit()
                st.rerun()

    elif menu == "Gestión de Clientes":
        st.title("👥 Panel Coach")
        clientes = pd.read_sql("SELECT * FROM users WHERE is_admin=0", conn)
        sel_u = st.selectbox("Alumno", clientes['username'].tolist())
        with st.form("metas"):
            c = clientes[clientes['username'] == sel_u].iloc[0]
            new_p = st.number_input("Proteína", value=c['target_prot'])
            new_c = st.number_input("Carbohidratos", value=c['target_carb'])
            new_f = st.number_input("Grasas", value=c['target_fat'])
            new_k = st.number_input("Calorías", value=c['target_kcal'])
            if st.form_submit_button("Actualizar Alumno"):
                conn.execute("UPDATE users SET target_prot=?, target_carb=?, target_fat=?, target_kcal=? WHERE username=?", (new_p, new_c, new_f, new_k, sel_u))
                conn.commit()
                st.success("Actualizado")

    elif menu == "Maestro de Alimentos":
        st.title("📂 Maestro de Alimentos")
        with st.form("alim"):
            n = st.text_input("Nombre")
            p, c, f, k = st.columns(4)
            ip = p.number_input("P", 0.0)
            ic = c.number_input("C", 0.0)
            if f.number_input("G", 0.0): ig = f.number_input("G", 0.0)
            else: ig = 0.0
            ik = k.number_input("K", 0.0)
            if st.form_submit_button("Guardar"):
                conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (n, ip, ic, ig, ik, "General"))
                conn.commit()
        st.dataframe(pd.read_sql("SELECT * FROM master_food", conn))

    elif menu == "Historial":
        st.title("📊 Historial")
        df_hist = pd.read_sql("SELECT date, SUM(prot) as P, SUM(carb) as C, SUM(fat) as G, SUM(kcal) as Kcal FROM logs WHERE username=? GROUP BY date ORDER BY date DESC", conn, params=(st.session_state.user,))
        st.dataframe(df_hist, use_container_width=True)

    conn.close()
