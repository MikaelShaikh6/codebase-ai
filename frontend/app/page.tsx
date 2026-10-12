"use client";

import { ChangeEvent, DragEvent, useCallback, useEffect, useRef, useState } from "react";

type ProjectStatus = "uploaded" | "processing" | "ready" | "failed";
type Project = {
  project_id: string;
  filename: string;
  status: ProjectStatus;
  files_found: number;
  error: string | null;
  created_at: string;
  updated_at: string;
};
type UploadResult = Pick<Project, "project_id" | "filename" | "status" | "files_found"> & { files: string[] };
type Citation = { file_path: string; start_line: number; end_line: number };
type ChatMessage = { question: string; answer: string; citations: Citation[] };
type AuthResponse = { access_token: string; token_type: string };

const MAX_UPLOAD_SIZE = 50 * 1024 * 1024;
const CHAT_TIMEOUT_MS = 150_000;
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("codebase_ai_token") : null;
  const headers = new Headers(options?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail ?? "The API request failed.");
  return payload as T;
}

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [result, setResult] = useState<UploadResult | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [error, setError] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isChatting, setIsChatting] = useState(false);
  const [isApiConnected, setIsApiConnected] = useState<boolean | null>(null);
  const [token, setToken] = useState(() => (
    typeof window !== "undefined" ? window.localStorage.getItem("codebase_ai_token") ?? "" : ""
  ));
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  async function authenticate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsAuthenticating(true);
    setError("");
    try {
      const response = await apiRequest<AuthResponse>(`/auth/${authMode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      window.localStorage.setItem("codebase_ai_token", response.access_token);
      setToken(response.access_token);
      setPassword("");
    } catch (authError) {
      setError(authError instanceof Error ? authError.message : "Authentication failed.");
    } finally {
      setIsAuthenticating(false);
    }
  }

  function signOut() {
    window.localStorage.removeItem("codebase_ai_token");
    setToken("");
    setProjects([]);
    setSelectedProjectId("");
    setMessages([]);
  }

  const loadProjects = useCallback(async () => {
    try {
      setProjects(await apiRequest<Project[]>("/projects"));
      setIsApiConnected(true);
    } catch {
      setIsApiConnected(false);
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    apiRequest<Project[]>("/projects")
      .then((items) => {
        if (!controller.signal.aborted) {
          setProjects(items);
          setIsApiConnected(true);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setIsApiConnected(false);
      });
    fetch(`${API_URL}/health`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Health check failed");
        setIsApiConnected(true);
      })
      .catch((healthError: unknown) => {
        if (!(healthError instanceof DOMException && healthError.name === "AbortError")) setIsApiConnected(false);
      });
    return () => controller.abort();
  }, [loadProjects, token]);

  const selectedProject = projects.find((project) => project.project_id === selectedProjectId);

  useEffect(() => {
    if (!selectedProjectId || selectedProject?.status === "ready" || selectedProject?.status === "failed") return;
    const poll = window.setInterval(async () => {
      try {
        const project = await apiRequest<Project>(`/projects/${selectedProjectId}/status`);
        setProjects((current) => current.map((item) => item.project_id === project.project_id ? project : item));
      } catch {
        setError("Could not refresh project status.");
      }
    }, 2000);
    return () => window.clearInterval(poll);
  }, [selectedProjectId, selectedProject?.status]);

  function chooseFile(file?: File) {
    setError("");
    setResult(null);
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".zip")) return setError("Choose a ZIP archive to upload.");
    if (file.size > MAX_UPLOAD_SIZE) return setError("That archive is larger than the 50 MB limit.");
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
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      const payload = await apiRequest<UploadResult>("/projects/upload", { method: "POST", body: formData });
      setResult(payload);
      setSelectedProjectId(payload.project_id);
      await loadProjects();
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Could not upload the project.");
    } finally {
      setIsUploading(false);
    }
  }

  async function askQuestion(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProjectId || !question.trim()) return;
    setIsChatting(true);
    setError("");
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);
    try {
      const response = await apiRequest<{ answer: string; citations: Citation[] }>(
        `/projects/${selectedProjectId}/chat`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question }),
          signal: controller.signal,
        },
      );
      setMessages((current) => [...current, { question, ...response }]);
      setQuestion("");
    } catch (chatError) {
      if (chatError instanceof DOMException && chatError.name === "AbortError") {
        setError("The answer took too long. Check that Ollama is reachable, then try again.");
      } else {
        setError(chatError instanceof Error ? chatError.message : "Could not answer that question.");
      }
    } finally {
      window.clearTimeout(timeout);
      setIsChatting(false);
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
        <div><p className="eyebrow">Codebase AI</p><p className="topbar-subtitle">Project workspace</p></div>
        <span className={`api-status${isApiConnected === false ? " is-offline" : ""}`}><span className="api-status-dot" /> API · {isApiConnected === null ? "checking" : isApiConnected ? "connected" : "offline"}</span>
        {token && <button className="clear-button" type="button" onClick={signOut}>Sign out</button>}
      </header>

      {!token && <section className="upload-panel auth-panel"><div className="panel-heading"><div><p className="eyebrow">Private workspace</p><h2>{authMode === "login" ? "Sign in" : "Create account"}</h2></div></div><form className="auth-form" onSubmit={authenticate}><input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email address" /><input type="password" required minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password (8+ characters)" /><button className="upload-button" disabled={isAuthenticating}>{isAuthenticating ? "Please wait..." : authMode === "login" ? "Sign in" : "Register"}</button></form><button className="clear-button" type="button" onClick={() => setAuthMode(authMode === "login" ? "register" : "login")}>{authMode === "login" ? "Need an account?" : "Already have an account?"}</button>{error && <p className="message error-message">{error}</p>}</section>}

      {token &&
      <section className="workspace-grid">
        <aside className="project-sidebar">
          <div className="panel-heading"><div><p className="eyebrow">Workspace</p><h2>Projects</h2></div><span className="step-count">{projects.length}</span></div>
          <div className="project-list">
            {projects.length === 0 && <p className="empty-copy">Upload a project to begin.</p>}
            {projects.map((project) => (
              <button className={`project-item${project.project_id === selectedProjectId ? " is-selected" : ""}`} key={project.project_id} onClick={() => { setSelectedProjectId(project.project_id); setMessages([]); }}>
                <strong>{project.filename}</strong><span><i className={`status-dot status-${project.status}`} /> {project.status} · {project.files_found} files</span>
              </button>
            ))}
          </div>
        </aside>

        <section className="workspace-main">
          <div className="intro-copy"><p className="eyebrow accent">Understand your codebase</p><h1>Ask questions grounded in your project.</h1><p className="lede">Upload a ZIP and explore the code with source-backed answers.</p></div>

          {!selectedProject && (
            <div className="upload-panel">
              <div className="panel-heading"><div><p className="eyebrow">New project</p><h2>Project archive</h2></div><span className="step-count">1 / 1</span></div>
              <div className={`drop-zone${isDragging ? " is-dragging" : ""}${selectedFile ? " has-file" : ""}`} onClick={() => inputRef.current?.click()} onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setIsDragging(false)} onDrop={handleDrop} role="button" tabIndex={0} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") inputRef.current?.click(); }}>
                <input ref={inputRef} type="file" accept=".zip,application/zip" onChange={handleFileChange} hidden />
                <div className="upload-icon">↑</div>
                {selectedFile ? <><strong>{selectedFile.name}</strong><span>{(selectedFile.size / 1024 / 1024).toFixed(2)} MB ready to upload</span></> : <><strong>Drop your ZIP here</strong><span>or click to browse your files</span></>}
              </div>
              {result && <div className="result-box"><strong>Project uploaded</strong><p>Indexing has started. You can watch its status in the sidebar.</p></div>}
              <div className="panel-actions">{selectedFile && <button className="clear-button" type="button" onClick={clearSelection}>Clear</button>}<button className="upload-button" type="button" disabled={!selectedFile || isUploading} onClick={uploadProject}>{isUploading ? "Uploading..." : "Upload project"}</button></div>
            </div>
          )}

          {selectedProject && (
            <div className="chat-panel">
              <div className="panel-heading"><div><p className="eyebrow">Active project</p><h2>{selectedProject.filename}</h2></div><span className={`project-state status-${selectedProject.status}`}>{selectedProject.status}</span></div>
              {selectedProject.status !== "ready" && <div className="processing-box"><span className="spinner" /> {selectedProject.status === "failed" ? selectedProject.error : "Processing files, generating embeddings, and indexing vectors..."}</div>}
              <div className="conversation">{messages.length === 0 && selectedProject.status === "ready" && <p className="empty-copy">Ask where authentication, database connections, or any other behavior is implemented.</p>}{messages.map((message, index) => <article className="answer-card" key={`${message.question}-${index}`}><p className="question-label">You asked</p><p className="question-text">{message.question}</p><p className="answer-text">{message.answer}</p>{message.citations.length > 0 && <div className="citation-list"><p className="question-label">Sources</p>{message.citations.map((citation) => <code key={`${citation.file_path}-${citation.start_line}`}>{citation.file_path}:{citation.start_line}-{citation.end_line}</code>)}</div>}</article>)}</div>
              <form className="chat-form" onSubmit={askQuestion}><input value={question} onChange={(event) => setQuestion(event.target.value)} disabled={selectedProject.status !== "ready" || isChatting} placeholder={selectedProject.status === "ready" ? "Ask about this project..." : "Project is still processing..."} /><button className="upload-button" disabled={selectedProject.status !== "ready" || isChatting || !question.trim()}>{isChatting ? "Thinking (up to 2 min)..." : "Ask"}</button></form>
            </div>
          )}
          {error && <p className="message error-message">{error}</p>}
        </section>
      </section>}
    </main>
  );
}
