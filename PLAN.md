# Build Plan — Hippo Data Finance Coding Exercise

- **Language:** Python
- **Deadline:** Wednesday 2026-11-25, 10:00 EST
- **Spec:** [`a0e28bc…/01-data-project.md`](a0e28bcbeade9e5044a08808a847a11c-62cd2eaac2150fcf7ff8d8e868bf7a18ba413035/01-data-project.md) (copy of the gist from the email)
- **Approach:** built together, one step at a time. Every line should be understood before moving on.
- **Next session:** Saturday 2026-11-21

## What's in the repo

| Path | What it is |
|---|---|
| `a0e28bc…/01-data-project.md` | The exercise spec (the gist) |
| `a0e28bc…/02-claims.json` | Small example claims file from the gist. It's not the real input. |
| `data/pharmacies/*.csv` | 17 pharmacies. **CSV with columns `chain,npi`**, while the spec says JSON with `id, chain`. |
| `data/claims/*.json` | 28 files, 27,076 claims, 10 drugs (NDCs), 20 NPIs |
| `data/reverts/*.json` | 4 files, 308 reverts |

## Data-quality traps found

1. **Claims from unknown pharmacies:** 4,085 claims come from 3 NPIs that aren't in the pharmacy file (`2345678901`, `6789012345`, `0000000000`). The spec says "we are only interested in events from Pharmacy dataset," so they get dropped. The spec's example output uses `0000000000`, which is only an illustration.
2. **Bad claims:** 2 have no `quantity` and 1 has `quantity: 0` (all from npi `3333333333`, all with the same price and timestamp). These would cause divide-by-zero errors or crashes.
3. **Mixed types:** `quantity` is sometimes an int (`15`) and sometimes a float (`90.0`). 3,028 claims have fractional quantities (e.g. 8.5). These are legitimate, since the spec's goal 4 example contains 8.5.
4. **Duplicate reverts:** 3 reverts arrive twice with the **same revert `id`** but different timestamps, which is a stream redelivering an event. They must be deduplicated, or the `reverted` count is inflated.
5. **Reverts timestamped before their claim:** 2 cases. These are out-of-order stream events.

## Open decisions (recommendation first)

1. **Price metrics and reverted claims:** exclude reverted claims from `avg_price` and `total_price`, because a revert invalidates the claim. `fills` counts all valid claims and `reverted` counts how many of them were reverted. **Decided: exclude.**
2. **Which "average unit price":** mean of each claim's `price / quantity` (recommended), or weighted `sum(price) / sum(quantity)`. **Decided: mean of per-claim unit prices.**
3. **Goal 4, how many quantities:** top 5 by frequency, most common first (matches the example).
4. **Libraries:** Python standard library only (`json`, `csv`, `argparse`, `dataclasses`, `concurrent.futures`) plus `pytest` for tests.
5. **Repo contents:** keep `data/` so the README can show how to run on the sample files. Possibly remove the gist folder later.

Decisions 1 and 2 are real ambiguities in the spec. One option is to email Matheus about them. Whatever is chosen gets documented in the README.

## Build steps

| Step | What we build | What you'll understand |
|---|---|---|
| 0 | Project skeleton: `pyproject.toml`, venv, `src/` layout, pytest running | How a Python package is laid out and why |
| 1 | `models.py`: `Pharmacy`, `Claim`, `Revert` dataclasses plus validation (returns a valid object or rejects it with a reason) | Schema validation; all 5 traps handled explicitly |
| 2 | `readers.py`: read the 3 lists of directories (CSV and JSON), skip invalid events and log a count of what was rejected | File I/O and defensive parsing |
| 3 | Parallel reading with `ProcessPoolExecutor` (the spec mentions 10 cores) | Why processes rather than threads (the GIL), and when parallelism is worth it |
| 4 | Goal 2, `metrics.py`: group by (npi, ndc), dedupe reverts by id, compute fills/reverted/avg/total | Single-pass aggregation with dicts |
| 5 | Goal 3, `recommendations.py`: join claims to chains, average unit price per (ndc, chain), keep the 2 cheapest | Joins and sorting without a framework |
| 6 | Goal 4, `quantities.py`: count quantities per ndc, keep the top 5 | `collections.Counter` |
| 7 | `cli.py` / `__main__.py`: argparse for the 3 directory lists plus an output dir; writes 3 JSON files | The entry point the graders will run |
| 8 | Tests for each step, with small hand-made inputs where the answer is known | Proving correctness |
| 9 | README: how to run it, assumptions made, the data-quality findings | The document graders read first |

## Progress

- [ ] Open decisions answered
- [x] Step 0 — Skeleton
- [x] Step 1 — Models & validation
- [x] Step 2 — Readers
- [ ] Step 3 — Parallel reading
- [ ] Step 4 — Goal 2 metrics
- [ ] Step 5 — Goal 3 recommendations
- [ ] Step 6 — Goal 4 quantities
- [ ] Step 7 — CLI
- [ ] Step 8 — Tests
- [ ] Step 9 — README
