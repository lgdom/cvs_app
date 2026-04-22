import streamlit as st
import pandas as pd
from datetime import datetime
from src.services.therion_service import TherionService

def render(df_productos, df_clientes):
    st.header("💳 Gestión de Cobro (Estado de Cuenta)")
    
    # --- AUTH ---
    if "erp_authorized_cobro" not in st.session_state:
        st.session_state.erp_authorized_cobro = False

    if not st.session_state.erp_authorized_cobro:
        st.warning("🔒 Esta sección requiere autorización para consultar estados de cuenta.")
        pin_input = st.text_input("Introduce tu PIN de Cobro:", type="password")
        
        # Buscar en raíz o dentro del bloque gcp por error de formato TOML
        authorized_pin = st.secrets.get("SYNC_PIN")
        if not authorized_pin and "gcp_service_account" in st.secrets:
            authorized_pin = st.secrets["gcp_service_account"].get("SYNC_PIN")
        if not authorized_pin: authorized_pin = "1234"
        
        if st.button("Validar Acceso", width="stretch"):
            if pin_input == authorized_pin:
                st.session_state.erp_authorized_cobro = True
                st.success("Acceso concedido.")
                st.rerun()
            else:
                st.error("PIN incorrecto.")
        return
        
    if "therion_service" not in st.session_state:
        st.session_state.therion_service = TherionService()
        
    auth_service = st.session_state.therion_service
    
    if not auth_service.logged_in:
        user = st.secrets.get("THERION_USER")
        pwd = st.secrets.get("THERION_PWD")
        
        # Robust fetch
        if not user and "gcp_service_account" in st.secrets:
            user = st.secrets["gcp_service_account"].get("THERION_USER")
            pwd = st.secrets["gcp_service_account"].get("THERION_PWD")
            
        if not user or not pwd:
            claves_detectadas = ", ".join(list(st.secrets.keys()))
            st.error(f"❌ Credenciales del ERP no configuradas. Las claves que Streamlit está detectando son: {claves_detectadas}. (Asegúrate de no usar comillas en los nombres de las variables y guardarlo sin espacios iniciales).")
            return
            
        with st.spinner("Autenticando en Therion..."):
            success, msg = auth_service.login(user, pwd)
            if not success:
                st.error(f"❌ Fallo de conexión: {msg}")
                return
    
    # --- FETCH DATA ---
    st.sidebar.divider()
    if st.sidebar.button("🔄 Refrescar Estado de Cuenta", type="primary"):
        st.session_state.df_estado_cuenta = None
        
    if 'df_estado_cuenta' not in st.session_state:
        st.session_state.df_estado_cuenta = None
        
    if st.session_state.df_estado_cuenta is None:
        with st.spinner("📥 Descargando reporte de estado de cuenta desde el ERP..."):
            df_cuenta, msg = auth_service.get_reporte_estado_cuenta()
            if df_cuenta is not None:
                st.session_state.df_estado_cuenta = df_cuenta
            else:
                st.error(f"No se pudo obtener la información: {msg}")
                return
                
    df = st.session_state.df_estado_cuenta.copy()
    
    if df.empty:
        st.info("No hay deudas pendientes registradas en este periodo.")
        return
        
    # --- PROCESS DATA ---
    # 1. Eliminar filas vacías o que sean ruido del paginador (filas que dicen "1", "2" en el folio)
    # También eliminamos filas donde el Folio sea muy corto (ruido de ASP.NET)
    df = df[df['Folio'].notna()].copy()
    df['Folio_str'] = df['Folio'].astype(str).str.replace('.0', '', regex=False).str.strip()
    df = df[~df['Folio_str'].isin(['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'])]
    
    # Limpiar montos
    df['Saldo_num'] = df['Saldo'].astype(str).str.replace('$', '').str.replace(',', '').apply(pd.to_numeric, errors='coerce').fillna(0)
    
    # Procesar fechas para calcular precisión de vencimientos
    df['Fecha_Venc'] = pd.to_datetime(df['Vencimiento'], format='%d/%m/%Y', errors='coerce')
    hoy = pd.to_datetime('today').normalize()
    
    # Recalcular la "Vigencia" matemáticamente
    df['Vigencia_num'] = (df['Fecha_Venc'] - hoy).dt.days.fillna(0).get(0, 0) # Fallback handled by apply
    df['Vigencia_num'] = (df['Fecha_Venc'] - hoy).dt.days.fillna(0).astype(int)
    
    saldo_vencido = df[df['Vigencia_num'] < 0]['Saldo_num'].sum()
    saldo_por_vencer = df[df['Vigencia_num'] >= 0]['Saldo_num'].sum()
    saldo_total = df['Saldo_num'].sum()
    facturas_pendientes = len(df)
    
    # --- METRICS ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Saldo Total", f"${saldo_total:,.2f}")
    c2.metric("🚨 Saldo Vencido", f"${saldo_vencido:,.2f}")
    c3.metric("⏳ Por Vencer", f"${saldo_por_vencer:,.2f}")
    c4.metric("📄 Facturas", facturas_pendientes)
    
    # --- FILTROS ---
    st.subheader("Buscador")
    filtro_cliente = st.text_input("Buscar factura (Cliente, Folio, etc):", "")
    
    if filtro_cliente:
        mask = (
            df['Cliente'].astype(str).str.contains(filtro_cliente, case=False, na=False) |
            df['Razón Social'].astype(str).str.contains(filtro_cliente, case=False, na=False) |
            df['Folio_str'].str.contains(filtro_cliente, case=False, na=False)
        )
        df_display = df[mask].copy()
    else:
        df_display = df.copy()
        
    # Ordenar por Vigencia (más vencidas arriba)
    df_display = df_display.sort_values(by=['Vigencia_num', 'Folio_str'], ascending=[True, False])
    
    # Formatear columnas para visualización (Quitar decimales de Folio y Vigencia)
    df_display['Folio'] = df_display['Folio_str']
    df_display['Vigencia'] = df_display['Vigencia_num']
    
    # Filtrar solo columnas esenciales para una vista más limpia
    cols_esenciales = ['Folio', 'Cliente', 'Fecha', 'Vencimiento', 'Importe', 'Saldo', 'Vigencia']
    df_display = df_display[cols_esenciales]
    
    # Función de color (usa el valor numérico interno)
    def style_rows(row):
        v = row['Vigencia']
        css = ''
        if v < 0:
            css = 'background-color: #ffcccc; color: #990000;' # Rojo (vencido)
        elif v <= 5:
            css = 'background-color: #fff3cd; color: #856404;' # Amarillo (por vencer pronto)
        else:
            css = 'background-color: #d4edda; color: #155724;' # Verde (al corriente)
        return [css if col == 'Vigencia' else '' for col in row.index]

    # Mostrar tabla con formato
    st.dataframe(
        df_display.style.apply(style_rows, axis=1),
        width='stretch',
        hide_index=True
    )
