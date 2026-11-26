import React, { lazy, Suspense, useState, useEffect, useRef, useCallback, useMemo } from "react";
import { ChatAdStrip } from "../components/CampusCards";
import MessageBubble, { FEE_CARD_TYPES } from "../components/MessageBubble";
import ChatLeadForm from "../components/ChatLeadForm";
import WelcomeBackPanel, { type WelcomeBackStatus } from "../components/WelcomeBackPanel";
import { describeGap } from "../utils/timeAgo";
import {
  choiceStillOffered,
  editableMessage,
  isSavedMessage,
  replyPreviewFor,
  type LaterChoice,
  type ReplyPreview,
} from "../utils/messageActions";
import { CalculatorIcon } from "../components/Icons";
import { getSessionId, startFreshSession } from "../hooks/useSession";
import { applyServerProfile, cleanPhone, forgetStudentDetails, keepContactOnly, readStudentDetails, syncStudentDetails } from "../utils/studentProfile";
import { deduplicateCards } from "../components/Cards";
import type { AcademicFormPayload } from "../components/Cards";
import { WELCOME_QUICK_ACTIONS } from "../data/welcomeQuickActions";
import {
  sendMessageStream,
  fetchRecoveryContext,
  resetSessionConversation,
  getConversation,
  type ConversationRecoveryContext,
  type MessageData,
  type ChatResponse,
} from "../services/api";
import { playChime, triggerConfetti, isEligibleResponse, claimEligibilityCelebration } from "../utils/effects";
import { APP_VERSION } from "../version";
import "./ChatPage.css";

const ScholarshipCalculatorModal = lazy(() => import("../components/ScholarshipCalculatorModal"));
const LeadAuthModal = lazy(() => import("../components/LeadAuthModal"));
const SettingsModal = lazy(() => import("../components/SettingsModal"));

interface Props {
  onOpenAdmin?: () => void;
  variant?: "full" | "widget";
}

/** v4.17.1: the message the student is replying to, shown above the composer (tap it to see it, X to cancel). */
function ReplyBar({ preview, onJump, onCancel }: { preview: ReplyPreview; onJump: () => void; onCancel: () => void }) {
  return (
    <div className="sru-reply-bar" role="group" aria-label="Replying to a message">
      <button
        type="button"
        className="sru-reply-bar-body"
        onClick={onJump}
        aria-label={`Replying to ${preview.label}: ${preview.text}. Show that message`}
      >
        <span className="sru-reply-bar-label">Replying to {preview.label}</span>
        <span className="sru-reply-bar-text">{preview.text}</span>
      </button>
      <button type="button" className="sru-reply-bar-close" onClick={onCancel} aria-label="Cancel reply">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>
  );
}

const EDIT_BLOCKED_AFTER_ACTION =
  "This message sent a request to the admissions team, so it can't be edited. Please send a new message instead.";

type MessageAction = {
  /** the saved message this one replies to */
  replyTo?: string;
  /** the latest typed message this one replaces (Edit) */
  editOf?: string;
  /** the user message already on screen for a held question (contact form first) */
  shownUserMsgId?: string;
  /** the chat as it was before an edit: put back if the server refuses the edit */
  restoreOnRefusal?: MessageData[];
};

/** Tell the page that embeds the widget to close it (public/widget.js listens for this). */
function closeWidget() {
  try {
    // Only when embedded. The message carries no data, so the parent's origin need not be known.
    if (window.parent && window.parent !== window) {
      window.parent.postMessage({ type: "sru-buddy:close" }, "*");
    }
  } catch {
    /* not embedded */
  }
}

const LOCKED_WELCOME_CONTENT =
  "Welcome to SR University! 👋\n" +
  "I’m SRU Buddy, your AI companion at a Next-Gen Living and Learning Campus.\n\n" +
  "🏆 Top Private University in Telangana & AP\n\n" +
  "Which program are you interested in? I’ll guide you on eligibility, fees, scholarships and campus life.\n\n" +
  "🌐 Ask in English, हिंदी, తెలుగు or any language.";

// Quick-action tiles (with an incentive badge each) shown under the welcome text instead of plain chips.
const WELCOME_QUICK_ACTIONS_CARD = {
  type: "welcome_actions",
  heading: "⚡ Quick start",
  items: WELCOME_QUICK_ACTIONS,
  live: true, // the tiles set in Admin -> Agent -> Quick Start tiles (these are the fallback)
};

export function getInitialWelcomeMessage(_seed: string = ""): MessageData {
  return {
    id: "welcome-sru-buddy",
    role: "assistant",
    content: LOCKED_WELCOME_CONTENT,
    created_at: new Date().toISOString(),
    cards: [WELCOME_QUICK_ACTIONS_CARD],
  };
}

export const DEFAULT_WELCOME_MESSAGE: MessageData = getInitialWelcomeMessage();

const MESSAGE_RENDER_WINDOW = 60;
// Minutes without a message after which a returning student is asked "continue or start new". The server
// sends the value with /recovery-context (RECOVERY_RESUME_AFTER_MINUTES); this is only the fallback.
const DEFAULT_RESUME_AFTER_MINUTES = 30;
// Conversations the student chose NOT to continue ("Start a new chat"): never offered or restored again.
const DISMISSED_KEY = "sru_recovery_dismissed";

function readDismissed(): string[] {
  try {
    const list = JSON.parse(localStorage.getItem(DISMISSED_KEY) || "[]");
    return Array.isArray(list) ? list.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function markDismissed(conversationId?: string | null) {
  if (!conversationId) return;
  try {
    const list = readDismissed().filter((id) => id !== conversationId);
    list.push(conversationId);
    localStorage.setItem(DISMISSED_KEY, JSON.stringify(list.slice(-20)));
  } catch {
    /* private mode: the choice still applies to this page */
  }
}

type RecoveryOffer = {
  ctx: ConversationRecoveryContext;
  mode: "returning" | "idle";
  status: WelcomeBackStatus;
  error?: string | null;
  canContinue?: boolean;
};

export default function ChatPage({ onOpenAdmin, variant = "full" }: Props) {
  const isWidget = variant === "widget";
  // The session ID is state: "Start afresh" replaces it, so everything the server keeps per session
  // (profile, marks, programme, pending steps, conversation state) starts empty.
  const [sessionId, setSessionId] = useState<string>(() => getSessionId());
  // Bumped whenever the conversation on screen is replaced (new chat, restore). A reply or restore that
  // belongs to an earlier generation is dropped instead of landing in the new conversation.
  const chatGenRef = useRef(0);
  // Read by callbacks created before a re-render (e.g. a question sent right after "Start a new chat").
  const sessionIdRef = useRef(sessionId);
  sessionIdRef.current = sessionId;

  // Widget visibility state: closed by default so floating bubble is visible, clicks open it
  const [isWidgetOpen, setIsWidgetOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  // Queries
  const [dockQuery, setDockQuery] = useState("");
  const [widgetInput, setWidgetInput] = useState("");
  const widgetTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const portalTextareaRef = useRef<HTMLTextAreaElement | null>(null);

  const adjustTextareaHeight = (el: HTMLTextAreaElement | null) => {
    if (!el) return;
    el.style.height = "34px";
    const scrollH = el.scrollHeight;
    const targetHeight = Math.min(Math.max(scrollH, 34), 136);
    el.style.height = `${targetHeight}px`;
  };

  useEffect(() => {
    adjustTextareaHeight(widgetTextareaRef.current);
    adjustTextareaHeight(portalTextareaRef.current);
  }, [widgetInput]);

  // Chat message state
  const hasValidContactDetails = (): boolean => {
    const details = readStudentDetails();
    return Boolean(details?.name?.trim() && cleanPhone(details?.phone || ""));
  };

  const [messages, setMessages] = useState<MessageData[]>(() => [getInitialWelcomeMessage(sessionId)]);
  const [showInlineLeadForm, setShowInlineLeadForm] = useState<boolean>(false);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const pendingQuestionRef = useRef<string | null>(null);
  const [visibleMessageCount, setVisibleMessageCount] = useState(MESSAGE_RENDER_WINDOW);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const activeConvIdRef = useRef<string | null>(activeConvId);
  const [copiedChatLink, setCopiedChatLink] = useState(false);

  useEffect(() => {
    activeConvIdRef.current = activeConvId;
    if (activeConvId) {
      sessionStorage.setItem("sru_active_conv_id", activeConvId);
      try {
        const url = new URL(window.location.href);
        if (url.searchParams.get("chat") !== activeConvId) {
          url.searchParams.set("chat", activeConvId);
          window.history.replaceState(null, "", url.toString());
        }
      } catch {}
    }
  }, [activeConvId]);

  // Deep linking: Load conversation if ?chat=<id> or ?cid=<id> is in URL on mount
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const urlConvId = params.get("chat") || params.get("cid") || params.get("chat_id");
      // Staff view: the admin key comes only from this tab's admin sign-in (sessionStorage), never from
      // the URL. A key left in an old link is removed from the address bar and not used.
      if (params.has("admin_key")) {
        try {
          const url = new URL(window.location.href);
          url.searchParams.delete("admin_key");
          window.history.replaceState(null, "", url.toString());
        } catch {}
      }
      let adminKeyParam = "";
      try {
        adminKeyParam = sessionStorage.getItem("university_ai_admin_key") || "";
      } catch {}
      if (urlConvId && urlConvId !== activeConvIdRef.current) {
        setIsRestoringConv(true);
        getConversation(urlConvId, sessionId, adminKeyParam || undefined)
          .then((conv) => {
            if (conv && conv.messages && conv.messages.length > 0) {
              setMessages(conv.messages);
              setActiveConvId(urlConvId);
              activeConvIdRef.current = urlConvId;
              setIsWidgetOpen(true);
            }
          })
          .catch((err) => {
            console.warn("Could not load deep-linked conversation:", err);
          })
          .finally(() => {
            setIsRestoringConv(false);
          });
      }
    } catch {}
  }, [sessionId]);

  const handleCopyShareLink = () => {
    if (!activeConvId) return;
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("chat", activeConvId);
      navigator.clipboard.writeText(url.toString());
      setCopiedChatLink(true);
      setTimeout(() => setCopiedChatLink(false), 2200);
    } catch {}
  };

  const handleLeadFormComplete = () => {
    setShowInlineLeadForm(false);
    setError(null);
    const q = pendingQuestionRef.current || pendingQuestion;
    // Clear immediately so that it can never be submitted more than once
    pendingQuestionRef.current = null;
    setPendingQuestion(null);
    if (q) {
      const action = pendingActionRef.current;
      pendingActionRef.current = {};
      executeSendMessage(q, true, undefined, pendingSourceRef.current, action);
    }
  };

  const [isLoading, setIsLoading] = useState(false);
  const [activeToolStatus, setActiveToolStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [streamingMsgId, setStreamingMsgId] = useState<string | null>(null);

  // Modals
  const [isCalculatorOpen, setIsCalculatorOpen] = useState(false);
  const [showLeadAuthModal, setShowLeadAuthModal] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [pendingAuthMessage, setPendingAuthMessage] = useState<string | null>(null);

  // Voice recognition
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  const messagesAreaRef = useRef<HTMLDivElement>(null);
  const cancelStreamRef = useRef<(() => void) | null>(null);

  // Conversation memory: the "continue or start new" offer for a returning student (see docs/32)
  const [recovery, setRecovery] = useState<RecoveryOffer | null>(null);
  const recoveryRef = useRef<RecoveryOffer | null>(null);
  // v4.15.0: the previous conversation found on opening is HELD here, not shown. The choice appears only after
  // the student sends their first message (no pop-up on load; nothing restored behind their back).
  const heldOfferRef = useRef<ConversationRecoveryContext | null>(null);
  const [isRestoringConv, setIsRestoringConv] = useState<boolean>(false);
  const [pendingRecoveryQuery, setPendingRecoveryQuery] = useState<string | null>(null);
  const pendingRecoveryQueryRef = useRef<string | null>(null);
  // Where a held message came from ("typed" or a "button" tap): kept so that, once the welcome-back choice or the
  // contact details are done, it is sent exactly as the student sent it (v4.17.1).
  const pendingSourceRef = useRef<"typed" | "button">("typed");
  // v4.17.1: a held question's reply target and the id of its message already on screen (contact form first)
  const pendingActionRef = useRef<MessageAction>({});
  const [replyTarget, setReplyTarget] = useState<{ id: string; preview: ReplyPreview } | null>(null);
  const [highlightMsgId, setHighlightMsgId] = useState<string | null>(null);
  // v4.17.1: after an edit, the button choices the student made after the edited message, replayed in order while
  // each new answer still offers them (so a corrected mark recalculates the estimate without asking again)
  const replayRef = useRef<LaterChoice[]>([]);
  const [isReplaying, setIsReplaying] = useState(false);
  const resumeAfterMinutesRef = useRef<number>(DEFAULT_RESUME_AFTER_MINUTES);
  const restoringRef = useRef(false);
  // Where a restored conversation continues: a quiet divider after its last saved message.
  const [resumeDivider, setResumeDivider] = useState<{ afterId: string; text: string } | null>(null);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
  useEffect(() => { recoveryRef.current = recovery; }, [recovery]);

  const isLoadingRef = useRef(isLoading);
  const isReplayingRef = useRef(false);
  const dockQueryRef = useRef(dockQuery);
  const widgetInputRef = useRef(widgetInput);

  useEffect(() => { isLoadingRef.current = isLoading; }, [isLoading]);
  useEffect(() => { isReplayingRef.current = isReplaying; }, [isReplaying]);
  useEffect(() => { dockQueryRef.current = dockQuery; }, [dockQuery]);
  useEffect(() => { widgetInputRef.current = widgetInput; }, [widgetInput]);

  const recordUserActivity = () => {
    try {
      localStorage.setItem("sru_last_active_time", Date.now().toString());
    } catch {}
  };

  // "Latest" appears only when the student scrolls UP, away from the newest messages (not while they read a
  // new answer from its top, which is where a new answer is shown), and goes away near the bottom.
  const lastScrollTopRef = useRef(0);
  const handleBodyScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const fromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const scrolledUp = el.scrollTop < lastScrollTopRef.current - 4;
    lastScrollTopRef.current = el.scrollTop;
    setShowJumpToLatest((prev) => {
      if (fromBottom < 120) return false;
      if (scrolledUp && fromBottom > 360) return true;
      return prev;
    });
  };

  const scrollToLatest = (behavior: ScrollBehavior = "auto") => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const el = messagesAreaRef.current;
        if (el) el.scrollTo({ top: el.scrollHeight, behavior });
      });
    });
  };

  /**
   * Load a saved conversation into the chat. Used for "Continue conversation" and for the quiet restore
   * after a refresh or a short break. Returns false when it could not be loaded (the caller decides what
   * to show). Only one restore runs at a time.
   */
  const restoreConversation = async (
    conversationId: string,
    opts: { silent?: boolean; lastActiveText?: string } = {}
  ): Promise<"ok" | "missing" | "failed"> => {
    if (restoringRef.current) return "failed";
    restoringRef.current = true;
    setIsRestoringConv(true);
    const gen = chatGenRef.current;
    try {
      const conv = await getConversation(conversationId, sessionId);
      if (gen !== chatGenRef.current) return "failed"; // the student started a new chat meanwhile
      if (!conv || !conv.messages || conv.messages.length === 0) return "missing";
      chatGenRef.current += 1;
      setMessages(conv.messages);
      setVisibleMessageCount(MESSAGE_RENDER_WINDOW);
      setActiveConvId(conversationId);
      activeConvIdRef.current = conversationId;
      const lastId = conv.messages[conv.messages.length - 1]?.id;
      setResumeDivider(
        !opts.silent && lastId && opts.lastActiveText
          ? { afterId: lastId, text: `Continued · last message ${opts.lastActiveText}` }
          : null
      );
      if (!isWidget) setIsWidgetOpen(true);
      scrollToLatest();
      return "ok";
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      return /not found/i.test(msg) ? "missing" : "failed";
    } finally {
      restoringRef.current = false;
      setIsRestoringConv(false);
    }
  };

  // Returning student: on opening SRU Buddy, find their latest conversation.
  //  * opened from a chat link / after a refresh (?chat=<id>): that conversation is loaded (deep-link effect);
  //  * last message less than RECOVERY_RESUME_AFTER_MINUTES ago: it simply continues (no question);
  //  * longer ago: the welcome-back choice is shown; nothing starts or restores until the student chooses;
  //  * a conversation the student chose not to continue is never offered again.
  useEffect(() => {
    let cancelled = false;
    let deepLinked = false;
    try {
      const params = new URLSearchParams(window.location.search);
      deepLinked = Boolean(params.get("chat") || params.get("cid") || params.get("chat_id"));
    } catch {}
    recordUserActivity();
    heldOfferRef.current = null;
    if (deepLinked) return;
    let tabConv = "";
    try {
      tabConv = sessionStorage.getItem("sru_active_conv_id") || "";
    } catch {}
    fetchRecoveryContext(sessionId)
      .then(async (ctx) => {
        if (cancelled || !ctx?.has_resumable_conversation || !ctx.conversation_id) return;
        resumeAfterMinutesRef.current = ctx.resume_after_minutes || DEFAULT_RESUME_AFTER_MINUTES;
        if (readDismissed().includes(ctx.conversation_id)) return;
        if (activeConvIdRef.current || isLoadingRef.current) return; // a conversation already started here
        if (tabConv && tabConv === ctx.conversation_id) {
          // The same tab was refreshed in the middle of this conversation: simply carry on.
          await restoreConversation(ctx.conversation_id, { silent: true });
        } else {
          heldOfferRef.current = ctx; // asked after the student's first message
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // A tab left open: when the student comes back after the same break, offer the same choice at the end of
  // the conversation (never while they are typing, waiting for an answer, or already choosing).
  useEffect(() => {
    // v4.15.0: a tab left open is never interrupted with a "continue or start new?" question; the student simply
    // carries on (a greeting in an ongoing conversation does not reset it either).
    const IDLE_PROMPT_ENABLED = false;
    const checkInactivity = () => {
      if (!IDLE_PROMPT_ENABLED) return;
      if (document.visibilityState !== "visible") return;
      if (isLoadingRef.current || widgetInputRef.current || dockQueryRef.current) return;
      if (recoveryRef.current || !activeConvIdRef.current) return;
      const lastActiveStr = localStorage.getItem("sru_last_active_time");
      const lastActive = lastActiveStr ? parseInt(lastActiveStr, 10) : 0;
      const thresholdMs = resumeAfterMinutesRef.current * 60 * 1000;
      if (lastActive > 0 && Date.now() - lastActive >= thresholdMs) {
        recordUserActivity(); // offered once per return
        setRecovery({
          ctx: {
            has_resumable_conversation: true,
            conversation_id: activeConvIdRef.current,
            student_name: readStudentDetails()?.name || null,
            last_active_at: new Date(lastActive).toISOString(),
            assessment_status: "none",
          },
          mode: "idle",
          status: "idle",
        });
        scrollToLatest("smooth");
      }
    };

    document.addEventListener("visibilitychange", checkInactivity);
    window.addEventListener("focus", checkInactivity);
    return () => {
      document.removeEventListener("visibilitychange", checkInactivity);
      window.removeEventListener("focus", checkInactivity);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const takePendingRecoveryQuery = (): string | null => {
    const pending = pendingRecoveryQueryRef.current || pendingRecoveryQuery;
    pendingRecoveryQueryRef.current = null;
    setPendingRecoveryQuery(null);
    return pending;
  };

  const handleContinueConversation = async () => {
    const offer = recoveryRef.current;
    if (!offer) return;
    recordUserActivity();
    if (offer.mode === "idle") {
      // The conversation is already on screen: just carry on.
      setRecovery(null);
      return;
    }
    const conversationId = offer.ctx.conversation_id;
    if (!conversationId) {
      setRecovery(null);
      return;
    }
    setRecovery({ ...offer, status: "restoring", error: null });
    const result = await restoreConversation(conversationId, {
      lastActiveText: describeGap(offer.ctx.inactive_minutes, offer.ctx.last_active_at),
    });
    if (result !== "ok") {
      setRecovery({
        ...offer,
        status: "error",
        canContinue: result !== "missing",
        error:
          result === "missing"
            ? "That conversation is no longer available. Start a new chat and I'll help you from here."
            : "I couldn't reach SRU Buddy to restore your conversation. Check your connection and try again.",
      });
      return;
    }
    setRecovery(null);
    const pending = takePendingRecoveryQuery();
    // A plain greeting ("hi") was only the way back in: the restored conversation is the answer to it.
    if (pending && !/^\s*(?:hi+|hello+|hey+|hai|hii+|good\s+(?:morning|afternoon|evening)|namaste|namaskaram|hlo|helo)\b[\s!.,]*$/i.test(pending)) {
      const pendingSource = pendingSourceRef.current;
      setTimeout(() => {
        executeSendMessage(pending, false, undefined, pendingSource);
      }, 60);
    }
  };

  /**
   * "Start afresh": a genuinely new conversation in a new session.
   *  * a new session ID, so the server has no messages, name, programme, marks, eligibility, pending steps
   *    or confirmations for it, and cannot bring any back;
   *  * the reply still streaming for the old chat is cancelled, and any late reply or restore is dropped;
   *  * the old conversation is not deleted: it stays saved (and can be opened from its link);
   *  * this browser keeps only the name and number used by the contact form; they are not given to the
   *    new conversation ("Not {name}?" forgets those too).
   * Used by the welcome-back choice and by the "New chat" button in the header. It works offline.
   */
  const startNewConversation = async (opts: { forgetIdentity?: boolean } = {}): Promise<boolean> => {
    const offer = recoveryRef.current;
    const previousSession = sessionId;
    const previousId = activeConvIdRef.current || offer?.ctx.conversation_id || null;
    if (offer) setRecovery({ ...offer, status: "starting", error: null });
    handleResetChat(); // cancels the stream and bumps the generation first
    if (opts.forgetIdentity) {
      try {
        await forgetStudentDetails(previousSession);
      } catch {}
    } else {
      keepContactOnly();
    }
    // File the old conversation's details with it on the server (best effort; nothing depends on it).
    if (previousId) void resetSessionConversation(previousSession, previousId);
    markDismissed(previousId);
    if (offer?.ctx.conversation_id) markDismissed(offer.ctx.conversation_id);
    heldOfferRef.current = null;
    const freshId = startFreshSession();
    sessionIdRef.current = freshId;
    setSessionId(freshId);
    setRecovery(null);
    setResumeDivider(null);
    recordUserActivity();
    return true;
  };

  const handleStartNewConversation = async (opts: { forgetIdentity?: boolean } = {}) => {
    const started = await startNewConversation(opts);
    if (!started) return;
    const pending = takePendingRecoveryQuery();
    if (pending) {
      const pendingSource = pendingSourceRef.current;
      setTimeout(() => {
        handleSendMessage(pending, undefined, pendingSource);
      }, 60);
    }
  };

  const handleNewChatClick = () => {
    if (isLoading && cancelStreamRef.current) {
      cancelStreamRef.current();
      cancelStreamRef.current = null;
    }
    void startNewConversation();
  };

  // Real-time connection status: setting_up -> connected -> thinking
  const [connStatus, setConnStatus] = useState<"setting_up" | "connected">("setting_up");

  // Auto-sync profile on mount and set connection status
  useEffect(() => {
    let isMounted = true;
    syncStudentDetails(sessionId)
      .then(() => {
        if (isMounted) setConnStatus("connected");
      })
      .catch(() => {
        if (isMounted) setConnStatus("connected");
      });
    return () => {
      isMounted = false;
    };
  }, [sessionId]);

  // Listen for messages from parent window (e.g. public/widget.js register button)
  useEffect(() => {
    const handleWidgetMessage = (e: MessageEvent) => {
      // Only the page that embeds this chat (public/widget.js) may ask for the registration form;
      // a message from any other window (a pop-up, another frame) is ignored.
      if (window.parent === window || e.source !== window.parent) return;
      if (e.data?.type === "sru-buddy:register") {
        setShowLeadAuthModal(true);
      }
    };
    window.addEventListener("message", handleWidgetMessage);
    return () => window.removeEventListener("message", handleWidgetMessage);
  }, []);

  // Dynamically bind to visualViewport for mobile virtual keyboards to prevent blank screen & panning
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;

    const handleViewportChange = () => {
      const height = Math.round(vv.height);
      document.documentElement.style.setProperty("--visual-viewport-height", `${height}px`);
      // Keep document at 0, 0 so mobile browser doesn't scroll the fixed page upwards
      if (window.scrollY > 0) {
        window.scrollTo(0, 0);
      }
    };

    handleViewportChange();
    vv.addEventListener("resize", handleViewportChange);
    vv.addEventListener("scroll", handleViewportChange);
    return () => {
      vv.removeEventListener("resize", handleViewportChange);
      vv.removeEventListener("scroll", handleViewportChange);
    };
  }, []);

  const currentStatus = isRestoringConv
    ? { text: "Restoring conversation...", type: "setting_up" }
    : isLoading
    ? { text: activeToolStatus || "Thinking...", type: "thinking" }
    : connStatus === "setting_up"
      ? { text: "Setting up...", type: "setting_up" }
      : error
        ? { text: "Setting up...", type: "setting_up" }
        : { text: "Connected", type: "connected" };
  // While a returning student chooses, the welcome-back panel is the greeting (no second, generic welcome
  // above it pushing the choice below the fold).
  const shownMessages = messages;
  const visibleMessages = shownMessages.length > visibleMessageCount
    ? shownMessages.slice(-visibleMessageCount)
    : shownMessages;

  // The newest message with a fee result: fee cards in earlier messages are marked outdated (v4.15.0).
  const latestFeeMsgId = (() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if ((messages[i].cards || []).some((c: any) => FEE_CARD_TYPES.has(c?.type))) return messages[i].id;
    }
    return null;
  })();

  const lastSentUserMsgIdRef = useRef<string | null>(null);

  // Position newly sent user message at comfortable top reading view without jumping to bottom
  useEffect(() => {
    if (!messagesAreaRef.current) return;
    const container = messagesAreaRef.current;

    if (lastSentUserMsgIdRef.current) {
      const msgId = lastSentUserMsgIdRef.current;
      requestAnimationFrame(() => {
        const userMsgEl = document.getElementById(`sru-msg-${msgId}`);
        if (userMsgEl && container) {
          const topOffset = userMsgEl.offsetTop - container.offsetTop - 12;
          container.scrollTo({ top: Math.max(0, topOffset), behavior: "smooth" });
          lastSentUserMsgIdRef.current = null;
        }
      });
    }
  }, [messages, showInlineLeadForm]);

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

  async function handleSendMessage(
    text: string,
    form?: AcademicFormPayload,
    source: "typed" | "button" = "typed",
    action: MessageAction = {}
  ) {
    const trimmed = text.trim();
    if (!trimmed) return;

    recordUserActivity();
    // the student acts themselves: no more replay of earlier choices after an edit
    replayRef.current = [];
    setIsReplaying(false);

    // The first message of a visit, with an earlier conversation on file: ask now, after this message, whether to
    // continue it or start fresh (the message is answered once the student chooses).
    const held = heldOfferRef.current;
    if (held && !activeConvIdRef.current && !recoveryRef.current && hasValidContactDetails()) {
      heldOfferRef.current = null;
      if (held.conversation_id && !readDismissed().includes(held.conversation_id)) {
        const firstOffer: RecoveryOffer = { ctx: held, mode: "returning", status: "idle" };
        recoveryRef.current = firstOffer;
        setRecovery(firstOffer);
        setPendingRecoveryQuery(trimmed);
        pendingRecoveryQueryRef.current = trimmed;
        pendingSourceRef.current = source;
        const userMsgId = crypto.randomUUID();
        setMessages((prev) => [
          ...prev.filter((m) => !m.id.startsWith("pending-recovery-")),
          { id: `pending-recovery-${userMsgId}`, role: "user", content: trimmed, created_at: new Date().toISOString() },
        ]);
        scrollToLatest("smooth");
        return;
      }
    }

    // While the welcome-back choice is open, typed answers to it choose too ("continue", "start fresh").
    const offer = recoveryRef.current;
    if (offer && offer.status !== "restoring" && offer.status !== "starting") {
      if (/^\s*(?:[▶\s]*(?:continue|resume|pick\s*up)(?:\s+(?:previous|prior|my|the|this))?\s*(?:conversation|chat)?)\s*$/i.test(trimmed)) {
        void handleContinueConversation();
        return;
      }
      if (/^\s*(?:[↺\s]*(?:start\s*(?:fresh|new|a\s+new\s+chat)|new\s*(?:chat|conversation)|restart(?:\s*fresh)?|refresh(?:\s*chat)?))\s*$/i.test(trimmed)) {
        void handleStartNewConversation();
        return;
      }
      if (offer.mode === "returning") {
        // A question typed before choosing: shown now, answered once the student chooses, in the
        // conversation they choose. Nothing is sent or started on their behalf.
        setPendingRecoveryQuery(trimmed);
        pendingRecoveryQueryRef.current = trimmed;
        pendingSourceRef.current = source;
        const userMsgId = crypto.randomUUID();
        setMessages((prev) => [
          ...prev.filter((m) => !m.id.startsWith("pending-recovery-")),
          { id: `pending-recovery-${userMsgId}`, role: "user", content: trimmed, created_at: new Date().toISOString() },
        ]);
        scrollToLatest("smooth");
        return;
      }
      // Idle tab: typing simply continues the conversation on screen.
      setRecovery(null);
    }

    // Check for explicit modal calculator trigger
    if (/^\s*(?:🧮\s*calculator|open\s+(?:the\s+)?(?:fee\s+|scholarship\s+)?calculator)\s*$/i.test(trimmed)) {
      setIsCalculatorOpen(true);
      return;
    }

    if (!hasValidContactDetails()) {
      const userMsgId = crypto.randomUUID();
      const tempUserMsg: MessageData = {
        id: userMsgId,
        role: "user",
        content: trimmed,
        created_at: new Date().toISOString(),
      };
      lastSentUserMsgIdRef.current = userMsgId;
      setMessages((prev) => [...prev, { ...tempUserMsg, reply_to: action.replyTo || null }]);
      setPendingQuestion(trimmed);
      pendingQuestionRef.current = trimmed;
      pendingSourceRef.current = source;
      pendingActionRef.current = { replyTo: action.replyTo, shownUserMsgId: userMsgId };
      setShowInlineLeadForm(true);
      setError(null);
      return;
    }

    await executeSendMessage(trimmed, false, form, source, action);
  }

  async function executeSendMessage(
    text: string,
    skipAppendUserMsg = false,
    form?: AcademicFormPayload,
    source: "typed" | "button" = "typed",
    action: MessageAction = {}
  ) {
    if (isLoading && cancelStreamRef.current) {
      cancelStreamRef.current();
      cancelStreamRef.current = null;
    }

    setIsLoading(true);
    setError(null);

    const userMsgId = crypto.randomUUID();
    const assistantMsgId = crypto.randomUUID();
    setStreamingMsgId(assistantMsgId);

    if (!skipAppendUserMsg) {
      const tempUserMsg: MessageData = {
        id: userMsgId,
        role: "user",
        content: text,
        created_at: new Date().toISOString(),
        reply_to: action.replyTo || null,
        edited: Boolean(action.editOf),
      };
      lastSentUserMsgIdRef.current = userMsgId;
      setMessages((prev) => [...prev, tempUserMsg]);
    }
    // the student's message on screen for this turn: given its saved id when the answer arrives
    const shownUserMsgId = skipAppendUserMsg ? action.shownUserMsgId : userMsgId;

    let assistantAppended = false;
    let accumulatedContent = "";
    const accumulatedCards: any[] = [];
    let renderFrame: number | null = null;

    const cancelScheduledRender = () => {
      if (renderFrame !== null) {
        window.cancelAnimationFrame(renderFrame);
        renderFrame = null;
      }
    };

    const flushAssistantRender = () => {
      renderFrame = null;
      if (stale()) return;
      if (!assistantAppended) {
        assistantAppended = true;
        setMessages((prev) => [
          ...prev,
          {
            id: assistantMsgId,
            role: "assistant",
            content: accumulatedContent,
            cards: accumulatedCards.length ? [...accumulatedCards] : undefined,
            created_at: new Date().toISOString(),
          },
        ]);
      } else {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                ...m,
                content: accumulatedContent,
                cards: accumulatedCards.length ? [...accumulatedCards] : undefined,
              }
              : m
          )
        );
      }
    };

    const scheduleAssistantRender = () => {
      if (renderFrame === null) {
        renderFrame = window.requestAnimationFrame(flushAssistantRender);
      }
    };

    const convIdToSend = activeConvIdRef.current || activeConvId;
    const gen = chatGenRef.current;
    const stale = () => gen !== chatGenRef.current;
    // A new session ("Start afresh") gets its contact details from this browser first, so the first question
    // is not met by the contact gate. Usually already done: the promise is shared and settled.
    try {
      await syncStudentDetails(sessionIdRef.current);
    } catch {}
    if (stale()) return;
    const cancelFn = sendMessageStream(sessionIdRef.current, text, convIdToSend, form, {
      onStart: (convId) => {
        if (stale()) return;
        if (convId) {
          setActiveConvId(convId);
          activeConvIdRef.current = convId;
        }
      },
      onTool: (tool) => {
        if (stale()) return;
        if (tool.status === "running") {
          setActiveToolStatus(tool.label || "Working...");
        } else {
          setActiveToolStatus(null);
        }
      },
      onCard: (card) => {
        if (stale()) return;
        const isVideo = card?.type === "get_university_videos" || card?.type === "video_recommendations";
        const alreadyHasVideo = accumulatedCards.some(
          (c) => c?.type === "get_university_videos" || c?.type === "video_recommendations"
        );
        if (isVideo && alreadyHasVideo) return;
        accumulatedCards.push(card);
        scheduleAssistantRender();
      },
      onToken: (delta) => {
        if (stale()) return;
        setActiveToolStatus(null);
        accumulatedContent += delta;
        scheduleAssistantRender();
      },
      onDone: (data: ChatResponse) => {
        cancelScheduledRender();
        if (stale()) return; // a reply for a conversation the student has left
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

        if (isEligibleResponse(data) && claimEligibilityCelebration(sessionIdRef.current)) {
          triggerConfetti();
        }

        const rawCards = data.cards?.length ? data.cards : accumulatedCards;
        const finalCards = deduplicateCards(rawCards);

        // v4.17.1 Edit: replay the next earlier button choice if this answer still offers it
        if (replayRef.current.length) {
          const next = replayRef.current[0];
          if (choiceStillOffered(next, data.suggestions, rawCards)) {
            replayRef.current = replayRef.current.slice(1);
            window.setTimeout(() => {
              if (!stale()) void executeSendMessage(next.text, false, undefined, "button");
            }, 350);
          } else {
            replayRef.current = [];
            setIsReplaying(false);
          }
        } else if (isReplayingRef.current) {
          setIsReplaying(false);
        }

        // v4.17.1: the student's message now has its saved id (Reply / Edit refer to it) and how it was saved
        if (shownUserMsgId && data.user_message_id) {
          const meta = data.user_metadata || {};
          setMessages((prev) =>
            prev.map((m) =>
              m.id === shownUserMsgId
                ? {
                  ...m,
                  id: data.user_message_id as string,
                  source: meta.source || source,
                  edited: Boolean(meta.edited),
                  reply_to: meta.reply_to || null,
                  action_done: Boolean(meta.action_done),
                }
                : m
            )
          );
        }

        if (!assistantAppended) {
          assistantAppended = true;
          setMessages((prev) => [
            ...prev,
            {
              id: data.message_id || assistantMsgId,
              role: "assistant",
              content: data.answer || accumulatedContent,
              sources: data.sources?.length ? data.sources : undefined,
              suggestions: data.suggestions?.length ? data.suggestions : undefined,
              cards: finalCards.length ? finalCards : undefined,
              flow: data.flow,
              model: data.model,
              created_at: new Date().toISOString(),
            },
          ]);
        } else {
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
        }
      },
      onError: (err) => {
        cancelScheduledRender();
        if (stale()) return;
        setIsLoading(false);
        setActiveToolStatus(null);
        setStreamingMsgId(null);
        cancelStreamRef.current = null;
        setError(err.message || "Failed to get response.");
        replayRef.current = [];
        setIsReplaying(false);
        if ((err as { code?: string }).code === "message_action") {
          // the server refused the reply / edit and changed nothing: the chat goes back to how it was
          if (action.restoreOnRefusal) {
            setMessages(action.restoreOnRefusal);
          } else {
            setMessages((prev) => prev.filter((m) => m.id !== shownUserMsgId && m.id !== assistantMsgId));
            setWidgetInput(text);
          }
          return;
        }
        setMessages((prev) =>
          prev.filter((m) => m.id !== assistantMsgId || accumulatedContent.length > 0)
        );
      },
    }, source, { replyTo: action.replyTo, editOf: action.editOf });

    if (stale()) {
      cancelFn(); // the chat was replaced before the request even started
      return;
    }
    cancelStreamRef.current = cancelFn;
  }

  function handleResetChat() {
    chatGenRef.current += 1;
    if (cancelStreamRef.current) {
      cancelStreamRef.current();
      cancelStreamRef.current = null;
    }
    setIsLoading(false);
    setStreamingMsgId(null);
    setActiveConvId(null);
    activeConvIdRef.current = null;
    try {
      sessionStorage.removeItem("sru_active_conv_id");
      const url = new URL(window.location.href);
      url.searchParams.delete("chat");
      url.searchParams.delete("cid");
      url.searchParams.delete("chat_id");
      window.history.replaceState(null, "", url.toString());
    } catch {}
    setMessages([getInitialWelcomeMessage(sessionId + Date.now().toString())]);
    setVisibleMessageCount(MESSAGE_RENDER_WINDOW);
    setError(null);
    setShowInlineLeadForm(false);
    setPendingQuestion(null);
    setResumeDivider(null);
    setReplyTarget(null);
    pendingActionRef.current = {};
    replayRef.current = [];
    setIsReplaying(false);
  }

  // Handle bottom floating dock input submit
  const handleDockSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const query = dockQuery.trim();
    if (!query) return;
    setIsWidgetOpen(true);
    setIsMinimized(false);
    handleSendMessage(query);
    setDockQuery("");
  };

  // Handle widget input submit
  const handleWidgetSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const input = widgetInput.trim();
    if (!input || isLoading || showInlineLeadForm) return;
    const replyTo = replyTarget?.id;
    setReplyTarget(null);
    handleSendMessage(input, undefined, "typed", replyTo ? { replyTo } : {});
    setWidgetInput("");
  };

  // ---- v4.17.1 Reply and Edit ----------------------------------------------------------------------------
  const messagesById = useMemo(() => new Map(messages.map((m) => [m.id, m])), [messages]);
  const editable = useMemo(() => editableMessage(messages), [messages]);
  const editableId = editable?.id ?? null;

  /** Scroll to a message (loading older ones if needed) and highlight it briefly. */
  const jumpToMessage = (id: string) => {
    const index = messages.findIndex((m) => m.id === id);
    if (index < 0) return;
    const needed = messages.length - index;
    if (needed > visibleMessageCount) setVisibleMessageCount(needed);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        document.getElementById(`sru-msg-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
        setHighlightMsgId(id);
        window.setTimeout(() => setHighlightMsgId((cur) => (cur === id ? null : cur)), 1800);
      });
    });
  };

  const startReply = (id: string) => {
    const target = messagesById.get(id);
    if (!target || !isSavedMessage(target, streamingMsgId)) return;
    setReplyTarget({ id, preview: replyPreviewFor(target) });
    requestAnimationFrame(() => (widgetTextareaRef.current || portalTextareaRef.current)?.focus());
  };

  /** Edit the latest typed message: the server puts back the state from before it and answers the new text. */
  const submitEdit = (id: string, text: string) => {
    if (isLoadingRef.current || isReplayingRef.current || showInlineLeadForm || recoveryRef.current) return;
    const index = messages.findIndex((m) => m.id === id);
    if (index < 0 || !editable || id !== editable.id || editable.blocked) return;
    const original = messages[index];
    recordUserActivity();
    setReplyTarget(null);
    const before = messages;
    // the message and everything after it is replaced (archived on the server, never deleted)
    setMessages(messages.slice(0, index));
    replayRef.current = [...editable.laterChoices];
    setIsReplaying(editable.laterChoices.length > 0);
    void executeSendMessage(text, false, undefined, "typed", {
      editOf: id,
      replyTo: original.reply_to || undefined,
      restoreOnRefusal: before,
    });
  };

  // stable callbacks for the memoised bubbles, always calling the latest handlers
  const actionHandlersRef = useRef({ startReply, submitEdit });
  actionHandlersRef.current = { startReply, submitEdit };
  const onReplyStable = useCallback((id: string) => actionHandlersRef.current.startReply(id), []);
  const onEditStable = useCallback((id: string, text: string) => actionHandlersRef.current.submitEdit(id, text), []);

  const replyQuoteFor = (id?: string | null): ReplyPreview | null => {
    if (!id) return null;
    const target = messagesById.get(id);
    return target ? replyPreviewFor(target) : { label: "Earlier message", text: "That message is no longer shown." };
  };

  // Render Widget View directly if variant === "widget" (used inside public/widget.js iframe)
  if (isWidget) {
    return (
      <div className="sru-portal-root sru-portal--widget sru-widget-iframe-root">
        <div className="sru-widget-container sru-widget-iframe-container">
          {/* Header */}
          <div className="sru-widget-header">
            <div className="sru-widget-header-left">
              <div className="sru-widget-avatar-wrap">
                <img src="/sru-logo.png" alt="SRU" className="sru-widget-avatar-img" />
              </div>
              <div className="sru-widget-title-col">
                <div className="sru-widget-title-row">
                  <span className="sru-widget-title">SRU Buddy</span>
                  <span className="sru-version-pill" title={`SR University AI Companion v${APP_VERSION}`}>v{APP_VERSION}</span>
                </div>
                <span className="sru-widget-status">
                  <span className={`sru-widget-status-dot ${currentStatus.type}`} />
                  {currentStatus.text}
                </span>
              </div>
            </div>

            <div className="sru-widget-header-actions">
              <button
                className="sru-widget-hdr-btn"
                onClick={() => setShowSettings(true)}
                title="Student Profile & Settings"
                aria-label="Student Profile & Settings"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
              </button>
              <button
                className="sru-widget-hdr-btn"
                onClick={() => setIsCalculatorOpen(true)}
                title="Fee Calculator"
                aria-label="Fee Calculator"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="4" y="2" width="16" height="20" rx="2" />
                  <line x1="8" y1="6" x2="16" y2="6" />
                  <line x1="16" y1="14" x2="16" y2="18" />
                  <path d="M16 10h.01M12 10h.01M8 10h.01M12 14h.01M8 14h.01M12 18h.01M8 18h.01" />
                </svg>
              </button>
              <button
                className="sru-widget-hdr-btn"
                onClick={handleNewChatClick}
                title="Reset / New Chat"
                aria-label="Reset Chat"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
                  <path d="M21 3v5h-5" />
                  <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
                  <path d="M8 16H3v5" />
                </svg>
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
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                  <polyline points="15 3 21 3 21 9" />
                  <line x1="10" y1="14" x2="21" y2="3" />
                </svg>
              </a>
              <button
                className="sru-widget-hdr-btn"
                onClick={closeWidget}
                title="Close"
                aria-label="Close"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="sru-widget-body" ref={messagesAreaRef} onScroll={handleBodyScroll}>
            {shownMessages.length > visibleMessages.length && (
              <button
                type="button"
                onClick={() => setVisibleMessageCount((count) => Math.min(messages.length, count + MESSAGE_RENDER_WINDOW))}
                style={{ alignSelf: "center", margin: "8px auto", color: "#0055a4", background: "#f1f5f9", border: "1px solid #cbd5e1", borderRadius: "999px", padding: "5px 12px", cursor: "pointer", fontSize: "0.75rem", fontWeight: 600 }}
              >
                Load older messages
              </button>
            )}
            {visibleMessages.filter((m) => !(m.id === streamingMsgId && !(m.content || "").trim())).map((msg, index) => (
              <div
                key={msg.id || index}
                id={msg.id ? `sru-msg-${msg.id}` : undefined}
                className={highlightMsgId === msg.id ? "msg-jump-highlight" : undefined}
                style={{ width: "100%" }}
              >
                <MessageBubble
                  role={msg.role}
                  content={msg.content}
                  cards={msg.cards}
                  sources={msg.sources}
                  suggestions={msg.suggestions}
                  flow={msg.flow}
                  messageId={msg.id}
                  feeOutdated={!!latestFeeMsgId && msg.id !== latestFeeMsgId}
                  conversationId={activeConvId}
                  sessionId={sessionId}
                  isStreaming={msg.id === streamingMsgId}
                  onSuggestionClick={(prompt, form) => handleSendMessage(prompt, form, "button")}
                  onReply={msg.role === "assistant" && isSavedMessage(msg, streamingMsgId) ? onReplyStable : undefined}
                  replyQuote={msg.role === "user" ? replyQuoteFor(msg.reply_to) : null}
                  onJumpToReply={msg.reply_to ? () => jumpToMessage(msg.reply_to as string) : undefined}
                  canEdit={msg.id === editableId && !isLoading && !isReplaying && !showInlineLeadForm && !recovery}
                  editBlockedReason={msg.id === editableId && editable?.blocked ? EDIT_BLOCKED_AFTER_ACTION : null}
                  onEditSubmit={onEditStable}
                  edited={msg.edited}
                />
                {resumeDivider && msg.id === resumeDivider.afterId && (
                  <div className="wb-resume-divider" role="note">{resumeDivider.text}</div>
                )}
              </div>
            ))}

            {recovery && (
              <WelcomeBackPanel
                context={recovery.ctx}
                mode={recovery.mode}
                status={recovery.status}
                errorText={recovery.error}
                canContinue={recovery.canContinue !== false}
                pendingMessage={pendingRecoveryQuery}
                onContinue={() => void handleContinueConversation()}
                onStartNew={() => void handleStartNewConversation()}
                onNotMe={() => void handleStartNewConversation({ forgetIdentity: true })}
              />
            )}

            {showInlineLeadForm && (
              <ChatLeadForm onComplete={handleLeadFormComplete} pendingQuestion={pendingQuestion} />
            )}

            {isLoading && !messages.some((m) => m.id === streamingMsgId && m.content && m.content.trim().length > 0) && (
              <div className="message-bubble-row assistant sru-thinking-bubble-row">
                <div className="message-avatar-col">
                  <div className="assistant-avatar-badge" title="SRU Buddy">
                    <img src="/sru-logo.png" alt="SRU" className="assistant-avatar-img" />
                  </div>
                </div>
                <div className="message-content-col">
                  <div className="message-text-bubble assistant sru-typing-bubble">
                    <div className="sru-typing-dots" aria-hidden="true">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                    <span className="sru-typing-tool-label">{activeToolStatus || "Thinking..."}</span>
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div style={{ color: "#b91c1c", fontSize: "0.82rem", padding: "8px 12px", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "8px" }}>
                {error}
              </div>
            )}

            {showJumpToLatest && (
              <button type="button" className="sru-jump-latest" onClick={() => scrollToLatest("smooth")} aria-label="Scroll to the latest message">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19" /><polyline points="19 12 12 19 5 12" /></svg>
                Latest
              </button>
            )}

          </div>

          {/* Footer / Input Bar */}
          <div className="sru-widget-footer">
            {!showInlineLeadForm && <ChatAdStrip />}
            {replyTarget && !showInlineLeadForm && (
              <ReplyBar
                preview={replyTarget.preview}
                onJump={() => jumpToMessage(replyTarget.id)}
                onCancel={() => setReplyTarget(null)}
              />
            )}
            <form className="sru-widget-input-row" onSubmit={handleWidgetSubmit}>
              <textarea
                ref={widgetTextareaRef}
                className="sru-widget-textarea"
                placeholder={
                  showInlineLeadForm
                    ? "Please share your name & mobile number above to chat"
                    : replyTarget
                      ? "Write your reply..."
                      : "Ask SRU Buddy..."
                }
                rows={1}
                value={widgetInput}
                disabled={showInlineLeadForm || isLoading}
                aria-label="Ask SRU Buddy"
                onChange={(e) => {
                  setWidgetInput(e.target.value);
                  adjustTextareaHeight(e.target);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    handleWidgetSubmit(e);
                  }
                }}
              />

              <button
                type="button"
                className={`sru-widget-voice-btn ${listening ? "listening" : ""}`}
                onClick={toggleVoice}
                disabled={showInlineLeadForm}
                title={listening ? "Stop voice recording" : "Voice Typing"}
                aria-label={listening ? "Stop voice recording" : "Start voice typing"}
                aria-pressed={listening}
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
                disabled={showInlineLeadForm || !widgetInput.trim() || isLoading}
                title="Send Message"
                aria-label="Send message"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" fill="currentColor" />
                </svg>
              </button>
            </form>

            <div className="sru-response-disclaimer" role="note">
              May contain inaccuracies. Verify with official university sources.
            </div>
            <div className="sru-widget-watermark">
              <span className="sru-watermark-version">v{APP_VERSION}</span>
              <span className="sru-watermark-dot">•</span>
              <span className="sru-watermark-text">powered by</span>
              <span className="sru-watermark-badge" title="SR University Student Ambassadors">
                <img src="/student-ambassadors.png" alt="Student Ambassadors" className="sru-watermark-logo" />
              </span>
            </div>
          </div>
        </div>

        <Suspense fallback={null}>
          {isCalculatorOpen && (
            <ScholarshipCalculatorModal
              onClose={() => setIsCalculatorOpen(false)}
              onAskBuddy={(prompt) => {
                setIsCalculatorOpen(false);
                handleSendMessage(prompt, undefined, "button");
              }}
            />
          )}

          {showLeadAuthModal && (
            <LeadAuthModal
              isOpen
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
            />
          )}

          {showSettings && (
            <SettingsModal
              isOpen
              onClose={() => setShowSettings(false)}
              sessionId={sessionId}
            />
          )}
        </Suspense>
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
          <span className="sru-ribbon-version-pill" title={`Release v${APP_VERSION}`}>v{APP_VERSION}</span>
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

          <a href="tel:8331003030" className="sru-ribbon-link">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
            </svg>
            833 100 3030
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
          <div className="sru-brand-logo-badge" title="SR University">
            <img src="/sru-logo-white.png" alt="SR University" className="sru-brand-logo-img" />
          </div>
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
              placeholder={showInlineLeadForm ? "Share your name & mobile number in chat to continue" : "Ask anything about us...."}
              value={dockQuery}
              onChange={(e) => setDockQuery(e.target.value)}
            />
            <button type="submit" className="sru-dock-btn">
              Just Ask
            </button>
          </form>

          <div className="sru-launcher-cluster">
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
              <img src="/sru-logo-white.png" alt="SRU" className="sru-launcher-img" />
              <div className="sru-launcher-tooltip">Ask SRU Buddy</div>
            </button>
          </div>
        </div>
      )}

      {/* 5. Floating AI Assistant Widget Modal (Matches Reference Image 1) */}
      {isWidgetOpen && (
        <div className={`sru-widget-container ${isMinimized ? "sru-widget-minimized" : ""}`}>
          {/* Header */}
          <div className="sru-widget-header">
            <div className="sru-widget-header-left">
              <div className="sru-widget-avatar-wrap">
                <img src="/sru-logo.png" alt="SRU" className="sru-widget-avatar-img" />
              </div>
              <div className="sru-widget-title-col">
                <div className="sru-widget-title-row">
                  <span className="sru-widget-title">SRU Buddy</span>
                  <span className="sru-version-pill" title={`SR University AI Companion v${APP_VERSION}`}>v{APP_VERSION}</span>
                </div>
                <span className="sru-widget-status">
                  <span className={`sru-widget-status-dot ${currentStatus.type}`} />
                  {currentStatus.text}
                </span>
              </div>
            </div>

            <div className="sru-widget-header-actions">
              <button
                className="sru-widget-hdr-btn"
                onClick={() => setShowSettings(true)}
                title="Student Profile & Settings"
                aria-label="Student Profile & Settings"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
              </button>
              <button
                className="sru-widget-hdr-btn"
                onClick={() => setIsCalculatorOpen(true)}
                title="Fee Calculator"
                aria-label="Fee Calculator"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="4" y="2" width="16" height="20" rx="2" />
                  <line x1="8" y1="6" x2="16" y2="6" />
                  <line x1="16" y1="14" x2="16" y2="18" />
                  <path d="M16 10h.01M12 10h.01M8 10h.01M12 14h.01M8 14h.01M12 18h.01M8 18h.01" />
                </svg>
              </button>
              <button
                className="sru-widget-hdr-btn"
                onClick={handleNewChatClick}
                title="Reset / New Chat"
                aria-label="Reset Chat"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
                  <path d="M21 3v5h-5" />
                  <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
                  <path d="M8 16H3v5" />
                </svg>
              </button>
              {activeConvId && (
                <button
                  className="sru-widget-hdr-btn"
                  onClick={handleCopyShareLink}
                  title={copiedChatLink ? "Link Copied!" : "Share / Copy Chat Link"}
                  aria-label="Share Chat Link"
                >
                  {copiedChatLink ? (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  ) : (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="18" cy="5" r="3" />
                      <circle cx="6" cy="12" r="3" />
                      <circle cx="18" cy="19" r="3" />
                      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
                      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
                    </svg>
                  )}
                </button>
              )}
              <button
                className="sru-widget-hdr-btn"
                onClick={() => setIsMinimized((prev) => !prev)}
                title={isMinimized ? "Expand" : "Minimize"}
                aria-label="Minimize"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
              </button>
              <button
                className="sru-widget-hdr-btn"
                onClick={() => setIsWidgetOpen(false)}
                title="Close"
                aria-label="Close"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          </div>

          {/* Body */}
          {!isMinimized && (
            <>
              <div className="sru-widget-body" ref={messagesAreaRef} onScroll={handleBodyScroll}>
                {shownMessages.length > visibleMessages.length && (
                  <button
                    type="button"
                    onClick={() => setVisibleMessageCount((count) => Math.min(messages.length, count + MESSAGE_RENDER_WINDOW))}
                    style={{ alignSelf: "center", margin: "8px auto", color: "#0055a4", background: "#f1f5f9", border: "1px solid #cbd5e1", borderRadius: "999px", padding: "5px 12px", cursor: "pointer", fontSize: "0.75rem", fontWeight: 600 }}
                  >
                    Load older messages
                  </button>
                )}
                {visibleMessages.filter((m) => !(m.id === streamingMsgId && !(m.content || "").trim())).map((msg, index) => (
                  <div
                    key={msg.id || index}
                    id={msg.id ? `sru-msg-${msg.id}` : undefined}
                    className={highlightMsgId === msg.id ? "msg-jump-highlight" : undefined}
                    style={{ width: "100%" }}
                  >
                    <MessageBubble
                      role={msg.role}
                      content={msg.content}
                      cards={msg.cards}
                      sources={msg.sources}
                      suggestions={msg.suggestions}
                      flow={msg.flow}
                      messageId={msg.id}
                      feeOutdated={!!latestFeeMsgId && msg.id !== latestFeeMsgId}
                      conversationId={activeConvId}
                      sessionId={sessionId}
                      isStreaming={msg.id === streamingMsgId}
                      onSuggestionClick={(prompt, form) => handleSendMessage(prompt, form, "button")}
                      onReply={msg.role === "assistant" && isSavedMessage(msg, streamingMsgId) ? onReplyStable : undefined}
                      replyQuote={msg.role === "user" ? replyQuoteFor(msg.reply_to) : null}
                      onJumpToReply={msg.reply_to ? () => jumpToMessage(msg.reply_to as string) : undefined}
                      canEdit={msg.id === editableId && !isLoading && !isReplaying && !showInlineLeadForm && !recovery}
                      editBlockedReason={msg.id === editableId && editable?.blocked ? EDIT_BLOCKED_AFTER_ACTION : null}
                      onEditSubmit={onEditStable}
                      edited={msg.edited}
                    />
                    {resumeDivider && msg.id === resumeDivider.afterId && (
                      <div className="wb-resume-divider" role="note">{resumeDivider.text}</div>
                    )}
                  </div>
                ))}

                {recovery && (
                  <WelcomeBackPanel
                    context={recovery.ctx}
                    mode={recovery.mode}
                    status={recovery.status}
                    errorText={recovery.error}
                    canContinue={recovery.canContinue !== false}
                    pendingMessage={pendingRecoveryQuery}
                    onContinue={() => void handleContinueConversation()}
                    onStartNew={() => void handleStartNewConversation()}
                    onNotMe={() => void handleStartNewConversation({ forgetIdentity: true })}
                  />
                )}

                {showInlineLeadForm && (
                  <ChatLeadForm onComplete={handleLeadFormComplete} pendingQuestion={pendingQuestion} />
                )}

                {isLoading && !messages.some((m) => m.id === streamingMsgId && m.content && m.content.trim().length > 0) && (
                  <div className="message-bubble-row assistant sru-thinking-bubble-row">
                    <div className="message-avatar-col">
                      <div className="assistant-avatar-badge" title="SRU Buddy">
                        <img src="/sru-logo.png" alt="SRU" className="assistant-avatar-img" />
                      </div>
                    </div>
                    <div className="message-content-col">
                      <div className="message-text-bubble assistant sru-typing-bubble">
                        <div className="sru-typing-dots" aria-hidden="true">
                          <span></span>
                          <span></span>
                          <span></span>
                        </div>
                        <span className="sru-typing-tool-label">{activeToolStatus || "Thinking..."}</span>
                      </div>
                    </div>
                  </div>
                )}

                {error && (
                  <div style={{ color: "#b91c1c", fontSize: "0.82rem", padding: "8px 12px", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "8px" }}>
                    {error}
                  </div>
                )}

                {showJumpToLatest && (
                  <button type="button" className="sru-jump-latest" onClick={() => scrollToLatest("smooth")} aria-label="Scroll to the latest message">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19" /><polyline points="19 12 12 19 5 12" /></svg>
                    Latest
                  </button>
                )}

              </div>

              {/* Footer / Input Bar */}
              <div className="sru-widget-footer">
                {!showInlineLeadForm && <ChatAdStrip />}
                {replyTarget && !showInlineLeadForm && (
                  <ReplyBar
                    preview={replyTarget.preview}
                    onJump={() => jumpToMessage(replyTarget.id)}
                    onCancel={() => setReplyTarget(null)}
                  />
                )}
                <form className="sru-widget-input-row" onSubmit={handleWidgetSubmit}>
                  <textarea
                    ref={portalTextareaRef}
                    className="sru-widget-textarea"
                    placeholder={
                      showInlineLeadForm
                        ? "Please share your name & mobile number above to chat"
                        : replyTarget
                      ? "Write your reply..."
                      : "Ask SRU Buddy..."
                    }
                    rows={1}
                    value={widgetInput}
                    disabled={showInlineLeadForm || isLoading}
                    aria-label="Ask SRU Buddy"
                    onChange={(e) => {
                      setWidgetInput(e.target.value);
                      adjustTextareaHeight(e.target);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                        e.preventDefault();
                        handleWidgetSubmit(e);
                      }
                    }}
                  />

                  <button
                    type="button"
                    className={`sru-widget-voice-btn ${listening ? "listening" : ""}`}
                    onClick={toggleVoice}
                    disabled={showInlineLeadForm}
                    title={listening ? "Stop voice recording" : "Voice Typing"}
                    aria-label={listening ? "Stop voice recording" : "Start voice typing"}
                    aria-pressed={listening}
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
                    disabled={showInlineLeadForm || !widgetInput.trim() || isLoading}
                    title="Send Message"
                    aria-label="Send message"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="22" y1="2" x2="11" y2="13" />
                      <polygon points="22 2 15 22 11 13 2 9 22 2" fill="currentColor" />
                    </svg>
                  </button>
                </form>

                <div className="sru-response-disclaimer" role="note">
              May contain inaccuracies. Verify with official university sources.
            </div>
            <div className="sru-widget-watermark">
                  <span className="sru-watermark-version">v{APP_VERSION}</span>
                  <span className="sru-watermark-dot">•</span>
                  <span className="sru-watermark-text">powered by</span>
                  <span className="sru-watermark-badge" title="SR University Student Ambassadors">
                    <img src="/student-ambassadors.png" alt="Student Ambassadors" className="sru-watermark-logo" />
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      <Suspense fallback={null}>
        {isCalculatorOpen && (
          <ScholarshipCalculatorModal
            onClose={() => setIsCalculatorOpen(false)}
            onAskBuddy={(prompt) => {
              setIsCalculatorOpen(false);
              handleSendMessage(prompt, undefined, "button");
            }}
          />
        )}

        {showLeadAuthModal && (
          <LeadAuthModal
            isOpen
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
          />
        )}

        {showSettings && (
          <SettingsModal
            isOpen
            onClose={() => setShowSettings(false)}
            sessionId={sessionId}
          />
        )}
      </Suspense>
    </div>
  );
}
