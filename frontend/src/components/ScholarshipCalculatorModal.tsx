import React, { useState, useMemo } from "react";
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
        scholarshipPercent: 35,
        ranges: { stateBoard: "80 – 91.99%", cbse: "75 – 89.99%", jeeMains: "90.1 – 93%", eamcet: "12001 – 15000", sat: "1251 – 1350", ib: "33 – 35" },
        payableFeeSem: 96000,
        cseYearlyPayable: { yr1: 96000, yr2: 101000, yr3: 106000, yr4: 111000 },
      },
      {
        scholarshipPercent: 40,
        ranges: { stateBoard: "92 – 97.99%", cbse: "90 – 97.99%", jeeMains: "93.1 – 95%", eamcet: "10001 – 12000", sat: "1351 – 1450", ib: "36 – 38" },
        payableFeeSem: 89000,
        cseYearlyPayable: { yr1: 89000, yr2: 94000, yr3: 99000, yr4: 104000 },
      },
      {
        scholarshipPercent: 50,
        ranges: { stateBoard: "98% & Above", cbse: "98% & Above", jeeMains: "95% & Above", eamcet: "1 – 10000", sat: "1451 & Above", ib: "39 & Above" },
        payableFeeSem: 74000,
        cseYearlyPayable: { yr1: 74000, yr2: 78000, yr3: 82000, yr4: 86000 },
      },
    ],
  },
  {
    id: "btech_ece",
    name: "B.Tech. Electronics & Communication (ECE)",
    degreeType: "Bachelors",
    baseTuitionSem: 120000,
    enrollmentFee: 5000,
    admissionFee: 25000,
    specializationFeeAnnual: 30000,
    specializations: ["Artificial Intelligence & Machine Learning", "VLSI Design"],
    supportedExams: [
      { key: "stateBoard", label: "State Board (10+2 / Inter) %" },
      { key: "cbse", label: "CBSE %" },
      { key: "jeeMains", label: "JEE Mains %" },
      { key: "eamcet", label: "EAMCET / EAPCET Rank" },
      { key: "sat", label: "SAT Score" },
      { key: "ib", label: "IB Score" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { stateBoard: "60 – 69.99%", cbse: "60 – 64.99%", jeeMains: "60 – 69.99%", eamcet: "16001 – 18000", sat: "1151 – 1200", ib: "27 – 29" }, payableFeeSem: 108000 },
      { scholarshipPercent: 20, ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%", jeeMains: "70 – 74.99%", eamcet: "15001 – 16000", sat: "1201 – 1250", ib: "30 – 32" }, payableFeeSem: 96000 },
      { scholarshipPercent: 30, ranges: { stateBoard: "80 – 91.99%", cbse: "75 – 89.99%", jeeMains: "75 – 79.99%", eamcet: "12001 – 15000", sat: "1251 – 1350", ib: "33 – 35" }, payableFeeSem: 84000 },
      { scholarshipPercent: 40, ranges: { stateBoard: "92 – 97.99%", cbse: "90 – 97.99%", jeeMains: "80 – 89.99%", eamcet: "10001 – 12000", sat: "1351 – 1450", ib: "36 – 38" }, payableFeeSem: 72000 },
      { scholarshipPercent: 50, ranges: { stateBoard: "98% & Above", cbse: "98% & Above", jeeMains: "90% & Above", eamcet: "1 – 10000", sat: "1451 – 1600", ib: "39 Above" }, payableFeeSem: 60000 },
    ],
  },
  {
    id: "btech_core",
    name: "B.Tech. Core (EEE, Mechanical, Civil)",
    degreeType: "Bachelors",
    baseTuitionSem: 100000,
    enrollmentFee: 5000,
    admissionFee: 25000,
    specializationFeeAnnual: 30000,
    specializations: ["Renewable Energy", "Robotics & Automation", "Electric Vehicles", "Smart Manufacturing"],
    supportedExams: [
      { key: "stateBoard", label: "State Board (10+2 / Inter) %" },
      { key: "cbse", label: "CBSE %" },
      { key: "jeeMains", label: "JEE Mains %" },
      { key: "eamcet", label: "EAMCET / EAPCET Rank" },
      { key: "sat", label: "SAT Score" },
      { key: "ib", label: "IB Score" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { stateBoard: "60 – 69.99%", cbse: "60 – 64.99%", jeeMains: "60 – 69.99%", eamcet: "16001 – 18000", sat: "1151 – 1200", ib: "27 – 29" }, payableFeeSem: 90000 },
      { scholarshipPercent: 20, ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%", jeeMains: "70 – 74.99%", eamcet: "15001 – 16000", sat: "1201 – 1250", ib: "30 – 32" }, payableFeeSem: 80000 },
      { scholarshipPercent: 30, ranges: { stateBoard: "80 – 91.99%", cbse: "75 – 89.99%", jeeMains: "75 – 79.99%", eamcet: "12001 – 15000", sat: "1251 – 1350", ib: "33 – 35" }, payableFeeSem: 70000 },
      { scholarshipPercent: 40, ranges: { stateBoard: "92 – 97.99%", cbse: "90 – 97.99%", jeeMains: "80 – 89.99%", eamcet: "10001 – 12000", sat: "1351 – 1450", ib: "36 – 38" }, payableFeeSem: 60000 },
      { scholarshipPercent: 50, ranges: { stateBoard: "98% & Above", cbse: "98% & Above", jeeMains: "90% & Above", eamcet: "1 – 10000", sat: "1451 – 1600", ib: "39 Above" }, payableFeeSem: 50000 },
    ],
  },
  {
    id: "bca",
    name: "BCA (Bachelor of Computer Applications)",
    degreeType: "Bachelors",
    baseTuitionSem: 90000,
    enrollmentFee: 5000,
    admissionFee: 25000,
    supportedExams: [
      { key: "stateBoard", label: "State Board (10+2) %" },
      { key: "cbse", label: "CBSE %" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { stateBoard: "60 – 69.99%", cbse: "60 – 64.99%" }, payableFeeSem: 81000 },
      { scholarshipPercent: 20, ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%" }, payableFeeSem: 72000 },
      { scholarshipPercent: 30, ranges: { stateBoard: "80 – 91.99%", cbse: "75 – 89.99%" }, payableFeeSem: 63000 },
      { scholarshipPercent: 40, ranges: { stateBoard: "92 – 97.99%", cbse: "90 – 97.99%" }, payableFeeSem: 54000 },
      { scholarshipPercent: 50, ranges: { stateBoard: "98% & Above", cbse: "98% & Above" }, payableFeeSem: 45000 },
    ],
  },
  {
    id: "bba",
    name: "BBA (Bachelor of Business Administration)",
    degreeType: "Bachelors",
    baseTuitionSem: 90000,
    enrollmentFee: 5000,
    admissionFee: 25000,
    specializations: ["Finance", "Marketing", "HRM", "Business Analytics"],
    supportedExams: [
      { key: "stateBoard", label: "State Board (10+2) %" },
      { key: "cbse", label: "CBSE %" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { stateBoard: "60 – 69.99%", cbse: "60 – 64.99%" }, payableFeeSem: 81000 },
      { scholarshipPercent: 20, ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%" }, payableFeeSem: 72000 },
      { scholarshipPercent: 30, ranges: { stateBoard: "80 – 91.99%", cbse: "75 – 89.99%" }, payableFeeSem: 63000 },
      { scholarshipPercent: 40, ranges: { stateBoard: "92 – 97.99%", cbse: "90 – 97.99%" }, payableFeeSem: 54000 },
      { scholarshipPercent: 50, ranges: { stateBoard: "98% & Above", cbse: "98% & Above" }, payableFeeSem: 45000 },
    ],
  },
  {
    id: "mba",
    name: "MBA (Master of Business Administration)",
    degreeType: "Masters",
    baseTuitionSem: 150000,
    enrollmentFee: 5000,
    admissionFee: 25000,
    supportedExams: [
      { key: "degree", label: "Undergraduate Degree %" },
      { key: "icet", label: "TS / AP ICET Rank" },
      { key: "catMat", label: "MAT / XAT / NMAT / CAT %" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { degree: "60 – 69.99%", icet: "1751 – 2000", catMat: "60 – 69.99%" }, payableFeeSem: 135000 },
      { scholarshipPercent: 20, ranges: { degree: "70 – 79.99%", icet: "1501 – 1750", catMat: "70 – 74.99%" }, payableFeeSem: 120000 },
      { scholarshipPercent: 30, ranges: { degree: "80 – 91.99%", icet: "1201 – 1500", catMat: "75 – 89.99%" }, payableFeeSem: 105000 },
      { scholarshipPercent: 40, ranges: { degree: "92 – 97.99%", icet: "1001 – 1200", catMat: "90 – 97.99%" }, payableFeeSem: 90000 },
      { scholarshipPercent: 50, ranges: { degree: "98% & Above", icet: "1 – 1000", catMat: "98% & Above" }, payableFeeSem: 75000 },
    ],
  },
  {
    id: "mca",
    name: "MCA (Master of Computer Applications)",
    degreeType: "Masters",
    baseTuitionSem: 75000,
    enrollmentFee: 5000,
    admissionFee: 25000,
    supportedExams: [
      { key: "degree", label: "Graduation Degree %" },
      { key: "icet", label: "ICET Rank" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { degree: "60 – 69.99%", icet: "1751 – 2000" }, payableFeeSem: 68000 },
      { scholarshipPercent: 20, ranges: { degree: "70 – 79.99%", icet: "1501 – 1750" }, payableFeeSem: 60000 },
      { scholarshipPercent: 30, ranges: { degree: "80 – 91.99%", icet: "1201 – 1500" }, payableFeeSem: 53000 },
      { scholarshipPercent: 40, ranges: { degree: "92 – 97.99%", icet: "1001 – 1200" }, payableFeeSem: 45000 },
      { scholarshipPercent: 50, ranges: { degree: "98% & Above", icet: "1 – 1000" }, payableFeeSem: 38000 },
    ],
  },
  {
    id: "mtech",
    name: "M.Tech Programs",
    degreeType: "Masters",
    baseTuitionSem: 52250,
    enrollmentFee: 5000,
    admissionFee: 25000,
    supportedExams: [
      { key: "degree", label: "B.Tech / B.E. %" },
      { key: "gate", label: "GATE / PGECET Rank" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { degree: "60 – 69.99%", gate: "1751 – 2000" }, payableFeeSem: 47025 },
      { scholarshipPercent: 20, ranges: { degree: "70 – 79.99%", gate: "1501 – 1750" }, payableFeeSem: 41800 },
      { scholarshipPercent: 30, ranges: { degree: "80 – 91.99%", gate: "1201 – 1500" }, payableFeeSem: 36575 },
      { scholarshipPercent: 40, ranges: { degree: "92 – 97.99%", gate: "1001 – 1200" }, payableFeeSem: 31350 },
      { scholarshipPercent: 50, ranges: { degree: "98% & Above", gate: "1 – 1000" }, payableFeeSem: 26125 },
    ],
  },
];

export default function ScholarshipCalculatorModal({ onClose, onAskBuddy }: Props) {
  const [selectedProgramId, setSelectedProgramId] = useState<string>("btech_cse");
  const [selectedExamKey, setSelectedExamKey] = useState<string>("stateBoard");
  const [selectedSlabIndex, setSelectedSlabIndex] = useState<number>(1);
  const [hasCalculated, setHasCalculated] = useState<boolean>(true);

  const currentProgram = useMemo(
    () => PROGRAMS.find((p) => p.id === selectedProgramId) || PROGRAMS[0],
    [selectedProgramId]
  );

  // When program changes, reset exam key if unsupported
  const activeExams = currentProgram.supportedExams;
  const currentExam = useMemo(() => {
    return activeExams.find((e) => e.key === selectedExamKey) || activeExams[0];
  }, [activeExams, selectedExamKey]);

  const currentSlab = currentProgram.slabs[selectedSlabIndex] || currentProgram.slabs[0];

  const handleProgramChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newProgId = e.target.value;
    setSelectedProgramId(newProgId);
    const prog = PROGRAMS.find((p) => p.id === newProgId);
    if (prog && !prog.supportedExams.some((x) => x.key === selectedExamKey)) {
      setSelectedExamKey(prog.supportedExams[0].key);
    }
  };

  const handleCalculate = (e: React.FormEvent) => {
    e.preventDefault();
    setHasCalculated(true);
  };

  const discountAmount = Math.round(
    currentProgram.baseTuitionSem * (currentSlab.scholarshipPercent / 100)
  );

  return (
    <div className="scholarship-modal-backdrop" onClick={onClose}>
      <div className="scholarship-modal-card" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="calc-header">
          <div className="calc-title-group">
            <span className="calc-icon">🧮</span>
            <div>
              <h3>Fee & Scholarship Calculator</h3>
              <p className="calc-subtitle">Unlock your scholarship potential & view exact payable fees</p>
            </div>
          </div>
          <button className="calc-close-btn" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        {/* Form Controls */}
        <form onSubmit={handleCalculate} className="calc-form">
          <div className="calc-grid-controls">
            {/* 1. Program */}
            <div className="calc-field">
              <label>1. Choose Program</label>
              <select value={selectedProgramId} onChange={handleProgramChange}>
                <optgroup label="Bachelors Programs">
                  {PROGRAMS.filter((p) => p.degreeType === "Bachelors").map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </optgroup>
                <optgroup label="Masters Programs">
                  {PROGRAMS.filter((p) => p.degreeType === "Masters").map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>

            {/* 2. Qualifying Exam / Board */}
            <div className="calc-field">
              <label>2. Exam / Qualifying Board</label>
              <select
                value={currentExam.key}
                onChange={(e) => setSelectedExamKey(e.target.value)}
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
              <label>3. Your Score / Rank Range</label>
              <select
                value={selectedSlabIndex}
                onChange={(e) => setSelectedSlabIndex(Number(e.target.value))}
              >
                {currentProgram.slabs.map((slab, idx) => {
                  const rangeText =
                    (slab.ranges as any)[currentExam.key] ||
                    slab.ranges.stateBoard ||
                    `Slab ${idx + 1}`;
                  return (
                    <option key={idx} value={idx}>
                      {rangeText} → {slab.scholarshipPercent}% Scholarship
                    </option>
                  );
                })}
              </select>
            </div>
          </div>

          <button type="submit" className="calc-submit-btn">
            ⚡ CALCULATE SCHOLARSHIP
          </button>
        </form>

        {/* Calculation Result */}
        {hasCalculated && (
          <div className="calc-result-box">
            <div className="result-top-badge">
              <span className="award-badge">🎉 {currentSlab.scholarshipPercent}% Tuition Scholarship Awarded</span>
              <span className="exam-tag">
                Grounded on: {currentExam.label} ({(currentSlab.ranges as any)[currentExam.key]})
              </span>
            </div>

            <div className="fee-comparison-row">
              <div className="fee-stat">
                <span className="stat-label">Standard Tuition (Per Sem)</span>
                <span className="stat-val strikethrough">
                  ₹{currentProgram.baseTuitionSem.toLocaleString("en-IN")}
                </span>
              </div>
              <div className="fee-stat highlight-green">
                <span className="stat-label">You Save Per Semester</span>
                <span className="stat-val savings">
                  -₹{discountAmount.toLocaleString("en-IN")} ({currentSlab.scholarshipPercent}%)
                </span>
              </div>
              <div className="fee-stat primary-payable">
                <span className="stat-label">You Pay Per Semester</span>
                <span className="stat-val payable">
                  ₹{currentSlab.payableFeeSem.toLocaleString("en-IN")}
                </span>
              </div>
            </div>

            {/* B.Tech CSE Progression Table if applicable */}
            {currentSlab.cseYearlyPayable && (
              <div className="progression-table-wrap">
                <div className="progression-title">📅 Semester-wise Progression across 4 Years (CSE):</div>
                <div className="progression-grid">
                  <div className="prog-col">
                    <span className="prog-yr">Year 1</span>
                    <span className="prog-val">₹{currentSlab.cseYearlyPayable.yr1.toLocaleString("en-IN")}/sem</span>
                  </div>
                  <div className="prog-col">
                    <span className="prog-yr">Year 2</span>
                    <span className="prog-val">₹{currentSlab.cseYearlyPayable.yr2.toLocaleString("en-IN")}/sem</span>
                  </div>
                  <div className="prog-col">
                    <span className="prog-yr">Year 3</span>
                    <span className="prog-val">₹{currentSlab.cseYearlyPayable.yr3.toLocaleString("en-IN")}/sem</span>
                  </div>
                  <div className="prog-col">
                    <span className="prog-yr">Year 4</span>
                    <span className="prog-val">₹{currentSlab.cseYearlyPayable.yr4.toLocaleString("en-IN")}/sem</span>
                  </div>
                </div>
              </div>
            )}

            {/* Additional info badges */}
            <div className="calc-notes">
              <div className="note-item">
                📌 <strong>One-time Fees:</strong> Enrollment ₹{currentProgram.enrollmentFee.toLocaleString("en-IN")} + Admission ₹{currentProgram.admissionFee.toLocaleString("en-IN")}.
              </div>
              {currentProgram.specializationFeeAnnual && (
                <div className="note-item">
                  🔬 <strong>Specialization Fee:</strong> ₹{currentProgram.specializationFeeAnnual.toLocaleString("en-IN")}/year (applicable from 2nd year onwards).
                </div>
              )}
              <div className="note-item special-scholarship">
                ❤️ <strong>Special Scholarship (15%):</strong> Additional 15% waiver available for students who lost their parents (Death certificate required; min 7.5 CGPA continuation).
              </div>
            </div>

            {/* Footer action */}
            <div className="calc-footer-actions">
              <button
                type="button"
                className="btn-ask-buddy"
                onClick={() => {
                  onClose();
                  onAskBuddy(
                    `I checked the scholarship for ${currentProgram.name} with ${currentExam.label} (${(currentSlab.ranges as any)[currentExam.key]}). Can you confirm my admission procedure and hostel fee options?`
                  );
                }}
              >
                💬 Ask SRU Buddy About This Calculation
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
