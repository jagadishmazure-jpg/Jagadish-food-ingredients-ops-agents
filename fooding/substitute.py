"""Ingredient-substitution engine (domain differentiator #1).

For a target claim (e.g. "clean label", "reduced sugar"), ranks candidate
substitutes for an ingredient by functional match + cost delta + label
impact, with a per-option transparent breakdown.

Cited rules:
  SUB-FUNC-01: a candidate must share the requested target claim.
  SUB-FUNC-02: func_match below 0.50 is rejected — not a real substitute.
  SUB-COST-01: cost deltas are always reported per-kg, never hidden.
  SUB-LABEL-01: label impact is reported as improves/neutral/worsens.

Score = 0.50*func_match + 0.30*cost_score + 0.20*label_score, where
  cost_score  = 1 / (1 + max(0, cost_delta)/10)   (cheaper-or-equal -> 1.0)
  label_score = improves 1.0 / neutral 0.5 / worsens 0.0
"""

from __future__ import annotations

import sqlite3

_LABEL_SCORE = {"improves": 1.0, "neutral": 0.5, "worsens": 0.0}
_FUNC_FLOOR = 0.50  # SUB-FUNC-02


def _cost_score(cost_delta: float) -> float:
    return 1.0 / (1.0 + max(0.0, cost_delta) / 10.0)


def rank_substitutes(conn: sqlite3.Connection, original: str,
                     target_claim: str) -> list[dict]:
    """Rank substitutes for `original` under `target_claim`.

    Returns options sorted best-first, each with a breakdown string.
    Empty list when nothing qualifies (never guesses).
    """
    cur = conn.execute(
        """SELECT sub_id, substitute_ing, target_claim, func_match,
                  cost_delta, label_impact
           FROM substitutions
           WHERE lower(original_ing) = lower(?)
             AND lower(target_claim) = lower(?)""",
        (original.strip(), target_claim.strip()),
    )
    options = []
    for sub_id, sub, claim, func_match, cost_delta, label_impact in cur:
        if func_match < _FUNC_FLOOR:  # SUB-FUNC-02
            continue
        cs = _cost_score(cost_delta)
        ls = _LABEL_SCORE.get(label_impact, 0.5)
        score = 0.50 * func_match + 0.30 * cs + 0.20 * ls
        options.append({
            "sub_id": sub_id,
            "substitute": sub,
            "func_match": func_match,
            "cost_delta_per_kg": cost_delta,  # SUB-COST-01: always surfaced
            "label_impact": label_impact,     # SUB-LABEL-01: always surfaced
            "score": round(score, 4),
            "breakdown": (
                f"{sub}: 0.50*{func_match:.2f}(func) + 0.30*{cs:.2f}(cost) "
                f"+ 0.20*{ls:.2f}(label) = {score:.4f}; "
                f"cost delta {cost_delta:+.2f}/kg; label {label_impact}"
            ),
        })
    options.sort(key=lambda o: o["score"], reverse=True)
    return options
