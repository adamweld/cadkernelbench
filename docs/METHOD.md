# Method

## The cases

| Set | Size | What it is |
|---|---|---|
| Near-degenerate booleans | 2,100 pairs | Two primitives in a configuration that is degenerate when an offset is zero: a block resting on another's face, a block with one face flush with another's, a hole tangent to a wall, coaxial cylinders of equal radius, a sphere touching a face, a cylinder whose axis lies on an edge, and a solid built twice. The offset takes 15 values from zero to one micron and from there to one millimetre, in both directions |
| Generic booleans | 600 pairs | Two random primitives (box, cylinder, sphere, cone, torus) in random positions and orientations |
| Fillets | 3,000 cases | A primitive, or a boolean of two, with one sharp edge or all sharp edges rounded at 2%, 5% or 15% of the shortest sharp edge. 456 had no sharp edge and were skipped |
| Feature sequences | 300 | A block with 12 booleans applied in turn (holes, pockets, bosses, ribs, spherical cuts), about half placed flush with existing faces or centred on them, followed by one fillet. This is the shape of a real feature tree |

Every solid is placed in a random orientation, so coincidences hold only up to floating-point rounding, as they do in real models. Union, subtraction and intersection are each run on every pair.

## The check

No second kernel is used as a reference. Every input is an analytic primitive, so whether a point is inside it is known in closed form, and so is the correct answer for any combination of them. For each result:

1. The kernel's own validity check is run.
2. Sample points are classified against the result and compared with the closed-form answer. Points within 0.01 mm of any input's boundary are not used.

A result is counted as **error** if the kernel reported failure, **invalid** if it returned a solid that fails its own check, and **wrong** if it returned a valid-looking solid that misclassifies a point or is empty when it cannot be. Wrong is the worst outcome, because nothing tells the user.

The closed-form inside tests were themselves validated against each kernel on the input primitives before use: 23,954 points with OCCT and 2,397 with SMLib, with no disagreement.

## Three mistakes found in the instrument, and fixed

They are recorded because they show how easily a benchmark produces false failures.

1. The first version judged booleans by a volume identity. It flagged 0.8% of generic pairs as wrong. Dense re-checking showed the solids were right and OCCT's volume integration on curved trimmed faces was off by up to 0.6%. The point test replaced it.
2. The first version caught exceptions too broadly, so a mistake in the benchmark script was counted as a kernel error. Exceptions are now counted only when the kernel raised them, and anything else stops the run.

3. The first feature sequences included a hole exactly tangent to a wall. Its exact result has a wall of zero thickness, which is not a valid solid, so no kernel can be marked right or wrong on it. It was replaced by a hole whose axis lies in the wall, which leaves a half-round notch. The superseded results are kept in the results folder and described under OCCT below, because how a kernel behaves on such input is still informative.

A further hazard applies to SMLib: its Python package's memory use grows with every operation, by roughly 100 MB per case, until the process is killed. A process killed for memory would look like a kernel crash. Workers are restarted every 15 cases, and a case whose process was killed is retried in a fresh one before it counts.

## Limits of this measurement

- **Analytic primitives only.** No freeform NURBS surfaces, where the literature and the kernels' own documentation place most of the difficulty. The surface-intersection corpus below covers that for intersection, not for booleans.
- **Clean input.** No imported geometry with gaps or tolerances.
- **Small models.** At most 13 bodies' worth of faces.
- **Fillet existence is not proved.** Radii are small relative to the edges, but a fillet at 15% of the shortest edge may be geometrically impossible on some solids. The fillet figures are an upper bound on kernel failure. The single-edge, 2% figure on well-angled edges is the closest to a true failure rate.
- **About 150 sample points per result.** A defect smaller than about 1% of the sampled volume can be missed.
