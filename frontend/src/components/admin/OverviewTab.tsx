import { useState, type FormEvent } from "react";
import { promoteExemplar, type AdminStats } from "../../services/api";

interface OverviewTabProps {
  stats: AdminStats;
  adminKey: string;
}

export function OverviewTab({ stats, adminKey }: OverviewTabProps) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [saving, setSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  async function handleAddExemplar(e: FormEvent) {
    e.preventDefault();
    const q = question.trim();
    const a = answer.trim();
    if (!q || !a) return;
    setSaving(true);
    setStatusMsg(null);
    try {
      const res = await promoteExemplar(adminKey, {
        message_id: crypto.randomUUID(),
        question: q,
        answer: a,
      });
      setStatusMsg({ type: "ok", text: res.message });
      setQuestion("");
      setAnswer("");
    } catch (err) {
      setStatusMsg({
        type: "err",
        text: err instanceof Error ? err.message : "Failed to save approved Q&A",
      });
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className="tab-pane-container">
      <div className="admin-metrics-grid">
        <div className="metric-box">
          <span className="metric-title">Total Student Conversations</span>
          <span className="metric-num num-indigo">{stats.total_conversations}</span>
        </div>
        <div className="metric-box">
          <span className="metric-title">Total Messages Exchanged</span>
          <span className="metric-num">{stats.total_messages}</span>
        </div>
        <div className="metric-box">
          <span className="metric-title">Active Knowledge Documents</span>
          <span className="metric-num">{stats.active_documents}</span>
        </div>
        <div className="metric-box">
          <span className="metric-title">Total Knowledge Base Docs</span>
          <span className="metric-num">{stats.total_documents}</span>
        </div>
        <div className="metric-box">
          <span className="metric-title">Positive Feedback 👍</span>
          <span className="metric-num num-green">{stats.positive_feedback}</span>
        </div>
        <div className="metric-box">
          <span className="metric-title">Negative Feedback 👎</span>
          <span className="metric-num num-red">{stats.negative_feedback}</span>
        </div>
      </div>

      <div className="admin-card-panel">
        <h3 className="panel-headline">Model Improvement & AI Training Guide</h3>
        <p className="panel-subtext">
          Follow these steps to continuously align and fine-tune your SRU Companion:
        </p>
        <ol className="guide-steps-list">
          <li>
            <strong>Audit Real Student Queries:</strong> Go to the <strong>Student Chats</strong> tab to review the exact queries students are asking and identify knowledge gaps.
          </li>
          <li>
            <strong>One-Click Few-Shot Learning:</strong> Click <strong>"⭐ Promote to Verified Exemplar"</strong> on any verified high-quality response to immediately embed it in ChromaDB's <code>verified_exemplars</code> collection.
          </li>
          <li>
            <strong>Bulk Export for Fine-Tuning:</strong> Click <strong>"Export All Chats (.md)"</strong> to export all student interactions into a single clean training document ready for evaluation benchmarks or fine-tuning models like Gemini, Llama, or Mistral.
          </li>
        </ol>
      </div>

      <div className="admin-card-panel">
        <h3 className="panel-headline">Add Approved Q&amp;A (Verified Exemplar)</h3>
        <p className="panel-subtext">
          Save an ideal leadership-approved response for a specific student question so the AI mirrors its tone, structure, and framing.
        </p>
        <form onSubmit={handleAddExemplar} style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "10px" }}>
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Student question (e.g. Why should I choose SR University?)"
            required
            style={{ padding: "8px 10px", borderRadius: "6px", border: "1px solid #d1d5db" }}
          />
          <textarea
            rows={4}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Approved response..."
            required
            style={{ padding: "8px 10px", borderRadius: "6px", border: "1px solid #d1d5db", resize: "vertical" }}
          />
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <button type="submit" className="btn-exemplar-promote" disabled={saving || !question.trim() || !answer.trim()}>
              {saving ? "Saving..." : "⭐ Save Approved Q&A"}
            </button>
            {statusMsg && (
              <span style={{ fontSize: "0.875rem", color: statusMsg.type === "ok" ? "#15803d" : "#b91c1c" }}>
                {statusMsg.text}
              </span>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
