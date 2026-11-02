import { useState, useEffect, useRef } from "react";
import MessageBubble from "../components/MessageBubble";
import ChatInput from "../components/ChatInput";
import ConversationList from "../components/ConversationList";
import ThinkingIndicator from "../components/ThinkingIndicator";
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

const QUICK_STARTERS = [
  {
    category: "admissions",
    icon: "🧭",
    title: "Admission 2026 Wizard",
    desc: "Step-by-step guided eligibility & registration checklist",
    prompt: "I want admission - start the admission wizard",
  },
  {
    category: "academics",
    icon: "🆚",
    title: "CSE vs CSE (AI/ML)",
    desc: "Side-by-side branch curriculum & career scope comparison",
    prompt: "Compare CSE vs CSE with AI/ML specialization",
  },
  {
    category: "fees",
    icon: "💰",
    title: "Fee & Scholarships",
    desc: "Tuition, hostel, mess fees & merit scholarship tiers",
    prompt: "What is the complete annual fee structure and scholarship for B.Tech?",
  },
  {
    category: "campus",
    icon: "🏠",
    title: "Hostel Rules & Curfew",
    desc: "Room types, mess schedule, night curfew & out-pass rules",
    prompt: "What are the hostel rules, mess food details, and curfew timings?",
  },
  {
    category: "tours",
    icon: "🎥",
    title: "Virtual Campus Tour",
    desc: "Watch official campus walkthrough, hostels & SRiX incubator",
    prompt: "Show me official video tours of SR University campus, hostels, and facilities",
  },
  {
    category: "academics",
    icon: "📊",
    title: "Placement Records",
    desc: "Highest packages, top recruiters, and placement statistics",
    prompt: "Tell me about SR University placement records, top recruiters, and highest package",
  },
];

const CATEGORY_TABS = [
  { id: "all", label: "🌟 All Topics" },
  { id: "admissions", label: "📝 Admissions" },
  { id: "fees", label: "💰 Fees" },
  { id: "academics", label: "🎓 Academics" },
  { id: "campus", label: "🏨 Hostels" },
  { id: "tours", label: "🎥 Video Tours" },
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
  const [selectedCategory, setSelectedCategory] = useState("all");

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

  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("sru_theme", theme);
  }, [theme]);

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, []);

  // Track scroll position to toggle the scroll-to-bottom FAB
  const handleScroll = () => {
    if (!messagesAreaRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = messagesAreaRef.current;
    const isScrolledUp = scrollHeight - scrollTop - clientHeight > 160;
    setShowScrollBottom(isScrolledUp);
  };

  // Scroll smoothly or instantly to bottom
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

  const filteredStarters =
    selectedCategory === "all"
      ? QUICK_STARTERS
      : QUICK_STARTERS.filter((s) => s.category === selectedCategory);

  return (
    <div className={`chat-page theme-${theme}`}>
      {/* Official Top Notice Bar */}
      <div className="official-top-banner" role="banner">
        <span className="banner-badge">🏛️ SR UNIVERSITY</span>
        <span className="banner-text">
          NIRF Ranked • Admissions 2026 Open • Official AI Campus Companion
        </span>
        <a
          href="https://sru.edu.in"
          target="_blank"
          rel="noopener noreferrer"
          className="banner-link"
        >
          sru.edu.in ↗
        </a>
      </div>

      {/* Mobile Drawer Backdrop Overlay */}
      {sidebarOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Main Wrapper: Sidebar + Chat Area */}
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

        {/* Main Chat Canvas */}
        <main className="chat-main">
          {/* Header */}
          <header className="chat-header">
            <button
              className="header-icon-btn toggle-sidebar-btn"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label="Toggle sidebar"
              title="Toggle sidebar"
            >
              <span className="hamburger-icon">☰</span>
            </button>

            {/* Official Logo & Portal Title */}
            <div className="header-brand-group">
              <img
                src="/sru-logo.png"
                alt="SR University Logo"
                className="header-sru-logo"
              />
              <div className="header-title-column">
                <div className="header-title-row">
                  <h1 className="header-title">SR University</h1>
                  <span className="header-status-badge">
                    <span className="status-dot"></span> Online
                  </span>
                </div>
                <p className="header-subtitle">
                  AI Companion & Official Knowledge Portal
                </p>
              </div>
            </div>

            {/* Header Right Actions */}
            <div className="header-actions">
              <a
                href="https://sru.edu.in"
                target="_blank"
                rel="noopener noreferrer"
                className="header-web-link-btn"
                title="Visit Official Website"
              >
                <span className="web-link-icon">🌐</span>
                <span className="web-link-text">sru.edu.in</span>
              </a>

              <button
                className="header-icon-btn"
                onClick={toggleSound}
                title={soundEnabled ? "Mute audio chimes" : "Enable audio chimes"}
                aria-label="Toggle sound"
              >
                {soundEnabled ? "🔊" : "🔇"}
              </button>

              <button
                className="header-icon-btn"
                onClick={toggleTheme}
                title={theme === "light" ? "Switch to Midnight Navy mode" : "Switch to Light mode"}
                aria-label="Toggle theme"
              >
                {theme === "light" ? "🌙" : "☀️"}
              </button>

              {onOpenAdmin && (
                <button
                  className="header-admin-btn"
                  onClick={onOpenAdmin}
                  title="Open Knowledge & Admin Console"
                >
                  ⚙️ Admin
                </button>
              )}
            </div>
          </header>

          {/* Messages Scroll Area */}
          <div
            className="messages-area"
            ref={messagesAreaRef}
            onScroll={handleScroll}
          >
            {messages.length === 0 && (
              <div className="welcome-screen">
                {/* Official Crest Hero */}
                <div className="welcome-crest-hero">
                  <div className="welcome-logo-badge">
                    <img
                      src="/sru-logo.png"
                      alt="SR University"
                      className="welcome-main-logo"
                    />
                  </div>
                  <div className="welcome-verify-pill">
                    <span className="verify-shield">🛡️</span>
                    <span>Official University Knowledge System</span>
                  </div>
                </div>

                <h2 className="welcome-title">SR University AI Companion</h2>
                <p className="welcome-text">
                  Your 24/7 intelligent guide for admissions, academic regulations,
                  scholarships, hostel living, and campus life at SR University, Warangal.
                </p>

                {/* Accreditation & Stats Bar */}
                <div className="welcome-stats-bar">
                  <div className="stat-pill">
                    <span className="stat-icon">🏆</span>
                    <span className="stat-label">NAAC 'A+' Grade</span>
                  </div>
                  <div className="stat-pill">
                    <span className="stat-icon">📈</span>
                    <span className="stat-label">NIRF Ranked</span>
                  </div>
                  <div className="stat-pill">
                    <span className="stat-icon">💡</span>
                    <span className="stat-label">SRiX Technology Hub</span>
                  </div>
                  <div className="stat-pill">
                    <span className="stat-icon">🎓</span>
                    <span className="stat-label">UGC / AICTE Approved</span>
                  </div>
                </div>

                {/* Category Filter Chips */}
                <div className="welcome-category-tabs" role="tablist">
                  {CATEGORY_TABS.map((tab) => (
                    <button
                      key={tab.id}
                      className={`cat-tab-btn ${selectedCategory === tab.id ? "active" : ""}`}
                      onClick={() => setSelectedCategory(tab.id)}
                      type="button"
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                {/* Interactive Quick Starters Grid */}
                <div className="quick-starters-grid">
                  {filteredStarters.map((item, idx) => (
                    <button
                      key={idx}
                      className="starter-card"
                      onClick={() => handleSendMessage(item.prompt)}
                      type="button"
                    >
                      <div className="starter-icon">{item.icon}</div>
                      <div className="starter-content">
                        <div className="starter-title">{item.title}</div>
                        <div className="starter-desc">{item.desc}</div>
                      </div>
                      <span className="starter-arrow">→</span>
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
                        <span className="buddy-online-indicator"></span>
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

          {/* Scroll-to-bottom Floating Action Button */}
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
    </div>
  );
}
