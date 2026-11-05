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
 * Universal resolver to match legacy or dynamic emoji keys to vector SVG icons.
 */
export function renderUniIcon(keyOrEmoji: string, size = 16, className = ""): React.ReactNode {
  const clean = keyOrEmoji.trim();
  switch (clean) {
    case "🎓":
    case "cap":
    case "degree":
    case "academic":
      return <CapIcon size={size} className={className} />;
    case "🧮":
    case "calculator":
    case "calc":
      return <CalculatorIcon size={size} className={className} />;
    case "💰":
    case "💳":
    case "rupee":
    case "fee":
      return <RupeeIcon size={size} className={className} />;
    case "⚡":
    case "bolt":
    case "ece":
      return <BoltIcon size={size} className={className} />;
    case "💼":
    case "briefcase":
    case "placement":
    case "job":
    case "mba":
      return <BriefcaseIcon size={size} className={className} />;
    case "📈":
    case "📊":
    case "trending":
    case "growth":
      return <TrendingUpIcon size={size} className={className} />;
    case "🏠":
    case "bed":
    case "hostel":
      return <BedIcon size={size} className={className} />;
    case "🏢":
    case "building":
    case "campus":
      return <BuildingIcon size={size} className={className} />;
    case "🔬":
    case "flask":
    case "lab":
      return <FlaskIcon size={size} className={className} />;
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
    case "🎥":
    case "video":
    case "tour":
      return <VideoIcon size={size} className={className} />;
    case "🎉":
    case "award":
    case "trophy":
      return <AwardIcon size={size} className={className} />;
    case "✨":
    case "sparkle":
      return <SparklesIcon size={size} className={className} />;
    case "❤️":
    case "heart":
    case "care":
      return <HeartHandIcon size={size} className={className} />;
    case "📌":
    case "pin":
      return <PinIcon size={size} className={className} />;
    case "📋":
    case "document":
    case "apply":
      return <FileTextIcon size={size} className={className} />;
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
    case "⚖️":
    case "scale":
    case "compare":
      return <ScaleIcon size={size} className={className} />;
    case "🎯":
    case "target":
      return <TargetIcon size={size} className={className} />;
    case "📚":
    case "book":
    case "curriculum":
      return <BookOpenIcon size={size} className={className} />;
    case "💬":
    case "chat":
    case "message":
      return <MessageSquareIcon size={size} className={className} />;
    default:
      return null;
  }
}
