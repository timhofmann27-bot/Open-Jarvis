"""
Self-Modification Engine for JARVIS.
Allows AI to read, write, edit, validate and explore its own source code.
All operations are restricted to the project directory and create backups.
"""
import ast
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


class SelfModifier:
    """Engine for JARVIS self-modification capabilities."""

    def __init__(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.actions_dir = self.project_root / "actions"
        self.core_dir = self.project_root / "core"
        self.tv_dir = self.project_root / "tv_interface"
        self.web_ui_dir = self.project_root / "web_ui"
        self.main_py = self.project_root / "main.py"
        self.log_path = self.project_root / "memory" / "self_modifications.json"
        self._init_log()

    def _init_log(self):
        os.makedirs(self.log_path.parent, exist_ok=True)
        if not self.log_path.exists():
            with open(self.log_path, "w") as f:
                json.dump([], f)

    def _log(self, action_type: str, details: dict):
        with open(self.log_path, "r") as f:
            logs = json.load(f)
        logs.append({
            "timestamp": datetime.now().isoformat(),
            "type": action_type,
            "details": details,
        })
        with open(self.log_path, "w") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)

    def _resolve(self, relative_path: str) -> Path:
        resolved = (self.project_root / relative_path).resolve()
        if not str(resolved).startswith(str(self.project_root)):
            raise PermissionError(f"Access denied: {relative_path} is outside project root")
        return resolved

    def list_sources(self) -> list:
        """List all project source files (py, json, html, css, js)."""
        files = []
        extensions = ["*.py", "*.json", "*.html", "*.css", "*.js", "*.md"]
        exclude_dirs = {"__pycache__", ".git", ".venv", "node_modules", "__pycache__"}
        for ext in extensions:
            for f in sorted(self.project_root.rglob(ext)):
                if any(part in exclude_dirs for part in f.relative_to(self.project_root).parts):
                    continue
                files.append(str(f.relative_to(self.project_root)))
        return files

    def read_source(self, relative_path: str) -> dict:
        """Read a source file. Returns {'content': str, 'path': str, 'size': int}."""
        abs_path = self._resolve(relative_path)
        if not abs_path.exists():
            return {"error": f"File not found: {relative_path}"}
        content = abs_path.read_text(encoding="utf-8")
        return {
            "content": content,
            "path": str(abs_path),
            "size": len(content),
            "lines": content.count("\n") + 1,
            "ext": abs_path.suffix,
        }

    def validate_syntax(self, code: str, language: str = "python") -> dict:
        """Check syntax validity of code."""
        if language == "python":
            try:
                tree = ast.parse(code)
                issues = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.ExceptHandler) and node.type is None:
                        issues.append({
                            "line": getattr(node, "lineno", 0),
                            "message": "Bare except clause",
                            "severity": "warning",
                        })
                    if isinstance(node, ast.Try) and not node.handlers and not node.finalbody:
                        issues.append({
                            "line": getattr(node, "lineno", 0),
                            "message": "Empty try block",
                            "severity": "warning",
                        })
                return {"valid": True, "issues": issues}
            except SyntaxError as e:
                return {"valid": False, "error": str(e), "lineno": e.lineno, "offset": e.offset}
        return {"valid": True, "issues": []}

    def write_new_file(self, relative_path: str, content: str) -> dict:
        """Write a brand new file. Will NOT overwrite existing files."""
        abs_path = self._resolve(relative_path)
        if abs_path.exists():
            return {
                "success": False,
                "error": f"File already exists: {relative_path}. Use edit_code to modify it.",
            }
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        if abs_path.suffix == ".py":
            validation = self.validate_syntax(content)
            if not validation["valid"]:
                return {
                    "success": False,
                    "error": f"Syntax error in new file: {validation['error']} (line {validation.get('lineno')})",
                    "validation": validation,
                }

        abs_path.write_text(content, encoding="utf-8")
        self._log("write_new_file", {"file": relative_path, "size": len(content)})
        return {
            "success": True,
            "path": str(abs_path),
            "relative_path": relative_path,
            "size": len(content),
            "validation": validation if abs_path.suffix == ".py" else {"valid": True, "issues": []},
        }

    def edit_code(self, relative_path: str, old_string: str, new_string: str) -> dict:
        """Surgically replace old_string with new_string. Creates backup, validates syntax."""
        abs_path = self._resolve(relative_path)
        if not abs_path.exists():
            return {"success": False, "error": f"File not found: {relative_path}"}

        content = abs_path.read_text(encoding="utf-8")

        if old_string not in content:
            return {"success": False, "error": "old_string not found in file. Check exact whitespace."}

        occurrences = content.count(old_string)
        if occurrences > 1:
            return {
                "success": False,
                "error": f"old_string found {occurrences} times. Provide more surrounding context to make it unique.",
                "occurrences": occurrences,
            }

        new_content = content.replace(old_string, new_string, 1)

        if abs_path.suffix == ".py":
            validation = self.validate_syntax(new_content)
            if not validation["valid"]:
                return {
                    "success": False,
                    "error": f"Syntax error after edit: {validation['error']}",
                    "validation": validation,
                }

        backup_path = abs_path.with_suffix(abs_path.suffix + ".bak")
        shutil.copy2(abs_path, backup_path)

        abs_path.write_text(new_content, encoding="utf-8")
        self._log("edit_code", {
            "file": relative_path,
            "old_len": len(old_string),
            "new_len": len(new_string),
        })
        return {
            "success": True,
            "backup": str(backup_path.relative_to(self.project_root)),
            "message": f"Edit applied to {relative_path}. Backup at {backup_path.name}",
        }

    def generate_tool_module(self, name: str, description: str, function_code: str, imports: str = "") -> dict:
        """Generate a complete new tool module in actions/. Returns the plan."""
        filepath = self.actions_dir / f"{name}.py"
        if filepath.exists():
            return {"error": f"Tool already exists: {name}.py"}

        module_code = f'''"""
{description}
"""
import asyncio
import json
import os
import subprocess
import sys

{imports}


{function_code}
'''
        validation = self.validate_syntax(module_code)
        if not validation["valid"]:
            return {"error": f"Syntax error: {validation['error']}", "validation": validation}

        return {
            "module_code": module_code,
            "filepath": str(filepath),
            "relative_path": f"actions/{name}.py",
            "validation": validation,
            "instructions": [
                f"Write new file: actions/{name}.py",
                f"Add import to main.py: from actions.{name} import <function_name>",
                "Add tool declaration to TOOL_DECLARATIONS",
                "Add elif handler in _execute_tool",
            ],
        }

    def dry_run(self, code: str) -> dict:
        """Run code syntax and basic safety checks."""
        issues = []

        dangerous = ["os.system(", "subprocess.call(", "shutil.rmtree(", "os.remove("]
        for d in dangerous:
            if d in code:
                issues.append({"severity": "warning", "message": f"Contains potentially dangerous call: {d}"})

        if "import sys" in code:
            issues.append({"severity": "info", "message": "Imports sys"})

        validation = self.validate_syntax(code)
        issues.extend(validation.get("issues", []))

        return {"valid": validation["valid"], "issues": issues}
