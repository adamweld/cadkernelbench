# SPDX-License-Identifier: MIT OR Apache-2.0
"""Adapter for solidcore.

NOT YET RUN. The server it drives (solidcore_server/) could not be
compiled in the session that wrote this, for lack of memory, so this
adapter is untested. Expect to fix small things on first use.

solidcore is driven through solidcore_server, a small program over its
solidcore-ops crate. Set SOLIDCORE_SERVER to the built binary.

What is covered: booleans (near-degenerate, generic) and feature
sequences, checked with solidcore's own point classification and its
validity check. Fillets are not wired up: solidcore's blend call takes a
richer description than one radius per edge, and that mapping has not
been written. The final fillet of each feature sequence is skipped.

    SOLIDCORE_SERVER=/path/to/solidcore-server \\
        python -m ckb.kernels.solidcore --out solidcore.jsonl --jobs 4
"""
import json
import os
import subprocess
import time

from ckb import core as m
from ckb import driver


class KernelError(RuntimeError):
    pass


class Server:
    def __init__(self):
        self.p = None

    def call(self, **req):
        if self.p is None or self.p.poll() is not None:
            self.p = subprocess.Popen([os.environ["SOLIDCORE_SERVER"]], stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, text=True, bufsize=1)
        try:
            self.p.stdin.write(json.dumps(req) + "\n")
            self.p.stdin.flush()
            line = self.p.stdout.readline()
        except (BrokenPipeError, OSError):
            line = ""
        if not line:                      # the server died: that is a kernel crash
            rc = self.p.poll()
            self.p = None
            raise KernelError(f"server exited rc={rc}")
        return json.loads(line)


S = Server()


class Body:
    """A handle to a body held by the server."""

    def __init__(self, h):
        self.h = h


def build(kind, fr, p, *dims):
    # Rows 0-2 are the images of x, y, z; row 3 is the translation; p' = p.A + t.
    mat = [[fr.R[0][i], fr.R[1][i], fr.R[2][i], 0.0] for i in range(3)] + [[fr.o[0], fr.o[1], fr.o[2], 1.0]]
    r = S.call(op="make", kind=kind, p=[float(x) for x in p], dims=[float(d) for d in dims], m=mat)
    if "h" not in r:
        raise KernelError(r.get("err", "make failed"))
    return Body(r["h"])


def volume(shape):
    if shape is None:
        return 0.0
    r = S.call(op="vol", h=shape.h)
    if "vol" not in r:
        raise KernelError(r.get("err"))
    return r["vol"]


def valid(shape):
    return shape is None or bool(S.call(op="valid", h=shape.h).get("valid"))


def bbox(shape):
    r = S.call(op="bbox", h=shape.h)
    if "lo" not in r:
        raise KernelError(r.get("err"))
    return (*r["lo"], *r["hi"])


def has_solid(shape):
    return shape is not None


def inside(shape, g):
    c = S.call(op="classify", h=shape.h, pts=[list(g)]).get("cls", [-2])[0]
    return True if c == 1 else False if c == 0 else None


def boolean(op, A, B, fuzzy):
    t = time.perf_counter()
    out = {"status": "ok"}
    try:
        r = S.call(op="bool", kind=op, a=A.h, b=B.h)
        if r.get("status") == "empty":
            out["shape"], out["vol"] = None, 0.0
        elif r.get("status") == "ok":
            out["shape"], out["vol"] = Body(r["h"]), r["vol"]
            if not valid(out["shape"]):
                out["status"] = "invalid"
        else:
            out["status"], out["exc"] = "error", str(r.get("err"))[:120]
    except KernelError as e:
        out["status"], out["exc"] = "error", str(e)[:120]
    out["ms"] = round((time.perf_counter() - t) * 1e3, 2)
    return out


def reraise_unless_kernel(e):
    if not isinstance(e, KernelError):
        raise e


def sharp_edges(shape):
    return []          # fillets are not wired up; see the module docstring


def fillet(shape, edges, radius):
    return "skipped"


m.install(globals())

if __name__ == "__main__":
    driver.main(m, "ckb.kernels.solidcore", default_kinds="near,generic,chain", fuzzy0=True)
