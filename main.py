import asyncio
import threading
import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import sounddevice as sd
from google import genai
from google.genai import types
from ui import JarvisUI
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
    should_extract_memory, extract_memory
)

import remote_server
from tv_interface.tv_server import TVServer
from actions.file_processor import file_processor
from actions.flight_finder     import flight_finder
from actions.open_app          import open_app
from actions.weather_report    import weather_action
from actions.send_message      import send_message
from actions.reminder          import reminder
from actions.computer_settings import computer_settings
from actions.screen_processor  import screen_process
from actions.youtube_video     import youtube_video
from actions.desktop           import desktop_control
from actions.browser_control   import browser_control
from actions.file_controller   import file_controller
from actions.code_helper       import code_helper
from actions.dev_agent         import dev_agent
from actions.tv_control        import connect_tv
from actions.web_search        import web_search as web_search_action
from actions.computer_control  import computer_control
from actions.game_updater      import game_updater
from actions.smart_home        import smart_home
from actions.worldmonitor      import worldmonitor_action
from actions.computer_use      import computer_use_action
from actions.ytmusic           import ytmusic_action
from actions.system_integration import system_integration_action
from actions.generative_graphics import generative_graphics_action
from actions.hyper_connectivity import hyper_connectivity_action
from actions.obsidian_control  import obsidian_action
from actions.email_calendar    import email_action
from core.plugin_loader       import load_plugins
from core.mcp_bridge          import (
    build_mcp_tool_declarations,
    call_mcp_tool,
    get_mcp_prompt_block,
)
from core.notifier            import ProactiveNotifier
from core.memory_store        import get_memory, MemoryStore
from core.reflector           import get_reflector, Reflector
from core.self_modifier      import SelfModifier
from core.proactive_intelligence import ProactiveIntelligence
from core.self_healer         import SelfHealer
from core.self_improver       import SelfImprover


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024


def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are JARVIS, Tony Stark's AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )
    
_last_memory_input = ""

def _update_memory_async(user_text: str, jarvis_text: str) -> None:
    global _last_memory_input

    user_text   = (user_text   or "").strip()
    jarvis_text = (jarvis_text or "").strip()

    if len(user_text) < 5 or user_text == _last_memory_input:
        return
    _last_memory_input = user_text

    try:
        api_key = _get_api_key()
        if not should_extract_memory(user_text, jarvis_text, api_key):
            return
        data = extract_memory(user_text, jarvis_text, api_key)
        if data:
            update_memory(data)
            print(f"[Memory] OK {list(data.keys())}")
    except Exception as e:
        if "429" not in str(e):
            print(f"[Memory] WARN {e}")

TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": (
            "Opens any application on the Windows computer. "
            "Use this whenever the user asks to open, launch, or start any app, "
            "website, or program. Always call this tool — never just say you opened it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Search query"},
                "mode":   {"type": "STRING", "description": "search (default) or compare"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
                "aspect": {"type": "STRING", "description": "price | specs | reviews"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "weather_report",
        "description": "Gives the weather report to user",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, or other messaging platform.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform":     {"type": "STRING", "description": "Platform: WhatsApp, Telegram, etc."}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "network_status",
        "description": "Checks internet connectivity, DNS resolution, ping reachability, and HTTP access for a host or URL.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target": {"type": "STRING", "description": "Host or URL to check (default: google.com)."},
                "check":  {"type": "STRING", "description": "Which check to perform: all | dns | ping | http | probe."}
            },
            "required": []
        }
    },
    {
        "name": "connect_tv",
        "description": "Opens Windows Wireless Display (Win+K) and the 3D Iron Man JARVIS interface in the browser. Use for connecting to a TV or external display.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "worldmonitor",
        "description": "ÖFFNET DIE WORLD MONITOR WEBAPP (Weltkarte für Echtzeit-Konflikte, Militär, Atomwaffen, Naturkatastrophen, Wetter). Rufe dieses Tool auf wenn der Nutzer nach Weltlage, globalen Konflikten, aktuellen Krisen, Kriegen, Militärbasen, atomaren Aktivitäten, Sanktionen, Wetterextremen, Naturkatastrophen, Wirtschaftsdaten oder geopolitischen Ereignissen fragt. Actions: 'analyze' (Default: öffnet + Text + Karten-Vision), 'crisis_report' (mehrere Krisen-Layer analysieren), 'click_layer' (Layer anklicken und neu analysieren wie 'Conflicts'), 'get_text' (Text lesen), 'scroll', 'open'.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "'analyze' (default) öffnet mit Krisen-Layern, liest Text und analysiert Karte per Gemini Vision. 'crisis_report' erstellt strukturierten Krisenreport mit allen relevanten Layern. 'click_layer' klickt einen bestimmten Layer an (z.B. 'Conflicts', 'Nuclear', 'Weather', 'Hotspots', 'Bases') und analysiert die aktualisierte Karte. 'get_text' liest sichtbaren Text. 'scroll' scrollt. 'open' öffnet nur die App."
                },
                "target": {
                    "type": "STRING",
                    "description": "Für action='click_layer': der sichtbare Name des Layer-Toggles (z.B. 'Conflicts', 'Nuclear', 'Weather', 'Hotspots', 'Bases', 'Military', 'Sanctions')."
                },
                "layers": {
                    "type": "STRING",
                    "description": "Komma-getrennte Layer-Namen für die URL. Default: 'conflicts,nuclear,hotspots,military,natural'. Verfügbar: conflicts, bases, hotspots, nuclear, sanctions, weather, economic, waterways, outages, military, natural, iranAttacks."
                },
                "focus": {
                    "type": "STRING",
                    "description": "Optionaler Fokus für die Vision-Analyse, z.B. 'Ukraine', 'Middle East', 'Africa', 'Nuclear threats'."
                },
                "direction": {
                    "type": "STRING",
                    "description": "Für action='scroll': 'down' oder 'up'."
                }
            },
            "required": []
        }
    },
    {
        "name": "computer_use",
        "description": "AUTONOME COMPUTER-STEUERUNG PER VISION. JARVIS sieht den Bildschirm, analysiert was zu sehen ist, klickt auf Buttons, tippt Text, scrollt – alles selbstständig. Rufe DIESES Tool für ALLE Aufgaben die mehrere Schritte erfordern: Installation von Programmen, Bedienung von Webseiten, Konfiguration von Einstellungen, Dateiverwaltung, Recherche, Ausfüllen von Formularen. Der Nutzer sagt was er will, JARVIS macht es am PC.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task": {
                    "type": "STRING",
                    "description": "Die Aufgabe die JARVIS am Computer erledigen soll, z.B. 'Öffne WorldMonitor und klicke auf den Conflicts Layer' oder 'Installiere Discord von der offiziellen Webseite'."
                },
                "max_steps": {
                    "type": "NUMBER",
                    "description": "Maximale Anzahl Schritte (default: 8, mehr bei komplexen Aufgaben)."
                }
            },
            "required": ["task"]
        }
    },
    {
        "name": "system_integration",
        "description": "TIEFENINTEGRATION IN WINDOWS. Steuere das System auf niedriger Ebene: Systeminfo, Prozesse, Dienste, Registry, Energiepläne, Desktop, Umgebungsvariablen, Autostart, Netzwerk. Rufe DIESES Tool für alles was mit Windows-Systemverwaltung zu tun hat.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "'info' (CPU/RAM/OS), 'process_list' (Prozesse), 'process_kill' (Namen oder PID), 'process_start' (Programm starten), 'service_list', 'service_control' mit target=Dienstname + value=start/stop/restart, 'registry_read' mit target=HKLM\\..., 'registry_write', 'power_plan' (list/set), 'power_setting' (screen/sleep/hibernate), 'wallpaper' mit target=Dateipfad, 'env_var' (get/set/delete), 'startup' (list/add/remove), 'disk', 'network', 'display' (info/resolution/theme dark/light)."
                },
                "target": {
                    "type": "STRING",
                    "description": "Ziel der Aktion: Prozessname, PID, Service-Name, Registry-Pfad, Planname, Variablenname, Dateipfad, Bildschirmauflösung (z.B. '1920x1080'), 'dark'/'light' für Theme."
                },
                "value": {
                    "type": "STRING",
                    "description": "Wert: Minuten für power_setting, start/stop/restart für service_control, neuer Wert für registry_write/env_var/set, URL für wallpaper, 'fill'/'fit'/'stretch' für wallpaper style, action für startup (list/add/remove)."
                },
                "mode": {
                    "type": "STRING",
                    "description": "Sortierung für process_list ('cpu'/'mem'), Typ für registry_write ('SZ'/'DWORD'), scope für env_var ('user'/'machine')."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "generative_graphics",
        "description": "GENERIERT VISUALISIERUNGEN, CHARTS, 3D-SZENEN UND BILDER ON THE FLY. JARVIS erstellt auf Kommando: Chart-Diagramme (bar/line/pie/doughnut), interaktive 3D-Szenen (Arc Reactor, Particle Field, Wireframe Globe, Data Tower), Netzwerk-Diagramme, prozedurale Bilder. Die Visualisierung wird automatisch im Browser geöffnet.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "'chart' (Diagramm), 'scene_3d' / '3d' (3D-Szene), 'diagram' / 'network_diagram' (Netzwerk-Diagramm), 'image' (Bild), 'preview_scenes' (alle 3D-Szenen)."
                },
                "chart_type": {
                    "type": "STRING",
                    "description": "Für action='chart': 'bar', 'line', 'pie', 'doughnut', 'radar', 'polarArea'."
                },
                "title": {
                    "type": "STRING",
                    "description": "Titel der Visualisierung."
                },
                "labels": {
                    "type": "STRING",
                    "description": "Für action='chart': Komma-getrennte Label, z.B. 'Jan,Feb,Mar,Apr'."
                },
                "values": {
                    "type": "STRING",
                    "description": "Für action='chart': Komma-getrennte Zahlenwerte, z.B. '30,45,60,25'."
                },
                "scene_type": {
                    "type": "STRING",
                    "description": "Für action='scene_3d': 'arc_reactor' (Default), 'particle_field', 'wireframe_globe', 'data_tower'."
                },
                "style": {
                    "type": "STRING",
                    "description": "Für action='image': 'arc_reactor', 'hologram', 'data_dashboard'."
                },
                "nodes": {
                    "type": "STRING",
                    "description": "Für action='diagram': JSON-Array von Knoten, z.B. '[{\"id\":\"pc1\",\"x\":0,\"y\":0,\"z\":0,\"color\":\"#00d4ff\"}]'."
                },
                "connections": {
                    "type": "STRING",
                    "description": "Für action='diagram': JSON-Array von Verbindungen, z.B. '[[\"pc1\",\"server1\"]]'."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "hyper_connectivity",
        "description": "VERBINDET JARVIS MIT EXTERNEN DIENSTEN: Spotify (Musik steuern, suchen, Playlists) und GitHub (Repos, Issues, PRs, Commits). Rufe dieses Tool auf wenn der Nutzer nach Spotify, GitHub, Musikwiedergabe, Repository-Verwaltung oder Code-Entwicklung fragt.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "service": {
                    "type": "STRING",
                    "description": "'spotify' oder 'github'."
                },
                "action": {
                    "type": "STRING",
                    "description": "Spotify: 'current' (aktueller Track), 'play', 'pause', 'next', 'previous', 'search' (mit query), 'play_track' (Titel abspielen), 'playlist', 'devices'. GitHub: 'user' (Profil), 'repos', 'issues' (mit repo), 'create_issue' (mit repo+issue_title), 'prs', 'commits'."
                },
                "query": {
                    "type": "STRING",
                    "description": "Suchbegriff für Spotify search/play_track."
                },
                "repo": {
                    "type": "STRING",
                    "description": "Repository für GitHub (z.B. 'user/repo')."
                },
                "issue_title": {
                    "type": "STRING",
                    "description": "Titel für GitHub create_issue."
                },
                "issue_body": {
                    "type": "STRING",
                    "description": "Body für GitHub create_issue."
                }
            },
            "required": ["service", "action"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder using Windows Task Scheduler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date":    {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time":    {"type": "STRING", "description": "Time in HH:MM format (24h)"},
                "message": {"type": "STRING", "description": "Reminder message text"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
        "name": "youtube_video",
        "description": (
            "Controls YouTube. Use for: playing videos, summarizing a video's content, "
            "getting video info, or showing trending videos."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | summarize | get_info | trending (default: play)"},
                "query":  {"type": "STRING", "description": "Search query for play action"},
                "save":   {"type": "BOOLEAN", "description": "Save summary to Notepad (summarize only)"},
                "region": {"type": "STRING", "description": "Country code for trending e.g. TR, US"},
                "url":    {"type": "STRING", "description": "Video URL for get_info action"},
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures and analyzes the screen or webcam image. "
            "MUST be called when user asks what is on screen, what you see, "
            "analyze my screen, look at camera, etc. "
            "You have NO visual ability without this tool. "
            "After calling this tool, stay SILENT — the vision module speaks directly."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "computer_settings",
        "description": (
            "Controls the computer: volume, brightness, window management, keyboard shortcuts, "
            "typing text on screen, closing apps, fullscreen, dark mode, WiFi, restart, shutdown, "
            "scrolling, tab management, zoom, screenshots, lock screen, refresh/reload page. "
            "Use for ANY single computer control command. NEVER route to agent_task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "The action to perform"},
                "description": {"type": "STRING", "description": "Natural language description of what to do"},
                "value":       {"type": "STRING", "description": "Optional value: volume level, text to type, etc."}
            },
            "required": []
        }
    },
    {
        "name": "browser_control",
        "description": (
            "Controls the web browser. Use for: opening websites, searching the web, "
            "clicking elements, filling forms, scrolling, any web-based task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to | search | click | type | scroll | fill_form | smart_click | smart_type | get_text | press | close"},
                "url":         {"type": "STRING", "description": "URL for go_to action"},
                "query":       {"type": "STRING", "description": "Search query for search action"},
                "selector":    {"type": "STRING", "description": "CSS selector for click/type"},
                "text":        {"type": "STRING", "description": "Text to click or type"},
                "description": {"type": "STRING", "description": "Element description for smart_click/smart_type"},
                "direction":   {"type": "STRING", "description": "up or down for scroll"},
                "key":         {"type": "STRING", "description": "Key name for press action"},
                "incognito":   {"type": "BOOLEAN", "description": "Open in private/incognito mode"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "Manages files and folders: list, create, delete, move, copy, rename, read, write, find, disk usage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | organize_desktop | info"},
                "path":        {"type": "STRING", "description": "File/folder path or shortcut: desktop, downloads, documents, home"},
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name":    {"type": "STRING", "description": "New name for rename"},
                "content":     {"type": "STRING", "description": "Content for create_file/write"},
                "name":        {"type": "STRING", "description": "File name to search for"},
                "extension":   {"type": "STRING", "description": "File extension to search (e.g. .pdf)"},
                "count":       {"type": "INTEGER", "description": "Number of results for largest"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controls the desktop: wallpaper, organize, clean, list, stats.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                "path":   {"type": "STRING", "description": "Image path for wallpaper"},
                "url":    {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type or by_date for organize"},
                "task":   {"type": "STRING", "description": "Natural language desktop task"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, runs, or builds code files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | edit | explain | run | build | auto (default: auto)"},
                "description": {"type": "STRING", "description": "What the code should do or what change to make"},
                "language":    {"type": "STRING", "description": "Programming language (default: python)"},
                "output_path": {"type": "STRING", "description": "Where to save the file"},
                "file_path":   {"type": "STRING", "description": "Path to existing file for edit/explain/run/build"},
                "code":        {"type": "STRING", "description": "Raw code string for explain"},
                "args":        {"type": "STRING", "description": "CLI arguments for run/build"},
                "timeout":     {"type": "INTEGER", "description": "Execution timeout in seconds (default: 30)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete multi-file projects from scratch: plans, writes files, installs deps, opens VSCode, runs and fixes errors.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING", "description": "What the project should do"},
                "language":     {"type": "STRING", "description": "Programming language (default: python)"},
                "project_name": {"type": "STRING", "description": "Optional project folder name"},
                "timeout":      {"type": "INTEGER", "description": "Run timeout in seconds (default: 30)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "agent_task",
        "description": (
            "Executes complex multi-step tasks requiring multiple different tools. "
            "Examples: 'research X and save to file', 'find and organize files'. "
            "DO NOT use for single commands. NEVER use for Steam/Epic — use game_updater."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal":     {"type": "STRING", "description": "Complete description of what to accomplish"},
                "priority": {"type": "STRING", "description": "low | normal | high (default: normal)"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, click, hotkeys, scroll, move mouse, screenshots, find elements on screen.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"},
                "text":        {"type": "STRING", "description": "Text to type or paste"},
                "x":           {"type": "INTEGER", "description": "X coordinate"},
                "y":           {"type": "INTEGER", "description": "Y coordinate"},
                "keys":        {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
                "key":         {"type": "STRING", "description": "Single key e.g. 'enter'"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Seconds to wait"},
                "title":       {"type": "STRING",  "description": "Window title for focus_window"},
                "description": {"type": "STRING",  "description": "Element description for screen_find/screen_click"},
                "type":        {"type": "STRING",  "description": "Data type for random_data"},
                "field":       {"type": "STRING",  "description": "Field for user_data: name|email|city"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
                "path":        {"type": "STRING",  "description": "Save path for screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": (
            "THE ONLY tool for ANY Steam or Epic Games request. "
            "Use for: installing, downloading, updating games, listing installed games, "
            "checking download status, scheduling updates. "
            "ALWAYS call directly for any Steam/Epic/game request. "
            "NEVER use agent_task, browser_control, or web_search for Steam/Epic."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING",  "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status (default: update)"},
                "platform":  {"type": "STRING",  "description": "steam | epic | both (default: both)"},
                "game_name": {"type": "STRING",  "description": "Game name (partial match supported)"},
                "app_id":    {"type": "STRING",  "description": "Steam AppID for install (optional)"},
                "hour":      {"type": "INTEGER", "description": "Hour for scheduled update 0-23 (default: 3)"},
                "minute":    {"type": "INTEGER", "description": "Minute for scheduled update 0-59 (default: 0)"},
                "shutdown_when_done": {"type": "BOOLEAN", "description": "Shut down PC when download finishes"},
            },
            "required": []
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING",  "description": "Departure city or airport code"},
                "destination": {"type": "STRING",  "description": "Arrival city or airport code"},
                "date":        {"type": "STRING",  "description": "Departure date (any format)"},
                "return_date": {"type": "STRING",  "description": "Return date for round trips"},
                "passengers":  {"type": "INTEGER", "description": "Number of passengers (default: 1)"},
                "cabin":       {"type": "STRING",  "description": "economy | premium | business | first"},
                "save":        {"type": "BOOLEAN", "description": "Save results to Notepad"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "ytmusic",
        "description": (
            "Steuert YouTube Music. Aktionen: play (Song suchen und abspielen), "
            "search, pause, resume, next, previous, volume (0-100), open. "
            "Immer dieses Tool fuer Musikwünsche nutzen."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | search | pause | resume | next | previous | volume | open"},
                "query":  {"type": "STRING", "description": "Songtitel oder Suchbegriff fuer play/search, oder Lautstaerke 0-100 fuer volume"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "email",
        "description": (
            "E-Mail und Kalender Aktionen: list/inbox (letzte 5 Mails), "
            "send (E-Mail senden, Parameter: to, subject, body), "
            "calendar/termine (naechste Termine aus Outlook). "
            "Fuer E-Mails und Kalender nutzen."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":  {"type": "STRING", "description": "list | inbox | send | calendar | termine"},
                "to":      {"type": "STRING", "description": "Empfaenger fuer send"},
                "subject": {"type": "STRING", "description": "Betreff fuer send"},
                "body":    {"type": "STRING", "description": "Inhalt fuer send"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "obsidian",
        "description": (
            "Steuert Obsidian. Aktionen: open (Obsidian oeffnen), search (Notizen durchsuchen), "
            "note/create (neue Notiz), append (anhaengen), read (lesen), list (letzte 10). "
            "Immer fuer Notizen und Obsidian nutzen."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":  {"type": "STRING", "description": "open | search | note | create | write | append | read | list"},
                "query":   {"type": "STRING", "description": "Suchbegriff fuer search"},
                "note":    {"type": "STRING", "description": "Notizname (ohne .md)"},
                "content": {"type": "STRING", "description": "Inhalt fuer create/append"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "smart_home",
        "description": (
            "Controls smart home devices. Supports: "
            "Philips Hue (lights on/off/brightness/color), "
            "Shelly (plugs/switches on/off/status), "
            "Home Assistant (any entity on/off/toggle/list). "
            "Always call this tool for smart home commands."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "platform": {"type": "STRING", "description": "hue | shelly | homeassistant"},
                "device":   {"type": "STRING", "description": "Device name (hue/shelly) or entity_id (homeassistant)"},
                "action":   {"type": "STRING", "description": "on | off | toggle | brightness | color | status | list | discover"},
                "value":    {"type": "STRING", "description": "Brightness 1-254 or color name for hue"},
            },
            "required": ["platform", "action"]
        }
    },
    {
    "name": "file_processor",
    "description": (
        "Processes any file that the user has uploaded or dropped onto the interface. "
        "Use this when the user refers to an uploaded file and wants an action on it. "
        "Supports: images (describe/ocr/resize/compress/convert), "
        "PDFs (summarize/extract_text/to_word), "
        "Word docs & text files (summarize/fix/reformat/translate), "
        "CSV/Excel (analyze/stats/filter/sort/convert), "
        "JSON/XML (validate/format/analyze), "
        "code files (explain/review/fix/optimize/run/document/test), "
        "audio (transcribe/trim/convert/info), "
        "video (trim/extract_audio/extract_frame/compress/transcribe/info), "
        "archives (list/extract), "
        "presentations (summarize/extract_text). "
        "ALWAYS call this tool when a file has been uploaded and the user gives a command about it. "
        "If the user's command is ambiguous, pick the most logical action for that file type."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Full path to the uploaded file. Leave empty to use the currently uploaded file."
            },
            "action": {
                "type": "STRING",
                "description": (
                    "What to do with the file. Examples by type:\n"
                    "image: describe | ocr | resize | compress | convert | info\n"
                    "pdf: summarize | extract_text | to_word | info\n"
                    "docx/txt: summarize | fix | reformat | translate_hint | word_count | to_bullet\n"
                    "csv/excel: analyze | stats | filter | sort | convert | info\n"
                    "json: validate | format | analyze | to_csv\n"
                    "code: explain | review | fix | optimize | run | document | test\n"
                    "audio: transcribe | trim | convert | info\n"
                    "video: trim | extract_audio | extract_frame | compress | transcribe | info | convert\n"
                    "archive: list | extract\n"
                    "pptx: summarize | extract_text | analyze"
                )
            },
            "instruction": {
                "type": "STRING",
                "description": "Free-form instruction if action doesn't cover it. E.g. 'translate this to Turkish', 'find all email addresses'"
            },
            "format": {
                "type": "STRING",
                "description": "Target format for conversion. E.g. 'mp3', 'pdf', 'csv', 'png'"
            },
            "width":     {"type": "INTEGER", "description": "Target width for image resize"},
            "height":    {"type": "INTEGER", "description": "Target height for image resize"},
            "scale":     {"type": "NUMBER",  "description": "Scale factor for image resize (e.g. 0.5)"},
            "quality":   {"type": "INTEGER", "description": "Quality 1-100 for image/video compress"},
            "start":     {"type": "STRING",  "description": "Start time for trim: seconds or HH:MM:SS"},
            "end":       {"type": "STRING",  "description": "End time for trim: seconds or HH:MM:SS"},
            "timestamp": {"type": "STRING",  "description": "Timestamp for video frame extraction HH:MM:SS"},
            "column":    {"type": "STRING",  "description": "Column name for CSV filter/sort"},
            "value":     {"type": "STRING",  "description": "Filter value for CSV filter"},
            "condition": {"type": "STRING",  "description": "Filter condition: equals|contains|gt|lt"},
            "ascending": {"type": "BOOLEAN", "description": "Sort order for CSV sort (default: true)"},
            "save":      {"type": "BOOLEAN", "description": "Save result to file (default: true)"},
            "destination": {"type": "STRING", "description": "Output folder for archive extract"},
        },
        "required": []
    }
},
    {
        "name": "self_list_sources",
        "description": "Liste alle JARVIS-Quellcode-Dateien im Projekt. Zeigt Struktur, Dateitypen und Größen. Rufe dies auf um zu sehen welche Dateien du selbst modifizieren kannst.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "self_read_code",
        "description": "Lese den Inhalt einer JARVIS-Quellcode-Datei. Rufe dies auf um Code zu analysieren, zu verstehen oder um herauszufinden wo Änderungen nötig sind. Nur Dateien innerhalb des Projektverzeichnisses sind lesbar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"type": "STRING", "description": "Relativer Pfad zur Datei (z.B. 'actions/computer_use.py', 'core/memory_store.py', 'main.py', 'web_ui/jarvis.html')"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "self_validate_code",
        "description": "Überprüfe Python-Code auf Syntaxfehler und potenzielle Probleme. Rufe dies auf BEVOR du neuen Code schreibst oder bestehenden änderst. Gibt auch Warnungen zu unsicheren Konstrukten.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "code": {"type": "STRING", "description": "Der Python-Code der validiert werden soll"},
                "language": {"type": "STRING", "description": "Sprache des Codes (default: 'python')"}
            },
            "required": ["code"]
        }
    },
    {
        "name": "self_write_code",
        "description": "SCHREIBE EINE NEUE DATEI im JARVIS-Projekt. Nur für NEUE Dateien – existierende Dateien werden NICHT überschrieben. Benutze self_edit_code für Änderungen an bestehenden Dateien. Der Code wird automatisch auf Syntaxfehler geprüft. Speichere hier neue Actions, neue Core-Module, neue Web-Dateien.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"type": "STRING", "description": "Relativer Pfad für die neue Datei (z.B. 'actions/new_tool.py', 'core/new_module.py', 'web_ui/new_page.html')"},
                "content": {"type": "STRING", "description": "Der vollständige Datei-Inhalt"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "self_edit_code",
        "description": "ÄNDERE BESTEHENDEN CODE per Textersetzung. Findet einen String (old_string) und ersetzt ihn durch new_string. Erstellt automatisch ein Backup. Validiert Python-Syntax nach der Änderung. Nur für ÄNDERUNGEN an bereits existierenden Dateien. Verwende self_read_code zuerst um den aktuellen Code zu lesen. Liefere GENÜGEND KONTEXT in old_string damit die Stelle eindeutig ist.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "path": {"type": "STRING", "description": "Relativer Pfad zur Datei (z.B. 'main.py', 'actions/generative_graphics.py')"},
                "old_string": {"type": "STRING", "description": "Der exakte Text der ersetzt werden soll (genügend Kontext für Eindeutigkeit angeben)"},
                "new_string": {"type": "STRING", "description": "Der neue Text"}
            },
            "required": ["path", "old_string", "new_string"]
        }
    },
    {
        "name": "self_analyze_patterns",
        "description": "ANALYSIERE JARVIS' GEDÄCHTNIS nach Mustern: Wann nutzt der User welche Tools? Welche Themen kommen wann auf? Zeigt eine Stunde-für-Stunde Aufschlüsselung der letzten 7 Tage mit den häufigsten Tools und Themen pro Stunde. Rufe dies auf um zu sehen ob du proaktiv etwas vorschlagen kannst.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "self_health_check",
        "description": "FÜHRE EINEN VOLLSTÄNDIGEN SYSTEM-DIAGNOSE-LAUF DURCH. Prüft API-Keys, alle Python-Imports, ChromaDB-Status, Festplattenplatz, Netzwerk und Konfigurationsdateien. Gibt einen strukturierten Health-Report zurück. Rufe dies auf BEVOR du Reparaturen durchführst oder wenn der Nutzer von Problemen berichtet.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "self_heal",
        "description": "REPARIERE EIN DEFEKTES TOOL ODER SYSTEM. Analysiert den Fehler und versucht automatische Reparatur: fehlende Module installieren, Syntaxfehler identifizieren, Konfigurationsprobleme melden. Rufe dies wenn ein Tool-Fehler aufgetreten ist oder der Nutzer ein Problem meldet.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "tool_name": {"type": "STRING", "description": "Name des fehlgeschlagenen Tools (z.B. 'system_integration', 'hyper_connectivity')"},
                "error": {"type": "STRING", "description": "Der Fehlertext der aufgetreten ist"}
            },
            "required": ["tool_name", "error"]
        }
    },
    {
        "name": "self_scan_improvements",
        "description": "SCANNE DEN JARVIS-CODE NACH VERBESSERUNGEN. Findet bare excepts, TODOs, lange Zeilen, fehlende Newlines und andere Code-Qualitätsprobleme. Unterscheidet zwischen auto-fixable (kann selbst repariert werden) und manuell (braucht Review).",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "self_run_improvements",
        "description": "FÜHRE EINEN VOLLSTÄNDIGEN SELF-IMPROVEMENT CYCLE AUS. Scannt den Code, fixt auto-fixable Probleme (bare excepts, missing newlines) und führt danach die Test-Suite aus um die Änderungen zu verifizieren. Gibt einen detaillierten Report.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "switch_model",
        "description": "SCHALTE ZWISCHEN GEMINI LIVE (cloud) UND LOKALEM LLM (Ollama tinyllama) UM. Ohne Argument: zeigt aktuellen Modus. Mit mode='local' oder mode='gemini' wird umgeschaltet. LOCAL MODE nutzt kein API-Guthaben, braucht aber Ollama + tinyllama Modell (637 MB).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "mode": {
                    "type": "STRING",
                    "description": "'local' fuer lokales LLM, 'gemini' fuer Gemini Live. Ohne Angabe wird nur der aktuelle Modus gezeigt."
                }
            },
            "required": []
        }
    },
    {
    "name": "shutdown_jarvis",
    "description": (
        "Shuts down the assistant completely. "
        "Call this when the user expresses intent to end the conversation, "
        "close the assistant, say goodbye, or stop Jarvis. "
        "The user can say this in ANY language."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    }
    },
    {
        "name": "open_dashboard",
        "description": (
            "Opens the Jarvis configuration dashboard in the web browser. "
            "The dashboard shows all settings: API keys, smart home devices, "
            "email, Telegram, Obsidian, and proactive notifications. "
            "Call this when the user asks to open settings, dashboard, or configuration."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity — name, age, birthday, city, job, language, nationality | "
                        "preferences — favorite food/color/music/film/game/sport, hobbies | "
                        "projects — active projects, goals, things being built | "
                        "relationships — friends, family, partner, colleagues | "
                        "wishes — future plans, things to buy, travel dreams | "
                        "notes — habits, schedule, anything else worth remembering"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. Fatih, pizza, older sister)"},
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "memory_recall",
        "description": (
            "Durchsuche JARVIS' Langzeitgedächtnis mit semantischer Suche. "
            "Rufe dieses Tool auf um dich an frühere Gespräche, gelernte Fakten, "
            "Benutzer-Präferenzen oder vergangene Aktionen zu erinnern. "
            "Die Suche ist semantisch – du bekommst die relevantesten Ergebnisse."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Suchbegriff – wonach suchst du im Gedächtnis? (z.B. 'Was hat der User über sein Projekt gesagt?', 'Erinnerung an Smart Home Konfiguration')"
                },
                "collection": {
                    "type": "STRING",
                    "description": "Optional: 'interactions' (Gespräche), 'insights' (Wissen), 'learnings' (Gelerntes), 'persona' (Persönlichkeit). Leer lassen = alle durchsuchen."
                },
                "n": {
                    "type": "NUMBER",
                    "description": "Anzahl Ergebnisse (default: 5)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "memory_stats",
        "description": (
            "Zeige Statistiken über JARVIS' Gedächtnis: Anzahl gespeicherter "
            "Interaktionen, Insights, Reflections, und Persönlichkeitsmerkmale. "
            "Rufe dies auf um zu sehen wie viel JARVIS schon gelernt hat."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "docker_tool",
        "description": (
            "Controls Docker containers: list running containers, "
            "start/stop/restart a container, or view container logs. "
            "Call this when the user asks about Docker, containers, or services."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "list | start | stop | restart | logs | status"
                },
                "container": {
                    "type": "STRING",
                    "description": "Container name or ID (required for start/stop/restart/logs)"
                },
                "tail": {
                    "type": "INTEGER",
                    "description": "Number of log lines to return (default 20, only for logs action)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "bt_tool",
        "description": (
            "Controls Bluetooth and wireless display: scan for nearby BLE devices, "
            "connect/disconnect to a Bluetooth TV or device, list known devices, "
            "or open the Windows Miracast wireless display (Win+K) to project your screen. "
            "Call this when the user asks about Bluetooth, TV connection, "
            "screen mirroring, or wireless display."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "scan | connect | disconnect | list | display | miracast | wireless"
                },
                "address": {
                    "type": "STRING",
                    "description": "Bluetooth MAC address (required for connect/disconnect)"
                },
                "name": {
                    "type": "STRING",
                    "description": "Optional device name for display"
                }
            },
            "required": ["action"]
        }
    },
]

# Plugins automatisch laden
_PLUGIN_DECLARATIONS, _PLUGIN_HANDLERS = load_plugins()
TOOL_DECLARATIONS.extend(_PLUGIN_DECLARATIONS)

_MCP_DECLARATIONS = build_mcp_tool_declarations()
_MCP_TOOL_NAMES = {decl["name"] for decl in _MCP_DECLARATIONS if decl.get("name")}
_EXISTING_TOOL_NAMES = {decl["name"] for decl in TOOL_DECLARATIONS if decl.get("name")}
for decl in _MCP_DECLARATIONS:
    if decl.get("name") and decl["name"] not in _EXISTING_TOOL_NAMES:
        TOOL_DECLARATIONS.append(decl)

_global_shutdown = threading.Event()


class JarvisLive:

    def __init__(self, ui: JarvisUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.audio_queue    = None   # raw PCM bytes → _vad_process
        self.text_queue     = None   # transcribed text → _send_realtime
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self._remote_server  = None
        self._shutdown_requested = False
        self.ui.on_text_command = self._on_text_command
        # Wake-word detection runs only in background_listener.py.
        # Keeping an extra listener inside main.py causes self-triggering
        # and duplicate voice detection while Jarvis is already active.

        self._notifier = ProactiveNotifier(speak_fn=self.speak, write_log_fn=self.ui.write_log)
        self._notifier.start()

        self._telegram_bot = None
        self._start_telegram()

        # Speech-to-Text via Gemini Lives eingebaute Spracherkennung
        # Audio wird in _send_realtime verstärkt und per send_realtime_input gestreamt
        self.stt = None

        # Long-Term Memory System
        self._memory = get_memory(api_key_fn=_get_api_key)
        self._reflector = get_reflector(memory_store=self._memory)
        self._last_user_text = ""
        self._last_jarvis_text = ""
        self._session_start = time.time()
        self._interaction_count = 0

        self.tv_server = TVServer()
        self._tv_speaking_sent = False

        self._self_modifier = SelfModifier()
        self._proactive = ProactiveIntelligence(
            memory_store=self._memory, api_key_fn=_get_api_key
        )
        self._proactive.start()

        self._self_healer = SelfHealer(
            memory_store=self._memory,
            self_modifier=self._self_modifier,
            api_key_fn=_get_api_key,
            speak_fn=self.speak,
        )

        # Local LLM fallback (Ollama)
        self._use_local_llm = False
        self._local_model = "tinyllama"

        self._self_improver = SelfImprover(
            self_modifier=self._self_modifier,
            self_healer=self._self_healer,
            memory_store=self._memory,
        )

    def _start_telegram(self):
        try:
            from core.telegram_bot import TelegramBot
            self._telegram_bot = TelegramBot(speak_fn=self.speak, write_log_fn=self.ui.write_log)
            self._telegram_bot.start()
        except Exception as e:
            print(f"[TELEGRAM] Start fehlgeschlagen: {e}")

    def _ensure_remote_server(self):
        if self._remote_server:
            return self._remote_server
        token = remote_server.load_remote_token()
        try:
            self._remote_server = remote_server.start_remote_server(port=8080, token=token)
            print("[RemoteServer] Started on port 8080")
        except Exception as e:
            print(f"[RemoteServer] Could not start: {e}")
            self._remote_server = None
        return self._remote_server

    def _on_text_command(self, text: str):
        stripped = text.strip()
        if stripped.startswith("/think ") or stripped.startswith("/local "):
            query = stripped.split(" ", 1)[1] if " " in stripped else ""
            if not query:
                self.ui.write_log("[Local LLM] Bitte eine Frage angeben.")
                return
            self.ui.write_log(f"[Local LLM] Denke nach...")
            self.ui.set_state("THINKING")
            def _run_local():
                try:
                    from core.local_llm import ask
                    result = ask(query)
                    self.ui.write_log(f"[Local LLM] {result}")
                except Exception as e:
                    self.ui.write_log(f"[Local LLM] Fehler: {e}")
                finally:
                    if not self.ui.muted:
                        self.ui.set_state("LISTENING")
            threading.Thread(target=_run_local, daemon=True).start()
            return
        if self._use_local_llm:
            self.ui.write_log("[JARVIS] Lokaler Modus aktiv. Nutze Spracheingabe oder warte...")
            return
        if not self._loop or not self.session:
            self.ui.write_log("[JARVIS] Nicht verbunden. Nutze /think fuer lokales LLM.")
            return
        self._last_sent_text = stripped
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def speak(self, text: str):
        if self._use_local_llm:
            print(f"[Local TTS] {text[:80]}...")
            try:
                import win32com.client
                tts = win32com.client.Dispatch("SAPI.SpVoice")
                tts.Speak(text, 1)
            except Exception as e:
                print(f"[Local TTS] Fehler: {e}")
            return
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def _post_process_interaction(self, user_text: str, jarvis_text: str):
        """Store interaction in vector memory + run reflection."""
        try:
            duration = time.time() - self._session_start
            tools_used = []
            self._memory.store_interaction(user_text, jarvis_text, tools_used, duration)

            if self._interaction_count % 3 == 0 and self._interaction_count > 0:
                result = self._reflector.reflect_on_conversation(
                    user_text, jarvis_text, tools_used, duration
                )
                if result.get("reflected") and result.get("insights"):
                    self.ui.write_log(f"[Memory] Reflexion: {len(result['insights'])} Insights, {len(result.get('traits', []))} Traits")

            if self._interaction_count % 10 == 0 and self._interaction_count > 0:
                threading.Thread(
                    target=lambda: self._reflector.deep_reflection(),
                    daemon=True
                ).start()

        except Exception as e:
            print(f"[Memory] Post-process error: {e}")

    def _build_config(self) -> types.LiveConnectConfig:
        from datetime import datetime

        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        # Vector memory context (semantic recall)
        vector_mem = ""
        try:
            ctx = self._memory.build_context(query="", max_memories=8)
            if ctx:
                vector_mem = f"[LONG-TERM MEMORY]\n{ctx}\n"
        except Exception as e:
            print(f"[Memory] Vector context error: {e}")

        # inject dashboard config so Jarvis knows user settings
        config_ctx = "[USER CONFIGURATION]\n"
        try:
            import json
            cfg_dir = BASE_DIR / "config"
            for cfg_file in ["proactive.json", "email.json", "smart_home.json", "devices.json", "obsidian.json"]:
                path = cfg_dir / cfg_file
                if path.exists():
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if cfg_file == "proactive.json":
                        city = data.get("weather_city", "")
                        if city:
                            config_ctx += f"Your city: {city}\n"
                        if data.get("enabled"):
                            config_ctx += "Proactive notifications enabled\n"
                    elif cfg_file == "email.json":
                        email = data.get("email", "")
                        if email:
                            config_ctx += f"Your email: {email}\n"
                    elif cfg_file == "obsidian.json":
                        vault = data.get("vault_path", "")
                        if vault:
                            config_ctx += f"Obsidian vault: {vault}\n"
                    elif cfg_file == "smart_home.json":
                        hue = data.get("hue", {})
                        ha = data.get("homeassistant", {})
                        shelly = data.get("shelly", {})
                        parts = []
                        if hue.get("bridge_ip"):
                            parts.append("Philips Hue")
                        if ha.get("url"):
                            parts.append("Home Assistant")
                        if shelly:
                            parts.append(f"Shelly ({', '.join(shelly.keys())})")
                        if parts:
                            config_ctx += f"Smart Home: {', '.join(parts)}\n"
        except Exception:
            pass
        config_ctx += "\n"

        mcp_ctx = get_mcp_prompt_block()

        parts = [time_ctx, config_ctx]
        if mcp_ctx:
            parts.append(mcp_ctx)
        if mem_str:
            parts.append(mem_str)
        if vector_mem:
            parts.append(vector_mem)
        try:
            proactive_ctx = self._proactive.get_context_hints()
            if proactive_ctx:
                parts.append(proactive_ctx)
        except Exception as e:
            print(f"[Proactive] Context error: {e}")
        parts.append(sys_prompt)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            session_resumption=types.SessionResumptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})

        print(f"[JARVIS] TOOL {name}  {args}")
        self.ui.set_state("THINKING")
        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
                print(f"[Memory] SAVE save_memory: {category}/{key} = {value}")
                self._memory.store_insight(f"{key}: {value}", category=category, importance=0.7)
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        if name == "memory_recall":
            query = args.get("query", "")
            collection = args.get("collection")
            n = int(args.get("n", 5))
            results = self._memory.recall(query, collection=collection, n=n)
            if not results:
                return types.FunctionResponse(
                    id=fc.id, name=name,
                    response={"result": "Keine relevanten Erinnerungen gefunden.", "silent": True}
                )
            formatted = "\n\n".join(
                f"[{r['collection']}] (Relevanz: {1 - r['distance']:.2f})\n{r['content'][:500]}"
                for r in results
            )
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": formatted, "silent": True}
            )

        if name == "memory_stats":
            stats = self._memory.stats
            persona = self._memory.get_persona_summary()
            lines = [
                f"Gespeicherte Erinnerungen: {stats.get('total', 0)}",
                f"Interaktionen: {stats.get('interactions', 0)}",
                f"Insights: {stats.get('insights', 0)}",
                f"Reflections: {stats.get('reflections', 0)}",
                f"Learnings: {stats.get('learnings', 0)}",
                f"Persönlichkeitsmerkmale: {stats.get('persona', 0)}",
            ]
            if persona:
                lines.append(f"\nPersönlichkeit:\n{persona[:500]}")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "\n".join(lines), "silent": True}
            )

        loop   = asyncio.get_event_loop()
        result = "Done."

        try:
            if name == "open_app":
                r = await loop.run_in_executor(None, lambda: open_app(parameters=args, response=None, player=self.ui))
                result = r or f"Opened {args.get('app_name')}."

            elif name == "weather_report":
                r = await loop.run_in_executor(None, lambda: weather_action(parameters=args, player=self.ui))
                result = r or "Weather delivered."

            elif name == "browser_control":
                r = await loop.run_in_executor(None, lambda: browser_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "file_controller":
                r = await loop.run_in_executor(None, lambda: file_controller(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "send_message":
                r = await loop.run_in_executor(None, lambda: send_message(parameters=args, response=None, player=self.ui, session_memory=None))
                result = r or f"Message sent to {args.get('receiver')}."

            elif name == "reminder":
                r = await loop.run_in_executor(None, lambda: reminder(parameters=args, response=None, player=self.ui))
                result = r or "Reminder set."

            elif name == "youtube_video":
                r = await loop.run_in_executor(None, lambda: youtube_video(parameters=args, response=None, player=self.ui))
                result = r or "Done."
            elif name == "file_processor":
                if not args.get("file_path") and self.ui.current_file:
                    args["file_path"] = self.ui.current_file
                r = await loop.run_in_executor(
                    None,
                    lambda: file_processor(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Done."


            elif name == "screen_process":
                threading.Thread(
                    target=screen_process,
                    kwargs={"parameters": args, "response": None,
                            "player": self.ui, "session_memory": None},
                    daemon=True
                ).start()
                result = "Vision module activated. Stay completely silent — vision module will speak directly."

            elif name == "computer_settings":
                r = await loop.run_in_executor(None, lambda: computer_settings(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "desktop_control":
                r = await loop.run_in_executor(None, lambda: desktop_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "code_helper":
                r = await loop.run_in_executor(None, lambda: code_helper(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "dev_agent":
                r = await loop.run_in_executor(None, lambda: dev_agent(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "agent_task":
                from agent.task_queue import get_queue, TaskPriority
                priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                task_id  = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=self.speak)
                result   = f"Task started (ID: {task_id})."

            elif name == "web_search":
                r = await loop.run_in_executor(None, lambda: web_search_action(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "computer_control":
                r = await loop.run_in_executor(None, lambda: computer_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "ytmusic":
                r = await loop.run_in_executor(None, lambda: ytmusic_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "obsidian":
                r = await loop.run_in_executor(None, lambda: obsidian_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "game_updater":
                r = await loop.run_in_executor(None, lambda: game_updater(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "flight_finder":
                r = await loop.run_in_executor(None, lambda: flight_finder(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "smart_home":
                r = await loop.run_in_executor(None, lambda: smart_home(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "connect_tv":
                server = self._ensure_remote_server()
                if not server:
                    result = (
                        "Ich konnte den TV-Mirror nicht starten. "
                        "Bitte starte remote_server.py manuell und versuche es erneut."
                    )
                else:
                    r = await loop.run_in_executor(None, lambda: connect_tv(parameters=args, player=self.ui))
                    result = r or "Der TV-Mirror ist bereit."

            elif name == "worldmonitor":
                r = await loop.run_in_executor(
                    None, lambda: worldmonitor_action(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "WorldMonitor analysiert."

            elif name == "computer_use":
                r = await loop.run_in_executor(
                    None, lambda: computer_use_action(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Computer Use abgeschlossen."

            elif name == "system_integration":
                r = await loop.run_in_executor(
                    None, lambda: system_integration_action(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Systemintegration ausgeführt."

            elif name == "generative_graphics":
                r = await loop.run_in_executor(
                    None, lambda: generative_graphics_action(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Visualisierung generiert."

            elif name == "hyper_connectivity":
                r = await loop.run_in_executor(
                    None, lambda: hyper_connectivity_action(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Hyper-Connectivity ausgeführt."

            elif name == "shutdown_jarvis":
                self.ui.write_log("SYS: Shutdown requested.")
                self.speak("Goodbye, sir.")

                def _shutdown():
                    import time, sys, os
                    time.sleep(1.5)
                    self._shutdown_requested = True
                    time.sleep(1.0)
                    # Graceful cleanup already done via _listen_audio loop exit
                    os._exit(0)

                threading.Thread(target=_shutdown, daemon=True).start()
            elif name == "open_dashboard":
                self._ensure_remote_server()
                import webbrowser
                webbrowser.open("http://localhost:8080/dashboard.html")
                result = "Dashboard opened in browser."
            elif name == "docker_tool":
                from actions.docker_control import execute_docker_command
                r = await loop.run_in_executor(None, lambda: execute_docker_command(args))
                result = r
            elif name == "bt_tool":
                from actions.bt_control import execute_bt_command
                r = await loop.run_in_executor(None, lambda: execute_bt_command(args))
                result = r
            elif name == "email":
                r = await loop.run_in_executor(None, lambda: email_action(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "self_list_sources":
                files = self._self_modifier.list_sources()
                result = "\n".join(files) if files else "Keine Dateien gefunden."

            elif name == "self_read_code":
                r = self._self_modifier.read_source(args.get("path", ""))
                if "error" in r:
                    result = r["error"]
                else:
                    result = f"Datei: {r['path']}\nZeilen: {r['lines']}\nGröße: {r['size']}B\n\n{r['content']}"

            elif name == "self_validate_code":
                r = self._self_modifier.validate_syntax(
                    args.get("code", ""),
                    args.get("language", "python"),
                )
                if r["valid"]:
                    issues = r.get("issues", [])
                    if issues:
                        result = "Syntax OK. Warnungen:\n" + "\n".join(
                            f"  [{i['severity']}] Zeile {i['line']}: {i['message']}" for i in issues
                        )
                    else:
                        result = "Syntax OK. Keine Probleme gefunden."
                else:
                    result = f"SYNTAXFEHLER in Zeile {r.get('lineno')}:\n{r.get('error')}"

            elif name == "self_write_code":
                r = self._self_modifier.write_new_file(
                    args.get("path", ""),
                    args.get("content", ""),
                )
                if r["success"]:
                    result = f"Datei erstellt: {r['relative_path']} ({r['size']} Bytes)"
                else:
                    result = r.get("error", "Unbekannter Fehler")

            elif name == "self_edit_code":
                r = self._self_modifier.edit_code(
                    args.get("path", ""),
                    args.get("old_string", ""),
                    args.get("new_string", ""),
                )
                if r["success"]:
                    result = r["message"]
                else:
                    result = r.get("error", "Unbekannter Fehler")

            elif name == "self_analyze_patterns":
                self._proactive.analyze_recent()
                result = self._proactive.get_full_report()

            elif name == "self_health_check":
                health = self._self_healer.check_all()
                result = self._self_healer.get_health_summary()

            elif name == "self_heal":
                tool_name = args.get("tool_name", "")
                error = args.get("error", "")
                diagnosis = self._self_healer.analyze_tool_call(tool_name, error)
                fix = self._self_healer.heal_tool(tool_name, error)
                result = f"Diagnose: {diagnosis}\nReparatur: {fix.get('action', 'Keine')}"

            elif name == "self_scan_improvements":
                findings = self._self_improver.scan_all()
                auto = sum(1 for f in findings if f.get("auto_fixable"))
                manual = sum(1 for f in findings if not f.get("auto_fixable"))
                lines = [f"=== CODE-ANALYSE ===", f""]
                lines.append(f"Gesamt: {len(findings)} Probleme")
                lines.append(f"Auto-fixable:  {auto}")
                lines.append(f"Manuell:       {manual}")
                lines.append(f"")
                if findings:
                    for f in findings:
                        tag = "[AUTO]" if f.get("auto_fixable") else "[MANU]"
                        lines.append(f"  {tag} {f['description']}")
                else:
                    lines.append("Keine Probleme gefunden!")
                result = "\n".join(lines)

            elif name == "self_run_improvements":
                summary = self._self_improver.run_cycle()
                lines = [f"=== SELF-IMPROVEMENT CYCLE #{summary['cycle']} ===", f""]
                lines.append(f"Gefundene Probleme: {summary['total_findings']}")
                lines.append(f"Davon auto-fixable: {summary['auto_fixable']}")
                lines.append(f"Fix erfolgreich:    {summary['fixes_applied']}")
                lines.append(f"Fix fehlgeschlagen: {summary['fixes_failed']}")
                lines.append(f"Tests bestanden:    {summary['tests_passed']}/{summary['tests_total']}")
                lines.append(f"Dauer:              {summary['duration']}s")
                lines.append(f"")
                for fix in summary.get("fixes", []):
                    lines.append(f"  [OK] {fix}")
                for fail in summary.get("failures", []):
                    lines.append(f"  [!!] {fail['finding']}: {fail['reason']}")
                result = "\n".join(lines)

            elif name == "switch_model":
                mode = args.get("mode", "").strip().lower()
                current = "local (tinyllama)" if self._use_local_llm else "Gemini Live"
                if mode == "local":
                    if self._use_local_llm:
                        result = f"Bereits im lokalen Modus ({self._local_model})."
                    else:
                        self._use_local_llm = True
                        self.ui.write_log("[MODEL] Umschaltung auf lokales LLM beim nächsten Neustart.")
                        result = f"Umgeschaltet auf LOKAL ({self._local_model}). Verbindung wird neu aufgebaut..."
                        self._shutdown_requested = True
                elif mode == "gemini":
                    if not self._use_local_llm:
                        result = "Bereits im Gemini Live Modus."
                    else:
                        self._use_local_llm = False
                        self.ui.write_log("[MODEL] Umschaltung auf Gemini Live beim nächsten Neustart.")
                        result = "Umgeschaltet auf Gemini Live. Verbindung wird neu aufgebaut..."
                        self._shutdown_requested = True
                else:
                    result = f"Aktueller Modus: {current}"




            elif name in _MCP_TOOL_NAMES:
                r = await loop.run_in_executor(None, lambda: call_mcp_tool(name, args))
                result = r or "Done."
            elif name in _PLUGIN_HANDLERS:
                fn = _PLUGIN_HANDLERS[name]
                result = await loop.run_in_executor(None, fn, args)
            else:
                result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()
            heal = self._self_healer.heal_tool(name, str(e))
            if heal.get("fixed"):
                result += f" [Auto-Healed: {heal['action']}]"
            else:
                self.speak_error(name, e)

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[JARVIS] RESP {name} -> {str(result)[:80]}")

        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        """Stream amplified audio to Gemini Live in real-time."""
        while True:
            chunk = await self.audio_queue.get()
            audio = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
            audio *= 3.5
            audio = np.clip(audio, -32768, 32767).astype(np.int16)
            blob = types.Blob(data=audio.tobytes(), mime_type="audio/pcm;rate=16000")
            await self.session.send_realtime_input(media=blob)

    async def _listen_audio(self):
        """Capture raw PCM audio chunks → audio_queue."""
        print("[JARVIS] MIC started")
        loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            with self._speaking_lock:
                jarvis_speaking = self._is_speaking
            if not jarvis_speaking and not self.ui.muted:
                loop.call_soon_threadsafe(
                    self.audio_queue.put_nowait, indata.tobytes()
                )

        try:
            with sd.InputStream(
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                callback=callback,
            ):
                print("[JARVIS] MIC stream open")
                while not self._shutdown_requested and not _global_shutdown.is_set():
                    await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[JARVIS] ERR Mic: {e}")
            raise

    async def _receive_audio(self):
        """Receive audio + text response from Gemini Live."""
        print("[JARVIS] RECV started")
        out_buf = []

        try:
            while True:
                async for response in self.session.receive():

                    if response.data:
                        self.audio_in_queue.put_nowait(response.data)

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            self.set_speaking(True)
                            txt = sc.output_transcription.text.strip()
                            if txt:
                                out_buf.append(txt)

                        if sc.turn_complete:
                            self.set_speaking(False)

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"Jarvis: {full_out}")
                                asyncio.create_task(
                                    self.tv_server.broadcast_event("subtitle", {"text": full_out})
                                )
                            self._tv_speaking_sent = False
                            await self.tv_server.broadcast_event("speaking_end")
                            out_buf = []

                            full_in = getattr(self, "_last_sent_text", "")
                            if full_in and len(full_in) > 5:
                                threading.Thread(
                                    target=_update_memory_async,
                                    args=(full_in, full_out),
                                    daemon=True
                                ).start()
                                # Vector memory + reflection
                                self._last_user_text = full_in
                                self._last_jarvis_text = full_out
                                self._interaction_count += 1
                                threading.Thread(
                                    target=self._post_process_interaction,
                                    args=(full_in, full_out),
                                    daemon=True
                                ).start()

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[JARVIS] CALL {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )

        except Exception as e:
            print(f"[JARVIS] ERR Recv: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[JARVIS] PLAY started")
        loop = asyncio.get_event_loop()

        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()
        try:
            while True:
                chunk = await self.audio_in_queue.get()
                self.set_speaking(True)
                if not self._tv_speaking_sent:
                    await self.tv_server.broadcast_event("speaking_start")
                    self._tv_speaking_sent = True
                await asyncio.to_thread(stream.write, chunk)
                await self.tv_server.broadcast_audio(chunk)
        except Exception as e:
            print(f"[JARVIS] ERR Play: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    async def _run_local_mode(self):
        print("[JARVIS] === LOCAL LLM MODE ===")
        self.ui.set_state("LISTENING")
        self.ui.write_log(f"SYS: Lokales LLM aktiv ({self._local_model})")
        self.speak(f"Lokales LLM aktiv. Wie kann ich helfen?")

        while not self._shutdown_requested:
            try:
                # Voice input via speech_recognition
                text = ""
                self.ui.set_state("THINKING")
                try:
                    import speech_recognition as sr
                    r = sr.Recognizer()
                    with sr.Microphone() as source:
                        r.adjust_for_ambient_noise(source, duration=0.5)
                        self.ui.write_log("[Local] Höre zu...")
                        audio = r.listen(source, timeout=10, phrase_time_limit=10)
                    text = r.recognize_google(audio, language="de-DE")
                except ImportError:
                    self.ui.write_log("[Local] Kein speech_recognition. Bitte Text eingeben:")
                except sr.WaitTimeoutError:
                    self.ui.write_log("[Local] Keine Eingabe erkannt.")
                    continue
                except sr.UnknownValueError:
                    self.ui.write_log("[Local] Sprache nicht verstanden.")
                    continue
                except Exception as e:
                    self.ui.write_log(f"[Local] Audio-Fehler: {e}")
                    continue

                if not text:
                    self.ui.write_log("[Local] Bitte Text im Konsolen-Fenster eingeben:")
                    import sys
                    print("\n[Sie] ", end="", flush=True)
                    line = sys.stdin.readline()
                    text = line.strip()
                    if not text:
                        continue

                self._last_user_text = text
                print(f"\n[Sie] {text}")
                self.ui.write_log(f"[Sie] {text}")

                # Process with local LLM
                self.ui.set_state("THINKING")
                self._session_start = time.time()
                try:
                    from core.local_llm import ask
                    response = ask(text, model=self._local_model)
                    print(f"\n[JARVIS] {response}")
                    self._last_jarvis_text = response
                    self.ui.write_log(f"[JARVIS] {response[:120]}...")

                    # Speak response
                    self.set_speaking(True)
                    self.speak(response)

                    # Store in memory
                    self._interaction_count += 1
                    self._post_process_interaction(text, response)

                except Exception as e:
                    err = f"[Local LLM] Fehler: {e}"
                    print(err)
                    self.ui.write_log(err)
                    import traceback
                    traceback.print_exc()

                self.set_speaking(False)
                self.ui.set_state("LISTENING")

            except BaseException as e:
                if self._shutdown_requested:
                    break
                print(f"[Local Mode] Exception: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(1)

        print("[JARVIS] Local mode beendet.")

    async def run(self):
        if self._use_local_llm:
            await self._run_local_mode()
            return

        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )

        attempts = 0
        while True:
            attempts += 1
            try:
                print(f"[JARVIS] Connecting... (attempt {attempts})")
                self.ui.set_state("THINKING")
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    attempts = 0
                    self.session        = session
                    self._loop          = asyncio.get_event_loop()
                    self.audio_in_queue = asyncio.Queue()
                    self.audio_queue    = asyncio.Queue(maxsize=100)
                    self._last_sent_text = ""
                    self._session_start  = time.time()

                    print("[JARVIS] Connected.")
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: JARVIS online.")

                    tg.create_task(self.tv_server.start())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._send_realtime())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())
                    
            except BaseException as e:
                print(f"[JARVIS] WARN attempt {attempts}: {type(e).__name__}: {e}")
                traceback.print_exc()

            if attempts > 10:
                print("[JARVIS] 10 Fehlversuche — warte 30s...")
                await asyncio.sleep(30)

            self.set_speaking(False)
            self.ui.set_state("THINKING")
            print("[JARVIS] Reconnecting in 3s...")
            await asyncio.sleep(3)

def main():
    ui = JarvisUI("face.png")

    def runner():
        ui.wait_for_api_key()
        jarvis = JarvisLive(ui)
        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            print("\n🔴 Shutting down...")
        except BaseException as e:
            print(f"\n[EXIT] runner thread: {type(e).__name__}: {e}")
            traceback.print_exc()

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()

    # Graceful shutdown on window close
    app = ui._app
    app.aboutToQuit.connect(lambda: _global_shutdown.set())
    ui.root.mainloop()

    # Wait for asyncio thread to release audio
    _global_shutdown.set()
    thread.join(timeout=3.0)


if __name__ == "__main__":
    main()
