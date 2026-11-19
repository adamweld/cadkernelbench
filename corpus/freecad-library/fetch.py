# SPDX-License-Identifier: MIT OR Apache-2.0
"""Fetches the parts parts.tsv includes from the FreeCAD parts library, at the pinned commit, into a
data directory outside this repository, and checks each against its git blob hash.

    python corpus/freecad-library/fetch.py [DATA]        # default ~/data/freecad-library

A partial clone (blobs fetched on demand) is made at DATA if there is none, checked out at the
commit with only the included files. Nothing is copied into this repository.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://github.com/FreeCAD/FreeCAD-library.git"


def rows():
    with open(os.path.join(HERE, "parts.tsv")) as f:
        lines = [line.rstrip("\n").split("\t") for line in f if not line.startswith("#")]
    head = lines[0]
    return [dict(zip(head, r)) for r in lines[1:]]


def glob_escape(path):
    """A path as a sparse-checkout pattern that matches it alone (gitignore syntax)."""
    out = "".join("\\" + c if c in "*?[]\\" else c for c in path)
    return "\\" + out if out[:1] in "!#" else out


def git(data, *args, **kw):
    return subprocess.run(["git", "-C", data, *args], check=True, text=True, **kw)


def main():
    data = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/data/freecad-library")
    commit = open(os.path.join(HERE, "parts.tsv")).readline().split(" at ")[1].split(".")[0]
    if not os.path.isdir(os.path.join(data, ".git")):
        subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", URL, data], check=True)
    wanted = [r for r in rows() if r["status"] == "include"]
    patterns = "".join("/" + glob_escape(r["path"]) + "\n" for r in wanted)
    git(data, "sparse-checkout", "set", "--no-cone", "--stdin", input=patterns)
    git(data, "reset", "-q", "--hard", commit)
    bad = 0
    for r in wanted:
        p = os.path.join(data, r["path"])
        h = git(data, "hash-object", "--", r["path"], capture_output=True).stdout.strip() if os.path.exists(p) else None
        if h != r["git_blob_sha1"]:
            bad += 1
            print(f"mismatch: {r['path']}", file=sys.stderr)
    print(f"{len(wanted) - bad} of {len(wanted)} parts present and matching at {data}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
