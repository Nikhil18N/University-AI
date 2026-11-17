import React, { useState, useEffect, useRef } from "react";
import MessageBubble from "../components/MessageBubble";
import ThinkingIndicator from "../components/ThinkingIndicator";
import ScholarshipCalculatorModal from "../components/ScholarshipCalculatorModal";
import LeadAuthModal from "../components/LeadAuthModal";
import SettingsModal from "../components/SettingsModal";
import { CalculatorIcon } from "../components/Icons";
import { getSessionId } from "../hooks/useSession";
import { applyServerProfile, syncStudentDetails } from "../utils/studentProfile";
import {
  sendMessageStream,
  type MessageData,
  type ChatResponse,
} from "../services/api";
import { playChime, triggerConfetti } from "../utils/effects";
import "./ChatPage.css";

interface Props {
  onOpenAdmin?: () => void;
  variant?: "full" | "widget";
}

/** Tell the page that embeds the widget to close it (public/widget.js listens for this). */
function closeWidget() {
  try {
    window.parent?.postMessage({ type: "sru-buddy:close" }, "*");
  } catch {
    /* not embedded */
  }
}

const DEFAULT_WELCOME_MESSAGE: MessageData = {
  id: "welcome-sru-buddy",
  role: "assistant",
  content: "Hello! Welcome to SR University. I am **SRU Buddy**, your virtual AI assistant. How may I assist you with admissions, fee structures, or scholarships today?",
  created_at: new Date().toISOString(),
};

const QUICK_STARTER_QUERIES = [
  { label: "💰 B.Tech Fees (2027-28)", prompt: "What is the complete fee structure and hostel fee for B.Tech for 2027-28?" },
  { label: "🧮 Calculate My Scholarship", prompt: "How much scholarship can I get for B.Tech based on my 10+2 marks or EAPCET rank?" },
  { label: "📜 Degree Validity & Accreditation", prompt: "Is SR University degree valid for government jobs, higher education in India and abroad?" },
  { label: "🏫 Plan a Campus Visit", prompt: "I would like to visit the SR University campus. Whom should I contact?" },
];

export default function ChatPage({ onOpenAdmin, variant = "full" }: Props) {
  const isWidget = variant === "widget";
  const sessionId = getSessionId();

  // Widget visibility state: closed by default so floating bubble is visible, clicks open it
  const [isWidgetOpen, setIsWidgetOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  // Queries
  const [dockQuery, setDockQuery] = useState("");
  const [widgetInput, setWidgetInput] = useState("");

  // Chat message state
  const [messages, setMessages] = useState<MessageData[]>([DEFAULT_WELCOME_MESSAGE]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const activeConvIdRef = useRef<string | null>(activeConvId);

  useEffect(() => {
    activeConvIdRef.current = activeConvId;
  }, [activeConvId]);

  const [isLoading, setIsLoading] = useState(false);
  const [activeToolStatus, setActiveToolStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [streamingMsgId, setStreamingMsgId] = useState<string | null>(null);

  // Modals
  const [isCalculatorOpen, setIsCalculatorOpen] = useState(false);
  const [showLeadAuthModal, setShowLeadAuthModal] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [pendingAuthMessage, setPendingAuthMessage] = useState<string | null>(null);
  const [authReason, setAuthReason] = useState<string | undefined>(undefined);

  // Voice recognition
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  const messagesAreaRef = useRef<HTMLDivElement>(null);
  const cancelStreamRef = useRef<(() => void) | null>(null);

  // Auto-sync profile on mount
  useEffect(() => {
    void syncStudentDetails(sessionId);
  }, [sessionId]);

  // Scroll to bottom of widget when messages update
  useEffect(() => {
    if (messagesAreaRef.current) {
      messagesAreaRef.current.scrollTop = messagesAreaRef.current.scrollHeight;
    }
  }, [messages, streamingMsgId, activeToolStatus]);

  // Voice typing toggle
  const toggleVoice = () => {
    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }

    const w = window as any;
    const SpeechRecognition = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Voice typing is not supported by your browser. Please try Chrome or Edge.");
      return;
    }

    try {
      const rec = new SpeechRecognition();
      rec.lang = "en-IN";
      rec.interimResults = true;
      rec.continuous = false;

      rec.onresult = (e: any) => {
        const transcript = Array.from(e.results)
          .map((r: any) => r[0]?.transcript || "")
          .join("");
        setWidgetInput(transcript);
      };

      rec.onend = () => setListening(false);
      rec.onerror = () => setListening(false);

      rec.start();
      recognitionRef.current = rec;
      setListening(true);
    } catch {
      setListening(false);
    }
  };

  function isHighIntentLeadQuery(text: string): boolean {
    const lower = text.toLowerCase();
    const feeKeywords = ["fee", "fees", "tuition", "scholarship", "cost", "hostel fee", "mess fee", "bus fee"];
    const admissionKeywords = ["admission", "admissions", "join", "joining", "apply", "eligibility", "take admission"];
    return feeKeywords.some((k) => lower.includes(k)) || admissionKeywords.some((k) => lower.includes(k));
  }

  function isStudentLeadVerified(): boolean {
    try {
      const lead = localStorage.getItem("sru_student_lead");
      if (!lead) return false;
      const parsed = JSON.parse(lead);
      const digits = (parsed?.phone || "").replace(/\D/g, "");
      return digits.length >= 10 && Boolean(parsed?.name);
    } catch {
      return false;
    }
  }

  async function handleSendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;

    // Check for calculator trigger
    if (/^\s*(🧮\s*)?(scholarship\s*calculator|calculate\s*(?:my\s*)?scholarship|fee\s*calculator|open\s*calculator|calculator)\s*$/i.test(trimmed)) {
      setIsCalculatorOpen(true);
      return;
    }

    let skipped = false;
    try {
      skipped = sessionStorage.getItem("sru_lead_skipped") === "1";
    } catch {
      /* ignore */
    }

    if (isHighIntentLeadQuery(trimmed) && !isStudentLeadVerified() && !skipped) {
      setPendingAuthMessage(trimmed);
      setAuthReason("Share your name and mobile number if you would like personal assistance from our admissions counselors.");
      setShowLeadAuthModal(true);
      return;
    }

    await executeSendMessage(trimmed);
  }

  async function executeSendMessage(text: string) {
    if (isLoading && cancelStreamRef.current) {
      cancelStreamRef.current();
      cancelStreamRef.current = null;
    }

    setIsLoading(true);
    setError(null);

    const userMsgId = crypto.randomUUID();
    const assistantMsgId = crypto.randomUUID();
    setStreamingMsgId(assistantMsgId);

    const tempUserMsg: MessageData = {
      id: userMsgId,
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };

    const placeholderAssistantMsg: MessageData = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, tempUserMsg, placeholderAssistantMsg]);

    let accumulatedContent = "";
    const accumulatedCards: any[] = [];

    const convIdToSend = activeConvIdRef.current || activeConvId;
    const cancelFn = sendMessageStream(sessionId, text, convIdToSend, {
      onStart: (convId) => {
        if (convId) {
          setActiveConvId(convId);
          activeConvIdRef.current = convId;
        }
      },
      onTool: (tool) => {
        if (tool.status === "running") {
          setActiveToolStatus(tool.label || "Working...");
        } else {
          setActiveToolStatus(null);
        }
      },
      onCard: (card) => {
        accumulatedCards.push(card);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId ? { ...m, cards: [...accumulatedCards] } : m
          )
        );
      },
      onToken: (delta) => {
        setActiveToolStatus(null);
        accumulatedContent += delta;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId ? { ...m, content: accumulatedContent } : m
          )
        );
      },
      onDone: (data: ChatResponse) => {
        setIsLoading(false);
        setActiveToolStatus(null);
        setStreamingMsgId(null);
        cancelStreamRef.current = null;

        if (data.conversation_id) {
          setActiveConvId(data.conversation_id);
          activeConvIdRef.current = data.conversation_id;
        }
        applyServerProfile(data.profile);
        playChime();

        const ansLower = (data.answer || "").toLowerCase();
        if (ansLower.includes("fully eligible") || ansLower.includes("congratulations")) {
          triggerConfetti();
        }

        const finalCards = data.cards?.length ? data.cards : accumulatedCards;

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  id: data.message_id || m.id,
                  content: data.answer || accumulatedContent,
                  sources: data.sources?.length ? data.sources : undefined,
                  suggestions: data.suggestions?.length ? data.suggestions : undefined,
                  cards: finalCards.length ? finalCards : undefined,
                  flow: data.flow,
                  model: data.model,
                }
              : m
          )
        );
      },
      onError: (err) => {
        setIsLoading(false);
        setActiveToolStatus(null);
        setStreamingMsgId(null);
        cancelStreamRef.current = null;
        setError(err.message || "Failed to get response.");
        setMessages((prev) =>
          prev.filter((m) => m.id !== assistantMsgId || accumulatedContent.length > 0)
        );
      },
    });

    cancelStreamRef.current = cancelFn;
  }

  function handleResetChat() {
    if (cancelStreamRef.current) {
      cancelStreamRef.current();
      cancelStreamRef.current = null;
    }
    setIsLoading(false);
    setStreamingMsgId(null);
    setActiveConvId(null);
    activeConvIdRef.current = null;
    setMessages([DEFAULT_WELCOME_MESSAGE]);
    setError(null);
  }

  // Handle bottom floating dock input submit
  const handleDockSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!dockQuery.trim()) return;
    setIsWidgetOpen(true);
    setIsMinimized(false);
    handleSendMessage(dockQuery.trim());
    setDockQuery("");
  };

  // Handle widget input submit
  const handleWidgetSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!widgetInput.trim() || isLoading) return;
    handleSendMessage(widgetInput.trim());
    setWidgetInput("");
  };

  // Render Widget View directly if variant === "widget" (used inside public/widget.js iframe)
  if (isWidget) {
    return (
      <div className="sru-portal-root sru-portal--widget" style={{ minHeight: "100vh", height: "100vh", background: "var(--bg-main, #0f172a)" }}>
        <div className="sru-widget-container" style={{ position: "fixed", inset: 0, width: "100%", height: "100%", maxHeight: "100%", maxWidth: "100%", borderRadius: 0, border: "none" }}>
          {/* Header */}
          <div className="sru-widget-header">
            <div className="sru-widget-header-left">
              <div className="sru-widget-avatar-wrap">
                <img src="/sru-crest.png" alt="SRU" className="sru-widget-avatar-img" />
              </div>
              <div className="sru-widget-title-col">
                <span className="sru-widget-title">SRU Assistant</span>
                <span className="sru-widget-status">
                  <span className="sru-widget-status-dot" />
                  Connected
                </span>
              </div>
            </div>

            <div className="sru-widget-header-actions">
              <button
                className="sru-widget-hdr-btn"
                onClick={() => setIsCalculatorOpen(true)}
                title="Fee Calculator"
                aria-label="Fee Calculator"
              >
                🧮
              </button>
              <button
                className="sru-widget-hdr-btn"
                onClick={handleResetChat}
                title="Reset / New Chat"
                aria-label="Reset Chat"
              >
                ↺
              </button>
              <a
                className="sru-widget-hdr-btn"
                href="/"
                target="_blank"
                rel="noopener noreferrer"
                title="Open full screen"
                aria-label="Open full screen"
                style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", textDecoration: "none", color: "white" }}
              >
                ↗
              </a>
              <button
                className="sru-widget-hdr-btn"
                onClick={closeWidget}
                title="Close"
                aria-label="Close"
              >
                ✕
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="sru-widget-body" ref={messagesAreaRef}>
            {messages.map((msg, index) => (
              <MessageBubble
                key={msg.id || index}
                role={msg.role}
                content={msg.content}
                cards={msg.cards}
                suggestions={msg.suggestions}
                flow={msg.flow}
                messageId={msg.id}
                conversationId={activeConvId}
                sessionId={sessionId}
                isStreaming={msg.id === streamingMsgId}
                onSuggestionClick={(prompt) => handleSendMessage(prompt)}
              />
            ))}

            {isLoading && (
              <ThinkingIndicator activeToolLabel={activeToolStatus} />
            )}

            {error && (
              <div style={{ color: "#f87171", fontSize: "0.82rem", padding: "8px 12px", background: "rgba(220, 38, 38, 0.15)", borderRadius: "8px" }}>
                {error}
              </div>
            )}

            {messages.length <= 1 && !isLoading && (
              <div className="sru-widget-starters">
                {QUICK_STARTER_QUERIES.map((q, i) => (
                  <button
                    key={i}
                    className="sru-starter-chip"
                    onClick={() => handleSendMessage(q.prompt)}
                  >
                    <span>{q.label}</span>
                    <span>→</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Footer / Input Bar */}
          <div className="sru-widget-footer">
            <form className="sru-widget-input-row" onSubmit={handleWidgetSubmit}>
              <textarea
                className="sru-widget-textarea"
                placeholder="Type your message...."
                rows={1}
                value={widgetInput}
                onChange={(e) => setWidgetInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleWidgetSubmit(e);
                  }
                }}
              />

              <button
                type="button"
                className={`sru-widget-voice-btn ${listening ? "listening" : ""}`}
                onClick={toggleVoice}
                title="Voice Typing"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="23" />
                  <line x1="8" y1="23" x2="16" y2="23" />
                </svg>
              </button>

              <button
                type="submit"
                className="sru-widget-send-btn"
                disabled={!widgetInput.trim() || isLoading}
                title="Send Message"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" fill="currentColor" />
                </svg>
              </button>
            </form>

            <div className="sru-widget-watermark">
              powered by <strong>SRU Buddy</strong>
            </div>
          </div>
        </div>

        {/* Modals */}
        {isCalculatorOpen && (
          <ScholarshipCalculatorModal
            onClose={() => setIsCalculatorOpen(false)}
            onAskBuddy={(prompt) => {
              setIsCalculatorOpen(false);
              handleSendMessage(prompt);
            }}
          />
        )}

        <LeadAuthModal
          isOpen={showLeadAuthModal}
          onClose={() => {
            setShowLeadAuthModal(false);
            try {
              sessionStorage.setItem("sru_lead_skipped", "1");
            } catch {
              /* ignore */
            }
            if (pendingAuthMessage) {
              const nextMsg = pendingAuthMessage;
              setPendingAuthMessage(null);
              executeSendMessage(nextMsg);
            }
          }}
          onSuccess={(_lead) => {
            setShowLeadAuthModal(false);
            if (pendingAuthMessage) {
              const nextMsg = pendingAuthMessage;
              setPendingAuthMessage(null);
              executeSendMessage(nextMsg);
            }
          }}
          reasonText={authReason}
        />

        {showSettings && (
          <SettingsModal
            isOpen={showSettings}
            onClose={() => setShowSettings(false)}
            sessionId={sessionId}
          />
        )}
      </div>
    );
  }

  // Full Portal Landing Page + Floating Minimal Assistant Widget
  return (
    <div className="sru-portal-root">
      {/* 1. Top Announcement Ribbon */}
      <div className="sru-top-ribbon">
        <div className="sru-ribbon-left">
          <span className="sru-ribbon-tag">Admissions 2027-28</span>
          <span className="sru-ribbon-text">
            Applications Open for Academic Session 2027-28
          </span>
          <button
            className="sru-btn-register"
            style={{ padding: "2px 8px", fontSize: "0.68rem" }}
            onClick={() => setShowLeadAuthModal(true)}
          >
            REGISTER NOW
          </button>
        </div>

        <div className="sru-ribbon-right">
          <button
            className="sru-btn-embed"
            onClick={() => {
              const code = `<script src="https://university-ai-companion.vercel.app/widget.js" defer></script>`;
              navigator.clipboard?.writeText(code);
              alert("Copied embed script to clipboard!\n\nAdd this tag before </body> on your university website to add this chat bubble:\n\n" + code);
            }}
            title="Copy script tag to add this chat bubble to your official university website"
          >
            📋 Add Bubble to Website
          </button>

          <a
            href="https://wa.me/919640606408"
            target="_blank"
            rel="noopener noreferrer"
            className="sru-ribbon-link"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
            </svg>
            WhatsApp
          </a>

          <a href="tel:08702818333" className="sru-ribbon-link">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
            </svg>
            Call Us
          </a>

          <div className="sru-ribbon-socials">
            <span className="sru-social-icon" title="Facebook">f</span>
            <span className="sru-social-icon" title="X / Twitter">𝕏</span>
            <span className="sru-social-icon" title="LinkedIn">in</span>
            <span className="sru-social-icon" title="Instagram">ig</span>
            <span className="sru-social-icon" title="YouTube">yt</span>
          </div>

          {onOpenAdmin && (
            <button className="sru-admin-badge" onClick={onOpenAdmin}>
              Admin Console
            </button>
          )}
        </div>
      </div>

      {/* 2. Main University Navigation Bar */}
      <header className="sru-main-nav">
        <div className="sru-nav-brand">
          <img src="/sru-logo.png" alt="SR University Logo" className="sru-brand-logo-img" />
          <div className="sru-brand-meta">
            <span className="sru-brand-title">SR UNIVERSITY</span>
            <span className="sru-brand-sub">WARANGAL, TELANGANA • NAAC 'A' GRADE</span>
          </div>
        </div>

        <nav>
          <ul className="sru-nav-menu">
            <li className="sru-nav-item"><span className="sru-nav-link">ABOUT US ▾</span></li>
            <li className="sru-nav-item"><span className="sru-nav-link sru-ai-nav-pill">AI FEATURES</span></li>
            <li className="sru-nav-item"><span className="sru-nav-link">ACADEMICS ▾</span></li>
            <li className="sru-nav-item"><span className="sru-nav-link">PROGRAMS ▾</span></li>
            <li className="sru-nav-item"><span className="sru-nav-link">ADMISSIONS ▾</span></li>
            <li className="sru-nav-item"><span className="sru-nav-link">CAMPUS LIFE ▾</span></li>
            <li className="sru-nav-item"><span className="sru-nav-link">RESEARCH</span></li>
            <li className="sru-nav-item"><span className="sru-nav-link">PLACEMENTS</span></li>
            <li className="sru-nav-item"><span className="sru-nav-link">CONTACT US</span></li>
          </ul>
        </nav>

        <div className="sru-nav-cta-group">
          <button
            className="sru-btn-embed"
            onClick={() => {
              const code = `<script src="https://university-ai-companion.vercel.app/widget.js" defer></script>`;
              navigator.clipboard?.writeText(code);
              alert("Copied embed script to clipboard!\n\nAdd this tag before </body> on your university website to add this chat bubble:\n\n" + code);
            }}
            title="Copy script tag to add this chat bubble to your official university website"
          >
            📋 Add Bubble to Website
          </button>
          <button
            className="sru-btn-calc"
            onClick={() => setIsCalculatorOpen(true)}
            title="Open Fee & Scholarship Calculator"
          >
            <CalculatorIcon size={16} />
            <span>Fee Calculator</span>
          </button>
          <button
            className="sru-btn-register"
            onClick={() => setShowLeadAuthModal(true)}
          >
            REGISTER NOW
          </button>
        </div>
      </header>

      {/* 3. Hero Section (Center Stage matching reference image) */}
      <main className="sru-hero-section">
        <div className="sru-hero-badge">
          ✨ Admissions Open • Academic Session 2027-28
        </div>
        <h1 className="sru-hero-title">
          India's First AI-Augmented Multidisciplinary University
        </h1>
        <p className="sru-hero-desc">
          In an era propelled by the advent of artificial intelligence, SR University, Telangana,
          has embraced customised learning pathways, data-driven insights, virtual reality experiences,
          and real-world simulations to transform every classroom into a future-ready launchpad,
          empowering students to learn smarter, think sharper, and graduate career-ready.
        </p>

        <div className="sru-hero-stats">
          <div className="sru-stat-card">
            <span className="sru-stat-value">₹51 LPA</span>
            <span className="sru-stat-label">Highest Package @ Microsoft</span>
          </div>
          <div className="sru-stat-card">
            <span className="sru-stat-value">91st</span>
            <span className="sru-stat-label">NIRF Rank in Engineering</span>
          </div>
          <div className="sru-stat-card">
            <span className="sru-stat-value">170 Acres</span>
            <span className="sru-stat-label">Green Tech Campus & Labs</span>
          </div>
          <div className="sru-stat-card">
            <span className="sru-stat-value">NAAC 'A'</span>
            <span className="sru-stat-label">Tier-I NBA Accredited</span>
          </div>
        </div>
      </main>

      {/* 4. Floating Bottom Launcher Dock (Matches Reference Image 2) */}
      {(!isWidgetOpen || isMinimized) && (
        <div className="sru-floating-dock">
          <form className="sru-dock-input-pill" onSubmit={handleDockSubmit}>
            <input
              type="text"
              className="sru-dock-field"
              placeholder="Ask anything about us...."
              value={dockQuery}
              onChange={(e) => setDockQuery(e.target.value)}
            />
            <button type="submit" className="sru-dock-btn">
              Just Ask
            </button>
          </form>

          <button
            className="sru-dock-register-btn"
            onClick={() => setShowLeadAuthModal(true)}
          >
            <span>REGISTER</span>
            <span>NOW</span>
          </button>

          <button
            className="sru-launcher-avatar-btn"
            onClick={() => {
              setIsWidgetOpen(true);
              setIsMinimized(false);
            }}
            title="Open SRU Buddy AI Assistant"
            aria-label="Open SRU Buddy AI Assistant"
          >
            <div className="sru-launcher-pulse" />
            <img src="/sru-crest.png" alt="SRU Crest" className="sru-launcher-img" />
          </button>
        </div>
      )}

      {/* 5. Floating AI Assistant Widget Modal (Matches Reference Image 1) */}
      {isWidgetOpen && (
        <div className={`sru-widget-container ${isMinimized ? "sru-widget-minimized" : ""}`}>
          {/* Header */}
          <div className="sru-widget-header">
            <div className="sru-widget-header-left">
              <div className="sru-widget-avatar-wrap">
                <img src="/sru-crest.png" alt="SRU" className="sru-widget-avatar-img" />
              </div>
              <div className="sru-widget-title-col">
                <span className="sru-widget-title">SRU Assistant</span>
                <span className="sru-widget-status">
                  <span className="sru-widget-status-dot" />
                  Connected
                </span>
              </div>
            </div>

            <div className="sru-widget-header-actions">
              <button
                className="sru-widget-hdr-btn"
                onClick={() => setIsCalculatorOpen(true)}
                title="Fee Calculator"
                aria-label="Fee Calculator"
              >
                🧮
              </button>
              <button
                className="sru-widget-hdr-btn"
                onClick={handleResetChat}
                title="Reset / New Chat"
                aria-label="Reset Chat"
              >
                ↺
              </button>
              <button
                className="sru-widget-hdr-btn"
                onClick={() => setIsMinimized((prev) => !prev)}
                title={isMinimized ? "Expand" : "Minimize"}
                aria-label="Minimize"
              >
                —
              </button>
              <button
                className="sru-widget-hdr-btn"
                onClick={() => setIsWidgetOpen(false)}
                title="Close"
                aria-label="Close"
              >
                ✕
              </button>
            </div>
          </div>

          {/* Body */}
          {!isMinimized && (
            <>
              <div className="sru-widget-body" ref={messagesAreaRef}>
                {messages.map((msg, index) => (
                  <MessageBubble
                    key={msg.id || index}
                    role={msg.role}
                    content={msg.content}
                    cards={msg.cards}
                    suggestions={msg.suggestions}
                    flow={msg.flow}
                    messageId={msg.id}
                    conversationId={activeConvId}
                    sessionId={sessionId}
                    isStreaming={msg.id === streamingMsgId}
                    onSuggestionClick={(prompt) => handleSendMessage(prompt)}
                  />
                ))}

                {isLoading && (
                  <ThinkingIndicator activeToolLabel={activeToolStatus} />
                )}

                {error && (
                  <div style={{ color: "#f87171", fontSize: "0.82rem", padding: "8px 12px", background: "rgba(220, 38, 38, 0.15)", borderRadius: "8px" }}>
                    {error}
                  </div>
                )}

                {/* Quick starter chips when conversation is just starting */}
                {messages.length <= 1 && !isLoading && (
                  <div className="sru-widget-starters">
                    {QUICK_STARTER_QUERIES.map((q, i) => (
                      <button
                        key={i}
                        className="sru-starter-chip"
                        onClick={() => handleSendMessage(q.prompt)}
                      >
                        <span>{q.label}</span>
                        <span>→</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Footer / Input Bar */}
              <div className="sru-widget-footer">
                <form className="sru-widget-input-row" onSubmit={handleWidgetSubmit}>
                  <textarea
                    className="sru-widget-textarea"
                    placeholder="Type your message...."
                    rows={1}
                    value={widgetInput}
                    onChange={(e) => setWidgetInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleWidgetSubmit(e);
                      }
                    }}
                  />

                  <button
                    type="button"
                    className={`sru-widget-voice-btn ${listening ? "listening" : ""}`}
                    onClick={toggleVoice}
                    title="Voice Typing"
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                      <line x1="12" y1="19" x2="12" y2="23" />
                      <line x1="8" y1="23" x2="16" y2="23" />
                    </svg>
                  </button>

                  <button
                    type="submit"
                    className="sru-widget-send-btn"
                    disabled={!widgetInput.trim() || isLoading}
                    title="Send Message"
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <line x1="22" y1="2" x2="11" y2="13" />
                      <polygon points="22 2 15 22 11 13 2 9 22 2" fill="currentColor" />
                    </svg>
                  </button>
                </form>

                <div className="sru-widget-watermark">
                  powered by <strong>SRU Buddy</strong>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Modals */}
      {isCalculatorOpen && (
        <ScholarshipCalculatorModal
          onClose={() => setIsCalculatorOpen(false)}
          onAskBuddy={(prompt) => {
            setIsCalculatorOpen(false);
            handleSendMessage(prompt);
          }}
        />
      )}

      <LeadAuthModal
        isOpen={showLeadAuthModal}
        onClose={() => {
          setShowLeadAuthModal(false);
          try {
            sessionStorage.setItem("sru_lead_skipped", "1");
          } catch {
            /* ignore */
          }
          if (pendingAuthMessage) {
            const nextMsg = pendingAuthMessage;
            setPendingAuthMessage(null);
            executeSendMessage(nextMsg);
          }
        }}
        onSuccess={(_lead) => {
          setShowLeadAuthModal(false);
          if (pendingAuthMessage) {
            const nextMsg = pendingAuthMessage;
            setPendingAuthMessage(null);
            executeSendMessage(nextMsg);
          }
        }}
        reasonText={authReason}
      />

      {showSettings && (
        <SettingsModal
          isOpen={showSettings}
          onClose={() => setShowSettings(false)}
          sessionId={sessionId}
        />
      )}
    </div>
  );
}
