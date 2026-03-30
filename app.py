import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Unite Nutrition - Erick Quiroz", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
# Forzamos la obtención de la URL para evitar errores de conexión
try:
    if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
        url_sheet = st.secrets["connections"]["gsheets"]["spreadsheet"]
    else:
        st.error("Faltan los Secrets de Google Sheets en Streamlit Cloud.")
        st.stop()

    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Error configurando la conexión: {e}")
    st.stop()

# --- FUNCIONES DE DATOS ---
def get_data(worksheet_name):
    # Forzamos que la URL termine en /export?format=csv
    # Esto elimina cualquier error de "Bad Request" (400)
    base_url = url_sheet.split('/edit')[0] # Limpiamos el final
    clean_url = f"{base_url}/export?format=csv"
    
    return conn.read(spreadsheet=clean_url, worksheet=worksheet_name)

# --- LÓGICA DE PERSISTENCIA ---
if 'user' not in st.session_state:
    params = st.query_params
    if "user" in params:
        u_url = params["user"]
        try:
            res = get_data("users")
            res = res[res['username'] == u_url]
            if not res.empty:
                vencimiento = datetime.strptime(str(res.iloc[0]['expiry_date']), '%Y-%m-%d')
                if datetime.now() <= vencimiento:
                    st.session_state.user = res.iloc[0]['username']
                    st.session_state.admin = int(res.iloc[0]['is_admin'])
        except:
            pass

# --- LOGIN / REGISTRO ---
if 'user' not in st.session_state:
    st.title("🏋️ Unite Nutrition - Erick Quiroz")
    tab_login, tab_reg = st.tabs(["🔑 Iniciar Sesión", "📝 Registro de Atleta"])
    
    with tab_login:
        u = st.text_input("Usuario", key="login_u")
        p = st.text_input("Contraseña", type="password", key="login_p")
        if st.button("Entrar"):
            try:
                df_users = get_data("users")
                res = df_users[(df_users['username'] == u) & (df_users['password'] == p)]
                if not res.empty:
                    vencimiento = datetime.strptime(str(res.iloc[0]['expiry_date']), '%Y-%m-%d')
                    if datetime.now() <= vencimiento:
                        st.session_state.user = u
                        st.session_state.admin = int(res.iloc[0]['is_admin'])
                        st.query_params["user"] = u
                        st.rerun()
                    else:
                        st.error("⚠️ Acceso vencido o pendiente de activación.")
                else:
                    st.error("Credenciales incorrectas.")
            except Exception as e:
                st.error(f"Error al conectar con la base de datos: {e}")

    with tab_reg:
        nu = st.text_input("Nuevo Usuario", key="reg_u")
        np = st.text_input("Nueva Contraseña", type="password", key="reg_p")
        if st.button("Crear Cuenta"):
            df_users = get_data("users")
            if nu in df_users['username'].values:
                st.error("El usuario ya existe.")
            else:
                venc_bloqueado = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                nuevo_usuario = pd.DataFrame([{
                    "username": nu, "password": np, "is_admin": 0, 
                    "target_prot": 0, "target_carb": 0, "target_fat": 0, 
                    "target_kcal": 0, "expiry_date": venc_bloqueado
                }])
                updated_users = pd.concat([df_users, nuevo_usuario], ignore_index=True)
                save_data(updated_users, "users")
                st.success("✅ ¡Registro exitoso! Avisa al Coach Erick.")

else:
    # --- BARRA LATERAL ---
    st.sidebar.title(f"🚀 {'Coach' if st.session_state.admin else 'Atleta'}")
    st.sidebar.write(f"Usuario: **{st.session_state.user}**")
    
    if st.sidebar.button("🔄 Actualizar Datos"):
        st.rerun()

    opciones = ["Mi Diario", "Historial"]
    if st.session_state.admin: 
        opciones = ["Gestión de Clientes", "Maestro de Alimentos", "Mi Diario", "Historial"]
    menu = st.sidebar.radio("Navegación", opciones)

    def mostrar_historial(usuario):
        st.subheader(f"📅 Últimos 7 días: {usuario}")
        df_logs = get_data("logs")
        df = df_logs[df_logs['username'] == usuario].copy()
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            res_hist = df.groupby('date').agg({
                'prot': 'sum', 'carb': 'sum', 'fat': 'sum', 'kcal': 'sum'
            }).reset_index().sort_values('date', ascending=False).head(7)
            
            dias_es = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
                       'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
            
            res_hist.insert(0, "Día", res_hist['date'].dt.day_name().map(dias_es))
            res_hist['date'] = res_hist['date'].dt.strftime('%d/%m')
            st.dataframe(res_hist, use_container_width=True, hide_index=True)
        else:
            st.info("No hay registros previos.")

    # --- LÓGICA DE MENÚS (Gestión, Diario, Maestro) ---
    if st.session_state.admin and menu == "Gestión de Clientes":
        st.header("👥 Control de Alumnos")
        hoy = datetime.now().strftime('%Y-%m-%d')
        df_logs = get_data("logs")
        pendientes = df_logs[df_logs['status'] == 'Pendiente']
        
        if not pendientes.empty:
            st.subheader("🔔 Alimentos por Validar")
            for idx, r in pendientes.iterrows():
                with st.expander(f"🔴 {r['username']} - {r['food_desc']}"):
                    c1, c2, c3 = st.columns(3)
                    p_val = c1.number_input("Prot (100g)", 0.0, key=f"p_{idx}")
                    c_val = c2.number_input("Carb (100g)", 0.0, key=f"c_{idx}")
                    g_val = c3.number_input("Fat (100g)", 0.0, key=f"g_{idx}")
                    if st.button("Validar", key=f"v_{idx}"):
                        try: gramos_atleta = float(r['food_desc'].split('g')[0])
                        except: gramos_atleta = 100.0
                        factor = gramos_atleta / 100
                        df_logs.at[idx, 'prot'] = p_val*factor
                        df_logs.at[idx, 'carb'] = c_val*factor
                        df_logs.at[idx, 'fat'] = g_val*factor
                        df_logs.at[idx, 'kcal'] = (p_val*4 + c_val*4 + g_val*9) * factor
                        df_logs.at[idx, 'status'] = 'Validado'
                        save_data(df_logs, "logs")
                        st.rerun()

        st.divider()
        df_users = get_data("users")
        usuarios_lista = df_users[df_users['is_admin'] == 0]
        st.dataframe(usuarios_lista[['username', 'expiry_date']], use_container_width=True)
        
        sel_atleta = st.selectbox("Seleccionar Alumno:", [""] + usuarios_lista['username'].tolist())
        if sel_atleta:
            m = df_users[df_users['username'] == sel_atleta].iloc[0]
            t_hoy, t_hist, t_cfg = st.tabs(["📊 Hoy", "📅 Historial", "⚙️ Plan"])
            with t_hoy:
                cons = get_data("logs")
                cons = cons[(cons['username'] == sel_atleta) & (cons['date'] == hoy)]
                st.metric("Kcal Hoy", f"{int(cons['kcal'].sum())}", f"Meta: {m['target_kcal']}")
            with t_hist: mostrar_historial(sel_atleta)
            with t_cfg:
                dias = st.number_input("Días extra de acceso:", 0, 30)
                if st.button("💾 Guardar Cambios"):
                    idx_u = df_users[df_users['username'] == sel_atleta].index[0]
                    df_users.at[idx_u, 'expiry_date'] = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d')
                    save_data(df_users, "users")
                    st.rerun()

    elif menu == "Mi Diario":
        df_users = get_data("users")
        m = df_users[df_users['username'] == st.session_state.user].iloc[0]
        hoy = datetime.now().strftime('%Y-%m-%d')
        
        st.header(f"📓 Diario: {st.session_state.user}")
        df_logs = get_data("logs")
        cons = df_logs[(df_logs['username'] == st.session_state.user) & (df_logs['date'] == hoy)]
        
        cols = st.columns(4)
        cols[0].metric("Prot", f"{cons['prot'].sum():.1f}g", f"/{m['target_prot']}g")
        cols[1].metric("Carb", f"{cons['carb'].sum():.1f}g", f"/{m['target_carb']}g")
        cols[2].metric("Fat", f"{cons['fat'].sum():.1f}g", f"/{m['target_fat']}g")
        cols[3].metric("Kcal", f"{int(cons['kcal'].sum())}", f"/{int(m['target_kcal'])}")
        
        st.divider()
        df_master = get_data("master_food")
        a_sel = st.selectbox("Alimento:", [""] + sorted(df_master['food_name'].tolist()) + ["➕ OTRO"])
        gramos = st.number_input("Gramos:", 1.0, 1000.0, 100.0)
        
        if st.button("✅ Registrar"):
            if a_sel == "➕ OTRO":
                row = {"username": st.session_state.user, "date": hoy, "food_desc": f"{int(gramos)}g OTRO", "prot": 0, "carb": 0, "fat": 0, "kcal": 0, "status": "Pendiente"}
            else:
                f = df_master[df_master['food_name'] == a_sel].iloc[0]
                fac = gramos/100
                row = {"username": st.session_state.user, "date": hoy, "food_desc": f"{int(gramos)}g {a_sel}", "prot": f['p100']*fac, "carb": f['c100']*fac, "fat": f['g100']*fac, "kcal": f['k100']*fac, "status": "Validado"}
            save_data(pd.concat([df_logs, pd.DataFrame([row])], ignore_index=True), "logs")
            st.rerun()

    elif menu == "Historial":
        mostrar_historial(st.session_state.user)

    elif menu == "Maestro de Alimentos":
        st.header("📂 Base de Alimentos")
        archivo = st.file_uploader("Sube Excel", type=["xlsx"])
        if archivo and st.button("🚀 Actualizar"):
            df_new = pd.read_excel(archivo)
            df_new.columns = [c.lower().strip() for c in df_new.columns]
            save_data(df_new, "master_food")
            st.success("Base de datos actualizada.")

    if st.sidebar.button("Cerrar Sesión"):
        st.query_params.clear()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
