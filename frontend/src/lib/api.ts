import type {
  Meeting,
  Transcript,
  SpeakerTranscript,
  Summary,
} from "../types/meeting";

const API_BASE_URL = "http://127.0.0.1:8000";

async function request<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });

  if (!response.ok) {
    throw new Error(
      `API request failed: ${response.status} ${response.statusText}`,
    );
  }

  return response.json();
}

export async function getMeetings(): Promise<Meeting[]> {
  return request<Meeting[]>("/meetings");
}

export async function getMeeting(id: string): Promise<Meeting> {
  return request<Meeting>(`/meetings/${id}`);
}

export async function getTranscript(
  id: string,
): Promise<Transcript> {
  return request<Transcript>(
    `/meetings/${id}/transcript`,
  );
}

export async function getSpeakerTranscript(
  id: string,
): Promise<SpeakerTranscript> {
  return request<SpeakerTranscript>(
    `/meetings/${id}/speaker-transcript`,
  );
}

export async function getSummary(
  id: string,
): Promise<Summary> {
  return request<Summary>(
    `/meetings/${id}/summary`,
  );
}
