import threading
import os
import time
import datetime
import shutil
from .adb import AdbWrapper
from .sorting import parse_timestamp, should_process

def format_time(seconds):
    if seconds < 60: return f"{int(seconds)}s"
    mins = int(seconds / 60)
    secs = int(seconds % 60)
    return f"{mins}m {secs}s"

class SyncWorker(threading.Thread):
    def __init__(self, config, ui_queue):
        super().__init__(daemon=True)
        self.config = config
        self.queue = ui_queue
        self.stop_event = threading.Event()
        
        # Setup Logger adapter
        def log_adapter(msg): self.queue.put(("log", msg))
        self.adb = AdbWrapper(config["adb_path"], config["debug_mode"], log_adapter)
        
    def _log(self, msg):
        self.queue.put(("log", msg))

    def run(self):
        self._log(f"--- Starting Extraction (Filter Aware) ---")
        self.queue.put(("wiggle_start",))
        self.queue.put(("status", "Scanning files & attributes..."))

        # We need STAT for dates now, ls is not enough for filters
        # cmd: stat -c '%Y|%n' *
        remote_dir = self.config["remote_path"].rstrip("/")
        res = self.adb.run(["shell", "cd", f"'{remote_dir}'", "&&", "stat", "-c", "'%Y|%n'", "*"])

        if res.returncode != 0:
            self.queue.put(("error", f"Scan failed (stat required):\n{res.stderr}"))
            self.queue.put(("wiggle_stop",))
            return

        # Parse File List
        all_items = []
        for line in res.stdout.splitlines():
            if "|" in line:
                parts = line.strip().split("|", 1)
                if len(parts) == 2:
                    ts_str, name = parts
                    # Ignore hidden/thumbs
                    if name.startswith("."): continue
                    all_items.append({
                        "name": name, 
                        "ts_raw": ts_str,
                        "date": parse_timestamp(ts_str)
                    })

        # Apply Filters (Phase 2)
        filtered_files = []
        ignored_count = 0
        
        for item in all_items:
            ok, reason = should_process(item["name"], item["date"], self.config)
            if ok:
                filtered_files.append(item)
            else:
                ignored_count += 1
                # self._log(f"[FILTER] Skip {item['name']}: {reason}") # Too verbose?

        if ignored_count > 0:
            self._log(f"(!) Filter Active: Ignored {ignored_count} files.")

        # Apply Sorting (Phase 1 logic adapted)
        sort_order = self.config.get("sort_order", "Oldest First")
        if sort_order == "Oldest First":
            filtered_files.sort(key=lambda x: x["date"])
        elif sort_order == "Newest First":
            filtered_files.sort(key=lambda x: x["date"], reverse=True)
        elif sort_order == "Name (A-Z)":
            filtered_files.sort(key=lambda x: x["name"])
        elif sort_order == "Name (Z-A)":
            filtered_files.sort(key=lambda x: x["name"], reverse=True)

        # Apply Limit
        limit = self.config.get("limit_n", 0)
        if limit > 0:
            filtered_files = filtered_files[:limit]
            self._log(f"(!) Limit Active: Processing first {limit} matches.")

        total = len(filtered_files)
        if total == 0:
            self._log("No files matched criteria.")
            self.queue.put(("done", 0, 0, "0s"))
            self.queue.put(("wiggle_stop",))
            return

        self._log(f"Queue: {total} files ready.")
        
        processed = 0
        deleted = 0
        start_time = time.time()
        local_dir = self.config["last_dest"]
        smart_sort = self.config.get("smart_sort", True)
        delete_after = self.config.get("delete_after", False)

        for i, item in enumerate(filtered_files):
            if self.stop_event.is_set(): break

            filename = item["name"]
            remote_path = f"{remote_dir}/{filename}"
            temp_local_path = os.path.join(local_dir, filename)
            
            # ETA
            elapsed = time.time() - start_time
            if i > 0:
                avg = elapsed / i
                eta = format_time(avg * (total - i))
            else: eta = "..."
            
            pct = ((i) / total) * 100
            self.queue.put(("progress", pct, f"[{i+1}/{total}] {filename} | ETA: {eta}"))

            # Logic mostly same as before, but using pulled timestamp info
            should_pull = True
            if os.path.exists(temp_local_path) and os.path.getsize(temp_local_path) > 0:
                should_pull = False
            
            if should_pull:
                pull_res = self.adb.run(["pull", "-a", remote_path, temp_local_path])
                if pull_res.returncode != 0:
                    self._log(f"[FAIL] {filename}")
                    continue

            # Smart Sort
            final_path = temp_local_path
            if smart_sort and os.path.exists(temp_local_path):
                # Use item["date"] which we already have!
                folder_name = item["date"].strftime("%Y-%m")
                target_folder = os.path.join(local_dir, folder_name)
                os.makedirs(target_folder, exist_ok=True)
                sorted_path = os.path.join(target_folder, filename)
                
                try:
                    if os.path.exists(sorted_path):
                        if os.path.getsize(sorted_path) == os.path.getsize(temp_local_path):
                            if should_pull: os.remove(temp_local_path)
                            final_path = sorted_path
                        else:
                            # Rename collision
                            base, ext = os.path.splitext(filename)
                            new_name = f"{base}_{int(time.time())}{ext}"
                            sorted_path = os.path.join(target_folder, new_name)
                            shutil.move(temp_local_path, sorted_path)
                            final_path = sorted_path
                            self._log(f"[SORT] Renamed: {new_name}")
                    else:
                        shutil.move(temp_local_path, sorted_path)
                        final_path = sorted_path
                except Exception as e:
                    self._log(f"[ERR] Sort: {e}")

            # Delete
            if delete_after:
                if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                    self.adb.run(["shell", "rm", f"'{remote_path}'"])
                    deleted += 1
                    self._log(f"[DEL] {filename}")

            processed += 1

        if deleted > 0:
            self.adb.scan_media()

        total_time = format_time(time.time() - start_time)
        self.queue.put(("progress", 100, "Done"))
        self.queue.put(("wiggle_stop",))
        self.queue.put(("jump",))
        self.queue.put(("done", processed, deleted, total_time))

    def stop(self):
        self.stop_event.set()

# We keep VerifyWorker largely the same but ensure it imports properly
class VerifyWorker(threading.Thread):
    def __init__(self, config, ui_queue):
        super().__init__(daemon=True)
        self.config = config
        self.queue = ui_queue
        self.adb = AdbWrapper(config["adb_path"], config["debug_mode"])
        self.remote_dir = config["remote_path"].rstrip("/")
        self.local_dir = config["last_dest"]
        self.safe_to_delete = []

    def run(self):
        self.queue.put(("log", "--- Verify Scan ---"))
        self.queue.put(("wiggle_start",))
        
        # Local Indexing
        local_index = {}
        for root, _, files in os.walk(self.local_dir):
            for f in files:
                try:
                    sz = os.path.getsize(os.path.join(root, f))
                    if f not in local_index: local_index[f] = set()
                    local_index[f].add(sz)
                except: pass
        
        # Remote Scan (stat)
        res = self.adb.run(["shell", "cd", f"'{self.remote_dir}'", "&&", "stat", "-c", "'%s|%n'", "*"])
        items = []
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if "|" in line: items.append(line.strip().split("|", 1))
        
        matched = 0
        total = len(items)
        
        for i, (sz, name) in enumerate(items):
            try:
                size = int(sz)
                if name in local_index and size in local_index[name]:
                    self.safe_to_delete.append(name)
                    matched += 1
                    self.queue.put(("log", f"[MATCH] {name}"))
                
                if i % 50 == 0:
                    self.queue.put(("progress", (i/total)*100, f"Verifying {i}/{total}"))
            except: pass

        self.queue.put(("progress", 100, "Done"))
        self.queue.put(("wiggle_stop",))
        self.queue.put(("jump",))
        self.queue.put(("verify_done", total, matched, self.safe_to_delete))