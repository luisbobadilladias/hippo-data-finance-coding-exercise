"""Read event files from lists of directories.

Every reader returns (records, rejects): the valid parsed records and a
Counter of rejection reasons, so the caller can report what was dropped.
"""
import csv
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable, TypeVar

from hippo.models import (
    Claim, InvalidRecord, Pharmacy, Revert,
    parse_claim, parse_pharmacy, parse_revert,
)

T = TypeVar("T")
SUPPORTED_SUFFIXES = (".json", ".csv")

log = logging.getLogger(__name__)


def list_files(dirs: Iterable[str | Path]) -> list[Path]:
    """All .json/.csv files directly inside the given directories, sorted."""
    files = []
    for directory in map(Path, dirs):
        if not directory.is_dir():
            raise NotADirectoryError(f"not a directory: {directory}")
        files.extend(p for p in directory.iterdir()
                     if p.suffix.lower() in SUPPORTED_SUFFIXES)
    return sorted(files)


def _raw_records(path: Path) -> list:
    """The file's records as plain Python objects, before validation."""
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("top level is not a list")
    return data


def read_file(path: Path, parse: Callable[[object], T]) -> tuple[list[T], Counter]:
    """Parse one file. Bad records are counted; a broken file is skipped."""
    records: list[T] = []
    rejects: Counter = Counter()
    try:
        raw_records = _raw_records(path)
    except (OSError, ValueError) as e:  # bad JSON and bad encoding are ValueErrors
        log.warning("skipping unreadable file %s: %s", path, e)
        rejects["unreadable file"] += 1
        return records, rejects
    for raw in raw_records:
        try:
            records.append(parse(raw))
        except InvalidRecord as e:
            rejects[str(e)] += 1
    return records, rejects


def _read_all(dirs, parse):
    records, rejects = [], Counter()
    for path in list_files(dirs):
        file_records, file_rejects = read_file(path, parse)
        records.extend(file_records)
        rejects.update(file_rejects)
    return records, rejects


def read_pharmacies(dirs) -> tuple[dict[str, Pharmacy], Counter]:
    pharmacies, rejects = _read_all(dirs, parse_pharmacy)
    return {p.npi: p for p in pharmacies}, rejects


def read_claims(dirs, known_npis) -> tuple[list[Claim], Counter]:
    claims, rejects = _read_all(dirs, parse_claim)
    kept = [c for c in claims if c.npi in known_npis]
    if dropped := len(claims) - len(kept):
        rejects["npi: not in pharmacy dataset"] += dropped
    return kept, rejects


def read_reverts(dirs) -> tuple[list[Revert], Counter]:
    return _read_all(dirs, parse_revert)
