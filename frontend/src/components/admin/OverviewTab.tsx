import type { AdminStats } from "../../services/api";

interface OverviewTabProps {
  stats: AdminStats;
}

export function OverviewTab({ stats }: OverviewTabProps) {
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
    </div>
  );
}
