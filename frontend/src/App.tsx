import { useEffect, useState } from "react";
import {
  FileAudio,
  Home,
  LoaderCircle,
  Mic,
  Plus,
  Search,
  Settings,
  Sparkles,
} from "lucide-react";

import "./App.css";

import { getMeetings } from "./lib/api";
import type { Meeting } from "./types/meeting";
import { useNavigate } from "react-router-dom";
import NewMeetingModal from "./components/NewMeetingModal";

function formatDuration(seconds: number | null): string {
  if (seconds === null) {
    return "—";
  }

  const totalSeconds = Math.round(seconds);
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = totalSeconds % 60;

  return `${minutes}m ${remainingSeconds}s`;
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function App() {
  const navigate = useNavigate();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    async function loadMeetings() {
      try {
        setLoading(true);
        setError(null);

        const data = await getMeetings();
        setMeetings(data);
      } catch (err) {
        console.error(err);
        setError("Unable to connect to the MeetingAI backend.");
      } finally {
        setLoading(false);
      }
    }

    loadMeetings();
  }, []);

  const filteredMeetings = meetings.filter((meeting) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      meeting.title.toLowerCase().includes(q) ||
      meeting.original_filename.toLowerCase().includes(q) ||
      (meeting.language && meeting.language.toLowerCase().includes(q))
    );
  });

  const totalDuration = meetings.reduce(
    (total, meeting) => total + (meeting.duration ?? 0),
    0,
  );

  const processedMeetings = meetings.filter(
    (meeting) => meeting.status === "completed",
  ).length;

  const handleMeetingCreated = (newMeetingId: string) => {
    setIsModalOpen(false);
    navigate(`/meetings/${newMeetingId}`);
  };

  return (
    <div className="app">
      <NewMeetingModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleMeetingCreated}
      />

      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Sparkles size={18} />
          </div>
          <span>MeetingAI</span>
        </div>

        <button
          className="new-meeting"
          onClick={() => setIsModalOpen(true)}
        >
          <Plus size={18} />
          New meeting
        </button>

        <nav className="nav">
          <a className="nav-item active" href="/">
            <Home size={18} />
            Meetings
          </a>

          <a className="nav-item" href="/">
            <FileAudio size={18} />
            Recordings
          </a>
        </nav>

        <div className="sidebar-section">
          <div className="section-label">Recent</div>

          {meetings.slice(0, 5).map((meeting) => (
            <div
              className="meeting-item"
              key={meeting.id}
              onClick={() => navigate(`/meetings/${meeting.id}`)}
              style={{ cursor: "pointer" }}
            >
              <div className="meeting-dot" />

              <div>
                <div className="meeting-name">{meeting.title}</div>
                <div className="meeting-date">
                  {formatDate(meeting.created_at)}
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="sidebar-bottom">
          <a className="nav-item">
            <Settings size={18} />
            Settings
          </a>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="search">
            <Search size={18} />

            <input
              placeholder="Search meetings..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />

            <kbd>⌘ K</kbd>
          </div>

          <div className="status">
            <span className="status-dot" />
            Local AI
          </div>
        </header>

        <div className="content">
          <div className="page-header">
            <div>
              <p className="eyebrow">YOUR WORKSPACE</p>

              <h1>Meetings</h1>

              <p className="subtitle">
                Your recordings, transcripts and summaries in one place.
              </p>
            </div>

            <button
              className="primary-button"
              onClick={() => setIsModalOpen(true)}
            >
              <Plus size={18} />
              New meeting
            </button>
          </div>

          <section className="stats">
            <div className="stat-card">
              <div className="stat-icon">
                <Mic size={19} />
              </div>

              <div>
                <span>Total meetings</span>
                <strong>{meetings.length}</strong>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon">
                <FileAudio size={19} />
              </div>

              <div>
                <span>Recorded time</span>
                <strong>
                  {Math.floor(totalDuration / 60)}m{" "}
                  {Math.round(totalDuration % 60)}s
                </strong>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon">
                <Sparkles size={19} />
              </div>

              <div>
                <span>AI processed</span>
                <strong>{processedMeetings}</strong>
              </div>
            </div>
          </section>

          <section className="meetings-section">
            <div className="section-heading">
              <h2>
                {searchQuery.trim()
                  ? `Search results (${filteredMeetings.length})`
                  : "Recent meetings"}
              </h2>

              {searchQuery.trim() && (
                <button
                  className="filter-button"
                  onClick={() => setSearchQuery("")}
                >
                  Clear search
                </button>
              )}
            </div>

            {loading && (
              <div className="empty-state">
                <LoaderCircle className="spinner" size={24} />
                <span>Loading meetings...</span>
              </div>
            )}

            {!loading && error && (
              <div className="error-state">
                <strong>Backend unavailable</strong>
                <span>{error}</span>

                <button
                  onClick={() => window.location.reload()}
                  className="retry-button"
                >
                  Retry
                </button>
              </div>
            )}

            {!loading && !error && filteredMeetings.length === 0 && (
              <div className="empty-state">
                <FileAudio size={28} />
                <strong>
                  {searchQuery.trim()
                    ? "No matching meetings found"
                    : "No meetings yet"}
                </strong>
                <span>
                  {searchQuery.trim()
                    ? "Try adjusting your search query."
                    : "Upload a recording to get started."}
                </span>
                {!searchQuery.trim() && (
                  <button
                    className="primary-button"
                    style={{ marginTop: "12px" }}
                    onClick={() => setIsModalOpen(true)}
                  >
                    <Plus size={16} />
                    New meeting
                  </button>
                )}
              </div>
            )}

            {!loading && !error && filteredMeetings.length > 0 && (
              <div className="meeting-grid">
                {filteredMeetings.map((meeting) => (
                  <article
                    className="meeting-card"
                    key={meeting.id}
                    onClick={() => navigate(`/meetings/${meeting.id}`)}
                    style={{ cursor: "pointer" }}
                  >
                    <div className="card-icon">
                      <FileAudio size={22} />
                    </div>

                    <div className="card-content">
                      <div className="card-top">
                        <span
                          className={
                            meeting.status === "completed"
                              ? "processed"
                              : "processing"
                          }
                        >
                          {meeting.status}
                        </span>

                        <span>{formatDate(meeting.created_at)}</span>
                      </div>

                      <h3>{meeting.title}</h3>

                      <p>{meeting.original_filename}</p>

                      <div className="card-footer">
                        <span>{formatDuration(meeting.duration)}</span>

                        <span>{meeting.language?.toUpperCase() ?? "—"}</span>

                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/meetings/${meeting.id}`);
                          }}
                        >
                          Open
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}

export default App;
