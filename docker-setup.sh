#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Desktop or Docker Engine with Compose." >&2
  exit 1
fi

if [ -z "${HF_TOKEN:-}" ]; then
  read -r -s -p "Enter your Hugging Face token: " HF_TOKEN
  echo
fi

if [ -z "$HF_TOKEN" ]; then
  echo "A Hugging Face token is required for pyannote and Whisper model setup." >&2
  exit 1
fi

ENV_FILE="$ROOT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then cp "$ROOT_DIR/.env.example" "$ENV_FILE"; fi
TEMP_ENV="$(mktemp)"
grep -v '^HF_TOKEN=' "$ENV_FILE" > "$TEMP_ENV" || true
printf 'HF_TOKEN=%s\n' "$HF_TOKEN" >> "$TEMP_ENV"
mv "$TEMP_ENV" "$ENV_FILE"

echo "Building CharchaNotes containers..."
docker compose build
echo "Starting CharchaNotes..."
docker compose up -d
echo
docker compose ps
echo
echo "Web UI:     http://localhost:${FRONTEND_PORT:-5173}"
echo "API docs:   http://localhost:${BACKEND_PORT:-8000}/docs"
echo "llama.cpp:  http://localhost:${LLAMA_PORT:-8080}"
echo
echo "Watch logs with: docker compose logs -f"
