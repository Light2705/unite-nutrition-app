import streamlit as st
import pandas as pd
import sqlite3
import os
import re 
from datetime import datetime, timedelta

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
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, 
                 food_desc TEXT, prot REAL, carb REAL, fat REAL, kcal REAL, status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS biometrics 
                 (username TEXT, date TEXT, weight REAL, sleep INTEGER, stress INTEGER, 
                 PRIMARY KEY (username, date))''')
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
            if datetime.now() <= vencimiento:
                st.session_state.user = res.iloc[0]['username']
                st.session_state.admin = res.iloc[0]['is_admin']

# --- LOGIN / REGISTRO ---
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
            if nu.strip() == "" or np.strip() == "":
                st.error("❌ El usuario y la contraseña no pueden estar vacíos.")
            else:
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
        else: st.info("No hay registros de alimentación en el periodo seleccionado.")

    if st.session_state.admin and menu == "Gestión de Clientes":
        # ... (Mantener igual que antes para no borrar nada)
        st.header("👥 Control de Alumnos")
        conn = sqlite3.connect(DB_PATH)
        hoy = datetime.now().strftime('%Y-%m-%d')
        hora_actual = datetime.now().hour
        alumnos_check = pd.read_sql("SELECT username FROM users WHERE is_admin=0", conn)['username'].tolist()
        for alum in alumnos_check:
            reg_hoy = pd.read_sql("SELECT count(*) as total FROM logs WHERE username=? AND date=?", conn, params=(alum, hoy)).iloc[0]['total']
            if reg_hoy == 0 and hora_actual >= 16:
                 st.markdown(f'<div style="color: #ff4b4b; border: 1px solid #ff4b4b; padding: 10px; border-radius: 5px;">⚠️ <b>{alum}</b> no ha registrado comidas hoy.</div>', unsafe_allow_html=True)
        st.divider()
        pendientes = pd.read_sql("SELECT * FROM logs WHERE status='Pendiente'", conn)
        if not pendientes.empty:
            st.subheader("🔔 Alimentos Pendientes por Clasificar")
            cats_existentes = pd.read_sql("SELECT DISTINCT category FROM master_food", conn)['category'].tolist()
            for _, r in pendientes.iterrows():
                with st.expander(f"🔴 {r['username']} - {r['food_desc']}"):
                    c1, c2, c3 = st.columns(3)
                    p_val = c1.number_input("Prot (100g)", 0.0, key=f"p_val_{r['id']}")
                    c_val = c2.number_input("Carb (100g)", 0.0, key=f"c_val_{r['id']}")
                    g_val = c3.number_input("Fat (100g)", 0.0, key=f"g_val_{r['id']}")
                    col_cat, col_new = st.columns(2)
                    cat_sel = col_cat.selectbox("Clasificar en:", [""] + sorted([c for c in cats_existentes if c]) + ["➕ Nueva Categoría"], key=f"cat_sel_{r['id']}")
                    nueva_cat_nombre = ""
                    if cat_sel == "➕ Nueva Categoría":
                        nueva_cat_nombre = col_new.text_input("Nombre de la categoría:", key=f"new_cat_{r['id']}").strip().capitalize()
                    categoria_final = nueva_cat_nombre if cat_sel == "➕ Nueva Categoría" else cat_sel
                    col_v, col_r = st.columns(2)
                    if col_v.button("✅ Validar y Guardar", key=f"v_btn_{r['id']}"):
                        if categoria_final == "": st.error("Selecciona categoría.")
                        else:
                            try: gramos_atleta = float(r['food_desc'].split('g')[0])
                            except: gramos_atleta = 100.0
                            factor = gramos_atleta / 100
                            k_calc = (p_val*4 + c_val*4 + g_val*9) * factor
                            conn.execute("UPDATE logs SET prot=?, carb=?, fat=?, kcal=?, status='Validado' WHERE id=?", (p_val*factor, c_val*factor, g_val*factor, k_calc, r['id']))
                            nombre_limpio = r['food_desc'].split(' ', 1)[1] if ' ' in r['food_desc'] else r['food_desc']
                            conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (nombre_limpio.strip(), p_val, c_val, g_val, p_val*4+c_val*4+g_val*9, categoria_final))
                            conn.commit(); st.rerun()
                    if col_r.button("🗑️ Rechazar / Borrar", key=f"del_log_{r['id']}"):
                        conn.execute("DELETE FROM logs WHERE id=?", (r['id'],))
                        conn.commit(); st.rerun()
        st.divider()
        usuarios_lista = pd.read_sql("SELECT username as Alumno, expiry_date as Acceso_Hasta FROM users WHERE is_admin=0", conn)
        st.dataframe(usuarios_lista, use_container_width=True)
        sel_atleta = st.selectbox("Selecciona un alumno:", [""] + usuarios_lista['Alumno'].tolist())
        if sel_atleta:
            m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(sel_atleta,)).iloc[0]
            last_bio = pd.read_sql("SELECT * FROM biometrics WHERE username=? ORDER BY date DESC LIMIT 1", conn, params=(sel_atleta,))
            t_hoy, t_hist, t_cfg = st.tabs(["📊 Hoy", "📅 Historial Completo", "⚙️ Plan"])
            with t_hoy:
                if not last_bio.empty:
                    st.info(f"🧬 **Último Peso:** {last_bio.iloc[0]['weight']}kg | **Sueño:** {last_bio.iloc[0]['sleep']}/10 | **Estrés:** {last_bio.iloc[0]['stress']}/10")
                cons = pd.read_sql("SELECT SUM(prot) as p, SUM(carb) as c, SUM(fat) as g, SUM(kcal) as k FROM logs WHERE username=? AND date=?", conn, params=(sel_atleta, hoy)).fillna(0).iloc[0]
                cols = st.columns(4)
                cols[0].metric("P", f"{cons['p']:.1f}g", f"/{m['target_prot']}g")
                cols[1].metric("C", f"{cons['c']:.1f}g", f"/{m['target_carb']}g")
                cols[2].metric("G", f"{cons['g']:.1f}g", f"/{m['target_fat']}g")
                cols[3].metric("Kcal", f"{int(cons['k'])}", f"/{int(m['target_kcal'])}")
            with t_hist: mostrar_historial(sel_atleta)
            with t_cfg:
                dias = st.number_input("Añadir días de acceso:", 0, 30)
                nueva_f = (datetime.strptime(m['expiry_date'], '%Y-%m-%d') + timedelta(days=dias)).strftime('%Y-%m-%d')
                p_o = st.number_input("P Meta", value=float(m['target_prot']))
                c_o = st.number_input("C Meta", value=float(m['target_carb']))
                g_o = st.number_input("G Meta", value=float(m['target_fat']))
                k_o = st.number_input("Kcal Meta", value=float(m['target_kcal']))
                if st.button("💾 Actualizar Plan"):
                    conn.execute("UPDATE users SET expiry_date=?, target_prot=?, target_carb=?, target_fat=?, target_kcal=? WHERE username=?", (nueva_f, p_o, c_o, g_o, k_o, sel_atleta))
                    conn.commit(); st.success("Plan actualizado."); st.rerun()
        st.divider()
        st.subheader("⚠️ Zona de Peligro")
        user_to_delete = st.selectbox("Selecciona alumno para BORRAR:", [""] + usuarios_lista['Alumno'].tolist(), key="del_user")
        if st.button("🗑️ Eliminar Alumno Definitivamente"):
            if user_to_delete != "":
                conn.execute("DELETE FROM users WHERE username=?", (user_to_delete,))
                conn.execute("DELETE FROM logs WHERE username=?", (user_to_delete,))
                conn.execute("DELETE FROM biometrics WHERE username=?", (user_to_delete,))
                conn.commit(); st.rerun()
        conn.close()

    elif menu == "Mi Diario":
        conn = sqlite3.connect(DB_PATH)
        m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(st.session_state.user,)).iloc[0]
        hoy_dt = datetime.now()
        hoy = hoy_dt.strftime('%Y-%m-%d')
        dias_es = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
        dia_nombre = dias_es[hoy_dt.strftime('%A')]

        st.header(f"📓 Diario: {st.session_state.user}")
        st.subheader(f"📅 {dia_nombre}, {hoy_dt.strftime('%d/%m/%Y')}")
        
        with st.expander("🧪 Registrar Biometría (Peso, Sueño, Estrés)"):
            c_b1, c_b2, c_b3 = st.columns(3)
            p_w = c_b1.number_input("Peso Actual (kg)", 30.0, 200.0, 75.0, step=0.1)
            p_s = c_b2.slider("Calidad de Sueño", 1, 10, 7)
            p_e = c_b3.slider("Nivel de Estrés", 1, 10, 3)
            if st.button("💾 Guardar Datos Físicos"):
                conn.execute("INSERT OR REPLACE INTO biometrics VALUES (?,?,?,?,?)", (st.session_state.user, hoy, p_w, p_s, p_e))
                conn.commit(); st.success("Biometría guardada.")

        st.divider()
        cons = pd.read_sql("SELECT SUM(prot) as p, SUM(carb) as c, SUM(fat) as g, SUM(kcal) as k FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy)).fillna(0).iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Proteína", f"{cons['p']:.1f}g", f"Meta: {m['target_prot']}g")
        c2.metric("Carbos", f"{cons['c']:.1f}g", f"Meta: {m['target_carb']}g")
        c3.metric("Grasas", f"{cons['g']:.1f}g", f"Meta: {m['target_fat']}g")
        c4.metric("Kcal", f"{int(cons['k'])}", f"Meta: {int(m['target_kcal'])}")
        
        st.divider()
        cats = pd.read_sql("SELECT DISTINCT category FROM master_food", conn)['category'].tolist()
        c_sel = st.selectbox("Filtrar por Categoría:", ["Todas"] + sorted([c for c in cats if c]))
        
        if c_sel == "Todas":
            alims = pd.read_sql("SELECT food_name FROM master_food", conn)['food_name'].tolist()
        else:
            alims = pd.read_sql("SELECT food_name FROM master_food WHERE category=?", conn, params=(c_sel,))['food_name'].tolist()
        
        a_sel = st.selectbox("Selecciona Alimento:", [""] + sorted(alims) + ["➕ OTRO"])
        gramos = st.number_input("Gramos consumidos:", min_value=1.0, value=100.0)
        
        food_f = ""
        if a_sel == "➕ OTRO": 
            # --- CAMBIO AQUÍ: BLOQUEO DE TECLAS NUMÉRICAS CON JAVASCRIPT ---
            food_f = st.text_input("Escribe el nombre del alimento:", key="food_input_text").strip()
            
            # Inyección de JavaScript para evitar que el navegador acepte números en el input
            st.components.v1.html(
                """
                <script>
                var input = window.parent.document.querySelectorAll('input[type="text"]');
                for (var i = 0; i < input.length; i++) {
                    if (input[i].getAttribute('aria-label') == 'Escribe el nombre del alimento:') {
                        input[i].onkeydown = function(e) {
                            if (e.key >= '0' && e.key <= '9') {
                                return false;
                            }
                        };
                    }
                }
                </script>
                """,
                height=0,
            )
            
        elif a_sel != "":
            food_f = a_sel
            pre = pd.read_sql("SELECT * FROM master_food WHERE food_name=?", conn, params=(food_f,)).iloc[0]
            st.info(f"💡 {gramos}g aportan: **P:** {pre['p100']*(gramos/100):.1f}g | **C:** {pre['c100']*(gramos/100):.1f}g | **G:** {pre['g100']*(gramos/100):.1f}g")

        if st.button("✅ Registrar Consumo"):
            if food_f != "":
                match = pd.read_sql("SELECT * FROM master_food WHERE LOWER(food_name) = ?", conn, params=(food_f.lower(),))
                if not match.empty:
                    f = match.iloc[0]; fac = gramos/100
                    conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status) VALUES (?,?,?,?,?,?,?,?)", (st.session_state.user, hoy, f"{int(gramos)}g {f['food_name']}", f['p100']*fac, f['c100']*fac, f['g100']*fac, f['k100']*fac, 'Validado'))
                else:
                    conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status) VALUES (?,?,?,?,?,?,?,?)", (st.session_state.user, hoy, f"{int(gramos)}g {food_f}", 0, 0, 0, 0, 'Pendiente'))
                conn.commit(); st.rerun()

        st.subheader("Consumo de hoy")
        tabla_hoy = pd.read_sql("SELECT id, food_desc as Plato, round(prot,1) as P, round(carb,1) as C, round(fat,1) as G, round(kcal,0) as Kcal FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
        st.dataframe(tabla_hoy, use_container_width=True, hide_index=True)
        if not tabla_hoy.empty:
            id_borrar = st.selectbox("ID para eliminar:", tabla_hoy['id'].tolist())
            if st.button("🗑️ Borrar"):
                conn.execute("DELETE FROM logs WHERE id=?", (id_borrar,))
                conn.commit(); st.rerun()
        conn.close()

    elif menu == "Historial": mostrar_historial(st.session_state.user)
    elif menu == "Maestro de Alimentos":
        # ... (Mantener igual para no borrar nada)
        st.header("📂 Base de Alimentos")
        archivo = st.file_uploader("Sube tu Excel (.xlsx)", type=["xlsx"])
        if archivo and st.button("🚀 Importar Base"):
            df = pd.read_excel(archivo); df.columns = [c.lower().strip() for c in df.columns]
            conn = sqlite3.connect(DB_PATH)
            for _, r in df.iterrows():
                p, c, g = float(r['proteina']), float(r['carbos']), float(r['grasas'])
                conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (str(r['nombre']).strip(), p, c, g, (p*4+c*4+g*9), str(r['categoria']).capitalize()))
            conn.commit(); conn.close(); st.success("Base actualizada.")
        st.divider()
        conn = sqlite3.connect(DB_PATH)
        base_actual = pd.read_sql("SELECT food_name as Alimento, category as Categoría, p100 as Prot, c100 as Carb, g100 as Fat FROM master_food", conn)
        st.dataframe(base_actual, use_container_width=True, hide_index=True)
        st.subheader("✏️ Editar Macros")
        alim_a_editar = st.selectbox("Selecciona alimento:", [""] + base_actual['Alimento'].tolist())
        if alim_a_editar:
            datos_alim = pd.read_sql("SELECT * FROM master_food WHERE food_name=?", conn, params=(alim_a_editar,)).iloc[0]
            with st.form("edit_macros_form"):
                ed_nombre = st.text_input("Nombre", value=datos_alim['food_name'])
                ed_cat = st.text_input("Categoría", value=datos_alim['category'])
                c1, c2, c3 = st.columns(3)
                ed_p = c1.number_input("P/100g", value=float(datos_alim['p100']))
                ed_c = c2.number_input("C/100g", value=float(datos_alim['c100']))
                ed_g = c3.number_input("G/100g", value=float(datos_alim['g100']))
                if st.form_submit_button("💾 Guardar"):
                    ed_k = (ed_p * 4) + (ed_c * 4) + (ed_g * 9)
                    if ed_nombre != datos_alim['food_name']: conn.execute("DELETE FROM master_food WHERE food_name=?", (datos_alim['food_name'],))
                    conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (ed_nombre.strip(), ed_p, ed_c, ed_g, ed_k, ed_cat.strip().capitalize()))
                    conn.commit(); st.rerun()
        food_to_delete = st.selectbox("Eliminar alimento:", [""] + base_actual['Alimento'].tolist(), key="del_food")
        if st.button("🗑️ Eliminar"):
            if food_to_delete != "":
                conn.execute("DELETE FROM master_food WHERE food_name=?", (food_to_delete,))
                conn.commit(); st.rerun()
        conn.close()

    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.query_params.clear()
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
