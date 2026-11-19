# SPDX-License-Identifier: MIT OR Apache-2.0
"""Writes a manifest of the STEP files under a directory: one row per model, its identifier, its
file's path under the directory, its SHA-256 and its size. For a corpus that may not be
redistributed, the manifest is all of it that is ever committed.

    python corpus/manifest.py KIND DIR OUT.tsv      # KIND: abc (id = the file name's prefix) or path
"""
import hashlib
import os
import sys

corpus, root, out = sys.argv[1], os.path.expanduser(sys.argv[2]), sys.argv[3]
rows = []
for d, _, files in os.walk(root):
    for f in files:
        if f.lower().endswith((".step", ".stp")):
            p = os.path.join(d, f)
            rel = os.path.relpath(p, root)
            # An ABC model's identifier is its eight-digit directory name, its file name's prefix.
            model = f.split("_")[0] if corpus == "abc" else rel
            h = hashlib.sha256(open(p, "rb").read()).hexdigest()
            rows.append((model, rel, h, os.path.getsize(p)))
rows.sort()
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
with open(out, "w") as f:
    f.write(f"# {corpus}: {root}\n".replace(os.path.expanduser("~"), "~"))
    f.write("model\tpath\tsha256\tbytes\n")
    for r in rows:
        f.write("\t".join(map(str, r)) + "\n")
print(f"{len(rows)} models -> {out}")
