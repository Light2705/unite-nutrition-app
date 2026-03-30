import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Unite Nutrition - Erick Quiroz", layout="wide")

# --- OBTENCIÓN DE URL Y ID (SEGURIDAD CONTRA ERROR 400) ---
try:
    if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
        url_raw = st.secrets["connections"]["gsheets"]["spreadsheet"].strip().replace('"', '')
        sheet_id = url_raw.split("/d/")[1].split("/")[0]
    else:
        st.error("⚠️ Configura el link en los Secrets de Streamlit.")
        st.stop()
except Exception as e:
    st.error(f"Error con el link del Excel: {e}")
    st.stop()

# --- FUNCIONES DE DATOS (MÉTODO DIRECTO) ---
def get_data(worksheet_name):
    # Usamos el motor de visualización de Google para bajar el CSV limpio
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={worksheet_name}"
    try:
        return pd.read_csv(csv_url)
    except:
        return pd.DataFrame()

def save_data(df, worksheet_name):
    from streamlit_gsheets import GSheetsConnection
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        conn.update(spreadsheet=url_raw, worksheet=worksheet_name, data=df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error al guardar: {e}")

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
                    st.error("⚠️ Acceso vencido.")
            else:
                st.error("Credenciales incorrectas.")

    with tab_reg:
        nu = st.text_input("Nuevo Usuario")
        np = st.text_input("Contraseña")
        if st.button("Crear Cuenta"):
            df_users = get_data("users")
            if nu in df_users['username'].values:
                st.error("El usuario ya existe.")
            else:
                venc_bloqueado = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                nuevo = pd.DataFrame([{"username": nu, "password": np, "is_admin": 0, "target_prot": 0, "target_carb": 0, "target_fat": 0, "target_kcal": 0, "expiry_date": venc_bloqueado}])
                save_data(pd.concat([df_users, nuevo], ignore_index=True), "users")
                st.success("✅ Registro exitoso. Avisa al Coach.")

# --- APP PRINCIPAL ---
else:
    st.sidebar.title(f"🚀 {'Coach' if st.session_state.admin else 'Atleta'}")
    st.sidebar.write(f"Usuario: **{st.session_state.user}**")
    
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
            res_hist['date'] = res_hist['date'].dt.strftime('%d/%m')
            st.dataframe(res_hist, use_container_width=True, hide_index=True)
        else:
            st.info("Sin registros.")

    # --- MÓDULOS ---
    if menu == "Gestión de Clientes" and st.session_state.admin:
        st.header("👥 Control de Alumnos")
        df_users = get_data("users")
        df_logs = get_data("logs")
        
        # Validación de pendientes
        pendientes = df_logs[df_logs['status'] == 'Pendiente']
        if not pendientes.empty:
            for idx, r in pendientes.iterrows():
                with st.expander(f"🔴 {r['username']} - {r['food_desc']}"):
                    c1, c2, c3 = st.columns(3)
                    p_v = c1.number_input("P/100g", 0.0, key=f"p{idx}")
                    c_v = c2.number_input("C/100g", 0.0, key=f"c{idx}")
                    g_v = c3.number_input("G/100g", 0.0, key=f"g{idx}")
                    if st.button("Validar", key=f"btn{idx}"):
                        try: gramos = float(r['food_desc'].split('g')[0])
                        except: gramos = 100
                        fac = gramos/100
                        df_logs.at[idx, 'prot'], df_logs.at[idx, 'carb'], df_logs.at[idx, 'fat'] = p_v*fac, c_v*fac, g_v*fac
                        df_logs.at[idx, 'kcal'] = (p_v*4 + c_v*4 + g_v*9)*fac
                        df_logs.at[idx, 'status'] = 'Validado'
                        save_data(df_logs, "logs")
                        st.rerun()

        st.divider()
        sel_atleta = st.selectbox("Selecciona Alumno", [""] + df_users[df_users['is_admin']==0]['username'].tolist())
        if sel_atleta:
            mostrar_historial(sel_atleta)

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
        a_sel = st.selectbox("Alimento", [""] + sorted(df_master['food_name'].tolist()) + ["➕ OTRO"])
        gramos = st.number_input("Gramos", 1.0, 1000.0, 100.0)
        
        if st.button("✅ Registrar"):
            if a_sel == "➕ OTRO":
                new = {"username": st.session_state.user, "date": hoy, "food_desc": f"{int(gramos)}g OTRO", "prot":0, "carb":0, "fat":0, "kcal":0, "status":"Pendiente"}
            else:
                f = df_master[df_master['food_name'] == a_sel].iloc[0]
                fac = gramos/100
                new = {"username": st.session_state.user, "date": hoy, "food_desc": f"{int(gramos)}g {a_sel}", "prot": f['p100']*fac, "carb": f['c100']*fac, "fat": f['g100']*fac, "kcal": f['k100']*fac, "status": "Validado"}
            save_data(pd.concat([df_logs, pd.DataFrame([new])], ignore_index=True), "logs")
            st.rerun()

    elif menu == "Historial":
        mostrar_historial(st.session_state.user)

    if st.sidebar.button("Cerrar Sesión"):
        st.query_params.clear()
        st.session_state.clear()
        st.rerun()
