"""With OCCT's adaptive volume integration (relative precision 1e-9), the volume change of each
cadrs fillet, against cadrs's own. Reads export_cadrs.py's output.

    python results/2026-11-12/fillet_check/occt_volume.py OUTDIR
"""
import json, sys
from OCP.STEPControl import STEPControl_Reader
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
D=sys.argv[1]; meta=json.load(open(f"{D}/meta.json"))
def read(p):
    r=STEPControl_Reader(); r.ReadFile(p); r.TransferRoots(); return r.OneShape()
def vol(s):
    g=GProp_GProps(); err=BRepGProp.VolumeProperties_s(s,g,1e-9); return g.Mass(), err
print("case | expected |dV| | cadrs dV | OCCT adaptive dV | OCCT error bound (before, after) | cadrs volume - OCCT volume (before, after)")
for cid,mt in meta.items():
    (vb,eb),(va,ea)=vol(read(f"{D}/{cid}_before.step")),vol(read(f"{D}/{cid}_after.step"))
    cv_b=mt["cadrs_vol"]; cv_a=cv_b-mt["cadrs_dV"]
    print(f"{cid} | {mt['expected']:.3g} | {mt['cadrs_dV']:.4g} | {vb-va:.4g} | {eb:.2g}, {ea:.2g} | {cv_b-vb:.3g}, {cv_a-va:.3g}")
