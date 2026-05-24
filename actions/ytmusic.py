import webbrowser
from urllib.parse import quote_plus


def ytmusic_action(parameters: dict, player=None, speak=None) -> str:
    action = (parameters.get("action") or "").lower().strip()
    query  = (parameters.get("query") or "").strip()

    if action == "play":
        if not query:
            return "Sir, I need a song name to play."
        url = f"https://music.youtube.com/search?q={quote_plus(query)}"
        webbrowser.open(url)
        msg = f"Suche nach {query} auf YouTube Music, Sir."
        _log(msg, player)
        if speak:
            speak(msg)
        return msg

    elif action == "search":
        if not query:
            return "Sir, I need a search term."
        url = f"https://music.youtube.com/search?q={quote_plus(query)}"
        webbrowser.open(url)
        msg = f"Zeige Suchergebnisse fuer {query} auf YouTube Music, Sir."
        _log(msg, player)
        if speak:
            speak(msg)
        return msg

    elif action in ("pause", "stop"):
        _send_media_key(VK_MEDIA_PLAY_PAUSE)
        msg = "Musik pausiert, Sir."
        _log(msg, player)
        return msg

    elif action == "resume":
        _send_media_key(VK_MEDIA_PLAY_PAUSE)
        msg = "Musik wird fortgesetzt, Sir."
        _log(msg, player)
        return msg

    elif action == "next":
        _send_media_key(VK_MEDIA_NEXT_TRACK)
        msg = "Naechster Titel, Sir."
        _log(msg, player)
        return msg

    elif action == "previous":
        _send_media_key(VK_MEDIA_PREV_TRACK)
        msg = "Vorheriger Titel, Sir."
        _log(msg, player)
        return msg

    elif action == "volume":
        try:
            vol = max(0, min(100, int(query)))
            _set_volume(vol)
            msg = f"Lautstaerke auf {vol} Prozent, Sir."
            _log(msg, player)
            return msg
        except ValueError:
            return "Sir, bitte gib eine Zahl zwischen 0 und 100 an."

    elif action == "open":
        webbrowser.open("https://music.youtube.com")
        msg = "Oeffne YouTube Music, Sir."
        _log(msg, player)
        if speak:
            speak(msg)
        return msg

    else:
        return f"Sir, unbekannte Aktion '{action}'. Moeglich: play, search, pause, resume, next, previous, volume, open."


VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1


def _send_media_key(vk_code: int):
    try:
        import ctypes
        user32 = ctypes.windll.user32
        user32.keybd_event(vk_code, 0, 0, 0)
        user32.keybd_event(vk_code, 0, 2, 0)
    except Exception:
        pass


def _set_volume(percent: int):
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        scalar = max(0.0, min(1.0, percent / 100.0))
        volume.SetMasterVolumeLevelScalar(scalar, None)
    except Exception:
        pass


def _log(msg: str, player):
    if player:
        try:
            player.write_log(f"JARVIS: {msg}")
        except Exception:
            pass
