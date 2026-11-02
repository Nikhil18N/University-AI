import type { ConversationSummary } from "../services/api";
import "./ConversationList.css";

interface Props {
  conversations: ConversationSummary[];
  activeId?: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onCloseMobile?: () => void;
}

export default function ConversationList({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onCloseMobile,
}: Props) {
  return (
    <div className="conversation-list">
      {/* Brand Header */}
      <div className="sidebar-brand-header">
        <div className="sidebar-logo-group">
          <img
            src="/sru-logo.png"
            alt="SRU Logo"
            className="sidebar-sru-logo"
          />
          <div className="sidebar-brand-text">
            <span className="sidebar-brand-title">SR University</span>
            <span className="sidebar-brand-sub">Companion Portal</span>
          </div>
        </div>
        {onCloseMobile && (
          <button
            className="sidebar-close-mobile-btn"
            onClick={onCloseMobile}
            aria-label="Close sidebar"
            title="Close menu"
          >
            ✕
          </button>
        )}
      </div>

      {/* New Chat Primary Button */}
      <div className="sidebar-action-bar">
        <button className="new-chat-primary-btn" onClick={onNew} aria-label="Start new chat">
          <span className="new-chat-icon">＋</span>
          <span className="new-chat-label">New Conversation</span>
        </button>
      </div>

      {/* Chats Section Header */}
      <div className="sidebar-section-title">
        <span>Recent Chats</span>
        <span className="conv-count-badge">{conversations.length}</span>
      </div>

      {/* Conversations Scrollable List */}
      <div className="conversation-items">
        {conversations.length === 0 ? (
          <div className="no-chats">
            <span className="no-chats-icon">💬</span>
            <p>No conversations yet</p>
            <span className="no-chats-hint">Ask a question to start</span>
          </div>
        ) : (
          conversations.map((conv) => {
            const isActive = conv.id === activeId;
            return (
              <div
                key={conv.id}
                className={`conversation-item ${isActive ? "active" : ""}`}
                onClick={() => {
                  onSelect(conv.id);
                  if (onCloseMobile) onCloseMobile();
                }}
                role="button"
                tabIndex={0}
              >
                <span className="conv-icon">{isActive ? "🔹" : "💬"}</span>
                <span className="conv-title" title={conv.title}>
                  {conv.title || "Untitled Chat"}
                </span>
                <button
                  className="delete-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(conv.id);
                  }}
                  aria-label="Delete conversation"
                  title="Delete"
                >
                  ✕
                </button>
              </div>
            );
          })
        )}
      </div>

      {/* Official Quick Links Footer */}
      <div className="sidebar-footer">
        <div className="sidebar-links-label">Official University Portals</div>
        <div className="sidebar-quick-links">
          <a
            href="https://sru.edu.in"
            target="_blank"
            rel="noopener noreferrer"
            className="sidebar-link-pill"
          >
            🌐 sru.edu.in ↗
          </a>
          <a
            href="https://sru.edu.in/admissions"
            target="_blank"
            rel="noopener noreferrer"
            className="sidebar-link-pill"
          >
            📋 Admissions 2026 ↗
          </a>
          <a
            href="https://sru.edu.in/contact-us"
            target="_blank"
            rel="noopener noreferrer"
            className="sidebar-link-pill"
          >
            📞 Helpline ↗
          </a>
        </div>
        <div className="sidebar-campus-tag">
          SR University • Warangal, Telangana • NIRF Ranked
        </div>
      </div>
    </div>
  );
}
