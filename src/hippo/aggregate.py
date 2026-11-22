"""Map-reduce over claim files.

map:    one claims file -> Partial (small running sums for that file)
reduce: merge Partials together
Workers only ever send back Partials, never individual claims, because
shipping objects between processes costs more than parsing them.
"""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Iterable

from hippo.models import Revert, parse_claim
from hippo.readers import list_files, read_file


@dataclass
class Totals:
    """Running sums for one (npi, ndc) pair."""
    fills: int = 0
    reverted: int = 0
    unit_price_sum: float = 0.0  # non-reverted claims only
    total_price: float = 0.0     # non-reverted claims only

    def add(self, other: "Totals") -> None:
        self.fills += other.fills
        self.reverted += other.reverted
        self.unit_price_sum += other.unit_price_sum
        self.total_price += other.total_price


@dataclass
class Partial:
    """Everything the three goals need, for some subset of the claim files."""
    by_pharmacy_drug: dict[tuple[str, str], Totals] = field(default_factory=dict)
    quantities: dict[str, Counter] = field(default_factory=dict)  # ndc -> {qty: count}
    rejects: Counter = field(default_factory=Counter)

    def merge(self, other: "Partial") -> None:
        for key, totals in other.by_pharmacy_drug.items():
            self.by_pharmacy_drug.setdefault(key, Totals()).add(totals)
        for ndc, counts in other.quantities.items():
            self.quantities.setdefault(ndc, Counter()).update(counts)
        self.rejects.update(other.rejects)


def reverted_claim_ids(reverts: Iterable[Revert]) -> frozenset[str]:
    # A set collapses redelivered reverts (trap #4) and repeat reverts of
    # one claim. Timestamps are ignored on purpose: stream events can
    # arrive out of order (trap #5).
    return frozenset(r.claim_id for r in reverts)


def summarize_file(path: Path, known_npis: frozenset[str],
                   reverted_ids: frozenset[str]) -> Partial:
    """The map step: one file in, one Partial out. Runs inside a worker."""
    claims, rejects = read_file(path, parse_claim)
    result = Partial(rejects=rejects)
    for claim in claims:
        if claim.npi not in known_npis:
            result.rejects["npi: not in pharmacy dataset"] += 1
            continue
        totals = result.by_pharmacy_drug.setdefault((claim.npi, claim.ndc), Totals())
        totals.fills += 1
        if claim.id in reverted_ids:
            totals.reverted += 1
        else:
            totals.unit_price_sum += claim.unit_price
            totals.total_price += claim.price
        # Goal 4 counts what was prescribed, reverted or not.
        result.quantities.setdefault(claim.ndc, Counter())[claim.quantity] += 1
    return result


def summarize_claims(dirs, known_npis, reverted_ids, workers: int = 1) -> Partial:
    """Map every claims file, then reduce into one Partial."""
    files = list_files(dirs)
    work = partial(summarize_file,
                   known_npis=frozenset(known_npis),
                   reverted_ids=frozenset(reverted_ids))
    total = Partial()
    if workers <= 1:
        for result in map(work, files):
            total.merge(result)
        return total
    with ProcessPoolExecutor(max_workers=workers) as pool:
        chunksize = max(1, len(files) // (workers * 4))
        for result in pool.map(work, files, chunksize=chunksize):
            total.merge(result)
    return total
