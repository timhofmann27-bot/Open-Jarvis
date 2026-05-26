import json
import threading
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
PROMPT_PATH = BASE_DIR / "core" / "prompt.txt"

DEFAULT_MODEL = "tinyllama"


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return "You are JARVIS, a helpful AI assistant. Answer concisely in German."


def _build_prompt(user_text: str) -> list[dict]:
    sys = _load_system_prompt()
    now = datetime.now().strftime("%A, %d.%m.%Y %H:%M")
    messages = [
        {"role": "system", "content": f"{sys}\n\nAktuelle Zeit: {now}"},
    ]
    try:
        from memory.memory_manager import load_memory, format_memory_for_prompt
        mem = load_memory()
        mem_str = format_memory_for_prompt(mem)
        if mem_str:
            messages.append({"role": "system", "content": mem_str})
    except Exception:
        pass
    messages.append({"role": "user", "content": user_text})
    return messages


def ask(user_text: str, model: str = DEFAULT_MODEL) -> str:
    try:
        import ollama
        messages = _build_prompt(user_text)
        response = ollama.chat(model=model, messages=messages)
        return response["message"]["content"]
    except Exception as e:
        return f"[Local LLM Fehler] {e}"


def ask_stream(user_text: str, on_token, model: str = DEFAULT_MODEL):
    try:
        import ollama
        messages = _build_prompt(user_text)
        stream = ollama.chat(model=model, messages=messages, stream=True)
        for chunk in stream:
            content = chunk.get("message", {}).get("content", "")
            if content:
                on_token(content)
    except Exception as e:
        on_token(f"\n[Fehler] {e}")
