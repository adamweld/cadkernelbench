# SPDX-License-Identifier: MIT OR Apache-2.0
"""Writes ATTRIBUTION.md from parts.tsv: the credit line of every part used, as CC BY 3.0 asks."""
import os
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "parts.tsv")) as f:
    first = f.readline()
    lines = [line.rstrip("\n").split("\t") for line in f]
commit = first.split(" at ")[1].split(".")[0]
head, rows = lines[0], [dict(zip(lines[0], r)) for r in lines[1:]]
used = [r for r in rows if r["status"] == "include"]
out = [
    "# Attribution: FreeCAD parts library",
    "",
    f"The parts run in this directory are from the [FreeCAD parts library](https://github.com/FreeCAD/FreeCAD-library), "
    f"at commit `{commit}`, licensed under [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) by their "
    "authors. The author of each is the person who added it to the library, as its README directs. The files are "
    "not redistributed here: `fetch.py` fetches them from the library. They are used unchanged; where a result or a "
    "case is derived from a part, it says so and credits the part as \"modified from\" it.",
    "",
    f"{len(used)} parts. Parts the library holds under other terms, or that are vendors' or third parties' models, "
    "are not used (see `status` and `reason` in `parts.tsv`).",
    "",
    "| Part | Author | Added |",
    "|---|---|---|",
]
for r in used:
    url = f"https://github.com/FreeCAD/FreeCAD-library/blob/{commit}/{quote(r['path'])}"
    name = r["path"].replace("|", "\\|")
    out.append(f"| [{name}]({url}) | {r['author'].replace('|', '/')} | {r['added_date']} |")
open(os.path.join(HERE, "ATTRIBUTION.md"), "w").write("\n".join(out) + "\n")
print(f"{len(used)} credit lines")
