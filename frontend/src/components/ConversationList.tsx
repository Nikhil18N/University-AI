import type { ConversationSummary } from "../services/api";
import "./ConversationList.css";

interface Props {
  conversations: ConversationSummary[];
  activeId?: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}

export default function ConversationList({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
}: Props) {
  return (
    <div className="conversation-list">
      <div className="sidebar-header">
        <h2 className="sidebar-title">💬 Chats</h2>
        <button className="new-chat-btn" onClick={onNew} aria-label="New chat">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>
      </div>

      <div className="conversation-items">
        {conversations.length === 0 && (
          <p className="no-chats">No conversations yet. Start chatting!</p>
        )}
        {conversations.map((conv) => (
          <div
            key={conv.id}
            className={`conversation-item ${conv.id === activeId ? "active" : ""}`}
            onClick={() => onSelect(conv.id)}
          >
            <span className="conv-title">{conv.title}</span>
            <button
              className="delete-btn"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(conv.id);
              }}
              aria-label="Delete conversation"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
