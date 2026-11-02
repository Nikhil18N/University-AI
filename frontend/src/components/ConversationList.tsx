import { useState } from "react";
import type { ConversationSummary } from "../services/api";
import "./ConversationList.css";

interface Props {
  conversations: ConversationSummary[];
  activeId?: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onCloseMobile?: () => void;
  onTriggerPrompt?: (prompt: string) => void;
}

const SRU_PORTALS = [
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10" />
        <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
      </svg>
    ),
    title: "Admissions 2026",
    prompt: "I want admission - start the admission wizard",
  },
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="2" y="4" width="20" height="16" rx="2" />
        <line x1="12" y1="8" x2="12" y2="16" />
        <line x1="8" y1="12" x2="16" y2="12" />
      </svg>
    ),
    title: "Fees & Scholarships",
    prompt: "What is the complete fee structure and merit scholarship for B.Tech?",
  },
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
        <polyline points="9 22 9 12 15 12 15 22" />
      </svg>
    ),
    title: "Hostel Rules & Curfew",
    prompt: "What are the hostel room options, curfew timings, and mess rules?",
  },
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <line x1="18" y1="20" x2="18" y2="10" />
        <line x1="12" y1="20" x2="12" y2="4" />
        <line x1="6" y1="20" x2="6" y2="14" />
      </svg>
    ),
    title: "Placement Records",
    prompt: "Tell me about SR University placement records and top recruiters",
  },
];

export default function ConversationList({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onCloseMobile,
  onTriggerPrompt,
}: Props) {
  const [searchQuery, setSearchQuery] = useState("");
  const [showSearchInput, setShowSearchInput] = useState(false);

  const filteredConvs = conversations.filter((c) =>
    (c.title || "").toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="chatgpt-sidebar">
      {/* Top Header (Matching Image 2: Brand title on left, Search icon on right) */}
      <div className="sidebar-top-bar">
        <div className="sidebar-brand-title-box">
          <span className="sidebar-brand-title">SRU Buddy</span>
          <span className="brand-beta-pill">Beta</span>
        </div>

        <button
          className="sidebar-search-circle-btn"
          onClick={() => setShowSearchInput(!showSearchInput)}
          aria-label="Search chats"
          title="Search chats"
        >
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </button>
      </div>

      {/* Inline Search Input */}
      {showSearchInput && (
        <div className="sidebar-search-box">
          <input
            type="text"
            className="sidebar-search-input"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            autoFocus
          />
        </div>
      )}

      {/* Quick Portals Navigation (Matching Image 2 top icons list) */}
      <div className="sidebar-portals-list">
        {SRU_PORTALS.map((portal, idx) => (
          <button
            key={idx}
            className="sidebar-portal-btn"
            onClick={() => {
              if (onTriggerPrompt) {
                onTriggerPrompt(portal.prompt);
              }
              if (onCloseMobile) onCloseMobile();
            }}
            type="button"
          >
            <span className="portal-icon">{portal.icon}</span>
            <span className="portal-title">{portal.title}</span>
          </button>
        ))}
      </div>

      {/* Section Divider / Label (Matching Image 2 "Pinned" / "Chats") */}
      <div className="sidebar-section-header">
        <span>Recent Chats</span>
      </div>

      {/* Conversations Scrollable List */}
      <div className="sidebar-conv-scroll-list">
        {filteredConvs.length === 0 ? (
          <div className="sidebar-no-chats">
            <p>No conversations yet</p>
          </div>
        ) : (
          filteredConvs.map((conv) => {
            const isActive = conv.id === activeId;
            return (
              <div
                key={conv.id}
                className={`sidebar-chat-item ${isActive ? "active" : ""}`}
                onClick={() => {
                  onSelect(conv.id);
                  if (onCloseMobile) onCloseMobile();
                }}
                role="button"
                tabIndex={0}
              >
                {/* Speech bubble outline icon (Matching Image 2) */}
                <svg
                  className="chat-bubble-outline-icon"
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>

                <span className="chat-title-text" title={conv.title}>
                  {conv.title || "Untitled Chat"}
                </span>

                <button
                  className="chat-item-delete-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(conv.id);
                  }}
                  aria-label="Delete chat"
                  title="Delete"
                >
                  ✕
                </button>
              </div>
            );
          })
        )}
      </div>

      {/* Bottom Footer (Matching Image 2: Blue New Chat pill on left, Avatar circle on right) */}
      <div className="sidebar-bottom-bar">
        <button
          className="sidebar-blue-new-chat-pill"
          onClick={() => {
            onNew();
            if (onCloseMobile) onCloseMobile();
          }}
          type="button"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
          </svg>
          <span>Chat</span>
        </button>

        <a
          href="https://sru.edu.in"
          target="_blank"
          rel="noopener noreferrer"
          className="sidebar-avatar-circle-btn"
          title="SR University (sru.edu.in)"
        >
          <span className="avatar-initials">SRU</span>
        </a>
      </div>
    </div>
  );
}
