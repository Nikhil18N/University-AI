const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8080").replace(/\/$/, "");

/**
 * API client for the University AI Companion backend.
 * No authentication — all requests use session_id for tracking.
 */

export interface SourceReference {
  document_id: string;
  title: string;
  page?: number;
  department?: string;
  effective_date?: string;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  answer: string;
  sources: SourceReference[];
  model?: string;
}

export interface MessageData {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceReference[];
  model?: string;
  created_at: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string;
  messages: MessageData[];
  created_at: string;
}

/**
 * Send a chat message to the backend.
 */
async function handleResponse<T>(res: Response, fallbackError: string): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || fallbackError);
  }
  return res.json();
}

function handleNetworkError(err: unknown, fallback: string): never {
  if (err instanceof TypeError && err.message.toLowerCase().includes("fetch")) {
    throw new Error(`Cannot connect to backend server at ${API_BASE}. Make sure the backend is running.`);
  }
  throw err instanceof Error ? err : new Error(fallback);
}

export async function sendMessage(
  sessionId: string,
  message: string,
  conversationId?: string | null
): Promise<ChatResponse> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        message,
        conversation_id: conversationId || null,
      }),
    });
    return await handleResponse<ChatResponse>(res, "Failed to send message");
  } catch (err) {
    handleNetworkError(err, "Failed to send message");
  }
}

/**
 * List all conversations for a session.
 */
export async function listConversations(
  sessionId: string
): Promise<ConversationSummary[]> {
  try {
    const res = await fetch(
      `${API_BASE}/api/v1/conversations?session_id=${encodeURIComponent(sessionId)}`
    );
    return await handleResponse<ConversationSummary[]>(res, "Failed to load conversations");
  } catch (err) {
    handleNetworkError(err, "Failed to load conversations");
  }
}

/**
 * Get a conversation with all messages.
 */
export async function getConversation(
  conversationId: string,
  sessionId: string
): Promise<ConversationDetail> {
  try {
    const res = await fetch(
      `${API_BASE}/api/v1/conversations/${conversationId}?session_id=${encodeURIComponent(sessionId)}`
    );
    return await handleResponse<ConversationDetail>(res, "Failed to load conversation");
  } catch (err) {
    handleNetworkError(err, "Failed to load conversation");
  }
}

/**
 * Delete a conversation.
 */
export async function deleteConversation(
  conversationId: string,
  sessionId: string
): Promise<void> {
  try {
    const res = await fetch(
      `${API_BASE}/api/v1/conversations/${conversationId}?session_id=${encodeURIComponent(sessionId)}`,
      { method: "DELETE" }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to delete conversation");
    }
  } catch (err) {
    handleNetworkError(err, "Failed to delete conversation");
  }
}

// ---- Admin API ----

export interface DocumentItem {
  id: string;
  title: string;
  document_type: string;
  department: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AdminStats {
  total_documents: number;
  active_documents: number;
  total_conversations: number;
  total_messages: number;
  positive_feedback: number;
  negative_feedback: number;
}

export interface FeedbackItem {
  id: string;
  session_id: string;
  conversation_id: string;
  message_id: string;
  rating: number;
  comment: string | null;
  created_at: string;
}

export async function fetchAdminStats(adminKey: string): Promise<AdminStats> {
  const res = await fetch(`${API_BASE}/api/v1/admin/stats`, {
    headers: { "X-Admin-Key": adminKey },
  });
  if (!res.ok) throw new Error("Invalid admin key or server error");
  return res.json();
}

export async function fetchAdminDocuments(adminKey: string): Promise<{ documents: DocumentItem[]; total: number }> {
  const res = await fetch(`${API_BASE}/api/v1/admin/documents`, {
    headers: { "X-Admin-Key": adminKey },
  });
  if (!res.ok) throw new Error("Failed to fetch documents");
  return res.json();
}

export async function uploadDocument(adminKey: string, formData: FormData): Promise<DocumentItem> {
  const res = await fetch(`${API_BASE}/api/v1/admin/documents`, {
    method: "POST",
    headers: { "X-Admin-Key": adminKey },
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to upload document");
  }
  return res.json();
}

export async function deactivateDocument(adminKey: string, documentId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/admin/documents/${documentId}`, {
    method: "DELETE",
    headers: { "X-Admin-Key": adminKey },
  });
  if (!res.ok) throw new Error("Failed to deactivate document");
}

export async function fetchAdminFeedback(adminKey: string): Promise<{ items: FeedbackItem[]; total: number }> {
  const res = await fetch(`${API_BASE}/api/v1/admin/feedback`, {
    headers: { "X-Admin-Key": adminKey },
  });
  if (!res.ok) throw new Error("Failed to fetch feedback");
  return res.json();
}
