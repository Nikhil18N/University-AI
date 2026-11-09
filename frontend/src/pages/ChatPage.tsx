import { useState, useEffect, useRef } from "react";
import MessageBubble from "../components/MessageBubble";
import ChatInput from "../components/ChatInput";
import ConversationList from "../components/ConversationList";
import ThinkingIndicator from "../components/ThinkingIndicator";
import ShareModal from "../components/ShareModal";
import ScholarshipCalculatorModal from "../components/ScholarshipCalculatorModal";
import LeadAuthModal from "../components/LeadAuthModal";
import { CalculatorIcon } from "../components/Icons";
import { exportToPDF, exportToMarkdown, exportToText } from "../utils/exportChat";
import { getSessionId } from "../hooks/useSession";
import {
  sendMessageStream,
  listConversations,
  getConversation,
  getSharedConversation,
  deleteConversation,
  type ConversationSummary,
  type MessageData,
  type ChatResponse,
} from "../services/api";
import { playChime, triggerConfetti } from "../utils/effects";
import "./ChatPage.css";

interface Props {
  onOpenAdmin?: () => void;
}

const MINIMAL_STARTERS = [
  {
    title: "Admissions 2026",
    desc: "Eligibility criteria, cutoff ranks & application procedure",
    prompt: "What is the eligibility criteria and admission process for B.Tech 2026?",
  },
  {
    title: "Fees & Scholarships",
    desc: "Tuition breakdown, hostel fee tiers & merit scholarships",
    prompt: "What is the complete fee structure and merit scholarship details for B.Tech?",
  },
  {
    title: "Hostel Living & Rules",
    desc: "Room types, mess schedule, night curfew & out-pass policies",
    prompt: "What are the hostel room options, mess food, and curfew rules?",
  },
  {
    title: "Placements & Recruiters",
    desc: "Highest packages, placement rate & top campus hiring companies",
    prompt: "Tell me about SR University placement records, top recruiters, and highest package",
  },
];

export default function ChatPage({ onOpenAdmin }: Props) {
  const sessionId = getSessionId();

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Responsive sidebar: closed by default on mobile (< 768px), open on desktop
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth > 768);

  // Modals & Popovers
  const [showShareModal, setShowShareModal] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const [isCalculatorOpen, setIsCalculatorOpen] = useState(false);
  const [showLeadAuthModal, setShowLeadAuthModal] = useState<boolean>(false);
  const [pendingAuthMessage, setPendingAuthMessage] = useState<string | null>(null);
  const [authReason, setAuthReason] = useState<string | undefined>(undefined);

  // Theme & Sound states (default to white / light mode)
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const saved = localStorage.getItem("sru_theme_v2");
    if (saved === "light" || saved === "dark") {
      return saved;
    }
    return "light";
  });
  const [soundEnabled, setSoundEnabled] = useState<boolean>(() => {
    return localStorage.getItem("sru_sound") !== "false";
  });

  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const [streamingMsgId, setStreamingMsgId] = useState<string | null>(null);

  // Shared chat states
  const [isSharedView, setIsSharedView] = useState(false);
  const [sharedTitle, setSharedTitle] = useState<string | null>(null);
  const [isLoadingShared, setIsLoadingShared] = useState(false);

  const messagesAreaRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const cancelStreamRef = useRef<(() => void) | null>(null);
  const exportMenuRef = useRef<HTMLDivElement>(null);
  const mobileMenuRef = useRef<HTMLDivElement>(null);
  const isAtBottomRef = useRef(true);

  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("sru_theme_v2", theme);
    localStorage.setItem("sru_theme", theme);
  }, [theme]);

  // Load conversations on mount & check for shared link (?chat=... or #s=...)
  useEffect(() => {
    loadConversations();

    async function checkSharedLink() {
      try {
        const searchParams = new URLSearchParams(window.location.search);
        const chatId = searchParams.get("chat") || searchParams.get("share");
        let hashData = "";
        if (window.location.hash.startsWith("#s=")) {
          hashData = window.location.hash.slice(3);
        }

        // 1. Instant recovery from hash snapshot if available (0ms offline/sleep fallback)
        if (hashData) {
          try {
            const jsonStr = decodeURIComponent(escape(atob(decodeURIComponent(hashData))));
            const parsed = JSON.parse(jsonStr);
            if (parsed && Array.isArray(parsed.m) && parsed.m.length > 0) {
              const restoredMsgs: MessageData[] = parsed.m.map((item: any, i: number) => ({
                id: `shared-${i}`,
                role: item.r,
                content: item.c,
                created_at: new Date().toISOString(),
              }));
              setMessages(restoredMsgs);
              setIsSharedView(true);
              setSharedTitle(parsed.t || "Shared Conversation");
              setTimeout(() => {
                if (messagesAreaRef.current) {
                  messagesAreaRef.current.scrollTop = messagesAreaRef.current.scrollHeight;
                }
              }, 60);
              return;
            }
          } catch (e) {
            console.warn("Could not decode hash snapshot:", e);
          }
        }

        // 2. Fetch from backend public shared endpoint if chatId is present
        if (chatId && chatId !== "share" && chatId !== "1") {
          setIsLoadingShared(true);
          try {
            const detail = await getSharedConversation(chatId);
            if (detail && detail.messages && detail.messages.length > 0) {
              setMessages(detail.messages);
              setIsSharedView(true);
              setSharedTitle(detail.title || "Shared Conversation");
              setTimeout(() => {
                if (messagesAreaRef.current) {
                  messagesAreaRef.current.scrollTop = messagesAreaRef.current.scrollHeight;
                }
              }, 60);
            }
          } catch (err) {
            console.warn("Failed to load shared chat from backend:", err);
          } finally {
            setIsLoadingShared(false);
          }
        }
      } catch (err) {
        console.error("Shared link check error:", err);
      }
    }

    checkSharedLink();
  }, []);

  // Close export & mobile menus when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        exportMenuRef.current &&
        !exportMenuRef.current.contains(event.target as Node)
      ) {
        setShowExportMenu(false);
      }
      if (
        mobileMenuRef.current &&
        !mobileMenuRef.current.contains(event.target as Node)
      ) {
        setShowMobileMenu(false);
      }
    }
    if (showExportMenu || showMobileMenu) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showExportMenu, showMobileMenu]);

  // Track user's manual scroll position
  const handleScroll = () => {
    if (!messagesAreaRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = messagesAreaRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;

    // If within 80px from bottom, consider user "at bottom"
    const atBottom = distanceFromBottom <= 80;
    isAtBottomRef.current = atBottom;
    setShowScrollBottom(!atBottom);
  };

  const scrollToBottom = (smooth: boolean = true) => {
    isAtBottomRef.current = true;
    setShowScrollBottom(false);
    if (messagesAreaRef.current) {
      if (smooth) {
        messagesAreaRef.current.scrollTo({
          top: messagesAreaRef.current.scrollHeight,
          behavior: "smooth",
        });
      } else {
        messagesAreaRef.current.scrollTop = messagesAreaRef.current.scrollHeight;
      }
    }
  };

  // Only auto-scroll on new stream tokens if user is already at the bottom
  // If the user scrolled up to read earlier text, DO NOT hijack their scroll!
  useEffect(() => {
    if (!isAtBottomRef.current) return;

    if (messagesAreaRef.current) {
      messagesAreaRef.current.scrollTop = messagesAreaRef.current.scrollHeight;
    }
  }, [messages, streamingMsgId]);

  async function loadConversations() {
    try {
      const convs = await listConversations(sessionId);
      setConversations(convs);
    } catch {
      // Silently fail on first load
    }
  }

  async function handleSelectConversation(convId: string) {
    if (cancelStreamRef.current) {
      cancelStreamRef.current();
      cancelStreamRef.current = null;
    }
    setStreamingMsgId(null);
    setActiveConvId(convId);
    setError(null);
    isAtBottomRef.current = true;
    setShowScrollBottom(false);
    try {
      const detail = await getConversation(convId, sessionId);
      setMessages(detail.messages);
      setTimeout(() => {
        if (messagesAreaRef.current) {
          messagesAreaRef.current.scrollTop = messagesAreaRef.current.scrollHeight;
        }
      }, 50);
    } catch {
      setError("Failed to load conversation.");
    }
  }

  function handleNewChat() {
    if (cancelStreamRef.current) {
      cancelStreamRef.current();
      cancelStreamRef.current = null;
    }
    setStreamingMsgId(null);
    setActiveConvId(null);
    setMessages([]);
    setIsSharedView(false);
    setSharedTitle(null);
    setError(null);
    isAtBottomRef.current = true;
    setShowScrollBottom(false);
    if (window.location.search || window.location.hash) {
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }

  function handleStopStreaming() {
    if (cancelStreamRef.current) {
      cancelStreamRef.current();
      cancelStreamRef.current = null;
    }
    setIsLoading(false);
    setStreamingMsgId(null);
  }

  async function handleDeleteConversation(convId: string) {
    try {
      await deleteConversation(convId, sessionId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConvId === convId) {
        handleNewChat();
      }
    } catch {
      setError("Failed to delete conversation.");
    }
  }

  function toggleTheme() {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  }

  function toggleSound() {
    setSoundEnabled((prev) => {
      const next = !prev;
      localStorage.setItem("sru_sound", String(next));
      return next;
    });
  }

  // Active chat title for share & export
  const activeChatTitle =
    conversations.find((c) => c.id === activeConvId)?.title ||
    messages.find((m) => m.role === "user")?.content.slice(0, 40) ||
    "SRU Buddy Chat";

  const handleExportPDF = () => {
    setShowExportMenu(false);
    exportToPDF(activeChatTitle, messages);
  };

  const handleExportMD = () => {
    setShowExportMenu(false);
    exportToMarkdown(activeChatTitle, messages);
  };

  const handleExportTXT = () => {
    setShowExportMenu(false);
    exportToText(activeChatTitle, messages);
  };

  function isHighIntentLeadQuery(text: string): boolean {
    const lower = text.toLowerCase();
    const feeKeywords = [
      "fee", "fees", "tuition", "scholarship", "cost", "hostel fee", "mess fee", "bus fee", "transport fee"
    ];
    const admissionKeywords = [
      "admission", "admissions", "join", "joining", "apply", "seat", "eligibility",
      "how to get into", "how to join", "cutoff", "cut off", "rank requirement",
      "interested in joining", "take admission", "b.tech admission", "how to apply"
    ];
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

    if (trimmed === "🧮 Scholarship Calculator" || trimmed === "🧮 Open Scholarship Calculator") {
      setIsCalculatorOpen(true);
      return;
    }

    // Middleware: Authenticate prospective student before answering high-intent fee & admission queries
    if (isHighIntentLeadQuery(trimmed) && !isStudentLeadVerified()) {
      setPendingAuthMessage(trimmed);
      setAuthReason(
        "To view complete SR University fee structures, scholarship calculations, and priority admission guidance, please authenticate with your student name and mobile number."
      );
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

    // If replying from a shared chat view, seamlessly fork into own conversation
    if (isSharedView) {
      setIsSharedView(false);
      setActiveConvId(null);
      if (window.location.search || window.location.hash) {
        window.history.replaceState({}, document.title, window.location.pathname);
      }
    }

    // CRITICAL: When user sends a message, immediately scroll to bottom
    isAtBottomRef.current = true;
    setShowScrollBottom(false);
    if (messagesAreaRef.current) {
      messagesAreaRef.current.scrollTop = messagesAreaRef.current.scrollHeight;
    }
    setTimeout(() => {
      if (messagesAreaRef.current) {
        messagesAreaRef.current.scrollTop = messagesAreaRef.current.scrollHeight;
      }
    }, 40);

    const userMsgId = crypto.randomUUID();
    const assistantMsgId = crypto.randomUUID();
    setStreamingMsgId(assistantMsgId);

    // 1. Optimistically append user message
    const tempUserMsg: MessageData = {
      id: userMsgId,
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };

    // 2. Add streaming placeholder for assistant
    const placeholderAssistantMsg: MessageData = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, tempUserMsg, placeholderAssistantMsg]);

    let accumulatedContent = "";

    // 3. Initiate Server-Sent Events stream
    const cancelFn = sendMessageStream(sessionId, text, activeConvId, {
      onStart: (convId) => {
        if (!activeConvId) {
          setActiveConvId(convId);
        }
      },
      onToken: (delta) => {
        accumulatedContent += delta;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId ? { ...m, content: accumulatedContent } : m
          )
        );
      },
      onDone: (data: ChatResponse) => {
        setIsLoading(false);
        setStreamingMsgId(null);
        cancelStreamRef.current = null;

        if (soundEnabled) {
          playChime();
        }

        const ansLower = (data.answer || "").toLowerCase();
        if (
          ansLower.includes("fully eligible") ||
          ansLower.includes("admission verdict: fully eligible") ||
          ansLower.includes("you are eligible") ||
          ansLower.includes("congratulations")
        ) {
          triggerConfetti();
        }

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  id: data.message_id,
                  content: data.answer || accumulatedContent,
                  sources: undefined,
                  suggestions: data.suggestions?.length ? data.suggestions : undefined,
                  cards: data.cards?.length ? data.cards : undefined,
                  flow: data.flow,
                  model: data.model,
                }
              : m
          )
        );

        loadConversations();
      },
      onError: (err) => {
        setIsLoading(false);
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

  return (
    <div className={`chat-page theme-${theme}`}>
      {/* Mobile Drawer Backdrop */}
      {sidebarOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Main Layout: Sidebar + Canvas */}
      <div className="chat-layout-wrapper">
        {/* Sliding Sidebar */}
        {/* Sliding Sidebar */}
        <aside className={`sidebar ${sidebarOpen ? "open" : "closed"}`}>
          <ConversationList
            conversations={conversations}
            activeId={activeConvId}
            onSelect={handleSelectConversation}
            onNew={handleNewChat}
            onDelete={handleDeleteConversation}
            onCloseMobile={() => setSidebarOpen(false)}
            onTriggerPrompt={handleSendMessage}
          />
        </aside>

        {/* Main Canvas */}
        <main className="chat-main">
          {/* Header (Matching Image 1: Circle Left [=], Center Pill, Circle Right [✎]) */}
          <header className="chat-header">
            {/* Left circular toggle button (Image 1) */}
            <div className="header-left">
              <button
                className="chatgpt-circle-icon-btn"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                aria-label="Toggle sidebar"
                title="Toggle sidebar"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
                  <line x1="5" y1="9" x2="19" y2="9" />
                  <line x1="5" y1="15" x2="19" y2="15" />
                </svg>
              </button>
            </div>

            {/* Center Pill (Matching Image 1 without 'Work') */}
            <div className="header-center" ref={mobileMenuRef}>
              <div
                className="chatgpt-center-pill"
                onClick={() => setShowMobileMenu(!showMobileMenu)}
                role="button"
                tabIndex={0}
              >
                <span className="pill-brand-name">SRU Buddy</span>
                <span className="brand-beta-pill">Beta</span>
                <span className="pill-down-arrow">▾</span>
              </div>

              {/* Dropdown Options for Center Pill */}
              {showMobileMenu && (
                <div className="mobile-options-popover">
                  {messages.length > 0 && (
                    <button
                      className="mobile-popover-item"
                      onClick={() => {
                        setShowMobileMenu(false);
                        setShowShareModal(true);
                      }}
                    >
                      <span className="popover-icon">🔗</span>
                      <span>Share Chat Link</span>
                    </button>
                  )}
                  {messages.length > 0 && (
                    <>
                      <button
                        className="mobile-popover-item"
                        onClick={() => {
                          setShowMobileMenu(false);
                          handleExportPDF();
                        }}
                      >
                        <span className="popover-icon">📄</span>
                        <span>Export as PDF / Print</span>
                      </button>
                      <button
                        className="mobile-popover-item"
                        onClick={() => {
                          setShowMobileMenu(false);
                          handleExportMD();
                        }}
                      >
                        <span className="popover-icon">📝</span>
                        <span>Export as Markdown</span>
                      </button>
                    </>
                  )}
                  <button
                    className="mobile-popover-item"
                    onClick={() => {
                      setShowMobileMenu(false);
                      toggleTheme();
                    }}
                  >
                    <span className="popover-icon">{theme === "light" ? "🌙" : "☀️"}</span>
                    <span>{theme === "light" ? "Dark Mode" : "Light Mode"}</span>
                  </button>
                  <button
                    className="mobile-popover-item"
                    onClick={() => {
                      setShowMobileMenu(false);
                      toggleSound();
                    }}
                  >
                    <span className="popover-icon">{soundEnabled ? "🔊" : "🔇"}</span>
                    <span>{soundEnabled ? "Sound: On" : "Sound: Muted"}</span>
                  </button>
                  {onOpenAdmin && (
                    <button
                      className="mobile-popover-item"
                      onClick={() => {
                        setShowMobileMenu(false);
                        onOpenAdmin();
                      }}
                    >
                      <span className="popover-icon">⚙️</span>
                      <span>Admin Console</span>
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Header Right Actions */}
            <div className="header-right">
              {/* Desktop Header Actions */}
              <div className="header-actions desktop-only">
                {/* Share Chat (ChatGPT style) */}
                {messages.length > 0 && (
                  <button
                    className="header-action-pill-btn share-btn"
                    onClick={() => setShowShareModal(true)}
                    title="Share chat link"
                    aria-label="Share chat"
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="18" cy="5" r="3" />
                      <circle cx="6" cy="12" r="3" />
                      <circle cx="18" cy="19" r="3" />
                      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
                      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
                    </svg>
                    <span className="btn-label">Share</span>
                  </button>
                )}

                {/* Export Chat Dropdown */}
                {messages.length > 0 && (
                  <div className="export-menu-container" ref={exportMenuRef}>
                    <button
                      className="header-action-pill-btn export-btn"
                      onClick={() => setShowExportMenu(!showExportMenu)}
                      title="Export chat"
                      aria-label="Export chat"
                      aria-expanded={showExportMenu}
                    >
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                      </svg>
                      <span className="btn-label">Export</span>
                    </button>

                    {showExportMenu && (
                      <div className="export-dropdown-card">
                        <div className="export-dropdown-header">Export Options</div>
                        <button className="export-option-item" onClick={handleExportPDF}>
                          <span className="export-opt-icon">📄</span>
                          <div className="export-opt-text">
                            <span className="export-opt-title">PDF / Print</span>
                            <span className="export-opt-desc">Official university transcript layout</span>
                          </div>
                        </button>
                        <button className="export-option-item" onClick={handleExportMD}>
                          <span className="export-opt-icon">📝</span>
                          <div className="export-opt-text">
                            <span className="export-opt-title">Markdown (.md)</span>
                            <span className="export-opt-desc">Formatted for Notion, Obsidian & notes</span>
                          </div>
                        </button>
                        <button className="export-option-item" onClick={handleExportTXT}>
                          <span className="export-opt-icon">📋</span>
                          <div className="export-opt-text">
                            <span className="export-opt-title">Plain Text (.txt)</span>
                            <span className="export-opt-desc">Clean unformatted text transcript</span>
                          </div>
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* Scholarship Calculator */}
                <button
                  className="calc-nav-pill-btn"
                  onClick={() => setIsCalculatorOpen(true)}
                  title="Fee & Scholarship Calculator"
                  aria-label="Fee & Scholarship Calculator"
                >
                  <span className="calc-nav-icon"><CalculatorIcon size={15} /></span>
                  <span className="calc-nav-text">Calculator</span>
                </button>

                {/* Theme Toggle */}
                <button
                  className="header-icon-btn"
                  onClick={toggleTheme}
                  title={theme === "light" ? "Switch to Dark mode" : "Switch to Light mode"}
                  aria-label="Toggle theme"
                >
                  {theme === "light" ? "🌙" : "☀️"}
                </button>

                {/* Sound Toggle */}
                <button
                  className="header-icon-btn sound-toggle-btn"
                  onClick={toggleSound}
                  title={soundEnabled ? "Mute chimes" : "Enable chimes"}
                  aria-label="Toggle audio"
                >
                  {soundEnabled ? "🔊" : "🔇"}
                </button>

                {/* Admin console */}
                {onOpenAdmin && (
                  <button
                    className="header-icon-btn"
                    onClick={onOpenAdmin}
                    title="Admin console"
                    aria-label="Admin console"
                  >
                    ⚙️
                  </button>
                )}
              </div>

              {/* Circular Right Button (Image 1: Circle with New Chat / Compose Icon) */}
              <button
                className="chatgpt-circle-icon-btn"
                onClick={handleNewChat}
                title="New chat"
                aria-label="New chat"
              >
                <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 20h9" />
                  <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                </svg>
              </button>
            </div>
          </header>

          {/* Messages Canvas */}
          <div
            className="messages-area"
            ref={messagesAreaRef}
            onScroll={handleScroll}
          >
            {/* Shared Chat Snapshot Banner */}
            {isLoadingShared && (
              <div className="shared-chat-banner">
                <div className="shared-chat-info">
                  <span className="shared-chat-pill">Loading</span>
                  <span className="shared-chat-hint">Retrieving shared conversation snapshot...</span>
                </div>
              </div>
            )}

            {isSharedView && (
              <div className="shared-chat-banner">
                <div className="shared-chat-info">
                  <span className="shared-chat-pill">Shared conversation</span>
                  <span className="shared-chat-hint">{sharedTitle || "Read-only preview"}</span>
                </div>
                <button
                  className="shared-continue-btn"
                  onClick={() => setIsSharedView(false)}
                >
                  Continue chat →
                </button>
              </div>
            )}

            {messages.length === 0 && (
              <div className="welcome-screen">
                {/* Minimalist Centered Brand Hero */}
                <div className="welcome-hero-brand">
                  <div className="welcome-hero-logo-box">
                    <img
                      src="/sru-logo.png"
                      alt="SR University"
                      className="welcome-hero-logo"
                    />
                  </div>
                  <div className="welcome-hero-title-row">
                    <h1 className="welcome-hero-title">SRU Buddy</h1>
                    <span className="hero-beta-pill">Beta</span>
                  </div>
                  <p className="welcome-hero-tagline">Your AI agent</p>
                </div>

                {/* 4 Clean Suggestion Cards */}
                <div className="minimal-starters-grid">
                  {MINIMAL_STARTERS.map((item, idx) => (
                    <button
                      key={idx}
                      className="starter-tile"
                      onClick={() => handleSendMessage(item.prompt)}
                      type="button"
                    >
                      <span className="starter-tile-title">{item.title}</span>
                      <span className="starter-tile-desc">{item.desc}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Rendered Messages */}
            {messages.map((msg) => {
              const isMsgStreaming = msg.id === streamingMsgId;

              if (isMsgStreaming && msg.content === "") {
                return (
                  <div key={msg.id} className="message-bubble-row assistant thinking-row">
                    <div className="message-avatar-col">
                      <div className="assistant-avatar-badge" title="SRU Buddy">
                        <img src="/sru-logo.png" alt="SRU" className="assistant-avatar-img" />
                      </div>
                    </div>
                    <div className="message-content-col">
                      <div className="message-text-bubble assistant">
                        <ThinkingIndicator />
                      </div>
                    </div>
                  </div>
                );
              }

              return (
                <MessageBubble
                  key={msg.id}
                  role={msg.role}
                  content={msg.content}
                  sources={undefined}
                  suggestions={msg.suggestions}
                  cards={msg.cards}
                  flow={msg.flow}
                  messageId={msg.id}
                  conversationId={activeConvId}
                  sessionId={sessionId}
                  createdAt={msg.created_at}
                  isStreaming={isMsgStreaming}
                  onSuggestionClick={handleSendMessage}
                />
              );
            })}

            {error && (() => {
              const getErrorDetails = (err: string) => {
                if (err.includes("Failed to fetch") || err.includes("NetworkError")) {
                  return {
                    title: "Server is connecting",
                    desc: "Backend service is spinning up. Please tap retry in a few seconds.",
                  };
                }
                if (err.includes("401") || err.includes("Unauthorized") || err.includes("Forbidden") || err.includes("generativelanguage")) {
                  return {
                    title: "AI service temporarily busy",
                    desc: "Unable to reach the AI service. Please tap retry to switch to an active key.",
                  };
                }
                if (err.includes("429") || err.includes("quota") || err.includes("rate limit")) {
                  return {
                    title: "High traffic",
                    desc: "The AI agent is receiving many requests. Please wait a moment and tap retry.",
                  };
                }
                return {
                  title: "Connection issue",
                  desc: "Something went wrong processing your request. Please tap retry.",
                };
              };
              const { title, desc } = getErrorDetails(error);
              return (
                <div className="error-toast-card">
                  <div className="error-toast-content">
                    <span className="error-toast-icon">⚡</span>
                    <div className="error-toast-text">
                      <span className="error-toast-title">{title}</span>
                      <span className="error-toast-desc">{desc}</span>
                    </div>
                  </div>
                  <button
                    className="error-retry-action-btn"
                    onClick={() => {
                      const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
                      if (lastUserMsg) {
                        setError(null);
                        handleSendMessage(lastUserMsg.content);
                      }
                    }}
                    type="button"
                  >
                    Retry ↻
                  </button>
                </div>
              );
            })()}

            <div ref={messagesEndRef} />
          </div>

          {/* Scroll-to-bottom FAB */}
          {showScrollBottom && (
            <button
              className={`scroll-bottom-fab ${streamingMsgId ? "is-streaming" : ""}`}
              onClick={() => scrollToBottom(true)}
              title="Scroll to latest message"
              aria-label="Scroll to bottom"
            >
              ↓
              {streamingMsgId && <span className="fab-unread-dot" />}
            </button>
          )}

          {/* Bottom Chat Input (ChatGPT/Gemini style with Stop generating & free typing) */}
          <ChatInput
            onSend={handleSendMessage}
            isLoading={isLoading}
            onStop={handleStopStreaming}
            disabled={false}
          />
        </main>
      </div>

      {/* ChatGPT-style Share Modal */}
      {showShareModal && (
        <ShareModal
          conversationId={activeConvId}
          title={activeChatTitle}
          messages={messages}
          onClose={() => setShowShareModal(false)}
          onExportPDF={handleExportPDF}
          onExportMD={handleExportMD}
        />
      )}

      {/* Scholarship Calculator Modal */}
      {isCalculatorOpen && (
        <ScholarshipCalculatorModal
          onClose={() => setIsCalculatorOpen(false)}
          onAskBuddy={(prompt) => {
            setIsCalculatorOpen(false);
            handleSendMessage(prompt);
          }}
        />
      )}

      {/* Prospective Student Authentication Modal */}
      <LeadAuthModal
        isOpen={showLeadAuthModal}
        onClose={() => {
          setShowLeadAuthModal(false);
          setPendingAuthMessage(null);
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
    </div>
  );
}
