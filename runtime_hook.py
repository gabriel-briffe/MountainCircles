import os
import sys
import shutil

def runtime_hook():
    if sys.platform == 'darwin':
        # Get the application's root directory
        if getattr(sys, 'frozen', False):
            app_path = os.path.dirname(sys._MEIPASS)
        else:
            app_path = os.path.dirname(os.path.abspath(__file__))
            
        # Rename the binary
        source = os.path.join(app_path, 'compute_mac')
        target = os.path.join(app_path, 'compute.exe')
        if os.path.exists(source) and not os.path.exists(target):
            shutil.copy2(source, target) 