import streamlit as st
import pandas as pd
import sqlite3
import os
import re
from datetime import datetime, timedelta

# --- FUNCIÓN PARA OBTENER HORA LOCAL (PERÚ UTC-5) ---
def get_local_time():
    """Ajusta la hora de los servidores (UTC) a la hora de Perú (UTC-5)"""
    return datetime.utcnow() - timedelta(hours=5)

# --- FUNCIÓN DE VALIDACIÓN (SOLO LETRAS) ---
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
    
    # 1. Tabla de Usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, is_admin INTEGER, 
                 target_prot REAL, target_carb REAL, target_fat REAL, target_kcal REAL, expiry_date TEXT)''')
    
    # Migración: Verificar columnas en users
    cursor = conn.execute('PRAGMA table_info(users)')
    columnas_actuales = [column[1] for column in cursor.fetchall()]
    columnas_necesarias = [
        ("target_prot", "REAL DEFAULT 0"), ("target_carb", "REAL DEFAULT 0"),
        ("target_fat", "REAL DEFAULT 0"), ("target_kcal", "REAL DEFAULT 0"),
        ("expiry_date", "TEXT DEFAULT '2099-12-31'")
    ]
    for col_nombre, col_tipo in columnas_necesarias:
        if col_nombre not in columnas_actuales:
            c.execute(f"ALTER TABLE users ADD COLUMN {col_nombre} {col_tipo}")

    # 2. Maestro de Alimentos
    c.execute('''CREATE TABLE IF NOT EXISTS master_food
                 (food_name TEXT PRIMARY KEY, p100 REAL, c100 REAL, g100 REAL, k100 REAL, category TEXT)''')
    
    # 3. Logs de Comidas
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, 
                 food_desc TEXT, prot REAL, carb REAL, fat REAL, kcal REAL, status TEXT, meal_time TEXT)''')
    
    # Migración: meal_time en logs
    cursor_logs = conn.execute('PRAGMA table_info(logs)')
    if 'meal_time' not in [col[1] for col in cursor_logs.fetchall()]:
        c.execute("ALTER TABLE logs ADD COLUMN meal_time TEXT DEFAULT 'General'")
        
    # 4. Biometría
    c.execute('''CREATE TABLE IF NOT EXISTS biometrics 
                 (username TEXT, date TEXT, weight REAL, sleep INTEGER, stress INTEGER, 
                 PRIMARY KEY (username, date))''')
    
    # 5. Insertar Administrador
    c.execute("""INSERT OR IGNORE INTO users 
                 (username, password, is_admin, target_prot, target_carb, target_fat, target_kcal, expiry_date) 
                 VALUES ('erick', 'erickale2005', 1, 0, 0, 0, 0, '2099-12-31')""")
    conn.commit()
    conn.close()

init_db()

# --- ESTILOS ---
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: bold; }
    div[data-testid="metric-container"]:nth-child(1) { color: #FF4B4B; } 
    div[data-testid="metric-container"]:nth-child(2) { color: #4BA3FF; } 
    div[data-testid="metric-container"]:nth-child(3) { color: #FFCA4B; } 
    </style>
    """, unsafe_allow_html=True)

# --- MANEJO DE SESIÓN SEGURO ---
if 'user' not in st.session_state: st.session_state.user = None
if 'admin' not in st.session_state: st.session_state.admin = 0

# Persistencia por URL
if st.session_state.user is None and "user" in st.query_params:
    u_url = st.query_params["user"]
    conn = sqlite3.connect(DB_PATH)
    res = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(u_url,))
    conn.close()
    if not res.empty:
        st.session_state.user = res.iloc[0]['username']
        st.session_state.admin = res.iloc[0]['is_admin']

# --- FLUJO DE PANTALLAS ---
if st.session_state.user is None:
    st.title("🏋️ Unite Nutrition - Erick Quiroz")
    t1, t2 = st.tabs(["🔑 Login", "📝 Registro"])
    with t1:
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            conn = sqlite3.connect(DB_PATH)
            res = pd.read_sql("SELECT * FROM users WHERE username=? AND password=?", conn, params=(u, p))
            conn.close()
            if not res.empty:
                st.session_state.user = u
                st.session_state.admin = res.iloc[0]['is_admin']
                st.query_params["user"] = u
                st.rerun()
    with t2:
        nu = st.text_input("Nuevo Atleta (Letras)")
        np = st.text_input("Clave", type="password")
        if st.button("Registrarse"):
            if nu and np and validar_solo_letras(nu):
                conn = sqlite3.connect(DB_PATH)
                try:
                    conn.execute("INSERT INTO users (username, password, is_admin, target_prot, target_carb, target_fat, target_kcal, expiry_date) VALUES (?, ?, 0, 0, 0, 0, 0, '2026-12-31')", (nu, np))
                    conn.commit(); st.success("Creado.")
                except: st.error("Existe.")
                conn.close()
else:
    # --- APP PRINCIPAL ---
    st.sidebar.title(f"🚀 {'Coach' if st.session_state.admin == 1 else 'Atleta'}")
    st.sidebar.write(f"Hola, **{st.session_state.user}**")
    
    opciones = ["Mi Diario", "Historial"]
    if st.session_state.admin == 1: 
        opciones = ["Gestión de Clientes", "Maestro de Alimentos", "Mi Diario", "Historial"]
    menu = st.sidebar.radio("Navegación", opciones)

    def mostrar_historial(usuario):
        st.subheader(f"📅 Historial: {usuario}")
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("SELECT date as Fecha, round(SUM(prot),1) as P, round(SUM(carb),1) as C, round(SUM(fat),1) as G, round(SUM(kcal),0) as Kcal FROM logs WHERE username=? GROUP BY date ORDER BY date DESC", conn, params=(usuario,))
        df_bio = pd.read_sql("SELECT date, weight FROM biometrics WHERE username=? ORDER BY date ASC", conn, params=(usuario,))
        conn.close()
        if not df_bio.empty:
            st.line_chart(df_bio.set_index('date')['weight'])
        st.dataframe(df, use_container_width=True)

    if menu == "Gestión de Clientes" and st.session_state.admin == 1:
        st.header("👥 Gestión de Alumnos")
        conn = sqlite3.connect(DB_PATH)
        # Pendientes por clasificar
        pend = pd.read_sql("SELECT * FROM logs WHERE status='Pendiente'", conn)
        if not pend.empty:
            st.subheader("🔔 Alimentos por Validar")
            for _, r in pend.iterrows():
                with st.expander(f"{r['username']} - {r['food_desc']}"):
                    c1, c2, c3 = st.columns(3); p_v = c1.number_input("P", 0.0, key=f"p{r['id']}"); c_v = c2.number_input("C", 0.0, key=f"c{r['id']}"); g_v = c3.number_input("G", 0.0, key=f"g{r['id']}")
                    if st.button("Validar", key=f"v{r['id']}"):
                        conn.execute("UPDATE logs SET prot=?, carb=?, fat=?, kcal=?, status='Validado' WHERE id=?", (p_v, c_v, g_v, (p_v*4+c_v*4+g_v*9), r['id']))
                        conn.commit(); st.rerun()
        
        # Editar Metas
        usuarios = pd.read_sql("SELECT username FROM users", conn)
        sel = st.selectbox("Atleta:", [""] + usuarios['username'].tolist())
        if sel:
            m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(sel,)).iloc[0]
            with st.form("metas"):
                mp = st.number_input("P Meta", value=float(m['target_prot']))
                mc = st.number_input("C Meta", value=float(m['target_carb']))
                mg = st.number_input("G Meta", value=float(m['target_fat']))
                mk = st.number_input("Kcal Meta", value=float(m['target_kcal']))
                if st.form_submit_button("Guardar"):
                    conn.execute("UPDATE users SET target_prot=?, target_carb=?, target_fat=?, target_kcal=? WHERE username=?", (mp, mc, mg, mk, sel))
                    conn.commit(); st.success("OK"); st.rerun()
        conn.close()

    elif menu == "Mi Diario":
        conn = sqlite3.connect(DB_PATH)
        m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
        hoy = get_local_time().strftime('%Y-%m-%d')
        st.header(f"📓 Diario - {hoy}")
        
        # Dashboard Macros
        cons = pd.read_sql("SELECT SUM(prot) as p, SUM(carb) as c, SUM(fat) as g, SUM(kcal) as k FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy)).fillna(0).iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Proteína", f"{cons['p']:.1f}g", f"/{m['target_prot']}"); c1.progress(min(cons['p']/m['target_prot'], 1.0) if m['target_prot']>0 else 0.0)
        c2.metric("Carbos", f"{cons['c']:.1f}g", f"/{m['target_carb']}"); c2.progress(min(cons['c']/m['target_carb'], 1.0) if m['target_carb']>0 else 0.0)
        c3.metric("Grasas", f"{cons['g']:.1f}g", f"/{m['target_fat']}"); c3.progress(min(cons['g']/m['target_fat'], 1.0) if m['target_fat']>0 else 0.0)
        c4.metric("Kcal", f"{int(cons['k'])}", f"/{int(m['target_kcal'])}"); c4.progress(min(cons['k']/m['target_kcal'], 1.0) if m['target_kcal']>0 else 0.0)

        # Registro por tiempo
        for t in ["Desayuno", "Almuerzo", "Cena", "Snacks"]:
            with st.expander(f"➕ {t}"):
                alim = st.text_input("¿Qué comiste?", key=f"in_{t}")
                gr = st.number_input("Gramos", 0.0, 1000.0, 100.0, key=f"gr_{t}")
                if st.button("Añadir", key=f"btn_{t}"):
                    # Buscar en maestro
                    match = pd.read_sql("SELECT * FROM master_food WHERE food_name=?", conn, params=(alim,))
                    if not match.empty:
                        f = match.iloc[0]; fac = gr/100
                        conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)", 
                                    (st.session_state.user, hoy, f"{int(gr)}g {alim}", f['p100']*fac, f['c100']*fac, f['g100']*fac, f['k100']*fac, 'Validado', t))
                    else:
                        conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,0,0,0,0,'Pendiente',?)", 
                                    (st.session_state.user, hoy, f"{int(gr)}g {alim}", t))
                    conn.commit(); st.rerun()
        
        resumen = pd.read_sql("SELECT id, meal_time, food_desc, round(kcal,0) as Kcal FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
        st.dataframe(resumen, use_container_width=True, hide_index=True)
        if not resumen.empty:
            if st.button("🗑️ Borrar último"):
                conn.execute("DELETE FROM logs WHERE id=?", (int(resumen.iloc[-1]['id']),))
                conn.commit(); st.rerun()
        conn.close()

    elif menu == "Maestro de Alimentos":
        st.header("📂 Base de Alimentos")
        # --- IMPORTACIÓN EXCEL ---
        with st.expander("📥 Importar Excel"):
            file = st.file_uploader("Sube .xlsx", type=["xlsx"])
            if file and st.button("Procesar Excel"):
                df_ex = pd.read_excel(file)
                conn = sqlite3.connect(DB_PATH)
                for _, r in df_ex.iterrows():
                    p, c, g = float(r['proteina']), float(r['carbos']), float(r['grasas'])
                    conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (str(r['nombre']), p, c, g, (p*4+c*4+g*9), str(r['categoria'])))
                conn.commit(); conn.close(); st.success("Importado.")

        # --- TABLA Y EDICIÓN ---
        conn = sqlite3.connect(DB_PATH)
        busqueda = st.text_input("🔍 Buscar:")
        base = pd.read_sql("SELECT * FROM master_food", conn)
        if busqueda: base = base[base['food_name'].str.contains(busqueda, case=False)]
        st.dataframe(base, use_container_width=True)
        
        with st.form("edicion"):
            st.subheader("Añadir/Editar Alimento")
            en = st.text_input("Nombre"); ec = st.text_input("Categoría")
            ep = st.number_input("P"); ecb = st.number_input("C"); eg = st.number_input("G")
            if st.form_submit_button("Guardar en Maestro"):
                if validar_solo_letras(en):
                    conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (en, ep, ecb, eg, (ep*4+ecb*4+eg*9), ec))
                    conn.commit(); st.rerun()
        conn.close()

    elif menu == "Historial":
        mostrar_historial(st.session_state.user)

    if st.sidebar.button("🚪 Salir"):
        st.query_params.clear()
        st.session_state.user = None; st.session_state.admin = 0
        st.rerun()
