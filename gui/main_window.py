import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import queue
import os
import sys
import datetime
import random

from core.settings import load_settings, save_settings, DEFAULT_REMOTE_PATH
from core.worker import SyncWorker
from core.adb import AdbWrapper
from .widgets import SettingsDialog, CleanupDialog

ICON_FILENAME = "obersturmkiippfuhrer.png"

# Common paths to check if default fails
FALLBACK_PATHS = [
    "/storage/emulated/0/DCIM/Camera",
    "/storage/emulated/0/DCIM/100ANDRO",
    "/storage/emulated/0/DCIM/100MEDIA",
    "/sdcard/DCIM/Camera",
    "/storage/emulated/0/DCIM",
]

class OSKCommanderPro(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OberSturmKlippCommander v6.5 (Release Candidate)")
        self.geometry("700x750")
        
        if not os.path.exists("logs"): os.makedirs("logs")
        self.settings = load_settings()
        self.ensure_adb()
        
        # Persist ADB wrapper for the GUI thread to use for polling
        self.adb = AdbWrapper(self.settings["adb_path"])
        
        self.queue = queue.Queue()
        self.worker = None
        self.current_log_file = None
        
        # Wiggle State
        self.wiggle_active = False
        self.icon_id = None
        self.base_x, self.base_y = 0, 0
        self.current_pct = 0

        self._build_ui()
        
        # Start loops
        self.after(500, self.startup_checks)
        self.after(100, self._process_queue)
        self.after(1000, self.monitor_usb)

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def ensure_adb(self):
        # 1. Check PyInstaller Bundle (_MEIPASS)
        preferred_adb = None
        if getattr(sys, 'frozen', False):
            bundle_path = os.path.join(sys._MEIPASS, "adb.exe")
            if os.path.exists(bundle_path):
                preferred_adb = bundle_path
        
        # Check Local Directory
        if not preferred_adb:
            local_path = os.path.abspath("adb.exe")
            if os.path.exists(local_path):
                preferred_adb = local_path

        current_setting = self.settings.get("adb_path", "")
        
        if preferred_adb:
            if not current_setting or current_setting == "adb" or not os.path.exists(current_setting):
                self.settings["adb_path"] = preferred_adb
                return

        if not current_setting:
            self.settings["adb_path"] = "adb"

    def monitor_usb(self):
        state = self.adb.get_state()
        
        if state == "Connected":
            self.lbl_usb_status.config(text="USB: Connected", foreground="green")
            if not self.worker:
                self.btn_start.config(state="normal")
        elif state == "Unauthorized":
            self.lbl_usb_status.config(text="USB: Unauthorized (Check Phone)", foreground="orange")
            if not self.worker: self.btn_start.config(state="disabled")
        elif state == "Offline":
            self.lbl_usb_status.config(text="USB: Offline (Cable issue?)", foreground="red")
            if not self.worker: self.btn_start.config(state="disabled")
        elif state == "Error":
            self.lbl_usb_status.config(text="USB: Error (ADB Missing?)", foreground="red")
            if not self.worker: self.btn_start.config(state="disabled")
        else:
            self.lbl_usb_status.config(text="USB: No Device", foreground="red")
            if not self.worker: self.btn_start.config(state="disabled")
            
        self.after(2000, self.monitor_usb)

    def startup_checks(self):
        self.check_remote_path_fallback()

    def check_remote_path_fallback(self):
        current_path = self.remote_var.get().strip()
        if self.adb.get_state() != "Connected": return
        if self.adb.remote_exists(current_path): return

        self.log_msg(f"[WARN] Path not found: {current_path}. Searching fallbacks...")
        found = None
        for path in FALLBACK_PATHS:
            if self.adb.remote_exists(path):
                found = path
                break
        
        if found:
            self.remote_var.set(found)
            self.settings["remote_path"] = found
            save_settings(self.settings)
            self.log_msg(f"[INFO] Auto-corrected path to: {found}")
            messagebox.showinfo("Path Auto-Correction", f"Default folder not found.\n\nSwitched to:\n{found}")
        else:
            self.log_msg("[ERR] Could not find any standard Camera folder.")

    def _build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)
        
        # Header
        top = ttk.Frame(main)
        top.pack(fill="x", pady=5)
        
        ttk.Label(top, text="OberSturmKlippCommander", font=("Segoe UI", 12, "bold")).pack(side="left")
        
        b_fr = ttk.Frame(top)
        b_fr.pack(side="right")
        self.lbl_usb_status = ttk.Label(b_fr, text="Checking USB...", font=("Segoe UI", 9, "bold"), foreground="gray")
        self.lbl_usb_status.pack(side="left", padx=(0, 15))
        ttk.Button(b_fr, text="⚙ Settings", command=self.open_settings).pack(side="left", padx=2)
        ttk.Button(b_fr, text="🛡 Verify & Cleanup", command=self.open_cleanup).pack(side="left")
        
        # Config
        grp = ttk.LabelFrame(main, text="Paths", padding=10)
        grp.pack(fill="x", pady=5)
        
        self.remote_var = tk.StringVar(value=self.settings.get("remote_path", DEFAULT_REMOTE_PATH))
        ttk.Entry(grp, textvariable=self.remote_var).pack(fill="x", pady=2)
        
        dest_fr = ttk.Frame(grp)
        dest_fr.pack(fill="x", pady=2)
        self.local_var = tk.StringVar(value=self.settings.get("last_dest", ""))
        ttk.Entry(dest_fr, textvariable=self.local_var).pack(side="left", fill="x", expand=True, padx=(0,5))
        ttk.Button(dest_fr, text="Browse", command=self.browse_dest).pack(side="right")

        # Controls
        self.del_var = tk.BooleanVar(value=self.settings.get("delete_after", False))
        ttk.Checkbutton(main, text="Delete after copy", variable=self.del_var).pack(anchor="w")
        
        ctrl = ttk.Frame(main, padding=10)
        ctrl.pack(fill="x")
        self.btn_start = ttk.Button(ctrl, text="START", command=self.start)
        self.btn_start.pack(side="left", fill="x", expand=True, padx=5)
        self.btn_stop = ttk.Button(ctrl, text="STOP", command=self.stop, state="disabled")
        self.btn_stop.pack(side="right", fill="x", expand=True, padx=5)

        # Wiggle & Progress
        p_fr = ttk.Frame(main)
        p_fr.pack(fill="x", pady=5)
        self.canvas = tk.Canvas(p_fr, width=50, height=80, highlightthickness=0)
        self.canvas.pack(side="left")
        self.load_avatar()
        
        self.progress = ttk.Progressbar(p_fr, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=5)

        # Log
        log_fr = ttk.LabelFrame(main, text="Log", padding=5)
        log_fr.pack(fill="both", expand=True)
        
        log_tools = ttk.Frame(log_fr)
        log_tools.pack(fill="x", pady=(0, 2))
        ttk.Button(log_tools, text="Copy Log", command=self.copy_log, width=10).pack(side="right", padx=2)
        ttk.Button(log_tools, text="Clear", command=self.clear_log, width=8).pack(side="right", padx=2)

        self.log = tk.Text(log_fr, height=12)
        self.log.pack(fill="both", expand=True)

    def load_avatar(self):
        try:
            # FIX: Use resource_path so PyInstaller finds the image!
            icon_path = self.resource_path(ICON_FILENAME)
            if os.path.exists(icon_path):
                img = tk.PhotoImage(file=icon_path)
                w, h = img.width(), img.height()
                scale = max(1, int(w/48))
                self.icon_img = img.subsample(scale, scale)
                self.base_x, self.base_y = 25, 60
                self.icon_id = self.canvas.create_image(self.base_x, self.base_y, image=self.icon_img)
        except: pass

    # Wiggle Logic
    def start_wiggle(self):
        self.wiggle_active = True
        self.do_wiggle()
        
    def stop_wiggle(self):
        self.wiggle_active = False
        if self.icon_id: self.canvas.coords(self.icon_id, self.base_x, self.base_y)

    def do_wiggle(self):
        if not self.wiggle_active or not self.icon_id: return
        dx = random.randint(-2, 2)
        dy = random.randint(-2, 2)
        self.canvas.coords(self.icon_id, self.base_x+dx, self.base_y+dy)
        self.after(50, self.do_wiggle)

    def jump(self):
        if not self.icon_id: return
        self.stop_wiggle()
        self.canvas.coords(self.icon_id, self.base_x, self.base_y - 30)
        self.after(600, lambda: self.canvas.coords(self.icon_id, self.base_x, self.base_y))

    def browse_dest(self):
        d = filedialog.askdirectory()
        if d: self.local_var.set(d)

    def open_settings(self):
        self.jump()
        dlg = SettingsDialog(self, self.settings)
        self.wait_window(dlg)
        if dlg.result:
            self.settings.update(dlg.result)
            save_settings(self.settings)
            self.adb = AdbWrapper(self.settings["adb_path"])

    def open_cleanup(self):
        self.jump()
        if not self.current_log_file:
            ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
            self.current_log_file = f"logs/osk_{ts}.txt"
            self.log_msg(f"=== Session Auto-Started {ts} ===")

        if not self.local_var.get():
            messagebox.showwarning("Error", "Please select PC destination first.")
            return
        
        def file_logger(msg):
            if self.current_log_file:
                try:
                    with open(self.current_log_file, "a", encoding="utf-8") as f:
                        f.write(msg + "\n")
                except: pass

        self.settings["remote_path"] = self.remote_var.get()
        self.settings["last_dest"] = self.local_var.get()
        CleanupDialog(self, self.settings, file_logger)

    def log_msg(self, msg):
        self.log.insert("end", msg+"\n")
        self.log.see("end")
        if self.current_log_file:
            try:
                with open(self.current_log_file, "a", encoding="utf-8") as f:
                    f.write(msg+"\n")
            except: pass

    def copy_log(self):
        self.jump()
        try:
            txt = self.log.get("1.0", "end")
            self.clipboard_clear()
            self.clipboard_append(txt)
            messagebox.showinfo("Log", "Log copied.")
        except: pass

    def clear_log(self):
        self.jump()
        self.log.delete("1.0", "end")

    def start(self):
        self.jump()
        self.check_remote_path_fallback()
        dest = self.local_var.get()
        
        # FIX: Shout if empty!
        if not dest: 
            messagebox.showwarning("Missing Destination", "You must select a folder on your PC to save the files!")
            return
        
        if not self.current_log_file:
            ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
            self.current_log_file = f"logs/osk_{ts}.txt"
            self.log_msg(f"=== Started {ts} ===")
        
        self.settings["last_dest"] = dest
        self.settings["remote_path"] = self.remote_var.get()
        self.settings["delete_after"] = self.del_var.get()
        save_settings(self.settings)
        
        self.worker = SyncWorker(self.settings, self.queue)
        self.worker.start()
        
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")

    def stop(self):
        if self.worker: self.worker.stop()

    def _process_queue(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                kind = msg[0]
                if kind == "log": self.log_msg(msg[1])
                elif kind == "progress": self.progress['value'] = msg[1]
                elif kind == "wiggle_start": self.start_wiggle()
                elif kind == "wiggle_stop": self.stop_wiggle()
                elif kind == "jump": self.jump()
                elif kind == "error": 
                    messagebox.showerror("Error", msg[1])
                    self._reset() 
                elif kind == "done": 
                    self.after(800, lambda: messagebox.showinfo("Done", "Complete"))
                    self.after(800, self._reset)
        except queue.Empty: pass
        self.after(50, self._process_queue)

    def _reset(self):
        self.stop_wiggle()
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.progress['value'] = 0
        self.update_idletasks()
        self.worker = None