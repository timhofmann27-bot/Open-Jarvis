"""
JARVIS Long-Term Memory System
Vector-gestützter Gedächtnisspeicher mit ChromaDB.
Ermöglicht semantische Suche, Reflexion und Persönlichkeitsentwicklung.
"""

import json
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import chromadb
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = BASE_DIR / "memory"


class MemoryStore:
    """Core memory system with vector search, structured data, and importance weighting."""

    COLLECTIONS = {
        "interactions": "Komplette Gespräche zwischen User und JARVIS",
        "insights":    "Extrahiertes Wissen über User, Präferenzen, Fakten",
        "reflections": "JARVIS' Selbstanalyse und Verbesserungsvorschläge",
        "persona":     "Persönlichkeitsmerkmale und Verhaltensmuster",
        "learnings":   "Gelernte Fähigkeiten, Tool-Optimierungen",
    }

    def __init__(self, api_key_fn=None):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(MEMORY_DIR / "chroma"))
        self._collections = {}
        self._api_key_fn = api_key_fn or (lambda: None)
        self._lock = threading.Lock()

        for name in self.COLLECTIONS:
            try:
                self._collections[name] = self._client.get_or_create_collection(
                    name, metadata={"description": self.COLLECTIONS[name]}
                )
            except Exception as e:
                print(f"[Memory] ⚠️ Collection '{name}': {e}")

        # Stats tracking
        self._stats = self._load_stats()
        print(f"[Memory] OK {len(self._collections)} Collections, ~{self._stats.get('total', 0)} Eintraege")

    def _load_stats(self):
        stats_file = MEMORY_DIR / "stats.json"
        if stats_file.exists():
            return json.loads(stats_file.read_text(encoding="utf-8"))
        return {"total": 0, "interactions": 0, "insights": 0, "reflections": 0, "persona": 0, "learnings": 0, "created": time.time()}

    def _save_stats(self):
        stats_file = MEMORY_DIR / "stats.json"
        stats_file.write_text(json.dumps(self._stats, indent=2), encoding="utf-8")

    def _make_id(self, prefix: str) -> str:
        return f"{prefix}_{int(time.time() * 1000000)}_{id(self)}"

    # ── Store ────────────────────────────────────────────────────────────────

    def store(self, collection: str, content: str, importance: float = 0.5, metadata: dict = None) -> str:
        """Store a memory with automatic embedding. Returns the memory ID."""
        col = self._collections.get(collection)
        if not col:
            raise ValueError(f"Unknown collection: {collection}. Available: {list(self.COLLECTIONS)}")

        mem_id = self._make_id(collection)
        meta = {
            "timestamp": time.time(),
            "date": datetime.now(timezone.utc).isoformat(),
            "importance": importance,
            "collection": collection,
        }
        if metadata:
            meta.update(metadata)

        with self._lock:
            col.add(documents=[content], metadatas=[meta], ids=[mem_id])

        self._stats["total"] = self._stats.get("total", 0) + 1
        self._stats[collection] = self._stats.get(collection, 0) + 1
        self._save_stats()
        return mem_id

    def store_interaction(self, user_text: str, jarvis_text: str, tools_used: list[str], duration: float, success: bool = True):
        """Store a complete interaction with structured metadata."""
        content = json.dumps({
            "user": user_text,
            "jarvis": jarvis_text,
            "tools": tools_used,
            "duration": round(duration, 1),
        }, ensure_ascii=False)
        return self.store("interactions", content, importance=0.6, metadata={
            "tools": ",".join(tools_used) if tools_used else "",
            "success": 1 if success else 0,
            "duration": round(duration, 1),
        })

    def store_insight(self, insight: str, category: str = "general", importance: float = 0.7):
        """Store a learned insight about the user or system."""
        return self.store("insights", insight, importance=importance, metadata={"category": category})

    def store_reflection(self, content: str, category: str = "system", importance: float = 0.5):
        return self.store("reflections", content, importance=importance, metadata={"category": category})

    def store_persona_trait(self, trait: str, importance: float = 0.8):
        return self.store("persona", trait, importance=importance, metadata={"category": "trait"})

    def store_learning(self, learning: str, category: str = "tool", importance: float = 0.6):
        return self.store("learnings", learning, importance=importance, metadata={"category": category})

    # ── Recall (Semantische Suche) ───────────────────────────────────────────

    def recall(self, query: str, collection: str = None, n: int = 5, min_importance: float = 0.0) -> list[dict]:
        """Semantic search across memories. Returns list of {content, metadata, distance}."""
        cols = [self._collections[collection]] if collection else list(self._collections.values())

        all_results = []
        for col in cols:
            try:
                results = col.query(query_texts=[query], n_results=n)
                if results and results.get("documents") and results["documents"][0]:
                    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
                        imp = meta.get("importance", 0.5) if meta else 0.5
                        if imp >= min_importance:
                            all_results.append({
                                "content": doc,
                                "metadata": meta or {},
                                "distance": dist,
                                "collection": col.name,
                            })
            except Exception as e:
                print(f"[Memory] Recall error in '{col.name}': {e}")

        all_results.sort(key=lambda x: x["distance"])
        return all_results[:n]

    def recall_recent(self, collection: str = None, hours: int = 24, n: int = 10) -> list[dict]:
        """Get most recent memories, sorted by timestamp."""
        cutoff = time.time() - (hours * 3600)
        cols = [self._collections[collection]] if collection else list(self._collections.values())

        all_results = []
        for col in cols:
            try:
                results = col.get(where={"timestamp": {"$gte": cutoff}})
                if results and results.get("documents"):
                    for doc, meta in zip(results["documents"], results["metadatas"]):
                        all_results.append({
                            "content": doc,
                            "metadata": meta or {},
                            "collection": col.name,
                        })
            except Exception as e:
                print(f"[Memory] Recent error: {e}")

        all_results.sort(key=lambda x: x["metadata"].get("timestamp", 0), reverse=True)
        return all_results[:n]

    def recall_important(self, n: int = 10, min_importance: float = 0.7) -> list[dict]:
        """Get high-importance memories across all collections."""
        all_results = []
        for name, col in self._collections.items():
            try:
                results = col.get()
                if results and results.get("documents"):
                    for doc, meta in zip(results["documents"], results["metadatas"]):
                        imp = meta.get("importance", 0.5) if meta else 0.5
                        if imp >= min_importance:
                            all_results.append({
                                "content": doc,
                                "metadata": meta or {},
                                "collection": name,
                                "importance": imp,
                            })
            except Exception:
                pass

        all_results.sort(key=lambda x: x["importance"], reverse=True)
        return all_results[:n]

    # ── Context Building ─────────────────────────────────────────────────────

    def build_context(self, query: str = "", max_memories: int = 10) -> str:
        """Build a context string for injection into the system prompt."""
        parts = []

        # Important memories
        important = self.recall_important(n=5)
        if important:
            parts.append("## Wichtige Erinnerungen")
            for m in important:
                content = m["content"]
                if len(content) > 300:
                    content = content[:300] + "..."
                parts.append(f"- [{m['collection']}] {content}")

        # Semantic search
        if query:
            relevant = self.recall(query, n=5)
            if relevant:
                parts.append("## Relevante Erinnerungen")
                for m in relevant:
                    content = m["content"]
                    if len(content) > 300:
                        content = content[:300] + "..."
                    parts.append(f"- [{m['collection']}] {content}")

        # Recent activity
        recent = self.recall_recent(hours=24, n=3)
        if recent:
            parts.append("## Letzte 24h")
            for m in recent:
                content = m["content"]
                if len(content) > 200:
                    content = content[:200] + "..."
                ts = m["metadata"].get("date", "")[:19]
                parts.append(f"- ({ts}) [{m['collection']}] {content}")

        if not parts:
            return ""

        return "\n\n".join(parts)

    # ── Personality ──────────────────────────────────────────────────────────

    def get_persona_summary(self) -> str:
        """Get a summary of JARVIS's personality traits."""
        traits = self._collections.get("persona")
        if not traits:
            return ""
        try:
            results = traits.get()
            if results and results.get("documents"):
                items = []
                for doc, meta in zip(results["documents"], results["metadatas"]):
                    imp = meta.get("importance", 0.5) if meta else 0.5
                    items.append((imp, doc))
                items.sort(reverse=True)
                return "\n".join(f"- {d}" for _, d in items[:10])
        except Exception:
            pass
        return ""

    # ── Maintenance ──────────────────────────────────────────────────────────

    def forget_old(self, older_than_days: int = 90):
        """Remove low-importance memories older than N days."""
        cutoff = time.time() - (older_than_days * 86400)
        removed = 0
        for name, col in self._collections.items():
            try:
                results = col.get(where={"timestamp": {"$lt": cutoff}})
                if results and results.get("ids"):
                    to_delete = []
                    for i, mem_id in enumerate(results["ids"]):
                        meta = results["metadatas"][i] if results.get("metadatas") else {}
                        if meta.get("importance", 0.5) < 0.3:
                            to_delete.append(mem_id)
                    if to_delete:
                        col.delete(ids=to_delete)
                        removed += len(to_delete)
            except Exception:
                pass
        if removed:
            self._stats["total"] = max(0, self._stats.get("total", 0) - removed)
            self._save_stats()
        return removed

    @property
    def stats(self) -> dict:
        return dict(self._stats)


# ── Singleton ────────────────────────────────────────────────────────────────

_memory = None
_mem_lock = threading.Lock()


def get_memory(api_key_fn=None) -> MemoryStore:
    global _memory
    with _mem_lock:
        if _memory is None:
            _memory = MemoryStore(api_key_fn=api_key_fn)
        return _memory
