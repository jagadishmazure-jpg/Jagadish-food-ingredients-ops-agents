# Interview points

- **The differentiator, in one line:** an ingredient-substitution engine
  that ranks swaps by functional match, cost delta, and label impact with
  a per-option breakdown you can audit — e.g. date paste scores 0.8559
  vs stevia 0.5865 for a reduced-sugar brief, and the math is printed.
- **Why the score is transparent:** every option carries its breakdown
  string (`0.50*0.82(func) + 0.30*0.82(cost) + 0.20*1.00(label)`), cost
  deltas are always per-kg and never netted, label impact is explicit.
  A scientist can disagree with the weights — they can't be misled.
- **Trial cycles as a metric:** pass rate per formulation plus
  per-criterion failing lists turn "reformulation is hard" into
  measurable cycle analytics (F-CLEAN-01: 3 cycles, texture the blocker).
- **Guardrails that matter here:** formula approvals and label-claim
  sign-offs are confirmation-gated (T4); the SQL gateway is SELECT-only
  with literal-stripped keyword scanning; feedback PII is scrubbed
  before storage.
- **Honest gaps:** the live price feed is a stub with an explicit gap;
  TF-IDF retrieval suits 4 SOPs; trial pass bars are demo-simple.
