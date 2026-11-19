# SPDX-License-Identifier: MIT OR Apache-2.0
"""Adapter for cadrs's kernel, cadrs_kernel.

cadrs_kernel is driven through cadrs_server, a small program over the
crate's Kernel API. Set CADRS_SERVER to the built binary.

    CADRS_SERVER=/path/to/cadrs-server \\
        python -m ckb.kernels.cadrs --out cadrs.jsonl --jobs 8

Every primitive is made in its local frame and placed by Kernel::transform
(a rigid motion). Points are classified with cadrs's own Kernel::classify;
winding_inside, the winding number about cadrs's own tessellation, is kept
for validating against it. A result is valid when cadrs's own check
(Body::check_with at CheckLevel::Full) finds no problem and the body is a
closed manifold solid; each verdict is recorded separately. Sharp edges are
judged at 10%, 50% and 90% along each edge, as for OCCT. Fillets are
Kernel::fillet: a constant-radius rolling-ball round, continued along
tangent edges as OCCT's is.

cadrs reports an empty boolean result as an error (EmptyResult). That is
an answer, not a failure: it becomes an empty solid, judged by the point
test like any other result.

Errors are kept in three kinds. cadrs refusing a call is a kernel error
(KernelError). The server rejecting a request is a bug in this benchmark
(HarnessError) and stops the run. The server process dying is a crash:
the worker dies with it, with the same exit status, so the driver records
the case as lost (and retries it once after signal 9).
"""
import json
import os
import subprocess
import time

from ckb import core as m
from ckb import driver


class KernelError(RuntimeError):
    pass


class HarnessError(Exception):
    pass


class Server:
    def __init__(self):
        self.p = None
        self.to_free = []

    def _start(self):
        log = os.environ.get("CADRS_LOG")
        err = open(log, "a") if log else subprocess.DEVNULL
        self.p = subprocess.Popen([os.environ["CADRS_SERVER"]], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=err, text=True, bufsize=1)

    def _send(self, req):
        if self.p is None:
            self._start()
        try:
            self.p.stdin.write(json.dumps(req) + "\n")
            self.p.stdin.flush()
            line = self.p.stdout.readline()
        except (BrokenPipeError, OSError):
            line = ""
        if not line:
            self._died()
        return json.loads(line)

    def _died(self):
        """The server died inside a kernel call: the case crashed. Every body it held is gone,
        so this worker cannot go on; it dies with the server's status."""
        rc = self.p.wait()
        if rc < 0:
            os.kill(os.getpid(), -rc)
            time.sleep(5)
        os._exit(rc if rc not in (0, 3, 4) else 70 + rc)

    def call(self, **req):
        if self.to_free:
            hs, self.to_free = self.to_free, []
            self._reply(self._send({"op": "free", "hs": hs}))
        return self._reply(self._send(req))

    @staticmethod
    def _reply(r):
        if "ok" in r:
            return r["ok"]
        if "kerr" in r:
            raise KernelError(r["kerr"])
        raise HarnessError(r.get("herr", r))


S = Server()


class Body:
    """A handle to a body held by the server, freed there when dropped here."""

    def __init__(self, h):
        self.h = h

    def __del__(self):
        S.to_free.append(self.h)


class _Empty:
    """The result of a boolean that cadrs reports as empty: no material anywhere."""


EMPTY = _Empty()


def build(kind, fr, p, *dims):
    # The server's placement matrix: rows 0-2 are the images of x, y and z, row 3 the
    # translation, p' = p.A + t. The image of local axis i is column i of fr.R.
    mat = [[fr.R[0][i], fr.R[1][i], fr.R[2][i], 0.0] for i in range(3)] + [[fr.o[0], fr.o[1], fr.o[2], 1.0]]
    r = S.call(op="make", kind=kind, p=[float(x) for x in p], dims=[float(d) for d in dims], m=mat)
    return Body(r["h"])


def volume(shape):
    if shape is EMPTY:
        return 0.0
    r = S.call(op="vol", h=shape.h)
    if "vol" not in r:
        raise KernelError(r["vol_err"])
    return r["vol"]


def _verdict(v):
    """The validity verdict from the server's two checks, and why it failed."""
    why = []
    if v["solid"] is False:
        why.append("not a manifold solid")
    if v["check"] is False:
        why.append("check failed " + ",".join(map(str, v["check_tests"])))
    if v["solid"] is None:
        why.append("manifold test did not run: " + v["solid_err"])
    if v["check"] is None:
        why.append("check did not run: " + v["check_err"])
    return v["solid"] is True and v["check"] is True, why


def valid(shape):
    if shape is EMPTY:
        return True
    return _verdict(S.call(op="valid", h=shape.h))[0]


def bbox(shape):
    r = S.call(op="bbox", h=shape.h)
    return (*r["lo"], *r["hi"])


def has_solid(shape):
    return shape is not EMPTY


MESH_LOG = os.environ.get("CADRS_MESHLOG")
_logged = set()


def inside(shape, g):
    """cadrs's own point classification (Kernel::classify, boundary band 1e-7 mm). None for a
    point it puts on the boundary or cannot classify (core counts those as undecided)."""
    if shape is EMPTY:
        return False
    c = S.call(op="classify", h=shape.h, pts=[list(g)])["cls"][0]
    return True if c == 1 else False if c == 0 else None


def winding_inside(shape, g):
    """Generalised winding number of g about cadrs's own tessellation of the shape (chord
    3e-3 mm, inside the 1e-2 mm band of unused points), with the SMLib and solidcore runs'
    thresholds: near 1 inside, near 0 outside, otherwise None. A mesh whose enclosed volume
    differs from the exact one by 0.1% or more answers None for every point."""
    if shape is EMPTY:
        return False
    r = S.call(op="wn", h=shape.h, pts=[list(g)])
    d = r["defects"]
    if d["volume_off"]:
        if MESH_LOG and shape.h not in _logged:
            _logged.add(shape.h)
            with open(MESH_LOG, "a") as f:
                f.write(json.dumps({"pid": os.getpid(), "h": shape.h, **d}) + "\n")
        return None
    w = abs(r["w"][0])
    return True if abs(w - 1) < 0.1 else False if w < 0.1 else None


def boolean(op, A, B, fuzzy):
    """The boolean, its volume and validity check, timed together as for OCCT."""
    t = time.perf_counter()
    out = {"status": "ok"}
    try:
        r = S.call(op="bool", kind=op, a=A.h, b=B.h)
        if r.get("empty"):
            out["shape"], out["vol"] = EMPTY, 0.0
        else:
            out["shape"] = Body(r["h"])
            if "vol" in r:
                out["vol"] = r["vol"]
            else:                        # recorded; volumes are never used to judge
                out["vol"], out["vol_err"] = float("nan"), r["vol_err"][:120]
            ok, why = _verdict(r["valid"])
            if why:
                out["why"] = why
            if not ok:
                out["status"] = "invalid"
    except KernelError as e:
        out["status"], out["exc"] = "error", str(e)[:200]
    out["ms"] = round((time.perf_counter() - t) * 1e3, 2)
    return out


def reraise_unless_kernel(e):
    if not isinstance(e, KernelError):
        raise e


def sharp_edges(shape):
    """Edges between two different faces whose outward normals differ by 5 degrees or more at
    all of 10%, 50% and 90% along the edge, as for OCCT. Elements are (edge, length, smallest
    angle, largest angle); edge is (body, edge id)."""
    if shape is EMPTY:
        return []
    r = S.call(op="edges", h=shape.h)
    return [((shape, e["i"]), e["len"], min(e["angs"]), max(e["angs"])) for e in r["edges"]
            if min(e["angs"]) >= 5.0 and e["len"] > 1e-6]


def fillet(shape, edges, radius):
    hs = {e[0][0].h for e in edges}
    if hs != {shape.h}:
        raise HarnessError("edges from another body")
    try:
        v = S.call(op="fillet", h=shape.h, edges=[e[0][1] for e in edges], r=float(radius))
    except KernelError:
        return "error"
    return "ok" if _verdict(v)[0] else "invalid"


m.install(globals())

if __name__ == "__main__":
    driver.main(m, "ckb.kernels.cadrs", fuzzy0=True)
