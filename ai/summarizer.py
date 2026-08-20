
import json
import sys
from pathlib import Path

import requests


# ============================================================
# Configuration
# ============================================================

LLAMA_URL = "http://127.0.0.1:8080/v1/chat/completions"

DEFAULT_MODEL = "Qwen3-8B"

OUTPUT_DIR = Path.home() / "meeting-summarizer" / "summaries"


# ============================================================
# JSON Schema
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
# Load Whisper transcript
# ============================================================

def load_transcript(path: Path) -> dict:
    """Load Whisper.cpp JSON output."""

    if not path.exists():
        raise FileNotFoundError(
            f"Transcript file does not exist: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


# ============================================================
# Extract transcript segments
# ============================================================

def extract_segments(data: dict) -> list[dict]:
    """
    Extract timestamped transcription segments from
    Whisper.cpp's JSON output.
    """

    transcription = data.get("transcription")

    if not isinstance(transcription, list):
        raise ValueError(
            "Whisper JSON does not contain a valid "
            "'transcription' array."
        )

    segments = []

    for segment in transcription:

        timestamps = segment.get("timestamps", {})
        offsets = segment.get("offsets", {})

        text = segment.get("text", "").strip()

        if not text:
            continue

        segments.append(
            {
                "start": timestamps.get("from"),
                "end": timestamps.get("to"),
                "start_ms": offsets.get("from"),
                "end_ms": offsets.get("to"),
                "text": text
            }
        )

    return segments


# ============================================================
# Build LLM transcript
# ============================================================

def build_transcript(segments: list[dict]) -> str:
    """
    Convert timestamped Whisper segments into text suitable
    for the LLM while preserving timestamps.
    """

    lines = []

    for segment in segments:

        start = segment["start"]
        text = segment["text"]

        lines.append(
            f"[{start}] {text}"
        )

    return "\n".join(lines)


# ============================================================
# Build LLM request
# ============================================================

def build_payload(transcript: str) -> dict:

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
8. Do not include information that is not relevant to the meeting.
"""

    user_prompt = f"""
Analyze this meeting transcript.

The timestamps are included so that the transcript can be
referenced precisely. They are not speaker labels.

TRANSCRIPT
-----------

{transcript}

-----------

Return the requested structured meeting analysis.
"""

    return {
        "model": DEFAULT_MODEL,

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

        # Qwen3 reasoning is unnecessary for extraction.
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


# ============================================================
# Call llama-server
# ============================================================

def summarize(transcript: str) -> dict:

    payload = build_payload(transcript)

    try:
        response = requests.post(
            LLAMA_URL,
            json=payload,
            timeout=300
        )

    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Could not connect to llama-server.\n\n"
            "Make sure it is running on "
            "http://127.0.0.1:8080"
        )

    response.raise_for_status()

    result = response.json()

    try:
        content = (
            result["choices"][0]
            ["message"]
            ["content"]
        )

    except (KeyError, IndexError, TypeError):

        raise RuntimeError(
            "Unexpected response from llama-server:\n"
            + json.dumps(result, indent=2)
        )

    if not content or not content.strip():

        raise RuntimeError(
            "Qwen returned empty content.\n\n"
            "Full response:\n"
            + json.dumps(result, indent=2)
        )

    try:
        return json.loads(content)

    except json.JSONDecodeError:

        raise RuntimeError(
            "Qwen returned invalid JSON:\n\n"
            + content
        )


# ============================================================
# Save result
# ============================================================

def save_summary(
    summary: dict,
    input_path: Path
) -> Path:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_name = (
        input_path.stem
        + "_summary.json"
    )

    output_path = OUTPUT_DIR / output_name

    with output_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            summary,
            file,
            indent=2,
            ensure_ascii=False
        )

    return output_path


# ============================================================
# Pretty-print result
# ============================================================

def print_summary(summary: dict):

    print()
    print("=" * 70)
    print("MEETING SUMMARY")
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

    for decision in summary["decisions"]:
        print(f"• {decision}")

    print()
    print("ACTION ITEMS")
    print("-" * 70)

    for item in summary["action_items"]:

        print(f"• {item['task']}")
        print(f"  Assignee: {item['assignee']}")
        print(f"  Deadline: {item['deadline']}")
        print()


# ============================================================
# Main
# ============================================================

def main():

    if len(sys.argv) != 2:

        print(
            "Usage:\n"
            "  python ai/summarizer.py "
            "<whisper_json>"
        )

        sys.exit(1)

    input_path = Path(sys.argv[1]).expanduser()

    print(
        f"Loading transcript: {input_path}"
    )

    data = load_transcript(input_path)

    segments = extract_segments(data)

    if not segments:

        raise RuntimeError(
            "No transcription segments found."
        )

    print(
        f"Loaded {len(segments)} transcript segments."
    )

    transcript = build_transcript(segments)

    print(
        f"Transcript length: "
        f"{len(transcript):,} characters"
    )

    print()
    print("Sending transcript to Qwen3...")

    summary = summarize(transcript)

    output_path = save_summary(
        summary,
        input_path
    )

    print_summary(summary)

    print("=" * 70)
    print(
        f"Saved summary to:\n{output_path}"
    )


if __name__ == "__main__":
    main()


