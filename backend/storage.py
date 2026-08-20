import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.database import get_connection
from backend.models import Meeting


PROJECT_ROOT = Path(__file__).resolve().parent.parent

MEETINGS_DIR = PROJECT_ROOT / "data" / "meetings"


def now():
    """
    Return the current UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()


def create_meeting(
    title: str,
    original_filename: str
) -> Meeting:

    meeting_id = str(
        uuid.uuid4()
    )

    timestamp = now()

    meeting_dir = (
        MEETINGS_DIR
        / meeting_id
    )

    meeting_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    meeting = Meeting(
        id=meeting_id,

        title=title,

        original_filename=original_filename,

        audio_path=None,

        transcript_path=None,

        speaker_transcript_path=None,

        summary_path=None,

        status="uploaded",

        duration=None,

        language=None,

        created_at=timestamp,

        updated_at=timestamp
    )

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO meetings (
            id,
            title,
            original_filename,
            audio_path,
            transcript_path,
            speaker_transcript_path,
            summary_path,
            status,
            duration,
            language,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            meeting.id,
            meeting.title,
            meeting.original_filename,
            meeting.audio_path,
            meeting.transcript_path,
            meeting.speaker_transcript_path,
            meeting.summary_path,
            meeting.status,
            meeting.duration,
            meeting.language,
            meeting.created_at,
            meeting.updated_at
        )
    )

    connection.commit()
    connection.close()

    return meeting


def get_meeting(
    meeting_id: str
) -> Meeting | None:

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
        return None

    return Meeting(
        id=row["id"],
        title=row["title"],
        original_filename=row["original_filename"],
        audio_path=row["audio_path"],
        transcript_path=row["transcript_path"],
        speaker_transcript_path=row["speaker_transcript_path"],
        summary_path=row["summary_path"],
        status=row["status"],
        duration=row["duration"],
        language=row["language"],
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )


def update_meeting(
    meeting_id: str,
    **fields
):

    if not fields:
        return

    fields["updated_at"] = now()

    allowed_fields = {
        "title",
        "audio_path",
        "transcript_path",
        "speaker_transcript_path",
        "summary_path",
        "status",
        "duration",
        "language",
        "updated_at"
    }

    for field in fields:

        if field not in allowed_fields:

            raise ValueError(
                f"Invalid meeting field: {field}"
            )

    assignments = ", ".join(
        f"{field} = ?"
        for field in fields
    )

    values = list(
        fields.values()
    )

    values.append(
        meeting_id
    )

    connection = get_connection()

    connection.execute(
        f"""
        UPDATE meetings
        SET {assignments}
        WHERE id = ?
        """,
        values
    )

    connection.commit()
    connection.close()


def save_recording(
    meeting_id: str,
    source_path: Path
) -> Path:

    meeting_dir = (
        MEETINGS_DIR
        / meeting_id
    )

    meeting_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    destination = (
        meeting_dir
        / f"recording{source_path.suffix.lower()}"
    )

    shutil.copy2(
        source_path,
        destination
    )

    relative_path = destination.relative_to(
        PROJECT_ROOT
    )

    update_meeting(
        meeting_id,
        audio_path=str(
            relative_path
        )
    )

    return destination


def save_transcript(
    meeting_id: str,
    source_path: Path
) -> Path:

    meeting_dir = (
        MEETINGS_DIR
        / meeting_id
    )

    destination = (
        meeting_dir
        / "transcript.json"
    )

    shutil.copy2(
        source_path,
        destination
    )

    relative_path = destination.relative_to(
        PROJECT_ROOT
    )

    update_meeting(
        meeting_id,
        transcript_path=str(
            relative_path
        )
    )

    return destination


def save_speaker_transcript(
    meeting_id: str,
    source_path: Path
) -> Path:

    meeting_dir = (
        MEETINGS_DIR
        / meeting_id
    )

    destination = (
        meeting_dir
        / "speaker_transcript.json"
    )

    shutil.copy2(
        source_path,
        destination
    )

    relative_path = destination.relative_to(
        PROJECT_ROOT
    )

    update_meeting(
        meeting_id,
        speaker_transcript_path=str(
            relative_path
        )
    )

    return destination


def save_summary(
    meeting_id: str,
    source_path: Path
) -> Path:

    meeting_dir = (
        MEETINGS_DIR
        / meeting_id
    )

    destination = (
        meeting_dir
        / "summary.json"
    )

    shutil.copy2(
        source_path,
        destination
    )

    relative_path = destination.relative_to(
        PROJECT_ROOT
    )

    update_meeting(
        meeting_id,
        summary_path=str(
            relative_path
        )
    )

    return destination
