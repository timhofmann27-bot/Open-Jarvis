import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "smart_home.json"


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def _request(method: str, url: str, **kwargs) -> dict | None:
    import requests
    try:
        r = requests.request(method, url, timeout=5, **kwargs)
        r.raise_for_status()
        return r.json() if r.text else {}
    except Exception as e:
        logger.error(f"SmartHome {method} {url}: {e}")
        return None


def smart_home(
    parameters: dict,
    player=None,
    speak=None
) -> str:
    platform = (parameters.get("platform") or "").lower()
    device   = (parameters.get("device") or "").strip()
    action   = (parameters.get("action") or "").lower()
    value    = parameters.get("value", "")

    if not platform:
        return "Sir, please specify a platform: hue, shelly, or homeassistant."

    config = _load_config()

    if platform == "hue":
        return _hue_action(device, action, value, config, player, speak)
    elif platform == "shelly":
        return _shelly_action(device, action, value, config, player, speak)
    elif platform == "homeassistant":
        return _homeassistant_action(device, action, value, config, player, speak)
    else:
        return f"Sir, unknown platform '{platform}'. Supported: hue, shelly, homeassistant."


def _hue_action(device: str, action: str, value: str, config: dict, player, speak) -> str:
    bridge_ip = config.get("hue", {}).get("bridge_ip")
    api_key   = config.get("hue", {}).get("api_key")

    if not bridge_ip or not api_key:
        return "Sir, Philips Hue is not configured. Please set bridge_ip and api_key in config/smart_home.json."

    if action == "discover":
        return _hue_discover(bridge_ip, api_key, player, speak)
    elif action == "list":
        return _hue_list(bridge_ip, api_key, player, speak)
    elif device and action in ("on", "off", "toggle"):
        return _hue_set_power(bridge_ip, api_key, device, action, player, speak)
    elif device and action == "brightness":
        return _hue_set_brightness(bridge_ip, api_key, device, value, player, speak)
    elif device and action == "color":
        return _hue_set_color(bridge_ip, api_key, device, value, player, speak)
    else:
        return f"Sir, I don't understand the hue command: {action} {device}"


def _hue_discover(bridge_ip: str, api_key: str, player, speak) -> str:
    data = _request("GET", f"http://{bridge_ip}/api/{api_key}/lights")
    if data is None:
        return "Sir, I could not reach the Hue bridge."
    lines = [f"{kid}: {v.get('name', 'Unknown')}" for kid, v in data.items()]
    msg = f"Found {len(lines)} Hue lights. " + "; ".join(lines)
    _log(msg, player)
    return msg


def _hue_list(bridge_ip: str, api_key: str, player, speak) -> str:
    return _hue_discover(bridge_ip, api_key, player, speak)


def _hue_set_power(bridge_ip: str, api_key: str, device: str, action: str, player, speak) -> str:
    light_id = _hue_find_id(bridge_ip, api_key, device)
    if light_id is None:
        return f"Sir, I could not find a Hue light named '{device}'."
    on = action == "on"
    data = _request("PUT", f"http://{bridge_ip}/api/{api_key}/lights/{light_id}/state",
                     json={"on": on})
    if data is None:
        return f"Sir, failed to turn {action} the light."
    state = "on" if on else "off"
    msg = f"Turned {device} {state}, sir."
    _log(msg, player)
    return msg


def _hue_set_brightness(bridge_ip: str, api_key: str, device: str, value: str, player, speak) -> str:
    light_id = _hue_find_id(bridge_ip, api_key, device)
    if light_id is None:
        return f"Sir, I could not find a Hue light named '{device}'."
    try:
        bri = max(1, min(254, int(value)))
    except ValueError:
        bri = 254
    data = _request("PUT", f"http://{bridge_ip}/api/{api_key}/lights/{light_id}/state",
                     json={"on": True, "bri": bri})
    if data is None:
        return f"Sir, failed to set brightness."
    pct = round(bri / 254 * 100)
    msg = f"Set {device} brightness to {pct}%, sir."
    _log(msg, player)
    return msg


def _hue_set_color(bridge_ip: str, api_key: str, device: str, color: str, player, speak) -> str:
    light_id = _hue_find_id(bridge_ip, api_key, device)
    if light_id is None:
        return f"Sir, I could not find a Hue light named '{device}'."
    xy = _color_name_to_xy(color)
    if xy is None:
        return f"Sir, unknown color '{color}'."
    data = _request("PUT", f"http://{bridge_ip}/api/{api_key}/lights/{light_id}/state",
                     json={"on": True, "xy": xy})
    if data is None:
        return f"Sir, failed to set color."
    msg = f"Set {device} to {color}, sir."
    _log(msg, player)
    return msg


_COLOR_MAP = {
    "red": (0.674, 0.322), "green": (0.409, 0.518), "blue": (0.167, 0.040),
    "white": (0.323, 0.329), "warm white": (0.459, 0.411), "cold white": (0.253, 0.268),
    "yellow": (0.443, 0.512), "orange": (0.569, 0.411), "purple": (0.375, 0.148),
    "pink": (0.462, 0.234), "cyan": (0.157, 0.350),
}


def _color_name_to_xy(name: str) -> tuple | None:
    name = name.lower().strip()
    if name in _COLOR_MAP:
        return _COLOR_MAP[name]
    return None


def _hue_find_id(bridge_ip: str, api_key: str, name: str) -> str | None:
    data = _request("GET", f"http://{bridge_ip}/api/{api_key}/lights")
    if data is None:
        return None
    nl = name.lower()
    for lid, info in data.items():
        if nl in info.get("name", "").lower():
            return lid
    for lid, info in data.items():
        if nl in lid:
            return lid
    return None


def _shelly_action(device: str, action: str, value: str, config: dict, player, speak) -> str:
    devices = config.get("shelly", {})
    ip = devices.get(device)
    if not ip:
        available = ", ".join(devices.keys()) if devices else "none configured"
        return f"Sir, Shelly device '{device}' not found. Configured: {available}"

    if action == "on":
        return _shelly_set(ip, "on", player)
    elif action == "off":
        return _shelly_set(ip, "off", player)
    elif action == "status":
        return _shelly_status(ip, device, player)
    else:
        return f"Sir, unknown Shelly action '{action}'."


def _shelly_set(ip: str, state: str, player) -> str:
    data = _request("GET", f"http://{ip}/relay/0?turn={state}")
    if data is None:
        return f"Sir, could not reach Shelly at {ip}."
    msg = f"Shelly turned {state}, sir."
    _log(msg, player)
    return msg


def _shelly_status(ip: str, name: str, player) -> str:
    data = _request("GET", f"http://{ip}/status")
    if data is None:
        return f"Sir, could not reach Shelly at {ip}."
    relay = data.get("relays", [{}])[0]
    state = "on" if relay.get("ison") else "off"
    power = data.get("meters", [{}])[0].get("power", 0)
    msg = f"{name} is {state}, drawing {power:.0f} watts, sir."
    _log(msg, player)
    return msg


def _homeassistant_action(device: str, action: str, value: str, config: dict, player, speak) -> str:
    ha = config.get("homeassistant", {})
    url   = ha.get("url", "").rstrip("/")
    token = ha.get("token", "")

    if not url or not token:
        return "Sir, Home Assistant is not configured. Set url and token in config/smart_home.json."

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    if action == "list":
        data = _request("GET", f"{url}/api/states", headers=headers)
        if data is None:
            return "Sir, could not reach Home Assistant."
        entities = [e for e in data if "light" in e.get("entity_id", "")
                    or "switch" in e.get("entity_id", "")]
        lines = [f"{e['entity_id']}: {e['state']}" for e in entities]
        msg = f"Found {len(lines)} devices. " + "; ".join(lines[:20])
        _log(msg, player)
        return msg

    if not device:
        return "Sir, please specify a device entity_id."

    domain = device.split(".")[0] if "." in device else "homeassistant"
    service = action
    if action == "on":
        service = "turn_on"
    elif action == "off":
        service = "turn_off"
    elif action == "toggle":
        service = "toggle"

    data = _request("POST", f"{url}/api/services/{domain}/{service}",
                     headers=headers, json={"entity_id": device})
    if data is None:
        return f"Sir, failed to execute {action} on {device}."
    msg = f"{device} turned {action}, sir."
    _log(msg, player)
    return msg


def _log(msg: str, player):
    if player:
        try:
            player.write_log(f"JARVIS: {msg}")
        except Exception:
            pass
