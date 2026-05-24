import importlib
import importlib.util
import os
import traceback
from pathlib import Path
from typing import Callable

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "plugins"


def _discover_plugins() -> list[dict]:
    plugins = []
    if not PLUGIN_DIR.is_dir():
        PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
        (PLUGIN_DIR / "__init__.py").write_text("")
        return plugins
    for f in sorted(PLUGIN_DIR.iterdir()):
        if f.suffix != ".py" or f.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"plugins.{f.stem}", f)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "plugin_info"):
                info = mod.plugin_info
                info["_file"] = str(f)
                info["_module"] = mod
                plugins.append(info)
        except Exception as e:
            print(f"[PLUGIN] Fehler beim Laden von {f.name}: {e}")
            traceback.print_exc()
    return plugins


def load_plugins() -> tuple[list[dict], dict[str, Callable]]:
    declarations = []
    handlers = {}

    for p in _discover_plugins():
        name = p.get("name", "")
        if not name:
            continue

        decl = {
            "name": name,
            "description": p.get("description", ""),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "_plugin_cmd": {
                        "type": "STRING",
                        "description": p.get("cmd_description", "Freitext-Kommando an das Plugin"),
                    }
                },
            },
        }

        user_params = p.get("parameters", {})
        if isinstance(user_params, dict):
            for k, v in user_params.items():
                decl["parameters"]["properties"][k] = v

        required = p.get("required", [])
        if "_plugin_cmd" not in required:
            required = ["_plugin_cmd"] + required
        decl["parameters"]["required"] = required

        declarations.append(decl)
        handlers[name] = p.get("handler")

    return declarations, handlers
