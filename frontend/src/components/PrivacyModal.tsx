import { useState } from "react";
import { deleteMyData } from "../services/api";
import "./PrivacyModal.css";

interface Props {
  sessionId: string;
  onClose: () => void;
  onDataPurged?: () => void;
}

export default function PrivacyModal({ sessionId, onClose, onDataPurged }: Props) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const handleDeleteData = async () => {
    if (!window.confirm("Are you sure you want to permanently delete all your conversation history and submitted inquiries? This action cannot be undone.")) {
      return;
    }

    setIsDeleting(true);
    setMessage(null);
    try {
      const res = await deleteMyData({ session_id: sessionId });
      setMessage({
        text: `Success: ${res.message} (${res.deleted_messages} messages and ${res.deleted_conversations} conversations removed).`,
        type: "success",
      });
      if (onDataPurged) {
        onDataPurged();
      }
    } catch (err: any) {
      setMessage({
        text: err?.message || "Failed to delete user data. Please try again.",
        type: "error",
      });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="privacy-modal-overlay" onClick={onClose}>
      <div className="privacy-modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="privacy-modal-header">
          <div className="privacy-modal-title">
            <span>🛡️</span> Privacy & DPDP Notice
          </div>
          <button className="privacy-modal-close-btn" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="privacy-modal-body">
          <div className="privacy-point">
            <h4>Admissions Assistance & Recording</h4>
            <p>
              Chats and inquiries are processed to provide accurate admissions, program, fee, and scholarship information. Chats may be recorded for service quality and verification.
            </p>
          </div>

          <div className="privacy-point">
            <h4>Data Masking & Protection (DPDP Compliant)</h4>
            <p>
              Under the Digital Personal Data Protection Act, phone numbers and emails submitted in conversations or benchmarks are masked before recording in evaluation logs.
            </p>
          </div>

          <div className="privacy-point">
            <h4>Retention Schedule</h4>
            <p>
              Conversation messages and evaluation logs are retained for a maximum of 90 days, after which they are automatically pruned.
            </p>
          </div>

          <div className="privacy-point">
            <h4>Right to Erasure (Delete My Data)</h4>
            <p>
              You may exercise your right to erasure at any time. Clicking the button below will immediately hard-delete all messages, inquiries, and records tied to this browser session.
            </p>
          </div>

          {message && (
            <div className={`privacy-status-msg ${message.type}`}>
              {message.text}
            </div>
          )}
        </div>

        <div className="privacy-modal-actions">
          <button
            type="button"
            className="privacy-delete-btn"
            onClick={handleDeleteData}
            disabled={isDeleting}
          >
            {isDeleting ? "Erasing Data..." : "Delete My Data"}
          </button>
          <button type="button" className="privacy-dismiss-btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
