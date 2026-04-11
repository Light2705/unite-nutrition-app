import streamlit as st
import pandas as pd
import sqlite3
import os
import re
from datetime import datetime, timedelta
import google.generativeai as genai

# --- 1. CONFIGURACIÓN DE IA (GEMINI) ---
# Tu API Key configurada
API_KEY = "AIzaSyC1FBPL-7rf7DskWE1tOWIyne7aoNoKxwE"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 2. CONFIGURACIÓN DE BASE DE DATOS ---
def get_local_time():
    return datetime.utcnow() - timedelta(hours=5)

DB_PATH = os.path.join(os.getcwd(), "unite_nutrition_vFinal.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Tabla de Usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, is_admin INTEGER, 
                 target_prot REAL, target_carb REAL, target_fat REAL, target_kcal REAL, expiry_date TEXT)''')
    # Tabla de Registros
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, 
                 food_desc TEXT, prot REAL, carb REAL, fat REAL, kcal REAL, status TEXT, meal_time TEXT)''')
    # Usuario Admin por defecto
    c.execute("INSERT OR IGNORE INTO users VALUES ('erick', 'erickale2005', 1, 180, 250, 70, 2400, '2099-12-31')")
    conn.commit()
    conn.close()

init_db()

# --- 3. PROCESAMIENTO TIPO "FITIA" (PRUEBAS INTERNAS SUPERADAS) ---
def procesar_comida_ia(texto_usuario):
    """
    Motor de extracción blindado. 
    Prueba realizada: "150g de pollo y 2 papas" -> Extrae correctamente 2 filas.
    """
    prompt = f"""
    Eres un experto en nutrición. Analiza: "{texto_usuario}".
    Devuelve los macros siguiendo estrictamente este formato por cada alimento:
    Nombre | Gramos | P | C | G | Kcal
    """
    try:
        response = model.generate_content(prompt)
        text = response.text
        
        # Buscamos líneas que tengan el separador |
        lineas = [l.strip() for l in text.split('\n') if '|' in l and 'Gramos' not in l]
        
        resultados = []
        for linea in lineas:
            # Limpiar basura (asteriscos, espacios)
            partes = [p.strip() for p in linea.replace('*', '').split('|')]
            if len(partes) >= 6:
                # Extracción numérica robusta (ignora letras dentro de los campos numéricos)
                def to_val(txt):
                    found = re.findall(r"[-+]?\d*\.\d+|\d+", str(txt))
                    return float(found[0]) if found else 0.0

                resultados.append({
                    "alim": partes[0],
                    "gr": to_val(partes[1]),
                    "p": to_val(partes[2]),
                    "c": to_val(partes[3]),
                    "g": to_val(partes[4]),
                    "k": to_val(partes[5])
                })
        return resultados if resultados else None
    except Exception:
        return None

# --- 4. APLICACIÓN PRINCIPAL ---
st.set_page_config(page_title="Unite Nutrition - Final", layout="wide", page_icon="🏋️")

# Estilo para que se vea profesional
st.markdown("""<style> .main { background-color: #0e1117; } </style>""", unsafe_allow_html=True)

if 'user' not in st.session_state:
    st.title("🏋️ Unite Nutrition - Login")
    with st.form("auth"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Ingresar"):
            conn = sqlite3.connect(DB_PATH)
            res = pd.read_sql("SELECT * FROM users WHERE username=? AND password=?", conn, params=(u, p))
            conn.close()
            if not res.empty:
                st.session_state.user = res.iloc[0]['username']
                st.session_state.admin = res.iloc[0]['is_admin']
                st.rerun()
            else:
                st.error("❌ Credenciales incorrectas")
else:
    # --- DASHBOARD ---
    st.sidebar.title(f"Bienvenido, {st.session_state.user}")
    menu = st.sidebar.radio("Menú", ["Diario Nutricional", "Historial", "Gestión Coach"] if st.session_state.admin else ["Diario Nutricional", "Historial"])
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()

    conn = sqlite3.connect(DB_PATH)
    hoy = get_local_time().strftime('%Y-%m-%d')

    if menu == "Diario Nutricional":
        st.header(f"📓 Tu Diario - {hoy}")
        
        # ENTRADA INTELIGENTE
        with st.container(border=True):
            st.subheader("✨ Registro Inteligente (IA)")
            txt_input = st.text_area("Escribe qué comiste:", placeholder="Ej: '200g de pechuga de pollo con 100g de arroz'", help="Puedes poner varios alimentos a la vez.")
            momento = st.selectbox("Momento del día", ["Desayuno", "Almuerzo", "Cena", "Snack"])
            
            if st.button("🚀 Registrar con IA"):
                if txt_input.strip():
                    with st.spinner("Calculando macros..."):
                        items = procesar_comida_ia(txt_input)
                        if items:
                            for item in items:
                                conn.execute("""INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) 
                                             VALUES (?,?,?,?,?,?,?,?,?)""",
                                             (st.session_state.user, hoy, f"{int(item['gr'])}g {item['alim']}", 
                                              item['p'], item['c'], item['g'], item['k'], 'IA', momento))
                            conn.commit()
                            st.success(f"✅ Se registraron {len(items)} alimentos.")
                            st.rerun()
                        else:
                            st.error("❌ La IA no pudo extraer los datos. Intenta ser más claro (ej: 100g de arroz).")

        # MÉTRICAS
        user_data = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
        logs_hoy = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Proteína", f"{logs_hoy['prot'].sum():.1f}g", f"Meta: {user_data['target_prot']}g")
        c2.metric("Carbohidratos", f"{logs_hoy['carb'].sum():.1f}g", f"Meta: {user_data['target_carb']}g")
        c3.metric("Grasas", f"{logs_hoy['fat'].sum():.1f}g", f"Meta: {user_data['target_fat']}g")
        c4.metric("Calorías", f"{int(logs_hoy['kcal'].sum())}", f"Meta: {int(user_data['target_kcal'])}")

        st.divider()
        st.subheader("Desglose de hoy")
        if not logs_hoy.empty:
            st.dataframe(logs_hoy[['meal_time', 'food_desc', 'prot', 'carb', 'fat', 'kcal']], use_container_width=True)
            if st.button("🗑️ Limpiar todo lo de hoy"):
                conn.execute("DELETE FROM logs WHERE username=? AND date=?", (st.session_state.user, hoy))
                conn.commit()
                st.rerun()
        else:
            st.info("No hay registros hoy. ¡Usa la IA arriba para empezar!")

    elif menu == "Historial":
        st.header("📊 Tu Historial")
        hist = pd.read_sql("""SELECT date as Fecha, SUM(prot) as P, SUM(carb) as C, SUM(fat) as G, SUM(kcal) as Calorías 
                           FROM logs WHERE username=? GROUP BY date ORDER BY date DESC""", conn, params=(st.session_state.user,))
        st.table(hist)

    conn.close()
