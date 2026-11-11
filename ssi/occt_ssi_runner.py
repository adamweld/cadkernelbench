# SPDX-License-Identifier: MIT OR Apache-2.0
# /// script
# requires-python = ">=3.11"
# dependencies = ["cadquery-ocp==8.0.1.1.0"]
# ///
"""Runner that lets the public SSI corpus score OCCT's surface/surface
intersection (https://github.com/jyviko/ssi-corpus).

It follows that corpus's runner contract:

    occt_ssi_runner.py <case.json> <mode> <tol> <out.json>

and writes the curves OCCT returns, sampled at 4001 points each, with
the parameter-space curves on both surfaces where OCCT provides them.

Modes:
    gsi    GeomInt_IntSS on the two surfaces (what GeomAPI_IntSS wraps).
           The name matches the corpus's primary SMLib mode so the same
           scorer command line works.
    face   IntTools_FaceFace on a face made from each surface, which is
           the intersector OCCT's booleans use.

A research instrument, not part of the product.
"""
import json
import math
import sys
import time

SM_SUCCESS = 1000   # the scorer's success code
N = 4001


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def unit(a):
    n = math.sqrt(sum(x * x for x in a))
    return tuple(x / n for x in a)


def ax3(origin, x, y):
    from OCP.gp import gp_Ax3, gp_Pnt, gp_Dir
    z = unit(cross(x, y))
    return gp_Ax3(gp_Pnt(*origin), gp_Dir(*z), gp_Dir(*unit(x))), z


def flat_knots(knots):
    vals, mults = [], []
    for k in knots:
        if vals and abs(k - vals[-1]) < 1e-14:
            mults[-1] += 1
        else:
            vals.append(k)
            mults.append(1)
    return vals, mults


def build(s):
    from OCP import Geom as G
    from OCP.collections import Array1_double, Array1_int, Array2_double, Array2_gp_Pnt
    from OCP.gp import gp_Pnt
    rad = math.radians
    t = s["type"]
    if t == "plane":
        a, _ = ax3(s["origin"], s["xaxis"], s["yaxis"])
        return G.Geom_RectangularTrimmedSurface(G.Geom_Plane(a), s["u"][0], s["u"][1], s["v"][0], s["v"][1])
    if t == "cylinder":
        a, _ = ax3(s["origin"], s["xaxis"], s["yaxis"])
        return G.Geom_RectangularTrimmedSurface(G.Geom_CylindricalSurface(a, s["radius"]),
                                                rad(s["angle"][0]), rad(s["angle"][1]), s["height"][0], s["height"][1])
    if t == "cone":
        # radius(h) = h tan(alpha) for h in [h0, h1] measured from the apex along z
        _, z = ax3(s["apex"], s["xaxis"], s["yaxis"])
        h0, h1 = s["height"]
        al = rad(s["half_angle_deg"])
        o = tuple(s["apex"][i] + z[i] * h0 for i in range(3))
        a, _ = ax3(o, s["xaxis"], s["yaxis"])
        return G.Geom_RectangularTrimmedSurface(G.Geom_ConicalSurface(a, al, h0 * math.tan(al)),
                                                0.0, 2 * math.pi, 0.0, (h1 - h0) / math.cos(al))
    if t == "sphere":
        a, _ = ax3(s["center"], s["xaxis"], s["yaxis"])
        return G.Geom_RectangularTrimmedSurface(G.Geom_SphericalSurface(a, s["radius"]),
                                                rad(s["lon"][0]), rad(s["lon"][1]), rad(s["lat"][0]), rad(s["lat"][1]))
    if t == "torus":
        a, _ = ax3(s["center"], s["xaxis"], s["yaxis"])
        return G.Geom_RectangularTrimmedSurface(G.Geom_ToroidalSurface(a, s["R"], s["r"]),
                                                rad(s["major"][0]), rad(s["major"][1]), rad(s["minor"][0]), rad(s["minor"][1]))
    if t == "nurbs":
        p, q = int(s["degree"][0]), int(s["degree"][1])
        nu, nv = int(s["nu"]), int(s["nv"])
        poles, wts = Array2_gp_Pnt(1, nu, 1, nv), Array2_double(1, nu, 1, nv)
        for i in range(nu):
            for j in range(nv):
                poles.SetValue(i + 1, j + 1, gp_Pnt(*s["points"][i * nv + j]))
                wts.SetValue(i + 1, j + 1, float(s["weights"][i * nv + j]))
        arrs = []
        for knots in (s["knots_u"], s["knots_v"]):
            vals, mults = flat_knots(knots)
            k, mm = Array1_double(1, len(vals)), Array1_int(1, len(vals))
            for i, (v, mu) in enumerate(zip(vals, mults)):
                k.SetValue(i + 1, float(v))
                mm.SetValue(i + 1, mu)
            arrs.append((k, mm))
        return G.Geom_BSplineSurface(poles, wts, arrs[0][0], arrs[1][0], arrs[0][1], arrs[1][1], p, q)
    raise ValueError("unknown surface type " + t)


def sample3(c):
    a, b = c.FirstParameter(), c.LastParameter()
    out = []
    for i in range(N):
        p = c.Value(a + (b - a) * i / (N - 1))
        out.append([p.X(), p.Y(), p.Z()])
    return out


def sample2(c, surf):
    a, b = c.FirstParameter(), c.LastParameter()
    uv, on = [], []
    for i in range(N):
        p = c.Value(a + (b - a) * i / (N - 1))
        q = surf.Value(p.X(), p.Y())
        uv.append([p.X(), p.Y()])
        on.append([q.X(), q.Y(), q.Z()])
    return uv, on


def main():
    case, mode, tol, out = sys.argv[1:5]
    tol = 1e-7 if tol == "default" else float(tol)
    d = json.load(open(case))
    s1, s2 = (build(s) for s in d["surfaces"])
    curves, points, ok, name = [], [], True, "OK"
    t0 = time.perf_counter()
    ms = 0.0
    try:
        if mode == "gsi":
            from OCP.GeomInt import GeomInt_IntSS
            x = GeomInt_IntSS()
            x.Perform(s1, s2, tol, True, True, True)
            ms = (time.perf_counter() - t0) * 1e3
            ok = bool(x.IsDone())
            if ok:
                for i in range(1, x.NbLines() + 1):
                    c = {"type": "UNKNOWN", "xyz": sample3(x.Line(i))}
                    if x.HasLineOnS1(i):
                        c["uv1"], c["s1_at_uv"] = sample2(x.LineOnS1(i), s1)
                    if x.HasLineOnS2(i):
                        c["uv2"], c["s2_at_uv"] = sample2(x.LineOnS2(i), s2)
                    curves.append(c)
                for i in range(1, x.NbPoints() + 1):
                    p = x.Point(i)
                    points.append([p.X(), p.Y(), p.Z()])
            else:
                name = "GeomInt_IntSS not done"
        elif mode == "face":
            from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
            from OCP.IntTools import IntTools_FaceFace
            f1, f2 = (BRepBuilderAPI_MakeFace(s, 1e-7).Face() for s in (s1, s2))
            x = IntTools_FaceFace()
            x.SetParameters(True, True, True, tol)
            x.Perform(f1, f2)
            ms = (time.perf_counter() - t0) * 1e3
            ok = bool(x.IsDone())
            if ok:
                for c in x.Lines():
                    curves.append({"type": "UNKNOWN", "xyz": sample3(c.Curve())})
                for p in x.Points():
                    v = p.P1().Pnt()
                    points.append([v.X(), v.Y(), v.Z()])
            else:
                name = "IntTools_FaceFace not done"
        else:
            raise SystemExit("unknown mode " + mode)
    except Exception as e:
        if not type(e).__module__.startswith("OCP"):
            raise                      # a bug in this runner, not a kernel failure
        ms = (time.perf_counter() - t0) * 1e3
        ok, name, curves, points = False, "exception " + type(e).__name__, [], []
    json.dump({"status": SM_SUCCESS if ok else 1, "status_name": name, "time_ms": ms,
               "curves": curves, "points": points}, open(out, "w"))


if __name__ == "__main__":
    main()
