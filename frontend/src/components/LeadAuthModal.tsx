import React, { useState } from "react";
import { ShieldCheckIcon, CloseIcon, BoltIcon } from "./Icons";
import { createLead } from "../services/api";
import "./LeadAuthModal.css";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (lead: { name: string; phone: string }) => void;
  programInterest?: string;
  reasonText?: string;
}

export default function LeadAuthModal({
  isOpen,
  onClose,
  onSuccess,
  programInterest,
  reasonText,
}: Props) {
  const [name, setName] = useState<string>(() => {
    try {
      const saved = localStorage.getItem("sru_student_lead");
      return saved ? JSON.parse(saved).name || "" : "";
    } catch {
      return "";
    }
  });

  const [phone, setPhone] = useState<string>(() => {
    try {
      const saved = localStorage.getItem("sru_student_lead");
      return saved ? JSON.parse(saved).phone || "" : "";
    } catch {
      return "";
    }
  });

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanName = name.trim();
    const cleanDigits = phone.replace(/\D/g, "");

    if (!cleanName) {
      setError("Please enter your full name.");
      return;
    }
    if (cleanDigits.length < 10) {
      setError("Please enter a valid 10-digit mobile number.");
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      localStorage.setItem(
        "sru_student_lead",
        JSON.stringify({ name: cleanName, phone: phone.trim() })
      );

      await createLead({
        name: cleanName,
        phone: phone.trim(),
        program_interest: programInterest || "B.Tech CSE",
        source: "chat_inquiry",
      });

      onSuccess({ name: cleanName, phone: phone.trim() });
      onClose();
    } catch (err: any) {
      console.warn("Lead registration note:", err);
      // Still allow continuation on network issue
      onSuccess({ name: cleanName, phone: phone.trim() });
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="lead-modal-backdrop" onClick={onClose}>
      <div className="lead-modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="lead-modal-header">
          <div className="lead-icon-badge" aria-hidden="true">
            <ShieldCheckIcon size={22} />
          </div>
          <div>
            <h3 className="lead-title">Student Verification</h3>
            <p className="lead-subtitle">SR University Admissions & Guidance Authentication</p>
          </div>
          <button className="lead-close-btn" onClick={onClose} aria-label="Close" type="button">
            <CloseIcon size={18} />
          </button>
        </div>

        <div className="lead-prompt-banner">
          <span>{reasonText || "To unlock official fee structures, scholarships, and priority admission counselling, please verify your student contact details."}</span>
        </div>

        <form onSubmit={handleSubmit} className="lead-form">
          <div className="lead-field">
            <label htmlFor="lead-name-input">Student Full Name *</label>
            <input
              id="lead-name-input"
              type="text"
              className="lead-input"
              placeholder="e.g. Rahul Sharma"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (error) setError(null);
              }}
              required
              autoFocus
            />
          </div>

          <div className="lead-field">
            <label htmlFor="lead-phone-input">10-Digit Mobile Number *</label>
            <input
              id="lead-phone-input"
              type="tel"
              className="lead-input"
              placeholder="e.g. 9876543210"
              value={phone}
              onChange={(e) => {
                setPhone(e.target.value);
                if (error) setError(null);
              }}
              maxLength={15}
              required
            />
          </div>

          {error && <div className="lead-error-text">{error}</div>}

          <div className="lead-actions">
            <button
              type="submit"
              className="lead-submit-btn"
              disabled={isSubmitting}
            >
              <BoltIcon size={16} />
              <span>{isSubmitting ? "Verifying..." : "Verify & Continue"}</span>
            </button>
            <button
              type="button"
              className="lead-skip-btn"
              onClick={onClose}
            >
              Continue without verification
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
