import docker
from typing import Any


def _get_client() -> docker.DockerClient | None:
    try:
        return docker.from_env()
    except Exception:
        return None


def docker_list_containers(all_flag: bool = True) -> str:
    client = _get_client()
    if not client:
        return "Docker ist nicht verfügbar."
    try:
        containers = client.containers.list(all=all_flag)
        if not containers:
            return "Keine Container gefunden."
        lines = []
        for c in containers:
            status = c.status
            name = c.name
            image = c.image.tags[0] if c.image.tags else c.image.short_id[:12]
            lines.append(f"{'▶' if status == 'running' else '⏹'} {name} ({image}) – {status}")
        return "Container:\n" + "\n".join(lines)
    except Exception as e:
        return f"Fehler beim Auflisten der Container: {e}"


def docker_start(container_id_or_name: str) -> str:
    client = _get_client()
    if not client:
        return "Docker ist nicht verfügbar."
    try:
        c = client.containers.get(container_id_or_name)
        c.start()
        return f"{c.name} gestartet."
    except Exception as e:
        return f"Konnte Container nicht starten: {e}"


def docker_stop(container_id_or_name: str) -> str:
    client = _get_client()
    if not client:
        return "Docker ist nicht verfügbar."
    try:
        c = client.containers.get(container_id_or_name)
        c.stop()
        return f"{c.name} gestoppt."
    except Exception as e:
        return f"Konnte Container nicht stoppen: {e}"


def docker_restart(container_id_or_name: str) -> str:
    client = _get_client()
    if not client:
        return "Docker ist nicht verfügbar."
    try:
        c = client.containers.get(container_id_or_name)
        c.restart()
        return f"{c.name} neu gestartet."
    except Exception as e:
        return f"Konnte Container nicht neustarten: {e}"


def docker_logs(container_id_or_name: str, tail: int = 20) -> str:
    client = _get_client()
    if not client:
        return "Docker ist nicht verfügbar."
    try:
        c = client.containers.get(container_id_or_name)
        logs = c.logs(tail=tail, timestamps=True).decode("utf-8", errors="replace")
        if not logs.strip():
            return f"Keine Logs für {c.name}."
        lines = logs.strip().split("\n")
        return f"Logs von {c.name} (letzte {len(lines)} Zeilen):\n" + "\n".join(lines)
    except Exception as e:
        return f"Fehler beim Abrufen der Logs: {e}"


def docker_status() -> str:
    client = _get_client()
    if not client:
        return "Docker ist nicht verfügbar."
    try:
        info = client.info()
        running = info.get("ContainersRunning", 0)
        stopped = info.get("ContainersStopped", 0)
        total = info.get("Containers", 0)
        images = info.get("Images", 0)
        version = info.get("ServerVersion", "?")
        return (f"Docker {version} – {total} Container ({running} running, {stopped} stopped), "
                f"{images} Images")
    except Exception as e:
        return f"Fehler beim Abrufen des Docker-Status: {e}"


def execute_docker_command(params: dict[str, Any]) -> str:
    action = params.get("action", "status")
    name_or_id = params.get("container", "")

    if action == "status":
        return docker_status()
    elif action == "list" or action == "ps":
        return docker_list_containers(params.get("all", True))
    elif action == "start":
        if not name_or_id:
            return "Bitte Container-Name oder ID angeben."
        return docker_start(name_or_id)
    elif action == "stop":
        if not name_or_id:
            return "Bitte Container-Name oder ID angeben."
        return docker_stop(name_or_id)
    elif action == "restart":
        if not name_or_id:
            return "Bitte Container-Name oder ID angeben."
        return docker_restart(name_or_id)
    elif action == "logs":
        return docker_logs(name_or_id, params.get("tail", 20))
    else:
        return f"Unbekannte Aktion: {action}. Verfügbar: status, list, start, stop, restart, logs"
