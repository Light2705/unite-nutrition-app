import streamlit as st
import pandas as pd
import sqlite3
import os
import re
from datetime import datetime, timedelta
import google.generativeai as genai

# --- 1. CONFIGURACIÓN IA ---
API_KEY = "AIzaSyC1FBPL-7rf7DskWE1tOWIyne7aoNoKxwE"
genai.configure(api_key=API_KEY)
# Instrucción de sistema para forzar el formato más simple posible
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    system_instruction="Extrae macros de alimentos. Responde SOLO con: Alimento | Gramos | P | C | G | Kcal"
)

# --- 2. BASE DE DATOS ---
def get_local_time():
    return datetime.utcnow() - timedelta(hours=5)

DB_PATH = os.path.join(os.getcwd(), "unite_nutrition_vFinal.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, is_admin INTEGER, 
                 target_prot REAL, target_carb REAL, target_fat REAL, target_kcal REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, 
                 food_desc TEXT, prot REAL, carb REAL, fat REAL, kcal REAL, status TEXT, meal_time TEXT)''')
    c.execute("INSERT OR IGNORE INTO users VALUES ('erick', 'erickale2005', 1, 180, 250, 70, 2400)")
    conn.commit()
    conn.close()

init_db()

# --- 3. MOTOR DE EXTRACCIÓN BLINDADO ---
def procesar_comida_ia(texto_usuario):
    prompt = f"Analiza: {texto_usuario}"
    try:
        response = model.generate_content(prompt)
        # Limpiamos caracteres de tablas de Markdown que rompen el split
        raw_text = response.text.replace('*', '').replace('-', '').strip()
        lineas = raw_text.split('\n')
        
        resultados = []
        for linea in lineas:
            # Dividir por el separador | y limpiar espacios
            partes = [p.strip() for p in linea.split('|') if p.strip()]
            
            # Verificamos que existan al menos los campos básicos
            if len(partes) >= 6:
                def extract_num(txt):
                    # Encuentra cualquier número (entero o decimal) ignorando texto alrededor
                    n = re.findall(r"[-+]?\d*\.\d+|\d+", str(txt))
                    return float(n[0]) if n else 0.0

                resultados.append({
                    "alim": partes[0],
                    "gr": extract_num(partes[1]),
                    "p": extract_num(partes[2]),
                    "c": extract_num(partes[3]),
                    "g": extract_num(partes[4]),
                    "k": extract_num(partes[5])
                })
        return resultados if resultados else None
    except:
        return None

# --- 4. INTERFAZ ---
st.set_page_config(page_title="Unite Nutrition", layout="wide")

if 'user' not in st.session_state:
    st.title("🏋️ Unite Nutrition")
    with st.form("login"):
        u = st.text_input("Usuario").lower()
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            conn = sqlite3.connect(DB_PATH)
            res = pd.read_sql("SELECT * FROM users WHERE username=? AND password=?", conn, params=(u, p))
            conn.close()
            if not res.empty:
                st.session_state.user = res.iloc[0]['username']
                st.rerun()
            else:
                st.error("Error de acceso")
else:
    hoy = get_local_time().strftime('%Y-%m-%d')
    st.header(f"Diario de Nutrición - {hoy}")

    with st.container(border=True):
        st.subheader("✨ Registro con IA")
        txt = st.text_area("¿Qué comiste?", placeholder="Ej: 150g de pollo y 100g de arroz")
        momento = st.selectbox("Momento", ["Desayuno", "Almuerzo", "Cena", "Snack"])
        
        if st.button("🚀 Registrar Ahora"):
            with st.spinner("Procesando..."):
                items = procesar_comida_ia(txt)
                if items:
                    conn = sqlite3.connect(DB_PATH)
                    for i in items:
                        conn.execute("""INSERT INTO logs 
                            (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) 
                            VALUES (?,?,?,?,?,?,?,?,?)""",
                            (st.session_state.user, hoy, f"{int(i['gr'])}g {i['alim']}", 
                             i['p'], i['c'], i['g'], i['k'], 'IA', momento))
                    conn.commit()
                    conn.close()
                    st.success("✅ ¡Hecho!")
                    st.rerun()
                else:
                    st.error("No se pudo extraer la información. Intenta ser más específico.")

    # Panel de Resumen
    conn = sqlite3.connect(DB_PATH)
    logs = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
    user = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
    conn.close()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Proteína", f"{logs['prot'].sum():.1f}g", f"Meta: {user['target_prot']}g")
    c2.metric("Carbos", f"{logs['carb'].sum():.1f}g", f"Meta: {user['target_carb']}g")
    c3.metric("Grasas", f"{logs['fat'].sum():.1f}g", f"Meta: {user['target_fat']}g")
    c4.metric("Kcal", f"{int(logs['kcal'].sum())}", f"Meta: {int(user['target_kcal'])}")

    st.dataframe(logs[['meal_time', 'food_desc', 'prot', 'carb', 'fat', 'kcal']], use_container_width=True)
