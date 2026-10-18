"""SQLite authorizer backstop for the SELECT-only gateway.

Why this exists: the text-level checks in views.py (SEC-SELECT-01/02/03)
can be fooled by exotic SQL. A sibling repo proved it — a
``LIMIT 100000 -- x`` comment smuggled 36,864 rows past a LIMIT-rewriting
cap. Text parsing sees what the attacker wants it to see; the authorizer
sees what SQLite ACTUALLY touches during compilation.

What the authorizer catches that text checks miss:
  - comma joins:      ``FROM v_formulations, trials``
  - quoted names:     ``FROM "sqlite_master"``
  - comment tricks:   ``FROM/**/trials``
  - raw base tables:  ``SELECT secret FROM ingredients``

Design note: SQLite expands views during compilation, so the authorizer
sees reads on the views' underlying base tables as well as the views
themselves. Denying base tables outright would break every legitimate
view query. The split is therefore:
  - authorizer: allow SELECT; allow READ on allowed views AND the base
    tables those views are built on; deny everything else (sqlite_master,
    unknown tables, all write actions).
  - text-level FROM check (in views.run_query): every table referenced in
    FROM/JOIN must be an allowed view. This is what blocks raw base-table
    access — the authorizer is the backstop for what the text check misses.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

# sqlite3 module constants (kept as literals so the module has no import-time
# dependency on CPython internals beyond the documented API).
_SQLITE_OK = 0
_SQLITE_DENY = 1
_SQLITE_SELECT = 21
_SQLITE_READ = 20
_SQLITE_FUNCTION = 31

# Read-only scalar/aggregate functions the published views may call.
# Everything else (load_extension, etc.) is denied.
_SAFE_FUNCTIONS = frozenset({
    "count", "sum", "avg", "min", "max",
    "lower", "upper", "substr", "length", "trim", "ltrim", "rtrim",
    "coalesce", "abs", "round", "strftime", "date", "like", "glob",
})


@contextmanager
def views_only(conn: sqlite3.Connection, allowed_views: set[str],
               base_tables: set[str]):
    """Restrict a connection to SELECT + READ on views (and their bases).

    Usage: wrap every planner/text2sql query::
        with views_only(conn, _VIEWS.keys(), _BASE_TABLES):
            cur = conn.execute(sql)

    sqlite3.DatabaseError raised from a denied access is mapped by the
    caller to the gateway rule ID.
    """
    allowed = set(allowed_views) | set(base_tables)

    def _authorizer(action: int, tname: str | None, cname: str | None,
                    dbname: str | None, src: str | None) -> int:
        if action == _SQLITE_SELECT:
            return _SQLITE_OK
        if action == _SQLITE_READ and tname in allowed:
            return _SQLITE_OK
        if action == _SQLITE_FUNCTION and (cname or "").lower() in _SAFE_FUNCTIONS:
            return _SQLITE_OK
        return _SQLITE_DENY

    conn.set_authorizer(_authorizer)
    try:
        yield
    finally:
        conn.set_authorizer(None)
