import { useState, useRef, useEffect } from "react";
import { CalculatorIcon } from "./Icons";
import "./ChatInput.css";

interface Props {
  onSend: (message: string) => void;
  isLoading?: boolean;
  onStop?: () => void;
  disabled?: boolean;
  onOpenCalculator?: () => void;
}

const QUICK_ACTIONS = [
  { label: "How do I apply for 2027-28?", prompt: "How do I apply for admission to SR University for 2027-28?" },
  { label: "B.Tech fees and scholarships", prompt: "What are the B.Tech fees and merit scholarships for 2027-28?" },
  { label: "Hostel rules and in-times", prompt: "What are the hostel rules, mess and in-time for first-year students?" },
  { label: "Placements", prompt: "Tell me about SR University placement records and top recruiters" },
  { label: "Book a campus visit", prompt: "I want to book a campus visit" },
];

// Voice typing uses the browser's own speech recognition (Chrome, Edge, Android, Safari 14.1+).
// Where it is not available the microphone button is simply not shown.
type Recognition = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: any) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: any) => void) | null;
  start: () => void;
  stop: () => void;
};
function createRecognition(): Recognition | null {
  const w = window as any;
  const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
  if (!Ctor) return null;
  const r: Recognition = new Ctor();
  r.lang = "en-IN";
  r.interimResults = true;
  r.continuous = false;
  return r;
}

export default function ChatInput({ onSend, isLoading, onStop, disabled, onOpenCalculator }: Props) {
  const [text, setText] = useState("");
  const [showPlusMenu, setShowPlusMenu] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceSupported] = useState(() => typeof window !== "undefined" && Boolean(
    (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition));
  const recognitionRef = useRef<Recognition | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const plusMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => () => recognitionRef.current?.stop(), []);

  const toggleVoice = () => {
    if (listening) {
      recognitionRef.current?.stop();
      return;
    }
    const rec = createRecognition();
    if (!rec) return;
    const before = text ? text.trimEnd() + " " : "";
    rec.onresult = (e: any) => {
      let heard = "";
      for (let i = 0; i < e.results.length; i++) heard += e.results[i][0].transcript;
      setText(before + heard);
    };
    rec.onend = () => {
      setListening(false);
      textareaRef.current?.focus();
    };
    rec.onerror = () => setListening(false);
    recognitionRef.current = rec;
    try {
      rec.start();
      setListening(true);
    } catch {
      setListening(false);
    }
  };

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
    if (!trimmed || disabled || isLoading) return;
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
      if (!isLoading) {
        handleSubmit();
      }
    }
  };

  const handleQuickPromptClick = (prompt: string) => {
    if (isLoading) return;
    setShowPlusMenu(false);
    onSend(prompt);
  };

  const hasText = text.trim().length > 0;

  return (
    <div className="chat-input-container">
      {/* Plus Menu Popover */}
      {showPlusMenu && (
        <div className="plus-quick-popover" ref={plusMenuRef}>
          <div className="popover-header">Quick questions</div>
          {onOpenCalculator && (
            <button
              className="plus-quick-item"
              onClick={() => {
                setShowPlusMenu(false);
                onOpenCalculator();
              }}
              type="button"
            >
              <CalculatorIcon size={15} /> Fee & Scholarship Calculator
            </button>
          )}
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
          title="Quick questions and calculator"
          aria-haspopup="menu"
          aria-expanded={showPlusMenu}
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
          placeholder={listening ? "Listening… speak now" : "Ask about admissions, fees, hostels…"}
          maxLength={2000}
          rows={1}
          aria-label="Ask SRU Buddy"
        />

        {/* Right Action Group */}
        <div className="input-right-action-group">
          {voiceSupported && (
            <button
              className={`input-mic-btn ${listening ? "listening" : ""}`}
              onClick={toggleVoice}
              title={listening ? "Stop voice typing" : "Voice typing"}
              aria-label={listening ? "Stop voice typing" : "Voice typing"}
              aria-pressed={listening}
              type="button"
              disabled={isLoading}
            >
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="22" />
              </svg>
            </button>
          )}

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
          ) : (
            <button
              className="chatgpt-action-circle send"
              onClick={handleSubmit}
              aria-label="Send message"
              title="Send (Enter)"
              type="button"
              disabled={!hasText || disabled}
            >
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <line x1="12" y1="19" x2="12" y2="5" />
                <polyline points="5 12 12 5 19 12" />
              </svg>
            </button>
          )}
        </div>
      </div>
      <p className="chat-input-disclaimer">
        SRU Buddy is an AI assistant and can make mistakes. Please confirm fees and admission details with the
        Admissions Office (0870-2818333).
      </p>
    </div>
  );
}
