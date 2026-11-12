# Results

OCCT and SMLib were first run on 2026-11-10 on a 4-core Linux machine with 16 GB of memory; solidcore, and OCCT again for pairing with it, on 2026-11-11 on the machine described in its section. Method and limits are in [METHOD.md](METHOD.md). Raw output is in [../results/2026-11-10/](../results/2026-11-10/).

Everything here is on analytic primitives. Read the limits before quoting any figure.

## OCCT 8.0.1

### Booleans

| Set | Pairs | Operations reporting an error | Returning an invalid solid | Returning the wrong solid | Hung | Pairs with any failure |
|---|---|---|---|---|---|---|
| Near-degenerate | 2,100 | 0 | 1 of 6,300 | 0 | 0 | 0.05% |
| Near-degenerate, with a fuzzy tolerance of 1e-6 | 2,100 | 0 | 0 | 0 | 0 | 0.00% |
| Generic position | 600 | 0 | 0 | 0 | 1 | 0.17% |

- The one near-degenerate failure is a sphere exactly tangent to a face, united with the block. The correct result is two solids touching at a point, which is not a manifold solid; OCCT returned something its own checker rejects.
- The hung case exceeded 180 seconds. It was not established whether the boolean or the point classification was slow.
- Median time per boolean: 4 ms on the near-degenerate set, 21 ms on the generic set, with the slowest 1% taking 185 ms or more.

### Feature sequences

| Fuzzy tolerance | Sequences | Completed all 12 booleans | Stopped early | Final fillet failed |
|---|---|---|---|---|
| none | 300 | 300 | 0 | 28 of 300 (9.3%) |
| 1e-6 | 300 | 299 | 1, an invalid solid after a spherical cut centred on an edge | 30 of 299 (10.0%) |

Median time for a 12-step sequence was about 140 ms, so about 7 sequences per second per core.

**On the superseded sequences**, which included the tangent hole, 3 of 300 stopped early without a fuzzy tolerance. Two of those returned an empty result with no error: a subtraction that should have removed a small hole returned nothing at all, reported as a success and as a valid shape. With the fuzzy tolerance set, neither happened. The input was ill-posed, so this is not counted as a boolean failure rate. It is still a silent wrong answer where an error was the right response.

### Fillets

| Edges rounded | Radius, as a fraction of the shortest sharp edge | Cases | Failed |
|---|---|---|---|
| One | 2% | 441 | 4.5% |
| One | 5% | 424 | 5.2% |
| One | 15% | 425 | 10.4% |
| All | 2% | 422 | 5.9% |
| All | 5% | 424 | 9.7% |
| All | 15% | 408 | 26.7% |

| Edges rounded | Solid | Cases | Failed |
|---|---|---|---|
| One | A single primitive | 338 | 0.0% |
| One | Union of two | 368 | 6.8% |
| One | Subtraction | 315 | 9.2% |
| One | Intersection | 269 | 11.9% |

| Edges rounded | Angle between the faces along the edge | Cases | Failed |
|---|---|---|---|
| One | Between 45 and 135 degrees throughout | 1,125 | 4.4% |
| One | Shallower or sharper somewhere | 165 | 22.4% |
| All | Between 45 and 135 degrees throughout | 668 | 9.3% |
| All | Shallower or sharper somewhere | 586 | 19.3% |

Of 2,544 fillet attempts, 207 reported an error and 54 returned a solid that failed the validity check.

### Reading the OCCT results

1. **OCCT's booleans on analytic geometry are robust.** One failure in 4,200 deliberately degenerate pairs and 599 of 600 twelve-step sequences completed. That is far better than its reputation. Version 8 follows a large modernisation, and opinions formed on earlier versions may be out of date.
2. **On ill-posed input it can fail silently.** Faced with a zero-thickness wall it twice returned an empty body and reported success. An agent that trusts a success code needs an independent check on every result, and a kernel should refuse such input, not answer it.
3. **Setting a tolerance removed those silent failures.** Commercial kernels document the same thing: robustness depends partly on hints the caller supplies.
4. **Fillets are where OCCT is weak.** About one in twenty single fillets fails on a well-conditioned edge of a two-primitive solid, and about one in ten after a 12-step sequence. None fail on plain primitives. (On the superseded sequences containing the tangent hole the final fillet failed about one time in five.)
5. **Throughput is modest.** Seven 12-step models per second per core is workable for an interactive tool and slow for machine-learning loops that run millions of executions.

## SMLib (USD BRep 1.0.1), compared with OCCT on identical cases

SMLib was driven through its Python package by `ckb/kernels/smlib.py`. OCCT was then run on exactly the same cases, so each row below compares the two on identical inputs.

Two differences in method, both forced by what SMLib's Python interface offers:

- It has no point-in-solid query, so points are classified by the winding number of SMLib's own tessellation of the result.
- It has no general validity checker, so "invalid" means not a closed manifold solid, or not tessellable. OCCT's checker is stricter.

### Booleans

| Set | Pairs | OCCT: pairs with any failure | SMLib: pairs with any failure |
|---|---|---|---|
| Near-degenerate, all families except the tangent hole | 1,800 | 2 | 1 |
| Tangent hole, offset of one micron or less | 180 | 0 | 180 |
| Tangent hole, larger offset | 120 | 0 | 1 |
| Generic position | 282 | 0 | 0 |

- OCCT's two failures are a sphere exactly touching a face, united with the block, whose exact result is not a manifold solid.
- SMLib's one failure outside the tangent-hole family is a wrong solid: a sphere sunk one micron into a face, united with the block, where one sample point was misclassified.
- **The tangent-hole split is a difference in tolerance, not a clear defect in either.** Within a micron the wall is thinner than SMLib's working tolerance, and SMLib returns a result that is not a closed solid. OCCT works to a tighter tolerance and returns a solid with a wall a few nanometres thick. Neither answer is obviously the right one for a designer.
- The generic set was stopped at 282 pairs because SMLib's run was slow there. The time went into tessellating results for the point test, not into its booleans.

### Feature sequences

| | Sequences | Completed all 12 booleans | Stopped: error | Stopped: wrong solid | Final fillet failed, of those completed |
|---|---|---|---|---|---|
| OCCT | 300 | 300 | 0 | 0 | 25 of 300 (8.3%) |
| SMLib | 300 | 205 (68%) | 93 | 2 | 39 of 205 (19.0%) |

- SMLib's 93 errors are a generic failure code from its boolean (`SM_ERR 1001`). 83 occurred when cutting a through hole and 12 when adding a boss, and about half of the failing tools were not placed flush with anything.
- The failures are spread across all steps from the second to the twelfth, and are reproducible.
- Two sequences produced a solid that misclassified sample points.

### Speed and memory

- SMLib's booleans alone took about 2.6 ms at the median on sequence steps, as fast as OCCT's or faster. The sequence times recorded for SMLib include tessellation and are not comparable.
- The Python package's memory use grew by roughly 100 MB per case until the process was killed. Whether that is the kernel or the binding was not established. As shipped, it rules out long-running use without restarting the process.

### Reading the SMLib results

1. On single booleans between two analytic solids, SMLib and OCCT are equally reliable.
2. **On chained booleans SMLib is much less reliable than OCCT**: 68% of 12-step sequences against 100%. This is the realistic case, and it is the opposite of what the surface-intersection scores below would suggest.
3. Its fillets failed about twice as often as OCCT's on the bodies both could build.
4. These results describe SMLib as published in its first open release, through its Python interface with default settings. A user of its C++ interface with tuned options might do better. That is also true of OCCT.

## solidcore, compared with OCCT and SMLib on identical cases

Run on 2026-11-11 on an Apple M1 Max (8 performance and 2 efficiency cores, 32 GB, macOS 26.6.2), not the machine above. solidcore is at SolidCraft commit `75a74aee` (its crate's version 1.0.1), built with Rust 1.98.0 and driven by `ckb/kernels/solidcore.py` through `solidcore_server`, a small program over solidcore-ops. On the same machine, OCCT 8.0.1 (cadquery-ocp 8.0.1.1.0) was re-run on the same `--fuzzy0` case list, fillets and all 600 generic pairs included, so every row below compares identical inputs. SMLib's figures are from the run above; it was not run on fillets, and its generic set stops at 282 pairs. Raw output is in [../results/2026-11-11/](../results/2026-11-11/).

solidcore describes itself as based on SMLib: it began as a port to Rust and has since diverged.

The release build took 4 minutes on this machine. Its largest compiler process peaked at 5.1 GB.

### Validating the instrument first

- **Placement.** After placement, the bounding boxes of boxes, cylinders and cones agree with OCCT's to 1e-7. Spheres and tori come out tighter than OCCT's, which pads curved surfaces.
- **solidcore's own point classification failed validation and is not used.** `Body::classify_point` disagreed with the closed-form test on 2,431 of 80,855 points. Of those, 2,422 are on tori (explained below). The other 9 are on spheres, cones and a cylinder that solidcore's own check accepts. They include a point 1.08 mm outside a sphere of radius 6.75 that it called inside. The answers are the same on every call, and OCCT agrees with the closed form on all 9. At that rate, about 6% of boolean pairs would have been scored as a wrong solid because of the classifier, not the boolean.
- **The classifier used instead** is the generalised winding number about solidcore's own tessellation of each result (`solidcore-tess`, 3 µm chord, inside the 10 µm band). This is the same method and the same thresholds as the SMLib run. On 67,679 points on boxes, cylinders, spheres and cones it gave 0 disagreements and 0 undecided. Tori could not be validated (finding 1).
- **Validity** means both that solidcore's own check passes (`Body::check` at the geometry level) and that the body is a closed manifold solid. The two verdicts are recorded separately.
- **Fillets** use solidcore-ops' `blend` with a constant-radius rolling-ball round and its corners filled, which is the same request as OCCT's. ops gives face normals only at the middle of an edge, so solidcore's sharp edges and face angles are judged there, not at three points along the edge as for OCCT.
- **Timing** covers the boolean, its volume and its validity check, as for OCCT. On sequence steps the boolean alone is about 350 ms of a median 397 ms.
- **Reproducibility.** Every failure examined was replayed and came out the same: all 91 sequence errors, all 5 wrong or invalid sequences, and 200 failed fillets. The sequence failures also came out the same when operands were given to the boolean directly, without the copies the adapter makes.

### Finding 1: a moved torus is broken

`Body::transform` is the only way solidcore-ops places a body. Applied to a torus, even as a translation of 1e-9 mm, it leaves a body whose tolerance is not finite and positive. The volume stays correct to eight digits, but:

- solidcore's own check rejects the body;
- `classify_point` calls nearly every point inside it outside;
- the body cannot be converted to a record, so it cannot be meshed and its edges cannot be listed.

A torus made in place, or moved by the identity matrix, is fine. Boxes, cylinders, spheres and cones moved by the same matrices are fine. SMLib's run placed tori through a different call and had no such problem.

Every input in this benchmark is placed in a random orientation, so every generic pair and fillet case containing a torus starts from an input that solidcore itself calls invalid. Those rows are shown separately below and are not counted as boolean or fillet failures. The near-degenerate pairs and the feature sequences use no tori.

### Booleans

Pairs with any failure:

| Set | Pairs | OCCT | SMLib | solidcore |
|---|---|---|---|---|
| Near-degenerate, all families except the tangent hole | 1,800 | 0 | 1 | 78 |
| Tangent hole, offset of one micron or less | 180 | 0 | 180 | 180 |
| Tangent hole, larger offset | 120 | 0 | 1 | 9 |
| Generic position, no torus | 386 | 0 | 0 of 188 | 0 |
| Generic position, with a torus (finding 1) | 214 | 0 | 0 of 94 | 160 |

| Set | Operations | solidcore: error | solidcore: invalid solid | solidcore: wrong solid |
|---|---|---|---|---|
| Near-degenerate | 6,300 | 386 | 45 | 0 |
| Generic position, no torus | 1,158 | 0 | 0 | 0 |
| Generic position, with a torus | 642 | 0 | 243 | 147 |

- **Tangent hole within a micron.** solidcore refuses all 180 pairs with `NotSolid`, which is its own check that a boolean of solids must give a closed body. SMLib returned an open body for the same 180, and OCCT returned a solid with a wall a few nanometres thick. solidcore's refusal is the more useful answer. The 9 larger-offset failures are all at an offset of −0.1 mm, where the hole breaks 0.1 mm through the wall. They are 8 `Status(1007)` and 1 `Status(1001)`.
- **Cylinder axis on a box edge**: 41 unions refused with `NotSolid`. These are all 20 pairs at an offset of −10 µm, all 20 at −1 µm, and 1 at −0.1 µm, with the axis just outside the edge. SMLib had no failure in this family.
- **Faces 10 µm apart, which is solidcore's tolerance.** Stacked and flush blocks at an offset of exactly ±1e-5 gave 25 results solidcore's check rejects for vertex-to-face gaps of 1e-5 against a tolerance of 1e-5. A sphere sunk 10 µm into a face, then subtracted, gave 20 more with a face loop of zero area.
- **No near-degenerate or torus-free generic boolean returned a wrong solid.** The 1,158 torus-free generic operations were all correct.
- OCCT's two failures in the earlier run, the tangent sphere united with the block, passed on this machine. Of the 2,682 rows the two OCCT runs share, 7 differ: these 2, and 5 final fillets in the sequences. All twelve booleans of every sequence match.

### Feature sequences

| | Sequences | Completed all 12 booleans | Stopped: error | Stopped: invalid solid | Stopped: wrong solid | Final fillet failed, of those completed | Median time for 12 steps |
|---|---|---|---|---|---|---|---|
| OCCT (this machine) | 300 | 300 | 0 | 0 | 0 | 27 of 300 (9.0%) | 94 ms |
| SMLib | 300 | 205 | 93 | 0 | 2 | 39 of 205 (19.0%) | not comparable |
| solidcore | 300 | 204 (68%) | 91 | 1 | 4 | 34 of 204 (16.7%) | 6.7 s |

- **solidcore fails where SMLib fails.** Its 204 completed sequences are a subset of SMLib's 205. Of the 95 sequences both fail, 93 fail at the same step on the same tool. Of solidcore's 91 errors, 90 are `Status(1001)`, SMLib's generic failure code, and 81 occur when cutting a through hole.
- **Three sequences returned an empty body and reported success.** Two came from cutting a through hole (from bodies of 704,117 and 445,256 mm³), and one from *uniting* a boss with a body of 547,744 mm³, which can never be empty. Each is reproducible. This is the worst outcome in the benchmark, because nothing tells the user.
- **One sequence returned a solid missing material.** After a pocket cut at step 8, a point 1.34 mm inside a rib added at step 7 is outside the result. The winding number and solidcore's own classifier agree.
- One spherical cut gave a solid that solidcore's check rejects.
- OCCT's final fillet failed on 20 of the 204 sequences solidcore completed. solidcore's failed on 34.

### Fillets

Cases with a torus are excluded (finding 1). Each kernel attempted almost exactly the same cases, 1,873 for OCCT and 1,874 for solidcore. A case is skipped when its solid has no sharp edge.

| Edges rounded | Radius, as a fraction of the shortest sharp edge | Cases | OCCT failed | solidcore failed |
|---|---|---|---|---|
| One | 2% | 316 | 3.2% | 21.2% |
| One | 5% | 304 | 2.6% | 29.9% |
| One | 15% | 314 | 6.1% | 29.3% |
| All | 2% | 313 | 2.6% | 37.4% |
| All | 5% | 300 | 8.3% | 39.7% |
| All | 15% | 326 / 327 | 22.1% | 45.3% |

| Edges rounded | Solid | Cases | OCCT failed | solidcore failed |
|---|---|---|---|---|
| One | A single primitive | 299 | 0.0% | 0.0% |
| One | Union of two | 206 | 4.4% | 38.8% |
| One | Subtraction | 236 | 6.4% | 40.3% |
| One | Intersection | 193 | 6.7% | 38.9% |
| All | A single primitive | 270 | 3.7% | 3.7% |
| All | Union of two | 256 | 12.9% | 49.2% |
| All | Subtraction | 207 / 208 | 17.9% | 64.4% |
| All | Intersection | 206 | 12.1% | 55.3% |

| Edges rounded | Angle between the faces along the edge, as each kernel measures it | OCCT: cases, failed | solidcore: cases, failed |
|---|---|---|---|
| One | Between 45 and 135 degrees | 849, 2.6% | 859, 23.3% |
| One | Shallower or sharper | 85, 17.6% | 67, 62.7% |
| All | Between 45 and 135 degrees | 523, 8.4% | 594, 26.4% |
| All | Shallower or sharper | 416, 14.7% | 340, 65.0% |

- Of solidcore's 634 torus-free failures, 620 are errors and 14 are invalid solids. In a sample of 200, the errors were `Status(1001)` (107), `NoRoom` (51), `NotSolid` (22), `TooLarge` (8) and `RoundsCross` (4). None was a refusal for an unported or unsupported path.
- In 14 of the errors, solidcore could not convert its own boolean result to a record (`Status(1007)`), so the edges could not be listed and no fillet was attempted.
- With a torus in the input, solidcore failed 68 to 76% of fillets, mostly because the moved torus's edges cannot be listed at all.

### Speed

| | OCCT, median / slowest 1% | solidcore, median / slowest 1% |
|---|---|---|
| Near-degenerate boolean | 1.9 / 5.6 ms | 77 / 631 ms |
| Generic boolean, no torus | 7.2 / 62 ms | 169 / 821 ms |
| 12-step sequence | 94 ms | 6.7 s |

solidcore was 23 to 71 times slower than OCCT here. This is a release build with default settings.

### Reading the solidcore results

1. **On booleans, solidcore today behaves like the SMLib it came from.** It fails the same sequences at the same steps, with the same error code, and completes 68% of 12-step sequences against OCCT's 100%.
2. **Where it differs from SMLib, it is both better and worse.** At the tangent hole it refuses where SMLib returned a broken body. But it refuses unions that SMLib built, and it returned three empty bodies reported as success where SMLib returned none.
3. **Two defects were found before any boolean was scored**: tori break when moved, and point classification is wrong on about 1 point in 7,500 on valid primitives. Both are confirmed by solidcore's own check or by the closed form. Neither would show in a test that only runs booleans.
4. **Its fillets match OCCT's on single primitives and fail far more often on anything built by a boolean**: about 40% for one edge, against about 5% for OCCT.
5. **No crash, hang or panic** occurred in 6,000 cases, and every failure replayed identically, which is consistent with its aims of no panics and determinism.
6. These results describe solidcore at one commit of a project under active development. Its own status page calls integration in progress.

## Surface intersection: the public corpus

The [SSI corpus](https://github.com/jyviko/ssi-corpus) at commit `b04c8a6` was scored against OCCT using `ssi/occt_ssi_runner.py`, at the corpus's standard tolerance of 1e-6. Before scoring, the runner's construction of each surface was validated: for 118 of the 119 cases the corpus's exact intersection points lie within 1e-6 of the surfaces as built. The remaining case could not be checked that way because the checking projection failed at a seam.

| Engine | Pass, of 119 | Source |
|---|---|---|
| OCCT, surface-level intersector (`GeomInt_IntSS`) | 65 | Measured here |
| OCCT, the intersector its booleans use (`IntTools_FaceFace`) | 66 | Measured here |
| SMLib | 81 | Published by solidcore; not re-run here |
| solidcore's new intersector | 118 | Its authors' figure; not re-run here |

| Class | Cases | OCCT surface-level | OCCT boolean-level |
|---|---|---|---|
| Transversal | 14 | 14 | 14 |
| Tangent along a curve | 10 | 3 | 3 |
| Isolated tangent point | 7 | 3 | 3 |
| Singular point | 6 | 4 | 4 |
| Patch boundary | 8 | 6 | 6 |
| Coincident region | 7 | 0 | 1 |
| Near-degenerate | 24 | 14 | 14 |
| Seam, pole, closed surface | 12 | 9 | 9 |
| High degree, rational | 6 | 6 | 6 |
| From the 2023 paper, published data | 6 | 4 | 4 |
| From the 2023 paper, reconstructed | 19 | 2 | 2 |

OCCT returned no crash and no error on any case. Its 53 non-passing results at boolean level are 40 incomplete and 13 with wrong topology. Median time was about 2 ms per case.

Reading:

1. **OCCT is weaker than SMLib at surface intersection on hard cases**, and both are far behind what solidcore claims for its new intersector. OCCT handles every transversal and high-degree case and loses at tangency, coincidence and near-degeneracy, the same places SMLib loses.
2. **The coincident-region score understates OCCT.** OCCT's booleans detect coincident faces by a separate route before intersecting, which is why its booleans handled flush faces without failure above while its intersector scores 1 of 7 here.
3. **Intersection scores do not predict boolean reliability.** SMLib beats OCCT 81 to 66 here and loses 68% to 100% on feature sequences. A kernel is more than its intersector, and the layers above it matter at least as much.
4. The reconstructed cases from the 2023 paper are where OCCT does worst, 2 of 19. They are tangential configurations chosen by that paper to be hard. This is the clearest measured weakness found in OCCT's geometry.

## quiddity 0.4.9: feature recognition

Sixty plates were generated with features placed on a grid so none overlap: through holes, blind holes, rectangular pockets, cylindrical bosses and rounded corners, each plate in a random orientation. They were written to STEP by OCCT and given to quiddity with no other information. The generator is `recognition/quiddity_eval.py`.

| Feature | In the 60 parts | Parts where quiddity's answer matched exactly |
|---|---|---|
| Through holes, with diameters | 99 | 60 of 60 |
| Blind holes, with diameters | 97 | 60 of 60 |
| Rectangular pockets | 94 | 60 of 60 |
| Cylindrical bosses, with diameters | 87 | 60 of 60 |
| Rounded corner edges | 116 | 60 of 60 |

Median time was 0.13 seconds per part, with no errors.

Reading:

- On clean, well-separated features, recognition is exact, including diameters and whether a hole is through or blind. That is the recognition half of recovering a parametric model from a STEP file, working today under Apache-2.0.
- This is an easy test. Features do not interact, there are no freeform faces, and no feature is cut by another. Real parts are harder, and this says nothing about them.
- quiddity reports features. It does not build an editable feature tree or decide the order of operations, which is the part of reconstruction still to be written.

## Reference survival

Method and outcome names are in [REFERENCE-SURVIVAL.md](REFERENCE-SURVIVAL.md). Run on 2026-11-12 with OCCT 8.0.1 and FreeCAD 1.1.4. Raw results and the full table for each system, by class of edit and model size, are in [`results/2026-11-12/`](../results/2026-11-12/).

990 cases, 8 references each where 8 well-posed ones could be found (7,920 references; 354 candidates passed over). Models have 10, 50 or 200 features.

| System | Cases completed | Notes |
|---|---|---|
| `occt_index` | 990 of 990 | |
| `occt_history` | 990 of 990 | |
| `freecad_partdesign` | 540 of 540 at 10 features, 358 of 360 at 50, 1 of 11 tried at 200 | See "FreeCAD at 200 features" below |

### Where the face is still there, in one piece

This is the common case, and the one where "silent wrong" does the most harm.

| System | Features | References | Correct | Silent wrong | False loss |
|---|---|---|---|---|---|
| `occt_index` | 10 | 3,981 | 2,558 (64.3%) | 1,400 (35.2%) | 23 (0.6%) |
| `occt_index` | 50 | 2,545 | 1,432 (56.3%) | 1,107 (43.5%) | 6 (0.2%) |
| `occt_index` | 200 | 614 | 309 (50.3%) | 305 (49.7%) | 0 |
| `occt_history` | 10 | 3,977 | 3,977 (100%) | 0 | 0 |
| `occt_history` | 50 | 2,540 | 2,540 (100%) | 0 | 0 |
| `occt_history` | 200 | 612 | 612 (100%) | 0 | 0 |
| `freecad_partdesign` | 10 | 3,983 | 3,751 (94.2%) | 0 | 232 (5.8%) |
| `freecad_partdesign` | 50 | 2,525 | 2,346 (92.9%) | 44 (1.7%) | 135 (5.3%) |

The counts differ slightly between systems because references that could not be judged are left out (see "Rows not judged").

By class of edit, at 10 and 50 features together, which all three systems completed:

| Edit | `occt_index` correct | silent wrong | `occt_history` correct | silent wrong | `freecad_partdesign` correct | silent wrong | false loss |
|---|---|---|---|---|---|---|---|
| A: dimension change | 92.0% | 61 | 100% | 0 | 99.1% | 0 | 7 |
| B: feature appended | 41.0% | 464 | 100% | 0 | 95.7% | 24 | 10 |
| C: feature moved | 60.6% | 302 | 100% | 0 | 90.6% | 0 | 72 |
| D: slot cut through (split) | 16.3% | 452 | 100% | 0 | 89.0% | 0 | 60 |
| E: slot shortened (merge) | 18.4% | 592 | 100% | 0 | 77.1% | 1 | 167 |
| F: feature removed | 56.3% | 242 | 100% | 0 | 99.0% | 0 | 6 |
| G: feature inserted upstream | 51.4% | 377 | 100% | 0 | 97.7% | 13 | 5 |
| H: two features reordered | 97.8% | 17 | 100% | 0 | 100% | 0 | 0 |
| J: edit made and undone | 100% | 0 | 100% | 0 | 94.1% | 6 | 40 |

Each class has between 545 and 790 references per system.

### Where the face is gone

| System | Features | References | Correctly lost | Silent wrong |
|---|---|---|---|---|
| `occt_index` | 10 | 176 | 16 | 160 |
| `occt_index` | 50 | 117 | 0 | 117 |
| `occt_index` | 200 | 27 | 0 | 27 |
| `occt_history` | 10 | 176 | 176 | 0 |
| `occt_history` | 50 | 117 | 117 | 0 |
| `occt_history` | 200 | 27 | 27 | 0 |
| `freecad_partdesign` | 10 | 176 | 176 | 0 |
| `freecad_partdesign` | 50 | 117 | 115 | 2 |

### Where the surface now bounds the solid in several pieces

No response here is called right or wrong, except a point on a different surface altogether, which is silent wrong.

| System | Features | References | All pieces | One piece at pick | One piece elsewhere | Some pieces | Lost on split | Silent wrong |
|---|---|---|---|---|---|---|---|---|
| `occt_index` | 10 and 50 | 377 | 0 | 148 | 37 | 0 | 2 | 190 |
| `occt_index` | 200 | 71 | 0 | 18 | 2 | 0 | 0 | 51 |
| `occt_history` | 10 and 50 | 375 | 371 | 3 | 0 | 1 | 0 | 0 |
| `occt_history` | 200 | 69 | 68 | 1 | 0 | 0 | 0 | 0 |
| `freecad_partdesign` | 10 and 50 | 376 | 0 | 238 | 27 | 0 | 106 | 5 |

The five `occt_history` rows that are not "all pieces" were each checked by hand. In all five the history returned every face there was: the method had counted one face as two, because the two parts were joined by a neck narrower than its sampling grid. So `occt_history` returned every piece in every case.

### Reading the reference-survival results

1. **A reference with no naming is wrong about half the time, and says nothing.** A face's position in the kernel's list survives a dimension change (92%) and little else. When the face is deleted, the position almost always resolves to some other face. This is the floor, and it gets worse with model size.
2. **OCCT's Boolean history, carried from one Boolean to the next, was exact on these models.** Of 7,129 references to a face that survived in one piece, all resolved to the right face. All 320 references to a deleted face were reported lost. Every piece of a divided face was returned. This held at 200 features as at 10. No naming scheme sits on top of it: only a label on each primitive face, moved to whatever OCCT says the face became.
3. **That result is narrower than it looks.** The models are boxes, cylinders and spheres joined by Booleans, with no fillets, no sketches and no coincident faces, and every reference is to a face. It shows that kernel history is sufficient for Boolean-only models of this depth. It does not show it for fillets, where Parasolid's own documentation calls its lineage ambiguous, or for edges. And `occt_history` cannot say which piece of a divided face was meant; it returns them all.
4. **FreeCAD loses references it need not lose.** About 5.6% of references to a face that is still there in one piece are reported lost. The loss is concentrated where a neighbouring feature changes the face's outline: a slot shortened (22.7% lost), a slot cut through (11.0%), a feature moved (9.4%). When a face is divided, FreeCAD reports the reference lost 28% of the time and otherwise follows one piece.
5. **A FreeCAD reference lost by an edit stays lost when the edit is undone.** After a dimension is changed and changed back, 40 of 775 references are still reported lost though the model is what it was.
6. **FreeCAD was silently wrong on 51 references, all in 50-feature models.** They fall in 14 of the 358 cases; none of the 540 ten-feature cases has one. In the cases examined, the solid FreeCAD built was the right one, the face numbering had shifted, and the link still held its old face number, so it pointed at a different face. Other links in the same model were renumbered correctly. Most are after a feature is added (40 of 51). The cause inside FreeCAD has not been found. One case examined twice gave a different number of stale links each time, so the behaviour may not be repeatable.
7. **FreeCAD reported a deleted face as lost in 291 of 293 cases.**

### Wrong solids found on the way

The method needs the solid a system builds to be the solid modelled, and twice it was not, with no error from the system:

- **OCCT, one 200-feature model of 90** (case 932). The result had 124 faces and the picked points lay 11 to 20 mm off it. All 8 picks failed, for both OCCT systems.
- **FreeCAD, one 50-feature model of 360** (case 886). The body came out as three separate solids of about 9,100 mm³ in total. 7 of 8 picks failed.

FreeCAD also failed to build 2 of the 360 fifty-feature models, reporting features in error.

### FreeCAD at 200 features

Not measured. A 200-feature case takes FreeCAD about 25 minutes, against about 2 minutes for the OCCT systems on the same models (both figures include the method's own checking). Of 11 cases tried, 1 completed in 1,446 s with all 8 references correct, 6 ran past the 1,500 s limit, 3 failed to rebuild with features in error, and 1 was lost to the fault in the adapter described next. The remaining 79 were not tried. Rebuild time is not what this suite measures, and the figure is given only to explain the gap.

### Rows not judged

- `occt_history`: 19 references unscored. Those examined were sliver faces (areas from 0.00002 to 0.02 mm²) that OCCT made beside the real face and that carry its name. They are too small for the method's grid to see, so the point returned on them cannot be judged.
- `occt_index`: 4 unscored, for the same reason.
- Both OCCT systems: 8 picks failed, all in case 932 above. FreeCAD: 7 picks failed, all in case 886 above.

### A correction made during the FreeCAD run

FreeCAD's `distToShape`, which the adapter first used to find the face under a picked point, throws an unknown C++ exception on some faces of 50-feature bodies. 34 cases at 50 features were first recorded as failures for that reason. The adapter now tests the point against each face's own surface and boundary, which agrees with the old test on all 432 references where the old test ran, and those 34 cases were run again. Their results are in the published file. 35 of FreeCAD's 51 silent-wrong references are in 11 of those 34 cases, and 16 are in 3 of the other 324, so the bodies that upset `distToShape` are also the ones where links go stale far more often. Why is not known.
