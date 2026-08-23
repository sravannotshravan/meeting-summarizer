import argparse
import json
import os
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
from ai.diarization import diarize, save_diarization
from backend.database import initialize_database
from backend.storage import (
    create_meeting,
    save_speaker_transcript,
    update_meeting,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEETINGS_DIR = PROJECT_ROOT / "data" / "meetings"

WHISPER_CLI = Path(
    os.getenv(
        "WHISPER_CLI_PATH",
        str(
            Path.home()
            / "whisper.cpp"
            / "build"
            / "bin"
            / "whisper-cli"
        ),
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
        ),
    )
).resolve()

LLAMA_URL = os.getenv(
    "LLAMA_URL",
    "http://127.0.0.1:8080/v1/chat/completions",
)

LLAMA_MODEL = os.getenv(
    "LLAMA_MODEL",
    "Qwen3-8B",
)


SUMMARY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {
            "type": "string",
        },
        "key_points": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "decisions": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "task": {
                        "type": "string",
                    },
                    "assignee": {
                        "type": "string",
                    },
                    "deadline": {
                        "type": "string",
                    },
                },
                "required": [
                    "task",
                    "assignee",
                    "deadline",
                ],
            },
        },
    },
    "required": [
        "summary",
        "key_points",
        "decisions",
        "action_items",
    ],
}


def check_dependencies() -> None:
    if not WHISPER_CLI.exists():
        raise RuntimeError(
            f"Whisper executable not found:\n{WHISPER_CLI}"
        )

    if not WHISPER_MODEL.exists():
        raise RuntimeError(
            f"Whisper model not found:\n{WHISPER_MODEL}"
        )

    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg was not found. Install ffmpeg in the container."
        )


def prepare_audio(
    meeting_id: str,
    audio_path: Path,
) -> Path:
    """
    Convert uploaded media to a Whisper and pyannote-compatible WAV.

    The output is:
    - 16 kHz
    - mono
    - signed 16-bit PCM
    """

    audio_path = Path(audio_path).expanduser().resolve()

    if not audio_path.exists():
        raise FileNotFoundError(
            f"Audio file not found: {audio_path}"
        )

    meeting_dir = MEETINGS_DIR / meeting_id
    meeting_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    normalized_path = (
        meeting_dir / "audio_normalized.wav"
    )

    print()
    print("=" * 70)
    print("AUDIO NORMALIZATION")
    print("=" * 70)
    print(f"Input: {audio_path}")
    print(f"Output: {normalized_path}")

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(audio_path),
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(normalized_path),
    ]

    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )

    if (
        result.returncode != 0
        or not normalized_path.exists()
        or normalized_path.stat().st_size == 0
    ):
        raise RuntimeError(
            "ffmpeg could not decode the uploaded audio:\n"
            f"{result.stderr[-4000:]}"
        )

    return normalized_path


def store_recording(
    meeting_id: str,
    source_path: Path,
) -> Path:
    meeting_dir = MEETINGS_DIR / meeting_id

    meeting_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        meeting_dir
        / f"recording{source_path.suffix.lower()}"
    )

    shutil.copy2(
        source_path,
        destination,
    )

    return destination


def create_speaker_transcript(
    meeting_id: str,
    audio_path: Path,
    whisper_path: Path,
) -> Path:
    """
    Run speaker diarization, align it with Whisper,
    and save the speaker transcript.
    """

    meeting_dir = MEETINGS_DIR / meeting_id

    diarization_path = (
        meeting_dir / "diarization.json"
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

    print()
    print("Running speaker diarization...")

    diarization_segments, elapsed = diarize(
        audio_path,
    )

    save_diarization(
        diarization_path,
        diarization_segments,
    )

    print(
        f"Diarization saved to:\n"
        f"{diarization_path}"
    )

    print()
    print("Aligning Whisper transcript with speakers...")

    whisper_segments, language, duration = (
        load_whisper_segments(
            whisper_path,
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

    speaker_transcript_path = (
        save_speaker_transcript(
            meeting_id,
            aligned_temp_path,
        )
    )

    print(
        f"Speaker transcript saved to:\n"
        f"{speaker_transcript_path}"
    )

    return speaker_transcript_path


def transcribe(
    meeting_id: str,
    audio_path: Path,
) -> Path:
    meeting_dir = MEETINGS_DIR / meeting_id

    output_base = meeting_dir / "transcript"
    output_json = meeting_dir / "transcript.json"

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
    print("STEP 1/2 - TRANSCRIPTION")
    print("=" * 70)
    print(f"Audio: {audio_path}")
    print(f"Model: {WHISPER_MODEL}")

    update_meeting(
        meeting_id,
        status="transcribing",
    )

    result = subprocess.run(
        command,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Whisper exited with code "
            f"{result.returncode}"
        )

    if not output_json.exists():
        raise RuntimeError(
            "Whisper finished but transcript was not found:\n"
            f"{output_json}"
        )

    return output_json


def extract_transcript(
    json_path: Path,
) -> tuple[str, str | None, float | None]:
    with json_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    transcription = data.get("transcription")

    if not isinstance(transcription, list):
        raise RuntimeError(
            "Whisper JSON does not contain a valid "
            "transcription array."
        )

    lines: list[str] = []
    end_ms = 0

    for segment in transcription:
        timestamps = segment.get(
            "timestamps",
            {},
        )

        offsets = segment.get(
            "offsets",
            {},
        )

        start = timestamps.get(
            "from",
            "Unknown",
        )

        text = segment.get(
            "text",
            "",
        ).strip()

        if not text:
            continue

        lines.append(
            f"[{start}] {text}"
        )

        segment_end = offsets.get("to")

        if isinstance(
            segment_end,
            (int, float),
        ):
            end_ms = max(
                end_ms,
                segment_end,
            )

    language = (
        data.get(
            "result",
            {},
        ).get("language")
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
        duration,
    )


def summarize(transcript: str) -> dict:
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
        "model": LLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt.strip(),
            },
            {
                "role": "user",
                "content": user_prompt.strip(),
            },
        ],
        "temperature": 0.1,
        "max_tokens": 1200,
        "chat_template_kwargs": {
            "enable_thinking": False,
        },
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "meeting_summary",
                "schema": SUMMARY_SCHEMA,
            },
        },
    }

    print()
    print("=" * 70)
    print("STEP 2/2 - AI SUMMARIZATION")
    print("=" * 70)
    print("Sending transcript to Qwen3...")

    try:
        response = requests.post(
            LLAMA_URL,
            json=payload,
            timeout=300,
        )
    except requests.exceptions.ConnectionError as error:
        raise RuntimeError(
            "Could not connect to llama-server."
        ) from error

    response.raise_for_status()

    result = response.json()

    try:
        content = (
            result["choices"][0]["message"]["content"]
        )
    except (
        KeyError,
        IndexError,
        TypeError,
    ) as error:
        raise RuntimeError(
            "Unexpected response from llama-server:\n"
            + json.dumps(
                result,
                indent=2,
            )
        ) from error

    if not content or not content.strip():
        raise RuntimeError(
            "Qwen returned empty content."
        )

    try:
        return json.loads(content)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Qwen returned invalid JSON:\n"
            f"{content}"
        ) from error


def save_summary(
    meeting_id: str,
    summary: dict,
) -> Path:
    meeting_dir = MEETINGS_DIR / meeting_id
    summary_path = meeting_dir / "summary.json"

    with summary_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            summary,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return summary_path


def process_existing_meeting(
    meeting_id: str,
    audio_path: Path,
):
    """
    Run the complete pipeline for an existing meeting.
    """

    try:
        normalized_audio_path = prepare_audio(
            meeting_id,
            audio_path,
        )

        transcript_path = transcribe(
            meeting_id,
            normalized_audio_path,
        )

        update_meeting(
            meeting_id,
            transcript_path=str(
                transcript_path.relative_to(
                    PROJECT_ROOT,
                )
            ),
        )

        print()
        print("Processing Whisper output...")

        (
            transcript,
            language,
            duration,
        ) = extract_transcript(
            transcript_path,
        )

        update_meeting(
            meeting_id,
            status="transcribed",
            language=language,
            duration=duration,
        )

        print(
            f"Transcript length: "
            f"{len(transcript):,} characters"
        )

        update_meeting(
            meeting_id,
            status="diarizing",
        )

        create_speaker_transcript(
            meeting_id,
            normalized_audio_path,
            transcript_path,
        )

        update_meeting(
            meeting_id,
            status="summarizing",
        )

        summary = summarize(transcript)

        summary_path = save_summary(
            meeting_id,
            summary,
        )

        update_meeting(
            meeting_id,
            summary_path=str(
                summary_path.relative_to(
                    PROJECT_ROOT,
                )
            ),
            status="completed",
        )

        print()
        print(
            f"Meeting {meeting_id} completed."
        )

        return summary

    except Exception:
        update_meeting(
            meeting_id,
            status="failed",
        )
        raise


def retry_meeting(
    meeting_id: str,
    audio_path: Path,
):
    """
    Remove previous artifacts and run the pipeline again.
    """

    meeting_dir = MEETINGS_DIR / meeting_id

    for filename in (
        "transcript.json",
        "transcript.srt",
        "speaker_transcript.json",
        "diarization.json",
        "summary.json",
        "audio_normalized.wav",
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

    return process_existing_meeting(
        meeting_id,
        audio_path,
    )


def print_summary(summary: dict) -> None:
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
        print(f"- {point}")

    print()
    print("DECISIONS")
    print("-" * 70)

    if summary["decisions"]:
        for decision in summary["decisions"]:
            print(f"- {decision}")
    else:
        print("None identified.")

    print()
    print("ACTION ITEMS")
    print("-" * 70)

    if summary["action_items"]:
        for item in summary["action_items"]:
            print(f"- {item['task']}")
            print(f"  Assignee: {item['assignee']}")
            print(f"  Deadline: {item['deadline']}")
    else:
        print("None identified.")

    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Meeting transcription and "
            "AI summarization pipeline"
        ),
    )

    parser.add_argument(
        "audio",
        help="Path to meeting audio/video",
    )

    parser.add_argument(
        "--title",
        help="Meeting title",
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
    initialize_database()

    title = (
        args.title
        if args.title
        else audio_path.stem
    )

    meeting = create_meeting(
        title=title,
        original_filename=audio_path.name,
    )

    meeting_id = meeting.id

    print()
    print("=" * 70)
    print("CHARCHANOTES")
    print("=" * 70)
    print(f"Meeting ID: {meeting_id}")
    print(f"Title: {title}")
    print(f"Input: {audio_path}")

    try:
        stored_audio = store_recording(
            meeting_id,
            audio_path,
        )

        update_meeting(
            meeting_id,
            audio_path=str(
                stored_audio.relative_to(
                    PROJECT_ROOT,
                )
            ),
        )

        normalized_audio_path = prepare_audio(
            meeting_id,
            stored_audio,
        )

        transcript_path = transcribe(
            meeting_id,
            normalized_audio_path,
        )

        update_meeting(
            meeting_id,
            transcript_path=str(
                transcript_path.relative_to(
                    PROJECT_ROOT,
                )
            ),
        )

        (
            transcript,
            language,
            duration,
        ) = extract_transcript(
            transcript_path,
        )

        update_meeting(
            meeting_id,
            status="transcribed",
            language=language,
            duration=duration,
        )

        update_meeting(
            meeting_id,
            status="diarizing",
        )

        create_speaker_transcript(
            meeting_id,
            normalized_audio_path,
            transcript_path,
        )

        update_meeting(
            meeting_id,
            status="summarizing",
        )

        summary = summarize(transcript)

        summary_path = save_summary(
            meeting_id,
            summary,
        )

        update_meeting(
            meeting_id,
            summary_path=str(
                summary_path.relative_to(
                    PROJECT_ROOT,
                )
            ),
            status="completed",
        )

        print_summary(summary)

        print()
        print(f"Meeting ID: {meeting_id}")
        print("Status: completed")

    except Exception as error:
        update_meeting(
            meeting_id,
            status="failed",
        )

        print()
        print("=" * 70)
        print("PIPELINE FAILED")
        print("=" * 70)
        print(str(error))
        print(f"Meeting ID: {meeting_id}")
        print("Status: failed")

        raise


if __name__ == "__main__":
    main()
