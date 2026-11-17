# CrimeMind (SRS v6.0) — working MVP

AI-assisted criminal-investigation **decision support** on a fully synthetic city. SQL-first, human-in-the-loop:
the AI never decides guilt, and every statement is labelled FACT / CORRELATED / INFERRED (AI output: RECORDED FACT / CORRELATED / AI-INFERRED / UNCERTAIN).

## Run
```
# PostgreSQL 16 running locally (postgres/postgres admin, see backend/app/config.py for env overrides)
./scripts/dev.sh            # init DB, seed synthetic world, start API :8000 and UI :5173
cd backend && python3 -m pytest tests -q      # 40 tests (use their own crimemind_test DB)
python3 -m synth.scenario list|next           # evolve evidence (GPS-17 fault, corrected access log, witness, retracted tip)
python3 -m synth.evaluate                     # Precision/Recall@K of Q40 vs isolated ground truth, stale-fact check
```
Demo users (password from `CM_DEMO_PASSWORD`, dev default `crimemind-demo`): `inv.asha` and `sup.rao` on CASE-2026-001, `inv.vikram` on CASE-2026-002, `admin`.
Set `CM_JWT_SECRET` in any real use. Copy `.env.example` to `.env` (git-ignored) and set `GEMINI_API_KEY` (model `gemini-3.6-flash`, override with `CM_GEMINI_MODEL`) or `ANTHROPIC_API_KEY` to enable a real model; `CM_AI_PROVIDER=auto|gemini|anthropic|offline` forces a choice. Without a key the **offline template provider** is used and is labelled as non-LLM. Every model's output goes through the same validator.

## Architecture
- **PostgreSQL**: case-scoped composite FKs, append-only history (triggers), EVLM validity lifecycle via `change_validity()` (SECURITY DEFINER) with a rules table, impact propagation to findings (RECOMPUTE_REQUIRED) and hypotheses (needs review), audit triggers. Ground truth lives in schema `gt`, unreadable by the app role `cm_app`.
- **SQL modules** (`backend/app/sql_modules`, 18 modules / 40 questions): registry-driven, bind parameters only, no dynamic SQL, `statement_timeout`, every run written to `query_audit`.
- **Correlation engine** (Python, versioned rules): FACT / CORRELATED / INFERRED with evidence links and uncertainties; explicit recompute, never silent.
- **Graph** built per request from the latest run; `/relationship-graph` and `/relationships` both served (Appendix D #3).
- **AI layer**: controlled context (authorised IDs only, untrusted text quoted) → provider → validator (schema, ID authorisation, classification rules, guilt/overreach checks). Failures are stored as INVALID/UNAVAILABLE and never shown as trusted.
- **Security**: JWT + bcrypt, roles, server-side case authorisation (unauthorised == nonexistent → identical 404, audited), least-privilege DB role, uniform error contract.
- **UI** (React/Vite): dashboard, entities, evidence with provenance + validity history + EVLM change panel, relationship graph (solid/dashed/dotted), question runner with module transparency, correlations + common link, AI panel, evidence-change queue, reports, audit.

## Added in round 2 (all deterministic, no language model)
- **Add data**: forms and API for evidence, entities, sightings, communications, transactions and relationships (`POST /api/cases/{ref}/evidence|entities|observations|communications|transactions|relationships`), plus all-or-nothing bulk import with dry run (`POST /api/cases/{ref}/import`, example in `backend/synth/example_import.json`). New records mark the correlation run stale; nothing is silently rewritten.
- **Cases and access**: `POST /api/cases` (supervisor/administrator), `GET/POST/DELETE /api/cases/{ref}/access`. Writes go through SECURITY DEFINER functions (migration 008); the app role still cannot touch `cases` or `user_case_access` directly.
- **Analysis tab** (`/api/cases/{ref}/insights/...`): movement plausibility (impossible speed / two places at once, with the sources involved), alibi checker, network metrics (betweenness, PageRank, communities, go-betweens), anomaly flags, money-trail tracing with pass-through detection, possible meetings.
- **Map**: offline SVG map of case locations with a per-person time-ordered trail and a time slider.
- **Notes and bookmarks**: append-only, audited, filterable by tag.

## Added in round 3
- **Ask for evidence** (`GET /api/cases/{ref}/evidence-search?q=...`, search box on the Evidence page): plain-language requests ("CCTV at the lawn", "calls by Rohit Sethi", "E-0042") return ranked evidence with *why it matched*. Case-scoped, audited, typo-tolerant.
- **RAG for the AI layer**: the same retriever adds the evidence relevant to the investigator's question to the controlled context (marked `retrieved`, still untrusted quoted text, citable only because it is in the authorised context). Works with the offline provider, Gemini and Anthropic; the validator is unchanged.
- **Gemini**: set `GEMINI_API_KEY` in `.env` (see `.env.example`).

## Deviations from the SRS (honest list)
- PostGIS/Oracle spatial replaced by haversine in SQL/Python (Appendix D #1); MongoDB not used.
- No CV/OCR/Whisper pipelines; no live LLM by default. Evidence retrieval (RAG) is lexical (BM25 + named-entity + reference matching), not embedding-based.
- Correlation rules run in Python over current-belief views rather than in SQL.
- Heuristic scores (reliability, Q40 association) are approved weights, not probabilities.
