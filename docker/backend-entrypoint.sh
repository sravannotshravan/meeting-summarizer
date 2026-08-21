#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${WHISPER_MODEL_PATH:-/models/whisper/ggml-small.bin}"
MODEL_URL="${WHISPER_MODEL_URL:-https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin?download=true}"

if [ ! -s "$MODEL_PATH" ]; then
  if [ -z "${HF_TOKEN:-}" ]; then
    echo "HF_TOKEN is required to download the Whisper model and load pyannote." >&2
    exit 1
  fi
  echo "Downloading Whisper ggml-small model..."
  mkdir -p "$(dirname "$MODEL_PATH")"
  curl --fail --location --retry 5 --header "Authorization: Bearer ${HF_TOKEN}" "$MODEL_URL" --output "$MODEL_PATH"
fi

exec "$@"
