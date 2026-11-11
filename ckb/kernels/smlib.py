# SPDX-License-Identifier: MIT OR Apache-2.0
# /// script
# requires-python = "==3.12.*"
# dependencies = ["usd-brep==1.0.1", "numpy"]
# ///
"""Adapter for SMLib, through NVIDIA's usd-brep Python package.

    python -m ckb.kernels.smlib --out results.jsonl [--jobs 3]

Two differences from the OCCT run, both forced by what the Python API
offers:

  * SMLib exposes no point-in-solid query. A point is classified by the
    winding number of SMLib's own tessellation of the result (chord
    height 3e-3 mm, inside the 1e-2 mm band of unused points), which is independent of how the solid was built.
  * SMLib exposes no general validity checker, so "invalid" here means
    the result is not a closed manifold solid, or could not be
    tessellated. OCCT's checker is stricter.

SMLib's booleans take no tolerance argument, so only the cases with
fuzzy value 0 are run (the same list as any kernel run with --fuzzy0).

The Python package's memory use grows by roughly 100 MB per case, so
workers restart every RECYCLE cases.

"""
import math

import numpy as np

from ckb import core as m
from ckb import driver


RECYCLE = 15


def _u():
    import usd_brep
    return usd_brep


def build(kind, fr, p, *dims):
    u = _u()
    p = tuple(float(x) for x in p)
    mk = {"box": u.create_box, "cyl": u.create_cylinder, "sph": u.create_sphere,
          "cone": u.create_cone, "torus": u.create_torus}[kind]
    b = mk(p, *[float(d) for d in dims])
    # Primitives are made in the case's local frame, then placed: global = o + R * local.
    x = tuple(fr.R[i][0] for i in range(3))
    y = tuple(fr.R[i][1] for i in range(3))
    u.transform(b, u.Axis2Placement(tuple(fr.o), x, y))
    return b


def volume(shape):
    return _u().compute_volume(shape, 1e-6) if shape.face_count() else 0.0


def valid(shape):
    return shape.face_count() == 0 or bool(shape.is_manifold_solid())


def bbox(shape):
    (x0, y0, z0), (x1, y1, z1) = shape.bounding_box()
    return x0, y0, z0, x1, y1, z1


def has_solid(shape):
    return shape.face_count() > 0


_mesh_cache = {}


def _mesh(shape):
    key = id(shape)
    if key not in _mesh_cache:
        _mesh_cache.clear()
        t = _u().tessellate(shape, chord_height_tolerance=3e-3)
        a = t.to_numpy_arrays()
        pts = np.asarray(a["points"], dtype=np.float64)
        f = np.asarray(a["faces"]).reshape(-1, 4)
        if not (f[:, 0] == 3).all():
            raise RuntimeError("tessellation returned non-triangles")
        _mesh_cache[key] = (shape, pts[f[:, 1]], pts[f[:, 2]], pts[f[:, 3]])
    return _mesh_cache[key][1:]


def inside(shape, g):
    """Generalised winding number of the tessellated boundary about g.
    Near 1 inside, near 0 outside. None when it is neither."""
    A, B, C = _mesh(shape)
    q = np.asarray(g, dtype=np.float64)
    total = 0.0
    for i in range(0, len(A), 200_000):      # in blocks, to bound memory on fine meshes
        a, b, c = A[i:i + 200_000] - q, B[i:i + 200_000] - q, C[i:i + 200_000] - q
        la, lb, lc = (np.linalg.norm(v, axis=1) for v in (a, b, c))
        num = np.einsum("ij,ij->i", a, np.cross(b, c))
        den = la * lb * lc + np.einsum("ij,ij->i", a, b) * lc + np.einsum("ij,ij->i", b, c) * la + np.einsum("ij,ij->i", c, a) * lb
        total += float(np.arctan2(num, den).sum())
    w = abs(total / (2 * math.pi))
    return True if abs(w - 1) < 0.1 else False if w < 0.1 else None


def boolean(op, A, B, fuzzy):
    import time
    u = _u()
    f = {"fuse": u.boolean_union, "cut": u.boolean_difference, "common": u.boolean_intersection}[op]
    t = time.perf_counter()
    out = {"status": "ok"}
    try:
        s = f(u.brep_copy(A), u.brep_copy(B))   # the operation consumes its inputs
        out["shape"] = s
        out["vol"] = volume(s)
        if not valid(s):
            out["status"] = "invalid"
        elif has_solid(s):
            _mesh(s)                              # a result that cannot be tessellated is not usable
    except Exception as e:
        m.reraise_unless_kernel(e)
        out["status"] = "error"
        out["exc"] = type(e).__name__
        out.setdefault("vol", 0.0)
    out["ms"] = round((time.perf_counter() - t) * 1e3, 2)
    return out


def reraise_unless_kernel(e):
    """The binding reports kernel failures as RuntimeError."""
    if not isinstance(e, RuntimeError):
        raise e


def sharp_edges(shape):
    """Edges where two different faces meet at more than 5 degrees."""
    out = []
    for e in shape.edges():
        fs = e.faces()
        if len(fs) != 2:
            continue
        t0, t1 = e.parameter_range()
        angles = []
        for t in (0.1, 0.5, 0.9):
            pt = e.point_at(t0 + t * (t1 - t0))
            ns = []
            for f in fs:
                uv = _u().surface_closest_point(f.surface(), pt)[1][0]
                uv = (uv.x, uv.y) if hasattr(uv, "x") else (uv[0], uv[1])
                ns.append(f.outward_normal_at_uv(uv[0], uv[1]))
            dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(*ns))))
            angles.append(math.degrees(math.acos(dot)))
        if min(angles) < 5.0:
            continue
        length = e.length()
        if length > 1e-6:
            out.append((e, length, min(angles), max(angles)))
    return out


def fillet(shape, edges, radius):
    u = _u()
    try:
        u.fillet_edges(shape, [x[0] for x in edges], radius=float(radius))   # in place
        if not valid(shape):
            return "invalid"
        _mesh(shape)
        return "ok"
    except Exception as e:
        m.reraise_unless_kernel(e)
        return "error"


m.install(globals())

if __name__ == "__main__":
    driver.main(m, "ckb.kernels.smlib", recycle=RECYCLE, fuzzy0=True)
