export const API_BASE = (
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== "undefined" && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1"
    ? `${window.location.protocol}//${window.location.hostname}:8080`
    : "http://localhost:8080")
).replace(/\/$/, "");

/** Where the chat runs: the full website ("web") or the embeddable widget ("widget").
 * Sent with each message so the admin console can tell them apart. */
let CHANNEL: "web" | "widget" = "web";
export function setChannel(channel: "web" | "widget") {
  CHANNEL = channel;
}

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
  /** Present for the legacy chat pipeline; the agent's replies carry no message id. */
  message_id?: string;
  /** What the agent now knows about the student (name, mobile number...), sent with every agent reply. */
  profile?: Record<string, unknown>;
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

export interface AgentFeeParams {
  program: string;
  percent?: number;
  board?: string;
  eapcet_rank?: number;
  jee_percentile?: number;
  ib_score?: number;
  hostel?: string;
  specialization?: boolean;
  transport?: boolean;
}

export interface AgentFeeResult {
  status: string;
  academic_year: string;
  source: string;
  data_status: string;
  program: string;
  program_key?: string;
  scholarship_percent: number;
  scholarship_basis?: string;
  tuition_first_year: string;
  tuition_first_year_after_scholarship: string;
  per_semester_after_scholarship: string;
  saving_first_year: string;
  one_time_enrollment_fee: string;
  other_fee_per_year?: string;
  exam_fee_first_year?: string;
  application_fee?: string;
  hostel?: { type?: string; per_year?: string; electricity_deposit?: string; status?: string } | null;
  transport_per_year?: string | null;
  semester_1?: { items: Array<{ key: string; item: string; amount: string; kind: string }>; total: string };
  semester_2?: { items: Array<{ key: string; item: string; amount: string; kind: string }>; total: string };
  total_per_semester?: string;
  sem1_total_payable?: string;
  sem2_total_payable?: string;
  next_scholarship_slab?: { scholarship_percent: number; requires: string; extra_saving_first_year: string } | null;
  first_year_total_payable: string;
  yearly_increase: string;
  duration_years?: number;
  year_by_year?: Array<{ year: number; tuition: string; after_scholarship: string; per_semester: string; total_payable: string }>;
  full_course_total?: string;
  specialization_fee_per_year?: string | null;
  flags?: string[];
  notes: string[];
}

const numberOrNull = (value: number | undefined): number | null =>
  value !== undefined && value !== null && !isNaN(value) ? value : null;

/**
 * The same fee calculation the chat agent uses (backend/app/sru_agent/fees.py).
 * The calculator shows these numbers, so the chat and the calculator can never disagree.
 */
export async function calculateAgentFee(params: AgentFeeParams, signal?: AbortSignal): Promise<AgentFeeResult> {
  const res = await fetch(`${API_BASE}/api/v1/agent/calculate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal,
    body: JSON.stringify({
      program: params.program,
      percent: numberOrNull(params.percent),
      board: params.board || "state_board",
      eapcet_rank: numberOrNull(params.eapcet_rank),
      jee_percentile: numberOrNull(params.jee_percentile),
      ib_score: numberOrNull(params.ib_score),
      hostel: params.hostel || "none",
      specialization: Boolean(params.specialization),
      transport: Boolean(params.transport),
    }),
  });
  return await handleResponse<AgentFeeResult>(res, "Failed to calculate fee");
}

/**
 * Programs, scholarship slabs, hostel and one-time fees for the Fee & Scholarship Calculator,
 * read live from the official fee file on the backend.
 */
export async function fetchFeeConfig<T = unknown>(signal?: AbortSignal): Promise<T> {
  if (!feeConfigRequest) {
    feeConfigRequest = fetch(`${API_BASE}/api/v1/agent/fee-config`)
      .then((res) => handleResponse<T>(res, "Failed to load fee table"))
      .catch((error) => {
        feeConfigRequest = null;
        throw error;
      });
  }

  if (!signal) return feeConfigRequest as Promise<T>;
  if (signal.aborted) {
    throw new DOMException("The fee table request was aborted.", "AbortError");
  }

  return await new Promise<T>((resolve, reject) => {
    const abort = () => {
      signal.removeEventListener("abort", abort);
      reject(new DOMException("The fee table request was aborted.", "AbortError"));
    };
    signal.addEventListener("abort", abort, { once: true });
    (feeConfigRequest as Promise<T>).then(
      (value) => {
        signal.removeEventListener("abort", abort);
        resolve(value);
      },
      (error) => {
        signal.removeEventListener("abort", abort);
        reject(error);
      },
    );
  });
}

let feeConfigRequest: Promise<unknown> | null = null;

/**
 * Send a chat message with Server-Sent Events (SSE) streaming tokens in real time.
 */
export function sendMessageStream(
  sessionId: string,
  message: string,
  conversationId: string | null | undefined,
  // A submitted academic details form (structured); only the agent endpoint reads it.
  form: Record<string, unknown> | undefined,
  callbacks: {
    onStart?: (conversationId: string) => void;
    onToken?: (delta: string) => void;
    onTool?: (tool: { name: string; status: string; label?: string; result?: any }) => void;
    onCard?: (card: { type: string; data: any }) => void;
    onDone?: (data: ChatResponse) => void;
    onError?: (error: Error) => void;
  },
  // "typed": the student typed it (the model understands it); "button": a chip / card option / tile the bot
  // offered (its fixed flow runs on the server).
  source: "typed" | "button" = "typed"
): () => void {
  const controller = new AbortController();

  (async () => {
    let tokensStreamed = 0;

    const streamFromEndpoint = async (url: string, strict = false): Promise<boolean> => {
      let res: Response;
      try {
        res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            message,
            conversation_id: conversationId || null,
            channel: CHANNEL,
            ...(url.includes("/agent/") ? { source } : {}),
            ...(form && url.includes("/agent/") ? { form } : {}),
          }),
          signal: controller.signal,
        });
      } catch (fetchErr: unknown) {
        if (controller.signal.aborted) throw fetchErr;
        // If the server was sleeping on cold start, retry once after a short wait
        await new Promise((r) => setTimeout(r, 2000));
        res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            message,
            conversation_id: conversationId || null,
            channel: CHANNEL,
            ...(url.includes("/agent/") ? { source } : {}),
            ...(form && url.includes("/agent/") ? { form } : {}),
          }),
          signal: controller.signal,
        });
      }

      if (!res.ok || !res.body) {
        if (strict) {
          // v4.17.1: the agent answered with an error (a limit, a validation problem): say it, do not resend the
          // message to a different pipeline that has neither this conversation's state nor its rules.
          let detail = "";
          try {
            const body = await res.json();
            detail = typeof body?.detail === "string" ? body.detail : "";
          } catch {
            /* not JSON */
          }
          throw new Error(detail || `SRU Buddy could not answer just now (error ${res.status}). Please tap Retry.`);
        }
        return false;
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
            continue;
          }

          if (parsed.type === "start") {
            callbacks.onStart?.(parsed.conversation_id);
          } else if (parsed.type === "token") {
            tokensStreamed++;
            callbacks.onToken?.(parsed.delta);
          } else if (parsed.type === "tool") {
            callbacks.onTool?.(parsed);
            if (parsed.status === "done" && parsed.result) {
              callbacks.onCard?.({ type: parsed.name, data: parsed.result });
            }
          } else if (parsed.type === "card") {
            callbacks.onCard?.(parsed.card || { type: parsed.name, data: parsed.result });
          } else if (parsed.type === "done") {
            callbacks.onDone?.(parsed);
            return true;
          } else if (parsed.type === "error") {
            // The agent's own honest error (model unavailable, a limit...): shown as it is. Only the legacy mode
            // (VITE_USE_AGENT=false) may try another endpoint before any token arrived.
            if (tokensStreamed === 0 && !strict) {
              return false;
            }
            throw new Error(parsed.detail || "Error streaming response");
          }
        }
      }
      return tokensStreamed > 0;
    };

    try {
      // Strict /api/v1/agent/stream path: no silent fallback to legacy /api/v1/chat/stream.
      const success = await streamFromEndpoint(`${API_BASE}/api/v1/agent/stream`, true);
      if (!success && !controller.signal.aborted) {
        throw new Error("SRU Buddy could not answer just now. Please tap Retry.");
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

const CONV_CACHE_TTL_MS = 30_000; // 30 seconds

export function invalidateConversationCache(sessionId: string): void {
  try {
    sessionStorage.removeItem(`conv_list_${sessionId}`);
  } catch {
    // Ignore storage quota / privacy mode exceptions
  }
}

/**
 * List all conversations for a session with sessionStorage caching (30s TTL)
 * to avoid duplicate network latency on sidebar navigation.
 */
export async function listConversations(
  sessionId: string
): Promise<ConversationSummary[]> {
  const cacheKey = `conv_list_${sessionId}`;
  try {
    const raw = sessionStorage.getItem(cacheKey);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && Array.isArray(parsed.data) && Date.now() - parsed.timestamp < CONV_CACHE_TTL_MS) {
        return parsed.data as ConversationSummary[];
      }
    }
  } catch {
    // sessionStorage not available or parsing failed, proceed to network fetch
  }

  try {
    const res = await fetch(
      `${API_BASE}/api/v1/conversations?session_id=${encodeURIComponent(sessionId)}`
    );
    const data = await handleResponse<ConversationSummary[]>(res, "Failed to load conversations");
    try {
      sessionStorage.setItem(cacheKey, JSON.stringify({ data, timestamp: Date.now() }));
    } catch {
      // sessionStorage quota exceeded, silent ignore
    }
    return data;
  } catch (err) {
    handleNetworkError(err, "Failed to load conversations");
  }
}

/**
 * Get a conversation with all messages.
 */
export async function getConversation(
  conversationId: string,
  sessionId: string,
  adminKey?: string
): Promise<ConversationDetail> {
  try {
    const headers: Record<string, string> = {};
    if (adminKey) {
      headers["X-Admin-Key"] = adminKey;
    }
    const res = await fetch(
      // The admin key travels only in the X-Admin-Key header, never in the URL (history, logs, shared links).
      `${API_BASE}/api/v1/conversations/${conversationId}?session_id=${encodeURIComponent(sessionId)}`,
      { headers }
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
  conversationId: string,
  sessionId: string
): Promise<ConversationDetail> {
  try {
    const res = await fetch(
      `${API_BASE}/api/v1/shared/${conversationId}?session_id=${encodeURIComponent(sessionId)}`
    );
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
    invalidateConversationCache(sessionId);
  } catch (err) {
    handleNetworkError(err, "Failed to delete conversation");
  }
}

export interface ConversationRecoveryContext {
  has_resumable_conversation: boolean;
  conversation_id?: string | null;
  title?: string | null;
  last_active_at?: string | null;
  student_name?: string | null;
  topic?: string | null;
  program_name?: string | null;
  board_name?: string | null;
  academic_stage?: string | null;
  score_text?: string | null;
  assessment_status: "completed" | "in_progress" | "none";
  scholarship_percent?: number | null;
  scholarship_label?: string | null;
  is_projected?: boolean;
  welcome_message?: string | null;
  total_messages?: number;
  workflow_step?: string | null;
  inactive_minutes?: number | null;
  resume_after_minutes?: number;
  offer_choice?: boolean;
  last_user_message?: string | null;
}

/**
 * Fetch structured recovery context for returning students.
 */
export async function fetchRecoveryContext(sessionId: string): Promise<ConversationRecoveryContext> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/agent/recovery-context?session_id=${encodeURIComponent(sessionId)}`);
    return await handleResponse<ConversationRecoveryContext>(res, "Failed to load recovery context");
  } catch {
    return { has_resumable_conversation: false, assessment_status: "none" };
  }
}

/**
 * Reset active conversation state for a fresh start while preserving verified identity & database records.
 */
export async function resetSessionConversation(sessionId: string, conversationId?: string | null): Promise<boolean> {
  // Starts a new conversation on the server: the previous one is kept (and its details filed with it).
  // Returns false when the server could not be reached, so the caller can say so instead of pretending.
  try {
    const res = await fetch(`${API_BASE}/api/v1/agent/reset-session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        conversation_id: conversationId || null,
      }),
    });
    invalidateConversationCache(sessionId);
    return res.ok;
  } catch {
    return false;
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

export interface AdminStudentSummary {
  name?: string | null;
  phone?: string | null;
  program?: string | null;
  marks?: string | null;
  scholarship_percent?: number | null;
  request?: string | null;
  lead_status?: string | null;
  is_parent?: boolean | null;
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
  student?: AdminStudentSummary | null;
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
  cards?: any[] | null;
  suggestions?: string[] | null;
  metadata?: Record<string, any> | null;
  created_at: string;
}

export interface AdminConversationDetail {
  id: string;
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: AdminMessageDetail[];
  student?: AdminStudentSummary | null;
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






// ---- v4.12.0: agent features ---------------------------------------------------------------------------

export interface CounsellorConnectStatus {
  request_id: string;
  status: "waiting" | "accepted" | "busy";
  seconds_left: number;
  wait_seconds: number;
  phone_last4: string;
  first_name?: string;
  counsellor?: string | null;
}

/** "Talk to a counsellor": the student's card polls its request. */
export async function fetchConnectStatus(requestId: string, sessionId: string): Promise<CounsellorConnectStatus> {
  const res = await fetch(
    `${API_BASE}/api/v1/agent/connect/${encodeURIComponent(requestId)}?session_id=${encodeURIComponent(sessionId)}`
  );
  if (!res.ok) throw new Error(res.status === 404 ? "not_found" : "failed");
  return res.json();
}

/** One Quick Start tile under the opening welcome message (Admin -> Agent -> Quick Start tiles). */
export interface WelcomeTile {
  id: string;
  title: string;
  badge: string;
  icon: string;
  prompt: string;
  subtitle?: string;
  enabled?: boolean;
}

let welcomeActionsRequest: Promise<{ heading: string; items: WelcomeTile[] }> | null = null;

/** The Quick Start tiles set in the admin panel (public; cached for the page). */
export function fetchWelcomeActions(): Promise<{ heading: string; items: WelcomeTile[] }> {
  if (!welcomeActionsRequest) {
    welcomeActionsRequest = fetch(`${API_BASE}/api/v1/agent/welcome-actions`)
      .then((res) => handleResponse<{ heading: string; items: WelcomeTile[] }>(res, "Failed to load quick start"))
      .catch((error) => {
        welcomeActionsRequest = null;
        throw error;
      });
  }
  return welcomeActionsRequest;
}

export interface EventHighlight {
  id: string;
  title: string;
  when: string;
  summary: string;
  image_url: string;
  video_id: string;
  keywords: string;
  enabled?: boolean;
}

export interface ChatAd {
  id: string;
  title: string;
  subtitle: string;
  tag: string;
  image_url: string;
  cta_text: string;
  link_url: string;
  enabled?: boolean;
}

export interface AddedVideo {
  id: string;
  title: string;
  category: string;
  type: "video" | "short";
  keywords: string;
}

export interface VideoChanges {
  hidden: string[];
  topics: Record<string, string>;
  added: AddedVideo[];
}

export interface BuiltinVideo {
  id: string;
  title: string;
  category: string;
  type: string;
  url: string;
  thumbnail_url: string;
}

let chatAdsRequest: Promise<{ rotate_seconds: number; items: ChatAd[] }> | null = null;

/** The small ads at the bottom of the chat (Admin -> Campus media -> Ads). Loaded once per page. */
export function fetchChatAds(): Promise<{ rotate_seconds: number; items: ChatAd[] }> {
  if (!chatAdsRequest) {
    chatAdsRequest = fetch(`${API_BASE}/api/v1/agent/chat-ads`)
      .then((res) => handleResponse<{ rotate_seconds: number; items: ChatAd[] }>(res, "Failed to load ads"))
      .catch((error) => {
        chatAdsRequest = null;
        throw error;
      });
  }
  return chatAdsRequest;
}

export interface ChatSettings {
  concession_picker: "grouped" | "table";
  connect_enabled: boolean;
  ai_answers: boolean;
  suggestion_chips: "questions_only" | "always";
  fee_questions: "evaluate_first" | "fee_card";
  welcome_tiles: WelcomeTile[];
  event_highlights: EventHighlight[];
  chat_ads: ChatAd[];
  ads_rotate_seconds: number;
  videos: VideoChanges;
  connect_wait_seconds: number;
  office_hours_start: string;
  office_hours_end: string;
  office_days: number[];
}

export interface ChatSettingsResponse {
  settings: ChatSettings;
  descriptions: Record<string, string>;
  updated_at?: string | null;
}

async function adminJson<T>(adminKey: string, path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1/admin${path}`, {
    ...init,
    headers: { "X-Admin-Key": adminKey, ...(init.body ? { "Content-Type": "application/json" } : {}), ...(init.headers || {}) },
  });
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body?.detail === "string" ? body.detail : "";
    } catch {}
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}

// Images uploaded in Admin -> Campus media (v4.15.1): stored in the database, served at /api/v1/agent/media/<id>.
export const MEDIA_PATH = /^\/api\/v1\/agent\/media\/[a-f0-9]{20}$/;

/** A usable image address: an https:// link, or an uploaded image (made absolute against the API). */
export function mediaUrl(u?: string | null): string {
  const v = (u || "").trim();
  if (MEDIA_PATH.test(v)) return `${API_BASE}${v}`;
  return /^https:\/\/\S+$/i.test(v) ? v : "";
}

export async function uploadAdminImage(adminKey: string, file: Blob, name: string)
  : Promise<{ id: string; url: string; type: string; size: number }> {
  const form = new FormData();
  form.append("file", file, name);
  const res = await fetch(`${API_BASE}/api/v1/admin/media`, { method: "POST", headers: { "X-Admin-Key": adminKey }, body: form });
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body?.detail === "string" ? body.detail : "";
    } catch {}
    throw new Error(detail || `Upload failed (${res.status})`);
  }
  return res.json();
}

export function fetchChatSettings(adminKey: string) {
  return adminJson<ChatSettingsResponse>(adminKey, "/settings");
}

export function saveChatSettings(adminKey: string, changes: Partial<ChatSettings>) {
  return adminJson<ChatSettingsResponse>(adminKey, "/settings", { method: "PUT", body: JSON.stringify(changes) });
}

export function fetchAdminVideos(adminKey: string) {
  return adminJson<{ builtin: BuiltinVideo[]; topics: string[]; changes: VideoChanges }>(adminKey, "/videos");
}

export interface LiveRequest {
  request_id: string;
  first_name: string;
  phone: string;
  seconds_left: number;
  case: Record<string, any>;
  lead_id?: string | null;
}

export function fetchLiveRequests(adminKey: string) {
  return adminJson<{ requests: LiveRequest[]; in_office_hours: boolean }>(adminKey, "/live-requests");
}

export function acceptLiveRequest(adminKey: string, requestId: string, counsellor?: string) {
  const q = counsellor ? `?counsellor=${encodeURIComponent(counsellor)}` : "";
  return adminJson<{ status: string; phone: string; first_name: string; case: Record<string, any> }>(
    adminKey, `/live-requests/${encodeURIComponent(requestId)}/accept${q}`, { method: "POST" }
  );
}

export interface CopilotLead {
  lead_id: string;
  name: string;
  phone: string;
  program?: string | null;
  status: string;
  created_at?: string | null;
  score: number;
  tier: "hot" | "warm" | "later";
  reasons: string[];
  case: Record<string, any>;
}

export function fetchCopilotPriorities(adminKey: string, limit = 20) {
  return adminJson<{ leads: CopilotLead[] }>(adminKey, `/copilot/priorities?limit=${limit}`);
}

export function fetchCopilotDraft(adminKey: string, leadId: string) {
  return adminJson<{ lead_id: string; text: string; whatsapp_url?: string | null }>(
    adminKey, `/copilot/draft/${encodeURIComponent(leadId)}`
  );
}
