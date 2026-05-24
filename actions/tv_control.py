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
DEFAULT_PATH = "/mirror"
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
    server_message = "Der TV-Mirror ist bereit."

    if player:
        player.write_log(f"[TV] Trying to connect TV at {target_url}")

    devices = discover_tvs(timeout=3.0)
    if not devices:
        return f"{server_message} Ich konnte kein Smart-TV automatisch finden. Öffne diese URL auf dem Fernseher: {target_url}."

    best = _best_device(devices)
    ip = best["ip"]
    name = best.get("friendly_name", "Smart-TV")
    if player:
        player.write_log(f"[TV] Gefundenes Gerät: {name} ({ip})")

    if _attempt_dial_launch(ip, target_url):
        return f"{server_message} Ich habe {name} im WLAN gefunden und den TV-Mirror an {target_url} gesendet."

    return f"{server_message} Ich habe {name} gefunden, konnte ihn aber nicht automatisch aufrufen. Öffne {target_url} manuell auf dem TV."