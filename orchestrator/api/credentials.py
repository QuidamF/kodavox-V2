import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "data", "credentials.json")

def load_credentials():
    """Carga credenciales desde el archivo a os.environ si existen."""
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
                creds = json.load(f)
                for key, value in creds.items():
                    if value:  # Solo cargar si no está vacío
                        os.environ[key] = str(value).strip()
        except Exception as e:
            print(f"[Credentials] Error al cargar {CREDENTIALS_FILE}: {e}")

def save_credentials(keys_dict: dict):
    """Guarda nuevas llaves en credentials.json y las inyecta en os.environ."""
    # Primero cargar el existente
    creds = {}
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
                creds = json.load(f)
        except:
            pass

    # Actualizar con los nuevos valores
    for k, v in keys_dict.items():
        if v:
            clean_v = str(v).strip()
            creds[k] = clean_v
            os.environ[k] = clean_v

    # Crear el directorio data/ si no existe
    os.makedirs(os.path.dirname(CREDENTIALS_FILE), exist_ok=True)
    
    # Guardar a disco
    try:
        with open(CREDENTIALS_FILE, 'w', encoding='utf-8') as f:
            json.dump(creds, f, indent=4)
    except Exception as e:
        print(f"[Credentials] Error al guardar {CREDENTIALS_FILE}: {e}")
