import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ai.pipeline import process_existing_meeting, retry_meeting
from backend.database import get_connection, initialize_database
from backend.storage import create_meeting, update_meeting


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEETINGS_DIR = PROJECT_ROOT / "data" / "meetings"

executor = ThreadPoolExecutor(max_workers=1)


class SpeakerNamesUpdate(BaseModel):
    names: dict[str, str] = Field(default_factory=dict)


class MeetingTitleUpdate(BaseModel):
    title: str


class BulkDeleteRequest(BaseModel):
    ids: list[str] = Field(default_factory=list)


app = FastAPI(
    title="CharchaNotes API",
    description="Local AI meeting transcription and summarization API",
    version="0.1.0",
)


cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def meeting_row_dict(row) -> dict:
    result = dict(row)

    try:
        result["speaker_names"] = json.loads(
            result.get("speaker_names") or "{}"
        )
    except json.JSONDecodeError:
        result["speaker_names"] = {}

    return result


def get_meeting_row(meeting_id: str):
    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM meetings
        WHERE id = ?
        """,
        (meeting_id,),
    ).fetchone()

    connection.close()
    return row


def resolve_meeting_path(relative_path: str | None) -> Path | None:
    if not relative_path:
        return None

    path = (PROJECT_ROOT / relative_path).resolve()

    if PROJECT_ROOT not in path.parents:
        raise HTTPException(
            status_code=400,
            detail="Invalid meeting file path",
        )

    return path


def delete_meeting_files(meeting_id: str) -> None:
    meeting_dir = (MEETINGS_DIR / meeting_id).resolve()

    if MEETINGS_DIR not in meeting_dir.parents:
        return

    if meeting_dir.exists():
        shutil.rmtree(meeting_dir)


@app.on_event("startup")
def startup() -> None:
    initialize_database()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/meetings")
def list_meetings() -> list[dict]:
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
        meeting_row_dict(row)
        for row in rows
    ]


@app.post("/meetings", status_code=202)
async def upload_meeting(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(None),
) -> dict:
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided",
        )

    allowed_extensions = {
        ".mp3",
        ".mp4",
        ".m4a",
        ".wav",
        ".webm",
        ".ogg",
        ".flac",
    }

    extension = Path(file.filename).suffix.lower()

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {extension}",
        )

    meeting_title = (
        title.strip()
        if title and title.strip()
        else Path(file.filename).stem
    )

    meeting = create_meeting(
        title=meeting_title,
        original_filename=file.filename,
    )

    meeting_id = meeting.id
    meeting_dir = MEETINGS_DIR / meeting_id
    meeting_dir.mkdir(parents=True, exist_ok=True)

    audio_path = meeting_dir / f"recording{extension}"

    try:
        with audio_path.open("wb") as destination:
            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                destination.write(chunk)

    except Exception as error:
        update_meeting(
            meeting_id,
            status="failed",
        )

        raise HTTPException(
            status_code=500,
            detail=f"Failed to save recording: {error}",
        ) from error

    finally:
        await file.close()

    relative_audio_path = audio_path.relative_to(PROJECT_ROOT)

    update_meeting(
        meeting_id,
        audio_path=str(relative_audio_path),
        status="queued",
    )

    # Submit the normal pipeline only.
    # retry_meeting is used by the retry endpoint below.
    background_tasks.add_task(
        executor.submit,
        process_existing_meeting,
        meeting_id,
        audio_path,
    )

    return {
        "id": meeting_id,
        "title": meeting_title,
        "filename": file.filename,
        "status": "queued",
    }


@app.get("/meetings/{meeting_id}")
def get_meeting(meeting_id: str) -> dict:
    row = get_meeting_row(meeting_id)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found",
        )

    return meeting_row_dict(row)


@app.patch("/meetings/{meeting_id}")
def rename_meeting(
    meeting_id: str,
    payload: MeetingTitleUpdate,
) -> dict:
    title = payload.title.strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="Meeting title cannot be empty",
        )

    row = get_meeting_row(meeting_id)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found",
        )

    update_meeting(
        meeting_id,
        title=title,
    )

    return {
        "id": meeting_id,
        "title": title,
    }


@app.post("/meetings/{meeting_id}/retry", status_code=202)
def retry_failed_meeting(meeting_id: str) -> dict:
    row = get_meeting_row(meeting_id)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found",
        )

    if row["status"] != "failed":
        raise HTTPException(
            status_code=409,
            detail="Only failed meetings can be retried",
        )

    audio_path = resolve_meeting_path(row["audio_path"])

    if audio_path is None or not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Recording file not found",
        )

    update_meeting(
        meeting_id,
        status="queued",
    )

    executor.submit(
        retry_meeting,
        meeting_id,
        audio_path,
    )

    return {
        "id": meeting_id,
        "status": "queued",
    }


@app.get("/meetings/{meeting_id}/transcript")
def get_transcript(meeting_id: str):
    row = get_meeting_row(meeting_id)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found",
        )

    transcript_path = resolve_meeting_path(
        row["transcript_path"]
    )

    if transcript_path is None or not transcript_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Transcript not available",
        )

    with transcript_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


@app.get("/meetings/{meeting_id}/speaker-transcript")
def get_speaker_transcript(meeting_id: str):
    row = get_meeting_row(meeting_id)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found",
        )

    transcript_path = resolve_meeting_path(
        row["speaker_transcript_path"]
    )

    if transcript_path is None or not transcript_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Speaker transcript not available",
        )

    with transcript_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


@app.put("/meetings/{meeting_id}/speakers")
def update_speaker_names(
    meeting_id: str,
    payload: SpeakerNamesUpdate,
) -> dict:
    row = get_meeting_row(meeting_id)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found",
        )

    names = {
        speaker.strip(): label.strip()
        for speaker, label in payload.names.items()
        if speaker.strip() and label.strip()
    }

    update_meeting(
        meeting_id,
        speaker_names=names,
    )

    transcript_path = resolve_meeting_path(
        row["speaker_transcript_path"]
    )

    if transcript_path and transcript_path.exists():
        with transcript_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            transcript = json.load(file)

        for segment in transcript.get("segments", []):
            speaker = segment.get("speaker", "UNKNOWN")
            segment["speaker_label"] = names.get(
                speaker,
                speaker,
            )

        with transcript_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                transcript,
                file,
                indent=2,
                ensure_ascii=False,
            )

    return {
        "speaker_names": names,
    }


@app.get("/meetings/{meeting_id}/summary")
def get_summary(meeting_id: str):
    row = get_meeting_row(meeting_id)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found",
        )

    summary_path = resolve_meeting_path(
        row["summary_path"]
    )

    if summary_path is None or not summary_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Summary not available",
        )

    with summary_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


@app.get("/meetings/{meeting_id}/audio")
def get_audio(meeting_id: str):
    row = get_meeting_row(meeting_id)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found",
        )

    audio_path = resolve_meeting_path(row["audio_path"])

    if audio_path is None or not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Recording not available",
        )

    return FileResponse(audio_path)


@app.delete("/meetings/{meeting_id}")
def delete_meeting(meeting_id: str) -> dict:
    row = get_meeting_row(meeting_id)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found",
        )

    connection = get_connection()

    connection.execute(
        """
        DELETE FROM meetings
        WHERE id = ?
        """,
        (meeting_id,),
    )

    connection.commit()
    connection.close()

    delete_meeting_files(meeting_id)

    return {
        "message": "Meeting deleted",
        "id": meeting_id,
    }


@app.delete("/meetings")
def delete_multiple_meetings(
    payload: BulkDeleteRequest,
) -> dict:
    meeting_ids = list(
        dict.fromkeys(
            meeting_id.strip()
            for meeting_id in payload.ids
            if meeting_id.strip()
        )
    )

    if not meeting_ids:
        raise HTTPException(
            status_code=400,
            detail="No meeting IDs provided",
        )

    connection = get_connection()

    deleted_ids = []

    for meeting_id in meeting_ids:
        row = connection.execute(
            """
            SELECT id
            FROM meetings
            WHERE id = ?
            """,
            (meeting_id,),
        ).fetchone()

        if row is None:
            continue

        connection.execute(
            """
            DELETE FROM meetings
            WHERE id = ?
            """,
            (meeting_id,),
        )

        deleted_ids.append(meeting_id)

    connection.commit()
    connection.close()

    for meeting_id in deleted_ids:
        delete_meeting_files(meeting_id)

    return {
        "message": "Meetings deleted",
        "ids": deleted_ids,
        "count": len(deleted_ids),
    }
