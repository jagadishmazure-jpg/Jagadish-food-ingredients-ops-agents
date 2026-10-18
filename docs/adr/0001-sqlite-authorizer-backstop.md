# ADR-0001: SQLite authorizer backstop for the SELECT-only gateway

**Status:** accepted
**Date:** 2026-10-18
**Context:** `fooding/views.py` (SEC-SELECT-01/02/03)

## Problem

The gateway's text-level checks (first-keyword must be SELECT, write-keyword
scan on literal-stripped SQL, row cap) can be fooled by exotic SQL. A sibling
repo proved it in production-shaped code: a `LIMIT 100000 -- x` comment
smuggled **36,864 rows** past a cap that trusted the query's own LIMIT.
Text parsing sees what the attacker wants it to see.

The bypass class:
- **Raw base tables** — `SELECT secret FROM ingredients` reads columns the
  published views never expose. Passes SEC-SELECT-01/02 (it *is* a SELECT,
  with no write keywords).
- **Comma-join smuggling** — `FROM v_formulations, trials` mixes a legit
  view with a raw table.
- **Quoted identifiers** — `FROM "sqlite_master"` reaches the schema table.
- **Comment obfuscation** — `FROM/**/trials` hides the table name from
  naive parsers.
- **LIMIT tricks** — `LIMIT 100000 -- x`, `LIMIT n OFFSET m`, `LIMIT m, n`,
  LIMIT inside subqueries all defeat LIMIT-rewriting caps.

## Decision

Defense in depth, two layers:

1. **Text-level FROM/JOIN check** (in `views.run_query`): after stripping
   string literals and `--` / `/* */` comments, every table referenced in
   FROM/JOIN — including comma-joined tables and quoted identifiers — must
   be one of the four published views. Anything else raises `GatewayError`
   citing SEC-SELECT-03. This is the primary defense against raw-table
   access.

2. **SQLite authorizer backstop** (`fooding/authz.py::views_only`): a
   `conn.set_authorizer()` context manager that allows `SQLITE_SELECT`,
   `SQLITE_READ` on the allowed views **and their underlying base tables**,
   and a whitelist of read-only functions (`COUNT`, `LOWER`, …) — and
   denies everything else, including `sqlite_master`. The authorizer sees
   what SQLite *actually touches* during compilation, so it catches
   whatever the text check misses.

   The base tables must be allowed because SQLite expands views during
   compilation — denying them breaks every legitimate view query (verified
   empirically: the authorizer fires on `formulations.form_id` *inside*
   `v_formulations`). The text-level FROM check is therefore what keeps raw
   tables out; the authorizer is the backstop.

3. **Row cap at fetch time**: `cursor.fetchmany(ROW_CAP + 1)`, truncated —
   never trust the query's LIMIT, never call `fetchall()` on planner
   queries.

4. **Engine separation**: the substitution engine and trial tracker read
   via direct `conn.execute` (not through the capped gateway), so the
   100-row cap can never silently drop rows they need.

Denied authorizer access surfaces as `sqlite3.DatabaseError`, mapped to
`GatewayError("SEC-SELECT-03: ...")`.

## Consequences

- Every bypass in `tests/test_gateway_backstop.py` is denied or capped;
  legitimate view queries (including view↔view JOINs) keep working.
- The authorizer is registered per-query via context manager and restored
  afterwards — no leakage into engine connections.
- PII scrubber hardened in the same pass: `(555) 123-4567`,
  `+1 (555) 123-4567`, `555.123.4567` now redact; dates (`2026-10-18`)
  are left intact.
