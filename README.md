# OberSturmKlippCommander (OSKC) 📸

**The "No-Nonsense" Android Photo Sync & Cleanup Tool.**

### TL;DR
OSKC is a modular Python application that safely pulls photos/videos from your Android device via ADB, sorts them into `YYYY-MM` folders on your PC, and helps you free up phone storage by verifying backups before deletion. It features a robust queue system, live USB monitoring, and a wiggling avatar.

---

### 🚀 How to Run

#### Option A: The Executable (Recommended)
Just download the latest `OberSturmKlippCommander.exe` from the Releases page and run it. No installation required.

#### Option B: From Source
1. Clone this repo:
   ```bash
   git clone [https://github.com/hanenashi/OSKCommander.git](https://github.com/hanenashi/OSKCommander.git)
   cd OSKCommander
   ```
2. Run the entry point:
   ```bash
   python main.py
   ```
   *(Note: Requires Python 3.x. No external dependencies needed for basic usage, standard library only.)*

---

### 🛡️ Safety First (Read This!)

If you are a new user or running this on a new phone for the first time, follow these **Golden Rules**:

1.  **✅ Toggle Logs ON:**
    Click **⚙ Settings** and check **"Verbose Debug Log"**. This lets you see exactly what the tool is doing in the log window.

2.  **✅ Use Small Batches:**
    Don't try to copy 10,000 photos in one go immediately. In **Settings**, set the **"Limit"** to `50`. Run the sync, check your PC folder to ensure everything looks right, *then* set Limit back to `0` (Unlimited).

3.  **✅ Verify Before You Delete:**
    Use the dedicated **"🛡 Verify & Cleanup"** button. It performs a deep scan to match files on your phone against your PC backup (checking name AND file size) before letting you delete anything.

---

### ✨ Features

* **Smart Sort:** Automatically organizes flat camera folders into neat `YYYY-MM` directories on your PC based on the file's original timestamp.
* **Zero-Risk Sync:** Skips files that already exist on the PC to save time.
* **Verify & Free Space:** A specialized tool to verify backups and mass-delete *only* safe files from the phone.
* **Advanced Filters:** Filter files by Date Range or Filename (e.g., only copy files starting with 'A' through 'F').
* **Live Status:** Real-time USB connection monitoring (detects Unauthorized/Offline states).
* **Portable:** Can auto-detect `adb.exe` if placed in the root folder, making it fully portable on a USB stick.

### 🛠️ Building the .exe
If you want to build the executable yourself (requires `pyinstaller`):
```bash
pip install pyinstaller
build_exe.bat
```
The resulting binary will be in the `dist/` folder.