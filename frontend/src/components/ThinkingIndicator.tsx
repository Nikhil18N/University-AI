import { useState, useEffect } from "react";
import "./ThinkingIndicator.css";

interface Props {
  /** What the agent is really doing right now (from the server), e.g. "Calculating your fee". */
  activeToolLabel?: string | null;
}

/**
 * Shown while SRU Buddy prepares an answer. It only ever says what is really happening:
 * the agent's current action when the server reports one, otherwise "Thinking". After a
 * few seconds it explains a slow first reply (the free server sleeps when idle and needs
 * up to a minute to wake up), so a student does not think the site is broken.
 */
export default function ThinkingIndicator({ activeToolLabel }: Props) {
  const [elapsedSecs, setElapsedSecs] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setElapsedSecs((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  const label = activeToolLabel
    ? activeToolLabel.replace(/[.…]+$/, "")
    : elapsedSecs >= 10
    ? "Waking up the server"
    : "Thinking";

  return (
    <div className="thinking-indicator-wrapper" role="status" aria-live="polite">
      <div className="thinking-active-step-row">
        <span className="step-title-animated">{label}…</span>
        <div className="typing-dots-animated" aria-hidden="true">
          <span></span>
          <span></span>
          <span></span>
        </div>
        {elapsedSecs >= 3 && <span className="thinking-badge-timer">{elapsedSecs}s</span>}
      </div>
      {elapsedSecs >= 10 && !activeToolLabel && (
        <p className="thinking-slow-note">
          The first reply after a quiet period can take up to a minute while the server starts. Please keep this
          page open.
        </p>
      )}
      <div className="thinking-progress-track indeterminate" aria-hidden="true">
        <div className="thinking-indeterminate-bar" />
      </div>
    </div>
  );
}
