"""Read-only views over the R&D telemetry plus a SELECT-only SQL gateway.

Rule IDs (cited in tests and README):
  SEC-SELECT-01: only statements starting with SELECT (after stripping
                 comments/whitespace) are executed.
  SEC-SELECT-02: write keywords (INSERT/UPDATE/DELETE/DROP/ALTER/...) are
                 rejected even when hidden inside the statement — string
                 literals are stripped before the scan so 'UPDATE' inside a
                 quoted value does not false-positive.
  SEC-SELECT-03: every query is capped at 100 rows AND may only touch the
                 published views. The SQLite authorizer (fooding/authz.py)
                 enforces this independently of the text check: a base table
                 is readable only on behalf of a published view, never when
                 named directly (comma joins, quoted or parenthesised names,
                 comment tricks), and sqlite_master, writes and
                 load_extension are always denied. Denied access raises
                 GatewayError citing this rule.
"""

from __future__ import annotations

import re
import sqlite3

from .authz import views_only

ROW_CAP = 100

_WRITE_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|replace|merge|grant|revoke|exec|execute|call)\b",
    re.IGNORECASE,
)

_VIEWS = {
    "v_formulations": """
        SELECT f.form_id, f.product, f.status, f.target_claim, f.version,
               f.cost_per_kg,
               (SELECT COUNT(*) FROM trials t WHERE t.form_id = f.form_id) AS n_trials,
               (SELECT COUNT(*) FROM trials t
                 WHERE t.form_id = f.form_id AND t.outcome = 'pass') AS n_pass
        FROM formulations f
    """,
    "v_trial_outcomes": """
        SELECT t.trial_id, t.form_id, t.batch_no, t.outcome,
               t.sensory, t.texture, t.shelf_ok, t.micro_ok, t.notes
        FROM trials t
    """,
    "v_substitutions": """
        SELECT s.sub_id, s.original_ing AS original, s.substitute_ing AS substitute,
               s.target_claim, s.func_match, s.cost_delta, s.label_impact
        FROM substitutions s
    """,
    "v_cost_impact": """
        SELECT i.name, i.category, i.cost_per_kg,
               CASE WHEN i.clean_label = 1 THEN 'yes' ELSE 'no' END AS clean_label,
               i.allergen
        FROM ingredients i
    """,
}


def create_views(conn: sqlite3.Connection) -> None:
    for name, sql in _VIEWS.items():
        conn.execute(f"CREATE VIEW IF NOT EXISTS {name} AS {sql}")
    conn.commit()


def _strip_literals(sql: str) -> str:
    """Remove single-quoted string literals so keyword scans don't false-positive.

    Double quotes are identifiers in SQLite (``FROM "ingredients"`` names a
    table), so they are kept for the FROM check to see.
    """
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def _first_keyword(sql: str) -> str:
    """First SQL keyword after stripping leading whitespace and -- comments."""
    rest = sql.lstrip()
    while rest.startswith("--"):
        rest = rest.split("\n", 1)[1] if "\n" in rest else ""
        rest = rest.lstrip()
    m = re.match(r"([A-Za-z]+)", rest)
    return m.group(1).upper() if m else ""


def _strip_comments(sql: str) -> str:
    """Remove -- line comments and /* */ block comments."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", " ", sql)


_FROM_JOIN = re.compile(r"\b(?:FROM|JOIN)\b", re.IGNORECASE)

_CLAUSE_END = re.compile(
    r"\b(WHERE|GROUP\s+BY|ORDER\s+BY|LIMIT|OFFSET|UNION|INTERSECT|EXCEPT|HAVING|WINDOW)\b",
    re.IGNORECASE,
)

_TABLE_IDENT = re.compile(r'\(*\s*["`\[]?([A-Za-z_][\w]*)["`\]]?')


def _referenced_tables(sql: str) -> set[str]:
    """Table names appearing in FROM/JOIN clauses.

    Literals and comments are stripped first so ``FROM/**/trials`` and
    ``FROM "trials"`` are seen for what they are. Comma joins
    (``FROM v, trials``) are split so every table is checked, not just
    the first. Quoted identifiers are unquoted before comparison.
    """
    cleaned = _strip_comments(_strip_literals(sql))
    tables: set[str] = set()
    for m in _FROM_JOIN.finditer(cleaned):
        rest = cleaned[m.end():]
        end = _CLAUSE_END.search(rest)
        segment = rest[:end.start()] if end else rest
        # Don't run past a subquery boundary or statement end; inner
        # FROMs are found by the finditer on its own pass.
        for cut in (")", ";"):
            idx = segment.find(cut)
            if idx != -1:
                segment = segment[:idx]
        for part in segment.split(","):
            tm = _TABLE_IDENT.match(part.strip())
            if tm and tm.group(1).lower() not in ("select", "with", "values"):
                tables.add(tm.group(1).lower())
    return tables


class GatewayError(Exception):
    pass


def run_query(conn: sqlite3.Connection, sql: str):
    """Execute read-only SQL. Raises GatewayError on any rule violation."""
    cleaned = sql.strip()
    if _first_keyword(cleaned) != "SELECT":
        raise GatewayError("SEC-SELECT-01: only SELECT statements are allowed")
    if _WRITE_KEYWORDS.search(_strip_literals(cleaned)):
        raise GatewayError("SEC-SELECT-02: write keywords are not allowed")
    allowed_views = {v.lower() for v in _VIEWS}
    bad = _referenced_tables(cleaned) - allowed_views
    if bad:
        raise GatewayError(
            f"SEC-SELECT-03: only published views may be queried, "
            f"blocked: {sorted(bad)}"
        )
    try:
        with views_only(conn, allowed_views) as denied:
            cur = conn.execute(cleaned)
            # Row cap is enforced at fetch time (fetchmany), never by trusting
            # the query's own LIMIT — LIMIT 100000, LIMIT n OFFSET m, and
            # LIMIT inside subqueries all bypass LIMIT-rewriting.
            rows = cur.fetchmany(ROW_CAP)  # SEC-SELECT-03
    except sqlite3.DatabaseError as e:
        if denied:
            raise GatewayError(
                f"SEC-SELECT-03: denied by authorizer: {sorted(set(denied))}") from e
        raise GatewayError(f"SEC-SELECT-01: query failed ({e})") from e
    cols = [d[0] for d in cur.description] if cur.description else []
    return cols, [dict(zip(cols, r)) for r in rows]
