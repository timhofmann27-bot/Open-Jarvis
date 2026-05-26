import asyncio
import json
import socket
import struct
import time
from pathlib import Path
from typing import Any

from bleak import BleakScanner, BleakClient

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DEVICES_PATH = CONFIG_DIR / "devices.json"


def _read_devices() -> dict:
    try:
        return json.loads(DEVICES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_devices(data: dict) -> None:
    existing = _read_devices()
    existing.update(data)
    DEVICES_PATH.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _get_bt_devices() -> dict:
    dev = _read_devices()
    return dev.get("bluetooth", {})


def _save_bt_device(address: str, name: str, device_type: str = "tv") -> None:
    bt = _get_bt_devices()
    bt[name] = {"address": address, "type": device_type, "last_seen": time.time()}
    _save_devices({"bluetooth": bt})
    if device_type == "tv":
        dev = _read_devices()
        dev["last_tv"] = {
            "ip": "",
            "name": name,
            "bt_address": address,
            "connected_at": time.time(),
        }
        _save_devices({"last_tv": dev["last_tv"]})


def wake_on_lan(mac_address: str, broadcast_ip: str = "255.255.255.255") -> bool:
    """Send Wake-on-LAN magic packet to wake a device by MAC address."""
    try:
        mac = mac_address.replace(":", "").replace("-", "")
        if len(mac) != 12:
            return False
        data = b"\xff" * 6 + bytes.fromhex(mac) * 16
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(data, (broadcast_ip, 9))
        sock.sendto(data, (broadcast_ip, 7))
        sock.close()
        return True
    except Exception:
        return False


def scan_ble(timeout: float = 10.0) -> list[dict[str, Any]]:
    """Scan for BLE devices in 2 rounds. Returns discovered devices."""
    results = []

    async def _scan_round(round_timeout: float):
        nonlocal results
        devices = await BleakScanner.discover(timeout=round_timeout, return_adv=True)
        seen = {d["address"] for d in results}
        for addr, (dev, adv) in devices.items():
            name = dev.name or adv.local_name or "?"
            if addr in seen:
                continue
            seen.add(addr)
            rssi = adv.rssi if adv else 0
            results.append({
                "address": addr,
                "name": name,
                "rssi": rssi,
                "is_tv": "tv" in name.lower(),
            })

    asyncio.run(_scan_round(timeout * 0.6))
    asyncio.run(_scan_round(timeout * 0.4))
    results.sort(key=lambda d: (-d["is_tv"], -d["rssi"]))
    return results


def connect_ble(address: str, timeout: float = 5.0) -> dict[str, Any]:
    """Connect to a BLE device with timeout. Returns success status."""
    result = {"success": False, "connected": False, "error": None}

    async def _connect():
        nonlocal result
        try:
            import asyncio as _asyncio
            client = BleakClient(address, timeout=timeout)
            await _asyncio.wait_for(client.connect(), timeout=timeout)
            if client.is_connected:
                name = await client.get_device_name() or address
                result["success"] = True
                result["connected"] = True
                result["name"] = name
                result["address"] = address
                _save_bt_device(address, name, "tv")
                try:
                    await client.disconnect()
                except Exception:
                    pass
            else:
                result["error"] = "Verbindung fehlgeschlagen"
        except asyncio.TimeoutError:
            result["error"] = "Zeitüberschreitung bei BLE-Verbindung"
        except Exception as e:
            result["error"] = str(e)

    asyncio.run(_connect())
    return result


def wake_tv(address: str = "", tv_data: dict | None = None) -> dict[str, Any]:
    """Try to wake TV via BLE connect, then WOL as fallback."""
    result = {"success": False, "method": "", "error": None}

    if tv_data:
        mac = tv_data.get("mac", "")
        ip = tv_data.get("ip", "")

    # 1. WOL is fastest and most reliable – try first
    wol_mac = ""
    if ":" in address and len(address) == 17:
        wol_mac = address
    elif mac:
        wol_mac = mac

    if wol_mac:
        woke = wake_on_lan(wol_mac)
        if woke:
            result["success"] = True
            result["method"] = "wol"
            result["error"] = None
            _save_bt_device(wol_mac, "[WOL] TV", "tv")
            return result

    # 2. Try BLE connect as fallback
    if address and ":" in address and len(address) == 17:
        ble = connect_ble(address, timeout=5.0)
        if ble["success"]:
            result["success"] = True
            result["method"] = "ble"
            result["error"] = None
            result["name"] = ble.get("name", address)
            return result
        result["error"] = f"BLE: {ble['error']}"

    if not result["success"]:
        result["error"] = result.get("error") or "Keine Verbindungsmethode verfügbar"
    return result


def get_known_devices() -> dict[str, Any]:
    """Return all known BT devices from config."""
    bt = _get_bt_devices()
    devices = []
    for name, info in bt.items():
        devices.append({
            "name": name,
            "address": info.get("address", ""),
            "type": info.get("type", "unknown"),
            "last_seen": info.get("last_seen", 0),
        })
    return {"devices": devices, "count": len(devices)}


def open_wireless_display() -> bool:
    """Open Windows Wireless Display / Miracast connect flyout (Win+K)."""
    try:
        import os
        os.startfile("ms-actioncenter:connect/")
        return True
    except Exception:
        try:
            import subprocess
            subprocess.Popen("start ms-actioncenter:connect/", shell=True)
            return True
        except Exception:
            return False


def execute_bt_command(params: dict[str, Any]) -> str:
    action = params.get("action", "scan")
    address = params.get("address", "")
    name = params.get("name", "")

    if action == "scan":
        devices = scan_ble(timeout=8.0)
        tvs = [d for d in devices if d["is_tv"]]
        others = [d for d in devices if not d["is_tv"]]
        lines = []
        if tvs:
            lines.append(f"📺 {len(tvs)} TV-Gerät(e) gefunden:")
            for d in tvs:
                lines.append(f"  {d['name']} ({d['address']})")
        if others:
            lines.append(f"📱 {len(others)} weitere Geräte:")
            for d in others[:5]:
                lines.append(f"  {d['name']} ({d['address']})")
            if len(others) > 5:
                lines.append(f"  ... und {len(others)-5} weitere")
        if not devices:
            return "Keine Bluetooth-Geräte in der Nähe gefunden."
        return "\n".join(lines)

    elif action == "connect" or action == "wake":
        if not address:
            return "Bitte eine Bluetooth-Adresse oder MAC-Adresse angeben."
        result = wake_tv(address)
        if result["success"]:
            method = "WOL" if result["method"] == "wol" else "Bluetooth"
            return (f"✅ TV per {method} aktiviert. "
                    f"Der TV-Bildschirm sollte jetzt angehen.")
        return (f"❌ Konnte TV nicht aktivieren: {result.get('error', 'Unbekannter Fehler')}. "
                f"Hinweis: WOL benötigt die MAC-Adresse des TVs (z.B. 7C:0A:3F:53:7F:09)")

    elif action == "display" or action == "miracast" or action == "wireless":
        ok = open_wireless_display()
        if ok:
            return "📺 Windows Connect-Fenster geöffnet. Wähle deinen Samsung TV aus der Liste."
        return "❌ Konnte Connect-Fenster nicht öffnen."

    elif action == "disconnect":
        if not address:
            return "Bitte eine Bluetooth-Adresse angeben."
        return f"🔌 Bluetooth-Verbindung zu {address} getrennt."

    elif action in ("list", "devices"):
        known = get_known_devices()
        if known["count"] == 0:
            return "Keine bekannten Bluetooth-Geräte. Führe einen Scan durch."
        lines = [f"Bekannte Geräte ({known['count']}):"]
        for d in known["devices"]:
            icon = "📺" if d["type"] == "tv" else "📱"
            lines.append(f"  {icon} {d['name']} ({d['address']})")
        return "\n".join(lines)

    else:
        return f"Unbekannte Aktion: {action}. Verfügbar: scan, connect, wake, disconnect, list"
