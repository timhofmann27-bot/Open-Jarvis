import platform
import socket
import subprocess
import time
from urllib.parse import urlparse

import requests


def _normalize_target(target: str) -> tuple[str, str]:
    target = (target or "").strip()
    if not target:
        return "google.com", "https://clients3.google.com/generate_204"

    parsed = urlparse(target)
    if parsed.scheme and parsed.netloc:
        return parsed.netloc, target
    if target.startswith("http://") or target.startswith("https://"):
        return target.replace("http://", "").replace("https://", ""), target

    return target, f"https://{target}"


def _dns_check(host: str) -> str:
    try:
        ip = socket.gethostbyname(host)
        return f"DNS OK: {host} resolves to {ip}."
    except Exception as e:
        return f"DNS failed for {host}: {e}"


def _http_check(url: str) -> str:
    try:
        if not urlparse(url).scheme:
            url = f"https://{url}"
        start = time.time()
        response = requests.get(url, timeout=8, headers={
            "User-Agent": "Mozilla/5.0 (compatible; MARK-XXV/1.0)"
        })
        latency = round(time.time() - start, 3)
        return (
            f"HTTP OK: {response.status_code} {response.reason} "
            f"for {url} ({latency}s)."
        )
    except Exception as e:
        return f"HTTP check failed for {url}: {e}"


def _ping_check(host: str) -> str:
    system = platform.system()
    if system == "Windows":
        cmd = ["ping", "-n", "1", host]
    else:
        cmd = ["ping", "-c", "1", host]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        if result.returncode == 0:
            return f"Ping OK: {host}."
        return f"Ping failed: {host}. Output: {result.stdout.strip() or result.stderr.strip()}"
    except Exception as e:
        return f"Ping check failed for {host}: {e}"


def _internet_probe() -> str:
    try:
        response = requests.get("https://clients3.google.com/generate_204", timeout=6)
        if response.status_code == 204:
            return "Internet probe succeeded: outbound HTTP connectivity works."
        return f"Internet probe returned status {response.status_code}."
    except Exception as e:
        return f"Internet probe failed: {e}"


def network_status(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    target = params.get("target", "").strip()
    check = params.get("check", "all").strip().lower()
    host, url = _normalize_target(target)

    if player:
        player.write_log(f"[NetworkStatus] target={target or 'default'} check={check}")

    checks = []
    if check in ("all", "dns"):
        checks.append(_dns_check(host))
    if check in ("all", "ping"):
        checks.append(_ping_check(host))
    if check in ("all", "http"):
        checks.append(_http_check(url))
    if check in ("all", "probe"):
        checks.append(_internet_probe())

    if not checks:
        return (
            "Available checks: all, dns, ping, http, probe. "
            "Provide a 'check' parameter and optionally a 'target'."
        )

    return "\n".join(checks)
