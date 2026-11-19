# Results: the FreeCAD parts library

Run 2026-11-18 on an Apple-silicon Mac (10 cores, 3 jobs at once), 120 s per model and kernel.
OCCT 8.0.1 (cadquery-ocp) and cadrs_kernel (rvdende/cadrs, the checkout beside this one). 750 parts:
every part `parts.tsv` includes, at most 100 of each family. Parts are credited in
[ATTRIBUTION.md](ATTRIBUTION.md); per-part results are in `results/`.

| Operation | OCCT | cadrs |
|---|---|---|
| import | 100% ok | 100% ok |
| own validity check | 99.6% valid | 97.1% valid |
| STEP round trip | 99.6% ok; volume changed beyond 1e-6 on 7 | 99.6% ok; volume unchanged on all |
| mesh | 100% ok | 100% ok |
| boolean with a ball | 99.9% ok, 0.1% invalid | 93.0% ok, 6.4% error, 0.5% invalid |
| single-edge fillet (3 per part) | 76.0% ok, 19.0% error, 5.0% invalid | 76.9% ok, 22.8% error, 0.3% invalid |
| shell, largest planar face open | 50.5% ok, 29.8% error, 19.7% invalid | 64.4% ok, 24.4% error, 11.1% timeout |

Where both kernels answered ok, their volumes differ beyond 1e-6 on 43 of 750 parts as read, and on
87 of 700 after the boolean. Neither is known to be right on those: each disagreement is a part to
reduce to a small case. The fillet and shell sizes are fixed fractions of each part's size, so some
of those failures are requests no kernel could meet (a radius larger than a short edge allows, a wall
thicker than a thin plate); the rates compare the kernels, not an absolute standard. Every cadrs
timeout was in the shell.

`python corpus/summarize.py corpus/freecad-library/results` prints the table from the raw results.
