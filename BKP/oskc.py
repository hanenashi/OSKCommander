import os
import json
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import time
import datetime
import shutil
import random

APP_TITLE = "OberSturmKlippCommander Pro v5.4 (Final Fix)"
DEFAULT_REMOTE_PATH = "/storage/emulated/0/DCIM/Camera"
SETTINGS_FILE = "osk_settings.json"
ICON_FILENAME = "obersturmkiippfuhrer.png"

# ----------------- CONFIG & UTILS -----------------

def load_settings():
    defaults = {
        "adb_path": "",
        "remote_path": DEFAULT_REMOTE_PATH,
        "last_dest": "",
        "limit_n": 0,
        "debug_mode": False,
        "smart_sort": True,
        "sort_order": "Oldest First"
    }
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
    except Exception:
        pass
    return defaults

def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def check_adb_dlls(adb_path):
    if not adb_path or not os.path.isabs(adb_path):
        return []
    folder = os.path.dirname(adb_path)
    required = ["AdbWinApi.dll", "AdbWinUsbApi.dll"]
    missing = [dll for dll in required if not os.path.exists(os.path.join(folder, dll))]
    return missing

def format_time(seconds):
    if seconds < 60: return f"{int(seconds)}s"
    mins = int(seconds / 60)
    secs = int(seconds % 60)
    return f"{mins}m {secs}s"

# ----------------- CORE LOGIC -----------------

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
            
        return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', startupinfo=startupinfo)

    def scan_media(self):
        if self.logger: self.logger("[*] Triggering Media Scan...")
        self.run([
            "shell", "content", "call",
            "--uri", "content://media",
            "--method", "scan_volume",
            "--arg", "external_primary"
        ])

# ----------------- WORKER: SYNC -----------------

class SyncWorker(threading.Thread):
    def __init__(self, config, ui_queue):
        super().__init__(daemon=True)
        self.config = config
        self.adb = AdbWrapper(config["adb_path"], config["debug_mode"], self._log_wrapper)
        self.remote_dir = config["remote_path"].rstrip("/")
        self.local_dir = config["last_dest"]
        self.delete_after = config.get("delete_after", False)
        self.limit = config.get("limit_n", 0)
        self.smart_sort = config.get("smart_sort", False)
        self.sort_order = config.get("sort_order", "Oldest First")
        self.queue = ui_queue
        self.stop_event = threading.Event()

    def _log_wrapper(self, msg):
        self.queue.put(("log", msg))

    def _log(self, msg):
        self.queue.put(("log", msg))

    def run(self):
        self._log(f"--- Starting Extraction ({self.sort_order}) ---")
        self.queue.put(("wiggle_start",)) 

        self.queue.put(("status", "Scanning & Sorting remote files..."))
        ls_flags = ["-1"]
        
        if self.sort_order == "Oldest First":
            ls_flags.append("-tr")
        elif self.sort_order == "Newest First":
            ls_flags.append("-t")
            
        res = self.adb.run(["shell", "ls"] + ls_flags + [self.remote_dir])
        
        if res.returncode != 0:
            self.queue.put(("error", f"Could not list files:\n{res.stderr}"))
            self.queue.put(("wiggle_stop",))
            return

        all_files = [f.strip() for f in res.stdout.splitlines() if f.strip()]
        all_files = [f for f in all_files if not f.startswith(".")]

        if self.sort_order == "Name (A-Z)":
            all_files.sort()
        elif self.sort_order == "Name (Z-A)":
            all_files.sort(reverse=True)

        if self.limit > 0:
            all_files = all_files[:self.limit]
            self._log(f"(!) Limit Active: Processing first {self.limit} files.")

        total = len(all_files)
        if total == 0:
            self._log("No files found.")
            self.queue.put(("done", 0, 0, "0s"))
            self.queue.put(("wiggle_stop",))
            return

        self._log(f"Queue: {total} files found.")
        
        processed = 0
        deleted = 0
        start_time = time.time()

        for i, filename in enumerate(all_files):
            if self.stop_event.is_set():
                self._log("!!! Cancelled by User !!!")
                break

            remote_path = f"{self.remote_dir}/{filename}"
            temp_local_path = os.path.join(self.local_dir, filename)
            final_local_path = temp_local_path
            
            elapsed = time.time() - start_time
            if i > 0:
                avg_time = elapsed / i
                remain_time = avg_time * (total - i)
                eta_str = f"ETA: {format_time(remain_time)}"
            else:
                eta_str = "Calculating..."

            pct = ((i) / total) * 100
            self.queue.put(("progress", pct, f"[{i+1}/{total}] {filename} | {eta_str}"))

            # --- 1. DOWNLOAD ---
            should_pull = True
            if os.path.exists(temp_local_path) and os.path.getsize(temp_local_path) > 0:
                should_pull = False
            
            if should_pull:
                pull_res = self.adb.run(["pull", "-a", remote_path, temp_local_path])
                if pull_res.returncode != 0:
                    self._log(f"[FAIL] Download error: {filename}")
                    continue

            # --- 2. SMART SORT ---
            if self.smart_sort and os.path.exists(temp_local_path):
                try:
                    mtime = os.path.getmtime(temp_local_path)
                    dt = datetime.datetime.fromtimestamp(mtime)
                    folder_name = dt.strftime("%Y-%m")
                    target_folder = os.path.join(self.local_dir, folder_name)
                    os.makedirs(target_folder, exist_ok=True)
                    sorted_path = os.path.join(target_folder, filename)
                    
                    if os.path.exists(sorted_path):
                        if os.path.getsize(sorted_path) == os.path.getsize(temp_local_path):
                             if should_pull: os.remove(temp_local_path)
                             final_local_path = sorted_path
                        else:
                            base, ext = os.path.splitext(filename)
                            new_name = f"{base}_{int(time.time())}{ext}"
                            sorted_path = os.path.join(target_folder, new_name)
                            shutil.move(temp_local_path, sorted_path)
                            final_local_path = sorted_path
                            self._log(f"[SORT] Renamed: {new_name}")
                    else:
                        shutil.move(temp_local_path, sorted_path)
                        final_local_path = sorted_path

                except Exception as e:
                    self._log(f"[ERR] Sort failed for {filename}: {e}")

            # --- 3. DELETE (Only if "Move Mode" checked) ---
            if self.delete_after:
                if os.path.exists(final_local_path) and os.path.getsize(final_local_path) > 0:
                    del_res = self.adb.run(["shell", "rm", f"'{remote_path}'"])
                    if del_res.returncode == 0:
                        deleted += 1
                        self._log(f"[DEL] {filename}")
                else:
                    self._log(f"[WARN] Verification failed, skipping delete: {filename}")

            processed += 1

        if deleted > 0:
            self.adb.scan_media()

        total_time = format_time(time.time() - start_time)
        self.queue.put(("progress", 100, "Finishing...")) 
        self.queue.put(("wiggle_stop",))
        self.queue.put(("jump",)) 
        self.queue.put(("done", processed, deleted, total_time))

    def stop(self):
        self.stop_event.set()

# ----------------- WORKER: VERIFY -----------------

class VerifyWorker(threading.Thread):
    def __init__(self, config, ui_queue):
        super().__init__(daemon=True)
        self.config = config
        self.adb = AdbWrapper(config["adb_path"], config["debug_mode"])
        self.remote_dir = config["remote_path"].rstrip("/")
        self.local_dir = config["last_dest"]
        self.queue = ui_queue
        self.safe_to_delete = []

    def run(self):
        self.queue.put(("log", "--- Starting Verification Scan ---"))
        self.queue.put(("wiggle_start",))
        
        local_index = {}
        count_local = 0
        for root, dirs, files in os.walk(self.local_dir):
            for f in files:
                path = os.path.join(root, f)
                try:
                    sz = os.path.getsize(path)
                    if f not in local_index: local_index[f] = set()
                    local_index[f].add(sz)
                    count_local += 1
                except: pass
        
        self.queue.put(("log", f"   Indexed {count_local} local files."))
        self.queue.put(("log", "2. Scanning Phone Files (Size Check)..."))

        res = self.adb.run(["shell", "cd", f"'{self.remote_dir}'", "&&", "stat", "-c", "'%s|%n'", "*"])
        
        files_to_check = []
        if res.returncode == 0 and "|" in res.stdout:
            files_to_check = [line.strip().split("|", 1) for line in res.stdout.splitlines() if "|" in line]
        else:
            self.queue.put(("error", "Device does not support 'stat' command."))
            self.queue.put(("wiggle_stop",))
            return

        total_remote = len(files_to_check)
        self.queue.put(("progress", 0, f"Comparing {total_remote} files..."))
        
        matched = 0
        for i, (sz_str, name) in enumerate(files_to_check):
            try:
                remote_size = int(sz_str)
                name = name.strip()
                is_safe = False
                if name in local_index:
                    if remote_size in local_index[name]:
                        is_safe = True
                
                if is_safe:
                    self.safe_to_delete.append(name)
                    matched += 1
                    # Log match to file
                    self.queue.put(("log", f"[MATCH] Safe to delete: {name}"))
                
                if i % 100 == 0:
                     pct = (i / total_remote) * 100
                     self.queue.put(("progress", pct, f"Comparing {i}/{total_remote}..."))
            except: pass

        self.queue.put(("progress", 100, "Done"))
        self.queue.put(("wiggle_stop",))
        self.queue.put(("jump",))
        self.queue.put(("verify_done", total_remote, matched, self.safe_to_delete))

# ----------------- UI DIALOGS -----------------

class CleanupDialog(tk.Toplevel):
    def __init__(self, parent, settings, main_logger):
        super().__init__(parent)
        self.title("Verify & Free Space")
        self.geometry("600x500")
        self.settings = settings
        self.main_logger = main_logger
        self.queue = queue.Queue()
        self.worker = None
        self.safe_files = [] 
        self.create_widgets()
        self.transient(parent)
        self.start_scan()
        self.after(100, self.process_queue)

    def create_widgets(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="Deep Verification Scan", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(main, text="Checking if files on Phone exist in PC Backup...").pack(anchor="w", pady=(0,10))
        self.log = tk.Text(main, height=15, state="disabled", font=("Consolas", 9))
        self.log.pack(fill="both", expand=True)
        self.progress = ttk.Progressbar(main, mode="determinate")
        self.progress.pack(fill="x", pady=10)
        self.lbl_status = ttk.Label(main, text="Initializing...")
        self.lbl_status.pack(anchor="w")
        self.btn_frame = ttk.Frame(main)
        self.btn_frame.pack(fill="x", pady=10)
        self.btn_delete = ttk.Button(self.btn_frame, text="DELETE SAFE FILES", command=self.delete_safe_files, state="disabled")
        self.btn_delete.pack(side="right")
        ttk.Button(self.btn_frame, text="Close", command=self.destroy).pack(side="right", padx=10)

    def log_msg(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", f"{msg}\n")
        self.log.see("end")
        self.log.config(state="disabled")
        if self.main_logger:
            self.main_logger(f"[CLEANUP] {msg}")

    def start_scan(self):
        self.worker = VerifyWorker(self.settings, self.queue)
        self.worker.start()

    def delete_safe_files(self):
        count = len(self.safe_files)
        if count == 0: return
        if not messagebox.askyesno("Confirm", f"Delete {count} verified files from phone?"): return
        self.btn_delete.config(state="disabled")
        self.log_msg("--- STARTING DELETION ---")
        threading.Thread(target=self.run_deletion, args=(self.settings["adb_path"], self.settings["remote_path"].rstrip("/")), daemon=True).start()

    def run_deletion(self, adb, base):
        batch_size = 20
        total = len(self.safe_files)
        def log_adapter(msg): self.queue.put(("log", msg))
        wrapper = AdbWrapper(adb, logger=log_adapter)
        
        for i in range(0, total, batch_size):
            batch = self.safe_files[i:i+batch_size]
            log_adapter(f"[DEL_BATCH] {', '.join(batch)}")
            
            args = ["shell", "cd", f"'{base}'", "&&", "rm"] + [f"'{f}'" for f in batch]
            wrapper.run(args)
            
            # FIXED: Correctly calculate items processed
            current_done = min(i + batch_size, total)
            self.queue.put(("log", f"Deleted {current_done}/{total}..."))
        
        self.queue.put(("log", "--- DELETION COMPLETE ---"))
        wrapper.scan_media()
        self.queue.put(("deletion_done",))

    def process_queue(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                kind = msg[0]
                if kind == "log": self.log_msg(msg[1])
                elif kind == "progress":
                    self.progress['value'] = msg[1]
                    self.lbl_status.config(text=msg[2])
                elif kind == "error": self.log_msg(f"ERROR: {msg[1]}")
                elif kind == "wiggle_start": pass 
                elif kind == "wiggle_stop": pass
                elif kind == "jump": pass
                elif kind == "verify_done":
                    total, matched, files = msg[1], msg[2], msg[3]
                    self.safe_files = files
                    self.log_msg(f"Safe to delete: {matched} / {total}")
                    if matched > 0: self.btn_delete.config(state="normal", text=f"DELETE {matched} FILES")
                    else: self.btn_delete.config(text="Nothing to delete")
                elif kind == "deletion_done":
                    messagebox.showinfo("Success", "Cleanup complete.")
                    self.btn_delete.config(text="Deletion Complete", state="disabled")
        except queue.Empty: pass
        self.after(100, self.process_queue)

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, current_settings):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("500x550")
        self.settings = current_settings
        self.result = None
        self.create_widgets()
        self.transient(parent)
        self.grab_set()

    def create_widgets(self):
        pad = {'padx': 10, 'pady': 5}
        
        lf_adb = ttk.LabelFrame(self, text="ADB Configuration", padding=10)
        lf_adb.pack(fill="x", **pad)
        f_adb = ttk.Frame(lf_adb)
        f_adb.pack(fill="x")
        self.adb_var = tk.StringVar(value=self.settings.get("adb_path", ""))
        self.adb_var.trace_add("write", self.validate_adb)
        ttk.Entry(f_adb, textvariable=self.adb_var).pack(side="left", fill="x", expand=True)
        ttk.Button(f_adb, text="Browse", command=self.browse_adb).pack(side="right", padx=(5,0))
        self.lbl_dll_status = ttk.Label(lf_adb, text="", font=("Segoe UI", 8))
        self.lbl_dll_status.pack(anchor="w", pady=(5,0))

        lf_feat = ttk.LabelFrame(self, text="Processing Options", padding=10)
        lf_feat.pack(fill="x", **pad)
        
        f_sort = ttk.Frame(lf_feat)
        f_sort.pack(fill="x", pady=2)
        ttk.Label(f_sort, text="Processing Order:").pack(side="left")
        self.sort_var = tk.StringVar(value=self.settings.get("sort_order", "Oldest First"))
        sort_opts = ["Oldest First", "Newest First", "Name (A-Z)", "Name (Z-A)"]
        ttk.Combobox(f_sort, textvariable=self.sort_var, values=sort_opts, state="readonly", width=15).pack(side="left", padx=10)

        self.sort_bool_var = tk.BooleanVar(value=self.settings.get("smart_sort", True))
        ttk.Checkbutton(lf_feat, text="Smart Sort: Organize into YYYY-MM folders", variable=self.sort_bool_var).pack(anchor="w", pady=(10,0))
        
        f_lim = ttk.Frame(lf_feat)
        f_lim.pack(fill="x", pady=(10, 2))
        ttk.Label(f_lim, text="Test Limit (0=Off):").pack(side="left")
        self.limit_var = tk.IntVar(value=self.settings.get("limit_n", 0))
        ttk.Spinbox(f_lim, from_=0, to=9999, textvariable=self.limit_var, width=8).pack(side="left", padx=10)

        self.debug_var = tk.BooleanVar(value=self.settings.get("debug_mode", False))
        ttk.Checkbutton(lf_feat, text="Verbose Debug Log", variable=self.debug_var).pack(anchor="w", pady=(5,0))

        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill="x", side="bottom")
        ttk.Button(btn_frame, text="Save", command=self.save).pack(side="right")
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="right", padx=5)
        self.validate_adb()

    def browse_adb(self):
        f = filedialog.askopenfilename(filetypes=[("ADB", "adb.exe")])
        if f: self.adb_var.set(f)

    def validate_adb(self, *args):
        path = self.adb_var.get()
        if not path:
            self.lbl_dll_status.config(text="Using system/fallback ADB", foreground="orange")
            return
        if not os.path.exists(path):
            self.lbl_dll_status.config(text="File not found!", foreground="red")
            return
        missing = check_adb_dlls(path)
        if missing:
            self.lbl_dll_status.config(text=f"Missing: {', '.join(missing)}", foreground="red")
        else:
            self.lbl_dll_status.config(text="ADB OK", foreground="green")

    def save(self):
        self.result = {
            "adb_path": self.adb_var.get(),
            "limit_n": self.limit_var.get(),
            "debug_mode": self.debug_var.get(),
            "smart_sort": self.sort_bool_var.get(),
            "sort_order": self.sort_var.get()
        }
        self.destroy()

# ----------------- MAIN GUI -----------------

class OSKCommanderPro(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("700x750")
        
        if not os.path.exists("logs"): os.makedirs("logs")

        self.settings = load_settings()
        self.ensure_adb_resolved()
        self.worker = None
        self.queue = queue.Queue()
        self.current_log_file = None
        
        # Wiggle stuff
        self.wiggle_active = False
        self.current_pct = 0.0
        self.icon_img = None
        self.icon_id = None
        self.base_x = 0
        self.base_y = 0

        self._build_ui()
        self.after(100, self._process_queue)

    def ensure_adb_resolved(self):
        if not self.settings.get("adb_path"):
            self.settings["adb_path"] = "adb"

    def _build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        # Header
        top = ttk.Frame(main)
        top.pack(fill="x", pady=5)
        ttk.Label(top, text="OberSturmKlippCommander", font=("Segoe UI", 12, "bold")).pack(side="left")
        
        btns = ttk.Frame(top)
        btns.pack(side="right")
        ttk.Button(btns, text="⚙ Settings", command=self.open_settings).pack(side="right", padx=5)
        ttk.Button(btns, text="🛡 Verify & Cleanup", command=self.open_cleanup).pack(side="right")

        # Config
        grp_path = ttk.LabelFrame(main, text="Paths", padding=10)
        grp_path.pack(fill="x", pady=5)
        
        r_row = ttk.Frame(grp_path)
        r_row.pack(fill="x", pady=2)
        ttk.Label(r_row, text="Phone Source:", width=12).pack(side="left")
        self.remote_var = tk.StringVar(value=self.settings.get("remote_path", DEFAULT_REMOTE_PATH))
        ttk.Entry(r_row, textvariable=self.remote_var).pack(side="left", fill="x", expand=True)

        l_row = ttk.Frame(grp_path)
        l_row.pack(fill="x", pady=2)
        ttk.Label(l_row, text="PC Destination:", width=12).pack(side="left")
        self.local_var = tk.StringVar(value=self.settings.get("last_dest", ""))
        ttk.Entry(l_row, textvariable=self.local_var).pack(side="left", fill="x", expand=True, padx=(0,5))
        ttk.Button(l_row, text="Browse", command=self._browse_dest).pack(side="right")

        # Action
        grp_act = ttk.LabelFrame(main, text="Sync Operation", padding=10)
        grp_act.pack(fill="x", pady=5)
        
        self.delete_var = tk.BooleanVar(value=False)
        cb_del = ttk.Checkbutton(grp_act, text="Auto-Delete after successful copy (Batch Mode)", variable=self.delete_var)
        cb_del.pack(anchor="w")

        self.lbl_info = ttk.Label(grp_act, text="", foreground="blue", font=("Segoe UI", 9))
        self.lbl_info.pack(anchor="w", padx=20, pady=(2,0))
        self.update_info_label()

        # Controls
        ctrl = ttk.Frame(main, padding=5)
        ctrl.pack(fill="x", pady=10)
        self.btn_start = ttk.Button(ctrl, text="START EXTRACTION", command=self._start)
        self.btn_start.pack(side="left", fill="x", expand=True, padx=5)
        self.btn_stop = ttk.Button(ctrl, text="STOP", command=self._stop, state="disabled")
        self.btn_stop.pack(side="right", fill="x", expand=True, padx=5)

        # Progress Area with Avatar
        prog_frame = ttk.Frame(main)
        prog_frame.pack(fill="x", pady=5)
        
        self.canvas = tk.Canvas(prog_frame, width=50, height=80, highlightthickness=0)
        self.canvas.pack(side="left", padx=(0, 10))
        self.load_avatar()

        status_frame = ttk.Frame(prog_frame)
        status_frame.pack(side="left", fill="x", expand=True)
        
        self.lbl_status = ttk.Label(status_frame, text="Ready")
        self.lbl_status.pack(anchor="w")
        self.progress = ttk.Progressbar(status_frame, mode="determinate")
        self.progress.pack(fill="x", pady=(2,0))

        # Log
        log_fr = ttk.LabelFrame(main, text="Log", padding=5)
        log_fr.pack(fill="both", expand=True)
        log_tools = ttk.Frame(log_fr)
        log_tools.pack(fill="x", pady=(0, 2))
        ttk.Button(log_tools, text="Copy Log", command=self.copy_log, width=10).pack(side="right", padx=2)
        ttk.Button(log_tools, text="Clear", command=self.clear_log, width=8).pack(side="right", padx=2)

        self.log_text = tk.Text(log_fr, height=10, state="disabled", font=("Consolas", 9))
        sb = ttk.Scrollbar(log_fr, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def load_avatar(self):
        try:
            if os.path.exists(ICON_FILENAME):
                img = tk.PhotoImage(file=ICON_FILENAME)
                w, h = img.width(), img.height()
                scale = max(1, int(w / 48)) 
                self.icon_img = img.subsample(scale, scale)
                self.base_x, self.base_y = 25, 60 
                self.icon_id = self.canvas.create_image(self.base_x, self.base_y, image=self.icon_img)
        except Exception:
            pass

    def start_wiggle(self):
        self.wiggle_active = True
        self.current_pct = 0
        self.do_wiggle()

    def stop_wiggle(self):
        self.wiggle_active = False
        if self.icon_id:
            self.canvas.coords(self.icon_id, self.base_x, self.base_y)

    def do_wiggle(self):
        if not self.icon_id or not self.wiggle_active: return
        pct = self.current_pct
        if pct < 50:
            intensity = 1
            delay = 150 
        elif pct < 85:
            intensity = 2
            delay = 80
        else:
            intensity = 4
            delay = 30
        dx = random.randint(-intensity, intensity)
        dy = random.randint(-intensity, intensity)
        self.canvas.coords(self.icon_id, self.base_x + dx, self.base_y + dy)
        self.after(delay, self.do_wiggle)

    def jump_for_joy(self):
        if not self.icon_id: return
        self.stop_wiggle()
        self.canvas.coords(self.icon_id, self.base_x, self.base_y - 30)
        def fall_down():
            self.canvas.coords(self.icon_id, self.base_x, self.base_y)
        self.after(600, fall_down)

    def update_info_label(self):
        info = []
        info.append(f"Sort: {self.settings.get('sort_order', 'Oldest First')}")
        if self.settings.get("smart_sort", True): info.append("Smart Sort: ON")
        if self.settings.get("limit_n", 0) > 0: info.append(f"Limit: {self.settings['limit_n']}")
        self.lbl_info.config(text=" | ".join(info))

    def open_settings(self):
        self.jump_for_joy()
        dlg = SettingsDialog(self, self.settings)
        self.wait_window(dlg)
        if dlg.result:
            self.settings.update(dlg.result)
            save_settings(self.settings)
            self.update_info_label()
            self._log("Configuration updated.")

    def ensure_log_session(self):
        if not self.current_log_file:
            ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
            self.current_log_file = os.path.join("logs", f"osk_log_{ts}.txt")
            self._log(f"=== Session Auto-Started: {ts} ===")
            self._log(f"Log file: {self.current_log_file}")

    def open_cleanup(self):
        self.jump_for_joy()
        self.ensure_log_session() 

        self.settings["remote_path"] = self.remote_var.get()
        self.settings["last_dest"] = self.local_var.get()
        if not self.settings["last_dest"]:
            messagebox.showwarning("Error", "Please select PC destination first.")
            return
        
        CleanupDialog(self, self.settings, self._log_file_only)

    def _browse_dest(self):
        d = filedialog.askdirectory()
        if d: self.local_var.set(d)

    def _log_file_only(self, msg):
        if self.current_log_file:
            try:
                with open(self.current_log_file, "a", encoding="utf-8") as f:
                    f.write(f"{msg}\n")
            except: pass

    def _log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"{msg}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        self._log_file_only(msg)

    def copy_log(self):
        try:
            txt = self.log_text.get("1.0", "end")
            self.clipboard_clear()
            self.clipboard_append(txt)
            messagebox.showinfo("Log", "Log copied.")
        except: pass

    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _start(self):
        self.jump_for_joy()
        remote = self.remote_var.get().strip()
        local = self.local_var.get().strip()
        if not local or not os.path.exists(local):
            messagebox.showwarning("Error", "Select a valid PC folder.")
            return
        
        if not self.current_log_file:
             ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
             self.current_log_file = os.path.join("logs", f"osk_log_{ts}.txt")
             self._log(f"=== Session Started: {ts} ===")
             self._log(f"Log file: {self.current_log_file}")

        self.settings["last_dest"] = local
        self.settings["remote_path"] = remote
        save_settings(self.settings)
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        cfg = self.settings.copy()
        cfg["delete_after"] = self.delete_var.get()
        self.worker = SyncWorker(cfg, self.queue)
        self.worker.start()

    def _stop(self):
        if self.worker:
            self.worker.stop()
            self.btn_stop.config(state="disabled")
            self._log("Stopping...")

    def _process_queue(self):
        try:
            while True:
                msg = self.queue.get_nowait()
                kind = msg[0]
                if kind == "log": self._log(msg[1])
                elif kind == "status": self.lbl_status.config(text=msg[1])
                elif kind == "progress":
                    self.current_pct = msg[1] # Update for wiggle
                    self.progress['value'] = msg[1]
                    self.lbl_status.config(text=msg[2])
                elif kind == "wiggle_start": self.start_wiggle()
                elif kind == "wiggle_stop": self.stop_wiggle()
                elif kind == "jump": self.jump_for_joy()
                elif kind == "error":
                    messagebox.showerror("Error", msg[1])
                    self._reset()
                elif kind == "done":
                    # DELAYED POPUP: Wait 800ms for jump to land
                    self.after(800, lambda m=msg: self._show_done(m))
        except queue.Empty: pass
        self.after(50, self._process_queue)

    def _show_done(self, msg):
        summary = f"Completed in {msg[3]}.\nProcessed: {msg[1]}\nDeleted: {msg[2]}"
        self._log("-" * 30)
        self._log(summary)
        messagebox.showinfo("Done", summary)
        self._reset()

    def _reset(self):
        self.stop_wiggle()
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.progress['value'] = 0
        self.lbl_status.config(text="Ready")
        self.worker = None

if __name__ == "__main__":
    app = OSKCommanderPro()
    app.mainloop()