const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8080").replace(/\/$/, "");

/**
 * API client for the University AI Companion backend.
 * No authentication — all requests use session_id for tracking.
 */

export interface SourceReference {
  document_id: string;
  title: string;
  section?: string;
  page?: number;
  page_url?: string;
  department?: string;
  effective_date?: string;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  answer: string;
  sources: SourceReference[];
  suggestions?: string[];
  cards?: any[];
  flow?: any;
  model?: string;
}

export interface MessageData {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceReference[];
  suggestions?: string[];
  cards?: any[];
  flow?: any;
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
 * Send a chat message with Server-Sent Events (SSE) streaming tokens in real time.
 */
export function sendMessageStream(
  sessionId: string,
  message: string,
  conversationId: string | null | undefined,
  callbacks: {
    onStart?: (conversationId: string) => void;
    onToken?: (delta: string) => void;
    onDone?: (data: ChatResponse) => void;
    onError?: (error: Error) => void;
  }
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          message,
          conversation_id: conversationId || null,
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to stream message");
      }

      if (!res.body) {
        throw new Error("No response stream available");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data: ")) continue;
          const jsonStr = trimmed.slice(6);
          let parsed: any;
          try {
            parsed = JSON.parse(jsonStr);
          } catch {
            // Ignore partial frames
            continue;
          }

          if (parsed.type === "start") {
            callbacks.onStart?.(parsed.conversation_id);
          } else if (parsed.type === "token") {
            callbacks.onToken?.(parsed.delta);
          } else if (parsed.type === "done") {
            callbacks.onDone?.(parsed);
          } else if (parsed.type === "error") {
            throw new Error(parsed.detail || "Error streaming response");
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error)?.name === "AbortError") return;
      let errorObj = err instanceof Error ? err : new Error(String(err));
      if (errorObj.message.includes("Failed to fetch")) {
        errorObj = new Error("Connection timed out (backend is waking up from sleep). Please tap Retry.");
      }
      callbacks.onError?.(errorObj);
    }
  })();

  return () => controller.abort();
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
 * Load a public shared conversation snapshot without requiring session_id.
 */
export async function getSharedConversation(
  conversationId: string
): Promise<ConversationDetail> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/shared/${conversationId}`);
    return await handleResponse<ConversationDetail>(res, "Failed to load shared conversation");
  } catch (err) {
    handleNetworkError(err, "Failed to load shared conversation");
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

export interface FeedbackPayload {
  session_id: string;
  conversation_id: string;
  message_id: string;
  rating: number;
  comment?: string;
}

export async function submitFeedback(
  payload: FeedbackPayload
): Promise<{ id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/v1/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to submit feedback");
  }
  return res.json();
}

export interface FeedbackItem {
  id: string;
  session_id: string;
  conversation_id: string;
  message_id: string;
  rating: number;
  comment: string | null;
  question?: string | null;
  answer?: string | null;
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

export interface AdminConversationItem {
  id: string;
  session_id: string;
  title: string;
  message_count: number;
  user_message_count: number;
  assistant_message_count: number;
  positive_feedback_count: number;
  negative_feedback_count: number;
  created_at: string;
  updated_at: string;
  last_message_preview: string | null;
}

export interface AdminMessageFeedback {
  id: string;
  rating: number;
  comment: string | null;
  created_at: string;
}

export interface AdminMessageDetail {
  id: string;
  role: "user" | "assistant";
  content: string;
  model: string | null;
  sources: Array<{
    document_id: string;
    title: string;
    section?: string | null;
    page?: number | null;
    page_url?: string | null;
    department?: string | null;
  }> | null;
  feedback: AdminMessageFeedback | null;
  created_at: string;
}

export interface AdminConversationDetail {
  id: string;
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: AdminMessageDetail[];
}

export interface AdminConversationsResponse {
  conversations: AdminConversationItem[];
  total: number;
  page: number;
  page_size: number;
}

export async function fetchAdminConversations(
  adminKey: string,
  params: {
    page?: number;
    pageSize?: number;
    search?: string;
    feedbackFilter?: string;
  } = {}
): Promise<AdminConversationsResponse> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.pageSize) query.set("page_size", String(params.pageSize));
  if (params.search) query.set("search", params.search);
  if (params.feedbackFilter) query.set("feedback_filter", params.feedbackFilter);

  const res = await fetch(`${API_BASE}/api/v1/admin/conversations?${query.toString()}`, {
    headers: { "X-Admin-Key": adminKey },
  });
  if (!res.ok) throw new Error("Failed to fetch conversations");
  return res.json();
}

export async function fetchAdminConversationDetail(
  adminKey: string,
  conversationId: string
): Promise<AdminConversationDetail> {
  const res = await fetch(`${API_BASE}/api/v1/admin/conversations/${conversationId}`, {
    headers: { "X-Admin-Key": adminKey },
  });
  if (!res.ok) throw new Error("Failed to fetch conversation details");
  return res.json();
}

export async function deleteAdminConversation(
  adminKey: string,
  conversationId: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/admin/conversations/${conversationId}`, {
    method: "DELETE",
    headers: { "X-Admin-Key": adminKey },
  });
  if (!res.ok) throw new Error("Failed to delete conversation");
}

export async function promoteExemplar(
  adminKey: string,
  payload: { message_id: string; question: string; answer: string }
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/api/v1/admin/exemplars/promote`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Key": adminKey,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to promote exemplar");
  }
  return res.json();
}

export async function downloadAllConversations(
  adminKey: string,
  format: "markdown" | "json" = "markdown",
  filters?: { search?: string; feedbackFilter?: string }
): Promise<void> {
  const query = new URLSearchParams();
  query.set("format", format);
  if (filters?.search) query.set("search", filters.search);
  if (filters?.feedbackFilter && filters.feedbackFilter !== "all") {
    query.set("feedback_filter", filters.feedbackFilter);
  }

  const res = await fetch(`${API_BASE}/api/v1/admin/conversations/export?${query.toString()}`, {
    headers: { "X-Admin-Key": adminKey },
  });
  if (!res.ok) throw new Error("Failed to export conversations dataset");

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const ext = format === "json" ? "json" : "md";
  a.download = `university_ai_student_chats_${new Date().toISOString().slice(0, 10)}.${ext}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export interface EvaluationRecordItem {
  id: string;
  test_id: string | null;
  category: string | null;
  question: string;
  expected_answer: string | null;
  actual_answer: string;
  groundedness_score: number;
  latency_ms: number | null;
  passed: boolean;
  created_at: string | null;
}

export interface EvaluationListResponse {
  total: number;
  page: number;
  page_size: number;
  records: EvaluationRecordItem[];
}

export async function fetchAdminEvaluations(
  adminKey: string,
  page: number = 1,
  pageSize: number = 50
): Promise<EvaluationListResponse> {
  const res = await fetch(
    `${API_BASE}/api/v1/admin/evaluations?page=${page}&page_size=${pageSize}`,
    {
      headers: { "X-Admin-Key": adminKey },
    }
  );
  if (!res.ok) throw new Error("Failed to load evaluation records");
  return res.json();
}

export async function runAdminBenchmark(adminKey: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/admin/evaluations/run`, {
    method: "POST",
    headers: { "X-Admin-Key": adminKey },
  });
  if (!res.ok) throw new Error("Failed to run benchmark suite");
  return res.json();
}

// ---- Prospective Leads API ----

export interface ProspectiveLeadItem {
  id: string;
  name: string;
  phone: string;
  email: string | null;
  program_interest: string | null;
  score: string | null;
  exam_type: string | null;
  source: string;
  conversation_id: string | null;
  status: string;
  created_at: string;
  metadata?: any;
}

export interface LeadListResponse {
  total: number;
  items: ProspectiveLeadItem[];
  leads?: ProspectiveLeadItem[];
}

export interface LeadStats {
  total_leads: number;
  chat_leads: number;
  calculator_leads: number;
  today_leads: number;
  enrolled_leads: number;
}

export interface CreateLeadPayload {
  name: string;
  phone: string;
  email?: string;
  program_interest?: string;
  score?: string;
  exam_type?: string;
  source?: string;
  conversation_id?: string;
  metadata?: any;
}

export async function createLead(payload: CreateLeadPayload): Promise<ProspectiveLeadItem> {
  const res = await fetch(`${API_BASE}/api/v1/leads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to register lead");
  }
  return res.json();
}

export async function fetchAdminLeads(
  adminKey: string,
  params: {
    page?: number;
    pageSize?: number;
    search?: string;
    program?: string;
    source?: string;
    status?: string;
  } = {}
): Promise<LeadListResponse> {
  const searchParams = new URLSearchParams();
  if (params.page) searchParams.set("page", String(params.page));
  if (params.pageSize) searchParams.set("page_size", String(params.pageSize));
  if (params.search) searchParams.set("search", params.search);
  if (params.program) searchParams.set("program", params.program);
  if (params.source) searchParams.set("source", params.source);
  if (params.status) searchParams.set("status", params.status);

  const res = await fetch(`${API_BASE}/api/v1/admin/leads?${searchParams.toString()}`, {
    headers: { "X-Admin-Key": adminKey },
  });
  if (!res.ok) throw new Error("Failed to load prospective leads");
  return res.json();
}

export async function fetchAdminLeadStats(adminKey: string): Promise<LeadStats> {
  const res = await fetch(`${API_BASE}/api/v1/admin/leads/stats`, {
    headers: { "X-Admin-Key": adminKey },
  });
  if (!res.ok) throw new Error("Failed to load lead statistics");
  return res.json();
}

export async function updateLeadStatus(
  adminKey: string,
  leadId: string,
  status: string
): Promise<ProspectiveLeadItem> {
  const res = await fetch(`${API_BASE}/api/v1/admin/leads/${leadId}/status`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Key": adminKey,
    },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error("Failed to update lead status");
  return res.json();
}

export async function exportAdminLeads(adminKey: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/admin/leads/export`, {
    headers: { "X-Admin-Key": adminKey },
  });
  if (!res.ok) throw new Error("Failed to export leads");
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `sru_prospective_leads_${new Date().toISOString().split("T")[0]}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}




