import io
import json
import time
from pathlib import Path
from google import genai
from google.genai import types

from actions.browser_control import browser_control
from actions.screen_processor import _capture_screenshot


BASE_URL = "https://www.worldmonitor.app/"
ALL_LAYERS = "conflicts,bases,hotspots,nuclear,sanctions,weather,economic,waterways,outages,military,natural,iranAttacks"

CRISIS_LAYERS = "conflicts,nuclear,hotspots,military,natural"
DIPLOMATIC_LAYERS = "conflicts,sanctions,economic,waterways,military,nuclear"
WEATHER_LAYERS = "weather,hotspots,natural,outages"

LAYER_GROUPS = {
    "crisis":   CRISIS_LAYERS,
    "all":      ALL_LAYERS,
    "diplomatic": DIPLOMATIC_LAYERS,
    "weather":  WEATHER_LAYERS,
}


def _get_api_key():
    cfg = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
    return json.loads(cfg.read_text(encoding="utf-8"))["gemini_api_key"]


def _build_url(layers: str = None, lat: float = 20.0, lon: float = 0.0, zoom: float = 1.0, time_range: str = "7d") -> str:
    layer_str = layers or CRISIS_LAYERS
    return (
        f"{BASE_URL}?lat={lat}&lon={lon}&zoom={zoom}&view=global"
        f"&timeRange={time_range}"
        f"&layers={layer_str}"
    )


def _vision_analyze_map(question: str) -> str:
    """Send screenshot to Gemini Vision and get text response back."""
    try:
        img_bytes = _capture_screenshot()
        client = genai.Client(api_key=_get_api_key())
        resp = client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=[
                question,
                types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
            ],
        )
        return resp.text.strip()
    except Exception as e:
        return f"[Vision Fehler: {e}]"


def worldmonitor_action(parameters: dict, player=None, speak=None) -> str:
    action = (parameters or {}).get("action", "analyze")

    # ── open: just open in browser ──────────────────────────────────────
    if action == "open":
        layers = (parameters or {}).get("layers")
        url = _build_url(layers=layers)
        if player:
            player.write_log(f"[WorldMonitor] Open: {url}")
        browser_control({"action": "go_to", "url": url}, player=player)
        return "WorldMonitor geöffnet."

    # ── click: click UI element (layer toggle, etc.) ────────────────────
    elif action == "click_layer" or action == "click":
        target = (parameters or {}).get("target") or (parameters or {}).get("text", "")
        if not target:
            return "Kein Ziel zum Klicken angegeben."

        if player:
            player.write_log(f"[WorldMonitor] Klicke Layer: {target}")
        browser_control({"action": "click", "text": target}, player=player)
        time.sleep(2)

        page_text = browser_control({"action": "get_text"}, player=player)
        vision = _vision_analyze_map(
            f"Die WorldMonitor-Karte zeigt jetzt Layer '{target}'. "
            f"Was ist auf der Karte zu sehen? Beschreibe relevante Ereignisse."
        )
        return f"## Layer: {target}\n\n**Kartenanalyse:**\n{vision}\n\n**Seitentext:**\n{page_text[:2000]}"

    # ── get_text: just read visible text ─────────────────────────────────
    elif action == "get_text":
        text = browser_control({"action": "get_text"}, player=player)
        return text[:4000]

    # ── scroll ──────────────────────────────────────────────────────────
    elif action == "scroll":
        direction = (parameters or {}).get("direction", "down")
        browser_control({"action": "scroll", "direction": direction}, player=player)
        time.sleep(1)
        text = browser_control({"action": "get_text"}, player=player)
        return text[:3000]

    # ── crisis_report: multi-layer crisis analysis ──────────────────────
    elif action == "crisis_report":
        layers = (parameters or {}).get("layers") or CRISIS_LAYERS
        focus = (parameters or {}).get("focus", "")
        url = _build_url(layers=layers)

        if player:
            player.write_log(f"[WorldMonitor] Krisenreport – Layer: {layers}")
        browser_control({"action": "go_to", "url": url}, player=player)
        time.sleep(5)

        page_text = browser_control({"action": "get_text"}, player=player)

        vision_question = (
            f"Du siehst die WorldMonitor-Karte mit Layern: {layers}. "
            f"{'Fokus: ' + focus + '. ' if focus else ''}"
            "Erstelle einen strukturierten Krisenreport:\n"
            "1. Aktive Konflikte und deren geografische Lage\n"
            "2. Militärische Aktivitäten und Truppenbewegungen\n"
            "3. Nukleare Aktivitäten oder Bedrohungen\n"
            "4. Naturkatastrophen und extreme Wetterereignisse\n"
            "5. Humanitäre Krisen (Versorgungsausfälle, etc.)\n"
            "Sei präzise, nenne Regionen und falls bekannt: Datenquellen."
        )
        vision = _vision_analyze_map(vision_question)

        return (
            f"## Krisenreport\n\n"
            f"**Layer:** {layers}\n\n"
            f"### Kartenanalyse\n{vision}\n\n"
            f"### Seite extrahiert\n{page_text[:3000]}"
        )

    # ── analyze (default) ───────────────────────────────────────────────
    else:
        layers = (parameters or {}).get("layers")
        focus = (parameters or {}).get("focus", "")
        url = _build_url(layers=layers)

        if player:
            player.write_log(f"[WorldMonitor] Öffne {url}")
        browser_control({"action": "go_to", "url": url}, player=player)
        time.sleep(4)

        page_text = browser_control({"action": "get_text"}, player=player)

        vision_question = (
            "Was zeigt die WorldMonitor-Karte aktuell? "
            f"{'Fokus: ' + focus + '. ' if focus else ''}"
            "Beschreibe Konflikte, Hotspots, militärische Aktivitäten "
            "und andere Ereignisse auf der Karte."
        )
        vision = _vision_analyze_map(vision_question)

        if speak and focus:
            speak(vision[:300])

        return (
            f"## WorldMonitor Analyse\n\n"
            f"### Kartenanalyse\n{vision}\n\n"
            f"### Seitentext\n{page_text[:2500]}"
        )
