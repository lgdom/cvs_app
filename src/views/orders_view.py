import streamlit as st
import pandas as pd
from src.services.excel_service import generar_excel_faltantes

def render(df_productos, df_clientes):
    st.header("📝 Generador de Reporte de Faltantes")
    
    # --- BOTÓN DE REINICIO EN LA BARRA LATERAL ---
    with st.sidebar:
        st.divider()
        st.markdown("### ⚙️ Acciones")
        with st.popover("🗑️ BORRAR TODO (Local)", use_container_width=True):
            st.warning("Esto borrará el carrito y los pedidos locales.")
            if st.button("Confirmar Borrar Todo", type="primary", use_container_width=True):
                st.session_state.pedidos = []
                st.session_state.carrito = []
                st.session_state.cliente_box = None
                st.session_state.memoria_cliente = None 
                st.rerun()
    # ----------------------------------------------------
    
    tab1, tab2 = st.tabs(["1. Registrar", "2. Descargar Excel"])
    
    with tab1:
        # --- ENCABEZADO COMPACTO (CLIENTE) ---
        c_cli, c_esp = st.columns([2, 1])
        
        with c_cli:
            # --- LÓGICA DE PERSISTENCIA PARA CLIENTE ---
            lista_opciones = df_clientes['DISPLAY'].tolist()
            try:
                idx_guardado = lista_opciones.index(st.session_state.memoria_cliente)
            except:
                idx_guardado = None

            def actualizar_cliente():
                st.session_state.memoria_cliente = st.session_state.cliente_box

            st.selectbox(
                "Cliente:", 
                options=df_clientes['DISPLAY'], 
                index=idx_guardado, 
                placeholder="Buscar cliente...", 
                key="cliente_box", 
                on_change=actualizar_cliente
            )
            
        with c_esp:
            # Herramientas de Historial en la parte superior
            c_h1, c_h2 = st.columns(2)
            with c_h1:
                # --- LÓGICA DE CARGA DESDE DRIVE ---
                if st.button("📂 Cargar Bitácora", width="stretch", help="Cargar pedidos desde Drive"):
                     with st.spinner("Cargando..."):
                         from src.services.drive_service import load_history_log
                         df_hist = load_history_log()
                         if not df_hist.empty:
                             # Agrupar por CLIENTE, FECHA y ID_PEDIDO para separar pedidos repetidos
                             cols_group = ['CLIENTE', 'FECHA']
                             if 'ID_PEDIDO' in df_hist.columns:
                                 cols_group.append('ID_PEDIDO')
                             
                             grupos = df_hist.groupby(cols_group, sort=False)
                             pedidos_creados = 0
                             for keys, grupo in grupos:
                                 # Manejar si es una tupla (multi-columna) o un valor único
                                 nombre_cliente_compuesto = keys[0]
                                 fecha_pedido = keys[1]
                                 id_pedido = keys[2] if len(keys) > 2 else 1
                                 
                                 if pd.isna(nombre_cliente_compuesto): continue
                                 
                                 nombre_limpio = str(nombre_cliente_compuesto).strip()
                                 if nombre_limpio.startswith("('") and nombre_limpio.endswith("',)"):
                                     nombre_limpio = nombre_limpio[2:-3].strip()
                                 
                                 try:
                                     cod_cli, nom_cli = nombre_limpio.split(" - ", 1)
                                 except:
                                     cod_cli = "S/C"; nom_cli = nombre_limpio
                                     
                                 items_df = pd.DataFrame()
                                 items_df['CODIGO'] = grupo['CODIGO']
                                 items_df['DESCRIPCION'] = grupo.get('DESCRIPCION', grupo.get('PRODUCTO', '-'))
                                 items_df['SOLICITADA'] = pd.to_numeric(grupo.get('SOLICITADA', 0), errors='coerce').fillna(0)
                                 items_df['SURTIDO'] = pd.to_numeric(grupo.get('SURTIDO', 0), errors='coerce').fillna(0)
                                 items_df['O.C.'] = "" 
                                 
                                 pedido_nuevo = {
                                     "cli_cod": cod_cli, 
                                     "cli_nom": nom_cli, 
                                     "items": items_df,
                                     "id_pedido": id_pedido,
                                     "fecha": fecha_pedido
                                 }
                                 st.session_state.pedidos.append(pedido_nuevo)
                                 pedidos_creados += 1
                             if pedidos_creados > 0: st.success(f"✅ {pedidos_creados} entradas cargadas.")
                             else: st.warning("No se encontraron pedidos.")
                         else: st.error("Bitácora vacía.")
            with c_h2:
                with st.popover("🔥 Reiniciar Drive", use_container_width=True):
                    st.error("¿Seguro que quieres borrar la bitácora en la Nube?")
                    if st.button("Sí, borrar Bitácora", type="primary", use_container_width=True):
                        with st.spinner("Limpiando..."):
                            from src.services.drive_service import reset_history_log
                            success, msg = reset_history_log()
                            if success: st.success("✅ Reiniciada")
                            else: st.error(f"❌ {msg}")
        
        st.divider()

        # --- SECCIÓN DE BÚSQUEDA (ESTILO EXISTENCIAS) ---
        st.subheader("🔍 Añadir Producto")
        
        def actualizar_busqueda_faltantes():
            st.session_state.memoria_busqueda_faltantes = st.session_state.input_busqueda_faltantes

        if 'memoria_busqueda_faltantes' not in st.session_state:
            st.session_state.memoria_busqueda_faltantes = ""

        # Input de Búsqueda con memoria
        texto_input = st.text_input(
            "¿Qué buscas?", 
            value=st.session_state.memoria_busqueda_faltantes,
            placeholder="Nombre, Clave o Sustancia...", 
            key="input_busqueda_faltantes",
            on_change=actualizar_busqueda_faltantes
        )
        
        query_faltantes = texto_input.upper()
        
        if query_faltantes:
            # 2. Filtrar Resultados
            mask = df_productos['SEARCH_INDEX'].str.contains(query_faltantes, na=False)
            resultados_f = df_productos[mask].copy()
            
            # --- LIMPIEZA VISUAL ---
            resultados_f = resultados_f.dropna(subset=['DESCRIPCION'])
            resultados_f = resultados_f.drop_duplicates(subset=['CODIGO'], keep='first')
            
            cols_mostrar = ['CODIGO', 'DESCRIPCION', 'SUSTANCIA']
            cols_existentes = [c for c in cols_mostrar if c in resultados_f.columns]
            resultados_f = resultados_f[cols_existentes]
            
            # 3. Mostrar Tabla con Selección Múltiple
            key_table = f"table_faltantes_{st.session_state.reset_counter}"
            
            event_f = st.dataframe(
                resultados_f, 
                width="stretch",
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row", 
                key=key_table
            )
            
            # 4. Lógica de Añadido (Columnas)
            if len(event_f.selection.rows) > 0:
                st.divider()
                c_btn, c_qty = st.columns([3, 1])
                
                cantidad = c_qty.number_input("Cantidad p/cada uno:", min_value=1, value=1, key="qty_faltantes_batch")
                
                if c_btn.button(f"⬇️ Agregar Selección ({len(event_f.selection.rows)})", use_container_width=True):
                    if st.session_state.cliente_box:
                        filas_sel = resultados_f.iloc[event_f.selection.rows]
                        for _, row_selected in filas_sel.iterrows():
                            item = {
                                "CODIGO": row_selected['CODIGO'],
                                "DESCRIPCION": row_selected['DESCRIPCION'],
                                "SOLICITADA": cantidad,
                                "SURTIDO": 0,
                                "O.C.": "N/A"
                            }
                            st.session_state.carrito.append(item)
                        
                        st.session_state.reset_counter += 1
                        st.toast("✅ Agregado al carrito")
                        st.rerun()
                    else:
                        st.warning("⚠️ ¡Falta seleccionar el Cliente arriba!")

        # --- SECCIÓN DE CARRITO Y HERRAMIENTAS (ABAJO) ---
        st.divider()
        
        with st.expander(f"🛒 Ver Carrito ({len(st.session_state.carrito)})", expanded=len(st.session_state.carrito) > 0):
            if st.session_state.carrito:
                df_cart = pd.DataFrame(st.session_state.carrito)
                df_edited = st.data_editor(df_cart, width="stretch", num_rows="dynamic", key="editor_data",
                    column_config={"SOLICITADA": st.column_config.NumberColumn("Solicitada", width="small"),
                                   "SURTIDO": st.column_config.NumberColumn("Surtido", width="small"),
                                   "O.C.": st.column_config.TextColumn("O.C.", width="small")})
                
                if not df_edited.equals(df_cart): st.session_state.carrito = df_edited.to_dict('records')
                
                # Callback para guardar pedido completo
                def finalizar_pedido_cb():
                    if st.session_state.cliente_box:
                        cod_cli, nom_cli = st.session_state.cliente_box.split(" - ", 1)
                        # Calcular el siguiente ID para este cliente en la sesión actual
                        pedidos_mismo_cli = [p for p in st.session_state.pedidos if p['cli_cod'] == cod_cli]
                        nuevo_id = 1
                        if pedidos_mismo_cli:
                            ids = [int(p.get('id_pedido', 0)) for p in pedidos_mismo_cli]
                            nuevo_id = max(ids) + 1
                            
                        pedido_nuevo = {
                            "cli_cod": cod_cli,
                            "cli_nom": nom_cli,
                            "items": pd.DataFrame(st.session_state.carrito),
                            "id_pedido": nuevo_id
                        }
                        st.session_state.pedidos.append(pedido_nuevo)
                        st.session_state.carrito = []
                        st.session_state.cliente_box = None
                        st.session_state.search_faltantes_input = ""
                    else:
                        st.error("Falta Cliente")

                st.button("💾 TERMINAR PEDIDO", type="primary", width="stretch", on_click=finalizar_pedido_cb)
            else:
                st.info("El carrito está vacío.")
                
            st.divider()
            st.info("Utiliza el buscador de arriba para añadir productos al carrito.")

    with tab2:
        col_met, col_dep = st.columns([2, 1])
        col_met.metric("Pedidos Listos", len(st.session_state.pedidos))
        
        # --- BOTÓN DE DEPURACIÓN ---
        if st.session_state.pedidos:
            if col_dep.button("🔍 Depurar Faltantes", use_container_width=True, help="Elimina productos que ya tienen existencia"):
                if st.session_state.df_inventario_diario is None:
                    st.error("⚠️ No hay inventario cargado para depurar.")
                else:
                    df_inv = st.session_state.df_inventario_diario
                    # Aseguramos que CODIGO sea string para el cruce
                    df_inv['CODIGO'] = df_inv['CODIGO'].astype(str).str.strip()
                    
                    eliminados_totales = []
                    nuevos_pedidos = []
                    
                    for p in st.session_state.pedidos:
                        items_df = p['items'].copy()
                        items_df['CODIGO'] = items_df['CODIGO'].astype(str).str.strip()
                        
                        # Cruzar con inventario para ver existencia
                        # Solo nos interesan las columnas CODIGO y EXISTENCIA
                        cruce = pd.merge(items_df, df_inv[['CODIGO', 'EXISTENCIA']], on='CODIGO', how='left')
                        cruce['EXISTENCIA'] = cruce['EXISTENCIA'].fillna(0)
                        
                        # Identificar qué se va
                        a_eliminar = cruce[cruce['EXISTENCIA'] > 0].copy()
                        if not a_eliminar.empty:
                            for _, row in a_eliminar.iterrows():
                                eliminados_totales.append({
                                    "Cliente": p['cli_nom'],
                                    "Código": row['CODIGO'],
                                    "Producto": row['DESCRIPCION'],
                                    "Existencia": row['EXISTENCIA']
                                })
                        
                        # Quedarse solo con lo que NO tiene existencia
                        items_filtrados = cruce[cruce['EXISTENCIA'] <= 0].drop(columns=['EXISTENCIA'])
                        
                        if not items_filtrados.empty:
                            p['items'] = items_filtrados
                            nuevos_pedidos.append(p)
                        # Si el pedido queda vacío, no se agrega a nuevos_pedidos
                    
                    st.session_state.pedidos = nuevos_pedidos
                    st.session_state.ultima_depuracion = eliminados_totales
                    
                    if eliminados_totales:
                        st.session_state.msg_depuracion = f"✅ Se eliminaron {len(eliminados_totales)} productos."
                    else:
                        st.session_state.msg_depuracion = "ℹ️ No se encontraron productos con existencia en la lista (nada que depurar)."
                    
                    st.rerun()

        # --- MOSTRAR RESULTADOS DE DEPURACIÓN ---
        if 'msg_depuracion' in st.session_state and st.session_state.msg_depuracion:
            if "✅" in st.session_state.msg_depuracion:
                st.success(st.session_state.msg_depuracion)
            else:
                st.info(st.session_state.msg_depuracion)
            # Limpiar el mensaje después de mostrarlo para que no sea eterno
            del st.session_state.msg_depuracion

        if 'ultima_depuracion' in st.session_state and st.session_state.ultima_depuracion:
            with st.expander("📝 Detalle de los productos eliminados", expanded=True):
                st.table(pd.DataFrame(st.session_state.ultima_depuracion))
                if st.button("Cerrar Reporte"):
                    st.session_state.ultima_depuracion = None
                    st.rerun()

        # --- CAMPOS PARA EL FORMATO ---
        if st.session_state.pedidos:
            st.divider()
            st.subheader("📅 Datos del Reporte")
            c_ed1, c_ed2, c_ed3 = st.columns(3)
            
            f_elab = c_ed1.date_input("Fecha Elaboración:", value=pd.Timestamp.now(), key="f_elab_faltantes")
            f_ini = c_ed2.date_input("Inicio Periodo:", value=pd.Timestamp.now(), key="f_ini_faltantes")
            f_fin = c_ed3.date_input("Fin Periodo:", value=pd.Timestamp.now(), key="f_fin_faltantes")
            st.divider()

        for i, p in enumerate(st.session_state.pedidos):
            try:
                id_int = int(float(p.get('id_pedido', 1)))
            except:
                id_int = 1
            id_display = f" [Pedido {id_int}]"
            with st.expander(f"{i+1}. {p['cli_nom']}{id_display}"):
                st.dataframe(p['items'])
                
                c_del_loc, c_del_dri = st.columns(2)
                
                if c_del_loc.button("🗑️ Borrar Local", key=f"del_{i}", use_container_width=True):
                    st.session_state.pedidos.pop(i)
                    st.rerun()
                
                # Solo permitir borrar de Drive si tiene fecha (está en el historial)
                if 'fecha' in p:
                    with c_del_dri.popover("🔥 Borrar de Drive", use_container_width=True):
                        st.error("¿Seguro que quieres eliminar este pedido permanentemente de la nube?")
                        if st.button("Confirmar Borrar en Drive", type="primary", key=f"del_drive_{i}", use_container_width=True):
                            from src.services.drive_service import remove_order_from_history
                            success, msg = remove_order_from_history(
                                f"{p['cli_cod']} - {p['cli_nom']}", 
                                p['fecha'], 
                                p['id_pedido']
                            )
                            if success:
                                st.session_state.pedidos.pop(i)
                                st.success("✅ Eliminado de Drive y Local")
                                st.rerun()
                            else:
                                st.error(f"❌ Error: {msg}")
        
        if len(st.session_state.pedidos) > 0:
            # UNIFICADO: st.download_button genera al momento
            try:
                semana_actual = f_elab.isocalendar()[1]
                semana_str = f"S{semana_actual:02d}"
                data_excel = generar_excel_faltantes(st.session_state.pedidos, f_elab, f_ini, f_fin)
                st.download_button(
                    "⬇️ Descargar Reporte (.xlsx)", 
                    data=data_excel, 
                    file_name=f"FALTANTES - 3354 - {semana_str}.xlsx", 
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                    type="primary"
                )
            except Exception as e: 
                # En este caso mostramos el botón deshabilitado o con el error si algo falla en la preparación
                st.button(f"⚠️ Error preparing Excel: {e}", disabled=True, width="stretch")
        else:
            st.info("Agrega pedidos en la pestaña 'Registrar' para generar el reporte.")
