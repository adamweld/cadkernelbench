# SPDX-License-Identifier: MIT OR Apache-2.0
"""Runs a kernel's corpus worker over every model a manifest lists, one process per model.

    python corpus/run.py --kernel occt --manifest M.tsv --data DIR --out RESULTS/occt.jsonl.gz
                         [--jobs 8] [--timeout 120] [--limit N]

The manifest (corpus/manifest.py) names each model and its file's path under DIR. The files are read
where they are and copied nowhere. The output has one line per model: its id and what each operation
reported. A run picks up where an earlier one stopped.
A worker that dies is a crash and one that runs past --timeout a timeout, both pinned to the operation
that had started and not finished.
"""
import argparse
import concurrent.futures as cf
import gzip
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

WORKERS = {
    "occt": lambda: [os.environ.get("OCCT_PYTHON", os.path.join(HERE, "..", ".venv-occt", "bin", "python")),
                     os.path.join(HERE, "occt_worker.py")],
    "cadrs": lambda: [os.environ.get("CADRS_CORPUS", os.path.join(HERE, "cadrs_worker", "target", "release",
                                                                   "cadrs-corpus"))],
}


def models(manifest, data):
    """(id, path) of each model the manifest lists, in order."""
    with open(manifest) as f:
        rows = [line.rstrip("\n").split("\t") for line in f if not line.startswith("#")]
    return [(r[0], os.path.join(data, r[1])) for r in rows[1:]]


def run_one(cmd, model, path, timeout):
    t = time.perf_counter()
    try:
        p = subprocess.run(cmd + [path], capture_output=True, text=True, timeout=timeout)
        out, outcome, code = p.stdout, ("done" if p.returncode == 0 else "crash"), p.returncode
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        outcome, code = "timeout", None
    ops, started = [], None
    for line in out.splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if "start" in r:
            started = r
        elif "op" in r:
            ops.append(r)
            started = None
    record = {"model": model, "outcome": outcome, "s": round(time.perf_counter() - t, 3), "ops": ops}
    if outcome != "done":
        record["in_op"] = started["start"] if started else None
        record["exit"] = code
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kernel", required=True, choices=sorted(WORKERS))
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    out = a.out
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    done = set()
    if os.path.exists(out):
        with gzip.open(out, "rt") as f:
            done = {json.loads(line)["model"] for line in f if line.strip()}
    todo = [(m, p) for m, p in models(a.manifest, os.path.expanduser(a.data)) if m not in done][: a.limit]
    print(f"{a.kernel} {os.path.basename(a.manifest)}: {len(done)} done, {len(todo)} to run", file=sys.stderr)
    cmd = WORKERS[a.kernel]()
    counts = {}
    with gzip.open(out, "at") as f, cf.ThreadPoolExecutor(a.jobs) as pool:
        futures = [pool.submit(run_one, cmd, m, p, a.timeout) for m, p in todo]
        for i, fut in enumerate(cf.as_completed(futures), 1):
            r = fut.result()
            f.write(json.dumps(r) + "\n")
            counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
            if i % 200 == 0:
                f.flush()
                print(f"  {i}/{len(todo)} {counts}", file=sys.stderr)
    print(f"{a.kernel} {os.path.basename(a.manifest)}: {counts}", file=sys.stderr)


if __name__ == "__main__":
    main()
