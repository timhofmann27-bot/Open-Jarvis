# Open-Jarvis Architecture

## Overview

Open-Jarvis is a voice-controlled AI assistant built around a central orchestrator (`main.py`) that connects to Google's Gemini Live API (cloud) or a local Ollama instance (offline). It exposes 57+ tools to the LLM and runs a continuous self-improvement loop.

```
┌────────────────────────────────────────────────────────────┐
│                     Wake Word Listener                     │
│              (background_listener.py :8765)                │
└────────────────────────┬───────────────────────────────────┘
                         │ "Jarvis!"
                         ▼
┌────────────────────────────────────────────────────────────┐
│                    Main Orchestrator (main.py)             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │            Gemini Live / Local LLM                   │  │
│  │  • Real-time audio streaming                         │  │
│  │  • Function calling (57+ tools)                      │  │
│  │  • System instructions with memory context           │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                 │
│         ┌────────────────┼────────────────┐                │
│         ▼                ▼                ▼                │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐            │
│   │ Memory   │    │ Tool Bus │    │ TV Audio │            │
│   │ (Chroma) │    │ (_exec)  │    │  (WS)    │            │
│   └──────────┘    └────┬─────┘    └──────────┘            │
│                        │                                   │
│         ┌──────────────┼──────────────┐                    │
│         ▼              ▼              ▼                    │
│   Smart Home    System/Apps     Generative                 │
│   (Hue/HA)      (Win32)         Graphics                   │
│                                                            │
│   Self-* Loops (background threads):                        │
│   • Proactive Intelligence (30 min)                        │
│   • Self-Healing (on error)                                │
│   • Self-Improvement (on demand)                           │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────┐
│              Dashboard (port 8080)                         │
│       9 tabs: Overview, Health, Memory, Tools,             │
│              Docker, TV&BT, Config, Logs, Tests            │
└────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Main Orchestrator (`main.py`)

The central state machine. Lifecycle:
1. Initialize all subsystems (memory, notifier, telegram, self-* systems)
2. Connect to Gemini Live (or run local LLM mode)
3. Open 5 concurrent async tasks:
   - `_listen_audio()` — capture mic
   - `_send_realtime()` — stream to Gemini
   - `_receive_audio()` — process responses
   - `_play_audio()` — play TTS
   - `tv_server.start()` — WebSocket server
4. Handle function calls via `_execute_tool()`
5. Reconnect on errors with exponential backoff

### 2. Memory System (`core/memory_store.py`)

ChromaDB vector database with 5 collections:
- `conversations` — past interactions (text + embedding)
- `facts` — extracted facts about the user
- `preferences` — user preferences
- `tasks` — todo items
- `reflections` — JARVIS's self-reflections

Embeddings: `all-MiniLM-L6-v2` via `onnxruntime` (no API needed)

### 3. Reflection System (`core/reflector.py`)

After each conversation:
- Run Gemini Flash API to extract insights, emotions, and growth signals
- Update `self_personality` JSON in `memory/stats.json`
- Every 10 interactions, run "depth reflection" combining all recent interactions

### 4. Self-Modification System (`core/self_modifier.py`)

Autonomous code reading, writing, editing. Safety:
- **Project-root restriction** via `_resolve()` — never escape `BASE_DIR`
- **Backup files** (`.bak`) before any edit
- **Syntax validation** via `ast.parse()` before saving
- **Audit log** at `memory/self_modifications.json`

Tools exposed to LLM:
- `self_list_sources` — list project files
- `self_read_code` — read file contents
- `self_validate_code` — check Python syntax
- `self_write_code` — create new files
- `self_edit_code` — modify existing files

### 5. Self-Healing System (`core/self_healer.py`)

6 health checks (run on demand or after tool errors):
1. API keys present and valid
2. Python imports work
3. Memory DB is writable
4. Disk space available
5. Network connectivity
6. Configuration files parseable

Auto-repair: catches `ModuleNotFoundError` → `pip install`. Catches `SyntaxError` → localizes.

### 6. Self-Improvement Loop (`core/self_improver.py`)

Periodic code quality scanning:
- Find bare `except:` clauses
- Find TODO/FIXME comments
- Find lines > 120 chars
- Find files missing trailing newlines

Auto-fixes: `bare_except` → `except Exception:`, missing newlines.
Reports all findings to `memory/improvements.json`.

### 7. Proactive Intelligence (`core/proactive_intelligence.py`)

Analyzes last 7 days of memory:
- Activity peaks by hour
- Most-used tools
- Topic trends

Background loop every 30 min. Insights injected into system prompt as `[PROACTIVE HINT]`.

### 8. MCP Bridge (`core/mcp_bridge.py`)

Connects to MCP (Model Context Protocol) servers running in Docker. Discovers tools dynamically and merges them into the LLM's tool set.

### 9. Dashboard (`remote_server.py` + `web_ui/dashboard.html`)

HTTP server on port 8080 with API endpoints:
- `/api/config` — read/write configuration
- `/api/status` — system status
- `/api/health` — self-healer report
- `/api/memory/stats` — ChromaDB stats
- `/api/proactive/patterns` — usage patterns
- `/api/modification/log` — self-modification log
- `/api/improvements/log` — self-improvement log
- `/api/tests` — test suite results
- `/api/docker` — Docker container control
- `/api/bt` — Bluetooth scan/connect
- `/api/wireless-display` — open Miracast flyout

### 10. TV Interface (`tv_interface/tv_server.py` + `web_ui/jarvis.html`)

WebSocket server on port 8765. Streams:
- Raw audio (24kHz, 16-bit, mono) for lip-sync visualization
- Events: `speaking_start`, `speaking_end`, `state_change`

3D frontend uses Three.js to render an Iron Man-style helmet with arc reactor, holographic data panels, and lip-sync jaw movement based on audio amplitude.

## Data Flow Example

User says "Jarvis, what's the weather in Berlin?":

1. `background_listener.py` detects wake word, launches `main.py`
2. `main.py` connects to Gemini Live, streams audio
3. Gemini transcribes: "What's the weather in Berlin?"
4. Gemini calls `weather_report(city="Berlin")` tool
5. `main.py:_execute_tool()` runs the handler → returns weather
6. Gemini synthesizes response text
7. `main.py` streams TTS audio → plays through speakers
8. `main.py` broadcasts audio to `tv_server` for TV lip-sync
9. `_post_process_interaction()` saves the exchange to ChromaDB
10. `reflector.py` analyzes the exchange for insights
11. UI updates state to "LISTENING"

## Extension Points

| Want to... | Edit... |
|------------|---------|
| Add a new tool | `actions/your_tool.py` + tool decl in `main.py` |
| Add a core system | `core/your_system.py` + init in `main.py:__init__` |
| Add a dashboard tab | `web_ui/dashboard.html` |
| Add an API endpoint | `remote_server.py` |
| Add a test | `core/test_suite.py` |
| Add a memory collection | `core/memory_store.py` |
