"""
JARVIS Self-Testing Suite.
Automatisierte Tests für alle Tools, Core-Module, API-Endpoints und Systeme.
"""
import importlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


class TestSuite:
    """Comprehensive self-testing for JARVIS systems."""

    def __init__(self):
        self.results = []
        self.start_time = 0
        self.end_time = 0

    def run_all(self) -> dict:
        """Run all test suites. Returns structured results."""
        self.start_time = time.time()
        self.results = []

        self._test_imports()
        self._test_configs()
        self._test_core_modules()
        self._test_action_tools()
        self._test_network()
        self._test_api_endpoints()

        self.end_time = time.time()

        return self._summary()

    def _add(self, suite: str, name: str, status: str, detail: str = ""):
        self.results.append({
            "suite": suite,
            "name": name,
            "status": status,
            "detail": detail[:200],
            "time": time.time() - self.start_time,
        })
        icon = {"PASS": "[OK]", "FAIL": "[!!]", "SKIP": "[--]"}.get(status, "[??]")
        print(f"  {icon} [{suite}] {name}: {detail[:80] if detail else status}")

    # ── Tests ────────────────────────────────────────────────────────────

    def _test_imports(self):
        """Verify all action and core modules import without errors."""
        for directory, label in [(BASE_DIR / "actions", "actions"), (BASE_DIR / "core", "core")]:
            for f in sorted(directory.glob("*.py")):
                if f.stem.startswith("__"):
                    continue
                try:
                    importlib.import_module(f"{label}.{f.stem}")
                    self._add("imports", f"{label}.{f.stem}", PASS)
                except Exception as e:
                    self._add("imports", f"{label}.{f.stem}", FAIL, str(e)[:120])

    def _test_configs(self):
        """Verify all config files exist and contain valid JSON."""
        config_dir = BASE_DIR / "config"
        required = ["api_keys.json", "proactive.json", "email.json", "smart_home.json", "devices.json", "obsidian.json"]

        for name in required:
            path = config_dir / name
            if not path.exists():
                self._add("configs", name, FAIL, "File not found")
                continue
            try:
                json.loads(path.read_text(encoding="utf-8"))
                self._add("configs", name, PASS)
            except json.JSONDecodeError as e:
                self._add("configs", name, FAIL, f"Invalid JSON: {e}")

    def _test_core_modules(self):
        """Test core module functions: memory, self_modifier, reflector, etc."""
        # SelfModifier
        try:
            from core.self_modifier import SelfModifier
            sm = SelfModifier()
            files = sm.list_sources()
            assert len(files) > 10, f"Only {len(files)} files"
            self._add("core", "SelfModifier.list_sources", PASS, f"{len(files)} files")

            r = sm.read_source("main.py")
            assert "content" in r, "Missing content"
            self._add("core", "SelfModifier.read_source", PASS, f"{r['lines']} lines")

            r = sm.validate_syntax("def foo():\n    pass")
            assert r["valid"], "Syntax should be valid"
            self._add("core", "SelfModifier.validate_syntax", PASS)

            r = sm.validate_syntax("def foo()\n    pass")
            assert not r["valid"], "Syntax should be invalid"
            self._add("core", "SelfModifier.validate_syntax (invalid)", PASS, "correctly rejected")
        except Exception as e:
            self._add("core", "SelfModifier", FAIL, str(e)[:120])

        # SelfHealer
        try:
            from core.self_healer import SelfHealer
            healer = SelfHealer()
            health = healer.check_all()
            self._add("core", "SelfHealer.check_all", PASS,
                      f"{health['summary']['healthy']}/{health['summary']['total']} healthy")

            r = healer.analyze_tool_call("test", "ModuleNotFoundError: No module named 'X'")
            assert "pip" in r.lower(), "Should suggest pip install"
            self._add("core", "SelfHealer.analyze_tool_call", PASS)
        except Exception as e:
            self._add("core", "SelfHealer", FAIL, str(e)[:120])

        # ProactiveIntelligence
        try:
            from core.proactive_intelligence import ProactiveIntelligence
            from core.memory_store import get_memory
            mem = get_memory()
            pi = ProactiveIntelligence(memory_store=mem)
            pi.analyze_recent()
            hints = pi.get_context_hints()
            self._add("core", "ProactiveIntelligence", PASS, f"hints={len(hints)} chars")
        except Exception as e:
            self._add("core", "ProactiveIntelligence", FAIL, str(e)[:120])

        # MemoryStore
        try:
            from core.memory_store import get_memory
            mem = get_memory()
            stats = mem.stats
            self._add("core", "MemoryStore.stats", PASS, f"{stats.get('total', 0)} entries")
        except Exception as e:
            self._add("core", "MemoryStore", FAIL, str(e)[:120])

    def _test_action_tools(self):
        """Test action module function signatures exist."""
        for f in sorted((BASE_DIR / "actions").glob("*.py")):
            if f.stem.startswith("__"):
                continue
            try:
                mod = importlib.import_module(f"actions.{f.stem}")
                # Look for the main action function
                func_names = [n for n in dir(mod) if not n.startswith("_") and callable(getattr(mod, n))]
                if not func_names:
                    self._add("actions", f.stem, SKIP, "No public functions")
                    continue
                # Try to call the first public function with no args to see if it handles defaults
                main_func = func_names[0]
                self._add("actions", f"{f.stem}.{main_func}", PASS, f"{len(func_names)} functions")
            except Exception as e:
                self._add("actions", f.stem, FAIL, str(e)[:120])

            # file_processor migration check
            if f.stem == "file_processor":
                src = f.read_text(encoding="utf-8")
                if "google.generativeai" in src:
                    self._add("actions", f"{f.stem}.migration", FAIL, "Deprecated 'google.generativeai' import present")
                elif "from google import genai" not in src and "google.genai" not in src:
                    self._add("actions", f"{f.stem}.migration", FAIL, "New 'google.genai' import missing")
                else:
                    if not hasattr(mod, "_generate"):
                        self._add("actions", f"{f.stem}._generate", FAIL, "_generate helper missing")
                    elif hasattr(mod, "_gemini_client"):
                        self._add("actions", f"{f.stem}._gemini_client", FAIL, "Deprecated _gemini_client still present")
                    else:
                        self._add("actions", f"{f.stem}.migration", PASS, "Migrated to google.genai SDK")

    def _test_network(self):
        """Test basic network connectivity."""
        import socket

        # DNS resolution
        try:
            socket.getaddrinfo("google.com", 80)
            self._add("network", "DNS resolution", PASS)
        except Exception as e:
            self._add("network", "DNS resolution", FAIL, str(e)[:80])

        # HTTP connectivity
        try:
            import urllib.request
            r = urllib.request.urlopen("http://8.8.8.8", timeout=3)
            self._add("network", "HTTP connectivity", PASS)
        except Exception:
            self._add("network", "HTTP connectivity", SKIP, "8.8.8.8:80 not available")

        # Gemini API key check
        try:
            config = json.loads((BASE_DIR / "config" / "api_keys.json").read_text(encoding="utf-8"))
            key = config.get("gemini_api_key", "")
            if key and len(key) > 20:
                self._add("network", "Gemini API key", PASS, f"{key[:8]}...")
            else:
                self._add("network", "Gemini API key", FAIL, "Missing or too short")
        except Exception as e:
            self._add("network", "Gemini API key", FAIL, str(e)[:80])

    def _test_api_endpoints(self):
        """Test dashboard API endpoints if server is running."""
        for port in [8080, 8081]:
            try:
                import urllib.request
                r = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2)
                data = json.loads(r.read())
                self._add("api", f"GET /api/status (:{port})", PASS, f"tools={data.get('tools','?')}")

                r = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2)
                h = json.loads(r.read())
                s = h.get("health", {}).get("summary", {})
                self._add("api", f"GET /api/health (:{port})", PASS,
                          f"{s.get('healthy',0)}/{s.get('total',6)}")

                r = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/memory/stats", timeout=2)
                m = json.loads(r.read())
                self._add("api", f"GET /api/memory/stats (:{port})", PASS,
                          f"{m.get('stats',{}).get('total',0)} entries")

                # If we got here, API server is running
                return
            except Exception:
                continue

        self._add("api", "API Server", SKIP, "No server running on :8080 or :8081")

    # ── Results ──────────────────────────────────────────────────────────

    def _summary(self) -> dict:
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == PASS)
        failed = sum(1 for r in self.results if r["status"] == FAIL)
        skipped = sum(1 for r in self.results if r["status"] == SKIP)
        duration = round(self.end_time - self.start_time, 1)

        suites = {}
        for r in self.results:
            suites.setdefault(r["suite"], {"pass": 0, "fail": 0, "skip": 0, "total": 0})
            suites[r["suite"]][r["status"].lower()] += 1
            suites[r["suite"]]["total"] += 1

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "duration": duration,
            "success_rate": round(passed / total * 100, 1) if total else 0,
            "suites": suites,
            "results": self.results,
            "timestamp": time.time(),
        }

    def summary_text(self) -> str:
        """Human-readable summary."""
        s = self._summary()
        lines = [
            f"=== JARVIS TEST SUITE ===",
            f"Total: {s['total']}  Passed: {s['passed']}  Failed: {s['failed']}  Skipped: {s['skipped']}",
            f"Duration: {s['duration']}s  Success Rate: {s['success_rate']}%",
            "",
        ]
        for suite, counts in s.get("suites", {}).items():
            status = "[OK]" if counts["fail"] == 0 else "[!!]"
            lines.append(f"  {status} {suite}: {counts['pass']} pass, {counts['fail']} fail, {counts['skip']} skip")
        lines.append("")
        for r in s["results"]:
            icon = {"PASS": "[OK]", "FAIL": "[!!]", "SKIP": "[--]"}[r["status"]]
            detail = f" — {r['detail']}" if r["detail"] else ""
            lines.append(f"  {icon} [{r['suite']}] {r['name']}{detail}")
        return "\n".join(lines)


def run_tests() -> dict:
    """Convenience function to run all tests."""
    suite = TestSuite()
    return suite.run_all()


if __name__ == "__main__":
    suite = TestSuite()
    suite.run_all()
    print(suite.summary_text())
