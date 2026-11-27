import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  fetchAdminStats,
  fetchAdminDocuments,
  enqueueDocumentUploadJob,
  pollAdminJob,
  deactivateDocument,
  fetchAdminFeedback,
  fetchAdminConversations,
  fetchAdminConversationDetail,
  deleteAdminConversation,
  promoteExemplar,
  downloadAllConversations,
  fetchAdminLeads,
  fetchAdminLeadStats,
  updateLeadStatus,
  exportAdminLeads,
  type AdminStats,
  type DocumentItem,
  type FeedbackItem,
  type AdminConversationItem,
  type AdminConversationDetail,
  type AdminMessageDetail,
  type ProspectiveLeadItem,
  type LeadStats,
} from "../services/api";
import MarkdownContent from "../components/MarkdownContent";
import { RenderCard } from "../components/Cards";
import AgentControlTab, { LiveRequestBanner } from "../components/admin/AgentControlTab";
import CampusMediaTab from "../components/admin/CampusMediaTab";
import { DocumentsTab } from "../components/admin/DocumentsTab";
import { FeedbackTab } from "../components/admin/FeedbackTab";
import { LeadsTab } from "../components/admin/LeadsTab";
import { OverviewTab } from "../components/admin/OverviewTab";
import AdminLogin from "../components/admin/AdminLogin";
import "../components/admin/AdminShell.css";
import "./AdminMobile.css";
import "./AdminPage.css";
import "./AdminChats.css";

interface Props {
  onBackToChat: () => void;
}

/** Strips markdown formatting to display clean preview text */
// Student chats (v4.15.1): who the student is, when, and what happened, at a glance.
function initials(name?: string | null): string {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean);
  return parts.length ? (parts[0][0] + (parts[1]?.[0] || "")).toUpperCase() : "?";
}
function chatWhen(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const day = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((day(now) - day(d)) / 86400000);
  if (diff === 0) return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  if (diff === 1) return "Yesterday";
  if (diff < 7) return d.toLocaleDateString([], { weekday: "short" });
  return d.toLocaleDateString([], { day: "numeric", month: "short" });
}
function prettyPhone(p?: string | null): string {
  const d = (p || "").replace(/\D/g, "").slice(-10);
  return d.length === 10 ? `${d.slice(0, 5)} ${d.slice(5)}` : (p || "");
}
function requestLabel(r?: string | null): string {
  return r === "campus_visit" ? "Visit request" : r === "callback" ? "Callback requested" : r ? "Request" : "";
}

function plainPreview(text: string): string {
  return (text || "")
    .replace(/\*\*|__|`|#{1,6}\s/g, "")
    .replace(/^\s*[-*•]\s+/gm, "")
    .replace(/\|/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const PROGRAM_LABEL_MAP: Record<string, string> = {
  btech_cse: "B.Tech CSE",
  btech_ai_robotics: "B.Tech AI & Robotics",
  btech_ece: "B.Tech ECE",
  btech_eee: "B.Tech EEE",
  btech_mech: "B.Tech Mechanical",
  btech_civil: "B.Tech Civil",
  btech_biotech: "B.Tech Biotechnology",
  btech_food_tech: "B.Tech Food Technology",
  btech_engg_physics: "B.Tech Engineering Physics",
  btech_iep: "B.Tech IEP (International)",
  bsc_agri: "B.Sc Agriculture",
  bdes: "B.Des (Design)",
  bba: "BBA",
  bsc_hospitality: "B.Sc Hospitality",
  bba_specialised: "BBA (Specialised)",
  bca: "BCA",
  bsc_cs: "B.Sc Computer Science",
  bsc_maths_ai: "B.Sc Mathematics & AI",
  bcom: "B.Com",
  bsc_physics: "B.Sc Physics",
  bsc_chemistry: "B.Sc Chemistry",
  mba: "MBA",
  mba_agri: "MBA Agri Business",
  mca: "MCA",
  mtech: "M.Tech",
  msc: "M.Sc",
};

/** Formats program interest into clean, professional titles and resolves missing or raw slug values */
function formatProgramInterest(raw?: string | null, meta?: any): string {
  const val = (raw || "").trim();
  const lower = val.toLowerCase();

  // If known slug
  if (PROGRAM_LABEL_MAP[lower]) {
    return PROGRAM_LABEL_MAP[lower];
  }

  // If already a valid specific name and not an unhelpful placeholder
  if (val && !["not specified", "unknown", "none", "null", "undefined", ""].includes(lower)) {
    // If it has parenthesized specialisations (e.g. "B.Tech CSE (AIML, Data Science...)"), shorten to primary
    if (val.includes(" (") && val.startsWith("B.Tech")) {
      return val.split(" (")[0];
    }
    return val;
  }

  // Attempt resolution from metadata (pending_question, query, program)
  const metaQ = meta?.pending_question || meta?.query || meta?.program_interest || meta?.program || "";
  const q = String(metaQ).toLowerCase();
  if (q) {
    if (q.includes("ai & robotics") || q.includes("ai and robotics")) return "B.Tech in AI and Robotics";
    if (q.includes("agri")) return "B.Sc Agriculture";
    if (q.includes("ece") || q.includes("electronics")) return "B.Tech ECE";
    if (q.includes("eee") || q.includes("electrical")) return "B.Tech EEE";
    if (q.includes("mech")) return "B.Tech Mechanical";
    if (q.includes("civil")) return "B.Tech Civil";
    if (q.includes("biotech")) return "B.Tech Biotechnology";
    if (q.includes("food tech")) return "B.Tech Food Technology";
    if (q.includes("mba")) return "MBA";
    if (q.includes("bba")) return "BBA";
    if (q.includes("bca")) return "BCA";
    if (q.includes("mca")) return "MCA";
    if (q.includes("design") || q.includes("bdes")) return "B.Des";
    if (q.includes("bcom") || q.includes("commerce")) return "B.Com";
    if (q.includes("cse") || q.includes("computer") || q.includes("software") || q.includes("data science") || q.includes("aiml")) return "B.Tech CSE";
  }

  return "General Admissions";
}

function NavIcon({ d }: { d: string }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"
         strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>
  );
}

export default function AdminPage({ onBackToChat }: Props) {
  const [adminKey, setAdminKey] = useState<string>(
    () => sessionStorage.getItem("university_ai_admin_key") || ""
  );
  const [activeTab, setActiveTab] = useState<"leads" | "chats" | "overview" | "documents" | "feedback" | "agent" | "media">("leads");

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);

  // Conversations (Audit) state
  const [conversations, setConversations] = useState<AdminConversationItem[]>([]);
  const [conversationsTotal, setConversationsTotal] = useState<number>(0);
  const [selectedConvId, setSelectedConvId] = useState<string | null>(null);
  const [selectedConvDetail, setSelectedConvDetail] = useState<AdminConversationDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState<boolean>(false);
  const [chatSearch, setChatSearch] = useState<string>("");
  const [feedbackFilter, setFeedbackFilter] = useState<string>("all");
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(50);
  const [isExportingAll, setIsExportingAll] = useState<boolean>(false);

  // Rich Transcript UX State
  const [transcriptViewMode, setTranscriptViewMode] = useState<"student" | "inspector">("student");
  const [transcriptFilterText, setTranscriptFilterText] = useState<string>("");
  const [copiedChatId, setCopiedChatId] = useState<string | null>(null);
  const [copiedTranscript, setCopiedTranscript] = useState<boolean>(false);

  // Leads State
  const [leads, setLeads] = useState<ProspectiveLeadItem[]>([]);
  const [leadsTotal, setLeadsTotal] = useState<number>(0);
  const [leadStats, setLeadStats] = useState<LeadStats | null>(null);
  const [leadSearch, setLeadSearch] = useState<string>("");
  const [leadProgramFilter, setLeadProgramFilter] = useState<string>("all");
  const [leadSourceFilter, setLeadSourceFilter] = useState<string>("all");
  const [leadStatusFilter, setLeadStatusFilter] = useState<string>("all");
  const [leadPage, setLeadPage] = useState<number>(1);
  const [leadPageSize] = useState<number>(50);
  const [isExportingLeads, setIsExportingLeads] = useState<boolean>(false);
  const [updatingLeadId, setUpdatingLeadId] = useState<string | null>(null);

  const matchedLead = selectedConvDetail
    ? leads.find(
        (l) =>
          l.conversation_id === selectedConvDetail.id ||
          (l.phone && selectedConvDetail.title?.includes(l.phone.replace(/\D/g, "").slice(-6)))
      )
    : null;

  const filteredMessages = selectedConvDetail
    ? selectedConvDetail.messages.filter((m) => {
        if (!transcriptFilterText.trim()) return true;
        return m.content.toLowerCase().includes(transcriptFilterText.toLowerCase());
      })
    : [];

  const [promotingMessageId, setPromotingMessageId] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Upload Form state
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadType, setUploadType] = useState("policy");
  const [uploadDept, setUploadDept] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  const detailScrollRef = useRef<HTMLDivElement>(null);

  const loadData = useCallback(async (key: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const [statsData, docsData, feedbackData, convsData, leadStatsData, leadsData] = await Promise.all([
        fetchAdminStats(key),
        fetchAdminDocuments(key),
        fetchAdminFeedback(key),
        fetchAdminConversations(key, { page: 1, pageSize: 50 }),
        fetchAdminLeadStats(key).catch(() => null),
        fetchAdminLeads(key, { page: 1, pageSize: 50 }).catch(() => ({ total: 0, items: [] })),
      ]);
      setStats(statsData);
      setDocuments(docsData.documents);
      setFeedback(feedbackData.items);
      setConversations(convsData.conversations);
      setConversationsTotal(convsData.total);
      if (leadStatsData) setLeadStats(leadStatsData);
      if (leadsData) {
        setLeads(leadsData.items || (leadsData as any).leads || []);
        setLeadsTotal(leadsData.total);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load admin data");
      setAdminKey("");
      sessionStorage.removeItem("university_ai_admin_key");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadConversationsOnly = useCallback(
    async (key: string, page: number, size: number, search: string, filter: string) => {
      try {
        const res = await fetchAdminConversations(key, {
          page,
          pageSize: size,
          search: search.trim() || undefined,
          feedbackFilter: filter === "all" ? undefined : filter,
        });
        setConversations(res.conversations);
        setConversationsTotal(res.total);
      } catch (err: unknown) {
        console.error("Failed to reload conversations:", err);
      }
    },
    []
  );

  const loadLeadsOnly = useCallback(
    async (
      key: string,
      page: number,
      size: number,
      search: string,
      program: string,
      source: string,
      status: string
    ) => {
      try {
        const [leadsRes, statsRes] = await Promise.all([
          fetchAdminLeads(key, {
            page,
            pageSize: size,
            search: search.trim() || undefined,
            program: program === "all" ? undefined : program,
            source: source === "all" ? undefined : source,
            status: status === "all" ? undefined : status,
          }),
          fetchAdminLeadStats(key).catch(() => null),
        ]);
        setLeads(leadsRes.items || (leadsRes as any).leads || []);
        setLeadsTotal(leadsRes.total);
        if (statsRes) setLeadStats(statsRes);
      } catch (err: unknown) {
        console.error("Failed to reload leads:", err);
      }
    },
    []
  );

  const handleSelectConversation = useCallback(
    async (convId: string) => {
      setSelectedConvId(convId);
      setIsLoadingDetail(true);
      setActionNotice(null);
      try {
        const url = new URL(window.location.href);
        url.searchParams.set("tab", "chats");
        url.searchParams.set("cid", convId);
        window.history.replaceState(null, "", url.toString());
      } catch {}
      try {
        const detail = await fetchAdminConversationDetail(adminKey, convId);
        setSelectedConvDetail(detail);
        setTimeout(() => {
          if (detailScrollRef.current) {
            detailScrollRef.current.scrollTop = 0;
          }
        }, 50);
      } catch (err: unknown) {
        alert(err instanceof Error ? err.message : "Failed to load conversation details");
      } finally {
        setIsLoadingDetail(false);
      }
    },
    [adminKey]
  );

  useEffect(() => {
    if (adminKey) {
      loadData(adminKey);
      try {
        const params = new URLSearchParams(window.location.search);
        const tabParam = params.get("tab") as any;
        if (tabParam && ["leads", "chats", "overview", "documents", "feedback", "agent", "media"].includes(tabParam)) {
          setActiveTab(tabParam);
        }
        const cidParam = params.get("cid") || params.get("chat_id") || params.get("conv_id");
        if (cidParam) {
          setSelectedConvId(cidParam);
          handleSelectConversation(cidParam);
        }
      } catch {}
    }
  }, [adminKey, loadData, handleSelectConversation]);

  // Refetch conversations when page, pageSize, filters or search change
  useEffect(() => {
    if (adminKey && activeTab === "chats") {
      const timer = setTimeout(() => {
        loadConversationsOnly(adminKey, currentPage, pageSize, chatSearch, feedbackFilter);
      }, 250);
      return () => clearTimeout(timer);
    }
  }, [adminKey, activeTab, currentPage, pageSize, chatSearch, feedbackFilter, loadConversationsOnly]);

  // Refetch leads when lead filters change
  useEffect(() => {
    if (adminKey && activeTab === "leads") {
      const timer = setTimeout(() => {
        loadLeadsOnly(
          adminKey,
          leadPage,
          leadPageSize,
          leadSearch,
          leadProgramFilter,
          leadSourceFilter,
          leadStatusFilter
        );
      }, 250);
      return () => clearTimeout(timer);
    }
  }, [
    adminKey,
    activeTab,
    leadPage,
    leadPageSize,
    leadSearch,
    leadProgramFilter,
    leadSourceFilter,
    leadStatusFilter,
    loadLeadsOnly,
  ]);

  const handleUpdateLeadStatus = async (leadId: string, newStatus: string) => {
    if (!adminKey) return;
    setUpdatingLeadId(leadId);
    try {
      const updated = await updateLeadStatus(adminKey, leadId, newStatus);
      setLeads((prev) => prev.map((l) => (l.id === leadId ? updated : l)));
      setActionNotice({
        text: `Status updated to "${newStatus}" for ${updated.name}`,
        type: "success",
      });
      fetchAdminLeadStats(adminKey).then((s) => setLeadStats(s)).catch(() => {});
    } catch (err: any) {
      setActionNotice({
        text: err.message || "Failed to update lead status",
        type: "error",
      });
    } finally {
      setUpdatingLeadId(null);
    }
  };

  const handleExportLeads = async () => {
    if (!adminKey || isExportingLeads) return;
    setIsExportingLeads(true);
    try {
      await exportAdminLeads(adminKey);
      setActionNotice({ text: "Prospective leads CSV exported successfully", type: "success" });
    } catch (err: any) {
      setActionNotice({ text: err.message || "Failed to export leads", type: "error" });
    } finally {
      setIsExportingLeads(false);
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem("university_ai_admin_key");
    setAdminKey("");
    setStats(null);
    setDocuments([]);
    setConversations([]);
    setSelectedConvDetail(null);
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile || !uploadTitle.trim()) {
      alert("Please provide a title and select a document file.");
      return;
    }

    setIsUploading(true);
    setUploadSuccess(null);
    try {
      const formData = new FormData();
      formData.append("file", uploadFile);
      formData.append("title", uploadTitle.trim());
      formData.append("document_type", uploadType);
      if (uploadDept.trim()) formData.append("department", uploadDept.trim());

      const queued = await enqueueDocumentUploadJob(adminKey, formData);
      setUploadSuccess(`Queued "${uploadTitle}" for indexing...`);
      await pollAdminJob(adminKey, queued.job_id);
      setUploadSuccess(`Successfully ingested "${uploadTitle}"!`);
      setUploadTitle("");
      setUploadDept("");
      setUploadFile(null);
      loadData(adminKey);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeactivate = async (docId: string) => {
    if (!confirm("Are you sure you want to deactivate this document?")) return;
    try {
      await deactivateDocument(adminKey, docId);
      loadData(adminKey);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Deactivation failed");
    }
  };

  const handleOpenLiveStudentChat = (convId: string) => {
    // No key in the URL: the new tab (same site) gets this tab's admin sign-in from sessionStorage.
    const targetUrl = `/?chat=${encodeURIComponent(convId)}`;
    window.open(targetUrl, "_blank");
  };

  const handleCopyConvId = (convId: string) => {
    navigator.clipboard.writeText(convId);
    setCopiedChatId(convId);
    setTimeout(() => setCopiedChatId(null), 2000);
  };

  const handleCopyShareableChatLink = (convId: string) => {
    // The link never carries the admin key: whoever opens it must be signed in to the admin panel.
    const link = `${window.location.origin}/?chat=${encodeURIComponent(convId)}`;
    navigator.clipboard.writeText(link);
    setActionNotice({ text: "Chat link copied (opens for signed-in staff only).", type: "success" });
    setTimeout(() => setActionNotice(null), 3000);
  };

  const handleCopyFullTranscriptText = (conv: AdminConversationDetail) => {
    const lines = [
      `# SR University AI Companion — Conversation Transcript`,
      `Conversation Title: ${conv.title}`,
      `Conversation ID: ${conv.id}`,
      `Session ID: ${conv.session_id}`,
      `Created At: ${new Date(conv.created_at).toLocaleString()}`,
      `Message Count: ${conv.messages.length}`,
      "",
      "---",
      "",
    ];
    conv.messages.forEach((m, idx) => {
      const sender = m.role === "user" ? "Student" : "SRU Buddy";
      const time = new Date(m.created_at).toLocaleTimeString();
      lines.push(`### Message ${idx + 1} • ${sender} [${time}]`);
      lines.push(m.content);
      if (m.suggestions && m.suggestions.length > 0) {
        lines.push(`*Quick Suggestions Shown:* ${m.suggestions.join(" | ")}`);
      }
      lines.push("");
    });
    navigator.clipboard.writeText(lines.join("\n"));
    setCopiedTranscript(true);
    setActionNotice({ text: "Complete conversation dialogue copied to clipboard!", type: "success" });
    setTimeout(() => {
      setCopiedTranscript(false);
      setActionNotice(null);
    }, 3000);
  };

  const handleDeleteConversation = async (convId: string) => {
    if (!confirm("Are you sure you want to delete this conversation log?")) return;
    try {
      await deleteAdminConversation(adminKey, convId);
      if (selectedConvId === convId) {
        setSelectedConvId(null);
        setSelectedConvDetail(null);
      }
      setActionNotice({ text: "Conversation deleted successfully.", type: "success" });
      loadConversationsOnly(adminKey, currentPage, pageSize, chatSearch, feedbackFilter);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to delete conversation");
    }
  };

  const handleExportAllMarkdown = async () => {
    setIsExportingAll(true);
    setActionNotice(null);
    try {
      await downloadAllConversations(adminKey, "markdown", {
        search: chatSearch,
        feedbackFilter,
      });
      setActionNotice({
        text: `Complete dataset downloaded in Markdown (.md)! Ready for AI model training / evaluation.`,
        type: "success",
      });
    } catch (err: unknown) {
      setActionNotice({
        text: err instanceof Error ? err.message : "Failed to export all conversations",
        type: "error",
      });
    } finally {
      setIsExportingAll(false);
    }
  };

  const handleExportSingleJson = (conv: AdminConversationDetail) => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(conv, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `chat-${conv.id.slice(0, 8)}-${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handlePrintPdf = () => {
    window.print();
  };

  const handlePromoteExemplar = async (msg: AdminMessageDetail, messages: AdminMessageDetail[]) => {
    const msgIdx = messages.findIndex((m) => m.id === msg.id);
    let question = "";
    for (let i = msgIdx - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        question = messages[i].content;
        break;
      }
    }

    if (!question) {
      alert("Could not identify the corresponding user question for this answer.");
      return;
    }

    setPromotingMessageId(msg.id);
    setActionNotice(null);
    try {
      await promoteExemplar(adminKey, {
        message_id: msg.id,
        question,
        answer: msg.content,
      });
      setActionNotice({
        text: `⭐ Exemplar Registered! Stored in ChromaDB verified_exemplars for dynamic few-shot learning.`,
        type: "success",
      });
    } catch (err: unknown) {
      setActionNotice({
        text: err instanceof Error ? err.message : "Failed to promote exemplar",
        type: "error",
      });
    } finally {
      setPromotingMessageId(null);
    }
  };

  /**
   * Always handles viewing a student's chat:
   * 1. If lead.conversation_id is present, opens directly.
   * 2. If missing, attempts matching existing conversations by phone or name.
   * 3. If not yet loaded, searches conversations via API by phone/name and selects the first match.
   */
  const handleViewLeadChat = async (lead: ProspectiveLeadItem) => {
    setActiveTab("chats");
    if (lead.conversation_id) {
      setSelectedConvId(lead.conversation_id);
      handleSelectConversation(lead.conversation_id);
      return;
    }

    const cleanPhone = lead.phone ? lead.phone.replace(/\D/g, "").slice(-10) : "";
    const matchedConv = conversations.find(
      (c) =>
        (cleanPhone && (c.title?.includes(cleanPhone) || c.last_message_preview?.includes(cleanPhone))) ||
        (lead.name && c.title?.toLowerCase().includes(lead.name.toLowerCase()))
    );

    if (matchedConv) {
      setSelectedConvId(matchedConv.id);
      handleSelectConversation(matchedConv.id);
      return;
    }

    // Fallback: search by phone or name
    const searchTerm = cleanPhone || lead.name;
    setChatSearch(searchTerm);
    setCurrentPage(1);

    try {
      const res = await fetchAdminConversations(adminKey, {
        page: 1,
        pageSize,
        search: searchTerm,
      });
      if (res.conversations.length > 0) {
        setConversations(res.conversations);
        setConversationsTotal(res.total);
        setSelectedConvId(res.conversations[0].id);
        handleSelectConversation(res.conversations[0].id);
      }
    } catch (e) {
      console.error("Auto search on lead click failed:", e);
    }
  };

  const totalPages = Math.max(1, Math.ceil(conversationsTotal / pageSize));

  // Authentication Box
  if (!adminKey) {
    return (
      <AdminLogin
        onBackToChat={onBackToChat}
        initialError={error}
        onSuccess={(key) => {
          sessionStorage.setItem("university_ai_admin_key", key);
          setError(null);
          setAdminKey(key);
        }}
      />
    );
  }

  const NAV: { key: typeof activeTab; label: string; icon: React.ReactNode; count?: number }[] = [
    { key: "leads", label: "Leads", icon: <NavIcon d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />, count: leadStats?.total_leads ?? leadsTotal },
    { key: "chats", label: "Student chats", icon: <NavIcon d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />, count: conversationsTotal || conversations.length },
    { key: "overview", label: "Overview", icon: <NavIcon d="M3 3v18h18M7 16l4-4 3 3 5-6" /> },
    { key: "agent", label: "Agent & counsellors", icon: <NavIcon d="M12 2a3 3 0 0 0-3 3v1H7a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-2V5a3 3 0 0 0-3-3zM9 13h.01M15 13h.01M9 17h6" /> },
    { key: "media", label: "Campus media", icon: <NavIcon d="M23 7l-7 5 7 5V7zM1 5h15v14H1z" /> },
    { key: "documents", label: "Knowledge base", icon: <NavIcon d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15zM20 22H6.5A2.5 2.5 0 0 1 4 19.5" />, count: documents.length },
    { key: "feedback", label: "Feedback", icon: <NavIcon d="M14 9V5a3 3 0 0 0-6 0v4M5 9h14l-1 12H6L5 9z" />, count: feedback.length },
  ];
  const activeLabel = NAV.find((n) => n.key === activeTab)?.label || "Dashboard";

  return (
    <div className="admin-container adm-shell">
      <aside className="adm-sidebar" aria-label="Admin navigation">
        <div className="adm-side-brand">
          <img src="/sru-logo.png" alt="SR University" />
          <div>
            <div className="adm-side-name">SRU Buddy</div>
            <div className="adm-side-sub">Admissions console</div>
          </div>
        </div>
        <nav className="adm-side-nav">
          {NAV.map((n) => (
            <button key={n.key} type="button" className={`adm-side-link ${activeTab === n.key ? "active" : ""}`}
                    aria-current={activeTab === n.key ? "page" : undefined} onClick={() => setActiveTab(n.key)}>
              <span className="adm-side-icon">{n.icon}</span>
              <span className="adm-side-label">{n.label}</span>
              {typeof n.count === "number" && n.count > 0 && <span className="adm-side-count">{n.count}</span>}
            </button>
          ))}
        </nav>
        <div className="adm-side-foot">
          <span className="adm-live"><span className="adm-live-dot" /> Live</span>
          <button type="button" className="adm-side-signout" onClick={handleLogout}>Sign out</button>
        </div>
      </aside>

      <div className="adm-body">
      <header className="admin-header adm-topbar">
        <div className="adm-top-left">
          <img src="/sru-logo.png" alt="" className="adm-top-logo" />
          <h1 className="adm-top-title">{activeLabel}</h1>
        </div>
        <div className="admin-header-actions">
          <span className="adm-live adm-live--top"><span className="adm-live-dot" /> Live</span>
          <button className="admin-btn-secondary adm-top-btn" onClick={onBackToChat}>
            <NavIcon d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /> <span>Open student chat</span>
          </button>
          <button className="admin-btn-secondary adm-top-btn adm-top-signout" onClick={handleLogout}>Sign out</button>
        </div>
      </header>

      {/* Phones and tablets: one scrollable row of sections (the sidebar is hidden there) */}
      <nav className="admin-nav-bar adm-mobile-tabs" ref={(nav) => {
        const active = nav?.querySelector<HTMLElement>(".admin-tab-btn.active");
        if (active && nav && nav.scrollWidth > nav.clientWidth) active.scrollIntoView({ block: "nearest", inline: "nearest" });
      }}>
        <div className="admin-tabs-list">
          {NAV.map((n) => (
            <button key={n.key} className={`admin-tab-btn ${activeTab === n.key ? "active" : ""}`} onClick={() => setActiveTab(n.key)}>
              <span className="adm-tab-icon">{n.icon}</span> {n.label}
              {typeof n.count === "number" && n.count > 0 && <span className="tab-counter">{n.count}</span>}
            </button>
          ))}
        </div>
      </nav>

      {/* Students waiting to talk to a counsellor (v4.12.0): rings on every tab */}
      {adminKey && activeTab !== "agent" && (
        <LiveRequestBanner adminKey={adminKey} onOpen={() => setActiveTab("agent")} />
      )}

      {/* Action Notification Toast */}
      {actionNotice && (
        <div className={`admin-toast toast-${actionNotice.type}`}>
          <span>{actionNotice.text}</span>
          <button className="toast-close-btn" onClick={() => setActionNotice(null)}>
            ✕
          </button>
        </div>
      )}

      {/* Main Scrollable Content */}
      <main className="admin-main-scroll">
        {isLoading ? (
          <div className="admin-loading-state">
            <div className="admin-spinner"></div>
            <p>Loading dashboard data...</p>
          </div>
        ) : (
          <>
            {/* =========================================================================
                TAB 1: PROSPECTIVE LEADS & ADMISSIONS CONVERSION
                ========================================================================= */}
            {activeTab === "leads" && (
              <LeadsTab
                adminKey={adminKey}
                leads={leads}
                leadsTotal={leadsTotal}
                leadStats={leadStats}
                leadSearch={leadSearch}
                setLeadSearch={setLeadSearch}
                leadProgramFilter={leadProgramFilter}
                setLeadProgramFilter={setLeadProgramFilter}
                leadSourceFilter={leadSourceFilter}
                setLeadSourceFilter={setLeadSourceFilter}
                leadStatusFilter={leadStatusFilter}
                setLeadStatusFilter={setLeadStatusFilter}
                leadPage={leadPage}
                setLeadPage={setLeadPage}
                leadPageSize={leadPageSize}
                isExportingLeads={isExportingLeads}
                updatingLeadId={updatingLeadId}
                formatProgramInterest={formatProgramInterest}
                onRefresh={() =>
                  loadLeadsOnly(
                    adminKey,
                    leadPage,
                    leadPageSize,
                    leadSearch,
                    leadProgramFilter,
                    leadSourceFilter,
                    leadStatusFilter
                  )
                }
                onExportLeads={handleExportLeads}
                onUpdateLeadStatus={handleUpdateLeadStatus}
                onViewLeadChat={handleViewLeadChat}
                onOpenLiveStudentChat={handleOpenLiveStudentChat}
              />
            )}

            {/* =========================================================================
                TAB 2: STUDENT CHATS AUDIT & MODEL IMPROVEMENT
                ========================================================================= */}
            {activeTab === "chats" && (
              <div className="tab-pane-container chats-pane">
                {/* Search & Export Toolbar */}
                <div className="admin-toolbar-card">
                  <div className="toolbar-filters">
                    <div className="admin-search-wrap">
                      <input
                        type="text"
                        className="admin-input-search"
                        placeholder="Search questions, answers, topics, mobile numbers, or session IDs..."
                        value={chatSearch}
                        onChange={(e) => {
                          setChatSearch(e.target.value);
                          setCurrentPage(1);
                        }}
                      />
                      {chatSearch && (
                        <button
                          className="search-clear-btn"
                          onClick={() => {
                            setChatSearch("");
                            setCurrentPage(1);
                          }}
                        >
                          ✕
                        </button>
                      )}
                    </div>

                    <div className="filter-chips-list">
                      <button
                        className={`filter-chip ${feedbackFilter === "all" ? "active" : ""}`}
                        onClick={() => {
                          setFeedbackFilter("all");
                          setCurrentPage(1);
                        }}
                      >
                        All Chats ({conversationsTotal})
                      </button>
                      <button
                        className={`filter-chip ${feedbackFilter === "positive" ? "active" : ""}`}
                        onClick={() => {
                          setFeedbackFilter("positive");
                          setCurrentPage(1);
                        }}
                      >
                        👍 Helpful
                      </button>
                      <button
                        className={`filter-chip ${feedbackFilter === "negative" ? "active" : ""}`}
                        onClick={() => {
                          setFeedbackFilter("negative");
                          setCurrentPage(1);
                        }}
                      >
                        👎 Inaccurate
                      </button>
                      <button
                        className={`filter-chip ${feedbackFilter === "none" ? "active" : ""}`}
                        onClick={() => {
                          setFeedbackFilter("none");
                          setCurrentPage(1);
                        }}
                      >
                        No Feedback
                      </button>
                    </div>
                  </div>

                  <div className="toolbar-actions">
                    <button
                      className="admin-btn-primary"
                      disabled={isExportingAll || conversationsTotal === 0}
                      onClick={handleExportAllMarkdown}
                      title="Download ALL conversations in Markdown (.md) to train or evaluate the AI model"
                    >
                      {isExportingAll ? "Preparing…" : "Export all chats"}
                    </button>
                  </div>
                </div>

                {/* Dual Pane Audit Workspace */}
                <div className={`chat-audit-layout ${selectedConvId ? "has-selection" : ""}`}>
                  {/* Left Column: Conversation List */}
                  <div className="chat-audit-sidebar">
                    <div className="sidebar-head">
                      <span>Conversations ({conversations.length} of {conversationsTotal})</span>
                      <button
                        className="btn-link-action"
                        onClick={() =>
                          loadConversationsOnly(adminKey, currentPage, pageSize, chatSearch, feedbackFilter)
                        }
                        title="Refresh conversations list"
                      >
                        ↻ Refresh
                      </button>
                    </div>

                    {conversations.length === 0 ? (
                      <div className="sidebar-empty">
                        <div style={{ fontSize: "1.8rem", marginBottom: "8px" }}></div>
                        <p>No conversations found matching filters.</p>
                      </div>
                    ) : (
                      <div className="sidebar-scroll-list">
                        {conversations.map((c) => {
                          const isSelected = selectedConvId === c.id;
                          return (
                            <button
                              type="button"
                              key={c.id}
                              className={`conv-list-item cv-item ${isSelected ? "selected" : ""}`}
                              aria-current={isSelected ? "true" : undefined}
                              onClick={() => handleSelectConversation(c.id)}
                            >
                              <span className={`cv-avatar ${c.student?.name ? "" : "is-unknown"}`} aria-hidden="true">
                                {initials(c.student?.name)}
                              </span>
                              <span className="cv-main">
                                <span className="cv-top">
                                  <strong className="cv-name">{c.student?.name || "Student (name not given)"}</strong>
                                  <time className="cv-time" dateTime={c.updated_at}
                                        title={new Date(c.updated_at).toLocaleString()}>{chatWhen(c.updated_at)}</time>
                                </span>
                                <span className="cv-topic">{c.title || "Untitled conversation"}</span>
                                {c.last_message_preview && (
                                  <span className="cv-preview">{plainPreview(c.last_message_preview)}</span>
                                )}
                                <span className="cv-tags">
                                  {c.student?.program && <span className="cv-tag">{c.student.program}</span>}
                                  {c.student?.marks && <span className="cv-tag">{c.student.marks}</span>}
                                  {c.student?.request && <span className="cv-tag is-req">{requestLabel(c.student.request)}</span>}
                                  <span className="cv-tag is-muted">{c.message_count} messages</span>
                                  {c.positive_feedback_count > 0 && <span className="cv-tag is-good">Helpful {c.positive_feedback_count}</span>}
                                  {c.negative_feedback_count > 0 && <span className="cv-tag is-bad">Not helpful {c.negative_feedback_count}</span>}
                                </span>
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    )}

                    {/* Pagination Bar */}
                    <div className="sidebar-pagination">
                      <div className="page-nav-btns">
                        <button
                          className="admin-btn-secondary btn-icon"
                          disabled={currentPage <= 1}
                          onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                        >
                          ◀
                        </button>
                        <span className="page-number-text">
                          {currentPage} / {totalPages}
                        </span>
                        <button
                          className="admin-btn-secondary btn-icon"
                          disabled={currentPage >= totalPages}
                          onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                        >
                          ▶
                        </button>
                      </div>

                      <div className="page-size-selector">
                        <span>Show:</span>
                        <select
                          className="admin-select select-compact"
                          value={pageSize}
                          onChange={(e) => {
                            setPageSize(Number(e.target.value));
                            setCurrentPage(1);
                          }}
                        >
                          <option value={25}>25</option>
                          <option value={50}>50</option>
                          <option value={100}>100</option>
                          <option value={1000}>All</option>
                        </select>
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Full Conversation Transcript */}
                  <div className="chat-audit-content">
                    {isLoadingDetail ? (
                      <div className="admin-loading-state">
                        <div className="admin-spinner"></div>
                        <p>Loading full conversation thread...</p>
                      </div>
                    ) : selectedConvDetail ? (
                      <div className="transcript-box">
                            <button type="button" className="admin-mobile-back" onClick={() => setSelectedConvId(null)}>
                              ← All chats
                            </button>
                            {/* Header: who the student is, then the actions (v4.15.1) */}
                            {(() => {
                              const st = selectedConvDetail.student || null;
                              const name = st?.name || matchedLead?.name || "";
                              const phone = (st?.phone || matchedLead?.phone || "").replace(/\D/g, "").slice(-10);
                              const program = st?.program || matchedLead?.program_interest || "";
                              const marks = st?.marks || matchedLead?.score || "";
                              return (
                                <div className="cv-head">
                                  <div className="cv-student">
                                    <span className={`cv-avatar cv-avatar-lg ${name ? "" : "is-unknown"}`} aria-hidden="true">{initials(name)}</span>
                                    <div className="cv-student-info">
                                      <h3 className="cv-student-name">
                                        {name || "Student (name not given)"}
                                        {st?.is_parent && <span className="cv-tag">Parent</span>}
                                      </h3>
                                      {phone.length === 10 && (
                                        <div className="cv-contact">
                                          <a className="cv-contact-link" href={`tel:+91${phone}`}>Call {prettyPhone(phone)}</a>
                                          <a className="cv-contact-link" href={`https://wa.me/91${phone}`} target="_blank" rel="noopener noreferrer">WhatsApp</a>
                                        </div>
                                      )}
                                      <div className="cv-tags">
                                        {program && <span className="cv-tag">{program}</span>}
                                        {marks && <span className="cv-tag">Marks {marks}</span>}
                                        {st?.scholarship_percent != null && <span className="cv-tag is-good">{st.scholarship_percent}% scholarship</span>}
                                        {st?.request && <span className="cv-tag is-req">{requestLabel(st.request)}</span>}
                                        {(st?.lead_status || matchedLead?.status) && (
                                          <span className={`cv-tag status-${st?.lead_status || matchedLead?.status}`}>Lead: {st?.lead_status || matchedLead?.status}</span>
                                        )}
                                      </div>
                                      <div className="cv-meta">
                                        <span title={selectedConvDetail.title}>{selectedConvDetail.title}</span>
                                        <span aria-hidden="true">·</span>
                                        <span>{new Date(selectedConvDetail.created_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</span>
                                        <span aria-hidden="true">·</span>
                                        <span>{selectedConvDetail.messages.length} messages</span>
                                      </div>
                                    </div>
                                  </div>
                                  <div className="cv-actions">
                                    <button type="button" className="admin-btn-primary" onClick={() => handleOpenLiveStudentChat(selectedConvDetail.id)}
                                            title="Open this chat exactly as the student sees it">Open as student</button>
                                    <button type="button" className="admin-btn-secondary" onClick={() => handleCopyFullTranscriptText(selectedConvDetail)}>
                                      {copiedTranscript ? "Copied" : "Copy chat"}
                                    </button>
                                    <details className="cv-more">
                                      <summary className="admin-btn-secondary">More</summary>
                                      <div className="cv-menu" role="menu">
                                        <button type="button" role="menuitem" onClick={() => handleCopyShareableChatLink(selectedConvDetail.id)}>Copy link to this chat</button>
                                        <button type="button" role="menuitem" onClick={handlePrintPdf}>Print / save as PDF</button>
                                        <button type="button" role="menuitem" onClick={() => handleExportSingleJson(selectedConvDetail)}>Download JSON</button>
                                        <button type="button" role="menuitem" onClick={() => handleCopyConvId(selectedConvDetail.id)}>
                                          {copiedChatId === selectedConvDetail.id ? "ID copied" : "Copy conversation ID"}
                                        </button>
                                        <button type="button" role="menuitem" className="is-danger" onClick={() => handleDeleteConversation(selectedConvDetail.id)}>Delete chat</button>
                                      </div>
                                    </details>
                                  </div>
                                </div>
                              );
                            })()}

                            {/* View Controls Sub-bar */}
                            <div className="transcript-sub-bar">
                              <div className="transcript-view-toggle">
                                <button
                                  className={`view-toggle-btn ${transcriptViewMode === "student" ? "active" : ""}`}
                                  onClick={() => setTranscriptViewMode("student")}
                                  title="Exact student view with Markdown tables, cards, avatars, and chips"
                                >
                                  Student View
                                </button>
                                <button
                                  className={`view-toggle-btn ${transcriptViewMode === "inspector" ? "active" : ""}`}
                                  onClick={() => setTranscriptViewMode("inspector")}
                                  title="Developer inspection view with telemetry and exemplar promotion"
                                >
                                  Inspector View
                                </button>
                              </div>
                              <div className="transcript-inline-search">
                                <span className="search-icon"></span>
                                <input
                                  type="text"
                                  placeholder="Search inside this dialogue..."
                                  value={transcriptFilterText}
                                  onChange={(e) => setTranscriptFilterText(e.target.value)}
                                  className="transcript-search-input"
                                />
                                {transcriptFilterText && (
                                  <button className="clear-search-btn" onClick={() => setTranscriptFilterText("")}>
                                    ×
                                  </button>
                                )}
                              </div>
                            </div>

                            {/* Dialogue Thread */}
                            <div className="transcript-scroll-area" ref={detailScrollRef}>
                              {filteredMessages.length === 0 ? (
                                <p className="transcript-empty-text">
                                  {transcriptFilterText
                                    ? `No messages matched "${transcriptFilterText}".`
                                    : "No messages recorded in this conversation."}
                                </p>
                              ) : (
                                filteredMessages.map((m) => {
                                  const isUser = m.role === "user";

                                  if (transcriptViewMode === "student") {
                                    return (
                                      <div
                                        key={m.id}
                                        className={`transcript-bubble-wrap ${isUser ? "role-user" : "role-assistant"}`}
                                      >
                                        <div className={`transcript-avatar ${isUser ? "student-avatar" : "bot-avatar"}`} aria-hidden="true">
                                          {isUser ? initials(selectedConvDetail.student?.name || matchedLead?.name) : "SRU"}
                                        </div>
                                        <div className="transcript-bubble-box">
                                          <div className="transcript-bubble-meta">
                                            <span className="sender-name">{isUser ? ((selectedConvDetail.student?.name || "").split(" ")[0] || "Student") : "SRU Buddy"}</span>
                                            {!isUser && <span className="bot-role-tag">AI Guide</span>}
                                            {m.model && <span className="msg-model-tag">{m.model}</span>}
                                            <span className="msg-time">
                                              {new Date(m.created_at).toLocaleTimeString([], {
                                                hour: "2-digit",
                                                minute: "2-digit",
                                              })}
                                            </span>
                                          </div>

                                          {/* Message Content with Markdown Support */}
                                          <div className={`transcript-bubble-content ${isUser ? "user-text" : "bot-markdown"}`}>
                                            {isUser ? (
                                              m.content
                                            ) : (
                                              <MarkdownContent content={m.content} />
                                            )}
                                          </div>

                                          {/* Visual Cards Rendered */}
                                          {!isUser && m.cards && m.cards.length > 0 && (
                                            <div className="transcript-cards-area">
                                              {m.cards.map((card, cIdx) => (
                                                <div key={cIdx} className="transcript-card-item">
                                                  <RenderCard card={card} />
                                                </div>
                                              ))}
                                            </div>
                                          )}

                                          {/* Visual Quick Response Chips Rendered */}
                                          {!isUser && m.suggestions && m.suggestions.length > 0 && (
                                            <div className="transcript-chips-area">
                                              <span className="chips-title">Quick Responses Shown:</span>
                                              <div className="chips-flex">
                                                {m.suggestions.map((chip, sIdx) => (
                                                  <span key={sIdx} className="transcript-chip-pill">
                                                    {chip}
                                                  </span>
                                                ))}
                                              </div>
                                            </div>
                                          )}

                                          {/* Grounded Sources */}
                                          {m.sources && m.sources.length > 0 && (
                                            <div className="msg-sources-box">
                                              <div className="sources-headline">
                                                Grounded Sources ({m.sources.length}):
                                              </div>
                                              <div className="sources-tags-list">
                                                {m.sources.map((src, i) => (
                                                  <div key={i} className="source-citation-chip">
                                                    <span></span>
                                                    <span className="src-title">{src.title}</span>
                                                    {src.page && <span className="src-page">(Page {src.page})</span>}
                                                    {src.department && (
                                                      <span className="src-dept">[{src.department}]</span>
                                                    )}
                                                  </div>
                                                ))}
                                              </div>
                                            </div>
                                          )}

                                          {/* User Feedback Alert */}
                                          {m.feedback && (
                                            <div
                                              className={`msg-feedback-alert ${
                                                m.feedback.rating === 1 ? "fb-positive" : "fb-negative"
                                              }`}
                                            >
                                              <span>
                                                {m.feedback.rating === 1
                                                  ? "👍 Student rated helpful"
                                                  : "👎 Student rated inaccurate"}
                                              </span>
                                              {m.feedback.comment && (
                                                <span className="feedback-comment-quote">
                                                  — "{m.feedback.comment}"
                                                </span>
                                              )}
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    );
                                  }

                                  // Inspector / Telemetry View Mode
                                  return (
                                    <div
                                      key={m.id}
                                      className={`transcript-message-bubble ${isUser ? "role-user" : "role-assistant"}`}
                                    >
                                      <div className="msg-header-row">
                                        <span className="msg-role-badge">
                                          {isUser ? "Student" : "SRU Buddy"}
                                        </span>
                                        {m.model && <span className="msg-model-tag">{m.model}</span>}
                                        <span className="msg-timestamp">
                                          {new Date(m.created_at).toLocaleTimeString([], {
                                            hour: "2-digit",
                                            minute: "2-digit",
                                            second: "2-digit",
                                          })}
                                        </span>
                                      </div>

                                      <div className="msg-body-content inspector-content">
                                        <pre className="inspector-raw-text">{m.content}</pre>
                                      </div>

                                      {/* Grounded Sources */}
                                      {m.sources && m.sources.length > 0 && (
                                        <div className="msg-sources-box">
                                          <div className="sources-headline">
                                            Grounded Sources ({m.sources.length}):
                                          </div>
                                          <div className="sources-tags-list">
                                            {m.sources.map((src, i) => (
                                              <div key={i} className="source-citation-chip">
                                                <span></span>
                                                <span className="src-title">{src.title}</span>
                                                {src.page && <span className="src-page">(Page {src.page})</span>}
                                                {src.department && (
                                                  <span className="src-dept">[{src.department}]</span>
                                                )}
                                              </div>
                                            ))}
                                          </div>
                                        </div>
                                      )}

                                      {/* User Feedback */}
                                      {m.feedback && (
                                        <div
                                          className={`msg-feedback-alert ${
                                            m.feedback.rating === 1 ? "fb-positive" : "fb-negative"
                                          }`}
                                        >
                                          <span>
                                            {m.feedback.rating === 1
                                              ? "👍 Student rated helpful"
                                              : "👎 Student rated inaccurate"}
                                          </span>
                                          {m.feedback.comment && (
                                            <span className="feedback-comment-quote">
                                              — "{m.feedback.comment}"
                                            </span>
                                          )}
                                        </div>
                                      )}

                                      {/* Model Improvement Action on Assistant Responses */}
                                      {!isUser && (
                                        <div className="msg-exemplar-action">
                                          <button
                                            className="btn-exemplar-promote"
                                            disabled={promotingMessageId === m.id}
                                            onClick={() => handlePromoteExemplar(m, selectedConvDetail.messages)}
                                            title="Store this verified Q&A in ChromaDB verified_exemplars to train the AI model"
                                          >
                                            {promotingMessageId === m.id
                                              ? "Registering..."
                                              : "⭐ Promote to Verified Exemplar (Train Model)"}
                                          </button>
                                        </div>
                                      )}
                                    </div>
                                  );
                                })
                              )}
                            </div>
                          </div>
                    ) : (
                      <div className="admin-empty-state transcript-placeholder">
                        <div className="empty-icon"></div>
                        <h3>Select a Conversation to Inspect</h3>
                        <p>
                          Click any conversation on the left to review student questions, AI responses, grounded citations, and feedback ratings.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* =========================================================================
                TAB 3: OVERVIEW STATS & AI TRAINING GUIDE
                ========================================================================= */}
            {activeTab === "overview" && stats && <OverviewTab stats={stats} />}

            {activeTab === "documents" && (
              <DocumentsTab
                documents={documents}
                uploadSuccess={uploadSuccess}
                uploadTitle={uploadTitle}
                setUploadTitle={setUploadTitle}
                uploadType={uploadType}
                setUploadType={setUploadType}
                uploadDept={uploadDept}
                setUploadDept={setUploadDept}
                setUploadFile={setUploadFile}
                isUploading={isUploading}
                onUpload={handleUpload}
                onDeactivate={handleDeactivate}
              />
            )}

            {activeTab === "agent" && adminKey && <AgentControlTab adminKey={adminKey} />}
            {activeTab === "media" && adminKey && <CampusMediaTab adminKey={adminKey} />}

            {activeTab === "feedback" && <FeedbackTab feedback={feedback} />}
          </>
        )}
      </main>
      </div>
    </div>
  );
}
