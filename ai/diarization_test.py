import sys
from pathlib import Path

from ai.diarization import (
    diarize,
    save_diarization,
)


def main():

    if len(sys.argv) != 2:
        print(
            f"Usage: python {sys.argv[0]} "
            "<audio_file>"
        )
        sys.exit(1)

    audio_path = (
        Path(sys.argv[1])
        .expanduser()
        .resolve()
    )

    if not audio_path.exists():
        print(
            f"Audio file not found: "
            f"{audio_path}"
        )
        sys.exit(1)

    segments, elapsed = diarize(
        audio_path
    )

    print()
    print("=" * 70)
    print("SPEAKER SEGMENTS")
    print("=" * 70)

    for segment in segments:

        print(
            f"{segment['start']:8.3f}s --> "
            f"{segment['end']:8.3f}s   "
            f"{segment['speaker']}"
        )

    output_path = (
        audio_path.parent
        / f"{audio_path.stem}_diarization.json"
    )

    save_diarization(
        output_path,
        segments,
    )

    print()
    print(
        f"Diarization saved to: "
        f"{output_path}"
    )


if __name__ == "__main__":
    main()
