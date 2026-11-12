# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tables from a results file."""
import collections
import json

from .cases import CLASSES, CLASS_NAMES, SIZES

GROUPS = [
    ("the face is still there, in one piece", lambda r: r["n_after"] == 1,
     ["correct", "silent_wrong", "false_loss", "false_ambiguous", "flagged_wrong"]),
    ("the face is gone", lambda r: r["n_after"] == 0,
     ["correctly_lost", "silent_wrong", "flagged_wrong"]),
    ("the surface now bounds the solid in several pieces", lambda r: r["n_after"] > 1,
     ["all_pieces", "ambiguity_reported", "one_piece_at_pick", "one_piece_elsewhere", "some_pieces",
      "lost_on_split", "silent_wrong", "flagged_wrong"]),
]


def summarise(path):
    rows, cases, errors, skipped, lost = [], 0, 0, 0, 0
    for line in open(path):
        d = json.loads(line)
        if "lost" in d:
            lost += 1
            continue
        cases += 1
        skipped += d["res"].get("skipped", 0)
        if d["res"]["status"] != "ok":
            errors += 1
            continue
        for ref in d["res"]["refs"]:
            rows.append(dict(ref, cls=d["case"]["kind"], size=d["case"]["size"]))
    print(f"{cases} cases, {len(rows)} references scored or attempted; {errors} cases where the system failed to "
          f"build or rebuild, {lost} lost to a crash or timeout; {skipped} references passed over as ill-posed\n")
    other = collections.Counter(r["outcome"] for r in rows if r["outcome"] in ("unscored", "pick_failed"))
    print(f"not judged: {dict(other)}\n")
    rows = [r for r in rows if r["outcome"] not in ("unscored", "pick_failed")]
    for title, keep, cols in GROUPS:
        print(f"### Where {title}\n")
        print("| edit | features | references | " + " | ".join(c.replace("_", " ") for c in cols) + " |")
        print("|---|---|---|" + "---|" * len(cols))
        for cls in CLASSES:
            for size in SIZES:
                sub = [r for r in rows if r["cls"] == cls and r["size"] == size and keep(r)]
                if not sub:
                    continue
                n = collections.Counter(r["outcome"] for r in sub)
                assert set(n) <= set(cols), (set(n) - set(cols))
                print(f"| {cls}: {CLASS_NAMES[cls]} | {size} | {len(sub)} | " + " | ".join(str(n[c]) for c in cols) + " |")
        print()
