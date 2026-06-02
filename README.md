# 🤖 Open-Jarvis

### The Ultimate Open-Source JARVIS AI Assistant

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Windows](https://img.shields.io/badge/Platform-Windows-0078d4.svg)](https://www.microsoft.com/windows)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Tests](https://img.shields.io/badge/Tests-94%20passing-brightgreen.svg)](docs/TOOLS.md)

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

For a detailed walkthrough see **[docs/SETUP.md](docs/SETUP.md)**.

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

## 📚 Documentation

- **[Setup Guide](docs/SETUP.md)** — Detailed installation walkthrough
- **[Architecture](docs/ARCHITECTURE.md)** — How it works internally
- **[Tools Reference](docs/TOOLS.md)** — All 57+ tools explained

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines, and check the [issue templates](.github/ISSUE_TEMPLATE/).

## 🔒 Security

See [SECURITY.md](SECURITY.md) for security policies and how to report vulnerabilities.

## 📊 Project Status

- **Version**: 1.0.0
- **Status**: Production-ready
- **Tests**: 94 self-tests (97% pass rate)
- **Tools**: 57+ native + 16+ MCP dynamic
- **Lines of code**: ~8,000+

## 🗺 Roadmap

- [ ] Multi-user voice profiles
- [ ] Cloud sync of memory
- [ ] Mobile app (React Native)
- [ ] Plugin marketplace
- [ ] Multi-language support
- [ ] Custom wake-word training

## 📄 License

[MIT](LICENSE) © 2026 Open-Jarvis Contributors

## 🙌 Credits

Built with ❤️ for the open-source community. Inspired by Iron Man's J.A.R.V.I.S.

Special thanks to:
- Google Gemini Live for the multimodal AI
- Ollama for local LLM inference
- ChromaDB for vector memory
- The open-source Python AI ecosystem
