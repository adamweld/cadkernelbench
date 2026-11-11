# Results

Run on 2026-11-10 on a 4-core Linux machine with 16 GB of memory. Method and limits are in [METHOD.md](METHOD.md). Raw output is in [../results/2026-11-10/](../results/2026-11-10/).

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
