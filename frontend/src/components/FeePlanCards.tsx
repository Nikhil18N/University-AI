import { useEffect, useMemo, useRef, useState } from "react";
import { AwardIcon, CheckIcon, RupeeIcon, ShareIcon, ShieldCheckIcon } from "./Icons";
import "./FeePlanCards.css";
import { SemesterFeeTable } from "./SemesterFeeTable";
import {
  canCopyImage,
  copyCaption,
  copyImage,
  downloadBlob,
  renderFeeCardPng,
  shareFeeCardImage,
  type FeeImageModel,
} from "../utils/feeCardImage";

/**
 * Fee-plan cards, all filled by the ONE fee engine (app/sru_agent/fees.py, the 2027-28 fee circular) via the backend
 * (app/sru_agent/fee_plan.py and fees.special_concessions):
 *  * ConcessionsTableCard: the circular's special concessions as a table; pick one and apply it to your fee;
 *  * ConcessionFeeCard: one card with the tuition after the chosen concession and the proof note;
 *  * FeePlanCard: the complete first-year fee chart with a Share button (older chats);
 *  * FeeSummaryCard (v4.11.0): the fee evaluation agent's final card. Confirmed amounts and pending
 *    evaluations are kept apart: a special consideration is never shown as approved.
 */

type Select = (text: string) => void;

function amountValue(text: string): number {
  return Number(String(text || "").replace(/[^0-9]/g, "")) || 0;
}

/** The special concessions card: grouped (default) or the full table, as chosen in the admin panel. */
export function ConcessionsCard({ card, onSelect }: { card: any; onSelect?: Select }) {
  const data = card.data || card;
  if (data.mode === "grouped" && Array.isArray(data.groups) && data.groups.length > 0) {
    return <GroupedConcessionsCard card={card} onSelect={onSelect} />;
  }
  return <ConcessionsTableCard card={card} onSelect={onSelect} />;
}

/**
 * Grouped picker (v4.12.0): five folded groups, one open at a time, so a student reads only the group that
 * may apply. "None of these apply" (during a fee evaluation) is one tap. The "Other circumstances" group holds
 * the personal categories: never asked about, chosen privately.
 */
export function GroupedConcessionsCard({ card, onSelect }: { card: any; onSelect?: Select }) {
  const data = card.data || card;
  const groups: { key: string; title: string; hint: string; private?: boolean; items: { category: string; per_year: string }[] }[] =
    data.groups || [];
  const [open, setOpen] = useState<string | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [done, setDone] = useState<"" | "picked" | "none">("");
  const locked = done !== "";

  const apply = () => {
    if (!picked || locked || !onSelect) return;
    setDone("picked");
    onSelect(`Apply the "${picked}" concession to my fee`);
  };
  const none = () => {
    if (locked || !onSelect) return;
    setDone("none");
    onSelect("None of these apply");
  };

  return (
    <div className="rich-card fp-card fp-concessions fp-grouped">
      <div className="card-header">
        <span className="card-badge">
          <AwardIcon size={14} /> Special concessions
        </span>
        <h4 className="card-title">Do any of these apply to you?</h4>
      </div>
      <p className="fp-hint">
        Open a group to see its categories ({data.academic_year || "2027-28"}, per year). Each one is approved only
        after your proof is verified.
      </p>
      <div className="fp-groups">
        {groups.map((g) => {
          const isOpen = open === g.key;
          // "₹15,000" or "₹15,000–₹50,000": the group's range, lowest first (never an unordered list).
          const values = g.items.map((i) => amountValue(i.per_year)).filter((v) => v > 0);
          const lo = Math.min(...values);
          const hi = Math.max(...values);
          const byText = (v: number) => g.items.find((i) => amountValue(i.per_year) === v)?.per_year || "";
          const range = values.length === 0 ? "" : lo === hi ? byText(lo) : `${byText(lo)}–${byText(hi)}`;
          return (
            <div key={g.key} className={`fp-group${isOpen ? " is-open" : ""}`}>
              <button
                type="button"
                className="fp-group-head"
                aria-expanded={isOpen}
                onClick={() => setOpen(isOpen ? null : g.key)}
                disabled={locked && !g.items.some((i) => i.category === picked)}
              >
                <span className="fp-group-title">
                  {g.title}
                  <span className="fp-group-hint">{g.hint}</span>
                </span>
                <span className="fp-group-meta">
                  {range}
                  <svg className="fp-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </span>
              </button>
              {isOpen && (
                <div className="fp-group-body" role="radiogroup" aria-label={g.title}>
                  {g.private && (
                    <p className="fp-private-note">Private: pick one only if it applies. You won't be asked about it.</p>
                  )}
                  {g.items.map((it) => {
                    const on = picked === it.category;
                    return (
                      <button
                        type="button"
                        key={it.category}
                        role="radio"
                        aria-checked={on}
                        className={`fp-option${on ? " is-on" : ""}`}
                        onClick={() => !locked && setPicked(it.category)}
                        disabled={locked && !on}
                      >
                        <span className="fp-pick">
                          <span className="fp-radio" aria-hidden="true">
                            {on && <CheckIcon size={11} strokeWidth={3} />}
                          </span>
                          <span className="fp-cat">{it.category}</span>
                        </span>
                        <span className="fp-num">{it.per_year}</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {(data.all_categories || []).some((r: any) => r.selectable === false) && (
        <p className="fp-hint fp-hint-muted">
          Also on the circular, by recommendation only:{" "}
          {(data.all_categories || [])
            .filter((r: any) => r.selectable === false)
            .map((r: any) => `${r.category} (${r.per_year})`)
            .join("; ")}
          .
        </p>
      )}
      <div className="agent-card-footer fp-footer">
        {picked && (
          <button type="button" className="agent-card-map-btn fp-apply" onClick={apply} disabled={locked || !onSelect}>
            {done === "picked" ? (
              <>
                <CheckIcon size={14} /> Selected
              </>
            ) : (
              "Check my fee with this"
            )}
          </button>
        )}
        {data.allow_none && (
          <button type="button" className="card-more-btn fp-none" onClick={none} disabled={locked || !onSelect}>
            {done === "none" ? (
              <>
                <CheckIcon size={14} /> None apply
              </>
            ) : (
              "None of these apply"
            )}
          </button>
        )}
      </div>
    </div>
  );
}

export function ConcessionsTableCard({ card, onSelect }: { card: any; onSelect?: Select }) {
  const data = card.data || card;
  // Categories granted only on a recommendation (not claimable by a student) are listed under the table.
  const rows: { category: string; per_year: string }[] = useMemo(
    () =>
      [...(data.all_categories || [])]
        .filter((r: any) => r.selectable !== false)
        .sort((a: any, b: any) => amountValue(b.per_year) - amountValue(a.per_year)),
    [data.all_categories]
  );
  const byRecommendation: { category: string; per_year: string }[] = (data.all_categories || []).filter(
    (r: any) => r.selectable === false
  );
  const [picked, setPicked] = useState<string | null>(null);
  const [applied, setApplied] = useState(false);

  const apply = () => {
    if (!picked || applied || !onSelect) return;
    setApplied(true);
    onSelect(`Apply the "${picked}" concession to my fee`);
  };

  return (
    <div className="rich-card fp-card fp-concessions">
      <div className="card-header">
        <span className="card-badge">
          <AwardIcon size={14} /> Special concessions
        </span>
        <h4 className="card-title">
          {rows.length} categories · per year · {data.academic_year || "2027-28"}
        </h4>
      </div>
      <p className="fp-hint">Pick the one that applies to you. It is approved only after your proof is verified.</p>
      <div className="fp-table-wrap">
        <table className="fp-table fp-select-table">
          <thead>
            <tr>
              <th scope="col">Category</th>
              <th scope="col" className="fp-num">Per year</th>
            </tr>
          </thead>
          <tbody role="radiogroup" aria-label="Special concession categories">
            {rows.map((r) => {
              const on = picked === r.category;
              return (
                <tr
                  key={r.category}
                  role="radio"
                  aria-checked={on}
                  tabIndex={applied ? -1 : 0}
                  className={`fp-select-row${on ? " is-on" : ""}${applied ? " is-locked" : ""}`}
                  onClick={() => !applied && setPicked(r.category)}
                  onKeyDown={(e) => {
                    if (applied) return;
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setPicked(r.category);
                    }
                  }}
                >
                  <td>
                    <span className="fp-pick">
                      <span className="fp-radio" aria-hidden="true">
                        {on && <CheckIcon size={11} strokeWidth={3} />}
                      </span>
                      <span className="fp-cat">{r.category}</span>
                    </span>
                  </td>
                  <td className="fp-num">{r.per_year}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {byRecommendation.length > 0 && (
        <p className="fp-hint fp-hint-muted">
          Also on the circular, by recommendation only:{" "}
          {byRecommendation.map((r) => `${r.category} (${r.per_year})`).join("; ")}.
        </p>
      )}
      <div className="agent-card-footer fp-footer">
        <button
          type="button"
          className="agent-card-map-btn fp-apply"
          onClick={apply}
          disabled={!picked || applied || !onSelect}
        >
          {applied ? (
            <>
              <CheckIcon size={14} /> Selected
            </>
          ) : picked ? (
            "Check my fee with this"
          ) : (
            "Select a category"
          )}
        </button>
        <span className="agent-card-source-tag">
          Each concession needs valid proof, verified by the Admissions Office.
        </span>
      </div>
    </div>
  );
}

export function ConcessionFeeCard({ card }: { card: any }) {
  const d = card.data || {};
  return (
    <div className="rich-card fp-card fp-concession-fee">
      <div className="card-header">
        <span className="card-badge fp-badge-green">
          <ShieldCheckIcon size={14} /> Fee with concession
        </span>
        <h4 className="card-title">
          {d.program} · {d.academic_year}
        </h4>
      </div>
      <div className="fp-hero">
        <span className="fp-hero-label">First year with this concession</span>
        <span className="fp-hero-amount">{d.first_year_total || d.tuition_after_concession}</span>
        {d.sem1_payable && (
          <span className="fp-hero-sub">
            Semester 1 {d.sem1_payable} · Semester 2 {d.sem2_payable}
          </span>
        )}
      </div>
      <dl className="fp-lines">
        <div>
          <dt>Tuition (first year)</dt>
          <dd>{d.tuition}</dd>
        </div>
        <div className="is-discount">
          <dt>{d.concession}</dt>
          <dd>− {d.concession_amount}</dd>
        </div>
        <div className="is-total">
          <dt>Tuition for the year</dt>
          <dd>{d.tuition_after_concession}</dd>
        </div>
      </dl>
      {d.semester_note && <p className="fp-hint">{d.semester_note}</p>}
      {d.merit_percent ? (
        <p className="fp-merit">
          Your <strong>{d.merit_percent}% merit scholarship</strong> brings tuition to{" "}
          <strong>{d.tuition_after_merit}</strong>. {d.combine_note}
        </p>
      ) : null}
      <div className="fp-proof" role="note">
        <ShieldCheckIcon size={16} />
        <span>{d.proof_note}</span>
      </div>
    </div>
  );
}

export function FeePlanCard({ card }: { card: any }) {
  const d = card.data || {};
  const rows: any[] = d.rows || [];
  const imageModel = useMemo<FeeImageModel>(() => {
    const merit = rows.find((r) => r.kind === "discount" && /scholarship/i.test(r.item || ""));
    return {
      heading: "Fee estimate",
      program: d.program || "",
      specialization: d.specialization || undefined,
      academicYear: d.academic_year,
      scholarship: merit ? `${merit.item} (${merit.amount})` : undefined,
      semesters: semestersOf(d),
      confirmed: d.first_year_total ? { label: "First-year payable", value: d.first_year_total } : undefined,
      pendingTotal: d.concession?.total_if_approved
        ? { label: `With ${d.concession.label} concession, if approved`, value: d.concession.total_if_approved }
        : undefined,
      notes: [d.course_total && d.duration_years ? `Full course (${d.duration_years} years): ${d.course_total}` : "",
              d.application_fee ? `Application fee ${d.application_fee}, paid separately.` : ""].filter(Boolean),
    };
  }, [d, rows]);

  return (
    <div className="rich-card fp-card fp-plan">
      <div className="card-header">
        <span className="card-badge">
          <RupeeIcon size={14} /> Fee chart
        </span>
        <h4 className="card-title">
          {d.program} · {d.academic_year} · first year
        </h4>
      </div>
      <div className="fp-table-wrap">
        <table className="fp-table">
          <thead>
            <tr>
              <th scope="col">Item</th>
              <th scope="col" className="fp-num">Amount</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.item} className={r.kind === "discount" ? "is-discount" : undefined}>
                <td>
                  <span className="fp-cat">{r.item}</span>
                  {r.note && <span className="fp-note">{r.note}</span>}
                </td>
                <td className="fp-num">{r.amount}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="is-total">
              <th scope="row">First-year total</th>
              <td className="fp-num">{d.first_year_total}</td>
            </tr>
            {d.concession && (
              <tr className="is-concession">
                <th scope="row">
                  With {d.concession.label} concession <span className="fp-note">if approved</span>
                </th>
                <td className="fp-num">{d.concession.total_if_approved}</td>
              </tr>
            )}
          </tfoot>
        </table>
      </div>
      {Array.isArray(d.semesters) && d.semesters.length > 0 && (
        <div className="fp-sem-block">
          <SemesterFeeTable semesters={d.semesters} caption="Semester by semester" compact />
        </div>
      )}
      <ul className="fp-foot-notes">
        {d.course_total && d.duration_years && (
          <li>
            Full course ({d.duration_years} years): {d.course_total}
          </li>
        )}
        {d.application_fee && <li>Application fee {d.application_fee}, paid separately when you apply.</li>}
        {d.not_included?.length > 0 && <li>Not included: {d.not_included.join(", ")}.</li>}
        {d.concession?.note && <li>{d.concession.note}</li>}
      </ul>
      <div className="agent-card-footer fp-footer">
        <FeeCardShare model={imageModel} fileName="sru-fee-estimate.png" title={`SR University fee estimate: ${d.program}`} />
        <span className="agent-card-source-tag">Source: SR University fee circular, {d.academic_year}.</span>
      </div>
    </div>
  );
}

/**
 * "Share fee card" (v4.17.1): shares the card as a PNG image (exact card data) with a short caption through the
 * phone's share sheet. Where a browser or embedded frame cannot share files, it offers Download / Copy caption /
 * Copy image instead, and says exactly what happened (an image is never reported as shared when it was not).
 */
function FeeCardShare({ model, fileName, title }: { model: FeeImageModel; fileName: string; title: string }) {
  const blobRef = useRef<Blob | null>(null);
  const [panel, setPanel] = useState(false);
  const [status, setStatus] = useState("");
  const key = JSON.stringify(model);
  useEffect(() => {
    // Rendered ahead, so a tap can open the share sheet at once (the browser allows it only right after a tap).
    let alive = true;
    blobRef.current = null;
    const t = window.setTimeout(() => {
      renderFeeCardPng(model)
        .then((b) => {
          if (alive) blobRef.current = b;
        })
        .catch(() => {});
    }, 250);
    return () => {
      alive = false;
      window.clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const blob = async (): Promise<Blob | null> => {
    if (blobRef.current) return blobRef.current;
    try {
      blobRef.current = await renderFeeCardPng(model);
      return blobRef.current;
    } catch {
      return null;
    }
  };
  const flash = (text: string) => {
    setStatus(text);
    window.setTimeout(() => setStatus(""), 3200);
  };
  const onShare = async () => {
    setStatus("");
    const b = await blob();
    if (!b) {
      setPanel(true);
      flash("Couldn't create the image on this device.");
      return;
    }
    const outcome = await shareFeeCardImage(b, fileName, title);
    if (outcome === "shared") flash("Fee card shared.");
    else if (outcome === "cancelled") return; // closed the share sheet: nothing to say
    else setPanel(true);
  };
  const onDownload = async () => {
    const b = await blob();
    flash(b && downloadBlob(b, fileName) ? "Fee card downloaded." : "Couldn't download the image.");
  };
  const onCopyCaption = async () => flash((await copyCaption()) ? "Caption copied." : "Couldn't copy the caption.");
  const onCopyImage = async () => {
    const b = await blob();
    flash(b && (await copyImage(b)) ? "Image copied. Paste it into WhatsApp." : "Couldn't copy the image.");
  };

  return (
    <>
      <button type="button" className="agent-card-map-btn" onClick={onShare} aria-label="Share this fee card as an image">
        <ShareIcon size={14} /> Share fee card
      </button>
      {panel && (
        <div className="fp-share-panel" role="group" aria-label="Fee card sharing options">
          <span className="fp-share-panel-note">Sharing the image directly isn't available here. You can:</span>
          <button type="button" className="fp-share-option" onClick={onDownload}>
            Download fee card
          </button>
          <button type="button" className="fp-share-option" onClick={onCopyCaption}>
            Copy caption
          </button>
          {canCopyImage() && (
            <button type="button" className="fp-share-option" onClick={onCopyImage}>
              Copy image
            </button>
          )}
        </div>
      )}
      {status && (
        <span className="agent-card-source-tag" role="status">
          {status}
        </span>
      )}
    </>
  );
}

function semestersOf(d: any) {
  return Array.isArray(d.semesters) ? d.semesters : undefined;
}

const STATUS_TEXT: Record<string, string> = {
  pending: "Pending verification",
  estimated: "Estimate",
};

export function FeeSummaryCard({ card }: { card: any }) {
  const d = card.data || {};
  const rows: any[] = d.rows || [];
  const sch = useMemo(() => d.scholarship || {}, [d.scholarship]);
  const cons = d.special_consideration || {};
  const pending: string[] = useMemo(() => d.pending || [], [d.pending]);
  const imageModel = useMemo<FeeImageModel>(
    () => ({
      heading: "Fee summary",
      program: d.course || d.program || "",
      specialization: d.specialization || undefined,
      academicYear: d.academic_year,
      scholarship: sch.label || undefined,
      semesters: semestersOf(d),
      confirmed: d.payable_confirmed ? { label: "First-year payable (confirmed)", value: d.payable_confirmed } : undefined,
      pendingTotal: d.payable_after_approval
        ? { label: "If pending concessions are approved", value: d.payable_after_approval }
        : undefined,
      pending,
      notes: [d.course_total && d.duration_years
        ? `Full course (${d.duration_years} years, as things stand): ${d.course_total}` : "",
              d.application_fee ? `Application fee ${d.application_fee}, paid separately.` : ""].filter(Boolean),
    }),
    [d, sch, pending]
  );

  return (
    <div className="rich-card fp-card fp-summary">
      <div className="card-header">
        <span className="card-badge">
          <RupeeIcon size={14} /> Your fee summary
        </span>
        <h4 className="card-title">{d.course || d.program}</h4>
      </div>
      <p className="fp-meta">
        {d.academic_year} · first year · <strong>{d.category}</strong>
      </p>

      <div className="fp-totals">
        <div className="fp-total-main">
          <span className="fp-hero-label">Payable now (confirmed)</span>
          <span className="fp-hero-amount">{d.payable_confirmed}</span>
        </div>
        {d.payable_after_approval && (
          <div className="fp-total-after">
            <span className="fp-hero-label">After pending approvals</span>
            <span className="fp-after-amount">{d.payable_after_approval}</span>
            <span className="fp-note">estimate, not yet approved</span>
          </div>
        )}
      </div>

      {Array.isArray(d.semesters) && d.semesters.length > 0 && (
        <div className="fp-sem-block">
          <SemesterFeeTable semesters={d.semesters} caption="Payable now, semester by semester" compact />
        </div>
      )}

      <div className="fp-table-wrap">
        <table className="fp-table">
          <thead>
            <tr>
              <th scope="col">Item</th>
              <th scope="col" className="fp-num">Amount</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.item}
                className={r.kind === "discount" ? "is-discount" : r.kind === "pending" ? "is-pending" : undefined}
              >
                <td>
                  <span className="fp-cat">{r.item}</span>
                  {r.kind === "pending" && (
                    <span className="fp-pill fp-pill--pending">{STATUS_TEXT[r.status] || "Pending"}</span>
                  )}
                  {r.kind === "discount" && <span className="fp-pill fp-pill--ok">Applied</span>}
                  {r.note && <span className="fp-note">{r.note}</span>}
                </td>
                <td className="fp-num">{r.amount}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row">Approved concessions</th>
              <td className="fp-num">{d.total_approved_concessions}</td>
            </tr>
            <tr className="is-total">
              <th scope="row">Payable now</th>
              <td className="fp-num">{d.payable_confirmed}</td>
            </tr>
          </tfoot>
        </table>
      </div>

      <dl className="fp-status-list">
        <div>
          <dt>Academic scholarship</dt>
          <dd>{sch.label}</dd>
        </div>
        <div>
          <dt>Special consideration</dt>
          <dd>{cons.category ? `${cons.category}: ${cons.label}` : cons.label}</dd>
        </div>
      </dl>

      {pending.length > 0 && (
        <div className="fp-proof" role="note">
          <ShieldCheckIcon size={16} />
          <div>
            <strong>Still open</strong>
            <ul className="fp-pending-list">
              {pending.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
      {d.combine_note && <p className="fp-merit">{d.combine_note}</p>}
      <ul className="fp-foot-notes">
        {d.course_total && d.duration_years && (
          <li>
            Full course ({d.duration_years} years, as things stand): {d.course_total}
          </li>
        )}
        {d.application_fee && <li>Application fee {d.application_fee}, paid separately when you apply.</li>}
        {Array.isArray(d.flags) && d.flags.map((f: string) => <li key={f}>{f}</li>)}
        <li>Books and personal expenses are not included.</li>
      </ul>

      <div className="agent-card-footer fp-footer">
        <FeeCardShare model={imageModel} fileName="sru-fee-summary.png" title={`SR University fee summary: ${d.program}`} />
        <span className="agent-card-source-tag">Source: SR University fee circular, {d.academic_year}.</span>
      </div>
    </div>
  );
}
