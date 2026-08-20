#!/usr/bin/env bash
# ==============================================================================
# Meeting Summarizer - Startup & Service Runner Script
# ==============================================================================
set -e

# Color helpers
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
RED="\033[0;31m"
BOLD="\033[1m"
NC="\033[0m"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BOLD}${CYAN}======================================================${NC}"
echo -e "${BOLD}${CYAN}            Starting Meeting Summarizer Stack         ${NC}"
echo -e "${BOLD}${CYAN}======================================================${NC}"

# Check if setup has been executed
if [ ! -d ".venv" ] || [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}Initial setup required. Running setup.sh first...${NC}\n"
    ./setup.sh
fi

# Load .env file if it exists
if [ -f .env ]; then
    echo -e "Loading environment variables from .env..."
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

# Set default ports and paths if not specified
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
LLAMA_PORT="${LLAMA_PORT:-8080}"
LLAMA_MODELS_DIR="${LLAMA_MODELS_DIR:-./models}"
LLAMA_MODEL_FILE="${LLAMA_MODEL_FILE:-qwen3-8b.gguf}"
LLAMA_N_GPU_LAYERS="${LLAMA_N_GPU_LAYERS:-0}"

# Auto-detect whisper.cpp path
if [ -z "$WHISPER_CLI_PATH" ]; then
    if [ -x "$HOME/whisper.cpp/build/bin/whisper-cli" ]; then
        export WHISPER_CLI_PATH="$HOME/whisper.cpp/build/bin/whisper-cli"
        export WHISPER_MODEL_PATH="$HOME/whisper.cpp/models/ggml-small.bin"
    elif [ -x "$SCRIPT_DIR/whisper.cpp/build/bin/whisper-cli" ]; then
        export WHISPER_CLI_PATH="$SCRIPT_DIR/whisper.cpp/build/bin/whisper-cli"
        export WHISPER_MODEL_PATH="$SCRIPT_DIR/whisper.cpp/models/ggml-small.bin"
    fi
fi

# Auto-detect llama-server binary
LLAMA_BIN=""
if command -v llama-server &>/dev/null; then
    LLAMA_BIN="llama-server"
elif [ -x "$HOME/llama.cpp/build/bin/llama-server" ]; then
    LLAMA_BIN="$HOME/llama.cpp/build/bin/llama-server"
elif [ -x "$SCRIPT_DIR/llama.cpp/build/bin/llama-server" ]; then
    LLAMA_BIN="$SCRIPT_DIR/llama.cpp/build/bin/llama-server"
fi

PIDS=()

cleanup() {
    echo -e "\n\n${YELLOW}Shutting down all services...${NC}"
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    wait 2>/dev/null || true
    echo -e "${GREEN}All services stopped cleanly.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# ------------------------------------------------------------------------------
# 1. Start LLM Server (llama-server) if available
# ------------------------------------------------------------------------------
LLAMA_MODEL_PATH="$LLAMA_MODELS_DIR/$LLAMA_MODEL_FILE"

# Check if something is already listening on LLAMA_PORT
if curl -s "http://127.0.0.1:$LLAMA_PORT/health" &>/dev/null || lsof -i :"$LLAMA_PORT" &>/dev/null 2>&1; then
    echo -e "${GREEN}[✓] LLM server is already running on http://127.0.0.1:$LLAMA_PORT${NC}"
elif [ -n "$LLAMA_BIN" ] && [ -f "$LLAMA_MODEL_PATH" ]; then
    echo -e "${CYAN}[1/3] Starting llama-server on port $LLAMA_PORT...${NC}"
    "$LLAMA_BIN" \
        -m "$LLAMA_MODEL_PATH" \
        --port "$LLAMA_PORT" \
        --host 0.0.0.0 \
        -c 8192 \
        -ngl "$LLAMA_N_GPU_LAYERS" > llama-server.log 2>&1 &
    LLAMA_PID=$!
    PIDS+=("$LLAMA_PID")
    echo -e "      llama-server started (PID: $LLAMA_PID, log: llama-server.log)"
else
    echo -e "${YELLOW}[!] Notice: Local llama-server was not started automatically.${NC}"
    if [ ! -f "$LLAMA_MODEL_PATH" ]; then
        echo -e "    Reason: Model file not found at $LLAMA_MODEL_PATH"
    fi
    if [ -z "$LLAMA_BIN" ]; then
        echo -e "    Reason: llama-server executable not found"
    fi
    echo -e "    If you run an external LLM server or Ollama, set LLAMA_URL in .env"
fi

# ------------------------------------------------------------------------------
# 2. Start FastAPI Backend Server
# ------------------------------------------------------------------------------
echo -e "${CYAN}[2/3] Starting FastAPI Backend on port $BACKEND_PORT...${NC}"
# shellcheck disable=SC1091
source .venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload > backend.log 2>&1 &
BACKEND_PID=$!
PIDS+=("$BACKEND_PID")
echo -e "      FastAPI backend started (PID: $BACKEND_PID, log: backend.log)"

# ------------------------------------------------------------------------------
# 3. Start Frontend Dev Server
# ------------------------------------------------------------------------------
echo -e "${CYAN}[3/3] Starting Frontend Dev Server on port $FRONTEND_PORT...${NC}"
(
    cd frontend
    npm run dev -- --host --port "$FRONTEND_PORT" > ../frontend.log 2>&1
) &
FRONTEND_PID=$!
PIDS+=("$FRONTEND_PID")
echo -e "      Frontend dev server started (PID: $FRONTEND_PID, log: frontend.log)"

# ------------------------------------------------------------------------------
# Ready Banner
# ------------------------------------------------------------------------------
sleep 2

echo -e "\n${BOLD}${GREEN}======================================================${NC}"
echo -e "${BOLD}${GREEN}   Meeting Summarizer Stack is Running!               ${NC}"
echo -e "${BOLD}${GREEN}======================================================${NC}"
echo -e "  🌐 ${BOLD}Web UI:${NC}        ${CYAN}http://localhost:${FRONTEND_PORT}${NC}"
echo -e "  🔌 ${BOLD}Backend API:${NC}   ${CYAN}http://localhost:${BACKEND_PORT}${NC}"
echo -e "  📚 ${BOLD}API Docs:${NC}      ${CYAN}http://localhost:${BACKEND_PORT}/docs${NC}"
echo -e "  🤖 ${BOLD}LLM Server:${NC}    ${CYAN}http://localhost:${LLAMA_PORT}${NC}"
echo -e "\n  Logs: ${BOLD}backend.log${NC}, ${BOLD}frontend.log${NC}, ${BOLD}llama-server.log${NC}"
echo -e "  Press ${RED}Ctrl+C${NC} anytime to stop all services.\n"

# Keep the script running to hold child processes
while true; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo -e "${RED}[!] Backend process crashed. Check backend.log for details:${NC}"
        tail -n 20 backend.log
        break
    fi
    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo -e "${RED}[!] Frontend process stopped. Check frontend.log for details:${NC}"
        tail -n 20 frontend.log
        break
    fi
    sleep 2
done
