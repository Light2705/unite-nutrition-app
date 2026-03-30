import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Unite Nutrition - Erick Quiroz", layout="wide")

# --- CONEXIÓN Y FUNCIONES DE DATOS ---
# Usamos el motor de GSheetsConnection para lectura y escritura
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("⚠️ Error de conexión. Verifica los Secrets en Streamlit.")
    st.stop()

def get_data(worksheet_name):
    # Forzamos la lectura fresca de los datos
    return conn.read(worksheet=worksheet_name, ttl=0)

def save_data(df, worksheet_name):
    try:
        conn.update(worksheet=worksheet_name, data=df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error al guardar en {worksheet_name}: {e}")

# --- LÓGICA DE PERSISTENCIA POR URL ---
if 'user' not in st.session_state:
    params = st.query_params
    if "user" in params:
        u_url = params["user"]
        df_users = get_data("users")
        res = df_users[df_users['username'] == u_url]
        if not res.empty:
            venc = datetime.strptime(str(res.iloc[0]['expiry_date']), '%Y-%m-%d')
            if datetime.now() <= venc:
                st.session_state.user = res.iloc[0]['username']
                st.session_state.admin = int(res.iloc[0]['is_admin'])

# --- PANTALLA DE LOGIN / REGISTRO ---
if 'user' not in st.session_state:
    st.title("🏋️ Unite Nutrition - Erick Quiroz")
    tab_login, tab_reg = st.tabs(["🔑 Iniciar Sesión", "📝 Registro de Atleta"])
    
    with tab_login:
        u = st.text_input("Usuario", key="login_u")
        p = st.text_input("Contraseña", type="password", key="login_p")
        if st.button("Entrar"):
            df_users = get_data("users")
            res = df_users[(df_users['username'] == u) & (df_users['password'] == p)]
            if not res.empty:
                venc = datetime.strptime(str(res.iloc[0]['expiry_date']), '%Y-%m-%d')
                if datetime.now() <= venc:
                    st.session_state.user = u
                    st.session_state.admin = int(res.iloc[0]['is_admin'])
                    st.query_params["user"] = u
                    st.rerun()
                else:
                    st.error("⚠️ Acceso vencido. Contacta al Coach Erick.")
            else:
                st.error("Credenciales incorrectas.")

    with tab_reg:
        nu = st.text_input("Nuevo Usuario", key="reg_u")
        np = st.text_input("Contraseña", type="password", key="reg_p")
        if st.button("Crear Cuenta"):
            df_users = get_data("users")
            if nu in df_users['username'].values:
                st.error("El usuario ya existe.")
            else:
                # Se registra bloqueado por defecto (fecha ayer)
                venc_bloqueado = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                nuevo = pd.DataFrame([{
                    "username": nu, "password": np, "is_admin": 0, 
                    "target_prot": 0, "target_carb": 0, "target_fat": 0, 
                    "target_kcal": 0, "expiry_date": venc_bloqueado
                }])
                save_data(pd.concat([df_users, nuevo], ignore_index=True), "users")
                st.success("✅ Registro exitoso. Avisa al Coach para tu activación.")

# --- APP PRINCIPAL ---
else:
    st.sidebar.title(f"🚀 {'Coach' if st.session_state.admin else 'Atleta'}")
    st.sidebar.write(f"Usuario: **{st.session_state.user}**")
    
    if st.sidebar.button("🔄 Sincronizar"):
        st.rerun()

    opciones = ["Mi Diario", "Historial"]
    if st.session_state.admin: 
        opciones = ["Gestión de Clientes", "Maestro de Alimentos", "Mi Diario", "Historial"]
    menu = st.sidebar.radio("Navegación", opciones)

    # --- FUNCIÓN HISTORIAL REUTILIZABLE ---
    def mostrar_historial(usuario):
        st.subheader(f"📅 Últimos 7 días: {usuario}")
        df_logs = get_data("logs")
        df = df_logs[df_logs['username'] == usuario].copy()
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            res_hist = df.groupby('date').agg({'prot': 'sum', 'carb': 'sum', 'fat': 'sum', 'kcal': 'sum'}).reset_index().sort_values('date', ascending=False).head(7)
            
            dias_es = {'Monday': 'Lun', 'Tuesday': 'Mar', 'Wednesday': 'Mie', 'Thursday': 'Jue', 'Friday': 'Vie', 'Saturday': 'Sab', 'Sunday': 'Dom'}
            res_hist.insert(0, "Día", res_hist['date'].dt.day_name().map(dias_es))
            res_hist['date'] = res_hist['date'].dt.strftime('%d/%m')
            st.dataframe(res_hist, use_container_width=True, hide_index=True)
        else:
            st.info("Sin registros recientes.")

    # --- MÓDULO: GESTIÓN DE CLIENTES ---
    if menu == "Gestión de Clientes" and st.session_state.admin:
        st.header("👥 Control de Alumnos")
        hoy = datetime.now().strftime('%Y-%m-%d')
        df_logs = get_data("logs")
        
        # 1. Validación de alimentos "OTRO"
        pendientes = df_logs[df_logs['status'] == 'Pendiente']
        if not pendientes.empty:
            st.subheader("🔔 Por Validar")
            for idx, r in pendientes.iterrows():
                with st.expander(f"🔴 {r['username']} - {r['food_desc']}"):
                    c1, c2, c3 = st.columns(3)
                    p_v = c1.number_input("P/100g", 0.0, key=f"pv_{idx}")
                    c_v = c2.number_input("C/100g", 0.0, key=f"cv_{idx}")
                    g_v = c3.number_input("G/100g", 0.0, key=f"gv_{idx}")
                    if st.button("Validar", key=f"btnv_{idx}"):
                        try: gramos = float(r['food_desc'].split('g')[0])
                        except: gramos = 100
                        fac = gramos/100
                        df_logs.at[idx, 'prot'], df_logs.at[idx, 'carb'], df_logs.at[idx, 'fat'] = p_v*fac, c_v*fac, g_v*fac
                        df_logs.at[idx, 'kcal'] = (p_v*4 + c_v*4 + g_v*9)*fac
                        df_logs.at[idx, 'status'] = 'Validado'
                        save_data(df_logs, "logs")
                        st.rerun()

        st.divider()
        df_users = get_data("users")
        usuarios_atle = df_users[df_users['is_admin'] == 0]
        sel_atleta = st.selectbox("Seleccionar Alumno", [""] + usuarios_atle['username'].tolist())
        
        if sel_atleta:
            m = usuarios_atle[usuarios_atle['username'] == sel_atleta].iloc[0]
            t_hoy, t_hist, t_plan = st.tabs(["📊 Hoy", "📅 Historial", "⚙️ Configurar Plan"])
            
            with t_hoy:
                cons = df_logs[(df_logs['username'] == sel_atleta) & (df_logs['date'] == hoy)]
                cols = st.columns(4)
                cols[0].metric("Prot", f"{cons['prot'].sum():.1f}g", f"/{m['target_prot']}g")
                cols[1].metric("Carb", f"{cons['carb'].sum():.1f}g", f"/{m['target_carb']}g")
                cols[2].metric("Fat", f"{cons['fat'].sum():.1f}g", f"/{m['target_fat']}g")
                cols[3].metric("Kcal", f"{int(cons['kcal'].sum())}", f"/{int(m['target_kcal'])}")
                st.dataframe(cons[['food_desc', 'kcal', 'status']], use_container_width=True)

            with t_hist:
                mostrar_historial(sel_atleta)

            with t_plan:
                st.write(f"Vence: {m['expiry_date']}")
                dias_add = st.number_input("Días de acceso desde hoy:", 0, 90, 30)
                new_date = (datetime.now() + timedelta(days=dias_add)).strftime('%Y-%m-%d')
                p_m = st.number_input("Meta Proteína", value=float(m['target_prot']))
                c_m = st.number_input("Meta Carbos", value=float(m['target_carb']))
                g_m = st.number_input("Meta Grasas", value=float(m['target_fat']))
                k_m = st.number_input("Meta Kcal", value=float(m['target_kcal']))
                
                if st.button("Guardar Cambios"):
                    idx_u = df_users[df_users['username'] == sel_atleta].index[0]
                    df_users.at[idx_u, 'expiry_date'] = new_date
                    df_users.at[idx_u, 'target_prot'], df_users.at[idx_u, 'target_carb'] = p_m, c_m
                    df_users.at[idx_u, 'target_fat'], df_users.at[idx_u, 'target_kcal'] = g_m, k_m
                    save_data(df_users, "users")
                    st.success("Plan Actualizado")
                    st.rerun()

    # --- MÓDULO: MI DIARIO ---
    elif menu == "Mi Diario":
        df_users = get_data("users")
        m = df_users[df_users['username'] == st.session_state.user].iloc[0]
        hoy = datetime.now().strftime('%Y-%m-%d')
        
        st.header(f"📓 Diario: {st.session_state.user}")
        df_logs = get_data("logs")
        cons = df_logs[(df_logs['username'] == st.session_state.user) & (df_logs['date'] == hoy)]
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Proteína", f"{cons['prot'].sum():.1f}g", f"/{m['target_prot']}g")
        c2.metric("Carbos", f"{cons['carb'].sum():.1f}g", f"/{m['target_carb']}g")
        c3.metric("Grasas", f"{cons['fat'].sum():.1f}g", f"/{m['target_fat']}g")
        c4.metric("Kcal", f"{int(cons['kcal'].sum())}", f"/{int(m['target_kcal'])}")

        st.divider()
        df_master = get_data("master_food")
        
        col_cat, col_alim = st.columns(2)
        with col_cat:
            cats = ["Todas"] + sorted(df_master['category'].unique().tolist())
            c_sel = st.selectbox("Filtrar por Categoría:", cats)
        
        with col_alim:
            df_fil = df_master if c_sel == "Todas" else df_master[df_master['category'] == c_sel]
            a_sel = st.selectbox("Selecciona Alimento:", [""] + sorted(df_fil['food_name'].tolist()) + ["➕ OTRO (No listado)"])

        gramos = st.number_input("Cantidad en Gramos:", 1.0, 2000.0, 100.0)
        
        if st.button("✅ Registrar Alimento"):
            if a_sel == "➕ OTRO (No listado)":
                new = {"username": st.session_state.user, "date": hoy, "food_desc": f"{int(gramos)}g OTRO", "prot": 0, "carb": 0, "fat": 0, "kcal": 0, "status": "Pendiente"}
                st.warning("⚠️ El coach deberá validar los macros de este alimento.")
            elif a_sel != "":
                f = df_master[df_master['food_name'] == a_sel].iloc[0]
                fac = gramos/100
                new = {"username": st.session_state.user, "date": hoy, "food_desc": f"{int(gramos)}g {a_sel}", "prot": f['p100']*fac, "carb": f['c100']*fac, "fat": f['g100']*fac, "kcal": f['k100']*fac, "status": "Validado"}
            
            if a_sel != "":
                save_data(pd.concat([df_logs, pd.DataFrame([new])], ignore_index=True), "logs")
                st.rerun()

        st.subheader("Registros de hoy")
        st.dataframe(cons[['food_desc', 'prot', 'carb', 'fat', 'kcal', 'status']], use_container_width=True, hide_index=True)

    # --- MÓDULO: HISTORIAL ---
    elif menu == "Historial":
        mostrar_historial(st.session_state.user)

    # --- MÓDULO: MAESTRO DE ALIMENTOS ---
    elif menu == "Maestro de Alimentos" and st.session_state.admin:
        st.header("📂 Base de Datos de Alimentos")
        archivo = st.file_uploader("Cargar Excel de Macros (.xlsx)", type=["xlsx"])
        if archivo and st.button("🚀 Reemplazar Base de Datos"):
            df_new = pd.read_excel(archivo)
            # Normalización de columnas para evitar errores de mayúsculas
            df_new.columns = [c.lower().strip() for c in df_new.columns]
            df_gsheet = pd.DataFrame({
                "food_name": df_new['nombre'], 
                "p100": df_new['proteina'], 
                "c100": df_new['carbos'], 
                "g100": df_new['grasas'],
                "k100": df_new['proteina']*4 + df_new['carbos']*4 + df_new['grasas']*9,
                "category": df_new['categoria']
            })
            save_data(df_gsheet, "master_food")
            st.success("✅ Maestro de alimentos actualizado correctamente.")

    # --- BOTÓN CERRAR SESIÓN ---
    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.query_params.clear()
        st.session_state.clear()
        st.rerun()
