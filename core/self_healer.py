"""
Self-Healing System for JARVIS.
Erkennung und automatische Reparatur von defekten Tools, fehlenden
Imports, Konfigurationsfehlern und Systemproblemen.
"""
import importlib
import json
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class SelfHealer:
    """Diagnostics and auto-repair for JARVIS systems."""

    def __init__(self, memory_store=None, self_modifier=None, api_key_fn=None, speak_fn=None):
        self.memory = memory_store
        self.modifier = self_modifier
        self.api_key_fn = api_key_fn or (lambda: "")
        self.speak = speak_fn or (lambda x: None)
        self.health_cache = {}
        self.repair_log = []
        self.ACTION_DIR = BASE_DIR / "actions"
        self.CORE_DIR = BASE_DIR / "core"
        self.CONFIG_DIR = BASE_DIR / "config"

    # ── Health Checks ─────────────────────────────────────────────────────

    def check_all(self) -> dict:
        """Run all health checks. Returns structured results."""
        results = {
            "api_keys": self._check_api_keys(),
            "imports": self._check_imports(),
            "memory": self._check_memory(),
            "disk": self._check_disk(),
            "network": self._check_network(),
            "config_files": self._check_configs(),
        }
        total = sum(1 for r in results.values() if r.get("status") == "ok")
        results["summary"] = {
            "healthy": total,
            "total": len(results),
            "all_ok": total == len(results),
        }
        self.health_cache = results
        return results

    def _check_api_keys(self) -> dict:
        try:
            path = self.CONFIG_DIR / "api_keys.json"
            if not path.exists():
                return {"status": "fail", "issues": ["api_keys.json not found"]}
            config = json.loads(path.read_text(encoding="utf-8"))
            checks = {}
            required = {"gemini_api_key": (20, "Gemini API")}
            optional = {"spotify_client_id": "Spotify", "github_token": "GitHub"}
            for key, (min_len, label) in required.items():
                val = config.get(key, "")
                if val and len(val) >= min_len:
                    checks[key] = "ok"
                else:
                    checks[key] = "missing"
            for key, label in optional.items():
                val = config.get(key, "")
                if val:
                    checks[key] = "ok"
            issues = [f"{k} missing" for k, v in checks.items() if v == "missing"]
            return {"status": "ok" if not issues else "warning", "checks": checks, "issues": issues}
        except Exception as e:
            return {"status": "fail", "issues": [str(e)]}

    def _check_imports(self) -> dict:
        failures = []
        for directory, label in [(self.ACTION_DIR, "actions"), (self.CORE_DIR, "core")]:
            for f in sorted(directory.glob("*.py")):
                if f.stem.startswith("__"):
                    continue
                try:
                    importlib.import_module(f"{label}.{f.stem}")
                except Exception as e:
                    failures.append({"module": f"{label}.{f.stem}", "error": str(e)[:120]})
        return {
            "status": "ok" if not failures else "fail",
            "failures": failures,
            "count": len(failures),
        }

    def _check_memory(self) -> dict:
        try:
            chroma_dir = BASE_DIR / "memory" / "chroma"
            if not chroma_dir.exists():
                return {"status": "fail", "issues": ["ChromaDB directory missing"]}
            return {"status": "ok", "path": str(chroma_dir)}
        except Exception as e:
            return {"status": "fail", "issues": [str(e)]}

    def _check_disk(self) -> dict:
        try:
            usage = os.path.getsize(BASE_DIR)
            total, used, free = 0, 0, 0
            if hasattr(os, "statvfs"):
                stat = os.statvfs(BASE_DIR)
                free = stat.f_frsize * stat.f_bavail
                free_mb = free / (1024 * 1024)
                return {
                    "status": "ok" if free_mb > 100 else "warning",
                    "free_mb": round(free_mb, 0),
                }
            return {"status": "ok", "free_mb": "unknown"}
        except Exception as e:
            return {"status": "warning", "issues": [str(e)]}

    def _check_network(self) -> dict:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("8.8.8.8", 53))
            s.close()
            return {"status": "ok", "latency": "available"}
        except Exception:
            return {"status": "warning", "issues": ["No internet"]}

    def _check_configs(self) -> dict:
        issues = []
        required = ["api_keys.json", "proactive.json"]
        for name in required:
            path = self.CONFIG_DIR / name
            if not path.exists():
                issues.append(f"{name} missing")
        return {"status": "ok" if not issues else "warning", "issues": issues}

    # ── Auto-Repair ───────────────────────────────────────────────────────

    def heal_tool(self, tool_name: str, error_text: str) -> dict:
        """Attempt to auto-repair a failed tool call. Returns fix result."""
        error_text = str(error_text)

        if "ModuleNotFoundError" in error_text or "No module named" in error_text:
            return self._fix_missing_import(error_text)

        if "SyntaxError" in error_text or "invalid syntax" in error_text:
            return self._fix_syntax_error(tool_name, error_text)

        if "FileNotFoundError" in error_text:
            return self._fix_missing_file(error_text)

        if "ConnectionError" in error_text or "Connection refused" in error_text:
            return {"fixed": False, "action": "Connection issue — check if service is running"}

        return {"fixed": False, "action": "No auto-repair pattern matched"}

    def _fix_missing_import(self, error_text: str) -> dict:
        """Try to fix a missing module by installing it."""
        match = re.search(r"ModuleNotFoundError: No module named ['\"](\S+)['\"]", error_text)
        if not match:
            match = re.search(r"No module named ['\"](\S+)['\"]", error_text)
        if not match:
            match = re.search(r"No module named (\S+)", error_text)
        if not match:
            return {"fixed": False, "action": "Could not parse module name from error"}

        module = match.group(1)
        # Remove submodule (e.g. actions.module → module, core.module → module)
        if "." in module:
            module = module.rsplit(".", 1)[1]
        # Sanity: only install if it looks like a PyPI package
        if not module or len(module) < 2 or module[0].isdigit():
            return {"fixed": False, "action": f"Invalid module name: {module}"}

        self._log(f"Attempting to install: {module}")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", module],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                msg = f"Installed missing module: {module}"
                self._log(msg)
                return {"fixed": True, "action": msg}
            else:
                return {"fixed": False, "action": f"pip install {module} failed: {result.stderr[:200]}"}
        except Exception as e:
            return {"fixed": False, "action": f"pip install failed: {e}"}

    def _fix_syntax_error(self, tool_name: str, error_text: str) -> dict:
        """Attempt to fix a syntax error in a tool file."""
        match = re.search(r"line (\d+)", error_text)
        line_no = int(match.group(1)) if match else None

        # Try to find which file has the error
        for directory in [self.ACTION_DIR, self.CORE_DIR]:
            for f in directory.glob("*.py"):
                if tool_name in f.stem or f.stem == tool_name:
                    content = f.read_text(encoding="utf-8")
                    lines = content.split("\n")
                    if line_no and line_no <= len(lines):
                        bad_line = lines[line_no - 1]
                        return {
                            "fixed": False,
                            "action": (
                                f"Syntax error in {f.name}:{line_no}:\n"
                                f"  {bad_line.strip()}\n"
                                "Use self_read_code + self_edit_code to fix."
                            ),
                            "file": f.name,
                            "line": line_no,
                            "content": bad_line,
                        }
        return {"fixed": False, "action": "Could not locate the file with syntax error"}

    def _fix_missing_file(self, error_text: str) -> dict:
        """Report missing file — can't auto-create unknown files."""
        match = re.search(r"FileNotFoundError:.*'(.*?)'", error_text)
        if match:
            missing_path = match.group(1)
            return {
                "fixed": False,
                "action": f"Missing file: {missing_path}. Check configuration or recreate it.",
            }
        return {"fixed": False, "action": "Could not parse file path from error"}

    # ── Error Analysis ────────────────────────────────────────────────────

    def analyze_tool_call(self, tool_name: str, error_text: str) -> str:
        """Analyze a tool call error and return a human-readable diagnosis."""
        error_text = str(error_text)
        diagnosis = []

        if "ModuleNotFoundError" in error_text:
            diagnosis.append("Missing module: pip install needed")
        if "AttributeError" in error_text:
            diagnosis.append("Function/attribute missing: code may be outdated")
        if "FileNotFoundError" in error_text:
            diagnosis.append("File not found: check path")
        if "ConnectionError" in error_text or "timeout" in error_text.lower():
            diagnosis.append("Network issue: check connectivity")
        if "KeyError" in error_text:
            diagnosis.append("Missing key in config/data structure")
        if "json.JSONDecodeError" in error_text:
            diagnosis.append("Corrupt JSON config file")
        if "PermissionError" in error_text:
            diagnosis.append("Permission denied: run as admin")

        if not diagnosis:
            diagnosis.append(f"Unrecognized error type: {error_text[:100]}")

        return "; ".join(diagnosis)

    # ── Background Watchdog ───────────────────────────────────────────────

    def _log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        self.repair_log.append(entry)
        print(f"[Healer] {message}")

    def get_log(self, n: int = 20) -> list:
        return self.repair_log[-n:]

    def get_health_summary(self) -> str:
        """Get a human-readable health summary."""
        if not self.health_cache:
            self.check_all()

        h = self.health_cache
        lines = ["=== SYSTEM HEALTH ==="]

        ap = h.get("api_keys", {})
        lines.append(f"API Keys: {ap.get('status', '?')}")
        for c, s in ap.get("checks", {}).items():
            lines.append(f"  {c}: {s}")

        im = h.get("imports", {})
        lines.append(f"Imports: {im.get('status', '?')} ({im.get('count', 0)} failures)")

        mem = h.get("memory", {})
        lines.append(f"Memory: {mem.get('status', '?')}")

        disk = h.get("disk", {})
        free = disk.get("free_mb", "?")
        lines.append(f"Disk: {disk.get('status', '?')} ({free} MB free)")

        net = h.get("network", {})
        lines.append(f"Network: {net.get('status', '?')}")

        summary = h.get("summary", {})
        lines.append(f"\nSummary: {summary.get('healthy', 0)}/{summary.get('total', 0)} healthy")

        return "\n".join(lines)
