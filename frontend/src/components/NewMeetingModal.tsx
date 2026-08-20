import React, { useState, useRef, useEffect } from "react";
import {
  AlertCircle,
  FileAudio,
  LoaderCircle,
  Sparkles,
  UploadCloud,
  X,
} from "lucide-react";
import { uploadMeeting } from "../lib/api";

interface NewMeetingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (meetingId: string) => void;
}

const ALLOWED_EXTENSIONS = [
  ".mp3",
  ".mp4",
  ".m4a",
  ".wav",
  ".webm",
  ".ogg",
  ".flac",
];

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

export default function NewMeetingModal({
  isOpen,
  onClose,
  onSuccess,
}: NewMeetingModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isOpen) {
      setFile(null);
      setTitle("");
      setError(null);
      setIsUploading(false);
      setIsDragging(false);
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !isUploading) {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isUploading, onClose]);

  if (!isOpen) return null;

  const validateAndSetFile = (selectedFile: File) => {
    setError(null);
    const extension = "." + selectedFile.name.split(".").pop()?.toLowerCase();

    if (!ALLOWED_EXTENSIONS.includes(extension)) {
      setError(
        `Unsupported format: ${extension}. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`,
      );
      return;
    }

    setFile(selectedFile);
    if (!title.trim()) {
      const defaultTitle = selectedFile.name.replace(/\.[^/.]+$/, "");
      setTitle(defaultTitle);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Please select an audio or video file.");
      return;
    }

    try {
      setIsUploading(true);
      setError(null);

      const result = await uploadMeeting(file, title.trim() || undefined);
      onSuccess(result.id);
    } catch (err: unknown) {
      console.error("Upload error:", err);
      const errorMessage =
        err instanceof Error
          ? err.message
          : "Failed to upload recording. Check server connection.";
      setError(errorMessage);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-container"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div className="modal-title-group">
            <div className="modal-icon">
              <Sparkles size={18} />
            </div>
            <div>
              <h2>New Meeting</h2>
              <p>Upload a recording to transcribe, diarize, and summarize.</p>
            </div>
          </div>

          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            disabled={isUploading}
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          {error && (
            <div className="modal-alert error">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <div
            className={`dropzone ${isDragging ? "active" : ""} ${file ? "has-file" : ""}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={ALLOWED_EXTENSIONS.join(",")}
              onChange={handleFileChange}
              style={{ display: "none" }}
            />

            {file ? (
              <div className="selected-file-info">
                <div className="selected-file-icon">
                  <FileAudio size={28} />
                </div>
                <div className="selected-file-details">
                  <strong>{file.name}</strong>
                  <span>{formatBytes(file.size)}</span>
                </div>
                <button
                  type="button"
                  className="change-file-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                    if (fileInputRef.current) fileInputRef.current.value = "";
                  }}
                  disabled={isUploading}
                >
                  Change
                </button>
              </div>
            ) : (
              <div className="dropzone-content">
                <div className="dropzone-icon">
                  <UploadCloud size={30} />
                </div>
                <div className="dropzone-text">
                  <strong>Drop your audio or video file here</strong>
                  <span>or click to browse from your device</span>
                </div>
                <div className="dropzone-formats">
                  Supports MP3, M4A, WAV, MP4, WEBM, OGG, FLAC
                </div>
              </div>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="meeting-title">Meeting Title</label>
            <input
              id="meeting-title"
              type="text"
              placeholder="e.g., Q3 Product Strategy Review"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={isUploading}
            />
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="secondary-btn"
              onClick={onClose}
              disabled={isUploading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="primary-btn-submit"
              disabled={isUploading || !file}
            >
              {isUploading ? (
                <>
                  <LoaderCircle className="spinner" size={16} />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <Sparkles size={16} />
                  <span>Start AI Pipeline</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
