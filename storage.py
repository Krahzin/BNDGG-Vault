# storage.py
import json
import os
import sys

def get_data_dir():
    base = os.path.expanduser("~/AppData/Roaming") if sys.platform == 'win32' else os.path.expanduser("~/.local/share")
    data_dir = os.path.join(base, "PasswordManager")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def get_icon_path(icon_filename="bndgg.ico"):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, icon_filename)

DATA_DIR = get_data_dir()
DATA_FILE = os.path.join(DATA_DIR, "vault.json")

def load_physical_file():
    """Returns a safe dictionary, ensuring no critical keys are None."""
    default = {"salt": None, "canary": None, "vault_blob": None}
    if not os.path.exists(DATA_FILE):
        return default
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else default
    except Exception as e:
        print(f"Error loading physical file: {e}")
        return default

def save_physical_file(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
