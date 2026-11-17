/**
 * Pure logic for the Fee & Scholarship Calculator.
 *
 * There are NO fee amounts in this file. Every number comes from the fee table the backend
 * serves at /api/v1/agent/fee-config (a generated copy is bundled as src/data/feeConfig.json so
 * the calculator can draw instantly). That table is produced from
 * backend/app/sru_agent/fees_2027_28.json, the same file the chat agent uses, so the calculator
 * and the chat cannot disagree.
 *
 * Run the checks for this file with:  npm run test:calc
 */

export interface FeeSlab {
  scholarship_percent: number;
  /** Text to show, per exam: "80 – 91.9%", "8,001 – 20,000". */
  ranges: Record<string, string>;
  /** Numbers to match a score against, per exam: [min, max]. */
  bounds: Record<string, number[]>;
  payable_per_semester: number;
}

export interface FeeProgram {
  id: string;
  name: string;
  level: string;
  tuition_per_year: number;
  tuition_per_semester: number;
  yearly_increase: number;
  duration_years: number | null;
  minimum_percent: number;
  eligibility: string;
  specialization_fee_per_year_from_year2: number;
  exams: { key: string; label: string }[];
  slabs: FeeSlab[];
}

export interface FeeConfig {
  status: string;
  academic_year: string;
  source: string;
  one_time: { enrollment_fee: number; application_fee: number };
  yearly_other: Record<string, number>;
  transport_per_year: number | null;
  hostel_per_year: Record<string, number>;
  hostel_labels: Record<string, string>;
  hostel_deposits: Record<string, number>;
  special_concessions: { key: string; label: string; amount: number }[];
  programs: FeeProgram[];
}

export interface ParsedScore {
  status: "empty" | "ok" | "invalid";
  /** The exam this score belongs to. May differ from the one selected in the dropdown. */
  examKey: string;
  /** True when the typed text itself named a different exam ("EAPCET 9000") or could only be one. */
  switched: boolean;
  /** Percentage, percentile, rank or IB score, ready to compare with slab bounds. */
  value?: number;
  /** How to show the score back to the student: "Rank 9,000", "850/1000 (85%)". */
  display: string;
  /** Why the entry could not be used. */
  message?: string;
}

export interface Estimate {
  scholarshipPercent: number;
  tuitionYear: number;
  netYear: number;
  netSem: number;
  savingYear: number;
  enrollment: number;
  otherYearly: number;
  hostelYear: number;
  regularSemTotal: number;
  sem1Total: number;
  firstYearTotal: number;
  /** Tuition payable in each year of the course (empty when the duration is not in the fee table). */
  years: number[];
  fullCourseTotal: number | null;
  nextSlab: { percent: number; requires: string; extraSavingYear: number } | null;
}

const PERCENT_EXAMS = new Set(["state_board", "cbse"]);

/** Words in the typed text that name an exam. Checked in this order. */
const EXAM_HINTS: { key: string; pattern: RegExp }[] = [
  { key: "eapcet_rank", pattern: /\b(?:eapcet|eamcet|emcet|rank)\b/i },
  { key: "jee_percentile", pattern: /\bjee\b|percentile|%\s*ile/i },
  { key: "ib", pattern: /\bib\b/i },
  { key: "cbse", pattern: /\b(?:cbse|icse)\b/i },
  { key: "state_board", pattern: /\b(?:inter|intermediate|ipe|state\s*board|12th|10\s*\+\s*2)\b/i },
];

export function inr(amount: number): string {
  return "₹" + Math.round(amount).toLocaleString("en-IN");
}

/** "₹2,55,000" -> 255000 */
export function rupees(text: string | null | undefined): number {
  const digits = (text || "").replace(/[^\d]/g, "");
  return digits ? parseInt(digits, 10) : 0;
}

function examLabel(program: FeeProgram, key: string): string {
  return program.exams.find((e) => e.key === key)?.label || key;
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

/**
 * Understand what the student typed: "88%", "850", "850/1000", "EAPCET 9000", "rank 4,500",
 * "jee 92.4", "IB 36". If the text names an exam, or can only belong to one, that exam is used
 * even when a different one is selected in the dropdown.
 */
export function parseScore(program: FeeProgram, selectedExamKey: string, raw: string): ParsedScore {
  const text = (raw || "").trim();
  const offered = program.exams.map((e) => e.key);
  const fallbackExam = offered.includes(selectedExamKey) ? selectedExamKey : offered[0];
  if (!text) return { status: "empty", examKey: fallbackExam, switched: false, display: "" };

  const invalid = (message: string, examKey = fallbackExam): ParsedScore => ({
    status: "invalid", examKey, switched: false, display: "", message,
  });

  // 1. Which exam? A keyword in the text wins over the dropdown.
  let examKey = fallbackExam;
  const hint = EXAM_HINTS.find((h) => h.pattern.test(text));
  if (hint) {
    if (!offered.includes(hint.key)) {
      // "cbse 92" on a PG course still means a percentage; other exams are simply not used there.
      if (PERCENT_EXAMS.has(hint.key) && offered.includes("state_board")) {
        examKey = "state_board";
      } else {
        const names: Record<string, string> = {
          eapcet_rank: "An EAPCET rank", jee_percentile: "A JEE Main percentile", ib: "An IB score",
        };
        return invalid(`${names[hint.key] || "That exam"} is not used for ${program.name}. ` +
          `Please enter your ${examLabel(program, fallbackExam)}.`);
      }
    } else {
      examKey = hint.key;
    }
  }

  // 2. The numbers. "4,500" is one number; "850/1000" or "850 out of 1000" is a fraction.
  const cleaned = text.replace(/(\d),(?=\d)/g, "$1");
  const fraction = cleaned.match(/(\d+(?:\.\d+)?)\s*(?:\/|out\s+of)\s*(\d+(?:\.\d+)?)/i);
  const first = cleaned.match(/\d+(?:\.\d+)?/);
  if (!first) return invalid("Please type your marks, percentage or rank as a number.", examKey);
  const num = parseFloat(first[0]);
  const hasPercentSign = /\d\s*%(?!\s*ile)/i.test(cleaned);

  // 3. Text that can only be one kind of score, whatever is selected.
  if (!hint) {
    if (fraction || hasPercentSign) {
      if (!PERCENT_EXAMS.has(examKey)) examKey = offered.includes("state_board") ? "state_board" : examKey;
    } else if (num > 1000 && offered.includes("eapcet_rank")) {
      examKey = "eapcet_rank"; // marks never exceed 1000, so a bigger number is a rank
    }
  }
  const switched = examKey !== fallbackExam;
  const ok = (value: number, display: string): ParsedScore => ({ status: "ok", examKey, switched, value, display });

  if (examKey === "eapcet_rank") {
    if (fraction || hasPercentSign) return invalid("An EAPCET rank is a whole number, for example 4500.", examKey);
    const rank = Math.round(num);
    if (rank < 1) return invalid("Please enter a valid EAPCET rank, for example 4500.", examKey);
    return ok(rank, `EAPCET rank ${rank.toLocaleString("en-IN")}`);
  }
  if (examKey === "jee_percentile") {
    if (num > 100) return invalid("A JEE Main percentile is between 0 and 100.", examKey);
    return ok(round2(num), `JEE Main ${round2(num)} percentile`);
  }
  if (examKey === "ib") {
    if (num > 45) return invalid("An IB Diploma score is out of 45.", examKey);
    return ok(Math.round(num), `IB score ${Math.round(num)}/45`);
  }

  // Percentage exams: a percentage, a fraction, or raw marks.
  if (fraction) {
    const got = parseFloat(fraction[1]);
    const max = parseFloat(fraction[2]);
    if (max <= 0 || got > max) return invalid("Marks obtained cannot be more than the maximum marks.", examKey);
    const pct = round2((got / max) * 100);
    return ok(pct, `${got}/${max} (${pct}%)`);
  }
  if (num <= 100) return ok(round2(num), `${round2(num)}%`);
  if (hasPercentSign) return invalid("A percentage cannot be more than 100.", examKey);
  if (examKey === "cbse" && num <= 500) {
    const pct = round2((num / 500) * 100);
    return ok(pct, `${num}/500 (${pct}%)`);
  }
  if (num <= 1000) {
    const pct = round2(num / 10);
    return ok(pct, `${num}/1000 (${pct}%)`);
  }
  return invalid("That is more than the maximum marks. Enter marks out of 1000, or a percentage.", examKey);
}

/** Scholarship % for a score. 0 when the score is outside every slab. */
export function matchSlab(program: FeeProgram, examKey: string, value: number): number {
  for (const slab of program.slabs) {
    const b = slab.bounds[examKey];
    if (b && value >= b[0] && value <= b[1]) return slab.scholarship_percent;
  }
  return 0;
}

/** "Merit scholarship starts at 60%" / "Rank scholarships cover ranks up to 20,000". */
export function scholarshipStartText(program: FeeProgram, examKey: string): string {
  const withExam = program.slabs.filter((s) => s.bounds[examKey]);
  if (!withExam.length) return "";
  if (examKey === "eapcet_rank") {
    const worstRank = Math.max(...withExam.map((s) => s.bounds[examKey][1]));
    return `Rank scholarships cover EAPCET ranks up to ${worstRank.toLocaleString("en-IN")}`;
  }
  const lowest = Math.min(...withExam.map((s) => s.bounds[examKey][0]));
  if (examKey === "ib") return `Merit scholarship starts at an IB score of ${lowest}`;
  if (examKey === "jee_percentile") return `Merit scholarship starts at ${lowest} percentile`;
  return `Merit scholarship starts at ${lowest}%`;
}

/** The fee estimate for one scholarship %, using only numbers from the fee table. */
export function computeEstimate(
  config: FeeConfig, program: FeeProgram, scholarshipPercent: number, hostelKey: string, examKey: string,
): Estimate {
  const tuitionYear = program.tuition_per_year;
  const netYear = Math.round((tuitionYear * (100 - scholarshipPercent)) / 100);
  const enrollment = config.one_time.enrollment_fee || 0;
  const otherYearly = Object.values(config.yearly_other).reduce((a, b) => a + b, 0);
  const hostelYear = hostelKey && hostelKey !== "none" ? config.hostel_per_year[hostelKey] || 0 : 0;
  const regularSemTotal = Math.round(netYear / 2) + Math.round(otherYearly / 2) + Math.round(hostelYear / 2);

  // The yearly increase is the same flat amount for every student, with or without scholarship.
  const years: number[] = [];
  for (let y = 0; y < (program.duration_years || 0); y++) years.push(netYear + program.yearly_increase * y);
  const fullCourseTotal = years.length
    ? years.reduce((a, b) => a + b, 0) + enrollment + (otherYearly + hostelYear) * years.length
    : null;

  const better = program.slabs
    .filter((s) => s.scholarship_percent > scholarshipPercent && s.bounds[examKey])
    .sort((a, b) => a.scholarship_percent - b.scholarship_percent)[0];

  return {
    scholarshipPercent, tuitionYear, netYear, netSem: Math.round(netYear / 2),
    savingYear: tuitionYear - netYear, enrollment, otherYearly, hostelYear,
    regularSemTotal, sem1Total: regularSemTotal + enrollment,
    firstYearTotal: netYear + enrollment + otherYearly + hostelYear,
    years, fullCourseTotal,
    nextSlab: better
      ? {
          percent: better.scholarship_percent,
          requires: `${examLabel(program, examKey)}: ${better.ranges[examKey]}`,
          extraSavingYear: Math.round((tuitionYear * (better.scholarship_percent - scholarshipPercent)) / 100),
        }
      : null,
  };
}

/** What to send to POST /api/v1/agent/calculate for this score. */
export function calculateParams(programId: string, parsed: ParsedScore, hostelKey: string) {
  const v = parsed.status === "ok" ? parsed.value : undefined;
  return {
    program: programId,
    board: parsed.examKey === "cbse" ? "cbse" : "state_board",
    percent: PERCENT_EXAMS.has(parsed.examKey) ? v : undefined,
    eapcet_rank: parsed.examKey === "eapcet_rank" ? v : undefined,
    jee_percentile: parsed.examKey === "jee_percentile" ? v : undefined,
    ib_score: parsed.examKey === "ib" ? v : undefined,
    hostel: hostelKey || "none",
  };
}

/** The backend's answer in the same shape as computeEstimate, so the screen can show either. */
export function estimateFromBackend(res: any, local: Estimate): Estimate {
  const netYear = rupees(res.tuition_first_year_after_scholarship);
  const years: number[] = Array.isArray(res.year_by_year)
    ? res.year_by_year.map((y: any) => rupees(y.after_scholarship))
    : local.years;
  return {
    scholarshipPercent: Number(res.scholarship_percent) || 0,
    tuitionYear: rupees(res.tuition_first_year),
    netYear,
    netSem: rupees(res.per_semester_after_scholarship),
    savingYear: rupees(res.saving_first_year),
    enrollment: rupees(res.one_time_enrollment_fee),
    otherYearly: rupees(res.other_yearly_fees),
    hostelYear: res.hostel ? rupees(res.hostel.per_year) : 0,
    regularSemTotal: rupees(res.total_per_semester) || local.regularSemTotal,
    sem1Total: rupees(res.sem1_total_payable) || local.sem1Total,
    firstYearTotal: rupees(res.first_year_total_payable),
    years,
    fullCourseTotal: res.full_course_total ? rupees(res.full_course_total) : local.fullCourseTotal,
    nextSlab: res.next_scholarship_slab
      ? {
          percent: res.next_scholarship_slab.scholarship_percent,
          requires: res.next_scholarship_slab.requires,
          extraSavingYear: rupees(res.next_scholarship_slab.extra_saving_first_year),
        }
      : null,
  };
}
