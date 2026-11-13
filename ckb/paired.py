# SPDX-License-Identifier: MIT OR Apache-2.0
"""Compare kernels case by case on the same case list.

    python -m ckb.paired NAME=results.jsonl[.gz] NAME=results.jsonl[.gz] ...

Each file is the output of one adapter run with --fuzzy0. Only cases
present in every file are compared. Generic and fillet cases are also
split by whether a torus is among the primitives they draw, found by
replaying the case's seeded choices (no kernel is called), so the split
is the same for every kernel.
"""
import collections
import gzip
import json
import random
import sys

from ckb import core as m
from ckb import rounds

m.FUZZY = [0.0]


def load(path):
    rows, lost = {}, {}
    op = gzip.open if path.endswith(".gz") else open
    for line in op(path, "rt"):
        d = json.loads(line)
        if "lost" in d:
            lost[d["lost"]] = d["why"]
        elif "case" in d:
            rows[d["case"]["id"]] = d["res"]
    return rows, lost


def _kinds(draw):
    """The primitive kinds drawn, with a stand-in build that calls no kernel."""
    kinds = []
    saved = m.build
    m.build = lambda kind, *a: kinds.append(kind)
    try:
        draw()
    finally:
        m.build = saved
    return kinds


def has_torus(c):
    if c["kind"] == "generic":
        rng = rounds.rng("boolean", c["id"], 1_000_003 * c["id"] + 17)
        return "torus" in _kinds(lambda: (m.random_prim(rng, 0), m.random_prim(rng, 25)))
    if c["kind"] == "fillet":
        rng = rounds.rng("fillet", c["id"], 2_000_003 * c["id"] + 29)

        def draw():
            m.random_prim(rng, 0)
            if rng.random() < 0.75:
                m.random_prim(rng, 20)
        return "torus" in _kinds(draw)   # either solid drawn, whatever base a kernel used
    return False


def main():
    runs = {}
    for arg in sys.argv[1:]:
        name, path = arg.split("=", 1)
        runs[name] = load(path)
    names = list(runs)
    cases = {c["id"]: c for c in m.case_list()}
    common = set.intersection(*[set(r) | set(l) for r, l in runs.values()])

    def bool_fail(res):
        return any(res[o]["status"] != "ok" for o in ("fuse", "cut", "common"))

    def fails(name, i):
        rows, lost = runs[name]
        if i in lost:
            return "lost"
        r = rows[i]
        c = cases[i]
        if c["kind"] in ("near", "generic"):
            return "fail" if bool_fail(r) else "ok"
        return r["status"]

    def row(label, ids):
        ids = sorted(ids)
        out = [label, str(len(ids))]
        for n in names:
            out.append(str(sum(fails(n, i) != "ok" for i in ids)))
        print("| " + " | ".join(out) + " |")

    print("### Booleans, pairs with any failure\n")
    print("| Set | Pairs | " + " | ".join(names) + " |\n|" + "---|" * (2 + len(names)))
    near = [i for i in common if cases[i]["kind"] == "near"]
    row("Near-degenerate, all families", near)
    for fam in m.NEAR_FAMILIES:
        row(f"- {fam}", [i for i in near if cases[i]["family"] == fam])
    tang = [i for i in near if cases[i]["family"] == "cyl_tangent_inside"]
    row("- tangent hole, offset of one micron or less", [i for i in tang if abs(cases[i]["eps"]) <= 1e-6])
    row("- tangent hole, larger offset", [i for i in tang if abs(cases[i]["eps"]) > 1e-6])
    gen = [i for i in common if cases[i]["kind"] == "generic"]
    tor = {i for i in gen if has_torus(cases[i])}
    row("Generic position, all", gen)
    row("Generic position, no torus", [i for i in gen if i not in tor])
    row("Generic position, with a torus", tor)

    print("\n### Operation outcomes on booleans\n")
    print("| Set | Kernel | Ops | error | invalid | wrong | lost pairs |\n|---|---|---|---|---|---|---|")
    for label, ids in (("Near-degenerate", near), ("Generic, no torus", [i for i in gen if i not in tor]),
                       ("Generic, with a torus", tor)):
        for n in names:
            rows, lost = runs[n]
            rs = [rows[i] for i in ids if i in rows]
            st = collections.Counter(r[o]["status"] for r in rs for o in ("fuse", "cut", "common"))
            print(f"| {label} | {n} | {3 * len(rs)} | {st['error']} | {st['invalid']} | {st['wrong']} | {sum(i in lost for i in ids)} |")

    ch = [i for i in common if cases[i]["kind"] == "chain"]
    if ch:
        print("\n### Feature sequences\n")
        print("| Kernel | Sequences | Completed all 12 | Stopped: error | Stopped: invalid | Stopped: wrong | Lost | Final fillet failed, of those attempted | Median ms for 12 steps |\n|---|---|---|---|---|---|---|---|---|")
        for n in names:
            rows, lost = runs[n]
            rs = [rows[i] for i in ch if i in rows]
            st = collections.Counter(r["status"] for r in rs)
            fil = [r["fillet"] for r in rs if "fillet" in r]
            ms = sorted(r["ms"] for r in rs if r["status"] == "ok")
            print(f"| {n} | {len(ch)} | {st['ok']} | {st['error']} | {st['invalid']} | {st['wrong']} | {sum(i in lost for i in ch)} | {sum(f != 'ok' for f in fil)} of {len(fil)} | {ms[len(ms) // 2] if ms else 0:.0f} |")
        both = [i for i in ch if all(i in runs[n][0] for n in names)]
        if len(names) > 1:
            agree = collections.Counter(tuple(runs[n][0][i]["status"] == "ok" for n in names) for i in both)
            print("\nSequences by completion (" + ", ".join(names) + "): " +
                  ", ".join(f"{k}: {v}" for k, v in sorted(agree.items())))

    fl = [i for i in common if cases[i]["kind"] == "fillet"]
    if fl:
        print("\n### Fillets, failed of attempted (cases skipped for no sharp edge excluded)\n")
        print("| Edges | Radius | Inputs | " + " | ".join(names) + " |\n|" + "---|" * (3 + len(names)))
        for tsel, tl in ((False, "no torus"), (True, "with a torus")):
            for mode in m.FILLET_MODES:
                for fr in m.FILLET_FRACTIONS:
                    ids = [i for i in fl if cases[i]["mode"] == mode and cases[i]["frac"] == fr
                           and has_torus(cases[i]) == tsel]
                    cells = []
                    for n in names:
                        rows, lost = runs[n]
                        att = [i for i in ids if i in lost or rows[i]["status"] != "skipped"]
                        bad = [i for i in att if i in lost or rows[i]["status"] != "ok"]
                        cells.append(f"{len(bad)} of {len(att)}" + (f" ({100 * len(bad) / len(att):.1f}%)" if att else ""))
                    print(f"| {mode} | {fr} | {tl} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
