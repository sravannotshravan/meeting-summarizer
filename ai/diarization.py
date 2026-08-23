import json
import os
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from pyannote.audio import Pipeline


MODEL = "pyannote/speaker-diarization-community-1"


def load_audio_for_pyannote(
    audio_path: Path,
) -> dict:
    """
    Load audio with soundfile instead of TorchCodec.

    Pyannote accepts preloaded audio in this format:
    {
        "waveform": Tensor[channel, time],
        "sample_rate": int,
    }
    """

    waveform, sample_rate = sf.read(
        str(audio_path),
        dtype="float32",
        always_2d=True,
    )

    if waveform.size == 0:
        raise RuntimeError(
            f"Audio file is empty: {audio_path}"
        )

    waveform = np.asarray(
        waveform,
        dtype=np.float32,
    )

    # soundfile returns [time, channels].
    # Pyannote expects [channels, time].
    waveform_tensor = torch.from_numpy(
        waveform.T.copy()
    )

    return {
        "waveform": waveform_tensor,
        "sample_rate": int(sample_rate),
    }


def diarize(
    audio_path: Path,
) -> tuple[list[dict], float]:
    """
    Run speaker diarization.

    CUDA is used when available.
    CPU is used only as a fallback.
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
        print(
            f"GPU: "
            f"{torch.cuda.get_device_name(0)}"
        )
        print("Diarization device: CUDA")
    else:
        device = torch.device("cpu")
        print("Diarization device: CPU fallback")

    print("\nLoading audio into memory...")

    audio = load_audio_for_pyannote(audio_path)

    print(
        f"Sample rate: {audio['sample_rate']}"
    )
    print(
        f"Channels: {audio['waveform'].shape[0]}"
    )
    print(
        f"Samples: {audio['waveform'].shape[1]}"
    )

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

    pipeline.to(device)

    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True
        torch.cuda.empty_cache()

    print("\nRunning diarization...")

    start = time.perf_counter()

    # Passing the preloaded dictionary bypasses TorchCodec.
    output = pipeline(audio)

    elapsed = time.perf_counter() - start

    print(
        f"\nDiarization completed in "
        f"{elapsed:.2f} seconds"
    )

    diarization = (
        output.exclusive_speaker_diarization
    )

    segments: list[dict] = []

    for turn,_, speaker in diarization.itertracks(
        yield_label=True,
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
