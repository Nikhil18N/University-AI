import React, { useState, useEffect } from "react";
import {
  fetchAdminStats,
  fetchAdminDocuments,
  uploadDocument,
  deactivateDocument,
  fetchAdminFeedback,
  type AdminStats,
  type DocumentItem,
  type FeedbackItem,
} from "../services/api";
import "./AdminPage.css";

interface Props {
  onBackToChat: () => void;
}

export default function AdminPage({ onBackToChat }: Props) {
  const [adminKey, setAdminKey] = useState<string>(
    () => sessionStorage.getItem("university_ai_admin_key") || ""
  );
  const [keyInput, setKeyInput] = useState<string>("");
  const [activeTab, setActiveTab] = useState<"overview" | "documents" | "feedback">("overview");

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Upload Form state
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadType, setUploadType] = useState("policy");
  const [uploadDept, setUploadDept] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  const loadData = async (key: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const [statsData, docsData, feedbackData] = await Promise.all([
        fetchAdminStats(key),
        fetchAdminDocuments(key),
        fetchAdminFeedback(key),
      ]);
      setStats(statsData);
      setDocuments(docsData.documents);
      setFeedback(feedbackData.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load admin data");
      setAdminKey("");
      sessionStorage.removeItem("university_ai_admin_key");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (adminKey) {
      loadData(adminKey);
    }
  }, [adminKey]);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyInput.trim()) return;
    sessionStorage.setItem("university_ai_admin_key", keyInput.trim());
    setAdminKey(keyInput.trim());
  };

  const handleLogout = () => {
    sessionStorage.removeItem("university_ai_admin_key");
    setAdminKey("");
    setStats(null);
    setDocuments([]);
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !uploadTitle.trim()) {
      alert("Please provide a title and select a document file.");
      return;
    }

    setIsUploading(true);
    setUploadSuccess(null);
    try {
      const formData = new FormData();
      formData.append("file", uploadFile);
      formData.append("title", uploadTitle.trim());
      formData.append("document_type", uploadType);
      if (uploadDept.trim()) formData.append("department", uploadDept.trim());

      await uploadDocument(adminKey, formData);
      setUploadSuccess(`Successfully ingested "${uploadTitle}"!`);
      setUploadTitle("");
      setUploadDept("");
      setUploadFile(null);
      // Reload documents and stats
      loadData(adminKey);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeactivate = async (docId: string) => {
    if (!confirm("Are you sure you want to deactivate this document?")) return;
    try {
      await deactivateDocument(adminKey, docId);
      loadData(adminKey);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Deactivation failed");
    }
  };

  if (!adminKey) {
    return (
      <div className="admin-container">
        <header className="admin-header">
          <div className="admin-logo">
            <span>🏛️</span> University AI Companion
            <span className="admin-logo-badge">Admin</span>
          </div>
          <button className="btn-secondary" onClick={onBackToChat}>
            ← Back to Student Chat
          </button>
        </header>

        <div className="admin-auth-box">
          <h2>Admin Authentication</h2>
          <p>Enter the admin API key to manage documents, view stats, and inspect student feedback.</p>
          <form onSubmit={handleLogin}>
            <input
              type="password"
              placeholder="Enter Admin API Key"
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              required
            />
            {error && <div style={{ color: "#f87171", marginBottom: "16px", fontSize: "0.85rem" }}>{error}</div>}
            <button type="submit" className="btn-primary" style={{ width: "100%" }}>
              Access Dashboard
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-container">
      <header className="admin-header">
        <div className="admin-logo">
          <span>🏛️</span> University AI Companion
          <span className="admin-logo-badge">Admin Console</span>
        </div>
        <div className="admin-nav-actions">
          <button className="btn-secondary" onClick={onBackToChat}>
            ← Student Chat
          </button>
          <button className="btn-secondary" onClick={handleLogout}>
            Exit Admin
          </button>
        </div>
      </header>

      <div className="admin-body">
        <div className="admin-tabs">
          <button
            className={`admin-tab ${activeTab === "overview" ? "active" : ""}`}
            onClick={() => setActiveTab("overview")}
          >
            Overview
          </button>
          <button
            className={`admin-tab ${activeTab === "documents" ? "active" : ""}`}
            onClick={() => setActiveTab("documents")}
          >
            Documents ({documents.length})
          </button>
          <button
            className={`admin-tab ${activeTab === "feedback" ? "active" : ""}`}
            onClick={() => setActiveTab("feedback")}
          >
            Feedback ({feedback.length})
          </button>
        </div>

        {isLoading ? (
          <div style={{ textAlign: "center", padding: "48px", color: "var(--text-2)" }}>Loading dashboard data...</div>
        ) : (
          <>
            {activeTab === "overview" && stats && (
              <div>
                <div className="stats-grid">
                  <div className="stat-card">
                    <div className="stat-label">Active Documents</div>
                    <div className="stat-value">{stats.active_documents}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Total Documents</div>
                    <div className="stat-value">{stats.total_documents}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Total Conversations</div>
                    <div className="stat-value">{stats.total_conversations}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Total Messages</div>
                    <div className="stat-value">{stats.total_messages}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Positive Feedback 👍</div>
                    <div className="stat-value" style={{ color: "#4ade80" }}>{stats.positive_feedback}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Negative Feedback 👎</div>
                    <div className="stat-value" style={{ color: "#f87171" }}>{stats.negative_feedback}</div>
                  </div>
                </div>

                <div className="admin-panel">
                  <div className="admin-panel-title">System Status</div>
                  <p style={{ color: "var(--text-2)", fontSize: "0.9rem", lineHeight: "1.6" }}>
                    The RAG pipeline is configured to ingest PDF, DOCX, TXT, and Markdown files, automatically compute SHA-256 checksums, chunk content with semantic overlap, and generate embeddings into ChromaDB.
                  </p>
                </div>
              </div>
            )}

            {activeTab === "documents" && (
              <div>
                <div className="admin-panel">
                  <div className="admin-panel-title">Upload & Ingest Document</div>
                  {uploadSuccess && (
                    <div style={{ background: "rgba(34, 197, 94, 0.15)", color: "#4ade80", padding: "10px 14px", borderRadius: "8px", marginBottom: "16px", fontSize: "0.85rem" }}>
                      {uploadSuccess}
                    </div>
                  )}
                  <form onSubmit={handleUpload}>
                    <div className="form-grid">
                      <div className="form-group">
                        <label>Document Title *</label>
                        <input
                          type="text"
                          placeholder="e.g. Examination Regulations 2026"
                          value={uploadTitle}
                          onChange={(e) => setUploadTitle(e.target.value)}
                          required
                        />
                      </div>
                      <div className="form-group">
                        <label>Document Type *</label>
                        <select value={uploadType} onChange={(e) => setUploadType(e.target.value)}>
                          <option value="policy">Policy</option>
                          <option value="calendar">Academic Calendar</option>
                          <option value="regulation">Regulations / Rules</option>
                          <option value="syllabus">Syllabus / Course</option>
                          <option value="circular">Notice / Circular</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label>Department</label>
                        <input
                          type="text"
                          placeholder="e.g. Office of Academic Affairs"
                          value={uploadDept}
                          onChange={(e) => setUploadDept(e.target.value)}
                        />
                      </div>
                      <div className="form-group">
                        <label>File (PDF, DOCX, TXT, MD) *</label>
                        <input
                          type="file"
                          accept=".pdf,.docx,.txt,.md"
                          onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                          required
                        />
                      </div>
                    </div>
                    <button type="submit" className="btn-primary" disabled={isUploading}>
                      {isUploading ? "Extracting & Embedding..." : "Ingest Document"}
                    </button>
                  </form>
                </div>

                <div className="admin-panel">
                  <div className="admin-panel-title">Knowledge Base Documents</div>
                  {documents.length === 0 ? (
                    <p style={{ color: "var(--text-2)" }}>No documents indexed yet.</p>
                  ) : (
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>Title</th>
                          <th>Type</th>
                          <th>Department</th>
                          <th>Status</th>
                          <th>Date</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {documents.map((doc) => (
                          <tr key={doc.id}>
                            <td style={{ fontWeight: 500 }}>{doc.title}</td>
                            <td>{doc.document_type}</td>
                            <td>{doc.department || "—"}</td>
                            <td>
                              <span className={`badge-${doc.status}`}>
                                {doc.status}
                              </span>
                            </td>
                            <td>{new Date(doc.created_at).toLocaleDateString()}</td>
                            <td>
                              {doc.status === "active" && (
                                <button
                                  className="btn-danger"
                                  onClick={() => handleDeactivate(doc.id)}
                                >
                                  Deactivate
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            )}

            {activeTab === "feedback" && (
              <div className="admin-panel">
                <div className="admin-panel-title">Student & User Feedback</div>
                {feedback.length === 0 ? (
                  <p style={{ color: "var(--text-2)" }}>No feedback submitted yet.</p>
                ) : (
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>Rating</th>
                        <th>User Question</th>
                        <th>AI Response</th>
                        <th>Comment</th>
                        <th>Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {feedback.map((f) => (
                        <tr key={f.id}>
                          <td style={{ whiteSpace: "nowrap" }}>
                            {f.rating === 1 ? (
                              <span style={{ color: "#4ade80", fontWeight: 600 }}>👍 Helpful</span>
                            ) : (
                              <span style={{ color: "#f87171", fontWeight: 600 }}>👎 Inaccurate</span>
                            )}
                          </td>
                          <td style={{ maxWidth: "240px", wordBreak: "break-word" }}>
                            {f.question || <span style={{ color: "var(--text-2)" }}>—</span>}
                          </td>
                          <td style={{ maxWidth: "320px", wordBreak: "break-word", fontSize: "0.85rem" }}>
                            {f.answer ? (
                              <span>{f.answer.length > 150 ? `${f.answer.slice(0, 150)}...` : f.answer}</span>
                            ) : (
                              <span style={{ color: "var(--text-2)" }}>—</span>
                            )}
                          </td>
                          <td>{f.comment || <span style={{ color: "var(--text-2)" }}>—</span>}</td>
                          <td style={{ whiteSpace: "nowrap" }}>{new Date(f.created_at).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
