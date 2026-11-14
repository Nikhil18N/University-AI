import { useState } from "react";
import {
  ScaleIcon,
  TargetIcon,
  BriefcaseIcon,
  FlaskIcon,
  SparklesIcon,
  RupeeIcon,
  AwardIcon,
  BookOpenIcon,
  BuildingIcon,
  FileTextIcon,
  BoltIcon,
  VideoIcon,
} from "./Icons";
import "./Cards.css";

interface CardProps {
  card: any;
}

export function ComparisonCard({ card }: CardProps) {
  const columns = card.columns || [];

  return (
    <div className="rich-card comparison-card">
      <div className="card-header">
        <span className="card-badge">
          <ScaleIcon size={14} /> Comparison
        </span>
        <h4 className="card-title">{card.title}</h4>
      </div>
      <div className="comparison-grid">
        {columns.map((col: any, idx: number) => (
          <div key={idx} className="comparison-col">
            <div className="col-header">
              <span className="col-badge">{col.badge}</span>
              <h5 className="col-name">{col.name}</h5>
            </div>
            <div className="col-section">
              <span className="section-label">
                <TargetIcon size={13} /> Focus:
              </span>
              <p>{col.focus}</p>
            </div>
            <div className="col-section">
              <span className="section-label">
                <BriefcaseIcon size={13} /> Career Paths:
              </span>
              <p>{col.careers}</p>
            </div>
            <div className="col-section">
              <span className="section-label">
                <FlaskIcon size={13} /> Specialized Labs:
              </span>
              <p>{col.labs}</p>
            </div>
            <div className="col-advantage">
              <span><SparklesIcon size={13} /> Key Edge:</span> {col.key_advantage}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function FeeBreakdownCard({ card }: CardProps) {
  const items = card.items || [];

  return (
    <div className="rich-card fee-card">
      <div className="card-header">
        <span className="card-badge">
          <RupeeIcon size={14} /> Fee Structure
        </span>
        <h4 className="card-title">{card.title}</h4>
      </div>
      <div className="fee-table-wrapper">
        <table className="fee-table">
          <thead>
            <tr>
              <th>Fee Category</th>
              <th>Amount</th>
              <th>Frequency</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item: any, idx: number) => (
              <tr key={idx}>
                <td className="fee-category-cell">{item.category}</td>
                <td className="fee-amount-cell">{item.amount}</td>
                <td className="fee-frequency-cell">{item.frequency}</td>
                <td className="fee-note-cell">{item.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {card.scholarship_note && (
        <div className="card-callout scholarship-callout">
          <span className="callout-icon">
            <AwardIcon size={15} />
          </span>
          <div>
            <strong>Merit Scholarship Alert:</strong> {card.scholarship_note}
          </div>
        </div>
      )}
    </div>
  );
}

export function CurriculumCard({ card }: CardProps) {
  const structure = card.structure || [];
  const [activeCategory, setActiveCategory] = useState<number>(0);

  return (
    <div className="rich-card curriculum-card">
      <div className="card-header">
        <span className="card-badge">
          <BookOpenIcon size={14} /> Curriculum
        </span>
        <h4 className="card-title">{card.title}</h4>
      </div>
      <div className="curriculum-tabs">
        {structure.map((cat: any, idx: number) => (
          <button
            key={idx}
            className={`curriculum-tab-btn ${activeCategory === idx ? "active" : ""}`}
            onClick={() => setActiveCategory(idx)}
          >
            {cat.category.split("(")[0].trim()}
            <span className="tab-credits">{cat.credits}</span>
          </button>
        ))}
      </div>
      <div className="curriculum-courses">
        <h5 className="category-title">
          {structure[activeCategory]?.category} —{" "}
          <span className="category-credits">{structure[activeCategory]?.credits}</span>
        </h5>
        <div className="course-badges-grid">
          {structure[activeCategory]?.courses?.map((course: string, cIdx: number) => (
            <div key={cIdx} className="course-pill">
              <span className="course-dot"></span>
              {course}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function CampusTourCard({ card }: CardProps) {
  const spots = card.spots || [];

  return (
    <div className="rich-card campus-tour-card">
      <div className="card-header">
        <span className="card-badge">
          <BuildingIcon size={14} /> Campus Life
        </span>
        <h4 className="card-title">{card.title}</h4>
      </div>
      <div className="campus-spots-list">
        {spots.map((spot: any, idx: number) => (
          <div key={idx} className="campus-spot-item">
            <div className="spot-icon-wrapper">{spot.icon}</div>
            <div className="spot-info">
              <h5 className="spot-name">{spot.name}</h5>
              <p className="spot-desc">{spot.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ProfileCard({ card }: CardProps) {
  const data = card.data || {};
  const isSuccess = data.status_color === "success";

  return (
    <div className="rich-card profile-card">
      <div className="card-header">
        <span className={`card-badge ${isSuccess ? "badge-success" : "badge-warning"}`}>
          {isSuccess ? (
            <>
              <AwardIcon size={14} /> Evaluation: Qualified
            </>
          ) : (
            <>
              <FileTextIcon size={14} /> Evaluation: Review
            </>
          )}
        </span>
        <h4 className="card-title">{card.title}</h4>
      </div>
      <div className="profile-grid">
        <div className="profile-field">
          <span className="field-label">Target Program</span>
          <span className="field-value">{data.degree} ({data.branch})</span>
        </div>
        <div className="profile-field">
          <span className="field-label">12th PCM Score</span>
          <span className="field-value font-mono">{data.score}</span>
        </div>
        <div className="profile-field full-width">
          <span className="field-label">Eligibility Status</span>
          <span className={`status-pill ${isSuccess ? "status-success" : "status-warning"}`}>
            {data.status}
          </span>
        </div>
        <div className="profile-field full-width next-steps-box">
          <span className="field-label">Roadmap & Next Steps</span>
          <p className="next-steps-text">{data.next_steps}</p>
        </div>
      </div>
    </div>
  );
}

const CATEGORY_COLOR_MAP: Record<string, string> = {
  "Campus Tour": "blue",
  "Hostels & Living": "purple",
  "Placements & Careers": "green",
  "Startups & Innovation (SRiX)": "orange",
  "CS, AI & Technology": "teal",
  "Sports & Activities": "red",
  "Testimonials & Reviews": "yellow",
};

function getCategoryColor(category: string | undefined): string {
  if (!category) return "grey";
  return CATEGORY_COLOR_MAP[category] ?? "grey";
}

export function VideoRecommendationsCard({ card }: { card: any }) {
  const videos = card.videos || [];
  const channelUrl = card.channel_url || "https://www.youtube.com/@SRUniversity/videos";
  const channelName = card.channel_name || "SR University Official";
  const videoCount = videos.length;

  if (!videoCount) return null;

  return (
    <div className="rich-card video-recommendations-card yt-red-border">
      <div className="video-card-header">
        <div className="video-card-header-left">
          <div>
            <div className="yt-header-title-row">
              <h4 className="video-card-title">{card.title || "Related University Videos"}</h4>
              {videoCount > 0 && (
                <span className="yt-count-pill">{videoCount} {videoCount === 1 ? "video" : "videos"}</span>
              )}
            </div>
            <span className="video-card-subtitle">Official videos from {channelName}</span>
          </div>
        </div>
        <div className="video-card-header-actions">
          <a
            href={channelUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="channel-link-btn yt-btn"
            title="Visit official YouTube channel"
          >
            <svg className="social-icon-svg" viewBox="0 0 24 24" width="15" height="15" fill="currentColor">
              <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
            </svg>
            YouTube
          </a>
        </div>
      </div>

      <div className="yt-carousel-row">
        {videos.map((vid: any, idx: number) => {
          const isShort = vid.type === "short" || (typeof vid.url === "string" && vid.url.includes("/shorts/"));
          const categoryColor = getCategoryColor(vid.category);
          const isFirst = idx === 0;
          return (
            <a
              key={vid.id || idx}
              href={vid.url}
              target="_blank"
              rel="noopener noreferrer"
              className="yt-card-item"
              title={`Watch: ${vid.title}`}
              style={{ animationDelay: `${idx * 80}ms` } as React.CSSProperties}
            >
              <div className="yt-thumb-wrapper">
                <img
                  src={vid.thumbnail_url || `https://i.ytimg.com/vi/${vid.id}/hqdefault.jpg`}
                  alt={vid.title}
                  className="yt-thumb-img"
                  loading="eager"
                  decoding="async"
                  referrerPolicy="no-referrer"
                  onError={(e) => {
                    const img = e.currentTarget as HTMLImageElement;
                    if (!img.src.includes("mqdefault")) {
                      img.src = `https://i.ytimg.com/vi/${vid.id}/mqdefault.jpg`;
                    }
                  }}
                />

                {/* Central play button overlay — appears on hover */}
                <div className="yt-play-overlay" aria-hidden="true">
                  <svg viewBox="0 0 24 24" width="28" height="28" fill="#ef4444">
                    <path d="M8 5v14l11-7z"/>
                  </svg>
                </div>

                {/* "Watch" pill — slides up on hover, bottom-left */}
                <span className="yt-watch-pill">
                  <VideoIcon size={12} /> Watch
                </span>

                {/* "New" pill on first video, top-left */}
                {isFirst && <span className="yt-new-pill">New</span>}

                {isShort ? (
                  <span className="yt-duration-badge yt-short-badge">
                    <BoltIcon size={12} /> Shorts
                  </span>
                ) : vid.duration ? (
                  <span className="yt-duration-badge">{vid.duration}</span>
                ) : (
                  <span className="yt-duration-badge">
                    <VideoIcon size={12} /> Video
                  </span>
                )}
              </div>

              <div className="yt-card-details">
                <div className="yt-channel-avatar" title={vid.channel_name || "SR University"}>
                  <span>SRU</span>
                </div>

                <div className="yt-text-meta">
                  <h5 className="yt-video-title">{vid.title}</h5>
                  <div className="yt-submeta">
                    <span className="yt-channel-name">{vid.channel_name || "SR University"}</span>
                    {vid.category && (
                      <span className={`yt-category-tag yt-cat-${categoryColor}`}>{vid.category}</span>
                    )}
                  </div>
                </div>

                <div className="yt-card-action" title="Open media" onClick={(e) => e.preventDefault()}>
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                    <path d="M14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3m-2 16H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7z"/>
                  </svg>
                </div>
              </div>
            </a>
          );
        })}
      </div>

      <div className="video-card-footer">
        <a
          href={channelUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="more-videos-link yt-footer-link"
        >
          Watch more on @SRUniversity YouTube ↗
        </a>
      </div>
    </div>
  );
}

export function PlacementHighlightsCard({ card }: CardProps) {
  const superstars = card.superstars || [
    {
      name: "B. Shiva Krishna",
      role: "Software Engineer",
      company: "Microsoft",
      package: "51 LPA",
      stipend: "₹1.25L / month",
      batch: "Batch 2025",
      badge_color: "#10b981",
    },
    {
      name: "Kencha Bhavana",
      role: "Software Development Engineer",
      company: "Amazon",
      package: "46.38 LPA",
      stipend: "₹1.10L / month",
      batch: "Batch 2026",
      badge_color: "#0284c7",
    },
    {
      name: "Mohammed Akramuddin",
      role: "Associate Software Engineer",
      company: "ServiceNow",
      package: "49.30 LPA",
      stipend: "₹0.80L / month",
      batch: "Batch 2027",
      badge_color: "#6366f1",
    },
  ];

  const stats = card.stats || [
    { label: "Highest Package", value: "51 LPA", note: "Microsoft" },
    { label: "Total Job Offers", value: "1,300+", note: "And counting" },
    { label: "Internships", value: "3,500+", note: "Stipends to ₹1.25L/mo" },
    { label: "Average CTC", value: "6 LPA", note: "Cohort Average" },
  ];

  const topMncs = card.top_mnc_offers || [];

  return (
    <div className="rich-card placement-card">
      <div className="card-header">
        <span className="card-badge placement-badge">
          <AwardIcon size={14} /> Placement Excellence
        </span>
        <h4 className="card-title">{card.title}</h4>
        {card.subtitle && <p className="card-subtitle">{card.subtitle}</p>}
      </div>

      {/* Official 3 Superstars Banner Image */}
      <div className="placement-banner-wrapper">
        <img
          src={card.image_url || "/placements-three-years.png"}
          alt={card.image_alt || card.title}
          className="placement-banner-image"
          loading="eager"
          onClick={() => window.open(card.image_url || "/placements-three-years.png", "_blank")}
        />
        <div className="placement-banner-hint">
          <span>Click to view full resolution banner ↗</span>
        </div>
      </div>

      {/* 3 Consecutive Years Superstars Showcase */}
      <div className="superstars-showcase-grid">
        {superstars.map((star: any, idx: number) => (
          <div key={idx} className="superstar-card">
            <div className="superstar-top">
              <span className="superstar-batch-tag">{star.batch}</span>
              <span className="superstar-package-pill">{star.package}</span>
            </div>
            <h5 className="superstar-name">{star.name}</h5>
            <p className="superstar-role">{star.role}</p>
            <div className="superstar-company">
              <BriefcaseIcon size={13} />
              <span>Placed @ <strong>{star.company}</strong></span>
            </div>
            {star.stipend && (
              <div className="superstar-stipend">
                <span>Internship: <strong>{star.stipend}</strong></span>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Key Milestone Stats */}
      <div className="placement-stats-grid">
        {stats.map((s: any, idx: number) => (
          <div key={idx} className="placement-stat-box">
            <span className="stat-val">{s.value}</span>
            <span className="stat-lbl">{s.label}</span>
            {s.note && <span className="stat-sub">{s.note}</span>}
          </div>
        ))}
      </div>

      {/* Top Recruiting MNCs Volume */}
      {topMncs.length > 0 && (
        <div className="placement-mnc-section">
          <h6 className="placement-mnc-title">
            <SparklesIcon size={13} /> Top MNC Offers
          </h6>
          <div className="placement-mnc-pills">
            {topMncs.map((m: any, idx: number) => (
              <span key={idx} className="mnc-offer-pill">
                <strong>{m.company}</strong>: {m.offers} offers
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SRU Advantage Comparison Card
// Positive-only comparison — highlights SRU's strengths as differentiators
// ---------------------------------------------------------------------------
interface SRUAdvantage {
  category: string;
  icon: string;
  sru_highlight: string;
  standout: string;
}

function SRUAdvantageCard({ card }: { card: any }) {
  const advantages: SRUAdvantage[] = card.advantages || [];
  return (
    <div className="sru-advantage-card card-animate">
      <div className="sru-advantage-header">
        <span className="sru-advantage-badge">🏅 SRU Edge</span>
        <h2 className="sru-advantage-title">{card.title}</h2>
        <p className="sru-advantage-subtitle">{card.subtitle}</p>
      </div>
      <div className="sru-advantage-grid">
        {advantages.map((adv, i) => (
          <div key={i} className="sru-advantage-item">
            <div className="sru-advantage-item-header">
              <span className="sru-advantage-icon">{adv.icon}</span>
              <div>
                <div className="sru-advantage-category">{adv.category}</div>
                <div className="sru-advantage-standout">{adv.standout}</div>
              </div>
            </div>
            <p className="sru-advantage-desc">{adv.sru_highlight}</p>
          </div>
        ))}
      </div>
      <div className="sru-advantage-footer">
        <span className="sru-advantage-tagline">
          🌟 SR University — Where Learning Meets Opportunity, and Futures Take Shape.
        </span>
      </div>
    </div>
  );
}

export function RenderCard({ card }: { card: any }) {
  if (!card || !card.type) return null;

  switch (card.type) {
    case "comparison":
      return <ComparisonCard card={card} />;
    case "fee_breakdown":
      return <FeeBreakdownCard card={card} />;
    case "curriculum":
      return <CurriculumCard card={card} />;
    case "campus_tour":
      return <CampusTourCard card={card} />;
    case "profile":
      return <ProfileCard card={card} />;
    case "video_recommendations":
      return <VideoRecommendationsCard card={card} />;
    case "placement_highlights":
      return <PlacementHighlightsCard card={card} />;
    case "sru_comparison":
      return <SRUAdvantageCard card={card} />;
    default:
      return null;
  }
}

