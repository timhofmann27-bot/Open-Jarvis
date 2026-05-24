import asyncio
import json
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "telegram.json"


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {"bot_token": "", "allowed_user_ids": []}


class TelegramBot:
    def __init__(self, speak_fn=None, write_log_fn=None):
        self._speak = speak_fn
        self._log = write_log_fn
        self._running = False
        self._thread = None
        self._app = None

    def start(self):
        if self._running:
            return
        cfg = _load_config()
        if not cfg.get("bot_token"):
            print("[TELEGRAM] Kein Bot-Token konfiguriert.")
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[TELEGRAM] Bot gestartet")

    def stop(self):
        self._running = False
        if self._app:
            try:
                self._app.stop()
            except Exception:
                pass

    def _run(self):
        try:
            from telegram import Update
            from telegram.ext import Application, CommandHandler, MessageHandler, filters
        except ImportError:
            print("[TELEGRAM] python-telegram-bot nicht installiert.")
            return

        cfg = _load_config()
        token = cfg.get("bot_token", "")
        allowed = cfg.get("allowed_user_ids", [])

        if not token:
            print("[TELEGRAM] Kein Token.")
            return

        async def _start(update: Update, context):
            uid = update.effective_user.id if update.effective_user else None
            if allowed and uid not in allowed:
                await update.message.reply_text("Nicht autorisiert.")
                return
            await update.message.reply_text("Jarvis Telegram Bot aktiv. Sende mir einen Befehl.")

        async def _handle(update: Update, context):
            uid = update.effective_user.id if update.effective_user else None
            if allowed and uid not in allowed:
                await update.message.reply_text("Nicht autorisiert.")
                return
            text = update.message.text if update.message else ""
            if not text:
                return
            if self._log:
                self._log(f"[TELEGRAM] {text}")
            if text.startswith("/"):
                await update.message.reply_text(f"Unbekannter Befehl: {text}")
                return
            try:
                from core.local_llm import ask
                result = ask(text)
                for i in range(0, len(result), 4000):
                    await update.message.reply_text(result[i:i + 4000])
                if self._speak and self._log:
                    self._log(f"[TELEGRAM] Antwort: {result[:100]}")
            except Exception as e:
                await update.message.reply_text(f"Fehler: {e}")

        try:
            app = Application.builder().token(token).build()
            self._app = app
            app.add_handler(CommandHandler("start", _start))
            app.add_handler(CommandHandler("help", _start))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle))
            print("[TELEGRAM] Bot läuft (Polling)...")
            app.run_polling(allowed_updates=["messages"])
        except Exception as e:
            print(f"[TELEGRAM] Fehler: {e}")
        finally:
            self._running = False
