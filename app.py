import streamlit as st
import pandas as pd
import sqlite3
import os
import re
from datetime import datetime, timedelta
import google.generativeai as genai

# --- CONFIGURACIÓN DE IA (GEMINI) ---
API_KEY = "AIzaSyC1FBPL-7rf7DskWE1tOWIyne7aoNoKxwE"
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

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
    # Tabla de Usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, is_admin INTEGER, 
                 target_prot REAL, target_carb REAL, target_fat REAL, target_kcal REAL, expiry_date TEXT)''')
    
    # Tabla Maestro de Alimentos
    c.execute('''CREATE TABLE IF NOT EXISTS master_food
                 (food_name TEXT PRIMARY KEY, p100 REAL, c100 REAL, g100 REAL, k100 REAL, category TEXT)''')
    
    # Tabla de Logs (Consumo diario)
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, 
                 food_desc TEXT, prot REAL, carb REAL, fat REAL, kcal REAL, status TEXT, meal_time TEXT)''')
    
    try:
        c.execute("ALTER TABLE logs ADD COLUMN meal_time TEXT DEFAULT 'General'")
    except:
        pass
        
    # Tabla de Biometría
    c.execute('''CREATE TABLE IF NOT EXISTS biometrics 
                 (username TEXT, date TEXT, weight REAL, sleep INTEGER, stress INTEGER, 
                 PRIMARY KEY (username, date))''')
    
    # Usuario Administrador por defecto
    c.execute("INSERT OR IGNORE INTO users VALUES ('erick', 'erickale2005', 1, 0, 0, 0, 0, '2099-12-31')")
    conn.commit()
    conn.close()

init_db()

# --- LÓGICA DE PERSISTENCIA (URL) ---
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
                    conn.execute("INSERT INTO users VALUES (?, ?, 0, 0, 0, 0, 0, ?)", (nu, np, venc_bloqueado))
                    conn.commit()
                    st.success("✅ ¡Registro exitoso! Avisa al Coach Erick.")
                except: st.error("El usuario ya existe.")
                conn.close()

else:
    # --- APP PRINCIPAL ---
    st.sidebar.title(f"🚀 {'Coach' if st.session_state.admin else 'Atleta'}")
    st.sidebar.write(f"Usuario: **{st.session_state.user}**")
    
    # --- SECCIÓN DE IA EN SIDEBAR ---
    with st.sidebar.expander("🤖 Coach IA - Consultas"):
        user_query = st.text_area("¿Tienes alguna duda sobre tu dieta o entreno?", height=100)
        if st.button("Consultar a la IA"):
            if user_query:
                with st.spinner("Pensando..."):
                    role = "Coach de Powerlifting" if st.session_state.admin else "Atleta de alto rendimiento"
                    prompt = f"Actúa como un experto en nutrición deportiva y Powerlifting en Perú. El usuario es un {role}. Pregunta: {user_query}. Responde de forma técnica pero motivadora y breve."
                    try:
                        response = model.generate_content(prompt)
                        st.info(response.text)
                    except Exception as e:
                        st.error("Error al conectar con la IA.")
            else:
                st.warning("Escribe algo primero.")

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
        else: 
            st.info("No hay registros de alimentación.")

    # --- GESTIÓN DE CLIENTES ---
    if st.session_state.admin and menu == "Gestión de Clientes":
        st.header("👥 Control de Alumnos y Mis Macros")
        conn = sqlite3.connect(DB_PATH)
        hoy_dt = get_local_time()
        hoy = hoy_dt.strftime('%Y-%m-%d')
        hora_actual = hoy_dt.hour
        
        alumnos_check = pd.read_sql("SELECT username FROM users WHERE is_admin=0", conn)['username'].tolist()
        for alum in alumnos_check:
            reg_hoy = pd.read_sql("SELECT count(*) as total FROM logs WHERE username=? AND date=?", conn, params=(alum, hoy)).iloc[0]['total']
            if reg_hoy == 0 and hora_actual >= 16:
                 st.markdown(f'<div style="color: #ff4b4b; border: 1px solid #ff4b4b; padding: 10px; border-radius: 5px; margin-bottom:10px;">⚠️ <b>{alum}</b> no ha registrado comidas hoy.</div>', unsafe_allow_html=True)
        
        st.divider()
        pendientes = pd.read_sql("SELECT * FROM logs WHERE status='Pendiente'", conn)
        if not pendientes.empty:
            st.subheader("🔔 Alimentos Pendientes")
            cats_existentes = pd.read_sql("SELECT DISTINCT category FROM master_food", conn)['category'].tolist()
            for _, r in pendientes.iterrows():
                with st.expander(f"🔴 {r['username']} - {r['food_desc']}"):
                    c1, c2, c3, c4 = st.columns(4)
                    p_val = c1.number_input("Prot (100g)", 0.0, key=f"p_val_{r['id']}")
                    c_val = c2.number_input("Carb (100g)", 0.0, key=f"c_val_{r['id']}")
                    g_val = c3.number_input("Fat (100g)", 0.0, key=f"g_val_{r['id']}")
                    k_val = c4.number_input("Kcal (100g)", 0.0, key=f"k_val_{r['id']}")
                    col_cat, col_new = st.columns(2)
                    cat_sel = col_cat.selectbox("Clasificar en:", [""] + sorted([c for c in cats_existentes if c]) + ["➕ Nueva Categoría"], key=f"cat_sel_{r['id']}")
                    categoria_final = col_new.text_input("Nueva Categoría:", key=f"new_cat_{r['id']}").strip().capitalize() if cat_sel == "➕ Nueva Categoría" else cat_sel
                    
                    col_v, col_r = st.columns(2)
                    if col_v.button("✅ Validar", key=f"v_btn_{r['id']}"):
                        if categoria_final == "": st.error("Selecciona categoría.")
                        else:
                            gramos_atleta = float(r['food_desc'].split('g')[0]) if 'g' in r['food_desc'] else 100.0
                            factor = gramos_atleta / 100
                            conn.execute("UPDATE logs SET prot=?, carb=?, fat=?, kcal=?, status='Validado' WHERE id=?", (p_val*factor, c_val*factor, g_val*factor, k_val*factor, r['id']))
                            nombre_limpio = r['food_desc'].split(' ', 1)[1] if ' ' in r['food_desc'] else r['food_desc']
                            conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (nombre_limpio.strip(), p_val, c_val, g_val, k_val, categoria_final))
                            conn.commit(); st.rerun()
                    if col_r.button("🗑️ Borrar", key=f"del_log_{r['id']}"):
                        conn.execute("DELETE FROM logs WHERE id=?", (r['id'],))
                        conn.commit(); st.rerun()

        st.divider()
        usuarios_all = pd.read_sql("SELECT username as Alumno, expiry_date as Acceso_Hasta, is_admin FROM users", conn)
        sel_atleta = st.selectbox("Selecciona un usuario:", [""] + usuarios_all['Alumno'].tolist())
        
        if sel_atleta:
            m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(sel_atleta,)).iloc[0]
            last_bio = pd.read_sql("SELECT * FROM biometrics WHERE username=? ORDER BY date DESC LIMIT 1", conn, params=(sel_atleta,))
            t_hoy, t_hist, t_cfg = st.tabs(["📊 Hoy", "📅 Historial", "⚙️ Configuración"])
            with t_hoy:
                if not last_bio.empty:
                    st.info(f"🧬 Peso: {last_bio.iloc[0]['weight']}kg | Sueño: {last_bio.iloc[0]['sleep']} | Estrés: {last_bio.iloc[0]['stress']}")
                detalles_hoy = pd.read_sql("SELECT food_desc as Plato, round(prot,1) as P, round(carb,1) as C, round(fat,1) as G, round(kcal,0) as Kcal FROM logs WHERE username=? AND date=?", conn, params=(sel_atleta, hoy))
                if not detalles_hoy.empty:
                    st.table(detalles_hoy)
                    cons_tot = detalles_hoy.sum(numeric_only=True)
                    st.write(f"**Total Hoy:** P:{cons_tot['P']} | C:{cons_tot['C']} | G:{cons_tot['G']} | Kcal:{cons_tot['Kcal']}")
            with t_hist: mostrar_historial(sel_atleta)
            with t_cfg:
                dias = st.number_input("Añadir días de acceso:", 0, 30)
                nueva_f = (datetime.strptime(m['expiry_date'], '%Y-%m-%d') + timedelta(days=dias)).strftime('%Y-%m-%d') if m['is_admin'] == 0 else m['expiry_date']
                p_o = st.number_input("P Meta", value=float(m['target_prot']))
                c_o = st.number_input("C Meta", value=float(m['target_carb']))
                g_o = st.number_input("G Meta", value=float(m['target_fat']))
                k_o = st.number_input("Kcal Meta", value=float(m['target_kcal']))
                if st.button("💾 Guardar Plan"):
                    conn.execute("UPDATE users SET expiry_date=?, target_prot=?, target_carb=?, target_fat=?, target_kcal=? WHERE username=?", (nueva_f, p_o, c_o, g_o, k_o, sel_atleta))
                    conn.commit(); st.success("Actualizado!"); st.rerun()
        conn.close()

    # --- MI DIARIO ---
    elif menu == "Mi Diario":
        conn = sqlite3.connect(DB_PATH)
        m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
        hoy_dt = get_local_time()
        hoy = hoy_dt.strftime('%Y-%m-%d')
        ayer = (hoy_dt - timedelta(days=1)).strftime('%Y-%m-%d')
        st.header(f"📓 Diario: {st.session_state.user}")
        
        if st.button("📋 Copiar comidas de ayer"):
            logs_ayer = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, ayer))
            for _, la in logs_ayer.iterrows():
                conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)",
                             (st.session_state.user, hoy, la['food_desc'], la['prot'], la['carb'], la['fat'], la['kcal'], la['status'], la['meal_time']))
            conn.commit(); st.rerun()
        
        with st.expander("🧪 Registrar Biometría"):
            p_w = st.number_input("Peso (kg)", 30.0, 200.0, 75.0)
            p_s = st.slider("Sueño", 1, 10, 7)
            p_e = st.slider("Estrés", 1, 10, 3)
            if st.button("💾 Guardar Biometría"):
                conn.execute("INSERT OR REPLACE INTO biometrics VALUES (?,?,?,?,?)", (st.session_state.user, hoy, p_w, p_s, p_e))
                conn.commit(); st.success("Guardado.")

        st.divider()
        cons = pd.read_sql("SELECT SUM(prot) as p, SUM(carb) as c, SUM(fat) as g, SUM(kcal) as k FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy)).fillna(0).iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Proteína", f"{cons['p']:.1f}g", f"/{m['target_prot']}")
        c2.metric("Carbos", f"{cons['c']:.1f}g", f"/{m['target_carb']}")
        c3.metric("Grasas", f"{cons['g']:.1f}g", f"/{m['target_fat']}")
        c4.metric("Kcal", f"{int(cons['k'])}", f"/{int(m['target_kcal'])}")

        tiempos = ["Desayuno", "Almuerzo", "Cena", "Snacks"]
        for tiempo in tiempos:
            with st.container():
                st.markdown(f"### {tiempo}")
                logs_t = pd.read_sql("SELECT id, food_desc, kcal FROM logs WHERE username=? AND date=? AND meal_time=?", conn, params=(st.session_state.user, hoy, tiempo))
                for _, row in logs_t.iterrows():
                    st.write(f"🍳 {row['food_desc']} - **{int(row['kcal'])} kcal**")
                
                with st.expander(f"➕ Agregar a {tiempo}"):
                    cats = pd.read_sql("SELECT DISTINCT category FROM master_food", conn)['category'].tolist()
                    c_sel = st.selectbox("Categoría:", ["Todas"] + sorted([c for c in cats if c]), key=f"cat_{tiempo}")
                    df_alims = pd.read_sql("SELECT * FROM master_food" if c_sel=="Todas" else "SELECT * FROM master_food WHERE category=?", conn, params=(c_sel,) if c_sel!="Todas" else None)
                    a_sel = st.selectbox("Alimento:", [""] + sorted(df_alims['food_name'].tolist()) + ["➕ OTRO"], key=f"alim_{tiempo}")
                    gramos = st.number_input("Gramos:", 0.0, 1000.0, 100.0, key=f"gr_{tiempo}")
                    
                    if st.button("Registrar", key=f"btn_{tiempo}"):
                        food_f = st.session_state.get(f"text_{tiempo}", a_sel)
                        if a_sel == "➕ OTRO": food_f = st.text_input("Nombre:", key=f"text_{tiempo}")
                        
                        match = pd.read_sql("SELECT * FROM master_food WHERE LOWER(food_name) = ?", conn, params=(a_sel.lower(),))
                        if not match.empty:
                            f = match.iloc[0]; fac = gramos/100
                            conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)", 
                                        (st.session_state.user, hoy, f"{int(gramos)}g {f['food_name']}", f['p100']*fac, f['c100']*fac, f['g100']*fac, f['k100']*fac, 'Validado', tiempo))
                        else:
                            conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)", 
                                        (st.session_state.user, hoy, f"{int(gramos)}g {a_sel}", 0, 0, 0, 0, 'Pendiente', tiempo))
                        conn.commit(); st.rerun()
        conn.close()

    elif menu == "Historial": mostrar_historial(st.session_state.user)

    elif menu == "Maestro de Alimentos":
        st.header("📂 Base de Alimentos")
        search_term = st.text_input("🔍 Buscar:", "").lower()
        conn = sqlite3.connect(DB_PATH)
        base = pd.read_sql("SELECT food_name as Alimento, category as Categoría, p100, c100, g100, k100 FROM master_food", conn)
        if search_term: base = base[base['Alimento'].str.lower().str.contains(search_term)]
        st.dataframe(base, use_container_width=True, hide_index=True)
        
        with st.form("nuevo_alimento"):
            n_n = st.text_input("Nombre")
            n_c = st.text_input("Categoría")
            c1, c2, c3 = st.columns(3)
            n_p = c1.number_input("P")
            n_c1 = c2.number_input("C")
            n_g = c3.number_input("G")
            if st.form_submit_button("Guardar Alimento"):
                conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (n_n, n_p, n_c1, n_g, (n_p*4+n_c1*4+n_g*9), n_c))
                conn.commit(); st.rerun()
        conn.close()

    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.query_params.clear()
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
