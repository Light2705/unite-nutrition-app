import streamlit as st
import pandas as pd
import sqlite3
import os
import re
from datetime import datetime, timedelta

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
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, is_admin INTEGER, 
                 target_prot REAL, target_carb REAL, target_fat REAL, target_kcal REAL, expiry_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS master_food
                 (food_name TEXT PRIMARY KEY, p100 REAL, c100 REAL, g100 REAL, k100 REAL, category TEXT)''')
    try:
        c.execute("ALTER TABLE logs ADD COLUMN meal_time TEXT DEFAULT 'General'")
    except:
        pass
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
        nu = st.text_input("Nuevo Usuario (Sin números)", key="reg_u")
        np = st.text_input("Nueva Contraseña", type="password", key="reg_p")
        if st.button("Crear Cuenta"):
            if nu.strip() == "" or np.strip() == "":
                st.error("❌ El usuario y la contraseña no pueden estar vacíos.")
            elif validar_solo_letras(nu):
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
        st.header("👥 Control de Alumnos y Mis Macros")
        conn = sqlite3.connect(DB_PATH)
        hoy = datetime.now().strftime('%Y-%m-%d')
        hora_actual = datetime.now().hour
        
        alumnos_check = pd.read_sql("SELECT username FROM users WHERE is_admin=0", conn)['username'].tolist()
        for alum in alumnos_check:
            reg_hoy = pd.read_sql("SELECT count(*) as total FROM logs WHERE username=? AND date=?", conn, params=(alum, hoy)).iloc[0]['total']
            if reg_hoy == 0 and hora_actual >= 16:
                 st.markdown(f'<div style="color: #ff4b4b; border: 1px solid #ff4b4b; padding: 10px; border-radius: 5px; margin-bottom:10px;">⚠️ <b>{alum}</b> no ha registrado comidas hoy.</div>', unsafe_allow_html=True)
        
        st.divider()
        pendientes = pd.read_sql("SELECT * FROM logs WHERE status='Pendiente'", conn)
        if not pendientes.empty:
            st.subheader("🔔 Alimentos Pendientes por Clasificar")
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
                    nueva_cat_nombre = ""
                    if cat_sel == "➕ Nueva Categoría":
                        nueva_cat_nombre = col_new.text_input("Nombre de la categoría:", key=f"new_cat_{r['id']}").strip().capitalize()
                    categoria_final = nueva_cat_nombre if cat_sel == "➕ Nueva Categoría" else cat_sel
                    col_v, col_r = st.columns(2)
                    if col_v.button("✅ Validar", key=f"v_btn_{r['id']}"):
                        if categoria_final == "": st.error("Selecciona categoría.")
                        else:
                            try: gramos_atleta = float(r['food_desc'].split('g')[0])
                            except: gramos_atleta = 100.0
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
        sel_atleta = st.selectbox("Selecciona un usuario (Alumno o Tú mismo):", [""] + usuarios_all['Alumno'].tolist())
        
        if sel_atleta:
            m = pd.read_sql("SELECT * FROM users WHERE username=?", conn, params=(sel_atleta,)).iloc[0]
            last_bio = pd.read_sql("SELECT * FROM biometrics WHERE username=? ORDER BY date DESC LIMIT 1", conn, params=(sel_atleta,))
            t_hoy, t_hist, t_cfg = st.tabs(["📊 Hoy (Desglose)", "📅 Historial", "⚙️ Configuración Plan"])
            with t_hoy:
                if not last_bio.empty:
                    st.info(f"🧬 **Peso:** {last_bio.iloc[0]['weight']}kg | **Sueño:** {last_bio.iloc[0]['sleep']}/10 | **Estrés:** {last_bio.iloc[0]['stress']}/10")
                st.write(f"🍴 **Comidas registradas por {sel_atleta} hoy:**")
                detalles_hoy = pd.read_sql("SELECT id, food_desc as Plato, round(prot,1) as P, round(carb,1) as C, round(fat,1) as G, round(kcal,0) as Kcal FROM logs WHERE username=? AND date=?", conn, params=(sel_atleta, hoy))
                if not detalles_hoy.empty:
                    st.table(detalles_hoy.drop(columns=['id']))
                    cons_tot = detalles_hoy.sum(numeric_only=True)
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Total P", f"{cons_tot['P']:.1f}g", f"/{m['target_prot']}")
                    c2.metric("Total C", f"{cons_tot['C']:.1f}g", f"/{m['target_carb']}")
                    c3.metric("Total G", f"{cons_tot['G']:.1f}g", f"/{m['target_fat']}")
                    c4.metric("Total Kcal", f"{int(cons_tot['Kcal'])}", f"/{int(m['target_kcal'])}")
                else: st.info("Sin registros el día de hoy.")
            with t_hist: mostrar_historial(sel_atleta)
            with t_cfg:
                st.subheader(f"Editar metas de {sel_atleta}")
                if m['is_admin'] == 0:
                    dias = st.number_input("Añadir días de acceso:", 0, 30)
                    nueva_f = (datetime.strptime(m['expiry_date'], '%Y-%m-%d') + timedelta(days=dias)).strftime('%Y-%m-%d')
                else: nueva_f = m['expiry_date']
                p_o = st.number_input("P Meta", value=float(m['target_prot']))
                c_o = st.number_input("C Meta", value=float(m['target_carb']))
                g_o = st.number_input("G Meta", value=float(m['target_fat']))
                k_o = st.number_input("Kcal Meta", value=float(m['target_kcal']))
                if st.button("💾 Guardar Cambios en Plan"):
                    conn.execute("UPDATE users SET expiry_date=?, target_prot=?, target_carb=?, target_fat=?, target_kcal=? WHERE username=?", (nueva_f, p_o, c_o, g_o, k_o, sel_atleta))
                    conn.commit(); st.success("¡Plan actualizado!"); st.rerun()

        st.divider()
        st.subheader("⚠️ Zona de Peligro")
        user_to_delete = st.selectbox("Borrar ALUMNO definitivamente:", [""] + usuarios_all[usuarios_all['is_admin']==0]['Alumno'].tolist(), key="del_user")
        if st.button("🗑️ Eliminar Alumno"):
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
        ayer = (hoy_dt - timedelta(days=1)).strftime('%Y-%m-%d')
        dias_es = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
        dia_nombre = dias_es[hoy_dt.strftime('%A')]

        st.header(f"📓 Diario: {st.session_state.user}")
        st.subheader(f"📅 {dia_nombre}, {hoy_dt.strftime('%d/%m/%Y')}")

        # --- FUNCIÓN NUEVA: COPIAR AYER ---
        if st.button("📋 Copiar todas las comidas de ayer"):
            logs_ayer = pd.read_sql("SELECT * FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, ayer))
            if not logs_ayer.empty:
                for _, la in logs_ayer.iterrows():
                    conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)",
                                 (st.session_state.user, hoy, la['food_desc'], la['prot'], la['carb'], la['fat'], la['kcal'], la['status'], la['meal_time']))
                conn.commit()
                st.success("✅ Comidas de ayer copiadas a hoy.")
                st.rerun()
            else:
                st.warning("No hay registros de ayer para copiar.")
        
        with st.expander("🧪 Registrar Biometría"):
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

        # --- SECCIÓN DE TIEMPOS DE COMIDA ---
        tiempos = ["Desayuno", "Almuerzo", "Cena", "Snacks"]
        
        for tiempo in tiempos:
            with st.container():
                st.markdown(f"### {tiempo}")
                
                logs_tiempo = pd.read_sql("SELECT id, food_desc, kcal FROM logs WHERE username=? AND date=? AND meal_time=?", 
                                         conn, params=(st.session_state.user, hoy, tiempo))
                
                for _, row in logs_tiempo.iterrows():
                    col_f, col_k = st.columns([4, 1])
                    col_f.markdown(f"🍳 {row['food_desc']}")
                    col_k.markdown(f"**{int(row['kcal'])} kcal**")
                
                with st.expander(f"➕ Agregar a {tiempo}"):
                    cats = pd.read_sql("SELECT DISTINCT category FROM master_food", conn)['category'].tolist()
                    c_sel = st.selectbox("Categoría:", ["Todas"] + sorted([c for c in cats if c]), key=f"cat_{tiempo}")
                    
                    alims_query = "SELECT * FROM master_food" if c_sel == "Todas" else "SELECT * FROM master_food WHERE category=?"
                    params_alims = (c_sel,) if c_sel != "Todas" else None
                    df_alims = pd.read_sql(alims_query, conn, params=params_alims)
                    
                    a_sel = st.selectbox("Alimento:", [""] + sorted(df_alims['food_name'].tolist()) + ["➕ OTRO"], key=f"alim_{tiempo}")
                    gramos = st.number_input("Gramos:", min_value=0.0, value=100.0, step=10.0, key=f"gramos_{tiempo}")
                    
                    if a_sel != "" and a_sel != "➕ OTRO":
                        datos_f = df_alims[df_alims['food_name'] == a_sel].iloc[0]
                        factor = gramos / 100
                        pv_p, pv_c, pv_g, pv_k = datos_f['p100']*factor, datos_f['c100']*factor, datos_f['g100']*factor, datos_f['k100']*factor
                        
                        st.markdown(f"""
                        <div style="background-color: #262730; padding: 12px; border-radius: 8px; border-left: 4px solid #00ffcc; margin-top: 10px;">
                            <p style="margin:0; font-size: 0.85em; color: #888;">📊 Macros para {int(gramos)}g:</p>
                            <span style="color: #ff4b4b; font-weight: bold;">P: {pv_p:.1f}g</span> | 
                            <span style="color: #4ba3ff; font-weight: bold;">C: {pv_c:.1f}g</span> | 
                            <span style="color: #ffca4b; font-weight: bold;">G: {pv_g:.1f}g</span> | 
                            <span style="color: #ffffff; font-weight: bold;">Kcal: {int(pv_k)}</span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    elif a_sel == "➕ OTRO":
                        st.info("💡 Al registrar un alimento nuevo, el Coach Erick asignará los macros pronto.")

                    food_f = ""
                    if a_sel == "➕ OTRO": 
                        food_f = st.text_input("Nombre del alimento:", key=f"text_{tiempo}").strip()
                    elif a_sel != "":
                        food_f = a_sel

                    if st.button("Registrar", key=f"btn_{tiempo}"):
                        if food_f != "":
                            match = pd.read_sql("SELECT * FROM master_food WHERE LOWER(food_name) = ?", conn, params=(food_f.lower(),))
                            if not match.empty:
                                f = match.iloc[0]; fac = gramos/100
                                conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)", 
                                            (st.session_state.user, hoy, f"{int(gramos)}g {f['food_name']}", f['p100']*fac, f['c100']*fac, f['g100']*fac, f['k100']*fac, 'Validado', tiempo))
                            else:
                                conn.execute("INSERT INTO logs (username, date, food_desc, prot, carb, fat, kcal, status, meal_time) VALUES (?,?,?,?,?,?,?,?,?)", 
                                            (st.session_state.user, hoy, f"{int(gramos)}g {food_f}", 0, 0, 0, 0, 'Pendiente', tiempo))
                            conn.commit(); st.rerun()
                st.markdown("---")

        st.subheader("📋 Resumen del Día")
        tabla_hoy = pd.read_sql("SELECT id, food_desc as Plato, meal_time as Momento, round(kcal,0) as Kcal, status as Estado FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
        
        if not tabla_hoy.empty:
            st.dataframe(tabla_hoy.drop(columns=['id']), use_container_width=True, hide_index=True)
            id_para_borrar = st.selectbox("Selecciona para borrar:", tabla_hoy['id'].tolist(), 
                                           format_func=lambda x: f"{tabla_hoy[tabla_hoy['id']==x]['Momento'].values[0]}: {tabla_hoy[tabla_hoy['id']==x]['Plato'].values[0]}")
            if st.button("🗑️ Borrar Alimento"):
                conn.execute("DELETE FROM logs WHERE id=?", (id_para_borrar,))
                conn.commit(); st.warning("Registro eliminado."); st.rerun()

        if st.session_state.admin:
            with st.expander("🛠️ Panel de Edición de Registros (Solo Coach)"):
                logs_hoy = pd.read_sql("SELECT id, food_desc FROM logs WHERE username=? AND date=?", conn, params=(st.session_state.user, hoy))
                if not logs_hoy.empty:
                    id_edit = st.selectbox("ID del registro a corregir:", logs_hoy['id'].tolist(), format_func=lambda x: logs_hoy[logs_hoy['id']==x]['food_desc'].values[0], key="coach_edit_select")
                    log_data = pd.read_sql("SELECT * FROM logs WHERE id=?", conn, params=(id_edit,)).iloc[0]
                    with st.form("coach_edit_form"):
                        e_desc = st.text_input("Descripción", value=log_data['food_desc'])
                        c_e1, c_e2, c_e3, c_e4 = st.columns(4)
                        e_p = c_e1.number_input("P (g)", value=float(log_data['prot']))
                        e_c = c_e2.number_input("C (g)", value=float(log_data['carb']))
                        e_g = c_e3.number_input("G (g)", value=float(log_data['fat']))
                        e_k = c_e4.number_input("Kcal", value=float(log_data['kcal']))
                        if st.form_submit_button("💾 Guardar Corrección"):
                            conn.execute("UPDATE logs SET food_desc=?, prot=?, carb=?, fat=?, kcal=?, status='Validado' WHERE id=?", (e_desc, e_p, e_c, e_g, e_k, id_edit))
                            conn.commit(); st.success("Registro corregido."); st.rerun()
        conn.close()

    elif menu == "Historial": mostrar_historial(st.session_state.user)
    
    elif menu == "Maestro de Alimentos":
        st.header("📂 Base de Alimentos")
        
        # --- FUNCIÓN NUEVA: BUSCADOR DINÁMICO ---
        search_term = st.text_input("🔍 Buscar alimento por nombre:", "").lower()
        
        with st.expander("📥 Importar desde Excel"):
            archivo = st.file_uploader("Sube tu Excel (.xlsx)", type=["xlsx"])
            if archivo and st.button("🚀 Importar Base"):
                df = pd.read_excel(archivo); df.columns = [c.lower().strip() for c in df.columns]
                conn = sqlite3.connect(DB_PATH)
                for _, r in df.iterrows():
                    p, c, g = float(r['proteina']), float(r['carbos']), float(r['grasas'])
                    conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (str(r['nombre']).strip(), p, c, g, (p*4+c*4+g*9), str(r['categoria']).capitalize()))
                conn.commit(); conn.close(); st.success("Base actualizada.")
        
        st.divider()
        st.subheader("➕ Agregar Nuevo Alimento")
        with st.form("add_new_food_form"):
            new_nombre = st.text_input("Nombre del Alimento (Sin números)")
            new_cat = st.text_input("Categoría")
            c1, c2, c3, c4 = st.columns(4)
            new_p = c1.number_input("P/100g", 0.0)
            new_c = c2.number_input("C/100g", 0.0)
            new_g = c3.number_input("G/100g", 0.0)
            new_k = c4.number_input("Kcal/100g (Manual)", 0.0)
            if st.form_submit_button("⭐ Registrar Alimento"):
                if new_nombre.strip() == "": st.error("El nombre es obligatorio.")
                elif validar_solo_letras(new_nombre):
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (new_nombre.strip(), new_p, new_c, new_g, new_k, new_cat.strip().capitalize()))
                    conn.commit(); conn.close(); st.success("Agregado."); st.rerun()

        st.divider()
        conn = sqlite3.connect(DB_PATH)
        # Filtro de búsqueda aplicado al dataframe
        base_actual = pd.read_sql("SELECT food_name as Alimento, category as Categoría, p100 as Prot, c100 as Carb, g100 as Fat, k100 as Kcal FROM master_food", conn)
        if search_term:
            base_actual = base_actual[base_actual['Alimento'].str.lower().str.contains(search_term)]
        
        st.dataframe(base_actual, use_container_width=True, hide_index=True)
        
        st.subheader("✏️ Editar Macros Maestros")
        alim_a_editar = st.selectbox("Selecciona alimento para editar:", [""] + base_actual['Alimento'].tolist())
        if alim_a_editar:
            datos_alim = pd.read_sql("SELECT * FROM master_food WHERE food_name=?", conn, params=(alim_a_editar,)).iloc[0]
            with st.form("edit_macros_form"):
                ed_nombre = st.text_input("Nombre (Sin números)", value=datos_alim['food_name'])
                ed_cat = st.text_input("Categoría", value=datos_alim['category'])
                c1, c2, c3, c4 = st.columns(4)
                ed_p = c1.number_input("P/100g", value=float(datos_alim['p100']))
                ed_c = c2.number_input("C/100g", value=float(datos_alim['c100']))
                ed_g = c3.number_input("G/100g", value=float(datos_alim['g100']))
                ed_k = c4.number_input("Kcal/100g (Manual)", value=float(datos_alim['k100']))
                if st.form_submit_button("💾 Guardar"):
                    if validar_solo_letras(ed_nombre):
                        if ed_nombre != datos_alim['food_name']: conn.execute("DELETE FROM master_food WHERE food_name=?", (datos_alim['food_name'],))
                        conn.execute("INSERT OR REPLACE INTO master_food VALUES (?,?,?,?,?,?)", (ed_nombre.strip(), ed_p, ed_c, ed_g, ed_k, ed_cat.strip().capitalize()))
                        conn.commit(); st.rerun()
        conn.close()

    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.query_params.clear()
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
