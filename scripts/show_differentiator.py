"""Print the substitution engine, trial tracker and gateway on the seeded data."""
from fooding import substitute, text2sql, trials
from fooding.demo_helpers import demo_db
from fooding.views import GatewayError, run_query

conn = demo_db()
print("Substitutes for cane sugar under 'reduced sugar':")
for opt in substitute.rank_substitutes(conn, "cane sugar", "reduced sugar"):
    print(f"  {opt['breakdown']}")

out = text2sql.answer(conn, "Suggest substitutes for cane sugar for reduced sugar")
print(f"Demo question -> {len(out['rows'])} rows: {[r['substitute'] for r in out['rows']]}")

print("Trial tracker (SOP-03 criteria):")
for fid in ("F-CLEAN-01", "F-SUGAR-01", "F-PRO-01", "F-LEG-01"):
    s = trials.trial_summary(conn, fid)
    print(f"  {fid}: {s['n_pass']}/{s['n_trials']} passed, failing criteria {s['failing_criteria']}")
try:
    trials.record_trial(conn, "F-CLEAN-01", "B-999", "pass", 8, 8, 1, 0)
except trials.TrialError as exc:
    print(f"  record 'pass' with micro failed -> {exc}")

try:
    run_query(conn, 'SELECT * FROM "ingredients"')
except GatewayError as exc:
    print(f'Gateway: SELECT * FROM "ingredients" -> {exc}')
