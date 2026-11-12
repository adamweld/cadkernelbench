# SPDX-License-Identifier: MIT OR Apache-2.0
"""Cases for reference survival: a generated model, references picked on
it, an upstream edit, and what the edit did to each referenced face.

A system under test is a module with five functions (see
docs/REFERENCE-SURVIVAL.md):

    build(model)            -> state        model is Model.to_json()
    pick(state, point)      -> reference    a global point on a face; any JSON value comes back
    edit(state, edit, model)-> state        the edit, and the whole model after it
    resolve(state, ref)     -> (status, points)
                               status is "found", "lost" or "ambiguous";
                               points has one global point on each face returned
    is_kernel_error(exc)    -> bool         tells the system's own failures from bugs in the adapter
"""
import math
import random
import time

from . import model as M

SIZES = [10, 50, 200]
CLASSES = ["A", "B", "C", "D", "E", "F", "G", "H", "J"]
CASES = {10: 60, 50: 40, 200: 10}     # per class
REFS = 8                              # references per case
FOCUS = 4                             # of which up to this many are on the edited feature

CLASS_NAMES = {
    "A": "dimension change", "B": "feature appended", "C": "feature moved", "D": "slot cut through (split)",
    "E": "slot shortened (merge)", "F": "feature removed", "G": "feature inserted upstream",
    "H": "two features reordered", "J": "edit made and undone",
}


def case_list():
    cases, i = [], 0
    for size in SIZES:
        for cls in CLASSES:
            for rep in range(CASES[size]):
                cases.append({"id": i, "kind": cls, "size": size, "rep": rep})
                i += 1
    return cases


# ---- generation

def block_side(size):
    return 30.0 * math.sqrt(size) + 50.0


def feature(rng, uid, S, Lz, kind=None):
    kind = kind or rng.choice(["hole", "blind", "sidehole", "boss", "pocket", "pad", "slot", "ball"])
    x, y = rng.uniform(0.08, 0.92) * S, rng.uniform(0.08, 0.92) * S
    s = {"uid": uid, "feature": kind}
    if kind == "hole":
        s.update(op="cut", kind="cyl", ax=2, p=[x, y, -5.0], r=rng.uniform(3, 8), h=Lz + 10.0)
    elif kind == "blind":
        depth = rng.uniform(5, 20)
        s.update(op="cut", kind="cyl", ax=2, p=[x, y, Lz - depth], r=rng.uniform(3, 8), h=depth + 5.0)
    elif kind == "sidehole":
        ax = rng.choice([0, 1])
        p = [x, y, rng.uniform(10, Lz - 10)]
        p[ax] = -5.0
        s.update(op="cut", kind="cyl", ax=ax, p=p, r=rng.uniform(3, 6), h=S + 10.0)
    elif kind == "boss":
        s.update(op="fuse", kind="cyl", ax=2, p=[x, y, Lz - 2.0], r=rng.uniform(5, 12), h=rng.uniform(8, 22))
    elif kind == "pocket":
        depth = rng.uniform(5, 20)
        s.update(op="cut", kind="box", p=[x, y, Lz - depth], d=[rng.uniform(8, 25), rng.uniform(8, 25), depth + 5.0])
    elif kind == "pad":
        s.update(op="fuse", kind="box", p=[x, y, Lz - 2.0], d=[rng.uniform(8, 25), rng.uniform(8, 25), rng.uniform(8, 22)])
    elif kind == "slot":
        depth = rng.uniform(5, 15)
        s.update(op="cut", kind="box", p=[x * 0.5, y, Lz - depth], d=[rng.uniform(30, 80), rng.uniform(4, 8), depth + 5.0])
    else:
        s.update(op="cut", kind="sph", p=[x, y, Lz], r=rng.uniform(5, 12))
    return s


def generate(c):
    """The case's model, its edits (one, or two for a round trip), and the
    uid of the feature the edit is about, if any."""
    rng = random.Random(7_000_003 * c["id"] + 17)
    size, cls = c["size"], c["kind"]
    S, Lz = block_side(size), rng.uniform(30, 50)
    frame = {"R": M.rotation(rng), "o": [rng.uniform(-200, 200) for _ in range(3)]}
    steps = [{"uid": 0, "feature": "block", "op": "base", "kind": "box", "p": [0.0, 0.0, 0.0], "d": [S, S, Lz]}]
    for uid in range(1, size + 1):
        steps.append(feature(rng, uid, S, Lz))
    if cls in "DE":                         # these need a slot to lengthen or shorten
        k = rng.randrange(1, size + 1)
        steps[k] = feature(rng, k, S, Lz, "slot")
    model = M.Model(frame, steps)
    new_uid = size + 1

    def one(cls):
        victim = rng.choice(model.steps[1:])
        if cls == "A":
            key = "r" if victim["kind"] != "box" else "d"
            f = rng.choice([rng.uniform(0.7, 0.9), rng.uniform(1.1, 1.35)])
            val = victim["r"] * f if key == "r" else [victim["d"][0] * f, victim["d"][1], victim["d"][2]]
            return {"op": "set", "uid": victim["uid"], "values": {key: val}}, victim["uid"]
        if cls == "B":
            return {"op": "insert", "index": len(model.steps), "step": feature(rng, new_uid, S, Lz)}, None
        if cls == "C":
            fresh = feature(rng, victim["uid"], S, Lz, victim["feature"])
            p = list(victim["p"])
            for i in (0, 1):
                if not (victim["feature"] == "sidehole" and victim["ax"] == i):
                    p[i] = fresh["p"][i]
            return {"op": "set", "uid": victim["uid"], "values": {"p": p}}, victim["uid"]
        if cls == "F":
            return {"op": "remove", "uid": victim["uid"]}, victim["uid"]
        if cls == "G":
            return {"op": "insert", "index": rng.randrange(1, len(model.steps)), "step": feature(rng, new_uid, S, Lz)}, None
        if cls == "H":                      # two neighbours that both cut or both add: the solid is unchanged
            pairs = [i for i in range(1, len(model.steps) - 1) if model.steps[i]["op"] == model.steps[i + 1]["op"]]
            i = rng.choice(pairs)
            return {"op": "swap", "index": i}, model.steps[i]["uid"]
        raise ValueError(cls)

    if cls in "DE":
        slot = next(s for s in model.steps if s["feature"] == "slot" and s["uid"] == k)
        through = {"p": [-5.0, slot["p"][1], slot["p"][2]], "d": [S + 10.0, slot["d"][1], slot["d"][2]]}
        short = {"p": list(slot["p"]), "d": list(slot["d"])}
        if cls == "D":
            return model, [{"op": "set", "uid": k, "values": through}], k
        model = apply(model, {"op": "set", "uid": k, "values": through})
        return model, [{"op": "set", "uid": k, "values": short}], k
    if cls == "J":
        e, focus = one(rng.choice("ACFG"))
        return model, [e, inverse(model, e)], focus
    e, focus = one(cls)
    return model, [e], focus


def apply(model, e):
    m = model.copy()
    if e["op"] == "set":
        m.step(e["uid"]).update({k: (list(v) if isinstance(v, list) else v) for k, v in e["values"].items()})
    elif e["op"] == "insert":
        m.steps.insert(e["index"], dict(e["step"]))
    elif e["op"] == "remove":
        m.steps = [s for s in m.steps if s["uid"] != e["uid"]]
    elif e["op"] == "swap":
        i = e["index"]
        m.steps[i], m.steps[i + 1] = m.steps[i + 1], m.steps[i]
    return M.Model(m.frame, m.steps)


def inverse(model, e):
    if e["op"] == "set":
        s = model.step(e["uid"])
        return {"op": "set", "uid": e["uid"], "values": {k: s[k] for k in e["values"]}}
    if e["op"] == "insert":
        return {"op": "remove", "uid": e["step"]["uid"]}
    if e["op"] == "remove":
        i = next(i for i, s in enumerate(model.steps) if s["uid"] == e["uid"])
        return {"op": "insert", "index": i, "step": dict(model.steps[i])}
    return dict(e)


def references(c, before, after, focus):
    """Up to REFS references: an identity that bounds the model before the
    edit, one of its pieces, a point well inside that piece, and what is
    true of the identity afterwards. Identities whose piece count depends on
    the sampling are passed over and counted."""
    rng = random.Random(9_000_011 * c["id"] + 5)
    every = before.surfaces()
    rng.shuffle(every)
    first = [i for i in every if i[0] == focus]
    first = first[:FOCUS - 1] + [(0, "z1")]  # and always the block's top, which most features open onto
    order = first + [i for i in every if i not in first]
    refs, skipped = [], 0
    for identity in order:
        if len(refs) == REFS:
            break
        b = before.pieces(identity)
        if b.count == 0:
            continue
        b = M.well_posed(before, identity)
        a = M.well_posed(after, identity)
        if b is None or a is None:
            skipped += 1
            continue
        piece = rng.randrange(1, b.count + 1)
        q, depth = b.interior_point(piece, rng)
        if depth < 3:                       # no point far enough from the piece's edge to pick safely
            skipped += 1
            continue
        refs.append({"identity": identity, "q": [float(x) for x in q], "n_before": b.count, "n_after": a.count,
                     "piece_at_pick_after": a.piece_at(q), "after": a})
    return refs, skipped


# ---- running one case against a system

def score(ref, status, points, after):
    """What a system's answer for one reference amounts to."""
    a, n = ref["after"], ref["n_after"]
    if status == "lost":
        return "correctly_lost" if n == 0 else ("false_loss" if n == 1 else "lost_on_split")
    pieces, wrong, unsure = set(), False, False
    for g in points:
        q = after.to_local(g)
        hits = after.attribute(q)
        if len(hits) != 1:
            unsure = True                   # off every surface, or on an edge: cannot be judged
        elif tuple(hits[0]) != tuple(ref["identity"]):
            wrong = True
        else:
            k = a.piece_at(q) if n else 0
            if k:
                pieces.add(k)
            elif n == 0:
                wrong = True                # on the right surface, where it no longer bounds the solid
            else:
                unsure = True
    if not points:
        return "unscored"
    if wrong or n == 0:
        return "silent_wrong" if status == "found" else "flagged_wrong"
    if unsure:
        return "unscored"
    if n == 1:
        return "correct" if status == "found" else "false_ambiguous"
    if status == "ambiguous":
        return "ambiguity_reported"
    if len(pieces) == n:
        return "all_pieces"
    if len(pieces) > 1:
        return "some_pieces"
    return "one_piece_at_pick" if pieces == {ref["piece_at_pick_after"]} else "one_piece_elsewhere"


def run_case(c, system):
    before, edits, focus = generate(c)
    after = before
    for e in edits:
        after = apply(after, e)
    refs, skipped = references(c, before, after, focus)
    r = {"status": "ok", "skipped": skipped, "refs": []}
    t = time.time()
    try:
        state = system.build(before.to_json())
        handles = [system.pick(state, [float(x) for x in before.to_global(ref["q"])]) for ref in refs]
        m = before
        for e in edits:
            m = apply(m, e)
            state = system.edit(state, e, m.to_json())
        answers = [system.resolve(state, h) if h is not None else None for h in handles]
    except Exception as exc:
        if not system.is_kernel_error(exc):
            raise
        r.update(status="error", err=str(exc)[:200])
        return r
    r["s"] = round(time.time() - t, 2)
    for ref, h, ans in zip(refs, handles, answers):
        row = {"identity": list(ref["identity"]), "n_before": ref["n_before"], "n_after": ref["n_after"]}
        if ans is None:
            row["outcome"] = "pick_failed"
        else:
            row["outcome"] = score(ref, ans[0], ans[1], after)
            row["returned"] = len(ans[1])
        r["refs"].append(row)
    return r
