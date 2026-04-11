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
# Usamos un system_instruction para obligar a la IA a no mandar tablas visuales
model = genai.GenerativeModel(
    model_name='gemini-1.5-flash',
    system_instruction="Responde exclusivamente en texto plano usando barras laterales como separador. Ejemplo: Pollo | 100 | 31 | 0 | 3 | 165"
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
                 target_prot REAL, target_carb REAL, target_fat REAL, target_kcal REAL, expiry_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, 
                 food_desc TEXT, prot REAL, carb REAL, fat REAL, kcal REAL, status TEXT, meal_time TEXT)''')
    c.execute("INSERT OR IGNORE INTO users VALUES ('erick', 'erickale2005', 1, 180, 250, 70, 2400, '2099-12-31')")
    conn.commit()
    conn.close()

init_db()

# --- 3. PROCESAMIENTO ULTRA-FLEXIBLE ---
def procesar_comida_ia(texto_usuario):
    prompt = f"Calcula macros para: {texto_usuario}. Formato: Nombre | Gramos | P | C | G | Kcal"
    try:
        response = model.generate_content(prompt)
        # Limpieza profunda: quitamos negritas y caracteres de tablas Markdown
        raw_text = response.text.replace('*', '').replace('- ', '').strip()
        lineas = raw_text.split('\n')
        
        resultados = []
        for linea in lineas:
            # Detectamos si la línea tiene datos (buscamos el separador o muchos números)
            partes = [p.strip() for p in linea.split('|') if p.strip()]
            
            # Si la IA mandó tabla de Markdown, las partes pueden tener guiones ---, los saltamos
            if len(partes) >= 6 and not all(c == '-' for c in partes[1]):
                def solo_numeros(txt):
                    # Extrae el primer número (entero o decimal) que encuentre en el texto
                    n = re.findall(r"[-+]?\d*\.\d+|\d+", str(txt))
                    return float(n[0]) if n else 0.0

                resultados.append({
                    "alim": partes[0],
                    "gr": solo_numeros(partes[1]),
                    "p": solo_numeros(partes[2]),
                    "c": solo_numeros(partes[3]),
                    "g": solo_numeros(partes[4]),
                    "k": solo_numeros(partes[5])
                })
        return resultados if resultados else None
    except:
        return None

# --- 4. INTERFAZ ---
st.set_page_config(page_title="Unite Nutrition - Fitia PRO", layout="wide")

if 'user' not in st.session_state:
    st.title("🏋️ Unite Nutrition")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Ingresar"):
            conn = sqlite3.connect(DB_PATH)
            res = pd.read_sql("SELECT * FROM users WHERE username=? AND password=?", conn, params=(u, p))
            conn.close()
            if not res.empty:
                st.session_state.user, st.session_state.admin = res.iloc[0]['username'], res.iloc[0]['is_admin']
                st.rerun()
else:
    hoy = get_local_time().strftime('%Y-%m-%d')
    st.title(f"📓 Diario - {hoy}")

    with st.expander("✨ REGISTRO RÁPIDO CON IA", expanded=True):
        txt = st.text_area("¿Qué comiste?", placeholder="100g de pechuga de pollo")
        momento = st.selectbox("Momento", ["Desayuno", "Almuerzo", "Cena", "Snacks"])
        if st.button("🚀 Registrar con IA"):
            items = procesar_comida_ia(txt)
            if items:
                conn = sqlite3.connect(DB_PATH)
                for i in items:
                    conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)",
                                 (st.session_state.user, hoy, f"{int(i['gr'])}g {i['alim']}", i['p'], i['c'], i['g'], i['k'], 'IA', momento))
                conn.commit()
                conn.close()
                st.success("✅ ¡Registrado!")
                st.rerun()
            else:
                st.error("Error al leer la respuesta de la IA. Intenta de nuevo.")

    # Resumen visual
    conn = sqlite3.connect(DB_PATH)
    logs = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
    meta = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
    conn.close()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Proteína", f"{logs['prot'].sum():.1f}g", f"Meta: {meta['target_prot']}g")
    c2.metric("Carbos", f"{logs['carb'].sum():.1f}g", f"Meta: {meta['target_carb']}g")
    c3.metric("Grasas", f"{logs['fat'].sum():.1f}g", f"Meta: {meta['target_fat']}g")
    c4.metric("Calorías", f"{int(logs['kcal'].sum())}", f"Meta: {int(meta['target_kcal'])}")

    st.dataframe(logs[['meal_time', 'food_desc', 'prot', 'carb', 'fat', 'kcal']], use_container_width=True)
