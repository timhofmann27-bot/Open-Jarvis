# Setup Guide

Detailed installation instructions for Open-Jarvis.

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Windows 10 (1809+) | Windows 11 |
| Python | 3.12 | 3.12+ |
| RAM | 4 GB (8 GB w/ local LLM) | 16 GB |
| Storage | 2 GB | 5 GB (with models) |
| Network | For Gemini API | + Local LLM offline |
| Mic | Required for voice | USB headset recommended |

## Step 1: Clone & Install

```bash
git clone https://github.com/timhofmann27-bot/Open-Jarvis.git
cd Open-Jarvis
pip install -r requirements.txt
```

If you get pip errors, try:
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt --user
```

## Step 2: Configure API Keys

```bash
cp config/api_keys.json.example config/api_keys.json
```

Edit `config/api_keys.json`:

```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY_HERE",
  "openrouter_api_key": "",
  "os_system": "windows",
  "spotify_client_id": "",
  "spotify_client_secret": "",
  "spotify_redirect_uri": "http://localhost:8888/callback",
  "github_token": ""
}
```

Get a Gemini API key from: https://aistudio.google.com/apikey

## Step 3: Optional — Install Ollama (for local fallback)

1. Download: https://ollama.com/download
2. Install
3. Pull a small model:
   ```bash
   ollama pull tinyllama
   ```

Ollama runs in the background. JARVIS will auto-detect it.

## Step 4: Optional — Configure Smart Home

Edit `config/smart_home.json`:
```json
{
  "hue": {
    "bridge_ip": "192.168.1.100",
    "api_key": "YOUR_HUE_KEY"
  },
  "homeassistant": {
    "url": "http://192.168.1.200:8123",
    "token": "YOUR_HA_TOKEN"
  }
}
```

## Step 5: Optional — Configure Telegram Bot

1. Talk to [@BotFather](https://t.me/botfather) on Telegram
2. Create a bot, get the token
3. Get your user ID from [@userinfobot](https://t.me/userinfobot)
4. Edit `config/telegram.json`:
   ```json
   {
     "bot_token": "YOUR_BOT_TOKEN",
     "allowed_user_ids": ["YOUR_USER_ID"]
   }
   ```

## Step 6: Run

```bash
python main.py
```

The desktop UI will open. Say "Jarvis" to activate.

## Step 7 (Optional): Autostart on Boot

```bash
python setup_autostart.py
```

This installs a Windows Task Scheduler entry that starts the wake-word listener on login.

## Troubleshooting

### Microphone not detected
- Check Windows Settings → Privacy → Microphone
- Allow apps to access your microphone
- Test in another app first

### Ollama not detected
- Make sure `ollama serve` is running (or Ollama desktop is open)
- Check `ollama list` shows installed models
- JARVIS falls back to Gemini if Ollama is unavailable

### Gemini credits depleted
- Switch to local mode: "Jarvis, switch to local model"
- Or add billing at https://aistudio.google.com/apikey

### Self-healing errors
- Run the dashboard health check: http://localhost:8080/api/health
- Check `listener.log` for detailed errors
- Run the self-test suite: see [Testing](README.md#testing)

### See also
- [Architecture](ARCHITECTURE.md) — How it works internally
- [Tools Reference](TOOLS.md) — All available tools
- [Contributing](../CONTRIBUTING.md) — How to add features
