import { useState, useRef, useEffect } from "react";
import "./ChatInput.css";

interface Props {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled }: Props) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [text]);

  // Focus on mount (desktop only)
  useEffect(() => {
    if (window.innerWidth > 768) {
      textareaRef.current?.focus();
    }
  }, []);

  // Refocus when assistant finishes
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

  return (
    <div className="chat-input-container">
      <div className="chat-input-wrapper">
        <textarea
          ref={textareaRef}
          className="chat-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message SRU Buddy..."
          disabled={disabled}
          rows={1}
          aria-label="Message SRU Buddy"
        />
        <button
          className={`send-btn ${text.trim() && !disabled ? "active" : ""}`}
          onClick={handleSubmit}
          disabled={!text.trim() || disabled}
          aria-label="Send message"
          title="Send (Enter)"
        >
          <svg
            width="17"
            height="17"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 19V5M5 12l7-7 7 7" />
          </svg>
        </button>
      </div>

      <div className="chat-input-disclaimer">
        <span>SRU Buddy can make mistakes. Verify vital dates & regulations with the university office.</span>
      </div>
    </div>
  );
}
