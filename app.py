import streamlit as st
import pandas as pd
import sqlite3
import os
import json
from datetime import datetime, timedelta
import google.generativeai as genai

# --- 1. CONFIGURACIÓN DE IA ---
# Se actualiza la configuración para evitar el error 404 de versión
API_KEY = "AIzaSyC1FBPL-7rf7DskWE1tOWIyne7aoNoKxwE"
genai.configure(api_key=API_KEY)

# Usamos una configuración de modelo más robusta
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash'
)

# --- 2. BASE DE DATOS ---
DB_PATH = "unite_nutrition_vFinal.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, is_admin INTEGER, 
                 target_prot REAL, target_carb REAL, target_fat REAL, target_kcal REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, 
                 food_desc TEXT, prot REAL, carb REAL, fat REAL, kcal REAL, status TEXT, meal_time TEXT)''')
    c.execute("INSERT OR IGNORE INTO users VALUES ('erick', 'erickale2005', 1, 180.0, 250.0, 70.0, 2400.0)")
    conn.commit()
    conn.close()

try:
    init_db()
except:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()

# --- 3. MOTOR DE PROCESAMIENTO ---
def procesar_comida_ia(texto_usuario):
    # Forzamos a la IA a responder en un formato JSON que Python pueda leer siempre
    prompt = f"""
    Eres un experto en nutrición peruana. Analiza: {texto_usuario}.
    Responde ÚNICAMENTE con un objeto JSON en este formato:
    [
      {{"alim": "nombre", "gr": 100, "p": 20.5, "c": 10.0, "g": 5.0, "k": 150}}
    ]
    """
    try:
        # Usamos generate_content de forma estándar para mayor compatibilidad
        response = model.generate_content(prompt)
        # Limpiamos la respuesta de posibles etiquetas de markdown (```json ... ```)
        json_clean = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(json_clean)
    except Exception as e:
        st.error(f"Error de comunicación con la IA: {e}")
        return None

# --- 4. INTERFAZ ---
st.set_page_config(page_title="Unite Nutrition vFinal", layout="wide")

if 'user' not in st.session_state:
    st.title("🏋️ Unite Nutrition - Login")
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
            st.error("Acceso denegado.")
else:
    hoy = (datetime.utcnow() - timedelta(hours=5)).strftime('%Y-%m-%d')
    st.title(f"Diario de {st.session_state.user} - {hoy}")

    with st.container(border=True):
        st.subheader("🚀 Registro Inteligente")
        txt = st.text_area("¿Qué comiste?", placeholder="Ej: 150g de pollo frito")
        momento = st.selectbox("Momento", ["Desayuno", "Almuerzo", "Cena", "Snack"])
        
        if st.button("Registrar con IA"):
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
                st.success("¡Registrado!")
                st.rerun()

    # Dashboard y Visualización
    conn = sqlite3.connect(DB_PATH)
    logs = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
    user_conf = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
    conn.close()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Proteína", f"{logs['prot'].sum():.1f}g", f"Meta: {user_conf['target_prot']}g")
    c2.metric("Carbos", f"{logs['carb'].sum():.1f}g", f"Meta: {user_conf['target_carb']}g")
    c3.metric("Grasas", f"{logs['fat'].sum():.1f}g", f"Meta: {user_conf['target_fat']}g")
    c4.metric("Kcal", f"{int(logs['kcal'].sum())}", f"Meta: {int(user_conf['target_kcal'])}")

    st.dataframe(logs[['meal_time', 'food_desc', 'prot', 'carb', 'fat', 'kcal']], use_container_width=True)

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()
