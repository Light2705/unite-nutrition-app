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
    
    # 1. Crear tabla de Usuarios con la estructura completa
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, 
                  password TEXT, 
                  is_admin INTEGER, 
                  target_prot REAL, 
                  target_carb REAL, 
                  target_fat REAL, 
                  target_kcal REAL, 
                  expiry_date TEXT)''')
    
    # --- LÓGICA DE MIGRACIÓN PARA TABLA USERS ---
    # Esto evita el OperationalError si la tabla ya existe con menos columnas
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
    
    # Migración de meal_time para logs antiguos
    cursor_logs = conn.execute('PRAGMA table_info(logs)')
    if 'meal_time' not in [col[1] for col in cursor_logs.fetchall()]:
        c.execute("ALTER TABLE logs ADD COLUMN meal_time TEXT DEFAULT 'General'")
        
    # 4. Tabla de Biometría
    c.execute('''CREATE TABLE IF NOT EXISTS biometrics 
                 (username TEXT, date TEXT, weight REAL, sleep INTEGER, stress INTEGER, 
                 PRIMARY KEY (username, date))''')
    
    # 5. Insertar Admin con nombres de columnas explícitos para mayor seguridad
    c.execute("""INSERT OR IGNORE INTO users 
                 (username, password, is_admin, target_prot, target_carb, target_fat, target_kcal, expiry_date) 
                 VALUES ('erick', 'erickale2005', 1, 0, 0, 0, 0, '2099-12-31')""")
    
    conn.commit()
    conn.close()

# Ejecutar inicialización
init_db()

# --- ESTILOS CSS PERSONALIZADOS ---
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: bold; }
    div[data-testid="metric-container"]:nth-child(1) { color: #FF4B4B; } 
    div[data-testid="metric-container"]:nth-child(2) { color: #4BA3FF; } 
    div[data-testid="metric-container"]:nth-child(3) { color: #FFCA4B; } 
    </style>
    """, unsafe_allow_html=True)

# --- LÓGICA DE PERSISTENCIA ---
if 'user' not in st.session_state:
    params = st.query_params
    if "user" in params:
        u_url = params["user"]
        conn = sqlite3.connect(DB_PATH)
        res = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(u_url,))
        conn.close()
        if not res.empty:
            vencimiento = datetime.strptime(res.iloc[0]['expiry_date'], '%Y-%m-%d')
            if get_local_time() <= vencimiento:
                st.session_state.user = res.iloc[0]['username']
                st.session_state.admin = res.iloc[0]['is_admin']

# --- PANTALLA DE ACCESO ---
if 'user' not in st.session_state:
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
        nu = st.text_input("Nuevo Usuario (Sin números)", key="reg_u")
        np = st.text_input("Nueva Contraseña", type="password", key="reg_p")
        if st.button("Crear Cuenta"):
            if nu.strip() == "" or np.strip() == "":
                st.error("❌ El usuario y la contraseña no pueden estar vacíos.")
            elif validar_solo_letras(nu):
                conn = sqlite3.connect(DB_PATH)
                venc_bloqueado = (get_local_time() - timedelta(days=1)).strftime('%Y-%m-%d')
                try:
                    conn.execute("INSERT INTO users (username, password, is_admin, target_prot, target_carb, target_fat, target_kcal, expiry_date) VALUES (?, ?, 0, 0, 0, 0, 0, ?)", (nu, np, venc_bloqueado))
                    conn.commit()
                    st.success("✅ ¡Registro exitoso! Avisa al Coach Erick.")
                except: st.error("El usuario ya existe.")
                conn.close()

else:
    # --- APLICACIÓN PRINCIPAL ---
    st.sidebar.title(f"🚀 {'Coach' if st.session_state.admin else 'Atleta'}")
    st.sidebar.write(f"Usuario: **{st.session_state.user}**")
    
    if st.sidebar.button("🔄 Actualizar Datos"):
        st.rerun()

    opciones = ["Mi Diario", "Historial"]
    if st.session_state.admin: 
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

    if st.session_state.admin and menu == "Gestión de Clientes":
        st.header("👥 Control de Alumnos")
        conn = sqlite3.connect(DB_PATH)
        hoy = get_local_time().strftime('%Y-%m-%d')
        
        # Alertas de cumplimiento
        alumnos_check = pd.read_sql("SELECT username FROM users WHERE is_admin=0", conn)['username'].tolist()
        for alum in alumnos_check:
            reg_hoy = pd.read_sql("SELECT count(*) as total FROM logs WHERE username=? AND date=?", conn, params=(alum, hoy)).iloc[0]['total']
            if reg_hoy == 0 and get_local_time().hour >= 16:
                 st.warning(f"⚠️ {alum} no ha registrado nada aún.")
        
        st.divider()
        # Clasificación de alimentos pendientes
        pendientes = pd.read_sql("SELECT * FROM logs WHERE status='Pendiente'", conn)
        if not pendientes.empty:
            st.subheader("🔔 Alimentos Pendientes")
            cats_existentes = pd.read_sql("SELECT DISTINCT category FROM master_food", conn)['category'].tolist()
            for _, r in pendientes.iterrows():
                with st.expander(f"🔴 {r['username']} - {r['food_desc']}"):
                    c1, c2, c3, c4 = st.columns(4)
                    p_val = c1.number_input("Prot", 0.0, key=f"p_val_{r['id']}")
                    c_val = c2.number_input("Carb", 0.0, key=f"c_val_{r['id']}")
                    g_val = c3.number_input("Fat", 0.0, key=f"g_val_{r['id']}")
                    k_val = c4.number_input("Kcal", 0.0, key=f"k_val_{r['id']}")
                    cat_sel = st.selectbox("Categoría:", [""] + sorted([c for c in cats_existentes if c]) + ["➕ Nueva"], key=f"cat_sel_{r['id']}")
                    if st.button("✅ Validar", key=f"v_btn_{r['id']}"):
                        try: gramos = float(r['food_desc'].split('g')[0])
                        except: gramos = 100.0
                        factor = gramos / 100
                        conn.execute("UPDATE logs SET prot=?, carb=?, fat=?, kcal=?, status='Validado' WHERE id=?", (p_val*factor, c_val*factor, g_val*factor, k_val*factor, r['id']))
                        nombre_limpio = r['food_desc'].split(' ', 1)[1] if ' ' in r['food_desc'] else r['food_desc']
                        conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (nombre_limpio.strip(), p_val, c_val, g_val, k_val, cat_sel))
                        conn.commit(); st.rerun()

        st.divider()
        # Edición de metas
        usuarios_all = pd.read_sql("SELECT username FROM users", conn)
        sel_atleta = st.selectbox("Selecciona un usuario:", [""] + usuarios_all['username'].tolist())
        if sel_atleta:
            m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(sel_atleta,)).iloc[0]
            t_hoy, t_hist, t_cfg = st.tabs(["📊 Hoy", "📅 Historial", "⚙️ Metas"])
            with t_hoy:
                detalles = pd.read_sql("SELECT food_desc, round(prot,1) as P, round(carb,1) as C, round(fat,1) as G, round(kcal,0) as Kcal FROM logs WHERE username=? AND date=?", conn, params=(sel_atleta, hoy))
                st.table(detalles)
            with t_hist: mostrar_historial(sel_atleta)
            with t_cfg:
                p_o = st.number_input("P Meta", value=float(m['target_prot']))
                c_o = st.number_input("C Meta", value=float(m['target_carb']))
                g_o = st.number_input("G Meta", value=float(m['target_fat']))
                k_o = st.number_input("Kcal Meta", value=float(m['target_kcal']))
                if st.button("💾 Guardar Plan"):
                    conn.execute("UPDATE users SET target_prot=?, target_carb=?, target_fat=?, target_kcal=? WHERE username=?", (p_o, c_o, g_o, k_o, sel_atleta))
                    conn.commit(); st.success("Actualizado."); st.rerun()
        conn.close()

    elif menu == "Mi Diario":
        conn = sqlite3.connect(DB_PATH)
        m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
        hoy = get_local_time().strftime('%Y-%m-%d')
        ayer = (get_local_time() - timedelta(days=1)).strftime('%Y-%m-%d')

        st.header(f"📓 Diario: {st.session_state.user}")
        
        if st.button("📋 Copiar ayer"):
            logs_ayer = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, ayer))
            if not logs_ayer.empty:
                for _, la in logs_ayer.iterrows():
                    conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)",
                                 (st.session_state.user, hoy, la['food_desc'], la['prot'], la['carb'], la['fat'], la['kcal'], la['status'], la['meal_time']))
                conn.commit(); st.rerun()

        # Registro de biometría
        with st.expander("🧪 Registrar Peso"):
            p_w = st.number_input("Peso Actual (kg)", 30.0, 200.0, 75.0)
            if st.button("💾 Guardar Peso"):
                conn.execute("INSERT OR REPLACE INTO biometrics (username, date, weight, sleep, stress) VALUES (?,?,?,0,0)", (st.session_state.user, hoy, p_w))
                conn.commit(); st.success("Peso guardado.")

        # Dashboard de Macros
        cons = pd.read_sql("SELECT SUM(prot) as p, SUM(carb) as c, SUM(fat) as g, SUM(kcal) as k FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy)).fillna(0).iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Proteína", f"{cons['p']:.1f}g", f"Meta: {m['target_prot']}")
            st.progress(min(cons['p'] / m['target_prot'], 1.0) if m['target_prot'] > 0 else 0.0)
        with c2:
            st.metric("Carbos", f"{cons['c']:.1f}g", f"Meta: {m['target_carb']}")
            st.progress(min(cons['c'] / m['target_carb'], 1.0) if m['target_carb'] > 0 else 0.0)
        with c3:
            st.metric("Grasas", f"{cons['g']:.1f}g", f"Meta: {m['target_fat']}")
            st.progress(min(cons['g'] / m['target_fat'], 1.0) if m['target_fat'] > 0 else 0.0)
        with c4:
            st.metric("Kcal", f"{int(cons['k'])}", f"Meta: {int(m['target_kcal'])}")
            st.progress(min(cons['k'] / m['target_kcal'], 1.0) if m['target_kcal'] > 0 else 0.0)

        # Secciones de comidas
        tiempos = ["Desayuno", "Almuerzo", "Cena", "Snacks"]
        for t in tiempos:
            with st.expander(f"➕ Agregar a {t}"):
                cats = pd.read_sql("SELECT DISTINCT category FROM master_food", conn)['category'].tolist()
                c_sel = st.selectbox("Categoría:", ["Todas"] + sorted([c for c in cats if c]), key=f"cat_{t}")
                df_alims = pd.read_sql("SELECT * FROM master_food" if c_sel == "Todas" else f"SELECT * FROM master_food WHERE category='{c_sel}'", conn)
                a_sel = st.selectbox("Alimento:", [""] + sorted(df_alims['food_name'].tolist()) + ["➕ OTRO"], key=f"alim_{t}")
                gramos = st.number_input("Gramos:", 0.0, 2000.0, 100.0, key=f"gr_{t}")
                if st.button("Registrar", key=f"btn_{t}"):
                    if a_sel == "➕ OTRO":
                        nombre_otro = st.text_input("Nombre:", key=f"txt_{t}")
                        conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,0,0,0,0,'Pendiente',?)", (st.session_state.user, hoy, f"{int(gramos)}g {nombre_otro}", t))
                    else:
                        f = df_alims[df_alims['food_name']==a_sel].iloc[0]; fac = gramos/100
                        conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)", (st.session_state.user, hoy, f"{int(gramos)}g {a_sel}", f['p100']*fac, f['c100']*fac, f['g100']*fac, f['k100']*fac, 'Validado', t))
                    conn.commit(); st.rerun()

        # Resumen del día
        tabla_resumen = pd.read_sql("SELECT id, meal_time, food_desc, round(kcal,0) as Kcal FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
        st.table(tabla_resumen.drop(columns=['id']))
        if not tabla_resumen.empty:
            borrar_id = st.selectbox("ID para borrar:", tabla_resumen['id'].tolist())
            if st.button("🗑️ Eliminar"):
                conn.execute("DELETE FROM logs WHERE id=?", (borrar_id,))
                conn.commit(); st.rerun()
        conn.close()

    elif menu == "Maestro de Alimentos":
        st.header("📂 Base de Alimentos")
        conn = sqlite3.connect(DB_PATH)
        with st.form("nuevo_alimento"):
            n = st.text_input("Nombre")
            c = st.text_input("Categoría")
            c1, c2, c3 = st.columns(3)
            p = c1.number_input("P/100g")
            cb = c2.number_input("C/100g")
            g = c3.number_input("G/100g")
            if st.form_submit_button("Añadir"):
                if validar_solo_letras(n):
                    conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (n, p, cb, g, (p*4+cb*4+g*9), c))
                    conn.commit(); st.success("Añadido.")
        base = pd.read_sql("SELECT * FROM master_food", conn)
        st.dataframe(base, use_container_width=True)
        conn.close()

    elif menu == "Historial":
        mostrar_historial(st.session_state.user)

    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.query_params.clear()
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
