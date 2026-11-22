import json

from hippo.cli import main


def test_end_to_end(tmp_path):
    for d in ("p", "c", "r"):
        (tmp_path / d).mkdir()
    (tmp_path / "p" / "p.csv").write_text("chain,npi\nhealth,111")
    (tmp_path / "c" / "c.json").write_text(json.dumps([
        {"id": "c1", "npi": "111", "ndc": "d1", "price": 10.0,
         "quantity": 2, "timestamp": "2024-01-01T00:00:00"}]))
    (tmp_path / "r" / "r.json").write_text("[]")
    out = tmp_path / "out"

    code = main(["--pharmacies", str(tmp_path / "p"), "--claims", str(tmp_path / "c"),
                 "--reverts", str(tmp_path / "r"), "--output", str(out), "--workers", "1"])

    assert code == 0
    metrics = json.loads((out / "pharmacy_drug_metrics.json").read_text())
    assert metrics == [{"npi": "111", "ndc": "d1", "fills": 1, "reverted": 0,
                        "avg_price": 5.0, "total_price": 10.0}]
    assert (out / "chain_recommendations.json").exists()
    assert (out / "common_quantities.json").exists()


def test_missing_directory_returns_error_code(tmp_path):
    code = main(["--pharmacies", str(tmp_path / "nope"), "--claims", str(tmp_path),
                 "--reverts", str(tmp_path), "--output", str(tmp_path / "out")])
    assert code == 2
    assert not (tmp_path / "out").exists()  # nothing half-written
