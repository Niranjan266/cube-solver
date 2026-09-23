"""Turn a move list into something a person can actually follow."""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from .model import Cube
from .solver_beginner import STAGE_NAMES as _BEGINNER_STAGE_NAMES

FACE_NAME = {
    "U": "top", "D": "bottom", "L": "left",
    "R": "right", "F": "front", "B": "back",
}

# rotation axis and the slice index (0 = negative end, 2 = positive end)
FACE_AXIS: Dict[str, Tuple[str, int]] = {
    "R": ("x", 2), "L": ("x", 0),
    "U": ("y", 2), "D": ("y", 0),
    "F": ("z", 2), "B": ("z", 0),
}

# plain-language hint for a single clockwise (as-you-look-at-that-face) turn
HINT_CW = {
    "U": "the top layer spins so the front row slides to the LEFT",
    "D": "the bottom layer spins so the front row slides to the RIGHT",
    "R": "the right column rolls UP at the front",
    "L": "the left column rolls DOWN at the front",
    "F": "the front face spins like a clock hand",
    "B": "the back face spins anti-clockwise when seen from the front",
}
HINT_CCW = {
    "U": "the top layer spins so the front row slides to the RIGHT",
    "D": "the bottom layer spins so the front row slides to the LEFT",
    "R": "the right column rolls DOWN at the front",
    "L": "the left column rolls UP at the front",
    "F": "the front face spins anti-clockwise",
    "B": "the back face spins like a clock hand when seen from the front",
}

# Which way your hand actually pushes, and a matching arrow glyph.
# Written for someone holding the cube with the front face towards them.
MOTION_CW = {
    "U": ("←", "push the TOP layer LEFT"),
    "D": ("→", "push the BOTTOM layer RIGHT"),
    "R": ("↑", "push the RIGHT column UP"),
    "L": ("↓", "push the LEFT column DOWN"),
    "F": ("↻", "spin the FRONT face CLOCKWISE"),
    "B": ("↺", "spin the BACK face ANTI-CLOCKWISE (as you see it from the front)"),
}
MOTION_CCW = {
    "U": ("→", "push the TOP layer RIGHT"),
    "D": ("←", "push the BOTTOM layer LEFT"),
    "R": ("↓", "push the RIGHT column DOWN"),
    "L": ("↑", "push the LEFT column UP"),
    "F": ("↺", "spin the FRONT face ANTI-CLOCKWISE"),
    "B": ("↻", "spin the BACK face CLOCKWISE (as you see it from the front)"),
}

EXTRA_STAGE_NAMES = {
    "quick-1": "Part 1 - tidy the cube up",
    "quick-2": "Part 2 - finish it off",
}

STAGE_NAMES = {**_BEGINNER_STAGE_NAMES, **EXTRA_STAGE_NAMES}

STAGE_GOAL = {
    "quick-1": "Get every piece facing the right way. The cube will still look "
               "mixed up - that is normal, keep going.",
    "quick-2": "Slide every piece home. Watch the colours snap together.",
    "cross": "Make a plus sign of the bottom colour on the bottom face.",
    "corners": "Drop the four bottom corners into place - the whole first layer is now done.",
    "middle": "Slot the four middle-layer edges in, so two layers are finished.",
    "top-cross": "Get a plus sign of the top colour on the top face.",
    "top-corner-place": "Move the top corners to the right spots (they may still be twisted).",
    "top-corner-turn": "Twist each top corner the right way up.",
    "top-edge-place": "Slide the last four edges home. Done!",
}


def describe(move: str) -> Dict:
    """Everything the UI needs to show and speak one move."""
    face, suffix = move[0], move[1:]
    axis, layer = FACE_AXIS[face]
    name = FACE_NAME[face]

    if suffix == "2":
        angle, direction = 180, "half"
        arrow, motion = MOTION_CW[face][0], MOTION_CW[face][1] + " TWICE"
        text = f"Turn the {name.upper()} face TWICE (a half turn)."
        hint = "Either direction works for a half turn - just go round twice."
        speech = f"{name} face, half turn"
    elif suffix == "'":
        angle, direction = -90, "anticlockwise"
        arrow, motion = MOTION_CCW[face]
        text = f"Turn the {name.upper()} face 90° ANTI-CLOCKWISE (looking straight at it)."
        hint = HINT_CCW[face].capitalize() + "."
        speech = f"{name} face, anti clockwise"
    else:
        angle, direction = 90, "clockwise"
        arrow, motion = MOTION_CW[face]
        text = f"Turn the {name.upper()} face 90° CLOCKWISE (looking straight at it)."
        hint = HINT_CW[face].capitalize() + "."
        speech = f"{name} face, clockwise"

    return {
        "move": move,
        "face": face,
        "faceName": name,
        "axis": axis,
        "layer": layer,
        # signed rotation about the POSITIVE axis, for the 3D renderer.
        # A clockwise turn seen from outside is negative about +axis for the
        # far slice (layer 2) and positive for the near slice (layer 0).
        "angle": (-angle) if layer == 2 else angle,
        "turns": 2 if suffix == "2" else 1,
        "direction": direction,
        "arrow": arrow,
        "motion": motion,
        "text": text,
        "hint": hint,
        "speech": speech,
    }


def build_steps(start: Cube, tagged: Sequence[Tuple[str, str]]) -> List[Dict]:
    """One entry per move, carrying the cube state it produces."""
    c = start.copy()
    steps: List[Dict] = []
    stage_counts: Dict[str, int] = {}
    for stage in (s for _, s in tagged):
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    seen: Dict[str, int] = {}
    for n, (move, stage) in enumerate(tagged, start=1):
        c.apply(move)
        seen[stage] = seen.get(stage, 0) + 1
        step = describe(move)
        step.update(
            {
                "index": n,
                "stage": stage,
                "stageName": STAGE_NAMES.get(stage, stage),
                "stageGoal": STAGE_GOAL.get(stage, ""),
                "stageStep": seen[stage],
                "stageTotal": stage_counts[stage],
                "stateAfter": str(c),
            }
        )
        steps.append(step)
    return steps


def build_stages(tagged: Sequence[Tuple[str, str]]) -> List[Dict]:
    """Collapsed view: one entry per phase of the solve."""
    out: List[Dict] = []
    for i, (move, stage) in enumerate(tagged):
        if not out or out[-1]["key"] != stage:
            out.append(
                {
                    "key": stage,
                    "name": STAGE_NAMES.get(stage, stage),
                    "goal": STAGE_GOAL.get(stage, ""),
                    "from": i,
                    "to": i,
                    "moves": [],
                }
            )
        out[-1]["to"] = i
        out[-1]["moves"].append(move)
    return out
