"""
Physical-validity checks for a scanned cube.

A camera scan gets colours wrong now and then, and an impossible cube would
send the solver on a wild goose chase.  These checks catch the mistake early
and say something a human can act on.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List, Tuple

from .model import (
    CENTRE,
    CORNERS,
    EDGES,
    FACE_ORDER,
    NORMAL,
    Cube,
    face_of,
)

FACE_LABEL = {
    "U": "Up", "R": "Right", "F": "Front",
    "D": "Down", "L": "Left", "B": "Back",
}

OPPOSITE = {"U": "D", "D": "U", "L": "R", "R": "L", "F": "B", "B": "F"}


class CubeError(ValueError):
    """Raised with a human-readable explanation of what is wrong with a scan."""

    def __init__(self, message: str, bad_faces: List[str] | None = None):
        super().__init__(message)
        self.message = message
        self.bad_faces = bad_faces or []


def _det(a, b, c) -> int:
    return (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )


def _corner_cycle(group: Tuple[int, ...]) -> Tuple[int, ...]:
    """Order a corner's three stickers consistently (counter-clockwise from outside)."""
    a, b, c = group
    cyc = (a, b, c)
    if _det(NORMAL[face_of(a)], NORMAL[face_of(b)], NORMAL[face_of(c)]) <= 0:
        cyc = (a, c, b)
    start = next(k for k, i in enumerate(cyc) if face_of(i) in "UD")
    return cyc[start:] + cyc[:start]


def _edge_reference(group: Tuple[int, ...]) -> int:
    """The sticker of an edge slot used to define its orientation."""
    for want in ("UD", "FB"):
        for i in group:
            if face_of(i) in want:
                return i
    return group[0]


def validate(cube: Cube) -> None:
    """Raise CubeError if `cube` is not a physically possible 3x3x3 state."""
    s = cube.s

    # 1. exactly nine of each colour ------------------------------------- #
    counts = Counter(s)
    if len(counts) != 6:
        raise CubeError(
            f"Found {len(counts)} colours instead of 6. "
            "Re-scan under steadier light, or fix the colours by hand."
        )
    bad = [c for c, n in counts.items() if n != 9]
    if bad:
        detail = ", ".join(f"{c}: {counts[c]}" for c in sorted(counts))
        raise CubeError(
            "Every colour must appear exactly 9 times. Counted " + detail + ".",
        )

    # 2. centres are the six distinct colours ----------------------------- #
    centres = {f: s[CENTRE[f]] for f in FACE_ORDER}
    if len(set(centres.values())) != 6:
        raise CubeError("Two faces have the same centre colour - re-scan.")

    to_face: Dict[str, str] = {v: k for k, v in centres.items()}

    # 3. every edge and corner is a real, unique piece -------------------- #
    seen_e = set()
    for grp in EDGES:
        piece = frozenset(to_face[s[i]] for i in grp)
        if len(piece) != 2 or OPPOSITE[list(piece)[0]] == list(piece)[1]:
            faces = sorted({face_of(i) for i in grp})
            raise CubeError(
                "An edge piece shows an impossible colour pair "
                f"({' + '.join(FACE_LABEL[f] for f in faces)} area).",
                faces,
            )
        if piece in seen_e:
            raise CubeError("The same edge piece was scanned twice - re-scan.")
        seen_e.add(piece)

    seen_c = set()
    for grp in CORNERS:
        piece = frozenset(to_face[s[i]] for i in grp)
        if len(piece) != 3 or any(OPPOSITE[a] in piece for a in piece):
            faces = sorted({face_of(i) for i in grp})
            raise CubeError(
                "A corner piece shows an impossible colour trio "
                f"({' + '.join(FACE_LABEL[f] for f in faces)} area).",
                faces,
            )
        if piece in seen_c:
            raise CubeError("The same corner piece was scanned twice - re-scan.")
        seen_c.add(piece)

    # 4. corner twist must cancel out ------------------------------------- #
    twist = 0
    for grp in CORNERS:
        cyc = _corner_cycle(grp)
        for k, i in enumerate(cyc):
            if to_face[s[i]] in "UD":
                twist += k
                break
    if twist % 3:
        raise CubeError(
            "One corner is twisted in place - that cannot happen on a real cube. "
            "A corner colour was probably misread."
        )

    # 5. edge flip must cancel out ---------------------------------------- #
    flip = 0
    for grp in EDGES:
        ref = _edge_reference(grp)
        piece_faces = [to_face[s[i]] for i in grp]
        want = next((f for f in piece_faces if f in "UD"), None)
        if want is None:
            want = next(f for f in piece_faces if f in "FB")
        if to_face[s[ref]] != want:
            flip += 1
    if flip % 2:
        raise CubeError(
            "One edge is flipped in place - that cannot happen on a real cube. "
            "An edge colour was probably misread."
        )

    # 6. permutation parity ------------------------------------------------ #
    if _parity(cube, EDGES, to_face) != _parity(cube, CORNERS, to_face):
        raise CubeError(
            "Two pieces appear to be swapped - that cannot happen on a real cube. "
            "Check the faces you scanned last."
        )


def _parity(cube: Cube, groups, to_face) -> int:
    home = {frozenset(face_of(i) for i in g): n for n, g in enumerate(groups)}
    perm = [
        home[frozenset(to_face[cube.s[i]] for i in g)] for g in groups
    ]
    seen = [False] * len(perm)
    par = 0
    for i in range(len(perm)):
        if seen[i]:
            continue
        j, size = i, 0
        while not seen[j]:
            seen[j] = True
            j = perm[j]
            size += 1
        par += size - 1
    return par % 2
