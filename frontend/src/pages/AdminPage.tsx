import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  fetchAdminStats,
  fetchAdminDocuments,
  uploadDocument,
  deactivateDocument,
  fetchAdminFeedback,
  fetchAdminConversations,
  fetchAdminConversationDetail,
  deleteAdminConversation,
  promoteExemplar,
  downloadAllConversations,
  type AdminStats,
  type DocumentItem,
  type FeedbackItem,
  type AdminConversationItem,
  type AdminConversationDetail,
  type AdminMessageDetail,
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
  const [activeTab, setActiveTab] = useState<"overview" | "chats" | "documents" | "feedback">("chats");

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);

  // Conversations (Audit) state
  const [conversations, setConversations] = useState<AdminConversationItem[]>([]);
  const [conversationsTotal, setConversationsTotal] = useState<number>(0);
  const [selectedConvId, setSelectedConvId] = useState<string | null>(null);
  const [selectedConvDetail, setSelectedConvDetail] = useState<AdminConversationDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState<boolean>(false);
  const [chatSearch, setChatSearch] = useState<string>("");
  const [feedbackFilter, setFeedbackFilter] = useState<string>("all");
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(50);
  const [isExportingAll, setIsExportingAll] = useState<boolean>(false);

  const [promotingMessageId, setPromotingMessageId] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Upload Form state
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadType, setUploadType] = useState("policy");
  const [uploadDept, setUploadDept] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  const detailScrollRef = useRef<HTMLDivElement>(null);

  const loadData = useCallback(async (key: string, page = 1, size = 50, search = "", filter = "all") => {
    setIsLoading(true);
    setError(null);
    try {
      const [statsData, docsData, feedbackData, convsData] = await Promise.all([
        fetchAdminStats(key),
        fetchAdminDocuments(key),
        fetchAdminFeedback(key),
        fetchAdminConversations(key, {
          page,
          pageSize: size,
          search: search.trim() || undefined,
          feedbackFilter: filter === "all" ? undefined : filter,
        }),
      ]);
      setStats(statsData);
      setDocuments(docsData.documents);
      setFeedback(feedbackData.items);
      setConversations(convsData.conversations);
      setConversationsTotal(convsData.total);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load admin data");
      setAdminKey("");
      sessionStorage.removeItem("university_ai_admin_key");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadConversationsOnly = useCallback(async (key: string, page: number, size: number, search: string, filter: string) => {
    try {
      const res = await fetchAdminConversations(key, {
        page,
        pageSize: size,
        search: search.trim() || undefined,
        feedbackFilter: filter === "all" ? undefined : filter,
      });
      setConversations(res.conversations);
      setConversationsTotal(res.total);
    } catch (err: unknown) {
      console.error("Failed to reload conversations:", err);
    }
  }, []);

  useEffect(() => {
    if (adminKey) {
      loadData(adminKey, currentPage, pageSize, chatSearch, feedbackFilter);
    }
  }, [adminKey, loadData]);

  // Refetch conversations when page, pageSize, filters or search change
  useEffect(() => {
    if (adminKey && activeTab === "chats") {
      const timer = setTimeout(() => {
        loadConversationsOnly(adminKey, currentPage, pageSize, chatSearch, feedbackFilter);
      }, 250);
      return () => clearTimeout(timer);
    }
  }, [adminKey, activeTab, currentPage, pageSize, chatSearch, feedbackFilter, loadConversationsOnly]);

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
    setConversations([]);
    setSelectedConvDetail(null);
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
      loadData(adminKey, currentPage, pageSize, chatSearch, feedbackFilter);
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
      loadData(adminKey, currentPage, pageSize, chatSearch, feedbackFilter);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Deactivation failed");
    }
  };

  const handleSelectConversation = async (convId: string) => {
    setSelectedConvId(convId);
    setIsLoadingDetail(true);
    setActionNotice(null);
    try {
      const detail = await fetchAdminConversationDetail(adminKey, convId);
      setSelectedConvDetail(detail);
      // Scroll to top of transcript
      setTimeout(() => {
        if (detailScrollRef.current) {
          detailScrollRef.current.scrollTop = 0;
        }
      }, 50);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to load conversation details");
    } finally {
      setIsLoadingDetail(false);
    }
  };

  const handleDeleteConversation = async (convId: string) => {
    if (!confirm("Are you sure you want to delete this conversation log?")) return;
    try {
      await deleteAdminConversation(adminKey, convId);
      if (selectedConvId === convId) {
        setSelectedConvId(null);
        setSelectedConvDetail(null);
      }
      setActionNotice({ text: "Conversation deleted successfully.", type: "success" });
      loadConversationsOnly(adminKey, currentPage, pageSize, chatSearch, feedbackFilter);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to delete conversation");
    }
  };

  const handleExportAllMarkdown = async () => {
    setIsExportingAll(true);
    setActionNotice(null);
    try {
      await downloadAllConversations(adminKey, "markdown", {
        search: chatSearch,
        feedbackFilter,
      });
      setActionNotice({
        text: `📥 Complete dataset downloaded in Markdown (.md)! Ready to be fed into your AI model training / evaluation pipeline.`,
        type: "success",
      });
    } catch (err: unknown) {
      setActionNotice({
        text: err instanceof Error ? err.message : "Failed to export all conversations",
        type: "error",
      });
    } finally {
      setIsExportingAll(false);
    }
  };

  const handleExportSingleJson = (conv: AdminConversationDetail) => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(conv, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `chat-${conv.id.slice(0, 8)}-${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handlePrintPdf = () => {
    window.print();
  };

  const handlePromoteExemplar = async (msg: AdminMessageDetail, messages: AdminMessageDetail[]) => {
    const msgIdx = messages.findIndex((m) => m.id === msg.id);
    let question = "";
    for (let i = msgIdx - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        question = messages[i].content;
        break;
      }
    }

    if (!question) {
      alert("Could not identify the corresponding user question for this answer.");
      return;
    }

    setPromotingMessageId(msg.id);
    setActionNotice(null);
    try {
      await promoteExemplar(adminKey, {
        message_id: msg.id,
        question,
        answer: msg.content,
      });
      setActionNotice({
        text: `⭐ Exemplar Registered! "${question.slice(0, 45)}..." stored in ChromaDB verified_exemplars for dynamic few-shot learning.`,
        type: "success",
      });
    } catch (err: unknown) {
      setActionNotice({
        text: err instanceof Error ? err.message : "Failed to promote exemplar",
        type: "error",
      });
    } finally {
      setPromotingMessageId(null);
    }
  };

  const totalPages = Math.max(1, Math.ceil(conversationsTotal / pageSize));

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
          <p>Enter the admin API key to manage documents, view stats, audit student chats, and train the model.</p>
          <form onSubmit={handleLogin}>
            <input
              type="password"
              placeholder="Admin API Key (e.g. change-me-in-production)"
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
            className={`admin-tab ${activeTab === "chats" ? "active" : ""}`}
            onClick={() => setActiveTab("chats")}
          >
            💬 Student Chats ({conversationsTotal || conversations.length})
          </button>
          <button
            className={`admin-tab ${activeTab === "overview" ? "active" : ""}`}
            onClick={() => setActiveTab("overview")}
          >
            📊 Overview
          </button>
          <button
            className={`admin-tab ${activeTab === "documents" ? "active" : ""}`}
            onClick={() => setActiveTab("documents")}
          >
            📚 Knowledge Base ({documents.length})
          </button>
          <button
            className={`admin-tab ${activeTab === "feedback" ? "active" : ""}`}
            onClick={() => setActiveTab("feedback")}
          >
            ⭐ Feedback ({feedback.length})
          </button>
        </div>

        {isLoading ? (
          <div style={{ textAlign: "center", padding: "48px", color: "var(--text-2)" }}>Loading dashboard data...</div>
        ) : (
          <>
            {/* ---- USER CHATS AUDIT & MODEL IMPROVEMENT TAB ---- */}
            {activeTab === "chats" && (
              <div className="chat-audit-container">
                {/* Search & Export Toolbar */}
                <div className="chat-audit-toolbar">
                  <div className="toolbar-left">
                    <div className="chat-search-box">
                      <input
                        type="text"
                        placeholder="🔍 Search all questions, answers, topics, or session IDs..."
                        value={chatSearch}
                        onChange={(e) => {
                          setChatSearch(e.target.value);
                          setCurrentPage(1);
                        }}
                      />
                      {chatSearch && (
                        <button
                          className="btn-clear-search"
                          onClick={() => {
                            setChatSearch("");
                            setCurrentPage(1);
                          }}
                        >
                          ✕
                        </button>
                      )}
                    </div>

                    <div className="chat-filter-group">
                      <button
                        className={`filter-chip ${feedbackFilter === "all" ? "active" : ""}`}
                        onClick={() => {
                          setFeedbackFilter("all");
                          setCurrentPage(1);
                        }}
                      >
                        All Chats ({conversationsTotal})
                      </button>
                      <button
                        className={`filter-chip ${feedbackFilter === "positive" ? "active" : ""}`}
                        onClick={() => {
                          setFeedbackFilter("positive");
                          setCurrentPage(1);
                        }}
                      >
                        👍 Helpful
                      </button>
                      <button
                        className={`filter-chip ${feedbackFilter === "negative" ? "active" : ""}`}
                        onClick={() => {
                          setFeedbackFilter("negative");
                          setCurrentPage(1);
                        }}
                      >
                        👎 Inaccurate
                      </button>
                      <button
                        className={`filter-chip ${feedbackFilter === "none" ? "active" : ""}`}
                        onClick={() => {
                          setFeedbackFilter("none");
                          setCurrentPage(1);
                        }}
                      >
                        No Feedback
                      </button>
                    </div>
                  </div>

                  {/* Bulk AI Training Export Button */}
                  <div className="toolbar-right">
                    <button
                      className="btn-export-bulk"
                      disabled={isExportingAll || conversationsTotal === 0}
                      onClick={handleExportAllMarkdown}
                      title="Download ALL conversations in a single formatted Markdown file to train/fine-tune the AI model"
                    >
                      {isExportingAll ? "Generating Dataset..." : `📥 Export All Chats (.md for AI Training)`}
                    </button>
                  </div>
                </div>

                {actionNotice && (
                  <div className={`action-notice notice-${actionNotice.type}`}>
                    {actionNotice.text}
                  </div>
                )}

                <div className="chat-audit-workspace">
                  {/* Left Column: Conversation List with Pagination */}
                  <div className="chat-conv-list">
                    <div className="chat-conv-list-header">
                      <span>Conversations ({conversations.length} shown of {conversationsTotal})</span>
                      <button
                        className="btn-refresh"
                        onClick={() => loadConversationsOnly(adminKey, currentPage, pageSize, chatSearch, feedbackFilter)}
                        title="Refresh conversations list"
                      >
                        ↻ Refresh
                      </button>
                    </div>

                    {conversations.length === 0 ? (
                      <div className="chat-conv-empty">
                        <div style={{ fontSize: "2rem", marginBottom: "8px" }}>🔍</div>
                        <p>No conversations found matching filters.</p>
                      </div>
                    ) : (
                      <div className="chat-conv-scroll">
                        {conversations.map((c) => {
                          const isSelected = selectedConvId === c.id;
                          return (
                            <div
                              key={c.id}
                              className={`chat-conv-card ${isSelected ? "selected" : ""}`}
                              onClick={() => handleSelectConversation(c.id)}
                            >
                              <div className="conv-card-top">
                                <span className="conv-card-title">{c.title || "Untitled Conversation"}</span>
                                <span className="conv-card-time">
                                  {new Date(c.updated_at).toLocaleDateString([], { month: "short", day: "numeric" })}
                                </span>
                              </div>

                              {c.last_message_preview && (
                                <p className="conv-card-preview">{c.last_message_preview}</p>
                              )}

                              <div className="conv-card-footer">
                                <span className="conv-badge-msgs">{c.message_count} msgs</span>
                                <div className="conv-feedback-badges">
                                  {c.positive_feedback_count > 0 && (
                                    <span className="badge-fb-pos" title="Helpful feedback">
                                      👍 {c.positive_feedback_count}
                                    </span>
                                  )}
                                  {c.negative_feedback_count > 0 && (
                                    <span className="badge-fb-neg" title="Inaccurate feedback">
                                      👎 {c.negative_feedback_count}
                                    </span>
                                  )}
                                </div>
                                <span className="conv-session-id" title={c.session_id}>
                                  Session: {c.session_id.slice(0, 8)}...
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* Pagination Bar */}
                    <div className="chat-pagination-bar">
                      <div className="pagination-pages">
                        <button
                          className="btn-page-nav"
                          disabled={currentPage <= 1}
                          onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                        >
                          ◀
                        </button>
                        <span>
                          {currentPage} / {totalPages}
                        </span>
                        <button
                          className="btn-page-nav"
                          disabled={currentPage >= totalPages}
                          onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                        >
                          ▶
                        </button>
                      </div>

                      <div className="pagination-size">
                        <label>Show:</label>
                        <select
                          value={pageSize}
                          onChange={(e) => {
                            setPageSize(Number(e.target.value));
                            setCurrentPage(1);
                          }}
                        >
                          <option value={25}>25</option>
                          <option value={50}>50</option>
                          <option value={100}>100</option>
                          <option value={1000}>All (64+)</option>
                        </select>
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Full Conversation Transcript */}
                  <div className="chat-conv-detail">
                    {isLoadingDetail ? (
                      <div className="detail-placeholder">
                        <p>Loading full conversation thread...</p>
                      </div>
                    ) : selectedConvDetail ? (
                      <div className="transcript-wrapper">
                        {/* Transcript Header */}
                        <div className="transcript-header">
                          <div className="transcript-title-area">
                            <h3>{selectedConvDetail.title}</h3>
                            <div className="transcript-meta">
                              <span>Session ID: <code>{selectedConvDetail.session_id}</code></span>
                              <span>•</span>
                              <span>Started: {new Date(selectedConvDetail.created_at).toLocaleString()}</span>
                              <span>•</span>
                              <span>{selectedConvDetail.messages.length} Messages</span>
                            </div>
                          </div>
                          <div className="transcript-actions">
                            <button
                              className="btn-secondary"
                              onClick={handlePrintPdf}
                              title="Print conversation or save as PDF"
                            >
                              📄 Print / PDF
                            </button>
                            <button
                              className="btn-secondary"
                              onClick={() => handleExportSingleJson(selectedConvDetail)}
                              title="Export chat as JSON"
                            >
                              📥 JSON
                            </button>
                            <button
                              className="btn-danger"
                              onClick={() => handleDeleteConversation(selectedConvDetail.id)}
                              title="Delete this conversation"
                            >
                              🗑️ Delete
                            </button>
                          </div>
                        </div>

                        {/* Dialogue Thread */}
                        <div className="transcript-messages" ref={detailScrollRef}>
                          {selectedConvDetail.messages.length === 0 ? (
                            <p style={{ color: "var(--text-2)", textAlign: "center", padding: "32px" }}>
                              No messages recorded in this conversation.
                            </p>
                          ) : (
                            selectedConvDetail.messages.map((m) => {
                              const isUser = m.role === "user";
                              return (
                                <div
                                  key={m.id}
                                  className={`transcript-bubble-container ${isUser ? "user" : "assistant"}`}
                                >
                                  <div className="transcript-bubble-header">
                                    <span className="role-badge">
                                      {isUser ? "👤 Student" : "🤖 University AI"}
                                    </span>
                                    {m.model && <span className="model-badge">{m.model}</span>}
                                    <span className="msg-time">
                                      {new Date(m.created_at).toLocaleTimeString([], {
                                        hour: "2-digit",
                                        minute: "2-digit",
                                        second: "2-digit",
                                      })}
                                    </span>
                                  </div>

                                  <div className="transcript-bubble-content">
                                    {m.content}
                                  </div>

                                  {/* Sources / Citations used */}
                                  {m.sources && m.sources.length > 0 && (
                                    <div className="transcript-sources">
                                      <div className="sources-title">
                                        📚 Grounded Sources ({m.sources.length}):
                                      </div>
                                      <div className="sources-list">
                                        {m.sources.map((src, i) => (
                                          <div key={i} className="source-item">
                                            <span className="source-bullet">📄</span>
                                            <span className="source-doc-title">{src.title}</span>
                                            {src.page && <span className="source-page">(Page {src.page})</span>}
                                            {src.department && (
                                              <span className="source-dept">[{src.department}]</span>
                                            )}
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  )}

                                  {/* User Feedback */}
                                  {m.feedback && (
                                    <div
                                      className={`transcript-feedback ${
                                        m.feedback.rating === 1 ? "fb-pos" : "fb-neg"
                                      }`}
                                    >
                                      <span>
                                        {m.feedback.rating === 1 ? "👍 Student rated helpful" : "👎 Student rated inaccurate"}
                                      </span>
                                      {m.feedback.comment && (
                                        <span className="fb-comment">
                                          — "{m.feedback.comment}"
                                        </span>
                                      )}
                                    </div>
                                  )}

                                  {/* Model Improvement Action on Assistant Responses */}
                                  {!isUser && (
                                    <div className="transcript-improvement-tools">
                                      <button
                                        className="btn-promote-exemplar"
                                        disabled={promotingMessageId === m.id}
                                        onClick={() => handlePromoteExemplar(m, selectedConvDetail.messages)}
                                        title="Store this verified Q&A in ChromaDB verified_exemplars to train the AI model"
                                      >
                                        {promotingMessageId === m.id
                                          ? "Registering..."
                                          : "⭐ Promote to Verified Exemplar (Train Model)"}
                                      </button>
                                    </div>
                                  )}
                                </div>
                              );
                            })
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="detail-placeholder">
                        <div className="placeholder-icon">💬</div>
                        <h3>Select a Conversation to Inspect</h3>
                        <p>
                          Click any conversation on the left to review student questions, AI responses, grounded citations, and feedback ratings.
                        </p>
                        <p style={{ marginTop: "12px", fontSize: "0.8rem", color: "var(--text-2)" }}>
                          💡 <strong>Tip for Model Training:</strong> Click <em>"Export All Chats (.md for AI Training)"</em> in the toolbar to export all 64+ conversations in a single training file.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* ---- OVERVIEW STATS TAB ---- */}
            {activeTab === "overview" && stats && (
              <div>
                <div className="stats-grid">
                  <div className="stat-card">
                    <div className="stat-label">Total Student Conversations</div>
                    <div className="stat-value" style={{ color: "#818cf8" }}>{stats.total_conversations}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Total Messages Exchanged</div>
                    <div className="stat-value">{stats.total_messages}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Active Documents</div>
                    <div className="stat-value">{stats.active_documents}</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-label">Total Knowledge Base Docs</div>
                    <div className="stat-value">{stats.total_documents}</div>
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
                  <div className="admin-panel-title">Model Improvement & AI Training Guide</div>
                  <p style={{ color: "var(--text-2)", fontSize: "0.9rem", lineHeight: "1.6" }}>
                    To train and improve your companion model:
                  </p>
                  <ol style={{ color: "var(--text-2)", fontSize: "0.88rem", lineHeight: "1.8", paddingLeft: "20px", marginTop: "8px" }}>
                    <li>
                      <strong>Audit Real Student Queries:</strong> Go to the <strong>Student Chats</strong> tab to review the exact queries students are asking and where the model succeeded or struggled.
                    </li>
                    <li>
                      <strong>One-Click Few-Shot Learning:</strong> Click <strong>"⭐ Promote to Verified Exemplar"</strong> on any verified high-quality response to immediately embed it in ChromaDB's <code>verified_exemplars</code> collection.
                    </li>
                    <li>
                      <strong>Bulk Export for Fine-Tuning:</strong> Click <strong>"📥 Export All Chats (.md)"</strong> to export all student interactions into a single clean training document ready for evaluation benchmarks or fine-tuning models like Gemini, Llama, or Mistral.
                    </li>
                  </ol>
                </div>
              </div>
            )}

            {/* ---- DOCUMENTS TAB ---- */}
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

            {/* ---- FEEDBACK TAB ---- */}
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
