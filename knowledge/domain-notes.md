# Domain notes — food-ingredient R&D operations

Fictional setting: Verdant Pantry Foods, an invented manufacturer.
No real brands appear anywhere in this repo.

## What R&D actually does here

1. **Formulation development.** A product brief (e.g. "clean-label oat
   bar") becomes a draft formula: ingredients at percentages, each
   chosen for functional properties — sweetness, binding, moisture,
   shelf-life contribution, emulsification.
2. **Reformulation for claims.** When marketing wants "reduced sugar" or
   "clean label", R&D swaps ingredients. Every swap trades three things
   against each other: functional match (does it still taste/bind/keep?),
   cost delta per kg, and label impact (does the claim get stronger?).
3. **Trial cycles.** Pilot batches are mixed and scored on four criteria:
   sensory (0–10), texture (0–10), shelf-life target, micro panel. A
   batch passes only if all four clear. Failing batches name the
   criterion and the suspected cause; the formula is tweaked and the
   cycle repeats. Three failures on one criterion sends the formula
   back to draft.
4. **Label compliance.** Claims have definitions (clean label = no
   artificial preservatives/colors/flavors; reduced sugar = ≥25% less
   sugar than reference; high protein = ≥10 g/serving; dairy free = no
   milk-derived ingredients). A claim prints only after a label
   specialist verifies the formula — and any later ingredient change
   voids the claim until re-verified.

## Why this is the differentiator

Generic agent scaffolds stop at "answer questions over a database".
This repo adds the two judgments R&D scientists actually make:
ranking substitute ingredients with a transparent, auditable score,
and tracking trial cycles so reformulation progress is measurable.
Both are real, tested modules — not prompt text.
