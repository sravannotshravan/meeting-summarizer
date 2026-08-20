# MeetingAI

A fully local, privacy-first AI meeting summarizer. Upload an audio or video recording and get back a speaker-aware transcript with Spotify lyrics-style playback and a structured AI summary — all processed on your own machine with no cloud APIs.

## What it does

1. **Transcribes** speech to text using [whisper.cpp](https://github.com/ggerganov/whisper.cpp)
2. **Identifies speakers** using [pyannote](https://github.com/pyannote/pyannote-audio) speaker diarization
3. **Aligns** transcript segments to the correct speaker by temporal overlap
4. **Summarizes** the meeting using [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) running locally via [llama.cpp](https://github.com/ggerganov/llama.cpp)
5. **Interactive UI**: Real-time synchronized lyrics-style transcript scrolling + click-to-seek playback.

The output is a structured JSON summary containing:

- A concise meeting overview
- Key discussion points
- Decisions made
- Action items with assignees and deadlines

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (React 19 + Vite + TypeScript + Nginx)               │
│  Dashboard · Synced Transcript · Audio Player · Summary UI      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST (localhost:5173 / localhost:8000)
┌──────────────────────────┴──────────────────────────────────────┐
│  API (FastAPI + BackgroundTasks)                                │
│  Upload · List · Status polling · SQLite database (meetings.db) │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│  AI Pipeline                                                    │
│                                                                 │
│  Audio ─→ whisper-cli ─→ pyannote ─→ alignment ─→ Qwen3-8B    │
│            (STT)       (diarize)    (speakers)    (summarize)   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────────┐
│  Storage                                                        │
│  SQLite (meetings.db) + filesystem (data/meetings/{id}/)        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🐳 Quickstart with Docker Compose

The easiest way to run the entire stack (llama.cpp server, backend with whisper + pyannote, and frontend) is with Docker.

### 1. Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/)
- A [Hugging Face Token](https://huggingface.co/settings/tokens) with accepted terms for [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
- A GGUF model file (e.g. `Qwen/Qwen3-8B-GGUF` placed in `./models/qwen3-8b.gguf`)

### 2. Configure Environment

Copy `.env.example` to `.env` and configure your settings:

```bash
cp .env.example .env
```

Edit `.env`:

```env
HF_TOKEN=hf_your_actual_token_here
LLAMA_MODELS_DIR=./models
LLAMA_MODEL_FILE=qwen3-8b.gguf
LLAMA_N_GPU_LAYERS=0
```

### 3. Start the Application

```bash
docker compose up --build
```

- **Web UI**: Open [http://localhost:5173](http://localhost:5173)
- **Backend API**: Accessible at [http://localhost:8000](http://localhost:8000)
- **LLM Server**: Accessible at [http://localhost:8080](http://localhost:8080)

---

## 🛠 Manual Local Setup

### 1. Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **whisper.cpp** — built at `~/whisper.cpp/build/bin/whisper-cli`
- **Whisper model** — `ggml-small.bin` at `~/whisper.cpp/models/ggml-small.bin`
- **llama.cpp** — `llama-server` running on port `8080`
- **Hugging Face Token** with access to `pyannote/speaker-diarization-community-1`

### 2. Python Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Start LLM Server (llama-server)

```bash
llama-server \
  -m /path/to/qwen3-8b.gguf \
  --port 8080 \
  -ngl 99
```

### 4. Run API Server

```bash
uvicorn api.main:app --reload --port 8000
```

### 5. Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Project Structure

```
meeting-summarizer/
├── ai/                          # AI pipeline
│   ├── pipeline.py              # Main orchestrator (Whisper + Pyannote + LLM)
│   ├── summarizer.py            # LLM summarization (Qwen3-8B)
│   ├── diarization.py           # Speaker diarization (pyannote)
│   └── alignment.py             # Whisper ↔ diarization temporal alignment
│
├── api/                         # REST API
│   └── main.py                  # FastAPI app with background tasks
│
├── backend/                     # Storage layer
│   ├── database.py              # SQLite connection + schema
│   ├── models.py                # Meeting dataclass
│   └── storage.py               # Meeting CRUD & artifact operations
│
├── frontend/                    # Web UI (React 19 + Vite + TypeScript)
│   ├── src/
│   │   ├── App.tsx              # Dashboard (meetings list, stats, search)
│   │   ├── components/
│   │   │   └── NewMeetingModal.tsx # Drag-and-drop recording upload modal
│   │   ├── pages/
│   │   │   └── MeetingPage.tsx  # Synced lyrics player + AI summary view
│   │   ├── lib/
│   │   │   └── api.ts           # Typed API client
│   │   └── types/
│   │       └── meeting.ts       # TypeScript interfaces
│   ├── nginx.conf               # Production Nginx reverse proxy
│   └── package.json
│
├── docker-compose.yml           # Multi-service orchestration
├── Dockerfile.backend           # Multi-stage Python + Whisper + Pyannote
├── Dockerfile.frontend          # Multi-stage Node + Vite + Nginx
├── requirements.txt             # Backend dependencies
└── data/                        # Persistent runtime data
    ├── meetings.db              # SQLite database
    └── meetings/{uuid}/         # Per-meeting recordings & transcripts
```

---

## API Reference

| Method   | Endpoint                            | Description                                      |
|:---------|:------------------------------------|:-------------------------------------------------|
| `GET`    | `/health`                           | API health check                                 |
| `GET`    | `/meetings`                         | List all meetings (ordered newest first)         |
| `POST`   | `/meetings`                         | Upload recording (`multipart/form-data`)         |
| `GET`    | `/meetings/{id}`                    | Get meeting status & metadata                    |
| `GET`    | `/meetings/{id}/transcript`         | Get raw Whisper transcript                       |
| `GET`    | `/meetings/{id}/speaker-transcript` | Get speaker-aligned transcript                   |
| `GET`    | `/meetings/{id}/summary`            | Get structured AI summary                        |
| `GET`    | `/meetings/{id}/audio`              | Stream or download original recording            |
| `DELETE` | `/meetings/{id}`                    | Delete meeting and its associated files          |

---

## Summary Output Format

```json
{
  "summary": "Brief overview of the discussion...",
  "key_points": [
    "Discussion about the new architecture",
    "Agreed to move forward with the design proposal"
  ],
  "decisions": [
    "Adopt Docker Compose for standard deployment"
  ],
  "action_items": [
    {
      "task": "Review and test Dockerfiles",
      "assignee": "Team",
      "deadline": "End of week"
    }
  ]
}
```

---

## Tech Stack

| Layer               | Technology                                       |
|:--------------------|:-------------------------------------------------|
| Speech-to-Text      | **whisper.cpp** (`ggml-small.bin` model)         |
| Speaker Diarization | **pyannote** (`speaker-diarization-community-1`) |
| LLM Summarization   | **Qwen3-8B** via **llama.cpp / llama-server**     |
| Backend API         | **FastAPI** + **Uvicorn**                        |
| Database            | **SQLite** (`data/meetings.db`)                  |
| Frontend            | **React 19**, **TypeScript**, **Vite**           |
| Web Server          | **Nginx** (Reverse proxy in Docker)              |
| Containerization    | **Docker** & **Docker Compose**                  |

---

## License

This project is for personal use.
