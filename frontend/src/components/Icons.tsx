import React from "react";

export interface IconProps {
  size?: number | string;
  className?: string;
  color?: string;
  strokeWidth?: number;
}

/**
 * Clean, modern SVG icon set for SR University Companion
 * Crisp geometry, consistent 24x24 viewBox, accessible and theme-reactive.
 */

export const CapIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
    <path d="M6 12v5c0 2 3 3 6 3s6-1 6-3v-5" />
  </svg>
);

export const CalculatorIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <rect x="4" y="2" width="16" height="20" rx="2" />
    <line x1="8" y1="6" x2="16" y2="6" />
    <line x1="16" y1="14" x2="16" y2="18" />
    <path d="M16 10h.01M12 10h.01M8 10h.01M12 14h.01M8 14h.01M12 18h.01M8 18h.01" />
  </svg>
);

export const RupeeIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M6 3h12M6 8h12M6 13l8.5 8M6 13h3a4 4 0 0 0 0-8" />
  </svg>
);

export const AwardIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <circle cx="12" cy="8" r="6" />
    <path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11" />
  </svg>
);

export const SparklesIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z" />
    <path d="M5 3v4M3 5h4M19 17v4M17 19h4" />
  </svg>
);

export const BuildingIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <rect x="4" y="2" width="16" height="20" rx="2" />
    <path d="M9 22v-4h6v4M8 6h.01M16 6h.01M12 6h.01M12 10h.01M12 14h.01M16 10h.01M16 14h.01M8 10h.01M8 14h.01" />
  </svg>
);

export const BedIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M2 4v16M2 8h18a2 2 0 0 1 2 2v10M2 17h20M6 8v9" />
  </svg>
);

export const BriefcaseIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <rect x="2" y="7" width="20" height="14" rx="2" />
    <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
  </svg>
);

export const TrendingUpIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
    <polyline points="16 7 22 7 22 13" />
  </svg>
);

export const FlaskIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M10 2v7.527a2 2 0 0 1-.211.896L4.72 20.55a1 1 0 0 0 .9 1.45h12.76a1 1 0 0 0 .9-1.45l-5.069-10.127A2 2 0 0 1 14 9.527V2" />
    <path d="M8.5 2h7M7 16h10" />
  </svg>
);

export const CalendarIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <rect x="3" y="4" width="18" height="18" rx="2" />
    <line x1="16" y1="2" x2="16" y2="6" />
    <line x1="8" y1="2" x2="8" y2="6" />
    <line x1="3" y1="10" x2="21" y2="10" />
  </svg>
);

export const ClockIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />
  </svg>
);

export const BusIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M8 6v6M16 6v6M4 11h16" />
    <rect x="3" y="3" width="18" height="15" rx="3" />
    <circle cx="7" cy="18" r="2" />
    <circle cx="17" cy="18" r="2" />
  </svg>
);

export const VideoIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <polygon points="23 7 16 12 23 17 23 7" />
    <rect x="1" y="5" width="15" height="14" rx="2" />
  </svg>
);

export const HeartHandIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" />
  </svg>
);

export const PinIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <line x1="12" y1="17" x2="12" y2="22" />
    <path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.89A2 2 0 0 1 15 10.77V5a3 3 0 0 0-6 0v5.77a2 2 0 0 1-1.11 1.79l-1.78.89A2 2 0 0 0 5 15.24Z" />
  </svg>
);

export const AlertTriangleIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

export const InfoIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="16" x2="12" y2="12" />
    <line x1="12" y1="8" x2="12.01" y2="8" />
  </svg>
);

export const ShieldCheckIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    <path d="m9 12 2 2 4-4" />
  </svg>
);

export const CheckIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

export const CloseIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

export const MessageSquareIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

export const FileTextIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
    <polyline points="10 9 9 9 8 9" />
  </svg>
);

export const BoltIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </svg>
);

export const ScaleIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
    <path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
    <path d="M7 21h10" />
    <path d="M12 3v18" />
    <path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2" />
  </svg>
);

export const TargetIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <circle cx="12" cy="12" r="10" />
    <circle cx="12" cy="12" r="6" />
    <circle cx="12" cy="12" r="2" />
  </svg>
);

export const BookOpenIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
  </svg>
);

export const RefreshIcon: React.FC<IconProps> = ({ size = 18, className = "", color = "currentColor", strokeWidth = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
  </svg>
);

/**
 * =======================================================================
 * SR UNIVERSITY MINIMAL EXECUTIVE VECTOR ICONS
 * Designed exclusively for SR University Brand Theme:
 * - Royal Blue:  #0055a4 (Primary Academic)
 * - Sky Blue:    #2979e2 (Accent / Light Contrast)
 * - Amber Gold:  #f59e0b (Merit / Highlight)
 * - Emerald:     #10b981 (Success / Criteria Met)
 *
 * Minimalist, transparent-background line art that sits seamlessly in text,
 * chips, and cards without chunky 3D borders or cluttered shadows.
 * =======================================================================
 */

export const SruLensIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <circle cx="11" cy="11" r="7" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M21 21l-4.35-4.35" stroke="#0055a4" strokeWidth="2.2" strokeLinecap="round" />
    <circle cx="11" cy="11" r="3.2" fill="#2979e2" fillOpacity="0.22" />
    <path d="M9 9l4 4" stroke="#2979e2" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
);

export const SruHandbookIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M12 2v8l2.5-1.5L17 10V2" fill="#f59e0b" stroke="#f59e0b" strokeWidth="1.2" strokeLinejoin="round" />
    <line x1="8" y1="13" x2="16" y2="13" stroke="#2979e2" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

export const SruEvaluationIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <path d="M12 3v18M7 21h10" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M4 7h16" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" />
    <path d="M4 7l3 6h-6l3-6z" fill="#2979e2" fillOpacity="0.25" stroke="#0055a4" strokeWidth="1.6" strokeLinejoin="round" />
    <path d="M20 7l3 6h-6l3-6z" fill="#2979e2" fillOpacity="0.25" stroke="#0055a4" strokeWidth="1.6" strokeLinejoin="round" />
    <circle cx="12" cy="4" r="1.5" fill="#f59e0b" />
  </svg>
);

export const SruPolicyIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <rect x="8" y="2" width="8" height="4" rx="1.5" stroke="#0055a4" strokeWidth="1.8" fill="#ffffff" />
    <path d="M9 13.5l2 2 4.5-4.5" stroke="#10b981" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    <line x1="9" y1="18" x2="15" y2="18" stroke="#2979e2" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

export const SruSparkleIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <path d="M12 2C12 7.5 7.5 12 2 12C7.5 12 12 16.5 12 22C12 16.5 16.5 12 22 12C16.5 12 12 7.5 12 2Z" fill="#0055a4" />
    <path d="M19 3C19 4.7 17.7 6 16 6C17.7 6 19 7.3 19 9C19 7.3 20.3 6 22 6C20.3 6 19 4.7 19 3Z" fill="#f59e0b" />
    <circle cx="6" cy="18" r="1.5" fill="#2979e2" />
  </svg>
);

export const SruCapIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <path d="M22 10v6M2 10l10-5 10 5-10 5z" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M6 12v5c0 2 3 3 6 3s6-1 6-3v-5" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M22 10v6" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
    <circle cx="22" cy="16.5" r="1.5" fill="#f59e0b" />
  </svg>
);

export const SruCalcIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <rect x="4" y="2" width="16" height="20" rx="3" stroke="#0055a4" strokeWidth="2" />
    <rect x="7" y="5" width="10" height="3" rx="1" fill="#2979e2" fillOpacity="0.25" stroke="#2979e2" strokeWidth="1" />
    <circle cx="8" cy="12" r="1.2" fill="#0055a4" />
    <circle cx="12" cy="12" r="1.2" fill="#0055a4" />
    <circle cx="16" cy="12" r="1.2" fill="#f59e0b" />
    <circle cx="8" cy="16" r="1.2" fill="#0055a4" />
    <circle cx="12" cy="16" r="1.2" fill="#0055a4" />
    <circle cx="16" cy="16" r="1.2" fill="#f59e0b" />
  </svg>
);

export const SruFeeIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <circle cx="12" cy="12" r="10" stroke="#0055a4" strokeWidth="2" />
    <path d="M8 7h8M8 10.5h8M8 14l5.5 5M8 14h2.5a3 3 0 0 0 0-6" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const SruPlacementIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <rect x="2" y="7" width="20" height="14" rx="2.5" stroke="#0055a4" strokeWidth="2" />
    <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M2 13h20" stroke="#2979e2" strokeWidth="1.5" />
    <circle cx="12" cy="13" r="1.8" fill="#f59e0b" stroke="#0055a4" strokeWidth="1.2" />
  </svg>
);

export const SruStatsIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <path d="M3 3v18h18" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <rect x="6" y="13" width="3" height="5" rx="1" fill="#2979e2" fillOpacity="0.4" stroke="#2979e2" strokeWidth="1.2" />
    <rect x="11" y="9" width="3" height="9" rx="1" fill="#0055a4" fillOpacity="0.5" stroke="#0055a4" strokeWidth="1.2" />
    <rect x="16" y="5" width="3" height="13" rx="1" fill="#10b981" fillOpacity="0.6" stroke="#10b981" strokeWidth="1.2" />
    <path d="M6 11l5-4 5-2 3-2" stroke="#f59e0b" strokeWidth="1.8" strokeLinecap="round" />
  </svg>
);

export const SruHostelIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <path d="M3 10l9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V10z" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <rect x="9" y="13" width="6" height="8" rx="1" fill="#2979e2" fillOpacity="0.3" stroke="#0055a4" strokeWidth="1.6" />
    <circle cx="12" cy="7.5" r="1.5" fill="#f59e0b" />
  </svg>
);

export const SruLabIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <path d="M9 3h6M10 3v6l-4.5 9A1.5 1.5 0 0 0 6.8 20h10.4a1.5 1.5 0 0 0 1.3-2L14 9V3" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M7.5 15h9l1.5 3H6z" fill="#2979e2" fillOpacity="0.35" />
    <circle cx="11" cy="16.5" r="1" fill="#ffffff" />
    <circle cx="14" cy="17" r="0.75" fill="#ffffff" />
  </svg>
);

export const SruRocketIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z" stroke="#f59e0b" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" fill="#f59e0b" fillOpacity="0.25" />
    <path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="15.5" cy="8.5" r="1.8" fill="#2979e2" stroke="#0055a4" strokeWidth="1" />
  </svg>
);

export const SruTargetIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <circle cx="12" cy="12" r="10" stroke="#0055a4" strokeWidth="2" />
    <circle cx="12" cy="12" r="6" stroke="#2979e2" strokeWidth="1.8" />
    <circle cx="12" cy="12" r="2.5" fill="#f59e0b" stroke="#f59e0b" strokeWidth="1" />
  </svg>
);

export const SruCampusIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <path d="M2 9.5L12 4l10 5.5v1.5H2v-1.5z" fill="#0055a4" stroke="#0055a4" strokeWidth="1.5" strokeLinejoin="round" />
    <line x1="5" y1="11" x2="5" y2="19" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" />
    <line x1="9.5" y1="11" x2="9.5" y2="19" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" />
    <line x1="14.5" y1="11" x2="14.5" y2="19" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" />
    <line x1="19" y1="11" x2="19" y2="19" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" />
    <path d="M2 19h20v2.5H2z" fill="#2979e2" stroke="#0055a4" strokeWidth="1.5" strokeLinejoin="round" />
    <circle cx="12" cy="7.2" r="1" fill="#f59e0b" />
  </svg>
);

export const SruTechIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="#2979e2" fillOpacity="0.25" />
    <polygon points="13 2 7 13 12 13 11 20 18 11 13 11 13 2" fill="#f59e0b" />
  </svg>
);

export const SruVideoIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <rect x="2" y="5" width="14" height="14" rx="3" stroke="#0055a4" strokeWidth="2" />
    <polygon points="16 9 22 5 22 19 16 15" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="#2979e2" fillOpacity="0.3" />
    <polygon points="7 9 12 12 7 15" fill="#f59e0b" />
  </svg>
);

export const SruHandshakeIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <path d="M11 15h2l4-4-2-2-4 4-2-2-4 4 2 2 3-1" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M18 11l3 3-5 5-3-3" stroke="#2979e2" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M6 13L3 10l5-5 3 3" stroke="#0055a4" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const SruSunIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <circle cx="12" cy="12" r="5" stroke="#f59e0b" strokeWidth="2" fill="#f59e0b" fillOpacity="0.25" />
    <line x1="12" y1="2" x2="12" y2="4" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
    <line x1="12" y1="20" x2="12" y2="22" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
    <line x1="2" y1="12" x2="4" y2="12" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
    <line x1="20" y1="12" x2="22" y2="12" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

export const SruMoonIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="#2979e2" fillOpacity="0.2" />
    <circle cx="17" cy="8" r="1" fill="#f59e0b" />
  </svg>
);

export const SruWaveIcon: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <path d="M7 11V5a2 2 0 0 1 4 0v5M11 6a2 2 0 0 1 4 0v5M15 8a2 2 0 0 1 4 0v5a7 7 0 0 1-7 7 7 7 0 0 1-7-7v-3a2 2 0 0 1 4 0v2" stroke="#0055a4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M2 7a4 4 0 0 1 3-3" stroke="#2979e2" strokeWidth="1.8" strokeLinecap="round" />
    <path d="M1 11a7 7 0 0 1 4-6" stroke="#f59e0b" strokeWidth="1.8" strokeLinecap="round" />
  </svg>
);

export const SruCloseBadge: React.FC<IconProps> = ({ size = 18, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={`sru-uni-icon ${className}`}>
    <circle cx="12" cy="12" r="9" stroke="#64748b" strokeWidth="1.8" />
    <line x1="15" y1="9" x2="9" y2="15" stroke="#64748b" strokeWidth="2" strokeLinecap="round" />
    <line x1="9" y1="9" x2="15" y2="15" stroke="#64748b" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

// Backwards compatibility aliases
export const SruLensBadge = SruLensIcon;
export const SruHandbookBadge = SruHandbookIcon;
export const SruEvaluationBadge = SruEvaluationIcon;
export const SruPolicyBadge = SruPolicyIcon;
export const SruSparkleBadge = SruSparkleIcon;
export const SruCapBadge = SruCapIcon;
export const SruCalcBadge = SruCalcIcon;
export const SruFeeBadge = SruFeeIcon;
export const SruPlacementBadge = SruPlacementIcon;
export const SruStatsBadge = SruStatsIcon;
export const SruHostelBadge = SruHostelIcon;
export const SruLabBadge = SruLabIcon;
export const SruRocketBadge = SruRocketIcon;
export const SruTargetBadge = SruTargetIcon;
export const SruCampusBadge = SruCampusIcon;
export const SruTechBadge = SruTechIcon;
export const SruVideoBadge = SruVideoIcon;
export const SruHandshakeBadge = SruHandshakeIcon;

/**
 * Universal resolver to match legacy or dynamic emoji keys to vector SVG icons.
 * Fully customized for SR University official brand aesthetic.
 */
export function renderUniIcon(keyOrEmoji: string, size = 16, className = ""): React.ReactNode {
  const clean = keyOrEmoji.replace(/[\uFE0E\uFE0F]/g, "").trim().toLowerCase();
  switch (clean) {
    case "🔍":
    case "🔎":
    case "search":
    case "query":
    case "enquiry":
    case "reviewing":
      return <SruLensIcon size={size} className={className} />;
    case "📘":
    case "book-blue":
    case "handbook":
    case "regulations":
      return <SruHandbookIcon size={size} className={className} />;
    case "⚖":
    case "⚖️":
    case "scale":
    case "criteria":
    case "evaluating":
    case "compare":
    case "vs":
    case "🆚":
      return <SruEvaluationIcon size={size} className={className} />;
    case "📋":
    case "document":
    case "policy":
    case "policies":
    case "verifying":
    case "apply":
      return <SruPolicyIcon size={size} className={className} />;
    case "✨":
    case "sparkle":
    case "sparkles":
    case "preparing":
    case "synthesis":
    case "ai":
      return <SruSparkleIcon size={size} className={className} />;
    case "🎓":
    case "cap":
    case "degree":
    case "academic":
    case "course":
    case "btech":
    case "mtech":
      return <SruCapIcon size={size} className={className} />;
    case "🧮":
    case "calculator":
    case "calc":
    case "scholarship":
      return <SruCalcIcon size={size} className={className} />;
    case "💰":
    case "💳":
    case "💵":
    case "₹":
    case "rupee":
    case "fee":
    case "fees":
    case "tuition":
      return <SruFeeIcon size={size} className={className} />;
    case "💼":
    case "briefcase":
    case "placement":
    case "job":
    case "recruiters":
    case "mba":
      return <SruPlacementIcon size={size} className={className} />;
    case "📈":
    case "📊":
    case "trending":
    case "growth":
    case "stats":
    case "highest":
      return <SruStatsIcon size={size} className={className} />;
    case "🏠":
    case "bed":
    case "hostel":
    case "room":
    case "mess":
    case "housing":
      return <SruHostelIcon size={size} className={className} />;
    case "🔬":
    case "flask":
    case "lab":
    case "labs":
    case "research":
      return <SruLabIcon size={size} className={className} />;
    case "🚀":
    case "rocket":
    case "srix":
    case "incubator":
    case "startup":
      return <SruRocketIcon size={size} className={className} />;
    case "🎯":
    case "target":
    case "cutoff":
    case "goal":
      return <SruTargetIcon size={size} className={className} />;
    case "🏢":
    case "🏫":
    case "🏛️":
    case "🏛":
    case "building":
    case "campus":
    case "university":
    case "sru":
      return <SruCampusIcon size={size} className={className} />;
    case "⚡":
    case "bolt":
    case "ece":
    case "tech":
    case "engineering":
      return <SruTechIcon size={size} className={className} />;
    case "🎥":
    case "video":
    case "tour":
      return <SruVideoIcon size={size} className={className} />;
    case "🤝":
    case "handshake":
    case "special":
    case "support":
    case "aid":
      return <SruHandshakeIcon size={size} className={className} />;
    case "☀️":
    case "sun":
    case "morning":
    case "day":
      return <SruSunIcon size={size} className={className} />;
    case "🌙":
    case "moon":
    case "evening":
    case "night":
      return <SruMoonIcon size={size} className={className} />;
    case "👋":
    case "wave":
    case "hello":
    case "hi":
      return <SruWaveIcon size={size} className={className} />;
    case "❌":
    case "close":
    case "dismiss":
    case "no":
      return <SruCloseBadge size={size} className={className} />;
    case "🎉":
    case "award":
    case "trophy":
      return <AwardIcon size={size} className={className} color="#f59e0b" />;
    case "❤️":
    case "heart":
    case "care":
      return <HeartHandIcon size={size} className={className} color="#0055a4" />;
    case "📌":
    case "pin":
      return <PinIcon size={size} className={className} color="#0055a4" />;
    case "⚠️":
    case "warning":
    case "alert":
      return <AlertTriangleIcon size={size} className={className} color="#f59e0b" />;
    case "ℹ️":
    case "info":
      return <InfoIcon size={size} className={className} color="#0055a4" />;
    case "🛡️":
    case "shield":
      return <ShieldCheckIcon size={size} className={className} color="#10b981" />;
    case "📚":
    case "book":
    case "curriculum":
      return <BookOpenIcon size={size} className={className} color="#0055a4" />;
    case "💬":
    case "chat":
    case "message":
      return <MessageSquareIcon size={size} className={className} color="#0055a4" />;
    case "📅":
    case "calendar":
      return <CalendarIcon size={size} className={className} color="#0055a4" />;
    case "🕒":
    case "clock":
    case "time":
      return <ClockIcon size={size} className={className} color="#64748b" />;
    case "🚌":
    case "bus":
    case "transport":
      return <BusIcon size={size} className={className} color="#0055a4" />;
    default:
      return null;
  }
}
