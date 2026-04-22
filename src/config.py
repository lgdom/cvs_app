import os

# Base Directory (assuming this is running from root)
BASE_DIR = os.getcwd()

# Data Files
DATA_DIR = os.path.join(BASE_DIR, 'data')
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')

FILE_CLIENTES = os.path.join(DATA_DIR, 'clientes.csv')
FILE_PRODUCTOS = os.path.join(DATA_DIR, 'productos.csv')
FILE_PLANTILLA = os.path.join(DATA_DIR, 'plantilla.xlsx')
FILE_PLANTILLA_COMPROBACION = os.path.join(DATA_DIR, 'plantilla_comprobacion.xlsx')
FILE_PLANTILLA_SOLICITUD = os.path.join(DATA_DIR, 'plantilla_solicitud.xlsx')

FILE_IMAGEN = os.path.join(ASSETS_DIR, 'logo.png')
FILE_FIRMA = os.path.join(ASSETS_DIR, 'firma.png')

# Google Drive
import streamlit as st

# Priorizar secretos de Streamlit Cloud, si no usar valores locales
try:
    DRIVE_FOLDER_ID = st.secrets["DRIVE_FOLDER_ID"]
    DRIVE_FOLDER_HISTORY_ID = st.secrets["DRIVE_FOLDER_HISTORY_ID"]
except:
    DRIVE_FOLDER_ID = "1bvF7yuIRiJQ0oiXiZ6s3JD8goy1DUi1K" # Carpeta EXISTENCIAS
    DRIVE_FOLDER_HISTORY_ID = "1Ft7N-FVaX6YwwgkfPXRKsTrTBnAvKG0R" # Carpeta HISTORIAL

TEMP_DRIVE_FOLDER = os.path.join(BASE_DIR, 'temp_drive_folder')
FILE_SERVICE_ACCOUNT = os.path.join(BASE_DIR, 'service_account.json')
FILE_HISTORIAL_FALTANTES = os.path.join(DATA_DIR, 'historial_faltantes.csv')

# Page Config
PAGE_TITLE = "Therion ERP"
PAGE_ICON = "📦"
LAYOUT = "wide"

# Therion ERP URLs
THERION_BASE_URL = "https://therion.victory-enterprises.com"
THERION_LOGIN_URL = f"{THERION_BASE_URL}/LoginLTE.aspx"
THERION_ALTA_PEDIDO_URL = f"{THERION_BASE_URL}/Autentificados/Ventas/Detalle/Pedido.aspx?op=alta"
THERION_EDIT_PEDIDO_URL = f"{THERION_BASE_URL}/Autentificados/Ventas/Detalle/Pedido.aspx?op=editar"
THERION_WELCOME_URL = f"{THERION_BASE_URL}/Autentificados/WelcomeLTE.aspx"
THERION_API_URL = "https://checador.victory-enterprises.com"
