# MeetingAI

A fully local, privacy-first AI meeting summarizer. Upload an audio recording and get back a speaker-aware transcript and structured summary — all processed on your own machine with no cloud APIs.

## What it does

1. **Transcribes** speech to text using [whisper.cpp](https://github.com/ggerganov/whisper.cpp)
2. **Identifies speakers** using [pyannote](https://github.com/pyannote/pyannote-audio) speaker diarization
3. **Aligns** transcript segments to the correct speaker by temporal overlap
4. **Summarizes** the meeting using [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) running locally via [llama.cpp](https://github.com/ggerganov/llama.cpp)

The output is a structured JSON summary containing:

- A concise meeting summary
- Key discussion points
- Decisions made
- Action items with assignees and deadlines

## Architecture

`
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite + TypeScript)                          │
│  Dashboard · Meeting detail · Audio player                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST (localhost:8000)
┌──────────────────────────┴──────────────────────────────────────┐
│  API (FastAPI)                                                  │
│  Upload · List · Get transcript/summary · Background processing │
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
`

## Project structure

`
meeting-summarizer/
├── ai/                          # AI pipeline
│   ├── pipeline.py              # Main orchestrator (CLI + API entry)
│   ├── summarizer.py            # LLM summarization (Qwen3-8B)
│   ├── diarization.py           # Speaker diarization (pyannote)
│   └── alignment.py             # Whisper ↔ diarization alignment
│
├── api/                         # REST API
│   └── main.py                  # FastAPI app with all endpoints
│
├── backend/                     # Data layer
│   ├── database.py              # SQLite connection + schema
│   ├── models.py                # Meeting dataclass
│   └── storage.py               # CRUD operations + file management
│
├── frontend/                    # Web UI
│   ├── src/
│   │   ├── App.tsx              # Dashboard (meeting list + stats)
│   │   ├── pages/
│   │   │   └── MeetingPage.tsx  # Meeting detail view
│   │   ├── lib/
│   │   │   └── api.ts           # Typed API client
│   │   └── types/
│   │       └── meeting.ts       # TypeScript interfaces
│   ├── package.json
│   └── vite.config.ts
│
└── data/                        # Runtime data (gitignored)
    ├── meetings.db              # SQLite database
    └── meetings/{uuid}/         # Per-meeting directory
        ├── recording.m4a
        ├── transcript.json
        ├── diarization.json
        ├── speaker_transcript.json
        └── summary.json
`

## Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **whisper.cpp** — built and available at ~/whisper.cpp/build/bin/whisper-cli
- **Whisper model** — ggml-small.bin at ~/whisper.cpp/models/ggml-small.bin
- **llama.cpp** — llama-server running on port 8080 with a Qwen3-8B GGUF model
- **PyTorch** with CUDA support (optional, but recommended for diarization speed)
- A [Hugging Face token](https://huggingface.co/settings/tokens) with access to pyannote/speaker-diarization-community-1

## Setup

### 1. Clone the repository

`ash
git clone https://github.com/your-username/meeting-summarizer.git
cd meeting-summarizer
`

### 2. Python environment

`ash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn requests torch pyannote.audio
`

### 3. Start llama-server

`ash
llama-server \
  -m /path/to/qwen3-8b.gguf \
  --port 8080 \
  -ngl 99
`

### 4. Frontend

`ash
cd frontend
npm install
npm run dev
`

### 5. API server

`ash
# From the project root
uvicorn api.main:app --reload --port 8000
`

## Usage

### Via the web UI

1. Open http://localhost:5173
2. Upload a meeting recording
3. Wait for the pipeline to process (status updates in real time)
4. View the transcript and AI summary on the meeting detail page

### Via the CLI

`ash
python -m ai.pipeline path/to/recording.m4a --title "Weekly Standup"
`

### Via the API

`ash
# Upload a meeting
curl -X POST http://localhost:8000/meetings \
  -F "file=@recording.m4a" \
  -F "title=Weekly Standup"

# Check status
curl http://localhost:8000/meetings/{meeting_id}

# Get the summary
curl http://localhost:8000/meetings/{meeting_id}/summary
`

## API reference

| Method   | Endpoint                                | Description                    |
|----------|-----------------------------------------|--------------------------------|
| GET    | /health                               | Health check                   |
| GET    | /meetings                             | List all meetings              |
| POST   | /meetings                             | Upload recording + start AI    |
| GET    | /meetings/{id}                        | Meeting metadata               |
| GET    | /meetings/{id}/transcript             | Whisper transcript             |
| GET    | /meetings/{id}/speaker-transcript     | Speaker-aligned transcript     |
| GET    | /meetings/{id}/summary               | AI-generated summary           |
| GET    | /meetings/{id}/audio                  | Download/stream recording      |
| DELETE | /meetings/{id}                        | Delete meeting and all files   |

## Summary output format

`json
{
  "summary": "Brief overview of the meeting...",
  "key_points": [
    "First key discussion point",
    "Second key discussion point"
  ],
  "decisions": [
    "Decision that was made"
  ],
  "action_items": [
    {
      "task": "What needs to be done",
      "assignee": "Who is responsible",
      "deadline": "When it's due"
    }
  ]
}
`

## Tech stack

| Component          | Technology                                          |
|--------------------|-----------------------------------------------------|
| Speech-to-text     | whisper.cpp (ggml-small model)                    |
| Speaker diarization| pyannote (speaker-diarization-community-1)        |
| LLM summarization  | Qwen3-8B via llama-server                           |
| API                | FastAPI + Uvicorn                                   |
| Database           | SQLite                                              |
| Frontend           | React 19 + TypeScript + Vite                        |
| Icons              | Lucide React                                        |

## License

This project is for personal use.
