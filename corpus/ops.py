# SPDX-License-Identifier: MIT OR Apache-2.0
"""What every kernel's corpus worker shares: how an operation is reported, and the fixed choices
(which edges, what radius, what ball) that make two kernels' runs on one model comparable."""
import hashlib
import json
import random
import sys
import time

# How many edges are each filleted on their own, chosen by a seed drawn from the model's file name.
FILLETS = 3


class KernelError(Exception):
    """The kernel declined an operation (as opposed to the worker going wrong)."""


# Python's own errors from a mistake in a worker. The kernels' bindings raise their own types.
HARNESS_ERRORS = (TypeError, NameError, AttributeError, ImportError, IndexError, KeyError, AssertionError)


class Size:
    """The fixed sizes, from the target solid's exact volume V and centroid, which any two kernels
    that read the model alike agree on (a bounding box is not: kernels pad theirs differently).
    L = V^(1/3). The ball is centred on the centroid and holds the solid's own volume, radius
    (3V/4π)^(1/3); a fillet's radius is L/100 and a shell's wall L/50."""

    def __init__(self, volume, centroid):
        import math
        length = abs(volume) ** (1 / 3)
        self.centre = tuple(centroid)
        self.ball_radius = (3 * abs(volume) / (4 * math.pi)) ** (1 / 3)
        self.fillet_radius = length / 100
        self.shell_thickness = length / 50


def pick(n, k, path):
    """k distinct indices below n, the same for the same file name on any machine."""
    import os
    seed = int(hashlib.sha256(os.path.basename(path).encode()).hexdigest()[:16], 16)
    return sorted(random.Random(seed).sample(range(n), min(k, n)))


class Run:
    def emit(self, record):
        print(json.dumps(record), flush=True)

    def op(self, name, call, describe, **extra):
        """Runs one operation and reports it: ok with what `describe` says of its result, or
        error with the kernel's words. Returns the result, or None."""
        self.emit({"start": name, **extra})
        t = time.perf_counter()
        try:
            result = call()
        except HARNESS_ERRORS as e:
            # A mistake in the worker, not the kernel's answer: reported as such, and the run stops.
            self.emit({"op": name, "status": "harness", "reason": f"{type(e).__name__}: {e}"[:300], **extra})
            raise
        except Exception as e:  # the kernel's own exceptions come in many types
            self.emit({"op": name, "status": "error", "reason": f"{type(e).__name__}: {e}"[:300],
                       "s": round(time.perf_counter() - t, 4), **extra})
            return None
        self.emit({"op": name, "status": "ok", "s": round(time.perf_counter() - t, 4),
                   **describe(result), **extra})
        return result
