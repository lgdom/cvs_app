import streamlit as st
import pandas as pd
import openpyxl
from openpyxl.drawing.image import Image
from io import BytesIO
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Ventas", page_icon="💊", layout="wide")

# --- ARCHIVOS EN GITHUB ---
FILE_CLIENTES = 'clientes.csv'
FILE_PRODUCTOS = 'productos.csv'
FILE_PLANTILLA = 'plantilla.xlsx'
FILE_IMAGEN = 'logo.png'

# --- ESTADO DE LA APP (MEMORIA) ---
# Faltantes
if 'pedidos' not in st.session_state: st.session_state.pedidos = []
if 'carrito' not in st.session_state: st.session_state.carrito = []
# Inventario (Nueva variable para persistencia)
if 'df_inventario_diario' not in st.session_state: st.session_state.df_inventario_diario = None

# --- FUNCIÓN DE CARGA DE DATOS (CATÁLOGOS MAESTROS) ---
@st.cache_data
def cargar_catalogos():
    errores = []
    df_cli = pd.DataFrame()
    df_prod = pd.DataFrame()
    
    # 1. CLIENTES
    try:
        try: df_cli = pd.read_csv(FILE_CLIENTES, encoding='utf-8')
        except: df_cli = pd.read_csv(FILE_CLIENTES, encoding='latin-1')
        
        df_cli.columns = df_cli.columns.str.strip().str.upper()
        col_clave = next((c for c in df_cli.columns if 'CLAVE' in c or 'CODIGO' in c), df_cli.columns[0])
        col_nombre = next((c for c in df_cli.columns if ('CLIENTE' in c or 'NOMBRE' in c) and c != col_clave), df_cli.columns[1])
        
        df_cli = df_cli[[col_clave, col_nombre]].copy()
        df_cli.columns = ['CODIGO', 'NOMBRE']
        df_cli['DISPLAY'] = df_cli['CODIGO'].astype(str) + " - " + df_cli['NOMBRE'].astype(str)
    except Exception as e:
        errores.append(f"Clientes: {e}")

    # 2. PRODUCTOS (Catálogo Maestro)
    try:
        try: df_prod = pd.read_csv(FILE_PRODUCTOS, encoding='utf-8')
        except: df_prod = pd.read_csv(FILE_PRODUCTOS, encoding='latin-1')
            
        df_prod.columns = df_prod.columns.str.strip().str.upper()
        col_clave = next(c for c in df_prod.columns if 'CLAVE' in c or 'CODIGO' in c)
        col_desc = next(c for c in df_prod.columns if 'NOMBRE' in c or 'DESCRIPCION' in c)
        col_sust = next((c for c in df_prod.columns if 'SUSTANCIA' in c), None)
        
        cols = [col_clave, col_desc]
        if col_sust: cols.append(col_sust)
        df_prod = df_prod[cols].copy()
        
        nombres = ['CODIGO', 'DESCRIPCION']
        if col_sust: nombres.append('SUSTANCIA')
        df_prod.columns = nombres
        
        if 'SUSTANCIA' not in df_prod.columns: df_prod['SUSTANCIA'] = '---'
        else: df_prod['SUSTANCIA'] = df_prod['SUSTANCIA'].fillna('---')

        # Índice de búsqueda optimizado (Pre-cálculo)
        df_prod['SEARCH_INDEX'] = (
            df_prod['CODIGO'].astype(str) + " | " + 
            df_prod['DESCRIPCION'].astype(str) + " | " + 
            df_prod['SUSTANCIA'].astype(str)
        ).str.upper()
        
    except Exception as e:
        errores.append(f"Productos: {e}")

    return df_cli, df_prod, errores

# Cargar datos al inicio
df_clientes, df_productos, logs = cargar_catalogos()

# --- NAVEGACIÓN LATERAL ---
with st.sidebar:
    st.title("Navegación")
    vista = st.radio("Ir a:", ["🔍 Revisar Existencias", "📝 Reportar Faltantes"])
    st.divider()
    
    # Indicadores de estado
    st.caption("Estado del Sistema:")
    if st.session_state.df_inventario_diario is not None:
        st.success("✅ Inventario Diario Cargado")
    else:
        st.warning("⚠️ Falta Inventario Diario")
        
    if logs:
        for l in logs: st.error(l)

# ==============================================================================
# VISTA 1: REVISAR EXISTENCIAS (INVENTARIO DIARIO)
# ==============================================================================
if vista == "🔍 Revisar Existencias":
    st.header("🔍 Buscador de Existencias")
    
    # LÓGICA DE PERSISTENCIA:
    # Si NO hay inventario en memoria, mostramos el cargador
    if st.session_state.df_inventario_diario is None:
        st.markdown("Sube el archivo del día para comenzar.")
        uploaded_file = st.file_uploader("📤 Sube Inventario de Hoy (Excel/CSV)", type=['csv', 'xlsx'])
        
        if uploaded_file:
            try:
                with st.spinner("Procesando e indexando..."):
                    # 1. Leer archivo
                    if uploaded_file.name.endswith('.csv'):
                        try: df_inv = pd.read_csv(uploaded_file, header=1, encoding='latin-1')
                        except: uploaded_file.seek(0); df_inv = pd.read_csv(uploaded_file, header=1, encoding='utf-8')
                    else:
                        df_inv = pd.read_excel(uploaded_file, header=1)

                    # 2. Limpiar (Tijuana)
                    df_tj = df_inv.iloc[:, [0, 1, 5, 6]].copy()
                    df_tj.columns = ['CODIGO', 'PRODUCTO_INV', 'CORTA_CAD', 'EXISTENCIA']
                    df_tj = df_tj.dropna(subset=['CODIGO'])
                    df_tj['CODIGO'] = df_tj['CODIGO'].astype(str).str.strip()

                    # 3. Cruzar con Catálogo Maestro (Optimización: Se hace UNA VEZ al subir)
                    df_merged = pd.merge(df_tj, df_productos[['CODIGO', 'SUSTANCIA']], on='CODIGO', how='left')
                    df_merged['SUSTANCIA'] = df_merged['SUSTANCIA'].fillna('---')
                    
                    # 4. Crear índice rápido (Optimización: Se hace UNA VEZ al subir)
                    df_merged['INDICE_BUSQUEDA'] = (
                        df_merged['CODIGO'] + " " + 
                        df_merged['PRODUCTO_INV'] + " " + 
                        df_merged['SUSTANCIA']
                    ).str.upper()

                    # 5. Guardar en Memoria de Sesión
                    cols_finales = ['CODIGO', 'PRODUCTO_INV', 'SUSTANCIA', 'EXISTENCIA', 'CORTA_CAD', 'INDICE_BUSQUEDA']
                    st.session_state.df_inventario_diario = df_merged[cols_finales]
                    
                    st.rerun() # Recargar página para mostrar buscador
            except Exception as e:
                st.error(f"Error procesando archivo diario: {e}")
                
    # Si SÍ hay inventario en memoria, mostramos el buscador directo
    else:
        col_search, col_reset = st.columns([4, 1])
        with col_reset:
            if st.button("🔄 Cargar Otro"):
                st.session_state.df_inventario_diario = None
                st.rerun()
        
        # Buscador Ultra Rápido (Usa datos en memoria)
        df_memoria = st.session_state.df_inventario_diario
        
        busqueda = st.text_input("¿Qué buscas?", placeholder="Nombre, Clave o Sustancia...").upper()
        
        if busqueda:
            # Filtro simple sobre columna pre-calculada
            mask = df_memoria['INDICE_BUSQUEDA'].str.contains(busqueda, na=False)
            resultados = df_memoria[mask].drop(columns=['INDICE_BUSQUEDA'])
            st.success(f"Encontrados: {len(resultados)}")
            st.dataframe(resultados, use_container_width=True, hide_index=True)
        else:
            st.info("Inventario cargado. Escribe arriba para filtrar.")
            st.dataframe(df_memoria.drop(columns=['INDICE_BUSQUEDA']).head(10), use_container_width=True, hide_index=True)


# ==============================================================================
# VISTA 2: REPORTAR FALTANTES (POS)
# ==============================================================================
elif vista == "📝 Reportar Faltantes":
    st.header("📝 Generador de Reporte de Faltantes")
    
    # --- BOTÓN DE REINICIO EN LA BARRA LATERAL ---
    with st.sidebar:
        st.divider()
        st.markdown("### ⚙️ Acciones")
        # Usamos type="primary" para que salga rojo/destacado
        if st.button("🗑️ BORRAR TODO (Reiniciar)", type="primary", help="Borra todos los pedidos y el carrito actual"):
            st.session_state.pedidos = []
            st.session_state.carrito = []
            st.session_state.cliente_box = None
            st.rerun() # Recarga la página suavemente con los datos en cero
    # ----------------------------------------------------
    
    # Callbacks
    def agregar_producto():
        cliente = st.session_state.cliente_box
        prod_str = st.session_state.prod_box
        cant = st.session_state.qty_box
        
        if cliente and prod_str:
            row = df_productos[df_productos['SEARCH_INDEX'] == prod_str].iloc[0]
            item = {
                "CODIGO": row['CODIGO'],
                "DESCRIPCION": row['DESCRIPCION'],
                "SOLICITADA": cant,
                "SURTIDO": 0,
                "O.C.": "N/A"
            }
            st.session_state.carrito.append(item)
            st.session_state.qty_box = 1      
            st.session_state.prod_box = None 
        else:
            st.warning("⚠️ Selecciona Cliente y Producto")

    def finalizar_pedido(fecha):
        if st.session_state.cliente_box:
            cod_cli, nom_cli = st.session_state.cliente_box.split(" - ", 1)
            pedido_nuevo = {
                "cli_cod": cod_cli,
                "cli_nom": nom_cli,
                "fecha": fecha,
                "items": pd.DataFrame(st.session_state.carrito)
            }
            st.session_state.pedidos.append(pedido_nuevo)
            st.session_state.carrito = []
            st.session_state.cliente_box = None
        else:
            st.error("Falta Cliente")

    tab1, tab2 = st.tabs(["1. Registrar", "2. Descargar Excel"])
    
    with tab1:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("Datos")
            st.selectbox("Cliente:", options=df_clientes['DISPLAY'], index=None, placeholder="Buscar...", key="cliente_box")
            fecha_input = st.date_input("Fecha:", datetime.today())
            
            st.divider()
            st.subheader("Producto")
            
            st.selectbox("Buscar:", options=df_productos['SEARCH_INDEX'], index=None, placeholder="Escribe para filtrar...", key="prod_box")
            st.number_input("Cantidad:", min_value=1, value=1, key="qty_box")
            st.button("➕ Agregar", on_click=agregar_producto, use_container_width=True)

        with col2:
            st.subheader("🛒 Carrito")
            if st.session_state.carrito:
                df_cart = pd.DataFrame(st.session_state.carrito)
                df_edited = st.data_editor(df_cart, use_container_width=True, num_rows="dynamic", key="editor_data",
                    column_config={"SOLICITADA": st.column_config.NumberColumn("Solicitada", width="small"),
                                   "SURTIDO": st.column_config.NumberColumn("Surtido", width="small"),
                                   "O.C.": st.column_config.TextColumn("O.C.", width="small")})
                
                if not df_edited.equals(df_cart): st.session_state.carrito = df_edited.to_dict('records')
                st.button("💾 TERMINAR PEDIDO", type="primary", use_container_width=True, on_click=finalizar_pedido, args=(fecha_input,))
            else:
                st.info("Carrito vacío.")

    with tab2:
        st.metric("Pedidos Listos", len(st.session_state.pedidos))
        for i, p in enumerate(st.session_state.pedidos):
            with st.expander(f"{i+1}. {p['cli_nom']}"):
                st.dataframe(p['items'])
                if st.button("Borrar", key=f"del_{i}"):
                    st.session_state.pedidos.pop(i); st.rerun()
        
        if st.button("🚀 GENERAR EXCEL", disabled=(len(st.session_state.pedidos)==0)):
            try:
                wb = openpyxl.load_workbook(FILE_PLANTILLA)
                base = wb.active; base.title = "Base"
                conteo = {}
                
                for p in st.session_state.pedidos:
                    cod = p['cli_cod']
                    conteo[cod] = conteo.get(cod, 0) + 1
                    nom_hoja = cod if conteo[cod] == 1 else f"{cod}-{conteo[cod]}"
                    ws = wb.copy_worksheet(base); ws.title = nom_hoja
                    
                    ws['B2'] = "SUC. TIJ"; ws['B3'] = "LUIS FELIPE GARCÍA DOMÍNGUEZ"
                    ws['B4'] = p['cli_nom']; ws['D6'] = p['fecha'].strftime('%d/%m/%Y')
                    try: ws['B6'] = int(cod)
                    except: ws['B6'] = cod
                    
                    # Insertar Imagen (con manejo de errores si no existe)
                    try:
                        img = Image(FILE_IMAGEN)
                        img.width = 270; img.height = 80; img.anchor = 'D1'
                        ws.add_image(img)
                    except: pass
                    
                    datos = p['items'][['CODIGO', 'DESCRIPCION', 'SOLICITADA', 'SURTIDO', 'O.C.']].values.tolist()
                    for idx, row in enumerate(datos):
                        for c, val in enumerate(row): ws.cell(row=10+idx, column=c+1, value=val)
                
                del wb['Base']
                b = BytesIO(); wb.save(b); b.seek(0)
                st.download_button("⬇️ DESCARGAR", data=b, file_name="Faltantes.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception as e: st.error(f"Error: {e}")
