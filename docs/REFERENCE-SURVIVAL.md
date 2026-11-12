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

Both are built on OCCT for this suite. Neither is a product.

| System | A reference is | Why it is here |
|---|---|---|
| [`occt_index`](../ckb/refsurv/systems/occt_index.py) | The face's position in the kernel's list of faces | The floor: the scheme with no naming at all |
| [`occt_history`](../ckb/refsurv/systems/occt_history.py) | A name given to each primitive face when it is made, and carried through every Boolean by what OCCT reports became of the face | The plainest scheme that can be built on a kernel's own history. It measures how far that history goes |

`occt_history` returns every face that carries the name, so on a divided face it always answers "all pieces".

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

The environment is the OCCT one from [RUNNING.md](RUNNING.md), which already has numpy and scipy. The 200-feature cases take about two minutes each.

## What this does not measure

- **Edges and vertices.** Only faces are referenced. An edge has the identity of the two surfaces it separates and can be added the same way.
- **Coincident faces.** Features are placed at random, so no two primitive surfaces coincide. A boss standing exactly on a face, which real models are full of, gives a face two possible identities and needs a rule this version does not have.
- **Fillets, sketches and freeform surfaces.** A fillet face could take the identity of the edge it replaced, and an extruded face that of its sketch curve. Lofts and sweeps have no closed-form origin.
- **Patterns.** Changing the count of a pattern is not among the edits.
- **Real engineering models.** Generated models are not designed. The suite can show that a scheme fails on generated models of realistic depth. It cannot show that a scheme works on real ones.
- **Intent.** A reference can resolve to the geometrically correct face and still not be the one the designer would have wanted after a large redesign.
- **Any existing CAD product.** FreeCAD and SolidCraft both have naming schemes and are the systems this suite was designed to measure. Neither has been run.

## Known limits of the method

- The piece that "contains the place originally picked" is a rule chosen for being objective. It is not the only reasonable one. A rule based on which neighbouring faces bound a piece was proposed first and has not been built.
- Model sizes above 200 features have not been tried.
- The two systems rebuild the model from nothing after an edit. A system that keeps state between rebuilds, as a CAD application does, is exercised differently by class J.
