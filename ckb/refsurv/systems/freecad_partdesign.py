# SPDX-License-Identifier: MIT OR Apache-2.0
"""FreeCAD's own references, in a PartDesign body.

The model is a PartDesign body of additive and subtractive primitives. A
reference is a link to a face of the body (an App::PropertyLinkSub, the
property FreeCAD's own features use to refer to geometry), held by a
separate object in the document. An edit is made the way a user makes it:
a property is changed, a feature is added at a place in the body's tree,
removed, or moved. The document is then recomputed and the link is read
back. FreeCAD rewrites the link itself: to the face's new name, or to a
name marked with "?" when it judges the face gone. Nothing here names,
matches or repairs anything.

Run it with the Python that ships inside FreeCAD, which has numpy and scipy:

    <FreeCAD>/usr/bin/python -m ckb.refsurv.systems.freecad_partdesign --out results.jsonl [--jobs 4]
    <FreeCAD>/usr/bin/python -m ckb.refsurv.systems.freecad_partdesign --summarise results.jsonl

Measured with FreeCAD 1.1.4. See docs/REFERENCE-SURVIVAL.md for what the
arrangement does and does not represent.
"""
import os
import random
import sys

sys.path.append(os.path.join(os.path.dirname(sys.executable), "..", "lib"))


class FreeCADDeclined(Exception):
    """FreeCAD could not build or rebuild the model."""


def is_kernel_error(exc):
    return isinstance(exc, FreeCADDeclined) or type(exc).__module__.startswith(("FreeCAD", "Part", "Base", "OCC"))


TYPES = {("base", "box"): "AdditiveBox", ("fuse", "box"): "AdditiveBox", ("fuse", "cyl"): "AdditiveCylinder",
         ("fuse", "sph"): "AdditiveSphere", ("cut", "box"): "SubtractiveBox", ("cut", "cyl"): "SubtractiveCylinder",
         ("cut", "sph"): "SubtractiveSphere"}


def _configure(obj, frame, s):
    """Size and place one primitive from its step."""
    import FreeCAD as App
    R, o = frame["R"], frame["o"]
    a = s["ax"] if s["kind"] == "cyl" else 2          # the primitive's own z axis, in the model's frame
    cols = [(a + 1) % 3, (a + 2) % 3, a]
    m = App.Matrix()
    for i in range(3):
        for j in range(3):
            setattr(m, f"A{i + 1}{j + 1}", R[i][cols[j]])
    base = App.Vector(*[o[i] + sum(R[i][j] * s["p"][j] for j in range(3)) for i in range(3)])
    obj.Placement = App.Placement(base, App.Rotation(m))
    if s["kind"] == "box":
        obj.Length, obj.Width, obj.Height = s["d"]
    elif s["kind"] == "cyl":
        obj.Radius, obj.Height = s["r"], s["h"]
    else:
        obj.Radius = s["r"]


def _recompute(state):
    doc, body = state["doc"], state["body"]
    doc.recompute()
    bad = [o.Name for o in body.Group if "Invalid" in o.State or "Touched" in o.State]
    if bad or body.Shape.isNull() or not body.Shape.Faces:
        raise FreeCADDeclined(f"recompute left {len(bad)} features in error")


def _add(state, frame, s):
    obj = state["body"].newObject("PartDesign::" + TYPES[(s["op"], s["kind"])], f"S{s['uid']}")
    _configure(obj, frame, s)
    state["feature"][s["uid"]] = obj
    return obj


def build(model):
    import FreeCAD as App
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    doc = App.newDocument("case")
    state = {"doc": doc, "body": doc.addObject("PartDesign::Body", "Body"), "feature": {}, "order": [], "refs": 0}
    for s in model["steps"]:
        _add(state, model["frame"], s)
        state["order"].append(s["uid"])
    _recompute(state)
    return state


def pick(state, point):
    import FreeCAD as App
    import Part
    body, v = state["body"], Part.Vertex(App.Vector(*point))
    found = []
    for i, f in enumerate(body.Shape.Faces, 1):
        box = f.BoundBox
        box.enlarge(1e-3)
        if box.isInside(App.Vector(*point)) and f.distToShape(v)[0] < 1e-6:
            found.append(i)
    if len(found) != 1:
        return None
    holder = state["doc"].addObject("App::FeaturePython", f"Ref{state['refs']}")
    state["refs"] += 1
    holder.addProperty("App::PropertyLinkSub", "Ref")
    holder.Ref = (body, [f"Face{found[0]}"])
    return holder.Name


def edit(state, e, model):
    body, feature, order = state["body"], state["feature"], state["order"]
    by_uid = {s["uid"]: s for s in model["steps"]}
    if e["op"] == "set":
        _configure(feature[e["uid"]], model["frame"], by_uid[e["uid"]])
    elif e["op"] == "insert":
        last = body.Tip
        body.Tip = feature[order[e["index"] - 1]]     # a new feature goes in after the tip
        _add(state, model["frame"], e["step"])
        order.insert(e["index"], e["step"]["uid"])
        body.Tip = feature[order[-1]] if e["index"] < len(order) - 1 else body.Tip
        del last
    elif e["op"] == "remove":
        obj = feature.pop(e["uid"])
        order.remove(e["uid"])
        body.removeObject(obj)
        state["doc"].removeObject(obj.Name)
        body.Tip = feature[order[-1]]
    elif e["op"] == "swap":
        i = e["index"]
        obj, after = feature[order[i]], feature[order[i + 1]]
        body.removeObject(obj)
        body.insertObject(obj, after, True)
        order[i], order[i + 1] = order[i + 1], order[i]
        body.Tip = feature[order[-1]]
    if order != [s["uid"] for s in model["steps"]]:
        raise RuntimeError("the adapter's feature order has parted from the model's")
    _recompute(state)
    return state


def resolve(state, ref):
    holder = state["doc"].getObject(ref)
    link = holder.Ref
    names = list(link[1]) if link and link[0] is not None else []
    if not names or any(n.startswith("?") or not n for n in names):
        return "lost", []
    shape, points = state["body"].Shape, []
    for n in names:
        try:
            face = shape.getElement(n)
        except Exception:
            return "lost", []
        points.append(_point_inside(face))
    return "found", points


def _point_inside(face):
    """A global point on the face and away from its edges."""
    u0, u1, v0, v1 = face.ParameterRange
    rng = random.Random(1)
    du, dv = (u1 - u0) * 0.02, (v1 - v0) * 0.02
    fallback = None
    for k in range(400):
        u, v = ((u0 + u1) / 2, (v0 + v1) / 2) if k == 0 else (rng.uniform(u0, u1), rng.uniform(v0, v1))
        if not face.isPartOfDomain(u, v):
            continue
        p = face.valueAt(u, v)
        if all(face.isPartOfDomain(u + a, v + b) for a, b in ((du, 0), (-du, 0), (0, dv), (0, -dv))):
            return [p.x, p.y, p.z]
        fallback = fallback or [p.x, p.y, p.z]
    return fallback


if __name__ == "__main__":
    from . import _run
    _run.main(sys.modules[__name__], "ckb.refsurv.systems.freecad_partdesign")
