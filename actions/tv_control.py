import re
import socket
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

import requests

from remote_server import get_local_ip


SSDP_ADDRESS = ("239.255.255.250", 1900)
SSDP_DISCOVER = "M-SEARCH * HTTP/1.1\r\nHost: 239.255.255.250:1900\r\nMan: \"ssdp:discover\"\r\nMX: 2\r\nST: urn:dial-multiscreen-org:service:dial:1\r\n\r\n"
DIAL_PORT = 8008
DEFAULT_PATH = "/jarvis"
DEFAULT_PORT = 8080


def _parse_ssdp_response(data: bytes) -> dict[str, str]:
    headers = {}
    try:
        text = data.decode("utf-8", errors="ignore")
        lines = text.split("\r\n")
        for line in lines[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    except Exception:
        pass
    return headers


def _fetch_device_description(location: str) -> dict[str, str] | None:
    try:
        response = requests.get(location, timeout=3)
        if response.status_code != 200:
            return None
        root = ET.fromstring(response.text)
        ns = {"upnp": "urn:schemas-upnp-org:device-1-0"}
        fn = root.find(".//upnp:friendlyName", ns)
        model = root.find(".//upnp:modelName", ns)
        return {
            "friendly_name": fn.text if fn is not None else "unknown",
            "model": model.text if model is not None else "unknown",
        }
    except Exception:
        return None


def discover_tvs(timeout: float = 3.0) -> list[dict[str, Any]]:
    devices: dict[str, dict[str, Any]] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(timeout)

    try:
        sock.sendto(SSDP_DISCOVER.encode("utf-8"), SSDP_ADDRESS)
        start = time.time()
        while time.time() - start < timeout:
            try:
                data, addr = sock.recvfrom(2048)
            except socket.timeout:
                break
            headers = _parse_ssdp_response(data)
            location = headers.get("location")
            if not location:
                continue
            if location in devices:
                continue
            descr = _fetch_device_description(location)
            device_ip = addr[0]
            devices[location] = {
                "ip": device_ip,
                "location": location,
                "server": headers.get("server", ""),
                "st": headers.get("st", ""),
                "friendly_name": descr["friendly_name"] if descr else "unknown",
                "model": descr["model"] if descr else "unknown",
            }
    finally:
        sock.close()

    return list(devices.values())


def _attempt_dial_launch(host: str, target_url: str) -> bool:
    candidates = [
        "Chrome",
        "com.android.chrome",
        "org.chromium.chrome",
        "Browser",
        "com.android.browser"
    ]
    for app in candidates:
        try:
            url = f"http://{host}:{DIAL_PORT}/apps/{urllib.parse.quote(app)}"
            payload = f"v={urllib.parse.quote(target_url, safe='')}"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "JarvisTV/1.0"
            }
            response = requests.post(url, data=payload, headers=headers, timeout=5)
            if response.status_code in (200, 201, 202):
                return True
        except Exception:
            continue
    return False


def _best_device(devices: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not devices:
        return None
    for device in devices:
        name = device.get("friendly_name", "").lower()
        if "android" in name or "google" in name or "chromecast" in name or "tv" in name:
            return device
    return devices[0]


def connect_tv(parameters: dict[str, Any], player: Any = None) -> str:
    target_url = f"http://{get_local_ip()}:{DEFAULT_PORT}{DEFAULT_PATH}"

    # 1. Open Windows Wireless Display dialog (Win+K)
    ws_ok = False
    try:
        from actions.bt_control import open_wireless_display
        ws_ok = open_wireless_display()
    except Exception:
        pass

    # 2. Open the 3D Jarvis page in browser
    import webbrowser
    webbrowser.open(target_url)

    if ws_ok:
        msg = "Ich habe die Drahtlosbildschirm-Verbindung geöffnet (Win+K). Verbinde den TV, dann siehst du den 3D Iron Man."
    else:
        msg = f"Öffne die Drahtlosbildschirm-Verbindung mit Win+K und navigiere zu {target_url}."

    if player:
        player.write_log(f"[TV] {msg}")

    return msg
