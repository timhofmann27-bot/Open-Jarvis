import json
import subprocess
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "mcp.json"
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_CACHE_TTL_SECONDS = 60
_TOOL_CACHE: dict[tuple[str, bool], tuple[float, list[dict[str, Any]]]] = {}
_ADMIN_TOOLS = {
    "code-mode",
    "mcp-activate-profile",
    "mcp-add",
    "mcp-config-set",
    "mcp-create-profile",
    "mcp-exec",
    "mcp-find",
    "mcp-remove",
    "mcp-discover",
}


def _now() -> float:
    import time
    return time.time()


def _default_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "profile": "jarvis_local",
    }


def read_mcp_config() -> dict[str, Any]:
    config = _default_config()
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                config.update(data)
    except Exception:
        pass
    return config


def mcp_enabled() -> bool:
    return bool(read_mcp_config().get("enabled", True))


def get_mcp_profile() -> str:
    profile = str(read_mcp_config().get("profile", "jarvis_local") or "jarvis_local").strip()
    return profile or "jarvis_local"


def _run_docker_mcp(args: list[str], timeout: int = 90) -> str:
    result = subprocess.run(
        ["docker", "mcp", *args],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=_CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "Docker MCP command failed.").strip()
        raise RuntimeError(msg)
    return (result.stdout or "").strip()


def _gateway_args(profile: str) -> list[str]:
    return [
        "--gateway-arg=--profile",
        f"--gateway-arg={profile}",
    ]


def list_mcp_tools(profile: str | None = None, include_admin: bool = False, refresh: bool = False) -> list[dict[str, Any]]:
    if not mcp_enabled():
        return []

    active_profile = profile or get_mcp_profile()
    cache_key = (active_profile, include_admin)
    cached = _TOOL_CACHE.get(cache_key)
    if cached and not refresh and (_now() - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    raw = _run_docker_mcp([
        "tools",
        "ls",
        *_gateway_args(active_profile),
        "--format=json",
    ])
    tools = json.loads(raw or "[]")
    if not include_admin:
        tools = [t for t in tools if t.get("name") not in _ADMIN_TOOLS]
    _TOOL_CACHE[cache_key] = (_now(), tools)
    return tools


def is_mcp_tool(name: str, profile: str | None = None) -> bool:
    try:
        return any(tool.get("name") == name for tool in list_mcp_tools(profile=profile))
    except Exception:
        return False


def _normalize_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}

    if "anyOf" in schema and isinstance(schema["anyOf"], list):
        for option in schema["anyOf"]:
            if isinstance(option, dict) and option.get("type") != "null":
                merged = dict(option)
                if "description" not in merged and schema.get("description"):
                    merged["description"] = schema["description"]
                return _normalize_schema(merged)

    if isinstance(schema.get("type"), list):
        for item in schema["type"]:
            if item != "null":
                schema = dict(schema)
                schema["type"] = item
                break

    return schema


def _schema_to_gemini(schema: dict[str, Any] | None) -> dict[str, Any]:
    schema = _normalize_schema(schema)
    type_name = str(schema.get("type", "string")).lower()
    mapped_type = {
        "object": "OBJECT",
        "array": "ARRAY",
        "string": "STRING",
        "integer": "INTEGER",
        "number": "NUMBER",
        "boolean": "BOOLEAN",
    }.get(type_name, "STRING")

    out: dict[str, Any] = {"type": mapped_type}
    if schema.get("description"):
        out["description"] = schema["description"]
    if schema.get("enum"):
        out["enum"] = schema["enum"]

    if mapped_type == "OBJECT":
        props = {}
        for key, value in (schema.get("properties") or {}).items():
            props[key] = _schema_to_gemini(value)
        out["properties"] = props
        if schema.get("required"):
            out["required"] = schema["required"]
    elif mapped_type == "ARRAY":
        out["items"] = _schema_to_gemini(schema.get("items") or {"type": "string"})

    return out


def build_mcp_tool_declarations(profile: str | None = None) -> list[dict[str, Any]]:
    try:
        tools = list_mcp_tools(profile=profile)
    except Exception:
        return []

    declarations = []
    for tool in tools:
        params = _schema_to_gemini(tool.get("inputSchema") or {"type": "object", "properties": {}})
        if params.get("type") != "OBJECT":
            params = {"type": "OBJECT", "properties": {}}
        params.setdefault("properties", {})
        declarations.append({
            "name": tool.get("name", ""),
            "description": tool.get("description", "Docker MCP tool"),
            "parameters": params,
        })
    return declarations


def _append_arg_pairs(cmd: list[str], key: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, list):
        for item in value:
            _append_arg_pairs(cmd, key, item)
        return
    if isinstance(value, dict):
        cmd.append(f"{key}={json.dumps(value, ensure_ascii=False)}")
        return
    if isinstance(value, bool):
        cmd.append(f"{key}={'true' if value else 'false'}")
        return
    cmd.append(f"{key}={value}")


def call_mcp_tool(name: str, parameters: dict[str, Any] | None = None, profile: str | None = None) -> str:
    if not mcp_enabled():
        return "Docker MCP ist deaktiviert."

    active_profile = profile or get_mcp_profile()
    params = parameters or {}
    cmd = [
        "tools",
        "call",
        *_gateway_args(active_profile),
        name,
    ]
    for key, value in params.items():
        _append_arg_pairs(cmd, key, value)

    raw = _run_docker_mcp(cmd, timeout=120)
    text = raw.strip()
    if not text:
        return "Done."
    try:
        parsed = json.loads(text)
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    except Exception:
        return text


def get_mcp_prompt_block(profile: str | None = None, max_tools: int = 24) -> str:
    try:
        tools = list_mcp_tools(profile=profile)
    except Exception:
        return ""
    if not tools:
        return ""

    active_profile = profile or get_mcp_profile()
    lines = [f"[DOCKER MCP TOOLS]", f"Active Docker MCP profile: {active_profile}"]
    for tool in tools[:max_tools]:
        name = tool.get("name", "")
        desc = str(tool.get("description", "")).strip().replace("\n", " ")
        lines.append(f"- {name}: {desc}")
    if len(tools) > max_tools:
        lines.append(f"- ... plus {len(tools) - max_tools} weitere MCP-Tools")
    lines.append("")
    return "\n".join(lines)
