import { useState, useEffect } from "react";
import { renderUniIcon } from "./Icons";
import "./ThinkingIndicator.css";

export const THINKING_STEPS = [
  { icon: "🔍", label: "Reviewing your enquiry..." },
  { icon: "📘", label: "Assessing university regulations..." },
  { icon: "⚖️", label: "Evaluating academic criteria..." },
  { icon: "📋", label: "Verifying applicable policies..." },
  { icon: "✨", label: "Preparing your response..." },
];

export default function ThinkingIndicator() {
  const [currentStepIdx, setCurrentStepIdx] = useState(0);
  const [elapsedSecs, setElapsedSecs] = useState(0);

  useEffect(() => {
    // Progress through thinking steps every 1.5 seconds
    const stepTimer = setInterval(() => {
      setCurrentStepIdx((prev) => (prev < THINKING_STEPS.length - 1 ? prev + 1 : prev));
    }, 1500);

    // Track total seconds elapsed
    const elapsedTimer = setInterval(() => {
      setElapsedSecs((s) => s + 1);
    }, 1000);

    return () => {
      clearInterval(stepTimer);
      clearInterval(elapsedTimer);
    };
  }, []);

  const activeStep = THINKING_STEPS[currentStepIdx];

  return (
    <div className="thinking-indicator-wrapper">
      <div className="thinking-top-row">
        <div className="thinking-badge-group">
          <span className="thinking-badge-step">
            Step {currentStepIdx + 1} of {THINKING_STEPS.length}
          </span>
          <span className="thinking-badge-timer">{elapsedSecs}s</span>
        </div>
        <div className="typing-dots-animated" aria-hidden="true">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>

      <div className="thinking-active-step-row">
        <span className="step-icon-bubble">
          {renderUniIcon(activeStep.icon, 20, "step-sru-icon-svg") || activeStep.icon}
        </span>
        <span className="step-title-animated">{activeStep.label}</span>
      </div>

      <div className="thinking-progress-track">
        {THINKING_STEPS.map((_, idx) => (
          <div
            key={idx}
            className={`thinking-step-segment ${
              idx === currentStepIdx
                ? "active"
                : idx < currentStepIdx
                ? "completed"
                : ""
            }`}
          />
        ))}
      </div>
    </div>
  );
}
