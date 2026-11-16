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
  CheckIcon,
  InfoIcon,
} from "./Icons";
import { createLead, calculateAgentFee } from "../services/api";
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
  annualIncrease?: number;
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
    name: "B.Tech. Computer Science & Engineering (CSE & Allied)",
    degreeType: "Bachelors",
    baseTuitionSem: 170000,
    annualIncrease: 9000,
    enrollmentFee: 5000,
    admissionFee: 0,
    specializationFeeAnnual: 30000,
    specializations: ["Artificial Intelligence & Machine Learning", "Cyber Security", "Data Science", "Robotics and Automation", "Quantum AI"],
    supportedExams: [
      { key: "stateBoard", label: "State Board (10+2 / Inter) %" },
      { key: "cbse", label: "CBSE / ICSE %" },
      { key: "jeeMains", label: "JEE Mains Percentile" },
      { key: "eamcet", label: "TG/AP EAPCET Rank" },
      { key: "ib", label: "IB Diploma Score" },
    ],
    slabs: [
      {
        scholarshipPercent: 10,
        ranges: { stateBoard: "60 – 64.9%", cbse: "60 – 64.9%", jeeMains: "50 – 59.9 %ile", eamcet: "40001 – 60000" },
        payableFeeSem: 153000,
        cseYearlyPayable: { yr1: 306000, yr2: 315000, yr3: 324000, yr4: 333000 },
      },
      {
        scholarshipPercent: 15,
        ranges: { stateBoard: "65 – 69.9%", cbse: "65 – 69.9%", jeeMains: "60 – 69.9 %ile", eamcet: "20001 – 40000" },
        payableFeeSem: 144500,
        cseYearlyPayable: { yr1: 289000, yr2: 298000, yr3: 307000, yr4: 316000 },
      },
      {
        scholarshipPercent: 20,
        ranges: { stateBoard: "70 – 79.9%", cbse: "70 – 79.9%", ib: "24 – 29", jeeMains: "70 – 79.9 %ile" },
        payableFeeSem: 136000,
        cseYearlyPayable: { yr1: 272000, yr2: 281000, yr3: 290000, yr4: 299000 },
      },
      {
        scholarshipPercent: 25,
        ranges: { stateBoard: "80 – 91.9%", cbse: "80 – 89.9%", ib: "30 – 33", jeeMains: "80 – 89.9 %ile", eamcet: "8001 – 20000" },
        payableFeeSem: 127500,
        cseYearlyPayable: { yr1: 255000, yr2: 264000, yr3: 273000, yr4: 282000 },
      },
      {
        scholarshipPercent: 30,
        ranges: { stateBoard: "92 – 97.9%", cbse: "90 – 94.9%", ib: "34 – 37", jeeMains: "90 – 94.99 %ile" },
        payableFeeSem: 119000,
        cseYearlyPayable: { yr1: 238000, yr2: 247000, yr3: 256000, yr4: 265000 },
      },
      {
        scholarshipPercent: 40,
        ranges: { stateBoard: "98% and above", cbse: "95% and above", ib: "35/45 and above", jeeMains: "95% and above", eamcet: "1 – 8000" },
        payableFeeSem: 102000,
        cseYearlyPayable: { yr1: 204000, yr2: 213000, yr3: 222000, yr4: 231000 },
      },
    ],
  },
  {
    id: "btech_ece",
    name: "B.Tech. Electronics & Communication Engineering (ECE)",
    degreeType: "Bachelors",
    baseTuitionSem: 135000,
    annualIncrease: 8000,
    enrollmentFee: 5000,
    admissionFee: 0,
    specializations: ["AIML", "VLSI Design", "Robotics and Automation"],
    supportedExams: [
      { key: "stateBoard", label: "State Board (10+2 / Inter) %" },
      { key: "cbse", label: "CBSE / ICSE %" },
      { key: "jeeMains", label: "JEE Mains Percentile" },
      { key: "eamcet", label: "TG/AP EAPCET Rank" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { stateBoard: "60 – 64.9%", cbse: "60 – 64.9%", jeeMains: "50 – 59.9 %ile", eamcet: "40001 – 60000" }, payableFeeSem: 121500 },
      { scholarshipPercent: 15, ranges: { stateBoard: "65 – 69.9%", cbse: "65 – 69.9%", jeeMains: "60 – 69.9 %ile", eamcet: "20001 – 40000" }, payableFeeSem: 114750 },
      { scholarshipPercent: 20, ranges: { stateBoard: "70 – 79.9%", cbse: "70 – 79.9%", jeeMains: "70 – 79.9 %ile" }, payableFeeSem: 108000 },
      { scholarshipPercent: 25, ranges: { stateBoard: "80 – 91.9%", cbse: "80 – 89.9%", jeeMains: "80 – 89.9 %ile", eamcet: "8001 – 20000" }, payableFeeSem: 101250 },
      { scholarshipPercent: 30, ranges: { stateBoard: "92 – 97.9%", cbse: "90 – 94.9%", jeeMains: "90 – 94.99 %ile" }, payableFeeSem: 94500 },
      { scholarshipPercent: 40, ranges: { stateBoard: "98% and above", cbse: "95% and above", jeeMains: "95% and above", eamcet: "1 – 8000" }, payableFeeSem: 81000 },
    ],
  },
  {
    id: "btech_core",
    name: "B.Tech. Core (Biotech / Mech / Civil / EEE / Food Tech)",
    degreeType: "Bachelors",
    baseTuitionSem: 100000,
    annualIncrease: 6000,
    enrollmentFee: 5000,
    admissionFee: 0,
    specializations: ["Biotechnology with AI", "Robotics and Automation", "Smart Manufacturing", "Electric Vehicles", "Renewable Energy"],
    supportedExams: [
      { key: "stateBoard", label: "State Board (10+2 / Inter) %" },
      { key: "cbse", label: "CBSE / ICSE %" },
      { key: "jeeMains", label: "JEE Mains Percentile" },
      { key: "eamcet", label: "TG/AP EAPCET Rank" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { stateBoard: "60 – 64.9%", cbse: "60 – 64.9%", jeeMains: "50 – 59.9 %ile", eamcet: "40001 – 60000" }, payableFeeSem: 90000 },
      { scholarshipPercent: 15, ranges: { stateBoard: "65 – 69.9%", cbse: "65 – 69.9%", jeeMains: "60 – 69.9 %ile", eamcet: "20001 – 40000" }, payableFeeSem: 85000 },
      { scholarshipPercent: 20, ranges: { stateBoard: "70 – 79.9%", cbse: "70 – 79.9%", jeeMains: "70 – 79.9 %ile" }, payableFeeSem: 80000 },
      { scholarshipPercent: 25, ranges: { stateBoard: "80 – 91.9%", cbse: "80 – 89.9%", jeeMains: "80 – 89.9 %ile", eamcet: "8001 – 20000" }, payableFeeSem: 75000 },
      { scholarshipPercent: 30, ranges: { stateBoard: "92 – 97.9%", cbse: "90 – 94.9%", jeeMains: "90 – 94.99 %ile" }, payableFeeSem: 70000 },
      { scholarshipPercent: 40, ranges: { stateBoard: "98% and above", cbse: "95% and above", jeeMains: "95% and above", eamcet: "1 – 8000" }, payableFeeSem: 60000 },
    ],
  },
  {
    id: "bca",
    name: "BCA (Bachelor of Computer Applications)",
    degreeType: "Bachelors",
    baseTuitionSem: 75000,
    annualIncrease: 4000,
    enrollmentFee: 5000,
    admissionFee: 0,
    supportedExams: [
      { key: "stateBoard", label: "State Board (10+2 / Inter) %" },
      { key: "cbse", label: "CBSE / ICSE %" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { stateBoard: "60 – 64.9%", cbse: "60 – 64.9%" }, payableFeeSem: 67500 },
      { scholarshipPercent: 15, ranges: { stateBoard: "65 – 69.9%", cbse: "65 – 69.9%" }, payableFeeSem: 63750 },
      { scholarshipPercent: 20, ranges: { stateBoard: "70 – 79.9%", cbse: "70 – 79.9%" }, payableFeeSem: 60000 },
      { scholarshipPercent: 25, ranges: { stateBoard: "80 – 91.9%", cbse: "80 – 89.9%" }, payableFeeSem: 56250 },
      { scholarshipPercent: 30, ranges: { stateBoard: "92 – 97.9%", cbse: "90 – 94.9%" }, payableFeeSem: 52500 },
      { scholarshipPercent: 40, ranges: { stateBoard: "98% and above", cbse: "95% and above" }, payableFeeSem: 45000 },
    ],
  },
  {
    id: "bba",
    name: "BBA (Bachelor of Business Administration)",
    degreeType: "Bachelors",
    baseTuitionSem: 75000,
    annualIncrease: 4000,
    enrollmentFee: 5000,
    admissionFee: 0,
    supportedExams: [
      { key: "stateBoard", label: "State Board (10+2 / Inter) %" },
      { key: "cbse", label: "CBSE / ICSE %" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { stateBoard: "60 – 64.9%", cbse: "60 – 64.9%" }, payableFeeSem: 67500 },
      { scholarshipPercent: 15, ranges: { stateBoard: "65 – 69.9%", cbse: "65 – 69.9%" }, payableFeeSem: 63750 },
      { scholarshipPercent: 20, ranges: { stateBoard: "70 – 79.9%", cbse: "70 – 79.9%" }, payableFeeSem: 60000 },
      { scholarshipPercent: 25, ranges: { stateBoard: "80 – 91.9%", cbse: "80 – 89.9%" }, payableFeeSem: 56250 },
      { scholarshipPercent: 30, ranges: { stateBoard: "92 – 97.9%", cbse: "90 – 94.9%" }, payableFeeSem: 52500 },
      { scholarshipPercent: 40, ranges: { stateBoard: "98% and above", cbse: "95% and above" }, payableFeeSem: 45000 },
    ],
  },
  {
    id: "mba",
    name: "MBA (Master of Business Administration)",
    degreeType: "Masters",
    baseTuitionSem: 150000,
    annualIncrease: 9000,
    enrollmentFee: 5000,
    admissionFee: 0,
    supportedExams: [
      { key: "degree", label: "Qualifying Degree %" },
      { key: "catMat", label: "MAT / CAT / CMAT %" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { degree: "60 – 64.9%", catMat: "60 – 64.9%" }, payableFeeSem: 135000 },
      { scholarshipPercent: 15, ranges: { degree: "65 – 69.9%", catMat: "65 – 69.9%" }, payableFeeSem: 127500 },
      { scholarshipPercent: 20, ranges: { degree: "70 – 79.9%", catMat: "70 – 79.9%" }, payableFeeSem: 120000 },
      { scholarshipPercent: 25, ranges: { degree: "80 – 91.9%", catMat: "80 – 91.9%" }, payableFeeSem: 112500 },
      { scholarshipPercent: 30, ranges: { degree: "92 – 97.9%", catMat: "92 – 97.9%" }, payableFeeSem: 105000 },
      { scholarshipPercent: 40, ranges: { degree: "98% and above", catMat: "98% and above" }, payableFeeSem: 90000 },
    ],
  },
  {
    id: "mca",
    name: "MCA (Master of Computer Applications)",
    degreeType: "Masters",
    baseTuitionSem: 75000,
    annualIncrease: 4000,
    enrollmentFee: 5000,
    admissionFee: 0,
    supportedExams: [
      { key: "degree", label: "Qualifying Degree %" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { degree: "60 – 64.9%" }, payableFeeSem: 67500 },
      { scholarshipPercent: 15, ranges: { degree: "65 – 69.9%" }, payableFeeSem: 63750 },
      { scholarshipPercent: 20, ranges: { degree: "70 – 79.9%" }, payableFeeSem: 60000 },
      { scholarshipPercent: 25, ranges: { degree: "80 – 91.9%" }, payableFeeSem: 56250 },
      { scholarshipPercent: 30, ranges: { degree: "92 – 97.9%" }, payableFeeSem: 52500 },
      { scholarshipPercent: 40, ranges: { degree: "98% and above" }, payableFeeSem: 45000 },
    ],
  },
];


/**
 * Helper to determine if an exam key is evaluated as a percentage or marks out of 1000.
 */
function isPercentageBoard(key: string): boolean {
  return key === "stateBoard" || key === "cbse" || key === "degree" || key === "ib" || key === "jeeMains";
}

/**
 * Parses user input to auto-detect intended qualifying exam boards and detect ranks.
 */
function detectBoardFromInput(text: string): {
  detectedExamKey?: "eamcet" | "jeeMains" | "cbse";
  cleanedNumberStr: string;
  isBareNumberGreaterThan1000: boolean;
  numericVal: number | null;
} {
  const trimmed = text.trim();
  const lower = trimmed.toLowerCase();

  let detectedExamKey: "eamcet" | "jeeMains" | "cbse" | undefined;
  if (/eapcet|eamcet|rank/i.test(lower)) {
    detectedExamKey = "eamcet";
  } else if (/jee|percentile|%ile/i.test(lower)) {
    detectedExamKey = "jeeMains";
  } else if (/cbse|icse/i.test(lower)) {
    detectedExamKey = "cbse";
  }

  const numMatch = trimmed.replace(/,/g, "").match(/(\d+(?:\.\d+)?)/);
  const numericVal = numMatch ? parseFloat(numMatch[1]) : null;
  const isFraction = trimmed.includes("/");
  const isBareNumberGreaterThan1000 = !detectedExamKey && !isFraction && numericVal !== null && numericVal > 1000;

  const cleanedNumberStr = numericVal !== null ? String(numericVal) : trimmed;

  return {
    detectedExamKey,
    cleanedNumberStr,
    isBareNumberGreaterThan1000,
    numericVal,
  };
}

/**
 * Intelligent parser & matcher for student scores and ranks.
 */
function matchSlabFromScore(
  program: ProgramConfig,
  examKey: string,
  rawScoreInput: string
): {
  slabIndex: number;
  percentage?: number;
  rank?: number;
  displayText: string;
  status: "matched" | "below_criteria" | "invalid";
} {
  const trimmed = rawScoreInput.trim();
  if (!trimmed) {
    return { slabIndex: -1, displayText: "", status: "invalid" };
  }

  const slabs = program.slabs;

  // 1. Rank-based exams (EAMCET / EAPCET, ICET, etc.)
  if (examKey === "eamcet" || examKey === "icet" || /rank/i.test(trimmed)) {
    const cleanNum = trimmed.replace(/[^\d]/g, "");
    const rank = parseInt(cleanNum, 10);
    if (isNaN(rank) || rank <= 0) {
      return { slabIndex: -1, displayText: "Please enter a valid rank number", status: "invalid" };
    }

    const displayText = `Rank ${rank.toLocaleString("en-IN")}`;

    for (let i = slabs.length - 1; i >= 0; i--) {
      const slab = slabs[i];
      const rangeStr = (slab.ranges as any)[examKey] || (slab.ranges as any).eamcet || "";
      if (!rangeStr) continue;

      const match = rangeStr.match(/(\d+)\s*[–-]\s*(\d+)/);
      if (match) {
        const low = parseInt(match[1], 10);
        const high = parseInt(match[2], 10);
        if (rank >= low && rank <= high) {
          return { slabIndex: i, rank, displayText, status: "matched" };
        }
      }
    }

    return {
      slabIndex: -1,
      rank,
      displayText: `${displayText} (Beyond Top Rank Slabs)`,
      status: "below_criteria",
    };
  }

  // 2. SAT Score
  if (examKey === "sat" || (/^\d{3,4}$/.test(trimmed) && parseInt(trimmed, 10) > 1000 && parseInt(trimmed, 10) <= 1600 && examKey === "sat")) {
    const cleanNum = trimmed.replace(/[^\d]/g, "");
    const satScore = parseInt(cleanNum, 10);
    if (!isNaN(satScore) && satScore >= 1000 && satScore <= 1600) {
      const displayText = `SAT Score ${satScore}`;
      for (let i = slabs.length - 1; i >= 0; i--) {
        const slab = slabs[i];
        const rangeStr = slab.ranges.sat || "";
        const match = rangeStr.match(/(\d+)\s*[–-]\s*(\d+)/);
        if (match) {
          const low = parseInt(match[1], 10);
          const high = parseInt(match[2], 10);
          if (satScore >= low && satScore <= high) {
            return { slabIndex: i, displayText, status: "matched" };
          }
        }
      }
      return { slabIndex: -1, displayText: `${displayText} (Below SAT Cutoff)`, status: "below_criteria" };
    }
  }

  // 3. Percentage or Raw Marks
  const fractionMatch = trimmed.match(/^(\d+(?:\.\d+)?)\s*[/]\s*(\d+(?:\.\d+)?)$/);
  let obtainedNum = 0;
  let totalMax = 0;

  if (fractionMatch) {
    obtainedNum = parseFloat(fractionMatch[1]);
    totalMax = parseFloat(fractionMatch[2]);
  } else {
    const numMatch = trimmed.match(/^(\d+(?:\.\d+)?)/);
    if (!numMatch) {
      return { slabIndex: -1, displayText: "Enter valid score/percentage", status: "invalid" };
    }
    obtainedNum = parseFloat(numMatch[1]);
  }

  let percentage: number;
  let displayText: string;

  if (totalMax > 0) {
    percentage = Math.round((obtainedNum / totalMax) * 10000) / 100;
    displayText = `${obtainedNum}/${totalMax} (${percentage}%)`;
  } else if (obtainedNum > 100) {
    // Intermediate marks out of 1000! (Telangana / AP state boards: 780 marks -> 78.0%)
    if (examKey === "cbse" && obtainedNum <= 500) {
      percentage = Math.round((obtainedNum / 500) * 10000) / 100;
      displayText = `${obtainedNum}/500 (${percentage}%)`;
    } else if (obtainedNum <= 1000) {
      percentage = Math.round((obtainedNum / 10) * 100) / 100;
      displayText = `${obtainedNum}/1000 (${percentage}%)`;
    } else {
      return {
        slabIndex: -1,
        displayText: `${obtainedNum} (Invalid mark range)`,
        status: "invalid",
      };
    }
  } else {
    percentage = Math.round(obtainedNum * 100) / 100;
    displayText = `${percentage}%`;
  }

  // Match normalized percentage against slabs
  for (let i = slabs.length - 1; i >= 0; i--) {
    const slab = slabs[i];
    const rangeStr = (slab.ranges as any)[examKey] || slab.ranges.stateBoard || "";

    if (rangeStr.includes("≥") || rangeStr.includes(">=") || rangeStr.includes(">") || rangeStr.includes("and above")) {
      const minVal = parseFloat(rangeStr.replace(/[^\d.]/g, ""));
      if (!isNaN(minVal) && percentage >= minVal) {
        return { slabIndex: i, percentage, displayText, status: "matched" };
      }
    }

    const match = rangeStr.match(/(\d+(?:\.\d+)?)\s*[–-]\s*(\d+(?:\.\d+)?)/);
    if (match) {
      const low = parseFloat(match[1]);
      const high = parseFloat(match[2]);
      if (percentage >= low && percentage <= high) {
        return { slabIndex: i, percentage, displayText, status: "matched" };
      }
    }
  }

  return {
    slabIndex: -1,
    percentage,
    displayText: `${displayText} (Below Cutoff)`,
    status: "below_criteria",
  };
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
  // Pre-load saved lead info if student already verified previously
  const savedLead = useMemo(() => {
    try {
      const raw = localStorage.getItem("sru_student_lead");
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      const digits = (parsed?.phone || "").replace(/\D/g, "");
      if (digits.length >= 10 && Boolean(parsed?.name)) {
        return { name: parsed.name.trim(), phone: parsed.phone.trim() };
      }
      return null;
    } catch {
      return null;
    }
  }, []);

  const [isVerified, setIsVerified] = useState<boolean>(Boolean(savedLead?.name && savedLead?.phone));

  // Form state - start without hardcoded marks so user sees real input state
  const [selectedProgramId, setSelectedProgramId] = useState<string>("btech_cse");
  const [selectedExamKey, setSelectedExamKey] = useState<string>("stateBoard");
  const [enteredScore, setEnteredScore] = useState<string>("");
  const [selectedSlabIndex, setSelectedSlabIndex] = useState<number>(-1);
  const [showSlabsPreview, setShowSlabsPreview] = useState<boolean>(false);
  const [includeHostel, setIncludeHostel] = useState<boolean>(false);
  const [hostelType, setHostelType] = useState<"non_ac" | "ac">("non_ac");

  // Optional admissions callback / lead inputs
  const [studentName, setStudentName] = useState<string>(savedLead?.name || "");
  const [studentPhone, setStudentPhone] = useState<string>(savedLead?.phone || "");
  const [consentAgreed, setConsentAgreed] = useState<boolean>(true);
  const [leadSuccessMsg, setLeadSuccessMsg] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Calculated snapshot state
  const [calculatedSnapshot, setCalculatedSnapshot] = useState<CalculatedSnapshot | null>(null);
  const [rankSuggestion, setRankSuggestion] = useState<number | null>(null);

  // Active program & exam
  const currentProgram = useMemo(
    () => PROGRAMS.find((p) => p.id === selectedProgramId) || PROGRAMS[0],
    [selectedProgramId]
  );

  const activeExams = currentProgram.supportedExams;
  const currentExam = useMemo(() => {
    return activeExams.find((e) => e.key === selectedExamKey) || activeExams[0];
  }, [activeExams, selectedExamKey]);

  // Compute current score match
  const scoreMatch = useMemo(() => {
    if (rankSuggestion !== null) {
      return { slabIndex: -1, displayText: "", status: "invalid" as const };
    }
    return matchSlabFromScore(currentProgram, currentExam.key, enteredScore);
  }, [currentProgram, currentExam.key, enteredScore, rankSuggestion]);

  // Execute calculation snapshot (clears previous snapshot and queries backend for official figures)
  const computeAndSaveSnapshot = async (
    prog: ProgramConfig,
    exam: { key: string; label: string },
    scoreInput: string,
    slabIdx: number,
    nameToUse: string = "",
    phoneToUse: string = ""
  ) => {
    // Clear every previous result snapshot before showing new result
    setCalculatedSnapshot(null);

    const match = matchSlabFromScore(prog, exam.key, scoreInput);
    const effectiveSlabIdx = match.slabIndex >= 0 ? match.slabIndex : slabIdx;
    const isNoScholarship = effectiveSlabIdx === -1;
    const slab: ScholarshipSlab = isNoScholarship
      ? {
          scholarshipPercent: 0,
          payableFeeSem: prog.baseTuitionSem,
          ranges: { [exam.key]: scoreInput.trim() ? "Standard Tuition (Below 60% Merit Cutoff)" : "Standard Base Tuition" },
          cseYearlyPayable:
            prog.id === "btech_cse"
              ? { yr1: 340000, yr2: 349000, yr3: 358000, yr4: 367000 }
              : undefined,
        }
      : prog.slabs[effectiveSlabIdx] || prog.slabs[0];

    const rangeText = isNoScholarship
      ? (scoreInput.trim() ? "Standard Tuition (Below 60% Merit Cutoff)" : "Standard Base Tuition")
      : (slab.ranges as any)[exam.key] ||
        slab.ranges.stateBoard ||
        `Slab ${effectiveSlabIdx + 1}`;

    const discount = isNoScholarship
      ? 0
      : Math.round(prog.baseTuitionSem * (slab.scholarshipPercent / 100));

    const finalScoreDisplay = match.displayText || scoreInput.trim() || rangeText;

    // Save lead in localStorage and PostgreSQL backend if valid contact provided
    if (nameToUse && phoneToUse && phoneToUse.replace(/\D/g, "").length >= 10) {
      const leadData = {
        name: nameToUse,
        phone: phoneToUse,
        program_interest: prog.name,
        score: finalScoreDisplay,
        exam_type: exam.label,
        source: "scholarship_calculator",
        metadata: {
          calculated_discount: discount,
          scholarship_percent: slab.scholarshipPercent,
          payable_sem: slab.payableFeeSem,
          admission_year: "2027-28",
        },
      };
      try {
        localStorage.setItem("sru_student_lead", JSON.stringify({ name: nameToUse, phone: phoneToUse }));
        setIsVerified(true);
        await createLead(leadData);
      } catch (err) {
        console.warn("Lead registration note:", err);
      }
    }

    // Query backend calculate endpoint to ensure 100% agreement with the AI agent
    try {
      const hostelParam = includeHostel ? (hostelType === "ac" ? "ac_4" : "non_ac_4") : "none";
      const backendCalc = await calculateAgentFee({
        program: prog.id,
        percent: match.percentage !== undefined ? match.percentage : undefined,
        board: exam.key === "cbse" ? "cbse" : "state_board",
        eapcet_rank: match.rank || (exam.key === "eamcet" && match.percentage ? Math.round(match.percentage) : undefined),
        jee_percentile: exam.key === "jeeMains" && match.percentage !== undefined ? match.percentage : undefined,
        hostel: hostelParam,
      });

      if (backendCalc && backendCalc.status === "ok") {
        const netSem = parseInt(backendCalc.per_semester_after_scholarship.replace(/[^\d]/g, ""), 10) || slab.payableFeeSem;
        const discountAmt = Math.round(parseInt(backendCalc.saving_first_year.replace(/[^\d]/g, ""), 10) / 2) || discount;
        const backendSlab: ScholarshipSlab = {
          ...slab,
          scholarshipPercent: backendCalc.scholarship_percent,
          payableFeeSem: netSem,
          cseYearlyPayable: backendCalc.year_by_year?.length === 4
            ? {
                yr1: parseInt(backendCalc.year_by_year[0].after_scholarship.replace(/[^\d]/g, ""), 10),
                yr2: parseInt(backendCalc.year_by_year[1].after_scholarship.replace(/[^\d]/g, ""), 10),
                yr3: parseInt(backendCalc.year_by_year[2].after_scholarship.replace(/[^\d]/g, ""), 10),
                yr4: parseInt(backendCalc.year_by_year[3].after_scholarship.replace(/[^\d]/g, ""), 10),
              }
            : slab.cseYearlyPayable,
        };
        setCalculatedSnapshot({
          program: prog,
          exam,
          slab: backendSlab,
          rangeText: backendCalc.scholarship_basis || rangeText,
          discountAmount: discountAmt,
          enteredScore: finalScoreDisplay,
          studentName: nameToUse,
          studentPhone: phoneToUse,
        });
        return;
      }
    } catch {
      // Graceful fallback to optimistic client-side calculations
    }

    setCalculatedSnapshot({
      program: prog,
      exam,
      slab,
      rangeText,
      discountAmount: discount,
      enteredScore: finalScoreDisplay,
      studentName: nameToUse,
      studentPhone: phoneToUse,
    });
  };

  // Reset calculation when clearing score
  const handleResetScore = () => {
    setEnteredScore("");
    setRankSuggestion(null);
    setSelectedSlabIndex(-1);
    setCalculatedSnapshot(null);
    setValidationError(null);
    setIncludeHostel(false);
  };

  // Switch to EAPCET Rank from rank prompt
  const handleSwitchToRank = (rankNum: number) => {
    setRankSuggestion(null);
    setSelectedExamKey("eamcet");
    const formatted = `Rank ${rankNum.toLocaleString("en-IN")}`;
    setEnteredScore(formatted);
    const eamcetExam = activeExams.find((e) => e.key === "eamcet") || { key: "eamcet", label: "TG/AP EAPCET Rank" };
    const res = matchSlabFromScore(currentProgram, "eamcet", formatted);
    setSelectedSlabIndex(res.slabIndex);
    computeAndSaveSnapshot(
      currentProgram,
      eamcetExam,
      formatted,
      res.slabIndex,
      savedLead?.name || studentName.trim(),
      savedLead?.phone || studentPhone.trim()
    );
  };

  // Handle score change live - parses typed text, auto-switches board, handles bare numbers > 1000
  const handleScoreChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setEnteredScore(val);
    setValidationError(null);

    // Clear every previous snapshot immediately before showing new result
    setCalculatedSnapshot(null);

    if (!val.trim()) {
      setRankSuggestion(null);
      setSelectedSlabIndex(-1);
      return;
    }

    // 1. Detect keywords to auto-switch board
    const detection = detectBoardFromInput(val);
    let activeExamKey = selectedExamKey;

    if (detection.detectedExamKey) {
      const isSupported = currentProgram.supportedExams.some((x) => x.key === detection.detectedExamKey);
      if (isSupported && activeExamKey !== detection.detectedExamKey) {
        activeExamKey = detection.detectedExamKey;
        setSelectedExamKey(activeExamKey);
      }
    }

    // 2. Bare number > 1000 with a percentage board selected cannot be marks.
    // Prompt to switch to EAPCET Rank and do NOT show standard fee or snapshot.
    if (isPercentageBoard(activeExamKey) && detection.isBareNumberGreaterThan1000 && detection.numericVal) {
      setRankSuggestion(detection.numericVal);
      setSelectedSlabIndex(-1);
      return;
    }

    setRankSuggestion(null);

    const activeExam = currentProgram.supportedExams.find((x) => x.key === activeExamKey) || currentExam;
    const res = matchSlabFromScore(currentProgram, activeExamKey, val);
    setSelectedSlabIndex(res.slabIndex);

    // Live update snapshot immediately if format is recognized
    if (res.status !== "invalid") {
      computeAndSaveSnapshot(
        currentProgram,
        activeExam,
        val,
        res.slabIndex,
        savedLead?.name || studentName.trim(),
        savedLead?.phone || studentPhone.trim()
      );
    }
  };

  // Program change
  const handleProgramChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newProgId = e.target.value;
    setSelectedProgramId(newProgId);
    setCalculatedSnapshot(null);
    setRankSuggestion(null);
    const prog = PROGRAMS.find((p) => p.id === newProgId);
    let nextExamKey = selectedExamKey;
    if (prog && !prog.supportedExams.some((x) => x.key === selectedExamKey)) {
      nextExamKey = prog.supportedExams[0].key;
      setSelectedExamKey(nextExamKey);
    }
    if (prog) {
      if (enteredScore.trim()) {
        const detection = detectBoardFromInput(enteredScore);
        if (isPercentageBoard(nextExamKey) && detection.isBareNumberGreaterThan1000 && detection.numericVal) {
          setRankSuggestion(detection.numericVal);
          setSelectedSlabIndex(-1);
          return;
        }
        const res = matchSlabFromScore(prog, nextExamKey, enteredScore);
        setSelectedSlabIndex(res.slabIndex);
        const nextExam = prog.supportedExams.find((x) => x.key === nextExamKey) || currentExam;
        computeAndSaveSnapshot(
          prog,
          nextExam,
          enteredScore,
          res.slabIndex,
          savedLead?.name || studentName.trim(),
          savedLead?.phone || studentPhone.trim()
        );
      } else {
        setSelectedSlabIndex(-1);
      }
    }
  };

  // Exam change
  const handleExamChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newExamKey = e.target.value;
    setSelectedExamKey(newExamKey);
    setCalculatedSnapshot(null);
    setRankSuggestion(null);
    if (enteredScore.trim()) {
      const detection = detectBoardFromInput(enteredScore);
      if (isPercentageBoard(newExamKey) && detection.isBareNumberGreaterThan1000 && detection.numericVal) {
        setRankSuggestion(detection.numericVal);
        setSelectedSlabIndex(-1);
        return;
      }
      const res = matchSlabFromScore(currentProgram, newExamKey, enteredScore);
      setSelectedSlabIndex(res.slabIndex);
      const nextExam = activeExams.find((x) => x.key === newExamKey) || currentExam;
      computeAndSaveSnapshot(
        currentProgram,
        nextExam,
        enteredScore,
        res.slabIndex,
        savedLead?.name || studentName.trim(),
        savedLead?.phone || studentPhone.trim()
      );
    } else {
      setSelectedSlabIndex(-1);
    }
  };

  // Form submit handler for score calculation
  const handleCalculateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (!enteredScore.trim()) {
      setValidationError("Please enter your marks (out of 1000), percentage (%), or EAPCET rank.");
      return;
    }

    const detection = detectBoardFromInput(enteredScore);
    let activeExamKey = selectedExamKey;

    if (detection.detectedExamKey) {
      const isSupported = currentProgram.supportedExams.some((x) => x.key === detection.detectedExamKey);
      if (isSupported && activeExamKey !== detection.detectedExamKey) {
        activeExamKey = detection.detectedExamKey;
        setSelectedExamKey(activeExamKey);
      }
    }

    if (isPercentageBoard(activeExamKey) && detection.isBareNumberGreaterThan1000 && detection.numericVal) {
      setRankSuggestion(detection.numericVal);
      setSelectedSlabIndex(-1);
      setCalculatedSnapshot(null);
      return;
    }

    setRankSuggestion(null);
    setCalculatedSnapshot(null);

    const activeExam = currentProgram.supportedExams.find((x) => x.key === activeExamKey) || currentExam;
    const res = matchSlabFromScore(currentProgram, activeExamKey, enteredScore);
    setSelectedSlabIndex(res.slabIndex);

    if (res.status !== "invalid") {
      await computeAndSaveSnapshot(
        currentProgram,
        activeExam,
        enteredScore,
        res.slabIndex,
        savedLead?.name || studentName.trim(),
        savedLead?.phone || studentPhone.trim()
      );
    }
  };

  // Optional admissions callback / lead request handler with mandatory consent
  const handleRequestCallback = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanName = studentName.trim();
    const cleanPhone = studentPhone.replace(/\D/g, "");
    if (!cleanName) {
      setValidationError("Please enter student name.");
      return;
    }
    if (cleanPhone.length < 10) {
      setValidationError("Please enter a valid 10-digit mobile number.");
      return;
    }
    if (!consentAgreed) {
      setValidationError("Please agree that SR University may contact you about admissions.");
      return;
    }

    setValidationError(null);
    const leadData = {
      name: cleanName,
      phone: cleanPhone,
      program_interest: currentProgram.name,
      score: scoreMatch.displayText || enteredScore || "Direct Inquiry",
      exam_type: currentExam.label,
      source: "scholarship_calculator_callback",
      metadata: {
        consent_given: true,
        calculated_discount: calculatedSnapshot?.discountAmount || 0,
        scholarship_percent: calculatedSnapshot?.slab.scholarshipPercent || 0,
        payable_sem: calculatedSnapshot?.slab.payableFeeSem || currentProgram.baseTuitionSem,
        admission_year: "2027-28",
      },
    };
    try {
      localStorage.setItem("sru_student_lead", JSON.stringify({ name: cleanName, phone: cleanPhone }));
      setIsVerified(true);
      await createLead(leadData);
      setLeadSuccessMsg("Admissions callback requested! An admissions counselor will reach out to you shortly.");
    } catch (err) {
      console.warn("Lead registration note:", err);
      setLeadSuccessMsg("Your inquiry was recorded. Our admissions team will reach out to you shortly.");
    }
  };

  // WhatsApp Share handler
  const handleWhatsAppShare = () => {
    if (!calculatedSnapshot) return;
    const p = calculatedSnapshot.program;
    const score = calculatedSnapshot.enteredScore || "N/A";
    const pct = calculatedSnapshot.slab.scholarshipPercent;
    const semFee = calculatedSnapshot.slab.payableFeeSem.toLocaleString("en-IN");
    const annualFee = (calculatedSnapshot.slab.payableFeeSem * 2).toLocaleString("en-IN");
    const hostelInfo = includeHostel
      ? `\n• Hostel (${hostelType === "ac" ? "AC" : "Non-AC"}): +₹${(hostelType === "ac" ? 125000 : 95000).toLocaleString("en-IN")}/year`
      : "";
    const total1stYr = ((calculatedSnapshot.slab.payableFeeSem * 2) + p.enrollmentFee + (includeHostel ? (hostelType === "ac" ? 125000 : 95000) : 0)).toLocaleString("en-IN");
    const text = `Hello SR University Admissions! I calculated my fee estimate for ${p.name} (Admissions 2027-28).\n• Score/Rank: ${score}\n• Scholarship: ${pct}%\n• Net Tuition: ₹${semFee}/sem (₹${annualFee}/year)${hostelInfo}\n• Total 1st Year: ₹${total1stYr}\nPlease share further admission and counseling guidance.`;
    window.open(`https://wa.me/918331003030?text=${encodeURIComponent(text)}`, "_blank");
  };

  // Print PDF handler
  const handlePrint = () => {
    window.print();
  };

  // Matched slab info for badge
  const matchedSlab =
    selectedSlabIndex >= 0 ? currentProgram.slabs[selectedSlabIndex] : null;
  const matchedRangeStr = matchedSlab
    ? (matchedSlab.ranges as any)[currentExam.key] ||
      matchedSlab.ranges.stateBoard ||
      "Standard Slab"
    : "Standard Fee (Below Cutoff)";

  // Next-tier upgrade calculation
  const nextTierInfo = useMemo(() => {
    if (selectedSlabIndex === -1) {
      return {
        nextSlab: currentProgram.slabs[0],
        message: enteredScore.trim()
          ? "Score 60%+ in State Board / CBSE or under 20,000 rank in TG/AP EAPCET to qualify for a 10% to 25% scholarship waiver!"
          : "Score 60%+ in State Board / CBSE or under 20,000 rank in TG/AP EAPCET to unlock 10% to 40% guaranteed merit scholarship waivers for all 4 years!",
      };
    }
    if (selectedSlabIndex < currentProgram.slabs.length - 1) {
      const current = currentProgram.slabs[selectedSlabIndex];
      const next = currentProgram.slabs[selectedSlabIndex + 1];
      const extraPerSem = current.payableFeeSem - next.payableFeeSem;
      const extraTotal = extraPerSem * 8;
      const nextRange = (next.ranges as any)[currentExam.key] || next.ranges.stateBoard;
      return {
        nextSlab: next,
        message: `Score ${nextRange} to unlock the ${next.scholarshipPercent}% Scholarship tier, saving you an extra ₹${extraPerSem.toLocaleString("en-IN")}/sem (₹${extraTotal.toLocaleString("en-IN")} across 4 years)!`,
      };
    }
    return {
      nextSlab: null,
      message: "🏆 Maximum Merit Tier: You have qualified for the highest official merit scholarship waiver (40% tuition discount)!",
    };
  }, [selectedSlabIndex, currentProgram, currentExam, enteredScore]);

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

        {/* 1. Verified Student Profile Bar (If verified: shows clean badge, NO name/phone inputs asked!) */}
        {isVerified && savedLead && (
          <div className="calc-verified-strip">
            <div className="calc-verified-info">
              <span className="calc-verified-check"><CheckIcon size={13} /></span>
              <span className="calc-verified-text">
                Verified Student: <strong>{savedLead.name}</strong> <span className="calc-verified-phone">({savedLead.phone})</span>
              </span>
            </div>
            <span className="calc-verified-tag">Authenticated</span>
          </div>
        )}

        {/* 2. Modern Inline Program & Qualifying Exam Selectors */}
        <div className="calc-selectors-grid">
          <div className="calc-select-group">
            <label htmlFor="calc-prog-select">Degree Program</label>
            <div className="calc-select-wrap">
              <select
                id="calc-prog-select"
                value={selectedProgramId}
                onChange={handleProgramChange}
                className="calc-select-modern"
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
          </div>

          <div className="calc-select-group">
            <label htmlFor="calc-exam-select">Qualifying Exam / Board</label>
            <div className="calc-select-wrap">
              <select
                id="calc-exam-select"
                value={currentExam.key}
                onChange={handleExamChange}
                className="calc-select-modern"
              >
                {activeExams.map((ex) => (
                  <option key={ex.key} value={ex.key}>
                    {ex.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* 3. Hero Marks Input & Presets */}
        <form onSubmit={handleCalculateSubmit} className="calc-input-section">
          <div className="calc-input-box">
            <label htmlFor="calc-marks-input" className="calc-input-label">
              <span>Enter Your Score / Percentage / Rank</span>
              <span className="calc-input-subtext">e.g. 850 marks in Inter, 88%, or EAPCET 4500</span>
            </label>

            <div className="calc-input-action-row">
              <div className="calc-input-field-wrap">
                <input
                  id="calc-marks-input"
                  type="text"
                  className="calc-main-input"
                  placeholder="Type marks, percentage, or rank..."
                  value={enteredScore}
                  onChange={handleScoreChange}
                  autoFocus
                />
                {enteredScore && (
                  <button
                    type="button"
                    className="calc-input-clear-btn"
                    onClick={handleResetScore}
                    title="Clear marks"
                    aria-label="Clear marks"
                  >
                    ✕
                  </button>
                )}
              </div>

              <button type="submit" className="calc-submit-btn">
                <BoltIcon size={16} />
                <span>Calculate</span>
              </button>
            </div>

            {/* Inline prompt for bare number > 1000 on percentage board */}
            {rankSuggestion !== null && (
              <div className="calc-rank-prompt-banner">
                <span>This looks like a rank. Switch to EAPCET Rank?</span>
                <button
                  type="button"
                  className="calc-switch-rank-btn"
                  onClick={() => handleSwitchToRank(rankSuggestion)}
                >
                  Switch to EAPCET Rank
                </button>
              </div>
            )}

            {rankSuggestion === null && scoreMatch.status === "matched" && matchedSlab && (
              <div className="calc-matched-badge">
                <AwardIcon size={14} />
                <span>
                  <strong>{matchedSlab.scholarshipPercent}% Scholarship Matched</strong>
                  {" • "}{matchedRangeStr}
                  {scoreMatch.displayText && !matchedRangeStr.includes(scoreMatch.displayText)
                    ? ` (${scoreMatch.displayText})`
                    : ""}
                </span>
              </div>
            )}
            {rankSuggestion === null && scoreMatch.status === "below_criteria" && enteredScore.trim() && (
              <div className="calc-matched-badge below-cutoff">
                <InfoIcon size={14} />
                <span>
                  <strong>Standard Tuition (Eligible for Admission)</strong>
                  {" • "}{scoreMatch.displayText}
                  {" • Merit scholarship starts at 60%"}
                </span>
              </div>
            )}
            {validationError && (
              <div className="calc-error-banner" style={{ marginTop: "4px" }}>
                <span>{validationError}</span>
              </div>
            )}
          </div>
        </form>

        {/* 4a. Ultra-Minimal Empty State (Hidden completely until user enters marks) */}
        {!calculatedSnapshot && (
          <div className="calc-empty-card">
            <div className="calc-empty-icon">🎯</div>
            <div className="calc-empty-info">
              <h4>Enter your marks to see your personalized fee</h4>
              <p>
                SR University provides guaranteed 10% to 40% merit scholarships for 60%+ marks or EAPCET rank under 20,000.
              </p>
            </div>
            <button
              type="button"
              className="calc-toggle-slabs-btn"
              onClick={() => setShowSlabsPreview(!showSlabsPreview)}
            >
              {showSlabsPreview ? "Hide Merit Slabs Table ▴" : "View Official Slabs & Criteria ▾"}
            </button>

            {showSlabsPreview && (
              <div className="calc-slabs-preview-table">
                <div className="slabs-table-header">
                  <span>Merit Waiver</span>
                  <span>{currentExam.label}</span>
                  <span>Payable Tuition</span>
                </div>
                {currentProgram.slabs.map((slab, idx) => {
                  const rangeText = (slab.ranges as any)[currentExam.key] || slab.ranges.stateBoard || `Slab ${idx + 1}`;
                  return (
                    <div key={idx} className="slabs-table-row">
                      <span className="slab-badge-min">{slab.scholarshipPercent}% Waiver</span>
                      <span className="slab-criteria-min">{rangeText}</span>
                      <span className="slab-payable-min">₹{slab.payableFeeSem.toLocaleString("en-IN")}/sem</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* 4b. Personalized Breakdown (Only shown when marks are entered/calculated) */}
        {calculatedSnapshot && (
          <div className="calc-results-container">
            {/* Results Header / Status Bar */}
            <div className="calc-results-header">
              <div className="calc-status-badge-wrap">
                {calculatedSnapshot.discountAmount > 0 ? (
                  <div className="calc-status-badge scholarship-awarded">
                    <AwardIcon size={16} />
                    <span>
                      <strong>{calculatedSnapshot.slab.scholarshipPercent}% Merit Scholarship Unlocked</strong>
                      {" • "}{calculatedSnapshot.enteredScore || calculatedSnapshot.rangeText}
                    </span>
                  </div>
                ) : (
                  <div className="calc-status-badge standard-tuition">
                    <InfoIcon size={16} />
                    <span>
                      <strong>Standard Tuition (Eligible for Admission)</strong>
                      {" • "}{calculatedSnapshot.enteredScore || calculatedSnapshot.rangeText}
                    </span>
                  </div>
                )}
              </div>
              <button
                type="button"
                className="calc-reset-action"
                onClick={handleResetScore}
                title="Test another score"
              >
                ↺ Test Another Score
              </button>
            </div>

            {/* High-Impact 2-Card Metric Display */}
            <div className="calc-metrics-grid">
              <div className="calc-metric-card primary-card">
                <span className="metric-tag">Net Payable Tuition</span>
                <div className="metric-primary-val">
                  ₹{calculatedSnapshot.slab.payableFeeSem.toLocaleString("en-IN")}
                  <span className="metric-unit"> / semester</span>
                </div>
                <div className="metric-sub-val">
                  ₹{(calculatedSnapshot.slab.payableFeeSem * 2).toLocaleString("en-IN")} / year (Annual Installment)
                </div>
              </div>

              <div className={`calc-metric-card ${calculatedSnapshot.discountAmount > 0 ? "savings-card" : "neutral-card"}`}>
                <span className="metric-tag">
                  {calculatedSnapshot.discountAmount > 0 ? "Merit Scholarship Savings" : "Scholarship Status"}
                </span>
                <div className="metric-primary-val green">
                  {calculatedSnapshot.discountAmount > 0
                    ? `Save ₹${(calculatedSnapshot.discountAmount * 2).toLocaleString("en-IN")}/yr`
                    : "Standard Fee"}
                </div>
                <div className="metric-sub-val">
                  {calculatedSnapshot.discountAmount > 0
                    ? `${calculatedSnapshot.slab.scholarshipPercent}% tuition discount (₹${calculatedSnapshot.discountAmount.toLocaleString("en-IN")}/sem)`
                    : "Scores below 60% pay standard tuition"}
                </div>
              </div>
            </div>

            {/* First-Year Joining Breakdown with Optional Hostel Toggle */}
            <div className="calc-breakdown-card">
              <div className="breakdown-card-header">
                <strong>First Year Total Payable Breakdown (2027-28)</strong>
                <span className="breakdown-badge">{calculatedSnapshot.program.name.split(" (")[0]}</span>
              </div>

              <div className="breakdown-lines">
                <div className="breakdown-line">
                  <span className="line-label">Net 1st Year Tuition Fee:</span>
                  <span className="line-val">₹{(calculatedSnapshot.slab.payableFeeSem * 2).toLocaleString("en-IN")}</span>
                </div>
                <div className="breakdown-line sub">
                  <span className="line-label">↳ Semester-wise Installment:</span>
                  <span className="line-val">₹{calculatedSnapshot.slab.payableFeeSem.toLocaleString("en-IN")} / semester</span>
                </div>
                <div className="breakdown-line">
                  <span className="line-label">One-Time Enrollment Fee:</span>
                  <span className="line-val">₹{calculatedSnapshot.program.enrollmentFee.toLocaleString("en-IN")}</span>
                </div>

                {/* Optional Hostel Accommodation Toggle */}
                <div className="calc-hostel-option-box">
                  <label className="hostel-toggle-label">
                    <input
                      type="checkbox"
                      checked={includeHostel}
                      onChange={(e) => setIncludeHostel(e.target.checked)}
                      className="hostel-checkbox"
                    />
                    <span className="hostel-toggle-text">
                      <strong>Include On-Campus Residential Hostel & Dining (Optional)</strong>
                    </span>
                  </label>

                  {includeHostel && (
                    <div className="hostel-sub-picker">
                      <label className={`hostel-type-pill ${hostelType === "non_ac" ? "selected" : ""}`}>
                        <input
                          type="radio"
                          name="hostelType"
                          value="non_ac"
                          checked={hostelType === "non_ac"}
                          onChange={() => setHostelType("non_ac")}
                        />
                        <span>Non-AC (3/4-Sharing): +₹95,000 / year</span>
                      </label>
                      <label className={`hostel-type-pill ${hostelType === "ac" ? "selected" : ""}`}>
                        <input
                          type="radio"
                          name="hostelType"
                          value="ac"
                          checked={hostelType === "ac"}
                          onChange={() => setHostelType("ac")}
                        />
                        <span>AC (3/4-Sharing): +₹1,25,000 / year</span>
                      </label>
                    </div>
                  )}
                </div>

                {calculatedSnapshot.program.annualIncrease && (
                  <div className="breakdown-line sub">
                    <span className="line-label">Tuition Increase from 2nd Year:</span>
                    <span className="line-val">+₹{calculatedSnapshot.program.annualIncrease.toLocaleString("en-IN")} / year</span>
                  </div>
                )}

                {/* Total 1st Year Sum */}
                <div className="breakdown-total-row">
                  <span className="total-label">
                    {includeHostel ? "Total 1st Year (Tuition + Enrollment + Hostel):" : "Total 1st Year (Tuition + Enrollment):"}
                  </span>
                  <span className="total-val bold-emerald">
                    ₹{((calculatedSnapshot.slab.payableFeeSem * 2) + calculatedSnapshot.program.enrollmentFee + (includeHostel ? (hostelType === "ac" ? 125000 : 95000) : 0)).toLocaleString("en-IN")}
                  </span>
                </div>
              </div>
            </div>

            {/* Next Tier Upgrade Opportunity */}
            {selectedSlabIndex < currentProgram.slabs.length - 1 && (
              <div className="calc-upgrade-card">
                <div className="upgrade-card-icon">💡</div>
                <div className="upgrade-card-text">
                  <strong>Upgrade Opportunity: </strong>
                  <span>{nextTierInfo.message}</span>
                </div>
              </div>
            )}

            {/* 4-Year Progression for B.Tech CSE */}
            {calculatedSnapshot.slab.cseYearlyPayable && (
              <div className="calc-progression-card">
                <div className="progression-header">
                  <CalendarIcon size={14} />
                  <span>4-Year Tuition Progression (Annual Base + ₹9,000/yr escalation):</span>
                </div>
                <div className="progression-pill-grid">
                  <div className="prog-pill">
                    <span className="prog-yr">Year 1</span>
                    <span className="prog-amt">₹{calculatedSnapshot.slab.cseYearlyPayable.yr1.toLocaleString("en-IN")}</span>
                  </div>
                  <div className="prog-pill">
                    <span className="prog-yr">Year 2</span>
                    <span className="prog-amt">₹{calculatedSnapshot.slab.cseYearlyPayable.yr2.toLocaleString("en-IN")}</span>
                  </div>
                  <div className="prog-pill">
                    <span className="prog-yr">Year 3</span>
                    <span className="prog-amt">₹{calculatedSnapshot.slab.cseYearlyPayable.yr3.toLocaleString("en-IN")}</span>
                  </div>
                  <div className="prog-pill">
                    <span className="prog-yr">Year 4</span>
                    <span className="prog-amt">₹{calculatedSnapshot.slab.cseYearlyPayable.yr4.toLocaleString("en-IN")}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Institutional Notes Callout */}
            <div className="calc-notes">
              <div className="note-item">
                <PinIcon size={15} />
                <div>
                  <strong>One-Time & Annual Charges:</strong> Enrollment Fee: ₹5,000 (one-time). Annual other fee: ₹15,000/yr | Exam fee: ₹5,000/yr | Tri-cities Bus transport: ₹30,000/yr.
                </div>
              </div>
              {calculatedSnapshot.program.specializationFeeAnnual && (
                <div className="note-item">
                  <FlaskIcon size={15} />
                  <div>
                    <strong>Specialization Fee:</strong> ₹{calculatedSnapshot.program.specializationFeeAnnual.toLocaleString("en-IN")}/year applicable from 2nd year onwards for advanced tech tracks (AI&ML, Cyber Security, Data Science, Quantum AI, Robotics).
                  </div>
                </div>
              )}
              <div className="note-item special-scholarship">
                <HeartHandIcon size={15} />
                <div>
                  <strong>19 Special Category Concessions:</strong> Flat annual tuition waivers of ₹50,000/yr (orphans, international sports, SRU staff children), ₹20,000/yr (differently abled over 50% disability), and ₹15,000/yr (girl students, single parent, defence/police, NCC C, SR Junior College, AP/out-of-state students, alumni siblings).
                </div>
              </div>
            </div>

            {/* Optional Admissions Counselor Callback Box */}
            <div className="calc-auth-box">
              <div className="calc-auth-header">
                <ShieldCheckIcon size={15} />
                <span>Request an Admissions Counselor Callback (Optional)</span>
              </div>
              <p className="calc-auth-subtext">
                Lock in this scholarship estimate and receive official counselor guidance for 2027-28 admissions.
              </p>
              {leadSuccessMsg ? (
                <div className="calc-lead-success">
                  <CheckIcon size={16} />
                  <span>{leadSuccessMsg}</span>
                </div>
              ) : (
                <div className="calc-callback-form-wrap">
                  <div className="calc-auth-grid">
                    <div className="calc-field">
                      <label htmlFor="calc-student-name">Student Full Name</label>
                      <input
                        id="calc-student-name"
                        type="text"
                        className="calc-input"
                        placeholder="Enter full name"
                        value={studentName}
                        onChange={(e) => {
                          setStudentName(e.target.value);
                          if (validationError) setValidationError(null);
                        }}
                      />
                    </div>
                    <div className="calc-field">
                      <label htmlFor="calc-student-phone">10-Digit Mobile Number</label>
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
                      />
                    </div>
                  </div>
                  <label className="calc-consent-label">
                    <input
                      type="checkbox"
                      checked={consentAgreed}
                      onChange={(e) => setConsentAgreed(e.target.checked)}
                    />
                    <span>I agree that SR University may contact me about admissions.</span>
                  </label>
                  {validationError && (
                    <div className="calc-error-banner">
                      <span>{validationError}</span>
                    </div>
                  )}
                  <button type="button" onClick={handleRequestCallback} className="calc-callback-btn">
                    Request Admissions Callback
                  </button>
                </div>
              )}
            </div>

            {/* Footer Action Buttons */}
            <div className="calc-footer-actions">
              <button
                type="button"
                className="btn-whatsapp"
                onClick={handleWhatsAppShare}
              >
                <span>💬 Send Estimate to WhatsApp</span>
              </button>
              <button
                type="button"
                className="btn-print"
                onClick={handlePrint}
              >
                <span>🖨️ Download / Print PDF</span>
              </button>
              <button
                type="button"
                className="btn-ask-buddy"
                onClick={() => {
                  onClose();
                  const hostelText = includeHostel ? ` (including ${hostelType === "ac" ? "AC" : "Non-AC"} hostel)` : "";
                  onAskBuddy(
                    `I evaluated the scholarship for ${calculatedSnapshot.program.name} with ${calculatedSnapshot.enteredScore || calculatedSnapshot.rangeText} which qualifies for a ${calculatedSnapshot.slab.scholarshipPercent}% merit waiver (Payable: ₹${calculatedSnapshot.slab.payableFeeSem.toLocaleString("en-IN")}/sem)${hostelText}. Please share details on admission verification and next steps.`
                  );
                }}
              >
                <MessageSquareIcon size={16} />
                <span>Ask SRU Buddy About This Fee</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
