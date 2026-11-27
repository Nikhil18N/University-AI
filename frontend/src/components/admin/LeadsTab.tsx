import type { LeadStats, ProspectiveLeadItem } from "../../services/api";

interface LeadsTabProps {
  adminKey: string;
  leads: ProspectiveLeadItem[];
  leadsTotal: number;
  leadStats: LeadStats | null;
  leadSearch: string;
  setLeadSearch: (v: string) => void;
  leadProgramFilter: string;
  setLeadProgramFilter: (v: string) => void;
  leadSourceFilter: string;
  setLeadSourceFilter: (v: string) => void;
  leadStatusFilter: string;
  setLeadStatusFilter: (v: string) => void;
  leadPage: number;
  setLeadPage: (fn: number | ((p: number) => number)) => void;
  leadPageSize: number;
  isExportingLeads: boolean;
  updatingLeadId: string | null;
  formatProgramInterest: (programInterest: string | null | undefined, metadata?: Record<string, any> | null) => string;
  onRefresh: () => void;
  onExportLeads: () => void;
  onUpdateLeadStatus: (leadId: string, status: string) => void;
  onViewLeadChat: (lead: ProspectiveLeadItem) => void;
  onOpenLiveStudentChat: (convId: string) => void;
}

export function LeadsTab({
  leads,
  leadsTotal,
  leadStats,
  leadSearch,
  setLeadSearch,
  leadProgramFilter,
  setLeadProgramFilter,
  leadSourceFilter,
  setLeadSourceFilter,
  leadStatusFilter,
  setLeadStatusFilter,
  leadPage,
  setLeadPage,
  leadPageSize,
  isExportingLeads,
  updatingLeadId,
  formatProgramInterest,
  onRefresh,
  onExportLeads,
  onUpdateLeadStatus,
  onViewLeadChat,
  onOpenLiveStudentChat,
}: LeadsTabProps) {
  return (
    <div className="tab-pane-container">
      <div className="admin-metrics-grid">
        <div className="metric-box">
          <span className="metric-title">Total Verified Leads</span>
          <span className="metric-num num-indigo">{leadStats?.total_leads ?? leadsTotal}</span>
          <span className="metric-caption">Authenticated prospects</span>
        </div>
        <div className="metric-box">
          <span className="metric-title">Chat Inquiries</span>
          <span className="metric-num num-green">{leadStats?.chat_leads ?? 0}</span>
          <span className="metric-caption">Admissions & fee questions</span>
        </div>
        <div className="metric-box">
          <span className="metric-title">Calculator Submissions</span>
          <span className="metric-num num-amber">{leadStats?.calculator_leads ?? 0}</span>
          <span className="metric-caption">Scholarship & merit inquiries</span>
        </div>
        <div className="metric-box">
          <span className="metric-title">Today's Leads</span>
          <span className="metric-num num-pink">{leadStats?.today_leads ?? 0}</span>
          <span className="metric-caption">Fresh high-intent inquiries</span>
        </div>
      </div>

      <div className="admin-toolbar-card">
        <div className="toolbar-filters">
          <div className="admin-search-wrap">
            <input
              type="text"
              className="admin-input-search"
              placeholder="Search student name or mobile number..."
              value={leadSearch}
              onChange={(e) => {
                setLeadSearch(e.target.value);
                setLeadPage(1);
              }}
            />
            {leadSearch && (
              <button
                className="search-clear-btn"
                onClick={() => {
                  setLeadSearch("");
                  setLeadPage(1);
                }}
              >
                ✕
              </button>
            )}
          </div>

          <select
            className="admin-select"
            value={leadProgramFilter}
            onChange={(e) => {
              setLeadProgramFilter(e.target.value);
              setLeadPage(1);
            }}
          >
            <option value="all">All Programs</option>
            <option value="B.Tech CSE">B.Tech CSE</option>
            <option value="B.Tech ECE">B.Tech ECE</option>
            <option value="B.Tech AI & Data Science">B.Tech AI & Data Science</option>
            <option value="B.Tech Mechanical">B.Tech Mechanical</option>
            <option value="B.Tech Civil">B.Tech Civil</option>
            <option value="B.Tech EEE">B.Tech EEE</option>
            <option value="BBA">BBA</option>
            <option value="MBA">MBA</option>
          </select>

          <select
            className="admin-select"
            value={leadSourceFilter}
            onChange={(e) => {
              setLeadSourceFilter(e.target.value);
              setLeadPage(1);
            }}
          >
            <option value="all">All Sources</option>
            <option value="chat_inquiry">Chat Inquiry</option>
            <option value="calculator">Calculator</option>
          </select>

          <select
            className="admin-select"
            value={leadStatusFilter}
            onChange={(e) => {
              setLeadStatusFilter(e.target.value);
              setLeadPage(1);
            }}
          >
            <option value="all">All Statuses</option>
            <option value="new">New</option>
            <option value="contacted">Contacted</option>
            <option value="counselled">Counselled</option>
            <option value="applied">Applied</option>
            <option value="enrolled">Enrolled</option>
            <option value="lost">Lost</option>
            <option value="do_not_contact">Do not contact</option>
          </select>
        </div>

        <div className="toolbar-actions">
          <button
            className="admin-btn-secondary"
            onClick={onRefresh}
            title="Refresh Leads Table"
          >
            ↻ Refresh
          </button>
          <button
            className="admin-btn-primary"
            onClick={onExportLeads}
            disabled={isExportingLeads}
          >
            {isExportingLeads ? "Exporting..." : "Export CSV"}
          </button>
        </div>
      </div>

      <div className="admin-table-card">
        {leads.length === 0 ? (
          <div className="admin-empty-state">
            <div className="empty-icon"></div>
            <h3>No Prospective Leads Found</h3>
            <p>
              {leadSearch || leadProgramFilter !== "all" || leadStatusFilter !== "all" || leadSourceFilter !== "all"
                ? "No leads matched your current filters. Try resetting the search or filter criteria."
                : "Leads captured via Chat Fee Inquiries or Scholarship Calculator will appear here automatically."}
            </p>
          </div>
        ) : (
          <div className="admin-table-wrapper">
            <table className="admin-clean-table">
              <thead>
                <tr>
                  <th className="col-name">Student Name</th>
                  <th className="col-phone">Mobile Number</th>
                  <th className="col-program">Program Interest</th>
                  <th className="col-score">Score / Qualifying Exam</th>
                  <th className="col-source">Lead Source</th>
                  <th className="col-date">Captured On</th>
                  <th className="col-status">Admission Status</th>
                  <th className="col-actions">Actions</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => {
                  const formattedDate = new Date(lead.created_at).toLocaleString("en-IN", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  });

                  return (
                    <tr key={lead.id} className="lead-row">
                      <td className="col-name" data-label="Student">
                        <div className="student-name-text">{lead.name}</div>
                        {lead.email && <div className="student-sub-email">{lead.email}</div>}
                      </td>
                      <td className="col-phone" data-label="Mobile">
                        <a href={`tel:${lead.phone}`} className="student-phone-link">
                          {lead.phone}
                        </a>
                      </td>
                      <td className="col-program" data-label="Programme">
                        <span className="program-badge">
                          {formatProgramInterest(lead.program_interest, lead.metadata)}
                        </span>
                      </td>
                      <td className="col-score" data-label="Score / exam">
                        {lead.score || lead.exam_type ? (
                          <div className="score-cell">
                            {lead.score && <span className="score-val">{lead.score}</span>}
                            {lead.exam_type && <span className="exam-type-val">({lead.exam_type})</span>}
                          </div>
                        ) : (
                          <span className="cell-muted">—</span>
                        )}
                      </td>
                      <td className="col-source" data-label="Source">
                        <span className={`source-pill source-${lead.source}`}>
                          {lead.source === "calculator" ? "Calculator" : "Chat Inquiry"}
                        </span>
                      </td>
                      <td className="col-date" data-label="Captured">{formattedDate}</td>
                      <td className="col-status" data-label="Status">
                        <select
                          className={`status-select status-${lead.status}`}
                          value={lead.status}
                          disabled={updatingLeadId === lead.id}
                          onChange={(e) => onUpdateLeadStatus(lead.id, e.target.value)}
                        >
                          <option value="new">New</option>
                          <option value="contacted">Contacted</option>
                          <option value="counselled">Counselled</option>
                          <option value="applied">Applied</option>
                          <option value="enrolled">Enrolled</option>
                          <option value="lost">Lost</option>
                          <option value="do_not_contact">Do not contact</option>
                        </select>
                      </td>
                      <td className="col-actions" data-label="Actions">
                        <div className="lead-actions-flex">
                          <button
                            className="admin-btn-action-view"
                            title={
                              lead.conversation_id
                                ? `Inspect conversation #${lead.conversation_id.slice(0, 8)} in Admin`
                                : "Search and inspect conversation in Admin"
                            }
                            onClick={() => onViewLeadChat(lead)}
                          >
                            Inspect
                          </button>
                          {lead.conversation_id ? (
                            <button
                              className="admin-btn-action-student"
                              title="Open conversation in Live Student Portal"
                              onClick={() => onOpenLiveStudentChat(lead.conversation_id!)}
                            >
                              Live ↗
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {leadsTotal > leadPageSize && (
          <div className="admin-pagination-footer">
            <span className="pagination-info">
              Showing {Math.min((leadPage - 1) * leadPageSize + 1, leadsTotal)}–
              {Math.min(leadPage * leadPageSize, leadsTotal)} of {leadsTotal} leads
            </span>
            <div className="pagination-ctrls">
              <button
                className="admin-btn-secondary"
                disabled={leadPage <= 1}
                onClick={() => setLeadPage((p) => Math.max(1, p - 1))}
              >
                ← Previous
              </button>
              <span className="pagination-page-label">
                Page {leadPage} of {Math.ceil(leadsTotal / leadPageSize)}
              </span>
              <button
                className="admin-btn-secondary"
                disabled={leadPage >= Math.ceil(leadsTotal / leadPageSize)}
                onClick={() => setLeadPage((p) => p + 1)}
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
