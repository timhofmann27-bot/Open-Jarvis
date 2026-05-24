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
CONFIG_PATH = ROOT_DIR / "config" / "api_keys.json"
STATIC_DIR = ROOT_DIR / "web_ui"


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
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body or "{}")

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

        if path.startswith("/static/"):
            self._serve_static(path.lstrip("/"))
            return

        if path == "/api/status":
            payload = {
                "status": "ok",
                "server": "Jarvis Remote API",
                "version": "1.0",
                "local_ip": get_local_ip(),
                "port": self.server.server_address[1],
                "auth_required": self.server.remote_token is not None,
            }
            self._send_json(200, payload)
            return

        self._send_json(404, {"error": "Endpoint not found."})

    def do_POST(self) -> None:
        try:
            body = self._read_json()
        except json.JSONDecodeError as exc:
            self._send_json(400, {"error": "Invalid JSON body.", "details": str(exc)})
            return

        if not self._check_token(body):
            self._auth_failed()
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
