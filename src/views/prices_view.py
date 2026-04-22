import streamlit as st
import pandas as pd
import os
from datetime import datetime

def render():
    st.title("🏷️ Comparador de Precios")
    st.markdown("Consulta y compara las listas de precios vigentes de manera rápida.")

    # Carga de datos
    csv_path = "data/precios.csv"
    if not os.path.exists(csv_path):
        st.error(f"No se encontró el archivo de precios en {csv_path}")
        return

    @st.cache_data
    def load_data():
        df_p = pd.read_csv(csv_path)
        
        # Unir con catálogo para sustancia
        prod_path = "data/productos.csv"
        if os.path.exists(prod_path):
            df_cat = pd.read_csv(prod_path)
            df_cat = df_cat[['CLAVE', 'SUSTANCIA ACTIVA']].drop_duplicates('CLAVE')
            df_p = pd.merge(df_p, df_cat, on='CLAVE', how='left')
        
        # Cargar descuentos
        desc_path = "data/descuentos.csv"
        df_desc = pd.read_csv(desc_path) if os.path.exists(desc_path) else None
        
        # Limpieza básica
        df_p['CLAVE'] = df_p['CLAVE'].astype(str)
        df_p['NOMBRE'] = df_p['NOMBRE'].astype(str)
        if 'SUSTANCIA ACTIVA' in df_p.columns:
            df_p['SUSTANCIA ACTIVA'] = df_p['SUSTANCIA ACTIVA'].fillna("NO ESPECIFICADA").astype(str)
            
        return df_p, df_desc

    df_precios, df_descuentos = load_data()

    # --- LÓGICA DE DESCUENTOS ---
    def get_discount_pct(clave, lista_num):
        if df_descuentos is None: return 0
        try:
            # Lista 3 es base (0%)
            if str(lista_num) == "3": return 0
            
            # Buscar la fila de la lista en descuentos
            row = df_descuentos[df_descuentos['LISTA'].astype(str) == str(lista_num)]
            if row.empty: return 0
            
            # Identificar si es MICRO (V01) o MACRO (V02)
            if clave.startswith('V01'):
                return float(row.iloc[0]['MICRO'])
            elif clave.startswith('V02'):
                return float(row.iloc[0]['MACRO'])
            return 0
        except:
            return 0

    # Columnas de precios (excluyendo metadatos)
    exclude = ['CLAVE', 'NOMBRE', 'SUSTANCIA ACTIVA']
    price_cols = [c for c in df_precios.columns if c not in exclude]

    # --- INICIALIZACIÓN DE ESTADO ---
    if 'prices_search' not in st.session_state: st.session_state.prices_search = ""
    if 'prices_cantidad' not in st.session_state: st.session_state.prices_cantidad = 1
    if 'prices_lista_ref' not in st.session_state: st.session_state.prices_lista_ref = "9"
    if 'prices_orden' not in st.session_state: st.session_state.prices_orden = "Mayor Ahorro"
    if 'prices_tipo_vista' not in st.session_state: st.session_state.prices_tipo_vista = "Tabla"
    if 'prices_visibles' not in st.session_state: 
        defaults = [l for l in ['5', '9', '23'] if l in price_cols]
        st.session_state.prices_visibles = defaults if defaults else price_cols[:3]

    # --- FILTROS ---
    col1, col2 = st.columns([2, 1])
    with col1:
        busqueda = st.text_input(
            "🔍 Buscar Producto", 
            value=st.session_state.prices_search,
            placeholder="Nombre, Clave o Sustancia...", 
            key="prices_search_input"
        ).upper()
        st.session_state.prices_search = busqueda
    
    with col2:
        listas_visibles = st.multiselect(
            "Listas Visibles", 
            options=price_cols, 
            default=st.session_state.prices_visibles,
            key="prices_visibles_input"
        )
        st.session_state.prices_visibles = listas_visibles
        
        tipo_vista = st.radio(
            "Modo de Vista", ["Tabla", "Fichas"], 
            index=0 if st.session_state.prices_tipo_vista == "Tabla" else 1,
            key="prices_tipo_vista_input",
            horizontal=True, label_visibility="collapsed"
        )
        st.session_state.prices_tipo_vista = tipo_vista
    
    # Filtrado extendido: Nombre, Clave o Sustancia (Sigue siendo buscable aunque no se vea en tabla)
    mask = (
        df_precios['NOMBRE'].str.contains(busqueda, na=False) | 
        df_precios['CLAVE'].str.contains(busqueda, na=False)
    )
    if 'SUSTANCIA ACTIVA' in df_precios.columns:
        mask = mask | df_precios['SUSTANCIA ACTIVA'].str.contains(busqueda, na=False)
    
    df_filtered = df_precios[mask]

    if df_filtered.empty:
        st.info("No se encontraron productos con ese criterio.")
        return

    # --- SIMULADOR Y REFERENCIA ---
    with st.sidebar:
        st.subheader("⚙️ Configuración")
        cantidad = st.number_input(
            "Cantidad de piezas", 
            min_value=1, 
            value=int(st.session_state.prices_cantidad), 
            step=1,
            key="prices_cantidad_input"
        )
        st.session_state.prices_cantidad = cantidad
        
        # Asegurar que el index de la lista_ref sea válido
        try:
            current_ref_idx = price_cols.index(st.session_state.prices_lista_ref)
        except:
            current_ref_idx = 0

        lista_ref = st.selectbox(
            "📍 Lista actual del cliente",
            options=price_cols,
            index=current_ref_idx,
            key="prices_lista_ref_input"
        )
        st.session_state.prices_lista_ref = lista_ref
        
        orden_ahorro = st.selectbox(
            "Orden de Mejora", 
            ["Mayor Ahorro", "Menor Ahorro", "Número de Lista"],
            index=["Mayor Ahorro", "Menor Ahorro", "Número de Lista"].index(st.session_state.prices_orden),
            key="side_orden_ahorro_input"
        )
        st.session_state.prices_orden = orden_ahorro

    # --- VISUALIZACIÓN ---
    if tipo_vista == "Fichas":
        st.markdown(f"### Resultados ({len(df_filtered)})")
        for _, row in df_filtered.iterrows():
            with st.expander(f"{row['NOMBRE']} ({row['CLAVE']})", expanded=(len(df_filtered) == 1)):
                if 'SUSTANCIA ACTIVA' in row and row['SUSTANCIA ACTIVA'] != "NO ESPECIFICADA":
                    st.markdown(f"<small style='color:gray'>Sustancia: {row['SUSTANCIA ACTIVA']}</small>", unsafe_allow_html=True)
                
                # Precios de Referencia y Base
                precio_ref_unid = float(row.get(lista_ref, 0))
                precio_base_unid = float(row.get('3', 0))
                
                # Ahorro Absoluto de la Lista de Referencia (vs L3)
                ahorro_ref_abs = (precio_base_unid - precio_ref_unid) * cantidad
                pct_ref_abs = get_discount_pct(row['CLAVE'], lista_ref)

                st.markdown(f"<div style='padding:10px; border-left: 5px solid #6c757d; background-color: rgba(108, 117, 125, 0.1); border-radius: 4px; margin-bottom:15px;'>"
                            f"<div style='font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; color: gray;'>Referencia ({lista_ref}) • ({pct_ref_abs}%)</div>"
                            f"<div style='font-size: 1.4rem; font-weight: bold;'>${(precio_ref_unid * cantidad):,.2f}</div>"
                            f"</div>", unsafe_allow_html=True)

                # Grid para mejoras
                m_col1, m_col2 = st.columns(2)
                mejoras = []
                
                for col_name in price_cols:
                    if str(col_name) == str(lista_ref): continue
                    
                    precio_unitario = float(row[col_name])
                    if precio_unitario < precio_ref_unid:
                        total_fila = precio_unitario * cantidad
                        
                        # Mejora Relativa (vs Referencia)
                        ahorro_rel = (precio_ref_unid - precio_unitario) * cantidad
                        pct_rel = ((precio_ref_unid - precio_unitario) / precio_ref_unid) * 100 if precio_ref_unid != 0 else 0
                        
                        # Porcentaje Base (desde descuentos.csv)
                        pct_base = get_discount_pct(row['CLAVE'], col_name)

                        # Ahorro Absoluto (vs Lista 3)
                        ahorro_abs = (precio_base_unid - precio_unitario) * cantidad
                        
                        mejoras.append({
                            "col": col_name,
                            "total": total_fila,
                            "ahorro_rel": ahorro_rel,
                            "pct_rel": pct_rel,
                            "pct_base": pct_base,
                            "ahorro_abs": ahorro_abs
                        })
                
                # Sorteo de mejoras
                if orden_ahorro == "Mayor Ahorro":
                    mejoras = sorted(mejoras, key=lambda x: x['ahorro_rel'], reverse=True)
                elif orden_ahorro == "Menor Ahorro":
                    mejoras = sorted(mejoras, key=lambda x: x['ahorro_rel'])
                elif orden_ahorro == "Número de Lista":
                    # Intentamos ordenar numéricamente si las columnas son números
                    try:
                        mejoras = sorted(mejoras, key=lambda x: int(x['col']) if str(x['col']).isdigit() else 999)
                    except:
                        pass

                def get_saving_color(pct):
                    # Escala clásica: Rojo -> Naranja -> Amarillo -> Verde
                    if pct < 3: return "#d32f2f" # Rojo
                    if pct < 7: return "#f57c00" # Naranja
                    if pct < 12: return "#fbc02d" # Amarillo/Oro
                    return "#28a745" # Verde

                for idx, item in enumerate(mejoras):
                    target_col = m_col1 if idx % 2 == 0 else m_col2
                    color_label = get_saving_color(item['pct_rel'])
                    
                    with target_col:
                        st.markdown(f"<div style='margin-bottom:15px; padding: 5px;'>"
                                    f"<div style='font-size: 0.85rem; font-weight: 600;'>Lista {item['col']} "
                                    f"<span style='color: gray;'>(</span>"
                                    f"<span style='color: #28a745;'>-{item['pct_rel']:.1f}%</span> "
                                    f"<span style='color: gray;'>| {item['pct_base']}%</span>"
                                    f"<span style='color: gray;'>)</span></div>"
                                    f"<div style='font-size: 1.5rem; font-weight: 800;'>${item['total']:,.2f}</div>"
                                    f"<div style='color: {color_label}; font-size: 0.85rem;'>- <strong>${item['ahorro_rel']:,.2f}</strong></div>"
                                    f"</div>", unsafe_allow_html=True)
                
                if not mejoras:
                    st.caption("No hay listas que representen una mejora respecto a la base seleccionada.")
    else:
        # Tabla comparativa
        st.markdown(f"### Comparativa de Mejoras (vs Lista {lista_ref})")
        
        # Botón para descargar lo que se está viendo
        cols_to_show = ['CLAVE', 'NOMBRE'] + listas_visibles
        df_table = df_filtered.copy()
        for c in price_cols:
            df_table[c] = df_table[c] * cantidad

        csv_download = df_table[['CLAVE', 'NOMBRE', 'SUSTANCIA ACTIVA'] + listas_visibles].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar resultados CSV",
            data=csv_download,
            file_name=f"precios_filtrados_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
        
        st.dataframe(
            df_table[cols_to_show],
            width='stretch',
            hide_index=True,
            column_config={
                "CLAVE": st.column_config.TextColumn("Clave", width="small"),
                "NOMBRE": st.column_config.TextColumn("Producto", width="large"),
                **{c: st.column_config.NumberColumn(f"L{c}", format="$%.2f") for c in listas_visibles}
            }
        )
        st.info("💡 Consejo: Usa la vista de 'Fichas' arriba para ver el detalle de los porcentajes de ahorro.")

