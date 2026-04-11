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

# --- 2. CONFIGURACIÓN DE BASE DE DATOS Y RUTAS ---
def get_local_time():
    # Ajuste para hora Perú (UTC-5)
    return datetime.utcnow() - timedelta(hours=5)

DB_PATH = os.path.join(os.getcwd(), "unite_nutrition_vFinal.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Tabla de Usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, is_admin INTEGER, 
                 target_prot REAL, target_carb REAL, target_fat REAL, target_kcal REAL, expiry_date TEXT)''')
    # Tabla de Registros de Comida
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, 
                 food_desc TEXT, prot REAL, carb REAL, fat REAL, kcal REAL, status TEXT, meal_time TEXT)''')
    # Usuario administrador por defecto
    c.execute("INSERT OR IGNORE INTO users VALUES ('erick', 'erickale2005', 1, 180, 250, 70, 2400, '2099-12-31')")
    conn.commit()
    conn.close()

init_db()

# --- 3. PROCESAMIENTO DE IA (VERSIÓN INDESTRUCTIBLE) ---
def procesar_comida_ia(texto_usuario):
    # Prompt diseñado para que la IA no hable, solo entregue datos
    prompt = f"""
    Eres un extractor de datos nutricionales. Analiza: "{texto_usuario}".
    RESPONDE ÚNICAMENTE CON ESTE FORMATO (una línea por alimento):
    Alimento | Gramos | Proteína | Carbohidratos | Grasas | Calorías
    
    Si no se especifica peso, asume una porción estándar de 100g.
    Ejemplo: Pollo | 150 | 30 | 0 | 10 | 220
    """
    try:
        response = model.generate_content(prompt)
        # Filtramos solo líneas que tengan el separador | para ignorar introducciones o basura
        lineas = [l.strip() for l in response.text.split('\n') if '|' in l and 'Gramos' not in l]
        
        resultados = []
        for linea in lineas:
            # Limpiamos asteriscos y espacios extra
            partes = [p.strip() for p in linea.replace('*', '').split('|')]
            if len(partes) >= 6:
                # Extractor numérico con Regex para ignorar "g", "gr", "kcal", etc.
                def solo_num(t):
                    f = re.findall(r"[-+]?\d*\.\d+|\d+", str(t))
                    return float(f[0]) if f else 0.0

                resultados.append({
                    "alim": partes[0],
                    "gr": solo_num(partes[1]),
                    "p": solo_num(partes[2]),
                    "c": solo_num(partes[3]),
                    "g": solo_num(partes[4]),
                    "k": solo_num(partes[5])
                })
        return resultados
    except:
        return None

# --- 4. INTERFAZ DE STREAMLIT ---
st.set_page_config(page_title="Unite Nutrition App", page_icon="🚀", layout="wide")

# Gestión de Sesión (Login)
if 'user' not in st.session_state:
    st.title("🏋️ Unite Nutrition - Acceso")
    with st.form("login_form"):
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
                st.error("❌ Usuario o contraseña incorrectos.")
else:
    # --- MENÚ Y NAVEGACIÓN ---
    st.sidebar.title(f"🚀 {'Coach' if st.session_state.admin else 'Atleta'}")
    st.sidebar.write(f"Usuario: **{st.session_state.user}**")
    
    opciones = ["Mi Diario", "Historial"]
    if st.session_state.admin:
        opciones = ["Gestión de Clientes"] + opciones
        
    menu = st.sidebar.radio("Navegación", opciones)
    
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()

    conn = sqlite3.connect(DB_PATH)

    # --- MÓDULO: DIARIO ---
    if menu == "Mi Diario":
        hoy = get_local_time().strftime('%Y-%m-%d')
        st.title(f"📓 Diario de Nutrición - {hoy}")
        
        # REGISTRO MÁGICO CON IA
        with st.expander("✨ REGISTRO MÁGICO CON IA", expanded=True):
            input_ia = st.text_area("¿Qué comiste?", placeholder="Ej: 150g de pollo frito con una taza de arroz")
            momento = st.selectbox("Momento", ["Desayuno", "Almuerzo", "Cena", "Snacks"])
            if st.button("🚀 Registrar con IA"):
                if input_ia:
                    with st.spinner("Procesando datos..."):
                        datos = procesar_comida_ia(input_ia)
                        if datos:
                            for item in datos:
                                conn.execute("""INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) 
                                             VALUES (?,?,?,?,?,?,?,?,?)""",
                                             (st.session_state.user, hoy, f"{int(item['gr'])}g {item['alim']}", 
                                              item['p'], item['c'], item['g'], item['k'], 'IA', momento))
                            conn.commit()
                            st.success("✅ Alimentos registrados correctamente.")
                            st.rerun()
                        else:
                            st.error("❌ No se pudo procesar. Intenta escribir algo como '100g de carne'.")

        # RESUMEN DE METAS Y MÉTRICAS
        user_meta = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
        logs_hoy = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Proteína", f"{logs_hoy['prot'].sum():.1f}g", f"Meta: {user_meta['target_prot']}g")
        c2.metric("Carbos", f"{logs_hoy['carb'].sum():.1f}g", f"Meta: {user_meta['target_carb']}g")
        c3.metric("Grasas", f"{logs_hoy['fat'].sum():.1f}g", f"Meta: {user_meta['target_fat']}g")
        c4.metric("Calorías", f"{int(logs_hoy['kcal'].sum())}", f"Meta: {int(user_meta['target_kcal'])}")

        st.divider()
        st.subheader("Registros de hoy")
        st.dataframe(logs_hoy[['meal_time', 'food_desc', 'prot', 'carb', 'fat', 'kcal']], use_container_width=True)
        
        if not logs_hoy.empty:
            id_borrar = st.selectbox("Seleccionar ID para eliminar", logs_hoy['id'])
            if st.button("🗑️ Eliminar Registro"):
                conn.execute("DELETE FROM logs WHERE id=?", (id_borrar,))
                conn.commit()
                st.rerun()

    # --- MÓDULO: GESTIÓN DE CLIENTES (ADMIN) ---
    elif menu == "Gestión de Clientes":
        st.title("👥 Gestión de Alumnos")
        alumnos = pd.read_sql("SELECT * FROM users WHERE is_admin=0", conn)
        if not alumnos.empty:
            sel_u = st.selectbox("Seleccionar Alumno", alumnos['username'].tolist())
            u_info = alumnos[alumnos['username'] == sel_u].iloc[0]
            
            with st.form("metas_alumnos"):
                st.write(f"Actualizando metas para: **{sel_u}**")
                col1, col2 = st.columns(2)
                p_m = col1.number_input("Proteína Meta", value=u_info['target_prot'])
                c_m = col2.number_input("Carbos Meta", value=u_info['target_carb'])
                g_m = col1.number_input("Grasas Meta", value=u_info['target_fat'])
                k_m = col2.number_input("Kcal Meta", value=u_info['target_kcal'])
                if st.form_submit_button("Actualizar Metas"):
                    conn.execute("UPDATE users SET target_prot=?, target_carb=?, target_fat=?, target_kcal=? WHERE username=?", 
                                 (p_m, c_m, g_m, k_m, sel_u))
                    conn.commit()
                    st.success(f"✅ Metas de {sel_u} actualizadas.")
        else:
            st.info("No hay alumnos registrados bajo tu supervisión.")

    # --- MÓDULO: HISTORIAL ---
    elif menu == "Historial":
        st.title("📊 Historial de Consumo")
        df_hist = pd.read_sql("""SELECT date, SUM(prot) as P, SUM(carb) as C, SUM(fat) as G, SUM(kcal) as Kcal 
                               FROM logs WHERE username=? GROUP BY date ORDER BY date DESC""", 
                               conn, params=(st.session_state.user,))
        st.dataframe(df_hist, use_container_width=True)

    conn.close()
