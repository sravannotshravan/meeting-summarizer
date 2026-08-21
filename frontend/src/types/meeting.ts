export interface Meeting {
  id: string;
  title: string;
  original_filename: string;
  audio_path: string | null;
  transcript_path: string | null;
  speaker_transcript_path: string | null;
  speaker_names: Record<string, string>;
  summary_path: string | null;
  status: string;
  duration: number | null;
  language: string | null;
  created_at: string;
  updated_at: string;
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface Transcript {
  language: string;
  duration: number;
  segments: TranscriptSegment[];
}

export interface SpeakerTranscriptSegment
  extends TranscriptSegment {
  speaker: string;
  speaker_label?: string;
}

export interface SpeakerTranscript {
  language: string;
  duration: number;
  segments: SpeakerTranscriptSegment[];
}

export interface ActionItem {
  task: string;
  assignee: string;
  deadline: string;
}

export interface Summary {
  summary: string;
  key_points: string[];
  decisions: string[];
  action_items: ActionItem[];
}
