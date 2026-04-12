import streamlit as st
import pandas as pd
import sqlite3
import os
import re
from datetime import datetime, timedelta

# --- CONFIGURACIÓN Y HORA ---
st.set_page_config(page_title="Unite Nutrition", page_icon="🏋️", layout="wide")

def get_local_time():
    """Ajusta la hora a UTC-5 (Perú)"""
    return datetime.utcnow() - timedelta(hours=5)

# --- BASE DE DATOS ---
DB_PATH = "unite_nutrition_vFinal.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # is_active: 0 = Pendiente/Bloqueado, 1 = Activo
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, is_admin INTEGER, is_active INTEGER,
                 target_prot REAL, target_carb REAL, target_fat REAL, target_kcal REAL, expiry_date TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS master_food
                 (food_name TEXT PRIMARY KEY, p100 REAL, c100 REAL, g100 REAL, k100 REAL, category TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, 
                 food_desc TEXT, prot REAL, carb REAL, fat REAL, kcal REAL, status TEXT, meal_time TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS biometrics 
                 (username TEXT, date TEXT, weight REAL, sleep INTEGER, stress INTEGER, PRIMARY KEY (username, date))''')
    
    # Usuario Maestro (Erick)
    c.execute("INSERT OR IGNORE INTO users VALUES ('erick', 'erickale2005', 1, 1, 0, 0, 0, 0, '2099-12-31')")
    conn.commit()
    conn.close()

init_db()

# --- MANEJO DE SESIÓN ---
if 'user' not in st.session_state: st.session_state.user = None
if 'is_admin' not in st.session_state: st.session_state.is_admin = 0

# --- PANTALLA DE ACCESO (LOGIN/REGISTRO) ---
if st.session_state.user is None:
    st.title("🏋️ Unite Nutrition - Coach Erick")
    t1, t2 = st.tabs(["🔑 Iniciar Sesión", "📝 Registro"])
    
    with t1:
        u = st.text_input("Usuario").lower().strip()
        p = st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            conn = sqlite3.connect(DB_PATH)
            res = pd.read_sql("SELECT * FROM users WHERE username=? AND password=?", conn, params=(u, p))
            conn.close()
            if not res.empty:
                if res.iloc[0]['is_active'] == 1:
                    st.session_state.user = u
                    st.session_state.is_admin = res.iloc[0]['is_admin']
                    st.rerun()
                else:
                    st.error("🚫 Tu cuenta está pendiente de activación. Contacta al Coach.")
            else:
                st.error("Usuario o contraseña incorrectos.")

    with t2:
        nu = st.text_input("Nombre de Usuario (Solo letras)").lower().strip()
        np = st.text_input("Clave Nueva", type="password")
        if st.button("Crear Cuenta"):
            if nu and np and nu.isalpha():
                conn = sqlite3.connect(DB_PATH)
                try:
                    # Se registra como inactivo (is_active=0)
                    conn.execute("INSERT INTO users (username, password, is_admin, is_active, target_prot, target_carb, target_fat, target_kcal, expiry_date) VALUES (?, ?, 0, 0, 0, 0, 0, 0, '2099-12-31')", (nu, np))
                    conn.commit()
                    st.success("✅ Registro enviado. Espera a que el Coach te dé acceso.")
                except: st.error("El usuario ya existe.")
                finally: conn.close()
            else: st.warning("Nombre inválido (usa solo letras).")
    st.stop()

# --- INTERFAZ PRINCIPAL ---
st.sidebar.title(f"🚀 {'COACH' if st.session_state.is_admin else 'ATLETA'}")
st.sidebar.write(f"Usuario: **{st.session_state.user}**")

if st.session_state.is_admin:
    opciones = ["Gestión de Atletas", "Progreso en Tiempo Real", "Maestro de Alimentos", "Mi Diario Personal"]
else:
    opciones = ["Mi Diario", "Mi Historial"]

menu = st.sidebar.radio("Navegación", opciones)

# --- LÓGICA DEL COACH ---
if st.session_state.is_admin:
    if menu == "Gestión de Atletas":
        st.header("👥 Control de Acceso")
        conn = sqlite3.connect(DB_PATH)
        usuarios = pd.read_sql("SELECT username, is_active FROM users WHERE is_admin=0", conn)
        
        for _, row in usuarios.iterrows():
            c1, c2, c3 = st.columns([2, 1, 1])
            estado = "✅ Activo" if row['is_active'] else "⏳ Pendiente"
            c1.write(f"**{row['username']}** - Estado: {estado}")
            if c2.button("Activar/Bloquear", key=f"btn_{row['username']}"):
                nuevo = 0 if row['is_active'] else 1
                conn.execute("UPDATE users SET is_active=? WHERE username=?", (nuevo, row['username']))
                conn.commit(); st.rerun()
            if c3.button("Eliminar", key=f"del_{row['username']}"):
                conn.execute("DELETE FROM users WHERE username=?", (row['username'],))
                conn.commit(); st.rerun()
        conn.close()

    elif menu == "Progreso en Tiempo Real":
        st.header("📈 Macros de Alumnos (Hoy)")
        conn = sqlite3.connect(DB_PATH)
        hoy = get_local_time().strftime('%Y-%m-%d')
        alumnos = pd.read_sql("SELECT * FROM users WHERE is_admin=0 AND is_active=1", conn)
        
        for _, al in alumnos.iterrows():
            with st.expander(f"👤 {al['username'].upper()}"):
                cons = pd.read_sql("SELECT SUM(prot) as p, SUM(carb) as c, SUM(fat) as g, SUM(kcal) as k FROM logs WHERE username=? AND date=?", conn, params=(al['username'], hoy)).fillna(0).iloc[0]
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Proteína", f"{cons['p']:.1f}g", f"Meta: {al['target_prot']}")
                col2.metric("Carbos", f"{cons['c']:.1f}g", f"Meta: {al['target_carb']}")
                col3.metric("Grasas", f"{cons['g']:.1f}g", f"Meta: {al['target_fat']}")
                col4.metric("Kcal", f"{int(cons['k'])}", f"Meta: {int(al['target_kcal'])}")
                
                st.subheader("⚙️ Ajustar Metas")
                with st.form(f"form_{al['username']}"):
                    ap = st.number_input("P Meta", value=float(al['target_prot']))
                    ac = st.number_input("C Meta", value=float(al['target_carb']))
                    ag = st.number_input("G Meta", value=float(al['target_fat']))
                    ak = st.number_input("Kcal Meta", value=float(al['target_kcal']))
                    if st.form_submit_button("Actualizar Plan"):
                        conn.execute("UPDATE users SET target_prot=?, target_carb=?, target_fat=?, target_kcal=? WHERE username=?", (ap, ac, ag, ak, al['username']))
                        conn.commit(); st.success("Actualizado"); st.rerun()
        conn.close()

# --- LÓGICA DEL DIARIO (ATLETAS Y COACH PERSONAL) ---
if menu in ["Mi Diario", "Mi Diario Personal"]:
    st.header(f"📓 Diario - {st.session_state.user}")
    conn = sqlite3.connect(DB_PATH)
    hoy = get_local_time().strftime('%Y-%m-%d')
    m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
    
    # Dashboard de Macros
    cons = pd.read_sql("SELECT SUM(prot) as p, SUM(carb) as c, SUM(fat) as g, SUM(kcal) as k FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy)).fillna(0).iloc[0]
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Proteína", f"{cons['p']:.1f}g", f"/ {m['target_prot']}")
    c1.progress(min(cons['p']/m['target_prot'], 1.0) if m['target_prot'] > 0 else 0.0)
    c2.metric("Carbos", f"{cons['c']:.1f}g", f"/ {m['target_carb']}")
    c2.progress(min(cons['c']/m['target_carb'], 1.0) if m['target_carb'] > 0 else 0.0)
    c3.metric("Grasas", f"{cons['g']:.1f}g", f"/ {m['target_fat']}")
    c3.progress(min(cons['g']/m['target_fat'], 1.0) if m['target_fat'] > 0 else 0.0)
    c4.metric("Kcal", f"{int(cons['k'])}", f"/ {int(m['target_kcal'])}")
    c4.progress(min(cons['k']/m['target_kcal'], 1.0) if m['target_kcal'] > 0 else 0.0)

    # Registro de Alimentos
    for t in ["Desayuno", "Almuerzo", "Cena", "Snacks"]:
        with st.expander(f"➕ Añadir a {t}"):
            foods = pd.read_sql("SELECT * FROM master_food", conn)
            sel = st.selectbox("Alimento", [""] + foods['food_name'].tolist(), key=f"sel_{t}")
            gms = st.number_input("Gramos", 1.0, 1000.0, 100.0, key=f"gms_{t}")
            if st.button("Registrar", key=f"btn_{t}"):
                if sel:
                    f_info = foods[foods['food_name'] == sel].iloc[0]
                    f = gms / 100
                    conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)",
                                 (st.session_state.user, hoy, f"{int(gms)}g {sel}", f_info['p100']*f, f_info['c100']*f, f_info['g100']*f, f_info['k100']*f, 'Validado', t))
                    conn.commit(); st.rerun()

    # Tabla de lo comido hoy
    st.subheader("🍽️ Resumen del día")
    res = pd.read_sql("SELECT id, meal_time as Tiempo, food_desc as Alimento, round(kcal,0) as Kcal FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
    st.table(res.drop(columns=['id']))
    if not res.empty:
        borrar = st.selectbox("Eliminar registro por ID", res['id'].tolist())
        if st.button("Borrar Alimento"):
            conn.execute("DELETE FROM logs WHERE id=?", (borrar,))
            conn.commit(); st.rerun()
    conn.close()

# --- BOTÓN DE SALIDA ---
if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state.user = None
    st.session_state.is_admin = 0
    st.rerun()
