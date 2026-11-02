import type { SourceReference } from "../services/api";
import "./MessageBubble.css";

interface Props {
  role: "user" | "assistant";
  content: string;
  sources?: SourceReference[] | null;
}

export default function MessageBubble({ role, content, sources }: Props) {
  return (
    <div className={`message-bubble ${role}`}>
      <div className="message-avatar">
        {role === "user" ? "👤" : "🎓"}
      </div>
      <div className="message-body">
        <div className="message-content">{content}</div>
        {sources && sources.length > 0 && (
          <div className="message-sources">
            <span className="sources-label">Sources:</span>
            {sources.map((s, idx) => (
              <div key={idx} className="source-card">
                <span className="source-title">{s.title}</span>
                {s.department && <span className="source-dept">{s.department}</span>}
                {s.page && <span className="source-page">Page {s.page}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
