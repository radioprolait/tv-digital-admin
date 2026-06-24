import streamlit as st
import pandas as pd
import json
import os

# Configuración de página
st.set_page_config(page_title="Administración TV Digital", page_icon="📺", layout="wide")

# Estilos CSS personalizados para estética premium (modo oscuro/azul)
st.markdown("""
    <style>
    /* Estilos para tarjetas métricas */
    .metric-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
        margin-bottom: 15px;
    }
    .metric-title {
        font-size: 14px;
        color: #94a3b8;
        margin-bottom: 8px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 32px;
        color: #38bdf8;
        font-weight: 700;
    }
    .metric-value.green {
        color: #34d399;
    }
    .metric-value.orange {
        color: #fb923c;
    }
    .metric-value.purple {
        color: #c084fc;
    }
    .metric-subtitle {
        font-size: 12px;
        color: #64748b;
        margin-top: 4px;
    }
    </style>
""", unsafe_allow_html=True)

CSV_FILE = "base_datos_tv.csv"
CONFIG_FILE = "vendedores_config.json"

# --- FUNCIONES DE PERSISTENCIA Y CARGA ---

def get_csv_encoding(file_path):
    if os.path.exists(file_path):
        for enc in ['utf-8', 'latin1', 'cp1252']:
            try:
                # Intentamos leer TODO el archivo para garantizar que decodifique completo sin errores
                pd.read_csv(file_path, encoding=enc)
                return enc
            except Exception:
                continue
    return 'utf-8'

@st.cache_data
def load_data_raw(file_path, file_mtime):
    if os.path.exists(file_path):
        enc = get_csv_encoding(file_path)
        # Leemos el archivo CSV con la codificación detectada
        df = pd.read_csv(file_path, encoding=enc)
        # Limpiamos los textos
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace('nan', '')
        return df
    else:
        return pd.DataFrame(columns=["Nombre", "Telefono", "Equipo", "Mes", "Vendedor"])

def save_data(df, file_path):
    enc = get_csv_encoding(file_path)
    df.to_csv(file_path, index=False, encoding=enc)
    st.cache_data.clear()


def load_sellers_config(df):
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                migrated = False
                # Migración de configuración antigua a la nueva estructura "precio_vendedor"
                for v, data in config.items():
                    if "valor_comision" in data:
                        val_com = data.get("valor_comision", 0)
                        if v.upper() == 'PROPIO':
                            data["precio_vendedor"] = 10000.0
                        elif v.upper() == 'ALEXIS':
                            data["precio_vendedor"] = 5000.0
                        elif v.upper() in ['MICA', 'NOE', 'EUGE']:
                            data["precio_vendedor"] = 4000.0
                        else:
                            data["precio_vendedor"] = 10000.0 - val_com if val_com < 10000 else 4000.0
                        del data["valor_comision"]
                        if "tipo_comision" in data:
                            del data["tipo_comision"]
                        migrated = True
                if migrated:
                    save_sellers_config(config)
                return config
        except Exception:
            pass
            
    # Si no existe, creamos la configuración inicial basada en los vendedores del CSV
    vendedores_detectados = []
    if 'Vendedor' in df.columns:
        vendedores_detectados = [v for v in df['Vendedor'].unique() if v]
    
    if not vendedores_detectados:
        vendedores_detectados = ['PROPIO', 'NOE', 'EUGE', 'MICA', 'ALEXIS']
        
    config = {}
    for v in vendedores_detectados:
        if v.upper() == 'PROPIO':
            precio = 10000.0
        elif v.upper() == 'ALEXIS':
            precio = 5000.0
        elif v.upper() in ['MICA', 'NOE', 'EUGE']:
            precio = 4000.0
        else:
            precio = 4000.0
            
        config[v] = {
            "nombre": v,
            "precio_vendedor": precio
        }
        
    save_sellers_config(config)
    return config

def save_sellers_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)



# --- INICIO DE LA APLICACIÓN ---

if not os.path.exists(CSV_FILE):
    st.error(f"❌ No se encontró el archivo '{CSV_FILE}' en la carpeta actual.")
    st.info("Por favor, asegúrate de colocar el archivo de base de datos en la carpeta del proyecto.")
    st.stop()

# Cargar datos e invalidar caché si el archivo cambia en disco
file_mtime = os.path.getmtime(CSV_FILE) if os.path.exists(CSV_FILE) else 0
df_raw = load_data_raw(CSV_FILE, file_mtime)

# Cargar configuración de vendedores
vendedores_config = load_sellers_config(df_raw)

# Sidebar - Configuración del Abono General
st.sidebar.title("⚙️ Configuración")
abono_general = st.sidebar.number_input(
    "Valor del Abono Mensual ($)", 
    min_value=0, 
    value=5000, 
    step=500, 
    help="El precio de suscripción mensual cobrado a cada cliente."
)

st.title("📺 Panel de Control - TV Digital")
st.write("Sistema de visualización, cobros y cálculo de comisiones.")

# --- PREPROCESAMIENTO DE DATOS ---
df = df_raw.copy()

# Determinar estado de pago
# Si la columna 'Mes' contiene '[P]' o '[p]' (ej: 'MAYO [P]'), está pagado.
df['Pagado'] = df['Mes'].apply(lambda x: '[P]' in str(x).upper())

# Mes limpio (sin el indicador de pago)
df['Mes_Limpio'] = df['Mes'].apply(lambda x: str(x).split('[')[0].strip().upper())

# Calcular lo que te paga el vendedor y la comisión por fila
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

# Comisión de la fila (lo que se queda el vendedor)
df['Comision_Valor'] = df['Monto_Facturado'] - df['Precio_Vendedor']
# La ganancia de la fila es lo que te pagan a vos (Precio_Vendedor)
df['Ganancia_Valor'] = df['Precio_Vendedor']


# Pestañas principales
tab_dashboard, tab_clientes, tab_pagos, tab_vendedores = st.tabs([
    "📊 Tablero General", 
    "👥 Clientes y Filtros", 
    "💰 Registrar Pagos / CRUD", 
    "⚙️ Gestión de Vendedores"
])

# ----------------- TABS 1: TABLERO GENERAL -----------------
with tab_dashboard:
    st.subheader("📈 Resumen del Negocio")
    
    # Cálculos globales
    total_clientes = len(df)
    total_pagos = len(df[df['Pagado'] == True])
    total_impagos = len(df[df['Pagado'] == False])
    
    # Bruto facturado a clientes
    recaudacion_bruta_clientes = total_pagos * abono_general
    
    # Neto recibido por el administrador (lo que te pagan a vos)
    plata_cobrada_neta = df[df['Pagado'] == True]['Precio_Vendedor'].sum()
    plata_pendiente_neta = df[df['Pagado'] == False]['Precio_Vendedor'].sum()
    
    # Comisiones retenidas por vendedores
    comisiones_pagos = df[df['Pagado'] == True]['Comision_Valor'].sum()
    
    # Tarjetas métricas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Clientes Totales</div>
                <div class="metric-value">{total_clientes}</div>
                <div class="metric-subtitle">Pagados: {total_pagos} | Pendientes: {total_impagos}</div>
            </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Tu Plata Cobrada (Neto)</div>
                <div class="metric-value green">${plata_cobrada_neta:,.0f}</div>
                <div class="metric-subtitle">Bruto Clientes: ${recaudacion_bruta_clientes:,.0f}</div>
            </div>
        """, unsafe_allow_html=True)
        
    with col3:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Tu Plata Pendiente (Neto)</div>
                <div class="metric-value orange">${plata_pendiente_neta:,.0f}</div>
                <div class="metric-subtitle">De {total_impagos} clientes impagos</div>
            </div>
        """, unsafe_allow_html=True)
        
    with col4:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Comisiones Vendedores</div>
                <div class="metric-value purple">${comisiones_pagos:,.0f}</div>
                <div class="metric-subtitle">Retenido por los vendedores</div>
            </div>
        """, unsafe_allow_html=True)
        
    st.divider()
    
    # Alta Rápida de Nuevos Clientes
    with st.expander("➕ **PUM! AGREGAR NUEVO CLIENTE (Alta Rápida)**", expanded=False):
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            c_nombre = st.text_input("Nombre Completo", key="quick_c_nombre")
            c_tel = st.text_input("Teléfono", key="quick_c_tel")
            c_vendedor = st.selectbox("Vendedor Asignado", list(vendedores_config.keys()), key="quick_c_vendedor")
        with col_c2:
            c_equipo = st.selectbox("Equipo", ["ANDROID", "Sin Asignar"], key="quick_c_equipo")
            c_mes_nombre = st.selectbox("Mes de Facturación", ["MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"], index=1, key="quick_c_mes") # Default a JUNIO
            c_pagado = st.checkbox("¿Registrar como PAGADO?", value=False, key="quick_c_pagado")
            
        if st.button("🚀 PUM! CREAR CLIENTE", key="quick_c_btn"):
            if not c_nombre.strip():
                st.error("Por favor, ingresá un nombre para el cliente.")
            else:
                c_mes_salida = f"{c_mes_nombre} [P]" if c_pagado else c_mes_nombre
                nueva_fila = {
                    "Nombre": c_nombre.strip().upper(),
                    "Telefono": c_tel.strip(),
                    "Equipo": c_equipo,
                    "Mes": c_mes_salida,
                    "Vendedor": c_vendedor
                }
                
                # Leer base de datos cruda del disco
                df_raw_actual = load_data_raw(CSV_FILE, os.path.getmtime(CSV_FILE))
                # Concatenar el nuevo registro
                df_raw_actual = pd.concat([df_raw_actual, pd.DataFrame([nueva_fila])], ignore_index=True)
                # Guardar cambios
                save_data(df_raw_actual, CSV_FILE)
                st.success(f"¡Cliente {c_nombre.upper()} agregado con éxito!")
                st.rerun()
                
    st.divider()
    
    # Métricas por vendedor
    st.subheader("👤 Rentabilidad y Métricas por Vendedor")
    
    vendedor_stats = []
    for vend, conf in vendedores_config.items():
        sub_df = df[df['Vendedor'] == vend]
        c_totales = len(sub_df)
        c_pagos = len(sub_df[sub_df['Pagado'] == True])
        c_pendientes = len(sub_df[sub_df['Pagado'] == False])
        
        cobrado_clientes = c_pagos * abono_general
        recaudacion_neta = sub_df[sub_df['Pagado'] == True]['Precio_Vendedor'].sum()
        recaudacion_pendiente = sub_df[sub_df['Pagado'] == False]['Precio_Vendedor'].sum()
        comisiones = sub_df[sub_df['Pagado'] == True]['Comision_Valor'].sum()
        
        margen = (recaudacion_neta / cobrado_clientes * 100) if cobrado_clientes > 0 else 0.0
        
        vendedor_stats.append({
            "Vendedor": vend,
            "Clientes Totales": c_totales,
            "Clientes Pagos": c_pagos,
            "Clientes Pendientes": c_pendientes,
            "Cobrado Clientes ($)": cobrado_clientes,
            "Comisión Vendedor ($)": comisiones,
            "Tu Recaudación Real ($)": recaudacion_neta,
            "Margen de Ganancia (%)": f"{margen:.1f}%"
        })
        
    df_vendedores = pd.DataFrame(vendedor_stats)
    
    # Mostrar tabla de vendedores
    st.dataframe(df_vendedores, use_container_width=True, hide_index=True)
    
    # Gráficos sencillos
    st.subheader("📊 Comparación Visual")
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.write("**Clientes Pagos vs Pendientes por Vendedor**")
        df_chart_data = df_vendedores.set_index("Vendedor")[["Clientes Pagos", "Clientes Pendientes"]]
        st.bar_chart(df_chart_data)
        
    with col_chart2:
        st.write("**Tu Recaudación Real por Vendedor ($)**")
        df_chart_money = df_vendedores.set_index("Vendedor")[["Tu Recaudación Real ($)"]]
        st.bar_chart(df_chart_money)


# ----------------- TABS 2: CLIENTES Y FILTROS -----------------
with tab_clientes:
    st.subheader("🔍 Filtros de Búsqueda")
    
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    with col_f1:
        busqueda = st.text_input("Buscar cliente por nombre o teléfono")
        
    with col_f2:
        vendedores_options = ["Todos"] + list(vendedores_config.keys())
        filtro_vendedor = st.selectbox("Filtrar por Vendedor", vendedores_options)
        
    with col_f3:
        filtro_estado = st.selectbox("Estado de Pago", ["Todos", "Pagados", "Pendientes"])
        
    with col_f4:
        equipos_detectados = ["Todos"] + [eq for eq in df['Equipo'].unique() if eq]
        filtro_equipo = st.selectbox("Filtrar por Equipo", equipos_detectados)
        
    # Aplicar filtros
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
        
    # Mostrar base limpia
    st.write(f"Mostrando **{len(df_filtrado)}** clientes de un total de **{len(df)}**.")
    
    # Preparar tabla para visualización limpia
    df_vista = df_filtrado[["Nombre", "Telefono", "Equipo", "Mes", "Vendedor"]].copy()
    
    # Función para colorear el estado de pago de forma premium
    def color_pago(val):
        color = '#10b981' if '[P]' in str(val).upper() else '#f97316'
        return f'background-color: {color}; color: white; font-weight: bold; border-radius: 4px;'
        
    # Aplicar estilos
    try:
        styled_df = df_vista.style.map(color_pago, subset=['Mes'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    except Exception:
        # En versiones antiguas de pandas se usaba applymap
        styled_df = df_vista.style.applymap(color_pago, subset=['Mes'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

# ----------------- TABS 3: REGISTRAR PAGOS / CRUD -----------------
with tab_pagos:
    subtab_modificar, subtab_crear, subtab_eliminar = st.tabs([
        "💳 Modificar Cliente / Registrar Pago", 
        "➕ Agregar Nuevo Cliente",
        "❌ Eliminar Cliente"
    ])
    
    # --- SUBTAB: MODIFICAR / REGISTRAR PAGO ---
    with subtab_modificar:
        st.subheader("Selecciona un Cliente para Gestionar")
        
        # Lista ordenada de clientes
        lista_clientes = sorted(df['Nombre'].tolist())
        cliente_seleccionado = st.selectbox("Elegí el cliente", lista_clientes)
        
        if cliente_seleccionado:
            # Obtener datos del cliente actual
            datos_cliente = df_raw[df_raw['Nombre'] == cliente_seleccionado].iloc[0]
            
            # Determinar si está pagado actualmente
            esta_pagado = '[P]' in str(datos_cliente['Mes']).upper()
            mes_limpio_cliente = str(datos_cliente['Mes']).split('[')[0].strip().upper()
            
            st.write("---")
            col_m1, col_m2 = st.columns(2)
            
            with col_m1:
                nuevo_nombre = st.text_input("Nombre Completo", datos_cliente['Nombre'])
                nuevo_tel = st.text_input("Teléfono", datos_cliente['Telefono'])
                
                # Cargar selector de vendedor con las opciones actuales
                lista_vendedores = list(vendedores_config.keys())
                vendedor_actual = datos_cliente['Vendedor'] if datos_cliente['Vendedor'] in lista_vendedores else lista_vendedores[0]
                nuevo_vendedor = st.selectbox("Vendedor Asignado", lista_vendedores, index=lista_vendedores.index(vendedor_actual))
                
            with col_m2:
                nuevo_equipo = st.selectbox("Equipo", ["ANDROID", "Sin Asignar"], index=0 if datos_cliente['Equipo'] == "ANDROID" else 1)
                
                meses_lista = ["MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE", "ENERO", "FEBRERO", "MARZO", "ABRIL"]
                mes_actual_index = meses_lista.index(mes_limpio_cliente) if mes_limpio_cliente in meses_lista else 0
                nuevo_mes_nombre = st.selectbox("Mes de Facturación", meses_lista, index=mes_actual_index)
                
                nuevo_estado_pago = st.checkbox("¿Registrar como PAGADO?", value=esta_pagado)
                
            # Formatear el mes de salida
            mes_salida = f"{nuevo_mes_nombre} [P]" if nuevo_estado_pago else nuevo_mes_nombre
            
            if st.button("💾 Guardar Cambios del Cliente"):
                # Encontrar el índice en df_raw
                idx = df_raw[df_raw['Nombre'] == cliente_seleccionado].index[0]
                
                # Actualizar datos
                df_raw.at[idx, 'Nombre'] = nuevo_nombre.strip().upper()
                df_raw.at[idx, 'Telefono'] = nuevo_tel.strip()
                df_raw.at[idx, 'Equipo'] = nuevo_equipo
                df_raw.at[idx, 'Mes'] = mes_salida
                df_raw.at[idx, 'Vendedor'] = nuevo_vendedor
                
                # Guardar en CSV
                save_data(df_raw, CSV_FILE)
                st.success(f"¡Datos de {cliente_seleccionado} actualizados correctamente!")
                st.rerun()

    # --- SUBTAB: AGREGAR CLIENTE ---
    with subtab_crear:
        st.subheader("Registrar un Nuevo Cliente")
        
        col_c1, col_c2 = st.columns(2)
        
        with col_c1:
            c_nombre = st.text_input("Nombre Completo (Nuevo)")
            c_tel = st.text_input("Teléfono (Nuevo)")
            c_vendedor = st.selectbox("Vendedor (Nuevo)", list(vendedores_config.keys()))
            
        with col_c2:
            c_equipo = st.selectbox("Equipo (Nuevo)", ["ANDROID", "Sin Asignar"])
            c_mes_nombre = st.selectbox("Mes de Facturación (Nuevo)", ["MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"])
            c_pagado = st.checkbox("¿Registrar como PAGADO inicialmente?")
            
        c_mes_salida = f"{c_mes_nombre} [P]" if c_pagado else c_mes_nombre
        
        if st.button("➕ Crear y Guardar Cliente"):
            if not c_nombre.strip():
                st.error("Por favor, ingresá un nombre válido.")
            else:
                # Crear nueva fila
                nueva_fila = {
                    "Nombre": c_nombre.strip().upper(),
                    "Telefono": c_tel.strip(),
                    "Equipo": c_equipo,
                    "Mes": c_mes_salida,
                    "Vendedor": c_vendedor
                }
                
                # Añadir al df_raw
                df_raw = pd.concat([df_raw, pd.DataFrame([nueva_fila])], ignore_index=True)
                
                # Guardar
                save_data(df_raw, CSV_FILE)
                st.success(f"¡Cliente {c_nombre.upper()} agregado con éxito!")
                st.rerun()

    # --- SUBTAB: ELIMINAR CLIENTE ---
    with subtab_eliminar:
        st.subheader("Eliminar un Cliente de la Base de Datos")
        
        cliente_a_eliminar = st.selectbox("Selecciona el cliente a dar de baja", sorted(df['Nombre'].tolist()), key="eliminar_sel")
        
        st.warning(f"⚠️ Atención: Estás por eliminar definitivamente a **{cliente_a_eliminar}**.")
        confirmar_eliminacion = st.checkbox("Confirmo que deseo borrar este registro de forma permanente.")
        
        if st.button("🗑️ Eliminar Registro"):
            if confirmar_eliminacion:
                # Filtrar fuera el registro
                df_raw = df_raw[df_raw['Nombre'] != cliente_a_eliminar]
                # Guardar
                save_data(df_raw, CSV_FILE)
                st.success(f"¡El cliente {cliente_a_eliminar} fue removido de la base de datos!")
                st.rerun()
            else:
                st.error("Debes marcar la casilla de confirmación antes de eliminar.")

# ----------------- TABS 4: GESTIÓN DE VENDEDORES -----------------
with tab_vendedores:
    st.subheader("⚙️ Configuración y Adición de Vendedores")
    
    col_v1, col_v2 = st.columns([1, 2])
    
    # Columna 1: Crear / Añadir un vendedor nuevo
    with col_v1:
        st.markdown("### ➕ Añadir Nuevo Vendedor")
        nuevo_vendedor_nombre = st.text_input("Nombre del Vendedor").strip().upper()
        precio_nuevo = st.number_input("Lo que te paga por cliente ($)", min_value=0.0, value=4000.0, step=500.0)
        
        if st.button("Registrar Vendedor"):
            if not nuevo_vendedor_nombre:
                st.error("Escribe un nombre para el vendedor.")
            elif nuevo_vendedor_nombre in vendedores_config:
                st.error("Este vendedor ya existe.")
            else:
                # Agregar a la estructura de configuración
                vendedores_config[nuevo_vendedor_nombre] = {
                    "nombre": nuevo_vendedor_nombre,
                    "precio_vendedor": precio_nuevo
                }
                save_sellers_config(vendedores_config)
                st.success(f"¡Vendedor '{nuevo_vendedor_nombre}' agregado!")
                st.rerun()
                
    # Columna 2: Mostrar y Editar Vendedores Existentes
    with col_v2:
        st.markdown("### 📋 Vendedores Registrados y Precios Mayoristas")
        
        # Hacemos una copia para guardar los campos modificados
        vendedores_editados = {}
        
        for vend, datos in list(vendedores_config.items()):
            with st.expander(f"👤 Vendedor: {vend}", expanded=True):
                col_e1, col_e2 = st.columns([2, 1])
                
                with col_e1:
                    # Permitir renombrar al vendedor
                    nombre_editado = st.text_input("Nombre", datos.get("nombre", vend), key=f"nom_{vend}").strip().upper()
                with col_e2:
                    precio_editado = st.number_input("Monto que te paga ($)", min_value=0.0, 
                                                    value=float(datos.get("precio_vendedor", 4000.0 if vend != 'PROPIO' else 10000.0)),
                                                    key=f"prc_{vend}")
                
                # Botón de eliminar vendedor
                eliminar_vend = st.button(f"🗑️ Quitar {vend}", key=f"del_{vend}")
                
                if eliminar_vend:
                    if len(vendedores_config) <= 1:
                        st.error("No puedes eliminar todos los vendedores. Debe quedar al menos uno.")
                    else:
                        # Remover de la configuración
                        del vendedores_config[vend]
                        save_sellers_config(vendedores_config)
                        st.success(f"¡Vendedor '{vend}' eliminado!")
                        st.rerun()
                else:
                    vendedores_editados[nombre_editado] = {
                        "nombre": nombre_editado,
                        "precio_vendedor": precio_editado
                    }
                    
        # Botón para guardar todos los cambios de edición
        if st.button("💾 Guardar Configuración de Vendedores"):
            save_sellers_config(vendedores_editados)
            st.success("¡Configuración de vendedores guardada con éxito!")
            st.rerun()

