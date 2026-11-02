import { useState } from "react";
import { submitFeedback } from "../services/api";
import { RenderCard } from "./Cards";
import MarkdownContent from "./MarkdownContent";
import { copyCleanText } from "../utils/cleanCopy";
import "./MessageBubble.css";

interface Props {
  role: "user" | "assistant";
  content: string;
  sources?: any[];
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

export default function MessageBubble({
  role,
  content,
  suggestions,
  cards,
  flow,
  messageId,
  conversationId,
  sessionId,
  isStreaming,
  onSuggestionClick,
}: Props) {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleCopy = async () => {
    const success = await copyCleanText(content);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleRating = async (rating: 1 | -1) => {
    const type = rating === 1 ? "up" : "down";
    if (feedback === type) return;
    setFeedback(type);

    if (messageId && conversationId && sessionId && !isSubmitting) {
      setIsSubmitting(true);
      try {
        await submitFeedback({
          session_id: sessionId,
          conversation_id: conversationId,
          message_id: messageId,
          rating,
        });
      } catch (err) {
        console.error("Failed to submit feedback:", err);
      } finally {
        setIsSubmitting(false);
      }
    }
  };

  return (
    <div className={`message-bubble-row ${role}`}>
      {role === "assistant" && (
        <div className="message-avatar-col">
          <div className="assistant-avatar-badge" title="SRU Buddy">
            <img src="/sru-logo.png" alt="SRU" className="assistant-avatar-img" />
          </div>
        </div>
      )}

      <div className="message-content-col">
        {/* Guided Flow Progress (if active) */}
        {role === "assistant" && flow && (
          <div className="flow-step-banner">
            <div className="flow-step-header">
              <span className="flow-badge">Admission Wizard</span>
              <span className="flow-step-count">
                Step {flow.step} of {flow.total_steps}
              </span>
            </div>
            <div className="flow-progress-bar">
              <div
                className="flow-progress-fill"
                style={{ width: `${(flow.step / flow.total_steps) * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* Message Content Bubble */}
        <div className={`message-text-bubble ${role}`}>
          <MarkdownContent content={content} isStreaming={isStreaming} />
        </div>

        {/* Rich Interactive Cards (e.g. branch comparison, fee breakdown) */}
        {!isStreaming && role === "assistant" && cards && cards.length > 0 && (
          <div className="message-cards-container">
            {cards.map((card, idx) => (
              <RenderCard key={idx} card={card} />
            ))}
          </div>
        )}

        {/* Clean Suggestion Chips */}
        {!isStreaming && role === "assistant" && suggestions && suggestions.length > 0 && (
          <div className="suggestion-chips-wrapper">
            <div className="suggestion-chips-list">
              {suggestions.map((suggestion, idx) => (
                <button
                  key={idx}
                  className="suggestion-chip"
                  onClick={() => onSuggestionClick?.(suggestion)}
                  type="button"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Sleek ChatGPT-Style Action Bar (Copy + Thumbs feedback) */}
        {!isStreaming && role === "assistant" && content.length > 0 && (
          <div className="minimal-action-bar">
            <button
              className="action-icon-btn"
              onClick={handleCopy}
              title={copied ? "Copied!" : "Copy message"}
              aria-label="Copy message"
              type="button"
            >
              {copied ? (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              ) : (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                </svg>
              )}
            </button>

            <button
              className={`action-icon-btn ${feedback === "up" ? "active" : ""}`}
              onClick={() => handleRating(1)}
              title="Good response"
              aria-label="Good response"
              type="button"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill={feedback === "up" ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2">
                <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
              </svg>
            </button>

            <button
              className={`action-icon-btn ${feedback === "down" ? "active" : ""}`}
              onClick={() => handleRating(-1)}
              title="Poor response"
              aria-label="Poor response"
              type="button"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill={feedback === "down" ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2">
                <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3" />
              </svg>
            </button>

            {copied && <span className="copy-feedback-label">Copied</span>}
          </div>
        )}
      </div>
    </div>
  );
}
