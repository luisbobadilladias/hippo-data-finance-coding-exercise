import json
from datetime import datetime

from hippo.aggregate import Totals, reverted_claim_ids, summarize_claims, summarize_file
from hippo.models import Revert

T0 = "2024-01-01T00:00:00"


def claim(id, npi="111", ndc="d1", price=10.0, quantity=2):
    return {"id": id, "npi": npi, "ndc": ndc, "price": price,
            "quantity": quantity, "timestamp": T0}


def test_summarize_file(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps([
        claim("c1", price=10.0, quantity=2),    # unit 5
        claim("c2", price=30.0, quantity=2.0),  # unit 15, same quantity as c1
        claim("c3", price=99.0, quantity=3),    # reverted
        claim("c4", npi="999"),                 # unknown pharmacy
        claim("c5", quantity=0),                # invalid
    ]))
    result = summarize_file(path, frozenset({"111"}), frozenset({"c3"}))

    assert result.by_pharmacy_drug == {
        ("111", "d1"): Totals(fills=3, reverted=1, unit_price_sum=20.0, total_price=40.0)
    }
    assert result.quantities == {"d1": {2.0: 2, 3.0: 1}}  # reverted c3 still counted
    assert result.rejects == {"npi: not in pharmacy dataset": 1,
                              "quantity: must be greater than 0": 1}


def test_reverted_claim_ids_collapses_duplicates():
    t = datetime(2024, 1, 1)
    reverts = [Revert("r1", "c1", t), Revert("r1", "c1", t), Revert("r2", "c2", t)]
    assert reverted_claim_ids(reverts) == {"c1", "c2"}


def test_parallel_matches_sequential(tmp_path):
    for i in range(6):
        (tmp_path / f"{i}.json").write_text(json.dumps(
            [claim(f"c{i}-{j}", ndc=f"d{j % 3}", price=1.1 * (i + j), quantity=j + 1)
             for j in range(20)]))
    args = ([tmp_path], {"111"}, {"c0-0", "c3-7"})
    assert summarize_claims(*args, workers=1) == summarize_claims(*args, workers=2)
