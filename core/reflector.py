"""
JARVIS Reflection Engine – Selbstreflexion & Persönlichkeitsentwicklung.
Analysiert Interaktionen, extrahiert Insights, treibt Selbstverbesserung voran.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types


BASE_DIR = Path(__file__).resolve().parent.parent


def _get_api_key():
    cfg = BASE_DIR / "config" / "api_keys.json"
    return json.loads(cfg.read_text(encoding="utf-8"))["gemini_api_key"]


class Reflector:
    """Self-reflection engine that analyzes interactions and drives evolution."""

    def __init__(self, memory_store=None):
        self._memory = memory_store
        self._last_reflection = 0.0
        self._reflection_interval = 3600  # minimum 1h between reflections

    def set_memory(self, memory_store):
        self._memory = memory_store

    def reflect_on_conversation(self, user_text: str, jarvis_text: str, tools_used: list[str], duration: float) -> dict:
        """After each conversation, extract insights and store them."""
        if not self._memory:
            return {"reflected": False, "reason": "no memory store"}

        result = {
            "reflected": True,
            "insights": [],
            "traits": [],
            "learnings": [],
        }

        try:
            client = genai.Client(api_key=_get_api_key())

            prompt = (
                "Du bist JARVIS' Reflexions-Engine. Analysiere diese Interaktion und extrahiere:\n\n"
                f"USER: {user_text[:2000]}\n"
                f"JARVIS: {jarvis_text[:2000]}\n"
                f"TOOLS: {', '.join(tools_used) if tools_used else 'keine'}\n"
                f"DAUER: {duration:.0f}s\n\n"
                "Antworte in diesem JSON-Format:\n"
                "{\n"
                '  "insights": ["Erkenntnis über User-Präferenz oder Verhalten", ...],\n'
                '  "persona_traits": ["Persönlichkeitsmerkmal das JARVIS weiterentwickeln sollte", ...],\n'
                '  "learnings": ["Was JARVIS für zukünftige Interaktionen besser machen kann", ...],\n'
                '  "mood_analysis": "User-Stimmung (neutral/positiv/frustriert/begeistert)",\n'
                '  "success_rating": 0.0-1.0\n'
                "}\n\n"
                "Maximal 3 Insights, 2 Traits, 2 Learnings. Sei präzise und wertvoll."
            )

            resp = client.models.generate_content(
                model="models/gemini-2.5-flash",
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )

            parsed = json.loads(resp.text.strip())

            # Store insights
            for insight in parsed.get("insights", []):
                self._memory.store_insight(insight, category="conversation", importance=0.6)
                result["insights"].append(insight)

            # Store persona traits
            for trait in parsed.get("persona_traits", []):
                self._memory.store_persona_trait(trait, importance=0.7)
                result["traits"].append(trait)

            # Store learnings
            for learning in parsed.get("learnings", []):
                self._memory.store_learning(learning, importance=0.5)
                result["learnings"].append(learning)

            # Store reflection
            reflection_text = (
                f"Interaktion analysiert: User-Stimmung={parsed.get('mood_analysis', 'unbekannt')}, "
                f"Rating={parsed.get('success_rating', 0.5)}, "
                f"Tools={', '.join(tools_used) if tools_used else 'keine'}"
            )
            self._memory.store_reflection(reflection_text, category="conversation", importance=0.4)

            result["mood"] = parsed.get("mood_analysis", "neutral")
            result["rating"] = parsed.get("success_rating", 0.5)

            return result

        except Exception as e:
            print(f"[Reflector] Fehler: {e}")
            return {"reflected": False, "reason": str(e)}

    def deep_reflection(self) -> dict:
        """Scheduled deep reflection – analyzes all recent activity for patterns."""
        if not self._memory:
            return {"reflected": False}

        # Only run every N seconds
        if time.time() - self._last_reflection < self._reflection_interval:
            return {"reflected": False, "reason": "too soon"}

        self._last_reflection = time.time()

        try:
            recent = self._memory.recall_recent(hours=24, n=20)
            if not recent:
                return {"reflected": False, "reason": "no recent data"}

            interactions_text = "\n---\n".join(
                m["content"][:500] for m in recent if m["collection"] == "interactions"
            )

            client = genai.Client(api_key=_get_api_key())
            prompt = (
                "Du bist JARVIS' Tiefenreflexion. Analysiere die letzten Interaktionen:\n\n"
                f"{interactions_text}\n\n"
                "Erkenne Muster und gib Empfehlungen in JSON:\n"
                "{\n"
                '  "patterns": ["Wiederkehrendes Thema oder Verhalten", ...],\n'
                '  "improvements": ["Was JARVIS besser machen kann", ...],\n'
                '  "new_capabilities": ["Neue Fähigkeit die nützlich wäre", ...],\n'
                '  "user_preferences": ["Was der User mag/nicht mag", ...],\n'
                '  "growth_direction": "Wie sich JARVIS weiterentwickeln sollte"\n'
                "}"
            )

            resp = client.models.generate_content(
                model="models/gemini-2.5-flash",
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )

            parsed = json.loads(resp.text.strip())
            self._memory.store_reflection(
                json.dumps(parsed, ensure_ascii=False),
                category="deep_reflection",
                importance=0.8,
            )

            return parsed

        except Exception as e:
            print(f"[Reflector] Deep reflection error: {e}")
            return {"reflected": False, "reason": str(e)}


# ── Singleton ────────────────────────────────────────────────────────────────

_reflector = None


def get_reflector(memory_store=None) -> Reflector:
    global _reflector
    if _reflector is None:
        _reflector = Reflector(memory_store=memory_store)
    elif memory_store:
        _reflector.set_memory(memory_store)
    return _reflector
