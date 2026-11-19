# SPDX-License-Identifier: MIT OR Apache-2.0
"""Rates from a directory of corpus results, by kernel and operation, and where two kernels disagree.

    python corpus/summarize.py RESULTS_DIR

Only rates and counts are printed, never a model's identity: what may be said of a private corpus.
A disagreement is two kernels' volumes for the same model and operation more than 1e-6 apart
(relative), where both said ok; agreement is not proof that either is right.
"""
import gzip
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REL = 1e-6


def load(d):
    out = {}
    for f in sorted(os.listdir(d)):
        if f.endswith(".jsonl.gz"):
            with gzip.open(os.path.join(d, f), "rt") as g:
                out[f[: -len(".jsonl.gz")]] = {r["model"]: r for r in map(json.loads, g) if r}
    return out


def outcome(rec, op):
    """Each attempt of op in a model's record: ok, invalid (ok but the kernel's own check failed,
    or a volume not finite and positive), error, or the crash or timeout it ended in."""
    got = []
    for r in rec["ops"]:
        if r["op"] != op:
            continue
        if r["status"] != "ok":
            got.append(r["status"])
        elif r.get("valid") is False or ("volume" in r and op != "mass" and not (0 < r["volume"] < 1e300)):
            got.append("invalid")
        else:
            got.append("ok")
    if rec["outcome"] != "done" and rec.get("in_op") == op:
        got.append(rec["outcome"])
    return got


OPS = ["import", "valid", "mass", "roundtrip", "mesh", "boolean", "fillet", "shell"]


def main():
    res = load(sys.argv[1])
    for kernel, recs in res.items():
        print(f"\n{kernel}: {len(recs)} models, outcomes {dict(Counter(r['outcome'] for r in recs.values()))}")
        for op in OPS:
            c = Counter(o for r in recs.values() for o in outcome(r, op))
            n = sum(c.values())
            if n:
                print(f"  {op:10s} {n:6d}  " + "  ".join(f"{k} {v / n:6.1%}" for k, v in c.most_common()))
        rt = [r for r in recs.values() if any(o["op"] == "roundtrip" and o["status"] == "ok" for o in r["ops"])]
        drift = sum(1 for r in rt if not close(vol(r, "mass"), vol(r, "roundtrip")))
        print(f"  roundtrip volume changed by more than {REL:g}: {drift} of {len(rt)}")
    kernels = sorted(res)
    for i, a in enumerate(kernels):
        for b in kernels[i + 1:]:
            common = res[a].keys() & res[b].keys()
            for op in ["mass", "boolean"]:
                both = [m for m in common if vol(res[a][m], op) is not None and vol(res[b][m], op) is not None]
                differ = sum(1 for m in both if not close(vol(res[a][m], op), vol(res[b][m], op)))
                print(f"\n{a} vs {b}, {op}: both ok on {len(both)}, volumes differ on {differ}")


def vol(rec, op):
    for r in rec["ops"]:
        if r["op"] == op and r["status"] == "ok" and "volume" in r:
            return r["volume"]
    return None


def close(x, y):
    return x is not None and y is not None and abs(x - y) <= REL * max(abs(x), abs(y), 1e-300)


if __name__ == "__main__":
    main()
