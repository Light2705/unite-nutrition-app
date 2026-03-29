import streamlit as st
import pandas as pd
from st_gsheets_connection import GSheetsConnection
import os
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE CONEXIÓN (NUEVO) ---
# Esto reemplaza a SQLite para que funcione en la nube sin errores
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(worksheet_name):
    return conn.read(worksheet=worksheet_name)

def save_data(df, worksheet_name):
    conn.update(worksheet=worksheet_name, data=df)
    st.cache_data.clear()

# --- LÓGICA DE PERSISTENCIA ---
if 'user' not in st.session_state:
    params = st.query_params
    if "user" in params:
        u_url = params["user"]
        res = get_data("users")
        res = res[res['username'] == u_url]
        if not res.empty:
            vencimiento = datetime.strptime(str(res.iloc[0]['expiry_date']), '%Y-%m-%d')
            if datetime.now() <= vencimiento:
                st.session_state.user = res.iloc[0]['username']
                st.session_state.admin = int(res.iloc[0]['is_admin'])

# --- LOGIN / REGISTRO ---
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
    if st.session_state.admin: opciones = ["Gestión de Clientes", "Maestro de Alimentos", "Mi Diario", "Historial"]
    menu = st.sidebar.radio("Navegación", opciones)

    def mostrar_historial(usuario):
        st.subheader(f"📅 Últimos 7 días registrados: {usuario}")
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
            st.info("No hay registros en la última semana.")

    # --- GESTIÓN DE CLIENTES ---
    if st.session_state.admin and menu == "Gestión de Clientes":
        st.header("👥 Control de Alumnos")
        hoy = datetime.now().strftime('%Y-%m-%d')
        df_logs = get_data("logs")
        pendientes = df_logs[df_logs['status'] == 'Pendiente']
        
        if not pendientes.empty:
            st.subheader("🔔 Alimentos Pendientes")
            for idx, r in pendientes.iterrows():
                with st.expander(f"🔴 {r['username']} - {r['food_desc']}"):
                    c1, c2, c3 = st.columns(3)
                    p_val = c1.number_input("Prot (100g)", 0.0, key=f"p_val_{idx}")
                    c_val = c2.number_input("Carb (100g)", 0.0, key=f"c_val_{idx}")
                    g_val = c3.number_input("Fat (100g)", 0.0, key=f"g_val_{idx}")
                    if st.button("Validar", key=f"v_btn_{idx}"):
                        try: gramos_atleta = float(r['food_desc'].split('g')[0])
                        except: gramos_atleta = 100.0
                        factor = gramos_atleta / 100
                        k_calc = (p_val*4 + c_val*4 + g_val*9) * factor
                        
                        df_logs.at[idx, 'prot'] = p_val*factor
                        df_logs.at[idx, 'carb'] = c_val*factor
                        df_logs.at[idx, 'fat'] = g_val*factor
                        df_logs.at[idx, 'kcal'] = k_calc
                        df_logs.at[idx, 'status'] = 'Validado'
                        save_data(df_logs, "logs")
                        st.rerun()

        st.divider()
        df_users = get_data("users")
        usuarios_lista = df_users[df_users['is_admin'] == 0][['username', 'expiry_date']]
        st.dataframe(usuarios_lista, use_container_width=True)
        
        sel_atleta = st.selectbox("Selecciona un alumno:", [""] + usuarios_lista['username'].tolist())
        if sel_atleta:
            m = df_users[df_users['username'] == sel_atleta].iloc[0]
            t_hoy, t_hist, t_cfg = st.tabs(["📊 Hoy", "📅 Últimos 7 Días", "⚙️ Plan"])
            
            with t_hoy:
                df_logs = get_data("logs")
                cons = df_logs[(df_logs['username'] == sel_atleta) & (df_logs['date'] == hoy)]
                p, c, g, k = cons['prot'].sum(), cons['carb'].sum(), cons['fat'].sum(), cons['kcal'].sum()
                cols = st.columns(4)
                cols[0].metric("P", f"{p:.1f}g", f"/{m['target_prot']}g")
                cols[1].metric("C", f"{c:.1f}g", f"/{m['target_carb']}g")
                cols[2].metric("G", f"{g:.1f}g", f"/{m['target_fat']}g")
                cols[3].metric("Kcal", f"{int(k)}", f"/{int(m['target_kcal'])}")

            with t_hist: mostrar_historial(sel_atleta)

            with t_cfg:
                dias = st.number_input("Días extra de acceso:", 0, 30)
                nueva_f = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d')
                p_o = st.number_input("P Meta", value=float(m['target_prot']))
                c_o = st.number_input("C Meta", value=float(m['target_carb']))
                g_o = st.number_input("G Meta", value=float(m['target_fat']))
                k_o = st.number_input("Kcal Meta", value=float(m['target_kcal']))
                if st.button("💾 Actualizar Plan"):
                    idx_u = df_users[df_users['username'] == sel_atleta].index[0]
                    df_users.at[idx_u, 'expiry_date'] = nueva_f
                    df_users.at[idx_u, 'target_prot'] = p_o
                    df_users.at[idx_u, 'target_carb'] = c_o
                    df_users.at[idx_u, 'target_fat'] = g_o
                    df_users.at[idx_u, 'target_kcal'] = k_o
                    save_data(df_users, "users")
                    st.success("Plan actualizado.")
                    st.rerun()

    # --- MI DIARIO ---
    elif menu == "Mi Diario":
        df_users = get_data("users")
        m = df_users[df_users['username'] == st.session_state.user].iloc[0]
        hoy_dt = datetime.now()
        hoy = hoy_dt.strftime('%Y-%m-%d')
        
        st.header(f"📓 Diario: {st.session_state.user}")
        df_logs = get_data("logs")
        cons = df_logs[(df_logs['username'] == st.session_state.user) & (df_logs['date'] == hoy)]
        p, c, g, k = cons['prot'].sum(), cons['carb'].sum(), cons['fat'].sum(), cons['kcal'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Proteína", f"{p:.1f}g", f"Meta: {m['target_prot']}g")
        c2.metric("Carbos", f"{c:.1f}g", f"Meta: {m['target_carb']}g")
        c3.metric("Grasas", f"{g:.1f}g", f"Meta: {m['target_fat']}g")
        c4.metric("Kcal", f"{int(k)}", f"Meta: {int(m['target_kcal'])}")
        
        st.divider()
        df_master = get_data("master_food")
        cats = sorted(df_master['category'].unique().tolist())
        c_sel = st.selectbox("Categoría:", ["Todas"] + cats)
        
        df_filtered = df_master if c_sel == "Todas" else df_master[df_master['category'] == c_sel]
        alims = sorted(df_filtered['food_name'].tolist())
        a_sel = st.selectbox("Alimento:", [""] + alims + ["➕ OTRO"])

        gramos = st.number_input("Gramos (pesado):", min_value=1.0, value=100.0)
        
        if st.button("✅ Registrar") and a_sel != "":
            if a_sel == "➕ OTRO":
                food_f = "Pendiente" # Lógica simplificada para otro
                new_row = {"username": st.session_state.user, "date": hoy, "food_desc": f"{int(gramos)}g OTRO", "prot": 0, "carb": 0, "fat": 0, "kcal": 0, "status": "Pendiente"}
            else:
                f = df_master[df_master['food_name'] == a_sel].iloc[0]
                fac = gramos/100
                new_row = {"username": st.session_state.user, "date": hoy, "food_desc": f"{int(gramos)}g {a_sel}", "prot": f['p100']*fac, "carb": f['c100']*fac, "fat": f['g100']*fac, "kcal": f['k100']*fac, "status": "Validado"}
            
            updated_logs = pd.concat([df_logs, pd.DataFrame([new_row])], ignore_index=True)
            save_data(updated_logs, "logs")
            st.rerun()

        st.subheader("Consumo de hoy")
        st.dataframe(cons[['food_desc', 'prot', 'carb', 'fat', 'kcal']], use_container_width=True, hide_index=True)

    # --- HISTORIAL ---
    elif menu == "Historial":
        mostrar_historial(st.session_state.user)

    # --- MAESTRO DE ALIMENTOS ---
    elif menu == "Maestro de Alimentos":
        st.header("📂 Base de Alimentos")
        archivo = st.file_uploader("Sube tu Excel (.xlsx)", type=["xlsx"])
        if archivo and st.button("🚀 Importar"):
            df_new = pd.read_excel(archivo)
            df_new.columns = [c.lower().strip() for c in df_new.columns]
            # Formatear para GSheets
            df_gsheet = pd.DataFrame({
                "food_name": df_new['nombre'], "p100": df_new['proteina'], 
                "c100": df_new['carbos'], "g100": df_new['grasas'],
                "k100": df_new['proteina']*4 + df_new['carbos']*4 + df_new['grasas']*9,
                "category": df_new['categoria']
            })
            save_data(df_gsheet, "master_food")
            st.success("Base actualizada.")

    if st.sidebar.button("Cerrar Sesión"):
        st.query_params.clear()
        if 'user' in st.session_state: del st.session_state.user
        st.rerun()
