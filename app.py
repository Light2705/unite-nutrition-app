import streamlit as st
import pandas as pd
import sqlite3
import os
import re
import json
from datetime import datetime, timedelta
import google.generativeai as genai

# --- 1. CONFIGURACIÓN DE IA (GEMINI) ---
API_KEY = "AIzaSyC1FBPL-7rf7DskWE1tOWIyne7aoNoKxwE"
genai.configure(api_key=API_KEY)

# Configuramos el modelo para que SOLO escupa JSON puro
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    generation_config={"response_mime_type": "application/json"}
)

# --- 2. GESTIÓN DE BASE DE DATOS (BLINDADA) ---
DB_PATH = "unite_nutrition_vFinal.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Tabla de usuarios con 7 columnas exactas
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, is_admin INTEGER, 
                 target_prot REAL, target_carb REAL, target_fat REAL, target_kcal REAL)''')
    
    # Tabla de registros (logs)
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, 
                 food_desc TEXT, prot REAL, carb REAL, fat REAL, kcal REAL, status TEXT, meal_time TEXT)''')
    
    # Usuario maestro
    c.execute("INSERT OR IGNORE INTO users VALUES ('erick', 'erickale2005', 1, 180.0, 250.0, 70.0, 2400.0)")
    conn.commit()
    conn.close()

# Si hay error de estructura, borramos y empezamos de cero automáticamente
try:
    init_db()
except:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()

# --- 3. MOTOR DE IA INFALIBLE (FORMATO JSON) ---
def procesar_comida_ia(texto_usuario):
    prompt = f"""
    Analiza: {texto_usuario}.
    Devuelve un JSON que sea una lista de objetos.
    Cada objeto debe tener: "alim", "gr", "p", "c", "g", "k".
    Ejemplo: [{{"alim": "pollo", "gr": 100, "p": 31, "c": 0, "g": 3, "k": 165}}]
    """
    try:
        response = model.generate_content(prompt)
        # Convertimos la respuesta de texto a un objeto real de Python
        datos = json.loads(response.text)
        return datos
    except Exception as e:
        st.error(f"Error técnico: {e}")
        return None

# --- 4. INTERFAZ DE USUARIO ---
st.set_page_config(page_title="Unite Nutrition vFinal", layout="wide", page_icon="🏋️")

if 'user' not in st.session_state:
    st.title("🏋️ Unite Nutrition - Acceso")
    col_login, _ = st.columns([1, 2])
    with col_login:
        u = st.text_input("Usuario").lower().strip()
        p = st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            conn = sqlite3.connect(DB_PATH)
            res = pd.read_sql("SELECT * FROM users WHERE username=? AND password=?", conn, params=(u, p))
            conn.close()
            if not res.empty:
                st.session_state.user = res.iloc[0]['username']
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
else:
    # Ajuste de hora local (Perú)
    hoy = (datetime.utcnow() - timedelta(hours=5)).strftime('%Y-%m-%d')
    
    st.sidebar.title(f"Hola, {st.session_state.user}")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()

    st.title(f"📓 Mi Diario - {hoy}")

    # Registro con IA
    with st.container(border=True):
        st.subheader("✨ Registro Mágico con IA")
        txt = st.text_area("¿Qué comiste?", placeholder="Ej: 150g de lomo saltado y una papa dorada")
        momento = st.selectbox("Momento", ["Desayuno", "Almuerzo", "Cena", "Snack"])
        
        if st.button("🚀 Registrar con IA"):
            if txt:
                with st.spinner("La IA está calculando..."):
                    items = procesar_comida_ia(txt)
                    if items:
                        conn = sqlite3.connect(DB_PATH)
                        for i in items:
                            conn.execute("""INSERT INTO logs 
                                (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) 
                                VALUES (?,?,?,?,?,?,?,?,?)""",
                                (st.session_state.user, hoy, f"{i['gr']}g {i['alim']}", 
                                 i['p'], i['c'], i['g'], i['k'], 'IA', momento))
                        conn.commit()
                        conn.close()
                        st.success("✅ ¡Registrado perfectamente!")
                        st.rerun()
            else:
                st.warning("Escribe algo primero.")

    # Dashboard de Macros
    conn = sqlite3.connect(DB_PATH)
    logs = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
    user_data = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
    conn.close()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Proteína", f"{logs['prot'].sum():.1f}g", f"Meta: {user_data['target_prot']}g")
    m2.metric("Carbos", f"{logs['carb'].sum():.1f}g", f"Meta: {user_data['target_carb']}g")
    m3.metric("Grasas", f"{logs['fat'].sum():.1f}g", f"Meta: {user_data['target_fat']}g")
    m4.metric("Kcal", f"{int(logs['kcal'].sum())}", f"Meta: {int(user_data['target_kcal'])}")

    st.subheader("Desglose del día")
    if not logs.empty:
        st.dataframe(logs[['meal_time', 'food_desc', 'prot', 'carb', 'fat', 'kcal']], use_container_width=True)
        if st.button("🗑️ Vaciar día"):
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM logs WHERE username=? AND date=?", (st.session_state.user, hoy))
            conn.commit()
            conn.close()
            st.rerun()
    else:
        st.info("Aún no hay registros hoy.")

    # Botón de mantenimiento
    with st.sidebar.expander("⚙️ Opciones avanzadas"):
        if st.button("Borrar DB y reiniciar"):
            if os.path.exists(DB_PATH):
                os.remove(DB_PATH)
            st.rerun()
