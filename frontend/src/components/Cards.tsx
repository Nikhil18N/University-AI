import { useState } from "react";
import "./Cards.css";

interface CardProps {
  card: any;
}

export function ComparisonCard({ card }: CardProps) {
  const columns = card.columns || [];

  return (
    <div className="rich-card comparison-card">
      <div className="card-header">
        <span className="card-badge">⚖️ Comparison</span>
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
              <span className="section-label">🎯 Focus:</span>
              <p>{col.focus}</p>
            </div>
            <div className="col-section">
              <span className="section-label">💼 Career Paths:</span>
              <p>{col.careers}</p>
            </div>
            <div className="col-section">
              <span className="section-label">🔬 Specialized Labs:</span>
              <p>{col.labs}</p>
            </div>
            <div className="col-advantage">
              <span>⭐ Key Edge:</span> {col.key_advantage}
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
        <span className="card-badge">💰 Fee Structure</span>
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
          <span className="callout-icon">🎓</span>
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
        <span className="card-badge">📚 Curriculum</span>
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
        <span className="card-badge">🏫 Campus Life</span>
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
          {isSuccess ? "🎉 Evaluation: Qualified" : "📋 Evaluation: Review"}
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

export function VideoRecommendationsCard({ card }: { card: any }) {
  const videos = card.videos || [];
  const channelUrl = card.channel_url || "https://www.youtube.com/@SRUniversity/videos";
  const channelName = card.channel_name || "SR University Official";
  const instagramUrl = card.instagram_url || "https://www.instagram.com/sr_university/";

  if (!videos.length) return null;

  const hasInstagram = videos.some((v: any) => v.platform === "instagram");
  const hasYouTube = videos.some((v: any) => v.platform === "youtube" || !v.platform);

  return (
    <div className={`rich-card video-recommendations-card ${hasInstagram && !hasYouTube ? "card-insta-theme" : ""}`}>
      <div className="video-card-header">
        <div className="video-card-header-left">
          <span className="video-header-icon">{hasInstagram && !hasYouTube ? "📸" : "🎥"}</span>
          <div>
            <h4 className="video-card-title">{card.title || "Related University Videos"}</h4>
            <span className="video-card-subtitle">Official videos from {channelName}</span>
          </div>
        </div>
        <div className="video-card-header-actions">
          {hasInstagram && (
            <a
              href={instagramUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="channel-link-btn insta-btn"
              title="Visit official Instagram page"
            >
              <svg className="social-icon-svg" viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
              </svg>
              @sr_university
            </a>
          )}
          {hasYouTube && (
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
          )}
        </div>
      </div>

      <div className="yt-carousel-row">
        {videos.map((vid: any, idx: number) => {
          const isInsta = vid.platform === "instagram";
          return (
            <a
              key={vid.id || idx}
              href={vid.url}
              target="_blank"
              rel="noopener noreferrer"
              className={`yt-card-item ${isInsta ? "insta-card-item" : ""}`}
              title={`Watch: ${vid.title}`}
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
                    if (!isInsta && !img.src.includes("mqdefault")) {
                      img.src = `https://i.ytimg.com/vi/${vid.id}/mqdefault.jpg`;
                    }
                  }}
                />
                {isInsta ? (
                  <span className="insta-reel-badge">▶ Reel</span>
                ) : (
                  vid.duration && <span className="yt-duration-badge">{vid.duration}</span>
                )}
              </div>

              <div className="yt-card-details">
                <div className={`yt-channel-avatar ${isInsta ? "insta-avatar" : ""}`} title={vid.channel_name || "SR University"}>
                  <span>{isInsta ? "📸" : "SRU"}</span>
                </div>

                <div className="yt-text-meta">
                  <h5 className="yt-video-title">{vid.title}</h5>
                  <div className="yt-submeta">
                    <span className="yt-channel-name">{isInsta ? vid.handle || "@sr_university" : vid.channel_name || "SR University"}</span>
                    {vid.category && <span className="yt-category-bullet"> • {vid.category}</span>}
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
        {hasYouTube && (
          <a
            href={channelUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="more-videos-link yt-footer-link"
          >
            Watch more on @SRUniversity YouTube ↗
          </a>
        )}
        {hasYouTube && hasInstagram && <span className="footer-link-divider">•</span>}
        {hasInstagram && (
          <a
            href={instagramUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="more-videos-link insta-footer-link"
          >
            Explore Reels on @sr_university Instagram ↗
          </a>
        )}
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
    default:
      return null;
  }
}
