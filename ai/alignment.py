import json
import sys
from pathlib import Path


def calculate_overlap(
    start_a: float,
    end_a: float,
    start_b: float,
    end_b: float,
) -> float:
    """Return the overlap duration between two time ranges."""

    start = max(start_a, start_b)
    end = min(end_a, end_b)

    return max(0.0, end - start)


def assign_speaker(
    start: float,
    end: float,
    diarization_segments: list[dict],
) -> str:
    """
    Assign the speaker with the greatest temporal overlap
    with a Whisper segment.
    """

    speaker_overlap = {}

    for segment in diarization_segments:

        overlap = calculate_overlap(
            start,
            end,
            segment["start"],
            segment["end"],
        )

        if overlap <= 0:
            continue

        speaker = segment["speaker"]

        speaker_overlap[speaker] = (
            speaker_overlap.get(speaker, 0.0)
            + overlap
        )

    if not speaker_overlap:
        return "UNKNOWN"

    return max(
        speaker_overlap,
        key=speaker_overlap.get,
    )


def align_transcript(
    whisper_segments: list[dict],
    diarization_segments: list[dict],
) -> list[dict]:

    aligned = []

    for whisper_segment in whisper_segments:

        start = whisper_segment["start"]
        end = whisper_segment["end"]

        speaker = assign_speaker(
            start,
            end,
            diarization_segments,
        )

        aligned.append({
            "start": start,
            "end": end,
            "speaker": speaker,
            "text": whisper_segment["text"].strip(),
        })

    return aligned


def load_whisper_segments(
    whisper_path: Path,
) -> tuple[list[dict], str, float]:

    with whisper_path.open(
        "r",
        encoding="utf-8",
    ) as file:

        data = json.load(file)

    segments = []

    for item in data["transcription"]:

        start = (
            item["offsets"]["from"]
            / 1000.0
        )

        end = (
            item["offsets"]["to"]
            / 1000.0
        )

        segments.append({
            "start": start,
            "end": end,
            "text": item["text"].strip(),
        })

    language = data["result"].get(
        "language",
        "unknown",
    )

    duration = (
        segments[-1]["end"]
        if segments
        else 0.0
    )

    return segments, language, duration


def save_aligned_transcript(
    output_path: Path,
    segments: list[dict],
    language: str,
    duration: float,
):

    output = {
        "language": language,
        "duration": duration,
        "segments": segments,
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False,
        )


def main():

    if len(sys.argv) != 3:

        print(
            "Usage:\n"
            "python ai/alignment.py "
            "<whisper.json> <diarization.json>"
        )

        sys.exit(1)

    whisper_path = Path(
        sys.argv[1]
    ).expanduser().resolve()

    diarization_path = Path(
        sys.argv[2]
    ).expanduser().resolve()

    if not whisper_path.exists():

        print(
            f"Whisper file not found: "
            f"{whisper_path}"
        )

        sys.exit(1)

    if not diarization_path.exists():

        print(
            f"Diarization file not found: "
            f"{diarization_path}"
        )

        sys.exit(1)

    # --------------------------------------------------------
    # Load Whisper
    # --------------------------------------------------------

    print("Loading Whisper transcript...")

    whisper_segments, language, duration = (
        load_whisper_segments(
            whisper_path
        )
    )

    # --------------------------------------------------------
    # Load diarization
    # --------------------------------------------------------

    print("Loading diarization...")

    with diarization_path.open(
        "r",
        encoding="utf-8",
    ) as file:

        diarization_segments = json.load(
            file
        )

    # --------------------------------------------------------
    # Align
    # --------------------------------------------------------

    print("Aligning speakers...")

    aligned = align_transcript(
        whisper_segments,
        diarization_segments,
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    output_path = (
        whisper_path.parent
        / "speaker_transcript.json"
    )

    save_aligned_transcript(
        output_path,
        aligned,
        language,
        duration,
    )

    # --------------------------------------------------------
    # Print
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SPEAKER-AWARE TRANSCRIPT")
    print("=" * 70)

    for segment in aligned:

        print(
            f"[{segment['start']:8.2f} → "
            f"{segment['end']:8.2f}] "
            f"{segment['speaker']:12} "
            f"{segment['text']}"
        )

    print()
    print(
        f"Saved to: {output_path}"
    )


if __name__ == "__main__":
    main()