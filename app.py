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
    
    # Migración de columnas para evitar OperationalError
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
    
    # Migración meal_time
    cursor_logs = conn.execute('PRAGMA table_info(logs)')
    if 'meal_time' not in [col[1] for col in cursor_logs.fetchall()]:
        c.execute("ALTER TABLE logs ADD COLUMN meal_time TEXT DEFAULT 'General'")
        
    # 4. Biometría
    c.execute('''CREATE TABLE IF NOT EXISTS biometrics 
                 (username TEXT, date TEXT, weight REAL, sleep INTEGER, stress INTEGER, 
                 PRIMARY KEY (username, date))''')
    
    # 5. Admin Erick
    c.execute("""INSERT OR IGNORE INTO users 
                 (username, password, is_admin, target_prot, target_carb, target_fat, target_kcal, expiry_date) 
                 VALUES ('erick', 'erickale2005', 1, 0, 0, 0, 0, '2099-12-31')""")
    conn.commit()
    conn.close()

init_db()

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: bold; }
    div[data-testid="metric-container"]:nth-child(1) { color: #FF4B4B; } 
    div[data-testid="metric-container"]:nth-child(2) { color: #4BA3FF; } 
    div[data-testid="metric-container"]:nth-child(3) { color: #FFCA4B; } 
    </style>
    """, unsafe_allow_html=True)

# --- MANEJO DE SESIÓN ---
if 'user' not in st.session_state: st.session_state.user = None
if 'admin' not in st.session_state: st.session_state.admin = 0

if st.session_state.user is None and "user" in st.query_params:
    u_url = st.query_params["user"]
    conn = sqlite3.connect(DB_PATH)
    res = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(u_url,))
    conn.close()
    if not res.empty:
        st.session_state.user = res.iloc[0]['username']
        st.session_state.admin = res.iloc[0]['is_admin']

# --- ACCESO ---
if st.session_state.user is None:
    st.set_page_config(page_title="Unite Nutrition Login", page_icon="🏋️")
    st.title("🏋️ Unite Nutrition - Coach Erick")
    t1, t2 = st.tabs(["🔑 Iniciar Sesión", "📝 Registro"])
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
        nu = st.text_input("Nombre de Usuario (Solo letras)")
        np = st.text_input("Clave Nueva", type="password")
        if st.button("Crear Cuenta"):
            if nu and np and validar_solo_letras(nu):
                conn = sqlite3.connect(DB_PATH)
                v_blq = (get_local_time() - timedelta(days=1)).strftime('%Y-%m-%d')
                try:
                    conn.execute("INSERT INTO users (username, password, is_admin, target_prot, target_carb, target_fat, target_kcal, expiry_date) VALUES (?, ?, 0, 0, 0, 0, 0, ?)", (nu, np, v_blq))
                    conn.commit(); st.success("Registrado. Espera activación.")
                except: st.error("El usuario ya existe.")
                conn.close()
else:
    # --- APP PRINCIPAL ---
    st.sidebar.title(f"🚀 {'Coach' if st.session_state.admin == 1 else 'Atleta'}")
    st.sidebar.write(f"Usuario: **{st.session_state.user}**")
    
    opciones = ["Mi Diario", "Historial"]
    if st.session_state.admin == 1: 
        opciones = ["Gestión de Clientes", "Maestro de Alimentos", "Mi Diario", "Historial"]
    menu = st.sidebar.radio("Navegación", opciones)

    def mostrar_historial(usuario):
        st.subheader(f"📅 Progreso de {usuario}")
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("SELECT date as Fecha, round(SUM(prot),1) as P, round(SUM(carb),1) as C, round(SUM(fat),1) as G, round(SUM(kcal),0) as Kcal FROM logs WHERE username=? GROUP BY date ORDER BY date DESC", conn, params=(usuario,))
        df_bio = pd.read_sql("SELECT date, weight FROM biometrics WHERE username=? ORDER BY date ASC", conn, params=(usuario,))
        conn.close()
        if not df_bio.empty: st.line_chart(df_bio.set_index('date')['weight'])
        st.dataframe(df, use_container_width=True, hide_index=True)

    if menu == "Gestión de Clientes" and st.session_state.admin == 1:
        st.header("👥 Panel del Coach")
        conn = sqlite3.connect(DB_PATH)
        hoy = get_local_time().strftime('%Y-%m-%d')
        
        # Validación de pendientes
        pend = pd.read_sql("SELECT * FROM logs WHERE status='Pendiente'", conn)
        if not pend.empty:
            st.subheader("🔔 Pendientes")
            for _, r in pend.iterrows():
                with st.expander(f"{r['username']} - {r['food_desc']}"):
                    c1, c2, c3, c4 = st.columns(4)
                    pv = c1.number_input("P/100g", key=f"pv{r['id']}")
                    cv = c2.number_input("C/100g", key=f"cv{r['id']}")
                    gv = c3.number_input("G/100g", key=f"gv{r['id']}")
                    kv = c4.number_input("K/100g", key=f"kv{r['id']}")
                    if st.button("Validar", key=f"v{r['id']}"):
                        try: gms = float(r['food_desc'].split('g')[0])
                        except: gms = 100.0
                        f = gms/100
                        conn.execute("UPDATE logs SET prot=?, carb=?, fat=?, kcal=?, status='Validado' WHERE id=?", (pv*f, cv*f, gv*f, kv*f, r['id']))
                        nom = r['food_desc'].split(' ', 1)[1] if ' ' in r['food_desc'] else r['food_desc']
                        conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (nom, pv, cv, gv, kv, 'General'))
                        conn.commit(); st.rerun()

        # Metas
        st.divider()
        alumns = pd.read_sql("SELECT username FROM users", conn)
        sel = st.selectbox("Seleccionar Alumno", [""] + alumns['username'].tolist())
        if sel:
            m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(sel,)).iloc[0]
            with st.form("f_metas"):
                mp = st.number_input("P Meta", value=float(m['target_prot']))
                mc = st.number_input("C Meta", value=float(m['target_carb']))
                mg = st.number_input("G Meta", value=float(m['target_fat']))
                mk = st.number_input("Kcal Meta", value=float(m['target_kcal']))
                exp = st.text_input("Vencimiento", value=m['expiry_date'])
                if st.form_submit_button("Actualizar Plan"):
                    conn.execute("UPDATE users SET target_prot=?, target_carb=?, target_fat=?, target_kcal=?, expiry_date=? WHERE username=?", (mp, mc, mg, mk, exp, sel))
                    conn.commit(); st.success("Listo"); st.rerun()
        conn.close()

    elif menu == "Mi Diario":
        conn = sqlite3.connect(DB_PATH)
        m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
        hoy = get_local_time().strftime('%Y-%m-%d')
        ayer = (get_local_time() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        st.header(f"📓 Diario - {st.session_state.user}")
        
        if st.button("📋 Copiar de Ayer"):
            ayer_data = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, ayer))
            for _, r in ayer_data.iterrows():
                conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)",
                             (st.session_state.user, hoy, r['food_desc'], r['prot'], r['carb'], r['fat'], r['kcal'], r['status'], r['meal_time']))
            conn.commit(); st.rerun()

        with st.expander("⚖️ Registrar Peso"):
            peso = st.number_input("Peso kg", 40.0, 150.0, 70.0)
            if st.button("Guardar Peso"):
                conn.execute("INSERT OR REPLACE INTO biometrics (username, date, weight, sleep, stress) VALUES (?,?,?,0,0)", (st.session_state.user, hoy, peso))
                conn.commit(); st.success("Peso OK")

        # Dashboard
        cons = pd.read_sql("SELECT SUM(prot) as p, SUM(carb) as c, SUM(fat) as g, SUM(kcal) as k FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy)).fillna(0).iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Proteína", f"{cons['p']:.1f}g", f"/{m['target_prot']}")
        c1.progress(min(cons['p']/m['target_prot'], 1.0) if m['target_prot']>0 else 0.0)
        c2.metric("Carbos", f"{cons['c']:.1f}g", f"/{m['target_carb']}")
        c2.progress(min(cons['c']/m['target_carb'], 1.0) if m['target_carb']>0 else 0.0)
        c3.metric("Grasas", f"{cons['g']:.1f}g", f"/{m['target_fat']}")
        c3.progress(min(cons['g']/m['target_fat'], 1.0) if m['target_fat']>0 else 0.0)
        c4.metric("Kcal", f"{int(cons['k'])}", f"/{int(m['target_kcal'])}")
        c4.progress(min(cons['k']/m['target_kcal'], 1.0) if m['target_kcal']>0 else 0.0)

        # Registro
        for t in ["Desayuno", "Almuerzo", "Cena", "Snacks"]:
            with st.expander(f"➕ {t}"):
                cats = pd.read_sql("SELECT DISTINCT category FROM master_food", conn)['category'].tolist()
                c_sel = st.selectbox("Categoría", ["Todas"] + sorted(cats), key=f"c{t}")
                base_f = pd.read_sql("SELECT * FROM master_food" if c_sel=="Todas" else f"SELECT * FROM master_food WHERE category='{c_sel}'", conn)
                alim = st.selectbox("Alimento", [""] + sorted(base_f['food_name'].tolist()) + ["OTRO"], key=f"a{t}")
                gms = st.number_input("Gramos", 0.0, 1000.0, 100.0, key=f"g{t}")
                if st.button("Añadir", key=f"b{t}"):
                    if alim == "OTRO":
                        ot = st.text_input("¿Qué es?", key=f"ot{t}")
                        conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,0,0,0,0,'Pendiente',?)", (st.session_state.user, hoy, f"{int(gms)}g {ot}", t))
                    else:
                        f_dat = base_f[base_f['food_name']==alim].iloc[0]; fc = gms/100
                        conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)", (st.session_state.user, hoy, f"{int(gms)}g {alim}", f_dat['p100']*fc, f_dat['c100']*fc, f_dat['g100']*fc, f_dat['k100']*fc, 'Validado', t))
                    conn.commit(); st.rerun()

        res = pd.read_sql("SELECT id, meal_time, food_desc, round(kcal,0) as Kcal FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
        st.table(res.drop(columns=['id']))
        if not res.empty:
            b_id = st.selectbox("Borrar ID", res['id'].tolist())
            if st.button("Eliminar"):
                conn.execute("DELETE FROM logs WHERE id=?", (b_id,))
                conn.commit(); st.rerun()
        conn.close()

    elif menu == "Maestro de Alimentos":
        st.header("📂 Maestro de Alimentos")
        conn = sqlite3.connect(DB_PATH)
        t_v, t_i, t_e = st.tabs(["Ver", "Excel", "Nuevo"])
        with t_v:
            st.dataframe(pd.read_sql("SELECT * FROM master_food", conn), use_container_width=True)
        with t_i:
            f = st.file_uploader("Subir Excel", type=["xlsx"])
            if f and st.button("Procesar"):
                df_ex = pd.read_excel(f)
                for _, r in df_ex.iterrows():
                    p, c, g = float(r['proteina']), float(r['carbos']), float(r['grasas'])
                    conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (str(r['nombre']), p, c, g, (p*4+c*4+g*9), str(r['categoria'])))
                conn.commit(); st.success("Importado")
        with t_e:
            with st.form("n_alim"):
                en = st.text_input("Nombre"); ec = st.text_input("Categoría")
                ep = st.number_input("P"); ecb = st.number_input("C"); eg = st.number_input("G")
                if st.form_submit_button("Guardar"):
                    conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (en, ep, ecb, eg, (ep*4+ecb*4+eg*9), ec))
                    conn.commit(); st.rerun()
        conn.close()

    elif menu == "Historial":
        mostrar_historial(st.session_state.user)

    if st.sidebar.button("🚪 Salir"):
        st.query_params.clear()
        st.session_state.user = None; st.session_state.admin = 0; st.rerun()
