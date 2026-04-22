from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from io import BytesIO
from src.config import DRIVE_FOLDER_ID
from src.services.drive_service import descargar_de_drive
from src.services.data_service import procesar_inventario

import pytz

def format_update_time(iso_str):
    """Convierte un ISO string de Drive a un formato humano y amigable en zona Tijuana."""
    if not iso_str: return "Desconocida"
    try:
        # Zona horaria de Tijuana
        tz_tj = pytz.timezone('America/Tijuana')
        
        # Parsear (Drive entrega UTC con 'Z')
        dt_utc = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        
        # Convertir a Tijuana
        dt_tj = dt_utc.astimezone(tz_tj)
        
        # Obtener "ahora" en Tijuana para comparar
        ahora_tj = datetime.now(tz_tj)
        
        es_hoy = dt_tj.date() == ahora_tj.date()
        es_ayer = dt_tj.date() == (ahora_tj - timedelta(days=1)).date()
        
        hora_str = dt_tj.strftime("%I:%M %p") # 12h AM/PM
        
        if es_hoy:
            return f"Hoy a las {hora_str}"
        elif es_ayer:
            return f"Ayer a las {hora_str}"
        else:
            return dt_tj.strftime("%d de %b a las ") + hora_str
    except Exception as e:
        return iso_str

# --- FUNCIONES CACHEADAS PARA PDF ---
@st.cache_data(show_spinner=False)
def cachear_pdf_bytes(time_str, df_activo, info_origen):
    """Genera el PDF y lo guarda en caché para no repetir el proceso."""
    from src.services.data_service import fetch_corta_caducidad_data
    from src.services.pdf_service import generate_inventory_pdf
    df_cad_extra, info_v_fechas = fetch_corta_caducidad_data()
    return generate_inventory_pdf(df_activo, time_str, df_corta_cad=df_cad_extra, info_v_fechas=info_v_fechas)

def render(df_productos, df_clientes):
    st.header("🔍 Buscador de Existencias")

    # --- LÓGICA DE CARGA DE INVENTARIO ---
    uploaded_file = st.file_uploader("📤 Cargar archivo local (sobrescribe)", type=['csv', 'xlsx'])
    
    df_activo = None
    info_origen = ""

    # CASO A: Local
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                try: df_raw = pd.read_csv(uploaded_file, header=1, encoding='latin-1')
                except: uploaded_file.seek(0); df_raw = pd.read_csv(uploaded_file, header=1, encoding='utf-8')
            else:
                df_raw = pd.read_excel(uploaded_file, header=1)
            
            df_activo = procesar_inventario(df_raw, df_productos)
            # Guardamos todo en sesión
            st.session_state.df_inventario_diario = df_activo
            st.session_state.info_archivo = f"Local: {uploaded_file.name}"
            info_origen = st.session_state.info_archivo
            
        except Exception as e:
            st.error(f"Error archivo local: {e}")

    # CASO B: Memoria (Ya cargado)
    elif st.session_state.df_inventario_diario is not None:
        df_activo = st.session_state.df_inventario_diario
        # Recuperamos la info del archivo guardada
        info_origen = st.session_state.get('info_archivo', 'Inventario Cargado')

    # CASO C: Carpeta Drive (Automático)
    elif DRIVE_FOLDER_ID:
        with st.spinner("☁️ Sincronizando (esto toma unos segundos)..."):
            # Llamamos a la función cacheada
            df_cloud, nombre_archivo, fecha_mod = descargar_de_drive(DRIVE_FOLDER_ID)
            
            if df_cloud is not None:
                df_activo = procesar_inventario(df_cloud, df_productos)
                
                # Guardamos en sesión
                st.session_state.df_inventario_diario = df_activo
                st.session_state.fecha_inventario_raw = fecha_mod
                
                # Formateamos la fecha de manera estética
                fecha_formateada = format_update_time(fecha_mod)
                info_str = f"Inventario actualizado: {fecha_formateada}"
                
                st.session_state.info_archivo = info_str
                info_origen = info_str
                
                # Rerun para mostrar los datos inmediatamente
                st.rerun()
            else:
                if nombre_archivo and "Error" in nombre_archivo:
                    st.error(nombre_archivo)
                else:
                    st.warning("⚠️ Carpeta vacía o sin acceso.")

    # --- RENDERIZADO DEL BUSCADOR ---
    if df_activo is not None:
        # Fila de Estado y Recarga
        c_status, c_reload = st.columns([4, 1])
        with c_status:
            # Si el info_origen sigue siendo la fecha ISO vieja, lo intentamos formatear
            if "Z" in info_origen or (info_origen and info_origen[0].isdigit()):
                info_origen = f"Inventario actualizado: {format_update_time(info_origen.replace(' Inventario actualizado el: ', ''))}"
            st.success(f"📅 {info_origen}")
        
        with c_reload:
            if st.button("🔄 Recargar", use_container_width=True, help="Forzar descarga y limpiar todos los cachés"):
                from src.services.data_service import fetch_corta_caducidad_data
                st.session_state.df_inventario_diario = None
                descargar_de_drive.clear()
                fetch_corta_caducidad_data.clear()
                cachear_pdf_bytes.clear()
                st.rerun()

        # --- LÓGICA DE TIEMPO (TIJUANA) Y NOMBRE DE ARCHIVO ---
        import pytz
        tz_tj = pytz.timezone('America/Tijuana')
        
        # Recuperamos la fecha raw que guardamos al descargar de Drive
        fecha_iso = st.session_state.get('fecha_inventario_raw')
        
        try:
            if fecha_iso:
                dt_ref = datetime.fromisoformat(fecha_iso.replace('Z', '+00:00')).astimezone(tz_tj)
            else:
                dt_ref = datetime.now(tz_tj)
        except:
            dt_ref = datetime.now(tz_tj)
            
        meses_abrev = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
        nombre_pdf = f"EXISTENCIAS CVS ({dt_ref.day}-{meses_abrev[dt_ref.month-1]}).pdf"

        meses_abrev = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
        nombre_pdf = f"EXISTENCIAS CVS ({dt_ref.day}-{meses_abrev[dt_ref.month-1]}).pdf"

        # Formatear la fecha para el subtítulo interno del PDF
        meses_full = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
        info_pdf_time_str = f"{dt_ref.day} DE {meses_full[dt_ref.month-1]} DE {dt_ref.year} | {dt_ref.strftime('%I:%M %p')}"

        try:
            pdf_listo = cachear_pdf_bytes(info_pdf_time_str, df_activo, info_origen)
        except Exception as e:
            pdf_listo = b""
            st.error(f"Error interno PDF: {e}")

        st.download_button(
            label="📄 Descargar Reporte PDF",
            data=pdf_listo,
            file_name=nombre_pdf,
            mime="application/pdf",
            use_container_width=True,
            type="primary",
            help=f"Fecha de actualización: {dt_ref.strftime('%d/%m/%Y %I:%M %p')}"
        )
        
        # --- BUSCADOR PERSISTENTE ---
        st.markdown("---")
        
        # --- BUSCADOR PERSISTENTE ---
        def actualizar_busqueda_inv():
            st.session_state.memoria_busqueda_inv = st.session_state.input_busqueda_inv

        # El input muestra el valor guardado en memoria
        texto_input = st.text_input(
            "¿Qué buscas?", 
            value=st.session_state.memoria_busqueda_inv, # Recupera lo escrito antes
            placeholder="Nombre, Clave o Sustancia...",
            key="input_busqueda_inv", 
            on_change=actualizar_busqueda_inv # Guarda al escribir
        )
        
        # Convertimos a mayúsculas para la lógica de filtrado
        busqueda = texto_input.upper()
        
        resultados = pd.DataFrame()
        
        if busqueda:
            # Asegurarse de que el índice de búsqueda existe
            if 'INDICE_BUSQUEDA' in df_activo.columns:
                mask = df_activo['INDICE_BUSQUEDA'].str.contains(busqueda, na=False)
                resultados = df_activo[mask].drop(columns=['INDICE_BUSQUEDA'])
            else:
                # Si no existe, buscamos en todas las columnas para no fallar
                mask = df_activo.astype(str).apply(lambda row: row.str.contains(busqueda, case=False).any(), axis=1)
                resultados = df_activo[mask]
                
            st.success(f"Encontrados: {len(resultados)}")
            
            dynamic_key = f"search_table_{st.session_state.reset_counter}"
            
            event = st.dataframe(
                resultados,
                width="stretch",
                hide_index=True,
                on_select="rerun", 
                selection_mode="multi-row",
                key=dynamic_key,
                column_config={
                    "EXISTENCIA": st.column_config.NumberColumn(format="%d"),
                    "CORTA_CAD": st.column_config.NumberColumn(format="%d")
                }
            )
            
            if len(event.selection.rows) > 0:
                st.divider()
                # --- NUEVO: COLUMNAS PARA BOTÓN Y CANTIDAD ---
                c_btn, c_qty = st.columns([3, 1])
                
                # Input de cantidad (opcional, por defecto 0)
                qty_add = c_qty.number_input("Piezas (Opcional):", min_value=0, value=0, key="qty_add_rev")
                
                if c_btn.button(f"⬇️ Agregar Selección ({len(event.selection.rows)})"):
                    filas_seleccionadas = resultados.iloc[event.selection.rows].copy()
                    
                    # Agregar columna de piezas
                    # Si es 0, mostramos "-", si tiene número, lo mostramos.
                    filas_seleccionadas['SOLICITADO'] = qty_add if qty_add > 0 else "-"
                    
                    nuevos_items = filas_seleccionadas.to_dict('records')
                    st.session_state.lista_revision.extend(nuevos_items)
                    
                    st.session_state.reset_counter += 1 
                    st.toast("✅ Agregado")
                    st.rerun() 
        else:
            st.info("Inventario cargado. Escribe arriba para filtrar.")

        # --- SECCIÓN INFERIOR: TABLA DE REVISIÓN ACUMULADA ---
        render_revision_list(df_clientes)

def render_revision_list(df_clientes):
    st.divider()
    st.subheader("📋 Tu Lista de Revisión")
    
    # Columnas para los botones de acción
    col_info, col_borrar_sel, col_borrar_todo = st.columns([3, 2, 1])
    
    if st.session_state.lista_revision:
        # Contador de productos
        st.markdown(f"{len(st.session_state.lista_revision)} productos agregados")
        
        df_rev = pd.DataFrame(st.session_state.lista_revision)
        
        # Orden de columnas
        cols_orden = ['CODIGO', 'PRODUCTO', 'SUSTANCIA', 'EXISTENCIA', 'CORTA_CAD', 'SOLICITADO']
        for c in cols_orden:
            if c not in df_rev.columns: df_rev[c] = "-"
        df_rev = df_rev[cols_orden]

        # Estilos
        def estilo_existencias(row):
            existencia = pd.to_numeric(row['EXISTENCIA'], errors='coerce') or 0
            corta_cad = pd.to_numeric(row['CORTA_CAD'], errors='coerce') or 0
            colores = [''] * len(row)
            if existencia == 0 and corta_cad == 0:
                colores = ['background-color: #390D10'] * len(row)
            elif existencia == 0 and corta_cad > 0:
                colores = ['background-color: #4B3718'] * len(row)
            return colores

        # Inicializar contador de reset para la tabla de revisión si no existe
        if 'reset_counter_rev' not in st.session_state:
            st.session_state.reset_counter_rev = 0

        # --- TABLA INTERACTIVA CON LLAVE DINÁMICA ---
        event_revision = st.dataframe(
            df_rev.style.apply(estilo_existencias, axis=1),
            width="stretch", 
            hide_index=True,
            on_select="rerun",          
            selection_mode="multi-row", 
            key=f"tabla_revision_{st.session_state.reset_counter_rev}",
            column_config={
                "EXISTENCIA": st.column_config.NumberColumn(format="%d"),
                "CORTA_CAD": st.column_config.NumberColumn(format="%d")
            }
        )
        
        # --- LÓGICA DE BORRADO SELECTIVO ---
        filas_seleccionadas = event_revision.selection.rows
        
        with col_borrar_sel:
            if filas_seleccionadas:
                if st.button(f"🗑️ Borrar ({len(filas_seleccionadas)})", use_container_width=True):
                    indices_a_borrar = set(filas_seleccionadas)
                    st.session_state.lista_revision = [
                        item for i, item in enumerate(st.session_state.lista_revision) 
                        if i not in indices_a_borrar
                    ]
                    st.session_state.reset_counter_rev += 1 # LIMPIAR SELECCIÓN
                    st.rerun()

        with col_borrar_todo:
            with st.popover("🔥 Borrar Todo", use_container_width=True):
                st.error("¿Seguro que quieres borrar toda la lista?")
                if st.button("Sí, borrar todo", type="primary", use_container_width=True):
                    st.session_state.lista_revision = []
                    st.session_state.reset_counter_rev += 1 # RESET
                    st.rerun()

        # --- SECCIÓN INFERIOR: GUARDAR Y DESCARGAR ---
        # Pasamos df_rev (original) en lugar de un df editado
        render_image_download_section(df_rev, df_clientes)
    else:
        st.caption("Selecciona productos arriba para armar tu lista de revisión.")

def generar_imagen_lista(df_rev, incluir_sustancia, cliente_foto, fecha_hist):
    """
    Función auxiliar para generar el buffer de la imagen.
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from io import BytesIO
    import pandas as pd

    try:
        # 1. FILTRAR DATOS
        df_plot = df_rev.copy()
        
        if not incluir_sustancia:
            if 'SUSTANCIA' in df_plot.columns:
                df_plot = df_plot.drop(columns=['SUSTANCIA'])
        
        # Asegurar que existencias y corta caducidad sean enteros para la imagen
        for col in ['EXISTENCIA', 'CORTA_CAD']:
            if col in df_plot.columns:
                try:
                    df_plot[col] = pd.to_numeric(df_plot[col], errors='coerce').fillna(0).astype(int)
                except: pass
                
        # 2. COLORES
        cell_colors = []
        hay_rojo = False
        hay_amarillo = False
        
        for _, row in df_plot.iterrows():
            ex = pd.to_numeric(row['EXISTENCIA'], errors='coerce') or 0
            cc = pd.to_numeric(row['CORTA_CAD'], errors='coerce') or 0
            
            if ex == 0 and cc == 0:
                fila_color = ['#fe9292'] * len(df_plot.columns)
                hay_rojo = True
            elif ex == 0 and cc > 0:
                fila_color = ['#ffe59a'] * len(df_plot.columns)
                hay_amarillo = True
            else:
                fila_color = ['#ffffff'] * len(df_plot.columns)
            cell_colors.append(fila_color)

        # 3. DIMENSIONES DINÁMICAS (ANCHO Y ALTO VARIABLE)
        num_filas = len(df_plot)
        num_cols = len(df_plot.columns)
        
        # Ancho: 2.5 pulgadas por columna (aprox) para dar buen espacio al texto
        ancho_dinamico = max(10, num_cols * 1.25) 
        
        # Alto: 0.5 pulgadas por fila + espacio extra para encabezados/títulos
        alto_dinamico = num_filas * 0.35
        
        if cliente_foto: alto_dinamico += 0.2
        if hay_rojo or hay_amarillo: alto_dinamico += 0.2
        
        fig, ax = plt.subplots(figsize=(ancho_dinamico, alto_dinamico)) 
        ax.axis('off')
        
        # 4. TÍTULO
        if cliente_foto:
            cod, nom = cliente_foto.split(" - ", 1)
            # pad=20 da un pequeño aire interno antes del margen blanco
            plt.title(f"{nom}\n{cod}", fontsize=16, fontweight='bold', pad=20)

        # 5. DIBUJAR TABLA
        # Convertimos todo a string para evitar que matplotlib/pandas metan decimales
        tabla_vals = df_plot.astype(str).values
        
        tabla = ax.table(
            cellText=tabla_vals,
            colLabels=df_plot.columns,
            cellColours=cell_colors,
            cellLoc='center',
            loc='center'
        )
        
        # Estilizado
        tabla.auto_set_font_size(False)
        tabla.set_fontsize(11)
        tabla.scale(1, 1.5) # Celdas más altas para mejor lectura
        tabla.auto_set_column_width(col=list(range(len(df_plot.columns))))
        
        # 6. LEYENDA
        leyendas = []
        if hay_amarillo:
            leyendas.append(mpatches.Patch(color='#ffe59a', label='SOLO CORTA CAD.'))
        if hay_rojo:
            leyendas.append(mpatches.Patch(color='#fe9292', label='NO DISPONIBLE'))
            
        if leyendas:
            plt.legend(
                handles=leyendas, 
                loc='upper center', 
                bbox_to_anchor=(0.5, -0.02), 
                ncol=2, 
                frameon=False,
                fontsize=10
            )

        # Guardar
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=150, pad_inches=0.5)
        buf.seek(0)
        return buf
    except Exception as e:
        st.error(f"Error generando imagen: {e}")
        return None

def render_image_download_section(df_rev, df_clientes):
    st.divider()
    
    # --- CONFIGURACIÓN DE DATOS DE SALIDA (CLIENTE / FECHA) ---
    st.markdown("### 📤 Opciones de Guardado")
    
    c_cli, c_fecha, c_opt = st.columns([2, 1, 1])
    with c_cli:
        # Recuperamos cliente de session state si existe
        default_idx = None
        if 'cli_foto_input' in st.session_state and st.session_state.cli_foto_input in df_clientes['DISPLAY'].values:
             default_idx = int(df_clientes[df_clientes['DISPLAY'] == st.session_state.cli_foto_input].index[0])

        cliente_foto = st.selectbox(
            "Cliente:", 
            options=df_clientes['DISPLAY'], 
            index=default_idx, 
            placeholder="Selecciona un cliente...", 
            key="cli_foto_input"
        )
    
    with c_fecha:
        from datetime import datetime
        fecha_hist = st.date_input("Fecha Registro:", value=datetime.today(), key="fecha_hist_input")

    with c_opt:
        incluir_sustancia = st.checkbox("Incluir 'Sustancia' en imagen", value=True)


    # --- BOTONES DE ACCIÓN ---
    col_img, col_drive, col_erp = st.columns(3)
    
    # 1. BOTÓN IMAGEN (ÚNICO PASO)
    with col_img:
        # Pre-generar nombre de archivo
        nombre_file = "Lista_Revision.png"
        if cliente_foto:
            try:
                _, nom_cli = cliente_foto.split(" - ", 1)
                nombre_file = f"Lista_{nom_cli}.png"
            except: pass

        # Generar imagen (Streamlit la genera en el render, pero es rápido para pocos items)
        img_data = generar_imagen_lista(df_rev, incluir_sustancia, cliente_foto, fecha_hist)
        
        if img_data:
            st.download_button(
                label="📸 Guardar Lista como Imagen", 
                data=img_data, 
                file_name=nombre_file, 
                mime="image/png",
                width='stretch',
                type="secondary"
            )
        else:
            st.error("No se pudo preparar la imagen para descarga.")

    # 2. BOTÓN DRIVE (FALTANTES)
    with col_drive:
        if st.button("📝 Guardar Faltantes (Drive)", width='stretch', type="secondary"):
             if not cliente_foto:
                 st.warning("⚠️ Debes seleccionar un **Cliente**.")
             else:
                 # FILTRO DE FALTANTES REALES
                 items_faltantes = []
                 for item in st.session_state.lista_revision:
                     try: ex = float(item.get('EXISTENCIA', 0))
                     except: ex = 0
                     try: cc = float(item.get('CORTA_CAD', 0))
                     except: cc = 0
                     
                     if ex == 0 and cc == 0:
                         sol = item.get('SOLICITADO', '-')
                         item_copy = item.copy()
                         item_copy['SOLICITADA'] = sol 
                         items_faltantes.append(item_copy)
                 
                 if items_faltantes:
                     with st.spinner("Subiendo a Drive..."):
                         from src.services.drive_service import append_to_history_log
                         df_hist = pd.DataFrame(items_faltantes)
                         df_export = pd.DataFrame()
                         df_export['CODIGO'] = df_hist['CODIGO']
                         df_export['DESCRIPCION'] = df_hist['PRODUCTO']
                         df_export['SOLICITADA'] = df_hist.get('SOLICITADA', '-')
                         df_export['SURTIDO'] = 0
                         df_export['FECHA'] = fecha_hist.strftime('%d/%m/%Y')
                         df_export['CLIENTE'] = cliente_foto
                         success, msg = append_to_history_log(df_export)
                         if success: st.success(f"✅ Faltantes guardados ({len(df_export)} items)")
                         else: st.error(f"❌ {msg}")
                 else:
                     st.info("No hay faltantes (Ex=0, CC=0) en la lista.")

    # 3. BOTÓN ERP (PRODUCTOS CON EXISTENCIA)
    with col_erp:
        if st.button("🚀 Sincronizar Venta (ERP)", width='stretch', type="primary"):
            if not cliente_foto:
                st.warning("⚠️ Selecciona un **Cliente** primero.")
            else:
                # FILTRAR SOLO LO QUE SÍ HAY
                items_venta = []
                for item in st.session_state.lista_revision:
                    try: ex = float(item.get('EXISTENCIA', 0))
                    except: ex = 0
                    try: cc = float(item.get('CORTA_CAD', 0))
                    except: cc = 0
                    
                    if ex > 0 or cc > 0:
                        # Para el ERP, la cantidad es lo que el vendedor "SOLICITÓ"
                        sqty = item.get('SOLICITADO', 1)
                        item_erp = {
                            "CODIGO": item['CODIGO'],
                            "DESCRIPCION": item['PRODUCTO'],
                            "SOLICITADA": sqty,
                            "EXISTENCIA": ex + cc # Info de referencia
                        }
                        items_venta.append(item_erp)
                
                if items_venta:
                    cod_cli, nom_cli = cliente_foto.split(" - ", 1)
                    if 'pedidos_erp' not in st.session_state:
                         st.session_state.pedidos_erp = []
                    
                    nuevo_pedido = {
                        "cli_cod": cod_cli,
                        "cli_nom": nom_cli,
                        "items": pd.DataFrame(items_venta)
                    }
                    st.session_state.pedidos_erp.append(nuevo_pedido)
                    st.success(f"✅ {len(items_venta)} productos enviados al Sincronizador ERP")
                    st.toast("Pedido enviado a la pestaña de sincronización")
                else:
                    st.error("No hay productos con existencia para vender.")