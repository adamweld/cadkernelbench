# SPDX-License-Identifier: MIT OR Apache-2.0
"""What the OCCT-based systems share: building a model step by step, finding
the face under a point, and finding a point inside a face."""
import random


def is_kernel_error(exc):
    return type(exc).__module__.startswith("OCP")


def primitive(frame, s):
    from OCP import BRepPrimAPI as B
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    R, o = frame["R"], frame["o"]

    def pt(p):
        return gp_Pnt(*[o[i] + sum(R[i][j] * p[j] for j in range(3)) for i in range(3)])

    def axis(j):
        return gp_Dir(R[0][j], R[1][j], R[2][j])
    if s["kind"] == "box":
        return B.BRepPrimAPI_MakeBox(gp_Ax2(pt(s["p"]), axis(2), axis(0)), *s["d"]).Shape()
    if s["kind"] == "cyl":
        a = s["ax"]
        return B.BRepPrimAPI_MakeCylinder(gp_Ax2(pt(s["p"]), axis(a), axis((a + 1) % 3)), s["r"], s["h"]).Shape()
    return B.BRepPrimAPI_MakeSphere(gp_Ax2(pt(s["p"]), axis(2), axis(0)), s["r"]).Shape()


def faces(shape):
    """The faces of a shape, each once, in the explorer's order."""
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    out, seen, ex = [], {}, TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face(ex.Current())
        same = seen.setdefault(hash(f), [])
        if not any(f.IsSame(g) for g in same):
            same.append(f)
            out.append(f)
        ex.Next()
    return out


def boolean(op, a, b):
    """The operation object, built, so its history can be read."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    x = (BRepAlgoAPI_Fuse if op == "fuse" else BRepAlgoAPI_Cut)(a, b)
    if not x.IsDone():
        raise OcctDeclined(f"{op} is not done")
    return x


class OcctDeclined(Exception):
    __module__ = "OCP.declined"     # so that is_kernel_error counts it as OCCT's


def face_at(face_list, point):
    """Index of the one face the global point lies on, or None."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt
    v = BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex()
    found = [i for i, f in enumerate(face_list) if BRepExtrema_DistShapeShape(v, f).Value() < 1e-6]
    return found[0] if len(found) == 1 else None


def point_inside(face):
    """A global point on the face and away from its edges."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.BRepTools import BRepTools
    from OCP.gp import gp_Pnt2d
    from OCP.TopAbs import TopAbs_IN
    u0, u1, v0, v1 = BRepTools.UVBounds_s(face)
    surf = BRepAdaptor_Surface(face)
    rng = random.Random(1)
    du, dv = (u1 - u0) * 0.02, (v1 - v0) * 0.02

    def is_in(u, v):
        return BRepClass_FaceClassifier(face, gp_Pnt2d(u, v), 1e-7).State() == TopAbs_IN
    fallback = None
    for k in range(400):
        u, v = ((u0 + u1) / 2, (v0 + v1) / 2) if k == 0 else (rng.uniform(u0, u1), rng.uniform(v0, v1))
        if not is_in(u, v):
            continue
        p = surf.Value(u, v)
        if all(is_in(u + a, v + b) for a, b in ((du, 0), (-du, 0), (0, dv), (0, -dv))):
            return [p.X(), p.Y(), p.Z()]
        fallback = fallback or [p.X(), p.Y(), p.Z()]
    return fallback
