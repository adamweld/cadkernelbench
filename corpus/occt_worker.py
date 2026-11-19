# SPDX-License-Identifier: MIT OR Apache-2.0
"""One model, one process: the corpus operations on a STEP file, in Open CASCADE (OCP).

    python corpus/occt_worker.py MODEL.step

Prints one JSON line as each operation starts ({"start": op}) and one as it ends ({"op": op, ...}),
so that a crash or a timeout is pinned to the operation it happened in. What the operations are,
and why, is in corpus/README.md. Nothing of the model's geometry is printed: only counts, verdicts,
measures and times.
"""
import json
import os
import random
import sys
import tempfile
import time

from OCP.BRep import BRep_Tool
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.GeomAbs import GeomAbs_SurfaceType
from OCP.IFSelect import IFSelect_ReturnStatus
from OCP.Message import Message
from OCP.STEPControl import STEPControl_Reader, STEPControl_StepModelType, STEPControl_Writer
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.collections import List_TopoDS_Shape as TopTools_ListOfShape
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Pnt

import ops

for printer in list(Message.DefaultMessenger_s().Printers()):
    Message.DefaultMessenger_s().RemovePrinter(printer)


def read(path):
    reader = STEPControl_Reader()
    if reader.ReadFile(path) != IFSelect_ReturnStatus.IFSelect_RetDone:
        raise ops.KernelError("STEPControl_Reader could not read the file")
    reader.TransferRoots()
    shape = reader.OneShape()
    if shape.IsNull():
        raise ops.KernelError("STEPControl_Reader transferred nothing")
    return shape


def subshapes(shape, kind):
    """The distinct sub-shapes of a kind, each once whatever its orientation, in the order found."""
    found, buckets = [], {}
    e = TopExp_Explorer(shape, kind)
    while e.More():
        s = e.Current()
        bucket = buckets.setdefault(hash(s), [])
        if not any(s.IsSame(t) for t in bucket):
            bucket.append(s)
            found.append(s)
        e.Next()
    return found


def mass(shape):
    v, a = GProp_GProps(), GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, v)
    BRepGProp.SurfaceProperties_s(shape, a)
    return v.Mass(), a.Mass()


def bbox(shape):
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    lo, hi = box.CornerMin(), box.CornerMax()
    return lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()


def valid(shape):
    return BRepCheck_Analyzer(shape).IsValid()


def main(path):
    run = ops.Run()
    shape = run.op("import", lambda: read(path), lambda s: {
        "solids": len(subshapes(s, TopAbs_SOLID)), "shells": len(subshapes(s, TopAbs_SHELL)),
        "faces": len(subshapes(s, TopAbs_FACE)), "edges": len(subshapes(s, TopAbs_EDGE))})
    if shape is None:
        return
    solids = [TopoDS.Solid(s) for s in subshapes(shape, TopAbs_SOLID)]
    run.op("valid", lambda: valid(shape), lambda ok: {"valid": ok})
    run.op("mass", lambda: mass(shape), lambda m: {"volume": m[0], "area": m[1]})
    run.op("kinds", lambda: surface_kinds(shape), lambda k: {"kinds": k})

    def roundtrip():
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "rt.step")
            w = STEPControl_Writer()
            w.Transfer(shape, STEPControl_StepModelType.STEPControl_AsIs)
            if w.Write(out) != IFSelect_ReturnStatus.IFSelect_RetDone:
                raise ops.KernelError("STEPControl_Writer could not write the shape")
            back = read(out)
        return mass(back), len(subshapes(back, TopAbs_SOLID))
    run.op("roundtrip", roundtrip, lambda r: {"volume": r[0][0], "area": r[0][1], "solids": r[1]})

    def mesh():
        x0, y0, z0, x1, y1, z1 = bbox(shape)
        diag = ((x1 - x0) ** 2 + (y1 - y0) ** 2 + (z1 - z0) ** 2) ** 0.5
        m = BRepMesh_IncrementalMesh(shape, diag * 1e-3, False, 0.5, True)
        if not m.IsDone():
            raise ops.KernelError("BRepMesh_IncrementalMesh is not done")
        tris, bare = 0, 0
        for f in subshapes(shape, TopAbs_FACE):
            t = BRep_Tool.Triangulation_s(TopoDS.Face(f), TopLoc_Location())
            if t is None:
                bare += 1
            else:
                tris += t.NbTriangles()
        return tris, bare
    run.op("mesh", mesh, lambda r: {"triangles": r[0], "faces_unmeshed": r[1]})

    if not solids:
        return
    # The operations act on the largest solid, by its volume.
    target = max(solids, key=lambda s: mass(s)[0])
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(target, props)
    c = props.CentreOfMass()
    size = ops.Size(props.Mass(), (c.X(), c.Y(), c.Z()))

    def boolean():
        ball = BRepPrimAPI_MakeSphere(gp_Pnt(*size.centre), size.ball_radius).Shape()
        cut = BRepAlgoAPI_Cut(target, ball)
        if not cut.IsDone():
            raise ops.KernelError("BRepAlgoAPI_Cut is not done")
        r = cut.Shape()
        return valid(r), mass(r)[0], len(subshapes(r, TopAbs_SOLID))
    run.op("boolean", boolean, lambda r: {"valid": r[0], "volume": r[1], "solids": r[2]})

    edges = fillet_edges(target)
    for i in ops.pick(len(edges), ops.FILLETS, path):
        def fillet(e=TopoDS.Edge(edges[i])):
            f = BRepFilletAPI_MakeFillet(target)
            f.Add(size.fillet_radius, e)
            f.Build()
            if not f.IsDone():
                raise ops.KernelError("BRepFilletAPI_MakeFillet is not done")
            r = f.Shape()
            return valid(r), mass(r)[0]
        run.op("fillet", fillet, lambda r: {"valid": r[0], "volume": r[1]}, edge=i)

    faces = subshapes(target, TopAbs_FACE)
    planar = [(mass_face(f), k) for k, f in enumerate(faces)
              if BRepAdaptor_Surface(TopoDS.Face(f)).GetType() == GeomAbs_SurfaceType.GeomAbs_Plane]
    if planar:
        k = max(planar)[1]

        def shell():
            remove = TopTools_ListOfShape()
            remove.Append(faces[k])
            t = BRepOffsetAPI_MakeThickSolid()
            t.MakeThickSolidByJoin(target, remove, -size.shell_thickness, 1e-3)
            t.Build()
            if not t.IsDone():
                raise ops.KernelError("BRepOffsetAPI_MakeThickSolid is not done")
            r = t.Shape()
            return valid(r), mass(r)[0]
        run.op("shell", shell, lambda r: {"valid": r[0], "volume": r[1]})


def fillet_edges(solid):
    """The edges a fillet could be asked of: not degenerate, and not a seam (an edge a closed face
    meets itself along), in the order found."""
    seams = []
    for f in subshapes(solid, TopAbs_FACE):
        for e in subshapes(f, TopAbs_EDGE):
            if BRep_Tool.IsClosed_s(TopoDS.Edge(e), TopoDS.Face(f)):
                seams.append(e)
    return [e for e in subshapes(solid, TopAbs_EDGE)
            if not BRep_Tool.Degenerated_s(TopoDS.Edge(e)) and not any(e.IsSame(s) for s in seams)]


def mass_face(face):
    a = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, a)
    return a.Mass()


KINDS = {GeomAbs_SurfaceType.GeomAbs_Plane: "plane", GeomAbs_SurfaceType.GeomAbs_Cylinder: "cylinder",
         GeomAbs_SurfaceType.GeomAbs_Cone: "cone", GeomAbs_SurfaceType.GeomAbs_Sphere: "sphere",
         GeomAbs_SurfaceType.GeomAbs_Torus: "torus", GeomAbs_SurfaceType.GeomAbs_BSplineSurface: "bspline"}


def surface_kinds(shape):
    counts = {}
    for f in subshapes(shape, TopAbs_FACE):
        k = KINDS.get(BRepAdaptor_Surface(TopoDS.Face(f)).GetType(), "other")
        counts[k] = counts.get(k, 0) + 1
    return counts


if __name__ == "__main__":
    main(sys.argv[1])
