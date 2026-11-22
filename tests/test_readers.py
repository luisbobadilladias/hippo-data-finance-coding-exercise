import json

import pytest
from hippo.readers import list_files, read_claims, read_pharmacies, read_reverts

CLAIM = {"id": "c1", "npi": "111", "ndc": "d1", "price": 10.0,
         "quantity": 2, "timestamp": "2024-01-01T00:00:00"}


def write_json(path, data):
    path.write_text(json.dumps(data))


def test_list_files_sorts_and_skips_other_extensions(tmp_path):
    for name in ["b.json", "a.csv", ".DS_Store", "notes.txt"]:
        (tmp_path / name).write_text("")
    assert [p.name for p in list_files([tmp_path])] == ["a.csv", "b.json"]


def test_missing_directory_fails_loudly(tmp_path):
    with pytest.raises(NotADirectoryError):
        list_files([tmp_path / "nope"])


def test_pharmacies_from_csv_and_json(tmp_path):
    (tmp_path / "p.csv").write_text("chain,npi\nhealth,111")
    write_json(tmp_path / "p.json", [{"id": "222", "chain": "saint"}])
    pharmacies, rejects = read_pharmacies([tmp_path])
    assert {npi: p.chain for npi, p in pharmacies.items()} == {"111": "health", "222": "saint"}
    assert not rejects


def test_claims_counts_rejects_and_drops_unknown_pharmacies(tmp_path):
    write_json(tmp_path / "c.json", [
        CLAIM,
        {**CLAIM, "id": "c2", "npi": "999"},     # unknown pharmacy
        {**CLAIM, "id": "c3", "quantity": 0},    # invalid
    ])
    claims, rejects = read_claims([tmp_path], known_npis={"111"})
    assert [c.id for c in claims] == ["c1"]
    assert rejects == {"npi: not in pharmacy dataset": 1,
                       "quantity: must be greater than 0": 1}


def test_unreadable_file_is_skipped(tmp_path):
    (tmp_path / "broken.json").write_text("{not json")
    write_json(tmp_path / "ok.json", [{"id": "r1", "claim_id": "c1",
                                       "timestamp": "2024-01-01T00:00:00"}])
    reverts, rejects = read_reverts([tmp_path])
    assert len(reverts) == 1
    assert rejects == {"unreadable file": 1}


def test_multiple_directories_are_merged(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    write_json(tmp_path / "a" / "1.json", [CLAIM])
    write_json(tmp_path / "b" / "2.json", [{**CLAIM, "id": "c2"}])
    claims, _ = read_claims([tmp_path / "a", tmp_path / "b"], known_npis={"111"})
    assert len(claims) == 2
