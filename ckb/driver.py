# SPDX-License-Identifier: MIT OR Apache-2.0
"""Shared worker and driver for kernel adapters.

An adapter installs its kernel functions into ckb.core (passed as m)
and then calls main(). Cases run in worker subprocesses so that a kernel
crash, hang or runaway memory use is recorded against one case and does
not stop the run.

Outcomes written per case:
    {"case": ..., "res": ...}   the case ran
    {"lost": id, "why": ...}    the worker died or stalled on it
A worker that is killed from outside (signal 9, usually for memory) has
its case retried once in a fresh process before it counts as lost. A
bug in the benchmark itself stops the whole run (exit code 3).
"""
import argparse
import json
import os
import subprocess
import sys
import time


def main(m, module, recycle=0, default_kinds="near,generic,fillet,chain", fuzzy0=False):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--stall", type=float, default=180.0, help="seconds without progress before a worker is killed")
    ap.add_argument("--kinds", default=default_kinds)
    ap.add_argument("--resume", action="store_true", help="keep existing part files and continue")
    ap.add_argument("--fuzzy0", action="store_true",
                    help="only the cases with no fuzzy tolerance; the list every kernel can run, for paired comparison")
    ap.add_argument("--summarise")
    ap.add_argument("--worker", nargs=3)
    a = ap.parse_args()
    if a.fuzzy0 or fuzzy0:
        m.FUZZY = [0.0]
    kinds = set(a.kinds.split(","))
    cases = [c for c in m.case_list() if c["kind"] in kinds]
    if a.summarise:
        m.summarise(a.summarise)
        return
    if a.worker:
        off, step, out = int(a.worker[0]), int(a.worker[1]), a.worker[2]
        done = set()
        if os.path.exists(out):
            for line in open(out):
                d = json.loads(line)
                if "begin" not in d:
                    done.add(d.get("lost", d.get("case", {}).get("id")))
        ran = 0
        with open(out, "a") as f:
            for c in cases[off::step]:
                if c["id"] in done:
                    continue
                if recycle and ran == recycle:   # start a fresh process to bound memory growth
                    sys.exit(4)
                ran += 1
                f.write(json.dumps({"begin": c["id"]}) + "\n")
                f.flush()
                try:
                    res = (m.run_fillet_case(c) if c["kind"] == "fillet" else
                           m.run_chain_case(c) if c["kind"] == "chain" else m.run_boolean_case(c))
                except Exception as e:           # a bug in the benchmark, not a kernel failure
                    f.write(json.dumps({"harness_error": c["id"], "exc": repr(e)}) + "\n")
                    f.flush()
                    sys.exit(3)
                f.write(json.dumps({"case": c, "res": res}) + "\n")
                f.flush()
        return
    parts = [f"{a.out}.part{j}" for j in range(a.jobs)]
    for p in parts:
        if os.path.exists(p) and not a.resume:
            os.remove(p)
    procs, seen, finished = [None] * a.jobs, [None] * a.jobs, [False] * a.jobs
    retried = set()
    while not all(finished):
        for j in range(a.jobs):
            if finished[j]:
                continue
            if procs[j] is None:
                procs[j] = subprocess.Popen([sys.executable, "-m", module, "--kinds", a.kinds, "--worker", str(j), str(a.jobs), parts[j]]
                                            + (["--fuzzy0"] if a.fuzzy0 else []),
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                seen[j] = (-1, time.time())
            size = os.path.getsize(parts[j]) if os.path.exists(parts[j]) else 0
            if size != seen[j][0]:
                seen[j] = (size, time.time())
            rc = procs[j].poll()
            stalled = rc is None and time.time() - seen[j][1] > a.stall
            if stalled:
                procs[j].kill()
                procs[j].wait()
            if rc == 3:
                for q in procs:
                    if q is not None and q.poll() is None:
                        q.kill()
                raise SystemExit(f"benchmark error, see {parts[j]}")
            if rc == 0:
                finished[j] = True
            elif rc == 4:
                procs[j] = None
            elif rc is not None or stalled:
                begun, closed = None, set()
                for line in open(parts[j]):
                    d = json.loads(line)
                    if "begin" in d:
                        begun = d["begin"]
                    else:
                        closed.add(d.get("lost", d.get("case", {}).get("id")))
                if rc == -9 and begun not in retried:
                    retried.add(begun)
                elif begun is not None and begun not in closed:
                    with open(parts[j], "a") as f:
                        f.write(json.dumps({"lost": begun, "why": "timeout" if stalled else f"crash rc={rc}"}) + "\n")
                procs[j] = None
        time.sleep(0.5)
    with open(a.out, "w") as o:
        for p in parts:
            for line in open(p):
                if '"begin"' not in line:
                    o.write(line)
            os.remove(p)
