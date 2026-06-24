import streamlit as st
import pandas as pd
import json
import os
import io
import base64
from github import Github, Auth, GithubException

# ============================================================
# CONFIGURACIÓN DE PÁGINA
# ============================================================
st.set_page_config(
    page_title="Admin TV Digital",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# ESTILOS CSS PREMIUM
# ============================================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* LOGIN PAGE */
    .login-container {
        max-width: 420px;
        margin: 80px auto;
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 20px;
        padding: 48px 40px;
        box-shadow: 0 25px 50px -12px rgba(0,0,0,0.6);
        text-align: center;
    }
    .login-logo {
        font-size: 64px;
        margin-bottom: 12px;
    }
    .login-title {
        font-size: 26px;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 4px;
    }
    .login-subtitle {
        font-size: 14px;
        color: #64748b;
        margin-bottom: 32px;
    }

    /* TARJETAS MÉTRICAS */
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #162032 100%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 24px 20px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        margin-bottom: 15px;
        transition: transform 0.2s ease;
    }
    .metric-card:hover { transform: translateY(-2px); }
    .metric-title {
        font-size: 12px;
        color: #64748b;
        margin-bottom: 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .metric-value {
        font-size: 34px;
        color: #38bdf8;
        font-weight: 700;
        line-height: 1;
    }
    .metric-value.green  { color: #34d399; }
    .metric-value.orange { color: #fb923c; }
    .metric-value.purple { color: #c084fc; }
    .metric-subtitle {
        font-size: 12px;
        color: #475569;
        margin-top: 6px;
    }

    /* BADGE DE ESTADO */
    .badge-pagado   { background:#065f46; color:#6ee7b7; padding:3px 10px; border-radius:99px; font-size:12px; font-weight:600; }
    .badge-pendiente{ background:#7c2d12; color:#fdba74; padding:3px 10px; border-radius:99px; font-size:12px; font-weight:600; }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# CONFIGURACIÓN: TOKEN Y REPO
# ============================================================
REPO_NAME   = "tv-digital-admin"
CSV_FILE    = "base_datos_tv.csv"
CONFIG_FILE = "vendedores_config.json"

def get_token():
    try:
        return st.secrets["GITHUB_TOKEN"]
    except Exception:
        return os.environ.get("GITHUB_TOKEN", "")

def get_repo():
    token = get_token()
    if not token:
        st.error("No se encontró el token de GitHub. Configurá los secrets de Streamlit.")
        st.stop()
    auth = Auth.Token(token)
    g = Github(auth=auth)
    user = g.get_user()
    return user.get_repo(REPO_NAME)

# ============================================================
# FUNCIONES DE DATOS — GITHUB
# ============================================================

def github_read_csv():
    """Lee el CSV desde el repositorio de GitHub."""
    try:
        repo = get_repo()
        contents = repo.get_contents(CSV_FILE)
        raw = base64.b64decode(contents.content)
        # Intentar encodings comunes
        for enc in ['utf-8', 'latin1', 'cp1252']:
            try:
                text = raw.decode(enc)
                break
            except Exception:
                continue
        df = pd.read_csv(io.StringIO(text))
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace('nan', '')
        return df, contents.sha
    except GithubException as e:
        if e.status == 404:
            # El archivo no existe aún, devolvemos vacío
            empty = pd.DataFrame(columns=["Nombre", "Telefono", "Equipo", "Mes", "Vendedor"])
            return empty, None
        st.error(f"Error GitHub al leer datos: {e}")
        return pd.DataFrame(columns=["Nombre", "Telefono", "Equipo", "Mes", "Vendedor"]), None

def github_write_csv(df, sha):
    """Guarda el DataFrame como CSV en GitHub."""
    try:
        repo = get_repo()
        csv_content = df.to_csv(index=False, encoding='utf-8')
        if sha:
            repo.update_file(CSV_FILE, "Actualizar base de clientes", csv_content, sha)
        else:
            repo.create_file(CSV_FILE, "Crear base de clientes", csv_content)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error al guardar datos: {e}")
        return False

def github_read_json(filename):
    """Lee un JSON desde GitHub."""
    try:
        repo = get_repo()
        contents = repo.get_contents(filename)
        raw = base64.b64decode(contents.content).decode('utf-8')
        return json.loads(raw), contents.sha
    except GithubException as e:
        if e.status == 404:
            return None, None
        return None, None

def github_write_json(filename, data, sha, commit_msg="Actualizar configuración"):
    """Guarda un JSON en GitHub."""
    try:
        repo = get_repo()
        content = json.dumps(data, indent=4, ensure_ascii=False)
        if sha:
            repo.update_file(filename, commit_msg, content, sha)
        else:
            repo.create_file(filename, commit_msg, content)
        return True
    except Exception as e:
        st.error(f"Error al guardar configuración: {e}")
        return False

# ============================================================
# SISTEMA DE LOGIN
# ============================================================

def get_users():
    """Obtiene los usuarios desde secrets o por defecto."""
    try:
        users_raw = st.secrets.get("USERS", '{"admin": "tv2024"}')
        return json.loads(users_raw)
    except Exception:
        return {"admin": "tv2024"}

def show_login():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
            <div class="login-container">
                <div class="login-logo">📺</div>
                <div class="login-title">TV Digital Admin</div>
                <div class="login-subtitle">Sistema de Gestión Privado</div>
            </div>
        """, unsafe_allow_html=True)
        st.write("")
        with st.form("login_form"):
            usuario = st.text_input("👤 Usuario", placeholder="Ingresá tu usuario")
            password = st.text_input("🔒 Contraseña", type="password", placeholder="Ingresá tu contraseña")
            submitted = st.form_submit_button("Ingresar al Sistema →", use_container_width=True)
            if submitted:
                users = get_users()
                if usuario in users and users[usuario] == password:
                    st.session_state.logged_in  = True
                    st.session_state.username   = usuario
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")

def logout():
    st.session_state.logged_in = False
    st.session_state.username  = ""
    st.rerun()

# ============================================================
# CARGA INICIAL CON CACHÉ
# ============================================================

@st.cache_data(ttl=60)
def load_data_cached(_token_hash):
    return github_read_csv()

@st.cache_data(ttl=60)
def load_config_cached(_token_hash):
    return github_read_json(CONFIG_FILE)

# ============================================================
# MAIN APP
# ============================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# Mostrar login si no está autenticado
if not st.session_state.logged_in:
    show_login()
    st.stop()

# ---- USUARIO AUTENTICADO ----
token = get_token()
token_hash = hash(token)  # Para cache_data (no pasamos el token directo)

# Cargar datos
df_raw, csv_sha = load_data_cached(token_hash)
config_data, config_sha = load_config_cached(token_hash)

# ---- CONFIGURACIÓN DE VENDEDORES ----
def get_default_config(df):
    config = {}
    vendedores = [v for v in df['Vendedor'].unique() if v and v != ''] if 'Vendedor' in df.columns else []
    if not vendedores:
        vendedores = ['PROPIO', 'NOE', 'EUGE', 'MICA', 'ALEXIS']
    for v in vendedores:
        if v.upper() == 'PROPIO':
            precio = 10000.0
        elif v.upper() == 'ALEXIS':
            precio = 5000.0
        else:
            precio = 4000.0
        config[v] = {"nombre": v, "precio_vendedor": precio}
    return config

if config_data is None:
    config_data = get_default_config(df_raw)
    github_write_json(CONFIG_FILE, config_data, None)

vendedores_config = config_data

# ---- SIDEBAR ----
st.sidebar.title("⚙️ Configuración")
abono_general = st.sidebar.number_input(
    "Valor del Abono ($)",
    min_value=0, value=5000, step=500,
    help="Precio mensual cobrado a cada cliente."
)
st.sidebar.divider()
st.sidebar.write(f"👤 Sesión: **{st.session_state.username}**")
if st.sidebar.button("🚪 Cerrar Sesión"):
    logout()

# ---- TÍTULO ----
st.title("📺 Panel de Control — TV Digital")
st.write("Sistema de gestión de clientes, cobros y comisiones.")

# ---- PREPROCESAMIENTO ----
df = df_raw.copy()
df['Pagado']     = df['Mes'].apply(lambda x: '[P]' in str(x).upper())
df['Mes_Limpio'] = df['Mes'].apply(lambda x: str(x).split('[')[0].strip().upper())

def calcular_precio_vendedor(row):
    vend = row['Vendedor'] if row['Vendedor'] else 'SIN ASIGNAR'
    if vend in vendedores_config:
        conf = vendedores_config[vend]
        if vend.upper() == 'PROPIO':
            return float(abono_general)
        return float(conf.get("precio_vendedor", 4000.0))
    return 4000.0

df['Precio_Vendedor'] = df.apply(calcular_precio_vendedor, axis=1)
df['Monto_Facturado'] = abono_general
df['Comision_Valor']  = df['Monto_Facturado'] - df['Precio_Vendedor']
df['Ganancia_Valor']  = df['Precio_Vendedor']

# ---- TABS ----
tab_dashboard, tab_clientes, tab_pagos, tab_vendedores = st.tabs([
    "📊 Tablero General",
    "👥 Clientes y Filtros",
    "💰 Registrar Pagos / CRUD",
    "⚙️ Gestión de Vendedores"
])

# ===================================================
# TAB 1 — TABLERO GENERAL
# ===================================================
with tab_dashboard:
    st.subheader("📈 Resumen del Negocio")

    total_clientes         = len(df)
    total_pagos            = len(df[df['Pagado'] == True])
    total_impagos          = len(df[df['Pagado'] == False])
    recaudacion_bruta      = total_pagos * abono_general
    plata_cobrada_neta     = df[df['Pagado'] == True]['Precio_Vendedor'].sum()
    plata_pendiente_neta   = df[df['Pagado'] == False]['Precio_Vendedor'].sum()
    comisiones_pagos       = df[df['Pagado'] == True]['Comision_Valor'].sum()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-title">Clientes Totales</div>
            <div class="metric-value">{total_clientes}</div>
            <div class="metric-subtitle">Pagados: {total_pagos} | Pendientes: {total_impagos}</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-title">Tu Plata Cobrada (Neto)</div>
            <div class="metric-value green">${plata_cobrada_neta:,.0f}</div>
            <div class="metric-subtitle">Bruto clientes: ${recaudacion_bruta:,.0f}</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-title">Tu Plata Pendiente (Neto)</div>
            <div class="metric-value orange">${plata_pendiente_neta:,.0f}</div>
            <div class="metric-subtitle">De {total_impagos} clientes impagos</div>
        </div>""", unsafe_allow_html=True)
    with col4:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-title">Comisiones Vendedores</div>
            <div class="metric-value purple">${comisiones_pagos:,.0f}</div>
            <div class="metric-subtitle">Retenido por vendedores</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # Alta Rápida
    with st.expander("➕  PUM! — AGREGAR NUEVO CLIENTE (Alta Rápida)", expanded=False):
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            c_nombre   = st.text_input("Nombre Completo", key="qc_nombre")
            c_tel      = st.text_input("Teléfono", key="qc_tel")
            c_vendedor = st.selectbox("Vendedor Asignado", list(vendedores_config.keys()), key="qc_vendedor")
        with col_c2:
            c_equipo   = st.selectbox("Equipo", ["ANDROID", "Sin Asignar"], key="qc_equipo")
            c_mes      = st.selectbox("Mes de Facturación",
                ["ENERO","FEBRERO","MARZO","ABRIL","MAYO","JUNIO",
                 "JULIO","AGOSTO","SEPTIEMBRE","OCTUBRE","NOVIEMBRE","DICIEMBRE"],
                index=5, key="qc_mes")
            c_pagado   = st.checkbox("Registrar como PAGADO", value=False, key="qc_pagado")

        if st.button("🚀 PUM! CREAR CLIENTE", key="qc_btn"):
            if not c_nombre.strip():
                st.error("Ingresá un nombre para el cliente.")
            else:
                mes_sal = f"{c_mes} [P]" if c_pagado else c_mes
                nueva_fila = {
                    "Nombre": c_nombre.strip().upper(),
                    "Telefono": c_tel.strip(),
                    "Equipo": c_equipo,
                    "Mes": mes_sal,
                    "Vendedor": c_vendedor
                }
                df_nuevo = pd.concat([df_raw, pd.DataFrame([nueva_fila])], ignore_index=True)
                with st.spinner("Guardando en la nube..."):
                    ok = github_write_csv(df_nuevo, csv_sha)
                if ok:
                    st.success(f"Cliente {c_nombre.upper()} agregado!")
                    st.rerun()

    st.divider()

    # Métricas por vendedor
    st.subheader("👤 Rentabilidad por Vendedor")
    vendedor_stats = []
    for vend, conf in vendedores_config.items():
        sub  = df[df['Vendedor'] == vend]
        c_t  = len(sub)
        c_p  = len(sub[sub['Pagado'] == True])
        c_pend = len(sub[sub['Pagado'] == False])
        cobrado   = c_p * abono_general
        neta      = sub[sub['Pagado'] == True]['Precio_Vendedor'].sum()
        pendiente = sub[sub['Pagado'] == False]['Precio_Vendedor'].sum()
        comis     = sub[sub['Pagado'] == True]['Comision_Valor'].sum()
        margen    = (neta / cobrado * 100) if cobrado > 0 else 0.0
        vendedor_stats.append({
            "Vendedor": vend,
            "Clientes": c_t,
            "Pagos": c_p,
            "Pendientes": c_pend,
            "Cobrado Clientes ($)": cobrado,
            "Comisión ($)": comis,
            "Tu Recaudación ($)": neta,
            "Margen (%)": f"{margen:.1f}%"
        })

    df_vend = pd.DataFrame(vendedor_stats)
    st.dataframe(df_vend, use_container_width=True, hide_index=True)

    st.subheader("📊 Comparación Visual")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.write("**Clientes Pagos vs Pendientes**")
        st.bar_chart(df_vend.set_index("Vendedor")[["Pagos", "Pendientes"]])
    with col_g2:
        st.write("**Tu Recaudación Real ($)**")
        st.bar_chart(df_vend.set_index("Vendedor")[["Tu Recaudación ($)"]])


# ===================================================
# TAB 2 — CLIENTES Y FILTROS
# ===================================================
with tab_clientes:
    st.subheader("Buscar y Filtrar Clientes")

    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        busqueda = st.text_input("Buscar por nombre o teléfono")
    with col_f2:
        filtro_vendedor = st.selectbox("Filtrar por Vendedor", ["Todos"] + list(vendedores_config.keys()))
    with col_f3:
        filtro_estado = st.selectbox("Estado de Pago", ["Todos", "Pagados", "Pendientes"])
    with col_f4:
        equipos = ["Todos"] + [eq for eq in df['Equipo'].unique() if eq]
        filtro_equipo = st.selectbox("Filtrar por Equipo", equipos)

    df_filtrado = df.copy()
    if busqueda:
        df_filtrado = df_filtrado[
            df_filtrado['Nombre'].str.contains(busqueda, case=False, na=False) |
            df_filtrado['Telefono'].str.contains(busqueda, case=False, na=False)
        ]
    if filtro_vendedor != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Vendedor'] == filtro_vendedor]
    if filtro_estado == "Pagados":
        df_filtrado = df_filtrado[df_filtrado['Pagado'] == True]
    elif filtro_estado == "Pendientes":
        df_filtrado = df_filtrado[df_filtrado['Pagado'] == False]
    if filtro_equipo != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Equipo'] == filtro_equipo]

    st.write(f"Mostrando **{len(df_filtrado)}** clientes de **{len(df)}** totales.")

    df_vista = df_filtrado[["Nombre", "Telefono", "Equipo", "Mes", "Vendedor"]].copy()

    def color_pago(val):
        if '[P]' in str(val).upper():
            return 'background-color: #065f46; color: #6ee7b7; font-weight: bold;'
        return 'background-color: #7c2d12; color: #fdba74; font-weight: bold;'

    try:
        styled = df_vista.style.map(color_pago, subset=['Mes'])
    except Exception:
        styled = df_vista.style.applymap(color_pago, subset=['Mes'])
    st.dataframe(styled, use_container_width=True, hide_index=True)


# ===================================================
# TAB 3 — REGISTRAR PAGOS / CRUD
# ===================================================
with tab_pagos:
    subtab_mod, subtab_crear, subtab_del = st.tabs([
        "💳 Modificar / Registrar Pago",
        "➕ Agregar Nuevo Cliente",
        "❌ Eliminar Cliente"
    ])

    # --- MODIFICAR ---
    with subtab_mod:
        st.subheader("Seleccioná un Cliente para Gestionar")
        lista_clientes = sorted(df['Nombre'].tolist())
        cliente_sel = st.selectbox("Elegí el cliente", lista_clientes)

        if cliente_sel:
            datos = df_raw[df_raw['Nombre'] == cliente_sel].iloc[0]
            esta_pagado   = '[P]' in str(datos['Mes']).upper()
            mes_limpio    = str(datos['Mes']).split('[')[0].strip().upper()

            st.write("---")
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                nuevo_nombre   = st.text_input("Nombre Completo", datos['Nombre'])
                nuevo_tel      = st.text_input("Teléfono", datos['Telefono'])
                lista_vend     = list(vendedores_config.keys())
                vend_actual    = datos['Vendedor'] if datos['Vendedor'] in lista_vend else lista_vend[0]
                nuevo_vendedor = st.selectbox("Vendedor", lista_vend, index=lista_vend.index(vend_actual))
            with col_m2:
                nuevo_equipo   = st.selectbox("Equipo", ["ANDROID", "Sin Asignar"],
                                              index=0 if datos['Equipo'] == "ANDROID" else 1)
                meses_lista    = ["ENERO","FEBRERO","MARZO","ABRIL","MAYO","JUNIO",
                                  "JULIO","AGOSTO","SEPTIEMBRE","OCTUBRE","NOVIEMBRE","DICIEMBRE"]
                mes_idx        = meses_lista.index(mes_limpio) if mes_limpio in meses_lista else 0
                nuevo_mes      = st.selectbox("Mes de Facturación", meses_lista, index=mes_idx)
                nuevo_pagado   = st.checkbox("Registrar como PAGADO", value=esta_pagado)

            mes_salida = f"{nuevo_mes} [P]" if nuevo_pagado else nuevo_mes

            if st.button("Guardar Cambios del Cliente"):
                idx = df_raw[df_raw['Nombre'] == cliente_sel].index[0]
                df_raw.at[idx, 'Nombre']   = nuevo_nombre.strip().upper()
                df_raw.at[idx, 'Telefono'] = nuevo_tel.strip()
                df_raw.at[idx, 'Equipo']   = nuevo_equipo
                df_raw.at[idx, 'Mes']      = mes_salida
                df_raw.at[idx, 'Vendedor'] = nuevo_vendedor
                with st.spinner("Guardando en la nube..."):
                    ok = github_write_csv(df_raw, csv_sha)
                if ok:
                    st.success(f"Datos de {cliente_sel} actualizados!")
                    st.rerun()

    # --- AGREGAR ---
    with subtab_crear:
        st.subheader("Registrar un Nuevo Cliente")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            c_nombre2   = st.text_input("Nombre Completo", key="nc_nombre")
            c_tel2      = st.text_input("Teléfono", key="nc_tel")
            c_vendedor2 = st.selectbox("Vendedor", list(vendedores_config.keys()), key="nc_vend")
        with col_c2:
            c_equipo2   = st.selectbox("Equipo", ["ANDROID", "Sin Asignar"], key="nc_equipo")
            c_mes2      = st.selectbox("Mes de Facturación",
                ["ENERO","FEBRERO","MARZO","ABRIL","MAYO","JUNIO",
                 "JULIO","AGOSTO","SEPTIEMBRE","OCTUBRE","NOVIEMBRE","DICIEMBRE"], key="nc_mes")
            c_pagado2   = st.checkbox("Registrar como PAGADO", key="nc_pagado")

        if st.button("Crear y Guardar Cliente"):
            if not c_nombre2.strip():
                st.error("Ingresá un nombre válido.")
            else:
                mes_sal2 = f"{c_mes2} [P]" if c_pagado2 else c_mes2
                nueva    = {"Nombre": c_nombre2.strip().upper(), "Telefono": c_tel2.strip(),
                            "Equipo": c_equipo2, "Mes": mes_sal2, "Vendedor": c_vendedor2}
                df_nuevo = pd.concat([df_raw, pd.DataFrame([nueva])], ignore_index=True)
                with st.spinner("Guardando en la nube..."):
                    ok = github_write_csv(df_nuevo, csv_sha)
                if ok:
                    st.success(f"Cliente {c_nombre2.upper()} agregado!")
                    st.rerun()

    # --- ELIMINAR ---
    with subtab_del:
        st.subheader("Eliminar un Cliente")
        cliente_del = st.selectbox("Cliente a dar de baja", sorted(df['Nombre'].tolist()), key="del_sel")
        st.warning(f"Atencion: Estas por eliminar permanentemente a **{cliente_del}**.")
        confirmar   = st.checkbox("Confirmo que deseo borrar este registro de forma permanente.")

        if st.button("Eliminar Registro"):
            if confirmar:
                df_filt = df_raw[df_raw['Nombre'] != cliente_del]
                with st.spinner("Eliminando en la nube..."):
                    ok = github_write_csv(df_filt, csv_sha)
                if ok:
                    st.success(f"Cliente {cliente_del} eliminado.")
                    st.rerun()
            else:
                st.error("Marcá la casilla de confirmación antes de eliminar.")


# ===================================================
# TAB 4 — GESTIÓN DE VENDEDORES
# ===================================================
with tab_vendedores:
    st.subheader("Configuración de Vendedores")
    col_v1, col_v2 = st.columns([1, 2])

    with col_v1:
        st.markdown("### Agregar Nuevo Vendedor")
        nv_nombre = st.text_input("Nombre del Vendedor").strip().upper()
        nv_precio = st.number_input("Lo que te paga por cliente ($)", min_value=0.0, value=4000.0, step=500.0)
        if st.button("Registrar Vendedor"):
            if not nv_nombre:
                st.error("Escribe un nombre.")
            elif nv_nombre in vendedores_config:
                st.error("Este vendedor ya existe.")
            else:
                vendedores_config[nv_nombre] = {"nombre": nv_nombre, "precio_vendedor": nv_precio}
                with st.spinner("Guardando..."):
                    github_write_json(CONFIG_FILE, vendedores_config, config_sha)
                st.success(f"Vendedor '{nv_nombre}' agregado!")
                st.rerun()

    with col_v2:
        st.markdown("### Vendedores Registrados")
        vendedores_editados = {}
        for vend, datos in list(vendedores_config.items()):
            with st.expander(f"Vendedor: {vend}", expanded=True):
                col_e1, col_e2 = st.columns([2, 1])
                with col_e1:
                    nom_ed = st.text_input("Nombre", datos.get("nombre", vend), key=f"nom_{vend}").strip().upper()
                with col_e2:
                    prc_ed = st.number_input("Monto que te paga ($)", min_value=0.0,
                                             value=float(datos.get("precio_vendedor", 4000.0)),
                                             key=f"prc_{vend}")
                if st.button(f"Quitar {vend}", key=f"del_{vend}"):
                    if len(vendedores_config) <= 1:
                        st.error("Debe quedar al menos un vendedor.")
                    else:
                        del vendedores_config[vend]
                        with st.spinner("Guardando..."):
                            github_write_json(CONFIG_FILE, vendedores_config, config_sha)
                        st.success(f"Vendedor '{vend}' eliminado.")
                        st.rerun()
                else:
                    vendedores_editados[nom_ed] = {"nombre": nom_ed, "precio_vendedor": prc_ed}

        if st.button("Guardar Configuracion de Vendedores"):
            with st.spinner("Guardando..."):
                github_write_json(CONFIG_FILE, vendedores_editados, config_sha)
            st.success("Configuracion guardada!")
            st.rerun()
