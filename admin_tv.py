import streamlit as st
import pandas as pd
import json
import os
import io
import base64
from github import Github, Auth, GithubException
try:
    import extra_streamlit_components as stx
    _cookies_available = True
except ImportError:
    _cookies_available = False

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

def github_read_image(filename="recibo_mes.png"):
    """Lee una imagen desde GitHub."""
    try:
        repo = get_repo()
        contents = repo.get_contents(filename)
        raw = base64.b64decode(contents.content)
        return raw, contents.sha
    except GithubException as e:
        if e.status == 404:
            return None, None
        return None, None

def github_write_image(filename, image_bytes, sha, commit_msg="Actualizar recibo de pago"):
    """Guarda una imagen en GitHub."""
    try:
        repo = get_repo()
        if sha:
            repo.update_file(filename, commit_msg, image_bytes, sha)
        else:
            repo.create_file(filename, commit_msg, image_bytes)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error al guardar imagen en GitHub: {e}")
        return False

def github_delete_file(filename, sha, commit_msg="Eliminar archivo"):
    """Elimina un archivo de GitHub."""
    try:
        repo = get_repo()
        repo.delete_file(filename, commit_msg, sha)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error al eliminar archivo en GitHub: {e}")
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

def show_login(cookie_ctrl):
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
            recordar = st.checkbox("🔑 Recordarme en este dispositivo", value=True)
            submitted = st.form_submit_button("Ingresar al Sistema →", use_container_width=True)
            if submitted:
                users = get_users()
                if usuario in users and users[usuario] == password:
                    st.session_state.logged_in  = True
                    st.session_state.username   = usuario
                    if recordar and cookie_ctrl:
                        cookie_ctrl.set("tv_digital_user", usuario)
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")

def logout(cookie_ctrl):
    st.session_state.logged_in = False
    st.session_state.username  = ""
    if cookie_ctrl:
        try:
            cookie_ctrl.set("tv_digital_user", "")  # limpiar cookie
        except Exception:
            pass
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

@st.cache_data(ttl=60)
def load_image_cached(_token_hash):
    return github_read_image()

# ============================================================
# MAIN APP
# ============================================================

# Inicializar cookie manager
if _cookies_available:
    cookie_ctrl = stx.CookieManager(key="tv_cookie_mgr")
else:
    cookie_ctrl = None

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# Intentar restaurar sesión desde cookie
if not st.session_state.logged_in and cookie_ctrl:
    try:
        saved_user = cookie_ctrl.get("tv_digital_user")
        if saved_user and str(saved_user).strip():
            users = get_users()
            if saved_user in users:
                st.session_state.logged_in = True
                st.session_state.username  = saved_user
    except Exception:
        pass

# Mostrar login si no está autenticado
if not st.session_state.logged_in:
    show_login(cookie_ctrl)
    st.stop()

# ---- USUARIO AUTENTICADO ----
token = get_token()
token_hash = hash(token)  # Para cache_data (no pasamos el token directo)

# Cargar datos
df_raw, csv_sha = load_data_cached(token_hash)
config_data, config_sha = load_config_cached(token_hash)
recibo_bytes, recibo_sha = load_image_cached(token_hash)

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
    min_value=0, value=12000, step=500,
    help="Precio mensual cobrado a cada cliente."
)
st.sidebar.divider()
st.sidebar.write(f"👤 Sesión: **{st.session_state.username}**")
if st.sidebar.button("🚩 Cerrar Sesión"):
    logout(cookie_ctrl)

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
tab_dashboard, tab_clientes, tab_pagos, tab_vendedores, tab_whatsapp = st.tabs([
    "📊 Tablero General",
    "👥 Clientes y Filtros",
    "💰 Registrar Pagos / CRUD",
    "⚙️ Gestión de Vendedores",
    "📨 Avisos WhatsApp"
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
        # Desglose por vendedor de los pagos cobrados
        df_pagados = df[df['Pagado'] == True]
        desglose_parts = []
        for vend in df_pagados['Vendedor'].unique():
            cantidad = len(df_pagados[df_pagados['Vendedor'] == vend])
            subtotal = df_pagados[df_pagados['Vendedor'] == vend]['Precio_Vendedor'].sum()
            desglose_parts.append(f"{cantidad} {vend}: ${subtotal:,.0f}")
        desglose_txt = " | ".join(desglose_parts) if desglose_parts else "Sin pagos aún"
        st.markdown(f"""<div class="metric-card">
            <div class="metric-title">Tu Plata Cobrada (Neto)</div>
            <div class="metric-value green">${plata_cobrada_neta:,.0f}</div>
            <div class="metric-subtitle">{desglose_txt}</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-title">Tu Plata Pendiente (Neto)</div>
            <div class="metric-value orange">${plata_pendiente_neta:,.0f}</div>
            <div class="metric-subtitle">De {total_impagos} clientes impagos</div>
        </div>""", unsafe_allow_html=True)
    with col4:
        # Desglose de comisiones por vendedor (excluir PROPIO que no tiene comisión)
        comis_parts = []
        for vend in df_pagados['Vendedor'].unique():
            if vend.upper() == 'PROPIO':
                continue
            comis_vend = df_pagados[df_pagados['Vendedor'] == vend]['Comision_Valor'].sum()
            if comis_vend > 0:
                comis_parts.append(f"{vend}: ${comis_vend:,.0f}")
        comis_txt = " | ".join(comis_parts) if comis_parts else "Sin comisiones aún"
        st.markdown(f"""<div class="metric-card">
            <div class="metric-title">Comisiones Vendedores</div>
            <div class="metric-value purple">${comisiones_pagos:,.0f}</div>
            <div class="metric-subtitle">{comis_txt}</div>
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

    # Cierre de Mes
    with st.expander("🗓️  CIERRE DE MES — Resetear y arrancar mes nuevo", expanded=False):
        st.markdown("""
        **¿Qué hace el cierre de mes?**
        - Quita el estado PAGADO de **todos** los clientes (vuelven a pendiente)
        - Cambia el mes de facturación al mes nuevo que elijas
        - Los datos del mes anterior quedan en cero, listos para arrancar
        """)
        st.warning("Esta acción modifica TODOS los clientes. No se puede deshacer.")

        col_cm1, col_cm2 = st.columns(2)
        with col_cm1:
            mes_nuevo = st.selectbox(
                "Mes nuevo a asignar a todos los clientes",
                ["ENERO","FEBRERO","MARZO","ABRIL","MAYO","JUNIO",
                 "JULIO","AGOSTO","SEPTIEMBRE","OCTUBRE","NOVIEMBRE","DICIEMBRE"],
                index=6,  # JULIO por defecto
                key="cierre_mes"
            )
        with col_cm2:
            st.write("")
            st.write("")
            pagados_actuales = len(df[df['Pagado'] == True])
            st.info(f"Clientes pagados que se van a resetear: **{pagados_actuales}**")

        confirmar_cierre = st.checkbox(
            f"Confirmo el cierre de mes. Todos los clientes pasarán a PENDIENTE en {mes_nuevo}.",
            key="confirmar_cierre"
        )

        if st.button("🗓️ EJECUTAR CIERRE DE MES", key="btn_cierre"):
            if not confirmar_cierre:
                st.error("Marcá la casilla de confirmación para continuar.")
            else:
                # Resetear: quitar [P] y actualizar mes en todos los clientes
                df_cierre = df_raw.copy()
                df_cierre['Mes'] = mes_nuevo  # Todos pasan al mes nuevo, sin [P]
                with st.spinner(f"Ejecutando cierre de mes... asignando {mes_nuevo} a todos los clientes."):
                    ok = github_write_csv(df_cierre, csv_sha)
                if ok:
                    st.success(f"Cierre de mes ejecutado! Todos los clientes ahora figuran en {mes_nuevo} como PENDIENTES. Listo para arrancar!")
                    st.balloons()
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

    # Inicializar estado para confirmación de eliminación
    if "confirmar_eliminar" not in st.session_state:
        st.session_state.confirmar_eliminar = None

    # Encabezados de la tabla
    col_h1, col_h2, col_h3, col_h4, col_h5, col_h6 = st.columns([2.5, 1.5, 1.2, 1.5, 1.5, 0.6])
    with col_h1: st.markdown("**Nombre**")
    with col_h2: st.markdown("**Teléfono**")
    with col_h3: st.markdown("**Equipo**")
    with col_h4: st.markdown("**Mes**")
    with col_h5: st.markdown("**Vendedor**")
    with col_h6: st.markdown("**Baja**")
    st.divider()

    for row_idx, row in df_filtrado.iterrows():
        col_r1, col_r2, col_r3, col_r4, col_r5, col_r6 = st.columns([2.5, 1.5, 1.2, 1.5, 1.5, 0.6])
        mes_val = str(row['Mes'])
        es_pagado = '[P]' in mes_val.upper()
        mes_color = "color:#6ee7b7;font-weight:600;" if es_pagado else "color:#fdba74;font-weight:600;"
        with col_r1: st.write(row['Nombre'])
        with col_r2: st.write(str(row['Telefono']) if str(row['Telefono']) not in ['nan', ''] else '—')
        with col_r3: st.write(row['Equipo'])
        with col_r4: st.markdown(f"<span style='{mes_color}'>{mes_val}</span>", unsafe_allow_html=True)
        with col_r5: st.write(row['Vendedor'])
        with col_r6:
            if st.button("🗑️", key=f"del_btn_{row_idx}", help=f"Eliminar a {row['Nombre']}"):
                st.session_state.confirmar_eliminar = row['Nombre']
                st.rerun()

    # Diálogo de confirmación de eliminación
    if st.session_state.confirmar_eliminar:
        nombre_a_eliminar = st.session_state.confirmar_eliminar
        st.error(f"⚠️ ¿Estás seguro que deseás eliminar a **{nombre_a_eliminar}**? Esta acción no se puede deshacer.")
        col_si, col_no, _ = st.columns([1, 1, 4])
        with col_si:
            if st.button("✅ Sí, eliminar", type="primary", use_container_width=True):
                df_filt = df_raw[df_raw['Nombre'] != nombre_a_eliminar]
                with st.spinner("Eliminando en la nube..."):
                    ok = github_write_csv(df_filt, csv_sha)
                if ok:
                    st.session_state.confirmar_eliminar = None
                    st.success(f"Cliente {nombre_a_eliminar} eliminado.")
                    st.rerun()
        with col_no:
            if st.button("❌ Cancelar", use_container_width=True):
                st.session_state.confirmar_eliminar = None
                st.rerun()


# ===================================================
# TAB 3 — REGISTRAR PAGOS / CRUD
# ===================================================
with tab_pagos:
    subtab_mod, subtab_crear = st.tabs([
        "💳 Modificar / Registrar Pago",
        "➕ Agregar Nuevo Cliente"
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

# ============================================================
# HELPER: FORMATTEAR TELÉFONO DE ARGENTINA PARA WHATSAPP
# ============================================================
def format_argentina_phone(phone):
    """
    Formatea números de teléfono al estándar E.164 para WhatsApp en Argentina.
    Formato esperado: 54 + 9 + código de área (sin 0) + número local (sin 15).
    """
    if not phone or pd.isna(phone):
        return None
    
    # Conservar solo dígitos
    clean = "".join(filter(str.isdigit, str(phone)))
    
    if not clean:
        return None
        
    # Si ya empieza con 54, asegurarse del 9 si tiene largo de celular estándar
    if clean.startswith("54"):
        if len(clean) == 12 and not clean.startswith("549"):
            # Insertar 9 después de 54
            clean = "549" + clean[2:]
        return clean
        
    # Si tiene 10 dígitos (ej: 2281302299 o 2983569326)
    if len(clean) == 10:
        return "549" + clean
        
    # Si empieza con 9 y tiene 11 dígitos (ej: 92281302299)
    if len(clean) == 11 and clean.startswith("9"):
        return "54" + clean
        
    # Si tiene menos de 10 dígitos, probablemente esté incompleto o local sin código de área
    if len(clean) < 10:
        return None
        
    return "549" + clean

# ===================================================
# TAB 5 — AVISOS WHATSAPP (GRATIS)
# ===================================================
with tab_whatsapp:
    # 1. Configurar el Mensaje Template
    st.subheader("📝 Configurar Mensaje de Cobro")
    
    # Template por defecto (con Alias)
    default_template = "Hola *{nombre}*! Te recordamos que tu abono de TV Digital de *{mes}* es de *${monto}*.\n\n*Alias de transferencia:* onplaymp\n\nPara informar tu pago o realizar consultas, podés responder a este chat. ¡Muchas gracias! 😊"
    
    mensaje_template = st.text_area(
        "Edita el texto del mensaje. Podés usar: {nombre}, {mes}, {monto}",
        value=default_template,
        height=150,
        help="Las palabras entre llaves {} se reemplazarán automáticamente por los datos de cada cliente."
    )
    
    # Selector de mes para el mensaje
    meses_lista = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
    mes_aviso = st.selectbox(
        "📅 Mes a incluir en el aviso de cobro:",
        meses_lista,
        index=6,  # JULIO por defecto
        help="Este mes reemplazará la palabra {mes} en el mensaje que le envíes a los clientes."
    )
    
    # Subir Recibo del Mes
    st.write("---")
    st.write("### 🖼️ Recibo / Imagen del Mes (Opcional)")
    
    adjuntar_link = False
    if recibo_bytes:
        st.image(recibo_bytes, caption="Recibo cargado para este mes", use_container_width=True)
        adjuntar_link = st.checkbox("🔗 Adjuntar automáticamente el link del recibo al mensaje (Muestra vista previa de la imagen en celulares y PC)", value=True)
        
        col_img1, col_img2 = st.columns([2, 1])
        with col_img2:
            if st.button("🗑️ Eliminar recibo actual", use_container_width=True, type="secondary"):
                with st.spinner("Eliminando recibo..."):
                    ok = github_delete_file("recibo_mes.png", recibo_sha, "Eliminar recibo del mes")
                if ok:
                    st.success("Recibo eliminado!")
                    st.rerun()
    else:
        st.warning("No hay ningún recibo cargado para este mes.")
        
    uploaded_file = st.file_uploader("Subir nueva imagen de recibo:", type=["png", "jpg", "jpeg"])
    if uploaded_file is not None:
        new_image_bytes = uploaded_file.read()
        if st.button("💾 Guardar y actualizar imagen"):
            with st.spinner("Subiendo imagen..."):
                ok = github_write_image("recibo_mes.png", new_image_bytes, recibo_sha)
            if ok:
                st.success("¡Imagen cargada exitosamente!")
                st.rerun()
                
    st.write("---")
    
    # Opción de plataforma
    whatsapp_platform = st.radio(
        "Abrir WhatsApp en:",
        ["WhatsApp Web (Recomendado para PC / Google Chrome)", "WhatsApp App / Celular (wa.me)"],
        horizontal=True
    )

    # 2. Clientes Impagos / Pendientes (Listado Individual)
    st.write("---")
    st.write("### 👥 Clientes Pendientes de Pago")
    
    # Filtro por vendedor específico para WhatsApp
    lista_vend_wa = ["Todos"] + list(vendedores_config.keys())
    filtro_vend_wa = st.selectbox("Filtrar por Vendedor", lista_vend_wa, key="wa_filtro_vendedor")
    
    # Obtener lista de clientes pendientes
    df_pendientes = df[df['Pagado'] == False].copy()
    if filtro_vend_wa != "Todos":
        df_pendientes = df_pendientes[df_pendientes['Vendedor'] == filtro_vend_wa]
        
    if df_pendientes.empty:
        st.success("¡Buenísimo! No hay clientes pendientes con los filtros seleccionados.")
    else:
        st.write(f"Hay **{len(df_pendientes)}** clientes pendientes.")
        
        # Buscador de cliente pendiente
        busqueda_wa = st.text_input("Buscar cliente pendiente por nombre o teléfono", key="wa_busqueda")
        if busqueda_wa:
            df_pendientes = df_pendientes[
                df_pendientes['Nombre'].str.contains(busqueda_wa, case=False, na=False) |
                df_pendientes['Telefono'].str.contains(busqueda_wa, case=False, na=False)
            ]
            
        # Tabla interactiva
        # Encabezados
        col_name, col_tel, col_vend, col_actions = st.columns([2.5, 1.5, 1.5, 2.5])
        with col_name:
            st.markdown("**Cliente**")
        with col_tel:
            st.markdown("**Teléfono**")
        with col_vend:
            st.markdown("**Vendedor**")
        with col_actions:
            st.markdown("**Acciones**")
            
        st.divider()
        
        import urllib.parse
        
        for idx, row in df_pendientes.iterrows():
            c_name = row['Nombre']
            c_tel = row['Telefono']
            c_vend = row['Vendedor']
            c_mes_limpio = row['Mes_Limpio']
            
            # Formatear teléfono
            formatted_phone = format_argentina_phone(c_tel)
            
            # Formatear mensaje
            # Reemplazar placeholders en el template
            try:
                mensaje_final = mensaje_template.format(
                    nombre=c_name.title(),
                    mes=mes_aviso.title(),
                    monto=f"{abono_general:,.0f}"
                )
            except Exception as e:
                mensaje_final = mensaje_template  # fallback
                
            if adjuntar_link:
                mensaje_final += "\n\nVer recibo: https://raw.githubusercontent.com/radioprolait/tv-digital-admin/main/recibo_mes.png"
                
            encoded_msg = urllib.parse.quote(mensaje_final)
            
            # Generar URL
            if whatsapp_platform.startswith("WhatsApp Web"):
                wa_url = f"https://web.whatsapp.com/send?phone={formatted_phone}&text={encoded_msg}"
            else:
                wa_url = f"https://wa.me/{formatted_phone}?text={encoded_msg}"
                
            col_r_name, col_r_tel, col_r_vend, col_r_actions = st.columns([2.5, 1.5, 1.5, 2.5])
            
            with col_r_name:
                st.write(c_name)
            with col_r_tel:
                st.write(c_tel if (c_tel and str(c_tel).strip() and str(c_tel) != 'nan') else "⚠️ Sin Tel")
            with col_r_vend:
                st.write(c_vend)
            with col_r_actions:
                col_btn_send, col_btn_pay = st.columns([1.2, 1.0])
                with col_btn_send:
                    if formatted_phone:
                        st.link_button("✉️ Enviar", wa_url, use_container_width=True)
                    else:
                        st.button("❌ Sin Tel", disabled=True, use_container_width=True, key=f"disabled_wa_{idx}")
                with col_btn_pay:
                    # Botón para marcar como pagado directamente
                    if st.button("✅ Pago", key=f"pay_wa_{idx}", use_container_width=True, help="Marcar como pagado sin salir"):
                        # Encontrar en df_raw original y marcar pagado
                        raw_idx = df_raw[df_raw['Nombre'] == c_name].index[0]
                        df_raw.at[raw_idx, 'Mes'] = f"{row['Mes']} [P]"
                        with st.spinner("Registrando pago..."):
                            ok = github_write_csv(df_raw, csv_sha)
                        if ok:
                            st.success(f"{c_name} marcado como PAGADO!")
                            st.rerun()
