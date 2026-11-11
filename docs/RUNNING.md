# Running the benchmarks, and what is left to run

Written 2026-11-10. The first measurements were made on a 16 GB machine, which was not enough for the items below.

## What is already done

Results are in [RESULTS.md](RESULTS.md) and the method in [METHOD.md](METHOD.md). Raw outputs are in [../results/](../results/).

| Measured | Result |
|---|---|
| OCCT 8.0.1: booleans, fillets, 12-step feature sequences | Done, 8,400 cases |
| SMLib (USD BRep 1.0.1): booleans and feature sequences, paired with OCCT on identical cases | Done, 2,682 cases |
| OCCT on the public surface-intersection corpus | Done, 119 cases, two modes |
| quiddity 0.4.9: feature recognition on generated parts | Done, 60 parts |

## What is left, in priority order

| # | Task | Why it matters | Rough time |
|---|---|---|---|
| 1 | Build and measure solidcore | It is designed for determinism and certified geometry, and has no measurement here | Build 20 to 60 min; run under 1 hour |
| 2 | SMLib fillets | Completes the SMLib comparison | 1 to 2 hours |
| 3 | Re-run SMLib and solidcore's intersector on the surface-intersection corpus | Their published scores (81 and 118 of 119) have not been reproduced | 1 to 2 hours, needs a C++ build of SMLib |
| 4 | Build SolidCraft's headless CLI and run feature sequences through it | Measures the application, not only the kernel | Half a day |
| 5 | Rebuild-performance profiling | Nothing measured yet | Open-ended; see the last section |

Stop after any of them. Each is independent.

## Requirements

- Linux x86_64 or Windows for SMLib's Python package (CPython 3.12 only). OCCT's package also works on macOS.
- [uv](https://docs.astral.sh/uv/) for Python environments.
- A Rust toolchain, 1.88 or newer, for solidcore.
- **Memory: 32 GB recommended.** Compiling solidcore's kernel crate was killed twice on a 16 GB machine. SMLib's Python package grows by about 100 MB per case; the scripts restart workers to contain it, at about 1.5 GB per worker.
- About 5 GB of disk.

## Setup

From the repository root:

```bash
uv venv --python 3.12 .venv-occt
```

```bash
uv pip install --python .venv-occt/bin/python cadquery-ocp==8.0.1.1.0 numpy scipy
```

```bash
uv venv --python 3.12 .venv-smlib
```

```bash
uv pip install --python .venv-smlib/bin/python usd-brep==1.0.1 numpy
```

A quick check that the OCCT instrument reproduces the stored results:

```bash
.venv-occt/bin/python -m ckb.kernels.occt --fuzzy0 --out /tmp/check.jsonl --jobs 4 --kinds chain
```

It should finish in about a minute with 300 lines, all with `"status": "ok"`, matching `results/2026-11-10/occt_paired_sequences.jsonl.gz`.

## Task 1: solidcore

solidcore is vendored inside SolidCraft's repository. The commit measured against so far is `75a74aee`.

```bash
git clone --depth 1 https://github.com/tangency-labs/solidcraft ~/solidcraft
```

Point the server's manifest at that checkout and build it. `-j 1` keeps memory down; drop it if you have plenty.

```bash
sed -i "s#SOLIDCORE#$HOME/solidcraft/solidcore#" solidcore_server/Cargo.toml
```

```bash
cargo build --release -j 1 --manifest-path solidcore_server/Cargo.toml
```

Then run the booleans and feature sequences:

```bash
SOLIDCORE_SERVER=$PWD/solidcore_server/target/release/solidcore-server .venv-occt/bin/python -m ckb.kernels.solidcore --out solidcore.jsonl --jobs 4
```

**This path has never been run.** `solidcore_server/src/main.rs` and `ckb/kernels/solidcore.py` were written against solidcore's source but could not be compiled in the session. Expect small fixes on first use. Things to check before trusting any number:

1. **The transform convention.** The adapter sends a 4x4 matrix with the rotated x, y and z axes in rows 0 to 2 and the translation in row 3, following the comment on `Body::transform`. Verify with one box: its bounding box after placement must match OCCT's for the same case.
2. **Validate the inside test first**, as was done for the other kernels. For a few hundred random primitives, classify sample points with solidcore and compare with the closed-form `margin` in `ckb/core.py`. There must be no disagreement before any boolean result is recorded. The pattern is in [ADDING-A-KERNEL.md](ADDING-A-KERNEL.md): build `m.random_prim`, take `m.sample_points`, skip points with `abs(margin) < m.BAND`, compare `m.inside` with `margin > 0`.
3. **Primitive conventions.** The server assumes `make_cylinder` and `make_cone` take a base centre and extend along +z, and `make_torus` lies in the xy plane. Step 2 will catch any mismatch.
4. **Fillets are not wired up.** solidcore's blend call takes more than a radius per edge. The final fillet of each sequence is skipped and reported as absent.

To compare, OCCT's results on the identical cases are already in `results/2026-11-10/occt_paired_booleans.jsonl.gz` and `occt_paired_sequences.jsonl.gz`. The generic set there covers the first 282 pairs only; to pair the full 600, re-run:

```bash
.venv-occt/bin/python -m ckb.kernels.occt --fuzzy0 --out occt_paired_full.jsonl --jobs 4 --kinds near,generic,chain
```

## Task 2: SMLib fillets

```bash
.venv-smlib/bin/python -m ckb.kernels.smlib --out smlib_fillets.jsonl --jobs 3 --kinds fillet
```

and OCCT on the same cases:

```bash
.venv-occt/bin/python -m ckb.kernels.occt --fuzzy0 --out occt_paired_fillets.jsonl --jobs 4 --kinds fillet
```

Use `--jobs` no higher than available memory divided by 2 GB for SMLib. To finish SMLib's generic booleans as well, add `generic` to `--kinds`; allow several hours, since the time goes into tessellating each result.

## Task 3: the surface-intersection corpus

```bash
git clone https://github.com/jyviko/ssi-corpus ~/ssi-corpus
```

OCCT was scored at corpus commit `b04c8a6` like this, with a one-line wrapper script as the runner:

```bash
printf '#!/bin/sh\nexec %s/.venv-occt/bin/python %s/ssi/occt_ssi_runner.py "$@"\n' "$PWD" "$PWD" > /tmp/occt_runner.sh && chmod +x /tmp/occt_runner.sh
```

```bash
cd ~/ssi-corpus && SSI_ENGINE=occt SSI_RUNNER=/tmp/occt_runner.sh SSI_JOBS=4 python3 -I scoring/score.py gsi 1e-6
```

Use `face` in place of `gsi` for the intersector OCCT's booleans use. The scorer needs numpy and scipy in the Python that runs it.

For SMLib, the corpus ships its own runner (`runner/ssi_runner.cpp`) and build file; it needs SMLib built from source from [NVIDIA-Omniverse/usd-brep](https://github.com/NVIDIA-Omniverse/usd-brep). For solidcore, its repository documents `goldens --ssi-corpus`. The aim is only to confirm or contradict the published 81 and 118.

## Task 4: SolidCraft's CLI

Not yet built or measured:

```bash
cd ~/solidcraft && cargo build --release -p solidcraft-cli
```

It runs command scripts in JSON (`examples/bracket.json` shows the format; `solid.box`, `solid.cylinder`, `solid.sphere`, `solid.move` and `solid.combine` are the relevant commands). No adapter exists yet. The simplest design is a script that turns each feature sequence from `ckb.core.run_chain_case` into one command file, runs the CLI, exports STEP, and classifies the sample points against the exported solid with OCCT.

## Task 5: rebuild performance

Not designed yet. The question is whether feature rebuild in existing systems is single-threaded and whether unaffected features are recomputed after an edit. A first measurement that needs no new tooling:

- In FreeCAD (OCCT) and SolidCraft, build one model with 50 to 200 independent features, change one early parameter and one late parameter, and record wall time, CPU time and peak core use for each rebuild.
- CPU time close to wall time means one core. A late edit costing as much as an early one means no incremental rebuild.

## Reporting back

- Put raw outputs in `results/<date>/`, gzip-compressed, named for the kernel and case kinds.
- Note the machine (cores, memory), the exact package versions and the commit of each external repository.
- Run `--summarise <file>` on any output for the standard tables.
- Open a pull request with them and extend [RESULTS.md](RESULTS.md).

## Hazards already met

These cost time in the first runs and are worth knowing.

| Hazard | What happens | Handled by |
|---|---|---|
| A bug in the benchmark counted as a kernel failure | Inflated failure rates | Only exceptions raised by the kernel are counted; anything else stops the run with exit code 3 |
| A worker killed for memory counted as a kernel crash | False crashes | A case whose worker was killed with signal 9 is retried once in a fresh process |
| Judging booleans by volume | OCCT's volume integration is off by up to 0.6% on curved trimmed faces, giving false "wrong" results | Results are judged by point membership against closed-form answers |
| Ill-posed cases | A hole exactly tangent to a wall has no valid solid as its answer | Removed from the sequences; the near-degenerate family that contains it is reported separately |
| Different case lists | The fuzzy-0-only list used for SMLib and solidcore has different ids and seeds from a full OCCT run | `--fuzzy0` runs any kernel on that same list |
| Timing that includes tessellation | SMLib's recorded times are dominated by the mesh built for the point test | Do not compare recorded SMLib times with OCCT's |
