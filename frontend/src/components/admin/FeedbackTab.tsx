import type { FeedbackItem } from "../../services/api";

interface FeedbackTabProps {
  feedback: FeedbackItem[];
}

export function FeedbackTab({ feedback }: FeedbackTabProps) {
  return (
    <div className="tab-pane-container">
      <div className="admin-table-card">
        <h3 className="card-headline">Student & User Feedback</h3>
        {feedback.length === 0 ? (
          <div className="admin-empty-state">
            <p>No feedback submitted yet.</p>
          </div>
        ) : (
          <div className="admin-table-wrapper">
            <table className="admin-clean-table">
              <thead>
                <tr>
                  <th>Rating</th>
                  <th>User Question</th>
                  <th>AI Response</th>
                  <th>Comment</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {feedback.map((f) => (
                  <tr key={f.id}>
                    <td data-label="Rating">
                      {f.rating === 1 ? (
                        <span className="rating-tag rating-pos">👍 Helpful</span>
                      ) : (
                        <span className="rating-tag rating-neg">👎 Inaccurate</span>
                      )}
                    </td>
                    <td data-label="Question" style={{ maxWidth: "260px", wordBreak: "break-word" }}>
                      {f.question || <span className="cell-muted">—</span>}
                    </td>
                    <td data-label="AI answer" style={{ maxWidth: "340px", wordBreak: "break-word", fontSize: "0.85rem" }}>
                      {f.answer ? (
                        <span>{f.answer.length > 160 ? `${f.answer.slice(0, 160)}...` : f.answer}</span>
                      ) : (
                        <span className="cell-muted">—</span>
                      )}
                    </td>
                    <td data-label="Comment">{f.comment || <span className="cell-muted">—</span>}</td>
                    <td data-label="Date" className="cell-date">{new Date(f.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
