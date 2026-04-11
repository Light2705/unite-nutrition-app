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

# --- 3. PROCESAMIENTO DE IA (FORMATO PLANO ULTRA-SEGURO) ---
def procesar_comida_ia(texto_usuario):
    prompt = f"""
    Eres un experto en nutrición. Analiza: "{texto_usuario}".
    Extrae alimentos y macros. Si no hay cantidad, asume porciones lógicas.
    RESPONDE ÚNICAMENTE EN ESTE FORMATO (una línea por alimento):
    Alimento | Gramos | P | C | G | Kcal
    
    Ejemplo:
    Pollo frito | 150 | 30.5 | 0.0 | 12.0 | 250
    """
    try:
        response = model.generate_content(prompt)
        lineas = response.text.strip().split('\n')
        resultados = []
        for linea in lineas:
            if '|' in linea:
                partes = [p.strip() for p in linea.split('|')]
                if len(partes) >= 6:
                    resultados.append({
                        "alimento": partes[0],
                        "gramos": float(re.sub(r'[^\d.]', '', partes[1])),
                        "p": float(re.sub(r'[^\d.]', '', partes[2])),
                        "c": float(re.sub(r'[^\d.]', '', partes[3])),
                        "g": float(re.sub(r'[^\d.]', '', partes[4])),
                        "kcal": float(re.sub(r'[^\d.]', '', partes[5]))
                    })
        return resultados
    except:
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
        else: st.error("Credenciales incorrectas")
else:
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
        
        # REGISTRO MÁGICO
        with st.expander("✨ Registro Mágico con IA", expanded=True):
            input_ia = st.text_area("¿Qué comiste?", placeholder="Ej: 150g de pollo frito y 2 papas cocidas")
            momento = st.selectbox("Momento", ["Desayuno", "Almuerzo", "Cena", "Snacks"])
            if st.button("🚀 Registrar con IA"):
                if input_ia:
                    with st.spinner("Analizando..."):
                        datos = procesar_comida_ia(input_ia)
                        if datos:
                            for item in datos:
                                conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)",
                                             (st.session_state.user, hoy, f"{int(item['gramos'])}g {item['alimento']}", item['p'], item['c'], item['g'], item['kcal'], 'IA', momento))
                            conn.commit()
                            st.success("✅ Comida registrada con éxito")
                            st.rerun()
                        else: st.error("⚠️ Error al procesar. Intenta escribir de forma más clara.")

        # MÉTRICAS
        user_data = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
        logs_hoy = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Proteína", f"{logs_hoy['prot'].sum():.1f}g", f"Meta: {user_data['target_prot']}g")
        c2.metric("Carbos", f"{logs_hoy['carb'].sum():.1f}g", f"Meta: {user_data['target_carb']}g")
        c3.metric("Grasas", f"{logs_hoy['fat'].sum():.1f}g", f"Meta: {user_data['target_fat']}g")
        c4.metric("Calorías", f"{int(logs_hoy['kcal'].sum())}", f"Meta: {int(user_data['target_kcal'])}")

        st.subheader("Registros de hoy")
        st.dataframe(logs_hoy[['meal_time', 'food_desc', 'prot', 'carb', 'fat', 'kcal']], use_container_width=True)
        if not logs_hoy.empty:
            id_borrar = st.selectbox("ID para borrar", logs_hoy['id'])
            if st.button("🗑️ Eliminar Registro"):
                conn.execute("DELETE FROM logs WHERE id=?", (id_borrar,))
                conn.commit(); st.rerun()

    elif menu == "Gestión de Clientes":
        st.title("👥 Panel Coach")
        clientes = pd.read_sql("SELECT * FROM users WHERE is_admin=0", conn)
        sel_u = st.selectbox("Alumno", clientes['username'].tolist())
        with st.form("metas"):
            c = clientes[clientes['username'] == sel_u].iloc[0]
            p = st.number_input("Proteína Meta", value=c['target_prot'])
            carb = st.number_input("Carbo Meta", value=c['target_carb'])
            f = st.number_input("Grasa Meta", value=c['target_fat'])
            k = st.number_input("Kcal Meta", value=c['target_kcal'])
            if st.form_submit_button("Actualizar Alumno"):
                conn.execute("UPDATE users SET target_prot=?, target_carb=?, target_fat=?, target_kcal=? WHERE username=?", (p, carb, f, k, sel_u))
                conn.commit(); st.success("Metas actualizadas")

    elif menu == "Maestro de Alimentos":
        st.title("📂 Maestro de Alimentos")
        with st.form("add_food"):
            n = st.text_input("Alimento")
            c1, c2, c3, c4 = st.columns(4)
            ip = c1.number_input("P", 0.0); ic = c2.number_input("C", 0.0); ig = c3.number_input("G", 0.0); ik = c4.number_input("Kcal", 0.0)
            if st.form_submit_button("Guardar"):
                conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (n, ip, ic, ig, ik, "Manual"))
                conn.commit(); st.success("Guardado")
        st.dataframe(pd.read_sql("SELECT * FROM master_food", conn), use_container_width=True)

    elif menu == "Historial":
        st.title("📊 Historial")
        df_hist = pd.read_sql("SELECT date, SUM(prot) as P, SUM(carb) as C, SUM(fat) as G, SUM(kcal) as Kcal FROM logs WHERE username=? GROUP BY date ORDER BY date DESC", conn, params=(st.session_state.user,))
        st.dataframe(df_hist, use_container_width=True)

    conn.close()
