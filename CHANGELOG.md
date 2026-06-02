# Changelog

All notable changes to Open-Jarvis will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub issue & PR templates
- Contributing guidelines
- Architecture documentation
- Development requirements file
- Code quality infrastructure (ruff, mypy, pre-commit, Makefile)
- Docker deployment (Dockerfile, docker-compose, .env.example)
- Migrated `file_processor.py` from deprecated `google.generativeai` to `google.genai`

### Changed
- **BREAKING**: Removed deprecated `google-generativeai` package dependency
- `file_processor.py` uses new `_generate()` helper for all Gemini calls (12 sites)

### Fixed
- Eliminated `FutureWarning` from `google.generativeai` deprecation

## [1.0.0] - 2026-06-02

### Added
- **Voice Control**: Wake word detection (openWakeWord) + clap detection
- **Gemini Live Integration**: Real-time bidirectional audio streaming
- **Local LLM Fallback**: Ollama (tinyllama/phi3) for offline operation
- **Long-Term Memory**: ChromaDB vector database with semantic recall
- **Reflection System**: Personality growth + depth reflection every 10 interactions
- **Tool System**: 57+ native tools across 32 action modules
- **MCP Bridge**: Dynamic tool loading from Docker containers
- **Self-Modification**: Autonomous code reading, writing, editing (with safety)
- **Self-Healing**: 6 health checks + auto-repair (pip install, syntax fix)
- **Self-Improvement**: Autonomous code scanning, fixing, testing cycle
- **Self-Testing**: 94 automated tests across 6 suites
- **Proactive Intelligence**: Pattern analysis + context hints, 30-min background loop
- **Smart Home**: Philips Hue, Shelly, Home Assistant
- **System Integration**: 19 Windows actions (processes, services, registry, power)
- **TV Interface**: WebSocket streaming (port 8765) + futuristic 3D interface
- **Dashboard v4**: 9 tabs (Overview, Health, Memory, Tools, Docker, TV&BT, Config, Logs, Tests)
- **Generative Graphics**: Chart.js, Three.js 3D, Pillow images
- **Hyper Connectivity**: Spotify (8 actions) + GitHub (6 actions)
- **Wireless Display**: Miracast via Win+K Connect flyout
- **Computer Use**: Autonomous visual PC control (screenshot + grid + pyautogui)
- **World Monitor**: Crisis report, click_layer, focus, layers
- **Telegram Bot**: Mobile remote control
- **Proactive Notifier**: Background scheduler
- **Plugin Loader**: Hot-loaded plugin system
- **Wireless Display**: Miracast support

### Security
- All sensitive config files (api_keys, telegram, obsidian, email) gitignored
- Template files (`.example`) for safe onboarding
- Project-root restriction on self-modification
- `.bak` backup files before any code edit
- Syntax validation before writes

[Unreleased]: https://github.com/timhofmann27-bot/Open-Jarvis/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/timhofmann27-bot/Open-Jarvis/releases/tag/v1.0.0
