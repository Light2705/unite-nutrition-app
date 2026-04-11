import streamlit as st
import pandas as pd
import sqlite3
import os
import re
from datetime import datetime, timedelta
import google.generativeai as genai

# --- 1. CONFIGURACIÓN DE IA (GEMINI) ---
API_KEY = "AIzaSyC1FBPL-7rf7DskWE1tOWIyne7aoNoKxwE"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 2. BASE DE DATOS Y RUTAS ---
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
    c.execute("INSERT OR IGNORE INTO users VALUES ('erick', 'erickale2005', 1, 0, 0, 0, 0, '2099-12-31')")
    conn.commit()
    conn.close()

init_db()

# --- 3. PROCESAMIENTO IA BLINDADO ---
def extraer_numero(texto):
    # Extrae el primer número que encuentre en un string
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(texto))
    return float(nums[0]) if nums else 0.0

def procesar_comida_ia(texto_usuario):
    prompt = f"""
    Analiza: "{texto_usuario}". Extrae alimentos y macros. 
    Responde ÚNICAMENTE en este formato:
    Alimento | Gramos | P | C | G | Kcal
    
    Ejemplo:
    Pollo | 150 | 30 | 0 | 10 | 220
    """
    try:
        response = model.generate_content(prompt)
        lineas = response.text.strip().split('\n')
        resultados = []
        for linea in lineas:
            linea = linea.replace('*', '').strip()
            if '|' in linea and "Alimento" not in linea:
                partes = [p.strip() for p in linea.split('|')]
                if len(partes) >= 6:
                    resultados.append({
                        "alim": partes[0],
                        "gr": extraer_numero(partes[1]),
                        "p": extraer_numero(partes[2]),
                        "c": extraer_numero(partes[3]),
                        "g": extraer_numero(partes[4]),
                        "k": extraer_numero(partes[5])
                    })
        return resultados if resultados else None
    except:
        return None

# --- 4. INTERFAZ APP ---
st.set_page_config(page_title="Unite Nutrition", page_icon="🚀", layout="wide")

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
        else: st.error("Credenciales incorrectas")
else:
    st.sidebar.title(f"Hola, {st.session_state.user}")
    menu = st.sidebar.radio("Navegación", ["Mi Diario", "Gestión de Clientes", "Maestro", "Historial"] if st.session_state.admin else ["Mi Diario", "Historial"])
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()

    conn = sqlite3.connect(DB_PATH)

    if menu == "Mi Diario":
        hoy = get_local_time().strftime('%Y-%m-%d')
        st.title(f"📓 Diario - {hoy}")
        
        with st.expander("✨ REGISTRO MÁGICO CON IA", expanded=True):
            input_ia = st.text_area("¿Qué comiste?", placeholder="Ej: 150g de pollo y 1 papa")
            momento = st.selectbox("Momento", ["Desayuno", "Almuerzo", "Cena", "Snacks"])
            if st.button("🚀 Registrar con IA"):
                if input_ia:
                    with st.spinner("Procesando..."):
                        datos = procesar_comida_ia(input_ia)
                        if datos:
                            for item in datos:
                                conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)",
                                             (st.session_state.user, hoy, f"{int(item['gr'])}g {item['alim']}", item['p'], item['c'], item['g'], item['k'], 'IA', momento))
                            conn.commit()
                            st.success("✅ Registrado correctamente")
                            st.rerun()
                        else: st.error("⚠️ Error: Intenta escribir cantidades claras como '100g de pollo'.")

        # Métricas
        user_res = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,))
        if not user_res.empty:
            u_data = user_res.iloc[0]
            l_hoy = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Proteína", f"{l_hoy['prot'].sum():.1f}g", f"Meta: {u_data['target_prot']}g")
            c2.metric("Carbos", f"{l_hoy['carb'].sum():.1f}g", f"Meta: {u_data['target_carb']}g")
            c3.metric("Grasas", f"{l_hoy['fat'].sum():.1f}g", f"Meta: {u_data['target_fat']}g")
            c4.metric("Kcal", f"{int(l_hoy['kcal'].sum())}", f"Meta: {int(u_data['target_kcal'])}")

            st.divider()
            st.dataframe(l_hoy[['meal_time', 'food_desc', 'prot', 'carb', 'fat', 'kcal']], use_container_width=True)
            if not l_hoy.empty:
                id_del = st.selectbox("ID para borrar", l_hoy['id'])
                if st.button("🗑️ Eliminar"):
                    conn.execute("DELETE FROM logs WHERE id=?", (id_del,))
                    conn.commit(); st.rerun()

    elif menu == "Gestión de Clientes":
        st.title("👥 Gestión")
        alumnos = pd.read_sql("SELECT * FROM users WHERE is_admin=0", conn)
        sel_u = st.selectbox("Alumno", alumnos['username'].tolist())
        if sel_u:
            c = alumnos[alumnos['username'] == sel_u].iloc[0]
            with st.form("metas"):
                p = st.number_input("P", value=c['target_prot'])
                cb = st.number_input("C", value=c['target_carb'])
                g = st.number_input("G", value=c['target_fat'])
                k = st.number_input("Kcal", value=c['target_kcal'])
                if st.form_submit_button("Actualizar"):
                    conn.execute("UPDATE users SET target_prot=?, target_carb=?, target_fat=?, target_kcal=? WHERE username=?", (p, cb, g, k, sel_u))
                    conn.commit(); st.success("Actualizado")

    elif menu == "Maestro":
        st.title("📂 Alimentos")
        st.dataframe(pd.read_sql("SELECT * FROM master_food", conn))

    elif menu == "Historial":
        st.title("📊 Historial")
        df_hist = pd.read_sql("SELECT date, SUM(prot) as P, SUM(carb) as C, SUM(fat) as G, SUM(kcal) as Kcal FROM logs WHERE username=? GROUP BY date ORDER BY date DESC", conn, params=(st.session_state.user,))
        st.dataframe(df_hist, use_container_width=True)

    conn.close()
