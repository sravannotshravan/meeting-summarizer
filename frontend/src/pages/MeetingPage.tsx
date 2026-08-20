import { useEffect, useState } from "react";
import { ArrowLeft, FileAudio, LoaderCircle } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { getMeeting } from "../lib/api";
import type { Meeting } from "../types/meeting";

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "—";

  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const remaining = total % 60;

  return `${minutes}:${remaining.toString().padStart(2, "0")}`;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function MeetingPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    async function loadMeeting() {
      try {
        setLoading(true);
        setError(null);

        const data = await getMeeting(id);
        setMeeting(data);
      } catch (err) {
        console.error(err);
        setError("Unable to load this meeting.");
      } finally {
        setLoading(false);
      }
    }

    loadMeeting();
  }, [id]);

  if (loading) {
    return (
      <div className="meeting-page-state">
        <LoaderCircle className="spinner" size={25} />
        <span>Loading meeting...</span>
      </div>
    );
  }

  if (error || !meeting) {
    return (
      <div className="meeting-page-state">
        <strong>{error ?? "Meeting not found."}</strong>

        <button onClick={() => navigate("/")}>
          Back to meetings
        </button>
      </div>
    );
  }

  return (
    <div className="meeting-page">
      <header className="meeting-header">
        <button
          className="back-button"
          onClick={() => navigate("/")}
        >
          <ArrowLeft size={18} />
          Meetings
        </button>

        <div className="meeting-header-info">
          <div className="meeting-file-icon">
            <FileAudio size={22} />
          </div>

          <div>
            <h1>{meeting.title}</h1>

            <p>
              {meeting.original_filename} ·{" "}
              {formatDate(meeting.created_at)}
            </p>
          </div>
        </div>

        <div className="meeting-status">
          <span className="status-dot" />
          {meeting.status}
        </div>
      </header>

      <main className="meeting-content">
        <section className="audio-section">
          <div className="audio-placeholder">
            <FileAudio size={28} />

            <div>
              <strong>{meeting.original_filename}</strong>

              <span>
                {formatDuration(meeting.duration)} ·{" "}
                {meeting.language?.toUpperCase() ?? "Unknown language"}
              </span>
            </div>
          </div>

          <audio
            className="audio-player"
            controls
            src={`http://127.0.0.1:8000/meetings/${meeting.id}/audio`}
          />
        </section>

        <section className="meeting-panels">
          <div className="transcript-panel">
            <div className="panel-header">
              <h2>Transcript</h2>
            </div>

            <div className="panel-placeholder">
              Transcript will appear here.
            </div>
          </div>

          <div className="summary-panel">
            <div className="panel-header">
              <h2>AI Summary</h2>
            </div>

            <div className="panel-placeholder">
              Summary will appear here.
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
