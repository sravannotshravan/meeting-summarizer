import { useEffect, useState } from "react";
import {
  Check,
  CheckSquare,
  FileAudio,

  LoaderCircle,
  Mic,
  Plus,
  Search,
  Settings,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";

import "./App.css";

import { deleteMeeting, getMeetings } from "./lib/api";
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
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    async function loadMeetings() {
      try {
        setLoading(true);
        setError(null);

        const data = await getMeetings();
        setMeetings(data);
      } catch (err) {
        console.error(err);
        setError("Unable to connect to the CharchaNotes backend.");
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
  };  const toggleSelection = (meetingId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(meetingId)) next.delete(meetingId);
      else next.add(meetingId);
      return next;
    });
  };

  const selectVisibleMeetings = () => {
    setSelectedIds((current) => {
      const next = new Set(current);
      filteredMeetings.forEach((meeting) => next.add(meeting.id));
      return next;
    });
  };

  const clearSelection = () => {
    setSelectedIds(new Set());
    setIsSelectionMode(false);
    setDeleteError(null);
  };

  const handleDeleteSelected = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0 || isDeleting) return;

    const noun = ids.length === 1 ? "meeting" : "meetings";
    if (!window.confirm("Delete " + ids.length + " " + noun + " and all of their files?")) return;

    try {
      setIsDeleting(true);
      setDeleteError(null);
      await Promise.all(ids.map((id) => deleteMeeting(id)));
      setMeetings((current) =>
        current.filter((meeting) => !selectedIds.has(meeting.id)),
      );
      clearSelection();
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : "Unable to delete the selected meetings.",
      );
    } finally {
      setIsDeleting(false);
    }
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
          <span>CharchaNotes</span>
        </div>

        <button
          className="new-meeting"
          onClick={() => setIsModalOpen(true)}
        >
          <Plus size={18} />
          New meeting
        </button>
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

        <div className="sidebar-bottom">          <button
            className="nav-item settings-nav-item"
            onClick={() => navigate("/settings")}
          >
            <Settings size={18} />
            Settings
          </button>
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
                  ? "Search results (" + filteredMeetings.length + ")"
                  : "Recent meetings"}
              </h2>

              <div className="meeting-selection-actions">
                {isSelectionMode ? (
                  <>
                    <span className="selection-count">{selectedIds.size} selected</span>
                    <button className="selection-button" onClick={selectVisibleMeetings} disabled={filteredMeetings.length === 0}>
                      <CheckSquare size={14} />
                      Select visible
                    </button>
                    <button className="bulk-delete-button" onClick={handleDeleteSelected} disabled={selectedIds.size === 0 || isDeleting}>
                      <Trash2 size={14} />
                      {isDeleting ? "Deleting..." : "Delete selected"}
                    </button>
                    <button className="selection-button" onClick={clearSelection}>
                      <X size={14} />
                      Cancel
                    </button>
                  </>
                ) : (
                  <button className="selection-button" onClick={() => setIsSelectionMode(true)}>
                    <CheckSquare size={14} />
                    Select
                  </button>
                )}

                {searchQuery.trim() && (
                  <button className="filter-button" onClick={() => setSearchQuery("")}>
                    Clear search
                  </button>
                )}
              </div>
            </div>

            {deleteError && <div className="bulk-delete-error">{deleteError}</div>}

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
                    className={"meeting-card " + (selectedIds.has(meeting.id) ? "selected" : "")}
                    key={meeting.id}
                    onClick={() => navigate(`/meetings/${meeting.id}`)}
                    style={{ cursor: "pointer" }}
                  >
                    {isSelectionMode && (
                      <button
                        className={"meeting-select-checkbox " + (selectedIds.has(meeting.id) ? "checked" : "")}
                        aria-label={"Select " + meeting.title}
                        onClick={(event) => {
                          event.stopPropagation();
                          toggleSelection(meeting.id);
                        }}
                      >
                        {selectedIds.has(meeting.id) ? <Check size={14} /> : null}
                      </button>
                    )}

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
