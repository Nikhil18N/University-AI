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


      </div>
    </div>
  );
}
