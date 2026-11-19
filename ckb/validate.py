# SPDX-License-Identifier: MIT OR Apache-2.0
"""Validate a kernel adapter before recording any result with it.

    python -m ckb.validate ckb.kernels.yourkernel [--prims 400] [--bbox out.json] [--inside NAME]

1. The closed-form inside tests against the kernel's own classification,
   on random primitives (every kind, random frames) and on both solids of
   every near-degenerate family (which place primitives off their local
   origin). Points within m.BAND of the boundary are skipped. Any
   disagreement, undecided point, or solid the kernel will not classify
   against is printed and makes the exit status 1.
2. Placement: each solid's bounding box from the kernel is compared with
   its exact box, computed in closed form from the primitive and its frame.
   The largest deviation is printed by kind, with the number of boxes
   smaller than the exact one (which would leave part of a solid out of
   the sample points). With --bbox, the boxes are also written out, to
   compare with another kernel's.
"""
import argparse
import collections
import importlib
import json
import math
import random
import sys

from ckb import core as m


def solids(n):
    """(label, Solid) for n random primitives and every near-degenerate family, seeded."""
    rng = random.Random(12345)
    for i in range(n):
        yield f"prim{i}", m.random_prim(rng, 50)
    for fam in m.NEAR_FAMILIES:
        for rep in range(10):
            eps = m.EPS[rep % len(m.EPS)]
            A, B = m.near_pair(fam, eps, random.Random(777 * rep + 1))
            yield f"{fam}{rep}A", A
            yield f"{fam}{rep}B", B


def exact_box(kind, fr, p, d):
    """The exact axis-aligned box of a placed primitive, from its closed form."""
    def disc(c, r):                       # a disc of radius r about the frame's local z axis
        g, ax = fr.pt(c), [fr.R[i][2] for i in range(3)]
        e = [r * math.sqrt(max(0.0, 1 - ax[i] ** 2)) for i in range(3)]
        return [g[i] - e[i] for i in range(3)] + [g[i] + e[i] for i in range(3)]

    def union(*bs):
        return [min(b[i] for b in bs) for i in range(3)] + [max(b[i] for b in bs) for i in range(3, 6)]
    if kind == "box":
        cs = [fr.pt([p[0] + a * d[0], p[1] + b * d[1], p[2] + c * d[2]]) for a in (0, 1) for b in (0, 1) for c in (0, 1)]
        return [min(x[i] for x in cs) for i in range(3)] + [max(x[i] for x in cs) for i in range(3)]
    if kind == "sph":
        g = fr.pt(p)
        return [g[i] - d[0] for i in range(3)] + [g[i] + d[0] for i in range(3)]
    if kind == "cyl":
        return union(disc(p, d[0]), disc([p[0], p[1], p[2] + d[1]], d[0]))
    if kind == "cone":
        return union(disc(p, d[0]), disc([p[0], p[1], p[2] + d[2]], d[1]))
    b = disc(p, d[0])                     # torus: its centre circle, widened by the tube
    return [b[i] - d[1] for i in range(3)] + [b[i] + d[1] for i in range(3, 6)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("module")
    ap.add_argument("--prims", type=int, default=400)
    ap.add_argument("--bbox")
    ap.add_argument("--inside", help="validate this function of the adapter module in place of its inside()")
    a = ap.parse_args()
    mod = importlib.import_module(a.module)    # installs the adapter into ckb.core
    if a.inside:
        m.inside = getattr(mod, a.inside)
    made = {}
    build = m.build

    def recording_build(kind, fr, p, *d):
        shape = build(kind, fr, p, *d)
        made[id(shape)] = (kind, fr, list(p), d)
        return shape
    m.build = recording_build
    worst, small, count = collections.defaultdict(float), collections.Counter(), collections.Counter()
    rng = random.Random(54321)
    checked = undecided = n_solids = 0
    bad, boxes, refused = [], {}, collections.Counter()
    per_kind = collections.Counter()
    for label, S in solids(a.prims):
        n_solids += 1
        kind = S.margin.__qualname__.split(".")[0]
        boxes[label] = m.bbox(S.shape)
        ex = exact_box(*made[id(S.shape)])
        worst[kind] = max(worst[kind], max(abs(x - y) for x, y in zip(boxes[label], ex)))
        small[kind] += any(boxes[label][i] > ex[i] + 1e-6 for i in range(3)) or any(boxes[label][i] < ex[i] - 1e-6 for i in range(3, 6))
        count[kind] += 1
        for g in m.sample_points(rng, S, S):
            mg = S.margin(g)
            if abs(mg) < m.BAND:
                continue
            try:
                got = m.inside(S.shape, g)
            except Exception as e:          # the kernel refused to classify against this solid
                m.reraise_unless_kernel(e)
                refused[kind, str(e)[:80]] += 1
                break
            if got is None:
                undecided += 1
                continue
            checked += 1
            per_kind[kind] += 1
            if got != (mg > 0):
                bad.append((label, g, mg, got))
    print(f"{n_solids} solids, {checked} points compared, {undecided} undecided, {len(bad)} disagreements")
    print("  points compared by kind:", dict(per_kind))
    for kind in sorted(count):
        print(f"  placement, {kind}: bounding box within {worst[kind]:.2g} mm of the exact box; smaller than it in {small[kind]} of {count[kind]}")
    for (kind, why), n in refused.items():
        print(f"  {n} {kind} solids the kernel would not classify against: {why}")
    for x in bad[:20]:
        print("  disagree:", x)
    if a.bbox:
        json.dump(boxes, open(a.bbox, "w"))
    sys.exit(1 if bad or undecided or refused else 0)


if __name__ == "__main__":
    main()
