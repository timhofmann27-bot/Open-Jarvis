# Open-Jarvis Dockerfile
# Builds a headless (no GUI) version that runs:
#   - HTTP dashboard on port 8080
#   - TV WebSocket on port 8765
#   - MCP bridge
# Voice + Windows-native features require running on Windows host.
#
# Build:  docker build -t open-jarvis .
# Run:    docker run -p 8080:8080 -p 8765:8765 open-jarvis
# Compose: docker compose up (recommended)

FROM python:3.12-slim AS base

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        portaudio19-dev \
        libasound2 \
        libpulse0 \
        ffmpeg \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies first (better Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 jarvis && \
    mkdir -p /app/memory /app/config && \
    chown -R jarvis:jarvis /app

USER jarvis

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    JARVIS_HEADLESS=1 \
    JARVIS_LOCAL_MODE=1 \
    DASHBOARD_PORT=8080 \
    TV_PORT=8765

# Expose ports
EXPOSE 8080 8765

# Health check via dashboard
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8080/api/status || exit 1

# Default: run dashboard + local LLM mode (works without Gemini API)
CMD ["python", "-c", "import sys; sys.path.insert(0, '/app'); from main import JarvisLive; from ui import JarvisUI; import asyncio; ui = JarvisUI('face.png'); jarvis = JarvisLive(ui); jarvis._use_local_llm = True; asyncio.run(jarvis.run())"]
