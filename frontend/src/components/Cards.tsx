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

  if (!videos.length) return null;

  return (
    <div className="rich-card video-recommendations-card">
      <div className="video-card-header">
        <div className="video-card-header-left">
          <span className="video-header-icon">🎥</span>
          <div>
            <h4 className="video-card-title">{card.title || "Related University Videos"}</h4>
            <span className="video-card-subtitle">Official videos from {channelName}</span>
          </div>
        </div>
        <a
          href={channelUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="channel-link-btn"
          title="Visit official YouTube channel"
        >
          <svg className="yt-icon-svg" viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
          </svg>
          Channel
        </a>
      </div>

      <div className="yt-carousel-row">
        {videos.map((vid: any, idx: number) => (
          <a
            key={vid.id || idx}
            href={vid.url}
            target="_blank"
            rel="noopener noreferrer"
            className="yt-card-item"
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
                  if (!img.src.includes("mqdefault")) {
                    img.src = `https://i.ytimg.com/vi/${vid.id}/mqdefault.jpg`;
                  }
                }}
              />
              {vid.duration && <span className="yt-duration-badge">{vid.duration}</span>}
            </div>

            <div className="yt-card-details">
              <div className="yt-channel-avatar" title={vid.channel_name || "SR University Official"}>
                <span>SRU</span>
              </div>

              <div className="yt-text-meta">
                <h5 className="yt-video-title">{vid.title}</h5>
                <div className="yt-submeta">
                  <span className="yt-channel-name">{vid.channel_name || "SR University"}</span>
                  {vid.category && <span className="yt-category-bullet"> • {vid.category}</span>}
                </div>
              </div>

              <div className="yt-card-action" title="More options" onClick={(e) => e.preventDefault()}>
                <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor">
                  <path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/>
                </svg>
              </div>
            </div>
          </a>
        ))}
      </div>

      <div className="video-card-footer">
        <a
          href={channelUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="more-videos-link"
        >
          Explore more videos on @SRUniversity YouTube ↗
        </a>
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
