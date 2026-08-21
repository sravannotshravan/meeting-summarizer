# CharchaNotes

CharchaNotes is a local-first meeting transcription and notes application. It accepts audio/video recordings, creates a timestamped transcript, identifies speakers, aligns speakers to transcript segments, generates a structured summary with a local Qwen model, and lets you review everything in a synchronized web UI.

No meeting audio, transcript, or summary is sent to a hosted AI API. The application runs FastAPI, whisper.cpp, pyannote, llama.cpp, and React locally or in Docker.

## What CharchaNotes does

- Uploads MP3, MP4, M4A, WAV, WebM, OGG, and FLAC recordings.
- Stores meeting metadata in SQLite and meeting artifacts under \`data/meetings/{meeting_id}/\`.
- Transcribes audio with whisper.cpp using the \`ggml-small.bin\` model.
- Detects speakers with \`pyannote/speaker-diarization-community-1\`.
- Aligns diarization intervals with Whisper segments using temporal overlap.
- Sends the plain transcript to a local llama.cpp OpenAI-compatible endpoint.
- Generates a structured JSON summary containing an overview, key points, decisions, and action items.
- Plays the original recording with click-to-seek transcript synchronization.
- Highlights the active transcript segment while audio plays.
- Saves human-readable speaker labels for each meeting.
- Retries the complete pipeline after a failed run.
- Deletes one meeting or multiple selected meetings, including stored files.

## Architecture

\`\`\`
Browser
  React 19 + TypeScript + Vite
        |
        | REST / audio streaming
        v
FastAPI + Uvicorn
  upload, status, artifacts, retry, delete, speaker labels
        |
        +--> Background pipeline
        |      whisper.cpp -> pyannote -> alignment -> llama.cpp
        |
        +--> SQLite: data/meetings.db
        +--> Files: data/meetings/{uuid}/
        |
        +--> llama-server:8080
               Qwen3-8B-GGUF:Q4_K_M
\`\`\`

In Docker, Nginx serves the compiled React application and proxies \`/health\` and \`/meetings...\` requests to FastAPI. The browser therefore uses one origin: \`http://localhost:5173\`.

## Docker setup

### Requirements

- Docker Desktop or Docker Engine with Docker Compose v2.
- A Hugging Face account and token.
- Docker configured for GPU access if you want GPU inference/diarization.
- Enough disk space for:
  - the Python/PyTorch/pyannote image,
  - the Whisper model,
  - the Qwen3-8B GGUF model downloaded by llama.cpp,
  - meeting recordings and artifacts.

### One-command setup

Run this from the repository root:

\`\`\`bash
chmod +x docker-setup.sh
./docker-setup.sh
\`\`\`

The script:

1. Checks that Docker is available.
2. Prompts for \`HF_TOKEN\` without echoing it.
3. Writes the token to the local \`.env\` file.
4. Builds the backend and frontend images.
5. Starts all services in the background.
6. Prints service status and local URLs.

The token is passed at runtime. It is not copied into a Docker image layer.

### What downloads on first start

The backend entrypoint downloads:

\`\`\`
ggerganov/whisper.cpp/ggml-small.bin
\`\`\`

using the Hugging Face token and stores it in the named volume \`charchanotes-whisper-models\`.

The llama.cpp container uses the exact model reference:

\`\`\`
Qwen/Qwen3-8B-GGUF:Q4_K_M
\`\`\`

with the equivalent of your local command:

\`\`\`bash
llama-server \
  -hf Qwen/Qwen3-8B-GGUF:Q4_K_M \
  -ngl 99 \
  -c 8192 \
  --host 0.0.0.0 \
  --port 8080
\`\`\`

The llama.cpp cache is stored in \`charchanotes-llama-cache\`, so the model is not downloaded again after the volume is populated.

### Docker services

| Service | Container | Host URL | Responsibility |
|---|---|---:|---|
| \`llama-server\` | \`charchanotes-llama-server\` | \`localhost:8080\` | Qwen3-8B inference via llama.cpp |
| \`backend\` | \`charchanotes-backend\` | \`localhost:8000\` | FastAPI, pipeline, SQLite, artifact storage |
| \`frontend\` | \`charchanotes-frontend\` | \`localhost:5173\` | Nginx, React SPA, API reverse proxy |

Open:

- Web UI: http://localhost:5173
- FastAPI Swagger UI: http://localhost:8000/docs
- FastAPI ReDoc: http://localhost:8000/redoc
- Backend health: http://localhost:8000/health
- llama.cpp health: http://localhost:8080/health

Useful commands:

\`\`\`bash
docker compose ps
docker compose logs -f
docker compose logs -f backend
docker compose logs -f llama-server
docker compose restart
docker compose down
\`\`\`

\`docker compose down\` keeps named model volumes. To remove downloaded model caches too:

\`\`\`bash
docker compose down -v
\`\`\`

### GPU and CPU settings

The default is \`LLAMA_N_GPU_LAYERS=99\`, matching your local command. If the Docker host has no usable GPU, set this in \`.env\`:

\`\`\`env
LLAMA_N_GPU_LAYERS=0
\`\`\`

The same Docker image can then run llama.cpp on CPU, although Qwen3-8B will be substantially slower.

Pyannote automatically selects CUDA when PyTorch can see a GPU and otherwise uses CPU.

### Docker environment variables

\`\`\`env
HF_TOKEN=hf_your_token_here
FRONTEND_PORT=5173
BACKEND_PORT=8000
LLAMA_PORT=8080
LLAMA_N_GPU_LAYERS=99
\`\`\`

The application-side defaults are:

\`\`\`env
WHISPER_CLI_PATH=/usr/local/bin/whisper-cli
WHISPER_MODEL_PATH=/models/whisper/ggml-small.bin
LLAMA_URL=http://llama-server:8080/v1/chat/completions
LLAMA_MODEL=Qwen3-8B
CORS_ORIGINS=*
\`\`\`

## Local development

Docker is the recommended reproducible deployment. For local development, the equivalent workflow is:

### Start llama.cpp

\`\`\`bash
cd ~/meeting-summarizer

~/llama.cpp/build/bin/llama-server \
  -hf Qwen/Qwen3-8B-GGUF:Q4_K_M \
  -ngl 99 \
  -c 8192 \
  --host 127.0.0.1 \
  --port 8080
\`\`\`

### Start FastAPI

\`\`\`bash
cd ~/meeting-summarizer
source .venv/bin/activate

uvicorn api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload
\`\`\`

### Start React/Vite

\`\`\`bash
cd ~/meeting-summarizer/frontend
npm run dev -- --host 0.0.0.0
\`\`\`

For local development, the frontend defaults to \`http://127.0.0.1:8000\`. Set \`VITE_API_URL\` if the backend runs elsewhere.

## Backend specification

### FastAPI application

The API entrypoint is \`api.main:app\`.

FastAPI provides:

- Typed request and response handling.
- Multipart file uploads.
- OpenAPI schema and interactive Swagger/ReDoc documentation.
- CORS configuration through \`CORS_ORIGINS\`.
- Background scheduling of the long-running pipeline.
- Health checks for Docker Compose.

The current local worker uses a single \`ThreadPoolExecutor\` worker. This is appropriate for a local privacy-first application because GPU/model work is serialized and two large meetings do not compete for the same model resources.

### Pipeline states

A meeting normally moves through:

\`\`\`
uploaded -> queued -> transcribing -> transcribed
         -> diarizing -> summarizing -> completed
\`\`\`

If any stage raises an exception, the meeting becomes \`failed\`.

Retrying a failed meeting:

- Removes stale transcript, diarization, speaker-transcript, and summary outputs.
- Clears derived metadata.
- Keeps the original recording.
- Runs transcription, diarization, alignment, and summarization again from the beginning.

### API endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | \`/health\` | Returns API health status. |
| GET | \`/meetings\` | Lists meetings newest first. |
| POST | \`/meetings\` | Uploads a recording with multipart \`file\` and optional \`title\`. |
| GET | \`/meetings/{id}\` | Returns meeting metadata and processing status. |
| POST | \`/meetings/{id}/retry\` | Queues a complete retry for a failed meeting. |
| GET | \`/meetings/{id}/transcript\` | Returns the raw Whisper transcript. |
| GET | \`/meetings/{id}/speaker-transcript\` | Returns the aligned transcript and saved labels. |
| PUT | \`/meetings/{id}/speakers\` | Saves a JSON speaker-ID-to-label map. |
| GET | \`/meetings/{id}/summary\` | Returns the structured summary JSON. |
| GET | \`/meetings/{id}/audio\` | Streams the original recording. |
| DELETE | \`/meetings/{id}\` | Deletes the database row and meeting directory. |

The speaker-label request body is:

\`\`\`json
{
  "names": {
    "SPEAKER_00": "Priya",
    "SPEAKER_01": "Arjun"
  }
}
\`\`\`

Saved labels are stored in SQLite and written to each speaker transcript segment as \`speaker_label\`, while the raw \`speaker\` ID remains available.

### Storage

SQLite database:

\`\`\`
data/meetings.db
\`\`\`

Per-meeting files:

\`\`\`
data/meetings/{uuid}/
  recording.<extension>
  transcript.json
  diarization.json
  speaker_transcript.json
  summary.json
\`\`\`

The Docker Compose backend mounts \`./data:/app/data\`, so recordings and generated artifacts remain on the host.

## LLM integration

llama.cpp exposes an OpenAI-compatible endpoint at:

\`\`\`
http://llama-server:8080/v1/chat/completions
\`\`\`

The backend sends:

- Model: \`Qwen3-8B\`
- Temperature: \`0.1\`
- Maximum output tokens: \`1200\`
- Thinking disabled through \`chat_template_kwargs.enable_thinking=false\`
- JSON schema response format

The model server itself is started with:

\`\`\`
-hf Qwen/Qwen3-8B-GGUF:Q4_K_M
-ngl 99
-c 8192
--host 0.0.0.0
--port 8080
\`\`\`

### System prompt

The summarizer currently sends this system prompt:

\`\`\`text
You are a meeting analysis assistant.

Analyze the provided meeting transcript and extract useful,
factual information.

IMPORTANT RULES:

1. Only use information explicitly supported by the transcript.
2. Do not invent people, decisions, tasks, deadlines, or facts.
3. Do not infer speaker identities because the transcript does
   not contain speaker labels.
4. If an action item's assignee is not explicitly mentioned,
   use "Unknown".
5. If an action item's deadline is not explicitly mentioned,
   use "Unknown".
6. Keep deadlines in the wording used in the transcript.
7. Produce a concise but useful summary.
8. Do not include irrelevant information.
\`\`\`

The user prompt adds the timestamped plain transcript and explicitly tells Qwen that timestamps are references, not speaker labels. Summaries are constrained by \`SUMMARY_SCHEMA\` to:

\`\`\`json
{
  "summary": "string",
  "key_points": ["string"],
  "decisions": ["string"],
  "action_items": [
    {
      "task": "string",
      "assignee": "string",
      "deadline": "string"
    }
  ]
}
\`\`\`

## Frontend specification

The frontend is a React 19 + TypeScript + Vite single-page application.

### Dashboard

- Displays total meetings, recorded time, and completed AI-processing count.
- Searches meeting titles, filenames, and detected languages.
- Opens individual meeting pages.
- Uploads new recordings through a drag-and-drop modal.
- Supports selection mode for one or more meetings.
- Selects all meetings currently visible through search.
- Deletes selected meetings after explicit confirmation.

### Meeting page

- Shows title, filename, creation date, duration, language, and status.
- Streams the original audio from FastAPI.
- Displays synchronized speaker-aware transcript segments.
- Clicks transcript segments to seek audio.
- Automatically scrolls to the active segment while playing.
- Shows AI overview, key points, decisions, and action items.
- Allows speaker labels to be renamed and saved.
- Shows a retry action when the pipeline fails.
- Allows the current meeting to be deleted.

### Frontend configuration

Vite uses:

\`\`\`env
VITE_API_URL=http://127.0.0.1:8000
\`\`\`

In Docker, \`VITE_API_URL\` is empty because Nginx proxies the API paths to the backend service.

## Troubleshooting

### Backend exits because HF_TOKEN is missing

Run:

\`\`\`bash
./docker-setup.sh
\`\`\`

or add a valid token to \`.env\`:

\`\`\`env
HF_TOKEN=hf_...
\`\`\`

The token must have access to \`pyannote/speaker-diarization-community-1\`.

### llama-server is unhealthy

Inspect:

\`\`\`bash
docker compose logs llama-server
\`\`\`

Confirm that the host can access Hugging Face and that the model reference is exactly:

\`\`\`
Qwen/Qwen3-8B-GGUF:Q4_K_M
\`\`\`

If the host has no GPU, set \`LLAMA_N_GPU_LAYERS=0\`.

### Backend is unhealthy

Inspect:

\`\`\`bash
docker compose logs backend
\`\`\`

The first backend start may take time because it downloads \`ggml-small.bin\` and initializes the Python dependencies/model cache.

### Frontend loads but API calls fail

Confirm:

\`\`\`bash
docker compose ps
curl http://localhost:8000/health
curl http://localhost:5173/health
\`\`\`

The Nginx container must be running and its upstream service must be named \`backend\`.

### Reset only application data

Stop the stack, then remove the host data directory contents you no longer need. This deletes recordings and meeting results, so back them up first.

## Repository structure

\`\`\`
CharchaNotes/
  ai/                  Whisper, diarization, alignment, summarization pipeline
  api/                 FastAPI application and routes
  backend/             SQLite and filesystem storage
  frontend/            React/Vite application and Nginx configuration
  data/                Runtime database and meeting artifacts
  docker/              Container entrypoint scripts
  Dockerfile.backend   Whisper + FastAPI runtime image
  Dockerfile.frontend  Vite build + Nginx image
  docker-compose.yml   llama.cpp, backend, and frontend services
  docker-setup.sh      HF token prompt and Docker startup helper
\`\`\`

## License

This project is for personal use.

### Meeting renaming

Open any meeting and use the **Rename** control beside its title. CharchaNotes sends the new title to FastAPI with PATCH /meetings/{id}; the backend validates that it is not empty, stores it in SQLite, and the updated title is reflected in the dashboard and recent-meetings list.
