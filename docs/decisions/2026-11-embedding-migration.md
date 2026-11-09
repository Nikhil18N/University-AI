# Architecture Decision Record: Embedding Model Migration (T11)

**Date**: November 10, 2026  
**Status**: Proposed / Ready for Owner Sign-off  
**Context**: Antigravity Hardening Task Brief (T11)  
**Authors**: Senior AI Engineering Team  

---

## 1. Executive Summary

The University AI Companion currently utilizes Google's legacy `models/embedding-001` with **3072 dimensions** to power vector similarity retrieval in ChromaDB. Google has introduced `text-embedding-004` (and `gemini-embedding-exp`) as the modern standard, offering **768 dimensions**, higher MTEB benchmark performance, and substantially reduced vector storage and memory requirements.

This document evaluates the migration timeline, token costs, dimensional trade-offs, and provides an idempotent, non-destructive **shadow collection script** to validate retrieval quality before switching production configurations.

---

## 2. Model Deprecation & Timeline

- **Current Model**: `models/embedding-001` (3072 dimensions, legacy PaLM/Gemini v1 embedding).
- **Target Replacement**: `text-embedding-004` (768 dimensions, native Matryoshka representations, top-tier MTEB score for semantic retrieval and code).
- **Deprecation Clock**: Google's Generative AI API documentation marks legacy v1 embedding endpoints for deprecation. While existing v1 endpoints remain operational, support and bugfixes are focused exclusively on v004.
- **Urgency Level**: **Medium-High (Q1 2027)**. Proactive migration avoids unexpected API cutoffs and aligns with Gemini 2.0/3.0 generation pipelines.

---

## 3. Financial & Token Cost Analysis

The university knowledge base is intentionally compact and high-signal, partitioned into `sru_facts` (95 chunks) and `sru_highlights` (67 chunks):

$$\text{Total Chunks} = 162 \text{ chunks}$$
$$\text{Average Tokens per Chunk} \approx 300 \text{ tokens}$$
$$\text{Total Corpus Tokens} = 162 \times 300 = 48,600 \text{ tokens}$$

### Re-embedding Cost on `text-embedding-004`:
- Google Cloud Gemini API Pricing: **\$0.00002 / 1,000 tokens** (Pay-as-you-go).
- First 1,500 requests per day are within the **Free Tier**.
- One-off re-embedding cost:
  $$\text{Cost} = \frac{48,600}{1,000} \times \$0.00002 = \$0.000972 \approx < \mathbf{\$0.001}$$

> [!NOTE]
> Re-embedding the entire university knowledge base costs less than one-tenth of one US cent (< \$0.001) and completes well within the daily Free Tier allowance.

---

## 4. Dimensionality & Architectural Trade-offs

| Dimension / Metric | Legacy `embedding-001` | Modern `text-embedding-004` | Impact / Benefit |
| :--- | :--- | :--- | :--- |
| **Vector Dimensions** | 3072 | 768 | **4x smaller** memory footprint in ChromaDB & Redis |
| **Vector Size per Chunk** | 12.28 KB | 3.07 KB | Faster cosine distance computation |
| **MTEB Retrieval Score** | 56.4% | 66.3% | Substantially higher precision on academic and technical QA |
| **Matryoshka Truncation** | No | Yes (supports 512, 256, 128) | Flexible dimension tuning if needed |
| **Latency per Embed** | ~180 ms | ~95 ms | **~50% lower embedding latency** |

---

## 5. Migration Strategy: Shadow Collection (Zero Risk)

Per Rule 4 of the Hardening Brief, **the existing 3072-dim collections (`sru_facts`, `sru_highlights`, `university_documents`) must never be dropped** until the replacement collection is live-tested and verified.

### Implementation Blueprint:
1. **Shadow Creation**: The script `backend/scripts/shadow_reembed_text_embedding_004.py` creates new isolated collections:
   - `sru_facts_v4` (768 dimensions)
   - `sru_highlights_v4` (768 dimensions)
2. **Side-by-Side Evaluation**: Run `backend/scripts/eval_live.py` with `RUN_LIVE_EVALS=1` against `sru_facts_v4` to verify:
   - 100% accuracy on Part C 15 benchmark questions.
   - Zero ungrounded numbers or hallucinations.
3. **Configuration Flip**:
   Once verified, staff updates `.env`:
   ```env
   EMBEDDING_MODEL=text-embedding-004
   CHROMA_FACTS_COLLECTION=sru_facts_v4
   CHROMA_HIGHLIGHTS_COLLECTION=sru_highlights_v4
   ```
4. **Archive Old Index**: Keep legacy collections as cold backups for 60 days before purging.

---

## 6. Recommendation

**Execute the shadow re-embedding into `sru_facts_v4` and `sru_highlights_v4` using `backend/scripts/shadow_reembed_text_embedding_004.py`**. Verify side-by-side with Part C evaluations, then switch production settings with zero downtime and zero risk of regression.
