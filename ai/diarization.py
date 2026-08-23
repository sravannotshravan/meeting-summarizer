import json
import os
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

    CUDA is used when available. CPU is used only as a fallback.

    Returns:
        segments: Speaker segments with start, end, and speaker.
        elapsed: Processing time in seconds.
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
    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")

    if torch.cuda.is_available():
        device = torch.device("cuda:0")

        print(f"CUDA version: {torch.version.cuda}")
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print("Diarization device: CUDA")
    else:
        device = torch.device("cpu")
        print("Diarization device: CPU fallback")

    print("\nLoading pyannote pipeline...")

    hf_token = os.getenv("HF_TOKEN")

    if not hf_token:
        raise RuntimeError(
            "HF_TOKEN is required to load the pyannote model."
        )

    pipeline = Pipeline.from_pretrained(
        MODEL,
        token=hf_token,
    )

    if pipeline is None:
        raise RuntimeError(
            f"Failed to load pyannote pipeline: {MODEL}"
        )

    # Move every pyannote model component to CUDA.
    pipeline.to(device)

    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True
        torch.cuda.empty_cache()

    print("\nRunning diarization...")

    start = time.perf_counter()

    output = pipeline(str(audio_path))

    elapsed = time.perf_counter() - start

    print(
        f"\nDiarization completed in {elapsed:.2f} seconds"
    )

    # Community-1 provides exclusive speaker diarization.
    diarization = output.exclusive_speaker_diarization

    segments: list[dict] = []

    for turn, speaker in diarization.itertracks(
        yield_label=True
    ):
        segments.append(
            {
                "start": round(turn.start, 3),
                "end": round(turn.end, 3),
                "speaker": speaker,
            }
        )

    speakers = sorted(
        {
            segment["speaker"]
            for segment in segments
        }
    )

    print()
    print("=" * 70)
    print("DIARIZATION RESULT")
    print("=" * 70)
    print(f"Speakers detected: {len(speakers)}")
    print(f"Speaker labels: {', '.join(speakers)}")
    print(f"Segments: {len(segments)}")

    if device.type == "cuda":
        torch.cuda.empty_cache()

    return segments, elapsed


def save_diarization(
    output_path: Path,
    segments: list[dict],
) -> None:
    """
    Save diarization segments as JSON.
    """

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
            ensure_ascii=False,
        )
