import sys
import os
from gui.main_window import OSKCommanderPro

# Fix for PyInstaller path resolution
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Monkey-patch the defaults or just let the OS handle relative paths?
# Since we used --add-data "file;.", they are in the current working directory 
# of the internal app. 
# BUT, `adb.exe` needs to be called by path.

if __name__ == "__main__":
    # If we are in the frozen exe, we need to make sure we find our bundled assets
    if getattr(sys, 'frozen', False):
        # We are running as an exe
        os.environ["PATH"] += os.pathsep + sys._MEIPASS
        
    app = OSKCommanderPro()
    app.mainloop()