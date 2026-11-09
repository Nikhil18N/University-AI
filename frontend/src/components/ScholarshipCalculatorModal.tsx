import React, { useState, useMemo, useEffect } from "react";
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
  TrendingUpIcon,
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
        ranges: { stateBoard: "98% and above", cbse: "98% and above", jeeMains: "95% and above", eamcet: "1 – 10000", sat: "1451 – 1600", ib: "39 and above" },
        payableFeeSem: 74000,
        cseYearlyPayable: { yr1: 74000, yr2: 78000, yr3: 82000, yr4: 86000 },
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
      { scholarshipPercent: 50, ranges: { stateBoard: "90% and above", cbse: "98% and above", jeeMains: "90% and above", eamcet: "1 – 10000", sat: "1451 – 1600", ib: "39 and above" }, payableFeeSem: 60000 },
    ],
  },
  {
    id: "btech_core",
    name: "B.Tech. Mechanical / Civil / EEE",
    degreeType: "Bachelors",
    baseTuitionSem: 100000,
    enrollmentFee: 5000,
    admissionFee: 25000,
    specializations: ["Renewable Energy", "Robotics and Automation", "Electric Vehicles", "Smart Manufacturing"],
    supportedExams: [
      { key: "stateBoard", label: "State Board (10+2 / Inter) %" },
      { key: "cbse", label: "CBSE %" },
      { key: "jeeMains", label: "JEE Mains %" },
      { key: "eamcet", label: "EAMCET / EAPCET Rank" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { stateBoard: "60 – 69.99%", cbse: "60 – 64.99%", jeeMains: "60 – 69.99%", eamcet: "16001 – 18000" }, payableFeeSem: 90000 },
      { scholarshipPercent: 20, ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%", jeeMains: "70 – 74.99%", eamcet: "15001 – 16000" }, payableFeeSem: 80000 },
      { scholarshipPercent: 30, ranges: { stateBoard: "80 – 91.99%", cbse: "75 – 89.99%", jeeMains: "75 – 79.99%", eamcet: "12001 – 15000" }, payableFeeSem: 70000 },
      { scholarshipPercent: 40, ranges: { stateBoard: "92 – 97.99%", cbse: "90 – 97.99%", jeeMains: "80 – 89.99%", eamcet: "10001 – 12000" }, payableFeeSem: 60000 },
      { scholarshipPercent: 50, ranges: { stateBoard: "90% and above", cbse: "98% and above", jeeMains: "90% and above", eamcet: "1 – 10000" }, payableFeeSem: 50000 },
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
      { key: "stateBoard", label: "State Board (10+2 / Inter) %" },
      { key: "cbse", label: "CBSE %" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { stateBoard: "60 – 69.99%", cbse: "60 – 64.99%" }, payableFeeSem: 81000 },
      { scholarshipPercent: 20, ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%" }, payableFeeSem: 72000 },
      { scholarshipPercent: 30, ranges: { stateBoard: "80 – 91.99%", cbse: "75 – 89.99%" }, payableFeeSem: 63000 },
      { scholarshipPercent: 40, ranges: { stateBoard: "92 – 97.99%", cbse: "90 – 97.99%" }, payableFeeSem: 54000 },
      { scholarshipPercent: 50, ranges: { stateBoard: "90% and above", cbse: "98% and above" }, payableFeeSem: 45000 },
    ],
  },
  {
    id: "bba",
    name: "BBA (Bachelor of Business Administration)",
    degreeType: "Bachelors",
    baseTuitionSem: 90000,
    enrollmentFee: 5000,
    admissionFee: 25000,
    supportedExams: [
      { key: "stateBoard", label: "State Board (10+2 / Inter) %" },
      { key: "cbse", label: "CBSE %" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { stateBoard: "60 – 69.99%", cbse: "60 – 64.99%" }, payableFeeSem: 81000 },
      { scholarshipPercent: 20, ranges: { stateBoard: "70 – 79.99%", cbse: "65 – 74.99%" }, payableFeeSem: 72000 },
      { scholarshipPercent: 30, ranges: { stateBoard: "80 – 91.99%", cbse: "75 – 89.99%" }, payableFeeSem: 63000 },
      { scholarshipPercent: 40, ranges: { stateBoard: "92 – 97.99%", cbse: "90 – 97.99%" }, payableFeeSem: 54000 },
      { scholarshipPercent: 50, ranges: { stateBoard: "90% and above", cbse: "98% and above" }, payableFeeSem: 45000 },
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
      { key: "degree", label: "Any Degree %" },
      { key: "icet", label: "ICET Rank" },
      { key: "catMat", label: "MAT/XAT/CAT %" },
    ],
    slabs: [
      { scholarshipPercent: 10, ranges: { degree: "60 – 69.99%", icet: "1751 – 2000", catMat: "60 – 69.99%" }, payableFeeSem: 135000 },
      { scholarshipPercent: 20, ranges: { degree: "70 – 79.99%", icet: "1501 – 1750", catMat: "70 – 74.99%" }, payableFeeSem: 120000 },
      { scholarshipPercent: 30, ranges: { degree: "80 – 89.99%", icet: "1251 – 1500", catMat: "75 – 79.99%" }, payableFeeSem: 105000 },
      { scholarshipPercent: 40, ranges: { degree: "90 – 94.99%", icet: "1001 – 1250", catMat: "80 – 84.99%" }, payableFeeSem: 90000 },
      { scholarshipPercent: 50, ranges: { degree: "95% and above", icet: "1 – 1000", catMat: "85% and above" }, payableFeeSem: 75000 },
    ],
  },
];

interface QuickPreset {
  label: string;
  value: string;
  examKey: string;
}

const QUICK_PRESETS: QuickPreset[] = [
  { label: "780 / 1000 (Inter)", value: "780", examKey: "stateBoard" },
  { label: "850 / 1000 (Inter)", value: "850", examKey: "stateBoard" },
  { label: "920 / 1000 (Inter)", value: "920", examKey: "stateBoard" },
  { label: "85% (10+2 MPC)", value: "85%", examKey: "stateBoard" },
  { label: "Rank 4,500 (EAPCET)", value: "4500", examKey: "eamcet" },
  { label: "Rank 8,500 (EAPCET)", value: "8500", examKey: "eamcet" },
  { label: "Rank 12,500 (EAPCET)", value: "12500", examKey: "eamcet" },
  { label: "CBSE 88%", value: "88%", examKey: "cbse" },
];

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

  // Form state
  const [selectedProgramId, setSelectedProgramId] = useState<string>("btech_cse");
  const [selectedExamKey, setSelectedExamKey] = useState<string>("stateBoard");
  const [enteredScore, setEnteredScore] = useState<string>("780");
  const [selectedSlabIndex, setSelectedSlabIndex] = useState<number>(1); // Default matches 30% slab for 780
  const [showProgramPicker, setShowProgramPicker] = useState<boolean>(false);

  // Student Authentication inputs (only used if unverified)
  const [studentName, setStudentName] = useState<string>(savedLead?.name || "");
  const [studentPhone, setStudentPhone] = useState<string>(savedLead?.phone || "");
  const [validationError, setValidationError] = useState<string | null>(null);

  // Calculated snapshot state
  const [calculatedSnapshot, setCalculatedSnapshot] = useState<CalculatedSnapshot | null>(null);

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
    return matchSlabFromScore(currentProgram, currentExam.key, enteredScore);
  }, [currentProgram, currentExam.key, enteredScore]);

  // Execute calculation snapshot
  const computeAndSaveSnapshot = async (
    prog: ProgramConfig,
    exam: { key: string; label: string },
    scoreInput: string,
    slabIdx: number,
    nameToUse: string,
    phoneToUse: string
  ) => {
    const isNoScholarship = slabIdx === -1;
    const slab: ScholarshipSlab = isNoScholarship
      ? {
          scholarshipPercent: 0,
          payableFeeSem: prog.baseTuitionSem,
          ranges: { [exam.key]: "Standard Tuition (Below Cutoff)" },
          cseYearlyPayable:
            prog.id === "btech_cse"
              ? { yr1: 147500, yr2: 155000, yr3: 163000, yr4: 171000 }
              : undefined,
        }
      : prog.slabs[slabIdx] || prog.slabs[0];

    const rangeText = isNoScholarship
      ? "Standard Tuition (No Merit Waiver)"
      : (slab.ranges as any)[exam.key] ||
        slab.ranges.stateBoard ||
        `Slab ${slabIdx + 1}`;

    const discount = isNoScholarship
      ? 0
      : Math.round(prog.baseTuitionSem * (slab.scholarshipPercent / 100));

    const finalScoreDisplay = scoreMatch.displayText || scoreInput.trim() || rangeText;

    // Save lead in localStorage and PostgreSQL backend
    if (nameToUse && phoneToUse) {
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

  // Initial calculation on mount (auto-evaluate default 780 marks for instant fee view)
  useEffect(() => {
    const initialMatch = matchSlabFromScore(currentProgram, currentExam.key, enteredScore);
    const initialSlabIdx = initialMatch.slabIndex >= 0 ? initialMatch.slabIndex : 1;
    setSelectedSlabIndex(initialSlabIdx);
    computeAndSaveSnapshot(
      currentProgram,
      currentExam,
      enteredScore,
      initialSlabIdx,
      savedLead?.name || "",
      savedLead?.phone || ""
    );
  }, []);

  // Handle score change live
  const handleScoreChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setEnteredScore(val);
    const res = matchSlabFromScore(currentProgram, currentExam.key, val);
    setSelectedSlabIndex(res.slabIndex);

    // Live update snapshot if already verified
    if (isVerified && savedLead) {
      computeAndSaveSnapshot(
        currentProgram,
        currentExam,
        val,
        res.slabIndex,
        savedLead.name,
        savedLead.phone
      );
    }
  };

  // Apply quick preset
  const applyPreset = (preset: QuickPreset) => {
    setEnteredScore(preset.value);
    setSelectedExamKey(preset.examKey);
    const res = matchSlabFromScore(currentProgram, preset.examKey, preset.value);
    setSelectedSlabIndex(res.slabIndex);

    const nameToUse = savedLead?.name || studentName.trim();
    const phoneToUse = savedLead?.phone || studentPhone.trim();

    computeAndSaveSnapshot(
      currentProgram,
      currentProgram.supportedExams.find((x) => x.key === preset.examKey) || currentExam,
      preset.value,
      res.slabIndex,
      nameToUse,
      phoneToUse
    );
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
    if (prog) {
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
    }
  };

  // Exam change
  const handleExamChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newExamKey = e.target.value;
    setSelectedExamKey(newExamKey);
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
  };

  // Form submit handler
  const handleCalculateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    let nameToUse = savedLead?.name || "";
    let phoneToUse = savedLead?.phone || "";

    // If not verified, validate inputs
    if (!isVerified) {
      const cleanName = studentName.trim();
      const cleanPhone = studentPhone.replace(/\D/g, "");
      if (!cleanName) {
        setValidationError("Please enter student name to view official fee structure.");
        return;
      }
      if (cleanPhone.length < 10) {
        setValidationError("Please enter a valid 10-digit mobile number for admissions authentication.");
        return;
      }
      nameToUse = cleanName;
      phoneToUse = studentPhone.trim();
      setValidationError(null);
    }

    const res = matchSlabFromScore(currentProgram, currentExam.key, enteredScore);
    setSelectedSlabIndex(res.slabIndex);
    await computeAndSaveSnapshot(currentProgram, currentExam, enteredScore, res.slabIndex, nameToUse, phoneToUse);
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
        message: "Score 60%+ in State Board or under 18,000 in EAPCET to qualify for 20% scholarship waiver!",
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
      message: "🏆 Highest Merit Tier: You have qualified for the maximum official merit scholarship waiver!",
    };
  }, [selectedSlabIndex, currentProgram, currentExam]);

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

        {/* 2. Program Selector Strip (Compact, with 1-click toggle) */}
        <div className="calc-program-strip">
          <div className="calc-program-summary">
            <span className="calc-program-name">
              <strong>{currentProgram.name}</strong>
            </span>
            <span className="calc-exam-tag">{currentExam.label}</span>
          </div>
          <button
            type="button"
            className="calc-toggle-prog-btn"
            onClick={() => setShowProgramPicker(!showProgramPicker)}
          >
            {showProgramPicker ? "Done ▴" : "Change Program / Board ▾"}
          </button>
        </div>

        {/* Expandable Program & Exam Dropdowns */}
        {showProgramPicker && (
          <div className="calc-picker-dropdowns">
            <div className="calc-picker-field">
              <label htmlFor="calc-prog-select">Select Academic Degree Program</label>
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

            <div className="calc-picker-field">
              <label htmlFor="calc-exam-select">Select Qualifying Examination / Board</label>
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
          </div>
        )}

        {/* 3. Primary "Marks Only" Input Card */}
        <form onSubmit={handleCalculateSubmit} className="calc-marks-form">
          <div className="calc-marks-card">
            <div className="calc-marks-label-row">
              <label htmlFor="calc-marks-input" className="calc-marks-label">
                Enter Your Marks / Score / Rank
              </label>
              <span className="calc-marks-instruction">
                Enter Intermediate marks (out of 1000), percentage (%), or EAPCET rank
              </span>
            </div>

            <div className="calc-input-button-row">
              <div className="calc-score-input-wrap">
                <input
                  id="calc-marks-input"
                  type="text"
                  className="calc-input calc-score-input"
                  placeholder="e.g. 780 marks in Inter, 85%, or EAPCET 8500"
                  value={enteredScore}
                  onChange={handleScoreChange}
                  autoFocus
                />
                {scoreMatch.status === "matched" && matchedSlab && (
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
                {scoreMatch.status === "below_criteria" && (
                  <div className="calc-matched-badge below-cutoff">
                    <InfoIcon size={14} />
                    <span>
                      <strong>Standard Tuition (No Merit Waiver)</strong>
                      {" • "}{scoreMatch.displayText}
                    </span>
                  </div>
                )}
              </div>

              <button type="submit" className="calc-eval-btn">
                <BoltIcon size={16} />
                <span>Calculate</span>
              </button>
            </div>

            {/* Quick Presets */}
            <div className="calc-presets-bar">
              <span className="calc-presets-title">Quick Marks:</span>
              <div className="calc-presets-list">
                {QUICK_PRESETS.map((preset) => (
                  <button
                    key={preset.label}
                    type="button"
                    className={`calc-preset-chip ${enteredScore === preset.value ? "active" : ""}`}
                    onClick={() => applyPreset(preset)}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* If NOT verified: prompt student for Name & Mobile Number */}
          {!isVerified && (
            <div className="calc-auth-box">
              <div className="calc-auth-header">
                <ShieldCheckIcon size={15} />
                <span>Student Verification (Required for Official Fee Calculation)</span>
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
          )}
        </form>

        {/* 4. Official Fee Structure Breakdown */}
        {calculatedSnapshot && (
          <div className="calc-result-box">
            <div className="result-section-header">
              <div className="result-header-title">
                <TrendingUpIcon size={16} />
                <h4>Official Fee Structure & Payable Amounts</h4>
              </div>
              <span className="result-program-badge">
                {calculatedSnapshot.program.name}
              </span>
            </div>

            {/* Three-Column Fee Comparison */}
            <div className="fee-comparison-row">
              <div className="fee-stat">
                <span className="stat-label">Standard Tuition</span>
                <span className={`stat-val ${calculatedSnapshot.discountAmount > 0 ? "strikethrough" : ""}`}>
                  ₹{calculatedSnapshot.program.baseTuitionSem.toLocaleString("en-IN")}
                </span>
                <span className="stat-sub">per semester</span>
              </div>

              <div className={`fee-stat ${calculatedSnapshot.discountAmount > 0 ? "highlight-green" : ""}`}>
                <span className="stat-label">Merit Scholarship Waiver</span>
                <span className="stat-val savings">
                  {calculatedSnapshot.discountAmount > 0
                    ? `-₹${calculatedSnapshot.discountAmount.toLocaleString("en-IN")}`
                    : "₹0"}
                </span>
                <span className="stat-sub">
                  {calculatedSnapshot.slab.scholarshipPercent > 0
                    ? `${calculatedSnapshot.slab.scholarshipPercent}% tuition discount`
                    : "Below minimum cutoff"}
                </span>
              </div>

              <div className="fee-stat primary-payable">
                <span className="stat-label">Net Payable Tuition</span>
                <span className="stat-val payable">
                  ₹{calculatedSnapshot.slab.payableFeeSem.toLocaleString("en-IN")}
                </span>
                <span className="stat-sub">per semester</span>
              </div>
            </div>

            {/* Total 1st Semester Payable (Tuition + Enrollment + Admission) */}
            <div className="calc-joining-breakdown">
              <div className="joining-header">
                <strong>Admission & First Semester Payable Breakdown:</strong>
              </div>
              <div className="joining-row">
                <span className="joining-item">Net 1st Semester Tuition:</span>
                <span className="joining-val">₹{calculatedSnapshot.slab.payableFeeSem.toLocaleString("en-IN")}</span>
              </div>
              <div className="joining-row">
                <span className="joining-item">One-Time Enrollment Fee:</span>
                <span className="joining-val">₹{calculatedSnapshot.program.enrollmentFee.toLocaleString("en-IN")}</span>
              </div>
              <div className="joining-row">
                <span className="joining-item">One-Time Admission Fee:</span>
                <span className="joining-val">₹{calculatedSnapshot.program.admissionFee.toLocaleString("en-IN")}</span>
              </div>
              <div className="joining-row total-joining">
                <span className="joining-item">Total Payable at 1st Semester Joining:</span>
                <span className="joining-val bold-emerald">
                  ₹{(calculatedSnapshot.slab.payableFeeSem + calculatedSnapshot.program.enrollmentFee + calculatedSnapshot.program.admissionFee).toLocaleString("en-IN")}
                </span>
              </div>
            </div>

            {/* 4-Year Semester Progression for B.Tech CSE */}
            {calculatedSnapshot.slab.cseYearlyPayable && (
              <div className="progression-table-wrap">
                <div className="progression-title">
                  <CalendarIcon size={14} />
                  <span>Year-by-Year Semester Tuition Progression (CSE):</span>
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

            {/* 5. "How Scholarship Is Possible" (Full Criteria Ladder & Roadmap) */}
            <div className="calc-roadmap-section">
              <div className="roadmap-title-row">
                <div className="roadmap-title">
                  <AwardIcon size={16} />
                  <h4>How Scholarship Is Possible (Merit Slabs & Criteria)</h4>
                </div>
                <span className="roadmap-sub">Guaranteed by SR University Regulations</span>
              </div>

              {/* Slabs Ladder Table */}
              <div className="roadmap-ladder">
                {currentProgram.slabs.map((slab, idx) => {
                  const isCurrentMatch = idx === selectedSlabIndex;
                  const rangeText = (slab.ranges as any)[currentExam.key] || slab.ranges.stateBoard || `Slab ${idx + 1}`;
                  return (
                    <div
                      key={idx}
                      className={`roadmap-slab-row ${isCurrentMatch ? "matched-active" : ""}`}
                    >
                      <div className="slab-pct-col">
                        <span className="slab-pct-badge">{slab.scholarshipPercent}% Waiver</span>
                        {isCurrentMatch && <span className="matched-tag">✓ Your Score Matched</span>}
                      </div>
                      <div className="slab-criteria-col">
                        <span className="slab-exam-label">{currentExam.label}:</span>
                        <strong className="slab-criteria-text">{rangeText}</strong>
                      </div>
                      <div className="slab-payable-col">
                        <span className="slab-payable-label">You Pay:</span>
                        <span className="slab-payable-amt">₹{slab.payableFeeSem.toLocaleString("en-IN")}/sem</span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Next Tier Upgrade Opportunity */}
              <div className="roadmap-upgrade-banner">
                <div className="upgrade-icon">💡</div>
                <div className="upgrade-text">
                  <strong>Upgrade Opportunity: </strong>
                  <span>{nextTierInfo.message}</span>
                </div>
              </div>
            </div>

            {/* Institutional Notes Callout */}
            <div className="calc-notes">
              <div className="note-item">
                <PinIcon size={15} />
                <div>
                  <strong>One-Time Fees:</strong> Enrollment Fee ₹{calculatedSnapshot.program.enrollmentFee.toLocaleString("en-IN")} and Admission Fee ₹{calculatedSnapshot.program.admissionFee.toLocaleString("en-IN")} payable only once during admission.
                </div>
              </div>
              {calculatedSnapshot.program.specializationFeeAnnual && (
                <div className="note-item">
                  <FlaskIcon size={15} />
                  <div>
                    <strong>Specialization Fee:</strong> ₹{calculatedSnapshot.program.specializationFeeAnnual.toLocaleString("en-IN")}/year applicable from 2nd year onwards for advanced tech tracks (AI&ML, Cyber Security, Data Science, etc.).
                  </div>
                </div>
              )}
              <div className="note-item special-scholarship">
                <HeartHandIcon size={15} />
                <div>
                  <strong>Special 15% Waiver:</strong> An additional 15% tuition concession is granted to students who lost their parents (Death certificate required; min 7.5 CGPA required for continuation).
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
                    `I evaluated the scholarship for ${calculatedSnapshot.program.name} with ${calculatedSnapshot.enteredScore || calculatedSnapshot.rangeText} which qualifies for a ${calculatedSnapshot.slab.scholarshipPercent}% merit waiver (Payable: ₹${calculatedSnapshot.slab.payableFeeSem.toLocaleString("en-IN")}/sem). Can you guide me through admission verification and hostel accommodation?`
                  );
                }}
              >
                <MessageSquareIcon size={16} />
                <span>Ask SRU Buddy About This Fee & Scholarship</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
