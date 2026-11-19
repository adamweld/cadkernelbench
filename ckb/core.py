# SPDX-License-Identifier: MIT OR Apache-2.0
"""Cases, closed-form ground truth and scoring. Kernel-neutral.

A kernel adapter (see ckb/kernels/) assigns the ten kernel functions
listed under "Kernel interface" below and calls ckb.driver.main().

Every input solid is an analytic primitive, so whether a point lies
inside it is known in closed form, and so is the right answer for any
boolean combination of them. Results are judged by classifying sample
points against the result and comparing with that closed form. Volume
identities are recorded as residuals but never used to judge a result,
because a kernel's own volume integration can be less accurate than its
booleans.

Every case is generated from a seed, so a run is reproducible. Which
draw of the cases a run uses is its round: see ckb/rounds.py.
"""

import argparse, json, math, os, random, subprocess, sys, time

from . import rounds


# ------------------------------------------------------ kernel interface
# An adapter replaces these. See docs/ADDING-A-KERNEL.md.

def _missing(*a, **k):
    raise NotImplementedError("no kernel adapter installed")


build = _missing                  # build(kind, frame, position, *dims) -> shape
boolean = _missing                # boolean(op, a, b, fuzzy) -> {"status", "shape", "vol", "ms"}
volume = _missing                 # volume(shape) -> float
bbox = _missing                   # bbox(shape) -> (x0, y0, z0, x1, y1, z1)
valid = _missing                  # valid(shape) -> bool, the kernel's own check
has_solid = _missing              # has_solid(shape) -> bool
inside = _missing                 # inside(shape, point) -> True, False, or None if undecided
sharp_edges = _missing            # sharp_edges(shape) -> [(edge, length, min_angle, max_angle)]
fillet = _missing                 # fillet(shape, edges, radius) -> "ok" | "invalid" | "error"
reraise_unless_kernel = _missing  # re-raise an exception unless the kernel raised it


def install(namespace):
    """Install an adapter's functions from its module namespace."""
    for name in ("build", "boolean", "volume", "bbox", "valid", "has_solid", "inside",
                 "sharp_edges", "fillet", "reraise_unless_kernel"):
        globals()[name] = namespace[name]


# ----------------------------------------------------------------- cases

EPS = [0.0] + [s * 10.0 ** e for e in range(-9, -2) for s in (1, -1)]
NEAR_FAMILIES = ["stacked", "flush_side", "cyl_tangent_inside", "coaxial_cyl",
                 "sphere_tangent", "cyl_on_edge", "identical"]
NEAR_REPS = 20
GENERIC_PAIRS = 600
FILLET_CASES = 3000
FUZZY = [0.0, 1e-6]
FILLET_FRACTIONS = [0.02, 0.05, 0.15]
FILLET_MODES = ["one_edge", "all_edges"]
CHAINS = 300
CHAIN_STEPS = 12


def case_list():
    cases = []
    for fam in NEAR_FAMILIES:
        for eps in EPS:
            for rep in range(NEAR_REPS):
                for fz in FUZZY:
                    cases.append({"kind": "near", "family": fam, "eps": eps,
                                  "rep": rep, "fuzzy": fz})
    for i in range(GENERIC_PAIRS):
        cases.append({"kind": "generic", "rep": i, "fuzzy": 0.0})
    for i in range(FILLET_CASES):
        cases.append({"kind": "fillet", "rep": i,
                      "frac": FILLET_FRACTIONS[i % len(FILLET_FRACTIONS)],
                      "mode": FILLET_MODES[(i // len(FILLET_FRACTIONS)) % 2]})
    for i in range(CHAINS):
        for fz in FUZZY:
            cases.append({"kind": "chain", "rep": i, "fuzzy": fz})
    for n, c in enumerate(cases):
        c["id"] = n
    return cases


# ------------------------------------------------------------ geometry

def _rot(rng):
    """Uniform random rotation matrix (from a random unit quaternion)."""
    while True:
        q = [rng.gauss(0, 1) for _ in range(4)]
        n = math.sqrt(sum(x * x for x in q))
        if n > 1e-6:
            break
    w, x, y, z = (v / n for v in q)
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


class Frame:
    """A rigid frame. Local coordinates are mapped to global ones in plain
    floating point, so that exact local coincidences become coincidences up
    to rounding, as they are in real models."""

    def __init__(self, rng, identity=False):
        if identity:
            self.R = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
            self.o = [0.0, 0.0, 0.0]
        else:
            self.R = _rot(rng)
            self.o = [rng.uniform(-200, 200) for _ in range(3)]

    def pt(self, p):
        return [self.o[i] + sum(self.R[i][j] * p[j] for j in range(3)) for i in range(3)]

    def vec(self, v):
        return [sum(self.R[i][j] * v[j] for j in range(3)) for i in range(3)]

    def local(self, g):
        d = [g[i] - self.o[i] for i in range(3)]
        return [sum(self.R[i][j] * d[i] for i in range(3)) for j in range(3)]


class Solid:
    """An OCCT shape together with a closed-form inside test. margin(g) is
    positive inside, negative outside, and its size is about the distance
    to the boundary."""

    def __init__(self, shape, margin):
        self.shape, self.margin = shape, margin


def box(fr, p, d):
    def margin(g):
        q = fr.local(g)
        return min(min(q[i] - p[i], p[i] + d[i] - q[i]) for i in range(3))
    return Solid(build("box", fr, p, *d), margin)


def cyl(fr, p, r, h):
    def margin(g):
        q = fr.local(g)
        rho = math.hypot(q[0] - p[0], q[1] - p[1])
        return min(r - rho, q[2] - p[2], p[2] + h - q[2])
    return Solid(build("cyl", fr, p, r, h), margin)


def sph(fr, p, r):
    def margin(g):
        q = fr.local(g)
        return r - math.dist(q, p)
    return Solid(build("sph", fr, p, r), margin)


def cone(fr, p, r1, r2, h):
    k = math.cos(math.atan2(abs(r1 - r2), h))
    def margin(g):
        q = fr.local(g)
        z = q[2] - p[2]
        rho = math.hypot(q[0] - p[0], q[1] - p[1])
        return min((r1 + (r2 - r1) * z / h - rho) * k, z, h - z)
    return Solid(build("cone", fr, p, r1, r2, h), margin)


def torus(fr, p, r1, r2):
    def margin(g):
        q = fr.local(g)
        rho = math.hypot(q[0] - p[0], q[1] - p[1])
        return r2 - math.hypot(rho - r1, q[2] - p[2])
    return Solid(build("torus", fr, p, r1, r2), margin)


def near_pair(family, eps, rng):
    """Two solids in a configuration that is degenerate at eps = 0."""
    fr = Frame(rng)
    ax, ay, az = (rng.uniform(20, 60) for _ in range(3))
    A = box(fr, (0, 0, 0), (ax, ay, az))
    if family == "stacked":            # B rests on A's top face
        B = box(fr, (ax * 0.3, ay * 0.2, az + eps), (ax, ay, rng.uniform(10, 30)))
    elif family == "flush_side":       # B overlaps A, one side face coplanar
        B = box(fr, (eps, ay * 0.4, az * 0.5), (ax * 0.6, ay, az))
    elif family == "cyl_tangent_inside":  # hole tangent to a side face
        r = min(ax, ay) * rng.uniform(0.1, 0.3)
        B = cyl(fr, (r + eps, ay * 0.5, -5.0), r, az + 10.0)
    elif family == "coaxial_cyl":      # equal-radius coaxial cylinders
        r = rng.uniform(5, 20)
        A = cyl(fr, (0, 0, 0), r, az)
        B = cyl(fr, (0, 0, az * 0.5), r + eps, az)
    elif family == "sphere_tangent":   # sphere touching the top face
        r = rng.uniform(5, 20)
        B = sph(fr, (ax * 0.5, ay * 0.5, az + r + eps), r)
    elif family == "cyl_on_edge":      # cylinder axis along a box edge
        r = min(ax, ay) * rng.uniform(0.1, 0.4)
        B = cyl(fr, (eps, 0.0, 0.0), r, az)
    elif family == "identical":        # the same box built twice
        B = box(fr, (0, 0, 0), (ax + eps, ay, az))
    else:
        raise ValueError(family)
    return A, B


def random_prim(rng, centre_spread):
    fr = Frame(rng)
    fr.o = [rng.uniform(-centre_spread, centre_spread) for _ in range(3)]
    k = rng.choice(["box", "cyl", "sph", "cone", "torus"])
    s = rng.uniform(10, 40)
    if k == "box":
        d = [rng.uniform(0.5, 1.5) * s for _ in range(3)]
        return box(fr, [-x / 2 for x in d], d)
    if k == "cyl":
        h = rng.uniform(0.5, 2) * s
        return cyl(fr, (0, 0, -h / 2), 0.5 * s, h)
    if k == "sph":
        return sph(fr, (0, 0, 0), 0.6 * s)
    if k == "cone":
        h = rng.uniform(0.5, 2) * s
        return cone(fr, (0, 0, -h / 2), 0.6 * s, rng.uniform(0, 0.4) * s, h)
    return torus(fr, (0, 0, 0), 0.6 * s, rng.uniform(0.1, 0.25) * s)


# ---------------------------------------------------------- measurement


BAND = 1e-2          # mm; sample points nearer than this to an input boundary are skipped
SAMPLES = 150


def sample_points(rng, A, B):
    """Points in the bounding boxes of A and B, half each."""
    pts = []
    for S in (A, B):
        x0, y0, z0, x1, y1, z1 = bbox(S.shape)
        for _ in range(SAMPLES // 2):
            pts.append((rng.uniform(x0, x1), rng.uniform(y0, y1), rng.uniform(z0, z1)))
    return pts


def run_boolean_case(c):
    rng = rounds.rng("boolean", c["id"], 1_000_003 * c["id"] + 17)
    if c["kind"] == "near":
        A, B = near_pair(c["family"], c["eps"], rng)
    else:
        A, B = random_prim(rng, 0), random_prim(rng, 25)
    va, vb = volume(A.shape), volume(B.shape)
    r = {"va": va, "vb": vb}
    res = {op: boolean(op, A.shape, B.shape, c.get("fuzzy", 0.0)) for op in ("fuse", "cut", "common")}
    pts = [(g, A.margin(g), B.margin(g)) for g in sample_points(rng, A, B)]
    pts = [(g, ma > 0, mb > 0) for g, ma, mb in pts if abs(ma) > BAND and abs(mb) > BAND]
    r["n_pts"] = len(pts)
    expect = {"fuse": lambda a, b: a or b, "cut": lambda a, b: a and not b, "common": lambda a, b: a and b}
    for op, x in res.items():
        shape = x.pop("shape", None)
        if shape is not None:
            miss = undecided = 0
            solid = has_solid(shape)
            for g, a, b in pts:
                want = expect[op](a, b)
                try:
                    got = inside(shape, g) if solid else False
                except Exception as e:
                    reraise_unless_kernel(e)
                    got = None
                if got is None:          # on the boundary, or the kernel could not decide
                    undecided += 1
                elif got != want:
                    miss += 1
            x["miss"] = miss
            if undecided:
                x["undecided"] = undecided
            if miss and x["status"] == "ok":
                x["status"] = "wrong"
        r[op] = x
    f, k, m = r["fuse"], r["cut"], r["common"]
    if all("vol" in x for x in (f, k, m)):
        r["res_union"] = f["vol"] + m["vol"] - va - vb
        r["res_cut"] = k["vol"] - va + m["vol"]
    r["overlap"] = any(a and b for _, a, b in pts)
    return r


def run_chain_case(c):
    """A feature sequence on one body, as a CAD model is built: holes,
    pockets, bosses and ribs applied one after another to a block, with
    about half of the tools placed flush with or tangent to existing
    faces. The true solid after every step is a known combination of
    analytic primitives, so the point test still applies."""
    rng = rounds.rng("chain", c["id"], 3_000_003 * c["id"] + 41)
    fr = Frame(rng)
    L = [rng.uniform(60, 120) for _ in range(3)]
    body = box(fr, (0, 0, 0), L)
    shape = body.shape
    prims = [body]              # every primitive used so far, for the boundary band
    ops = []                    # (is_fuse, primitive) in order

    def truth(g):
        v = body.margin(g) > 0
        for is_fuse, t in ops:
            inside_t = t.margin(g) > 0
            v = (v or inside_t) if is_fuse else (v and not inside_t)
        return v

    def tool():
        snap = rng.random() < 0.5
        k = rng.choice(["hole", "boss", "pocket", "rib", "ball"])
        x, y = rng.uniform(0.15, 0.85) * L[0], rng.uniform(0.15, 0.85) * L[1]
        if k == "hole":          # through hole along z; snapped: axis exactly in the x = 0 face (a half-round notch)
            r = rng.uniform(3, 10)       # A hole tangent to the face was used at first. Its exact result has a
            return False, cyl(fr, (0.0 if snap else x, y, -5.0), r, L[2] + 10.0), k, snap  # zero-thickness wall, which is not a solid.
        if k == "boss":          # cylinder on the top face; snapped: base exactly on the face
            r = rng.uniform(4, 12)
            return True, cyl(fr, (x, y, L[2] if snap else L[2] - 2.0), r, rng.uniform(5, 20)), k, snap
        if k == "pocket":        # box cut from the top; snapped: one wall flush with the y = 0 face
            w = (rng.uniform(8, 25), rng.uniform(8, 25), rng.uniform(5, 20))
            return False, box(fr, (x, 0.0 if snap else y, L[2] - w[2]), (w[0], w[1], w[2] + 5.0)), k, snap
        if k == "rib":           # box added on the x = L face; snapped: flush with top and bottom
            w = (rng.uniform(5, 20), rng.uniform(5, 15))
            z0, hz = (0.0, L[2]) if snap else (rng.uniform(0.1, 0.4) * L[2], 0.4 * L[2])
            return True, box(fr, (L[0] - 1.0 if not snap else L[0], y, z0), (w[0], w[1], hz)), k, snap
        r = rng.uniform(5, 15)   # spherical cut; snapped: centre exactly on an edge of the block
        return False, sph(fr, (0.0, y, L[2]) if snap else (x, y, L[2]), r), k, snap

    r = {"steps_ok": 0, "status": "ok", "ms": []}
    for step in range(1, CHAIN_STEPS + 1):
        is_fuse, t, kind, snap = tool()
        x = boolean("fuse" if is_fuse else "cut", shape, t.shape, c["fuzzy"])
        r["ms"].append(x["ms"])
        new = x.pop("shape", None)
        if x["status"] != "ok":
            r.update(status=x["status"], fail_step=step, fail_tool=kind, fail_snap=snap)
            break
        if not has_solid(new):   # the block can never be removed entirely by these tools
            r.update(status="wrong", fail_step=step, fail_tool=kind, fail_snap=snap, empty=True)
            break
        ops.append((is_fuse, t))
        prims.append(t)
        shape = new
        if step % 4 == 0:        # point test against the known solid
            x0, y0, z0, x1, y1, z1 = bbox(shape)
            miss = n = 0
            for _ in range(120):
                g = (rng.uniform(x0, x1), rng.uniform(y0, y1), rng.uniform(z0, z1))
                if min(abs(q.margin(g)) for q in prims) < BAND:
                    continue
                n += 1
                got = inside(shape, g)
                if got is None:
                    r["undecided"] = r.get("undecided", 0) + 1
                elif got != truth(g):
                    miss += 1
            if miss:
                r.update(status="wrong", fail_step=step, fail_tool=kind, fail_snap=snap, miss=miss, n_pts=n)
                break
        r["steps_ok"] = step
    r["ms"] = round(sum(r["ms"]), 1)
    if r["status"] == "ok":      # finish as a designer would: round one edge
        try:
            edges = sharp_edges(shape)
        except Exception as e:   # the kernel could not list the edges of its own result
            reraise_unless_kernel(e)
            edges, r["fillet"] = [], "error"
        if edges:
            e = rng.choice(edges)
            r["fillet"] = fillet(shape, [e], 0.05 * min(x[1] for x in edges))
    return r


def run_fillet_case(c):
    """Fillet sharp edges of a solid with a small radius. The radius is a
    small fraction of the shortest sharp edge, so a fillet should nearly
    always exist geometrically; the reported rate is still an upper bound
    on kernel failure, because existence is not proved case by case."""
    rng = rounds.rng("fillet", c["id"], 2_000_003 * c["id"] + 29)
    A = random_prim(rng, 0).shape
    base, how = A, "primitive"
    if rng.random() < 0.75:
        B = random_prim(rng, 20).shape
        op = rng.choice(["fuse", "cut", "common"])
        va = volume(A)
        x = boolean(op, A, B, 0.0)
        if x["status"] == "ok" and x["vol"] > 1.0 and abs(x["vol"] - va) > 1e-6 * va:
            base, how = x["shape"], op
    try:
        edges = sharp_edges(base)
    except Exception as e:       # the kernel could not list the edges of its own solid
        reraise_unless_kernel(e)
        return {"base": how, "mode": c["mode"], "status": "error", "exc": "sharp_edges: " + str(e)[:100]}
    r = {"base": how, "n_sharp": len(edges), "mode": c["mode"]}
    if not edges:
        r["status"] = "skipped"
        return r
    radius = c["frac"] * min(x[1] for x in edges)
    chosen = [rng.choice(edges)] if c["mode"] == "one_edge" else edges
    r["radius"] = radius
    r["ang_min"] = round(min(x[2] for x in chosen), 2)
    r["ang_max"] = round(max(x[3] for x in chosen), 2)
    t = time.perf_counter()
    r["status"] = fillet(base, chosen, radius)
    r["ms"] = round((time.perf_counter() - t) * 1e3, 2)
    return r


# ------------------------------------------------- crash-proof execution


# ---------------------------------------------------------------- report

def summarise(path):
    cases = {c["id"]: c for c in case_list()}
    rows, lost = [], {}
    for line in open(path):
        d = json.loads(line)
        if "lost" in d:
            lost[d["lost"]] = d["why"]
        else:
            rows.append(d)

    def pct(a, b):
        return f"{100 * a / b:.2f}%" if b else "n/a"

    def bool_stats(sel, label):
        rs = [r for r in rows if sel(r["case"])]
        ls = [i for i in lost if sel(cases[i])]
        ops = 3 * len(rs)
        err = sum(r["res"][o]["status"] == "error" for r in rs for o in ("fuse", "cut", "common"))
        inv = sum(r["res"][o]["status"] == "invalid" for r in rs for o in ("fuse", "cut", "common"))
        wrong = sum(r["res"][o]["status"] == "wrong" for r in rs for o in ("fuse", "cut", "common"))
        anybad = sum(any(r["res"][o]["status"] != "ok" for o in ("fuse", "cut", "common")) for r in rs)
        ms = sorted(r["res"][o]["ms"] for r in rs for o in ("fuse", "cut", "common"))
        med = ms[len(ms) // 2] if ms else 0
        p99 = ms[int(len(ms) * 0.99)] if ms else 0
        print(f"| {label} | {len(rs) + len(ls)} | {pct(err, ops)} | {pct(inv, ops)} | {pct(wrong, ops)} | {len(ls)} | {pct(anybad + len(ls), len(rs) + len(ls))} | {med:.1f} / {p99:.1f} |")

    hdr = "| Set | Pairs | Ops reporting error | Ops returning an invalid solid | Ops returning the wrong solid | Crashed or hung | Pairs with any failure | Time per op, median / p99 (ms) |\n|---|---|---|---|---|---|---|---|"
    print("### Booleans by set\n\n" + hdr)
    bool_stats(lambda c: c["kind"] == "generic", "Generic position")
    gen = [r for r in rows if r["case"]["kind"] == "generic"]
    ov = sum(bool(r["res"].get("overlap")) for r in gen)
    for fz in FUZZY:
        bool_stats(lambda c, fz=fz: c["kind"] == "near" and c["fuzzy"] == fz, f"Near-degenerate, fuzzy {fz:g}")
    for fz in FUZZY:
        print(f"\n### Near-degenerate by family, fuzzy {fz:g}\n\n" + hdr)
        for fam in NEAR_FAMILIES:
            bool_stats(lambda c, fam=fam, fz=fz: c["kind"] == "near" and c["family"] == fam and c["fuzzy"] == fz, fam)
        print(f"\n### Near-degenerate by offset magnitude, fuzzy {fz:g}\n\n" + hdr)
        for e in sorted({abs(x) for x in EPS}):
            bool_stats(lambda c, e=e, fz=fz: c["kind"] == "near" and abs(c["eps"]) == e and c["fuzzy"] == fz, f"{e:g}")

    print("\n### Fillets on sharp edges, small radius\n")
    print("| Edges filleted | Radius as fraction of shortest sharp edge | Cases | Error | Invalid result | Crashed or hung | Any failure | Median time (ms) |\n|---|---|---|---|---|---|---|---|")
    for mode in FILLET_MODES:
        for fr in FILLET_FRACTIONS:
            sel = lambda c: c["kind"] == "fillet" and c["frac"] == fr and c["mode"] == mode
            rs = [r for r in rows if sel(r["case"]) and r["res"]["status"] != "skipped"]
            ls = [i for i in lost if sel(cases[i])]
            e = sum(r["res"]["status"] == "error" for r in rs)
            v = sum(r["res"]["status"] == "invalid" for r in rs)
            ms = sorted(r["res"].get("ms", 0) for r in rs)
            n = len(rs) + len(ls)
            print(f"| {mode} | {fr} | {n} | {pct(e, n)} | {pct(v, n)} | {len(ls)} | {pct(e + v + len(ls), n)} | {ms[len(ms) // 2] if ms else 0:.1f} |")
    print("\n| Edges filleted | Base solid | Cases | Any failure |\n|---|---|---|---|")
    for mode in FILLET_MODES:
        for how in ("primitive", "fuse", "cut", "common"):
            rs = [r for r in rows if r["case"]["kind"] == "fillet" and r["case"]["mode"] == mode and r["res"].get("base") == how and r["res"]["status"] != "skipped"]
            bad = sum(r["res"]["status"] != "ok" for r in rs)
            print(f"| {mode} | {how} | {len(rs)} | {pct(bad, len(rs))} |")
    sk = sum(r["res"]["status"] == "skipped" for r in rows if r["case"]["kind"] == "fillet")
    print(f"\nFillet cases skipped because the solid had no sharp edge: {sk}")
    print(f"\nGeneric pairs whose solids overlap: {ov} of {len(gen)}")
    print("\n| Edges filleted | Face angle along the edges | Cases | Any failure |\n|---|---|---|---|")
    for mode in FILLET_MODES:
        for label, sel in (("all between 45 and 135 degrees", lambda x: x["ang_min"] >= 45 and x["ang_max"] <= 135),
                           ("some outside 45 to 135 degrees", lambda x: not (x["ang_min"] >= 45 and x["ang_max"] <= 135))):
            rs = [r for r in rows if r["case"]["kind"] == "fillet" and r["case"]["mode"] == mode and "ang_min" in r["res"] and sel(r["res"])]
            bad = sum(r["res"]["status"] != "ok" for r in rs)
            print(f"| {mode} | {label} | {len(rs)} | {pct(bad, len(rs))} |")
    print("\n### Feature sequences (12 booleans on one body, then one fillet)\n")
    print("| Fuzzy | Sequences | Completed all 12 | Stopped: error | Stopped: invalid solid | Stopped: wrong solid | Crashed or hung | Final fillet failed | Median time for 12 steps (ms) |\n|---|---|---|---|---|---|---|---|---|")
    for fz in FUZZY:
        rs = [r for r in rows if r["case"]["kind"] == "chain" and r["case"]["fuzzy"] == fz]
        ls = [i for i in lost if cases[i]["kind"] == "chain" and cases[i]["fuzzy"] == fz]
        n = len(rs) + len(ls)
        st = lambda k: sum(r["res"]["status"] == k for r in rs)
        fil = [r for r in rs if "fillet" in r["res"]]
        fbad = sum(r["res"]["fillet"] != "ok" for r in fil)
        ms = sorted(r["res"]["ms"] for r in rs if r["res"]["status"] == "ok")
        print(f"| {fz:g} | {n} | {pct(st('ok'), n)} | {pct(st('error'), n)} | {pct(st('invalid'), n)} | {pct(st('wrong'), n)} | {len(ls)} | {pct(fbad, len(fil))} | {ms[len(ms) // 2] if ms else 0:.0f} |")
    print("\n| Tool at the failing step | Placed flush or tangent | Failures |\n|---|---|---|")
    import collections
    cnt = collections.Counter((r["res"].get("fail_tool"), r["res"].get("fail_snap")) for r in rows if r["case"]["kind"] == "chain" and r["res"]["status"] != "ok")
    for (k, sn), v in sorted(cnt.items(), key=lambda x: -x[1]):
        print(f"| {k} | {'yes' if sn else 'no'} | {v} |")
    print(f"\nTotal cases recorded: {len(rows)}; lost to crash or hang: {len(lost)}")


