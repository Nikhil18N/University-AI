import React, { useState, useMemo } from "react";
import {
  CalculatorIcon,
  AwardIcon,
  BoltIcon,
  CalendarIcon,
  PinIcon,
  FlaskIcon,
  HeartHandIcon,
  MessageSquareIcon,
  CloseIcon,
  ShieldCheckIcon,
  RefreshIcon,
  CheckIcon,
} from "./Icons";
import { createLead } from "../services/api";
import "./ScholarshipCalculatorModal.css";

interface Props {
  onClose: () => void;
  onAskBuddy: (prompt: string) => void;
}

interface ScholarshipSlab {
  scholarshipPercent: number;
  ranges: {
    stateBoard?: string;
    cbse?: string;
    jeeMains?: string;
    eamcet?: string;
    sat?: string;
    ib?: string;
    degree?: string;
    icet?: string;
    catMat?: string;
    gate?: string;
    icar?: string;
  };
  payableFeeSem: number;
  cseYearlyPayable?: { yr1: number; yr2: number; yr3: number; yr4: number };
}

interface ProgramConfig {
  id: string;
  name: string;
  degreeType: "Bachelors" | "Masters";
  baseTuitionSem: number;
  enrollmentFee: number;
  admissionFee: number;
  specializationFeeAnnual?: number;
  specializations?: string[];
  supportedExams: { key: string; label: string }[];
  slabs: ScholarshipSlab[];
}

const PROGRAMS: ProgramConfig[] = [
  {
    id: "btech_cse",
    name: "B.Tech. Computer Science & Engineering (CSE)",
    degreeType: "Bachelors",
    baseTuitionSem: 147500,
    enrollmentFee: 5000,
    admissionFee: 25000,
    specializationFeeAnnual: 30000,
    specializations: ["Artificial Intelligence & Machine Learning", "Cyber Security", "Data Science", "Gaming & ARVR", "Robotics and Automation"],
    supportedExams: [
      { key: "stateBoard", label: "State Board (10+2 / Inter) %" },
      { key: "cbse", label: "CBSE %" },
      { key: "jeeMains", label: "JEE Mains %" },
      { key: "eamcet", label: "EAMCET / EAPCET Rank" },
      { key: "sat", label: "SAT Score" },
      { key: "ib", label: "IB Score" },
    ],
    slabs: [
      {
        scholarshipPercent: 20,
        ranges: { stateBoard: "60 – 69.99%", cbse: "60 – 64.99%", jeeMains: "75 – 85%", eamcet: "16001 – 18000", sat: "1151 – 1200", ib: "27 – 29" },
        payableFeeSem: 118000,
        cseYearlyPayable: { yr1: 118000, yr2: 124000, yr3: 130000, yr4: 136000 },
      },
      {
        scholarshipPercent: 30,
        ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%", jeeMains: "85.1 – 90%", eamcet: "15001 – 16000", sat: "1201 – 1250", ib: "30 – 32" },
        payableFeeSem: 104000,
        cseYearlyPayable: { yr1: 104000, yr2: 109000, yr3: 114000, yr4: 119000 },
      },
      {
        scholarshipPercent: 40,
        ranges: { stateBoard: "80 – 89.99%", cbse: "75 – 84.99%", jeeMains: "90.1 – 93%", eamcet: "10001 – 15000", sat: "1251 – 1300", ib: "33 – 35" },
        payableFeeSem: 89000,
        cseYearlyPayable: { yr1: 89000, yr2: 93000, yr3: 98000, yr4: 102000 },
      },
      {
        scholarshipPercent: 50,
        ranges: { stateBoard: "90 – 94.99%", cbse: "85 – 89.99%", jeeMains: "93.1 – 95%", eamcet: "5001 – 10000", sat: "1301 – 1350", ib: "36 – 38" },
        payableFeeSem: 74000,
        cseYearlyPayable: { yr1: 74000, yr2: 77500, yr3: 81500, yr4: 85500 },
      },
      {
        scholarshipPercent: 70,
        ranges: { stateBoard: "≥ 95%", cbse: "≥ 90%", jeeMains: "≥ 95.1%", eamcet: "1 – 5000", sat: "≥ 1351", ib: "≥ 39" },
        payableFeeSem: 45000,
        cseYearlyPayable: { yr1: 45000, yr2: 46500, yr3: 49000, yr4: 51500 },
      },
    ],
  },
  {
    id: "btech_ece",
    name: "B.Tech. Electronics & Communication Engineering (ECE)",
    degreeType: "Bachelors",
    baseTuitionSem: 120000,
    enrollmentFee: 5000,
    admissionFee: 25000,
    supportedExams: [
      { key: "stateBoard", label: "State Board (10+2 / Inter) %" },
      { key: "cbse", label: "CBSE %" },
      { key: "jeeMains", label: "JEE Mains %" },
      { key: "eamcet", label: "EAMCET / EAPCET Rank" },
      { key: "sat", label: "SAT Score" },
      { key: "ib", label: "IB Score" },
    ],
    slabs: [
      { scholarshipPercent: 20, ranges: { stateBoard: "60 – 69.99%", cbse: "60 – 64.99%", jeeMains: "75 – 85%", eamcet: "16001 – 18000", sat: "1151 – 1200", ib: "27 – 29" }, payableFeeSem: 96000 },
      { scholarshipPercent: 30, ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%", jeeMains: "85.1 – 90%", eamcet: "15001 – 16000", sat: "1201 – 1250", ib: "30 – 32" }, payableFeeSem: 84000 },
      { scholarshipPercent: 40, ranges: { stateBoard: "80 – 89.99%", cbse: "75 – 84.99%", jeeMains: "90.1 – 93%", eamcet: "10001 – 15000", sat: "1251 – 1300", ib: "33 – 35" }, payableFeeSem: 72000 },
      { scholarshipPercent: 50, ranges: { stateBoard: "90 – 94.99%", cbse: "85 – 89.99%", jeeMains: "93.1 – 95%", eamcet: "5001 – 10000", sat: "1301 – 1350", ib: "36 – 38" }, payableFeeSem: 60000 },
      { scholarshipPercent: 70, ranges: { stateBoard: "≥ 95%", cbse: "≥ 90%", jeeMains: "≥ 95.1%", eamcet: "1 – 5000", sat: "≥ 1351", ib: "≥ 39" }, payableFeeSem: 36000 },
    ],
  },
  {
    id: "btech_core",
    name: "B.Tech. Core (Mechanical / Civil / EEE)",
    degreeType: "Bachelors",
    baseTuitionSem: 100000,
    enrollmentFee: 5000,
    admissionFee: 25000,
    supportedExams: [
      { key: "stateBoard", label: "State Board (10+2 / Inter) %" },
      { key: "cbse", label: "CBSE %" },
      { key: "jeeMains", label: "JEE Mains %" },
      { key: "eamcet", label: "EAMCET / EAPCET Rank" },
    ],
    slabs: [
      { scholarshipPercent: 20, ranges: { stateBoard: "60 – 69.99%", cbse: "60 – 64.99%", jeeMains: "75 – 85%", eamcet: "16001 – 20000" }, payableFeeSem: 80000 },
      { scholarshipPercent: 35, ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%", jeeMains: "85.1 – 90%", eamcet: "10001 – 16000" }, payableFeeSem: 65000 },
      { scholarshipPercent: 50, ranges: { stateBoard: "80 – 89.99%", cbse: "75 – 84.99%", jeeMains: "90.1 – 93%", eamcet: "5001 – 10000" }, payableFeeSem: 50000 },
      { scholarshipPercent: 70, ranges: { stateBoard: "≥ 90%", cbse: "≥ 85%", jeeMains: "≥ 93.1%", eamcet: "1 – 5000" }, payableFeeSem: 30000 },
    ],
  },
  {
    id: "bba",
    name: "BBA (Bachelor of Business Administration)",
    degreeType: "Bachelors",
    baseTuitionSem: 90000,
    enrollmentFee: 5000,
    admissionFee: 15000,
    supportedExams: [
      { key: "stateBoard", label: "10+2 Any Stream %" },
      { key: "cbse", label: "CBSE %" },
    ],
    slabs: [
      { scholarshipPercent: 20, ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%" }, payableFeeSem: 72000 },
      { scholarshipPercent: 35, ranges: { stateBoard: "80 – 89.99%", cbse: "75 – 84.99%" }, payableFeeSem: 58500 },
      { scholarshipPercent: 50, ranges: { stateBoard: "≥ 90%", cbse: "≥ 85%" }, payableFeeSem: 45000 },
    ],
  },
  {
    id: "bca",
    name: "BCA (Bachelor of Computer Applications)",
    degreeType: "Bachelors",
    baseTuitionSem: 90000,
    enrollmentFee: 5000,
    admissionFee: 15000,
    supportedExams: [
      { key: "stateBoard", label: "10+2 Any Stream %" },
      { key: "cbse", label: "CBSE %" },
    ],
    slabs: [
      { scholarshipPercent: 20, ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%" }, payableFeeSem: 72000 },
      { scholarshipPercent: 35, ranges: { stateBoard: "80 – 89.99%", cbse: "75 – 84.99%" }, payableFeeSem: 58500 },
      { scholarshipPercent: 50, ranges: { stateBoard: "≥ 90%", cbse: "≥ 85%" }, payableFeeSem: 45000 },
    ],
  },
  {
    id: "bsc_agri",
    name: "B.Sc. (Hons) Agriculture",
    degreeType: "Bachelors",
    baseTuitionSem: 97500,
    enrollmentFee: 5000,
    admissionFee: 25000,
    supportedExams: [
      { key: "stateBoard", label: "10+2 BiPC / MPC %" },
      { key: "eamcet", label: "EAMCET Agri Stream Rank" },
      { key: "icar", label: "ICAR AIEEA Rank" },
    ],
    slabs: [
      { scholarshipPercent: 20, ranges: { stateBoard: "70 – 79.99%", eamcet: "10001 – 15000", icar: "5001 – 8000" }, payableFeeSem: 78000 },
      { scholarshipPercent: 35, ranges: { stateBoard: "80 – 89.99%", eamcet: "5001 – 10000", icar: "2001 – 5000" }, payableFeeSem: 63375 },
      { scholarshipPercent: 50, ranges: { stateBoard: "≥ 90%", eamcet: "1 – 5000", icar: "1 – 2000" }, payableFeeSem: 48750 },
    ],
  },
  {
    id: "mba",
    name: "MBA (Master of Business Administration)",
    degreeType: "Masters",
    baseTuitionSem: 150000,
    enrollmentFee: 5000,
    admissionFee: 20000,
    supportedExams: [
      { key: "degree", label: "Graduation Degree %" },
      { key: "icet", label: "TS / AP ICET Rank" },
      { key: "catMat", label: "CAT / MAT Percentile" },
    ],
    slabs: [
      { scholarshipPercent: 20, ranges: { degree: "70 – 79.99%", icet: "5001 – 10000", catMat: "70 – 79.9%" }, payableFeeSem: 120000 },
      { scholarshipPercent: 35, ranges: { degree: "80 – 89.99%", icet: "1001 – 5000", catMat: "80 – 89.9%" }, payableFeeSem: 97500 },
      { scholarshipPercent: 50, ranges: { degree: "≥ 90%", icet: "1 – 1000", catMat: "≥ 90%" }, payableFeeSem: 75000 },
    ],
  },
  {
    id: "mtech",
    name: "M.Tech. (Engineering Postgraduate)",
    degreeType: "Masters",
    baseTuitionSem: 52250,
    enrollmentFee: 5000,
    admissionFee: 10000,
    supportedExams: [
      { key: "degree", label: "B.Tech Graduation %" },
      { key: "gate", label: "GATE Qualified Score" },
    ],
    slabs: [
      { scholarshipPercent: 20, ranges: { degree: "70 – 79.99%", gate: "Score 350 – 450" }, payableFeeSem: 41800 },
      { scholarshipPercent: 35, ranges: { degree: "80 – 89.99%", gate: "Score 451 – 550" }, payableFeeSem: 33962 },
      { scholarshipPercent: 50, ranges: { degree: "≥ 90%", gate: "Score > 550" }, payableFeeSem: 26125 },
    ],
  },
];

/** Helper to match exact input score or rank into appropriate slab index */
function matchSlabFromScore(
  program: ProgramConfig,
  examKey: string,
  scoreInput: string
): number {
  if (!scoreInput.trim()) return 0;
  const num = parseFloat(scoreInput.replace(/[^\d.]/g, ""));
  if (isNaN(num)) return 0;

  const slabs = program.slabs;
  if (!slabs || slabs.length === 0) return 0;

  const isRank =
    examKey.toLowerCase().includes("rank") ||
    examKey.toLowerCase().includes("eamcet") ||
    examKey.toLowerCase().includes("icet") ||
    examKey.toLowerCase().includes("icar");

  if (isRank) {
    // For ranks: lower number is higher percentile
    for (let i = slabs.length - 1; i >= 0; i--) {
      const slab = slabs[i];
      const rangeStr = (slab.ranges as any)[examKey] || "";
      const match = rangeStr.match(/(\d+)\s*[–-]\s*(\d+)/);
      if (match) {
        const low = parseInt(match[1], 10);
        const high = parseInt(match[2], 10);
        if (num >= low && num <= high) return i;
      }
    }
    // Check if score is better than the top tier
    for (let i = slabs.length - 1; i >= 0; i--) {
      const rangeStr = (slabs[i].ranges as any)[examKey] || "";
      const match = rangeStr.match(/(\d+)\s*[–-]\s*(\d+)/);
      if (match && num <= parseInt(match[2], 10)) return i;
    }
    return 0;
  }

  // Percentage or Score based exam (higher is better)
  for (let i = slabs.length - 1; i >= 0; i--) {
    const slab = slabs[i];
    const rangeStr = (slab.ranges as any)[examKey] || slab.ranges.stateBoard || "";
    if (rangeStr.includes("≥") || rangeStr.includes(">=") || rangeStr.includes(">")) {
      const minVal = parseFloat(rangeStr.replace(/[^\d.]/g, ""));
      if (!isNaN(minVal) && num >= minVal) return i;
    }
    const match = rangeStr.match(/(\d+(?:\.\d+)?)\s*[–-]\s*(\d+(?:\.\d+)?)/);
    if (match) {
      const low = parseFloat(match[1]);
      const high = parseFloat(match[2]);
      if (num >= low && num <= high) return i;
    }
  }

  // If score exceeds the highest defined threshold
  for (let i = slabs.length - 1; i >= 0; i--) {
    const rangeStr = (slabs[i].ranges as any)[examKey] || slabs[i].ranges.stateBoard || "";
    const match = rangeStr.match(/(\d+(?:\.\d+)?)/);
    if (match && num >= parseFloat(match[1])) return i;
  }

  return 0;
}

interface CalculatedSnapshot {
  program: ProgramConfig;
  exam: { key: string; label: string };
  slab: ScholarshipSlab;
  rangeText: string;
  discountAmount: number;
  enteredScore: string;
  studentName: string;
  studentPhone: string;
}

export default function ScholarshipCalculatorModal({ onClose, onAskBuddy }: Props) {
  // Pre-load saved lead info if user already verified previously
  const savedLead = useMemo(() => {
    try {
      const raw = localStorage.getItem("sru_student_lead");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }, []);

  // 1. Form state
  const [selectedProgramId, setSelectedProgramId] = useState<string>("btech_cse");
  const [selectedExamKey, setSelectedExamKey] = useState<string>("stateBoard");
  const [enteredScore, setEnteredScore] = useState<string>("85%");
  const [selectedSlabIndex, setSelectedSlabIndex] = useState<number>(2);
  const [isManualSlabOverride, setIsManualSlabOverride] = useState<boolean>(false);

  // Student Authentication / Lead details
  const [studentName, setStudentName] = useState<string>(savedLead?.name || "");
  const [studentPhone, setStudentPhone] = useState<string>(savedLead?.phone || "");
  const [validationError, setValidationError] = useState<string | null>(null);

  // 2. Calculated snapshot state
  const [calculatedSnapshot, setCalculatedSnapshot] = useState<CalculatedSnapshot | null>(null);
  const [isSelectionModified, setIsSelectionModified] = useState<boolean>(false);

  // Active program & exam configuration
  const currentProgram = useMemo(
    () => PROGRAMS.find((p) => p.id === selectedProgramId) || PROGRAMS[0],
    [selectedProgramId]
  );

  const activeExams = currentProgram.supportedExams;
  const currentExam = useMemo(() => {
    return activeExams.find((e) => e.key === selectedExamKey) || activeExams[0];
  }, [activeExams, selectedExamKey]);

  // Handle score input change and auto-match slab
  const handleScoreChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setEnteredScore(val);
    if (!isManualSlabOverride) {
      const idx = matchSlabFromScore(currentProgram, currentExam.key, val);
      setSelectedSlabIndex(idx);
    }
    if (calculatedSnapshot) setIsSelectionModified(true);
  };

  // Program change
  const handleProgramChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newProgId = e.target.value;
    setSelectedProgramId(newProgId);
    const prog = PROGRAMS.find((p) => p.id === newProgId);
    let nextExamKey = selectedExamKey;
    if (prog && !prog.supportedExams.some((x) => x.key === selectedExamKey)) {
      nextExamKey = prog.supportedExams[0].key;
      setSelectedExamKey(nextExamKey);
    }
    if (prog && !isManualSlabOverride) {
      const idx = matchSlabFromScore(prog, nextExamKey, enteredScore);
      setSelectedSlabIndex(idx);
    }
    if (calculatedSnapshot) setIsSelectionModified(true);
  };

  // Exam change
  const handleExamChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newExamKey = e.target.value;
    setSelectedExamKey(newExamKey);
    if (!isManualSlabOverride) {
      const idx = matchSlabFromScore(currentProgram, newExamKey, enteredScore);
      setSelectedSlabIndex(idx);
    }
    if (calculatedSnapshot) setIsSelectionModified(true);
  };

  // Slab manual select
  const handleSlabChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedSlabIndex(Number(e.target.value));
    setIsManualSlabOverride(true);
    if (calculatedSnapshot) setIsSelectionModified(true);
  };

  // Calculate & authenticate lead
  const handleCalculate = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate student authentication inputs
    const cleanName = studentName.trim();
    const cleanPhoneDigits = studentPhone.replace(/\D/g, "");

    if (!cleanName) {
      setValidationError("Please enter student name to authenticate and view official fee structure.");
      return;
    }
    if (cleanPhoneDigits.length < 10) {
      setValidationError("Please enter a valid 10-digit mobile number for admissions verification.");
      return;
    }
    setValidationError(null);

    const prog = currentProgram;
    const exam = currentExam;
    const slab = prog.slabs[selectedSlabIndex] || prog.slabs[0];
    const rangeText =
      (slab.ranges as any)[exam.key] ||
      slab.ranges.stateBoard ||
      `Slab ${selectedSlabIndex + 1}`;
    const discount = Math.round(
      prog.baseTuitionSem * (slab.scholarshipPercent / 100)
    );

    // Save lead in localStorage and backend
    const leadData = {
      name: cleanName,
      phone: studentPhone.trim(),
      program_interest: prog.name,
      score: enteredScore.trim() || rangeText,
      exam_type: exam.label,
      source: "scholarship_calculator",
      metadata: {
        calculated_discount: discount,
        scholarship_percent: slab.scholarshipPercent,
        payable_sem: slab.payableFeeSem,
      },
    };
    try {
      localStorage.setItem("sru_student_lead", JSON.stringify({ name: cleanName, phone: studentPhone.trim() }));
      await createLead(leadData);
    } catch (err) {
      console.warn("Lead registration note:", err);
    }

    setCalculatedSnapshot({
      program: prog,
      exam,
      slab,
      rangeText,
      discountAmount: discount,
      enteredScore: enteredScore.trim(),
      studentName: cleanName,
      studentPhone: studentPhone.trim(),
    });
    setIsSelectionModified(false);
  };

  // Matched slab info for badge
  const matchedSlab = currentProgram.slabs[selectedSlabIndex] || currentProgram.slabs[0];
  const matchedRangeStr =
    (matchedSlab.ranges as any)[currentExam.key] ||
    matchedSlab.ranges.stateBoard ||
    "Standard Slab";

  return (
    <div className="scholarship-modal-backdrop" onClick={onClose}>
      <div className="scholarship-modal-card" onClick={(e) => e.stopPropagation()}>
        {/* Executive Minimalist Header */}
        <div className="calc-header">
          <div className="calc-title-group">
            <div className="calc-icon-badge" aria-hidden="true">
              <CalculatorIcon size={20} />
            </div>
            <div>
              <h3 className="calc-title">Fee & Scholarship Calculator</h3>
              <p className="calc-subtitle">SR University Official Merit Scholarship & Payable Fee Portal</p>
            </div>
          </div>
          <button className="calc-close-btn" onClick={onClose} aria-label="Close calculator" type="button">
            <CloseIcon size={18} />
          </button>
        </div>

        {/* Form Controls */}
        <form onSubmit={handleCalculate} className="calc-form">
          <div className="calc-grid-controls">
            {/* 1. Academic Program */}
            <div className="calc-field">
              <label htmlFor="calc-prog-select">1. Academic Program</label>
              <select
                id="calc-prog-select"
                value={selectedProgramId}
                onChange={handleProgramChange}
                className="calc-select"
              >
                <optgroup label="Bachelors Degrees">
                  {PROGRAMS.filter((p) => p.degreeType === "Bachelors").map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </optgroup>
                <optgroup label="Masters Degrees">
                  {PROGRAMS.filter((p) => p.degreeType === "Masters").map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>

            {/* 2. Qualifying Board / Exam */}
            <div className="calc-field">
              <label htmlFor="calc-exam-select">2. Qualifying Board / Exam</label>
              <select
                id="calc-exam-select"
                value={currentExam.key}
                onChange={handleExamChange}
                className="calc-select"
              >
                {activeExams.map((ex) => (
                  <option key={ex.key} value={ex.key}>
                    {ex.label}
                  </option>
                ))}
              </select>
            </div>

            {/* 3. Ask for Exact Score / Rank */}
            <div className="calc-field calc-field-score">
              <div className="calc-score-label-row">
                <label htmlFor="calc-score-input">
                  3. Enter Score / Rank
                </label>
                <button
                  type="button"
                  className="calc-toggle-btn"
                  onClick={() => setIsManualSlabOverride(!isManualSlabOverride)}
                >
                  {isManualSlabOverride ? "← Enter exact score" : "Choose range list →"}
                </button>
              </div>

              {!isManualSlabOverride ? (
                <div className="calc-score-input-wrap">
                  <input
                    id="calc-score-input"
                    type="text"
                    className="calc-input calc-score-input"
                    placeholder="e.g. 92.5% in Inter, 8500 rank, or 1320 in SAT"
                    value={enteredScore}
                    onChange={handleScoreChange}
                  />
                  {matchedSlab && (
                    <div className="calc-matched-badge">
                      <AwardIcon size={14} />
                      <span>
                        <strong>{matchedSlab.scholarshipPercent}% Scholarship Matched</strong>
                        {" • "}{matchedRangeStr}
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                <select
                  id="calc-slab-select"
                  value={selectedSlabIndex}
                  onChange={handleSlabChange}
                  className="calc-select"
                >
                  {currentProgram.slabs.map((slab, idx) => {
                    const rangeStr =
                      (slab.ranges as any)[currentExam.key] ||
                      slab.ranges.stateBoard ||
                      `Slab ${idx + 1}`;
                    return (
                      <option key={idx} value={idx}>
                        {rangeStr} ({slab.scholarshipPercent}% Waiver)
                      </option>
                    );
                  })}
                </select>
              )}
            </div>
          </div>

          {/* Student Verification / Lead Capture Box */}
          <div className="calc-auth-box">
            <div className="calc-auth-header">
              <ShieldCheckIcon size={15} />
              <span>Student Verification & Admission Authentication</span>
            </div>
            <div className="calc-auth-grid">
              <div className="calc-field">
                <label htmlFor="calc-student-name">Student Full Name *</label>
                <input
                  id="calc-student-name"
                  type="text"
                  className="calc-input"
                  placeholder="Enter student full name"
                  value={studentName}
                  onChange={(e) => {
                    setStudentName(e.target.value);
                    if (validationError) setValidationError(null);
                  }}
                  required
                />
              </div>
              <div className="calc-field">
                <label htmlFor="calc-student-phone">10-Digit Mobile Number *</label>
                <input
                  id="calc-student-phone"
                  type="tel"
                  className="calc-input"
                  placeholder="e.g. 9876543210"
                  value={studentPhone}
                  onChange={(e) => {
                    setStudentPhone(e.target.value);
                    if (validationError) setValidationError(null);
                  }}
                  maxLength={15}
                  required
                />
              </div>
            </div>
            {validationError && (
              <div className="calc-error-banner">
                <span>{validationError}</span>
              </div>
            )}
          </div>

          {/* Action Button */}
          <button type="submit" className="calc-submit-btn">
            <BoltIcon size={16} />
            <span>Calculate Official Scholarship</span>
          </button>
        </form>

        {/* Calculation Status Banner (if inputs changed post-calculation) */}
        {calculatedSnapshot && isSelectionModified && (
          <div className="calc-stale-banner">
            <RefreshIcon size={14} />
            <span>Parameters modified. Click <strong>Calculate Official Scholarship</strong> to update results.</span>
          </div>
        )}

        {/* Empty State when user has not yet calculated */}
        {!calculatedSnapshot && (
          <div className="calc-placeholder-box">
            <div className="calc-placeholder-icon">
              <ShieldCheckIcon size={28} />
            </div>
            <div className="calc-placeholder-text">
              <h4>Ready to evaluate your scholarship</h4>
              <p>Enter your qualifying score and contact details above, then click <strong>Calculate Official Scholarship</strong> to see your exact payable fee and multi-year progression.</p>
            </div>
          </div>
        )}

        {/* Calculation Result Panel (ONLY shown when user explicitly calculated) */}
        {calculatedSnapshot && (
          <div className="calc-result-box">
            <div className="result-top-badge">
              <div className="award-badge">
                <AwardIcon size={18} />
                <span>{calculatedSnapshot.slab.scholarshipPercent}% Merit Scholarship Awarded</span>
              </div>
              <div className="exam-tag">
                Criteria: <strong>{calculatedSnapshot.exam.label}</strong> ({calculatedSnapshot.rangeText})
              </div>
            </div>

            {/* Verification confirmation */}
            <div className="calc-verified-banner">
              <CheckIcon size={14} />
              <span>Verified for <strong>{calculatedSnapshot.studentName}</strong> ({calculatedSnapshot.studentPhone})</span>
            </div>

            {/* Three-Column Financial Summary */}
            <div className="fee-comparison-row">
              <div className="fee-stat">
                <span className="stat-label">Standard Tuition</span>
                <span className="stat-val strikethrough">
                  ₹{calculatedSnapshot.program.baseTuitionSem.toLocaleString("en-IN")}
                </span>
                <span className="stat-sub">Per semester</span>
              </div>
              <div className="fee-stat highlight-green">
                <span className="stat-label">Scholarship Savings</span>
                <span className="stat-val savings">
                  -₹{calculatedSnapshot.discountAmount.toLocaleString("en-IN")}
                </span>
                <span className="stat-sub">{calculatedSnapshot.slab.scholarshipPercent}% tuition waiver</span>
              </div>
              <div className="fee-stat primary-payable">
                <span className="stat-label">You Pay Tuition</span>
                <span className="stat-val payable">
                  ₹{calculatedSnapshot.slab.payableFeeSem.toLocaleString("en-IN")}
                </span>
                <span className="stat-sub">Per semester</span>
              </div>
            </div>

            {/* 4-Year Semester Progression for B.Tech CSE */}
            {calculatedSnapshot.slab.cseYearlyPayable && (
              <div className="progression-table-wrap">
                <div className="progression-title">
                  <CalendarIcon size={14} />
                  <span>Semester-wise Progression Across 4 Years (CSE):</span>
                </div>
                <div className="progression-grid">
                  <div className="prog-col">
                    <span className="prog-yr">Year 1</span>
                    <span className="prog-val">₹{calculatedSnapshot.slab.cseYearlyPayable.yr1.toLocaleString("en-IN")}</span>
                    <span className="prog-unit">per sem</span>
                  </div>
                  <div className="prog-col">
                    <span className="prog-yr">Year 2</span>
                    <span className="prog-val">₹{calculatedSnapshot.slab.cseYearlyPayable.yr2.toLocaleString("en-IN")}</span>
                    <span className="prog-unit">per sem</span>
                  </div>
                  <div className="prog-col">
                    <span className="prog-yr">Year 3</span>
                    <span className="prog-val">₹{calculatedSnapshot.slab.cseYearlyPayable.yr3.toLocaleString("en-IN")}</span>
                    <span className="prog-unit">per sem</span>
                  </div>
                  <div className="prog-col">
                    <span className="prog-yr">Year 4</span>
                    <span className="prog-val">₹{calculatedSnapshot.slab.cseYearlyPayable.yr4.toLocaleString("en-IN")}</span>
                    <span className="prog-unit">per sem</span>
                  </div>
                </div>
              </div>
            )}

            {/* Institutional Notes Callout */}
            <div className="calc-notes">
              <div className="note-item">
                <PinIcon size={15} />
                <div>
                  <strong>One-Time Fees:</strong> Enrollment Fee ₹{calculatedSnapshot.program.enrollmentFee.toLocaleString("en-IN")} and Admission Fee ₹{calculatedSnapshot.program.admissionFee.toLocaleString("en-IN")} payable at joining.
                </div>
              </div>
              {calculatedSnapshot.program.specializationFeeAnnual && (
                <div className="note-item">
                  <FlaskIcon size={15} />
                  <div>
                    <strong>Specialization Fee:</strong> ₹{calculatedSnapshot.program.specializationFeeAnnual.toLocaleString("en-IN")}/year applicable from 2nd year onwards for advanced tech tracks.
                  </div>
                </div>
              )}
              <div className="note-item special-scholarship">
                <HeartHandIcon size={15} />
                <div>
                  <strong>Special 15% Waiver:</strong> Additional 15% scholarship available for students who lost their parents (Death certificate required; min 7.5 CGPA continuation).
                </div>
              </div>
            </div>

            {/* Footer Action */}
            <div className="calc-footer-actions">
              <button
                type="button"
                className="btn-ask-buddy"
                onClick={() => {
                  onClose();
                  onAskBuddy(
                    `I evaluated the scholarship for ${calculatedSnapshot.program.name} with ${calculatedSnapshot.exam.label} (${calculatedSnapshot.enteredScore || calculatedSnapshot.rangeText}) which pays ₹${calculatedSnapshot.slab.payableFeeSem.toLocaleString("en-IN")}/sem (${calculatedSnapshot.slab.scholarshipPercent}% waiver). Can you clarify admission verification and hostel accommodation options?`
                  );
                }}
              >
                <MessageSquareIcon size={16} />
                <span>Ask SRU Buddy About This Calculation</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
