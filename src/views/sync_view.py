import streamlit as st
import pandas as pd
from src.services.therion_service import TherionService
import time

def render(df_productos, df_clientes):
    st.header("🚀 Sincronizador ERP (Therion)")

    # --- SEGURIDAD: VERIFICACIÓN DE PIN ---
    if "erp_authorized" not in st.session_state:
        st.session_state.erp_authorized = False

    if not st.session_state.erp_authorized:
        st.warning("🔒 Esta sección requiere autorización.")
        pin_input = st.text_input("Introduce tu PIN de Sincronización:", type="password")
        
        # Robust PIN fetch
        authorized_pin = st.secrets.get("SYNC_PIN")
        if not authorized_pin and "gcp_service_account" in st.secrets:
            authorized_pin = st.secrets["gcp_service_account"].get("SYNC_PIN")
        if not authorized_pin: authorized_pin = "1234"
        
        if st.button("Validar Acceso", width="stretch"):
            if pin_input == authorized_pin:
                st.session_state.erp_authorized = True
                st.success("Acceso concedido.")
                st.rerun()
            else:
                st.error("PIN incorrecto.")
        return

    # --- INICIALIZACIÓN DE SERVICIO ---
    if "therion_service" not in st.session_state:
        st.session_state.therion_service = TherionService()
    
    auth_service = st.session_state.therion_service

    # --- LOGIN AUTOMÁTICO (Desde Secretos) ---
    if not auth_service.logged_in:
        # Revisamos si accidentalmente guardo las credenciales DENTRO del apartado [gcp_service_account]
        user = st.secrets.get("THERION_USER")
        pwd = st.secrets.get("THERION_PWD")
        if not user and "gcp_service_account" in st.secrets:
            user = st.secrets["gcp_service_account"].get("THERION_USER")
            pwd = st.secrets["gcp_service_account"].get("THERION_PWD")

        if not user or not pwd:
            claves_detectadas = ", ".join(list(st.secrets.keys()))
            st.error(f"❌ Credenciales del ERP no configuradas en Secretos. Claves detectadas nativas: {claves_detectadas}")
            return
        
        with st.spinner("Conectando con Therion ERP..."):
            success, msg = auth_service.login(user, pwd)
            if not success:
                st.error(f"❌ Fallo de conexión: {msg}")
                return
            st.toast("✅ Conexión establecida con el ERP")

    # --- SELECCIÓN DE PEDIDO ---
    pedidos_pendientes = st.session_state.get('pedidos_erp', [])
    
    with st.sidebar:
        st.divider()
        if st.button("🗑️ Reiniciar Sincronizador", type="primary", help="Borra todos los pedidos pendientes"):
            st.session_state.pedidos_erp = []
            st.rerun()
        
        if st.button("🔄 Resetear Sesión ERP", help="Forzar re-conexión y limpia caché de sesión"):
            if "therion_service" in st.session_state: del st.session_state.therion_service
            if "erp_authorized" in st.session_state: st.session_state.erp_authorized = False
            if "config_cliente_cache" in st.session_state: st.session_state.config_cliente_cache = {}
            st.toast("Sesión de ERP reiniciada")
            st.rerun()

    if not pedidos_pendientes:
        st.info("No hay ventas con existencia listas para sincronizar. Ve a 'Revisar Existencias' y usa el botón 'Sincronizar Venta (ERP)'.")
        return

    col_sel, col_del = st.columns([4, 1])
    with col_sel:
        nombres_pedidos = [f"{p['cli_cod']} - {p['cli_nom']} ({len(p['items'])} items)" for p in pedidos_pendientes]
        idx_pedido = st.selectbox("1. Selecciona la venta a sincronizar:", range(len(nombres_pedidos)), format_func=lambda x: nombres_pedidos[x])
    
    with col_del:
        st.write("") # Espaciador
        st.write("") # Espaciador
        if st.button("🗑️ Quitar"):
            st.session_state.pedidos_erp.pop(idx_pedido)
            st.rerun()

    pedido_selec = pedidos_pendientes[idx_pedido]
    st.divider()

    # --- CONFIGURACIÓN DINÁMICA DEL CLIENTE (PAGOS Y LISTAS DE PRECIOS) ---
    if "config_cliente_cache" not in st.session_state:
        st.session_state.config_cliente_cache = {}

    cli_cod = pedido_selec['cli_cod']
    
    if cli_cod not in st.session_state.config_cliente_cache:
        with st.spinner(f"Consultando listas y pagos para {cli_cod}..."):
            config, msg = auth_service.get_client_config(cli_cod)
            if config:
                st.session_state.config_cliente_cache[cli_cod] = config
            else:
                st.error(msg)
                st.session_state.config_cliente_cache[cli_cod] = {"metodos": [], "formas": [], "listas": []}

    config_cliente = st.session_state.config_cliente_cache[cli_cod]
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        metodos_txt = [opt['text'] for opt in config_cliente['metodos']]
        metodo_choice = st.selectbox("Método de Pago:", metodos_txt if metodos_txt else ["PPD Pago en parcialidades o diferido"])
        metodo_val = next((opt['value'] for opt in config_cliente['metodos'] if opt['text'] == metodo_choice), "3")
        
    with col_p2:
        formas_txt = [opt['text'] for opt in config_cliente['formas']]
        forma_pago_choice = st.selectbox("Forma de Pago:", formas_txt if formas_txt else ["99 Por definir"])
        forma_pago_val = next((opt['value'] for opt in config_cliente['formas'] if opt['text'] == forma_pago_choice), "99")

    # --- CONFIGURACIÓN DE PRECIOS ---
    st.subheader("2. Configuración de Precios")
    
    # Listas detectadas para este cliente
    listas_detectadas = [opt['text'] for opt in config_cliente['listas']]
    if not listas_detectadas:
        listas_detectadas = ["1", "2", "3", "3a", "4", "5", "5a", "9a", "13a"]
    
    col_l1, col_l2 = st.columns([3, 1])
    with col_l1:
        master_lista = st.selectbox("Lista de precios aplicada a todo el pedido:", listas_detectadas)
    with col_l2:
        st.write("") # Espaciador
        st.write("") # Espaciador
        if st.button("Aplicar a todos"):
            st.session_state.pedidos_erp[idx_pedido]['items']['lista_precio'] = master_lista
            st.rerun()

    items_df = pedido_selec['items'].copy()
    if "lista_precio" not in items_df.columns:
        items_df['lista_precio'] = master_lista
    
    st.info("💡 Tip: Solo se muestran las listas de precios que el ERP autoriza para este cliente.")
    edited_df = st.data_editor(
        items_df[['CODIGO', 'DESCRIPCION', 'SOLICITADA', 'lista_precio']],
        column_config={
            "lista_precio": st.column_config.SelectboxColumn(
                "Lista",
                options=listas_detectadas,
                required=True,
            ),
            "SOLICITADA": st.column_config.NumberColumn("Cant", disabled=True),
            "CODIGO": st.column_config.TextColumn("Código", disabled=True),
            "DESCRIPCION": st.column_config.TextColumn("Producto", disabled=True),
        },
        width='stretch',
        hide_index=True,
        num_rows="dynamic",
        key="editor_sincro"
    )

    if not edited_df.equals(items_df[['CODIGO', 'DESCRIPCION', 'SOLICITADA', 'lista_precio']]):
        st.session_state.pedidos_erp[idx_pedido]['items'] = edited_df.reset_index(drop=True)
        st.rerun()

    # --- DEBUG INFO ---
    with st.expander("🛠️ Debug Info (ERP)"):
        token_status = "✅ Activo" if auth_service.api_token else "❌ No disponible"
        st.write(f"**Token API Mobile:** {token_status}")
        if st.button("Ver Logs de Depuración"):
            try:
                with open("/tmp/debug_erp.txt", "r") as f:
                    st.code(f.read())
            except:
                st.warning("No hay logs disponibles todavía.")

    st.divider()

    # --- ACCIÓN FINAL ---
    if st.button("🔥 SINCRONIZAR CON THERION ERP", type="primary", width="stretch"):
        with st.status("Sincronizando con Therion ERP...") as status:
            status.update(label="Iniciando maniobra de inicialización (Comodín)...", state="running")
            
            success, msg = auth_service.sync_order(
                client_code=cli_cod,
                items_list=edited_df.to_dict('records'),
                payment_method_val=metodo_val,
                payment_form_val=forma_pago_val
            )
            
            if success:
                status.update(label="Sincronización completada con éxito.", state="complete")
                st.success(f"✅ {msg}")
                st.balloons()
                st.session_state.pedidos_erp.pop(idx_pedido)
                if st.button("Continuar"):
                    st.rerun()
            else:
                status.update(label="Error en la sincronización.", state="error")
                st.error(f"❌ Fallo: {msg}")
