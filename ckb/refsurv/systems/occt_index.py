# SPDX-License-Identifier: MIT OR Apache-2.0
# /// script
# requires-python = ">=3.11"
# dependencies = ["cadquery-ocp==8.0.1.1.0", "numpy", "scipy"]
# ///
"""Baseline: a reference is the face's position in the kernel's own list.

This is the naive scheme: "Face 7" of the solid, counted in the order OCCT's
explorer visits the faces. Nothing ties the number to the face except that
order. It is here as the floor other schemes are measured against.

    python -m ckb.refsurv.systems.occt_index --out results.jsonl [--jobs 4]
    python -m ckb.refsurv.systems.occt_index --summarise results.jsonl
"""
from . import _occt
from ._occt import is_kernel_error  # noqa: F401


def build(model):
    shape = None
    for s in model["steps"]:
        prim = _occt.primitive(model["frame"], s)
        shape = prim if s["op"] == "base" else _occt.boolean(s["op"], shape, prim).Shape()
    return _occt.faces(shape)


def pick(state, point):
    return _occt.face_at(state, point)


def edit(state, e, model):
    return build(model)


def resolve(state, ref):
    if ref >= len(state):
        return "lost", []
    return "found", [_occt.point_inside(state[ref])]


if __name__ == "__main__":
    import sys
    from . import _run
    _run.main(sys.modules[__name__], "ckb.refsurv.systems.occt_index")
