import { useState } from "react";
import { submitFeedback, type SourceReference } from "../services/api";
import { RenderCard } from "./Cards";
import MarkdownContent from "./MarkdownContent";
import { copyCleanText } from "../utils/cleanCopy";
import "./MessageBubble.css";

interface Props {
  role: "user" | "assistant";
  content: string;
  sources?: SourceReference[];
  suggestions?: string[];
  cards?: any[];
  flow?: any;
  messageId?: string;
  conversationId?: string | null;
  sessionId?: string;
  createdAt?: string;
  isStreaming?: boolean;
  onSuggestionClick?: (text: string) => void;
}

const EMOJI_REACTIONS = [
  { emoji: "👍", label: "Helpful", rating: 1 },
  { emoji: "👎", label: "Inaccurate", rating: -1 },
  { emoji: "🔥", label: "Awesome" },
  { emoji: "❤️", label: "Love" },
  { emoji: "😂", label: "Haha" },
  { emoji: "🤔", label: "Thinking" },
];

/** Format ISO timestamp string to human-friendly local time (e.g. 10:45 AM) */
function formatMessageTime(isoString?: string): string {
  if (!isoString) {
    return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) {
      return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export default function MessageBubble({
  role,
  content,
  sources: _sources,
  suggestions,
  cards,
  flow,
  messageId,
  conversationId,
  sessionId,
  createdAt,
  isStreaming,
  onSuggestionClick,
}: Props) {
  const [selectedReaction, setSelectedReaction] = useState<string | null>(null);
  const [copiedClean, setCopiedClean] = useState(false);
  const [copiedRaw, setCopiedRaw] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  // If content is very long (> 1600 characters) and not streaming, provide collapsible view
  const isLongMessage = !isStreaming && role === "assistant" && content.length > 1600;

  async function handleReaction(item: { emoji: string; label: string; rating?: number }) {
    if (selectedReaction === item.emoji) return;
    setSelectedReaction(item.emoji);

    // If rating is associated (thumbs up / down), submit to backend feedback
    if (item.rating && messageId && conversationId && sessionId && !isSubmitting) {
      setIsSubmitting(true);
      try {
        await submitFeedback({
          session_id: sessionId,
          conversation_id: conversationId,
          message_id: messageId,
          rating: item.rating,
        });
      } catch (err) {
        console.error("Failed to submit feedback:", err);
      } finally {
        setIsSubmitting(false);
      }
    }
  }

  // Clean copy strips markdown markers (for WhatsApp, Email, Docs)
  async function handleCleanCopy() {
    const success = await copyCleanText(content);
    if (success) {
      setCopiedClean(true);
      setTimeout(() => setCopiedClean(false), 2000);
    }
  }

  // Raw copy preserves markdown syntax
  function handleRawCopy() {
    navigator.clipboard.writeText(content);
    setCopiedRaw(true);
    setTimeout(() => setCopiedRaw(false), 2000);
  }

  const timeLabel = formatMessageTime(createdAt);

  return (
    <div className={`message-bubble ${role}`}>
      <div className="message-avatar">
        {role === "user" ? (
          "👤"
        ) : (
          <div className="sru-buddy-avatar" title="SRU Buddy — AI Senior">
            <span className="buddy-icon">🎓</span>
            <span className="buddy-online-indicator"></span>
          </div>
        )}
      </div>

      <div className="message-body">
        {/* Message Top Header: Identity & Timestamp */}
        <div className="message-meta-header">
          <span className="message-sender-name">
            {role === "user" ? "You" : "SRU Buddy"}
          </span>
          {timeLabel && (
            <time className="message-timestamp" title={createdAt}>
              {timeLabel}
            </time>
          )}
        </div>

        {/* Guided Flow Step Banner */}
        {role === "assistant" && flow && (
          <div className="flow-step-banner">
            <div className="flow-step-header">
              <span className="flow-icon">🧭</span>
              <span className="flow-badge">Admission Wizard</span>
              <span className="flow-step-count">
                Step {flow.step} of {flow.total_steps}
              </span>
            </div>
            <div className="flow-progress-bar">
              <div
                className="flow-progress-fill"
                style={{ width: `${(flow.step / flow.total_steps) * 100}%` }}
              ></div>
            </div>
          </div>
        )}

        {/* Message Content Bubble with Live Markdown & Streaming Caret */}
        <div
          className={`message-content ${
            isLongMessage && !isExpanded ? "message-content-collapsed" : ""
          }`}
        >
          <MarkdownContent content={content} isStreaming={isStreaming} />

          {/* Fade-out overlay when long message is collapsed */}
          {isLongMessage && !isExpanded && (
            <div className="collapsed-gradient-overlay" aria-hidden="true" />
          )}
        </div>

        {/* Expand / Collapse Toggle for Long Messages */}
        {isLongMessage && (
          <button
            type="button"
            className="expand-collapse-btn"
            onClick={() => setIsExpanded((prev) => !prev)}
          >
            {isExpanded ? "▴ Show less" : "▾ Show full answer"}
          </button>
        )}

        {/* Rich Interactive Cards (Shown once streaming is complete) */}
        {!isStreaming && role === "assistant" && cards && cards.length > 0 && (
          <div className="message-cards-container fade-in-group">
            {cards.map((card, idx) => (
              <RenderCard key={idx} card={card} />
            ))}
          </div>
        )}

        {/* Quick Suggestion Chips (Shown once streaming is complete) */}
        {!isStreaming && role === "assistant" && suggestions && suggestions.length > 0 && (
          <div className="suggestion-chips-wrapper fade-in-group">
            <span className="chips-hint">Suggested follow-ups:</span>
            <div className="suggestion-chips-list">
              {suggestions.map((suggestion, idx) => (
                <button
                  key={idx}
                  className="suggestion-chip"
                  onClick={() => onSuggestionClick?.(suggestion)}
                  title={`Ask: ${suggestion}`}
                  style={{ animationDelay: `${idx * 0.05}s` }}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Action Row: Emoji Reactions & Copy Button (Shown once streaming is complete) */}
        {!isStreaming && role === "assistant" && (
          <div className="message-action-bar fade-in-group">
            <div className="emoji-reaction-group">
              {EMOJI_REACTIONS.map((item) => (
                <button
                  key={item.emoji}
                  className={`emoji-btn ${selectedReaction === item.emoji ? "selected" : ""}`}
                  onClick={() => handleReaction(item)}
                  title={item.label}
                  type="button"
                >
                  <span className="emoji-char">{item.emoji}</span>
                </button>
              ))}
              {selectedReaction && (
                <span className="reaction-ack">
                  {selectedReaction === "👍"
                    ? "Verified!"
                    : selectedReaction === "👎"
                    ? "Feedback noted!"
                    : "Reacted!"}
                </span>
              )}
            </div>

            <div className="copy-action-group">
              <button
                className="copy-btn clean-copy-btn"
                onClick={handleCleanCopy}
                title="Copy clean plain text without Markdown markers (ideal for sharing)"
                type="button"
              >
                {copiedClean ? "✓ Clean Copied!" : "📋 Clean Copy"}
              </button>
              <button
                className="copy-btn raw-copy-btn"
                onClick={handleRawCopy}
                title="Copy raw Markdown"
                type="button"
              >
                {copiedRaw ? "✓ MD" : "MD"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
