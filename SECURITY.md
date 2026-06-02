# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

Please report security vulnerabilities privately by emailing [security@open-jarvis.local](mailto:security@open-jarvis.local) (placeholder) or by opening a [GitHub issue](https://github.com/timhofmann27-bot/Open-Jarvis/issues) with the `security` label.

**Do not disclose vulnerabilities publicly until a fix has been released.**

## Security Considerations

### Self-Modification System
Open-Jarvis includes a self-modification system that can autonomously read, write, and edit source code. The following safeguards are in place:

- **Project-root restriction**: `core/self_modifier.py:_resolve()` ensures all file operations stay within the project root
- **Backup files**: `.bak` files are created before any edit
- **Syntax validation**: Python files are validated with `ast.parse()` before being saved
- **Audit log**: All modifications are logged to `memory/self_modifications.json`

### API Keys & Secrets
- All sensitive configuration files are gitignored (see `.gitignore`)
- Template files (`.example`) are provided for safe onboarding
- Never commit real API keys, tokens, or passwords

### Local LLM Mode
When using local LLM (Ollama), all processing happens on your machine. No data is sent to external servers.

### Network Exposure
The remote server (`remote_server.py`) listens on `0.0.0.0:8080` by default. This exposes the dashboard to your local network. For production use:
- Use a strong token (configured in `remote_server.py`)
- Bind to `127.0.0.1` if remote access is not needed
- Use a reverse proxy with TLS for internet exposure
