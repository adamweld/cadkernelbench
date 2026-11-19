"""With OCCT, the material a cadrs fillet removed and added (before - after, after - before),
split by whether each piece touches the filleted edge. Reads export_cadrs.py's output.

    python results/2026-11-12/fillet_check/occt_difference.py OUTDIR
"""
import json, sys
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Pnt
D=sys.argv[1]; meta=json.load(open(f"{D}/meta.json"))
def read(p):
    r=STEPControl_Reader(); assert r.ReadFile(p)==IFSelect_RetDone, p; r.TransferRoots(); return r.OneShape()
def vol(s):
    g=GProp_GProps(); BRepGProp.VolumeProperties_s(s,g); return g.Mass()
def pieces(s):
    e=TopExp_Explorer(s,TopAbs_SOLID); out=[]
    while e.More(): out.append(e.Current()); e.Next()
    return out
print("case | r | expected |dV| | cadrs dV | OCCT removed: near edge / away | OCCT added: near edge / away | farthest piece from edge | valid before/after (OCCT)")
for cid,mt in meta.items():
    b,a=read(f"{D}/{cid}_before.step"),read(f"{D}/{cid}_after.step")
    poly=BRepBuilderAPI_MakePolygon()
    for seg in mt["edge_points"]:
        for p in seg: poly.Add(gp_Pnt(*p))
    wire=poly.Wire()
    near_tol=4*mt["r"]+1e-3
    res={}
    far=0.0
    for lab,(x,y) in (("removed",(b,a)),("added",(a,b))):
        c=BRepAlgoAPI_Cut(x,y); c.Build()
        if not c.IsDone(): res[lab]="cut failed"; continue
        nv=fv=0.0
        for s in pieces(c.Shape()):
            v=vol(s); d=BRepExtrema_DistShapeShape(s,wire).Value()
            if d<=near_tol: nv+=v
            else: fv+=v; far=max(far,d)
        res[lab]=f"{nv:.3g} / {fv:.3g}"
    print(f"{cid} | {mt['r']:.4g} | {mt['expected']:.3g} | {mt['cadrs_dV']:.3g} | {res['removed']} | {res['added']} | {far:.3g} | {BRepCheck_Analyzer(b).IsValid()}/{BRepCheck_Analyzer(a).IsValid()}")
