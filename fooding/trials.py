"""Formulation trial tracker (domain differentiator #2).

Trial batches carry pass/fail criteria (sensory, texture, shelf-life,
micro). The tracker validates trial records, summarizes pass rates with
per-criterion breakdowns, and computes reformulation-cycle analytics:
how many trial cycles a formulation needed to reach approval.
"""

from __future__ import annotations

import sqlite3


class TrialError(Exception):
    pass


def record_trial(conn: sqlite3.Connection, form_id: str, batch_no: str,
                 outcome: str, sensory: int, texture: int,
                 shelf_ok: int, micro_ok: int, notes: str = "") -> str:
    """Insert a trial record. Returns the trial_id. Validates inputs."""
    if outcome not in ("pass", "fail"):
        raise TrialError(f"outcome must be pass/fail, got {outcome!r}")
    for label, v in (("sensory", sensory), ("texture", texture)):
        if not isinstance(v, int) or not 0 <= v <= 10:
            raise TrialError(f"{label} must be an int 0-10, got {v!r}")
    for label, v in (("shelf_ok", shelf_ok), ("micro_ok", micro_ok)):
        if v not in (0, 1):
            raise TrialError(f"{label} must be 0/1, got {v!r}")
    if not conn.execute(
            "SELECT 1 FROM formulations WHERE form_id = ?", (form_id,)).fetchone():
        raise TrialError(f"unknown formulation {form_id!r}")
    cur = conn.execute("SELECT COUNT(*) FROM trials WHERE form_id = ?", (form_id,))
    trial_id = f"T-{form_id}-{cur.fetchone()[0] + 1:03d}"
    conn.execute(
        """INSERT INTO trials
           (trial_id, form_id, batch_no, outcome, sensory, texture,
            shelf_ok, micro_ok, notes)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (trial_id, form_id, batch_no, outcome, sensory, texture,
         shelf_ok, micro_ok, notes),
    )
    conn.commit()
    return trial_id


def trial_summary(conn: sqlite3.Connection, form_id: str) -> dict:
    """Pass rate + per-criterion breakdown for one formulation."""
    rows = conn.execute(
        """SELECT outcome, sensory, texture, shelf_ok, micro_ok
           FROM trials WHERE form_id = ?""", (form_id,)).fetchall()
    if not rows:
        raise TrialError(f"no trials recorded for {form_id!r}")
    n = len(rows)
    n_pass = sum(1 for r in rows if r[0] == "pass")
    failing = []
    if any(r[2] < 6 for r in rows):
        failing.append("texture")
    if any(r[1] < 6 for r in rows):
        failing.append("sensory")
    if any(r[3] == 0 for r in rows):
        failing.append("shelf_life")
    if any(r[4] == 0 for r in rows):
        failing.append("micro")
    return {
        "form_id": form_id,
        "n_trials": n,
        "n_pass": n_pass,
        "pass_rate": round(n_pass / n, 4),
        "avg_sensory": round(sum(r[1] for r in rows) / n, 2),
        "avg_texture": round(sum(r[2] for r in rows) / n, 2),
        "failing_criteria": failing,
    }


def cycle_analytics(conn: sqlite3.Connection) -> list[dict]:
    """Reformulation cycles: trials run per formulation and whether it
    ever passed (a proxy for cycles-to-approval)."""
    out = []
    for (form_id, status) in conn.execute(
            "SELECT form_id, status FROM formulations ORDER BY form_id"):
        n = conn.execute(
            "SELECT COUNT(*) FROM trials WHERE form_id = ?", (form_id,)).fetchone()[0]
        n_pass = conn.execute(
            """SELECT COUNT(*) FROM trials
               WHERE form_id = ? AND outcome = 'pass'""", (form_id,)).fetchone()[0]
        out.append({
            "form_id": form_id,
            "status": status,
            "trial_cycles": n,
            "ever_passed": n_pass > 0,
        })
    return out
