import json
import os
import webbrowser
from pathlib import Path
from urllib.parse import quote

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "obsidian.json"


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {"vault_path": "", "local_api_port": 27123, "api_token": ""}


def obsidian_action(parameters: dict, player=None, speak=None) -> str:
    action = (parameters.get("action") or "").lower().strip()
    query  = (parameters.get("query") or "").strip()
    note   = (parameters.get("note") or "").strip()
    content = (parameters.get("content") or "").strip()

    cfg = _load_config()
    vault = cfg.get("vault_path", "")

    if action == "open":
        _open_obsidian()
        msg = "Oeffne Obsidian, Sir."
        _log(msg, player)
        return msg

    if action in ("search", "find"):
        if not query:
            return "Sir, wonach soll ich suchen?"
        _open_obsidian_search(query)
        msg = f"Suche nach {query} in Obsidian, Sir."
        _log(msg, player)
        return msg

    if action in ("note", "create", "write"):
        if not note:
            return "Sir, wie soll die Notiz heissen?"
        if not vault:
            return "Sir, Obsidian Vault-Pfad ist nicht konfiguriert."
        filepath = Path(vault) / f"{note}.md"
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            timestamp = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")
            full = f"---\ncreated: {timestamp}\n---\n\n"
            if content:
                full += content + "\n"
            filepath.write_text(full, encoding="utf-8")
            msg = f"Notiz {note} erstellt, Sir."
            _open_obsidian_note(note)
            _log(msg, player)
            return msg
        except Exception as e:
            return f"Konnte Notiz nicht erstellen: {e}"

    if action == "append":
        if not note or not content:
            return "Sir, ich brauche einen Notiznamen und Inhalt."
        if not vault:
            return "Sir, Obsidian Vault-Pfad ist nicht konfiguriert."
        filepath = Path(vault) / f"{note}.md"
        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(f"\n{content}\n")
            msg = f"Notiz {note} aktualisiert, Sir."
            _log(msg, player)
            return msg
        except Exception as e:
            return f"Konnte Notiz nicht aktualisieren: {e}"

    if action == "read":
        if not note:
            return "Sir, welche Notiz soll ich lesen?"
        if not vault:
            return "Sir, Obsidian Vault-Pfad ist nicht konfiguriert."
        filepath = Path(vault) / f"{note}.md"
        try:
            text = filepath.read_text(encoding="utf-8")
            preview = text[:500].strip()
            if speak:
                speak(f"Inhalt von {note}: " + preview[:200])
            msg = f"{note}: {preview}"
            _log(msg, player)
            return msg
        except FileNotFoundError:
            return f"Notiz {note} nicht gefunden."
        except Exception as e:
            return f"Fehler beim Lesen: {e}"

    if action == "list":
        if not vault:
            return "Sir, Obsidian Vault-Pfad ist nicht konfiguriert."
        try:
            vault_path = Path(vault)
            files = sorted(vault_path.rglob("*.md"))
            recent = [f.stem for f in files[-10:]]
            msg = "Letzte 10 Notizen: " + ", ".join(recent)
            _log(msg, player)
            return msg
        except Exception as e:
            return f"Fehler: {e}"

    return "Unbekannte Aktion. Moeglich: open, search, note, append, read, list."


def _open_obsidian():
    try:
        webbrowser.open("obsidian://open")
    except Exception:
        os.startfile("obsidian://open")


def _open_obsidian_search(query: str):
    try:
        webbrowser.open(f"obsidian://search?query={quote(query)}")
    except Exception:
        os.startfile(f"obsidian://search?query={quote(query)}")


def _open_obsidian_note(note: str):
    try:
        webbrowser.open(f"obsidian://new?name={quote(note)}")
    except Exception:
        os.startfile(f"obsidian://new?name={quote(note)}")


def _log(msg: str, player):
    if player:
        try:
            player.write_log(f"JARVIS: {msg}")
        except Exception:
            pass
