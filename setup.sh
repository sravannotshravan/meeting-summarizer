#!/usr/bin/env bash
# ==============================================================================
# Meeting Summarizer - Local Environment Setup Script
# ==============================================================================
set -e

# Color helpers
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BOLD="\033[1m"
NC="\033[0m"

echo -e "${BOLD}${BLUE}======================================================${NC}"
echo -e "${BOLD}${BLUE}   Meeting Summarizer - Setup & Dependency Installer  ${NC}"
echo -e "${BOLD}${BLUE}======================================================${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ------------------------------------------------------------------------------
# 1. Check System Prerequisites
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[1/6] Checking system tools...${NC}"
MISSING_PKGS=()

check_tool() {
    local name="$1"
    shift
    for alt in "$@"; do
        if command -v "$alt" &>/dev/null; then
            echo -e "  [✓] $name is installed ($alt)"
            return 0
        fi
    done
    echo -e "  [✗] $name is NOT found"
    MISSING_PKGS+=("$name")
    return 1
}

check_tool "python3" "python3" "python"
check_tool "ffmpeg" "ffmpeg"
check_tool "node" "node" "nodejs" "node.exe"
check_tool "npm" "npm" "npm.cmd"
check_tool "git" "git"
check_tool "cmake" "cmake"
check_tool "curl" "curl"

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo -e "\n${YELLOW}Missing recommended system packages: ${MISSING_PKGS[*]}${NC}"
    echo -e "On Ubuntu/Debian, install them using:"
    echo -e "  ${BOLD}sudo apt update && sudo apt install -y python3 python3-venv python3-pip ffmpeg nodejs npm git cmake build-essential curl${NC}"
fi

# ------------------------------------------------------------------------------
# 2. Environment Configuration (.env)
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[2/6] Configuring environment (.env)...${NC}"
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "  ${GREEN}[✓] Created .env from .env.example${NC}"
    else
        echo "HF_TOKEN=" > .env
        echo "LLAMA_MODELS_DIR=./models" >> .env
        echo "LLAMA_MODEL_FILE=qwen3-8b.gguf" >> .env
        echo "LLAMA_N_GPU_LAYERS=0" >> .env
        echo "FRONTEND_PORT=5173" >> .env
        echo "BACKEND_PORT=8000" >> .env
        echo "LLAMA_PORT=8080" >> .env
        echo -e "  ${GREEN}[✓] Created default .env file${NC}"
    fi
    echo -e "  ${YELLOW}Remember to add your Hugging Face token in .env for pyannote speaker diarization!${NC}"
else
    echo -e "  [✓] .env already exists"
fi

# ------------------------------------------------------------------------------
# 3. Python Virtual Environment & Dependencies
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[3/6] Setting up Python virtual environment (.venv)...${NC}"
if [ ! -d ".venv" ]; then
    echo -e "  Creating virtual environment with python3..."
    python3 -m venv .venv
fi

# Activate venv
# shellcheck disable=SC1091
source .venv/bin/activate
echo -e "  [✓] Virtual environment activated (.venv)"

echo -e "  Installing/Updating Python requirements..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo -e "  ${GREEN}[✓] Python dependencies installed successfully${NC}"

# ------------------------------------------------------------------------------
# 4. Whisper.cpp Setup & Model Download
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[4/6] Setting up whisper.cpp & transcription model...${NC}"
WHISPER_DIR=""

if [ -x "$HOME/whisper.cpp/build/bin/whisper-cli" ]; then
    WHISPER_DIR="$HOME/whisper.cpp"
    echo -e "  [✓] Found whisper.cpp in $HOME/whisper.cpp"
elif [ -x "$SCRIPT_DIR/whisper.cpp/build/bin/whisper-cli" ]; then
    WHISPER_DIR="$SCRIPT_DIR/whisper.cpp"
    echo -e "  [✓] Found whisper.cpp in $SCRIPT_DIR/whisper.cpp"
else
    echo -e "  whisper.cpp not found. Cloning and building whisper.cpp in $HOME/whisper.cpp..."
    git clone https://github.com/ggerganov/whisper.cpp.git "$HOME/whisper.cpp"
    cd "$HOME/whisper.cpp"
    cmake -B build
    cmake --build build --config Release -j "$(nproc)"
    cd "$SCRIPT_DIR"
    WHISPER_DIR="$HOME/whisper.cpp"
    echo -e "  ${GREEN}[✓] whisper.cpp compiled successfully${NC}"
fi

# Check whisper model (ggml-small.bin)
WHISPER_MODEL_PATH="$WHISPER_DIR/models/ggml-small.bin"
if [ ! -f "$WHISPER_MODEL_PATH" ] || [ ! -s "$WHISPER_MODEL_PATH" ]; then
    echo -e "  Downloading Whisper ggml-small model..."
    cd "$WHISPER_DIR/models"
    bash ./download-ggml-model.sh small
    cd "$SCRIPT_DIR"
    echo -e "  ${GREEN}[✓] Whisper ggml-small model downloaded${NC}"
else
    echo -e "  [✓] Whisper ggml-small model present: $WHISPER_MODEL_PATH"
fi

# ------------------------------------------------------------------------------
# 5. Local LLM / llama.cpp Setup
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[5/6] Setting up LLM model and llama-server...${NC}"
mkdir -p models

# Check if model exists or link from cache
if [ ! -f "models/qwen3-8b.gguf" ]; then
    # Try finding Qwen GGUF in huggingface hub cache
    CACHED_MODEL=$(find "$HOME/.cache/huggingface/hub" -name "*Qwen3-8B*.gguf" 2>/dev/null | head -n 1)
    if [ -n "$CACHED_MODEL" ] && [ -f "$CACHED_MODEL" ]; then
        echo -e "  Linking cached Qwen model from $CACHED_MODEL -> models/qwen3-8b.gguf"
        ln -sf "$CACHED_MODEL" models/qwen3-8b.gguf
    else
        echo -e "  ${YELLOW}No LLM GGUF model found at ./models/qwen3-8b.gguf${NC}"
        echo -e "  You can download Qwen3-8B GGUF with:"
        echo -e "  ${BOLD}huggingface-cli download Qwen/Qwen3-8B-GGUF Qwen3-8B-Q4_K_M.gguf --local-dir ./models --local-dir-use-symlinks False${NC}"
        echo -e "  and symlink/rename it to ./models/qwen3-8b.gguf"
    fi
else
    echo -e "  [✓] LLM model found at models/qwen3-8b.gguf"
fi

# Check llama-server
if command -v llama-server &>/dev/null; then
    echo -e "  [✓] llama-server available in PATH"
elif [ -x "$HOME/llama.cpp/build/bin/llama-server" ]; then
    echo -e "  [✓] llama-server found at $HOME/llama.cpp/build/bin/llama-server"
elif [ -x "$SCRIPT_DIR/llama.cpp/build/bin/llama-server" ]; then
    echo -e "  [✓] llama-server found at $SCRIPT_DIR/llama.cpp/build/bin/llama-server"
else
    echo -e "  ${YELLOW}llama-server binary not found in standard locations.${NC}"
    echo -e "  To build llama.cpp:"
    echo -e "    git clone https://github.com/ggerganov/llama.cpp.git ~/llama.cpp"
    echo -e "    cd ~/llama.cpp && cmake -B build && cmake --build build --config Release -j \$(nproc)"
fi

# ------------------------------------------------------------------------------
# 6. Frontend Dependencies
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}[6/6] Installing frontend dependencies...${NC}"
if [ -d "frontend" ]; then
    cd frontend
    if [ ! -d "node_modules" ]; then
        echo -e "  Running npm install in frontend/..."
        npm install --silent
    else
        echo -e "  [✓] Frontend node_modules already installed"
    fi
    cd "$SCRIPT_DIR"
    echo -e "  ${GREEN}[✓] Frontend setup complete${NC}"
fi

echo -e "\n${BOLD}${GREEN}======================================================${NC}"
echo -e "${BOLD}${GREEN}   Setup Completed Successfully!                      ${NC}"
echo -e "${BOLD}${GREEN}   Run ./start.sh to launch the application.          ${NC}"
echo -e "${BOLD}${GREEN}======================================================${NC}\n"
