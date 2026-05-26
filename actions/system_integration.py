"""
JARVIS System-Tiefenintegration für Windows.
Registry, Prozesse, Dienste, Power, Desktop, Netzwerk, Startup.
"""

import ctypes
import glob as glob_mod
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import psutil

try:
    import winreg
except ImportError:
    winreg = None


BASE_DIR = Path(__file__).resolve().parent.parent


# ── Helper ───────────────────────────────────────────────────────────────────

def _run(cmd: list[str], timeout: int = 15) -> tuple[str, str]:
    """Run a command and return (stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return "", "Timeout"
    except FileNotFoundError:
        return "", "Command not found"
    except Exception as e:
        return "", str(e)


def _powershell(script: str, timeout: int = 15) -> str:
    """Run a PowerShell script and return stdout."""
    out, _ = _run(["powershell", "-NoProfile", "-Command", script], timeout=timeout)
    return out


def _get_registry_key(hive_name: str, subkey: str):
    """Open a registry key by hive name."""
    hives = {
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
        "HKCR": winreg.HKEY_CLASSES_ROOT,
        "HKU":  winreg.HKEY_USERS,
        "HKCC": winreg.HKEY_CURRENT_CONFIG,
    }
    hive = hives.get(hive_name.upper())
    if not hive:
        raise ValueError(f"Unknown hive: {hive_name}")
    return winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ)


# ── Actions ──────────────────────────────────────────────────────────────────

def system_info() -> str:
    """Get comprehensive system information."""
    uname = platform.uname()

    # CPU
    cpu_count = psutil.cpu_count(logical=True)
    cpu_phys = psutil.cpu_count(logical=False)
    cpu_percent = psutil.cpu_percent(interval=0.5)

    # RAM
    mem = psutil.virtual_memory()
    ram_total = mem.total // (1024**3)
    ram_used = mem.used // (1024**3)
    ram_percent = mem.percent

    # Disk
    disks = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append(f"{part.device} ({usage.used//1024**3}GB/{usage.total//1024**3}GB {usage.percent}%)")
        except Exception:
            disks.append(f"{part.device}")

    # Network
    net = psutil.net_if_addrs()
    ifaces = []
    for name, addrs in net.items():
        for addr in addrs:
            if addr.family == socket.AF_INET:
                ifaces.append(f"{name}: {addr.address}")

    # Boot time
    boot = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot

    lines = [
        f"System: {uname.system} {uname.release} (Build {uname.version})",
        f"Rechner: {uname.node}",
        f"Prozessor: {cpu_phys} Kerne / {cpu_count} Logisch ({cpu_percent}% Auslastung)",
        f"RAM: {ram_used}/{ram_total} GB ({ram_percent}%)",
        f"Festplatten: {'; '.join(disks)}",
    ]
    if ifaces:
        lines.append(f"Netzwerk: {'; '.join(ifaces[:3])}")
    lines.append(f"Betriebszeit: {uptime.days}T {uptime.seconds//3600}h")
    lines.append(f"Python: {platform.python_version()}")
    return "\n".join(lines)


def process_list(filter_name: str = "", sort_by: str = "cpu") -> str:
    """List running processes, optionally filtered by name."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "create_time"]):
        try:
            info = p.info
            name = info["name"] or ""
            if filter_name and filter_name.lower() not in name.lower():
                continue
            procs.append({
                "pid": info["pid"],
                "name": name,
                "cpu": info["cpu_percent"] or 0,
                "mem": info["memory_percent"] or 0,
                "started": datetime.fromtimestamp(info["create_time"]).strftime("%H:%M") if info["create_time"] else "?",
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if sort_by == "mem":
        procs.sort(key=lambda x: x["mem"], reverse=True)
    else:
        procs.sort(key=lambda x: x["cpu"], reverse=True)

    lines = [f"{'PID':<7} {'CPU%':<6} {'MEM%':<6} {'Started':<8} Name"]
    lines.append("-" * 60)
    for p in procs[:30]:
        lines.append(f"{p['pid']:<7} {p['cpu']:<6.1f} {p['mem']:<6.1f} {p['started']:<8} {p['name']}")

    return "\n".join(lines)


def process_kill(name_or_pid: str) -> str:
    """Kill a process by name or PID."""
    if name_or_pid.isdigit():
        pid = int(name_or_pid)
        try:
            p = psutil.Process(pid)
            p.terminate()
            p.wait(timeout=3)
            return f"Prozess {pid} ({p.name()}) beendet."
        except psutil.NoSuchProcess:
            return f"PID {pid} nicht gefunden."
        except Exception as e:
            return f"Fehler: {e}"
    else:
        killed = 0
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if name_or_pid.lower() in (p.info["name"] or "").lower():
                    p.terminate()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if killed:
            return f"{killed} Prozess(e) mit '{name_or_pid}' beendet."
        else:
            return f"Kein Prozess '{name_or_pid}' gefunden."


def process_start(command: str) -> str:
    """Start a process."""
    try:
        subprocess.Popen(command, shell=True)
        return f"Gestartet: {command}"
    except Exception as e:
        return f"Fehler beim Starten: {e}"


def service_list(filter_name: str = "") -> str:
    """List Windows services."""
    services = []
    for s in psutil.win_service_iter():
        try:
            name = s.name()
            if filter_name and filter_name.lower() not in name.lower():
                continue
            status = s.status()
            display = s.display_name()
            services.append(f"  {name:<30} {status:<12} {display}")
        except Exception:
            continue

    services.sort()
    lines = [f"Letzte {len(services)} Dienste (von {len(psutil.win_service_list())}):"]
    lines.append("-" * 70)
    lines.extend(services[-25:])
    return "\n".join(lines)


def service_control(service_name: str, action: str) -> str:
    """Start, stop, or restart a Windows service."""
    valid = {"start": "start", "stop": "stop", "restart": "restart"}
    cmd = valid.get(action.lower())
    if not cmd:
        return f"Unbekannte Aktion: {action}. Nutze: start, stop, restart"

    out, err = _run(["net", cmd, service_name])
    if err and "failure" in err.lower():
        out, err = _run(["sc", cmd, service_name])

    if "successfully" in out.lower() or "successfully" in err.lower():
        return f"Service '{service_name}' {action} erfolgreich."
    return f"Service '{service_name}' {action}: {out[:200] or err[:200]}"


def registry_read(key_path: str) -> str:
    """Read a Windows Registry value."""
    if not winreg:
        return "winreg nicht verfügbar (nicht Windows)."
    try:
        # Parse "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\value_name"
        parts = key_path.replace("/", "\\").split("\\")
        hive_name = parts[0]
        value_name = parts[-1]
        subkey = "\\".join(parts[1:-1])
        key = _get_registry_key(hive_name, subkey)
        value, reg_type = winreg.QueryValueEx(key, value_name)
        winreg.CloseKey(key)
        return f"{key_path} = {value}"
    except FileNotFoundError:
        return f"Registrierungsschlüssel nicht gefunden: {key_path}"
    except Exception as e:
        return f"Registry-Fehler: {e}"


def registry_write(key_path: str, value: str, type_hint: str = "SZ") -> str:
    """Write a Windows Registry value."""
    if not winreg:
        return "winreg nicht verfügbar."
    try:
        parts = key_path.replace("/", "\\").split("\\")
        hive_name = parts[0]
        value_name = parts[-1]
        subkey = "\\".join(parts[1:-1])

        hives = {
            "HKCU": winreg.HKEY_CURRENT_USER,
            "HKLM": winreg.HKEY_LOCAL_MACHINE,
        }
        hive = hives.get(hive_name.upper())
        if not hive:
            return f"Unbekannte Hive: {hive_name}"

        type_map = {
            "SZ": winreg.REG_SZ,
            "DWORD": winreg.REG_DWORD,
            "QWORD": winreg.REG_QWORD,
            "BINARY": winreg.REG_BINARY,
            "EXPAND_SZ": winreg.REG_EXPAND_SZ,
            "MULTI_SZ": winreg.REG_MULTI_SZ,
        }
        reg_type = type_map.get(type_hint.upper(), winreg.REG_SZ)

        if reg_type in (winreg.REG_DWORD, winreg.REG_QWORD):
            typed_value = int(value)
        elif reg_type == winreg.REG_BINARY:
            typed_value = bytes.fromhex(value)
        elif reg_type == winreg.REG_MULTI_SZ:
            typed_value = value.split(",")
        else:
            typed_value = value

        key = winreg.CreateKey(hive, subkey)
        winreg.SetValueEx(key, value_name, 0, reg_type, typed_value)
        winreg.CloseKey(key)
        return f"Registry geschrieben: {key_path} = {value}"
    except Exception as e:
        return f"Registry-Fehler: {e}"


def power_plan(action: str = "list", plan_name: str = "") -> str:
    """List, set, or get the active power plan."""
    if action == "list":
        out, _ = _run(["powercfg", "/list"])
        if not out:
            return "Keine Energiepläne gefunden."
        lines = [line.strip() for line in out.split("\n") if line.strip()]
        active, _ = _run(["powercfg", "/getactivescheme"])
        result = "Energiepläne:\n" + "\n".join(lines)
        if active:
            result += f"\n\nAktiv: {active.strip()}"
        return result

    elif action == "set":
        if not plan_name:
            return "Bitte einen Plannamen angeben (z.B. 'High performance', 'Balanced', 'Power saver')."
        out, _ = _run(["powercfg", "/list"])
        for line in out.split("\n"):
            if plan_name.lower() in line.lower():
                guid = re.search(r"([a-f0-9\-]{36})", line)
                if guid:
                    _run(["powercfg", "/s", guid.group(1)])
                    return f"Energieplan '{plan_name}' aktiviert."
        return f"Energieplan '{plan_name}' nicht gefunden."

    return f"Unbekannte Aktion: {action}. Nutze: list, set"


def power_setting(subcategory: str = "screen", value_minutes: int = None) -> str:
    """Get or set power settings (screen timeout, sleep, etc.)."""
    guid_map = {
        "screen":   "7516b95f-f776-4464-8c53-06167f40cc99",
        "sleep":    "238c9fa8-0aad-41ed-83f4-97be242c8f20",
        "hibernate": "9d7815a6-7ee4-497e-8888-515a05f02364",
    }
    subguid = guid_map.get(subcategory.lower())
    if not subguid:
        return f"Unbekannte Kategorie: {subcategory}. Nutze: screen, sleep, hibernate"

    power_settings = subcategory.replace("_", " ").title()

    if value_minutes is not None:
        seconds = value_minutes * 60
        for setting in ["AC", "DC"]:
            _run(["powercfg", "/change", subcategory.lower(), f"/{setting.lower()}", str(seconds)])
        return f"'{power_settings}' Timeout auf {value_minutes} Minuten gesetzt."

    out, _ = _run(["powercfg", "/query", subguid])
    return f"Aktuelle '{power_settings}' Einstellungen:\n{out[:500]}"


def wallpaper_set(image_path: str, style: str = "fill") -> str:
    """Set desktop wallpaper from a file path."""
    expanded = os.path.expandvars(image_path)
    path = Path(expanded)
    if not path.exists():
        return f"Bild nicht gefunden: {expanded}"

    abs_path = str(path.resolve())
    style_map = {
        "fill": "10", "fit": "6", "stretch": "2",
        "tile": "0", "center": "0", "span": "22",
    }
    style_val = style_map.get(style.lower(), "10")

    try:
        ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path, 3)
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, style_val)
        winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")
        winreg.CloseKey(key)
        return f"Wallpaper gesetzt: {path.name} ({style})"
    except Exception as e:
        return f"Wallpaper-Fehler: {e}"


def env_var(action: str, name: str, value: str = "", scope: str = "user") -> str:
    """Get, set, or delete an environment variable."""
    try:
        import ctypes.wintypes as wintypes
    except Exception:
        return "Nur unter Windows verfügbar."

    if action == "get":
        val = os.environ.get(name, "")
        if val:
            return f"{name} = {val}"
        return f"Umgebungsvariable '{name}' nicht gesetzt."

    elif action == "set":
        if not value:
            return "Bitte einen Wert angeben."
        target = "USER" if scope.lower() == "user" else "MACHINE"
        _run(["setx", name, value])
        os.environ[name] = value
        return f"Umgebungsvariable '{name}' = '{value}' gesetzt ({target})."

    elif action == "delete":
        _run(["reg", "delete",
              f"HKCU\\Environment" if scope.lower() == "user" else "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
              "/v", name, "/f"])
        os.environ.pop(name, None)
        return f"Umgebungsvariable '{name}' gelöscht."

    return f"Unbekannte Aktion: {action}. Nutze: get, set, delete"


def startup_add(action: str, name: str = "", command: str = "") -> str:
    """Manage startup programs (list, add, remove)."""
    startup_folder = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

    if action == "list":
        items = []
        # Current user startup folder
        if startup_folder.exists():
            for f in startup_folder.iterdir():
                items.append(f.name)
        # Registry
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run")
            i = 0
            while True:
                try:
                    val_name, val_data, _ = winreg.EnumValue(key, i)
                    items.append(f"{val_name} ({val_data[:60]})")
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except Exception:
            pass
        if not items:
            return "Keine Autostart-Einträge gefunden."
        return "Autostart-Programme:\n" + "\n".join(f"  - {item}" for item in items)

    elif action == "add":
        if not name or not command:
            return "Bitte Name und Ausführungspfad angeben."
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)
            return f"'{name}' zum Autostart hinzugefügt: {command}"
        except Exception as e:
            return f"Fehler: {e}"

    elif action == "remove":
        if not name:
            return "Bitte den Namen des Autostart-Eintrags angeben."
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, name)
            winreg.CloseKey(key)
            return f"'{name}' aus Autostart entfernt."
        except FileNotFoundError:
            return f"'{name}' nicht gefunden."
        except Exception as e:
            return f"Fehler: {e}"

    return f"Unbekannte Aktion: {action}. Nutze: list, add, remove"


def disk_usage(path: str = "") -> str:
    """Show disk space usage."""
    if path:
        target = Path(path)
        if target.exists():
            usage = psutil.disk_usage(str(target.anchor) if target.is_absolute() else str(target))
            return (f"{target}: {usage.used//1024**3}GB / {usage.total//1024**3}GB "
                    f"({usage.percent}% belegt, {usage.free//1024**3}GB frei)")
        return f"Pfad nicht gefunden: {path}"
    else:
        lines = ["Festplatten:"]
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                lines.append(f"  {part.device} ({part.mountpoint}): "
                             f"{usage.used//1024**3}GB/{usage.total//1024**3}GB "
                             f"{usage.percent}% belegt, {usage.free//1024**3}GB frei")
            except Exception:
                lines.append(f"  {part.device} ({part.mountpoint}): ?")
        return "\n".join(lines)


def network_info() -> str:
    """Get network configuration."""
    hostname = socket.gethostname()
    lines = [f"Hostname: {hostname}"]

    # IP addresses
    net = psutil.net_if_addrs()
    for name, addrs in net.items():
        for addr in addrs:
            if addr.family == socket.AF_INET:
                lines.append(f"  {name}: IP {addr.address}")
            elif addr.family == socket.AF_INET6:
                lines.append(f"  {name}: IPv6 {addr.address.split('%')[0]}")
            elif hasattr(socket, 'AF_LINK') and addr.family == socket.AF_LINK:
                lines.append(f"  {name}: MAC {addr.address}")

    # Default gateway
    out, _ = _run(["ipconfig"])
    for line in out.split("\n"):
        if "Standardgateway" in line and ":" in line:
            gw = line.split(":")[-1].strip()
            if gw and gw != ":":
                lines.append(f"  Gateway: {gw}")

    # DNS
    dns_out, _ = _run(["nslookup", "localhost"])
    for line in dns_out.split("\n"):
        if "Address:" in line and ":" in line.split(":")[-1].strip():
            dns = line.split(":")[-1].strip()
            if dns and dns != "::1" and dns != "127.0.0.1":
                lines.append(f"  DNS: {dns}")
                break

    return "\n".join(lines)


def display_settings(action: str = "info", value: str = "") -> str:
    """Get/set display settings: resolution, brightness, theme."""
    if action == "info":
        lines = ["Bildschirme:"]
        try:
            from screeninfo import get_monitors
            for m in get_monitors():
                lines.append(f"  {m.name}: {m.width}x{m.height} @ {m.x},{m.y} ({m.is_primary=})")
        except ImportError:
            out, _ = _run(["powershell",
                "Get-WmiObject -Class Win32_VideoController | Select-Object Name, CurrentHorizontalResolution, CurrentVerticalResolution | Format-List"])
            if out:
                lines.append(out[:300])
        return "\n".join(lines)

    elif action == "resolution":
        if not value:
            out, _ = _run(["powershell", "(Get-WmiObject -Class Win32_VideoController).CurrentHorizontalResolution.ToString()+'x'+(Get-WmiObject -Class Win32_VideoController).CurrentVerticalResolution.ToString()"])
            return f"Aktuelle Auflösung: {out.strip()}"
        if "x" in value:
            try:
                w, h = value.lower().split("x")
                script = (
                    f'Add-Type @"\nusing System;\nusing System.Runtime.InteropServices;\n'
                    f'public class ResChanger {{\n[DllImport("user32.dll")]\n'
                    f'public static extern int ChangeDisplaySettings(ref DEVMODE devMode,int flags);\n}}\n'
                    f'"@\n$w=[int]{w};$h=[int]{h}\n'
                    f'[ResChanger]::ChangeDisplaySettings(...)'
                )
                # Simple approach via QRes or PowerShell
                out, _ = _run(["powershell",
                    f"(Get-WmiObject -Class Win32_VideoController).SetCurrentResolution({w},{h})"])
                return f"Auflösung auf {value} gesetzt." if "returnvalue" not in out.lower() else f"Fehler: {out}"
            except Exception as e:
                return f"Fehler: {e}"
        return f"Format ungültig: {value}. Nutze z.B. '1920x1080'"

    elif action == "theme":
        if "dark" in value.lower():
            _run(["reg", "add", "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize",
                  "/v", "AppsUseLightTheme", "/t", "REG_DWORD", "/d", "0", "/f"])
            _run(["reg", "add", "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize",
                  "/v", "SystemUsesLightTheme", "/t", "REG_DWORD", "/d", "0", "/f"])
            return "Dark Mode aktiviert."
        elif "light" in value.lower():
            _run(["reg", "add", "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize",
                  "/v", "AppsUseLightTheme", "/t", "REG_DWORD", "/d", "1", "/f"])
            _run(["reg", "add", "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize",
                  "/v", "SystemUsesLightTheme", "/t", "REG_DWORD", "/d", "1", "/f"])
            return "Light Mode aktiviert."
        return f"Unbekanntes Theme: {value}. Nutze: dark, light"

    return f"Unbekannte Aktion: {action}. Nutze: info, resolution, theme"


def system_integration_action(parameters: dict, player=None, speak=None) -> str:
    """Main entry point for system integration."""
    action = (parameters or {}).get("action", "info").strip().lower()
    target = (parameters or {}).get("target", "")
    value = (parameters or {}).get("value", "")
    mode = (parameters or {}).get("mode", "")

    if player:
        player.write_log(f"[SysIntegration] action={action} target={target}")

    action_map = {
        "info": lambda: system_info(),
        "process_list": lambda: process_list(target, mode),
        "process_kill": lambda: process_kill(target),
        "process_start": lambda: process_start(target),
        "service_list": lambda: service_list(target),
        "service_control": lambda: service_control(target, value or "restart"),
        "registry_read": lambda: registry_read(target),
        "registry_write": lambda: registry_write(target, value, mode),
        "power_plan": lambda: power_plan(target, value),
        "power_setting": lambda: power_setting(target, int(value) if value.isdigit() else None),
        "wallpaper": lambda: wallpaper_set(target, value or "fill"),
        "env_var": lambda: env_var(target, value, mode, "user"),
        "startup": lambda: startup_add(target, value, mode),
        "disk": lambda: disk_usage(target),
        "network": lambda: network_info(),
        "display": lambda: display_settings(target, value),
    }

    handler = action_map.get(action)
    if not handler:
        # Map short names
        short = {
            "system_info": "info",
            "processes": "process_list",
            "ps": "process_list",
            "kill": "process_kill",
            "run": "process_start",
            "services": "service_list",
            "service": "service_control",
            "reg": "registry_read",
            "reg_write": "registry_write",
            "power": "power_plan",
            "wallpaper_set": "wallpaper",
            "disk_usage": "disk",
            "network_info": "network",
        }
        mapped = short.get(action)
        handler = action_map.get(mapped) if mapped else None

    if not handler:
        return (
            f"Unbekannte Aktion: {action}.\n\n"
            f"Verfügbare Aktionen:\n"
            f"  info             - Systeminformationen (CPU, RAM, OS)\n"
            f"  process_list     - Laufende Prozesse anzeigen\n"
            f"  process_kill     - Prozess beenden\n"
            f"  process_start    - Programm starten\n"
            f"  service_list     - Windows-Dienste anzeigen\n"
            f"  service_control  - Dienst starten/stoppen/neustarten\n"
            f"  registry_read    - Registrierung lesen\n"
            f"  registry_write   - Registrierung schreiben\n"
            f"  power_plan       - Energieplan verwalten\n"
            f"  power_setting    - Bildschirm/Schlaf-Timeout\n"
            f"  wallpaper        - Desktop-Hintergrund ändern\n"
            f"  env_var          - Umgebungsvariablen\n"
            f"  startup          - Autostart verwalten\n"
            f"  disk             - Festplattenbelegung\n"
            f"  network          - Netzwerkkonfiguration\n"
            f"  display          - Bildschirm-Einstellungen"
        )

    try:
        return handler()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Fehler: {e}"


from datetime import datetime
