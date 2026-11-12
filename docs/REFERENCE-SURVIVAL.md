# Reference survival

A feature in a parametric model refers to geometry made by earlier features: round this edge, sketch on that face. When an earlier feature changes, the model is rebuilt and each reference has to find its geometry again. This suite measures how often it does.

For a system, a kind of upstream edit and a model size, it reports what fraction of references:

- resolve to the right face,
- are correctly reported lost,
- **silently resolve to the wrong face**, which is the outcome that matters most,
- are reported lost when the face is still there.

Results are in [RESULTS.md](RESULTS.md#reference-survival).

## Why the answers are exact

A model is a block and a list of steps. Each step cuts or adds one analytic primitive: a box, a cylinder or a sphere.

- Every face of the true solid lies on one surface of one primitive. That gives the face an identity no kernel is needed for: the step, and which of that primitive's surfaces (a box has six, a cylinder three, a sphere one).
- Whether a point is inside the true solid is a closed form: the primitives' inside tests combined in step order.
- So whether a surface bounds the solid at a point is also a closed form: the solid is on one side of the surface there and not on the other.

The code is [`ckb/refsurv/model.py`](../ckb/refsurv/model.py). It uses no kernel.

## How many pieces

A surface can bound the solid in several separate pieces, for example a top face cut in two by a slot. The number of pieces is not a closed form. It is found by sampling the surface on a grid, testing each sample as above and counting connected groups.

That count can depend on the grid where pieces are joined by a neck, or separated by a gap, narrower than the spacing. Such references are **left out, not scored**:

- The count is taken at two spacings, 0.5 and 0.3. If they differ the reference is passed over.
- A piece of fewer than 12 fine cells is treated as a sliver and the reference is passed over.
- A surface that shares its plane, cylinder or sphere with another primitive's is passed over, because a face there has no single identity.

The number passed over is reported with every result.

## A case

1. **Generate.** A block and 10, 50 or 200 features: through holes, blind holes, side holes, bosses, pockets, pads, slots and spherical cuts, placed at random. Features overlap freely. The block grows with the feature count.
2. **Refer.** Eight faces are chosen. Each is given to the system as a point well inside the face, which is how a person or an agent picks. The system returns whatever it uses as a durable reference.
3. **Edit.** One upstream change, from the classes below.
4. **Rebuild**, and **resolve** each reference. The system returns "found" with one point on each face it resolved to, or "lost", or "ambiguous" with a point on each candidate.
5. **Score.** Each returned point is attributed to its surface and piece by the closed forms, and compared with what the edit did to the referenced face.

Because a reference goes in as a point and comes back as a point, the suite never needs to understand a system's naming scheme.

Which faces are chosen: up to three on the feature the edit is about, the block's top face, and the rest at random among all faces.

## Classes of edit

| Class | Edit |
|---|---|
| A | A dimension of one feature changes by 10 to 35% |
| B | A feature is appended |
| C | A feature is moved elsewhere on the block |
| D | A slot is lengthened until it runs right through, dividing the block's top face |
| E | The reverse: a through slot is shortened, joining the two parts of the top |
| F | A feature is removed |
| G | A feature is inserted at a random earlier position |
| H | Two adjacent features that both cut, or both add, are swapped. The solid does not change |
| J | One of A, C, F or G is made and then exactly undone |

A class names the edit, not its effect. An appended hole usually leaves a referenced face alone, sometimes divides it and occasionally removes it. The effect on each reference is computed, and results are tabulated by effect.

## Outcomes

Where the face is still there in one piece:

| Outcome | Meaning |
|---|---|
| correct | Resolved to it |
| silent wrong | Resolved to a different face, with no warning |
| false loss | Reported lost |
| false ambiguous | Reported ambiguous |

Where the face is gone: **correctly lost**, or **silent wrong** if anything was returned as found.

Where the surface now bounds the solid in several pieces, each response is recorded separately and none is called right or wrong here:

| Outcome | Meaning |
|---|---|
| all pieces | Every piece returned |
| ambiguity reported | Reported ambiguous |
| one piece at pick | One piece returned: the one that contains the place originally picked |
| one piece elsewhere | One piece returned: a different one, or the picked place is no longer on the solid |
| some pieces | Several but not all |
| lost on split | Reported lost |

How these should be weighed is a judgement about what a designer wants, and is left to the reader. The several-piece group includes faces that were already in several pieces before the edit.

**Unscored** means a returned point could not be judged, because it lay on an edge or on no surface. **Pick failed** means the system found no single face under the picked point.

## Systems measured

Two are built on OCCT for this suite and are not products. The third is FreeCAD.

| System | A reference is | Why it is here |
|---|---|---|
| [`occt_index`](../ckb/refsurv/systems/occt_index.py) | The face's position in the kernel's list of faces | The floor: the scheme with no naming at all |
| [`occt_history`](../ckb/refsurv/systems/occt_history.py) | A name given to each primitive face when it is made, and carried through every Boolean by what OCCT reports became of the face | The plainest scheme that can be built on a kernel's own history. It measures how far that history goes |

| [`freecad_partdesign`](../ckb/refsurv/systems/freecad_partdesign.py) | A link from another object in the document to a face of a PartDesign body, which FreeCAD rewrites itself on every recompute | An existing product's own scheme, measured as shipped |

`occt_history` returns every face that carries the name, so on a divided face it always answers "all pieces".

### How FreeCAD is driven

FreeCAD 1.1.4, from the project's Linux AppImage, without its window.

- The model is a PartDesign body of additive and subtractive boxes, cylinders and spheres, with FreeCAD's default settings. That includes "refine", which merges faces lying on one surface after each feature.
- A reference is an `App::PropertyLinkSub` to a face of the body, on an object added to the document for the purpose. It is the property FreeCAD's own features use to refer to geometry.
- An edit is made as a user makes it: a property is changed, or a feature is added at a place in the body's tree, deleted, or moved. The document is recomputed. Unlike the two OCCT systems, the model is not rebuilt from nothing.
- The link is read back. FreeCAD has by then rewritten it to the face's new name, or marked it with "?" where it judges the face missing. The adapter reports the first as found and the second as lost. It does no naming, matching or repair of its own.

Two things about this arrangement should be kept in mind:

- The link is to the body, not to one feature in it. Inside a body, FreeCAD's own features usually refer to a face of the feature just before them. A link to the body is what an object outside the body holds, such as a part in an assembly or a drawing view, and it is the only kind that can be asked about the finished model.
- The adapter was checked for building the right solid: on sampled cases the body's volume agrees with the closed form to within sampling error, and a body after edits is identical in volume and face count to one built afresh.

## Adding a system

A system is a module with five functions:

```python
build(model)             -> state       # the model as JSON: a frame and a list of steps
pick(state, point)       -> reference   # a global point on a face; return any JSON value, or None
edit(state, edit, model) -> state       # the edit, and the whole model after it
resolve(state, ref)      -> (status, points)   # "found" | "lost" | "ambiguous", one point per face
is_kernel_error(exc)     -> bool        # the system's own failures, as against bugs in the adapter
```

An edit is one of `{"op": "set", "uid", "values"}`, `{"op": "insert", "index", "step"}`, `{"op": "remove", "uid"}` and `{"op": "swap", "index"}`. Every step has a `uid` that never changes, so a system that names by feature can follow a feature through an edit. A system with no memory can ignore the edit and rebuild from the model.

End the module as the two existing ones do, and it runs under the same isolating driver as the kernel benchmarks.

## Running

```bash
.venv-occt/bin/python -m ckb.refsurv.systems.occt_history --out refsurv_history.jsonl --jobs 4
```

```bash
.venv-occt/bin/python -m ckb.refsurv.systems.occt_history --summarise refsurv_history.jsonl
```

FreeCAD runs under the Python inside its own AppImage, unpacked with `--appimage-extract`:

```bash
squashfs-root/usr/bin/python -m ckb.refsurv.systems.freecad_partdesign --out refsurv_freecad.jsonl --jobs 4
```

The environment is the OCCT one from [RUNNING.md](RUNNING.md), which already has numpy and scipy. The 200-feature cases take about two minutes each for the OCCT systems and about 25 minutes each for FreeCAD, so give FreeCAD a long `--stall`.

## What this does not measure

- **Edges and vertices.** Only faces are referenced. An edge has the identity of the two surfaces it separates and can be added the same way.
- **Coincident faces.** A boss standing exactly on a face, which real models are full of, gives the face there two possible identities and needs a rule this version does not have. Features are placed and sized at random so that it does not arise, and any surface that shares a plane, cylinder or sphere with another is passed over.
- **Fillets, sketches and freeform surfaces.** A fillet face could take the identity of the edge it replaced, and an extruded face that of its sketch curve. Lofts and sweeps have no closed-form origin.
- **Patterns.** Changing the count of a pattern is not among the edits.
- **Real engineering models.** Generated models are not designed. The suite can show that a scheme fails on generated models of realistic depth. It cannot show that a scheme works on real ones.
- **Intent.** A reference can resolve to the geometrically correct face and still not be the one the designer would have wanted after a large redesign.
- **Any commercial CAD product, or SolidCraft.** SolidCraft has a naming scheme this suite was designed to measure and has not been run. FreeCAD is measured through its Part Design primitives only, not through sketches, pads and pockets, which is how most FreeCAD models are made.

## Known limits of the method

- The piece that "contains the place originally picked" is a rule chosen for being objective. It is not the only reasonable one. A rule based on which neighbouring faces bound a piece was proposed first and has not been built.
- Model sizes above 200 features have not been tried.
- Pieces are counted on a sampling grid. Two parts of a face joined by a neck narrower than the grid are counted as two pieces, and a sliver smaller than the grid is not counted at all. In the first full run this misjudged 5 references of 7,920 as "not all pieces" and left 19 unscored. Both show up against a system that is otherwise exact, and are small beside any real effect.
- The method takes the solid a system builds to be the solid modelled. It does not check. Where a system builds a wrong solid without reporting an error, the picks fail and the case shows up as "pick failed". That happened once for OCCT and once for FreeCAD in the first run.
- The FreeCAD link is held by a scripted object, not by one of FreeCAD's built-in features. Both use the same link property, but a built-in feature may treat a stale link differently.
- The two OCCT systems rebuild the model from nothing after an edit, so class J cannot fail for them unless the kernel is not repeatable. FreeCAD keeps its document between rebuilds, and class J is a real test of it.
