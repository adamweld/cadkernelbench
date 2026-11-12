# SPDX-License-Identifier: MIT OR Apache-2.0
# /// script
# requires-python = ">=3.11"
# dependencies = ["cadquery-ocp==8.0.1.1.0", "numpy", "scipy"]
# ///
"""A reference built from the kernel's own history of each operation.

Each face of each primitive is named when it is made: (the step's uid, its
position among that primitive's faces). After every Boolean, OCCT is asked
what became of each named face (BRepAlgoAPI's Modified and IsDeleted), and
the names are carried to the faces that replaced it. A reference is a name.
It resolves to every face that carries it: none is "lost", and where a face
was divided, all of its pieces are returned.

This is not a product. It is the plainest scheme that can be built on what
OCCT reports, written to measure how far that report goes.

    python -m ckb.refsurv.systems.occt_history --out results.jsonl [--jobs 4]
    python -m ckb.refsurv.systems.occt_history --summarise results.jsonl
"""
from . import _occt
from ._occt import is_kernel_error  # noqa: F401


def build(model):
    named = []                       # (face, name) for every face of the body so far
    shape = None
    for s in model["steps"]:
        prim = _occt.primitive(model["frame"], s)
        fresh = [(f, (s["uid"], i)) for i, f in enumerate(_occt.faces(prim))]
        if s["op"] == "base":
            shape, named = prim, fresh
            continue
        op = _occt.boolean(s["op"], shape, prim)
        shape = op.Shape()
        result = {}                  # the result's faces, found by hash and then by identity
        for h in _occt.faces(shape):
            result.setdefault(hash(h), []).append(h)
        carried = []
        for f, name in named + fresh:
            after = list(op.Modified(f))
            if not after and not op.IsDeleted(f):
                after = [f]          # untouched: the same face is in the result
            for g in after:
                for h in result.get(hash(g), []):
                    if h.IsSame(g):
                        carried.append((h, name))
                        break
        named = carried
    return named


def pick(state, point):
    i = _occt.face_at([f for f, _ in state], point)
    return None if i is None else list(state[i][1])


def edit(state, e, model):
    return build(model)


def resolve(state, ref):
    found = [f for f, name in state if list(name) == list(ref)]
    if not found:
        return "lost", []
    return "found", [_occt.point_inside(f) for f in found]


if __name__ == "__main__":
    import sys
    from . import _run
    _run.main(sys.modules[__name__], "ckb.refsurv.systems.occt_history")
