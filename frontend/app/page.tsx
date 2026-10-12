"use client";

import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";

type UploadResult = {
  project_id: string;
  filename: string;
  files_found: number;
  files: string[];
};

const MAX_UPLOAD_SIZE = 50 * 1024 * 1024;
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isApiConnected, setIsApiConnected] = useState<boolean | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    fetch(`${API_URL}/health`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Health check failed");
        setIsApiConnected(true);
      })
      .catch((healthError: unknown) => {
        if (healthError instanceof DOMException && healthError.name === "AbortError") return;
        setIsApiConnected(false);
      });

    return () => controller.abort();
  }, []);

  function chooseFile(file?: File) {
    setError("");
    setResult(null);

    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".zip")) {
      setSelectedFile(null);
      setError("Choose a ZIP archive to upload.");
      return;
    }
    if (file.size > MAX_UPLOAD_SIZE) {
      setSelectedFile(null);
      setError("That archive is larger than the 50 MB limit.");
      return;
    }
    setSelectedFile(file);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    chooseFile(event.target.files?.[0]);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    chooseFile(event.dataTransfer.files[0]);
  }

  async function uploadProject() {
    if (!selectedFile) return;

    setIsUploading(true);
    setError("");
    setResult(null);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch(`${API_URL}/projects/upload`, {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.detail ?? "The project could not be uploaded.");
      }

      setResult(payload);
    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Could not connect to the API. Is the backend running?",
      );
    } finally {
      setIsUploading(false);
    }
  }

  function clearSelection() {
    setSelectedFile(null);
    setResult(null);
    setError("");
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <main className="workspace-shell">
      <header className="topbar">
        <div className="brand-mark">CA</div>
        <div>
          <p className="eyebrow">Codebase AI</p>
          <p className="topbar-subtitle">Project workspace</p>
        </div>
        <span className={`api-status${isApiConnected === false ? " is-offline" : ""}`}>
          <span className="api-status-dot" />
          API · {isApiConnected === null ? "checking" : isApiConnected ? "connected" : "offline"}
        </span>
      </header>

      <section className="content-grid">
        <div className="intro-copy">
          <p className="eyebrow accent">Start with a project</p>
          <h1>Upload a codebase and make it searchable.</h1>
          <p className="lede">
            Bring a ZIP archive of your project. Codebase AI will unpack the
            supported files and prepare them for the workspace.
          </p>
          <div className="feature-list">
            <span><b>01</b> ZIP archives up to 50 MB</span>
            <span><b>02</b> Common source and documentation files</span>
            <span><b>03</b> Private project workspace per upload</span>
          </div>
        </div>

        <div className="upload-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">New project</p>
              <h2>Project archive</h2>
            </div>
            <span className="step-count">1 / 1</span>
          </div>

          <div
            className={`drop-zone${isDragging ? " is-dragging" : ""}${selectedFile ? " has-file" : ""}`}
            onClick={() => inputRef.current?.click()}
            onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            role="button"
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
            }}
          >
            <input ref={inputRef} type="file" accept=".zip,application/zip" onChange={handleFileChange} hidden />
            <div className="upload-icon">↑</div>
            {selectedFile ? (
              <>
                <strong>{selectedFile.name}</strong>
                <span>{(selectedFile.size / 1024 / 1024).toFixed(2)} MB ready to upload</span>
              </>
            ) : (
              <>
                <strong>Drop your ZIP here</strong>
                <span>or click to browse your files</span>
              </>
            )}
          </div>

          {error && <p className="message error-message">{error}</p>}
          {result && (
            <div className="result-box">
              <div>
                <span className="success-dot" />
                <strong>Project uploaded</strong>
              </div>
              <p>{result.files_found} supported files found in your project.</p>
              <code>{result.project_id}</code>
            </div>
          )}

          <div className="panel-actions">
            {selectedFile && <button className="clear-button" type="button" onClick={clearSelection}>Clear</button>}
            <button className="upload-button" type="button" disabled={!selectedFile || isUploading} onClick={result ? clearSelection : uploadProject}>
              {isUploading ? "Uploading..." : result ? "Upload another" : "Upload project"}
            </button>
          </div>
          <p className="panel-note">Your archive stays on the local API server.</p>
        </div>
      </section>
    </main>
  );
}
