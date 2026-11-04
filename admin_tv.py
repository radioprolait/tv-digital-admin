import streamlit as st
import pandas as pd
import os
import io
import base64
import math
import urllib.parse
from datetime import datetime
from github import Github, Auth, GithubException

# ============================================================
# CONFIGURACIÓN DE PÁGINA
# ============================================================
st.set_page_config(
    page_title="Admin TV Digital — Mar TV",
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
        color: #94a3b8;
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
        color: #64748b;
        margin-top: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# CONFIGURACIÓN: TOKEN Y REPO
# ============================================================
REPO_NAME = "tv-digital-admin"
CSV_FILE  = "base_datos_tv.csv"
MESES_LISTA = [
    "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"
]
RECIBO_RAW_URL = "https://raw.githubusercontent.com/radioprolait/tv-digital-admin/main/recibo_mes.png"

def get_token():
    try:
        return st.secrets["GITHUB_TOKEN"]
    except Exception:
        return os.environ.get("GITHUB_TOKEN", "")

@st.cache_resource(ttl=600)
def _get_cached_repo(token):
    auth = Auth.Token(token)
    g = Github(auth=auth, timeout=12)
    return g.get_repo(f"radioprolait/{REPO_NAME}")

def get_repo():
    token = get_token()
    if not token:
        st.error("No se encontró el token de GitHub. Configurá los secrets de Streamlit.")
        st.stop()
    return _get_cached_repo(token)

# ============================================================
# FUNCIONES DE DATOS — GITHUB + MEMORIA INSTANTÁNEA
# ============================================================

def github_read_csv():
    """Lee el CSV desde el repositorio de GitHub."""
    try:
        repo = get_repo()
        contents = repo.get_contents(CSV_FILE)
        raw = base64.b64decode(contents.content)
        text = None
        for enc in ['utf-8', 'latin1', 'cp1252']:
            try:
                text = raw.decode(enc)
                break
            except Exception:
                continue
        df = pd.read_csv(io.StringIO(text))
        for col in ["Nombre", "Telefono", "Apps", "Mes", "Vendedor"]:
            if col not in df.columns:
                df[col] = "PROPIO" if col == "Vendedor" else ""
            df[col] = df[col].astype(str).str.strip().replace('nan', '')
        return df, contents.sha
    except GithubException as e:
        if e.status == 404:
            empty = pd.DataFrame(columns=["Nombre", "Telefono", "Apps", "Mes", "Vendedor"])
            return empty, None
        raise e

def save_df_instant(df_nuevo, commit_msg="Actualizar base de clientes"):
    """
    Guarda el DataFrame en GitHub y actualiza st.session_state en el acto
    sin tener que volver a descargar el CSV desde internet.
    """
    try:
        repo = get_repo()
        df_clean = df_nuevo[["Nombre", "Telefono", "Apps", "Mes", "Vendedor"]].copy()
        csv_content = df_clean.to_csv(index=False, encoding='utf-8')
        sha = st.session_state.get("csv_sha")
        if sha:
            try:
                res = repo.update_file(CSV_FILE, commit_msg, csv_content, sha)
            except GithubException as ge:
                if ge.status in (409, 422, 500, 502, 503):
                    fresh_sha = repo.get_contents(CSV_FILE).sha
                    res = repo.update_file(CSV_FILE, commit_msg, csv_content, fresh_sha)
                else:
                    raise ge
        else:
            res = repo.create_file(CSV_FILE, "Crear base de clientes", csv_content)

        # Actualizar memoria instantánea con el nuevo SHA devuelto por GitHub
        new_sha = res["content"].sha if isinstance(res, dict) and "content" in res else repo.get_contents(CSV_FILE).sha
        st.session_state.df_data = df_clean.reset_index(drop=True)
        st.session_state.csv_sha = new_sha
        return True
    except Exception as e:
        st.error(f"Error al guardar datos en GitHub: {e}")
        return False

@st.cache_data(ttl=120)
def load_image_cached(_token_hash):
    try:
        repo = get_repo()
        contents = repo.get_contents("recibo_mes.png")
        return contents.sha
    except Exception:
        return None

def github_write_image(filename, image_bytes, sha, commit_msg="Actualizar recibo de pago"):
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
    try:
        repo = get_repo()
        repo.delete_file(filename, commit_msg, sha)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error al eliminar archivo en GitHub: {e}")
        return False

# ============================================================
# HELPER: FORMATEAR TELÉFONO DE ARGENTINA PARA WHATSAPP
# ============================================================
def format_argentina_phone(phone):
    if not phone or pd.isna(phone):
        return None
    clean = "".join(filter(str.isdigit, str(phone)))
    if not clean or clean == "123":
        return None
    if clean.startswith("54"):
        if len(clean) == 12 and not clean.startswith("549"):
            clean = "549" + clean[2:]
        return clean
    if len(clean) == 10:
        return "549" + clean
    if len(clean) == 11 and clean.startswith("9"):
        return "54" + clean
    if len(clean) < 10:
        return None
    return "549" + clean

# ============================================================
# SISTEMA DE LOGIN
# ============================================================
def get_users():
    return {"zoeyalbert": "misbebes"}

def show_login():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
            <div class="login-container">
                <div class="login-logo">📺</div>
                <div class="login-title">Mar TV Admin</div>
                <div class="login-subtitle">Sistema de Gestión de Clientes</div>
            </div>
        """, unsafe_allow_html=True)
        st.write("")
        with st.form("login_form"):
            usuario  = st.text_input("👤 Usuario", placeholder="Ingresá tu usuario")
            password = st.text_input("🔒 Contraseña", type="password", placeholder="Ingresá tu contraseña")
            recordar = st.checkbox("🔑 Recordarme en este dispositivo", value=True)
            submitted = st.form_submit_button("Ingresar al Sistema →", use_container_width=True)
            if submitted:
                users = get_users()
                if usuario in users and users[usuario] == password:
                    st.session_state.logged_in = True
                    st.session_state.username  = usuario
                    if recordar:
                        st.query_params["_u"] = usuario
                    else:
                        st.query_params.clear()
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")

def logout():
    st.session_state.logged_in = False
    st.session_state.username  = ""
    st.query_params.clear()
    st.rerun()

# ============================================================
# MAIN APP — AUTENTICACIÓN
# ============================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

if not st.session_state.logged_in:
    saved_user = st.query_params.get("_u", "")
    if saved_user and saved_user in get_users():
        st.session_state.logged_in = True
        st.session_state.username  = saved_user

if not st.session_state.logged_in:
    show_login()
    st.stop()

# ============================================================
# CARGA DE DATOS EN MEMORIA DE SESIÓN (MODO TURBO)
# ============================================================
token = get_token()
token_hash = hash(token)

if "df_data" not in st.session_state or "csv_sha" not in st.session_state:
    try:
        with st.spinner("Cargando base de clientes..."):
            df_loaded, sha_loaded = github_read_csv()
            st.session_state.df_data = df_loaded.reset_index(drop=True)
            st.session_state.csv_sha = sha_loaded
    except Exception as _conn_err:
        st.error("⚠️ **No se pudo conectar con GitHub.**")
        if st.button("🔄 Reintentar conexión", type="primary"):
            st.rerun()
        st.stop()

df_raw = st.session_state.df_data

# Preprocesamiento rápido en memoria
df = df_raw.copy()
df["RowID"]      = df.index
df["Pagado"]     = df["Mes"].apply(lambda x: "[P]" in str(x).upper())
df["Mes_Limpio"] = df["Mes"].apply(lambda x: str(x).split("[")[0].strip().upper())

# Detectar automáticamente el mes activo de la base (ej: NOVIEMBRE)
meses_validos = [m for m in df["Mes_Limpio"] if m in MESES_LISTA]
mes_activo_default = pd.Series(meses_validos).mode().iloc[0] if meses_validos else "NOVIEMBRE"
mes_default_idx = MESES_LISTA.index(mes_activo_default) if mes_activo_default in MESES_LISTA else 10

# ============================================================
# SIDEBAR (CONFIGURACIÓN + BACKUP EN 1 CLIC + SINCRONIZAR)
# ============================================================
st.sidebar.title("⚙️ Panel Mar TV")
abono_general = st.sidebar.number_input(
    "💵 Valor del Abono ($)",
    min_value=0, value=12000, step=500,
    help="Precio mensual cobrado a cada cliente."
)

st.sidebar.divider()
st.sidebar.subheader("🛡️ Copia de Seguridad")
fecha_str = datetime.now().strftime("%Y-%m-%d")
csv_backup_bytes = df_raw.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
st.sidebar.download_button(
    label="📥 Descargar Backup (Excel/CSV)",
    data=csv_backup_bytes,
    file_name=f"backup_martv_{fecha_str}_{len(df_raw)}clientes.csv",
    mime="text/csv",
    use_container_width=True,
    help="Descarga una copia completa de tus clientes a tu computadora."
)

if st.sidebar.button("🔄 Sincronizar con la Nube", use_container_width=True, help="Recarga los datos desde GitHub si hiciste cambios desde otro dispositivo."):
    df_loaded, sha_loaded = github_read_csv()
    st.session_state.df_data = df_loaded.reset_index(drop=True)
    st.session_state.csv_sha = sha_loaded
    st.cache_data.clear()
    st.sidebar.success("¡Base sincronizada!")
    st.rerun()

st.sidebar.divider()
st.sidebar.write(f"👤 Sesión: **{st.session_state.username}**")
if st.sidebar.button("🚩 Cerrar Sesión", use_container_width=True):
    logout()

# ============================================================
# TÍTULO Y TABS PRINCIPALES
# ============================================================
st.title("📺 Panel de Control — Mar TV")

tab_dashboard, tab_clientes, tab_crud, tab_whatsapp = st.tabs([
    "📊 Tablero y Cobro en Lote",
    "⚡ Clientes y Cobro Rápido",
    "✏️ Agregar / Editar Cliente",
    "📨 Avisos WhatsApp"
])

# ===================================================
# TAB 1 — TABLERO GENERAL + COBRO EN LOTE + ALTA RÁPIDA
# ===================================================
with tab_dashboard:
    total_clientes = len(df)
    total_pagos    = int(df["Pagado"].sum())
    total_impagos  = total_clientes - total_pagos
    plata_cobrada  = total_pagos * abono_general
    plata_pendiente = total_impagos * abono_general
    potencial_mes  = total_clientes * abono_general
    efectividad    = (total_pagos / total_clientes * 100) if total_clientes > 0 else 0.0
    meta_600_pct   = min(total_clientes / 600.0, 1.0)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-title">Clientes Activos</div>
            <div class="metric-value">{total_clientes}</div>
            <div class="metric-subtitle">✅ Pagados: {total_pagos} | ⏳ Pendientes: {total_impagos}</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-title">Plata Cobrada ({mes_activo_default})</div>
            <div class="metric-value green">${plata_cobrada:,.0f}</div>
            <div class="metric-subtitle">Efectividad hoy: {efectividad:.1f}% cobrado</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-title">Plata por Entrar</div>
            <div class="metric-value orange">${plata_pendiente:,.0f}</div>
            <div class="metric-subtitle">Potencial total del mes: ${potencial_mes:,.0f}</div>
        </div>""", unsafe_allow_html=True)
    with col4:
        faltan_600 = max(600 - total_clientes, 0)
        st.markdown(f"""<div class="metric-card">
            <div class="metric-title">🎯 Meta 600 Clientes</div>
            <div class="metric-value purple">{total_clientes} / 600</div>
            <div class="metric-subtitle">{meta_600_pct*100:.1f}% alcanzado (faltan {faltan_600})</div>
        </div>""", unsafe_allow_html=True)

    st.progress(meta_600_pct, text=f"🚀 Progreso hacia los 600 clientes: {total_clientes}/600 ({meta_600_pct*100:.1f}%) — Facturación potencial a los 600: ${600*abono_general:,.0f}/mes")

    st.divider()

    # ---- COBRO EN LOTE (MÚLTIPLE) ----
    st.subheader("⚡ Cobro Relámpago en Lote (Marcar varios pagos juntos)")
    df_pend_lote = df[df["Pagado"] == False]
    if df_pend_lote.empty:
        st.success("🎉 ¡Todos los clientes están al día!")
    else:
        opciones_lote = {
            f"{row['Nombre']} ({row['Telefono'] if row['Telefono'] else 'Sin tel'}) — #{row['RowID']+1}": row["RowID"]
            for _, row in df_pend_lote.iterrows()
        }
        col_lote1, col_lote2 = st.columns([3, 1])
        with col_lote1:
            seleccionados_labels = st.multiselect(
                "Escribí los nombres o teléfonos de los clientes que te transfirieron y marcalos todos juntos:",
                options=list(opciones_lote.keys()),
                placeholder="Ej: escribí el nombre o teléfono para elegir 1 o varios clientes..."
            )
        with col_lote2:
            st.write("")
            st.write("")
            if st.button(f"✅ Marcar {len(seleccionados_labels)} Pagado(s)", type="primary", use_container_width=True, disabled=(len(seleccionados_labels) == 0)):
                df_upd = df_raw.copy()
                for lbl in seleccionados_labels:
                    r_id = opciones_lote[lbl]
                    mes_base = str(df_upd.at[r_id, "Mes"]).split("[")[0].strip().upper()
                    if not mes_base or mes_base == "NAN":
                        mes_base = mes_activo_default
                    df_upd.at[r_id, "Mes"] = f"{mes_base} [P]"
                with st.spinner("Guardando pagos en lote..."):
                    ok = save_df_instant(df_upd, f"Registrar {len(seleccionados_labels)} pagos en lote")
                if ok:
                    st.success(f"¡{len(seleccionados_labels)} pago(s) registrado(s) en un segundo!")
                    st.rerun()

    st.divider()

    # ---- ALTA RÁPIDA (PUM!) CON DETECTOR DE DUPLICADOS ----
    with st.expander("➕  PUM! — AGREGAR NUEVO CLIENTE (Alta Rápida)", expanded=False):
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            c_nombre = st.text_input("Nombre Completo", key="qc_nombre")
            c_tel    = st.text_input("Teléfono", key="qc_tel")
        with col_c2:
            c_equipo = st.selectbox("App", ["ON PLAY", "MarTV", "MULTI GEMA"], key="qc_equipo")
            c_mes    = st.selectbox("Mes de Facturación", MESES_LISTA, index=mes_default_idx, key="qc_mes")
            c_pagado = st.checkbox("Registrar como PAGADO", value=True, key="qc_pagado")

        # Aviso inteligente en vivo si ya existe el nombre o teléfono
        if c_nombre.strip():
            dup_nom = df[df["Nombre"].str.upper() == c_nombre.strip().upper()]
            if not dup_nom.empty:
                st.warning(f"⚠️ Ya existe un cliente llamado **{c_nombre.strip().upper()}** (Tel: {dup_nom.iloc[0]['Telefono']}). Si es una segunda cuenta, podés ponerle **{c_nombre.strip().upper()} 2**.")
        if c_tel.strip():
            clean_new_tel = "".join(filter(str.isdigit, c_tel.strip()))
            if len(clean_new_tel) >= 7:
                dup_tel = df[df["Telefono"].apply(lambda t: clean_new_tel in "".join(filter(str.isdigit, str(t))))]
                if not dup_tel.empty:
                    nombres_mismo_tel = ", ".join(dup_tel["Nombre"].tolist())
                    st.info(f"ℹ️ Este número de teléfono ya lo tiene: **{nombres_mismo_tel}**.")

        if st.button("🚀 PUM! CREAR CLIENTE", key="qc_btn", type="primary"):
            if not c_nombre.strip():
                st.error("Ingresá un nombre para el cliente.")
            else:
                mes_sal = f"{c_mes} [P]" if c_pagado else c_mes
                nueva_fila = {
                    "Nombre": c_nombre.strip().upper(),
                    "Telefono": c_tel.strip(),
                    "Apps": c_equipo,
                    "Mes": mes_sal,
                    "Vendedor": "PROPIO"
                }
                df_nuevo = pd.concat([df_raw, pd.DataFrame([nueva_fila])], ignore_index=True)
                with st.spinner("Guardando cliente..."):
                    ok = save_df_instant(df_nuevo, f"Alta cliente {c_nombre.strip().upper()}")
                if ok:
                    st.success(f"¡Cliente {c_nombre.strip().upper()} agregado con éxito!")
                    st.rerun()

    st.divider()

    # ---- ÚLTIMOS 10 CLIENTES AGREGADOS ----
    st.subheader("🆕 Últimos 10 Clientes Agregados")
    st.caption("Ideal para ver de un vistazo los clientes nuevos y agendarlos en tus listas de WhatsApp.")
    ultimos_10 = df.tail(10).iloc[::-1].copy()
    ultimos_10["# Orden"] = ultimos_10["RowID"] + 1
    ultimos_10["Estado"]  = ultimos_10["Pagado"].apply(lambda p: "✅ PAGADO" if p else "⏳ PENDIENTE")
    st.dataframe(
        ultimos_10[["# Orden", "Nombre", "Telefono", "Apps", "Mes", "Estado"]],
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # ---- CIERRE DE MES ----
    with st.expander("🗓️  CIERRE DE MES — Resetear y arrancar mes nuevo", expanded=False):
        st.warning("Esta acción pasa TODOS los clientes a PENDIENTE en el mes nuevo que elijas.")
        col_cm1, col_cm2 = st.columns(2)
        with col_cm1:
            proximo_idx = (mes_default_idx + 1) % 12
            mes_nuevo = st.selectbox(
                "Mes nuevo a asignar a todos los clientes",
                MESES_LISTA,
                index=proximo_idx,
                key="cierre_mes"
            )
        with col_cm2:
            st.write("")
            st.write("")
            st.info(f"Clientes pagados actuales que se van a resetear: **{total_pagos}**")

        confirmar_cierre = st.checkbox(
            f"Confirmo el cierre de mes. Todos los {total_clientes} clientes pasarán a PENDIENTE en {mes_nuevo}.",
            key="confirmar_cierre"
        )

        if st.button("🗓️ EJECUTAR CIERRE DE MES", key="btn_cierre"):
            if not confirmar_cierre:
                st.error("Marcá la casilla de confirmación para continuar.")
            else:
                df_cierre = df_raw.copy()
                df_cierre["Mes"] = mes_nuevo
                with st.spinner(f"Ejecutando cierre de mes a {mes_nuevo}..."):
                    ok = save_df_instant(df_cierre, f"Cierre de mes a {mes_nuevo}")
                if ok:
                    st.success(f"¡Cierre de mes ejecutado! Todos figuran en {mes_nuevo} como PENDIENTES.")
                    st.balloons()
                    st.rerun()


# ===================================================
# TAB 2 — CLIENTES Y COBRO RÁPIDO (PAGINADO TURBO)
# ===================================================
with tab_clientes:
    st.subheader("⚡ Buscar, Filtrar y Cobrar en 1 Clic")

    col_f1, col_f2, col_f3, col_f4 = st.columns([2.2, 1.2, 1.2, 1.0])
    with col_f1:
        busqueda = st.text_input("🔍 Buscar por nombre o teléfono", placeholder="Escribí nombre o número...")
    with col_f2:
        filtro_estado = st.selectbox("Estado de Pago", ["Todos", "Pendientes", "Pagados"])
    with col_f3:
        apps_opts = ["Todas"] + sorted([a for a in df["Apps"].unique() if a])
        filtro_equipo = st.selectbox("Filtrar por App", apps_opts)
    with col_f4:
        filas_por_pagina = st.selectbox("Mostrar por página", [30, 50, 100], index=0)

    df_filtrado = df.copy()
    if busqueda:
        q = busqueda.strip()
        df_filtrado = df_filtrado[
            df_filtrado["Nombre"].str.contains(q, case=False, na=False) |
            df_filtrado["Telefono"].str.contains(q, case=False, na=False)
        ]
    if filtro_estado == "Pagados":
        df_filtrado = df_filtrado[df_filtrado["Pagado"] == True]
    elif filtro_estado == "Pendientes":
        df_filtrado = df_filtrado[df_filtrado["Pagado"] == False]
    if filtro_equipo != "Todas":
        df_filtrado = df_filtrado[df_filtrado["Apps"] == filtro_equipo]

    total_filt = len(df_filtrado)
    total_paginas = max(1, math.ceil(total_filt / filas_por_pagina))

    col_info, col_pag = st.columns([2, 1])
    with col_info:
        st.write(f"Mostrando **{total_filt}** clientes encontrados (de **{len(df)}** totales).")
    with col_pag:
        if total_paginas > 1:
            pagina_actual = st.number_input(f"Página (1 a {total_paginas})", min_value=1, max_value=total_paginas, value=1, step=1, key="pag_clientes")
        else:
            pagina_actual = 1

    inicio = (pagina_actual - 1) * filas_por_pagina
    fin    = inicio + filas_por_pagina
    df_pagina = df_filtrado.iloc[inicio:fin]

    if "confirmar_eliminar_id" not in st.session_state:
        st.session_state.confirmar_eliminar_id = None

    # Diálogo de confirmación de eliminación (arriba para que sea visible al instante)
    if st.session_state.confirmar_eliminar_id is not None:
        elim_id = st.session_state.confirmar_eliminar_id
        if elim_id in df_raw.index:
            nom_elim = df_raw.at[elim_id, "Nombre"]
            tel_elim = df_raw.at[elim_id, "Telefono"]
            st.error(f"⚠️ ¿Estás seguro que deseás eliminar a **{nom_elim}** (Tel: `{tel_elim}`, Fila #{elim_id+1})? Esta acción no se puede deshacer.")
            col_si, col_no, _ = st.columns([1, 1, 3])
            with col_si:
                if st.button("✅ Sí, eliminar definitivamente", type="primary", use_container_width=True):
                    df_sin_cliente = df_raw.drop(index=elim_id).reset_index(drop=True)
                    with st.spinner("Eliminando cliente..."):
                        ok = save_df_instant(df_sin_cliente, f"Eliminar cliente {nom_elim}")
                    if ok:
                        st.session_state.confirmar_eliminar_id = None
                        st.success(f"Cliente {nom_elim} eliminado.")
                        st.rerun()
            with col_no:
                if st.button("❌ Cancelar", use_container_width=True):
                    st.session_state.confirmar_eliminar_id = None
                    st.rerun()
        else:
            st.session_state.confirmar_eliminar_id = None

    # Encabezados de la tabla
    col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([2.6, 1.5, 1.0, 1.3, 1.8])
    with col_h1: st.markdown("**# / Nombre**")
    with col_h2: st.markdown("**Teléfono**")
    with col_h3: st.markdown("**App**")
    with col_h4: st.markdown("**Estado / Mes**")
    with col_h5: st.markdown("**Acciones Rápidas**")
    st.divider()

    for _, row in df_pagina.iterrows():
        r_id      = int(row["RowID"])
        mes_val   = str(row["Mes"])
        es_pagado = bool(row["Pagado"])
        mes_limp  = str(row["Mes_Limpio"]) if row["Mes_Limpio"] else mes_activo_default
        mes_color = "color:#34d399;font-weight:700;" if es_pagado else "color:#fb923c;font-weight:700;"

        col_r1, col_r2, col_r3, col_r4, col_r5 = st.columns([2.6, 1.5, 1.0, 1.3, 1.8])
        with col_r1:
            st.write(f"**#{r_id+1}** — {row['Nombre']}")
        with col_r2:
            st.write(str(row["Telefono"]) if str(row["Telefono"]) not in ["nan", ""] else "—")
        with col_r3:
            st.write(row["Apps"])
        with col_r4:
            st.markdown(f"<span style='{mes_color}'>{mes_val}</span>", unsafe_allow_html=True)
        with col_r5:
            b_col1, b_col2 = st.columns([1.4, 0.6])
            with b_col1:
                if not es_pagado:
                    if st.button("✅ Pagó", key=f"fast_pay_{r_id}", use_container_width=True, help="Marcar como PAGADO en 1 clic"):
                        df_upd = df_raw.copy()
                        df_upd.at[r_id, "Mes"] = f"{mes_limp} [P]"
                        ok = save_df_instant(df_upd, f"Pago {row['Nombre']}")
                        if ok:
                            st.rerun()
                else:
                    if st.button("↩️ Quitar [P]", key=f"fast_unpay_{r_id}", use_container_width=True, help="Volver a PENDIENTE"):
                        df_upd = df_raw.copy()
                        df_upd.at[r_id, "Mes"] = mes_limp
                        ok = save_df_instant(df_upd, f"Pasar a pendiente {row['Nombre']}")
                        if ok:
                            st.rerun()
            with b_col2:
                if st.button("🗑️", key=f"del_btn_{r_id}", use_container_width=True, help=f"Eliminar a {row['Nombre']}"):
                    st.session_state.confirmar_eliminar_id = r_id
                    st.rerun()


# ===================================================
# TAB 3 — EDITAR CLIENTE / SUMAR 2DA CUENTA
# ===================================================
with tab_crud:
    st.subheader("✏️ Modificar Datos de un Cliente o Sumar 2da Cuenta")

    # Identificar por Nombre + Teléfono + ID para que nunca se pisen homónimos
    opciones_edicion = {
        f"{row['Nombre']} ({row['Telefono'] if row['Telefono'] else 'Sin tel'}) — Fila #{int(row['RowID'])+1}": int(row["RowID"])
        for _, row in df.sort_values("Nombre").iterrows()
    }

    cliente_label_sel = st.selectbox("Buscá y seleccioná el cliente", list(opciones_edicion.keys()))

    if cliente_label_sel:
        sel_id      = opciones_edicion[cliente_label_sel]
        datos       = df_raw.iloc[sel_id]
        esta_pagado = "[P]" in str(datos["Mes"]).upper()
        mes_limpio  = str(datos["Mes"]).split("[")[0].strip().upper()

        st.write("---")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            nuevo_nombre = st.text_input("Nombre Completo", datos["Nombre"], key=f"ed_nom_{sel_id}")
            nuevo_tel    = st.text_input("Teléfono", datos["Telefono"], key=f"ed_tel_{sel_id}")
        with col_m2:
            apps_disponibles = ["ON PLAY", "MarTV", "MULTI GEMA"]
            app_actual = str(datos.get("Apps", "ON PLAY"))
            if app_actual not in apps_disponibles:
                apps_disponibles.append(app_actual)
            nuevo_equipo = st.selectbox("App", apps_disponibles, index=apps_disponibles.index(app_actual), key=f"ed_app_{sel_id}")
            mes_idx      = MESES_LISTA.index(mes_limpio) if mes_limpio in MESES_LISTA else mes_default_idx
            nuevo_mes    = st.selectbox("Mes de Facturación", MESES_LISTA, index=mes_idx, key=f"ed_mes_{sel_id}")
            nuevo_pagado = st.checkbox("Registrar como PAGADO", value=esta_pagado, key=f"ed_pag_{sel_id}")

        mes_salida = f"{nuevo_mes} [P]" if nuevo_pagado else nuevo_mes

        col_btn_save, col_btn_dup, _ = st.columns([1.5, 1.8, 2])
        with col_btn_save:
            if st.button("💾 Guardar Cambios", type="primary", use_container_width=True):
                df_upd = df_raw.copy()
                df_upd.at[sel_id, "Nombre"]   = nuevo_nombre.strip().upper()
                df_upd.at[sel_id, "Telefono"] = nuevo_tel.strip()
                df_upd.at[sel_id, "Apps"]     = nuevo_equipo
                df_upd.at[sel_id, "Mes"]      = mes_salida
                df_upd.at[sel_id, "Vendedor"] = "PROPIO"
                with st.spinner("Guardando cambios..."):
                    ok = save_df_instant(df_upd, f"Editar cliente {nuevo_nombre.strip().upper()}")
                if ok:
                    st.success(f"¡Datos de {nuevo_nombre.strip().upper()} actualizados!")
                    st.rerun()

        with col_btn_dup:
            nombre_2da = f"{datos['Nombre'].strip().upper()} 2"
            if st.button(f"➕ Crear 2da Cuenta ({nombre_2da})", use_container_width=True, help="Crea otra cuenta con el mismo teléfono y marca pagada"):
                nueva_2da = {
                    "Nombre": nombre_2da,
                    "Telefono": str(datos["Telefono"]).strip(),
                    "Apps": nuevo_equipo,
                    "Mes": f"{mes_activo_default} [P]",
                    "Vendedor": "PROPIO"
                }
                df_nuevo = pd.concat([df_raw, pd.DataFrame([nueva_2da])], ignore_index=True)
                with st.spinner("Creando segunda cuenta..."):
                    ok = save_df_instant(df_nuevo, f"Crear 2da cuenta {nombre_2da}")
                if ok:
                    st.success(f"¡Segunda cuenta '{nombre_2da}' creada y marcada como PAGADA!")
                    st.rerun()


# ===================================================
# TAB 4 — AVISOS WHATSAPP (PAGINADO TURBO)
# ===================================================
with tab_whatsapp:
    st.subheader("📝 Configurar Mensaje de Cobro por WhatsApp")

    default_template = (
        "📺 *MAR TV — Abono {mes}*\n\n"
        "¡Hola *{nombre}*! Te recordamos que se encuentra habilitado el pago del abono mensual de *{mes} (${monto})*.\n\n"
        "💳 *Alias oficial:* streamvision.mp\n"
        "👤 *Titular:* Maria Celeste Laitan\n\n"
        "📩 _Una vez realizada la transferencia, por favor envianos el comprobante por este chat para registrar tu pago._ ¡Muchas gracias! 🙌"
    )

    mensaje_template = st.text_area(
        "Editá el texto del mensaje. Podés usar: {nombre}, {mes}, {monto}",
        value=default_template,
        height=160
    )

    mes_aviso = st.selectbox(
        "📅 Mes a incluir en el aviso:",
        MESES_LISTA,
        index=mes_default_idx
    )

    st.write("---")
    with st.expander("🖼️ Imagen / Placa de Abono del Mes (Opcional)", expanded=False):
        recibo_sha = load_image_cached(token_hash)
        adjuntar_link = False
        if recibo_sha:
            st.image(f"{RECIBO_RAW_URL}?v={recibo_sha[:8]}", caption="Placa cargada actualmente", width=320)
            adjuntar_link = st.checkbox("🔗 Adjuntar link de la imagen al mensaje", value=False)
            if st.button("🗑️ Eliminar imagen actual", type="secondary"):
                if github_delete_file("recibo_mes.png", recibo_sha, "Eliminar recibo del mes"):
                    st.success("Imagen eliminada.")
                    st.rerun()
        uploaded_file = st.file_uploader("Subir nueva placa del mes:", type=["png", "jpg", "jpeg"])
        if uploaded_file is not None:
            if st.button("💾 Guardar imagen en la nube"):
                if github_write_image("recibo_mes.png", uploaded_file.read(), recibo_sha):
                    st.success("¡Imagen actualizada!")
                    st.rerun()

    whatsapp_platform = st.radio(
        "Abrir WhatsApp en:",
        ["WhatsApp Web (Recomendado para PC / Google Chrome)", "WhatsApp App / Celular (wa.me)"],
        horizontal=True
    )

    st.write("---")
    st.subheader("👥 Clientes Pendientes de Pago")

    df_pendientes = df[df["Pagado"] == False].copy()

    if df_pendientes.empty:
        st.success("🎉 ¡No hay clientes pendientes de pago!")
    else:
        col_wa_search, col_wa_pag = st.columns([2.5, 1])
        with col_wa_search:
            busqueda_wa = st.text_input("🔍 Buscar cliente pendiente por nombre o teléfono", key="wa_busqueda")
        if busqueda_wa:
            q_wa = busqueda_wa.strip()
            df_pendientes = df_pendientes[
                df_pendientes["Nombre"].str.contains(q_wa, case=False, na=False) |
                df_pendientes["Telefono"].str.contains(q_wa, case=False, na=False)
            ]

        total_pend_filt = len(df_pendientes)
        wa_por_pagina = 30
        total_pag_wa = max(1, math.ceil(total_pend_filt / wa_por_pagina))

        with col_wa_pag:
            if total_pag_wa > 1:
                pag_wa = st.number_input(f"Página (1 a {total_pag_wa})", min_value=1, max_value=total_pag_wa, value=1, step=1, key="pag_wa_num")
            else:
                pag_wa = 1

        st.write(f"Hay **{total_pend_filt}** clientes pendientes (mostrando página {pag_wa} de {total_pag_wa}).")

        ini_wa = (pag_wa - 1) * wa_por_pagina
        df_wa_page = df_pendientes.iloc[ini_wa : ini_wa + wa_por_pagina]

        col_name, col_tel, col_actions = st.columns([2.8, 1.8, 2.4])
        with col_name: st.markdown("**# / Cliente**")
        with col_tel:  st.markdown("**Teléfono**")
        with col_actions: st.markdown("**Acciones**")
        st.divider()

        for _, row in df_wa_page.iterrows():
            r_id      = int(row["RowID"])
            c_name    = row["Nombre"]
            c_tel     = row["Telefono"]
            mes_limp  = str(row["Mes_Limpio"]) if row["Mes_Limpio"] else mes_activo_default
            formatted_phone = format_argentina_phone(c_tel)

            try:
                mensaje_final = mensaje_template.format(
                    nombre=c_name.title(),
                    mes=mes_aviso.title(),
                    monto=f"{abono_general:,.0f}"
                )
            except Exception:
                mensaje_final = mensaje_template

            encoded_msg = urllib.parse.quote(mensaje_final)
            if whatsapp_platform.startswith("WhatsApp Web"):
                wa_url = f"https://web.whatsapp.com/send?phone={formatted_phone}&text={encoded_msg}"
            else:
                wa_url = f"https://wa.me/{formatted_phone}?text={encoded_msg}"

            col_r_name, col_r_tel, col_r_actions = st.columns([2.8, 1.8, 2.4])
            with col_r_name:
                st.write(f"**#{r_id+1}** — {c_name}")
            with col_r_tel:
                st.write(c_tel if (c_tel and str(c_tel).strip() and str(c_tel) != "nan") else "⚠️ Sin Tel")
            with col_r_actions:
                col_btn_send, col_btn_pay = st.columns([1.2, 1.0])
                with col_btn_send:
                    if formatted_phone:
                        st.link_button("✉️ Enviar", wa_url, use_container_width=True)
                    else:
                        st.button("❌ Sin Tel", disabled=True, use_container_width=True, key=f"dis_wa_{r_id}")
                with col_btn_pay:
                    if st.button("✅ Pagó", key=f"pay_wa_{r_id}", use_container_width=True):
                        df_upd = df_raw.copy()
                        df_upd.at[r_id, "Mes"] = f"{mes_limp} [P]"
                        ok = save_df_instant(df_upd, f"Pago {c_name}")
                        if ok:
                            st.rerun()
