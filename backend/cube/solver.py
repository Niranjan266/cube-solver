"""
Solver front door.

Two modes:

* ``quick`` (default) - the built-in two-phase solver.  About 23 turns,
  answered in well under a second.  This is what most people want: fewer turns
  to make by hand means fewer chances to go wrong.
* ``learn`` - layer-by-layer.  Around 140 turns, but every one of them belongs
  to a stage you can name and watch complete, so you can see *why* it works.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from . import twophase
from .explain import build_stages, build_steps
from .model import CENTRE, FACE_ORDER, Cube
from .solver_beginner import SolveError, solve as solve_beginner
from .validate import CubeError, validate

QUICK_STAGES = ("quick-1", "quick-2")


def to_face_string(cube: Cube) -> str:
    """Facelet string in URFDLB face letters."""
    centres = {cube.s[CENTRE[f]]: f for f in FACE_ORDER}
    return "".join(centres[c] for c in cube.s)


def warm_up() -> None:
    """Build the two-phase tables ahead of the first request."""
    twophase.warm_up()


def solve(cube: Cube, mode: str = "quick") -> Dict:
    """Validate then solve. Returns a JSON-ready dictionary."""
    validate(cube)

    note = None
    tagged: List[Tuple[str, str]]

    if mode == "learn":
        tagged = solve_beginner(cube)
    else:
        try:
            moves, split = twophase.solve_split(cube)
            tagged = [
                (m, QUICK_STAGES[0] if i < split else QUICK_STAGES[1])
                for i, m in enumerate(moves)
            ]
        except RuntimeError as exc:
            note = (
                f"The short solver ran out of time ({exc}); "
                "here is the step-by-step method instead."
            )
            tagged = solve_beginner(cube)
            mode = "learn"

    if not cube.moved([m for m, _ in tagged]).is_solved:
        raise SolveError("internal error: produced solution does not solve the cube")

    return {
        "ok": True,
        "mode": mode if mode in ("learn", "quick") else "quick",
        "note": note,
        "moveCount": len(tagged),
        "moves": [m for m, _ in tagged],
        "notation": " ".join(m for m, _ in tagged),
        "start": str(cube),
        "steps": build_steps(cube, tagged),
        "stages": build_stages(tagged),
    }


__all__ = ["solve", "warm_up", "SolveError", "CubeError", "validate", "to_face_string"]
