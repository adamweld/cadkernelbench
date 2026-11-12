# SPDX-License-Identifier: MIT OR Apache-2.0
"""A feature model made of analytic primitives, and what is true of it
without asking a kernel.

A model is a base block and a list of steps, each a primitive that is cut
from or fused to the body. Every face of the true solid lies on one surface
of one primitive, so it has an identity no kernel is needed for:
(the step's uid, the name of that primitive's surface). The functions here
compute, in closed form or by sampling the closed forms, which identities
bound the solid and in how many separate pieces.

All geometry is held in the model's local coordinates. Only points handed
to or received from a system under test are in global coordinates.
"""
import math

import numpy as np
from scipy import ndimage

EPS = 1e-4          # step either side of a surface when testing whether it bounds the solid
ON_TOL = 1e-5       # a point this near a surface is on it
STEP_COARSE = 0.5   # grid spacing for the piece count, and the finer spacing it is checked at
STEP_FINE = 0.3
MIN_CELLS = 12      # a piece smaller than this many fine cells is a sliver: the case is ill-posed
MAX_SIDE = 1400     # most cells along one side of a grid


def rotation(rng):
    """A uniform random rotation matrix."""
    while True:
        q = [rng.gauss(0, 1) for _ in range(4)]
        n = math.sqrt(sum(x * x for x in q))
        if n > 1e-6:
            break
    w, x, y, z = (v / n for v in q)
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


class Model:
    """frame: {"R": 3x3, "o": [3]}, global = o + R·local.
    steps: [{"uid", "op": "base"|"cut"|"fuse", "kind": "box"|"cyl"|"sph", ...}]
      box: "p" (low corner), "d" (sizes)
      cyl: "p" (centre of the low end), "r", "h", "ax" (0, 1 or 2: the local axis it runs along)
      sph: "p" (centre), "r"
    """

    def __init__(self, frame, steps):
        self.frame, self.steps = frame, steps
        self.R = np.array(frame["R"], float)
        self.o = np.array(frame["o"], float)

    def to_json(self):
        return {"frame": self.frame, "steps": self.steps}

    def copy(self):
        return Model(self.frame, [dict(s) for s in self.steps])

    def step(self, uid):
        return next(s for s in self.steps if s["uid"] == uid)

    def to_global(self, q):
        return self.o + np.asarray(q, float) @ self.R.T

    def to_local(self, g):
        return (np.asarray(g, float) - self.o) @ self.R

    # ---- what is inside

    def inside(self, Q):
        """For local points Q (n, 3): which are inside the true solid."""
        v = None
        for s in self.steps:
            if s["op"] == "base":
                v = margin(s, Q) > 0
                continue
            lo, hi = bounds(s)       # only the points in the primitive's box can be inside it
            idx = np.flatnonzero((Q[:, 0] > lo[0]) & (Q[:, 0] < hi[0]))
            for i in (1, 2):
                idx = idx[(Q[idx, i] > lo[i]) & (Q[idx, i] < hi[i])]
            if not len(idx):
                continue
            m = margin(s, Q[idx]) > 0
            if s["op"] == "fuse":
                v[idx] |= m
            else:
                v[idx] &= ~m
        return v

    # ---- identities

    def surfaces(self):
        return [(s["uid"], name) for s in self.steps for name in SURFACES[s["kind"]]]

    def attribute(self, q):
        """The identities of the surfaces a local point lies on, and whether
        it is on the boundary of the solid there."""
        q = np.asarray(q, float)
        hits = []
        for s in self.steps:
            for name in SURFACES[s["kind"]]:
                if surface_distance(s, name, q) < ON_TOL:
                    hits.append((s["uid"], name))
        return hits

    def coincident(self, identity):
        """Whether another primitive has a surface in the same plane, on the
        same cylinder or on the same sphere as this one. A face there would
        belong to both, so it has no single identity."""
        if all(s["uid"] != identity[0] for s in self.steps):
            return False
        mine = _carrier(self.step(identity[0]), identity[1])
        for s in self.steps:
            for name in SURFACES[s["kind"]]:
                if (s["uid"], name) == tuple(identity):
                    continue
                c = _carrier(s, name)
                if c[0] == mine[0] and np.allclose(c[1], mine[1], rtol=0, atol=1e-6):
                    return True
        return False

    def pieces(self, identity, step=STEP_COARSE):
        """The pieces of one primitive surface that bound the solid.
        Returns a Pieces, whose count is the number of separate faces the
        true solid has on that surface."""
        uid, name = identity
        s = next((s for s in self.steps if s["uid"] == uid), None)
        if s is None:
            return Pieces(None, None, 0, None)
        grid = Grid(s, name, step)
        P, N = grid.points, grid.normals
        on = self.inside(P + EPS * N) != self.inside(P - EPS * N)
        on = on.reshape(grid.shape) & grid.mask
        labels, n = ndimage.label(on)
        if grid.periodic and n > 1:          # join labels across the seam of a closed surface
            parent = list(range(n + 1))

            def find(a):
                while parent[a] != a:
                    parent[a] = parent[parent[a]]
                    a = parent[a]
                return a
            for a, b in zip(labels[0], labels[-1]):
                if a and b:
                    parent[find(a)] = find(b)
            roots = sorted({find(a) for a in range(1, n + 1)})
            remap = np.zeros(n + 1, int)
            for a in range(1, n + 1):
                remap[a] = roots.index(find(a)) + 1
            labels, n = remap[labels], len(roots)
        return Pieces(grid, labels, n, s)


class Pieces:
    def __init__(self, grid, labels, count, step):
        self.grid, self.labels, self.count, self.step = grid, labels, count, step

    def sizes(self):
        return [int((self.labels == k).sum()) for k in range(1, self.count + 1)]

    def piece_at(self, q):
        """The piece (1..count) a local point on the surface lies in, 0 if in
        none. Looks one cell around, since a point may fall on a cell the
        sampling left just outside."""
        if not self.count:
            return 0
        i, j = self.grid.cell(q)
        nu, nv = self.grid.shape
        best = 0
        for di in (0, -1, 1):
            for dj in (0, -1, 1):
                a, b = i + di, j + dj
                if self.grid.periodic:
                    a %= nu
                if 0 <= a < nu and 0 <= b < nv and self.labels[a, b]:
                    if di == 0 and dj == 0:
                        return int(self.labels[a, b])
                    best = best or int(self.labels[a, b])
        return best

    def interior_point(self, piece, rng):
        """A local point well inside a piece: a cell far from the piece's edge."""
        member = self.labels == piece
        if self.grid.periodic:
            # Wrapped round the seam, and closed off at the two ends, which are real edges.
            padded = np.pad(np.concatenate([member[-3:], member, member[:3]]), ((0, 0), (1, 1)))
            depth = ndimage.distance_transform_cdt(padded)[3:-3, 1:-1]
        else:
            depth = ndimage.distance_transform_cdt(np.pad(member, 1))[1:-1, 1:-1]
        deep = np.argwhere(depth >= max(1, int(depth.max() * 0.5)))
        i, j = deep[rng.randrange(len(deep))]
        return self.grid.points[i * self.grid.shape[1] + j], int(depth.max())


SURFACES = {"box": ["x0", "x1", "y0", "y1", "z0", "z1"], "cyl": ["side", "lo", "hi"], "sph": ["s"]}


def _carrier(s, name):
    """The unbounded surface a primitive's surface lies on, as a kind and numbers."""
    p = s["p"]
    if s["kind"] == "box":
        i = "xyz".index(name[0])
        return ("plane", i), [p[i] + (s["d"][i] if name[1] == "1" else 0.0)]
    if s["kind"] == "sph":
        return ("sphere",), [*p, s["r"]]
    a = s["ax"]
    if name == "side":
        return ("cylinder", a), [*[p[i] for i in range(3) if i != a], s["r"]]
    return ("plane", a), [p[a] + (s["h"] if name == "hi" else 0.0)]


def margin(s, Q):
    """Positive inside the primitive, negative outside; about the distance to its boundary."""
    p = np.array(s["p"], float)
    if s["kind"] == "box":
        d = np.array(s["d"], float)
        return np.minimum(Q - p, p + d - Q).min(axis=1)
    if s["kind"] == "cyl":
        a = s["ax"]
        j, k = [i for i in range(3) if i != a]
        rho = np.hypot(Q[:, j] - p[j], Q[:, k] - p[k])
        return np.minimum(np.minimum(s["r"] - rho, Q[:, a] - p[a]), p[a] + s["h"] - Q[:, a])
    return s["r"] - np.linalg.norm(Q - p, axis=1)


def bounds(s):
    """The primitive's bounding box in local coordinates."""
    p = s["p"]
    if s["kind"] == "box":
        return p, [p[i] + s["d"][i] for i in range(3)]
    if s["kind"] == "sph":
        return [x - s["r"] for x in p], [x + s["r"] for x in p]
    lo, hi = [x - s["r"] for x in p], [x + s["r"] for x in p]
    lo[s["ax"]], hi[s["ax"]] = p[s["ax"]], p[s["ax"]] + s["h"]
    return lo, hi


def surface_distance(s, name, q):
    """Distance from a local point to one surface of a primitive (to the
    surface as bounded by the primitive, with a small allowance at its rim)."""
    p = s["p"]
    if s["kind"] == "box":
        i, hi = "xyz".index(name[0]), name[1] == "1"
        for j in range(3):
            if j != i and not (p[j] - ON_TOL <= q[j] <= p[j] + s["d"][j] + ON_TOL):
                return math.inf
        return abs(q[i] - (p[i] + s["d"][i] if hi else p[i]))
    if s["kind"] == "cyl":
        a = s["ax"]
        j, k = [i for i in range(3) if i != a]
        rho = math.hypot(q[j] - p[j], q[k] - p[k])
        if name == "side":
            if not (p[a] - ON_TOL <= q[a] <= p[a] + s["h"] + ON_TOL):
                return math.inf
            return abs(rho - s["r"])
        if rho > s["r"] + ON_TOL:
            return math.inf
        return abs(q[a] - (p[a] + s["h"] if name == "hi" else p[a]))
    return abs(math.dist(q, p) - s["r"])


class Grid:
    """Sample points on one surface of a primitive, on a grid whose cells
    are neighbours when the points are. `points` and `normals` are (n, 3),
    row-major over `shape`; `mask` is false for cells off the surface (the
    corners of the square around a disc); `periodic` when the first axis
    closes on itself."""

    def __init__(self, s, name, step):
        self.s, self.name = s, name
        p = np.array(s["p"], float)
        self.periodic = False

        def count(length):
            return int(min(MAX_SIDE, max(4, math.ceil(length / step))))
        if s["kind"] == "box":
            i, hi = "xyz".index(name[0]), name[1] == "1"
            j, k = [a for a in range(3) if a != i]
            nu, nv = count(s["d"][j]), count(s["d"][k])
            u = p[j] + (np.arange(nu) + 0.5) * s["d"][j] / nu
            v = p[k] + (np.arange(nv) + 0.5) * s["d"][k] / nv
            U, V = np.meshgrid(u, v, indexing="ij")
            P = np.zeros((nu, nv, 3))
            P[..., i] = p[i] + (s["d"][i] if hi else 0.0)
            P[..., j], P[..., k] = U, V
            N = np.zeros((nu, nv, 3))
            N[..., i] = 1.0 if hi else -1.0
            mask = np.ones((nu, nv), bool)
            self._cell = lambda q: (int((q[j] - p[j]) / s["d"][j] * nu), int((q[k] - p[k]) / s["d"][k] * nv))
        elif s["kind"] == "cyl":
            a, r, h = s["ax"], s["r"], s["h"]
            j, k = [b for b in range(3) if b != a]
            if name == "side":
                nu, nv = count(2 * math.pi * r), count(h)
                t = (np.arange(nu) + 0.5) * 2 * math.pi / nu
                z = p[a] + (np.arange(nv) + 0.5) * h / nv
                T, Z = np.meshgrid(t, z, indexing="ij")
                P = np.zeros((nu, nv, 3))
                N = np.zeros((nu, nv, 3))
                N[..., j], N[..., k] = np.cos(T), np.sin(T)
                P[..., j], P[..., k], P[..., a] = p[j] + r * np.cos(T), p[k] + r * np.sin(T), Z
                mask = np.ones((nu, nv), bool)
                self.periodic = True
                self._cell = lambda q: (int((math.atan2(q[k] - p[k], q[j] - p[j]) % (2 * math.pi)) / (2 * math.pi) * nu) % nu,
                                        int((q[a] - p[a]) / h * nv))
            else:
                nu = nv = count(2 * r)
                u = p[j] - r + (np.arange(nu) + 0.5) * 2 * r / nu
                v = p[k] - r + (np.arange(nv) + 0.5) * 2 * r / nv
                U, V = np.meshgrid(u, v, indexing="ij")
                P = np.zeros((nu, nv, 3))
                P[..., j], P[..., k] = U, V
                P[..., a] = p[a] + (h if name == "hi" else 0.0)
                N = np.zeros((nu, nv, 3))
                N[..., a] = 1.0 if name == "hi" else -1.0
                mask = np.hypot(U - p[j], V - p[k]) < r
                self._cell = lambda q: (int((q[j] - p[j] + r) / (2 * r) * nu), int((q[k] - p[k] + r) / (2 * r) * nv))
        else:
            r = s["r"]
            nu, nv = count(2 * math.pi * r), count(math.pi * r)
            t = (np.arange(nu) + 0.5) * 2 * math.pi / nu
            f = (np.arange(nv) + 0.5) * math.pi / nv
            T, F = np.meshgrid(t, f, indexing="ij")
            N = np.stack([np.sin(F) * np.cos(T), np.sin(F) * np.sin(T), np.cos(F)], axis=-1)
            P = p + r * N
            mask = np.ones((nu, nv), bool)
            self.periodic = True

            def cell(q):
                d = (np.asarray(q) - p) / r
                return (int((math.atan2(d[1], d[0]) % (2 * math.pi)) / (2 * math.pi) * nu) % nu,
                        int(math.acos(max(-1.0, min(1.0, d[2]))) / math.pi * nv))
            self._cell = cell
        self.shape = (nu, nv)
        self.points, self.normals, self.mask = P.reshape(-1, 3), N.reshape(-1, 3), mask

    def cell(self, q):
        i, j = self._cell(q)
        return min(max(i, 0), self.shape[0] - 1), min(max(j, 0), self.shape[1] - 1)


def well_posed(model, identity):
    """The piece count of an identity, or None where the count depends on
    the sampling: it differs between two grid spacings, or a piece is a
    sliver of a few cells. Such a reference is left out, not scored."""
    coarse = model.pieces(identity, STEP_COARSE)
    fine = model.pieces(identity, STEP_FINE)
    if coarse.count != fine.count:
        return None
    if fine.count and min(fine.sizes()) < MIN_CELLS:
        return None
    return fine
