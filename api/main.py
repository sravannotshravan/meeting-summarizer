import os
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import (
    BackgroundTasks,
    File,
    Form,
    UploadFile,
)

from backend.storage import (
    create_meeting,
    update_meeting,
)

from ai.pipeline import (
    process_existing_meeting,
)
from pathlib import Path
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from backend.database import (
    initialize_database,
    get_connection,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

MEETINGS_DIR = (
    PROJECT_ROOT
    / "data"
    / "meetings"
)


app = FastAPI(
    title="CharchaNotes API",
    description="Local AI meeting transcription and summarization API",
    version="0.1.0",
)

from fastapi.middleware.cors import CORSMiddleware

cors_origins_env = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost,http://localhost:80,http://localhost:3000,*"
)
cors_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(
    max_workers=1
)

@app.on_event("startup")
def startup():

    initialize_database()


# ============================================================
# Health
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok"
    }


# ============================================================
# List meetings
# ============================================================

@app.get("/meetings")
def list_meetings():

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM meetings
        ORDER BY created_at DESC
        """
    ).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]

@app.post("/meetings", status_code=202)
async def upload_meeting(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(None),
):
    """
    Upload a meeting recording and start AI processing.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided"
        )

    # --------------------------------------------------------
    # Validate extension
    # --------------------------------------------------------

    allowed_extensions = {
        ".mp3",
        ".mp4",
        ".m4a",
        ".wav",
        ".webm",
        ".ogg",
        ".flac",
    }

    extension = (
        Path(file.filename)
        .suffix
        .lower()
    )

    if extension not in allowed_extensions:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: {extension}"
            )
        )

    # --------------------------------------------------------
    # Create database record
    # --------------------------------------------------------

    meeting_title = (
        title
        if title and title.strip()
        else Path(file.filename).stem
    )

    meeting = create_meeting(
        title=meeting_title,
        original_filename=file.filename
    )

    meeting_id = meeting.id

    # --------------------------------------------------------
    # Create meeting directory
    # --------------------------------------------------------

    meeting_dir = (
        MEETINGS_DIR
        / meeting_id
    )

    meeting_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    audio_path = (
        meeting_dir
        / f"recording{extension}"
    )

    # --------------------------------------------------------
    # Save uploaded recording
    # --------------------------------------------------------

    try:

        with audio_path.open(
            "wb"
        ) as destination:

            while True:

                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                destination.write(
                    chunk
                )

    except Exception:

        update_meeting(
            meeting_id,
            status="failed"
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to save recording"
        )

    finally:

        await file.close()

    # --------------------------------------------------------
    # Update database
    # --------------------------------------------------------

    relative_audio_path = (
        audio_path.relative_to(
            PROJECT_ROOT
        )
    )

    update_meeting(
        meeting_id,
        audio_path=str(
            relative_audio_path
        ),
        status="queued"
    )

    # --------------------------------------------------------
    # Start background processing
    # --------------------------------------------------------

    background_tasks.add_task(
        executor.submit,
        process_existing_meeting,
        meeting_id,
        audio_path
    )

    # --------------------------------------------------------
    # Return immediately
    # --------------------------------------------------------

    return {
        "id": meeting_id,
        "title": meeting_title,
        "filename": file.filename,
        "status": "queued"
    }
# ============================================================
# Get meeting
# ============================================================

@app.get("/meetings/{meeting_id}")
def get_meeting(
    meeting_id: str
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM meetings
        WHERE id = ?
        """,
        (meeting_id,)
    ).fetchone()

    connection.close()

    if row is None:

        raise HTTPException(
            status_code=404,
            detail="Meeting not found"
        )

    return meeting_row_dict(row)


# ============================================================
# Get transcript
# ============================================================

@app.get(
    "/meetings/{meeting_id}/transcript"
)
def get_transcript(
    meeting_id: str
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT transcript_path
        FROM meetings
        WHERE id = ?
        """,
        (meeting_id,)
    ).fetchone()

    connection.close()

    if row is None:

        raise HTTPException(
            status_code=404,
            detail="Meeting not found"
        )

    if not row["transcript_path"]:

        raise HTTPException(
            status_code=404,
            detail="Transcript not available"
        )

    transcript_path = (
        PROJECT_ROOT
        / row["transcript_path"]
    )

    if not transcript_path.exists():

        raise HTTPException(
            status_code=404,
            detail="Transcript file not found"
        )

    with transcript_path.open(
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ============================================================
# Get speaker transcript
# ============================================================

@app.get(
    "/meetings/{meeting_id}/speaker-transcript"
)
def get_speaker_transcript(
    meeting_id: str
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT speaker_transcript_path
        FROM meetings
        WHERE id = ?
        """,
        (meeting_id,)
    ).fetchone()

    connection.close()

    if row is None:

        raise HTTPException(
            status_code=404,
            detail="Meeting not found"
        )

    if not row["speaker_transcript_path"]:

        raise HTTPException(
            status_code=404,
            detail="Speaker transcript not available"
        )

    speaker_transcript_path = (
        PROJECT_ROOT
        / row["speaker_transcript_path"]
    )

    if not speaker_transcript_path.exists():

        raise HTTPException(
            status_code=404,
            detail="Speaker transcript file not found"
        )

    with speaker_transcript_path.open(
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ============================================================
# Get summary
# ============================================================

@app.get(
    "/meetings/{meeting_id}/summary"
)
def get_summary(
    meeting_id: str
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT summary_path
        FROM meetings
        WHERE id = ?
        """,
        (meeting_id,)
    ).fetchone()

    connection.close()

    if row is None:

        raise HTTPException(
            status_code=404,
            detail="Meeting not found"
        )

    if not row["summary_path"]:

        raise HTTPException(
            status_code=404,
            detail="Summary not available"
        )

    summary_path = (
        PROJECT_ROOT
        / row["summary_path"]
    )

    if not summary_path.exists():

        raise HTTPException(
            status_code=404,
            detail="Summary file not found"
        )

    with summary_path.open(
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ============================================================
# Get audio
# ============================================================

@app.get(
    "/meetings/{meeting_id}/audio"
)
def get_audio(
    meeting_id: str
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT audio_path
        FROM meetings
        WHERE id = ?
        """,
        (meeting_id,)
    ).fetchone()

    connection.close()

    if row is None:

        raise HTTPException(
            status_code=404,
            detail="Meeting not found"
        )

    if not row["audio_path"]:

        raise HTTPException(
            status_code=404,
            detail="Recording not available"
        )

    audio_path = (
        PROJECT_ROOT
        / row["audio_path"]
    )

    if not audio_path.exists():

        raise HTTPException(
            status_code=404,
            detail="Recording file not found"
        )

    return FileResponse(
        audio_path
    )


# ============================================================
# Delete meeting
# ============================================================

@app.delete(
    "/meetings/{meeting_id}"
)
def delete_meeting(
    meeting_id: str
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM meetings
        WHERE id = ?
        """,
        (meeting_id,)
    ).fetchone()

    if row is None:

        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Meeting not found"
        )

    connection.execute(
        """
        DELETE FROM meetings
        WHERE id = ?
        """,
        (meeting_id,)
    )

    connection.commit()
    connection.close()

    meeting_dir = (
        MEETINGS_DIR
        / meeting_id
    )

    if meeting_dir.exists():

        import shutil

        shutil.rmtree(
            meeting_dir
        )

    return {
        "message": "Meeting deleted",
        "id": meeting_id
    }
