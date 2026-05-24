import json
import random
import threading
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "proactive.json"


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {
            "enabled": True,
            "weather_interval_min": 120,
            "news_interval_min": 180,
            "greeting_enabled": True,
        }


class ProactiveNotifier:
    def __init__(self, speak_fn, write_log_fn):
        self._speak = speak_fn
        self._log = write_log_fn
        self._running = False
        self._thread = None
        self._cfg = _load_config()
        self._last_weather = 0.0
        self._last_news = 0.0
        self._greeted_today = False

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[NOTIFIER] Gestartet")

    def stop(self):
        self._running = False

    def reload_config(self):
        self._cfg = _load_config()

    def _loop(self):
        while self._running:
            try:
                now = time.time()
                cfg = self._cfg
                if not cfg.get("enabled", True):
                    time.sleep(30)
                    continue
                hour = datetime.now().hour
                if cfg.get("greeting_enabled") and not self._greeted_today:
                    if 7 <= hour <= 10:
                        self._say_greeting("morning")
                        self._greeted_today = True
                    elif 18 <= hour <= 22:
                        self._say_greeting("evening")
                        self._greeted_today = True
                if hour == 0 and self._greeted_today:
                    self._greeted_today = False
                wi = cfg.get("weather_interval_min", 120) * 60
                ni = cfg.get("news_interval_min", 180) * 60
                if wi > 0 and (now - self._last_weather) > wi:
                    self._announce_weather()
                    self._last_weather = now
                if ni > 0 and (now - self._last_news) > ni:
                    self._announce_news()
                    self._last_news = now
            except Exception as e:
                print(f"[NOTIFIER] Fehler: {e}")
            time.sleep(60)

    def _say_greeting(self, period: str):
        msgs = {
            "morning": [
                "Guten Morgen, Sir. Ich hoffe, Sie haben gut geschlafen.",
                "Guten Morgen. Ein neuer Tag voller Moeglichkeiten.",
            ],
            "evening": [
                "Guten Abend, Sir. Ich bin fuer Sie da, falls Sie etwas brauchen.",
                "Guten Abend. Wie war Ihr Tag?",
            ],
        }
        msg = random.choice(msgs.get(period, ["Hallo Sir."]))
        self._log(f"[NOTIFIER] {msg}")
        self._speak(msg)

    def _announce_weather(self):
        try:
            import requests
            city = self._cfg.get("weather_city", "")
            if not city:
                return
            r = requests.get(
                f"https://wttr.in/{city}?format=%C+%t&lang=de",
                timeout=8
            )
            if r.status_code == 200:
                text = r.text.strip()
                msg = f"Aktuelles Wetter in {city}: {text}, Sir."
                self._log(f"[NOTIFIER] {msg}")
                self._speak(msg)
        except Exception as e:
            print(f"[NOTIFIER] Wetter-Fehler: {e}")

    def _announce_news(self):
        try:
            import requests
            r = requests.get(
                "https://rss.golem.de/rss.php?feed=ATOM",
                timeout=8
            )
            if r.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(r.text)
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                entries = root.findall("atom:entry", ns)[:3]
                titles = []
                for entry in entries:
                    title = entry.find("atom:title", ns)
                    if title is not None and title.text:
                        titles.append(title.text.strip())
                if titles:
                    msg = "Aktuelle News: " + ". ".join(titles) + ", Sir."
                    self._log(f"[NOTIFIER] {msg}")
                    self._speak(msg)
        except Exception as e:
            print(f"[NOTIFIER] News-Fehler: {e}")
