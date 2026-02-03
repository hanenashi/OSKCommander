# OberSturmKlippCommander (OSKC) 📸

**The "No-Nonsense" Android Photo Sync & Cleanup Tool.**

### TL;DR
OSKC is a modular Python application that safely pulls photos/videos from your Android device via ADB, sorts them into `YYYY-MM` folders on your PC, and helps you free up phone storage by verifying backups before deletion. It features a robust queue system, live USB monitoring, and a wiggling avatar.

---

### 📱 Phone Setup (First Time Only)
Before you start, you must enable **USB Debugging** on your phone:

1.  **Unlock Developer Mode:**
    * Go to **Settings > About Phone**.
    * Find **"Build Number"** (sometimes under Software Information).
    * Tap it **7 times fast** until it says "You are now a developer!".
2.  **Enable USB Debugging:**
    * Go back to **Settings > System > Developer Options**.
    * Scroll down and toggle **ON** "USB Debugging".
3.  **Authorize the PC:**
    * Connect your phone to the PC via USB.
    * Look at your phone screen. A popup will ask **"Allow USB Debugging?"**.
    * Check **"Always allow from this computer"** and tap **Allow**.

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

### 🛠️ Building the .exe
If you want to build the executable yourself (requires `pyinstaller`):
```bash
pip install pyinstaller
build_exe.bat
```
The resulting binary will be in the `dist/` folder.