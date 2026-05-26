"""
Proactive Intelligence Engine for JARVIS.
Analysiert Muster aus dem Langzeitgedächtnis und liefert Kontext-Hinweise,
damit JARVIS selbstständig relevante Aktionen vorschlagen kann.
"""
import json
import threading
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class ProactiveIntelligence:
    """Memory-driven proactive intelligence engine."""

    def __init__(self, memory_store, api_key_fn=None):
        self.memory = memory_store
        self.api_key_fn = api_key_fn or (lambda: None)
        self.cache = {}
        self.cache["patterns"] = {}
        self.cache["stats"] = {}
        self.last_analysis = 0.0
        self.analysis_interval = 1800
        self.running = False
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self.running = True
        self._thread = threading.Thread(target=self._bg_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def _bg_loop(self):
        while self.running:
            try:
                if time.time() - self.last_analysis > self.analysis_interval:
                    self.analyze_recent()
            except Exception as e:
                print(f"[Proactive] Analysis error: {e}")
            time.sleep(60)

    def analyze_recent(self):
        """Analyze recent interactions for time-based + topic patterns."""
        interactions = self.memory.recall_recent(
            collection="interactions", hours=24 * 7, n=200
        )

        hour_counts = defaultdict(int)
        hour_tools = defaultdict(lambda: defaultdict(int))
        hour_topics = defaultdict(list)
        top_tools_global = defaultdict(int)
        total = len(interactions)

        for interaction in interactions:
            meta = interaction.get("metadata", {}) or {}
            content = interaction.get("content", "")

            try:
                data = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                continue

            ts = meta.get("timestamp", 0)
            if not ts:
                continue
            dt = datetime.fromtimestamp(ts)
            h = dt.hour

            hour_counts[h] += 1
            tools = data.get("tools", []) or []
            user_text = (data.get("user", "") or "").strip()

            for t in tools:
                hour_tools[h][t] += 1
                top_tools_global[t] += 1

            if user_text and len(user_text) > 10:
                hour_topics[h].append(user_text)

        patterns = {}
        for h in range(24):
            count = hour_counts.get(h, 0)
            if count < 2:
                continue
            hints = []
            tools = hour_tools.get(h, {})
            if tools:
                top_tool = max(tools, key=tools.get)
                hints.append(f"often uses '{top_tool}'")
            topics = hour_topics.get(h, [])
            if topics:
                from collections import Counter
                common = Counter(topics).most_common(1)
                if common:
                    hints.append(f"common topic: '{common[0][0][:60]}'")
            if hints:
                patterns[str(h)] = hints

        self.cache["patterns"] = patterns
        self.cache["stats"] = {
            "total_analyzed": total,
            "peak_hour": max(hour_counts, key=hour_counts.get) if hour_counts else None,
            "top_tools": dict(sorted(top_tools_global.items(), key=lambda x: -x[1])[:10]),
        }
        self.cache["hour_counts"] = dict(hour_counts)
        self.last_analysis = time.time()

        print(
            f"[Proactive] Analyzed {total} interactions, "
            f"{len(patterns)} hour-patterns found"
        )

    def get_context_hints(self) -> str:
        """Build proactive context hints for system prompt injection."""
        parts = []
        now = datetime.now()
        hour = now.hour
        day = now.strftime("%A")

        stats = self.cache.get("stats", {})
        total = stats.get("total_analyzed", 0)

        # Pattern hint for current hour
        hour_str = str(hour)
        patterns = self.cache.get("patterns", {})
        current_hints = patterns.get(hour_str, [])
        hour_count = self.cache.get("hour_counts", {}).get(hour, 0)

        if current_hints:
            hints_str = "; ".join(current_hints)
            parts.append(
                f"[PROACTIVE HINT] At this time ({day}, {hour}:00) "
                f"the user has interacted {hour_count}x and {hints_str}."
            )

        # Top tools this week
        top_tools = stats.get("top_tools", {})
        if top_tools:
            tools_str = ", ".join(
                f"{t}({c}x)" for t, c in list(top_tools.items())[:5]
            )
            parts.append(f"[PROACTIVE HINT] Most used tools this week: {tools_str}")

        # Peak activity time
        peak = stats.get("peak_hour")
        if peak is not None and int(peak) != hour:
            parts.append(
                f"[PROACTIVE HINT] User's peak activity hour: {peak}:00"
            )

        # Important memories
        important = self.memory.recall_important(n=3, min_importance=0.8)
        if important:
            parts.append("[PROACTIVE HINT] High-importance memories to consider:")
            for m in important:
                content = m["content"]
                if len(content) > 200:
                    content = content[:200] + "..."
                parts.append(f"  - [{m['collection']}] {content}")

        if not parts:
            return ""

        parts.append(
            "[INSTRUCTION] You are proactive. Based on the PROACTIVE HINTs above, "
            "if you notice a good opportunity to help, suggest it naturally. "
            "But don't force it — only suggest when it genuinely seems helpful."
        )

        return "\n".join(parts)

    def get_full_report(self) -> str:
        """Get a detailed pattern analysis report (for tool use)."""
        lines = []
        stats = self.cache.get("stats", {})
        patterns = self.cache.get("patterns", {})
        hour_counts = self.cache.get("hour_counts", {})

        lines.append("=== PATTERN ANALYSIS REPORT ===")
        lines.append(f"Total interactions analyzed: {stats.get('total_analyzed', 0)}")
        lines.append(f"Last analysis: {datetime.fromtimestamp(self.last_analysis).strftime('%H:%M:%S') if self.last_analysis else 'never'}")
        lines.append("")

        top_tools = stats.get("top_tools", {})
        if top_tools:
            lines.append("Top tools:")
            for t, c in list(top_tools.items())[:10]:
                lines.append(f"  {t}: {c}x")
            lines.append("")

        lines.append("Hour-by-hour patterns:")
        for h in range(24):
            hs = str(h)
            count = hour_counts.get(h, 0)
            if count > 0:
                hints = patterns.get(hs, [])
                hint_str = f" — {'; '.join(hints)}" if hints else ""
                lines.append(f"  {h:02d}:00 — {count} interactions{hint_str}")

        if not lines:
            return "No data yet. Use self_analyze_patterns to start analysis."
        return "\n".join(lines)
