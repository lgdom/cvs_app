import requests
import streamlit as st
from src.config import (
    THERION_LOGIN_URL, THERION_ALTA_PEDIDO_URL, THERION_EDIT_PEDIDO_URL,
    THERION_API_URL, THERION_BASE_URL
)
import time
import re
import json
import urllib3
import pandas as pd
from io import StringIO
from bs4 import BeautifulSoup

# El ERP Therion usa certificado SSL auto-firmado
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TherionService:
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False  # Certificado auto-firmado del ERP
        self.logged_in = False
        self.api_token = None
        self.user_creds = {}
        # Usar ruta absoluta en /tmp para evitar problemas de permisos/cwd
        self.debug_file = "/tmp/debug_erp.txt"


    def _log(self, msg):
        try:
            with open(self.debug_file, "a") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
        except:
            pass

    def _get_tokens(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        tokens = {}
        # Capturar TODOS los inputs (hidden, text, number, etc.)
        # ASP.NET requiere que se reenvíen todos los campos en cada postback
        for input_tag in soup.find_all('input'):
            name = input_tag.get('name')
            itype = input_tag.get('type', 'text').lower()
            # Excluir botones submit e image para no disparar clicks accidentales
            if name and itype not in ('submit', 'image', 'button'):
                if itype in ('checkbox', 'radio'):
                    if input_tag.has_attr('checked'):
                        tokens[name] = input_tag.get('value', 'on')
                else:
                    tokens[name] = input_tag.get('value', '')
        
        # Capturar selects con su valor seleccionado
        for select_tag in soup.find_all('select'):
            name = select_tag.get('name')
            if name:
                selected_opt = select_tag.find('option', selected=True)
                if selected_opt:
                    tokens[name] = selected_opt.get('value', '')
                else:
                    first_opt = select_tag.find('option')
                    if first_opt:
                        tokens[name] = first_opt.get('value', '')
        return tokens, soup

    def _extract_options(self, soup, select_id):
        select = soup.find('select', {'id': select_id})
        if not select:
            return []
        return [{'value': opt['value'], 'text': opt.text} for opt in select.find_all('option') if opt.get('value')]

    def login(self, username, password):
        """Inicia sesión tanto en la web como en la API del ERP."""
        self.user_creds = {"user": username, "pass": password}
        try:
            # 1. Login Web (Para compatibilidad y consultas HTML si fallan los catálogos API)
            res = self.session.get(THERION_LOGIN_URL, timeout=15)
            tokens, _ = self._get_tokens(res.text)
            
            payload = tokens.copy()
            payload.update({
                'ctl00$ContentPlaceHolder1$txtUsuario': username,
                'ctl00$ContentPlaceHolder1$txtPassword': password,
                'ctl00$ContentPlaceHolder1$loginButton': 'Ingresar',
                'Language': 'es'
            })
            
            res_login = self.session.post(THERION_LOGIN_URL, data=payload, timeout=20)
            web_success = "txtUsuario" not in res_login.text
            
            # 2. Login API (Nuevo motor descubierto en APK)
            api_url = f"{THERION_API_URL}/auth/loginUserTherion"
            self._log(f"Intentando login API en {api_url}")
            api_res = requests.post(
                api_url,
                json={"user": username, "pass": password},
                timeout=10
            )
            self._log(f"Respuesta API Login: {api_res.status_code} - {api_res.text[:100]}")
            
            if api_res.status_code == 200:
                self.api_token = api_res.json().get("token")
                self._log("Token API obtenido con éxito")
            
            if web_success or self.api_token:
                self.logged_in = True
                return True, "Login exitoso (Motor Híbrido)"
            
            return False, "Credenciales incorrectas"
        except Exception as e:
            return False, f"Error de conexión: {str(e)}"

    def get_client_config(self, client_code):
        """Obtiene opciones de pago y listas de precios."""
        if not self.logged_in: return None, "No autenticado"
        
        # Intentar vía API primero (más rápido y limpio)
        if self.api_token:
            headers = {"Authorization": f"Bearer {self.api_token}"}
            try:
                # Nota: Estos endpoints se dedujeron del APK
                metodos_res = requests.get(f"{THERION_API_URL}/ventas/metodosPago", headers=headers, timeout=5)
                formas_res = requests.get(f"{THERION_API_URL}/ventas/formasPago", headers=headers, timeout=5)
                
                if metodos_res.status_code == 200 and formas_res.status_code == 200:
                    metodos = [{'value': str(m['metodoPagoId']), 'text': f"{m['clave']} {m['descripcion']}"} for m in metodos_res.json()]
                    formas = [{'value': str(f['formaPagoId']), 'text': f"{f['clave']} {f['descripcion']}"} for f in formas_res.json()]
                    
                    # Para las listas de precios, la API suele requerir el ID del cliente. 
                    # Por ahora usamos el fallback técnico que ya funcionaba bien.
                    listas = [{'value': l, 'text': l} for l in ["1", "2", "3", "3a", "4", "5", "5a", "9a", "13a"]]
                    
                    return {
                        'metodos': metodos, 
                        'formas': formas,
                        'listas': listas
                    }, "Éxito (API)"
            except:
                pass # Si falla API, cae al método Web

        # Fallback: Método Web (Ya implementado anteriormente)
        try:
            res = self.session.get(THERION_ALTA_PEDIDO_URL, timeout=15)
            tokens, _ = self._get_tokens(res.text)
            
            payload = tokens.copy()
            payload.update({
                'ctl00$MainContent$txtClienteClave': client_code,
                '__EVENTTARGET': 'ctl00$MainContent$txtClienteClave',
            })
            res_client = self.session.post(THERION_ALTA_PEDIDO_URL, data=payload, timeout=15)
            tokens, soup = self._get_tokens(res_client.text)
            
            metodos = self._extract_options(soup, 'MainContent_ddlMetodoPago')
            formas = self._extract_options(soup, 'MainContent_ddlReferenciasBancarias')
            listas = self._extract_options(soup, 'MainContent_ddlListaPrecios')
            if not listas: listas = self._extract_options(soup, 'MainContent_ddlPreciosVenta')
            if not listas: listas = [{'value': l, 'text': l} for l in ["1", "2", "3", "3a", "4", "5", "5a", "9a", "13a"]]

            return {'metodos': metodos, 'formas': formas, 'listas': listas}, "Éxito (Web)"
        except Exception as e:
            return None, f"Error Web: {str(e)}"

    def sync_order(self, client_code, items_list, payment_method_val, payment_form_val, helper_product="V01027"):
        """
        Sincroniza el pedido utilizando el motor más estable disponible.
        Ahora prioriza la API REST para evitar problemas de stock negativo y stock web.
        """
        self._log(f"--- INICIO SINCRONIZACIÓN: Cliente {client_code} ---")
        if not self.logged_in: 
            self._log("Error: No autenticado")
            return False, "No autenticado"
        
        # Intentar vía API (El "Santo Grial" descubierto en el APK)
        if self.api_token:
            self._log("Intentando registro vía API...")
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
            try:
                # El APK usa 'clienteId', pero nosotros tenemos el código. 
                # Busquemos el ID real a través de la API primero.
                cli_search = requests.get(f"{THERION_API_URL}/ventas/clientes/{client_code}", headers=headers, timeout=10)
                self._log(f"Búsqueda cliente API: {cli_search.status_code}")
                
                # Si el cliente no se encuentra por la ruta directa, intentamos enviarlo tal cual
                # Algunos sistemas aceptan el código si el ID no existe
                cid = client_code
                if cli_search.status_code == 200:
                    c_data = cli_search.json()
                    if isinstance(c_data, list) and len(c_data) > 0:
                        # Buscamos el que coincida exactamente con la clave
                        match = next((c for c in c_data if c.get('clienteClave') == str(client_code)), None)
                        if match:
                            cid = match.get('clienteId')
                            self._log(f"Cliente ID encontrado en API: {cid}")

                payload = {
                    "clienteId": cid, 
                    "metodoPagoId": int(payment_method_val) if payment_method_val.isdigit() else 3,
                    "formaPagoId": int(payment_form_val) if payment_form_val.isdigit() else 20,
                    "articulos": [
                        {
                            "articuloId": item['CODIGO'], # Intentamos con el código
                            "cantidad": float(item['SOLICITADA']),
                            "listaPrecio": item.get('lista_precio', '1')
                        } for item in items_list
                    ]
                }
                
                self._log(f"Enviando payload API: {json.dumps(payload)}")
                res = requests.post(f"{THERION_API_URL}/ventas/pedidos/registrar-pedido", json=payload, headers=headers, timeout=20)
                self._log(f"Respuesta registrar-pedido: {res.status_code}")
                
                if res.status_code < 300:
                    self._log("¡API ÉXITO!")
                    try:
                        data = res.json()
                        folio = data.get("folio", data.get("id", "API-OK"))
                        return True, f"Pedido {folio} registrado por API."
                    except:
                        return True, "Pedido registrado por API."
                
                self._log(f"API Falló con {res.status_code}. Procediendo a Web.")
            except Exception as e:
                self._log(f"Error crítico en API: {str(e)}")
        else:
            self._log("No hay token API disponible. Usando método Web.")

        # --- MOTOR WEB ROBUSTO (Respaldo Principal) ---
        # NOTA CLAVE: ASP.NET usa ctl00$MainContent$xxx para POST, NO MainContent_xxx
        try:
            self._log("Iniciando Fase 1: Alta con Comodín (Web)")
            
            # Reintento de carga de cliente y producto
            precios = []
            for attempt in range(3):
                self._log(f"Intento {attempt+1} de carga web...")
                # Empezar desde cero en cada intento
                res = self.session.get(THERION_ALTA_PEDIDO_URL)
                tokens, soup = self._get_tokens(res.text)
                
                # 1. Cargar cliente y disparar postback
                payload = tokens.copy()
                payload.update({
                    'ctl00$MainContent$txtClienteClave': client_code,
                    '__EVENTTARGET': 'ctl00$MainContent$txtClienteClave',
                    '__EVENTARGUMENT': ''
                })
                res = self.session.post(THERION_ALTA_PEDIDO_URL, data=payload)
                tokens, soup = self._get_tokens(res.text)
                
                # Verificar que el cliente se cargó
                client_field = soup.find('input', {'id': 'MainContent_txtClienteClave'})
                client_val = client_field.get('value', '') if client_field else ''
                self._log(f"Cliente cargado: '{client_val}'")
                
                # 2. Cargar producto comodín y disparar postback
                payload = tokens.copy()
                payload.update({
                    'ctl00$MainContent$txtClienteClave': client_code,
                    'ctl00$MainContent$txtProductoClave': helper_product,
                    '__EVENTTARGET': 'ctl00$MainContent$txtProductoClave',
                    '__EVENTARGUMENT': ''
                })
                res = self.session.post(THERION_ALTA_PEDIDO_URL, data=payload)
                tokens, soup = self._get_tokens(res.text)
                
                precios = self._extract_options(soup, 'MainContent_ddlPreciosVenta')
                if precios:
                    self._log(f"¡Precios encontrados en intento {attempt+1}! ({len(precios)} opciones)")
                    break
                else:
                    err_span = soup.find('span', {'id': 'MainContent_labMensaje'})
                    err_text = err_span.text.strip() if err_span else "Sin mensaje de error"
                    self._log(f"Intento {attempt+1} fallido. Mensaje ERP: {err_text}")
                    # Guardar HTML para debug
                    with open(f"/tmp/error_web_phase1_att{attempt+1}.html", "w") as f:
                        f.write(res.text)
                    time.sleep(1.5)

            if not precios:
                self._log("Error FATAL: No se encontraron precios tras 3 reintentos.")
                return False, "Error: El ERP no cargó la lista de precios. Intenta de nuevo o verifica el cliente en Therion."
            
            # Agregar comodín para abrir pedido
            payload = tokens.copy()
            payload.update({
                'ctl00$MainContent$txtClienteClave': client_code,
                'ctl00$MainContent$ddlMetodoPago': payment_method_val,
                'ctl00$MainContent$ddlReferenciasBancarias': payment_form_val,
                'ctl00$MainContent$txtProductoClave': helper_product,
                'ctl00$MainContent$txtCantidad': '1',
                'ctl00$MainContent$ddlPreciosVenta': precios[0]['value'],
                'ctl00$MainContent$btnAgregarProducto': 'Agregar'
            })
            res = self.session.post(THERION_ALTA_PEDIDO_URL, data=payload)
            self._log(f"Comodín agregado. Buscando folio...")
            
            # Extraer Folio
            match = re.search(r'Pedido\.aspx\?op=editar(?:&amp;|&)folio=(\d+)', res.text)
            if not match:
                with open("/tmp/error_web_folio.html", "w") as f:
                    f.write(res.text)
                self._log("No se encontró folio en la respuesta")
                return False, "No se pudo generar el folio inicial (Web)."
            folio = match.group(1)
            edit_url = f"{THERION_EDIT_PEDIDO_URL}&folio={folio}"
            self._log(f"Folio obtenido: {folio}")
            
            # Fase 2: Agregar productos reales
            for item in items_list:
                res = self.session.get(edit_url)
                tokens, soup = self._get_tokens(res.text)
                
                payload = tokens.copy()
                payload.update({
                    'ctl00$MainContent$txtProductoClave': item['CODIGO'],
                    '__EVENTTARGET': 'ctl00$MainContent$txtProductoClave'
                })
                res = self.session.post(edit_url, data=payload)
                tokens, soup = self._get_tokens(res.text)
                
                precio_lista = item.get('lista_precio', '1')
                payload = tokens.copy()
                payload.update({
                    'ctl00$MainContent$txtProductoClave': item['CODIGO'],
                    'ctl00$MainContent$txtCantidad': str(item['SOLICITADA']),
                    'ctl00$MainContent$ddlPreciosVenta': precio_lista,
                    'ctl00$MainContent$btnAgregarProducto': 'Agregar'
                })
                res = self.session.post(edit_url, data=payload)
                self._log(f"Producto {item['CODIGO']} agregado")

            # Fase 3: Limpiar comodín y Guardar
            res = self.session.get(edit_url)
            tokens, soup = self._get_tokens(res.text)
            
            # Buscar botón de borrar para el comodín
            rows = soup.find_all('tr')
            target_btn = None
            for row in rows:
                if helper_product in row.text:
                    target_btn = row.find('input', {'type': 'image'}) or row.find('a', href=re.compile(r'__doPostBack'))
                    break
            
            if target_btn:
                payload = tokens.copy()
                btn_name = getattr(target_btn, 'attrs', {}).get('name')
                href = getattr(target_btn, 'attrs', {}).get('href')
                tag_name = getattr(target_btn, 'name', '')

                if tag_name == 'input' and btn_name:
                    payload.update({btn_name + '.x': '1', btn_name + '.y': '1'})
                elif href:
                    match_et = re.search(r"__doPostBack\('([^']+)'", href)
                    if match_et:
                        payload.update({'__EVENTTARGET': match_et.group(1)})
                
                res = self.session.post(edit_url, data=payload)
                tokens, _ = self._get_tokens(res.text)
                self._log("Comodín eliminado")

            # Guardar Final
            payload = tokens.copy()
            payload.update({'ctl00$ButtonGuardar': 'Guardar'})
            self.session.post(edit_url, data=payload)
            self._log(f"Pedido {folio} guardado exitosamente")
            
            return True, f"Pedido {folio} sincronizado exitosamente."

        except Exception as e:
            self._log(f"Error en sincronización web: {str(e)}")
            return False, f"Fallo total de sincronización: {str(e)}"

    def get_reporte_estado_cuenta(self, start_date=None, end_date=None):
        """
        Obtiene el reporte de Estado de Cuenta desde el ERP.
        Por defecto, obtiene desde el 1 de enero del año en curso hasta hoy.
        """
        self._log("Iniciando obtención de Estado de Cuenta")
        if not self.logged_in:
            return None, "No autenticado"
            
        import time
        import pandas as pd
        from bs4 import BeautifulSoup
        
        if not start_date:
            year = time.strftime('%Y')
            start_date = f"01/01/{year}"
            
        url = f"{THERION_BASE_URL}/Autentificados/Ventas/ReporteEstadoCuenta.aspx"
        try:
            res = self.session.get(url, timeout=15)
            tokens, _ = self._get_tokens(res.text)
            
            payload = tokens.copy()
            payload['ctl00$MainContent$txtFechaInicio'] = start_date
            if end_date:
                payload['ctl00$MainContent$txtFechaFin'] = end_date
                
            payload['ctl00$MainContent$btnEstadoRangoFechas'] = 'Rango de fechas'
            
            res_post = self.session.post(url, data=payload, timeout=30)
            soup = BeautifulSoup(res_post.text, 'html.parser')
            
            target_table = soup.find('table', {'id': 'MainContent_gridPrincipal'})
            if target_table:
                # Wrap the table HTML in io.StringIO to avoid Pandas warnings
                from io import StringIO
                
                all_dfs = []
                # Page 1
                df_page = pd.read_html(StringIO(str(target_table)))[0]
                df_page.dropna(how='all', inplace=True)
                # Filter pager rows and header rows if repeated
                df_page = df_page[df_page['Folio'].notna()]
                if not df_page.empty:
                    all_dfs.append(df_page)
                    
                # Loop through remaining pages
                # ASP.NET grids paginate using __EVENTTARGET and __EVENTARGUMENT (Page$2, Page$3...)
                page = 2
                while True:
                    tokens_pg, _ = self._get_tokens(res_post.text)
                    payload_pg = tokens_pg.copy()
                    payload_pg['__EVENTTARGET'] = 'ctl00$MainContent$gridPrincipal'
                    payload_pg['__EVENTARGUMENT'] = f'Page${page}'
                    
                    # Do not set any buttons as we are performing a postback for the grid component directly
                    res_post = self.session.post(url, data=payload_pg, timeout=30)
                    soup_pg = BeautifulSoup(res_post.text, 'html.parser')
                    grid_pg = soup_pg.find('table', {'id': 'MainContent_gridPrincipal'})
                    
                    if not grid_pg:
                        break
                        
                    df_pg = pd.read_html(StringIO(str(grid_pg)))[0]
                    df_pg.dropna(how='all', inplace=True)
                    df_pg = df_pg[df_pg['Folio'].notna()]
                    
                    if df_pg.empty:
                        break
                        
                    # Stop if we reached beyond the last page (some ASP return the last page repeatedly)
                    if len(all_dfs) > 0:
                        if list(all_dfs[-1]['Folio'].values) == list(df_pg['Folio'].values):
                            break
                        
                    all_dfs.append(df_pg)
                    page += 1
                
                if not all_dfs:
                    empty_df = pd.DataFrame(columns=['Folio', 'Cliente', 'Razón Social', 'Vencimiento', 'Importe', 'Saldo'])
                    return empty_df, "Vacio"
                    
                df_final = pd.concat(all_dfs, ignore_index=True)
                
                # Cleanup the combined DataFrame
                cols_to_drop = [c for c in df_final.columns if 'Unnamed' in c]
                df_final.drop(columns=cols_to_drop, inplace=True, errors='ignore')
                
                return df_final, "Éxito"
            else:
                return None, "No se encontró la tabla de estado de cuenta"
        except Exception as e:
            self._log(f"Error parseando Estado de Cuenta: {str(e)}")
            return None, f"Error: {str(e)}"

