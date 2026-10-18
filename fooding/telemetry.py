"""Synthetic food-ingredient R&D telemetry on SQLite (seeded, deterministic).

Fictional manufacturer: Verdant Pantry Foods. Every ingredient, product,
brand and person in this file is invented for the demo. No real company
names appear anywhere in this repo.
"""

from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE ingredients (
    ing_id      TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    sweetness   REAL NOT NULL,   -- 0-10 functional scores
    binding     REAL NOT NULL,
    moisture    REAL NOT NULL,
    shelf_life  REAL NOT NULL,
    emulsify    REAL NOT NULL,
    cost_per_kg REAL NOT NULL,
    clean_label INTEGER NOT NULL, -- 1 = acceptable for clean-label claims
    allergen    TEXT NOT NULL
);
CREATE TABLE formulations (
    form_id      TEXT PRIMARY KEY,
    product      TEXT NOT NULL,
    status       TEXT NOT NULL,   -- draft | in_trial | approved | rejected
    target_claim TEXT NOT NULL,
    version      INTEGER NOT NULL,
    cost_per_kg  REAL NOT NULL
);
CREATE TABLE formulation_ingredients (
    form_id TEXT NOT NULL,
    ing_id  TEXT NOT NULL,
    pct     REAL NOT NULL
);
CREATE TABLE trials (
    trial_id  TEXT PRIMARY KEY,
    form_id   TEXT NOT NULL,
    batch_no  TEXT NOT NULL,
    outcome   TEXT NOT NULL,      -- pass | fail
    sensory   INTEGER NOT NULL,   -- 0-10 panel scores
    texture   INTEGER NOT NULL,
    shelf_ok  INTEGER NOT NULL,   -- 1 = met shelf-life target
    micro_ok  INTEGER NOT NULL,   -- 1 = micro panel clear
    notes     TEXT NOT NULL
);
CREATE TABLE substitutions (
    sub_id         TEXT PRIMARY KEY,
    original_ing   TEXT NOT NULL,
    substitute_ing TEXT NOT NULL,
    target_claim   TEXT NOT NULL,
    func_match     REAL NOT NULL, -- 0-1 functional equivalence
    cost_delta     REAL NOT NULL, -- + means more expensive, per kg
    label_impact   TEXT NOT NULL  -- improves | neutral | worsens
);
CREATE TABLE claims (
    claim_id    TEXT PRIMARY KEY,
    claim       TEXT NOT NULL,
    requirement TEXT NOT NULL
);
"""

_INGREDIENTS = [
    # ing_id, name, category, sweetness, binding, moisture, shelf_life, emulsify, cost/kg, clean, allergen
    ("ING-SUG-001", "cane sugar", "sweetener", 10, 2, 4, 3, 0, 1.20, 1, "none"),
    ("ING-SUG-002", "date paste", "sweetener", 8, 5, 8, 4, 0, 3.40, 1, "none"),
    ("ING-SUG-003", "stevia leaf extract", "sweetener", 9, 0, 0, 2, 0, 28.00, 1, "none"),
    ("ING-PRS-001", "sodium benzoate", "preservative", 0, 0, 0, 9, 0, 4.10, 0, "none"),
    ("ING-PRS-002", "cultured dextrose", "preservative", 0, 1, 2, 7, 0, 6.80, 1, "none"),
    ("ING-EML-001", "mono-diglycerides", "emulsifier", 0, 3, 3, 4, 9, 5.20, 0, "none"),
    ("ING-EML-002", "sunflower lecithin", "emulsifier", 0, 3, 4, 4, 8, 7.90, 1, "none"),
    ("ING-BND-001", "xanthan gum", "binder", 0, 9, 7, 3, 2, 12.50, 1, "none"),
    ("ING-BND-002", "guar gum", "binder", 0, 8, 8, 3, 1, 9.30, 1, "none"),
    ("ING-COL-001", "caramel color IV", "color", 0, 0, 0, 5, 0, 3.90, 0, "none"),
    ("ING-COL-002", "annatto extract", "color", 0, 0, 0, 5, 0, 14.20, 1, "none"),
    ("ING-PRT-001", "whey protein isolate", "protein", 1, 4, 5, 4, 3, 11.00, 1, "milk"),
    ("ING-PRT-002", "pea protein isolate", "protein", 1, 4, 6, 4, 2, 8.40, 1, "none"),
    ("ING-FAT-001", "palm shortening", "fat", 0, 2, 6, 6, 4, 2.60, 0, "none"),
    ("ING-FAT-002", "sunflower oil", "fat", 0, 1, 5, 5, 3, 3.10, 1, "none"),
]

_FORMULATIONS = [
    # form_id, product, status, target_claim, version, cost/kg
    ("F-CLEAN-01", "Harvest Oat Bar", "in_trial", "clean label", 3, 4.62),
    ("F-CLEAN-02", "Harvest Oat Bar", "draft", "clean label", 4, 4.88),
    ("F-SUGAR-01", "Citrus Chew", "in_trial", "reduced sugar", 2, 3.15),
    ("F-PRO-01", "Field Protein Bite", "approved", "high protein", 5, 6.40),
    ("F-LEG-01", "Orchard Fruit Strip", "rejected", "clean label", 1, 2.90),
]

_FORM_INGS = [
    ("F-CLEAN-01", "ING-SUG-001", 18.0), ("F-CLEAN-01", "ING-BND-001", 0.6),
    ("F-CLEAN-01", "ING-FAT-002", 12.0), ("F-CLEAN-01", "ING-PRS-002", 0.4),
    ("F-SUGAR-01", "ING-SUG-002", 14.0), ("F-SUGAR-01", "ING-SUG-003", 0.2),
    ("F-SUGAR-01", "ING-BND-002", 0.8),
    ("F-PRO-01", "ING-PRT-002", 22.0), ("F-PRO-01", "ING-SUG-001", 8.0),
    ("F-LEG-01", "ING-SUG-001", 30.0), ("F-LEG-01", "ING-PRS-001", 0.3),
]

_TRIALS = [
    # trial_id, form_id, batch, outcome, sensory, texture, shelf_ok, micro_ok, notes
    ("T-001", "F-CLEAN-01", "B-101", "pass", 8, 8, 1, 1, "panel liked chew; 9-month shelf met"),
    ("T-002", "F-CLEAN-01", "B-102", "fail", 8, 5, 1, 1, "texture too crumbly after date paste bump"),
    ("T-003", "F-CLEAN-01", "B-103", "pass", 8, 8, 1, 1, "binder tweak fixed crumb"),
    ("T-004", "F-SUGAR-01", "B-201", "fail", 5, 7, 1, 1, "stevia aftertaste flagged by panel"),
    ("T-005", "F-SUGAR-01", "B-202", "pass", 7, 8, 1, 1, "blend ratio adjusted; aftertaste acceptable"),
    ("T-006", "F-PRO-01", "B-301", "pass", 8, 8, 1, 1, "release trial"),
    ("T-007", "F-PRO-01", "B-302", "pass", 9, 8, 1, 1, "scale-up verification"),
    ("T-008", "F-LEG-01", "B-401", "fail", 7, 7, 1, 0, "micro panel failed; preservative system inadequate"),
]

_SUBSTITUTIONS = [
    # sub_id, original, substitute, claim, func_match, cost_delta, label_impact
    ("SUB-01", "cane sugar", "date paste", "reduced sugar", 0.82, 2.20, "improves"),
    ("SUB-02", "cane sugar", "stevia leaf extract", "reduced sugar", 0.61, 26.80, "improves"),
    ("SUB-03", "sodium benzoate", "cultured dextrose", "clean label", 0.78, 2.70, "improves"),
    ("SUB-04", "mono-diglycerides", "sunflower lecithin", "clean label", 0.85, 2.70, "improves"),
    ("SUB-05", "caramel color IV", "annatto extract", "clean label", 0.70, 10.30, "improves"),
    ("SUB-06", "whey protein isolate", "pea protein isolate", "dairy free", 0.74, -2.60, "improves"),
    ("SUB-07", "palm shortening", "sunflower oil", "clean label", 0.66, 0.50, "improves"),
]

_CLAIMS = [
    ("CL-01", "clean label", "no artificial preservatives, colors or flavors; every ingredient recognizable to shoppers"),
    ("CL-02", "reduced sugar", "at least 25% less sugar than the reference product"),
    ("CL-03", "high protein", "at least 10g protein per serving"),
    ("CL-04", "dairy free", "no milk-derived ingredients anywhere in the formula"),
]


def build_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT INTO ingredients VALUES (?,?,?,?,?,?,?,?,?,?,?)", _INGREDIENTS
    )
    conn.executemany(
        "INSERT INTO formulations VALUES (?,?,?,?,?,?)", _FORMULATIONS
    )
    conn.executemany(
        "INSERT INTO formulation_ingredients VALUES (?,?,?)", _FORM_INGS
    )
    conn.executemany("INSERT INTO trials VALUES (?,?,?,?,?,?,?,?,?)", _TRIALS)
    conn.executemany(
        "INSERT INTO substitutions VALUES (?,?,?,?,?,?,?)", _SUBSTITUTIONS
    )
    conn.executemany("INSERT INTO claims VALUES (?,?,?)", _CLAIMS)
    conn.commit()
    return conn
