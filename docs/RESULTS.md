# Results

OCCT and SMLib were first run on 2026-11-10 on a 4-core Linux machine with 16 GB of memory; solidcore, and OCCT again for pairing with it, on 2026-11-11, and cadrs on 2026-11-12, on the machine described in the solidcore section. Method and limits are in [METHOD.md](METHOD.md). Raw output is in [../results/2026-11-10/](../results/2026-11-10/).

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
| Tangent hole, offset of 1 nm or less | 180 | 0 | 180 |
| Tangent hole, larger offset | 120 | 0 | 1 |
| Generic position | 282 | 0 | 0 |

- OCCT's two failures are a sphere exactly touching a face, united with the block, whose exact result is not a manifold solid.
- SMLib's one failure outside the tangent-hole family is a wrong solid: a sphere sunk 1 nm into a face, united with the block, where one sample point was misclassified.
- **The tangent-hole split is a difference in tolerance, not a clear defect in either.** At 1 nm or less the wall is thinner than SMLib's working tolerance, and SMLib returns a result that is not a closed solid. OCCT works to a tighter tolerance and returns a solid with a wall at most 1 nm thick. Neither answer is obviously the right one for a designer.
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

Run on 2026-11-11 on an Apple M1 Max (8 performance and 2 efficiency cores, 32 GB, macOS 26.6.2), not the machine above. solidcore is at SolidCraft commit `75a74aee` (its crate's version 1.0.1), built with Rust 1.98.0 and driven by `ckb/kernels/solidcore.py` through `solidcore_server`, a small program over solidcore-ops. On the same machine, OCCT 8.0.1 (cadquery-ocp 8.0.1.1.0) was re-run on the same `--fuzzy0` case list, fillets and all 600 generic pairs included, so every row below compares identical inputs. The cadrs columns come from the 2026-11-12 run on the same machine, described in its own section below. SMLib's figures are from the run above; it was not run on fillets, and its generic set stops at 282 pairs. Raw output is in [../results/2026-11-11/](../results/2026-11-11/).

solidcore describes itself as based on SMLib: it began as a port to Rust and has since diverged.

The release build took 4 minutes on this machine. Its largest compiler process peaked at 5.1 GB.

### Validating the instrument first

- **Placement.** After placement, the bounding boxes of boxes, cylinders and cones agree with OCCT's to 1e-7, and with the exact boxes to 1e-13 (`results/2026-11-12/validate_solidcore.txt`). solidcore's sphere boxes are up to 1.2 mm off the exact box, and smaller than it for 3 of 117 spheres. Bounding boxes only choose where sample points are drawn, so a box that is too small leaves part of a solid untested but does not change how any point is judged. (An earlier version of this page said solidcore's sphere and torus boxes were tighter than OCCT's; that was wrong.)
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

| Set | Pairs | OCCT | SMLib | solidcore | cadrs |
|---|---|---|---|---|---|
| Near-degenerate, all families except the tangent hole | 1,800 | 0 | 1 | 78 | 66 |
| Tangent hole, offset of 1 nm or less | 180 | 0 | 180 | 180 | 81 |
| Tangent hole, larger offset | 120 | 0 | 1 | 9 | 0 |
| Generic position, no torus | 386 | 0 | 0 of 188 | 0 | 0 |
| Generic position, with a torus (finding 1) | 214 | 0 | 0 of 94 | 160 | 1 |

| Set | Operations | solidcore: error | solidcore: invalid solid | solidcore: wrong solid |
|---|---|---|---|---|
| Near-degenerate | 6,300 | 386 | 45 | 0 |
| Generic position, no torus | 1,158 | 0 | 0 | 0 |
| Generic position, with a torus | 642 | 0 | 243 | 147 |

- **Tangent hole within 1 nm.** solidcore refuses all 180 pairs with `NotSolid`, which is its own check that a boolean of solids must give a closed body. SMLib returned an open body for the same 180, and OCCT returned a solid with a wall at most 1 nm thick. solidcore's refusal is the more useful answer. The 9 larger-offset failures are all at an offset of −0.1 µm, where the hole breaks 0.1 µm through the wall. They are 8 `Status(1007)` and 1 `Status(1001)`.
- **Cylinder axis on a box edge**: 41 unions refused with `NotSolid`. These are all 20 pairs at an offset of −10 nm, all 20 at −1 nm, and 1 at −0.1 nm, with the axis just outside the edge. SMLib had no failure in this family.
- **Faces 10 nm apart, which is solidcore's tolerance.** Stacked and flush blocks at an offset of exactly ±1e-5 gave 25 results solidcore's check rejects for vertex-to-face gaps of 1e-5 against a tolerance of 1e-5. A sphere sunk 10 nm into a face, then subtracted, gave 20 more with a face loop of zero area.
- **No near-degenerate or torus-free generic boolean returned a wrong solid.** The 1,158 torus-free generic operations were all correct.
- OCCT's two failures in the earlier run, the tangent sphere united with the block, passed on this machine. Of the 2,682 rows the two OCCT runs share, 7 differ: these 2, and 5 final fillets in the sequences. All twelve booleans of every sequence match.

### Feature sequences

| | Sequences | Completed all 12 booleans | Stopped: error | Stopped: invalid solid | Stopped: wrong solid | Final fillet failed, of those completed | Median time for 12 steps |
|---|---|---|---|---|---|---|---|
| OCCT (this machine) | 300 | 300 | 0 | 0 | 0 | 27 of 300 (9.0%) | 94 ms |
| SMLib | 300 | 205 | 93 | 0 | 2 | 39 of 205 (19.0%) | not comparable |
| solidcore | 300 | 204 (68%) | 91 | 1 | 4 | 34 of 204 (16.7%) | 6.7 s |
| cadrs | 300 | 300 | 0 | 0 | 0 | 0 of 300 (0.0%) | 68 ms |

- **solidcore fails where SMLib fails.** Its 204 completed sequences are a subset of SMLib's 205. Of the 95 sequences both fail, 93 fail at the same step on the same tool. Of solidcore's 91 errors, 90 are `Status(1001)`, SMLib's generic failure code, and 81 occur when cutting a through hole.
- **Three sequences returned an empty body and reported success.** Two came from cutting a through hole (from bodies of 704,117 and 445,256 mm³), and one from *uniting* a boss with a body of 547,744 mm³, which can never be empty. Each is reproducible. This is the worst outcome in the benchmark, because nothing tells the user.
- **One sequence returned a solid missing material.** After a pocket cut at step 8, a point 1.34 mm inside a rib added at step 7 is outside the result. The winding number and solidcore's own classifier agree.
- One spherical cut gave a solid that solidcore's check rejects.
- OCCT's final fillet failed on 20 of the 204 sequences solidcore completed. solidcore's failed on 34.

### Fillets

Cases with a torus are excluded (finding 1). Each kernel attempted almost exactly the same cases, 1,873 for OCCT and 1,874 for solidcore. A case is skipped when its solid has no sharp edge.

| Edges rounded | Radius, as a fraction of the shortest sharp edge | Cases | OCCT failed | solidcore failed | cadrs failed |
|---|---|---|---|---|---|
| One | 2% | 316 | 3.2% | 21.2% | 1.3% |
| One | 5% | 304 | 2.6% | 29.9% | 3.9% |
| One | 15% | 314 | 6.1% | 29.3% | 6.1% |
| All | 2% | 313 | 2.6% | 37.4% | 5.4% |
| All | 5% | 300 | 8.3% | 39.7% | 10.7% |
| All | 15% | 326 / 327 | 22.1% | 45.3% | 16.9% |

| Edges rounded | Solid | Cases | OCCT failed | solidcore failed | cadrs failed |
|---|---|---|---|---|---|
| One | A single primitive | 299 | 0.0% | 0.0% | 0.0% |
| One | Union of two | 206 | 4.4% | 38.8% | 2.9% |
| One | Subtraction | 236 | 6.4% | 40.3% | 6.8% |
| One | Intersection | 193 | 6.7% | 38.9% | 6.7% |
| All | A single primitive | 270 | 3.7% | 3.7% | 0.0% |
| All | Union of two | 256 | 12.9% | 49.2% | 7.4% |
| All | Subtraction | 207 / 208 | 17.9% | 64.4% | 26.6% |
| All | Intersection | 206 | 12.1% | 55.3% | 14.6% |

| Edges rounded | Angle between the faces along the edge, as each kernel measures it | OCCT: cases, failed | solidcore: cases, failed | cadrs: cases, failed |
|---|---|---|---|---|
| One | Between 45 and 135 degrees | 849, 2.6% | 859, 23.3% | 864, 3.1% |
| One | Shallower or sharper | 85, 17.6% | 67, 62.7% | 70, 11.4% |
| All | Between 45 and 135 degrees | 523, 8.4% | 594, 26.4% | 548, 7.5% |
| All | Shallower or sharper | 416, 14.7% | 340, 65.0% | 391, 16.1% |

- Of solidcore's 634 torus-free failures, 620 are errors and 14 are invalid solids. In a sample of 200, the errors were `Status(1001)` (107), `NoRoom` (51), `NotSolid` (22), `TooLarge` (8) and `RoundsCross` (4). None was a refusal for an unported or unsupported path.
- In 14 of the errors, solidcore could not convert its own boolean result to a record (`Status(1007)`), so the edges could not be listed and no fillet was attempted.
- With a torus in the input, solidcore failed 68 to 76% of fillets, mostly because the moved torus's edges cannot be listed at all.

### Speed

| | OCCT, median / slowest 1% | solidcore, median / slowest 1% | cadrs, median / slowest 1% |
|---|---|---|---|
| Near-degenerate boolean | 1.9 / 5.6 ms | 77 / 631 ms | 1.6 / 33 ms |
| Generic boolean, no torus | 7.2 / 62 ms | 169 / 821 ms | 5.4 / 29 ms |
| 12-step sequence | 94 ms | 6.7 s | 68 ms |

solidcore was 23 to 71 times slower than OCCT here. This is a release build with default settings.

### Reading the solidcore results

1. **On booleans, solidcore today behaves like the SMLib it came from.** It fails the same sequences at the same steps, with the same error code, and completes 68% of 12-step sequences against OCCT's 100%.
2. **Where it differs from SMLib, it is both better and worse.** At the tangent hole it refuses where SMLib returned a broken body. But it refuses unions that SMLib built, and it returned three empty bodies reported as success where SMLib returned none.
3. **Two defects were found before any boolean was scored**: tori break when moved, and point classification is wrong on about 1 point in 7,500 on valid primitives. Both are confirmed by solidcore's own check or by the closed form. Neither would show in a test that only runs booleans.
4. **Its fillets match OCCT's on single primitives and fail far more often on anything built by a boolean**: about 40% for one edge, against about 5% for OCCT.
5. **No crash, hang or panic** occurred in 6,000 cases, and every failure replayed identically, which is consistent with its aims of no panics and determinism.
6. These results describe solidcore at one commit of a project under active development. Its own status page calls integration in progress.

## cadrs, compared with OCCT, SMLib and solidcore on identical cases

Run on 2026-11-12 on the same Apple M1 Max as the solidcore run (32 GB, macOS 26.6.2), on the same `--fuzzy0` case list, paired with the OCCT run of 2026-11-11 from that machine (cadquery-ocp 8.0.1.1.0, unchanged, so OCCT was not re-run). Raw output, validation transcripts and the scripts behind the replay and fillet checks are in [../results/2026-11-12/](../results/2026-11-12/).

- **What was measured.** The kernel of [cadrs](https://github.com/rvdende/cadrs), the `cadrs_kernel` crate, at commit `6525e80a` (workspace version 0.2.7). It was built with cadrs's pinned toolchain `nightly-2026-10-21` (rustc 1.101.0-nightly 19833af72) and driven by `ckb/kernels/cadrs.py` through `cadrs_server`, a small program over the crate's `Kernel` API. The release build took 1 minute 48 seconds, with a peak of 3.1 GB.
- **Authorship.** cadrs is essentially a single-author project: 1,200 of its 1,264 commits are by one author.
- **brep-bench.** Its v0.2.7 release notes say that on [brep-bench](https://brepbench.org) "cadrs builds every case, none of them meshed". brep-bench was not run here, and that result has not been reproduced.
- **Nothing is absent.** cadrs has every operation the benchmark uses: the five primitives, placement by a rigid motion (`Kernel::transform`), the three booleans, volume, its own validity check, point classification, edges with their faces, face normals and constant-radius fillets.
- **One convention.** cadrs reports an empty boolean result as an error (`EmptyResult`). That is an answer, not a failure, so the adapter turns it into an empty solid, judged by the point test like any other result.

### Validating the instrument first

- **Placement.** Each primitive's bounding box after placement was compared with its exact box, computed in closed form. cadrs's boxes are within 1e-13 mm of the exact box for all five kinds.
  - OCCT's agree with both, within OCCT's 1e-7 padding, for boxes, cylinders, cones and spheres.
  - For tori, OCCT's boxes are themselves wrong: up to 2.3 mm off, and smaller than the exact box for 14 of 88. So tori were compared with the closed form, not with OCCT.
- **The inside test.** cadrs's own classification (`Kernel::classify`, boundary band 1e-7 mm) agreed with the closed form on all 80,862 points, on all five kinds, with none undecided. It is the classifier used for the results.
  - The winding number about cadrs's own tessellation (3 µm chord, the SMLib and solidcore method and thresholds) also agreed on all 80,862 points. It is kept for cross-checking.
- **Validity.** cadrs has two verdicts, recorded separately. One is its own check at its strictest level (`Body::check_with(CheckLevel::Full)`). The other is whether the body is a closed manifold solid. cadrs has no function for the second, so the server computes it from the topology: a solid, every shell closed, no sheets, wires or loose points, and every edge of a face used exactly once in each direction.
  - The first version of that test also failed bodies with an unused entry in their edge list, an edge used by no face. That made 24 correct results "invalid", 17 of them from torus-free generic pairs. It was a bug in the benchmark. It was fixed, the whole run was repeated, and every figure here is from the repeat.
- **Sharp edges** are judged as for OCCT, by the face normals at 10%, 50% and 90% along each edge. `Kernel::fillet` carries a round on along tangent edges, as OCCT's does.
- **Fillets changed the body.** Every sequence's final fillet and 300 fillet cases recorded as successful were replayed, and in all 600 the volume changed and faces were added.
  - On single edges where the faces meet at 90 degrees, the median volume removed was 1.000000 times the closed form, (1 − π/4)·r²·L.
  - A few differ by much more, up to 4,248 times on a radius of 0.002 mm. Those 31 cases, with 5 typical ones as controls, were written to STEP before and after the fillet and measured with OCCT ([../results/2026-11-12/fillet_check/](../results/2026-11-12/fillet_check/)):
    - **29 agree.** OCCT's adaptive volume integration (error bound 1e-9) gives the same volume change to about 1e-5 mm³. Where OCCT could subtract one body from the other, the whole change touched the filleted edge. Ratios above 1 there come from the round continuing along tangent edges, and from edges that are not straight lines between planes.
    - **In 4, cadrs's own volume of the filleted body is off** by 0.045 to 0.125 mm³ in bodies of 380,000 to 643,000 mm³, at most about 3e-7 of the volume. OCCT finds a much smaller change, and in 3 of them its subtraction found that change at the edge alone. Volumes are not used to judge any result here. OCCT's default volume integration is off by up to 0.6%.
    - **3 are unresolved** (cases 5905, 5925 and 5995). After STEP export, OCCT reads cadrs's filleted body as 65, 2,081 and 216 mm³ larger than cadrs's own volume, and calls two of the three invalid. cadrs's own check passes, and its own mesh agrees with its own volume both before and after the fillet. So the fault is either in the STEP export or in a body cadrs's own tools cannot see wrong. The STEP files are in the folder above.
  - The benchmark does not judge fillet geometry for any kernel, so none of this changes a count above.
- **Every failure was replayed**: all 436 cases with a failure, three times, with the same outcome each time. The one hung case was replayed twice.
- **Timing** covers the boolean, its volume and both validity verdicts, as for the other kernels. On sequence steps the median operation took 3.3 ms, of which the validity check was 1.5 ms and the volume 0.17 ms.

### Booleans

Pairs with any failure:

| Set | Pairs | OCCT | SMLib | solidcore | cadrs |
|---|---|---|---|---|---|
| Near-degenerate, all families except the tangent hole | 1,800 | 0 | 1 | 78 | 66 |
| Tangent hole, offset of 1 nm or less | 180 | 0 | 180 | 180 | 81 |
| Tangent hole, larger offset | 120 | 0 | 1 | 9 | 0 |
| Generic position, no torus | 386 | 0 | 0 of 188 | 0 | 0 |
| Generic position, with a torus | 214 | 0 | 0 of 94 | 160 (moved torus broken) | 1 |

| Set | Operations | cadrs: error | cadrs: invalid solid | cadrs: wrong solid |
|---|---|---|---|---|
| Near-degenerate | 6,300 | 123 | 81 | 0 |
| Generic position, no torus | 1,158 | 0 | 0 | 0 |
| Generic position, with a torus | 642 | 3 | 0 | 0 |

The offsets below are in millimetres, as all lengths are; 1e-6 mm is 1 nm.

- **Tangent hole, 81 pairs.** The subtraction returned a body cadrs's own full check rejects, because two faces cross away from their edges. This happened in all 20 pairs at each of the offsets 0, 1 pm, 10 pm and 0.1 nm, and in 1 of 20 at 1 nm. In each case the wall left between the hole and the face is 1 nm thick or less. OCCT returned a solid, SMLib an open body, and solidcore refused.
- **Coaxial cylinders of nearly equal radius, 30 pairs.** All three operations were refused (`OpenResult` or `BooleanFailed`) when the second cylinder's radius is larger by 0.1 µm (10 of 20 pairs) or 1 µm (20 of 20). Equal radii, smaller differences, and a second radius smaller by the same amounts all succeeded. OCCT, SMLib and solidcore had no failure in this family.
- **The same block built twice, 29 pairs.** The subtraction was refused with `OpenResult` when the second block is 10 nm shorter (16 of 20), 1 nm shorter (9) or 1 nm longer (4).
- **Stacked blocks, 7 pairs.** The intersection was refused with `OpenResult` when the blocks overlap by 1 nm (7 of 20).
- **No near-degenerate or generic boolean returned a wrong solid.** The one generic failure is a pair with a torus, where all three operations were refused with `OpenResult`.

### Feature sequences

| | Sequences | Completed all 12 booleans | Stopped: error | Stopped: invalid solid | Stopped: wrong solid | Final fillet failed, of those completed | Median time for 12 steps |
|---|---|---|---|---|---|---|---|
| OCCT | 300 | 300 | 0 | 0 | 0 | 27 of 300 (9.0%) | 94 ms |
| SMLib | 300 | 205 | 93 | 0 | 2 | 39 of 205 (19.0%) | not comparable |
| solidcore | 300 | 204 | 91 | 1 | 4 | 34 of 204 (16.7%) | 6.7 s |
| cadrs | 300 | 300 | 0 | 0 | 0 | 0 of 300 (0.0%) | 68 ms |

- cadrs completed the 96 sequences that SMLib or solidcore could not.
- Every final fillet succeeded, with no failure in 300, where OCCT's failed 27 times. Each kernel rounds an edge it chose from its own list, so the two sets of 300 fillets are not the same edges.

### Fillets

Cases without a torus. Both kernels attempted 1,873, and both skipped 182 for having no sharp edge.

| Edges rounded | Radius, as a fraction of the shortest sharp edge | Cases | OCCT failed | solidcore failed | cadrs failed |
|---|---|---|---|---|---|
| One | 2% | 316 | 3.2% | 21.2% | 1.3% |
| One | 5% | 304 | 2.6% | 29.9% | 3.9% |
| One | 15% | 314 | 6.1% | 29.3% | 6.1% |
| All | 2% | 313 | 2.6% | 37.4% | 5.4% |
| All | 5% | 300 | 8.3% | 39.7% | 10.7% |
| All | 15% | 326 | 22.1% | 45.3% | 16.9% |

| Edges rounded | Solid | Cases | OCCT failed | cadrs failed |
|---|---|---|---|---|
| One | A single primitive | 299 | 0.0% | 0.0% |
| One | Union of two | 206 | 4.4% | 2.9% |
| One | Subtraction | 236 | 6.4% | 6.8% |
| One | Intersection | 193 | 6.7% | 6.7% |
| All | A single primitive | 270 | 3.7% | 0.0% |
| All | Union of two | 256 | 12.9% | 7.4% |
| All | Subtraction | 207 | 17.9% | 26.6% |
| All | Intersection | 206 | 12.1% | 14.6% |

| Edges rounded | Angle between the faces along the edge | OCCT: cases, failed | cadrs: cases, failed |
|---|---|---|---|
| One | Between 45 and 135 degrees | 849, 2.6% | 864, 3.1% |
| One | Shallower or sharper | 85, 17.6% | 70, 11.4% |
| All | Between 45 and 135 degrees | 523, 8.4% | 548, 7.5% |
| All | Shallower or sharper | 416, 14.7% | 391, 16.1% |

- **Overall, without a torus**, cadrs failed 139 of 1,873 fillets and OCCT 142.
  - All of cadrs's failures are refusals. None returned a body that fails either verdict. OCCT's 142 include 29 invalid solids.
  - Both kernels failed 63 of the same cases.
- **With a torus in the input**, which cadrs places correctly, cadrs failed 150 of 686 and OCCT 140 of 689.
- **Why cadrs refused**, over all 288 refusals:

  | Error | Refusals |
  |---|---|
  | `InvalidResult` | 79 |
  | `OpenResult` | 79 |
  | `BudgetExhausted` | 47 |
  | `BooleanFailed` | 34 |
  | `InvalidProfile` | 34 |
  | `TooLarge` | 15 |
  | `Unsupported` | none |

- **One case hung.** Rounding all 9 sharp edges of a union containing a torus, at 2% (fillet case 5121), ran past the 180-second limit applied to every kernel. Run alone it took 228 to 232 seconds and then refused with `OpenResult`. It is counted as hung, and as a failure in the fillet tables.

### Speed

| | OCCT, median / slowest 1% | cadrs, median / slowest 1% |
|---|---|---|
| Near-degenerate boolean | 1.9 / 5.6 ms | 1.6 / 33 ms |
| Generic boolean, no torus | 7.2 / 62 ms | 5.4 / 29 ms |
| 12-step sequence | 94 ms | 68 ms |
| Fillet, no torus | 6.5 / 101 ms | 14 / 1,094 ms |

Medians are close to OCCT's, and on booleans slightly lower. cadrs's slowest fillets are an order of magnitude slower than OCCT's, and one ran for about 230 seconds.

### Reading the cadrs results

1. **On booleans in sequence, cadrs matched OCCT.** It completed all 300 twelve-step sequences, which SMLib and solidcore managed only 204 or 205 times, and no boolean anywhere returned a wrong solid.
2. **On near-degenerate pairs it is weaker than OCCT**: 147 of 2,100 pairs failed against none. The failures sit at sub-micrometre offsets, and each is either a refusal or a body its own full check rejects:
   - walls 1 nm thick or less;
   - radii differing by 0.1 to 1 µm;
   - faces 1 to 10 nm apart.

   The coaxial-cylinder failures are the clearest weakness. They occur at the larger offsets of that family, where the other three kernels had none.
3. **Its fillets fail about as often as OCCT's** on these cases, more often on all edges of a subtraction and less often elsewhere, and never returned an invalid solid. In 300 sequences its final fillet never failed.
4. **Its speed is comparable to OCCT's**, with a long tail on fillets.
5. **Limits.** These results describe one commit of a young, essentially single-author project. They do not confirm its brep-bench claim, which concerns different cases. The limits in [METHOD.md](METHOD.md) apply as to every kernel here: analytic primitives only, clean input, and fillet geometry not judged.

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

Method and outcome names are in [REFERENCE-SURVIVAL.md](REFERENCE-SURVIVAL.md). The first full run of the two OCCT-based systems is in progress; no figures are published yet.
