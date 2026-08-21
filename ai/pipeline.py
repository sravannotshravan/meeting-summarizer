import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import requests

from ai.alignment import (
    align_transcript,
    load_whisper_segments,
    save_aligned_transcript,
)
from ai.diarization import (
    diarize,
    save_diarization,
)

from backend.database import initialize_database
from backend.storage import (
    create_meeting,
    save_speaker_transcript,
    update_meeting,
)


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

import os

WHISPER_CLI = Path(
    os.getenv(
        "WHISPER_CLI_PATH",
        str(
            Path.home()
            / "whisper.cpp"
            / "build"
            / "bin"
            / "whisper-cli"
        )
    )
).resolve()

WHISPER_MODEL = Path(
    os.getenv(
        "WHISPER_MODEL_PATH",
        str(
            Path.home()
            / "whisper.cpp"
            / "models"
            / "ggml-small.bin"
        )
    )
).resolve()

LLAMA_URL = os.getenv(
    "LLAMA_URL",
    "http://127.0.0.1:8080/v1/chat/completions"
)

MEETINGS_DIR = PROJECT_ROOT / "data" / "meetings"


# ============================================================
# Speaker transcript pipeline
# ============================================================

def create_speaker_transcript(
    meeting_id: str,
    audio_path: Path,
    whisper_path: Path,
) -> Path:
    """
    Run speaker diarization and align it with Whisper.

    The resulting speaker-aware transcript is stored inside
    the meeting's directory and linked in SQLite.
    """

    meeting_dir = (
        MEETINGS_DIR
        / meeting_id
    )

    diarization_path = (
        meeting_dir
        / "diarization.json"
    )

    aligned_temp_path = (
        PROJECT_ROOT
        / "ai"
        / "transcripts"
        / f"{meeting_id}_speaker_transcript.json"
    )

    print()
    print("=" * 70)
    print("SPEAKER-AWARE TRANSCRIPTION")
    print("=" * 70)

    # --------------------------------------------------------
    # Diarization
    # --------------------------------------------------------

    print()
    print("Running speaker diarization...")

    diarization_segments, elapsed = diarize(
        audio_path
    )

    save_diarization(
        diarization_path,
        diarization_segments,
    )

    print(
        f"Diarization saved to:\n"
        f"{diarization_path}"
    )

    # --------------------------------------------------------
    # Whisper + diarization alignment
    # --------------------------------------------------------

    print()
    print("Aligning Whisper transcript with speakers...")

    whisper_segments, language, duration = (
        load_whisper_segments(
            whisper_path
        )
    )

    aligned_segments = align_transcript(
        whisper_segments,
        diarization_segments,
    )

    save_aligned_transcript(
        aligned_temp_path,
        aligned_segments,
        language,
        duration,
    )

    # --------------------------------------------------------
    # Store speaker transcript
    # --------------------------------------------------------

    speaker_transcript_path = save_speaker_transcript(
        meeting_id,
        aligned_temp_path,
    )

    print(
        f"Speaker transcript saved to:\n"
        f"{speaker_transcript_path}"
    )

    return speaker_transcript_path


# ============================================================
# JSON schema for Qwen
# ============================================================

SUMMARY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {
            "type": "string"
        },
        "key_points": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },
        "decisions": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "task": {
                        "type": "string"
                    },
                    "assignee": {
                        "type": "string"
                    },
                    "deadline": {
                        "type": "string"
                    }
                },
                "required": [
                    "task",
                    "assignee",
                    "deadline"
                ]
            }
        }
    },
    "required": [
        "summary",
        "key_points",
        "decisions",
        "action_items"
    ]
}


# ============================================================
# Dependency checks
# ============================================================

def check_dependencies():

    if not WHISPER_CLI.exists():
        raise RuntimeError(
            f"Whisper executable not found:\n"
            f"{WHISPER_CLI}"
        )

    if not WHISPER_MODEL.exists():
        raise RuntimeError(
            f"Whisper model not found:\n"
            f"{WHISPER_MODEL}"
        )


# ============================================================
# Copy recording into meeting storage
# ============================================================

def store_recording(
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

    return destination


# ============================================================
# Run Whisper
# ============================================================

def transcribe(
    meeting_id: str,
    audio_path: Path
) -> Path:

    meeting_dir = (
        MEETINGS_DIR
        / meeting_id
    )

    output_base = (
        meeting_dir
        / "transcript"
    )

    output_json = (
        meeting_dir
        / "transcript.json"
    )

    command = [
        str(WHISPER_CLI),

        "-m",
        str(WHISPER_MODEL),

        "-f",
        str(audio_path),

        "-oj",

        "-of",
        str(output_base),

        "-l",
        "auto",
    ]

    print()
    print("=" * 70)
    print("STEP 1/2 — TRANSCRIPTION")
    print("=" * 70)

    print()
    print(f"Audio: {audio_path}")
    print(f"Model: {WHISPER_MODEL}")
    print()

    update_meeting(
        meeting_id,
        status="transcribing"
    )

    result = subprocess.run(
        command,
        check=False
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Whisper exited with code "
            f"{result.returncode}"
        )

    if not output_json.exists():
        raise RuntimeError(
            "Whisper finished but transcript "
            f"was not found:\n{output_json}"
        )

    return output_json


# ============================================================
# Extract Whisper transcript
# ============================================================

def extract_transcript(
    json_path: Path
) -> tuple[str, str | None, float | None]:

    with json_path.open(
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    transcription = data.get(
        "transcription"
    )

    if not isinstance(
        transcription,
        list
    ):
        raise RuntimeError(
            "Whisper JSON does not contain "
            "a valid transcription array."
        )

    lines = []

    end_ms = 0

    for segment in transcription:

        timestamps = segment.get(
            "timestamps",
            {}
        )

        offsets = segment.get(
            "offsets",
            {}
        )

        start = timestamps.get(
            "from",
            "Unknown"
        )

        text = segment.get(
            "text",
            ""
        ).strip()

        if not text:
            continue

        lines.append(
            f"[{start}] {text}"
        )

        segment_end = offsets.get(
            "to"
        )

        if isinstance(
            segment_end,
            (int, float)
        ):
            end_ms = max(
                end_ms,
                segment_end
            )

    language = (
        data.get("result", {})
        .get("language")
    )

    duration = (
        end_ms / 1000
        if end_ms > 0
        else None
    )

    if not lines:
        raise RuntimeError(
            "Whisper produced an empty transcript."
        )

    return (
        "\n".join(lines),
        language,
        duration
    )


# ============================================================
# Qwen summarization
# ============================================================

def summarize(
    transcript: str
) -> dict:

    system_prompt = """
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
"""

    user_prompt = f"""
Analyze this meeting transcript.

The timestamps are included for reference.
They are NOT speaker labels.

TRANSCRIPT
-----------

{transcript}

-----------

Return the structured meeting analysis.
"""

    payload = {
        "model": "Qwen3-8B",

        "messages": [
            {
                "role": "system",
                "content": system_prompt.strip()
            },
            {
                "role": "user",
                "content": user_prompt.strip()
            }
        ],

        "temperature": 0.1,

        "max_tokens": 1200,

        "chat_template_kwargs": {
            "enable_thinking": False
        },

        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "meeting_summary",
                "schema": SUMMARY_SCHEMA
            }
        }
    }

    print()
    print("=" * 70)
    print("STEP 2/2 — AI SUMMARIZATION")
    print("=" * 70)

    print()
    print("Sending transcript to Qwen3...")

    try:

        response = requests.post(
            LLAMA_URL,
            json=payload,
            timeout=300
        )

    except requests.exceptions.ConnectionError:

        raise RuntimeError(
            "\nCould not connect to llama-server.\n\n"
            "Start it with:\n\n"
            "~/llama.cpp/build/bin/llama-server "
            "-hf Qwen/Qwen3-8B-GGUF:Q4_K_M "
            "-ngl 99 "
            "-c 8192 "
            "--host 127.0.0.1 "
            "--port 8080"
        )

    response.raise_for_status()

    result = response.json()

    try:

        content = (
            result["choices"][0]
            ["message"]
            ["content"]
        )

    except (
        KeyError,
        IndexError,
        TypeError
    ):

        raise RuntimeError(
            "Unexpected response from "
            "llama-server:\n"
            + json.dumps(
                result,
                indent=2
            )
        )

    if not content or not content.strip():

        raise RuntimeError(
            "Qwen returned empty content."
        )

    try:

        return json.loads(
            content
        )

    except json.JSONDecodeError:

        raise RuntimeError(
            "Qwen returned invalid JSON:\n\n"
            + content
        )


# ============================================================
# Save summary
# ============================================================

def save_summary(
    meeting_id: str,
    summary: dict
) -> Path:

    meeting_dir = (
        MEETINGS_DIR
        / meeting_id
    )

    summary_path = (
        meeting_dir
        / "summary.json"
    )

    with summary_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            summary,
            file,
            indent=2,
            ensure_ascii=False
        )

    return summary_path


# ============================================================
# Pretty-print result
# ============================================================

def print_summary(
    summary: dict
):

    print()
    print()
    print("=" * 70)
    print("FINAL MEETING SUMMARY")
    print("=" * 70)

    print()
    print(summary["summary"])

    print()
    print("KEY POINTS")
    print("-" * 70)

    for point in summary["key_points"]:
        print(f"• {point}")

    print()
    print("DECISIONS")
    print("-" * 70)

    if summary["decisions"]:

        for decision in summary["decisions"]:
            print(f"• {decision}")

    else:
        print("None identified.")

    print()
    print("ACTION ITEMS")
    print("-" * 70)

    if summary["action_items"]:

        for item in summary["action_items"]:

            print(
                f"• {item['task']}"
            )

            print(
                f"  Assignee: "
                f"{item['assignee']}"
            )

            print(
                f"  Deadline: "
                f"{item['deadline']}"
            )

            print()

    else:
        print("None identified.")

    print("=" * 70)

def process_existing_meeting(
    meeting_id: str,
    audio_path: Path
):
    """
    Run the complete AI pipeline for an existing meeting.

    The meeting record must already exist in SQLite.
    """

    try:
        # ----------------------------------------------------
        # Whisper
        # ----------------------------------------------------

        transcript_path = transcribe(
            meeting_id,
            audio_path
        )

        update_meeting(
            meeting_id,
            transcript_path=str(
                transcript_path.relative_to(
                    PROJECT_ROOT
                )
            )
        )

        # ----------------------------------------------------
        # Extract transcript
        # ----------------------------------------------------

        print()
        print("Processing Whisper output...")

        (
            transcript,
            language,
            duration
        ) = extract_transcript(
            transcript_path
        )

        update_meeting(
            meeting_id,
            status="transcribed",
            language=language,
            duration=duration
        )

        print(
            f"Transcript length: "
            f"{len(transcript):,} characters"
        )

        # ----------------------------------------------------
        # Speaker diarization + alignment
        # ----------------------------------------------------

        update_meeting(
            meeting_id,
            status="diarizing"
        )

        create_speaker_transcript(
            meeting_id,
            audio_path,
            transcript_path
        )

        # ----------------------------------------------------
        # Qwen
        # ----------------------------------------------------

        update_meeting(
            meeting_id,
            status="summarizing"
        )

        summary = summarize(
            transcript
        )

        # ----------------------------------------------------
        # Save summary
        # ----------------------------------------------------

        summary_path = save_summary(
            meeting_id,
            summary
        )

        update_meeting(
            meeting_id,
            summary_path=str(
                summary_path.relative_to(
                    PROJECT_ROOT
                )
            ),
            status="completed"
        )

        print()
        print(
            f"Meeting {meeting_id} completed."
        )

        return summary

    except Exception:

        update_meeting(
            meeting_id,
            status="failed"
        )

        raise


# ============================================================

def retry_meeting(
    meeting_id: str,
    audio_path: Path,
):
    """Run the complete pipeline again, starting from the recording."""

    meeting_dir = MEETINGS_DIR / meeting_id

    for filename in (
        "transcript.json",
        "transcript.srt",
        "speaker_transcript.json",
        "diarization.json",
        "summary.json",
    ):
        output_path = meeting_dir / filename
        if output_path.exists():
            output_path.unlink()

    update_meeting(
        meeting_id,
        transcript_path=None,
        speaker_transcript_path=None,
        summary_path=None,
        duration=None,
        language=None,
        status="queued",
    )

    return process_existing_meeting(meeting_id, audio_path)
# Main pipeline
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Meeting transcription and "
            "AI summarization pipeline"
        )
    )

    parser.add_argument(
        "audio",
        help="Path to meeting audio/video"
    )

    parser.add_argument(
        "--title",
        help="Meeting title"
    )

    args = parser.parse_args()

    audio_path = (
        Path(args.audio)
        .expanduser()
        .resolve()
    )

    if not audio_path.exists():

        print(
            f"ERROR: Audio file does not exist:\n"
            f"{audio_path}"
        )

        sys.exit(1)

    check_dependencies()

    # --------------------------------------------------------
    # Initialize database
    # --------------------------------------------------------

    initialize_database()

    # --------------------------------------------------------
    # Create meeting record
    # --------------------------------------------------------

    title = (
        args.title
        if args.title
        else audio_path.stem
    )

    meeting = create_meeting(
        title=title,
        original_filename=audio_path.name
    )

    meeting_id = meeting.id

    print()
    print("=" * 70)
    print("CHARCHANOTES")
    print("=" * 70)

    print()
    print(f"Meeting ID: {meeting_id}")
    print(f"Title: {title}")
    print(f"Input: {audio_path}")

    try:

        # ----------------------------------------------------
        # Store recording
        # ----------------------------------------------------

        stored_audio = store_recording(
            meeting_id,
            audio_path
        )

        update_meeting(
            meeting_id,
            audio_path=str(
                stored_audio.relative_to(
                    PROJECT_ROOT
                )
            )
        )

        print()
        print(
            f"Recording stored at:\n"
            f"{stored_audio}"
        )

        # ----------------------------------------------------
        # Whisper
        # ----------------------------------------------------

        transcript_path = transcribe(
            meeting_id,
            stored_audio
        )

        update_meeting(
            meeting_id,
            transcript_path=str(
                transcript_path.relative_to(
                    PROJECT_ROOT
                )
            )
        )

        # ----------------------------------------------------
        # Extract transcript
        # ----------------------------------------------------

        print()
        print(
            "Processing Whisper output..."
        )

        (
            transcript,
            language,
            duration
        ) = extract_transcript(
            transcript_path
        )

        update_meeting(
            meeting_id,
            status="transcribed",
            language=language,
            duration=duration
        )

        print(
            f"Transcript length: "
            f"{len(transcript):,} characters"
        )

        # ----------------------------------------------------
        # Speaker diarization + alignment
        # ----------------------------------------------------

        update_meeting(
            meeting_id,
            status="diarizing"
        )

        create_speaker_transcript(
            meeting_id,
            stored_audio,
            transcript_path
        )

        print(
            f"Language: {language}"
        )

        if duration is not None:
            print(
                f"Duration: {duration:.1f} seconds"
            )

        # ----------------------------------------------------
        # Qwen
        # ----------------------------------------------------

        update_meeting(
            meeting_id,
            status="summarizing"
        )

        summary = summarize(
            transcript
        )

        # ----------------------------------------------------
        # Save summary
        # ----------------------------------------------------

        summary_path = save_summary(
            meeting_id,
            summary
        )

        update_meeting(
            meeting_id,
            summary_path=str(
                summary_path.relative_to(
                    PROJECT_ROOT
                )
            ),
            status="completed"
        )

        # ----------------------------------------------------
        # Display
        # ----------------------------------------------------

        print_summary(
            summary
        )

        print()
        print(
            f"Meeting ID:\n{meeting_id}"
        )

        print()
        print(
            f"Meeting directory:\n"
            f"{MEETINGS_DIR / meeting_id}"
        )

        print()
        print(
            "Status: completed"
        )

    except Exception as error:

        update_meeting(
            meeting_id,
            status="failed"
        )

        print()
        print("=" * 70)
        print("PIPELINE FAILED")
        print("=" * 70)

        print()
        print(str(error))

        print()
        print(
            f"Meeting ID: {meeting_id}"
        )

        print(
            "Status: failed"
        )

        raise


if __name__ == "__main__":
    main()
