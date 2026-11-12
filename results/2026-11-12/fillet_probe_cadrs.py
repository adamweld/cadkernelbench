"""Check that cadrs's successful fillets changed the body: replay every sequence's final
fillet and 300 fillet cases recorded ok, with the server's fillet_probe request.

    CADRS_SERVER=... PYTHONPATH=. python results/2026-11-12/fillet_probe_cadrs.py
"""
import math, random, statistics, collections, sys
from ckb import core as m
import ckb.kernels.cadrs as k
from ckb.kernels.cadrs import S, KernelError
from ckb.paired import load
m.FUZZY=[0.0]
cases={c["id"]:c for c in m.case_list()}
R={}
for part in ("booleans","fillets","sequences"):
    R.update(load(f"results/2026-11-12/cadrs_{part}.jsonl.gz")[0])
log=[]
def probe(shape, edges, radius):
    try:
        v=S.call(op="fillet_probe", h=shape.h, edges=[e[0][1] for e in edges], r=float(radius))
    except KernelError:
        log.append(("error",)); return "error"
    L=sum(e[1] for e in edges)
    right=all(abs(e[2]-90)<1e-6 and abs(e[3]-90)<1e-6 for e in edges)
    log.append(("ok", v["vol_before"]-v["vol_after"], v["faces_after"]-v["faces_before"], (1-math.pi/4)*radius**2*L, right, len(edges)))
    return "ok"
m.fillet=probe
chains=[i for i in R if cases[i]["kind"]=="chain"]
random.seed(3)
fils=random.sample([i for i in R if cases[i]["kind"]=="fillet" and R[i]["status"]=="ok"],300)
for label,ids,run in (("sequence final fillets",chains,m.run_chain_case),("fillet cases recorded ok",fils,m.run_fillet_case)):
    log.clear()
    for i in ids: run(cases[i])
    ok=[x for x in log if x[0]=="ok"]
    changed=sum(abs(x[1])>1e-9 and x[2]>0 for x in ok)
    ratios=[abs(x[1])/x[3] for x in ok if x[4] and x[5]==1]
    print(f"{label}: {len(log)} replayed, {len(ok)} ok; volume changed and faces added in {changed} of {len(ok)}")
    if ratios:
        print(f"   single edges at 90 degrees: {len(ratios)}; |dV| / ((1-pi/4) r^2 L) median {statistics.median(ratios):.6f}, min {min(ratios):.4f}, max {max(ratios):.4f}")
    nochange=[x for x in ok if not(abs(x[1])>1e-9 and x[2]>0)]
    print("   unchanged examples:", nochange[:5])

