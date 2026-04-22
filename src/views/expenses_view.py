import streamlit as st
from datetime import datetime
import pandas as pd
from src.services.expenses_service import generar_excel_comprobacion, generar_excel_solicitud

def render():
    def actualizar_calculos_frontend():
        val = st.session_state.get('f_monto_base', 600.0)
        concepto = st.session_state.get('f_concepto', 'COMBUSTIBLE')
        usa_ieps = st.session_state.get('f_ieps_toggle', True)
        
        if concepto == "COMBUSTIBLE" and usa_ieps:
            # Fórmula mágica para gasolina en frontera (Magna aprox)
            iva = round(val / 13.864, 2)
            imp = round(val - iva, 2)
        else:
            # Desglose estándar 8%
            imp = round(val / 1.08, 2)
            iva = round(val - imp, 2)
            
        st.session_state.f_importe = imp
        st.session_state.f_tasa = iva

    def get_periodo(base_date, tipo_periodo, force_current=False):
        # Convertir a datetime si es solo date
        now = pd.to_datetime(base_date)
        # Lunes de esa semana base
        monday_base = now - pd.Timedelta(days=now.weekday())
        
        if force_current:
            start = monday_base
        elif tipo_periodo == 'solicitud':
            # Si la base es lunes, el inmediato es hoy. Si no, el de la próxima semana.
            if now.weekday() == 0: start = now
            else: start = monday_base + pd.Timedelta(days=7)
        else: # comprobación 
            # Si la base es lunes, se reporta la semana pasada. 
            # Si es cualquier otro día (ej. viernes/domingo), el inmediato anterior es el lunes de esa misma semana.
            if now.weekday() == 0: start = monday_base - pd.Timedelta(days=7)
            else: start = monday_base
            
        end = start + pd.Timedelta(days=4) # Viernes
        return start.date(), end.date()

    def sync_periodo_sol():
        base = st.session_state.get('f_sol_date', datetime.today())
        is_curr = st.session_state.get('is_curr_sol', False)
        ini, fin = get_periodo(base, 'solicitud', is_curr)
        st.session_state.s_ini = ini
        st.session_state.s_fin = fin

    def sync_periodo_just():
        base = st.session_state.get('j_elab', datetime.today())
        is_curr = st.session_state.get('is_curr_just', False)
        ini, fin = get_periodo(base, 'comprobacion', is_curr)
        st.session_state.j_ini = ini
        st.session_state.j_fin = fin

    st.header("💸 Gestión de Viáticos")
    
    # --- CÁLCULO DE SEMANA ACTUAL ---
    semana_actual = datetime.today().isocalendar()[1]
    semana_str = f"S{semana_actual:02d}"

    tab1, tab2 = st.tabs(["📝 Solicitud", "✅ Comprobación"])
    
    # --- TAB 1: SOLICITUD ---
    with tab1:
        st.subheader("Generar Solicitud de Viáticos")
        
        # Inicializar claves si no existen
        if "f_sol_date" not in st.session_state: st.session_state.f_sol_date = datetime.today()
        if "s_ini" not in st.session_state or "s_fin" not in st.session_state:
            ini, fin = get_periodo(st.session_state.f_sol_date, 'solicitud', False)
            st.session_state.s_ini, st.session_state.s_fin = ini, fin

        c1, c_toggle = st.columns([1.5, 1])
        with c1:
            fecha_sol = st.date_input("Fecha Solicitud", key="f_sol_date", on_change=sync_periodo_sol)
        with c_toggle:
            st.markdown("<br>", unsafe_allow_html=True) # Espaciador para alinear con el label del date_input
            is_curr_sol = st.toggle("Semana actual", key="is_curr_sol", help="Ajusta las fechas al lunes y viernes de la semana de solicitud", on_change=sync_periodo_sol)
        
        c2_ini, c3_fin = st.columns(2)
        inicio = c2_ini.date_input("Inicio Periodo", key="s_ini")
        fin = c3_fin.date_input("Fin Periodo", key="s_fin")
        
        c4, c5 = st.columns(2)
        monto_sol = c4.number_input("Monto Solicitado", value=600.0, step=100.0)
        costo_est = c5.number_input("Costo Estimado", value=monto_sol, step=100.0)
        
        st.markdown("#### Desglose de Presupuesto")
        # Alimentos
        c_al_m, c_al_d = st.columns(2)
        m_ali = c_al_m.number_input("Alimentos ($)", value=0.0)
        d_ali = c_al_d.number_input("Días Alimentos", value=0, step=1)
        
        # Combustible
        c_co_m, c_co_d = st.columns(2)
        m_com = c_co_m.number_input("Combustible ($)", value=120.0)
        d_com = c_co_d.number_input("Días Combustible", value=5, step=1)

        # Hospedaje
        c_ho_m, c_ho_d = st.columns(2)
        m_hos = c_ho_m.number_input("Hospedaje ($)", value=0.0)
        d_hos = c_ho_d.number_input("Días Hospedaje", value=0, step=1)
        
        # Transporte
        c_tr_m, c_tr_d = st.columns(2)
        m_tra = c_tr_m.number_input("Transporte ($)", value=00.0)
        d_tra = c_tr_d.number_input("Días Transporte", value=0, step=1)
        
        # Lógica de descarga en un solo paso
        datos_sol = {
            'fecha_solicitud': fecha_sol,
            'inicio_periodo': inicio,
            'fin_periodo': fin,
            'monto_solicitado': monto_sol,
            'costo_estimado': costo_est,
            'presupuesto': {
                'alimentos': {'monto': m_ali, 'dias': d_ali},
                'combustible': {'monto': m_com, 'dias': d_com},
                'hospedaje': {'monto': m_hos, 'dias': d_hos},
                'transporte': {'monto': m_tra, 'dias': d_tra}
            }
        }
        
        try:
            excel_sol = generar_excel_solicitud(datos_sol)
            st.download_button(
                "⬇️ Descargar Solicitud (.xlsx)",
                data=excel_sol,
                file_name=f"SOLICITUD DE VIATICOS - 3354 - {semana_str}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
                type="primary"
            )
            st.caption(f"📅 Archivo configurado para la **Semana {semana_actual}**")
            st.caption("💡 Para obtener el PDF, abre el Excel y guarda como PDF.")
        except Exception as e:
            st.error(f"Error preparando solicitud: {e}")

    # --- TAB 2: COMPROBACIÓN ---
    with tab2:
        st.subheader("Generar Comprobación de Viáticos")
        
        # Inicializar claves si no existen
        if "j_elab" not in st.session_state: st.session_state.j_elab = datetime.today()
        if "j_ini" not in st.session_state or "j_fin" not in st.session_state:
            ini, fin = get_periodo(st.session_state.j_elab, 'comprobacion', False)
            st.session_state.j_ini, st.session_state.j_fin = ini, fin

        col_fe, col_toggle = st.columns([1.5, 1])
        with col_fe:
            f_elab = st.date_input("Fecha Elaboración", key="j_elab", on_change=sync_periodo_just)
        with col_toggle:
            st.markdown("<br>", unsafe_allow_html=True) # Espaciador
            is_curr_just = st.toggle("Semana actual", key="is_curr_just", help="Ajusta las fechas al lunes y viernes de la semana de elaboración", on_change=sync_periodo_just)
        
        col_fe1, col_fe2 = st.columns(2)
        ini_just = col_fe1.date_input("Inicio Justificación", key="j_ini")
        fin_just = col_fe2.date_input("Fin Justificación", key="j_fin")
        
        total_dep = st.number_input("Total Depositado", value=600.0, step=10.0, key="j_tot")
        
        st.markdown("#### Facturas (Máx 13)")
        
        if 'facturas' not in st.session_state:
            st.session_state.facturas = []

        # --- ESTADO DE CAMPOS DEL FORMULARIO ---
        # Inicializar claves si no existen
        if "f_fecha" not in st.session_state: st.session_state["f_fecha"] = datetime.today()
        if "f_folio" not in st.session_state: st.session_state["f_folio"] = ""
        if "f_concepto" not in st.session_state: st.session_state["f_concepto"] = "COMBUSTIBLE"
        if "f_concepto_otro" not in st.session_state: st.session_state["f_concepto_otro"] = ""
        if "f_ieps_toggle" not in st.session_state: st.session_state["f_ieps_toggle"] = True
        if "f_monto_base" not in st.session_state: st.session_state["f_monto_base"] = 600.0
        if "f_importe" not in st.session_state: 
            # Inicializamos con el cálculo de gasolina (IVA = 600 / 13.864)
            st.session_state["f_tasa"] = round(600.0 / 13.864, 2)
            st.session_state["f_importe"] = round(600.0 - st.session_state["f_tasa"], 2)
        if "f_tasa" not in st.session_state: st.session_state["f_tasa"] = round(600.0 / 13.864, 2)
        if "f_ish" not in st.session_state: st.session_state["f_ish"] = 0.0
        if "f_obs" not in st.session_state: st.session_state["f_obs"] = "Ninguna"
        if "f_obs_otro" not in st.session_state: st.session_state["f_obs_otro"] = ""

        def reset_form():
             st.session_state["f_fecha"] = datetime.today()
             st.session_state["f_folio"] = ""
             st.session_state["f_concepto"] = "COMBUSTIBLE"
             st.session_state["f_concepto_otro"] = ""
             st.session_state["f_importe"] = 0.0
             st.session_state["f_tasa"] = 0.0
             st.session_state["f_ish"] = 0.0
             st.session_state["f_obs"] = "Ninguna"
             st.session_state["f_obs_otro"] = ""

        # Botón de Reset fuera del formulario
        st.button("🔄 Reiniciar Campos", on_click=reset_form)

        # Reemplazamos st.form por un contenedor simple para permitir reactividad inmediata
        with st.container(border=True):
            c_f1, c_f2, c_f3 = st.columns([1, 1, 2])
            # Al usar key, el widget lee y escribe directamente en st.session_state por defecto
            f_fecha = c_f1.date_input("Fecha Factura", key="f_fecha")
            f_folio = c_f2.text_input("No. Factura", key="f_folio")
            
            # Concepto
            opts_con = ["COMBUSTIBLE", "COMISIÓN POR USO ATM", "OTRO"]
            f_concepto = c_f3.selectbox("Concepto", opts_con, key="f_concepto", on_change=actualizar_calculos_frontend)
            
            f_concepto_otro = ""
            if f_concepto == "OTRO":
                f_concepto_otro = st.text_input("Especificar Concepto", key="f_concepto_otro")
            
            # Campo de cálculo individual
            c_calc1, c_calc2 = st.columns([2, 1])
            with c_calc1:
                st.number_input("Monto de la factura", value=600.0, step=100.0, key="f_monto_base", on_change=actualizar_calculos_frontend, help="Usa este campo para desglosar el importe e IVA")
            
            with c_calc2:
                if f_concepto == "COMBUSTIBLE":
                    st.toggle("Ajuste IEPS", key="f_ieps_toggle", on_change=actualizar_calculos_frontend, help="Ajusta el IVA usando el factor de combustibles (13.864)")

            c_f4, c_f5, c_f6 = st.columns(3)
            f_importe = c_f4.number_input("Importe ($)", min_value=0.0, step=0.1, key="f_importe")
            f_tasa = c_f5.number_input("Tasa IVA", min_value=0.0, step=0.1, key="f_tasa")
            f_ish = c_f6.number_input("I.S.H.", min_value=0.0, step=0.1, key="f_ish")
            
            # Observaciones
            opts_obs = ["NO. FACTURA CORRESPONDE A FOLIO DE TICKET DE ATM", "OTRO", "Ninguna"]
            f_obs = st.selectbox("Observaciones", opts_obs, key="f_obs")
            
            f_obs_otro = ""
            if f_obs == "OTRO":
                f_obs_otro = st.text_input("Especificar Observaciones", key="f_obs_otro")
                
            add = st.button("➕ Agregar Factura", width="stretch", type="secondary")
            
            if add:
                item = {
                    'fecha': f_fecha,
                    'factura': f_folio,
                    'concepto': f_concepto,
                    'concepto_otro': f_concepto_otro,
                    'importe': f_importe,
                    'tasa': f_tasa,
                    'ish': f_ish,
                    'observaciones': '' if f_obs == "Ninguna" else f_obs,
                    'observaciones_otro': f_obs_otro
                }
                st.session_state.facturas.append(item)
                st.success("Factura agregada")
                st.rerun()

        if st.session_state.facturas:
            st.markdown("##### Listado Actual")
            df_fac = pd.DataFrame(st.session_state.facturas)
            
            # Formatear fecha para visualización
            df_display = df_fac.copy()
            if 'fecha' in df_display.columns:
                df_display['fecha'] = pd.to_datetime(df_display['fecha']).dt.strftime('%d/%m/%Y')
            
            # TABLA CON SELECCIÓN PARA BORRAR
            event_del = st.dataframe(
                df_display, 
                width="stretch",
                hide_index=True,
                on_select="rerun",          
                selection_mode="multi-row",
                key="tabla_borrar_facturas"
            )
            
            col_del, col_gen = st.columns([1, 2])
            
            with col_del:
                filas_sel = event_del.selection.rows
                if filas_sel:
                    if st.button(f"🗑️ Borrar ({len(filas_sel)})"):
                         # Reconstruimos la lista EXCLUYENDO los índices seleccionados
                        indices_a_borrar = set(filas_sel)
                        st.session_state.facturas = [
                            item for i, item in enumerate(st.session_state.facturas) 
                            if i not in indices_a_borrar
                        ]
                        st.rerun()
                
                if st.button("🔥 Borrar Todo Lista"):
                    st.session_state.facturas = []
                    st.rerun()
             
            with col_gen:
                if st.session_state.facturas:
                    rango = f"{ini_just.strftime('%d/%m/%Y')} - {fin_just.strftime('%d/%m/%Y')}"
                    datos_comp = {
                        'rango_fechas': rango,
                        'fecha_elaboracion': f_elab,
                        'total_depositado': total_dep,
                        'items': st.session_state.facturas
                    }
                    try:
                        excel_comp = generar_excel_comprobacion(datos_comp)
                        st.download_button(
                            "⬇️ Descargar Comprobación (.xlsx)",
                            data=excel_comp,
                            file_name=f"COMPROBACION DE VIATICOS - 3354 - {semana_str}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            width="stretch",
                            type="primary"
                        )
                        st.caption(f"📅 Archivo configurado para la **Semana {semana_actual}**")
                        st.caption("💡 Para obtener el PDF, abre el Excel y guarda como PDF.")
                    except Exception as e:
                        st.error(f"Error preparando comprobación: {e}")
                else:
                    st.button("Generar Excel Comprobación", type="primary", disabled=True, width="stretch")
