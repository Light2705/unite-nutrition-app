import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE RUTAS ---
# Si estás en la nube, usa el directorio actual, si no, usa descargas
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
    # Tabla de Registros Diarios
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, 
                 food_desc TEXT, prot REAL, carb REAL, fat REAL, kcal REAL, status TEXT)''')
    
    # Insertar Admin por defecto (Cambia 'admin123' por algo seguro después)
    c.execute("INSERT OR IGNORE INTO users VALUES ('admin', 'admin123', 1, 0, 0, 0, 0, '2099-12-31')")
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
            if datetime.now() <= vencimiento:
                st.session_state.user = res.iloc[0]['username']
                st.session_state.admin = res.iloc[0]['is_admin']

# --- PANTALLA DE LOGIN / REGISTRO ---
if 'user' not in st.session_state:
    st.set_page_config(page_title="Unite Nutrition Login", page_icon="🏋️")
    st.title("🏋️ Unite Nutrition - Erick Quiroz")
    
    tab_login, tab_reg = st.tabs(["🔑 Iniciar Sesión", "📝 Registro de Atleta"])
    
    with tab_login:
        u = st.text_input("Usuario", key="login_u")
        p = st.text_input("Contraseña", type="password", key="login_p")
        if st.button("Entrar"):
            conn = sqlite3.connect(DB_PATH)
            # Validación segura contra inyección SQL
            query = "SELECT * FROM users WHERE username=? AND password=?"
            res = pd.read_sql(query, conn, params=(u, p))
            conn.close()
            
            if not res.empty:
                vencimiento = datetime.strptime(res.iloc[0]['expiry_date'], '%Y-%m-%d')
                if datetime.now() <= vencimiento:
                    st.session_state.user = u
                    st.session_state.admin = res.iloc[0]['is_admin']
                    st.query_params["user"] = u
                    st.rerun()
                else:
                    st.error("⚠️ Acceso vencido. Contacta al Coach Erick para renovar.")
            else:
                st.error("Usuario o contraseña incorrectos.")

    with tab_reg:
        st.subheader("Crea tu cuenta de Atleta")
        nu = st.text_input("Elige un Usuario", key="reg_u")
        np = st.text_input("Elige una Contraseña", type="password", key="reg_p")
        if st.button("Crear Cuenta"):
            if nu.strip() == "" or np.strip() == "":
                st.error("❌ Completa todos los campos.")
            else:
                conn = sqlite3.connect(DB_PATH)
                # Registro inicial bloqueado (vence ayer) hasta que el coach lo active
                venc_bloqueado = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                try:
                    conn.execute("INSERT INTO users VALUES (?, ?, 0, 0, 0, 0, 0, ?)", (nu, np, venc_bloqueado))
                    conn.commit()
                    st.success("✅ ¡Registro enviado! Avisa al Coach para que active tu plan.")
                except sqlite3.IntegrityError:
                    st.error("El nombre de usuario ya está tomado.")
                finally:
                    conn.close()

# --- APLICACIÓN PRINCIPAL (POST-LOGIN) ---
else:
    st.sidebar.title(f"🚀 {'Coach' if st.session_state.admin else 'Atleta'}")
    st.sidebar.write(f"Conectado como: **{st.session_state.user}**")
    
    opciones = ["Mi Diario", "Historial"]
    if st.session_state.admin: 
        opciones = ["Gestión de Clientes", "Maestro de Alimentos", "Mi Diario", "Historial"]
    
    menu = st.sidebar.radio("Navegación", opciones)

    # Función para mostrar historial en tablas
    def mostrar_historial(usuario):
        st.subheader(f"📅 Historial: {usuario}")
        conn = sqlite3.connect(DB_PATH)
        dias_es = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
        query = """SELECT date as Fecha, round(SUM(prot),1) as P, round(SUM(carb),1) as C, 
                   round(SUM(fat),1) as G, round(SUM(kcal),0) as Kcal 
                   FROM logs WHERE username=? GROUP BY date ORDER BY date DESC LIMIT 7"""
        df = pd.read_sql(query, conn, params=(usuario,))
        conn.close()
        if not df.empty:
            df['Fecha'] = pd.to_datetime(df['Fecha'])
            df.insert(0, "Día", df['Fecha'].dt.day_name().map(dias_es))
            df['Fecha'] = df['Fecha'].dt.strftime('%d/%m')
            st.dataframe(df, use_container_width=True, hide_index=True)
        else: st.info("Aún no tienes registros de consumo.")

    # --- LÓGICA DE MENÚS (REUTILIZADA DE TU ORIGINAL) ---
    if st.session_state.admin and menu == "Gestión de Clientes":
        st.header("👥 Control de Alumnos")
        conn = sqlite3.connect(DB_PATH)
        
        # Validar registros pendientes de alumnos
        pendientes = pd.read_sql("SELECT * FROM logs WHERE status='Pendiente'", conn)
        if not pendientes.empty:
            st.subheader("🔔 Alimentos por Validar")
            for _, r in pendientes.iterrows():
                with st.expander(f"🔴 {r['username']} - {r['food_desc']}"):
                    c1, c2, c3 = st.columns(3)
                    p_val = c1.number_input("Prot (100g)", 0.0, key=f"p_{r['id']}")
                    c_val = c2.number_input("Carb (100g)", 0.0, key=f"c_{r['id']}")
                    g_val = c3.number_input("Fat (100g)", 0.0, key=f"g_{r['id']}")
                    
                    if st.button("Validar y Guardar", key=f"btn_{r['id']}"):
                        gramos = float(r['food_desc'].split('g')[0]) if 'g' in r['food_desc'] else 100.0
                        factor = gramos / 100
                        kcal = (p_val*4 + c_val*4 + g_val*9) * factor
                        conn.execute("UPDATE logs SET prot=?, carb=?, fat=?, kcal=?, status='Validado' WHERE id=?", 
                                     (p_val*factor, c_val*factor, g_val*factor, kcal, r['id']))
                        # Guardar en maestro para que ya no pida validación
                        nombre = r['food_desc'].split(' ', 1)[1] if ' ' in r['food_desc'] else r['food_desc']
                        conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", 
                                     (nombre.strip(), p_val, c_val, g_val, p_val*4+c_val*4+g_val*9, "Validado"))
                        conn.commit(); st.rerun()

        # Gestión de Planes
        st.divider()
        usuarios = pd.read_sql("SELECT username, expiry_date, target_kcal FROM users WHERE is_admin=0", conn)
        st.dataframe(usuarios, use_container_width=True)
        
        sel_atleta = st.selectbox("Selecciona un alumno para editar plan:", [""] + usuarios['username'].tolist())
        if sel_atleta:
            m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(sel_atleta,)).iloc[0]
            with st.form("edit_plan"):
                st.write(f"Configurando a: **{sel_atleta}**")
                p_o = st.number_input("Proteína Meta", value=float(m['target_prot']))
                c_o = st.number_input("Carbos Meta", value=float(m['target_carb']))
                g_o = st.number_input("Grasas Meta", value=float(m['target_fat']))
                k_o = st.number_input("Calorías Meta", value=float(m['target_kcal']))
                dias = st.number_input("Sumar días de acceso", 0, 365, value=30)
                if st.form_submit_button("Guardar Cambios"):
                    nueva_f = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d')
                    conn.execute("UPDATE users SET expiry_date=?, target_prot=?, target_carb=?, target_fat=?, target_kcal=? WHERE username=?", 
                                 (nueva_f, p_o, c_o, g_o, k_o, sel_atleta))
                    conn.commit(); st.success("Plan Actualizado"); st.rerun()
        conn.close()

    elif menu == "Mi Diario":
        st.header(f"📓 Diario de Nutrición")
        conn = sqlite3.connect(DB_PATH)
        m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
        hoy = datetime.now().strftime('%Y-%m-%d')
        
        # Métricas principales
        cons = pd.read_sql("SELECT SUM(prot) as p, SUM(carb) as c, SUM(fat) as g, SUM(kcal) as k FROM logs WHERE username=? AND date=?", 
                           conn, params=(st.session_state.user, hoy)).fillna(0).iloc[0]
        
        cols = st.columns(4)
        cols[0].metric("Proteína", f"{cons['p']:.1f}g", f"/{m['target_prot']}g")
        cols[1].metric("Carbos", f"{cons['c']:.1f}g", f"/{m['target_carb']}g")
        cols[2].metric("Grasas", f"{cons['g']:.1f}g", f"/{m['target_fat']}g")
        cols[3].metric("Calorías", f"{int(cons['k'])}", f"/{int(m['target_kcal'])}")

        st.divider()
        # Buscador de Alimentos
        alims = pd.read_sql("SELECT food_name FROM master_food", conn)['food_name'].tolist()
        a_sel = st.selectbox("Registrar Alimento:", [""] + sorted(alims) + ["➕ OTRO (Consultar al Coach)"])
        gramos = st.number_input("Gramos consumidos:", 1.0, 2000.0, 100.0)
        
        if st.button("Añadir al Diario"):
            if a_sel == "➕ OTRO (Consultar al Coach)":
                nombre_otro = st.text_input("¿Qué comiste?")
                if nombre_otro:
                    conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status) VALUES (?,?,?,?,?,?,?,?)",
                                 (st.session_state.user, hoy, f"{int(gramos)}g {nombre_otro}", 0, 0, 0, 0, 'Pendiente'))
                    conn.commit(); st.rerun()
            elif a_sel != "":
                f = pd.read_sql("SELECT * FROM master_food WHERE food_name=?", conn, params=(a_sel,)).iloc[0]
                fac = gramos/100
                conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status) VALUES (?,?,?,?,?,?,?,?)",
                             (st.session_state.user, hoy, f"{int(gramos)}g {a_sel}", f['p100']*fac, f['c100']*fac, f['g100']*fac, f['k100']*fac, 'Validado'))
                conn.commit(); st.rerun()

        # Tabla de hoy
        st.subheader("Consumo del día")
        tabla_hoy = pd.read_sql("SELECT id, food_desc as Alimento, round(prot,1) as P, round(kcal,0) as Kcal FROM logs WHERE username=? AND date=?", 
                                conn, params=(st.session_state.user, hoy))
        st.dataframe(tabla_hoy, use_container_width=True, hide_index=True)
        conn.close()

    elif menu == "Historial":
        mostrar_historial(st.session_state.user)

    elif menu == "Maestro de Alimentos":
        st.header("📂 Base de Datos de Alimentos")
        archivo = st.file_uploader("Importar desde Excel", type=["xlsx"])
        if archivo and st.button("Cargar Alimentos"):
            df = pd.read_excel(archivo)
            df.columns = [c.lower().strip() for c in df.columns]
            conn = sqlite3.connect(DB_PATH)
            for _, r in df.iterrows():
                p, c, g = float(r['proteina']), float(r['carbos']), float(r['grasas'])
                conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", 
                             (str(r['nombre']).strip(), p, c, g, (p*4+c*4+g*9), str(r['categoria'])))
            conn.commit(); conn.close(); st.success("Base de datos actualizada.")

    # --- BOTÓN CERRAR SESIÓN ---
    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.query_params.clear()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
