import imaplib
import json
import smtplib
import ssl
from datetime import datetime
from email.mime.text import MIMEText
from email.header import decode_header
from pathlib import Path
from urllib.parse import quote_plus

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "email.json"


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {"provider": "imap", "imap_server": "", "smtp_server": "", "email": "", "password": ""}


def email_action(parameters: dict, player=None, speak=None) -> str:
    action = (parameters.get("action") or "").lower().strip()
    cfg = _load_config()

    if action in ("list", "inbox"):
        try:
            imap = imaplib.IMAP4_SSL(cfg["imap_server"])
            imap.login(cfg["email"], cfg["password"])
            imap.select("INBOX")
            _, data = imap.search(None, "ALL")
            ids = data[0].split()[-5:]
            result = []
            for mid in ids:
                _, msg_data = imap.fetch(mid, "(BODY[HEADER.FIELDS (FROM SUBJECT DATE)])")
                result.append(msg_data[0][1].decode(errors="replace").strip())
            imap.logout()
            msg = "Letzte 5 Mails:\n" + "\n---\n".join(result)
            _log(msg[:500], player)
            return msg
        except Exception as e:
            return f"Fehler beim Abrufen: {e}"

    elif action == "send":
        to = parameters.get("to", "")
        subject = parameters.get("subject", "")
        body = parameters.get("body", "")
        if not to or not subject:
            return "Sir, ich brauche einen Empfänger und Betreff."
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = cfg["email"]
            msg["To"] = to
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg["smtp_server"], 465, context=ctx) as s:
                s.login(cfg["email"], cfg["password"])
                s.sendmail(cfg["email"], [to], msg.as_string())
            r = f"Mail an {to} gesendet: {subject}"
            _log(r, player)
            return r
        except Exception as e:
            return f"Fehler beim Senden: {e}"

    elif action in ("calendar", "termine"):
        try:
            import win32com.client
            outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
            cal = outlook.GetDefaultFolder(9)
            items = cal.Items
            items.Sort("[Start]")
            items = items.Restrict(f"[Start] >= '{datetime.now().strftime('%m/%d/%Y')}'")
            result = []
            for i, item in enumerate(items):
                if i >= 5:
                    break
                result.append(f"{item.Start.Format('dd.MM HH:mm')} - {item.Subject}")
            if result:
                msg = "Nächste Termine:\n" + "\n".join(result)
            else:
                msg = "Keine Termine gefunden."
            _log(msg, player)
            return msg
        except Exception:
            return "Outlook-Kalender nicht verfügbar (nur Windows/Outlook)."

    else:
        return "Aktionen: list/inbox, send, calendar/termine."


def _log(msg: str, player):
    if player:
        try:
            player.write_log(f"JARVIS: {msg[:200]}")
        except Exception:
            pass
