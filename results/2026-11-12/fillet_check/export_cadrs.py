"""Write cadrs's body before and after each listed fillet as STEP, with the fillet's radius,
edges, expected and measured volume change (meta.json), using cadrs_server's fillet_export.

    CADRS_SERVER=... PYTHONPATH=. python results/2026-11-12/fillet_check/export_cadrs.py OUTDIR "5897 5905 ..."
"""
import json, math, sys
from ckb import core as m
import ckb.kernels.cadrs as k
from ckb.kernels.cadrs import S
m.FUZZY=[0.0]
cases={c["id"]:c for c in m.case_list()}
D=sys.argv[1]; meta={}
def exp(shape, edges, radius, cid=None):
    ids=[e[0][1] for e in edges]
    v=S.call(op="fillet_export", h=shape.h, edges=ids, r=float(radius), before=f"{D}/{cid}_before.step", after=f"{D}/{cid}_after.step")
    p=S.call(op="fillet_probe", h=shape.h, edges=ids, r=float(radius))
    L=sum(e[1] for e in edges)
    meta[cid]=dict(r=radius, L=L, n_edges=len(edges), angs=[(e[2],e[3]) for e in edges], expected=(1-math.pi/4)*radius**2*L,
                   cadrs_dV=v["vol_before"]-v["vol_after"], cadrs_vol=v["vol_before"], edge_points=p["edge_points"])
    return "ok"
for cid in map(int, " ".join(sys.argv[2:]).split()):
    m.fillet=lambda s,e,r,cid=cid: exp(s,e,r,cid)
    (m.run_chain_case if cases[cid]["kind"]=="chain" else m.run_fillet_case)(cases[cid])
json.dump(meta, open(f"{D}/meta.json","w"))
print(len(meta), "exported")
