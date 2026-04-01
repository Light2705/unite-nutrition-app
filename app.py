import streamlit as st
import pandas as pd
import sqlite3
import os
import re
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN DE PÁGINA (SIEMPRE PRIMERO Y FUERA DE TODO) ---
st.set_page_config(page_title="Unite Nutrition - Coach Erick", page_icon="🏋️", layout="wide")

# --- FUNCIÓN DE VALIDACIÓN ---
def validar_solo_letras(texto):
    if re.search(r'\d', texto):
        st.error("❌ No se permiten números en este campo.")
        return False
    return True

# --- CONFIGURACIÓN DE RUTAS ---
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
    try:
        c.execute("ALTER TABLE logs ADD COLUMN meal_time TEXT DEFAULT 'General'")
    except: pass
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

# --- LÓGICA DE PERSISTENCIA ---
if 'user' not in st.session_state:
    params = st.query_params
    if "user" in params:
        u_url = params["user"]
        conn = sqlite3.connect(DB_PATH)
        res = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(u_url,))
        conn.close()
        if not res.empty:
            venc = datetime.strptime(res.iloc[0]['expiry_date'], '%Y-%m-%d')
            if datetime.now() <= venc:
                st.session_state.user = res.iloc[0]['username']
                st.session_state.admin = res.iloc[0]['is_admin']

# --- LOGIN / REGISTRO ---
if 'user' not in st.session_state:
    st.title("🏋️ Unite Nutrition - Erick Quiroz")
    tab_login, tab_reg = st.tabs(["🔑 Iniciar Sesión", "📝 Registro de Atleta"])
    with tab_login:
        u = st.text_input("Usuario", key="login_u")
        p = st.text_input("Contraseña", type="password", key="login_p")
        if st.button("Entrar", key="btn_login_principal"):
            conn = sqlite3.connect(DB_PATH)
            res = pd.read_sql("SELECT * FROM users WHERE username=? AND password=?", conn, params=(u, p))
            conn.close()
            if not res.empty:
                venc = datetime.strptime(res.iloc[0]['expiry_date'], '%Y-%m-%d')
                if datetime.now() <= venc:
                    st.session_state.user = u
                    st.session_state.admin = res.iloc[0]['is_admin']
                    st.query_params["user"] = u
                    st.rerun()
                else: st.error("⚠️ Acceso vencido o pendiente.")
            else: st.error("Credenciales incorrectas.")
    with tab_reg:
        nu = st.text_input("Nuevo Usuario (Sin números)", key="reg_u")
        np = st.text_input("Nueva Contraseña", type="password", key="reg_p")
        if st.button("Crear Cuenta", key="btn_reg_principal"):
            if nu and np and validar_solo_letras(nu):
                conn = sqlite3.connect(DB_PATH)
                venc_b = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                try:
                    conn.execute("INSERT INTO users VALUES (?, ?, 0, 0, 0, 0, 0, ?)", (nu, np, venc_b))
                    conn.commit(); st.success("✅ ¡Registro exitoso! Avisa al Coach.")
                except: st.error("El usuario ya existe.")
                conn.close()
    st.stop()

# --- BARRA LATERAL (UNA SOLA VEZ) ---
st.sidebar.title(f"🚀 {'Coach' if st.session_state.admin else 'Atleta'}")
st.sidebar.write(f"Usuario: **{st.session_state.user}**")
if st.sidebar.button("🔄 Actualizar", key="sidebar_refresh"): st.rerun()

opciones = ["Mi Diario", "Historial"]
if st.session_state.admin: opciones = ["Gestión de Clientes", "Maestro de Alimentos", "Mi Diario", "Historial"]
menu = st.sidebar.radio("Navegación", opciones)

# --- FUNCIONES DE HISTORIAL ---
def mostrar_historial(usuario):
    st.subheader(f"📅 Historial: {usuario}")
    conn = sqlite3.connect(DB_PATH)
    dias_es = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
    df_bio = pd.read_sql("SELECT date, weight FROM biometrics WHERE username=? ORDER BY date ASC", conn, params=(usuario,))
    if not df_bio.empty:
        st.write("📈 Evolución del Peso")
        df_bio['date'] = pd.to_datetime(df_bio['date']).dt.strftime('%d/%m')
        st.line_chart(df_bio.set_index('date')['weight'])
    query = "SELECT date as Fecha, round(SUM(prot),1) as P, round(SUM(carb),1) as C, round(SUM(fat),1) as G, round(SUM(kcal),0) as Kcal FROM logs WHERE username=? GROUP BY date ORDER BY date DESC LIMIT 14"
    st.dataframe(pd.read_sql(query, conn, params=(usuario,)), use_container_width=True, hide_index=True)
    conn.close()

# --- LÓGICA DE MENÚS ---
if st.session_state.admin and menu == "Gestión de Clientes":
    st.header("👥 Control de Alumnos")
    conn = sqlite3.connect(DB_PATH)
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    pendientes = pd.read_sql("SELECT * FROM logs WHERE status='Pendiente'", conn)
    if not pendientes.empty:
        st.subheader("🔔 Pendientes por Validar")
        for _, r in pendientes.iterrows():
            with st.expander(f"🔴 {r['username']} - {r['food_desc']}"):
                c1, c2, c3, c4 = st.columns(4)
                pv = c1.number_input("P/100g", key=f"pv_{r['id']}")
                cv = c2.number_input("C/100g", key=f"cv_{r['id']}")
                gv = c3.number_input("G/100g", key=f"gv_{r['id']}")
                kv = c4.number_input("K/100g", key=f"kv_{r['id']}")
                if st.button("✅ Validar", key=f"btn_v_{r['id']}"):
                    try: gr = float(r['food_desc'].split('g')[0])
                    except: gr = 100.0
                    f = gr/100
                    conn.execute("UPDATE logs SET prot=?, carb=?, fat=?, kcal=?, status='Validado' WHERE id=?", (pv*f, cv*f, gv*f, kv*f, r['id']))
                    conn.commit(); st.rerun()

    alumnos = pd.read_sql("SELECT username FROM users", conn)['username'].tolist()
    sel = st.selectbox("Ver Alumno:", [""] + alumnos)
    if sel:
        m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(sel,)).iloc[0]
        t1, t2, t3 = st.tabs(["📊 Hoy", "📅 Historial", "⚙️ Plan"])
        with t1:
            det = pd.read_sql("SELECT id, food_desc, kcal FROM logs WHERE username=? AND date=?", conn, params=(sel, hoy))
            st.table(det)
        with t2: mostrar_historial(sel)
        with t3:
            p_n, c_n, g_n, k_n = st.number_input("P Meta", value=m['target_prot']), st.number_input("C Meta", value=m['target_carb']), st.number_input("G Meta", value=m['target_fat']), st.number_input("Kcal Meta", value=m['target_kcal'])
            if st.button("💾 Guardar Plan"):
                conn.execute("UPDATE users SET target_prot=?, target_carb=?, target_fat=?, target_kcal=? WHERE username=?", (p_n, c_n, g_n, k_n, sel))
                conn.commit(); st.success("Plan Actualizado"); st.rerun()
    conn.close()

elif menu == "Mi Diario":
    conn = sqlite3.connect(DB_PATH)
    hoy = datetime.now().strftime('%Y-%m-%d')
    m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
    st.header(f"📓 Diario - {st.session_state.user}")

    with st.expander("🧪 Registrar Peso de Hoy"):
        p_w = st.number_input("Peso (kg)", 30.0, 200.0, 74.0)
        if st.button("Guardar Peso"):
            conn.execute("INSERT OR REPLACE INTO biometrics (username, date, weight, sleep, stress) VALUES (?,?,?,8,3)", (st.session_state.user, hoy, p_w))
            conn.commit(); st.success("Peso registrado")

    cons = pd.read_sql("SELECT SUM(prot) as p, SUM(carb) as c, SUM(fat) as g, SUM(kcal) as k FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy)).fillna(0).iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Proteína", f"{cons['p']:.1f}g", f"/{m['target_prot']}")
    c2.metric("Carbos", f"{cons['c']:.1f}g", f"/{m['target_carb']}")
    c3.metric("Grasas", f"{cons['g']:.1f}g", f"/{m['target_fat']}")
    c4.metric("Kcal", f"{int(cons['k'])}", f"/{int(m['target_kcal'])}")

    for t in ["Desayuno", "Almuerzo", "Cena", "Snacks"]:
        st.subheader(t)
        logs_t = pd.read_sql("SELECT id, food_desc, kcal FROM logs WHERE username=? AND date=? AND meal_time=?", conn, params=(st.session_state.user, hoy, t))
        for _, r in logs_t.iterrows():
            col1, col2 = st.columns([5, 1])
            col1.write(f"🍳 {r['food_desc']} ({int(r['kcal'])} kcal)")
            if col2.button("🗑️", key=f"del_{r['id']}"):
                conn.execute("DELETE FROM logs WHERE id=?", (r['id'],)); conn.commit(); st.rerun()
        
        with st.expander(f"➕ Añadir a {t}"):
            alims = pd.read_sql("SELECT food_name FROM master_food", conn)
            sel_f = st.selectbox("Alimento", [""] + alims['food_name'].tolist() + ["➕ OTRO"], key=f"sel_{t}")
            gr = st.number_input("Gramos", 1.0, 2000.0, 100.0, key=f"gr_{t}")
            if st.button("Registrar", key=f"btn_{t}"):
                if sel_f == "➕ OTRO":
                    conn.execute("INSERT INTO logs (username, date, food_desc, status, meal_time, prot, carb, fat, kcal) VALUES (?,?,?,?,?,0,0,0,0)", (st.session_state.user, hoy, f"{int(gr)}g Alimento Nuevo", 'Pendiente', t))
                else:
                    d = pd.read_sql("SELECT * FROM master_food WHERE food_name=?", conn, params=(sel_f,)).iloc[0]
                    f = gr/100
                    conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)",
                                 (st.session_state.user, hoy, f"{int(gr)}g {sel_f}", d['p100']*f, d['c100']*f, d['g100']*f, d['k100']*f, 'Validado', t))
                conn.commit(); st.rerun()
    conn.close()

elif menu == "Maestro de Alimentos":
    st.header("📂 Base de Datos")
    search = st.text_input("🔍 Buscar...")
    conn = sqlite3.connect(DB_PATH)
    df_m = pd.read_sql("SELECT * FROM master_food", conn)
    if search: df_m = df_m[df_m['food_name'].str.contains(search, case=False)]
    st.dataframe(df_m, use_container_width=True, hide_index=True)
    with st.expander("➕ Nuevo Alimento"):
        with st.form("n_f"):
            n = st.text_input("Nombre")
            cat = st.text_input("Categoría")
            np, nc, ng, nk = st.number_input("P"), st.number_input("C"), st.number_input("G"), st.number_input("K")
            if st.form_submit_button("Guardar"):
                conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (n, np, nc, ng, nk, cat))
                conn.commit(); st.success("Guardado"); st.rerun()
    conn.close()

elif menu == "Historial": mostrar_historial(st.session_state.user)

if st.sidebar.button("🚪 Cerrar Sesión", key="sidebar_logout"):
    st.query_params.clear(); st.session_state.clear(); st.rerun()
