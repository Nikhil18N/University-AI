# SR University AI Companion — Lead Verification, Tracking & Conversion SQL

This document provides documentation and SQL queries to cross-reference prospective student leads captured via the **SRU Buddy Scholarship Calculator** and **Chat Fee/Admissions Inquiries** against official university enrollment & admissions databases.

---

## 1. Prospective Leads Database Schema (`prospective_leads`)

Table created via Alembic migration `c3a1f8901234_add_prospective_leads_table.py`:

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID PRIMARY KEY` | Unique lead record identifier |
| `name` | `VARCHAR(255)` | Student's full name |
| `phone` | `VARCHAR(50)` | Verified contact mobile number (cleaned digits) |
| `email` | `VARCHAR(255)` | Optional email address |
| `program_interest`| `VARCHAR(255)` | Program of interest (e.g., `B.Tech CSE`, `B.Tech ECE`, `MBA`) |
| `score` | `VARCHAR(100)` | Student's entered score/rank (e.g., `92.5%`, `Rank 4500`, `SAT 1320`) |
| `exam_type` | `VARCHAR(100)` | Qualifying board/exam (e.g., `State Board (Inter)`, `CBSE`, `TG EAPCET`) |
| `source` | `VARCHAR(50)` | Ingestion source: `'calculator'` or `'chat_inquiry'` |
| `conversation_id` | `UUID REFERENCES conversations(id)` | Linked chat session (if originating from AI chat) |
| `status` | `VARCHAR(50)` | Conversion pipeline status: `'new'`, `'contacted'`, `'counselled'`, `'applied'`, `'enrolled'`, `'lost'` |
| `created_at` | `TIMESTAMPTZ` | Timestamp when lead authenticated/calculated |
| `metadata_` | `JSONB` | Additional JSON attributes (e.g. scholarship %, payable fee) |

---

## 2. SQL Queries for Conversion Attribution & Matching

### Query 1: Cross-Reference SRU Buddy Leads against University Admissions Table
Match prospective students who showed interest on SRU Buddy with final enrolled students in your university admissions / ERP system.

> **Normalization Note**: Matches on the last 10 digits of the mobile number to reliably handle country code variations (e.g., `+91`, `0`, or bare 10-digit numbers).

```sql
-- Query 1: Cross-reference leads with enrolled students
SELECT 
    l.id AS lead_id,
    l.name AS buddy_student_name,
    e.student_name AS enrolled_student_name,
    l.phone AS buddy_phone,
    e.mobile AS enrolled_mobile,
    l.program_interest AS buddy_program_interest,
    e.branch AS enrolled_branch,
    l.score AS qualifying_score,
    l.exam_type AS board_or_exam,
    l.source AS lead_source,
    l.created_at AS lead_captured_at,
    e.admission_date AS university_enrolled_at,
    -- Calculate days from AI Buddy inquiry to official enrollment
    DATE_PART('day', e.admission_date - l.created_at) AS days_to_conversion,
    CASE 
        WHEN e.roll_number IS NOT NULL THEN 'Enrolled via SRU Buddy'
        ELSE 'Pending / Unenrolled'
    END AS conversion_verdict
FROM prospective_leads l
INNER JOIN university_admissions e 
    ON RIGHT(REGEXP_REPLACE(l.phone, '[^0-9]', '', 'g'), 10) = 
       RIGHT(REGEXP_REPLACE(e.mobile, '[^0-9]', '', 'g'), 10)
ORDER BY l.created_at DESC;
```

---

### Query 2: Lead-to-Admission Conversion Rate by Channel (ROI Attribution)
Calculate the conversion percentage for students originating from the **Scholarship Calculator** vs **Chat Inquiries**:

```sql
-- Query 2: Conversion rate breakdown by source
SELECT 
    l.source AS lead_channel,
    COUNT(DISTINCT l.id) AS total_leads_captured,
    COUNT(DISTINCT e.roll_number) AS total_enrolled_students,
    ROUND(
        (COUNT(DISTINCT e.roll_number)::NUMERIC / NULLIF(COUNT(DISTINCT l.id), 0)::NUMERIC) * 100, 
        2
    ) AS conversion_rate_percentage
FROM prospective_leads l
LEFT JOIN university_admissions e 
    ON RIGHT(REGEXP_REPLACE(l.phone, '[^0-9]', '', 'g'), 10) = 
       RIGHT(REGEXP_REPLACE(e.mobile, '[^0-9]', '', 'g'), 10)
GROUP BY l.source
ORDER BY conversion_rate_percentage DESC;
```

---

### Query 3: Automatic Reconciliation — Update Status to 'enrolled'
Run this daily or after each admissions cycle to automatically mark matched leads as `'enrolled'` in SRU Buddy:

```sql
-- Query 3: Sync conversion status into prospective_leads
UPDATE prospective_leads l
SET status = 'enrolled'
FROM university_admissions e
WHERE RIGHT(REGEXP_REPLACE(l.phone, '[^0-9]', '', 'g'), 10) = 
      RIGHT(REGEXP_REPLACE(e.mobile, '[^0-9]', '', 'g'), 10)
  AND l.status != 'enrolled';
```

---

### Query 4: High-Value Unenrolled Leads for Admissions Tele-Counseling
Identify high-scoring students (eligible for 30%–50% scholarship) who showed interest but have not yet enrolled, for immediate follow-up by the admissions counselling desk:

```sql
-- Query 4: High-merit prospects pending enrollment
SELECT 
    l.id,
    l.name,
    l.phone,
    l.program_interest,
    l.score,
    l.exam_type,
    l.source,
    l.status,
    l.created_at
FROM prospective_leads l
LEFT JOIN university_admissions e 
    ON RIGHT(REGEXP_REPLACE(l.phone, '[^0-9]', '', 'g'), 10) = 
       RIGHT(REGEXP_REPLACE(e.mobile, '[^0-9]', '', 'g'), 10)
WHERE e.roll_number IS NULL
  AND l.status NOT IN ('enrolled', 'lost')
ORDER BY l.created_at DESC
LIMIT 100;
```

---

### Query 5: Full Lead Audit with Associated Chat Conversation Title
Inspect the exact chat conversation that triggered the student's interest:

```sql
-- Query 5: Leads joined with conversation metadata
SELECT 
    l.name AS student_name,
    l.phone,
    l.program_interest,
    l.score,
    l.source,
    l.status,
    c.title AS chat_conversation_topic,
    c.created_at AS chat_started_at,
    l.created_at AS lead_captured_at
FROM prospective_leads l
LEFT JOIN conversations c ON l.conversation_id = c.id
ORDER BY l.created_at DESC;
```
