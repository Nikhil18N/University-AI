# Production Architecture & Cloud Model Strategy Plan

## Executive Summary
This document outlines the production deployment requirements, cloud model trade-offs, data privacy guarantees for SR University, and strategies to improve reasoning in local vs. cloud-hosted models.

---

## 1. Production Server Requirements

In production, the SR University AI Companion comprises:
1. **Frontend**: Vite React static bundle (served via Nginx, Cloudflare Pages, or AWS S3/CloudFront).
2. **Backend**: FastAPI + Uvicorn (async Python REST API).
3. **Database**: PostgreSQL 16 (conversations, messages, user feedback).
4. **Cache**: Redis 7 (conversation session state & API rate limiting).
5. **Vector Store**: ChromaDB (document chunk embeddings & verified exemplars).
6. **Inference Engine**: Cloud LLM API or Self-Hosted GPU Worker.

### Hardware & Cost Comparison

| Specification | Architecture A: Cloud Model (API)<br>*(Recommended)* | Architecture B: Self-Hosted Model<br>*(Ollama / vLLM on-premise)* |
| :--- | :--- | :--- |
| **Server Type** | Standard Cloud VM (AWS `t4g.xlarge` / DigitalOcean / Hetzner) | Dedicated GPU Instance (AWS `g5.xlarge` / Lambda Labs) |
| **GPU** | **None (0 GPU)** | **NVIDIA A10G / L4 / RTX 4090** (min 16GB–24GB VRAM) |
| **vCPU** | 4 to 8 vCPUs | 8 to 16 vCPUs |
| **RAM** | 16 GB | 32 GB to 64 GB |
| **Storage (NVMe SSD)** | 50 GB to 100 GB | 200 GB to 500 GB (model weights + vector index) |
| **Concurrency Capacity** | **500+ simultaneous students** (Cloud scales instantly) | **5 to 15 concurrent users** per GPU before response delays |
| **Baseline Server Cost** | **$30 to $60 / month** | **$350 to $700 / month** per GPU instance |
| **Token Usage Cost** | Pay-as-you-go (~$10–$40/mo for 50k queries on Gemini Flash) | $0 token cost, but fixed 24/7 high GPU rental |

---

## 2. Cloud Model Evaluation

Moving from a compact local 3B model (`llama3.2 3B`) to an enterprise cloud model (e.g., Google Gemini 1.5 Flash, Anthropic Claude 3.5 Sonnet, or OpenAI GPT-4o-mini) provides four key advantages:

### 2.1 Natural Synthesis vs. Document Regurgitation
- **3B Local Model**: Limited attention budget often leads the model to paraphrase or copy-paste large portions of raw handbook regulations.
- **Cloud Model**: Reads the retrieved context, extracts the core truth, and articulates it in friendly, concise, human-counsellor phrasing.

### 2.2 Strict Instruction Following & Zero Prompt Leakage
- Cloud models have superior negative constraint compliance (*"never assume marks"*, *"never generate portal URLs"*).
- Eliminates example leakage (where small models accidentally recite template examples as closing remarks).

### 2.3 Conversational Agility (Companion + Admissions Counsellor)
- Effortlessly switches between casual student banter (jokes, slang, typos) and rigorous official policy counseling.
- Tracks multi-turn conversational state across 20+ turns without degradation.

---

## 3. Data Privacy & Compliance for SR University

Using cloud models does **not** compromise SR University's internal data:

1. **Commercial Zero-Training Guarantee**:
   - Enterprise API terms (Google Cloud Vertex AI / Gemini API, OpenAI API, AWS Bedrock) legally guarantee that inputs and outputs are **never used to train foundation models**.
2. **RAG Architecture Isolates the Full Database**:
   - The entire university handbook and student database stay on your private server.
   - The cloud model is only sent the specific 2-paragraph excerpt relevant to the immediate question, which is processed ephemerally in RAM.
3. **Outbound Data Scrubbing**:
   - Automated guardrails strip any student identifiers (phone numbers, emails, roll numbers) before passing context to an external API.
4. **Provider Interoperability**:
   - The system uses the abstract `LLMProvider` interface, allowing the backend to swap between local Ollama and Cloud APIs via an environment variable (`LLM_PROVIDER=gemini`).

---

## 4. Local Model Reasoning Improvement

### Can we improve reasoning on `llama3.2 3B`?
**Yes.** While 3B models cannot be expanded in parameter count, their effective reasoning accuracy can be significantly boosted without fine-tuning:

1. **Chain-of-Thought (Scratchpad Reasoning)**:
   - Prompt the model to produce a hidden `<thought>` block before generating the final answer.
   - The model analyzes the student's status, checks criteria against the cutoff, plans what to confirm and what to omit, and then outputs only the clean conversational text.
2. **Deterministic Python Offloading**:
   - Rather than relying on a 3B model to perform fuzzy mathematical reasoning (e.g. comparing intermediate PCM marks vs 60%), our `profile_service` calculates eligibility deterministically in Python and passes unambiguous directives to the prompt.
3. **Dynamic Few-Shot Learning (`verified_exemplars`)**:
   - Dynamically retrieving high-quality, human-approved answers for similar questions anchors the reasoning structure for small models.

### Is heavy reasoning required for this application?
- **No.** The University AI Companion is an informational and conversational counsellor, not a multi-step mathematical theorem solver or software engineer.
- Heavy reasoning models (like DeepSeek-R1 or OpenAI o1) introduce 10–20 seconds of thinking latency per query, which impairs the instant conversational experience for students asking simple queries like *"When do exams start?"*.
- What is required is **crisp synthesis, high instruction-following fidelity, and zero hallucinations**, which is best achieved via prompt engineering + Python guardrails locally, or via modern fast cloud models (Gemini 1.5 Flash).
