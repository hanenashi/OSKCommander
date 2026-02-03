import subprocess
import os

class AdbWrapper:
    def __init__(self, adb_path, debug=False, logger=None):
        self.adb = adb_path
        self.debug = debug
        self.logger = logger

    def run(self, args):
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        cmd = [self.adb] + args
        if self.debug and self.logger:
            self.logger(f"[DEBUG] CMD: {' '.join(cmd)}")
            
        try:
            return subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='replace', 
                startupinfo=startupinfo
            )
        except FileNotFoundError:
            # Graceful fail if adb.exe is missing/path is wrong
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="ADB binary not found")
        except Exception as e:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr=str(e))

    def remote_exists(self, path):
        """Checks if a path exists on the device."""
        res = self.run(["shell", "ls", "-d", f"'{path}'"])
        return res.returncode == 0

    def get_state(self):
        """Returns: 'Connected', 'Unauthorized', 'Offline', 'No Device', or 'Error'"""
        res = self.run(["devices"])
        if res.returncode != 0: return "Error"
        
        out = res.stdout
        if "\tdevice" in out: return "Connected"
        if "\tunauthorized" in out: return "Unauthorized"
        if "\toffline" in out: return "Offline"
        return "No Device"

    def scan_media(self):
        if self.logger: self.logger("[*] Triggering Media Scan...")
        self.run([
            "shell", "content", "call",
            "--uri", "content://media",
            "--method", "scan_volume",
            "--arg", "external_primary"
        ])

def check_adb_dlls(adb_path):
    if not adb_path or not os.path.isabs(adb_path):
        return []
    folder = os.path.dirname(adb_path)
    required = ["AdbWinApi.dll", "AdbWinUsbApi.dll"]
    missing = [dll for dll in required if not os.path.exists(os.path.join(folder, dll))]
    return missing