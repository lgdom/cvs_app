import streamlit as st
import config
import utils
from views import inventario, faltantes

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title=config.PAGE_TITLE, 
    page_icon=config.PAGE_ICON, 
    layout=config.LAYOUT
)

# --- INICIALIZACIÓN ---
utils.inicializar_estado()
df_clientes, df_productos, logs = utils.cargar_catalogos()

# --- SIDEBAR ---
with st.sidebar:
    st.title("Navegación")
    vista = st.radio("Ir a:", ["🔍 Revisar Existencias", "📝 Reportar Faltantes"])
    st.divider()
    
    st.caption("Estado del Sistema:")
    if st.session_state.df_inventario_diario is not None:
        st.success("✅ Inventario Diario Cargado")
    else:
        st.warning("⚠️ Falta Inventario Diario")
        
    if logs:
        for l in logs: st.error(l)

# --- ENRUTAMIENTO ---
if vista == "🔍 Revisar Existencias":
    inventario.render_view(df_productos, df_clientes)

elif vista == "📝 Reportar Faltantes":
    faltantes.render_view(df_productos, df_clientes)
