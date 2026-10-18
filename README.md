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
>
> **Boundary.** Both repos suggest substitutions, differently. The
> original maps each flagged non-clean-label ingredient to a preferred
> clean-label swap (fixed demo map, cost-sorted fallback) inside a
> multi-agent reformulation graph that *predicts* texture and shelf life
> and *estimates* cycle time. This repo ranks several candidates per claim
> brief with a weighted, floor-gated score (SUB-FUNC/CLAIM/COST/LABEL) and
> *records* actual pilot-trial outcomes against SOP-03 criteria. It has no
> supply-chain, ESG or customer-advisor agents, no FastAPI service and no
> cloud infrastructure.

> **Recruiter summary.** Reformulating a product for "clean label" or
> "reduced sugar" means trading functional match, cost, and label impact
> on every swap. This repo models that end-to-end: synthetic R&D telemetry
> on SQLite, text-to-SQL over read-only views, a substitution engine
> that prints its math (date paste 0.8559 vs stevia 0.5865 for a
> reduced-sugar brief), and a trial tracker with per-criterion failing
> lists (F-CLEAN-01: 3 cycles, texture the blocker). Test count below,
> checked by CI.

All data is synthetic and fictional (Glinthaven Foods, an invented
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
python -m pytest tests/ -q          # full suite, stdlib only
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
- Only the four published views may be queried. Independently of the text
  check, the SQLite authorizer (`fooding/authz.py`) allows a base-table
  read only on behalf of a published view, so raw tables named directly
  (comma joins, quoted or parenthesised names, comment tricks) are denied,
  and `sqlite_master`, writes and `load_extension` always are; see
  `docs/adr/0001-sqlite-authorizer-backstop.md`
- Gateway and escalation errors never echo raw row data
- Formula approvals and label-claim sign-offs are confirmation-gated (T4)
- Feedback free text PII-scrubbed (email, phone, SSN, card, account) before it reaches the audit log
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
- Stage changes are not derived from trials: SOP-01's "two consecutive
  passes to approve, three same-criterion fails or two micro fails to
  reject" is not enforced. The seeded F-LEG-01 is "rejected" after one
  micro failure because the seed data says so.
- SUB-CLAIM-01 checks only what the ingredient table records (clean-label
  flag, milk allergen). Reduced-sugar and high-protein thresholds need
  nutrition data this repo does not have.
- Gateway: the authorizer allows an empty-column read of a table behind a
  view (needed for view self-joins), so `SELECT count(*)` of such a table
  returns a count if the text check is bypassed; no column data is
  readable.

## Standardization review (2026-10-18)

grokbot-portfolio reviewed this repo against the portfolio standard. Each
bug below has a regression test (`tests/test_fooding.py`, "review fixes"
section, and `tests/test_authorizer_strict.py`) that fails on the old code.

- **Gateway bypass.** The literal stripper also removed double-quoted
  text, but double quotes are identifiers in SQLite, so
  `SELECT * FROM "ingredients"` passed the FROM check; `FROM (ingredients)`
  and `FROM (v_cost_impact), ingredients` passed too. The authorizer
  allowed every table behind a view, so all of these read the raw table.
  The text check now sees quoted and parenthesised names, and the
  authorizer allows a base-table read only on behalf of a published view
  (ADR 0001, revision).
- **The default demo question returned nothing.** "Suggest substitutes for
  cane sugar for reduced sugar" searched for an ingredient named "cane
  sugar for reduced sugar". The claim is now parsed as a filter.
- **Trial records could contradict SOP-03.** `record_trial` accepted
  `outcome="pass"` with the micro panel failed or sensory below 6. The
  outcome must now match the criteria (TRIAL-OUTCOME-01).
- **Substitutes were not checked against the claim.** A candidate whose
  own ingredient record breaks the target claim (not clean label, or a
  milk allergen under "dairy free") could rank first. It is now rejected
  (SUB-CLAIM-01). The seeded candidates all pass, so the seed ranking is
  unchanged (date paste 0.8559, stevia 0.5865).
- Card numbers are now redacted alongside email, phone, SSN and account.
- The fictional manufacturer name matched real small food businesses; it
  is now Glinthaven Foods.

Differentiator on the seeded data (regenerated and checked by CI on every push):

<!-- run: python scripts/show_differentiator.py -->
```text
Substitutes for cane sugar under 'reduced sugar':
  date paste: 0.50*0.82(func) + 0.30*0.82(cost) + 0.20*1.00(label) = 0.8559; cost delta +2.20/kg; label improves
  stevia leaf extract: 0.50*0.61(func) + 0.30*0.27(cost) + 0.20*1.00(label) = 0.5865; cost delta +26.80/kg; label improves
Demo question -> 2 rows: ['date paste', 'stevia leaf extract']
Trial tracker (SOP-03 criteria):
  F-CLEAN-01: 2/3 passed, failing criteria ['texture']
  F-SUGAR-01: 1/2 passed, failing criteria ['sensory']
  F-PRO-01: 2/2 passed, failing criteria []
  F-LEG-01: 0/1 passed, failing criteria ['micro']
  record 'pass' with micro failed -> TRIAL-OUTCOME-01: outcome 'pass' contradicts the SOP-03 criteria (sensory 8, texture 8, shelf_ok 1, micro_ok 0 -> fail)
Gateway: SELECT * FROM "ingredients" -> SEC-SELECT-03: only published views may be queried, blocked: ['ingredients']
```
<!-- /run -->

Test count (also checked by CI):

<!-- run: python scripts/count_tests.py -->
```text
109 tests collected
```
<!-- /run -->

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
| CI: ruff, pytest, docs drift check, hashed brand check, gitleaks; CodeQL; Dependabot | Built (runs on every push) |
| Live price vendor integration | Planned |
| Weight calibration against historical swaps | Planned |
| Deployment | Planned (nothing deployed) |

## Related repos

Part of a 12-domain end-to-end showcase series sharing one agentic
spine: cold-chain logistics, retail ops, healthcare ops, insurance
underwriting, warehouse ops, energy grid, telecom incident, airline
disruption, pharma QA, predictive maintenance, marketplace seller,
property ops, contract lifecycle.
Each repo documents how its domain logic differs.

## Knowledge

- [Domain notes](knowledge/domain-notes.md) — how food-ingredient R&D works
- [Architecture](knowledge/architecture.md) — Mermaid diagram
