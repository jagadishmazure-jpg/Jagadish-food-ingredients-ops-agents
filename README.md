# Jagadish-food-ingredients-ops-agents

End-to-end food-ingredient R&D operations: an agent that ranks ingredient
substitutions for label claims, tracks formulation trial cycles, answers
R&D questions over controlled records — with citations, confirmation
gates, and a hash-chained audit trail.

> **Sibling repo.** For the deeper, Microsoft Agent Framework-based
> multi-agent system (R&D formulation, supply chain, ESG, customer advisor
> agents, FastAPI service, Azure IaC), see
> [Jagadish-food-ingredients-agentic-ai](https://github.com/jagadishmazure-jpg/Jagadish-food-ingredients-agentic-ai).
> This repo is the operations-focused FDE showcase on the same domain.

> **Recruiter summary.** Reformulating a product for "clean label" or
> "reduced sugar" means trading functional match, cost, and label impact
> on every swap. This repo models that end-to-end: synthetic R&D telemetry
> on SQLite, text-to-SQL over read-only views, a substitution engine
> that prints its math (date paste 0.8559 vs stevia 0.5865 for a
> reduced-sugar brief), and a trial tracker with per-criterion failing
> lists (F-CLEAN-01: 3 cycles, texture the blocker). 57 tests, all green.

All data is synthetic and fictional (Verdant Pantry Foods, an invented
manufacturer). No real brands appear anywhere in this repo. This project
is independent and unaffiliated with any food company.

## Problem → approach → outcome

**Problem.** R&D teams juggle three questions at once: which substitute
ingredient actually works, what it costs, and whether the label claim
survives. Answers live across formula sheets, trial logs, and spec docs.

**Approach.** One agent over one synthetic-but-faithful data model:
- 5 natural-language intents → fixed SQL templates → SELECT-only gateway
  (cited rule IDs SEC-SELECT-01/02/03) → 4 read-only views
- Substitution engine: 0.50·functional match + 0.30·cost position +
  0.20·label impact, per-option breakdown, sub-0.50 candidates rejected
  (SUB-FUNC-01/02, SUB-COST-01, SUB-LABEL-01)
- Trial tracker: pass/fail criteria per batch, pass rates, failing
  criteria, reformulation-cycle analytics
- TF-IDF SOP retrieval with citations and explicit not-found;
  ingredient-price feed with fake backend and an honest live gap
- T1–T4 escalation; formula approvals and label-claim sign-offs are
  confirmation-gated; hash-chained audit; PII-scrubbed feedback

**Outcome.** Real run on the seeded data: for "cane sugar → reduced
sugar", date paste ranks first (0.8559: cost +2.20/kg, label improves)
over stevia extract (0.5865: cost +26.80/kg). F-CLEAN-01 ran 3 trial
cycles (2 pass, texture the failing criterion). Two formulations
currently in trial.

## How this differs from coldchain/retail

The cold-chain repo tracks reefer telemetry and temperature compliance;
the retail repo tracks stores, SKUs, and promotions. This repo models
**R&D formulation work**: nothing here exists in those repos — the
substitution engine with auditable scoring, the trial-cycle tracker with
per-criterion pass/fail, label-claim definitions with sign-off rules,
and an ingredient price signal. The shared spine (gateway, RAG,
orchestrator, audit, feedback) is the same engineering; the domain logic
is entirely food-ingredient R&D.

## Quickstart

```bash
python -m pytest tests/ -q          # 57 tests, stdlib only
pip install streamlit               # optional, demo only
streamlit run demo/app.py
```

```python
from fooding.telemetry import build_db
from fooding.views import create_views
from fooding import substitute

conn = build_db(); create_views(conn)
opts = substitute.rank_substitutes(conn, "cane sugar", "reduced sugar")
print(opts[0]["breakdown"])
```

Real output:

```
date paste: 0.50*0.82(func) + 0.30*0.82(cost) + 0.20*1.00(label) = 0.8559; cost delta +2.20/kg; label improves
```

## Module table

| Module | What it does |
|---|---|
| `telemetry.py` | Seeded SQLite: ingredients, formulations, trials, substitutions, claims |
| `views.py` | 4 read-only views + SELECT-only gateway (SEC-SELECT-01/02/03) |
| `text2sql.py` | 5 intents, fixed templates, one retry → escalation |
| `substitute.py` | Substitution engine, cited rules SUB-FUNC/COST/LABEL |
| `trials.py` | Trial tracker: validation, summaries, cycle analytics |
| `pricesignal.py` | Price feed: fake seeded / live gap |
| `sop_rag.py` | TF-IDF SOP retrieval with citations |
| `orchestrator.py` | ReAct planner, multi-intent fan-out, audited turns |
| `escalation.py` | T1–T4 tiers, confirmation gates |
| `audit.py` | Hash-chained log with tamper detection |
| `feedback.py` / `pii.py` | Thumbs/corrections, PII scrubbed before storage |
| `demo_helpers.py` | Stdlib logic behind the Streamlit demo |

## Guardrails and security controls

- SELECT-only gateway: write keywords rejected even inside statements;
  string literals stripped before the scan (no false positives); 100-row cap
- Only the four published views may be queried — raw base tables, comma-join
  smuggling, quoted `sqlite_master`, and comment-obfuscated names are denied
  by a SQLite authorizer backstop (`fooding/authz.py`); see
  `docs/adr/0001-sqlite-authorizer-backstop.md`
- Gateway and escalation errors never echo raw row data
- Formula approvals and label-claim sign-offs are confirmation-gated (T4)
- Feedback free text PII-scrubbed before it reaches the audit log
- Threat model: `docs/threat-model.md`

## Limitations and known failures

- Substitution weights (0.50/0.30/0.20) are a starting point — calibrate
  against historical swaps before trusting the ranking (see
  `docs/implementation-guide.md`).
- Trial pass bars (sensory/texture ≥ 6) are demo-simple; real panels use
  statistical cutoffs.
- TF-IDF retrieval suits 4 SOPs; past a few dozen documents it needs
  embeddings.
- The live price feed is a stub that reports a gap; wire a real source
  before relying on it.

## Built / Written-not-run / Planned

| Item | Status |
|---|---|
| Synthetic R&D telemetry + 4 views + gateway | Built |
| 5 text-to-SQL intents | Built |
| Substitution engine with auditable scoring | Built |
| Trial tracker + cycle analytics | Built |
| SOP RAG with citations | Built |
| Price signal (fake) + live gap | Built |
| T1–T4 escalation + confirmation gates | Built |
| Hash-chained audit | Built |
| PII-scrubbed feedback | Built |
| Streamlit demo | Built (demo only; `pip install streamlit`) |
| Live price vendor integration | Planned |
| Weight calibration against historical swaps | Planned |
| Deployment | Planned (nothing deployed) |

## Related repos

Part of a 12-domain end-to-end showcase series sharing one agentic
spine: cold-chain logistics, retail ops, healthcare ops, insurance
underwriting, warehouse ops, energy grid, telecom incident, airline
disruption, pharma QA, predictive maintenance, marketplace seller.
Each repo documents how its domain logic differs.

## Knowledge

- [Domain notes](knowledge/domain-notes.md) — how food-ingredient R&D works
- [Architecture](knowledge/architecture.md) — Mermaid diagram
