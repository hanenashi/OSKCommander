import json
import os

SETTINGS_FILE = "osk_settings.json"
DEFAULT_REMOTE_PATH = "/storage/emulated/0/DCIM/Camera"

DEFAULTS = {
    "adb_path": "",
    "remote_path": DEFAULT_REMOTE_PATH,
    "last_dest": "",
    "limit_n": 0,
    "debug_mode": False,
    "smart_sort": True,
    "sort_order": "Oldest First",
    # --- Phase 2: Filters ---
    "filter_enable_date": False,
    "filter_date_start": "2020-01-01",
    "filter_date_end": "2030-12-31",
    "filter_enable_letter": False,
    "filter_letter_start": "A",
    "filter_letter_end": "Z"
}

def load_settings():
    settings = DEFAULTS.copy()
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                settings.update(data)
    except Exception:
        pass
    return settings

def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass