import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import os  # <--- FIXED: Added missing import
from core.adb import AdbWrapper, check_adb_dlls
from core.worker import VerifyWorker

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, current_settings):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("500x650")
        self.settings = current_settings
        self.result = None
        self.create_widgets()
        self.transient(parent)
        self.grab_set()

    def create_widgets(self):
        pad = {'padx': 10, 'pady': 5}
        
        # ADB
        lf_adb = ttk.LabelFrame(self, text="ADB Config", padding=10)
        lf_adb.pack(fill="x", **pad)
        f_adb = ttk.Frame(lf_adb)
        f_adb.pack(fill="x")
        self.adb_var = tk.StringVar(value=self.settings.get("adb_path", ""))
        self.adb_var.trace_add("write", self.validate_adb)
        ttk.Entry(f_adb, textvariable=self.adb_var).pack(side="left", fill="x", expand=True)
        ttk.Button(f_adb, text="Browse", command=self.browse_adb).pack(side="right")
        self.lbl_dll = ttk.Label(lf_adb, text="", font=("Segoe UI", 8))
        self.lbl_dll.pack(anchor="w")

        # Sort & Limits
        lf_gen = ttk.LabelFrame(self, text="General Processing", padding=10)
        lf_gen.pack(fill="x", **pad)
        
        f_s = ttk.Frame(lf_gen)
        f_s.pack(fill="x", pady=2)
        ttk.Label(f_s, text="Order:").pack(side="left")
        self.sort_var = tk.StringVar(value=self.settings.get("sort_order", "Oldest First"))
        ttk.Combobox(f_s, textvariable=self.sort_var, values=["Oldest First", "Newest First", "Name (A-Z)", "Name (Z-A)"], state="readonly").pack(side="left", padx=5)
        
        self.smart_sort_var = tk.BooleanVar(value=self.settings.get("smart_sort", True))
        ttk.Checkbutton(lf_gen, text="Smart Sort (YYYY-MM folders)", variable=self.smart_sort_var).pack(anchor="w")

        f_lim = ttk.Frame(lf_gen)
        f_lim.pack(fill="x", pady=2)
        ttk.Label(f_lim, text="Limit (0=All):").pack(side="left")
        self.limit_var = tk.IntVar(value=self.settings.get("limit_n", 0))
        ttk.Spinbox(f_lim, from_=0, to=9999, textvariable=self.limit_var, width=8).pack(side="left", padx=5)

        # Filters
        lf_filt = ttk.LabelFrame(self, text="Filters (Include Only)", padding=10)
        lf_filt.pack(fill="x", **pad)

        # Date Filter
        f_date = ttk.Frame(lf_filt)
        f_date.pack(fill="x", pady=2)
        self.use_date_var = tk.BooleanVar(value=self.settings.get("filter_enable_date", False))
        ttk.Checkbutton(f_date, text="Date Range:", variable=self.use_date_var).pack(side="left")
        
        self.date_s_var = tk.StringVar(value=self.settings.get("filter_date_start", "2020-01-01"))
        ttk.Entry(f_date, textvariable=self.date_s_var, width=10).pack(side="left", padx=5)
        ttk.Label(f_date, text="to").pack(side="left")
        self.date_e_var = tk.StringVar(value=self.settings.get("filter_date_end", "2030-12-31"))
        ttk.Entry(f_date, textvariable=self.date_e_var, width=10).pack(side="left", padx=5)
        ttk.Label(f_date, text="(YYYY-MM-DD)", foreground="gray", font=("Segoe UI", 8)).pack(side="left")

        # Letter Filter
        f_let = ttk.Frame(lf_filt)
        f_let.pack(fill="x", pady=2)
        self.use_let_var = tk.BooleanVar(value=self.settings.get("filter_enable_letter", False))
        ttk.Checkbutton(f_let, text="Filename Starts With:", variable=self.use_let_var).pack(side="left")
        
        self.let_s_var = tk.StringVar(value=self.settings.get("filter_letter_start", "A"))
        ttk.Entry(f_let, textvariable=self.let_s_var, width=3).pack(side="left", padx=5)
        ttk.Label(f_let, text="to").pack(side="left")
        self.let_e_var = tk.StringVar(value=self.settings.get("filter_letter_end", "Z"))
        ttk.Entry(f_let, textvariable=self.let_e_var, width=3).pack(side="left", padx=5)

        self.debug_var = tk.BooleanVar(value=self.settings.get("debug_mode", False))
        ttk.Checkbutton(self, text="Debug Log", variable=self.debug_var).pack(anchor="w", padx=15)

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
            self.lbl_dll.config(text="Using system/fallback", foreground="orange")
            return
        if not os.path.exists(path):
            self.lbl_dll.config(text="File not found", foreground="red")
            return
        missing = check_adb_dlls(path)
        if missing:
            self.lbl_dll.config(text=f"Missing: {','.join(missing)}", foreground="red")
        else:
            self.lbl_dll.config(text="ADB OK", foreground="green")

    def save(self):
        self.result = {
            "adb_path": self.adb_var.get(),
            "limit_n": self.limit_var.get(),
            "debug_mode": self.debug_var.get(),
            "smart_sort": self.smart_sort_var.get(),
            "sort_order": self.sort_var.get(),
            "filter_enable_date": self.use_date_var.get(),
            "filter_date_start": self.date_s_var.get(),
            "filter_date_end": self.date_e_var.get(),
            "filter_enable_letter": self.use_let_var.get(),
            "filter_letter_start": self.let_s_var.get(),
            "filter_letter_end": self.let_e_var.get()
        }
        self.destroy()

# --- CLEANUP DIALOG (RESTORED) ---
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