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
 * SR University Custom University Badges / Emojis
 * Designed specifically for SR University AI Companion workflows
 */

export const SruLensBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruLens_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruLens_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruLens_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruLens_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruLens_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruLens_glass)" />
    <circle cx="10.5" cy="10.5" r="4.8" stroke="url(#sruLens_gold)" strokeWidth="1.6" />
    <circle cx="10.5" cy="10.5" r="3.2" fill="#0284c7" fillOpacity="0.3" />
    <path d="M14 14L18.5 18.5" stroke="url(#sruLens_gold)" strokeWidth="2.2" strokeLinecap="round" />
    <path d="M10.5 7.8L11.2 9.7L13.1 10.5L11.2 11.3L10.5 13.2L9.8 11.3L7.9 10.5L9.8 9.7Z" fill="#ffffff" />
  </svg>
);

export const SruHandbookBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruBook_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruBook_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruBook_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruBook_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruBook_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruBook_glass)" />
    <path d="M4.5 6.5C7 5.5 11 5.8 12 7.2C13 5.8 17 5.5 19.5 6.5V17C17 16 13 16.3 12 17.8C11 16.3 7 16 4.5 17V6.5Z" fill="#003e7a" stroke="url(#sruBook_gold)" strokeWidth="1.2" strokeLinejoin="round" />
    <path d="M12 7.2V17.8" stroke="url(#sruBook_gold)" strokeWidth="1.2" />
    <line x1="6.5" y1="9.5" x2="10" y2="9.5" stroke="#fef08a" strokeWidth="0.9" strokeLinecap="round" />
    <line x1="6.5" y1="12" x2="10" y2="12" stroke="#fef08a" strokeWidth="0.9" strokeLinecap="round" />
    <line x1="6.5" y1="14.5" x2="9" y2="14.5" stroke="#fef08a" strokeWidth="0.9" strokeLinecap="round" />
    <line x1="14" y1="9.5" x2="17.5" y2="9.5" stroke="#fef08a" strokeWidth="0.9" strokeLinecap="round" />
    <line x1="14" y1="12" x2="17.5" y2="12" stroke="#fef08a" strokeWidth="0.9" strokeLinecap="round" />
    <line x1="14" y1="14.5" x2="16.5" y2="14.5" stroke="#fef08a" strokeWidth="0.9" strokeLinecap="round" />
    <path d="M11 5.5V9.5L12 8.5L13 9.5V5.5" fill="#ef4444" />
  </svg>
);

export const SruEvaluationBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruScale_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruScale_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruScale_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruScale_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruScale_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruScale_glass)" />
    <path d="M12 4.5L14 5.5L12 6.5L10 5.5Z" fill="url(#sruScale_gold)" />
    <path d="M12 6.5V18.5M8 18.5H16" stroke="url(#sruScale_gold)" strokeWidth="1.6" strokeLinecap="round" />
    <path d="M5.5 8.5H18.5" stroke="url(#sruScale_gold)" strokeWidth="1.6" strokeLinecap="round" />
    <path d="M5.5 8.5L4 13.5H7L5.5 8.5Z" stroke="#38bdf8" strokeWidth="0.9" fill="#003e7a" fillOpacity="0.4" />
    <path d="M3.5 13.5C3.5 14.6 4.4 15.5 5.5 15.5C6.6 15.5 7.5 14.6 7.5 13.5H3.5Z" fill="url(#sruScale_gold)" />
    <path d="M18.5 8.5L17 13.5H20L18.5 8.5Z" stroke="#38bdf8" strokeWidth="0.9" fill="#003e7a" fillOpacity="0.4" />
    <path d="M16.5 13.5C16.5 14.6 17.4 15.5 18.5 15.5C19.6 15.5 20.5 14.6 20.5 13.5H16.5Z" fill="url(#sruScale_gold)" />
  </svg>
);

export const SruPolicyBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruPolicy_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruPolicy_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruPolicy_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruPolicy_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruPolicy_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruPolicy_glass)" />
    <rect x="5.5" y="4.5" width="13" height="15" rx="1.5" fill="#003e7a" stroke="url(#sruPolicy_gold)" strokeWidth="1.2" />
    <rect x="9" y="3.5" width="6" height="2.2" rx="1" fill="url(#sruPolicy_gold)" />
    <line x1="8" y1="8" x2="16" y2="8" stroke="#ffffff" strokeWidth="1" strokeLinecap="round" />
    <line x1="8" y1="10.8" x2="16" y2="10.8" stroke="#ffffff" strokeWidth="1" strokeLinecap="round" />
    <line x1="8" y1="13.5" x2="13" y2="13.5" stroke="#ffffff" strokeWidth="1" strokeLinecap="round" />
    <circle cx="15.5" cy="15.5" r="3.2" fill="url(#sruPolicy_gold)" />
    <path d="M14.3 15.5L15.1 16.3L16.7 14.7" stroke="#002147" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const SruSparkleBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruSpark_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruSpark_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruSpark_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruSpark_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruSpark_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruSpark_glass)" />
    <circle cx="12" cy="12" r="7.5" stroke="#38bdf8" strokeWidth="1" strokeDasharray="3 2" opacity="0.65" />
    <path d="M12 4.5L13.5 9.8L18.5 12L13.5 14.2L12 19.5L10.5 14.2L5.5 12L10.5 9.8Z" fill="url(#sruSpark_gold)" />
    <path d="M16.5 6.5L17.1 8L18.5 8.5L17.1 9L16.5 10.5L15.9 9L14.5 8.5L15.9 8Z" fill="#38bdf8" />
    <circle cx="7" cy="16.5" r="1.3" fill="#ffffff" />
  </svg>
);

export const SruCapBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruCap_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruCap_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruCap_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruCap_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruCap_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruCap_glass)" />
    <path d="M12 5.5L20 9.5L12 13.5L4 9.5Z" fill="url(#sruCap_gold)" />
    <path d="M7 11V15.5C7 17.5 9.2 19 12 19C14.8 19 17 17.5 17 15.5V11" stroke="url(#sruCap_gold)" strokeWidth="1.4" fill="#003e7a" />
    <path d="M20 9.5V14.5" stroke="#fef08a" strokeWidth="1.2" strokeLinecap="round" />
    <circle cx="20" cy="15" r="1.2" fill="url(#sruCap_gold)" />
  </svg>
);

export const SruCalcBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruCalc_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruCalc_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruCalc_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruCalc_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruCalc_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruCalc_glass)" />
    <rect x="5.5" y="4.5" width="13" height="15" rx="2" fill="#003e7a" stroke="url(#sruCalc_gold)" strokeWidth="1.2" />
    <rect x="7" y="6" width="10" height="3" rx="0.8" fill="#fef08a" />
    <circle cx="8" cy="11.5" r="0.9" fill="#ffffff" />
    <circle cx="12" cy="11.5" r="0.9" fill="#ffffff" />
    <circle cx="16" cy="11.5" r="0.9" fill="url(#sruCalc_gold)" />
    <circle cx="8" cy="14.5" r="0.9" fill="#ffffff" />
    <circle cx="12" cy="14.5" r="0.9" fill="#ffffff" />
    <circle cx="16" cy="14.5" r="0.9" fill="url(#sruCalc_gold)" />
    <rect x="7.5" y="16.5" width="9" height="1.5" rx="0.75" fill="url(#sruCalc_gold)" />
  </svg>
);

export const SruFeeBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruFee_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruFee_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruFee_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruFee_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruFee_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruFee_glass)" />
    <circle cx="12" cy="12" r="6" stroke="url(#sruFee_gold)" strokeWidth="1.5" fill="#003e7a" />
    <path d="M9.5 8.5H14.5M9.5 10.8H14.5M9.5 8.5V12.5H11.5C13 12.5 13.8 11.8 13.8 10.5C13.8 9.2 12.8 8.5 11.5 8.5M11.5 12.5L14.5 16" stroke="url(#sruFee_gold)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const SruPlacementBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruJob_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruJob_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruJob_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruJob_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruJob_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruJob_glass)" />
    <rect x="4.5" y="8" width="15" height="11" rx="2" fill="#003e7a" stroke="url(#sruJob_gold)" strokeWidth="1.2" />
    <path d="M9 8V6.5C9 5.7 9.7 5 10.5 5H13.5C14.3 5 15 5.7 15 6.5V8" stroke="url(#sruJob_gold)" strokeWidth="1.2" />
    <line x1="4.5" y1="12" x2="19.5" y2="12" stroke="url(#sruJob_gold)" strokeWidth="1" />
    <circle cx="12" cy="12" r="1.5" fill="url(#sruJob_gold)" />
  </svg>
);

export const SruStatsBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruStats_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruStats_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruStats_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruStats_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruStats_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruStats_glass)" />
    <rect x="5.5" y="13.5" width="2.8" height="5" rx="0.6" fill="#38bdf8" />
    <rect x="9.5" y="10.5" width="2.8" height="8" rx="0.6" fill="#38bdf8" />
    <rect x="13.5" y="7.5" width="2.8" height="11" rx="0.6" fill="url(#sruStats_gold)" />
    <path d="M5.5 11.5L10.5 7.5L14.5 9.5L18.5 5.5" stroke="url(#sruStats_gold)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M15.5 5.5H18.5V8.5" stroke="url(#sruStats_gold)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const SruHostelBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruHostel_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruHostel_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruHostel_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruHostel_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruHostel_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruHostel_glass)" />
    <path d="M12 4.5L4.5 10.5H19.5L12 4.5Z" fill="url(#sruHostel_gold)" />
    <rect x="6" y="10.5" width="12" height="8" fill="#003e7a" stroke="url(#sruHostel_gold)" strokeWidth="1.2" />
    <rect x="10" y="13.5" width="4" height="5" fill="url(#sruHostel_gold)" rx="0.5" />
    <circle cx="8" cy="13" r="1.2" fill="#38bdf8" />
    <circle cx="16" cy="13" r="1.2" fill="#38bdf8" />
  </svg>
);

export const SruLabBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruLab_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruLab_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruLab_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruLab_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruLab_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruLab_glass)" />
    <path d="M10 5.5H14M11 5.5V9.5L6.5 17.5C5.8 18.6 6.6 20 8 20H16C17.4 20 18.2 18.6 17.5 17.5L13 9.5V5.5" stroke="url(#sruLab_gold)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M8 17L16 17L14.5 14L9.5 14Z" fill="#38bdf8" fillOpacity="0.8" />
    <circle cx="11.5" cy="16" r="0.8" fill="#ffffff" />
  </svg>
);

export const SruRocketBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruRocket_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruRocket_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruRocket_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruRocket_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruRocket_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruRocket_glass)" />
    <path d="M12 4.5C15 7 16 11 15 14L12 13L9 14C8 11 9 7 12 4.5Z" fill="url(#sruRocket_gold)" stroke="#ffffff" strokeWidth="0.8" />
    <circle cx="12" cy="8.5" r="1.3" fill="#002147" />
    <path d="M9 13.5L6.5 16L8 16.5L9 15" fill="#38bdf8" />
    <path d="M15 13.5L17.5 16L16 16.5L15 15" fill="#38bdf8" />
    <path d="M12 13.5V18.5M10.5 18L12 20L13.5 18" stroke="#ef4444" strokeWidth="1.4" strokeLinecap="round" />
  </svg>
);

export const SruTargetBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruTarget_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruTarget_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruTarget_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruTarget_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruTarget_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruTarget_glass)" />
    <circle cx="12" cy="12" r="6.8" stroke="url(#sruTarget_gold)" strokeWidth="1.2" />
    <circle cx="12" cy="12" r="4.2" stroke="#38bdf8" strokeWidth="1.2" fill="#003e7a" />
    <circle cx="12" cy="12" r="1.8" fill="url(#sruTarget_gold)" />
  </svg>
);

export const SruCampusBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruCampus_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruCampus_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruCampus_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruCampus_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruCampus_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruCampus_glass)" />
    <path d="M12 4.5L4.5 8.5H19.5L12 4.5Z" fill="url(#sruCampus_gold)" />
    <rect x="5.5" y="8.5" width="13" height="1.5" fill="#fef08a" />
    <line x1="7" y1="10" x2="7" y2="17.5" stroke="url(#sruCampus_gold)" strokeWidth="1.3" />
    <line x1="10.3" y1="10" x2="10.3" y2="17.5" stroke="url(#sruCampus_gold)" strokeWidth="1.3" />
    <line x1="13.7" y1="10" x2="13.7" y2="17.5" stroke="url(#sruCampus_gold)" strokeWidth="1.3" />
    <line x1="17" y1="10" x2="17" y2="17.5" stroke="url(#sruCampus_gold)" strokeWidth="1.3" />
    <rect x="4.5" y="17.5" width="15" height="1.8" fill="#fef08a" rx="0.4" />
  </svg>
);

export const SruTechBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruTech_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruTech_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruTech_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruTech_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruTech_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruTech_glass)" />
    <path d="M13 4.5L6.5 12.5H12L11 19.5L17.5 11.5H12L13 4.5Z" fill="url(#sruTech_gold)" stroke="#ffffff" strokeWidth="0.8" strokeLinejoin="round" />
  </svg>
);

export const SruVideoBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruVideo_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruVideo_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruVideo_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruVideo_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruVideo_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruVideo_glass)" />
    <rect x="4.5" y="6.5" width="11" height="11" rx="2" fill="#003e7a" stroke="url(#sruVideo_gold)" strokeWidth="1.2" />
    <path d="M15.5 10L19.5 7.5V16.5L15.5 14" fill="url(#sruVideo_gold)" />
    <path d="M8.5 9.5L12 12L8.5 14.5V9.5Z" fill="#ffffff" />
  </svg>
);

export const SruHandshakeBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruHand_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#0055a4" />
        <stop offset="60%" stopColor="#003e7a" />
        <stop offset="100%" stopColor="#002147" />
      </linearGradient>
      <linearGradient id="sruHand_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fef08a" />
        <stop offset="45%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#b45309" />
      </linearGradient>
      <linearGradient id="sruHand_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruHand_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruHand_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruHand_glass)" />
    <path d="M4.5 14L8.5 10L11 12.5L8.5 15L4.5 14Z" fill="url(#sruHand_gold)" />
    <path d="M19.5 14L15.5 10L13 12.5L15.5 15L19.5 14Z" fill="url(#sruHand_gold)" />
    <path d="M10 11.5L12 9.5L14 11.5L12 13.5L10 11.5Z" fill="#ffffff" />
  </svg>
);

export const SruCloseBadge: React.FC<IconProps> = ({ size = 20, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={`sru-badge-icon ${className}`}>
    <defs>
      <linearGradient id="sruClose_bg" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#991b1b" />
        <stop offset="100%" stopColor="#450a0a" />
      </linearGradient>
      <linearGradient id="sruClose_gold" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#fca5a5" />
        <stop offset="100%" stopColor="#ef4444" />
      </linearGradient>
      <linearGradient id="sruClose_glass" x1="0" y1="1" x2="0" y2="10.5" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.35" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>
    <rect x="1" y="1" width="22" height="22" rx="6" fill="url(#sruClose_bg)" />
    <rect x="1" y="1" width="22" height="22" rx="6" stroke="url(#sruClose_gold)" strokeWidth="1.2" />
    <path d="M1 7C1 3.69 3.69 1 7 1H17C20.31 1 23 3.69 23 7V10.5C16.5 12 7.5 12 1 10.5V7Z" fill="url(#sruClose_glass)" />
    <line x1="8" y1="8" x2="16" y2="16" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
    <line x1="16" y1="8" x2="8" y2="16" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

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
      return <SruLensBadge size={size} className={className} />;
    case "📘":
    case "book-blue":
    case "handbook":
    case "regulations":
      return <SruHandbookBadge size={size} className={className} />;
    case "⚖":
    case "⚖️":
    case "scale":
    case "criteria":
    case "evaluating":
    case "compare":
    case "vs":
    case "🆚":
      return <SruEvaluationBadge size={size} className={className} />;
    case "📋":
    case "document":
    case "policy":
    case "policies":
    case "verifying":
    case "apply":
      return <SruPolicyBadge size={size} className={className} />;
    case "✨":
    case "sparkle":
    case "sparkles":
    case "preparing":
    case "synthesis":
    case "ai":
      return <SruSparkleBadge size={size} className={className} />;
    case "🎓":
    case "cap":
    case "degree":
    case "academic":
    case "course":
    case "btech":
    case "mtech":
      return <SruCapBadge size={size} className={className} />;
    case "🧮":
    case "calculator":
    case "calc":
    case "scholarship":
      return <SruCalcBadge size={size} className={className} />;
    case "💰":
    case "💳":
    case "💵":
    case "₹":
    case "rupee":
    case "fee":
    case "fees":
    case "tuition":
      return <SruFeeBadge size={size} className={className} />;
    case "💼":
    case "briefcase":
    case "placement":
    case "job":
    case "recruiters":
    case "mba":
      return <SruPlacementBadge size={size} className={className} />;
    case "📈":
    case "📊":
    case "trending":
    case "growth":
    case "stats":
    case "highest":
      return <SruStatsBadge size={size} className={className} />;
    case "🏠":
    case "bed":
    case "hostel":
    case "room":
    case "mess":
    case "housing":
      return <SruHostelBadge size={size} className={className} />;
    case "🔬":
    case "flask":
    case "lab":
    case "labs":
    case "research":
      return <SruLabBadge size={size} className={className} />;
    case "🚀":
    case "rocket":
    case "srix":
    case "incubator":
    case "startup":
      return <SruRocketBadge size={size} className={className} />;
    case "🎯":
    case "target":
    case "cutoff":
    case "goal":
      return <SruTargetBadge size={size} className={className} />;
    case "🏢":
    case "🏫":
    case "🏛️":
    case "🏛":
    case "building":
    case "campus":
    case "university":
    case "sru":
      return <SruCampusBadge size={size} className={className} />;
    case "⚡":
    case "bolt":
    case "ece":
    case "tech":
    case "engineering":
      return <SruTechBadge size={size} className={className} />;
    case "🎥":
    case "video":
    case "tour":
      return <SruVideoBadge size={size} className={className} />;
    case "🤝":
    case "handshake":
    case "special":
    case "support":
    case "aid":
      return <SruHandshakeBadge size={size} className={className} />;
    case "❌":
    case "close":
    case "dismiss":
    case "no":
      return <SruCloseBadge size={size} className={className} />;
    case "🎉":
    case "award":
    case "trophy":
      return <AwardIcon size={size} className={className} />;
    case "❤️":
    case "heart":
    case "care":
      return <HeartHandIcon size={size} className={className} />;
    case "📌":
    case "pin":
      return <PinIcon size={size} className={className} />;
    case "⚠️":
    case "warning":
    case "alert":
      return <AlertTriangleIcon size={size} className={className} />;
    case "ℹ️":
    case "info":
      return <InfoIcon size={size} className={className} />;
    case "🛡️":
    case "shield":
      return <ShieldCheckIcon size={size} className={className} />;
    case "📚":
    case "book":
    case "curriculum":
      return <BookOpenIcon size={size} className={className} />;
    case "💬":
    case "chat":
    case "message":
      return <MessageSquareIcon size={size} className={className} />;
    case "📅":
    case "calendar":
      return <CalendarIcon size={size} className={className} />;
    case "🕒":
    case "clock":
    case "time":
      return <ClockIcon size={size} className={className} />;
    case "🚌":
    case "bus":
    case "transport":
      return <BusIcon size={size} className={className} />;
    default:
      return null;
  }
}
