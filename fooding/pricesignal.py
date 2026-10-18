"""Ingredient price signal: fake seeded backend + explicit live gap.

The fake backend returns deterministic seeded prices (as of 2026-10-18).
The live backend is a stub that raises SignalGap — it never hallucinates
a price.
"""

from __future__ import annotations

_PRICES = {  # USD per kg, seeded demo values
    "cane sugar": 1.20,
    "date paste": 3.40,
    "stevia leaf extract": 28.00,
    "sodium benzoate": 4.10,
    "cultured dextrose": 6.80,
    "sunflower lecithin": 7.90,
    "xanthan gum": 12.50,
    "annatto extract": 14.20,
    "pea protein isolate": 8.40,
    "sunflower oil": 3.10,
}

AS_OF = "2026-10-18"


class SignalGap(Exception):
    pass


class FakePriceFeed:
    backend = "fake"

    def price(self, ingredient: str) -> dict:
        key = ingredient.strip().lower()
        if key not in _PRICES:
            raise SignalGap(f"no seeded price for {ingredient!r}")
        return {"ingredient": key, "usd_per_kg": _PRICES[key],
                "as_of": AS_OF, "backend": "fake"}


class LivePriceFeed:
    backend = "live"

    def price(self, ingredient: str) -> dict:
        raise SignalGap(
            "live price feed is not configured; wire a vendor API before "
            "relying on live prices")
