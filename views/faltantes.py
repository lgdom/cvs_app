import streamlit as st
import pandas as pd
import utils

def render_view(df_productos, df_clientes):
    st.header("📝 Generador de Reporte de Faltantes")
    
    # Sidebar: Botón de reset específico
    with st.sidebar:
        st.divider()
        st.markdown("### ⚙️ Acciones")
        if st.button("🗑️ BORRAR TODO (Reiniciar)", type="primary"):
            st.session_state.pedidos = []
            st.session_state.carrito = []
            st.session_state.cliente_box = None
            st.session_state.memoria_cliente = None
            st.rerun()
            
    tab1, tab2 = st.tabs(["1. Registrar", "2. Descargar Excel"])
    
    with tab1:
        col1, col2 = st.columns([1, 2])
        
        # --- INPUTS ---
        with col1:
            st.subheader("Datos")
            
            # Persistencia Cliente
            lista_opciones = df_clientes['DISPLAY'].tolist()
            try: idx_guardado = lista_opciones.index(st.session_state.memoria_cliente)
            except: idx_guardado = None

            def actualizar_cliente():
                st.session_state.memoria_cliente = st.session_state.cliente_box

            st.selectbox(
                "Cliente:", options=df_clientes['DISPLAY'], index=idx_guardado,
                placeholder="Buscar...", key="cliente_box", on_change=actualizar_cliente
            )
            
            # Persistencia Fecha
            def actualizar_fecha():
                st.session_state.memoria_fecha = st.session_state.fecha_box

            fecha_input = st.date_input(
                "Fecha:", value=st.session_state.memoria_fecha,
                key="fecha_box", on_change=actualizar_fecha
            )
            
            st.divider()
            st.subheader("Producto")
            
            query_faltantes = st.text_input("Buscar:", placeholder="Nombre, Clave...", key="search_faltantes_input").upper()
            
            if 'reset_search_faltantes' not in st.session_state: st.session_state.reset_search_faltantes = 0
            
            if query_faltantes:
                mask = df_productos['SEARCH_INDEX'].str.contains(query_faltantes, na=False)
                resultados_f = df_productos[mask].copy()
                
                # Limpieza visual
                resultados_f = resultados_f.dropna(subset=['DESCRIPCION'])
                resultados_f = resultados_f.drop_duplicates(subset=['CODIGO'], keep='first')
                cols_mostrar = ['CODIGO', 'DESCRIPCION', 'SUSTANCIA']
                cols_existentes = [c for c in cols_mostrar if c in resultados_f.columns]
                resultados_f = resultados_f[cols_existentes]
                
                key_table = f"table_results_{st.session_state.reset_search_faltantes}"
                
                event_f = st.dataframe(
                    resultados_f, width="stretch", hide_index=True,
                    on_select="rerun", selection_mode="single-row", key=key_table
                )
                
                if len(event_f.selection.rows) > 0:
                    idx = event_f.selection.rows[0]
                    row_selected = resultados_f.iloc[idx]
                    
                    st.success(f"Seleccionado: **{row_selected['DESCRIPCION']}**")
                    
                    c_qty, c_btn = st.columns([1, 1])
                    cantidad = c_qty.number_input("Cantidad:", min_value=1, value=1, key="qty_faltantes_input")
                    
                    def agregar_seleccion():
                        if st.session_state.cliente_box:
                            item = {
                                "CODIGO": row_selected['CODIGO'],
                                "DESCRIPCION": row_selected['DESCRIPCION'],
                                "SOLICITADA": cantidad,
                                "SURTIDO": 0,
                                "O.C.": "N/A"
                            }
                            st.session_state.carrito.append(item)
                            st.session_state.reset_search_faltantes += 1 
                            st.session_state.search_faltantes_input = "" 
                            st.session_state.qty_faltantes_input = 1     
                        else:
                            st.warning("⚠️ ¡Falta seleccionar el Cliente arriba!")

                    c_btn.button("➕ Agregar", on_click=agregar_seleccion, use_container_width=True)

        # --- CARRITO ---
        with col2:
            st.subheader("🛒 Carrito")
            if st.session_state.carrito:
                df_cart = pd.DataFrame(st.session_state.carrito)
                df_edited = st.data_editor(
                    df_cart, width="stretch", num_rows="dynamic", key="editor_data",
                    column_config={
                        "SOLICITADA": st.column_config.NumberColumn("Solicitada", width="small"),
                        "SURTIDO": st.column_config.NumberColumn("Surtido", width="small"),
                        "O.C.": st.column_config.TextColumn("O.C.", width="small")
                    }
                )
                
                if not df_edited.equals(df_cart): st.session_state.carrito = df_edited.to_dict('records')
                
                def finalizar_pedido_cb():
                    if st.session_state.cliente_box:
                        cod_cli, nom_cli = st.session_state.cliente_box.split(" - ", 1)
                        pedido_nuevo = {
                            "cli_cod": cod_cli,
                            "cli_nom": nom_cli,
                            "fecha": fecha_input,
                            "items": pd.DataFrame(st.session_state.carrito)
                        }
                        st.session_state.pedidos.append(pedido_nuevo)
                        st.session_state.carrito = []
                        st.session_state.cliente_box = None
                        st.session_state.search_faltantes_input = ""
                    else:
                        st.error("Falta Cliente")

                st.button("💾 TERMINAR PEDIDO", type="primary", use_container_width=True, on_click=finalizar_pedido_cb)
            else:
                st.info("El carrito está vacío.")

    with tab2:
        st.metric("Pedidos Listos", len(st.session_state.pedidos))
        for i, p in enumerate(st.session_state.pedidos):
            with st.expander(f"{i+1}. {p['cli_nom']}"):
                st.dataframe(p['items'])
                if st.button("Borrar", key=f"del_{i}"):
                    st.session_state.pedidos.pop(i); st.rerun()
        
        if st.button("🚀 GENERAR EXCEL", disabled=(len(st.session_state.pedidos)==0)):
            b = utils.generar_excel_pedidos(st.session_state.pedidos)
            if b:
                st.download_button(
                    "⬇️ DESCARGAR", data=b, file_name="Faltantes.xlsx", 
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.error("Error al generar el Excel.")
