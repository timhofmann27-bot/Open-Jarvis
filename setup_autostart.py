"""Installiert den Hintergrund-Listener in den Windows-Autostart.

Lauf: python setup_autostart.py
Danach neu anmelden oder start_listener.vbs doppelklicken.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LISTENER_PY = BASE_DIR / "background_listener.py"
STARTUP_DIR = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
SHORTCUT_NAME = "JarvisListener.lnk"
VBS_NAME = "start_listener.vbs"

def create_vbs():
    """Create VBS that runs background_listener.py hidden."""
    vbs_path = BASE_DIR / VBS_NAME
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable  # fallback
    lines = [
        'Dim shell',
        'Set shell = CreateObject("WScript.Shell")',
        f'shell.Run "{pythonw} ""{LISTENER_PY}""", 0, False',
        'Set shell = Nothing',
    ]
    vbs_path.write_text("\r\n".join(lines), encoding="utf-8")
    print(f"[OK] {vbs_path} erstellt")
    return vbs_path

def install_startup(vbs_path: Path):
    """Create shortcut in Startup folder via VBScript."""
    lines = [
        'Dim WSH, Shortcut',
        'Set WSH = CreateObject("WScript.Shell")',
        f'Set Shortcut = WSH.CreateShortcut("{STARTUP_DIR / SHORTCUT_NAME}")',
        'Shortcut.TargetPath = "wscript.exe"',
        f'Shortcut.Arguments = "{vbs_path}"',
        f'Shortcut.WorkingDirectory = "{BASE_DIR}"',
        'Shortcut.Description = "Jarvis Background Listener"',
        'Shortcut.WindowStyle = 7',
        'Shortcut.Save',
    ]
    vbs_code = "\r\n".join(lines)
    tmp = Path(tempfile.gettempdir()) / "_mk_jarvis_link.vbs"
    tmp.write_text(vbs_code, encoding="utf-8")
    subprocess.run(["wscript.exe", str(tmp)], capture_output=True)
    tmp.unlink()
    print(f"[OK] Autostart-Link erstellt: {STARTUP_DIR / SHORTCUT_NAME}")

if __name__ == "__main__":
    vbs = create_vbs()
    if not (STARTUP_DIR / SHORTCUT_NAME).exists():
        install_startup(vbs)
        print("[OK] Neuanmelden oder Neustarten, dann läuft Jarvis immer im Hintergrund.")
    else:
        print("[OK] Autostart bereits installiert.")
    print(f"\nManueller Start: Doppelklick auf {BASE_DIR / VBS_NAME}")
