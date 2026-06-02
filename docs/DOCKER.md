# Docker Setup

Open-Jarvis can run in two modes:

| Mode | Where | Capabilities |
|------|-------|--------------|
| **Full** | Windows host | Voice, all system controls, smart home, TV, dashboard |
| **Headless** (Docker) | Any OS | Dashboard, memory, MCP, local LLM |

Docker is recommended for:
- Trying JARVIS without installing Python deps
- Running the **backend** (dashboard + LLM + memory) on a server
- CI/CD and reproducible builds
- macOS/Linux testing

## Quick Start

```bash
# 1. Clone
git clone https://github.com/timhofmann27-bot/Open-Jarvis.git
cd Open-Jarvis

# 2. Configure
cp .env.example .env
# Edit .env with your API keys

# 3. Build & start
docker compose up -d

# 4. Open dashboard
# http://localhost:8080
```

That's it. JARVIS + Ollama are running in containers.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 Your Windows PC                 │
│  ┌─────────────────┐      ┌──────────────────┐  │
│  │  python main.py │◄────►│ Docker Backend   │  │
│  │  (voice + UI)   │  WS  │  - JARVIS        │  │
│  └─────────────────┘      │  - Ollama (LLM)  │  │
│         │                 │  - MCP servers   │  │
│         │                 └──────────────────┘  │
│         ▼                          ▲            │
│  ┌─────────────────┐               │            │
│  │  System APIs    │      8080/8765 ports      │
│  └─────────────────┘                            │
└─────────────────────────────────────────────────┘
```

The Windows side handles voice + system control. The Docker side handles LLM + memory + MCP.

## Docker Images

| Image | Purpose | Size |
|-------|---------|------|
| `open-jarvis:latest` | Main JARVIS service | ~1.5 GB |
| `ollama/ollama:latest` | Local LLM server | ~1 GB (no models) + model size |

## Standalone Docker

```bash
# Just JARVIS (no LLM)
docker build -t open-jarvis .
docker run -p 8080:8080 -p 8765:8765 \
    -v jarvis-memory:/app/memory \
    -e GEMINI_API_KEY=your_key \
    open-jarvis

# Or with local LLM
docker run -d --name ollama -p 11434:11434 \
    -v ollama-data:/root/.ollama \
    ollama/ollama

# Pull a model (first time only)
docker exec -it ollama ollama pull tinyllama

# JARVIS connecting to it
docker run -p 8080:8080 -p 8765:8765 \
    -v jarvis-memory:/app/memory \
    -e OLLAMA_HOST=http://host.docker.internal:11434 \
    open-jarvis
```

## Configuration via .env

```bash
# Required
GEMINI_API_KEY=AIzaSy...

# Optional
OLLAMA_MODEL=tinyllama          # tinyllama, phi3:mini, llama3.2:3b
OLLAMA_PORT=11434
DASHBOARD_PORT=8080
TV_PORT=8765
JARVIS_LOCAL_MODE=1             # 1 = use local LLM, 0 = use Gemini
TZ=Europe/Berlin
```

## Volumes

| Volume | Purpose |
|--------|---------|
| `open-jarvis-memory` | ChromaDB vector store, stats, self-modification log |
| `open-jarvis-config` | Configuration files |
| `open-jarvis-ollama` | Downloaded Ollama models |

To inspect:
```bash
docker volume inspect open-jarvis-memory
```

To back up:
```bash
docker run --rm -v open-jarvis-memory:/data -v $(pwd):/backup \
    alpine tar czf /backup/jarvis-memory-$(date +%F).tar.gz /data
```

## Profiles

The compose file supports optional profiles:

```bash
# Add MCP servers (filesystem, GitHub)
docker compose --profile mcp up

# Add nginx web UI server
docker compose --profile webui up

# All together
docker compose --profile mcp --profile webui up
```

## Troubleshooting

### Container won't start
```bash
docker compose logs jarvis
docker compose logs ollama
```

### Ollama model not loaded
```bash
docker exec -it jarvis-ollama ollama list
docker exec -it jarvis-ollama ollama pull tinyllama
```

### Port conflicts
Change ports in `.env`:
```bash
DASHBOARD_PORT=9080
TV_PORT=9765
OLLAMA_PORT=11435
```

### Out of disk space
```bash
# Remove unused Ollama models
docker exec -it jarvis-ollama ollama rm unused-model

# Clean up Docker
docker system prune -a
```

### Can't access dashboard
- Check `docker compose ps` — all services should be "Up" or "healthy"
- Try `http://127.0.0.1:8080` instead of `localhost`
- On Windows: ensure Docker Desktop is running and WSL2 is enabled

## Limitations of Docker Mode

| Feature | Docker | Windows host |
|---------|--------|--------------|
| Voice input | ❌ (no mic) | ✅ |
| System control | ❌ (no Win32) | ✅ |
| Smart home (Hue) | ⚠️ (network only) | ✅ |
| TV control | ❌ (no GUI) | ✅ |
| Local LLM | ✅ (Ollama) | ✅ |
| Dashboard | ✅ | ✅ |
| Memory + Self-X | ✅ | ✅ |
| MCP servers | ✅ | ✅ |

For full features, run JARVIS on Windows. The Docker mode is best for the backend.

## Production Deployment

For production, consider:
- Use a reverse proxy (nginx, caddy) with TLS
- Set strong `REMOTE_TOKEN` in `remote_server.py`
- Use Docker secrets for API keys
- Enable log aggregation (Loki, ELK)
- Set resource limits in compose:

```yaml
services:
  jarvis:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```
