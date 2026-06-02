# Contributing to Open-Jarvis

First off, thank you for considering contributing to Open-Jarvis! 🎉

## Code of Conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/). By participating, you agree to uphold this code.

## How to Contribute

### Reporting Bugs
- Use the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md) template
- Include Python version, OS, Ollama version (if applicable)
- Provide logs from `listener.log` and `/api/health` from the dashboard

### Suggesting Features
- Use the [Feature Request](.github/ISSUE_TEMPLATE/feature_request.md) template
- Explain the use case, not just the solution

### Pull Requests
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run the test suite: `python -c "from core.test_suite import TestSuite, run_tests; t = TestSuite(); t.run_all()"`
5. Update documentation (README, CHANGELOG, etc.)
6. Commit with clear messages
7. Push to your fork
8. Open a [Pull Request](.github/PULL_REQUEST_TEMPLATE.md)

## Development Setup

```bash
git clone https://github.com/timhofmann27-bot/Open-Jarvis.git
cd Open-Jarvis
pip install -r requirements-dev.txt
cp config/api_keys.json.example config/api_keys.json
# Edit config/api_keys.json
```

## Project Structure

| Path | Purpose |
|------|---------|
| `actions/` | Tool modules (one per domain) |
| `core/` | Core systems (memory, LLM, self-X) |
| `web_ui/` | Browser-based UI (dashboard + 3D TV) |
| `tv_interface/` | WebSocket TV streaming server |
| `config/` | Configuration templates (gitignored: real configs) |
| `main.py` | Central orchestrator |
| `ui.py` | PyQt6 desktop interface |

## Coding Standards

- Python 3.12+
- Follow PEP 8
- Use type hints for new code
- Add docstrings to public functions
- Keep functions focused and small
- Use async/await consistently in main.py

## Adding a New Tool

1. Create `actions/your_tool.py` with a main function
2. Add a tool declaration in `main.py` `TOOL_DECLARATIONS`
3. Add a handler in `_execute_tool()` in `main.py`
4. Add a test in `core/test_suite.py`
5. Update `docs/TOOLS.md` with the new tool

## Adding a New Core System

1. Create `core/your_system.py`
2. Wire it up in `main.py` `__init__`
3. Add API endpoints to `remote_server.py` (if needed)
4. Add dashboard UI in `web_ui/dashboard.html` (if applicable)
5. Add tests

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
