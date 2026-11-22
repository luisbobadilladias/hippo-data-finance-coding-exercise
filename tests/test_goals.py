from hippo.aggregate import Partial, Totals
from hippo.goals import pharmacy_drug_metrics


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
