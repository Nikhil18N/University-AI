/**
 * The student's own details (name, mobile number), in ONE place.
 *
 * Before this file there were three separate copies that could disagree: what the chat agent
 * remembered on the server, `sru_student_lead` in this browser, and the forms that wrote to
 * only one of them. So a new number given in the chat never reached "My details".
 *
 * Now every writer goes through saveStudentDetails() and every reader through
 * readStudentDetails(); the server copy (GET/PUT /api/v1/agent/profile) is the one that wins,
 * and anything listening to "sru-profile-changed" redraws itself.
 */
import { API_BASE } from "../services/api";

export interface StudentDetails {
  name: string;
  phone: string;
  program_interest?: string;
  open_request?: string;
}

const STORAGE_KEY = "sru_student_lead";
export const PROFILE_EVENT = "sru-profile-changed";

export function cleanPhone(raw: string): string | null {
  const digits = (raw || "").replace(/\D/g, "").replace(/^(?:91|0)(?=[6-9]\d{9}$)/, "");
  return /^[6-9]\d{9}$/.test(digits) ? digits : null;
}

export function readStudentDetails(): StudentDetails | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    return {
      name: String(parsed.name || "").trim(),
      phone: String(parsed.phone || "").trim(),
      program_interest: parsed.program_interest || undefined,
      open_request: parsed.open_request || undefined,
    };
  } catch {
    return null;
  }
}

function writeLocal(details: Partial<StudentDetails> | null) {
  try {
    if (!details || (!details.name && !details.phone)) {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...readStudentDetails(), ...details }));
    }
  } catch {
    /* private mode: the server copy still holds the details */
  }
  window.dispatchEvent(new CustomEvent(PROFILE_EVENT));
}

/** Take what the server knows (sent with every agent reply) as the truth for this browser. */
export function applyServerProfile(profile: Record<string, unknown> | null | undefined) {
  if (!profile) return;
  const name = typeof profile.name === "string" ? profile.name : "";
  const phone = typeof profile.phone === "string" ? profile.phone : "";
  if (!name && !phone) return;
  const current = readStudentDetails();
  const next = {
    name: name || current?.name || "",
    phone: phone || current?.phone || "",
    program_interest: (profile.program_interest as string) || current?.program_interest,
    open_request: (profile.open_request as string) || undefined,
  };
  if (JSON.stringify(next) !== JSON.stringify(current)) writeLocal(next);
}

export async function fetchServerProfile(sessionId: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/api/v1/agent/profile?session_id=${encodeURIComponent(sessionId)}`);
  if (!res.ok) throw new Error("Could not load your details");
  return (await res.json()).profile || {};
}

/**
 * Save the student's details everywhere: this browser, the chat agent's memory, and any
 * callback / visit request already saved. Throws with a readable message when the number is not valid.
 */
export async function saveStudentDetails(
  sessionId: string,
  details: { name?: string; phone?: string; program_interest?: string }
): Promise<StudentDetails> {
  const name = (details.name || "").trim();
  const phone = details.phone ? cleanPhone(details.phone) : null;
  if (details.phone && !phone) throw new Error("Please enter a valid 10-digit mobile number.");
  writeLocal({ ...(name ? { name } : {}), ...(phone ? { phone } : {}) });
  try {
    const res = await fetch(`${API_BASE}/api/v1/agent/profile`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        name: name || null,
        phone: phone || null,
        program_interest: details.program_interest || null,
      }),
    });
    if (res.status === 422) throw new Error("Please enter a valid 10-digit mobile number.");
    if (res.ok) applyServerProfile((await res.json()).profile);
  } catch (err) {
    if (err instanceof Error && err.message.startsWith("Please enter")) throw err;
    /* offline: kept in this browser, sent to the server on the next sync */
  }
  return readStudentDetails() || { name, phone: phone || "" };
}

/** "Forget my details": remove them from this browser and from the chat agent's memory. */
export async function forgetStudentDetails(sessionId: string): Promise<void> {
  writeLocal(null);
  try {
    await fetch(`${API_BASE}/api/v1/agent/profile?session_id=${encodeURIComponent(sessionId)}`, { method: "DELETE" });
  } catch {
    /* offline: the browser copy is gone; the server copy expires by itself */
  }
}

/**
 * On page load: make this browser and the server agree. The server wins when it has details;
 * otherwise details typed earlier in this browser (verification form, calculator) are sent up
 * so the chat agent knows them too.
 */
export async function syncStudentDetails(sessionId: string): Promise<void> {
  try {
    const server = await fetchServerProfile(sessionId);
    if (server.name || server.phone) {
      applyServerProfile(server);
      return;
    }
    const local = readStudentDetails();
    if (local?.name && cleanPhone(local.phone)) {
      await saveStudentDetails(sessionId, { name: local.name, phone: local.phone });
    }
  } catch {
    /* backend asleep: try again on the next load */
  }
}
