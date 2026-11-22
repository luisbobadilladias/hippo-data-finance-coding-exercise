"""Command-line entry point: read the inputs, compute the 3 goals, write JSON."""
import argparse
import json
import logging
import os
from collections import Counter
from pathlib import Path

from hippo.aggregate import reverted_claim_ids, summarize_claims
from hippo.goals import cheapest_chains, common_quantities, pharmacy_drug_metrics
from hippo.readers import read_pharmacies, read_reverts

log = logging.getLogger("hippo")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="hippo", description="Pharmacy claims metrics and recommendations.")
    parser.add_argument("--pharmacies", nargs="+", required=True, type=Path,
                        help="directories with pharmacy files")
    parser.add_argument("--claims", nargs="+", required=True, type=Path,
                        help="directories with claim event files")
    parser.add_argument("--reverts", nargs="+", required=True, type=Path,
                        help="directories with revert event files")
    parser.add_argument("--output", type=Path, default=Path("output"),
                        help="directory for the 3 result files (default: output)")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1,
                        help="processes for reading claims; 1 = no pool (default: all cores)")
    return parser.parse_args(argv)


def _log_rejects(dataset: str, kept: int, rejects: Counter) -> None:
    log.info("%s: %d kept, %d rejected", dataset, kept, sum(rejects.values()))
    for reason, count in rejects.most_common():
        log.info("  %6d  %s", count, reason)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        pharmacies, pharmacy_rejects = read_pharmacies(args.pharmacies)
        reverts, revert_rejects = read_reverts(args.reverts)
        reverted_ids = reverted_claim_ids(reverts)
        summary = summarize_claims(args.claims, pharmacies.keys(), reverted_ids,
                                   workers=args.workers)
    except NotADirectoryError as e:
        log.error("%s", e)
        return 2

    _log_rejects("pharmacies", len(pharmacies), pharmacy_rejects)
    _log_rejects("reverts", len(reverts), revert_rejects)
    log.info("  reverts point to %d distinct claims", len(reverted_ids))
    _log_rejects("claims", sum(t.fills for t in summary.by_pharmacy_drug.values()),
                 summary.rejects)

    reports = {
        "pharmacy_drug_metrics.json": pharmacy_drug_metrics(summary),
        "chain_recommendations.json": cheapest_chains(summary, pharmacies),
        "common_quantities.json": common_quantities(summary),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    for name, report in reports.items():
        path = args.output / name
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        log.info("wrote %s (%d rows)", path, len(report))
    return 0
