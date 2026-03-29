import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE RUTAS ---
BASE_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
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
                 food_desc TEXT, prot REAL, carb REAL, fat REAL, kcal REAL, status TEXT)''')
    c.execute("INSERT OR IGNORE INTO users VALUES ('admin', 'admin123', 1, 0, 0, 0, 0, '2099-12-31')")
    conn.commit()
    conn.close()

init_db()

# --- LÓGICA DE PERSISTENCIA ---
if 'user' not in st.session_state:
    params = st.query_params
    if "user" in params:
        u_url = params["user"]
        conn = sqlite3.connect(DB_PATH)
        res = pd.read_sql(f"SELECT * FROM users WHERE username='{u_url}'", conn)
        conn.close()
        if not res.empty:
            vencimiento = datetime.strptime(res.iloc[0]['expiry_date'], '%Y-%m-%d')
            if datetime.now() <= vencimiento:
                st.session_state.user = res.iloc[0]['username']
                st.session_state.admin = res.iloc[0]['is_admin']

# --- LOGIN / REGISTRO ---
if 'user' not in st.session_state:
    st.title("🏋️ Unite Nutrition - Erick Quiroz")
    tab_login, tab_reg = st.tabs(["🔑 Iniciar Sesión", "📝 Registro de Atleta"])
    with tab_login:
        u = st.text_input("Usuario", key="login_u")
        p = st.text_input("Contraseña", type="password", key="login_p")
        if st.button("Entrar"):
            conn = sqlite3.connect(DB_PATH)
            res = pd.read_sql(f"SELECT * FROM users WHERE username='{u}' AND password='{p}'", conn)
            conn.close()
            if not res.empty:
                vencimiento = datetime.strptime(res.iloc[0]['expiry_date'], '%Y-%m-%d')
                if datetime.now() <= vencimiento:
                    st.session_state.user = u
                    st.session_state.admin = res.iloc[0]['is_admin']
                    st.query_params["user"] = u
                    st.rerun()
                else:
                    st.error("⚠️ Acceso vencido o pendiente de activación.")
            else:
                st.error("Credenciales incorrectas.")
    with tab_reg:
        nu = st.text_input("Nuevo Usuario", key="reg_u")
        np = st.text_input("Nueva Contraseña", type="password", key="reg_p")
        if st.button("Crear Cuenta"):
            conn = sqlite3.connect(DB_PATH)
            venc_bloqueado = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            try:
                conn.execute("INSERT INTO users VALUES (?, ?, 0, 0, 0, 0, 0, ?)", (nu, np, venc_bloqueado))
                conn.commit()
                st.success("✅ ¡Registro exitoso! Avisa al Coach Erick.")
            except: st.error("El usuario ya existe.")
            conn.close()

else:
    # --- BARRA LATERAL ---
    st.sidebar.title(f"🚀 {'Coach' if st.session_state.admin else 'Atleta'}")
    st.sidebar.write(f"Usuario: **{st.session_state.user}**")
    
    if st.sidebar.button("🔄 Actualizar Datos"):
        st.rerun()

    opciones = ["Mi Diario", "Historial"]
    if st.session_state.admin: opciones = ["Gestión de Clientes", "Maestro de Alimentos", "Mi Diario", "Historial"]
    menu = st.sidebar.radio("Navegación", opciones)

    # --- FUNCIÓN COMPARTIDA DE HISTORIAL (ÚLTIMOS 7 DÍAS) ---
    def mostrar_historial(usuario):
        st.subheader(f"📅 Últimos 7 días registrados: {usuario}")
        conn = sqlite3.connect(DB_PATH)
        
        dias_es = {
            'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
            'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
        }
        
        query = f"""
            SELECT date as Fecha, 
                   round(SUM(prot),1) as P_Total, 
                   round(SUM(carb),1) as C_Total, 
                   round(SUM(fat),1) as G_Total, 
                   round(SUM(kcal),0) as Kcal_Total 
            FROM logs 
            WHERE username='{usuario}' 
            GROUP BY date 
            ORDER BY date DESC
            LIMIT 7
        """
        df = pd.read_sql(query, conn)
        conn.close()
        
        if not df.empty:
            df['Fecha'] = pd.to_datetime(df['Fecha'])
            df.insert(0, "Día", df['Fecha'].dt.day_name().map(dias_es))
            df['Fecha'] = df['Fecha'].dt.strftime('%d/%m')
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No hay registros en la última semana.")

    # --- GESTIÓN DE CLIENTES ---
    if st.session_state.admin and menu == "Gestión de Clientes":
        st.header("👥 Control de Alumnos")
        conn = sqlite3.connect(DB_PATH)
        hoy = datetime.now().strftime('%Y-%m-%d')
        
        pendientes = pd.read_sql("SELECT * FROM logs WHERE status='Pendiente'", conn)
        if not pendientes.empty:
            st.subheader("🔔 Alimentos Pendientes")
            for _, r in pendientes.iterrows():
                with st.expander(f"🔴 {r['username']} - {r['food_desc']}"):
                    c1, c2, c3 = st.columns(3)
                    p_val = c1.number_input("Prot (100g)", 0.0, key=f"p_val_{r['id']}")
                    c_val = c2.number_input("Carb (100g)", 0.0, key=f"c_val_{r['id']}")
                    g_val = c3.number_input("Fat (100g)", 0.0, key=f"g_val_{r['id']}")
                    if st.button("Validar", key=f"v_btn_{r['id']}"):
                        try: gramos_atleta = float(r['food_desc'].split('g')[0])
                        except: gramos_atleta = 100.0
                        factor = gramos_atleta / 100
                        k_calc = (p_val*4 + c_val*4 + g_val*9) * factor
                        conn.execute("UPDATE logs SET prot=?, carb=?, fat=?, kcal=?, status='Validado' WHERE id=?",
                                     (p_val*factor, c_val*factor, g_val*factor, k_calc, r['id']))
                        nombre_limpio = r['food_desc'].split(' ', 1)[1] if ' ' in r['food_desc'] else r['food_desc']
                        conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)",
                                     (nombre_limpio.strip(), p_val, c_val, g_val, p_val*4+c_val*4+g_val*9, "Validado"))
                        conn.commit()
                        st.rerun()

        st.divider()
        usuarios_lista = pd.read_sql("SELECT username as Alumno, expiry_date as Acceso_Hasta FROM users WHERE is_admin=0", conn)
        st.dataframe(usuarios_lista, use_container_width=True)
        
        sel_atleta = st.selectbox("Selecciona un alumno:", [""] + usuarios_lista['Alumno'].tolist())
        if sel_atleta:
            m = pd.read_sql(f"SELECT * FROM users WHERE username='{sel_atleta}'", conn).iloc[0]
            t_hoy, t_hist, t_cfg = st.tabs(["📊 Hoy", "📅 Últimos 7 Días", "⚙️ Plan"])
            
            with t_hoy:
                cons = pd.read_sql(f"SELECT SUM(prot) as p, SUM(carb) as c, SUM(fat) as g, SUM(kcal) as k FROM logs WHERE username='{sel_atleta}' AND date='{hoy}'", conn).fillna(0).iloc[0]
                cols = st.columns(4)
                cols[0].metric("P", f"{cons['p']:.1f}g", f"/{m['target_prot']}g")
                cols[1].metric("C", f"{cons['c']:.1f}g", f"/{m['target_carb']}g")
                cols[2].metric("G", f"{cons['g']:.1f}g", f"/{m['target_fat']}g")
                cols[3].metric("Kcal", f"{int(cons['k'])}", f"/{int(m['target_kcal'])}")

            with t_hist:
                mostrar_historial(sel_atleta)

            with t_cfg:
                dias = st.number_input("Días extra de acceso:", 0, 30)
                nueva_f = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d')
                p_o = st.number_input("P Meta", value=float(m['target_prot']))
                c_o = st.number_input("C Meta", value=float(m['target_carb']))
                g_o = st.number_input("G Meta", value=float(m['target_fat']))
                k_o = st.number_input("Kcal Meta", value=float(m['target_kcal']))
                if st.button("💾 Actualizar Plan"):
                    conn.execute("UPDATE users SET expiry_date=?, target_prot=?, target_carb=?, target_fat=?, target_kcal=? WHERE username=?",
                                 (nueva_f, p_o, c_o, g_o, k_o, sel_atleta))
                    conn.commit()
                    st.success("Plan actualizado.")
                    st.rerun()
        conn.close()

    # --- MI DIARIO ---
    elif menu == "Mi Diario":
        conn = sqlite3.connect(DB_PATH)
        m = pd.read_sql(f"SELECT * FROM users WHERE username='{st.session_state.user}'", conn).iloc[0]
        hoy_dt = datetime.now()
        hoy = hoy_dt.strftime('%Y-%m-%d')
        
        dias_es = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 
                   'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
        dia_nombre = dias_es[hoy_dt.strftime('%A')]

        st.header(f"📓 Diario: {st.session_state.user}")
        st.subheader(f"📅 {dia_nombre}, {hoy_dt.strftime('%d/%m/%Y')}")
        
        cons = pd.read_sql(f"SELECT SUM(prot) as p, SUM(carb) as c, SUM(fat) as g, SUM(kcal) as k FROM logs WHERE username='{st.session_state.user}' AND date='{hoy}'", conn).fillna(0).iloc[0]
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Proteína", f"{cons['p']:.1f}g", f"Meta: {m['target_prot']}g")
        c2.metric("Carbos", f"{cons['c']:.1f}g", f"Meta: {m['target_carb']}g")
        c3.metric("Grasas", f"{cons['g']:.1f}g", f"Meta: {m['target_fat']}g")
        c4.metric("Kcal", f"{int(cons['k'])}", f"Meta: {int(m['target_kcal'])}")
        
        st.divider()
        cats = pd.read_sql("SELECT DISTINCT category FROM master_food", conn)['category'].tolist()
        c_sel = st.selectbox("Categoría:", ["Todas"] + sorted(cats))
        q = "SELECT food_name FROM master_food"
        if c_sel != "Todas": q += f" WHERE category = '{c_sel}'"
        alims = pd.read_sql(q, conn)['food_name'].tolist()
        a_sel = st.selectbox("Alimento:", [""] + sorted(alims) + ["➕ OTRO"])

        gramos = st.number_input("Gramos (pesado):", min_value=1.0, value=100.0)
        
        if a_sel == "➕ OTRO":
            food_f = st.text_input("Nombre:").strip()
        elif a_sel != "":
            food_f = a_sel
            pre = pd.read_sql("SELECT * FROM master_food WHERE food_name=?", conn, params=(food_f,)).iloc[0]
            st.info(f"💡 {gramos}g aportan {pre['p100']*(gramos/100):.1f}g de Proteína.")

        if st.button("✅ Registrar") and a_sel != "":
            match = pd.read_sql("SELECT * FROM master_food WHERE LOWER(food_name) = ?", conn, params=(food_f.lower(),))
            if not match.empty:
                f = match.iloc[0]
                fac = gramos/100
                conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status) VALUES (?,?,?,?,?,?,?,?)",
                             (st.session_state.user, hoy, f"{int(gramos)}g {f['food_name']}", f['p100']*fac, f['c100']*fac, f['g100']*fac, f['k100']*fac, 'Validado'))
            else:
                conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status) VALUES (?,?,?,?,?,?,?,?)",
                             (st.session_state.user, hoy, f"{int(gramos)}g {food_f}", 0, 0, 0, 0, 'Pendiente'))
            conn.commit()
            st.rerun()

        st.subheader("Consumo de hoy")
        tabla_hoy = pd.read_sql(f"SELECT id, food_desc as Plato, round(prot,1) as P, round(carb,1) as C, round(fat,1) as G, round(kcal,0) as Kcal FROM logs WHERE username='{st.session_state.user}' AND date='{hoy}'", conn)
        st.dataframe(tabla_hoy, use_container_width=True, hide_index=True)
        conn.close()

    # --- HISTORIAL ---
    elif menu == "Historial":
        mostrar_historial(st.session_state.user)

    # --- MAESTRO DE ALIMENTOS ---
    elif menu == "Maestro de Alimentos":
        st.header("📂 Base de Alimentos")
        archivo = st.file_uploader("Sube tu Excel (.xlsx)", type=["xlsx"])
        if archivo and st.button("🚀 Importar"):
            df = pd.read_excel(archivo)
            df.columns = [c.lower().strip() for c in df.columns]
            conn = sqlite3.connect(DB_PATH)
            for _, r in df.iterrows():
                p, c, g = float(r['proteina']), float(r['carbos']), float(r['grasas'])
                conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)",
                             (str(r['nombre']).strip(), p, c, g, (p*4+c*4+g*9), str(r['categoria']).capitalize()))
            conn.commit()
            conn.close()
            st.success("Base actualizada.")

    if st.sidebar.button("Cerrar Sesión"):
        st.query_params.clear()
        if 'user' in st.session_state: del st.session_state.user
        st.rerun()