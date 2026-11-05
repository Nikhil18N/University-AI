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
} from "./Icons";
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
      { scholarshipPercent: 20, ranges: { stateBoard: "60 – 69.99%", cbse: "60 – 64.99%", jeeMains: "75 – 85%", eamcet: "20001 – 25000", sat: "1151 – 1200", ib: "27 – 29" }, payableFeeSem: 96000 },
      { scholarshipPercent: 30, ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%", jeeMains: "85.1 – 90%", eamcet: "15001 – 20000", sat: "1201 – 1250", ib: "30 – 32" }, payableFeeSem: 84000 },
      { scholarshipPercent: 40, ranges: { stateBoard: "80 – 89.99%", cbse: "75 – 84.99%", jeeMains: "90.1 – 93%", eamcet: "10001 – 15000", sat: "1251 – 1300", ib: "33 – 35" }, payableFeeSem: 72000 },
      { scholarshipPercent: 50, ranges: { stateBoard: "90 – 94.99%", cbse: "85 – 89.99%", jeeMains: "93.1 – 95%", eamcet: "5001 – 10000", sat: "1301 – 1350", ib: "36 – 38" }, payableFeeSem: 60000 },
      { scholarshipPercent: 70, ranges: { stateBoard: "≥ 95%", cbse: "≥ 90%", jeeMains: "≥ 95.1%", eamcet: "1 – 5000", sat: "≥ 1351", ib: "≥ 39" }, payableFeeSem: 36000 },
    ],
  },
  {
    id: "btech_core",
    name: "B.Tech. Core Engineering (EEE / Mechanical / Civil)",
    degreeType: "Bachelors",
    baseTuitionSem: 100000,
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
      { scholarshipPercent: 20, ranges: { stateBoard: "60 – 69.99%", cbse: "60 – 64.99%", jeeMains: "75 – 85%", eamcet: "25001 – 30000", sat: "1151 – 1200", ib: "27 – 29" }, payableFeeSem: 80000 },
      { scholarshipPercent: 30, ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%", jeeMains: "85.1 – 90%", eamcet: "20001 – 25000", sat: "1201 – 1250", ib: "30 – 32" }, payableFeeSem: 70000 },
      { scholarshipPercent: 40, ranges: { stateBoard: "80 – 89.99%", cbse: "75 – 84.99%", jeeMains: "90.1 – 93%", eamcet: "15001 – 20000", sat: "1251 – 1300", ib: "33 – 35" }, payableFeeSem: 60000 },
      { scholarshipPercent: 50, ranges: { stateBoard: "90 – 94.99%", cbse: "85 – 89.99%", jeeMains: "93.1 – 95%", eamcet: "10001 – 15000", sat: "1301 – 1350", ib: "36 – 38" }, payableFeeSem: 50000 },
      { scholarshipPercent: 70, ranges: { stateBoard: "≥ 95%", cbse: "≥ 90%", jeeMains: "≥ 95.1%", eamcet: "1 – 10000", sat: "≥ 1351", ib: "≥ 39" }, payableFeeSem: 30000 },
    ],
  },
  {
    id: "bca",
    name: "BCA (Bachelor of Computer Applications)",
    degreeType: "Bachelors",
    baseTuitionSem: 60000,
    enrollmentFee: 5000,
    admissionFee: 10000,
    supportedExams: [
      { key: "stateBoard", label: "State Board (10+2) %" },
      { key: "cbse", label: "CBSE %" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { stateBoard: "60 – 69.99%", cbse: "60 – 64.99%" }, payableFeeSem: 54000 },
      { scholarshipPercent: 20, ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%" }, payableFeeSem: 48000 },
      { scholarshipPercent: 30, ranges: { stateBoard: "80 – 89.99%", cbse: "75 – 84.99%" }, payableFeeSem: 42000 },
      { scholarshipPercent: 40, ranges: { stateBoard: "90 – 94.99%", cbse: "85 – 89.99%" }, payableFeeSem: 36000 },
      { scholarshipPercent: 50, ranges: { stateBoard: "≥ 95%", cbse: "≥ 90%" }, payableFeeSem: 30000 },
    ],
  },
  {
    id: "bba",
    name: "BBA (Bachelor of Business Administration)",
    degreeType: "Bachelors",
    baseTuitionSem: 60000,
    enrollmentFee: 5000,
    admissionFee: 10000,
    supportedExams: [
      { key: "stateBoard", label: "State Board (10+2) %" },
      { key: "cbse", label: "CBSE %" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { stateBoard: "60 – 69.99%", cbse: "60 – 64.99%" }, payableFeeSem: 54000 },
      { scholarshipPercent: 20, ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%" }, payableFeeSem: 48000 },
      { scholarshipPercent: 30, ranges: { stateBoard: "80 – 89.99%", cbse: "75 – 84.99%" }, payableFeeSem: 42000 },
      { scholarshipPercent: 40, ranges: { stateBoard: "90 – 94.99%", cbse: "85 – 89.99%" }, payableFeeSem: 36000 },
      { scholarshipPercent: 50, ranges: { stateBoard: "≥ 95%", cbse: "≥ 90%" }, payableFeeSem: 30000 },
    ],
  },
  {
    id: "bsc_agri",
    name: "B.Sc. (Hons) Agriculture",
    degreeType: "Bachelors",
    baseTuitionSem: 100000,
    enrollmentFee: 5000,
    admissionFee: 10000,
    supportedExams: [
      { key: "stateBoard", label: "10+2 Inter BiPC %" },
      { key: "cbse", label: "CBSE %" },
      { key: "eamcet", label: "EAMCET Rank (Ag Stream)" },
      { key: "icar", label: "ICAR Percentile" },
    ],
    slabs: [
      { scholarshipPercent: 15, ranges: { stateBoard: "60 – 69.99%", cbse: "60 – 64.99%", eamcet: "15001 – 20000", icar: "75 – 80%" }, payableFeeSem: 85000 },
      { scholarshipPercent: 25, ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%", eamcet: "10001 – 15000", icar: "80.1 – 85%" }, payableFeeSem: 75000 },
      { scholarshipPercent: 35, ranges: { stateBoard: "80 – 89.99%", cbse: "75 – 84.99%", eamcet: "5001 – 10000", icar: "85.1 – 90%" }, payableFeeSem: 65000 },
      { scholarshipPercent: 50, ranges: { stateBoard: "≥ 90%", cbse: "≥ 85%", eamcet: "1 – 5000", icar: "≥ 90.1%" }, payableFeeSem: 50000 },
    ],
  },
  {
    id: "mba",
    name: "MBA (Master of Business Administration)",
    degreeType: "Masters",
    baseTuitionSem: 150000,
    enrollmentFee: 5000,
    admissionFee: 10000,
    supportedExams: [
      { key: "degree", label: "Graduation (Degree) %" },
      { key: "icet", label: "ICET Rank" },
      { key: "catMat", label: "CAT / MAT Percentile" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { degree: "60 – 69.99%", icet: "15001 – 20000", catMat: "70 – 75%" }, payableFeeSem: 135000 },
      { scholarshipPercent: 20, ranges: { degree: "70 – 79.99%", icet: "10001 – 15000", catMat: "75.1 – 80%" }, payableFeeSem: 120000 },
      { scholarshipPercent: 30, ranges: { degree: "80 – 89.99%", icet: "5001 – 10000", catMat: "80.1 – 85%" }, payableFeeSem: 105000 },
      { scholarshipPercent: 40, ranges: { degree: "90 – 94.99%", icet: "1001 – 5000", catMat: "85.1 – 90%" }, payableFeeSem: 90000 },
      { scholarshipPercent: 50, ranges: { degree: "≥ 95%", icet: "1 – 1000", catMat: "≥ 90.1%" }, payableFeeSem: 75000 },
    ],
  },
  {
    id: "mca",
    name: "MCA (Master of Computer Applications)",
    degreeType: "Masters",
    baseTuitionSem: 75000,
    enrollmentFee: 5000,
    admissionFee: 10000,
    supportedExams: [
      { key: "degree", label: "Graduation (BCA / B.Sc) %" },
      { key: "icet", label: "ICET Rank" },
    ],
    slabs: [
      { scholarshipPercent: 15, ranges: { degree: "60 – 69.99%", icet: "10001 – 15000" }, payableFeeSem: 63750 },
      { scholarshipPercent: 25, ranges: { degree: "70 – 79.99%", icet: "5001 – 10000" }, payableFeeSem: 56250 },
      { scholarshipPercent: 35, ranges: { degree: "80 – 89.99%", icet: "1001 – 5000" }, payableFeeSem: 48750 },
      { scholarshipPercent: 50, ranges: { degree: "≥ 90%", icet: "1 – 1000" }, payableFeeSem: 37500 },
    ],
  },
  {
    id: "mtech",
    name: "M.Tech (Engineering Post-Graduation)",
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

interface CalculatedSnapshot {
  program: ProgramConfig;
  exam: { key: string; label: string };
  slab: ScholarshipSlab;
  rangeText: string;
  discountAmount: number;
}

export default function ScholarshipCalculatorModal({ onClose, onAskBuddy }: Props) {
  // 1. Form interactive selection state
  const [selectedProgramId, setSelectedProgramId] = useState<string>("btech_cse");
  const [selectedExamKey, setSelectedExamKey] = useState<string>("stateBoard");
  const [selectedSlabIndex, setSelectedSlabIndex] = useState<number>(1);

  // 2. Calculated snapshot state: ONLY updated when user clicks Calculate
  const [calculatedSnapshot, setCalculatedSnapshot] = useState<CalculatedSnapshot | null>(null);
  const [isSelectionModified, setIsSelectionModified] = useState<boolean>(false);

  // Active program configuration for the form dropdowns
  const currentProgram = useMemo(
    () => PROGRAMS.find((p) => p.id === selectedProgramId) || PROGRAMS[0],
    [selectedProgramId]
  );

  const activeExams = currentProgram.supportedExams;
  const currentExam = useMemo(() => {
    return activeExams.find((e) => e.key === selectedExamKey) || activeExams[0];
  }, [activeExams, selectedExamKey]);

  // Handle Form Changes (Mark calculation as stale if results are already showing)
  const handleProgramChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newProgId = e.target.value;
    setSelectedProgramId(newProgId);
    setSelectedSlabIndex(0);
    const prog = PROGRAMS.find((p) => p.id === newProgId);
    if (prog && !prog.supportedExams.some((x) => x.key === selectedExamKey)) {
      setSelectedExamKey(prog.supportedExams[0].key);
    }
    if (calculatedSnapshot) setIsSelectionModified(true);
  };

  const handleExamChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedExamKey(e.target.value);
    setSelectedSlabIndex(0);
    if (calculatedSnapshot) setIsSelectionModified(true);
  };

  const handleSlabChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedSlabIndex(Number(e.target.value));
    if (calculatedSnapshot) setIsSelectionModified(true);
  };

  // ONLY calculate when user clicks the button
  const handleCalculate = (e: React.FormEvent) => {
    e.preventDefault();
    const prog = PROGRAMS.find((p) => p.id === selectedProgramId) || PROGRAMS[0];
    const exam = prog.supportedExams.find((x) => x.key === selectedExamKey) || prog.supportedExams[0];
    const slab = prog.slabs[selectedSlabIndex] || prog.slabs[0];
    const rangeText =
      (slab.ranges as any)[exam.key] ||
      slab.ranges.stateBoard ||
      `Slab ${selectedSlabIndex + 1}`;
    const discount = Math.round(
      prog.baseTuitionSem * (slab.scholarshipPercent / 100)
    );

    setCalculatedSnapshot({
      program: prog,
      exam,
      slab,
      rangeText,
      discountAmount: discount,
    });
    setIsSelectionModified(false);
  };

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
            {/* 1. Program Selection */}
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

            {/* 3. Score Range */}
            <div className="calc-field">
              <label htmlFor="calc-slab-select">3. Score / Rank Range</label>
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
            </div>
          </div>

          {/* Action Button */}
          <button type="submit" className="calc-submit-btn">
            <BoltIcon size={16} />
            <span>Calculate Scholarship</span>
          </button>
        </form>

        {/* Calculation Status Banner (if inputs changed post-calculation) */}
        {calculatedSnapshot && isSelectionModified && (
          <div className="calc-stale-banner">
            <RefreshIcon size={14} />
            <span>Parameters modified. Click <strong>Calculate Scholarship</strong> to update results.</span>
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
              <p>Select your program and qualifying examination score above, then click <strong>Calculate Scholarship</strong> to view your exact payable fee.</p>
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
                    `I evaluated the scholarship for ${calculatedSnapshot.program.name} with ${calculatedSnapshot.exam.label} (${calculatedSnapshot.rangeText}) which pays ₹${calculatedSnapshot.slab.payableFeeSem.toLocaleString("en-IN")}/sem (${calculatedSnapshot.slab.scholarshipPercent}% waiver). Can you clarify admission verification and hostel accommodation options?`
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
