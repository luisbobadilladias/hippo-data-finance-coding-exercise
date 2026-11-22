from hippo.aggregate import Partial, Totals
from hippo.goals import cheapest_chains, pharmacy_drug_metrics
from hippo.models import Pharmacy


def summary(**pairs):
    """Build a Partial from npi_ndc="..." keyword names, e.g. summary(a_d1=Totals(...))."""
    return Partial(by_pharmacy_drug={tuple(k.split("_")): v for k, v in pairs.items()})


def test_goal2_row():
    s = summary(a_d1=Totals(fills=3, reverted=1, unit_price_sum=20.0, total_price=40.0))
    assert pharmacy_drug_metrics(s) == [{
        "npi": "a", "ndc": "d1", "fills": 3, "reverted": 1,
        "avg_price": 10.0, "total_price": 40.0,  # 20 / (3 - 1), reverted excluded
    }]


def test_goal2_rounds_to_two_decimals():
    s = summary(a_d1=Totals(fills=3, unit_price_sum=1.0, total_price=8150.999999999999))
    [row] = pharmacy_drug_metrics(s)
    assert (row["avg_price"], row["total_price"]) == (0.33, 8151.0)


def test_goal2_all_reverted_has_null_average():
    [row] = pharmacy_drug_metrics(summary(a_d1=Totals(fills=2, reverted=2)))
    assert row["avg_price"] is None and row["total_price"] == 0.0


def test_goal2_sorted_by_npi_then_ndc():
    s = summary(b_d1=Totals(fills=1), a_d2=Totals(fills=1), a_d1=Totals(fills=1))
    assert [(r["npi"], r["ndc"]) for r in pharmacy_drug_metrics(s)] == [
        ("a", "d1"), ("a", "d2"), ("b", "d1")]


def pharmacies(**chains):
    """npi="chain" pairs -> {npi: Pharmacy}."""
    return {npi: Pharmacy(npi=npi, chain=chain) for npi, chain in chains.items()}


def test_goal3_rolls_up_claims_not_pharmacy_averages():
    s = summary(
        a_d1=Totals(fills=1, unit_price_sum=10.0),        # 1 claim at 10
        b_d1=Totals(fills=9, unit_price_sum=9 * 20.0),    # 9 claims at 20
    )
    [row] = cheapest_chains(s, pharmacies(a="health", b="health"))
    assert row == {"ndc": "d1", "chain": [{"name": "health", "avg_price": 19.0}]}


def test_goal3_keeps_two_cheapest_ascending():
    s = summary(
        a_d1=Totals(fills=1, unit_price_sum=30.0),
        b_d1=Totals(fills=1, unit_price_sum=10.0),
        c_d1=Totals(fills=1, unit_price_sum=20.0),
    )
    [row] = cheapest_chains(s, pharmacies(a="doctor", b="health", c="saint"))
    assert [c["name"] for c in row["chain"]] == ["health", "saint"]


def test_goal3_ranks_on_exact_average_not_rounded():
    s = summary(
        a_d1=Totals(fills=1, unit_price_sum=0.304),  # rounds to 0.30
        b_d1=Totals(fills=1, unit_price_sum=0.296),  # rounds to 0.30
    )
    [row] = cheapest_chains(s, pharmacies(a="aaa", b="zzz"), top=1)
    assert row["chain"] == [{"name": "zzz", "avg_price": 0.3}]


def test_goal3_skips_fully_reverted_chain():
    s = summary(a_d1=Totals(fills=2, reverted=2), b_d1=Totals(fills=1, unit_price_sum=5.0))
    [row] = cheapest_chains(s, pharmacies(a="doctor", b="health"))
    assert [c["name"] for c in row["chain"]] == ["health"]
