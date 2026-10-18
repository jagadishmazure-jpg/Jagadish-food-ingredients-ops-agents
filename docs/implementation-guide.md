# Implementation guide

How to adopt this repo's patterns in a real R&D org.

## Data model first
The six tables (`ingredients`, `formulations`,
`formulation_ingredients`, `trials`, `substitutions`, `claims`) mirror
how R&D actually records work: formulas reference ingredient
percentages, trials reference formula versions, substitutions are
first-class records (not chat text). Start here — the agent is only as
good as the records.

## Substitution scoring weights
The 0.50/0.30/0.20 weights are a starting point, not science. Calibrate
them against historical swaps: for each past substitution, check whether
the engine would have ranked the actually-chosen ingredient first. If
not, adjust weights per claim type (cost matters more for value-tier
products, label impact more for premium clean-label lines).

## Trial criteria
The pass bar (sensory ≥ 6, texture ≥ 6, shelf met, micro clear) is a
demo simplification. Real panels use hedonic scales with statistical
cutoffs and accelerated shelf-life models. Keep the criterion-level
breakdown — it is what makes failures actionable.

## Gateway rules travel
SEC-SELECT-01/02/03 are deliberately database-agnostic. The same three
rules (SELECT-only, literal-stripped keyword scan, row cap) apply
unchanged against a real warehouse — only the view definitions change.

## What to wire for production
- Replace `FakePriceFeed` with a vendor API client; keep the explicit
  `SignalGap` so missing data is visible, never silent.
- Put the confirmation gates behind your identity provider; the
  `approver` callable is the seam.
- Stream audit entries to your SIEM; the hash chain gives you
  tamper evidence per batch.
