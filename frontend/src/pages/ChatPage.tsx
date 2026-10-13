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
    icon: "🧭",
    title: "Admission Wizard",
    desc: "Step-by-step guided admission & eligibility check",
    prompt: "I want admission - start the admission wizard",
  },
  {
    icon: "🆚",
    title: "CSE vs CSE (AI/ML)",
    desc: "Side-by-side branch curriculum & career comparison",
    prompt: "Compare CSE vs CSE with AI/ML specialization",
  },
  {
    icon: "💰",
    title: "Fee Structure",
    desc: "Detailed tuition, hostel, mess & scholarship breakdown",
    prompt: "What is the complete annual fee structure for B.Tech?",
  },
  {
    icon: "🏠",
    title: "Hostels & Campus",
    desc: "Living facilities, mess food, timings & student clubs",
    prompt: "Tell me about hostel rooms, mess food, and campus life",
  },
];

export default function ChatPage({ onOpenAdmin }: Props) {
  const sessionId = getSessionId();

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

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
      // During active token streaming, stick instantly to bottom without animation jitter
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
            m.id === assistantMsgId
              ? { ...m, content: accumulatedContent }
              : m
          )
        );
      },
      onDone: (data: ChatResponse) => {
        setIsLoading(false);
        setStreamingMsgId(null);
        cancelStreamRef.current = null;

        // Sound chime if enabled
        if (soundEnabled) {
          playChime();
        }

        // Trigger celebration confetti if eligible or celebratory
        const ansLower = (data.answer || "").toLowerCase();
        if (
          ansLower.includes("fully eligible") ||
          ansLower.includes("admission verdict: fully eligible") ||
          ansLower.includes("you are eligible") ||
          ansLower.includes("congratulations")
        ) {
          triggerConfetti();
        }

        // Finalize assistant message with full metadata
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
        // Remove empty placeholder if nothing was streamed
        setMessages((prev) =>
          prev.filter((m) => m.id !== assistantMsgId || accumulatedContent.length > 0)
        );
      },
    });

    cancelStreamRef.current = cancelFn;
  }

  return (
    <div className={`chat-page theme-${theme}`}>
      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? "open" : "closed"}`}>
        <ConversationList
          conversations={conversations}
          activeId={activeConvId}
          onSelect={handleSelectConversation}
          onNew={handleNewChat}
          onDelete={handleDeleteConversation}
        />
      </aside>

      {/* Main chat area */}
      <main className="chat-main">
        {/* Glassmorphism Header */}
        <header className="chat-header">
          <button
            className="header-icon-btn toggle-sidebar-btn"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Toggle sidebar"
            title="Toggle sidebar"
          >
            ☰
          </button>

          <div className="header-info">
            <div className="header-title-row">
              <span className="header-mascot">🎓</span>
              <h1 className="header-title">SRU Buddy</h1>
              <span className="header-status-badge">
                <span className="status-dot"></span> Online
              </span>
            </div>
            <p className="header-subtitle">
              SR University Official AI Companion & Senior Guide
            </p>
          </div>

          <div className="header-actions">
            <button
              className="header-icon-btn"
              onClick={toggleSound}
              title={soundEnabled ? "Sound enabled (Click to mute)" : "Sound muted (Click to enable)"}
            >
              {soundEnabled ? "🔊" : "🔇"}
            </button>

            <button
              className="header-icon-btn"
              onClick={toggleTheme}
              title={theme === "light" ? "Switch to Dark Mode" : "Switch to Light Mode"}
            >
              {theme === "light" ? "🌙" : "☀️"}
            </button>

            {onOpenAdmin && (
              <button
                className="header-admin-btn"
                onClick={onOpenAdmin}
                title="Open Admin Console"
              >
                ⚙️ Admin
              </button>
            )}
          </div>
        </header>

        {/* Messages scroll area */}
        <div
          className="messages-area"
          ref={messagesAreaRef}
          onScroll={handleScroll}
        >
          {messages.length === 0 && (
            <div className="welcome-screen">
              <div className="welcome-mascot-container">
                <div className="welcome-mascot-ring">
                  <span className="welcome-mascot-emoji">🎓</span>
                </div>
              </div>
              <h2 className="welcome-title">Hey there! I'm SRU Buddy 👋</h2>
              <p className="welcome-text">
                Your friendly senior guide for SR University. Ask me about admissions,
                compare branches, check fee structures, or explore campus life!
              </p>

              {/* Interactive Quick Starters */}
              <div className="quick-starters-grid">
                {QUICK_STARTERS.map((item, idx) => (
                  <button
                    key={idx}
                    className="starter-card"
                    onClick={() => handleSendMessage(item.prompt)}
                  >
                    <div className="starter-icon">{item.icon}</div>
                    <div className="starter-content">
                      <div className="starter-title">{item.title}</div>
                      <div className="starter-desc">{item.desc}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => {
            const isMsgStreaming = msg.id === streamingMsgId;

            // When streaming message has not received its first token yet, display thinking state inline
            if (isMsgStreaming && msg.content === "") {
              return (
                <div key={msg.id} className="message-bubble assistant thinking-bubble">
                  <div className="message-avatar">
                    <div className="sru-buddy-avatar pulse">
                      <span className="buddy-icon">🎓</span>
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

        {/* Input */}
        <ChatInput onSend={handleSendMessage} disabled={isLoading} />
      </main>
    </div>
  );
}
