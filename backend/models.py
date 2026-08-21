from dataclasses import dataclass
from typing import Optional


@dataclass
class Meeting:

    id: str

    title: str

    original_filename: str

    audio_path: Optional[str]

    transcript_path: Optional[str]

    speaker_transcript_path: Optional[str]

    speaker_names: dict[str, str]

    summary_path: Optional[str]

    status: str

    duration: Optional[float]

    language: Optional[str]

    created_at: str

    updated_at: str
