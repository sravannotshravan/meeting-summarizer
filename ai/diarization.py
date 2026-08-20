import time
from pathlib import Path

import torch
from pyannote.audio import Pipeline


MODEL = "pyannote/speaker-diarization-community-1"


def diarize(
    audio_path: Path,
) -> tuple[list[dict], float]:
    """
    Run speaker diarization on an audio file.

    Returns:
        segments:
            List of speaker segments with start, end and speaker.
        elapsed:
            Processing time in seconds.
    """

    audio_path = (
        Path(audio_path)
        .expanduser()
        .resolve()
    )

    if not audio_path.exists():
        raise FileNotFoundError(
            f"Audio file not found: {audio_path}"
        )

    print()
    print("=" * 70)
    print("SPEAKER DIARIZATION")
    print("=" * 70)

    print(f"\nAudio: {audio_path}")
    print(f"Model: {MODEL}")

    print(f"\nPyTorch: {torch.__version__}")
    print(
        f"CUDA available: "
        f"{torch.cuda.is_available()}"
    )

    if torch.cuda.is_available():
        print(
            f"GPU: "
            f"{torch.cuda.get_device_name(0)}"
        )

    print("\nLoading pyannote pipeline...")

    pipeline = Pipeline.from_pretrained(MODEL)

    if torch.cuda.is_available():
        pipeline.to(torch.device("cuda"))
        print("Diarization device: CUDA")
    else:
        print("Diarization device: CPU")

    print("\nRunning diarization...")

    start = time.perf_counter()

    output = pipeline(str(audio_path))

    elapsed = time.perf_counter() - start

    print(
        f"\nDiarization completed in "
        f"{elapsed:.2f} seconds"
    )

    # Community-1 provides exclusive speaker
    # diarization, which is what we want for
    # aligning with Whisper.
    diarization = (
        output.exclusive_speaker_diarization
    )

    segments = []

    for turn, speaker in diarization:

        segment = {
            "start": round(
                turn.start,
                3,
            ),
            "end": round(
                turn.end,
                3,
            ),
            "speaker": speaker,
        }

        segments.append(segment)

    speakers = sorted(
        set(
            segment["speaker"]
            for segment in segments
        )
    )

    print()
    print("=" * 70)
    print("DIARIZATION RESULT")
    print("=" * 70)

    print(
        f"Speakers detected: "
        f"{len(speakers)}"
    )

    print(
        f"Speaker labels: "
        f"{', '.join(speakers)}"
    )

    print(
        f"Segments: "
        f"{len(segments)}"
    )

    return segments, elapsed


def save_diarization(
    output_path: Path,
    segments: list[dict],
):
    """
    Save diarization segments as JSON.
    """

    import json

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            segments,
            file,
            indent=2,
        )
