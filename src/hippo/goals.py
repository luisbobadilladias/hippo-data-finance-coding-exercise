"""Turn the merged sums into the three output reports.

Each function takes the merged Partial and returns plain lists and dicts,
ready for json.dump. Division and rounding happen only here, at the end.
"""
from hippo.aggregate import Partial, Totals

DECIMALS = 2


def _avg_unit_price(totals: Totals) -> float | None:
    priced = totals.fills - totals.reverted
    if priced == 0:
        return None  # every claim was reverted: there is no price to average
    return round(totals.unit_price_sum / priced, DECIMALS)


def pharmacy_drug_metrics(summary: Partial) -> list[dict]:
    """Goal 2: fills, reverts, average unit price and total price per (npi, ndc)."""
    return [
        {
            "npi": npi,
            "ndc": ndc,
            "fills": totals.fills,
            "reverted": totals.reverted,
            "avg_price": _avg_unit_price(totals),
            "total_price": round(totals.total_price, DECIMALS),
        }
        for (npi, ndc), totals in sorted(summary.by_pharmacy_drug.items())
    ]
