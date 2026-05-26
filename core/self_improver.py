"""
Self-Improvement Loop for JARVIS.
Analysiert Codebase, findet Optimierungspotential und wendet
Verbesserungen autonom an – mit voller Audit-Trail.
"""
import ast
import json
import os
import re
import time
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class SelfImprover:
    """Engine for autonomous code improvement."""

    def __init__(self, self_modifier=None, self_healer=None, memory_store=None):
        self.modifier = self_modifier
        self.healer = self_healer
        self.memory = memory_store
        self.log_path = BASE_DIR / "memory" / "improvements.json"
        self._init_log()
        self.running = False
        self._thread = None
        self.cycle_count = 0

    def _init_log(self):
        os.makedirs(self.log_path.parent, exist_ok=True)
        if not self.log_path.exists():
            with open(self.log_path, "w") as f:
                json.dump([], f)

    def _log(self, entry: dict):
        with open(self.log_path, "r") as f:
            logs = json.load(f)
        logs.append(entry)
        with open(self.log_path, "w") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)

    # ── Scanning ─────────────────────────────────────────────────────────

    def scan_all(self) -> list:
        """Run all scanners. Returns list of improvement candidates."""
        findings = []
        findings.extend(self._scan_bare_excepts())
        findings.extend(self._scan_todos())
        findings.extend(self._scan_long_lines())
        findings.extend(self._scan_missing_final_newline())
        return findings

    def _scan_bare_excepts(self) -> list:
        """Find bare 'except:' clauses that should be 'except Exception:'."""
        findings = []
        for f in sorted((BASE_DIR / "actions").glob("*.py")) + sorted((BASE_DIR / "core").glob("*.py")) + [BASE_DIR / "main.py"]:
            if f.stem.startswith("__"):
                continue
            try:
                content = f.read_text(encoding="utf-8")
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ExceptHandler) and node.type is None:
                        findings.append({
                            "type": "bare_except",
                            "file": str(f.relative_to(BASE_DIR)),
                            "line": node.lineno,
                            "severity": "medium",
                            "description": f"Bare except at {f.name}:{node.lineno}",
                            "code": content.split("\n")[node.lineno - 1].strip(),
                            "auto_fixable": True,
                        })
            except (SyntaxError, Exception):
                continue
        return findings

    def _scan_todos(self) -> list:
        """Find TODO/FIXME/HACK comments."""
        findings = []
        pattern = re.compile(r"#\s*(TODO|FIXME|HACK|XXX)", re.IGNORECASE)
        for directory in [BASE_DIR / "actions", BASE_DIR / "core"]:
            for f in sorted(directory.glob("*.py")):
                if f.stem.startswith("__"):
                    continue
                try:
                    content = f.read_text(encoding="utf-8")
                    for i, line in enumerate(content.split("\n"), 1):
                        m = pattern.search(line)
                        if m:
                            findings.append({
                                "type": "todo",
                                "file": str(f.relative_to(BASE_DIR)),
                                "line": i,
                                "severity": "low",
                                "description": f"{m.group(1)} in {f.name}:{i}: {line.strip()[:60]}",
                                "auto_fixable": False,
                            })
                except Exception:
                    continue
        return findings

    def _scan_long_lines(self) -> list:
        """Find lines over 120 chars."""
        findings = []
        for directory in [BASE_DIR / "actions", BASE_DIR / "core"]:
            for f in sorted(directory.glob("*.py")):
                if f.stem.startswith("__"):
                    continue
                try:
                    content = f.read_text(encoding="utf-8")
                    for i, line in enumerate(content.split("\n"), 1):
                        if len(line) > 120 and not line.strip().startswith("#"):
                            findings.append({
                                "type": "long_line",
                                "file": str(f.relative_to(BASE_DIR)),
                                "line": i,
                                "severity": "low",
                                "description": f"Long line ({len(line)} chars) in {f.name}:{i}",
                                "auto_fixable": False,
                            })
                except Exception:
                    continue
        return findings

    def _scan_missing_final_newline(self) -> list:
        """Find files missing final newline."""
        findings = []
        for directory in [BASE_DIR / "actions", BASE_DIR / "core"]:
            for f in sorted(directory.glob("*.py")):
                if f.stem.startswith("__"):
                    continue
                try:
                    content = f.read_bytes()
                    if content and content[-1] != 10:  # no trailing newline
                        findings.append({
                            "type": "missing_newline",
                            "file": str(f.relative_to(BASE_DIR)),
                            "line": 0,
                            "severity": "low",
                            "description": f"No trailing newline in {f.name}",
                            "auto_fixable": True,
                        })
                except Exception:
                    continue
        return findings

    # ── Auto-Fix ─────────────────────────────────────────────────────────

    def apply_fix(self, finding: dict) -> dict:
        """Attempt to auto-fix a finding. Returns result."""
        if not finding.get("auto_fixable"):
            return {"fixed": False, "reason": "Not auto-fixable"}

        if finding["type"] == "bare_except":
            return self._fix_bare_except(finding)

        if finding["type"] == "missing_newline":
            return self._fix_missing_newline(finding)

        return {"fixed": False, "reason": "Unknown fix type"}

    def _fix_bare_except(self, finding: dict) -> dict:
        """Replace bare 'except:' with 'except Exception:'."""
        try:
            filepath = finding["file"]
            line_no = finding["line"]
            abs_path = BASE_DIR / filepath
            content = abs_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            if line_no > len(lines):
                return {"fixed": False, "reason": "Line out of range"}

            old_line = lines[line_no - 1]
            indent = old_line[: len(old_line) - len(old_line.lstrip())]
            new_line = f"{indent}except Exception:"
            lines[line_no - 1] = new_line
            new_content = "\n".join(lines)

            # Validate syntax
            try:
                ast.parse(new_content)
            except SyntaxError as e:
                return {"fixed": False, "reason": f"Syntax error after fix: {e}"}

            # Create backup
            backup = abs_path.with_suffix(abs_path.suffix + ".bak")
            import shutil
            shutil.copy2(abs_path, backup)

            abs_path.write_text(new_content, encoding="utf-8")
            self._log({
                "timestamp": time.time(),
                "action": "fix_bare_except",
                "file": filepath,
                "line": line_no,
                "old": old_line.strip(),
                "new": new_line.strip(),
            })
            return {"fixed": True, "action": f"Fixed bare except in {filepath}:{line_no}"}

        except Exception as e:
            return {"fixed": False, "reason": str(e)}

    def _fix_missing_newline(self, finding: dict) -> dict:
        """Add trailing newline to file."""
        try:
            filepath = finding["file"]
            abs_path = BASE_DIR / filepath
            content = abs_path.read_bytes()
            if content[-1] == 10:
                return {"fixed": False, "reason": "Already has newline"}

            import shutil
            shutil.copy2(abs_path, abs_path.with_suffix(abs_path.suffix + ".bak"))
            abs_path.write_bytes(content + b"\n")
            self._log({
                "timestamp": time.time(),
                "action": "fix_missing_newline",
                "file": filepath,
            })
            return {"fixed": True, "action": f"Added trailing newline to {filepath}"}

        except Exception as e:
            return {"fixed": False, "reason": str(e)}

    # ── Improvement Cycle ────────────────────────────────────────────────

    def run_cycle(self) -> dict:
        """Run one full improvement cycle: scan, fix, verify."""
        self.cycle_count += 1
        cycle_start = time.time()

        findings = self.scan_all()
        auto_fixable = [f for f in findings if f["auto_fixable"]]
        manual = [f for f in findings if not f["auto_fixable"]]

        fixes_applied = []
        fixes_failed = []

        for finding in auto_fixable:
            result = self.apply_fix(finding)
            if result.get("fixed"):
                fixes_applied.append(result["action"])
            else:
                fixes_failed.append({
                    "finding": finding["description"],
                    "reason": result.get("reason", "Unknown"),
                })

        # Verify with test suite
        test_result = {}
        try:
            from core.test_suite import TestSuite
            suite = TestSuite()
            test_result = suite.run_all()
        except Exception as e:
            test_result = {"error": str(e)}

        summary = {
            "cycle": self.cycle_count,
            "timestamp": time.time(),
            "duration": round(time.time() - cycle_start, 1),
            "total_findings": len(findings),
            "auto_fixable": len(auto_fixable),
            "fixes_applied": len(fixes_applied),
            "fixes_failed": len(fixes_failed),
            "tests_passed": test_result.get("passed", 0),
            "tests_failed": test_result.get("failed", 0),
            "tests_total": test_result.get("total", 0),
            "fixes": fixes_applied,
            "failures": fixes_failed,
            "manual_findings": [m["description"] for m in manual[:20]],
        }

        self._log({
            "cycle": self.cycle_count,
            "timestamp": time.time(),
            "summary": summary,
        })

        return summary

    def get_report(self) -> str:
        """Get a human-readable improvement report."""
        with open(self.log_path, "r") as f:
            logs = json.load(f)

        if not logs:
            return "No improvement cycles run yet."

        lines = ["=== SELF-IMPROVEMENT REPORT ===", ""]
        for entry in logs[-5:]:
            s = entry.get("summary", {})
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.get("timestamp", 0)))
            lines.append(f"Cycle #{s.get('cycle', '?')} [{ts}]")
            lines.append(f"  Findings: {s.get('total_findings', 0)} "
                         f"(auto-fixable: {s.get('auto_fixable', 0)})")
            lines.append(f"  Fixes: {s.get('fixes_applied', 0)} applied, "
                         f"{s.get('fixes_failed', 0)} failed")
            lines.append(f"  Tests: {s.get('tests_passed', 0)}/{s.get('tests_total', 0)} passed")
            lines.append(f"  Duration: {s.get('duration', 0)}s")
            for fix in s.get("fixes", []):
                lines.append(f"    [OK] {fix}")
            for fail in s.get("failures", []):
                lines.append(f"    [!!] {fail['finding']}: {fail['reason']}")
            lines.append("")

        return "\n".join(lines)

    def get_log(self, n: int = 20) -> list:
        with open(self.log_path, "r") as f:
            logs = json.load(f)
        return logs[-n:]
