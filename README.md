# cadkernelbench

Generated robustness benchmarks for B-rep geometric kernels: thousands of seeded cases whose right answer is known in closed form, run in bulk to give failure rates.

It asks one kind of question: **how often does a kernel fail on a given kind of input, and how does that change as the input gets harder?**

## How this relates to brep-bench

[brep-bench](https://github.com/bmander/brep-bench) is a curated library of several hundred individual solids, each built by hand in every kernel's own idiom, with a public results board at [brepbench.org](https://brepbench.org). It answers which operations a kernel can perform and on which named hard cases it fails. If that is your question, use brep-bench.

cadkernelbench does not repeat that. It holds what a curated library cannot:

| | brep-bench | cadkernelbench |
|---|---|---|
| Cases | Hand-written, one at a time | Generated from seeds, in families |
| Result | Pass or fail per named solid | A failure rate per family, and how it varies with a parameter |
| Per-kernel work | One implementation per case | Ten functions, written once |
| Ground truth | Closed-form volume and area | Closed-form point membership |
| Breadth of operations | Wide | Narrow, so far |

The two are meant to be read together.

## What is in it

| Suite | State | Cases |
|---|---|---|
| Near-degenerate booleans | Working | 7 families x 15 offsets from zero to 1 mm x 20 placements |
| Generic booleans | Working | Random pairs of primitives |
| Feature sequences | Working | 12 booleans on one body, then a fillet |
| Fillets on sharp edges | Working, with a known limit: fillet existence is not proved | One edge or all edges, three radii |
| Surface intersection | An OCCT runner for the external [SSI corpus](https://github.com/jyviko/ssi-corpus) | 119, theirs |
| Feature recognition | A generator of STEP parts with known features | 60 |
| [Reference survival](docs/REFERENCE-SURVIVAL.md): after an upstream edit, does a stored reference to a face still find it? | Working for faces, on two OCCT-based naming schemes. No existing CAD product measured yet | 9 kinds of edit x models of 10, 50 and 200 features, 8 references each |
| Feature sequences at depth, blends with proved existence, freeform booleans, throughput and determinism | Planned | |

Kernel adapters: Open CASCADE (run), SMLib through NVIDIA's `usd-brep` (run), solidcore (written, **never run**).

## Results so far

From 2026-11-10, on a 4-core Linux machine. Full tables, method and limits are in [docs/RESULTS.md](docs/RESULTS.md) and [docs/METHOD.md](docs/METHOD.md). Raw output is in [results/](results/).

OCCT 8.0.1 and SMLib 1.0.1 on identical cases:

| Test | OCCT | SMLib |
|---|---|---|
| Near-degenerate boolean pairs failing, of 1,800 | 2 | 1 |
| 12-step feature sequences completed, of 300 | 300 | 205 |
| Final fillet failing, of the sequences completed | 8.3% | 19.0% |

These are analytic primitives only. They say nothing yet about freeform surfaces or imported geometry.

## Running it

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv venv --python 3.12 .venv-occt
```

```bash
uv pip install --python .venv-occt/bin/python cadquery-ocp==8.0.1.1.0 numpy scipy
```

```bash
.venv-occt/bin/python -m ckb.kernels.occt --out occt.jsonl --jobs 4
```

```bash
.venv-occt/bin/python -m ckb.kernels.occt --summarise occt.jsonl
```

Add `--fuzzy0` to run only the cases every kernel can run, for a case-by-case comparison. Other kernels, the remaining measurements and the hazards already met are in [docs/RUNNING.md](docs/RUNNING.md).

## Rules

1. **Ground truth by construction, never from another kernel.**
2. **A kernel is plugged in behind a small interface** and nothing else about a case changes. See [docs/ADDING-A-KERNEL.md](docs/ADDING-A-KERNEL.md).
3. **Every checker is validated on known-good inputs before any result counts**, and that validation is reported with the results.
4. **Crash, error, invalid result and wrong result are reported separately.** A silent wrong result is the worst outcome and is never folded into a total.
5. **Ill-posed cases are excluded and listed.** A case whose exact answer is not a valid solid cannot be passed or failed.
6. **Results are reported by family and difficulty, never as one number.**
7. **Every published result names the kernel version, the machine and the commit**, and can be regenerated.
8. **Results for every kernel are published**, favourable or not.

## Contributing

Adapters for more kernels and new case families are welcome. A result that shows a flaw in the benchmark itself is the most valuable contribution of all: three such flaws were found and fixed in the first week, and they are described in [docs/METHOD.md](docs/METHOD.md).

## Licence

MIT or Apache-2.0, at your option. Each kernel keeps its own licence; an adapter only calls its kernel and does not include it.
