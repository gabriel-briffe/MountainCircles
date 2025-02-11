import os
import json

CONFIG_FILE = os.path.normpath(os.path.join(os.path.expanduser("~"), ".mountaincircles.json"))

def cload_settings():
    """
    Loads settings from a JSON config file.
    Returns a dictionary with the settings or an empty dict if the file doesn't exist.
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print("Could not load settings:", e)
    return {}

def csave_settings(settings):
    """
    Saves the given settings (a dictionary) to the JSON config file.
    """
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print("Could not save settings:", e) 