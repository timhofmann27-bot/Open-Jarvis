# 🤖 Open-Jarvis

### The Ultimate Open-Source JARVIS AI Assistant

Open-Jarvis is a completely local, voice-controlled AI assistant inspired by Tony Stark's J.A.R.V.I.S. It runs on **Windows**, understands natural language, and can interact with your system, smart home, codebase, TV, and more — all through voice commands.

---

## ✨ Features

| Category | Capabilities |
|----------|-------------|
| **🎤 Voice** | Wake word detection (openWakeWord), clap detection, real-time Gemini Live streaming |
| **🧠 AI** | Gemini Live (cloud) **or** local Ollama (tinyllama, phi3, etc.) — automatic fallback |
| **💾 Memory** | ChromaDB vector database — semantic recall, reflection, personality growth |
| **🛠 Tools** | 57+ native tools + MCP bridge (16+ dynamic tools) |
| **🖥 System** | Processes, services, registry, power, wallpapers, disks, network, display |
| **🏠 Smart Home** | Philips Hue, Shelly, Home Assistant |
| **📺 TV** | Wireless Display (Miracast), WebSocket lip-sync streaming |
| **🎵 Media** | YouTube Music, Spotify, GitHub |
| **📬 Communication** | Email, calendar, Telegram bot |
| **🌐 Web UI** | Dashboard v4 (9 tabs), futuristic 3D TV interface (Three.js) |
| **🔄 Self-Modification** | Autonomous code reading, writing, editing with safety validation |
| **🩺 Self-Healing** | 6 health checks, auto-repair (pip install, syntax fix) |
| **🧪 Self-Testing** | 94 automated tests across 6 suites |
| **📊 Self-Improvement** | Autonomous code scanning, fixing, testing cycle |
| **🔮 Proactive Intelligence** | Pattern analysis, context hints, 30-min background loop |

---

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/timhofmann27-bot/Open-Jarvis.git
cd Open-Jarvis

# Install dependencies
pip install -r requirements.txt

# Configure API key
cp config/api_keys.json.example config/api_keys.json
# Edit config/api_keys.json with your Gemini API key

# Install Ollama (for local fallback)
# https://ollama.com/download
ollama pull tinyllama

# Launch
python main.py
```

### Prerequisites

- **Python 3.12+**
- **Windows 10/11** (some features Windows-specific)
- **Ollama** (optional, for local LLM fallback)
- **Gemini API key** from [Google AI Studio](https://aistudio.google.com/apikey)

---

## 🎯 Usage

### Voice
Say **"Jarvis"** or clap your hands to wake the assistant. Speak naturally — commands are processed via Gemini Live.

### Local Mode
When Gemini credits run out, switch to local mode:
```
"Jarvis, switch to local mode"
```
Or via dashboard. Requires Ollama + tinyllama (~700 MB RAM).

### Commands
```
"Jarvis, open Spotify"
"Jarvis, what's the weather?"
"Jarvis, scan my system for improvements"
"Jarvis, run the self-healing check"
"Jarvis, switch to local model"
"Jarvis, analyze my usage patterns"
```

### Keyboard
| Key | Action |
|-----|--------|
| F4 | Toggle mute |
| F11 | Toggle fullscreen |

---

## 🏗 Architecture

```
Open-Jarvis/
├── actions/          # Tool modules (smart home, system, media, etc.)
├── core/             # Core systems (memory, LLM, self-modification, etc.)
├── web_ui/           # Dashboard HTML + 3D TV interface
├── tv_interface/     # WebSocket TV streaming server
├── config/           # Configuration files (+ .example templates)
├── memory/           # Runtime memory data (gitignored)
├── main.py           # Central orchestrator + Gemini Live session
├── remote_server.py  # Dashboard HTTP API server
├── background_listener.py  # Wake word + clap detection
└── ui.py             # PyQt6 desktop interface
```

### Model Selection

| Model | RAM | Quality | Command |
|-------|-----|---------|---------|
| tinyllama (default) | ~700 MB | Basic | `ollama pull tinyllama` |
| phi3:mini | ~2.2 GB | Good | `ollama pull phi3:mini` |
| llama3.2:3b | ~2 GB | Good | `ollama pull llama3.2:3b` |

---

## 🧪 Testing

```bash
python -c "import sys; sys.path.insert(0, '.'); from core.test_suite import TestSuite, run_tests; t = TestSuite(); t.run_all()"
```

Or via Dashboard → Tests tab.

---

## 🐳 Docker / MCP Bridge

Open-Jarvis can connect to MCP (Model Context Protocol) servers running in Docker containers for expanded tool capabilities:

```bash
# Profile-based auto-discovery
# Configure in config/mcp.json
```

---

## 📄 License

MIT

---

## 🙌 Credits

Built with ❤️ for the open-source community. Inspired by Iron Man's J.A.R.V.I.S.
