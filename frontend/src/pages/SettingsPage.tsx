import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  Gauge,
  Info,
  Save,
  Settings2,
  ShieldCheck,
  Sparkles,
  Waypoints,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { API_BASE_URL } from "../lib/api";

const SETTINGS_KEY = "charchanotes-settings";

type Preferences = {
  confirmDelete: boolean;
  autoFollowTranscript: boolean;
  playbackSpeed: string;
};

const DEFAULT_PREFERENCES: Preferences = {
  confirmDelete: true,
  autoFollowTranscript: true,
  playbackSpeed: "1",
};

function loadPreferences(): Preferences {
  try {
    const stored = localStorage.getItem(SETTINGS_KEY);
    return stored
      ? { ...DEFAULT_PREFERENCES, ...JSON.parse(stored) }
      : DEFAULT_PREFERENCES;
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export default function SettingsPage() {
  const navigate = useNavigate();
  const [preferences, setPreferences] = useState<Preferences>(loadPreferences);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setSaved(false);
  }, [preferences]);

  const updatePreference = <K extends keyof Preferences>(
    key: K,
    value: Preferences[K],
  ) => {
    setPreferences((current) => ({ ...current, [key]: value }));
  };

  const savePreferences = () => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(preferences));
    setSaved(true);
  };

  return (
    <div className="settings-page">
      <header className="settings-header">
        <button className="settings-back" onClick={() => navigate("/")}>
          <ArrowLeft size={17} />
          Back to meetings
        </button>

        <div className="settings-heading">
          <div className="settings-heading-icon">
            <Settings2 size={19} />
          </div>
          <div>
            <p className="eyebrow">WORKSPACE PREFERENCES</p>
            <h1>Settings</h1>
          </div>
        </div>

        <button className="settings-save-button" onClick={savePreferences}>
          {saved ? <Check size={15} /> : <Save size={15} />}
          {saved ? "Saved" : "Save changes"}
        </button>
      </header>

      <main className="settings-content">
        <section className="settings-intro">
          <span className="settings-kicker">
            <Sparkles size={13} />
            Local by design
          </span>
          <h2>Make CharchaNotes feel like yours.</h2>
          <p>
            These preferences are stored in this browser. Your recordings,
            transcripts, and summaries remain in the local CharchaNotes data
            directory.
          </p>
        </section>

        <div className="settings-grid">
          <section className="settings-card">
            <div className="settings-card-heading">
              <div className="settings-card-icon blue">
                <Waypoints size={17} />
              </div>
              <div>
                <h3>Transcript experience</h3>
                <p>Choose how the meeting page follows your audio.</p>
              </div>
            </div>

            <label className="settings-row">
              <span>
                <strong>Follow active segment</strong>
                <small>Scroll the transcript as audio plays.</small>
              </span>
              <input
                className="settings-switch"
                type="checkbox"
                checked={preferences.autoFollowTranscript}
                onChange={(event) =>
                  updatePreference("autoFollowTranscript", event.target.checked)
                }
              />
            </label>

            <label className="settings-row">
              <span>
                <strong>Playback speed</strong>
                <small>Default speed for the meeting audio player.</small>
              </span>
              <span className="settings-select">
                <select
                  value={preferences.playbackSpeed}
                  onChange={(event) =>
                    updatePreference("playbackSpeed", event.target.value)
                  }
                >
                  <option value="0.75">0.75×</option>
                  <option value="1">1×</option>
                  <option value="1.25">1.25×</option>
                  <option value="1.5">1.5×</option>
                  <option value="2">2×</option>
                </select>
                <ChevronDown size={13} />
              </span>
            </label>
          </section>

          <section className="settings-card">
            <div className="settings-card-heading">
              <div className="settings-card-icon amber">
                <ShieldCheck size={17} />
              </div>
              <div>
                <h3>Safety</h3>
                <p>Keep destructive actions intentional.</p>
              </div>
            </div>

            <label className="settings-row">
              <span>
                <strong>Confirm before deleting</strong>
                <small>Ask before removing meetings and recordings.</small>
              </span>
              <input
                className="settings-switch"
                type="checkbox"
                checked={preferences.confirmDelete}
                onChange={(event) =>
                  updatePreference("confirmDelete", event.target.checked)
                }
              />
            </label>
          </section>

          <section className="settings-card settings-system-card">
            <div className="settings-card-heading">
              <div className="settings-card-icon green">
                <Gauge size={17} />
              </div>
              <div>
                <h3>Local AI runtime</h3>
                <p>Current connection details used by this browser.</p>
              </div>
            </div>

            <div className="settings-detail">
              <span>Backend endpoint</span>
              <code>{API_BASE_URL}</code>
            </div>
            <div className="settings-detail">
              <span>Summarization model</span>
              <strong>Qwen3-8B via llama.cpp</strong>
            </div>
            <div className="settings-detail">
              <span>Speech model</span>
              <strong>whisper.cpp · ggml-small</strong>
            </div>
            <div className="settings-detail">
              <span>Speaker model</span>
              <strong>pyannote community-1</strong>
            </div>
          </section>
        </div>

        <div className="settings-note">
          <Info size={15} />
          <span>
            CharchaNotes does not upload meeting content to a cloud service.
            Model serving and processing run through your local stack.
          </span>
        </div>
      </main>
    </div>
  );
}
