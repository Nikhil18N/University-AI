import React, { useEffect, useState } from "react";
import { CloseIcon, CheckIcon, ShieldCheckIcon } from "./Icons";
import {
  PROFILE_EVENT,
  cleanPhone,
  fetchServerProfile,
  forgetStudentDetails,
  readStudentDetails,
  saveStudentDetails,
} from "../utils/studentProfile";
import "./LeadAuthModal.css";

interface Props {
  isOpen: boolean;
  sessionId: string;
  onClose: () => void;
}

/**
 * Settings > My details. Shows the same name and mobile number the chat uses, lets the student
 * change them (the change also reaches any saved callback / visit request), or forget them.
 */
export default function SettingsModal({ isOpen, sessionId, onClose }: Props) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [openRequest, setOpenRequest] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    const fill = () => {
      const local = readStudentDetails();
      setName(local?.name || "");
      setPhone(local?.phone || "");
      setOpenRequest(local?.open_request || null);
    };
    fill();
    setError(null);
    setSaved(null);
    // The server copy is the truth: a number changed in the chat shows up here.
    fetchServerProfile(sessionId)
      .then((profile) => {
        if (typeof profile.name === "string" && profile.name) setName(profile.name);
        if (typeof profile.phone === "string" && profile.phone) setPhone(profile.phone);
        setOpenRequest(typeof profile.open_request === "string" ? profile.open_request : null);
      })
      .catch(() => {
        /* offline: the browser copy is shown */
      });
    window.addEventListener(PROFILE_EVENT, fill);
    return () => window.removeEventListener(PROFILE_EVENT, fill);
  }, [isOpen, sessionId]);

  if (!isOpen) return null;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaved(null);
    if (name.trim().length < 2) {
      setError("Please enter your full name.");
      return;
    }
    if (!cleanPhone(phone)) {
      setError("Please enter a valid 10-digit mobile number.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const details = await saveStudentDetails(sessionId, { name, phone });
      setName(details.name);
      setPhone(details.phone);
      setSaved("Saved. The chat and your saved requests now use these details.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const handleForget = async () => {
    setBusy(true);
    await forgetStudentDetails(sessionId);
    setName("");
    setPhone("");
    setOpenRequest(null);
    setBusy(false);
    setError(null);
    setSaved("Your details were removed from this browser and from SRU Buddy's memory.");
  };

  return (
    <div className="lead-modal-backdrop" onClick={onClose}>
      <div className="lead-modal-card" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="My details">
        <div className="lead-modal-header">
          <div className="lead-icon-badge" aria-hidden="true">
            <ShieldCheckIcon size={22} />
          </div>
          <div>
            <h3 className="lead-title">My details</h3>
            <p className="lead-subtitle">The name and mobile number SRU Buddy uses for you</p>
          </div>
          <button className="lead-close-btn" onClick={onClose} aria-label="Close" type="button">
            <CloseIcon size={18} />
          </button>
        </div>

        <div className="lead-prompt-banner">
          <span>
            {openRequest
              ? `You have a ${openRequest}. If you change your number here, that request is updated too.`
              : "These are used only when you ask for a counsellor callback or a campus visit. You can change or remove them at any time."}
          </span>
        </div>

        <form onSubmit={handleSave} className="lead-form">
          <div className="lead-field">
            <label htmlFor="settings-name-input">Full name</label>
            <input
              id="settings-name-input"
              type="text"
              className="lead-input"
              placeholder="Enter your full name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setError(null);
              }}
              maxLength={80}
            />
          </div>
          <div className="lead-field">
            <label htmlFor="settings-phone-input">Mobile number</label>
            <input
              id="settings-phone-input"
              type="tel"
              inputMode="numeric"
              className="lead-input"
              placeholder="10-digit mobile number"
              value={phone}
              onChange={(e) => {
                setPhone(e.target.value);
                setError(null);
              }}
              maxLength={15}
            />
          </div>

          {error && <div className="lead-error-text">{error}</div>}
          {saved && (
            <div className="lead-prompt-banner" role="status">
              <CheckIcon size={14} /> <span>{saved}</span>
            </div>
          )}

          <button type="submit" className="lead-submit-btn" disabled={busy}>
            {busy ? "Saving..." : "Save details"}
          </button>
          <button
            type="button"
            className="lead-skip-btn"
            onClick={handleForget}
            disabled={busy || (!name && !phone)}
            style={{ marginTop: 8 }}
          >
            Forget my details
          </button>
        </form>
      </div>
    </div>
  );
}
