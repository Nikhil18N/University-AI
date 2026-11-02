import { useState, useRef, useEffect } from "react";
import "./ChatInput.css";

interface Props {
  onSend: (message: string) => void;
  isLoading?: boolean;
  onStop?: () => void;
  disabled?: boolean;
  onOpenQuickPrompt?: (prompt: string) => void;
}

const QUICK_ACTIONS = [
  { label: "🧭 Admission Wizard 2026", prompt: "I want admission - start the admission wizard" },
  { label: "💰 Fee & Scholarship Guide", prompt: "What is the complete fee structure and merit scholarship for B.Tech?" },
  { label: "🏠 Hostel Rules & Curfew", prompt: "What are the hostel rules, mess schedule, and curfew timings?" },
  { label: "📊 Placement Highlights", prompt: "Tell me about SR University placement records and top recruiters" },
];

export default function ChatInput({ onSend, isLoading, onStop, disabled }: Props) {
  const [text, setText] = useState("");
  const [showPlusMenu, setShowPlusMenu] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const plusMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
    }
  }, [text]);

  // Focus on mount (desktop only)
  useEffect(() => {
    if (window.innerWidth > 768) {
      textareaRef.current?.focus();
    }
  }, []);

  // Close plus menu on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (plusMenuRef.current && !plusMenuRef.current.contains(event.target as Node)) {
        setShowPlusMenu(false);
      }
    }
    if (showPlusMenu) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showPlusMenu]);

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    if (isLoading && onStop) {
      onStop();
    }
    onSend(trimmed);
    setText("");
    setShowPlusMenu(false);
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

  const handleQuickPromptClick = (prompt: string) => {
    setShowPlusMenu(false);
    onSend(prompt);
  };

  const hasText = text.trim().length > 0;

  return (
    <div className="chat-input-container">
      {/* Plus Menu Popover */}
      {showPlusMenu && (
        <div className="plus-quick-popover" ref={plusMenuRef}>
          <div className="popover-header">Quick SRU Topics</div>
          {QUICK_ACTIONS.map((item, idx) => (
            <button
              key={idx}
              className="plus-quick-item"
              onClick={() => handleQuickPromptClick(item.prompt)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
      )}

      {/* Floating Pill Input Wrapper (Matching Image 1) */}
      <div className="chat-input-pill-wrapper">
        {/* Left Plus Button */}
        <button
          className={`input-plus-circle-btn ${showPlusMenu ? "open" : ""}`}
          onClick={() => setShowPlusMenu(!showPlusMenu)}
          aria-label="Quick actions"
          title="Quick actions"
          type="button"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          className="chat-input-textarea"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask SRU Buddy"
          rows={1}
          aria-label="Ask SRU Buddy"
        />

        {/* Right Action Group */}
        <div className="input-right-action-group">
          {/* Mic Button (Matching Image 1) */}
          <button
            className="input-mic-btn"
            onClick={() => {
              // Mic feature trigger / hint
              if (textareaRef.current) textareaRef.current.focus();
            }}
            title="Voice input"
            aria-label="Voice input"
            type="button"
          >
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="22" />
            </svg>
          </button>

          {/* Circular Action Button (Matching Image 1 blue circle ılı / ↑ / ⏹) */}
          {isLoading ? (
            <button
              className="chatgpt-action-circle stop"
              onClick={onStop}
              aria-label="Stop generating"
              title="Stop generating"
              type="button"
            >
              <span className="stop-square-box" />
            </button>
          ) : hasText ? (
            <button
              className="chatgpt-action-circle send"
              onClick={handleSubmit}
              aria-label="Send message"
              title="Send (Enter)"
              type="button"
            >
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="19" x2="12" y2="5" />
                <polyline points="5 12 12 5 19 12" />
              </svg>
            </button>
          ) : (
            <button
              className="chatgpt-action-circle waveform"
              onClick={() => {
                if (textareaRef.current) textareaRef.current.focus();
              }}
              aria-label="Speech mode"
              title="Voice mode"
              type="button"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <rect x="3" y="10" width="2.5" height="4" rx="1.2" />
                <rect x="8.5" y="6" width="2.5" height="12" rx="1.2" />
                <rect x="14" y="3" width="2.5" height="18" rx="1.2" />
                <rect x="19.5" y="8" width="2.5" height="8" rx="1.2" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
