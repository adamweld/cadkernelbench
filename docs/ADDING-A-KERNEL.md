# Adding a kernel

An adapter is one Python module in `ckb/kernels/` that defines ten functions, installs them, and calls the shared driver. `ckb/kernels/smlib.py` is the shortest complete example; `ckb/kernels/solidcore.py` shows how to drive a kernel that has no Python interface through a small server process.

## The ten functions

| Function | Returns |
|---|---|
| `build(kind, frame, position, *dims)` | A box, cylinder, sphere, cone or torus, placed in space. `frame.R` is a rotation matrix and `frame.o` an origin: a local point `p` maps to `o + R p`. Cylinders and cones stand on their base centre along local +z; a torus lies in the local xy plane |
| `boolean(op, a, b, fuzzy)` | A dictionary with `status` (`ok`, `invalid` or `error`), `shape`, `vol` and `ms`. `op` is `fuse`, `cut` or `common`. Inputs must be left usable |
| `volume(shape)` | Volume |
| `bbox(shape)` | `(x0, y0, z0, x1, y1, z1)` |
| `valid(shape)` | The kernel's own validity check |
| `has_solid(shape)` | Whether the result is non-empty |
| `inside(shape, point)` | `True`, `False`, or `None` if the kernel cannot decide |
| `sharp_edges(shape)` | A list of `(edge, length, min_angle, max_angle)` for edges where two different faces meet at more than 5 degrees, angles in degrees between the face normals |
| `fillet(shape, edges, radius)` | `ok`, `invalid` or `error` |
| `reraise_unless_kernel(exception)` | Re-raises the exception unless the kernel raised it |

End the module with:

```python
m.install(globals())

if __name__ == "__main__":
    driver.main(m, "ckb.kernels.yourkernel", fuzzy0=True)
```

Pass `fuzzy0=True` unless the kernel's booleans accept a tolerance argument.

## Before recording any result

1. **Validate `inside`.** For a few hundred random primitives, classify sample points with the kernel and compare with the closed-form `margin` of each primitive. Skip points with `abs(margin) < m.BAND`. There must be no disagreement. Report the count with your results.
2. **Check placement** on one box: its bounding box must match another kernel's for the same case.
3. **Make `reraise_unless_kernel` strict.** If a bug in your adapter is counted as a kernel error, the failure rates are meaningless.
4. **Watch memory.** If the kernel or its binding leaks, pass `recycle=N` to `driver.main` so workers restart every N cases.

## If the kernel lacks something

- No point classification: classify against the kernel's own tessellation with a winding number, as the SMLib adapter does, and say so.
- No validity checker: use the strongest check available and say which.
- No fillets: return an empty list from `sharp_edges`; fillet cases are then skipped and reported as skipped.
