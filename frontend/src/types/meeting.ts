export interface Meeting {
  id: string;
  title: string;
  original_filename: string;

  audio_path: string | null;
  transcript_path: string | null;
  summary_path: string | null;

  status: string;

  duration: number | null;
  language: string | null;

  created_at: string;
  updated_at: string;
}
