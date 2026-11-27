import type { FormEvent } from "react";
import type { DocumentItem } from "../../services/api";

interface DocumentsTabProps {
  documents: DocumentItem[];
  uploadSuccess: string | null;
  uploadTitle: string;
  setUploadTitle: (v: string) => void;
  uploadType: string;
  setUploadType: (v: string) => void;
  uploadDept: string;
  setUploadDept: (v: string) => void;
  setUploadFile: (file: File | null) => void;
  isUploading: boolean;
  onUpload: (e: FormEvent) => void;
  onDeactivate: (docId: string) => void;
}

export function DocumentsTab({
  documents,
  uploadSuccess,
  uploadTitle,
  setUploadTitle,
  uploadType,
  setUploadType,
  uploadDept,
  setUploadDept,
  setUploadFile,
  isUploading,
  onUpload,
  onDeactivate,
}: DocumentsTabProps) {
  return (
    <div className="tab-pane-container">
      <div className="admin-card-panel">
        <h3 className="panel-headline">Upload & Ingest Document</h3>
        {uploadSuccess && (
          <div className="admin-toast toast-success" style={{ marginBottom: "16px" }}>
            <span>{uploadSuccess}</span>
          </div>
        )}
        <form onSubmit={onUpload}>
          <div className="form-responsive-grid">
            <div className="form-field-group">
              <label>Document Title *</label>
              <input
                type="text"
                className="admin-input"
                placeholder="e.g. Examination Regulations 2026"
                value={uploadTitle}
                onChange={(e) => setUploadTitle(e.target.value)}
                required
              />
            </div>
            <div className="form-field-group">
              <label>Document Type *</label>
              <select
                className="admin-select"
                value={uploadType}
                onChange={(e) => setUploadType(e.target.value)}
              >
                <option value="policy">Policy</option>
                <option value="calendar">Academic Calendar</option>
                <option value="regulation">Regulations / Rules</option>
                <option value="syllabus">Syllabus / Course</option>
                <option value="circular">Notice / Circular</option>
              </select>
            </div>
            <div className="form-field-group">
              <label>Department</label>
              <input
                type="text"
                className="admin-input"
                placeholder="e.g. Office of Academic Affairs"
                value={uploadDept}
                onChange={(e) => setUploadDept(e.target.value)}
              />
            </div>
            <div className="form-field-group">
              <label>File (PDF, DOCX, TXT, MD) *</label>
              <input
                type="file"
                className="admin-input-file"
                accept=".pdf,.docx,.txt,.md"
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                required
              />
            </div>
          </div>
          <button
            type="submit"
            className="admin-btn-primary"
            disabled={isUploading}
            style={{ marginTop: "16px" }}
          >
            {isUploading ? "Extracting & Embedding..." : "Ingest Document"}
          </button>
        </form>
      </div>

      <div className="admin-table-card">
        <h3 className="card-headline">Knowledge Base Documents</h3>
        {documents.length === 0 ? (
          <div className="admin-empty-state">
            <p>No documents indexed yet.</p>
          </div>
        ) : (
          <div className="admin-table-wrapper">
            <table className="admin-clean-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Type</th>
                  <th>Department</th>
                  <th>Status</th>
                  <th>Date</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.id}>
                    <td data-label="Title" style={{ fontWeight: 600 }}>{doc.title}</td>
                    <td data-label="Type">{doc.document_type}</td>
                    <td data-label="Department">{doc.department || "—"}</td>
                    <td data-label="Status">
                      <span className={`status-pill pill-${doc.status}`}>
                        {doc.status}
                      </span>
                    </td>
                    <td data-label="Date" className="cell-date">{new Date(doc.created_at).toLocaleDateString()}</td>
                    <td data-label="Action">
                      {doc.status === "active" && (
                        <button
                          className="admin-btn-danger"
                          onClick={() => onDeactivate(doc.id)}
                        >
                          Deactivate
                        </button>
                      )}
                    </td>
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
