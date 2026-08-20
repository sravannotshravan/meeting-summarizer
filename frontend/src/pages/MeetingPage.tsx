import { useEffect, useState, useRef, useCallback } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  Clock,
  FileAudio,
  ListChecks,
  LoaderCircle,
  MessageSquareText,
  Sparkles,
  User,
} from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { getMeeting, getSpeakerTranscript, getSummary, API_BASE_URL } from "../lib/api";
import type {
  Meeting,
  SpeakerTranscript,
  SpeakerTranscriptSegment,
  Summary,
} from "../types/meeting";

// ── Speaker colors ──────────────────────────────────────────

const SPEAKER_COLORS = [
  "#7c9aff", // blue
  "#f5a673", // orange
  "#82ddb5", // green
  "#d7a0f0", // purple
  "#f27a8a", // pink
  "#5cc8e0", // cyan
  "#e8d46a", // yellow
  "#f08080", // coral
];

function getSpeakerColor(
  speaker: string,
  speakerMap: Map<string, number>,
): string {
  if (!speakerMap.has(speaker)) {
    speakerMap.set(speaker, speakerMap.size);
  }

  return SPEAKER_COLORS[speakerMap.get(speaker)! % SPEAKER_COLORS.length];
}

function speakerLabel(speaker: string): string {
  if (speaker === "UNKNOWN") return "Unknown";

  const match = speaker.match(/(\d+)$/);

  if (match) {
    return `Speaker ${parseInt(match[1], 10) + 1}`;
  }

  return speaker;
}

// ── Formatters ──────────────────────────────────────────────

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "-";

  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const remaining = total % 60;

  return `${minutes}:${remaining.toString().padStart(2, "0")}`;
}

function formatTimestamp(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);

  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

// ── Component ───────────────────────────────────────────────

export default function MeetingPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Data
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [transcript, setTranscript] = useState<SpeakerTranscript | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Audio sync
  const audioRef = useRef<HTMLAudioElement>(null);
  const [activeIndex, setActiveIndex] = useState<number>(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const segmentRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const speakerColorMap = useRef<Map<string, number>>(new Map());

  // ── Fetch meeting data ──────────────────────────────────

  const fetchMeetingData = useCallback(
    async (showLoading = true) => {
      if (!id) return;

      try {
        if (showLoading) {
          setLoading(true);
          setError(null);
        }

        const meetingData = await getMeeting(id);
        setMeeting(meetingData);

        // If completed or transcribed, fetch transcript & summary
        const [transcriptResult, summaryResult] = await Promise.allSettled([
          getSpeakerTranscript(id),
          getSummary(id),
        ]);

        if (transcriptResult.status === "fulfilled") {
          setTranscript(transcriptResult.value);
        }

        if (summaryResult.status === "fulfilled") {
          setSummary(summaryResult.value);
        }
      } catch (err) {
        console.error(err);
        if (showLoading) {
          setError("Unable to load this meeting.");
        }
      } finally {
        if (showLoading) {
          setLoading(false);
        }
      }
    },
    [id],
  );

  useEffect(() => {
    fetchMeetingData(true);
  }, [fetchMeetingData]);

  // ── Polling while processing ────────────────────────────

  useEffect(() => {
    if (!meeting) return;

    const isProcessing =
      meeting.status !== "completed" && meeting.status !== "failed";

    if (!isProcessing) return;

    const interval = setInterval(() => {
      fetchMeetingData(false);
    }, 2500);

    return () => clearInterval(interval);
  }, [meeting?.status, fetchMeetingData]);

  // ── Audio sync ──────────────────────────────────────────

  const findActiveSegment = useCallback(
    (time: number): number => {
      if (!transcript) return -1;

      const segments = transcript.segments;

      for (let i = 0; i < segments.length; i++) {
        if (time >= segments[i].start && time < segments[i].end) {
          return i;
        }
      }

      // If between segments, find closest upcoming
      for (let i = 0; i < segments.length; i++) {
        if (time < segments[i].start) {
          if (i > 0 && time >= segments[i - 1].end) {
            const gapToPrev = time - segments[i - 1].end;
            const gapToNext = segments[i].start - time;
            return gapToPrev < gapToNext ? i - 1 : -1;
          }
          return -1;
        }
      }

      return -1;
    },
    [transcript],
  );

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !transcript) return;

    const handleTimeUpdate = () => {
      const index = findActiveSegment(audio.currentTime);

      setActiveIndex((prev) => {
        if (prev !== index && index >= 0) {
          // Auto-scroll
          const el = segmentRefs.current.get(index);
          if (el) {
            el.scrollIntoView({
              behavior: "smooth",
              block: "center",
            });
          }
        }
        return index;
      });
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);

    audio.addEventListener("timeupdate", handleTimeUpdate);
    audio.addEventListener("play", handlePlay);
    audio.addEventListener("pause", handlePause);

    return () => {
      audio.removeEventListener("timeupdate", handleTimeUpdate);
      audio.removeEventListener("play", handlePlay);
      audio.removeEventListener("pause", handlePause);
    };
  }, [transcript, findActiveSegment]);

  // ── Click to seek ───────────────────────────────────────

  const seekTo = (time: number) => {
    const audio = audioRef.current;
    if (!audio) return;

    audio.currentTime = time;

    if (audio.paused) {
      audio.play();
    }
  };

  // ── Loading / Error states ──────────────────────────────

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

        <button onClick={() => navigate("/")}>Back to meetings</button>
      </div>
    );
  }

  // ── Render helpers ──────────────────────────────────────

  const segments: SpeakerTranscriptSegment[] = transcript?.segments ?? [];
  const isProcessing =
    meeting.status !== "completed" && meeting.status !== "failed";

  const renderTranscript = () => {
    if (!transcript || segments.length === 0) {
      return (
        <div className="panel-placeholder">
          {isProcessing ? (
            <div className="processing-indicator">
              <LoaderCircle className="spinner" size={20} />
              <span>
                {meeting.status === "transcribing"
                  ? "Whisper is transcribing audio..."
                  : meeting.status === "diarizing"
                    ? "Pyannote is identifying speakers..."
                    : "Transcript will appear shortly..."}
              </span>
            </div>
          ) : (
            <span>No transcript available for this meeting.</span>
          )}
        </div>
      );
    }

    return (
      <div className="transcript-scroll">
        {segments.map((segment, index) => {
          const isActive = index === activeIndex;
          const color = getSpeakerColor(
            segment.speaker,
            speakerColorMap.current,
          );

          return (
            <div
              key={index}
              ref={(el) => {
                if (el) segmentRefs.current.set(index, el);
              }}
              className={`transcript-segment ${isActive ? "active" : ""} ${isPlaying && !isActive ? "dimmed" : ""}`}
              onClick={() => seekTo(segment.start)}
            >
              <div className="segment-timestamp">
                {formatTimestamp(segment.start)}
              </div>

              <div
                className="segment-speaker-dot"
                style={{ background: color }}
              />

              <div className="segment-body">
                <span
                  className="segment-speaker"
                  style={{ color }}
                >
                  {speakerLabel(segment.speaker)}
                </span>

                <span className="segment-text">{segment.text}</span>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  const renderSummary = () => {
    if (!summary) {
      return (
        <div className="panel-placeholder">
          {isProcessing ? (
            <div className="processing-indicator">
              <Sparkles className="spinner" size={20} />
              <span>
                {meeting.status === "summarizing"
                  ? "Qwen3 is generating meeting summary..."
                  : "Summary will be generated once transcript is ready..."}
              </span>
            </div>
          ) : (
            <span>No summary available for this meeting.</span>
          )}
        </div>
      );
    }

    return (
      <div className="summary-scroll">
        {/* Overview */}
        <div className="summary-section">
          <div className="summary-section-header">
            <MessageSquareText size={15} />
            <h3>Overview</h3>
          </div>

          <p className="summary-text">{summary.summary}</p>
        </div>

        {/* Key Points */}
        {summary.key_points.length > 0 && (
          <div className="summary-section">
            <div className="summary-section-header">
              <Sparkles size={15} />
              <h3>Key Points</h3>
            </div>

            <ul className="summary-list">
              {summary.key_points.map((point, i) => (
                <li key={i}>
                  <ChevronRight size={13} />
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Decisions */}
        {summary.decisions.length > 0 && (
          <div className="summary-section">
            <div className="summary-section-header">
              <CheckCircle2 size={15} />
              <h3>Decisions</h3>
            </div>

            <ul className="summary-list decisions-list">
              {summary.decisions.map((decision, i) => (
                <li key={i}>
                  <CheckCircle2 size={13} />
                  <span>{decision}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Action Items */}
        {summary.action_items.length > 0 && (
          <div className="summary-section">
            <div className="summary-section-header">
              <ListChecks size={15} />
              <h3>Action Items</h3>
            </div>

            <div className="action-items">
              {summary.action_items.map((item, i) => (
                <div className="action-item-card" key={i}>
                  <p className="action-task">{item.task}</p>

                  <div className="action-meta">
                    <span className="action-chip">
                      <User size={11} />
                      {item.assignee}
                    </span>

                    <span className="action-chip">
                      <Clock size={11} />
                      {item.deadline}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  // ── Page ────────────────────────────────────────────────

  return (
    <div className="meeting-page">
      <header className="meeting-header">
        <button className="back-button" onClick={() => navigate("/")}>
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
              {meeting.original_filename} · {formatDate(meeting.created_at)}
            </p>
          </div>
        </div>

        <div
          className={`meeting-status ${isProcessing ? "processing" : "completed"}`}
        >
          <span
            className={`status-dot ${isProcessing ? "pulse" : ""}`}
          />
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
            ref={audioRef}
            className="audio-player"
            controls
            src={`${API_BASE_URL}/meetings/${meeting.id}/audio`}
          />
        </section>

        <section className="meeting-panels">
          <div className="transcript-panel">
            <div className="panel-header">
              <h2>Transcript</h2>

              {transcript && (
                <span className="panel-badge">
                  {segments.length} segments
                </span>
              )}
            </div>

            {renderTranscript()}
          </div>

          <div className="summary-panel">
            <div className="panel-header">
              <h2>AI Summary</h2>
            </div>

            {renderSummary()}
          </div>
        </section>
      </main>
    </div>
  );
}

