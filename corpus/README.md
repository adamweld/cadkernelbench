# Corpora: kernels on real parts

The rest of cadkernelbench generates its cases, so every answer is known. Real parts have no
exact answer, but they hold what generators do not: geometry people made for a purpose, imported
from a file, with all its small faces, slivers and tolerances. This directory runs every kernel
over a collection of STEP files, the same operations on each, and records what happens.

## What is run on each model

Each model runs in a process of its own for each kernel (`occt_worker.py`, `cadrs_worker/`), so a
crash or a hang costs that model only, and is pinned to the operation it happened in:

| Operation | What | Recorded |
|---|---|---|
| import | read the STEP file | solids, shells, faces, edges |
| valid | the kernel's own check of everything read | true or false |
| mass | volume and area of everything read | the measures |
| kinds | faces by surface kind | counts |
| roundtrip | write STEP with the kernel's own writer, read it back | the measures again, and solids |
| mesh | tessellate, chord 1/1000 of the bounding box's diagonal | triangles |
| boolean | the largest solid less a ball on its centroid that holds its own volume | validity, volume, solids |
| fillet | three edges of the largest solid, each on its own, radius L/100 where L = V^(1/3), chosen by a seed from the file name | validity, volume |
| shell | the largest solid, its largest planar face removed, wall L/50 inward | validity, volume |

The sizes come from the solid's exact volume and centroid, which two kernels that read the file
alike agree on, so their booleans cut the same ball and can be compared. Bounding boxes are not
used: kernels pad theirs differently. Fillet edges are chosen per kernel, since kernels number
edges differently, so fillets are compared as rates only.

There is no exact answer for a real part. The outcomes are crash, timeout, error, invalid (an ok
result that the kernel's own check rejects, or a volume that is not positive and finite), and
disagreement between two kernels' volumes beyond 1e-6. **Agreement is not proof that either is
right.** A failure worth reporting is first reduced to a small case with a closed form, written
fresh, and contributed to [brep-bench](https://github.com/bmander/brep-bench).

## Running it

```bash
uv venv --python 3.12 .venv-occt && uv pip install --python .venv-occt/bin/python cadquery-ocp
cargo build --release --manifest-path corpus/cadrs_worker/Cargo.toml   # needs a cadrs checkout beside this one

python corpus/manifest.py path DIR manifest.tsv           # identifiers, paths under DIR, SHA-256
python corpus/run.py --kernel occt  --manifest manifest.tsv --data DIR --out results/occt.jsonl.gz
python corpus/run.py --kernel cadrs --manifest manifest.tsv --data DIR --out results/cadrs.jsonl.gz
python corpus/summarize.py results/
```

A run resumes where it stopped.

## Which collections

A collection is run here, with its files fetched by a script and never committed, only where its
licence allows the parts to be named and the results published with attribution. Collections whose
licence does not allow that (the ABC dataset, whose models stay their creators' copyright) are run
privately with the same code, and only rates are reported from them.
