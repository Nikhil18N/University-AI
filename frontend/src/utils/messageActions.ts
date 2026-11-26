/**
 * Reply / Edit helpers for the chat (v4.17.1).
 *
 * A reply refers to a SAVED message by its server id; the server checks it belongs to this conversation and gives
 * the model that message (and, for a fee card, that card's own estimate). Only the latest message the student
 * typed can be edited; the server restores the state from before it and answers the corrected text.
 */
import type { MessageData } from "../services/api";

/** Cards that show a fee result; only the newest one in the chat is current. */
export const FEE_CARD_TYPES = new Set(["fee_summary", "calculate_fee", "concession_fee", "fee_plan"]);

export interface ReplyPreview {
  /** "Fee estimate", "SRU Buddy" or "You" */
  label: string;
  /** one line: the card's programme / scholarship / first-year amount, or the start of the message */
  text: string;
}

const MAX_PREVIEW = 110;

function plain(markdown: string): string {
  return (markdown || "")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[*_`>#|~]/g, " ")
    .replace(/-{3,}/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function shorten(text: string): string {
  return text.length > MAX_PREVIEW ? `${text.slice(0, MAX_PREVIEW - 1).trimEnd()}…` : text;
}

function money(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) return `₹${value.toLocaleString("en-IN")}`;
  return typeof value === "string" ? value : "";
}

/** One line naming a fee card's estimate, taken only from the card's own data (nothing is recalculated). */
export function feeCardSummary(card: any): string {
  const d = (card && (card.data || card)) || {};
  const program = d.program || d.program_name || d.course || "";
  const scholarship =
    d.scholarship && typeof d.scholarship === "object"
      ? String(d.scholarship.label || "").replace(/\s*\(.*\)\s*$/, "") // "25% merit scholarship (rules...)"
      : d.scholarship_percent
        ? `${d.scholarship_percent}% scholarship`
        : "";
  const total = money(d.payable_confirmed || d.first_year_total || d.first_year_total_payable);
  return [program, scholarship, total ? `${total} first year` : ""].filter(Boolean).join(" · ");
}

export function replyPreviewFor(message: MessageData): ReplyPreview {
  const fee = (message.cards || []).find((c: any) => FEE_CARD_TYPES.has(c?.type));
  if (fee) {
    return { label: "Fee estimate", text: shorten(feeCardSummary(fee) || plain(message.content)) };
  }
  return { label: message.role === "assistant" ? "SRU Buddy" : "You", text: shorten(plain(message.content)) };
}

/** A message the server has saved (so it can be replied to): not the local welcome card, not a held message. */
export function isSavedMessage(message: MessageData | undefined, streamingId?: string | null): boolean {
  if (!message || !message.id) return false;
  if (message.id === streamingId) return false;
  return !message.id.startsWith("welcome-") && !message.id.startsWith("pending-");
}

/**
 * The student's message that can be edited: their latest TYPED message (buttons may have been tapped after it),
 * saved by the server. Returns its id, whether a request to the admissions team was started from it or after it
 * (then it cannot be edited), and the button choices made after it (replayed after the edit when still offered).
 */
export interface LaterChoice {
  /** what the student tapped */
  text: string;
  /** the cards of the answer it was chosen from (the step that asked for it) */
  askedWith: string[];
}

const cardTypes = (cards?: any[]) => (cards || []).map((c) => c?.type).filter(Boolean).sort();

export function editableMessage(
  messages: MessageData[]
): { id: string; blocked: boolean; laterChoices: LaterChoice[] } | null {
  let blocked = false;
  const laterChoices: LaterChoice[] = [];
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const m = messages[i];
    if (m.role !== "user") continue;
    if (!isSavedMessage(m)) return null;
    blocked = blocked || Boolean(m.action_done);
    if (m.source === "button") {
      const askedBy = messages[i - 1]?.role === "assistant" ? messages[i - 1] : undefined;
      laterChoices.unshift({ text: m.content, askedWith: cardTypes(askedBy?.cards) });
      continue;
    }
    if (m.source !== "typed") return null; // an older message without this information
    return { id: m.id, blocked, laterChoices };
  }
  return null;
}

/**
 * Does this answer ask for the same choice again? Either it offers the same option (a chip or a card option), or it
 * is the same step: the same cards as the answer the student originally chose from (e.g. the concessions card,
 * whose "None of these apply" is part of the card itself).
 */
export function choiceStillOffered(choice: LaterChoice, suggestions?: string[], cards?: any[]): boolean {
  const text = choice.text.trim();
  if (!text) return false;
  if ((suggestions || []).some((s) => s.trim() === text)) return true;
  const now = cardTypes(cards);
  if (choice.askedWith.length > 0 && now.join("|") === choice.askedWith.join("|")) return true;
  try {
    return JSON.stringify(cards || []).includes(JSON.stringify(text).slice(1, -1));
  } catch {
    return false;
  }
}
