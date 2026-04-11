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
# Mantenemos tu lógica de detección de carpetas de descarga
if os.path.exists(os.path.join(os.path.expanduser("~"), "Downloads")):
    BASE_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
else:
    BASE_DIR = os.getcwd()

DB_PATH = os.path.join(BASE_DIR, "unite_nutrition_vFinal.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. Tabla de Usuarios (8 columnas originales)
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, is_admin INTEGER, 
                 target_prot REAL, target_carb REAL, target_fat REAL, target_kcal REAL, expiry_date TEXT)''')
    
    # --- LÓGICA DE MIGRACIÓN PARA USERS ---
    cursor = conn.execute('PRAGMA table_info(users)')
    columnas_actuales = [column[1] for column in cursor.fetchall()]
    columnas_necesarias = [
        ("target_prot", "REAL DEFAULT 0"),
        ("target_carb", "REAL DEFAULT 0"),
        ("target_fat", "REAL DEFAULT 0"),
        ("target_kcal", "REAL DEFAULT 0"),
        ("expiry_date", "TEXT DEFAULT '2099-12-31'")
    ]
    for col_nombre, col_tipo in columnas_necesarias:
        if col_nombre not in columnas_actuales:
            c.execute(f"ALTER TABLE users ADD COLUMN {col_nombre} {col_tipo}")

    # 2. Tabla Maestro de Alimentos
    c.execute('''CREATE TABLE IF NOT EXISTS master_food
                 (food_name TEXT PRIMARY KEY, p100 REAL, c100 REAL, g100 REAL, k100 REAL, category TEXT)''')
    
    # 3. Tabla de Logs (Consumo diario)
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, 
                 food_desc TEXT, prot REAL, carb REAL, fat REAL, kcal REAL, status TEXT, meal_time TEXT)''')
    
    # Migración meal_time
    cursor_logs = conn.execute('PRAGMA table_info(logs)')
    if 'meal_time' not in [col[1] for col in cursor_logs.fetchall()]:
        c.execute("ALTER TABLE logs ADD COLUMN meal_time TEXT DEFAULT 'General'")
        
    # 4. Tabla de Biometría
    c.execute('''CREATE TABLE IF NOT EXISTS biometrics 
                 (username TEXT, date TEXT, weight REAL, sleep INTEGER, stress INTEGER, 
                 PRIMARY KEY (username, date))''')
    
    # 5. Admin por defecto
    c.execute("""INSERT OR IGNORE INTO users 
                 (username, password, is_admin, target_prot, target_carb, target_fat, target_kcal, expiry_date) 
                 VALUES ('erick', 'erickale2005', 1, 0, 0, 0, 0, '2099-12-31')""")
    
    conn.commit()
    conn.close()

init_db()

# --- ESTILOS CSS PERSONALIZADOS (TU CONFIGURACIÓN DE COLORES) ---
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: bold; }
    div[data-testid="metric-container"]:nth-child(1) { color: #FF4B4B; } 
    div[data-testid="metric-container"]:nth-child(2) { color: #4BA3FF; } 
    div[data-testid="metric-container"]:nth-child(3) { color: #FFCA4B; } 
    .stProgress > div > div > div > div { background-color: #00ffcc; }
    </style>
    """, unsafe_allow_html=True)

# --- SISTEMA DE SESIÓN SEGURO ---
if 'user' not in st.session_state:
    st.session_state.user = None
if 'admin' not in st.session_state:
    st.session_state.admin = 0

# Persistencia por URL
if st.session_state.user is None:
    params = st.query_params
    if "user" in params:
        u_url = params["user"]
        conn = sqlite3.connect(DB_PATH)
        res = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(u_url,))
        conn.close()
        if not res.empty:
            st.session_state.user = res.iloc[0]['username']
            st.session_state.admin = res.iloc[0]['is_admin']

# --- PANTALLA DE ACCESO ---
if st.session_state.user is None:
    st.set_page_config(page_title="Unite Nutrition Login", page_icon="🏋️")
    st.title("🏋️ Unite Nutrition - Erick Quiroz")
    tab_login, tab_reg = st.tabs(["🔑 Iniciar Sesión", "📝 Registro de Atleta"])
    
    with tab_login:
        u = st.text_input("Usuario", key="login_u")
        p = st.text_input("Contraseña", type="password", key="login_p")
        if st.button("Entrar"):
            conn = sqlite3.connect(DB_PATH)
            res = pd.read_sql("SELECT * FROM users WHERE username=? AND password=?", conn, params=(u, p))
            conn.close()
            if not res.empty:
                vencimiento = datetime.strptime(res.iloc[0]['expiry_date'], '%Y-%m-%d')
                if get_local_time() <= vencimiento:
                    st.session_state.user = u
                    st.session_state.admin = res.iloc[0]['is_admin']
                    st.query_params["user"] = u
                    st.rerun()
                else:
                    st.error("⚠️ Acceso vencido o pendiente de activación.")
            else:
                st.error("Credenciales incorrectas.")
    
    with tab_reg:
        nu = st.text_input("Nuevo Usuario (Solo letras)", key="reg_u")
        np = st.text_input("Nueva Contraseña", type="password", key="reg_p")
        if st.button("Crear Cuenta"):
            if nu and np and validar_solo_letras(nu):
                conn = sqlite3.connect(DB_PATH)
                venc_bloqueado = (get_local_time() - timedelta(days=1)).strftime('%Y-%m-%d')
                try:
                    conn.execute("INSERT INTO users (username, password, is_admin, target_prot, target_carb, target_fat, target_kcal, expiry_date) VALUES (?, ?, 0, 0, 0, 0, 0, ?)", (nu, np, venc_bloqueado))
                    conn.commit()
                    st.success("✅ ¡Registro exitoso! Avisa al Coach Erick.")
                except: st.error("El usuario ya existe.")
                conn.close()

# --- APLICACIÓN PRINCIPAL ---
else:
    st.sidebar.title(f"🚀 {'Coach' if st.session_state.admin == 1 else 'Atleta'}")
    st.sidebar.write(f"Usuario: **{st.session_state.user}**")
    
    if st.sidebar.button("🔄 Actualizar Datos"):
        st.rerun()

    opciones = ["Mi Diario", "Historial"]
    if st.session_state.admin == 1: 
        opciones = ["Gestión de Clientes", "Maestro de Alimentos", "Mi Diario", "Historial"]
    menu = st.sidebar.radio("Navegación", opciones)

    def mostrar_historial(usuario):
        st.subheader(f"📅 Historial de Progreso: {usuario}")
        conn = sqlite3.connect(DB_PATH)
        dias_es = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
        
        query = "SELECT date as Fecha, round(SUM(prot),1) as P_Total, round(SUM(carb),1) as C_Total, round(SUM(fat),1) as G_Total, round(SUM(kcal),0) as Kcal_Total FROM logs WHERE username=? GROUP BY date ORDER BY date DESC LIMIT 14"
        df = pd.read_sql(query, conn, params=(usuario,))
        df_bio = pd.read_sql("SELECT date as Fecha, weight as Peso FROM biometrics WHERE username=? ORDER BY date ASC", conn, params=(usuario,))
        conn.close()

        if not df_bio.empty:
            st.write("📈 **Evolución del Peso (kg)**")
            df_chart = df_bio.copy()
            df_chart['Fecha'] = pd.to_datetime(df_chart['Fecha']).dt.strftime('%d/%m')
            st.line_chart(df_chart.set_index('Fecha')['Peso'])

        if not df.empty:
            df['Fecha'] = pd.to_datetime(df['Fecha'])
            if not df_bio.empty:
                df_bio['Fecha'] = pd.to_datetime(df_bio['Fecha'])
                df = pd.merge(df, df_bio, on="Fecha", how="left")
            df.insert(0, "Día", df['Fecha'].dt.day_name().map(dias_es))
            df['Fecha'] = df['Fecha'].dt.strftime('%d/%m')
            st.write("📋 **Registros Diarios**")
            st.dataframe(df, use_container_width=True, hide_index=True)

    # --- SECCIÓN: GESTIÓN DE CLIENTES (ADMIN) ---
    if st.session_state.admin == 1 and menu == "Gestión de Clientes":
        st.header("👥 Control de Alumnos")
        conn = sqlite3.connect(DB_PATH)
        hoy = get_local_time().strftime('%Y-%m-%d')
        
        # Alertas de cumplimiento
        alumnos_check = pd.read_sql("SELECT username FROM users WHERE is_admin=0", conn)['username'].tolist()
        for alum in alumnos_check:
            reg_hoy = pd.read_sql("SELECT count(*) as total FROM logs WHERE username=? AND date=?", conn, params=(alum, hoy)).iloc[0]['total']
            if reg_hoy == 0 and get_local_time().hour >= 16:
                 st.markdown(f'<div style="color: #ff4b4b; padding: 10px; border: 1px solid #ff4b4b; border-radius: 5px;">⚠️ {alum} no ha registrado nada hoy.</div>', unsafe_allow_html=True)
        
        st.divider()
        # Clasificación de pendientes
        pendientes = pd.read_sql("SELECT * FROM logs WHERE status='Pendiente'", conn)
        if not pendientes.empty:
            st.subheader("🔔 Alimentos Pendientes por Validar")
            cats_existentes = pd.read_sql("SELECT DISTINCT category FROM master_food", conn)['category'].tolist()
            for _, r in pendientes.iterrows():
                with st.expander(f"🔴 {r['username']} - {r['food_desc']}"):
                    c1, c2, c3, c4 = st.columns(4)
                    p_v = c1.number_input("Prot (100g)", 0.0, key=f"p_v_{r['id']}")
                    c_v = c2.number_input("Carb (100g)", 0.0, key=f"c_v_{r['id']}")
                    g_v = c3.number_input("Fat (100g)", 0.0, key=f"g_v_{r['id']}")
                    k_v = c4.number_input("Kcal (100g)", 0.0, key=f"k_v_{r['id']}")
                    cat_sel = st.selectbox("Categoría:", [""] + sorted([c for c in cats_existentes if c]) + ["➕ Nueva"], key=f"cat_{r['id']}")
                    if st.button("✅ Validar y Guardar", key=f"btn_v_{r['id']}"):
                        try: gramos = float(r['food_desc'].split('g')[0])
                        except: gramos = 100.0
                        factor = gramos / 100
                        conn.execute("UPDATE logs SET prot=?, carb=?, fat=?, kcal=?, status='Validado' WHERE id=?", (p_v*factor, c_v*factor, g_v*factor, k_v*factor, r['id']))
                        nombre_limpio = r['food_desc'].split(' ', 1)[1] if ' ' in r['food_desc'] else r['food_desc']
                        conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (nombre_limpio.strip(), p_v, c_v, g_v, k_v, cat_sel))
                        conn.commit(); st.rerun()

        st.divider()
        # Gestión Individual (Pestañas completas)
        usuarios_all = pd.read_sql("SELECT username FROM users", conn)
        sel_atleta = st.selectbox("Selecciona un usuario:", [""] + usuarios_all['username'].tolist())
        if sel_atleta:
            m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(sel_atleta,)).iloc[0]
            t_hoy, t_hist, t_cfg = st.tabs(["📊 Hoy", "📅 Historial", "⚙️ Metas y Plan"])
            with t_hoy:
                detalles = pd.read_sql("SELECT food_desc, round(prot,1) as P, round(carb,1) as C, round(fat,1) as G, round(kcal,0) as Kcal FROM logs WHERE username=? AND date=?", conn, params=(sel_atleta, hoy))
                if not detalles.empty:
                    st.table(detalles)
                    cons_tot = detalles.sum(numeric_only=True)
                    st.write(f"**Total consumido:** P: {cons_tot['P']} | C: {cons_tot['C']} | G: {cons_tot['G']} | Kcal: {cons_tot['Kcal']}")
            with t_hist: mostrar_historial(sel_atleta)
            with t_cfg:
                st.subheader(f"Plan de {sel_atleta}")
                p_meta = st.number_input("P Meta", value=float(m['target_prot']))
                c_meta = st.number_input("C Meta", value=float(m['target_carb']))
                g_meta = st.number_input("G Meta", value=float(m['target_fat']))
                k_meta = st.number_input("Kcal Meta", value=float(m['target_kcal']))
                venc = st.text_input("Vencimiento (YYYY-MM-DD)", value=m['expiry_date'])
                if st.button("💾 Actualizar Todo"):
                    conn.execute("UPDATE users SET target_prot=?, target_carb=?, target_fat=?, target_kcal=?, expiry_date=? WHERE username=?", (p_meta, c_meta, g_meta, k_meta, venc, sel_atleta))
                    conn.commit(); st.success("Datos guardados."); st.rerun()
        conn.close()

    # --- SECCIÓN: MI DIARIO ---
    elif menu == "Mi Diario":
        conn = sqlite3.connect(DB_PATH)
        m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
        hoy = get_local_time().strftime('%Y-%m-%d')
        ayer = (get_local_time() - timedelta(days=1)).strftime('%Y-%m-%d')

        st.header(f"📓 Diario: {st.session_state.user}")
        
        col_acc1, col_acc2 = st.columns(2)
        if col_acc1.button("📋 Copiar ayer"):
            logs_ayer = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, ayer))
            check_hoy = pd.read_sql("SELECT count(*) as tot FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy)).iloc[0]['tot']
            if check_hoy == 0 and not logs_ayer.empty:
                for _, la in logs_ayer.iterrows():
                    conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)",
                                 (st.session_state.user, hoy, la['food_desc'], la['prot'], la['carb'], la['fat'], la['kcal'], la['status'], la['meal_time']))
                conn.commit(); st.rerun()
            else: st.warning("Ya hay registros hoy o no hay nada ayer.")

        with st.expander("🧪 Registrar Biometría"):
            p_w = st.number_input("Peso Actual (kg)", 30.0, 200.0, 75.0)
            if st.button("💾 Guardar"):
                conn.execute("INSERT OR REPLACE INTO biometrics (username, date, weight, sleep, stress) VALUES (?,?,?,0,0)", (st.session_state.user, hoy, p_w))
                conn.commit(); st.success("Peso guardado.")

        st.divider()
        # Dash de Macros con Barras
        cons = pd.read_sql("SELECT SUM(prot) as p, SUM(carb) as c, SUM(fat) as g, SUM(kcal) as k FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy)).fillna(0).iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Proteína", f"{cons['p']:.1f}g", f"/{m['target_prot']}g")
        c1.progress(min(cons['p'] / m['target_prot'], 1.0) if m['target_prot'] > 0 else 0.0)
        c2.metric("Carbos", f"{cons['c']:.1f}g", f"/{m['target_carb']}g")
        c2.progress(min(cons['c'] / m['target_carb'], 1.0) if m['target_carb'] > 0 else 0.0)
        c3.metric("Grasas", f"{cons['g']:.1f}g", f"/{m['target_fat']}g")
        c3.progress(min(cons['g'] / m['target_fat'], 1.0) if m['target_fat'] > 0 else 0.0)
        c4.metric("Kcal", f"{int(cons['k'])}", f"/{int(m['target_kcal'])}")
        c4.progress(min(cons['k'] / m['target_kcal'], 1.0) if m['target_kcal'] > 0 else 0.0)

        st.divider()
        # Tiempos de Comida con Lógica de Maestro
        tiempos = ["Desayuno", "Almuerzo", "Cena", "Snacks"]
        for t in tiempos:
            with st.container():
                st.subheader(t)
                logs_t = pd.read_sql("SELECT id, food_desc, round(kcal,0) as Kcal FROM logs WHERE username=? AND date=? AND meal_time=?", conn, params=(st.session_state.user, hoy, t))
                for _, row in logs_t.iterrows():
                    st.write(f"🍴 {row['food_desc']} - **{row['Kcal']} kcal**")
                
                with st.expander(f"➕ Agregar a {t}"):
                    cats = pd.read_sql("SELECT DISTINCT category FROM master_food", conn)['category'].tolist()
                    c_sel = st.selectbox("Categoría:", ["Todas"] + sorted([c for c in cats if c]), key=f"cat_{t}")
                    df_alims = pd.read_sql("SELECT * FROM master_food" if c_sel == "Todas" else f"SELECT * FROM master_food WHERE category='{c_sel}'", conn)
                    a_sel = st.selectbox("Alimento:", [""] + sorted(df_alims['food_name'].tolist()) + ["➕ OTRO"], key=f"alim_{t}")
                    gr = st.number_input("Gramos:", 0.0, 2000.0, 100.0, key=f"gr_{t}")
                    
                    if st.button("Añadir Registro", key=f"btn_{t}"):
                        if a_sel == "➕ OTRO":
                            nombre_o = st.text_input("¿Qué es?", key=f"txt_{t}")
                            conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,0,0,0,0,'Pendiente',?)", (st.session_state.user, hoy, f"{int(gr)}g {nombre_o}", t))
                        else:
                            f = df_alims[df_alims['food_name']==a_sel].iloc[0]; fac = gr/100
                            conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)", (st.session_state.user, hoy, f"{int(gr)}g {a_sel}", f['p100']*fac, f['c100']*fac, f['g100']*fac, f['k100']*fac, 'Validado', t))
                        conn.commit(); st.rerun()
        
        st.divider()
        st.subheader("🗑️ Eliminar Registros de Hoy")
        tabla_resumen = pd.read_sql("SELECT id, meal_time, food_desc FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
        if not tabla_resumen.empty:
            borrar_id = st.selectbox("Selecciona para borrar:", tabla_resumen['id'].tolist(), format_func=lambda x: f"{tabla_resumen[tabla_resumen['id']==x]['food_desc'].values[0]}")
            if st.button("❌ Eliminar Alimento"):
                conn.execute("DELETE FROM logs WHERE id=?", (borrar_id,))
                conn.commit(); st.rerun()
        conn.close()

    # --- SECCIÓN: MAESTRO DE ALIMENTOS (TU LÓGICA DE IMPORTACIÓN) ---
    elif menu == "Maestro de Alimentos":
        st.header("📂 Gestión de la Base de Datos")
        conn = sqlite3.connect(DB_PATH)
        
        t_ver, t_imp, t_edit = st.tabs(["🔍 Ver Alimentos", "📥 Importar Excel", "✏️ Editar/Nuevo"])
        
        with t_ver:
            busq = st.text_input("Buscar alimento:")
            base = pd.read_sql("SELECT food_name as Alimento, category as Categoría, p100, c100, g100, k100 FROM master_food", conn)
            if busq: base = base[base['Alimento'].str.contains(busq, case=False)]
            st.dataframe(base, use_container_width=True, hide_index=True)
            
        with t_imp:
            st.info("El Excel debe tener columnas: nombre, proteina, carbos, grasas, categoria")
            file = st.file_uploader("Sube el archivo .xlsx", type=["xlsx"])
            if file and st.button("🚀 Iniciar Importación"):
                try:
                    df_ex = pd.read_excel(file)
                    df_ex.columns = [c.lower().strip() for c in df_ex.columns]
                    for _, r in df_ex.iterrows():
                        p, c, g = float(r['proteina']), float(r['carbos']), float(r['grasas'])
                        conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (str(r['nombre']).strip(), p, c, g, (p*4+c*4+g*9), str(r['categoria']).capitalize()))
                    conn.commit(); st.success("Base de datos actualizada con éxito.")
                except Exception as e: st.error(f"Error: {e}")
                
        with t_edit:
            st.subheader("Añadir o Editar Manualmente")
            with st.form("manual_alim"):
                en = st.text_input("Nombre del Alimento")
                ec = st.text_input("Categoría")
                col1, col2, col3 = st.columns(3)
                ep = col1.number_input("Prot / 100g")
                ecb = col2.number_input("Carb / 100g")
                eg = col3.number_input("Fat / 100g")
                if st.form_submit_button("⭐ Guardar Alimento"):
                    if en and validar_solo_letras(en):
                        conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (en.strip(), ep, ecb, eg, (ep*4+ecb*4+eg*9), ec.strip().capitalize()))
                        conn.commit(); st.success("Guardado."); st.rerun()
        conn.close()

    elif menu == "Historial":
        mostrar_historial(st.session_state.user)

    # --- BOTÓN DE SALIDA ---
    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.query_params.clear()
        st.session_state.user = None
        st.session_state.admin = 0
        st.rerun()
