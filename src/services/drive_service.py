from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import os
import io
import pandas as pd
from src.config import FILE_SERVICE_ACCOUNT, DRIVE_FOLDER_ID, DRIVE_FOLDER_HISTORY_ID

SCOPES = ['https://www.googleapis.com/auth/drive']

import streamlit as st

def get_drive_service():
    """Autentica y devuelve el servicio de Drive."""
    # Intentar usar secretos de Streamlit Cloud primero
    if "gcp_service_account" in st.secrets:
        info = st.secrets["gcp_service_account"]
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        # Fallback a archivo local
        if not os.path.exists(FILE_SERVICE_ACCOUNT):
            raise FileNotFoundError(f"No se encontró el archivo de credenciales local ni en secretos.")
        creds = service_account.Credentials.from_service_account_file(
            FILE_SERVICE_ACCOUNT, scopes=SCOPES)
            
    return build('drive', 'v3', credentials=creds)

def find_file_in_folder(service, filename, folder_id):
    """Busca un archivo por nombre dentro de una carpeta específica."""
    query = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']
    return None

def download_file_from_drive(local_path, drive_filename, folder_id=DRIVE_FOLDER_ID):
    """
    Descarga un archivo desde Drive dado su nombre y la carpeta ID.
    Si no existe, no hace nada (o retorna False).
    """
    try:
        service = get_drive_service()
        file_id = find_file_in_folder(service, drive_filename, folder_id)
        
        if not file_id:
            print(f"Archivo {drive_filename} no encontrado en Drive.")
            return False

        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()

        with open(local_path, 'wb') as f:
            f.write(fh.getbuffer())
            
        print(f"Descargado {drive_filename} a {local_path}")
        return True
    
    except Exception as e:
        print(f"Error descargando {drive_filename}: {e}")
        return False

def upload_file_to_drive(local_path, drive_filename, folder_id=DRIVE_FOLDER_ID):
    """
    Sube (o actualiza) un archivo a Drive.
    """
    try:
        service = get_drive_service()
        file_id = find_file_in_folder(service, drive_filename, folder_id)
        
        media = MediaFileUpload(local_path, resumable=True)
        
        if file_id:
            # Actualizar existente
            service.files().update(fileId=file_id, media_body=media).execute()
            msg = f"Actualizado {drive_filename} (ID: {file_id})"
            print(msg)
        else:
            # Crear nuevo
            file_metadata = {
                'name': drive_filename,
                'parents': [folder_id]
            }
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            msg = f"Creado {drive_filename}"
            print(msg)
            
        return True, msg
    except Exception as e:
        err_msg = f"Error subiendo {drive_filename}: {str(e)}"
        print(err_msg)
        return False, err_msg

def append_to_history_log(new_rows_df, drive_filename="historial_faltantes.csv", folder_id=DRIVE_FOLDER_HISTORY_ID):
    """
    Lógica específica para añadir filas al historial CSV en Drive:
    1. Descarga el actual (si existe).
    2. Concatena los nuevos datos.
    3. Sube el archivo actualizado.
    """
    import tempfile
    
    # Usar un archivo temporal local
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        temp_path = tmp.name
        
    try:
        # 1. Intentar descargar existente
        exists = download_file_from_drive(temp_path, drive_filename, folder_id)
        
        if exists:
            # Leer existente
            try:
                df_hist = pd.read_csv(temp_path)
            except:
                 df_hist = pd.DataFrame()
        else:
            df_hist = pd.DataFrame()
            
        # 2. Asignar ID_PEDIDO inteligente
        if not new_rows_df.empty:
            # Aseguramos que existan columnas necesarias para el cálculo
            if 'FECHA' in new_rows_df.columns and 'CLIENTE' in new_rows_df.columns:
                for cliente in new_rows_df['CLIENTE'].unique():
                    for fecha in new_rows_df[new_rows_df['CLIENTE'] == cliente]['FECHA'].unique():
                        mask_new = (new_rows_df['CLIENTE'] == cliente) & (new_rows_df['FECHA'] == fecha)
                        
                        max_id = 0
                        if not df_hist.empty and 'ID_PEDIDO' in df_hist.columns and 'FECHA' in df_hist.columns:
                            mask_hist = (df_hist['CLIENTE'] == cliente) & (df_hist['FECHA'] == fecha)
                            ids_existentes = pd.to_numeric(df_hist[mask_hist]['ID_PEDIDO'], errors='coerce').fillna(0)
                            if not ids_existentes.empty:
                                max_id = int(ids_existentes.max())
                        
                        new_rows_df.loc[mask_new, 'ID_PEDIDO'] = max_id + 1
        
        # 3. Concatenar
        df_updated = pd.concat([df_hist, new_rows_df], ignore_index=True)
        
        # Guardar localmente
        df_updated.to_csv(temp_path, index=False)
        
        # 3. Subir
        return upload_file_to_drive(temp_path, drive_filename, folder_id)
        
    finally:
        # Limpieza
        if os.path.exists(temp_path):
            os.remove(temp_path)

def remove_order_from_history(cliente_full, fecha_str, id_pedido, drive_filename="historial_faltantes.csv", folder_id=DRIVE_FOLDER_HISTORY_ID):
    """
    Busca y elimina un pedido específico (Cliente, Fecha, ID) del historial en Drive.
    """
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        temp_path = tmp.name
        
    try:
        exists = download_file_from_drive(temp_path, drive_filename, folder_id)
        if not exists:
            return False, "Archivo no encontrado"
            
        df_hist = pd.read_csv(temp_path)
        if df_hist.empty:
            return False, "Historial vacío"
            
        # Filtro de eliminación
        # Aseguramos tipos para comparación
        df_hist['ID_PEDIDO'] = pd.to_numeric(df_hist['ID_PEDIDO'], errors='coerce').fillna(0).astype(int)
        
        mask_a_quitar = (
            (df_hist['CLIENTE'].astype(str).str.strip() == str(cliente_full).strip()) &
            (df_hist['FECHA'].astype(str).str.strip() == str(fecha_str).strip()) &
            (df_hist['ID_PEDIDO'] == int(id_pedido))
        )
        
        inicial = len(df_hist)
        df_updated = df_hist[~mask_a_quitar].copy()
        final = len(df_updated)
        
        if inicial == final:
            return False, "No se encontró el pedido con esos criterios"
            
        # Guardar y subir
        df_updated.to_csv(temp_path, index=False)
        return upload_file_to_drive(temp_path, drive_filename, folder_id)
        
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def reset_history_log(drive_filename="historial_faltantes.csv", folder_id=DRIVE_FOLDER_HISTORY_ID):
    """
    Reinicia el historial en Drive subiendo un archivo CSV vacío con las cabeceras.
    """
    import tempfile
    cols = ['CODIGO', 'DESCRIPCION', 'SOLICITADA', 'SURTIDO', 'FECHA', 'CLIENTE', 'ID_PEDIDO']
    df_empty = pd.DataFrame(columns=cols)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        temp_path = tmp.name
        
    try:
        df_empty.to_csv(temp_path, index=False)
        return upload_file_to_drive(temp_path, drive_filename, folder_id)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def load_history_log(drive_filename="historial_faltantes.csv", folder_id=DRIVE_FOLDER_HISTORY_ID):
    """
    Descarga y retorna el DataFrame del historial.
    """
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        temp_path = tmp.name
        
    try:
        exists = download_file_from_drive(temp_path, drive_filename, folder_id)
        if exists:
            return pd.read_csv(temp_path)
        else:
            return pd.DataFrame()
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


import streamlit as st

@st.cache_data(show_spinner=False)
def descargar_de_drive(folder_id):
    """
    Busca el archivo más reciente (CSV o XLSX) en la carpeta de Drive,
    lo descarga en memoria y devuelve (dataframe, nombre, fecha).
    Usa streamlit cache para no descargar a cada rato si no ha cambiado.
    """
    
    # Esta función interna es la que hace el trabajo pesado
    try:
        service = get_drive_service()
        # Listar archivos ordenados por fecha mod (desc)
        query = f"'{folder_id}' in parents and trashed = false and (mimeType = 'text/csv' or mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')"
        results = service.files().list(
            q=query, 
            orderBy="modifiedTime desc", 
            pageSize=1, 
            fields="files(id, name, modifiedTime, mimeType)").execute()
        files = results.get('files', [])
        
        if not files:
            return None, None, None
            
        latest = files[0]
        file_id = latest['id']
        name = latest['name']
        mod_time = latest.get('modifiedTime', '') # Fecha ISO
        
        # Descargar en memoria
        import io
        from googleapiclient.http import MediaIoBaseDownload
        
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        fh.seek(0)
        
        # Parsear
        if name.endswith('.csv'):
            try: df = pd.read_csv(fh, header=0, encoding='latin-1')
            except: fh.seek(0); df = pd.read_csv(fh, header=0, encoding='utf-8')
        else:
            try:
                df = pd.read_excel(fh, header=0, engine='calamine')
            except:
                df = pd.read_excel(fh, header=0)
            
        return df, name, mod_time
        
    except Exception as e:
        return None, f"Error: {str(e)}", None
