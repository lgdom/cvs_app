import streamlit as st
import pandas as pd
import utils
import config

def render_view(df_productos, df_clientes):
    st.header("🔍 Buscador de Existencias")

    # --- CARGA DE DATOS (LOCAL O DRIVE) ---
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
            
            df_activo = utils.procesar_inventario(df_raw, df_productos)
            st.session_state.df_inventario_diario = df_activo
            st.session_state.info_archivo = f"Local: {uploaded_file.name}"
            info_origen = st.session_state.info_archivo
            
        except Exception as e:
            st.error(f"Error archivo local: {e}")

    # CASO B: Memoria (Ya cargado)
    elif st.session_state.df_inventario_diario is not None:
        df_activo = st.session_state.df_inventario_diario
        info_origen = st.session_state.get('info_archivo', 'Memoria')

    # CASO C: Drive (Automático)
    elif config.DRIVE_FOLDER_ID:
        with st.spinner("☁️ Sincronizando con Drive..."):
            df_cloud, nombre_archivo, fecha_mod = utils.descargar_de_drive(config.DRIVE_FOLDER_ID)
            
            if df_cloud is not None:
                df_activo = utils.procesar_inventario(df_cloud, df_productos)
                st.session_state.df_inventario_diario = df_activo
                info_str = f"☁️ Nube: {nombre_archivo} | 📅 Fecha: {fecha_mod}"
                st.session_state.info_archivo = info_str
                info_origen = info_str
                st.rerun()
            else:
                if nombre_archivo and "Error" in nombre_archivo: st.error(nombre_archivo)
                else: st.warning("⚠️ Carpeta vacía o sin acceso.")

    # --- INTERFAZ ---
    if df_activo is not None:
        st.success(f"✅ {info_origen}")
        
        col_search, col_reset = st.columns([4, 1])
        with col_reset:
            if st.button("🔄 Recargar Nube"):
                st.session_state.df_inventario_diario = None
                utils.descargar_de_drive.clear()
                st.rerun()
        
        # Buscador
        def actualizar_busqueda_inv():
            st.session_state.memoria_busqueda_inv = st.session_state.input_busqueda_inv

        texto_input = st.text_input(
            "¿Qué buscas?", 
            value=st.session_state.memoria_busqueda_inv,
            placeholder="Nombre, Clave o Sustancia...",
            key="input_busqueda_inv", 
            on_change=actualizar_busqueda_inv
        )
        
        busqueda = texto_input.upper()
        resultados = pd.DataFrame()
        
        if busqueda:
            mask = df_activo['INDICE_BUSQUEDA'].str.contains(busqueda, na=False)
            resultados = df_activo[mask].drop(columns=['INDICE_BUSQUEDA'])
            st.success(f"Encontrados: {len(resultados)}")
            
            dynamic_key = f"search_table_{st.session_state.reset_counter}"
            event = st.dataframe(
                resultados, width="stretch", hide_index=True,
                on_select="rerun", selection_mode="multi-row", key=dynamic_key 
            )
            
            if len(event.selection.rows) > 0:
                st.divider()
                c_btn, c_qty = st.columns([3, 1])
                qty_add = c_qty.number_input("Piezas (Opcional):", min_value=0, value=0, key="qty_add_rev")
                
                if c_btn.button(f"⬇️ Agregar Selección ({len(event.selection.rows)})"):
                    filas_seleccionadas = resultados.iloc[event.selection.rows].copy()
                    filas_seleccionadas['SOLICITADO'] = qty_add if qty_add > 0 else "-"
                    
                    nuevos_items = filas_seleccionadas.to_dict('records')
                    st.session_state.lista_revision.extend(nuevos_items)
                    st.session_state.reset_counter += 1 
                    st.toast("✅ Agregado")
                    st.rerun() 
        else:
            st.info("Inventario cargado. Escribe arriba para filtrar.")

        # --- LISTA DE REVISIÓN ---
        st.divider()
        st.subheader("📋 Tu Lista de Revisión")
        
        col_info, col_borrar_sel, col_borrar_todo = st.columns([3, 2, 1])
        
        if st.session_state.lista_revision:
            df_rev = pd.DataFrame(st.session_state.lista_revision)
            cols_orden = ['CODIGO', 'PRODUCTO', 'SUSTANCIA', 'EXISTENCIA', 'CORTA_CAD', 'SOLICITADO']
            for c in cols_orden:
                if c not in df_rev.columns: df_rev[c] = "-"
            df_rev = df_rev[cols_orden]

            def estilo_existencias(row):
                existencia = pd.to_numeric(row['EXISTENCIA'], errors='coerce') or 0
                corta_cad = pd.to_numeric(row['CORTA_CAD'], errors='coerce') or 0
                colores = [''] * len(row)
                if existencia == 0 and corta_cad == 0: colores = ['background-color: #390D10'] * len(row)
                elif existencia == 0 and corta_cad > 0: colores = ['background-color: #4B3718'] * len(row)
                return colores

            event_revision = st.dataframe(
                df_rev.style.apply(estilo_existencias, axis=1),
                width="stretch", hide_index=True, on_select="rerun", selection_mode="multi-row",
                key="tabla_revision_final"
            )
            
            filas_seleccionadas = event_revision.selection.rows
            with col_borrar_sel:
                if filas_seleccionadas:
                    if st.button(f"🗑️ Borrar ({len(filas_seleccionadas)})"):
                        indices_a_borrar = set(filas_seleccionadas)
                        st.session_state.lista_revision = [
                            item for i, item in enumerate(st.session_state.lista_revision) if i not in indices_a_borrar
                        ]
                        st.rerun()
            with col_borrar_todo:
                if st.button("🔥 Borrar Todo"):
                    st.session_state.lista_revision = []
                    st.rerun()

            # --- GENERAR IMAGEN ---
            st.divider()
            st.caption("Configuración de la Imagen:")
            c_cli, c_opt = st.columns([2, 1])
            with c_cli:
                cliente_foto = st.selectbox("Título (Opcional):", options=df_clientes['DISPLAY'], index=None, placeholder="Sin título...", key="cli_foto_input")
            with c_opt:
                incluir_sustancia = st.checkbox("Incluir columna 'Sustancia'", value=True)

            if st.button("📸 Descargar Tabla como Imagen"):
                try:
                    buf = utils.generar_imagen_lista(df_rev, cliente_foto, incluir_sustancia)
                    st.download_button(
                        label="⬇️ Guardar PNG", data=buf, file_name="Lista_Revision.png", mime="image/png"
                    )
                except Exception as e:
                    st.error(f"Error generando imagen: {e}")
        else:
            st.caption("Selecciona productos arriba para armar tu lista de revisión.")
