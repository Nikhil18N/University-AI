import { useState, useRef, useEffect } from "react";
import "./ChatInput.css";

interface Props {
  onSend: (message: string) => void;
  disabled?: boolean;
}

const QUICK_PROMPT_PILLS = [
  "Are admissions open?",
  "B.Tech fee structure",
  "Hostel rules & curfew",
  "CSE vs AI/ML",
  "Placement statistics",
  "Scholarship criteria",
];

export default function ChatInput({ onSend, disabled }: Props) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 140) + "px";
    }
  }, [text]);

  // Always keep input focused on mount (desktop only, avoid auto-popping keyboard on mobile on fresh load)
  useEffect(() => {
    if (window.innerWidth > 768) {
      textareaRef.current?.focus();
    }
  }, []);

  // Automatically refocus on desktop when assistant finishes responding
  useEffect(() => {
    if (!disabled && window.innerWidth > 768) {
      const timer = setTimeout(() => {
        textareaRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [disabled]);

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handlePillClick = (prompt: string) => {
    if (disabled) return;
    onSend(prompt);
  };

  return (
    <div className="chat-input-container">
      {/* Quick Prompt Carousel Pills */}
      <div className="quick-pills-row" aria-label="Suggested questions">
        {QUICK_PROMPT_PILLS.map((pill, idx) => (
          <button
            key={idx}
            className="quick-pill-btn"
            onClick={() => handlePillClick(pill)}
            disabled={disabled}
            type="button"
          >
            {pill}
          </button>
        ))}
      </div>

      <div className="chat-input-wrapper">
        <textarea
          ref={textareaRef}
          className="chat-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask SRU Buddy about admissions, courses, hostels, fees..."
          disabled={disabled}
          rows={1}
          aria-label="Ask SR University Assistant"
        />
        <button
          className="send-btn"
          onClick={handleSubmit}
          disabled={!text.trim() || disabled}
          aria-label="Send message"
          title="Send (Enter)"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>

      <div className="chat-input-footer">
        <span className="official-verify-tag">
          🔒 Official SR University AI • Grounded in Student Handbook & Regulations
        </span>
      </div>
    </div>
  );
}
