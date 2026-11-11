# SPDX-License-Identifier: MIT OR Apache-2.0
# /// script
# requires-python = ">=3.11"
# dependencies = ["cadquery-ocp==8.0.1.1.0"]
# ///
"""Adapter for Open CASCADE Technology, through the cadquery-ocp binding.

    python -m ckb.kernels.occt --out results.jsonl [--jobs 4] [--fuzzy0]
    python -m ckb.kernels.occt --summarise results.jsonl

Points are classified with OCCT's own solid classifier and results are
checked with BRepCheck_Analyzer.
"""
import math
import time

from ckb import core as m
from ckb import driver


def _ax2(fr, p, z=(0, 0, 1), x=(1, 0, 0)):
    from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
    return gp_Ax2(gp_Pnt(*fr.pt(p)), gp_Dir(*fr.vec(z)), gp_Dir(*fr.vec(x)))


def build(kind, fr, p, *dims):
    """Construct the kernel shape for one primitive. """
    from OCP import BRepPrimAPI as B
    mk = {"box": B.BRepPrimAPI_MakeBox, "cyl": B.BRepPrimAPI_MakeCylinder, "sph": B.BRepPrimAPI_MakeSphere,
          "cone": B.BRepPrimAPI_MakeCone, "torus": B.BRepPrimAPI_MakeTorus}[kind]
    return mk(_ax2(fr, p), *dims).Shape()


def volume(shape):
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, g)
    return g.Mass()


def valid(shape):
    from OCP.BRepCheck import BRepCheck_Analyzer
    return bool(BRepCheck_Analyzer(shape).IsValid())


def bbox(shape):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    bb = Bnd_Box()
    BRepBndLib.Add_s(shape, bb)
    lo, hi = bb.CornerMin(), bb.CornerMax()
    return lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()


def has_solid(shape):
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SOLID
    return TopExp_Explorer(shape, TopAbs_SOLID).More()


def inside(shape, g):
    """OCCT's own point classification against a result. None means the
    point was reported as on the boundary."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN, TopAbs_OUT
    st = BRepClass3d_SolidClassifier(shape, gp_Pnt(*g), 1e-7).State()
    return True if st == TopAbs_IN else False if st == TopAbs_OUT else None


def boolean(op, A, B, fuzzy):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse, BRepAlgoAPI_Cut, BRepAlgoAPI_Common
    from OCP.collections import List_TopoDS_Shape
    cls = {"fuse": BRepAlgoAPI_Fuse, "cut": BRepAlgoAPI_Cut, "common": BRepAlgoAPI_Common}[op]
    t = time.perf_counter()
    out = {"status": "ok"}
    try:
        b = cls()
        la, lb = List_TopoDS_Shape(), List_TopoDS_Shape()
        la.Append(A)
        lb.Append(B)
        b.SetArguments(la)
        b.SetTools(lb)
        if fuzzy > 0:
            b.SetFuzzyValue(fuzzy)
        b.Build()
        if not b.IsDone():
            out["status"] = "error"
        else:
            s = b.Shape()
            out["shape"] = s
            out["vol"] = volume(s)
            if not valid(s):
                out["status"] = "invalid"
    except Exception as e:
        reraise_unless_kernel(e)
        out["status"] = "error"
        out["exc"] = type(e).__name__
    out["ms"] = round((time.perf_counter() - t) * 1e3, 2)
    return out


def sharp_edges(shape):
    """Edges where two different faces meet at an angle. Seams, degenerate
    edges and smooth joins are excluded: they are not edges a designer
    could ask to fillet."""
    from OCP.TopExp import TopExp
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopoDS import TopoDS
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    from OCP.gp import gp_Pnt2d
    from OCP.TopAbs import TopAbs_REVERSED
    from OCP.collections import IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as AncMap
    m = AncMap()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, m)
    out = []
    for i in range(1, m.Extent() + 1):
        e = TopoDS.Edge(m.FindKey(i))
        faces = [TopoDS.Face(f) for f in m.FindFromIndex(i)]
        if BRep_Tool.Degenerated_s(e) or len(faces) != 2 or faces[0].IsSame(faces[1]):
            continue
        # Angle between the two face normals at three points along the edge.
        # 0 degrees is a smooth join, 90 a square corner, 180 a knife edge.
        angles = []
        for t in (0.1, 0.5, 0.9):
            normals = []
            for f in faces:
                c2d = BRep_Tool.CurveOnSurface_s(e, f, 0.0, 0.0)
                uv = c2d.Value(c2d.FirstParameter() + t * (c2d.LastParameter() - c2d.FirstParameter()))
                pr = BRepLProp_SLProps(BRepAdaptor_Surface(f), uv.X(), uv.Y(), 1, 1e-9)
                if not pr.IsNormalDefined():
                    break
                n = pr.Normal()
                sgn = -1.0 if f.Orientation() == TopAbs_REVERSED else 1.0
                normals.append((sgn * n.X(), sgn * n.Y(), sgn * n.Z()))
            if len(normals) != 2:
                angles = None
                break
            dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(*normals))))
            angles.append(math.degrees(math.acos(dot)))
        if angles is None or min(angles) < 5.0:   # undefined, or smooth to within 5 degrees
            continue
        g = GProp_GProps()
        BRepGProp.LinearProperties_s(e, g)
        if g.Mass() > 1e-6:
            out.append((e, g.Mass(), min(angles), max(angles)))
    return out


def fillet(shape, edges, radius):
    """Round the given sharp edges. Returns ok, invalid or error."""
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
    try:
        mk = BRepFilletAPI_MakeFillet(shape)
        for x in edges:
            mk.Add(radius, x[0])
        mk.Build()
        if not mk.IsDone():
            return "error"
        return "ok" if valid(mk.Shape()) else "invalid"
    except Exception as e:
        reraise_unless_kernel(e)
        return "error"


def reraise_unless_kernel(e):
    """Re-raise e unless OCCT raised it. The binding gives its exception
    classes no common Python base, so they are recognised by the module
    they come from. Anything else is a bug in this script and must never
    be counted as a kernel failure."""
    if not type(e).__module__.startswith("OCP"):
        raise e


m.install(globals())

if __name__ == "__main__":
    driver.main(m, "ckb.kernels.occt")
