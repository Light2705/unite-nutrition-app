import streamlit as st
import pandas as pd
import sqlite3
import os
import json
from datetime import datetime, timedelta
import google.generativeai as genai

# --- 1. CONFIGURACIÓN DE IA ---
API_KEY = "AIzaSyC1FBPL-7rf7DskWE1tOWIyne7aoNoKxwE"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 2. BASE DE DATOS ---
DB_PATH = "unite_nutrition_vFinal.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, is_admin INTEGER, 
                 target_prot REAL, target_carb REAL, target_fat REAL, target_kcal REAL)''')
    # Registros de comida
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, 
                 food_desc TEXT, prot REAL, carb REAL, fat REAL, kcal REAL, status TEXT, meal_time TEXT)''')
    # Insertar admin por defecto
    c.execute("INSERT OR IGNORE INTO users VALUES ('erick', 'erickale2005', 1, 180.0, 250.0, 70.0, 2400.0)")
    conn.commit()
    conn.close()

try:
    init_db()
except:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()

# --- 3. FUNCIONES DE APOYO ---
def procesar_comida_ia(texto_usuario):
    prompt = f"""
    Eres un experto en nutrición. Analiza: {texto_usuario}.
    Devuelve un JSON estrictamente con este formato:
    [
      {{"alim": "nombre", "gr": 100, "p": 20.5, "c": 10.0, "g": 5.0, "k": 150}}
    ]
    """
    try:
        response = model.generate_content(prompt)
        json_clean = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(json_clean)
    except:
        return None

# --- 4. INTERFAZ Y NAVEGACIÓN ---
st.set_page_config(page_title="Unite Nutrition", layout="wide")

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
            st.error("Error en credenciales.")
else:
    # MENÚ LATERAL (Lo que faltaba)
    st.sidebar.title(f"Hola, {st.session_state.user}")
    menu = st.sidebar.radio("Navegación", ["Mi Diario", "Gestión de Clientes", "Historial"])
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()

    hoy = (datetime.utcnow() - timedelta(hours=5)).strftime('%Y-%m-%d')

    # --- SECCIÓN: MI DIARIO ---
    if menu == "Mi Diario":
        st.header(f"📓 Diario Nutricional - {hoy}")
        
        with st.expander("✨ REGISTRO MÁGICO CON IA", expanded=True):
            txt = st.text_area("¿Qué comiste?", placeholder="150g de pollo y 100g de arroz")
            momento = st.selectbox("Momento", ["Desayuno", "Almuerzo", "Cena", "Snack"])
            if st.button("Registrar con IA"):
                items = procesar_comida_ia(txt)
                if items:
                    conn = sqlite3.connect(DB_PATH)
                    for i in items:
                        conn.execute("""INSERT INTO logs 
                            (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) 
                            VALUES (?,?,?,?,?,?,?,?,?)""",
                            (st.session_state.user, hoy, f"{i['gr']}g {i['alim']}", i['p'], i['c'], i['g'], i['k'], 'IA', momento))
                    conn.commit()
                    conn.close()
                    st.success("Registrado correctamente.")
                    st.rerun()
                else:
                    st.error("No se pudo procesar. Intenta ser más claro.")

        # Dashboard
        conn = sqlite3.connect(DB_PATH)
        logs = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
        user_data = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
        conn.close()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Proteína", f"{logs['prot'].sum():.1f}g", f"Meta: {user_data['target_prot']}g")
        c2.metric("Carbos", f"{logs['carb'].sum():.1f}g", f"Meta: {user_data['target_carb']}g")
        c3.metric("Grasas", f"{logs['fat'].sum():.1f}g", f"Meta: {user_data['target_fat']}g")
        c4.metric("Kcal", f"{int(logs['kcal'].sum())}", f"Meta: {int(user_data['target_kcal'])}")

        st.dataframe(logs[['meal_time', 'food_desc', 'prot', 'carb', 'fat', 'kcal']], use_container_width=True)

    # --- SECCIÓN: GESTIÓN DE CLIENTES ---
    elif menu == "Gestión de Clientes":
        st.header("👥 Panel de Control de Clientes")
        st.info("Aquí puedes ver el progreso de tus alumnos de powerlifting.")
        # Lógica para agregar/ver clientes (puedes expandirla luego)
        conn = sqlite3.connect(DB_PATH)
        clientes = pd.read_sql("SELECT username, target_prot, target_kcal FROM users WHERE is_admin=0", conn)
        conn.close()
        st.table(clientes)

    # --- SECCIÓN: HISTORIAL ---
    elif menu == "Historial":
        st.header("📅 Historial de Registros")
        fecha_busqueda = st.date_input("Selecciona una fecha")
        fecha_str = fecha_busqueda.strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(DB_PATH)
        historial = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, fecha_str))
        conn.close()
        
        if not historial.empty:
            st.dataframe(historial, use_container_width=True)
        else:
            st.warning("No hay registros para esta fecha.")
