"""Replay every cadrs case that did not fully succeed and compare outcomes.

    CADRS_SERVER=... PYTHONPATH=. python results/2026-11-12/replay_cadrs_failures.py \
        results/2026-11-12/cadrs_{booleans,fillets,sequences}.jsonl.gz
"""
import collections, json, sys
from multiprocessing import Pool
from ckb import core as m
from ckb.paired import load
m.FUZZY = [0.0]
cases = {c["id"]: c for c in m.case_list()}

def outcome(c, r):
    if c["kind"] in ("near", "generic"):
        return tuple(r[o]["status"] for o in ("fuse", "cut", "common"))
    if c["kind"] == "chain":
        return (r["status"], r.get("fail_step"), r.get("fillet"))
    return (r["status"],)

def replay(i):
    import ckb.kernels.cadrs as k
    from ckb.kernels.cadrs import S, KernelError
    texts = []
    orig = m.fillet
    def f(shape, edges, radius):
        try:
            v = S.call(op="fillet", h=shape.h, edges=[e[0][1] for e in edges], r=float(radius))
        except KernelError as e:
            texts.append(str(e)[:160]); return "error"
        ok, why = k._verdict(v)
        if not ok: texts.append("invalid: " + "; ".join(why)[:160])
        return "ok" if ok else "invalid"
    m.fillet = f
    c = cases[i]
    run = m.run_fillet_case if c["kind"] == "fillet" else m.run_chain_case if c["kind"] == "chain" else m.run_boolean_case
    r = run(c)
    return i, outcome(c, r), texts

if __name__ == "__main__":
    R = {}
    for path in sys.argv[1:]:
        R.update(load(path)[0])
    todo = [i for i, r in R.items() if outcome(cases[i], r) not in (("ok", "ok", "ok"), ("ok",), ("skipped",), ("ok", None, "ok"), ("ok", None, None))]
    with Pool(8) as p:
        out = p.map(replay, todo, chunksize=4)
    same = [i for i, o, _ in out if o == outcome(cases[i], R[i])]
    diff = [(i, outcome(cases[i], R[i]), o) for i, o, _ in out if o != outcome(cases[i], R[i])]
    kinds = collections.Counter(cases[i]["kind"] for i in todo)
    print(f"replayed {len(todo)} failing cases {dict(kinds)}: same outcome {len(same)}, different {len(diff)}")
    for d in diff: print("  differs:", d)
    print("fillet failure texts:")
    t = collections.Counter(x.split("(")[0].split("{")[0].strip()[:60] for _, _, ts in out for x in ts)
    for k_, v in t.most_common(): print(f"  {v:4d} {k_}")
