# Threat model (STRIDE-lite)

## Spoofing
- The `approver` callable on confirmation gates is the trust boundary.
  In production it must be backed by SSO, not a lambda. A spoofed
  approver could release an untested formula.

## Tampering
- Audit log is hash-chained; `verify()` detects edits. In production,
  ship entries to append-only storage so a compromised host can't
  rewrite history.
- Seeded SQLite is rebuilt per run; a production deployment needs
  write-path controls on the R&D records themselves.

## Repudiation
- Every orchestrator turn, gate decision, and feedback item is audit
  logged with actor + timestamp.

## Information disclosure
- Gateway errors never echo row data. Feedback free text is PII-scrubbed
  before storage (email/phone/SSN/account patterns).
- The fake price feed returns only seeded demo prices; the live stub
  raises instead of guessing.

## Denial of service
- Gateway caps every query at 100 rows. TF-IDF runs over 4 small SOPs;
  scale to embeddings before growing the corpus.

## Elevation of privilege
- The SQL gateway is the privilege boundary: SELECT-only,
  literal-stripped keyword scan blocks stacked writes and comment
  smuggling. One retry, then explicit escalation — never a second,
  broader guess.
