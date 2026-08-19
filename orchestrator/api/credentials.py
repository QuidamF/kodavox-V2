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
            # Si pegaron por error 'sk-proj-...' dos veces juntas
            if k == "OPENAI_API_KEY" and clean_v.count("sk-proj-") > 1:
                first_idx = clean_v.find("sk-proj-")
                second_idx = clean_v.find("sk-proj-", first_idx + 1)
                clean_v = clean_v[second_idx:]
            creds[k] = clean_v
            os.environ[k] = clean_v

    # Crear el directorio data/ si no existe
    os.makedirs(os.path.dirname(CREDENTIALS_FILE), exist_ok=True)
    
    # Guardar a disco credentials.json
    try:
        with open(CREDENTIALS_FILE, 'w', encoding='utf-8') as f:
            json.dump(creds, f, indent=4)
    except Exception as e:
        print(f"[Credentials] Error al guardar {CREDENTIALS_FILE}: {e}")

    # También actualizar .env si existe en la raíz
    env_path = os.path.abspath(os.path.join(BASE_DIR, "..", ".env"))
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_lines = []
            updated_keys = set()
            for line in lines:
                key_match = False
                for k, v in keys_dict.items():
                    if v and line.startswith(f"{k}="):
                        clean_v = str(v).strip()
                        new_lines.append(f"{k}={clean_v}\n")
                        updated_keys.add(k)
                        key_match = True
                        break
                if not key_match:
                    new_lines.append(line)
            for k, v in keys_dict.items():
                if v and k not in updated_keys:
                    clean_v = str(v).strip()
                    new_lines.append(f"{k}={clean_v}\n")
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
        except Exception as e:
            print(f"[Credentials] Error al actualizar .env: {e}")
