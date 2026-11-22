import pytest
from hippo.models import InvalidRecord, parse_claim, parse_pharmacy, parse_revert

GOOD_CLAIM = {
    "id": "c1", "npi": "1234567890", "ndc": "00002323401",
    "price": 100.0, "quantity": 4, "timestamp": "2024-02-01T14:55:56",
}


def test_valid_claim_parses_and_quantity_becomes_float():
    claim = parse_claim(GOOD_CLAIM)
    assert claim.quantity == 4.0 and isinstance(claim.quantity, float)
    assert claim.unit_price == 25.0


@pytest.mark.parametrize("change, reason", [
    ({"quantity": None}, "quantity"),
    ({"quantity": 0}, "quantity"),
    ({"quantity": True}, "quantity"),
    ({"quantity": float("nan")}, "quantity"),
    ({"price": -1.0}, "price"),
    ({"npi": ""}, "npi"),
    ({"timestamp": "yesterday"}, "timestamp"),
])
def test_invalid_claims_are_rejected_with_reason(change, reason):
    with pytest.raises(InvalidRecord, match=reason):
        parse_claim({**GOOD_CLAIM, **change})


def test_non_object_is_rejected():
    with pytest.raises(InvalidRecord):
        parse_claim(["not", "a", "dict"])


def test_pharmacy_and_revert_parse():
    assert parse_pharmacy({"npi": "1", "chain": "health"}).chain == "health"
    assert parse_revert({"id": "r1", "claim_id": "c1",
                         "timestamp": "2024-01-01T00:00:00"}).claim_id == "c1"


def test_pharmacy_accepts_spec_id_key():
    assert parse_pharmacy({"id": "1", "chain": "health"}).npi == "1"
