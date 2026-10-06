import { useState, useEffect, useRef } from "react";
import MessageBubble from "../components/MessageBubble";
import ChatInput from "../components/ChatInput";
import ConversationList from "../components/ConversationList";
import { getSessionId } from "../hooks/useSession";
import {
  sendMessage,
  listConversations,
  getConversation,
  deleteConversation,
  type ConversationSummary,
  type MessageData,
} from "../services/api";
import "./ChatPage.css";

interface Props {
  onOpenAdmin?: () => void;
}

export default function ChatPage({ onOpenAdmin }: Props) {
  const sessionId = getSessionId();

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function loadConversations() {
    try {
      const convs = await listConversations(sessionId);
      setConversations(convs);
    } catch {
      // Silently fail on first load
    }
  }

  async function handleSelectConversation(convId: string) {
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

  async function handleSendMessage(text: string) {
    setIsLoading(true);
    setError(null);

    // Optimistically add user message
    const tempUserMsg: MessageData = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const response = await sendMessage(sessionId, text, activeConvId);

      // Update conversation ID (may be new)
      if (!activeConvId) {
        setActiveConvId(response.conversation_id);
      }

      // Add assistant response
      const assistantMsg: MessageData = {
        id: response.message_id,
        role: "assistant",
        content: response.answer,
        sources: response.sources.length > 0 ? response.sources : undefined,
        model: response.model ?? undefined,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // Refresh conversation list
      await loadConversations();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      // Remove optimistic message on error
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="chat-page">
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
        {/* Header */}
        <header className="chat-header">
          <button
            className="toggle-sidebar-btn"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Toggle sidebar"
          >
            ☰
          </button>
          <div className="header-info">
            <h1 className="header-title">🎓 University AI Companion</h1>
            <p className="header-subtitle">
              Ask me anything about the university
            </p>
          </div>
          {onOpenAdmin && (
            <button
              className="toggle-sidebar-btn"
              onClick={onOpenAdmin}
              title="Open Admin Console"
              style={{ fontSize: "0.85rem", padding: "6px 12px", width: "auto", borderRadius: "8px", border: "1px solid var(--border)", background: "var(--surface-2)", color: "var(--text-1)", cursor: "pointer" }}
            >
              ⚙️ Admin
            </button>
          )}
        </header>

        {/* Messages */}
        <div className="messages-area">
          {messages.length === 0 && (
            <div className="welcome-screen">
              <div className="welcome-emoji">🎓</div>
              <h2 className="welcome-title">Welcome!</h2>
              <p className="welcome-text">
                I'm your University AI Companion. Ask me about exams, fees,
                courses, hostel rules, or just say hello!
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              role={msg.role}
              content={msg.content}
              sources={msg.sources}
              messageId={msg.id}
              conversationId={activeConvId}
              sessionId={sessionId}
            />
          ))}

          {isLoading && (
            <div className="message-bubble assistant">
              <div className="message-avatar">🎓</div>
              <div className="message-body">
                <div className="message-content typing-indicator">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          )}

          {error && <div className="error-toast">{error}</div>}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <ChatInput onSend={handleSendMessage} disabled={isLoading} />
      </main>
    </div>
  );
}
