/**
 * Session hook — generates and persists an anonymous session ID in localStorage.
 * No login required.
 */

const SESSION_KEY = "university_ai_session_id";

function generateUUID(): string {
  return crypto.randomUUID();
}

export function getSessionId(): string {
  let sessionId = localStorage.getItem(SESSION_KEY);
  if (!sessionId) {
    sessionId = generateUUID();
    localStorage.setItem(SESSION_KEY, sessionId);
  }
  return sessionId;
}
