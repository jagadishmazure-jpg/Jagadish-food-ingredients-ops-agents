"""Text-to-SQL: 5 fixed intents over the read-only views.

One simplified retry, then explicit escalation (EscalationNeeded) — never a
hallucinated query.
"""

from __future__ import annotations

import re
import sqlite3

from .views import run_query


class EscalationNeeded(Exception):
    pass


def _intents():
    return [
        # specific intents first (ordering matters — see tests)
        ("trial_pass_rates",
         re.compile(r"pass rate|trial outcomes|trials for", re.IGNORECASE),
         lambda q: _trial_pass_rates(q)),
        ("formulations_by_status",
         re.compile(r"formulation", re.IGNORECASE),
         lambda q: _formulations_by_status(q)),
        ("substitution_options",
         re.compile(r"substitut|swap|replace .* with", re.IGNORECASE),
         lambda q: _substitution_options(q)),
        ("cost_impact",
         re.compile(r"\bcost\b", re.IGNORECASE),
         lambda q: _cost_impact(q)),
        ("claim_coverage",
         re.compile(r"\bclaim\b", re.IGNORECASE),
         lambda q: _claim_coverage(q)),
    ]


def _formulations_by_status(q: str) -> str:
    m = re.search(r"\b(draft|in[-_ ]trial|approved|rejected)\b", q, re.IGNORECASE)
    status = (m.group(1).lower().replace("-", "_").replace(" ", "_")
              if m else "in_trial")
    return ("SELECT form_id, product, status, target_claim, version, cost_per_kg "
            f"FROM v_formulations WHERE status = '{status}'")


def _trial_pass_rates(q: str) -> str:
    m = re.search(r"\bF-[A-Z]+-\d+\b", q)
    if not m:
        raise EscalationNeeded("trial_pass_rates needs a formulation id like F-CLEAN-01")
    fid = m.group(0)
    return (f"SELECT outcome, COUNT(*) AS n FROM v_trial_outcomes "
            f"WHERE form_id = '{fid}' GROUP BY outcome")


def _substitution_options(q: str) -> str:
    m = re.search(r"for\s+([a-z][a-z \-]+?)(?:\?|$)", q, re.IGNORECASE)
    if m:
        ing = m.group(1).strip().lower()
        return ("SELECT sub_id, original, substitute, target_claim, func_match, "
                f"cost_delta, label_impact FROM v_substitutions "
                f"WHERE lower(original) LIKE '%{ing}%'")
    return ("SELECT sub_id, original, substitute, target_claim, func_match, "
            "cost_delta, label_impact FROM v_substitutions")


def _cost_impact(q: str) -> str:
    m = re.search(r"of\s+([a-z][a-z \-]+?)(?:\?|$)", q, re.IGNORECASE)
    if m:
        ing = m.group(1).strip().lower()
        return (f"SELECT name, category, cost_per_kg, clean_label FROM v_cost_impact "
                f"WHERE lower(name) LIKE '%{ing}%'")
    return "SELECT name, category, cost_per_kg, clean_label FROM v_cost_impact"


def _claim_coverage(q: str) -> str:
    m = re.search(r"(clean label|reduced sugar|high protein|dairy free)", q, re.IGNORECASE)
    claim = m.group(1).lower() if m else "clean label"
    return ("SELECT form_id, product, status, target_claim FROM v_formulations "
            f"WHERE lower(target_claim) = '{claim}'")


def answer(conn: sqlite3.Connection, question: str) -> dict:
    """Match one intent, run it, return rows. One retry, then escalate."""
    for name, pattern, build in _intents():
        if pattern.search(question):
            try:
                sql = build(question)
            except EscalationNeeded:
                # simplified retry: broaden once, then escalate for real
                try:
                    sql = _retry_broaden(name, question)
                except EscalationNeeded:
                    raise
            cols, rows = run_query(conn, sql)
            return {"intent": name, "sql": sql, "columns": cols, "rows": rows}
    raise EscalationNeeded(f"no intent matched: {question!r}")


def _retry_broaden(name: str, question: str) -> str:
    if name == "trial_pass_rates":
        return "SELECT form_id, outcome, COUNT(*) AS n FROM v_trial_outcomes GROUP BY form_id, outcome"
    raise EscalationNeeded(f"retry exhausted for intent {name}")
