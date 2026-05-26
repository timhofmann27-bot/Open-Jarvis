import argparse
import json
import mimetypes
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, unquote

from agent.executor import AgentExecutor, _call_tool
from agent.planner import create_plan

ROOT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = ROOT_DIR / "config"
CONFIG_PATH = CONFIG_DIR / "api_keys.json"
STATIC_DIR = ROOT_DIR / "web_ui"

_CONFIG_FILES: dict[str, str] = {
    "api_keys": "api_keys.json",
    "smart_home": "smart_home.json",
    "email": "email.json",
    "telegram": "telegram.json",
    "obsidian": "obsidian.json",
    "proactive": "proactive.json",
    "devices": "devices.json",
    "docker": "docker.json",
    "mcp": "mcp.json",
}


def _read_config(section: str) -> dict:
    filename = _CONFIG_FILES.get(section)
    if not filename:
        return {}
    path = CONFIG_DIR / filename
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_config(section: str, data: dict) -> None:
    filename = _CONFIG_FILES.get(section)
    if not filename:
        return
    path = CONFIG_DIR / filename
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _read_all_configs() -> dict:
    result = {}
    for section in _CONFIG_FILES:
        result[section] = _read_config(section)
    return result


def _save_all_configs(data: dict) -> None:
    for section, values in data.items():
        if section in _CONFIG_FILES and isinstance(values, dict):
            existing = _read_config(section)
            existing.update(values)
            _write_config(section, existing)


def load_remote_token() -> str | None:
    token = os.getenv("REMOTE_API_TOKEN")
    if token:
        return token.strip()

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        token = data.get("remote_api_token")
        if token:
            return str(token).strip()
    except FileNotFoundError:
        pass
    except json.JSONDecodeError:
        pass

    return None


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def guess_mimetype(path: str) -> str:
    mimetype, _ = mimetypes.guess_type(path)
    return mimetype or "application/octet-stream"


def safe_static_path(path: str) -> Path:
    normalized = unquote(path).lstrip("/")
    return (STATIC_DIR / normalized).resolve()


class JarvisRemoteHandler(BaseHTTPRequestHandler):
    server_version = "JarvisRemote/1.0"

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        for enc in ("utf-8", "cp1252", "latin-1"):
            try:
                body = raw.decode(enc)
                return json.loads(body or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        return {}

    def _auth_failed(self) -> None:
        self._send_json(401, {"error": "Unauthorized. Provide a valid api_token."})

    def _serve_static(self, path: str) -> None:
        try:
            target = safe_static_path(path)
        except Exception:
            self._send_json(404, {"error": "Not found."})
            return

        if not target.exists() or not target.is_file() or STATIC_DIR not in target.parents and target != STATIC_DIR:
            self._send_json(404, {"error": "Not found."})
            return

        try:
            content = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", guess_mimetype(str(target)))
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)
        except Exception:
            self._send_json(500, {"error": "Could not read resource."})

    def _check_token(self, data: dict[str, Any]) -> bool:
        expected = self.server.remote_token
        if expected is None:
            return True

        token = data.get("api_token") or self.headers.get("X-Api-Token")
        if token and str(token).strip() == expected:
            return True
        return False

    def _handle_command(self, body: dict[str, Any]) -> None:
        goal = str(body.get("goal", "")).strip()
        if not goal:
            self._send_json(400, {"error": "Missing 'goal' in request body."})
            return

        executor = AgentExecutor()
        try:
            result = executor.execute(goal)
            self._send_json(200, {"status": "ok", "goal": goal, "result": result})
        except Exception as exc:
            self._send_json(500, {
                "error": "Execution failed.",
                "details": str(exc),
            })

    def _handle_plan(self, body: dict[str, Any]) -> None:
        goal = str(body.get("goal", "")).strip()
        if not goal:
            self._send_json(400, {"error": "Missing 'goal' in request body."})
            return

        try:
            plan = create_plan(goal)
            self._send_json(200, {"status": "ok", "goal": goal, "plan": plan})
        except Exception as exc:
            self._send_json(500, {"error": "Plan generation failed.", "details": str(exc)})

    def _handle_tool(self, body: dict[str, Any]) -> None:
        tool = str(body.get("tool", "")).strip()
        params = body.get("parameters", {}) or {}

        if not tool:
            self._send_json(400, {"error": "Missing 'tool' in request body."})
            return

        try:
            result = _call_tool(tool, params, speak=None)
            self._send_json(200, {"status": "ok", "tool": tool, "result": result})
        except Exception as exc:
            self._send_json(500, {"error": "Tool execution failed.", "details": str(exc)})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ["/", "/index.html"]:
            self._serve_static("index.html")
            return

        if path == "/mirror" or path == "/mirror.html":
            self._serve_static("mirror.html")
            return

        if path == "/dashboard" or path == "/dashboard.html":
            self._serve_static("dashboard.html")
            return

        if path == "/jarvis" or path == "/jarvis.html":
            self._serve_static("jarvis.html")
            return

        if path == "/api/config":
            self._send_json(200, _read_all_configs())
            return

        if path.startswith("/static/"):
            self._serve_static(path.lstrip("/"))
            return

        if path == "/api/tv/discover":
            try:
                from actions.tv_control import discover_tvs, _best_device
                tvs = discover_tvs(timeout=3.0)
                best = _best_device(tvs)
                self._send_json(200, {
                    "devices": tvs,
                    "best": best,
                    "count": len(tvs),
                })
            except Exception as exc:
                self._send_json(500, {"error": "TV discovery failed.", "details": str(exc)})
            return

        # ── Docker Endpoints ──
        if path == "/api/docker/status":
            try:
                import docker
                client = docker.from_env()
                info = client.info()
                self._send_json(200, {
                    "connected": True,
                    "version": info.get("ServerVersion", "?"),
                    "containers": info.get("Containers", 0),
                    "running": info.get("ContainersRunning", 0),
                    "paused": info.get("ContainersPaused", 0),
                    "stopped": info.get("ContainersStopped", 0),
                    "images": info.get("Images", 0),
                    "os": info.get("OperatingSystem", "?"),
                    "kernel": info.get("KernelVersion", "?"),
                    "driver": info.get("Driver", "?"),
                })
            except Exception as exc:
                self._send_json(200, {"connected": False, "error": str(exc)})
            return

        if path == "/api/docker/ps":
            try:
                import docker
                client = docker.from_env()
                all_flag = parsed.query and "all=1" in parsed.query
                containers = client.containers.list(all=all_flag)
                data = []
                for c in containers:
                    ports = []
                    if c.ports:
                        for container_port, mappings in c.ports.items():
                            if mappings:
                                for m in mappings:
                                    ports.append(f"{m.get('HostIp','0.0.0.0')}:{m.get('HostPort','?')}->{container_port}")
                            else:
                                ports.append(str(container_port))
                    data.append({
                        "id": c.short_id,
                        "name": c.name,
                        "image": c.image.tags[0] if c.image.tags else c.image.short_id,
                        "status": c.status,
                        "state": c.attrs["State"]["Status"],
                        "ports": ports,
                        "created": c.attrs.get("Created", ""),
                    })
                self._send_json(200, data)
            except Exception as exc:
                self._send_json(500, {"error": "Docker ps failed.", "details": str(exc)})
            return

        if path == "/api/docker/images":
            try:
                import docker
                client = docker.from_env()
                images = client.images.list()
                data = []
                for img in images:
                    data.append({
                        "id": img.short_id,
                        "tags": img.tags or ["<none>"],
                        "size": img.attrs.get("Size", 0),
                        "created": img.attrs.get("Created", ""),
                    })
                self._send_json(200, data)
            except Exception as exc:
                self._send_json(500, {"error": "Docker images failed.", "details": str(exc)})
            return

        # ── Bluetooth Endpoints ──
        if path == "/api/bt/scan":
            try:
                from actions.bt_control import scan_ble
                devices = scan_ble(timeout=8.0)
                tvs = [d for d in devices if d["is_tv"]]
                self._send_json(200, {
                    "devices": devices,
                    "tvs": tvs,
                    "count": len(devices),
                })
            except Exception as exc:
                self._send_json(500, {"error": "BT scan failed.", "details": str(exc)})
            return

        if path == "/api/bt/devices":
            try:
                from actions.bt_control import get_known_devices
                self._send_json(200, get_known_devices())
            except Exception as exc:
                self._send_json(500, {"error": "BT devices failed.", "details": str(exc)})
            return

        if path == "/api/health":
            try:
                from core.self_healer import SelfHealer
                from core.self_modifier import SelfModifier
                sm = SelfModifier()
                healer = SelfHealer(self_modifier=sm)
                health = healer.check_all()
                summary = healer.get_health_summary()
                self._send_json(200, {
                    "health": health,
                    "summary": summary,
                    "log": healer.get_log(20),
                })
            except Exception as exc:
                self._send_json(500, {"error": "Health check failed.", "details": str(exc)})
            return

        if path == "/api/memory/stats":
            try:
                from core.memory_store import get_memory
                mem = get_memory()
                stats = mem.stats
                persona = mem.get_persona_summary()
                self._send_json(200, {
                    "stats": stats,
                    "persona": persona,
                })
            except Exception as exc:
                self._send_json(500, {"error": "Memory stats failed.", "details": str(exc)})
            return

        if path == "/api/proactive/patterns":
            try:
                from core.proactive_intelligence import ProactiveIntelligence
                from core.memory_store import get_memory
                pi = ProactiveIntelligence(memory_store=get_memory())
                pi.analyze_recent()
                report = pi.get_full_report()
                hints = pi.get_context_hints()
                self._send_json(200, {
                    "report": report,
                    "hints": hints,
                    "patterns": pi.cache.get("patterns", {}),
                    "hour_counts": pi.cache.get("hour_counts", {}),
                    "stats": pi.cache.get("stats", {}),
                })
            except Exception as exc:
                self._send_json(500, {"error": "Pattern analysis failed.", "details": str(exc)})
            return

        if path == "/api/tests":
            try:
                from core.test_suite import TestSuite
                suite = TestSuite()
                result = suite.run_all()
                self._send_json(200, {
                    **result,
                    "summary_text": suite.summary_text(),
                })
            except Exception as exc:
                self._send_json(500, {"error": "Tests failed.", "details": str(exc)})
            return

        if path == "/api/modification/log":
            try:
                from core.self_modifier import SelfModifier
                sm = SelfModifier()
                log_path = sm.log_path
                if log_path.exists():
                    import json
                    logs = json.loads(log_path.read_text(encoding="utf-8"))
                    self._send_json(200, {"logs": logs[-50:], "total": len(logs)})
                else:
                    self._send_json(200, {"logs": [], "total": 0})
            except Exception as exc:
                self._send_json(500, {"error": "Modification log failed.", "details": str(exc)})
            return

        if path == "/api/improvements/log":
            try:
                from core.self_improver import SelfImprover
                sm = SelfImprover()
                log_path = sm.log_path
                if log_path.exists():
                    import json
                    logs = json.loads(open(log_path, "r", encoding="utf-8").read())
                    self._send_json(200, {"logs": logs[-20:], "total": len(logs)})
                else:
                    self._send_json(200, {"logs": [], "total": 0})
            except Exception as exc:
                self._send_json(500, {"error": "Improvements read failed.", "details": str(exc)})
            return

        if path == "/api/status":
            # Extended status with tool count
            from core.self_healer import SelfHealer
            from core.self_modifier import SelfModifier
            sm = SelfModifier()
            healer = SelfHealer(self_modifier=sm)
            health = healer.check_all() if healer.health_cache.get("summary", {}).get("all_ok") is not None else healer.check_all()
            source_files = sm.list_sources()
            action_files = [f for f in source_files if f.startswith("actions") and f.endswith(".py")]
            payload = {
                "status": "ok",
                "server": "Jarvis Remote API",
                "version": "4.0",
                "local_ip": get_local_ip(),
                "port": self.server.server_address[1],
                "auth_required": self.server.remote_token is not None,
                "tools": len(action_files),
                "total_files": len(source_files),
                "health": health.get("summary", {}),
                "env": {
                    "python": __import__("sys").version.split()[0],
                    "platform": __import__("sys").platform,
                    "host": __import__("socket").gethostname(),
                },
            }
            self._send_json(200, payload)
            return

        if path == "/api/mcp/tools":
            try:
                from core.mcp_bridge import get_mcp_profile, list_mcp_tools, mcp_enabled
                tools = list_mcp_tools(refresh=True)
                self._send_json(200, {
                    "enabled": mcp_enabled(),
                    "profile": get_mcp_profile(),
                    "count": len(tools),
                    "tools": tools,
                })
            except Exception as exc:
                self._send_json(500, {"error": "MCP tools failed.", "details": str(exc)})
            return

        self._send_json(404, {"error": "Endpoint not found."})

    def do_POST(self) -> None:
        try:
            body = self._read_json()
        except json.JSONDecodeError as exc:
            self._send_json(400, {"error": "Invalid JSON body.", "details": str(exc)})
            return

        # TV endpoints are auth-free (local network)
        if self.path == "/api/tv/connect":
            try:
                from actions.tv_control import _attempt_dial_launch
                ip = body.get("ip", "")
                if not ip:
                    self._send_json(400, {"error": "Missing 'ip' in body."})
                    return
                target_url = f"http://{get_local_ip()}:8080/jarvis"
                ok = _attempt_dial_launch(ip, target_url)
                if ok:
                    # save as last connected TV
                    dev = _read_config("devices")
                    dev["last_tv"] = {"ip": ip, "name": body.get("name", ip), "connected_at": __import__("time").time()}
                    _write_config("devices", dev)
                    self._send_json(200, {"status": "ok", "connected": True, "ip": ip})
                else:
                    self._send_json(200, {"status": "ok", "connected": False, "ip": ip})
            except Exception as exc:
                self._send_json(500, {"error": "TV connect failed.", "details": str(exc)})
            return

        # Docker container actions (auth-free, local)
        if self.path.startswith("/api/docker/"):
            try:
                import docker
                client = docker.from_env()
                action = self.path.replace("/api/docker/", "")
                if action.startswith("start/"):
                    cid = action.split("/", 1)[1]
                    c = client.containers.get(cid)
                    c.start()
                    self._send_json(200, {"status": "ok", "action": "start", "container": cid, "state": "running"})
                elif action.startswith("stop/"):
                    cid = action.split("/", 1)[1]
                    c = client.containers.get(cid)
                    c.stop()
                    self._send_json(200, {"status": "ok", "action": "stop", "container": cid, "state": "stopped"})
                elif action.startswith("restart/"):
                    cid = action.split("/", 1)[1]
                    c = client.containers.get(cid)
                    c.restart()
                    self._send_json(200, {"status": "ok", "action": "restart", "container": cid, "state": "running"})
                elif action.startswith("logs/"):
                    cid = action.split("/", 1)[1]
                    c = client.containers.get(cid)
                    logs = c.logs(tail=100, timestamps=True).decode("utf-8", errors="replace")
                    self._send_json(200, {"status": "ok", "container": cid, "logs": logs})
                else:
                    self._send_json(404, {"error": f"Unknown docker action: {action}"})
            except Exception as exc:
                self._send_json(500, {"error": "Docker action failed.", "details": str(exc)})
            return

        # Bluetooth actions (auth-free, local)
        if self.path == "/api/bt/connect":
            try:
                from actions.bt_control import wake_tv
                address = body.get("address", "")
                if not address:
                    self._send_json(400, {"error": "Missing 'address' in body."})
                    return
                result = wake_tv(address)
                if result["success"]:
                    name = result.get("name", address)
                    method = result.get("method", "?")
                    tv = _read_config("devices")
                    tv["last_tv"] = {"ip": "", "name": name, "bt_address": address, "connected_at": __import__("time").time(), "method": method}
                    _write_config("devices", tv)
                    self._send_json(200, {"status": "ok", "connected": True, "name": name, "address": address, "method": method})
                else:
                    self._send_json(200, {"status": "ok", "connected": False, "error": result.get("error")})
            except Exception as exc:
                self._send_json(500, {"error": "BT connect failed.", "details": str(exc)})
            return

        if self.path == "/api/bt/disconnect":
            try:
                from actions.bt_control import disconnect_device
                address = body.get("address", "")
                if not address:
                    self._send_json(400, {"error": "Missing 'address' in body."})
                    return
                result = disconnect_device(address)
                if result["success"]:
                    self._send_json(200, {"status": "ok", "disconnected": True, "address": address})
                else:
                    self._send_json(200, {"status": "ok", "disconnected": False, "error": result.get("error")})
            except Exception as exc:
                self._send_json(500, {"error": "BT disconnect failed.", "details": str(exc)})
            return

        if self.path == "/api/bt/save":
            try:
                from actions.bt_control import _save_bt_device
                address = body.get("address", "")
                name = body.get("name", address or "Unbekannt")
                dtype = body.get("type", "tv")
                if not address:
                    self._send_json(400, {"error": "Missing 'address' in body."})
                    return
                _save_bt_device(address, name, dtype)
                self._send_json(200, {"status": "ok", "saved": True, "name": name})
            except Exception as exc:
                self._send_json(500, {"error": "BT save failed.", "details": str(exc)})
            return

        if self.path == "/api/wireless-display":
            try:
                from actions.bt_control import open_wireless_display
                ok = open_wireless_display()
                if ok:
                    self._send_json(200, {"status": "ok", "opened": True})
                else:
                    self._send_json(500, {"error": "Konnte Connect-Fenster nicht öffnen."})
            except Exception as exc:
                self._send_json(500, {"error": "Wireless display failed.", "details": str(exc)})
            return

        if not self._check_token(body):
            self._auth_failed()
            return

        if self.path == "/api/config":
            try:
                _save_all_configs(body)
                self._send_json(200, {"status": "ok", "saved": list(body.keys())})
            except Exception as exc:
                self._send_json(500, {"error": "Config save failed.", "details": str(exc)})
            return

        if self.path == "/api/command":
            self._handle_command(body)
            return
        if self.path == "/api/plan":
            self._handle_plan(body)
            return
        if self.path == "/api/tool":
            self._handle_tool(body)
            return

        self._send_json(404, {"error": "Endpoint not found."})

    def log_message(self, format: str, *args: Any) -> None:
        # suppress default console spam
        return


class JarvisRemoteServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, remote_token=None):
        super().__init__(server_address, RequestHandlerClass)
        self.remote_token = remote_token


def start_remote_server(host: str = "0.0.0.0", port: int = 8080, token: str | None = None, daemon: bool = True) -> JarvisRemoteServer:
    server = JarvisRemoteServer((host, port), JarvisRemoteHandler, remote_token=token)
    thread = threading.Thread(target=server.serve_forever, daemon=daemon)
    thread.start()
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Jarvis remote API server.")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to.")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on.")
    parser.add_argument("--token", default=None, help="Optional API token for remote access.")
    args = parser.parse_args()

    token = args.token or load_remote_token()
    if token:
        print("[RemoteServer] API token enabled.")
    else:
        print("[RemoteServer] WARNING: remote API running without authentication.")

    server = JarvisRemoteServer((args.host, args.port), JarvisRemoteHandler, remote_token=token)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print(f"[RemoteServer] Listening on http://{args.host}:{args.port}")
    print("[RemoteServer] Endpoints: /api/status, /api/plan, /api/command, /api/tool")
    print("Press CTRL+C to stop.")

    try:
        thread.join()
    except KeyboardInterrupt:
        print("\n[RemoteServer] Shutting down...")
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
