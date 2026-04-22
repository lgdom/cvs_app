import streamlit as st
from datetime import datetime
from src.config import PAGE_TITLE, PAGE_ICON, LAYOUT
from src.services.data_service import cargar_catalogos
from src.views import inventory_view, orders_view, expenses_view, sync_view, cobro_view, prices_view

#PARA CORRER ESTE RELAJO:
#./venv/bin/streamlit run app.py

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout=LAYOUT)

# --- SISTEMA DE PERSISTENCIA (OFFLINE SYNC) ---
from src.services.persistence_service import load_persistence, save_persistence

if 'inicializado' not in st.session_state:
    cache = load_persistence()
    if cache:
        import pandas as pd
        st.session_state.carrito = cache.get("carrito", [])
        st.session_state.lista_revision = cache.get("lista_revision", [])
        st.session_state.facturas = cache.get("facturas", [])
        
        # Recuperar pedidos y convertir items a DataFrame
        pedidos_recuperados = cache.get("pedidos", [])
        for p in pedidos_recuperados:
            if isinstance(p.get("items"), list):
                p["items"] = pd.DataFrame(p["items"])
        st.session_state.pedidos = pedidos_recuperados
        
        # Recuperar pedidos ERP y convertir items a DataFrame
        pedidos_erp_recup = cache.get("pedidos_erp", [])
        for p in pedidos_erp_recup:
            if isinstance(p.get("items"), list):
                p["items"] = pd.DataFrame(p["items"])
        st.session_state.pedidos_erp = pedidos_erp_recup
        
        st.session_state.memoria_cliente = cache.get("memoria_cliente", None)
        st.session_state.memoria_busqueda_inv = cache.get("memoria_busqueda_inv", "")
    st.session_state.inicializado = True

# --- INICIALIZACIÓN DE ESTADO (MEMORIA POR DEFECTO) ---
if 'pedidos' not in st.session_state: st.session_state.pedidos = []
if 'pedidos_erp' not in st.session_state: st.session_state.pedidos_erp = []
if 'carrito' not in st.session_state: st.session_state.carrito = []
if 'df_inventario_diario' not in st.session_state: st.session_state.df_inventario_diario = None
if 'memoria_cliente' not in st.session_state: st.session_state.memoria_cliente = None
if 'memoria_fecha' not in st.session_state: st.session_state.memoria_fecha = datetime.today()
if 'memoria_busqueda_inv' not in st.session_state: st.session_state.memoria_busqueda_inv = ""
if 'lista_revision' not in st.session_state: st.session_state.lista_revision = []
if 'facturas' not in st.session_state: st.session_state.facturas = []
if 'reset_counter' not in st.session_state: st.session_state.reset_counter = 0

# --- CARGA DE DATOS ---
df_clientes, df_productos, logs = cargar_catalogos()

# --- NAVEGACIÓN LATERAL ---
with st.sidebar:
    st.title("Navegación")
    vista = st.radio("Ir a:", [
        "🔍 Revisar Existencias", 
        "📝 Reportar Faltantes", 
        "💸 Gestionar Viáticos", 
        "💳 Gestión de Cobro",
        "🏷️ Comparar Precios"
    ])
    st.divider()
    
    if st.button("🗑️ Limpiar Cache Local"):
        from src.services.persistence_service import clear_persistence
        clear_persistence()
        st.session_state.carrito = []
        st.session_state.lista_revision = []
        st.session_state.facturas = []
        st.session_state.pedidos = []
        st.rerun()

    st.caption("Estado del Sistema:")
    if st.session_state.df_inventario_diario is not None:
        st.success("✅ Inventario Diario Cargado")
    else:
        st.warning("⚠️ Falta Inventario Diario")
        
    if logs:
        for l in logs: st.error(l)

# --- ENRUTAMIENTO DE VISTAS ---
if vista == "🔍 Revisar Existencias":
    inventory_view.render(df_productos, df_clientes)
elif vista == "📝 Reportar Faltantes":
    orders_view.render(df_productos, df_clientes)
elif vista == "💸 Gestionar Viáticos":
    expenses_view.render()
elif vista == "💳 Gestión de Cobro":
    cobro_view.render(df_productos, df_clientes)
elif vista == "🏷️ Comparar Precios":
    prices_view.render()
# elif vista == "🚀 Sincronizar ERP":
#     sync_view.render(df_productos, df_clientes)

# --- AUTOMATIC SAVE AT END OF SESSION ---
save_persistence(st.session_state)
