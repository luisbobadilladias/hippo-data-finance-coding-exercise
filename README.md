# Hippo Data Finance — Claims Metrics

Reads pharmacy, claim and revert events and produces three JSON reports:

| File | Goal | Contents |
|---|---|---|
| `pharmacy_drug_metrics.json` | 2 | fills, reverts, average unit price and total price per (pharmacy, drug) |
| `chain_recommendations.json` | 3 | the 2 chains with the lowest average unit price for each drug |
| `common_quantities.json` | 4 | the 5 most prescribed quantities for each drug |

Python 3.10+, standard library only (pytest for tests).

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run on the sample files

```
hippo --pharmacies data/pharmacies --claims data/claims --reverts data/reverts
```

(`python -m hippo ...` works the same.) Results go to `output/`. A summary of what was
kept and rejected is logged to stderr:

```
INFO pharmacies: 17 kept, 0 rejected
INFO reverts: 308 kept, 0 rejected
INFO   reverts point to 305 distinct claims
INFO claims: 22988 kept, 4088 rejected
INFO     4085  npi: not in pharmacy dataset
INFO        2  quantity: missing or not a number
INFO        1  quantity: must be greater than 0
INFO wrote output/pharmacy_drug_metrics.json (170 rows)
INFO wrote output/chain_recommendations.json (10 rows)
INFO wrote output/common_quantities.json (10 rows)
```

| Option | Meaning |
|---|---|
| `--pharmacies DIR [DIR ...]` | directories with pharmacy files |
| `--claims DIR [DIR ...]` | directories with claim event files |
| `--reverts DIR [DIR ...]` | directories with revert event files |
| `--output DIR` | where to write the reports (default `output`) |
| `--workers N` | processes for reading claims (default: all cores; `1` = no pool) |

Every directory is scanned (not recursively) for `.json` and `.csv` files. Any dataset may
be in either format. The sample pharmacies are CSV, while the spec describes JSON.

## Tests

```
pytest
```

## How it works

```
reverts ──► set of reverted claim ids ─┐
pharmacies ──► {npi: chain} ───────────┤
                                       ▼
claims files ──► [worker] parse + validate + sum one file ──► partial sums ─┐
             ──► [worker] ...                                 partial sums ─┼─► merge ──► goals 2, 3, 4
             ──► [worker] ...                                 partial sums ─┘
```

1. **Validate** (`models.py`). Each record becomes a typed, frozen dataclass or is
   rejected with a reason. Rejections are counted, never silently dropped.
2. **Read** (`readers.py`). Pharmacies and reverts are small and read up front. A file
   that can't be parsed is skipped with a warning. A missing directory is an error.
3. **Map-reduce** (`aggregate.py`). Each worker turns one claims file into running sums
   per (npi, ndc) plus quantity counts per ndc. The main process adds them together.
4. **Report** (`goals.py`). Division and rounding happen only here, once, at the end.

### Why map-reduce rather than parallel parsing

The obvious approach is for workers to parse files and send the `Claim` objects back. I
measured it, and it was *slower* than a plain loop: moving objects between processes
(pickling) cost more than parsing them (2.1 ms vs 1.5 ms per file). Sending back only
small partial sums fixes that:

| Input | Sequential | Pool, ships claims | Pool, ships partial sums |
|---|---|---|---|
| sample (28 files) | 0.04 s | 0.13 s | 0.12 s |
| sample ×20 | 0.83 s | 0.93 s | 0.28 s |
| sample ×100 | 4.6 s | 7.6 s | 1.1 s |

*(10-core machine. ×N = the sample claim files repeated N times.)*

On the small sample, starting the pool costs about 0.1 s, so `--workers 1` is faster
there. The default still uses every core, because that's what pays off at the scale
the spec describes.

Storing **sums and counts, never averages**, is what makes this possible. Sums from
different files can simply be added together, but averages of averages would be wrong.
Results are bit-identical for any worker count. Partials are merged in file order, and a
test checks this.

## Decisions and assumptions

- **Only pharmacies in the pharmacy dataset count.** Claims from other NPIs are dropped.
  A revert of a dropped claim has nothing to apply to.
- **Reverted claims:**
  - **Counted** in `fills` and `reverted`.
  - **Excluded** from `avg_price`, `total_price` and the Goal 3 ranking, because a revert
    invalidates the claim.
  - **Included** in Goal 4, because the prescription was still written even if it was
    never picked up.
- **Average unit price** is the mean of each claim's `price / quantity`. It is not
  `sum(price) / sum(quantity)`. For chains (Goal 3) it is the mean over all of the chain's
  claims, not an average of pharmacy averages.
- **Duplicate reverts.** A revert delivered twice, or two reverts of one claim, counts once.
- **Out-of-order reverts.** A revert timestamped before its claim still counts. Stream
  events can arrive out of order, so timestamps are not used for ordering.
- **Quantities are floats.** The spec says integer, but its own example shows `8.5`, and
  `15` and `15.0` must count as the same quantity.
- **Rounding.** Prices are rounded to 2 decimals. Goal 3 ranks on the exact, unrounded
  average.
- **No average when everything is reverted.** If every claim for a (pharmacy, drug) pair
  is reverted, the row is kept and `avg_price` is `null`.
- **Ties:**
  - Goal 3 ties are broken by chain name.
  - Goal 4 count ties go to the smaller quantity, so the result never depends on file
    order.
- **Pharmacy key.** Pharmacy records may use `npi` (as in the sample data) or `id` (as in
  the spec). If an NPI appears twice, the last one read wins.

## What the sample data contains

- **Claims from unknown pharmacies:** 4,085 claims come from 3 NPIs that are not in the
  pharmacy file (`2345678901`, `6789012345`, `0000000000`).
- **Invalid claims:** 3 claims have no quantity or a quantity of 0.
- **Mixed quantity types:** quantities are a mix of ints and floats. 3,028 of them are
  fractional.
- **Reverts and what they apply to:**
  - 3 reverts are delivered twice with the same revert id, so 308 reverts cover 305 claims.
  - 45 of those claims belong to unknown pharmacies, so 260 reverts take effect.
  - 2 reverts are timestamped before their claim.
- **Ties at the top-5 cutoff:** for drug `00031074998`, quantities `15.0` and `30.0` tie
  for 5th place (252 each).
- **Two price tiers:** every (pharmacy, drug) pair averages either at most $2.90 or at
  least $676.10 per unit, with nothing in between. A chain's Goal 3 average therefore
  depends mostly on how many of its pharmacies are in the low tier for that drug.

## Layout

```
src/hippo/
  models.py     schemas and validation
  readers.py    find and parse files
  aggregate.py  map-reduce over claim files
  goals.py      the three reports
  cli.py        command-line entry point
tests/          one test file per module
data/           sample input
```
