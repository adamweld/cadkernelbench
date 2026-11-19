# The FreeCAD parts library

Real parts from the [FreeCAD parts library](https://github.com/FreeCAD/FreeCAD-library), run by every
kernel with the operations of [`corpus/`](../README.md). The parts are licensed
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) by their authors, at the commit `parts.tsv`
names; each part's author is credited in [ATTRIBUTION.md](ATTRIBUTION.md), and anything published here
that names a part links to that credit.

- `parts.tsv`: every STEP file of the library at that commit, its git blob hash, its author (the person
  who added it, as the library directs), and whether it is used. 2,442 are used. Left out: folders the
  library holds under other terms (an LGPL folder of clearance-hole cylinders, a CC BY-SA and a CC BY 2.0
  model), vendors' and third parties' models re-uploaded to the library, two empty files, and 24 whose
  origin is unstated (commercial boards, kit pieces, pallets) until each is checked.
- `fetch.py`: fetches the used parts, at the commit, into `~/data/freecad-library` (a partial clone, checked
  out sparsely) and checks each against its blob hash. The files are not copied into this repository.
- `attribution.py`: writes ATTRIBUTION.md from `parts.tsv`.
- `results/`: what each kernel did with each part.

Three generated families make up most of the library: 912 EN profiles, 622 fasteners and 429 chain
sprockets. They are much alike within a family, so a run takes at most 100 parts of each family
(`--per-family 100`, the first by blob hash) and the rest whole: 750 parts.

```bash
python corpus/freecad-library/fetch.py
for k in occt cadrs; do
  python corpus/run.py --kernel $k --manifest corpus/freecad-library/parts.tsv --data ~/data/freecad-library \
    --out corpus/freecad-library/results/$k.jsonl.gz --per-family 100
done
python corpus/summarize.py corpus/freecad-library/results
```

There is no exact answer for a real part: see [`corpus/`](../README.md) for what the outcomes mean.
A failure found here is reported to a kernel's authors as a small case written fresh, crediting the
part it was found on.
