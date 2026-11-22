"""Turn the merged sums into the three output reports.

Each function takes the merged Partial and returns plain lists and dicts,
ready for json.dump. Division and rounding happen only here, at the end.
"""
from hippo.aggregate import Partial, Totals
from hippo.models import Pharmacy

DECIMALS = 2


def _avg_unit_price(totals: Totals) -> float | None:
    """Exact mean unit price over non-reverted claims; None if there are none."""
    priced = totals.fills - totals.reverted
    if priced == 0:
        return None  # every claim was reverted: there is no price to average
    return totals.unit_price_sum / priced


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, DECIMALS)


def pharmacy_drug_metrics(summary: Partial) -> list[dict]:
    """Goal 2: fills, reverts, average unit price and total price per (npi, ndc)."""
    return [
        {
            "npi": npi,
            "ndc": ndc,
            "fills": totals.fills,
            "reverted": totals.reverted,
            "avg_price": _rounded(_avg_unit_price(totals)),
            "total_price": round(totals.total_price, DECIMALS),
        }
        for (npi, ndc), totals in sorted(summary.by_pharmacy_drug.items())
    ]


def cheapest_chains(summary: Partial, pharmacies: dict[str, Pharmacy],
                    top: int = 2) -> list[dict]:
    """Goal 3: per drug, the `top` chains with the lowest average unit price."""
    # Roll (npi, ndc) totals up to ndc -> chain -> Totals.
    by_drug: dict[str, dict[str, Totals]] = {}
    for (npi, ndc), totals in summary.by_pharmacy_drug.items():
        chain = pharmacies[npi].chain
        by_drug.setdefault(ndc, {}).setdefault(chain, Totals()).add(totals)

    report = []
    for ndc in sorted(by_drug):
        ranked = sorted(
            (avg, chain)
            for chain, totals in by_drug[ndc].items()
            if (avg := _avg_unit_price(totals)) is not None
        )
        report.append({
            "ndc": ndc,
            "chain": [{"name": chain, "avg_price": _rounded(avg)}
                      for avg, chain in ranked[:top]],
        })
    return report


def common_quantities(summary: Partial, top: int = 5) -> list[dict]:
    """Goal 4: per drug, the `top` most prescribed quantities, most common first.

    Ties in count go to the smaller quantity, so the result never depends
    on the order in which files were read.
    """
    report = []
    for ndc, counts in sorted(summary.quantities.items()):
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        report.append({
            "ndc": ndc,
            "most_prescribed_quantity": [qty for qty, _ in ranked[:top]],
        })
    return report
