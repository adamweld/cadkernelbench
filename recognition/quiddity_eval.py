# SPDX-License-Identifier: MIT OR Apache-2.0
# /// script
# requires-python = ">=3.11"
# dependencies = ["cadquery-ocp==8.0.1.1.0"]
# ///
"""Generate STEP parts whose features are known, for checking a feature
recogniser such as quiddity against ground truth.

Each part is a plate with features placed on a grid so that none
overlap: through holes, blind holes, rectangular pockets and cylindrical
bosses, with the four vertical corner edges optionally rounded. The plate
is given a random orientation in space, so nothing is axis-aligned.

    python -m recognition.quiddity_eval generate <dir> [count]

writes part_NNN.step and truth.json. A research instrument.
"""
import json
import os
import random
import sys

from ckb.kernels import occt  # noqa: F401  (installs the OCCT adapter)
from ckb import core as m


def make_part(seed):
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
    rng = random.Random(7_000_003 * seed + 5)
    fr = m.Frame(rng)
    nx, ny = rng.randint(2, 4), rng.randint(2, 3)
    cell, T = 30.0, rng.uniform(8, 16)
    L = (nx * cell, ny * cell, T)
    shape = m.box(fr, (0, 0, 0), L).shape
    truth = {"through_holes": [], "blind_holes": [], "pockets": 0, "bosses": [], "corner_fillets": 0}
    for i in range(nx):
        for j in range(ny):
            cx, cy = (i + 0.5) * cell, (j + 0.5) * cell
            k = rng.choice(["through", "blind", "pocket", "boss", "none"])
            if k == "through":
                r = round(rng.uniform(2, 8), 2)
                tool, op = m.cyl(fr, (cx, cy, -5.0), r, T + 10.0), "cut"
                truth["through_holes"].append(2 * r)
            elif k == "blind":
                r = round(rng.uniform(2, 8), 2)
                d = round(rng.uniform(0.3, 0.7) * T, 2)
                tool, op = m.cyl(fr, (cx, cy, T - d), r, d + 5.0), "cut"
                truth["blind_holes"].append(2 * r)
            elif k == "pocket":
                w, h = rng.uniform(8, 18), rng.uniform(8, 18)
                d = rng.uniform(0.3, 0.7) * T
                tool, op = m.box(fr, (cx - w / 2, cy - h / 2, T - d), (w, h, d + 5.0)), "cut"
                truth["pockets"] += 1
            elif k == "boss":
                r = round(rng.uniform(3, 9), 2)
                tool, op = m.cyl(fr, (cx, cy, T), r, rng.uniform(4, 12)), "fuse"
                truth["bosses"].append(2 * r)
            else:
                continue
            x = m.boolean(op, shape, tool.shape, 0.0)
            if x["status"] != "ok":
                return None, None
            shape = x["shape"]
    if rng.random() < 0.5:          # round the plate's four vertical corner edges
        vertical = [e for e in m.sharp_edges(shape) if abs(e[1] - T) < 1e-6 and abs(e[2] - 90) < 1e-6]
        if len(vertical) == 4:
            mk = BRepFilletAPI_MakeFillet(shape)
            for e in vertical:
                mk.Add(4.0, e[0])
            mk.Build()
            if mk.IsDone() and m.valid(mk.Shape()):
                shape = mk.Shape()
                truth["corner_fillets"] = 4
    return shape, truth


def generate(out, count):
    from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
    from OCP.Interface import Interface_Static
    os.makedirs(out, exist_ok=True)
    truths = {}
    for seed in range(count):
        shape, truth = make_part(seed)
        if shape is None:
            continue
        name = f"part_{seed:03d}.step"
        w = STEPControl_Writer()
        Interface_Static.SetCVal_s("write.step.schema", "AP214")
        w.Transfer(shape, STEPControl_AsIs)
        w.Write(os.path.join(out, name))
        truths[name] = truth
    json.dump(truths, open(os.path.join(out, "truth.json"), "w"), indent=1)
    print(len(truths), "parts written")


if __name__ == "__main__":
    if sys.argv[1] == "generate":
        generate(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 60)
