import { useState } from "react";
import { submitFeedback, type SourceReference } from "../services/api";
import { RenderCard } from "./Cards";
import MarkdownContent from "./MarkdownContent";
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
  isStreaming,
  onSuggestionClick,
}: Props) {
  const [selectedReaction, setSelectedReaction] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

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

  function handleCopy() {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

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
        <div className="message-content">
          <MarkdownContent content={content} isStreaming={isStreaming} />
        </div>

        {/* Rich Interactive Cards (Shown once streaming is complete) */}
        {!isStreaming && role === "assistant" && cards && cards.length > 0 && (
          <div className="message-cards-container">
            {cards.map((card, idx) => (
              <RenderCard key={idx} card={card} />
            ))}
          </div>
        )}

        {/* Quick Suggestion Chips (Shown once streaming is complete) */}
        {!isStreaming && role === "assistant" && suggestions && suggestions.length > 0 && (
          <div className="suggestion-chips-wrapper">
            <span className="chips-hint">Suggested follow-ups:</span>
            <div className="suggestion-chips-list">
              {suggestions.map((suggestion, idx) => (
                <button
                  key={idx}
                  className="suggestion-chip"
                  onClick={() => onSuggestionClick?.(suggestion)}
                  title={`Ask: ${suggestion}`}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Action Row: Emoji Reactions & Copy Button (Shown once streaming is complete) */}
        {!isStreaming && role === "assistant" && (
          <div className="message-action-bar">
            <div className="emoji-reaction-group">
              {EMOJI_REACTIONS.map((item) => (
                <button
                  key={item.emoji}
                  className={`emoji-btn ${selectedReaction === item.emoji ? "selected" : ""}`}
                  onClick={() => handleReaction(item)}
                  title={item.label}
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

            <button className="copy-btn" onClick={handleCopy} title="Copy response">
              {copied ? "✓ Copied" : "📋 Copy"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
