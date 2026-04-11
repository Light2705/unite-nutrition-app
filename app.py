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
model = genai.GenerativeModel('gemini-1.5-flash')

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
    c.execute("INSERT OR IGNORE INTO users VALUES ('erick', 'erickale2005', 1, 0, 0, 0, 0, '2099-12-31')")
    conn.commit()
    conn.close()

init_db()

# --- 3. PROCESAMIENTO ULTRA-AGRESIVO (LA SOLUCIÓN) ---
def procesar_comida_ia(texto_usuario):
    prompt = f"""
    Analiza: "{texto_usuario}". Responde UNICAMENTE con este formato:
    Alimento | Gramos | P | C | G | Kcal
    Ejemplo: Pollo | 150 | 30 | 0 | 10 | 220
    """
    try:
        response = model.generate_content(prompt)
        # Filtramos solo las líneas que tienen el separador |
        lineas = [l.strip() for l in response.text.split('\n') if '|' in l and 'Gramos' not in l]
        
        resultados = []
        for linea in lineas:
            # Limpiamos asteriscos y basura, luego dividimos
            partes = [p.strip() for p in linea.replace('*', '').split('|')]
            if len(partes) >= 6:
                # Extraemos solo los números de cada parte para evitar errores de texto
                def n(t):
                    find = re.findall(r"[-+]?\d*\.\d+|\d+", t)
                    return float(find[0]) if find else 0.0

                resultados.append({
                    "alim": partes[0], "gr": n(partes[1]), "p": n(partes[2]),
                    "c": n(partes[3]), "g": n(partes[4]), "k": n(partes[5])
                })
        return resultados if resultados else None
    except:
        return None

# --- 4. INTERFAZ ---
st.set_page_config(page_title="Unite Nutrition", layout="wide")

if 'user' not in st.session_state:
    st.title("🏋️ Unite Nutrition - Login")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        conn = sqlite3.connect(DB_PATH)
        res = pd.read_sql("SELECT * FROM users WHERE username=? AND password=?", conn, params=(u, p))
        conn.close()
        if not res.empty:
            st.session_state.user, st.session_state.admin = res.iloc[0]['username'], res.iloc[0]['is_admin']
            st.rerun()
else:
    st.sidebar.title(f"Hola, {st.session_state.user}")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()

    hoy = get_local_time().strftime('%Y-%m-%d')
    st.title(f"📓 Diario - {hoy}")

    with st.expander("✨ REGISTRO RÁPIDO CON IA", expanded=True):
        txt = st.text_area("¿Qué comiste?", placeholder="Ej: 150g de pollo y 2 papas")
        momento = st.selectbox("Momento", ["Desayuno", "Almuerzo", "Cena", "Snacks"])
        if st.button("🚀 Registrar ahora"):
            datos = procesar_comida_ia(txt)
            if datos:
                conn = sqlite3.connect(DB_PATH)
                for i in datos:
                    conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)",
                                 (st.session_state.user, hoy, f"{int(i['gr'])}g {i['alim']}", i['p'], i['c'], i['g'], i['k'], 'IA', momento))
                conn.commit()
                conn.close()
                st.success("✅ ¡Hecho!")
                st.rerun()
            else:
                st.error("❌ La IA no respondió correctamente. Intenta de nuevo.")

    # Resumen de hoy
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
