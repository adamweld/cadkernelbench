# Running the benchmarks, and what is left to run

Written 2026-11-10 and updated 2026-11-11, when task 1 was done. The first measurements were made on a 16 GB machine, which was not enough for solidcore's build; it built on a 32 GB machine.

## What is already done

Results are in [RESULTS.md](RESULTS.md) and the method in [METHOD.md](METHOD.md). Raw outputs are in [../results/](../results/).

| Measured | Result |
|---|---|
| OCCT 8.0.1: booleans, fillets, 12-step feature sequences | Done, 8,400 cases |
| SMLib (USD BRep 1.0.1): booleans and feature sequences, paired with OCCT on identical cases | Done, 2,682 cases |
| OCCT on the public surface-intersection corpus | Done, 119 cases, two modes |
| quiddity 0.4.9: feature recognition on generated parts | Done, 60 parts |
| solidcore (SolidCraft `75a74aee`): booleans, fillets and feature sequences, with OCCT re-run on the identical cases | Done, 6,000 cases each |
| cadrs's kernel (cadrs `6525e80a`): the same 6,000 cases, paired with that OCCT run | Done 2026-11-12; see [Measuring cadrs](#measuring-cadrs) |

## What is left, in priority order

| # | Task | Why it matters | Rough time |
|---|---|---|---|
| 1 | ~~Build and measure solidcore~~ | Done 2026-11-11; see [RESULTS.md](RESULTS.md) | Build took 4 min and 5.1 GB peak on an M1 Max; run 12 min on 8 cores |
| 1a | Report solidcore's moved-torus and point-classification defects upstream, then re-run its generic pairs and fillets with tori | A torus placed by `Body::transform` fails solidcore's own check, so those cases are reported separately, not measured | Re-run under 15 minutes once fixed |
| 1b | Run brep-bench against cadrs | cadrs's release notes report building every brep-bench case; not reproduced here | Unknown |
| 2 | SMLib fillets | Completes the SMLib comparison | 1 to 2 hours |
| 3 | Re-run SMLib and solidcore's intersector on the surface-intersection corpus | Their published scores (81 and 118 of 119) have not been reproduced | 1 to 2 hours, needs a C++ build of SMLib |
| 4 | Build SolidCraft's headless CLI and run feature sequences through it | Measures the application, not only the kernel | Half a day |
| 5 | Rebuild-performance profiling | Nothing measured yet | Open-ended; see the last section |

Stop after any of them. Each is independent.

## Requirements

- Linux x86_64 or Windows for SMLib's Python package (CPython 3.12 only). OCCT's package also works on macOS.
- [uv](https://docs.astral.sh/uv/) for Python environments.
- A Rust toolchain, 1.88 or newer, for solidcore.
- **Memory: 32 GB recommended.** Compiling solidcore's kernel crate was killed twice on a 16 GB Linux machine; on a 32 GB M1 Max its largest compiler process peaked at 5.1 GB. SMLib's Python package grows by about 100 MB per case; the scripts restart workers to contain it, at about 1.5 GB per worker.
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

Done on 2026-11-11; results in [RESULTS.md](RESULTS.md). To repeat it:

solidcore is vendored inside SolidCraft's repository. The commit measured is `75a74aee`.

```bash
git clone https://github.com/tangency-labs/solidcraft ~/solidcraft && git -C ~/solidcraft checkout 75a74aee
```

Point the server's manifest at that checkout and build it with the toolchain solidcore pins (1.98.0). `-i.bak` works with both GNU and BSD sed.

```bash
sed -i.bak "s#SOLIDCORE#$HOME/solidcraft/solidcore#" solidcore_server/Cargo.toml
```

```bash
cargo +1.98.0 build --release --manifest-path solidcore_server/Cargo.toml
```

With Homebrew's rustup, `cargo +1.98.0` may not find `rustc`; put `~/.rustup/toolchains/1.98.0-<host>/bin` first on `PATH` instead. On a 16 GB machine add `-j 1`.

Validate first. The inside test must show no disagreement:

```bash
SOLIDCORE_SERVER=$PWD/solidcore_server/target/release/solidcore-server .venv-occt/bin/python -m ckb.validate ckb.kernels.solidcore
```

At commit `75a74aee` this reports 0 disagreements on boxes, cylinders, spheres and cones, and 88 tori it will not classify against (its moved-torus defect), so it exits with status 1. Then run everything:

```bash
SOLIDCORE_SERVER=$PWD/solidcore_server/target/release/solidcore-server SOLIDCORE_MESHLOG=mesh_defects.jsonl .venv-occt/bin/python -m ckb.kernels.solidcore --out solidcore.jsonl --jobs 8
```

and OCCT on the same cases:

```bash
.venv-occt/bin/python -m ckb.kernels.occt --fuzzy0 --out occt_paired.jsonl --jobs 8 --kinds near,generic,fillet,chain
```

Compare them with `python -m ckb.paired OCCT=occt_paired.jsonl solidcore=solidcore.jsonl`.

What the first run found in the adapter, and how it is handled now:

1. **Point classification** is by winding number about solidcore's own tessellation, because `Body::classify_point` failed the inside-test validation. `python -m ckb.validate ckb.kernels.solidcore --inside classify_point` shows the failure.
2. **Errors are kept in three kinds.** A kernel refusal counts against the kernel. The server rejecting a request (a bad handle, for example) is a benchmark bug and stops the run. The server dying is a crash: the worker dies with the same status, so the case is recorded as lost and is retried after signal 9.
3. **An empty result is a solid with nothing in it**, not a missing shape, so its point test still runs.
4. **Fillets** use solidcore-ops' `blend` with a constant radius. Sharp edges are judged at the middle of each edge, the only place ops gives face normals.
5. The transform convention in `build` was right: the bounding boxes of boxes, cylinders and cones agree with OCCT's to 1e-7.

## Measuring cadrs

Done on 2026-11-12; results in [RESULTS.md](RESULTS.md). To repeat it with cadrs at the commit measured:

```bash
git clone https://github.com/rvdende/cadrs ~/cadrs && git -C ~/cadrs checkout 6525e80a
```

Point the server's manifest at the checkout. `-i.bak` works with both GNU and BSD sed.

```bash
sed -i.bak "s#CADRS#$HOME/cadrs#" cadrs_server/Cargo.toml
```

Build it with the toolchain cadrs pins (`nightly-2026-10-21`). It took 2 minutes and 3.1 GB on an M1 Max.

```bash
rustup toolchain install nightly-2026-10-21 --profile minimal
```

```bash
cargo +nightly-2026-10-21 build --release --manifest-path cadrs_server/Cargo.toml
```

With Homebrew's rustup, `cargo +nightly-2026-10-21` may not find `rustc`; put `~/.rustup/toolchains/nightly-2026-10-21-<host>/bin` first on `PATH` instead.

Validate first. Both lines must report 0 disagreements and every bounding box within about 1e-13 mm of the exact one:

```bash
CADRS_SERVER=$PWD/cadrs_server/target/release/cadrs-server .venv-occt/bin/python -m ckb.validate ckb.kernels.cadrs
```

```bash
CADRS_SERVER=$PWD/cadrs_server/target/release/cadrs-server .venv-occt/bin/python -m ckb.validate ckb.kernels.cadrs --inside winding_inside
```

Then run everything (4.5 minutes on 8 cores):

```bash
CADRS_SERVER=$PWD/cadrs_server/target/release/cadrs-server .venv-occt/bin/python -m ckb.kernels.cadrs --out cadrs.jsonl --jobs 8
```

Compare with the OCCT run made on the same machine:

```bash
.venv-occt/bin/python -m ckb.paired OCCT=occt_paired.jsonl cadrs=cadrs.jsonl
```

Use OCCT from `results/2026-11-11/` only if your machine and OCCT version match; otherwise re-run OCCT as under task 1. To replay every failure and to check that fillets change the body, use the two scripts in `results/2026-11-12/`.

How the adapter handles cadrs:

1. **Placement.** Every primitive is made in its local frame and placed by `Kernel::transform`.
2. **Point classification** is cadrs's own `Kernel::classify`, which passed the inside test.
3. **Empty results.** `EmptyResult` from a boolean is the answer "empty", judged by the point test, not an error.
4. **Validity** is two verdicts. One is cadrs's `CheckLevel::Full` check. The other is a closed-manifold test the server computes from the topology, ignoring edge entries that no face uses.
5. **Sharp edges** are judged at three points along each edge, as for OCCT.
6. **Fillets** are `Kernel::fillet` with one radius.

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
