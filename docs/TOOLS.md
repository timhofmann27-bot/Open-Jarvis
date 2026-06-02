# Open-Jarvis Tools Reference

All 57+ tools are exposed to the LLM via Gemini Live's function calling or invoked manually in local mode.

## Categories

### 🖥 System & Apps
| Tool | Description |
|------|-------------|
| `open_app` | Open applications or URLs |
| `desktop` | Desktop actions (screenshot, mouse, keyboard) |
| `computer_settings` | 59 Windows system settings |
| `computer_use` | Autonomous visual PC control (vision + pyautogui) |
| `system_integration` | 19 system actions (processes, services, registry, power, wallpaper, etc.) |
| `reminder` | Set reminders |
| `network_status` | Network diagnostics |

### 📁 Files
| Tool | Description |
|------|-------------|
| `file_processor` | File operations with AI analysis |
| `file_controller` | File system operations |
| `code_helper` | Code analysis and help |

### 🌐 Web & Search
| Tool | Description |
|------|-------------|
| `web_search` | Web search via Google |
| `browser_control` | Browser automation |
| `youtube_video` | YouTube video search and play |

### 📧 Communication
| Tool | Description |
|------|-------------|
| `email_calendar` | Email and calendar management |
| `send_message` | Send messages |
| `telegram_bot` | Telegram integration |

### 🏠 Smart Home & Hardware
| Tool | Description |
|------|-------------|
| `smart_home` | Hue, Shelly, Home Assistant |
| `bt_control` | Bluetooth scan and connect |

### 📺 Media & Display
| Tool | Description |
|------|-------------|
| `tv_control` | TV control (SSDP discovery) |
| `wireless_display` | Open Miracast flyout |
| `ytmusic` | YouTube Music |
| `hyper_connectivity` | Spotify (8 actions) + GitHub (6 actions) |
| `generative_graphics` | Chart.js, Three.js, Pillow images |
| `worldmonitor` | Crisis reports, click layers |

### 🎮 Other
| Tool | Description |
|------|-------------|
| `weather_report` | Weather forecasts |
| `flight_finder` | Flight search |
| `game_updater` | Game launcher and updater |
| `obsidian_control` | Obsidian vault integration |

### 🧠 Self-Management
| Tool | Description |
|------|-------------|
| `save_memory` | Store a fact in memory |
| `memory_recall` | Semantic search memory |
| `memory_stats` | Memory statistics |
| `self_analyze_patterns` | Run pattern analysis |
| `self_health_check` | System health check |
| `self_heal` | Trigger auto-repair |
| `self_scan_improvements` | Scan code for issues |
| `self_run_improvements` | Run improvement cycle |
| `self_list_sources` | List project files |
| `self_read_code` | Read file content |
| `self_validate_code` | Validate Python syntax |
| `self_write_code` | Create new files |
| `self_edit_code` | Edit existing files |
| `switch_model` | Toggle Gemini/local LLM |
| `shutdown_jarvis` | Graceful shutdown |

### 🔌 MCP Tools (Dynamic)
Additional tools loaded dynamically from MCP servers in Docker containers. See `core/mcp_bridge.py` and `config/mcp.json`.

## Adding a New Tool

1. **Create the action module** in `actions/your_tool.py`:
   ```python
   def your_tool_action(param1: str, param2: int) -> str:
       """Your tool description."""
       return f"Did {param1} {param2} times"
   ```

2. **Declare the tool** in `main.py`:
   ```python
   {
       "name": "your_tool",
       "description": "Does something useful.",
       "parameters": {
           "type": "OBJECT",
           "properties": {
               "param1": {"type": "STRING", "description": "First param"},
               "param2": {"type": "INTEGER", "description": "Second param"},
           },
           "required": ["param1", "param2"]
       }
   }
   ```

3. **Add a handler** in `_execute_tool()`:
   ```python
   elif name == "your_tool":
       result = your_tool_action(args.get("param1"), int(args.get("param2", 0)))
   ```

4. **Test it**:
   - Add a test case in `core/test_suite.py`
   - Run the test suite
   - Try it via voice: "Jarvis, your tool with param1=X"
