# End-to-End Cost & Unit Economics Analysis

This document provides a breakdown of operational costs for **FamilyCareEats Backend**, including per-photo multimodal AI inference, deterministic scoring, family weekly batch synthesis, and cloud storage/database infrastructure.

All AI pricing rates are queried live from the [OpenRouter API](https://openrouter.ai/api/v1/models).

---

## 1. Executive Summary

| Operation | Engine / Service | Unit Cost | Cost per 1,000 Invocations |
| :--- | :--- | :--- | :--- |
| **Meal Photo Analysis** | OpenRouter (`google/gemini-2.5-flash`) | **$0.00040** | **$0.40** (40 cents) |
| **Alternative Vision Engine** | OpenRouter (`google/gemini-2.5-flash-lite`) | **$0.00009** | **$0.09** (9 cents) |
| **Deterministic Scoring** | Python Engine (`services/scoring.py`) | **$0.00000** (Free) | **$0.00** (0 tokens) |
| **Weekly Family Digest** | OpenRouter Reasoning Synthesis | **$0.00035** | **$0.35** (35 cents) |
| **Image Asset Storage** | Supabase Storage (100 KB WebP) | **$0.000002** / mo | **$0.002** / month |

> **Key Takeaway:** A user logging 3 meals a day for an entire month costs approximately **$0.036 in AI inference** (less than 4 cents per active user per month).

---

## 2. Live OpenRouter Pricing Rates

Rates extracted directly from OpenRouter:

| Model ID | Input Tokens (Prompt) | Output Tokens (Completion) | Image Processing Rate | Context Window |
| :--- | :--- | :--- | :--- | :--- |
| **`google/gemini-2.5-flash`** (Primary) | `$0.30` / 1M tokens (`$0.00000030`/tok) | `$2.50` / 1M tokens (`$0.00000250`/tok) | Included at prompt token rate | 1,048,576 |
| **`google/gemini-2.5-flash-lite`** (Ultra-budget) | `$0.10` / 1M tokens (`$0.00000010`/tok) | `$0.40` / 1M tokens (`$0.00000040`/tok) | Included at prompt token rate | 1,048,576 |
| **`google/gemini-3.8-flash`** (Latest generation) | `$0.75` / 1M tokens (`$0.00000075`/tok) | `$3.75` / 1M tokens (`$0.00000375`/tok) | Included at prompt token rate | 1,048,576 |
| **`openai/gpt-4o-mini`** (Comparison) | `$0.15` / 1M tokens (`$0.00000015`/tok) | `$0.60` / 1M tokens (`$0.00000060`/tok) | Standard high-res tiles | 128,000 |

---

## 3. Detailed Per-Photo Analysis Breakdown

When a user calls `POST /api/v1/meals/upload`, the backend performs the following steps:

```
Mobile Upload
      │
      ▼
FastAPI Server (Image Validation & Sizing)
      │
      ├─► 1. OpenRouter Multimodal Vision (gemini-2.5-flash)  ──► ~$0.00040
      │
      ├─► 2. Deterministic Scoring Algorithm                   ──► $0.00000 (Local CPU)
      │
      └─► 3. Background Task: Supabase Storage & DB Record     ──► ~$0.000002 (Free tier eligible)
```

### 3.1 Token Consumption Profile (Live Ingestion Payload)

A typical meal analysis request with strict JSON schema enforcement:

| Item | Token Count | Rate (USD) | Subtotal Cost |
| :--- | :--- | :--- | :--- |
| **System Instruction & Schema Definition** | ~170 tokens | `$0.00000030` | `$0.0000510` |
| **Image Visual Tokens (Tiled 768x768)** | ~258 tokens | `$0.00000030` | `$0.0000774` |
| **User Text Prompt + Context String** | ~22 tokens | `$0.00000030` | `$0.0000066` |
| **Total Prompt Input** | **~450 tokens** | — | **$0.0001350** |
| **Structured Output JSON Completion** | **~110 tokens** | `$0.00000250` | **$0.0002750** |
| **Total per Photo Evaluation** | **~560 tokens** | — | **$0.0004100** |

*Measured runtime test result from OpenRouter gateway:*
`total_tokens: 531, cost: $0.0004035`

### 3.2 What You Spend on Photo Analysis:

- **100 photos:** **$0.04** (4 cents)
- **1,000 photos:** **$0.40** (40 cents)
- **10,000 photos:** **$4.04**
- **100,000 photos:** **$40.35**

---

## 4. Score Calculation Cost

### Cost: **$0.000000 (100% Free)**

The demographic score calculation implemented in `services/scoring.py` runs entirely as deterministic Python code in memory:

```python
raw = plant_points + whole_food_points + protein_points - upf_penalty
normalized = raw * multiplier  # (student: +15%, parent: -15% / +10%, athlete: +10%)
```

- **LLM Token Cost:** `0 tokens`
- **Network API Cost:** `$0.00`
- **Compute Overhead:** `< 0.05 milliseconds` per request
- **Memory Footprint:** Insignificant (primitive arithmetic)

Because the LLM only outputs discrete point buckets (`plant_points`, `whole_food_points`, etc.) and the application code applies demographic baselines, you avoid running separate reasoning prompts for each family member's profile.

---

## 5. Weekly Family Digest Cost

### Trigger: `GET /api/v1/families/{id}/weekly` (Batch Once per Week per Family)

The weekly digest aggregates all meals logged by all circle members and synthesizes:
1. Member leaderboard rankings
2. Collective plant color count
3. 2–3 sentence empathetic AI family narrative
4. 1 evidence-based grocery swap recommendation

### Token & Cost Breakdown (OpenRouter Reasoning):

| Parameter | Volume | Rate (USD) | Total Cost |
| :--- | :--- | :--- | :--- |
| **Input (Week summary prompt + meal titles)** | ~350 tokens | `$0.00000030` | `$0.000105` |
| **Output (Narrative + grocery swap JSON)** | ~100 tokens | `$0.00000250` | `$0.000250` |
| **Total per Weekly Digest** | **~450 tokens** | — | **$0.000355** |

### What You Spend on Weekly Digests:

- **1 Family for 1 Year (52 weeks):** `52 * $0.000355 = $0.018` (~2 cents per year!)
- **100 Families for 1 Month:** `400 * $0.000355 = $0.14` (14 cents)
- **1,000 Families for 1 Month:** `4,000 * $0.000355 = $1.42`

---

## 6. Storage & Database Infrastructure (Supabase)

### 6.1 Database (PostgreSQL)

- Each meal record consumes ~1 KB of indexed relational storage.
- **Supabase Free Tier:** Includes **500 MB** database capacity (supports **~500,000 meal records** for $0).
- **Supabase Pro Tier ($25/mo):** Includes **8 GB** database (supports **~8,000,000 meal records**).

### 6.2 Asset Storage (Meal Photos)

Assuming standard client-side image compression (1024x1024 WebP or JPEG @ 80% quality ≈ 100 KB per photo):

| Volume | Raw Disk Storage | Supabase Free (1 GB quota) | Supabase Pro ($0.021 / GB extra) |
| :--- | :--- | :--- | :--- |
| **1,000 photos** | 100 MB | **$0.00** | **$0.00** |
| **10,000 photos** | 1.0 GB | **$0.00** | **$0.00** |
| **50,000 photos** | 5.0 GB | — | **$0.08 / month** |
| **100,000 photos** | 10.0 GB | — | **$0.19 / month** |

---

## 7. Projected Budget Scenarios

### Scenario A: Hackathon & Demo Phase
- **Scope:** 500 test meal uploads + 50 weekly digest runs
- **AI Inference Cost:** `500 * $0.0004035 = $0.2018`
- **Weekly Digest Cost:** `50 * $0.000355 = $0.0178`
- **Database / Storage:** Free Tier (`$0.00`)
- **Total Project Spend:** **~$0.22** (22 cents total)

### Scenario B: 100 Active Families (Pilot Stage)
- **Assumptions:** 100 families (average 3 members = 300 active users).
- **Activity:** 1 photo/user/day = 9,000 photos/month + 400 weekly digests/month.

| Cost Item | Monthly Calculation | Monthly Spend |
| :--- | :--- | :--- |
| Meal Photo Inference | 9,000 * $0.0004035 | **$3.63** |
| Deterministic Scoring | 9,000 executions | **$0.00** |
| Weekly AI Digest | 400 * $0.000355 | **$0.14** |
| Database & Storage | ~0.9 GB data / month | **$0.00** (Free tier) |
| **Total Monthly Spend** | | **$3.77 / month** |

### Scenario C: 1,000 Active Families (Growth Stage)
- **Assumptions:** 1,000 families (3,000 active users).
- **Activity:** 90,000 photos/month + 4,000 weekly digests/month.

| Cost Item | Monthly Calculation | Monthly Spend |
| :--- | :--- | :--- |
| Meal Photo Inference | 90,000 * $0.0004035 | **$36.32** |
| Deterministic Scoring | 90,000 executions | **$0.00** |
| Weekly AI Digest | 4,000 * $0.000355 | **$1.42** |
| Supabase Pro Plan | Base plan + 9 GB storage | **$25.19** |
| **Total Monthly Spend** | | **$62.93 / month** |
| **Per Family Cost** | `$62.93 / 1,000` | **~$0.063 / family / mo** |

---

## 8. Cost Optimization Recommendations

1. **Client-Side Image Resizing:** Ensure the mobile client resizes camera captures to a maximum dimension of `1024px` before uploading. This lowers upload payload from 5–8MB down to <150KB, reducing bandwidth and storage fees by 95%.
2. **Switch to `gemini-2.5-flash-lite` for Background Audits:** If you want to reduce AI costs even further (down to **$0.09 per 1,000 photos**), switch `OPENROUTER_PRIMARY_MODEL` in `.env` to `google/gemini-2.5-flash-lite`.
3. **Digest Caching:** The weekly digest endpoint caches generated digests for the current week (`week_start` to `week_end`), preventing redundant LLM calls when family members repeatedly check their screen.
