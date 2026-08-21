import type {
  Meeting,
  Transcript,
  SpeakerTranscript,
  Summary,
} from "../types/meeting";

export const API_BASE_URL =
  import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : "http://127.0.0.1:8000";

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

export async function uploadMeeting(
  file: File,
  title?: string,
): Promise<{ id: string; title: string; filename: string; status: string }> {
  const formData = new FormData();
  formData.append("file", file);
  if (title && title.trim()) {
    formData.append("title", title.trim());
  }

  const response = await fetch(`${API_BASE_URL}/meetings`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let errorMsg = `Upload failed (${response.status})`;
    try {
      const err = await response.json();
      if (err?.detail) {
        errorMsg = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
      }
    } catch {
      // ignore
    }
    throw new Error(errorMsg);
  }

  return response.json();
}
export async function deleteMeeting(id: string): Promise<void> {
  const response = await fetch(API_BASE_URL + "/meetings/" + id, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error("Delete failed (" + response.status + ")");
  }
}

export async function retryMeeting(
  id: string,
): Promise<{ id: string; status: string }> {
  return request<{ id: string; status: string }>(
    "/meetings/" + id + "/retry",
    { method: "POST" },
  );
}

export async function updateSpeakerNames(
  id: string,
  names: Record<string, string>,
): Promise<{ speaker_names: Record<string, string> }> {
  return request<{ speaker_names: Record<string, string> }>(
    "/meetings/" + id + "/speakers",
    {
      method: "PUT",
      body: JSON.stringify({ names }),
    },
  );
}