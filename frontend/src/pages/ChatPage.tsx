import { useState, useEffect, useRef } from "react";
import MessageBubble from "../components/MessageBubble";
import ChatInput from "../components/ChatInput";
import ConversationList from "../components/ConversationList";
import ThinkingIndicator from "../components/ThinkingIndicator";
import ShareModal from "../components/ShareModal";
import { exportToPDF, exportToMarkdown, exportToText } from "../utils/exportChat";
import { getSessionId } from "../hooks/useSession";
import {
  sendMessageStream,
  listConversations,
  getConversation,
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

  // Theme & Sound states
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    return (localStorage.getItem("sru_theme") as "light" | "dark") || "light";
  });
  const [soundEnabled, setSoundEnabled] = useState<boolean>(() => {
    return localStorage.getItem("sru_sound") !== "false";
  });

  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const [streamingMsgId, setStreamingMsgId] = useState<string | null>(null);

  const messagesAreaRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const cancelStreamRef = useRef<(() => void) | null>(null);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("sru_theme", theme);
  }, [theme]);

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, []);

  // Close export dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        exportMenuRef.current &&
        !exportMenuRef.current.contains(event.target as Node)
      ) {
        setShowExportMenu(false);
      }
    }
    if (showExportMenu) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showExportMenu]);

  // Track scroll position to toggle scroll-to-bottom button
  const handleScroll = () => {
    if (!messagesAreaRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = messagesAreaRef.current;
    const isScrolledUp = scrollHeight - scrollTop - clientHeight > 160;
    setShowScrollBottom(isScrolledUp);
  };

  const scrollToBottom = (instant: boolean = false) => {
    if (instant && messagesAreaRef.current) {
      messagesAreaRef.current.scrollTop = messagesAreaRef.current.scrollHeight;
    } else {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  };

  useEffect(() => {
    if (!showScrollBottom) {
      scrollToBottom(Boolean(streamingMsgId));
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
    try {
      const detail = await getConversation(convId, sessionId);
      setMessages(detail.messages);
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
    setError(null);
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

  async function handleSendMessage(text: string) {
    if (isLoading) return;

    setIsLoading(true);
    setError(null);

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
                  sources: data.sources?.length ? data.sources : undefined,
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
        <aside className={`sidebar ${sidebarOpen ? "open" : "closed"}`}>
          <ConversationList
            conversations={conversations}
            activeId={activeConvId}
            onSelect={handleSelectConversation}
            onNew={handleNewChat}
            onDelete={handleDeleteConversation}
            onCloseMobile={() => setSidebarOpen(false)}
          />
        </aside>

        {/* Main Canvas */}
        <main className="chat-main">
          {/* Header */}
          <header className="chat-header">
            <div className="header-left">
              <button
                className="header-icon-btn toggle-sidebar-btn"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                aria-label="Toggle sidebar"
                title="Toggle sidebar"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </svg>
              </button>

              <button
                className="header-icon-btn new-chat-header-btn"
                onClick={handleNewChat}
                aria-label="New chat"
                title="New chat"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 5v14M5 12h14" />
                </svg>
              </button>

              {/* Brand Branding */}
              <div className="header-brand-group">
                <img
                  src="/sru-logo.png"
                  alt="SRU Logo"
                  className="header-sru-logo"
                />
                <div className="header-brand-text">
                  <span className="header-title">SRU Buddy</span>
                  <span className="header-tagline">Your AI agent</span>
                </div>
              </div>
            </div>

            {/* Header Right Actions */}
            <div className="header-actions">
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
          </header>

          {/* Messages Canvas */}
          <div
            className="messages-area"
            ref={messagesAreaRef}
            onScroll={handleScroll}
          >
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
                  <h1 className="welcome-hero-title">SRU Buddy</h1>
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
                  <div key={msg.id} className="message-bubble assistant thinking-bubble">
                    <div className="message-avatar">
                      <div className="sru-buddy-avatar pulse">
                        <img src="/sru-logo.png" alt="SRU" className="buddy-logo-img" />
                      </div>
                    </div>
                    <div className="message-body">
                      <div className="message-content thinking-content-box">
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
                  sources={msg.sources}
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

            {error && <div className="error-toast">{error}</div>}

            <div ref={messagesEndRef} />
          </div>

          {/* Scroll-to-bottom FAB */}
          {showScrollBottom && (
            <button
              className="scroll-bottom-fab"
              onClick={() => scrollToBottom()}
              title="Scroll to latest message"
              aria-label="Scroll to bottom"
            >
              ↓
            </button>
          )}

          {/* Bottom Chat Input */}
          <ChatInput onSend={handleSendMessage} disabled={isLoading} />
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
    </div>
  );
}
