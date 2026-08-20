import sys
import time
from pathlib import Path

import torch
from pyannote.audio import Pipeline


MODEL = "pyannote/speaker-diarization-community-1"


def main():
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <audio_file>")
        sys.exit(1)

    audio_path = Path(sys.argv[1]).expanduser().resolve()

    if not audio_path.exists():
        print(f"Audio file not found: {audio_path}")
        sys.exit(1)

    print("=" * 70)
    print("SPEAKER DIARIZATION TEST")
    print("=" * 70)

    print(f"\nAudio: {audio_path}")
    print(f"Model: {MODEL}")

    print(f"\nPyTorch: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")

    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")

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

    print(f"\nDiarization completed in {elapsed:.2f} seconds")

    print("\n" + "=" * 70)
    print("SPEAKER SEGMENTS")
    print("=" * 70)

    # Community-1 provides exclusive speaker diarization,
    # which will be useful later when aligning with Whisper.
    diarization = output.exclusive_speaker_diarization

    segments = []

    for turn, speaker in diarization:
        segment = {
            "start": round(turn.start, 3),
            "end": round(turn.end, 3),
            "speaker": speaker,
        }

        segments.append(segment)

        print(
            f"{segment['start']:8.3f}s --> "
            f"{segment['end']:8.3f}s   "
            f"{segment['speaker']}"
        )

    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)

    speakers = sorted(set(segment["speaker"] for segment in segments))

    print(f"Speakers detected: {len(speakers)}")
    print(f"Speaker labels: {', '.join(speakers)}")
    print(f"Segments: {len(segments)}")
    output_path = (
        audio_path.parent
        / f"{audio_path.stem}_diarization.json"
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        import json

        json.dump(
            segments,
            file,
            indent=2,
        )

    print()
    print(f"Diarization saved to: {output_path}")


if __name__ == "__main__":
    main()
