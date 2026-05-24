import random
import subprocess
import sys


def _handle(params: dict) -> str:
    cmd = (params.get("_plugin_cmd") or "").strip().lower()

    if cmd == "ping":
        return "Pong! Plugin ist aktiv."

    if cmd in ("würfel", "wuerfel", "roll", "dice"):
        sides = int(params.get("sides", 6))
        result = random.randint(1, sides)
        return f"Du hast eine {result} gewuerfelt (W{sides})."

    if cmd == "ip":
        try:
            r = subprocess.run(["curl", "-s", "ifconfig.me"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                return f"Deine oeffentliche IP: {r.stdout.strip()}"
        except Exception:
            pass
        try:
            import requests
            r = requests.get("https://api.ipify.org", timeout=5)
            return f"Deine oeffentliche IP: {r.text.strip()}"
        except Exception:
            return "Konnte IP nicht ermitteln."

    if cmd in ("help", "hilfe"):
        return (
            "Verfuegbare Befehle: ping, dice [sides=N], ip, help. "
            "Beispiel: 'plugin example dice' oder 'plugin example\\n_plugin_cmd: dice\\nsides: 20'"
        )

    return f"Unbekannter Befehl: {cmd}. Sag 'help' fuer eine Liste."


plugin_info = {
    "name": "example_plugin",
    "description": "Beispiel-Plugin mit nuetzlichen Hilfsfunktionen: Wuerfel, IP-Abfrage, Ping.",
    "cmd_description": "Befehl: ping, dice, ip, help",
    "parameters": {
        "sides": {"type": "INTEGER", "description": "Anzahl der Seiten fuer dice (default: 6)"},
    },
    "required": [],
    "handler": _handle,
}
