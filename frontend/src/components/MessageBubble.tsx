import { useState } from "react";
import { submitFeedback } from "../services/api";
import "./MessageBubble.css";

interface Props {
  role: "user" | "assistant";
  content: string;
  sources?: unknown;
  messageId?: string;
  conversationId?: string | null;
  sessionId?: string;
}

export default function MessageBubble({
  role,
  content,
  messageId,
  conversationId,
  sessionId,
}: Props) {
  const [feedbackRating, setFeedbackRating] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleFeedback(rating: number) {
    if (!messageId || !conversationId || !sessionId || isSubmitting) return;

    setIsSubmitting(true);
    try {
      await submitFeedback({
        session_id: sessionId,
        conversation_id: conversationId,
        message_id: messageId,
        rating,
      });
      setFeedbackRating(rating);
    } catch (err) {
      console.error("Failed to submit feedback:", err);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className={`message-bubble ${role}`}>
      <div className="message-avatar">
        {role === "user" ? "👤" : "🎓"}
      </div>
      <div className="message-body">
        <div className="message-content">{content}</div>



        {/* Feedback actions for assistant responses */}
        {role === "assistant" && messageId && conversationId && sessionId && (
          <div className="message-feedback-row">
            <span className="feedback-prompt">Was this accurate?</span>
            <button
              className={`feedback-btn ${feedbackRating === 1 ? "active-pos" : ""}`}
              onClick={() => handleFeedback(1)}
              disabled={isSubmitting || feedbackRating !== null}
              title="Helpful & accurate"
            >
              👍 Helpful
            </button>
            <button
              className={`feedback-btn ${feedbackRating === -1 ? "active-neg" : ""}`}
              onClick={() => handleFeedback(-1)}
              disabled={isSubmitting || feedbackRating !== null}
              title="Needs improvement"
            >
              👎 Inaccurate
            </button>
            {feedbackRating !== null && (
              <span className="feedback-thankyou">
                {feedbackRating === 1
                  ? "Saved to verified knowledge!"
                  : "Thank you for the correction!"}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
