import { useState } from "react";
import type { MessageData } from "../services/api";
import { stripMarkdown } from "../utils/cleanCopy";
import "./ShareModal.css";

interface Props {
  conversationId: string | null;
  title: string;
  messages: MessageData[];
  onClose: () => void;
  onExportPDF: () => void;
  onExportMD: () => void;
}

export default function ShareModal({
  conversationId,
  title,
  messages,
  onClose,
  onExportPDF,
  onExportMD,
}: Props) {
  const [copied, setCopied] = useState(false);

  // Generate share link with conversation identifier
  const shareUrl = `${window.location.origin}${window.location.pathname}?chat=${conversationId || "share"}`;

  const firstUserMsg = messages.find((m) => m.role === "user")?.content || "Conversation with SRU Buddy";
  const firstAssistantMsg = messages.find((m) => m.role === "assistant")?.content || "";

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // Fallback
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  const handleWhatsAppShare = () => {
    const text = encodeURIComponent(`Check out this conversation with SRU Buddy:\n"${title || firstUserMsg.slice(0, 60)}"\n${shareUrl}`);
    window.open(`https://api.whatsapp.com/send?text=${text}`, "_blank");
  };

  const handleEmailShare = () => {
    const subject = encodeURIComponent(`SRU Buddy Chat: ${title || "SR University Discussion"}`);
    const body = encodeURIComponent(
      `Hi,\n\nHere is a conversation from SRU Buddy (SR University AI Agent):\n\n${shareUrl}\n\nSummary:\n${stripMarkdown(firstUserMsg).slice(0, 150)}...\n`
    );
    window.open(`mailto:?subject=${subject}&body=${body}`, "_blank");
  };

  return (
    <div className="share-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="share-modal-card" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="share-modal-header">
          <div className="share-modal-title-group">
            <span className="share-header-icon">🔗</span>
            <h3 className="share-modal-title">Share link to Chat</h3>
          </div>
          <button className="share-close-btn" onClick={onClose} aria-label="Close modal">
            ✕
          </button>
        </div>

        <p className="share-modal-subtitle">
          Anyone with this link will be able to view this conversation snapshot.
        </p>

        {/* Conversation Snapshot Preview */}
        <div className="share-preview-box">
          <div className="preview-meta-row">
            <span className="preview-chat-title">{title || "Untitled Conversation"}</span>
            <span className="preview-msg-count">{messages.length} messages</span>
          </div>
          <div className="preview-snippet">
            <div className="preview-user-bubble">
              <span className="preview-role-label">You:</span>
              <span className="preview-text">{stripMarkdown(firstUserMsg).slice(0, 95)}...</span>
            </div>
            {firstAssistantMsg && (
              <div className="preview-assistant-bubble">
                <span className="preview-role-label">SRU Buddy:</span>
                <span className="preview-text">{stripMarkdown(firstAssistantMsg).slice(0, 110)}...</span>
              </div>
            )}
          </div>
        </div>

        {/* Share Link Copy Field */}
        <div className="share-url-group">
          <input
            type="text"
            readOnly
            value={shareUrl}
            className="share-url-input"
            onClick={(e) => (e.target as HTMLInputElement).select()}
          />
          <button
            className={`share-copy-btn ${copied ? "copied" : ""}`}
            onClick={handleCopyLink}
          >
            {copied ? (
              <>
                <span>✓</span>
                <span>Copied!</span>
              </>
            ) : (
              <>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                </svg>
                <span>Copy Link</span>
              </>
            )}
          </button>
        </div>

        {/* Direct Action Channels */}
        <div className="share-channels-row">
          <button className="share-channel-btn" onClick={handleWhatsAppShare} title="Share to WhatsApp">
            <span className="channel-icon">💬</span>
            <span>WhatsApp</span>
          </button>
          <button className="share-channel-btn" onClick={handleEmailShare} title="Share via Email">
            <span className="channel-icon">✉️</span>
            <span>Email</span>
          </button>
          <button className="share-channel-btn" onClick={onExportPDF} title="Save / Print as PDF">
            <span className="channel-icon">📄</span>
            <span>Print PDF</span>
          </button>
          <button className="share-channel-btn" onClick={onExportMD} title="Download Markdown">
            <span className="channel-icon">📝</span>
            <span>Markdown</span>
          </button>
        </div>

        <div className="share-modal-footer">
          <span>SRU Buddy • Your AI Agent • SR University</span>
        </div>
      </div>
    </div>
  );
}
