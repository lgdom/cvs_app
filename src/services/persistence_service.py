import json
import os
from datetime import date, datetime

PERSISTENCE_FILE = "data/session_cache.json"

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def save_persistence(state):
    """Guarda los datos críticos del session_state en un archivo local."""
    try:
        import pandas as pd
        # Asegurar que el directorio existe
        os.makedirs(os.path.dirname(PERSISTENCE_FILE), exist_ok=True)
        
        # Convertir pedidos a formato serializable (items de DataFrame a dict)
        pedidos_raw = state.get("pedidos", [])
        pedidos_serializable = []
        for p in pedidos_raw:
            p_copy = p.copy()
            if isinstance(p_copy.get("items"), pd.DataFrame):
                p_copy["items"] = p_copy["items"].to_dict('records')
            pedidos_serializable.append(p_copy)

        # Convertir pedidos ERP a formato serializable
        pedidos_erp_raw = state.get("pedidos_erp", [])
        pedidos_erp_serializable = []
        for p in pedidos_erp_raw:
            p_erp_copy = p.copy()
            if isinstance(p_erp_copy.get("items"), pd.DataFrame):
                p_erp_copy["items"] = p_erp_copy["items"].to_dict('records')
            pedidos_erp_serializable.append(p_erp_copy)

        data = {
            "carrito": state.get("carrito", []),
            "lista_revision": state.get("lista_revision", []),
            "facturas": state.get("facturas", []),
            "pedidos": pedidos_serializable,
            "pedidos_erp": pedidos_erp_serializable,
            "memoria_cliente": state.get("memoria_cliente", None),
            "memoria_busqueda_inv": state.get("memoria_busqueda_inv", ""),
            "last_updated": datetime.now().isoformat()
        }
        
        with open(PERSISTENCE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, default=json_serial, indent=4)
    except Exception as e:
        print(f"Error en persistencia (save): {e}")

def load_persistence():
    """Carga los datos guardados si existen."""
    if not os.path.exists(PERSISTENCE_FILE):
        return None
        
    try:
        with open(PERSISTENCE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception as e:
        print(f"Error en persistencia (load): {e}")
        return None

def clear_persistence():
    """Elimina el archivo de cache."""
    if os.path.exists(PERSISTENCE_FILE):
        os.remove(PERSISTENCE_FILE)
