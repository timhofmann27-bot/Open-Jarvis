import argparse
import json
import os
import sys
from urllib.parse import urljoin

import requests


def call_api(url: str, endpoint: str, payload: dict) -> dict:
    full_url = urljoin(url, endpoint)
    headers = {"Content-Type": "application/json"}
    if payload.get("api_token"):
        headers["X-Api-Token"] = payload["api_token"]

    response = requests.post(full_url, json=payload, headers=headers, timeout=60)
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote Jarvis client for home devices.")
    parser.add_argument("--server", default="http://127.0.0.1:8080", help="Jarvis remote server URL.")
    parser.add_argument("--token", default=os.getenv("REMOTE_API_TOKEN"), help="API token for remote server.")
    parser.add_argument("--goal", help="User goal to send to Jarvis.")
    parser.add_argument("--tool", help="Call a specific tool instead of full goal.")
    parser.add_argument("--params", help="JSON string with tool parameters.")
    parser.add_argument("--plan", action="store_true", help="Request a plan for the goal without executing.")
    args = parser.parse_args()

    if not args.goal:
        print("Please provide --goal for command or use --tool with --params.")
        sys.exit(1)

    payload = {"api_token": args.token} if args.token else {}

    if args.plan:
        payload["goal"] = args.goal
        data = call_api(args.server, "/api/plan", payload)
    elif args.tool:
        payload["tool"] = args.tool
        try:
            params = json.loads(args.params) if args.params else {}
        except json.JSONDecodeError as e:
            print(f"Invalid JSON for --params: {e}")
            sys.exit(1)
        payload["parameters"] = params
        data = call_api(args.server, "/api/tool", payload)
    else:
        payload["goal"] = args.goal
        data = call_api(args.server, "/api/command", payload)

    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
