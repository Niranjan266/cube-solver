"""
Cubie-level cube representation (corner/edge permutation + orientation).

The facelet model in :mod:`cube.model` is what the camera and the 3D view speak.
The two-phase solver needs the other view: which piece is where, and which way
up.  Everything here is *derived* from the facelet geometry, so the two models
cannot drift apart.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from .model import Cube, _slot, face_of

# Standard piece ordering.  The first face of each tuple carries the
# orientation reference (the U/D sticker for corners and for the eight
# non-slice edges).
CORNER_FACES: Tuple[Tuple[str, str, str], ...] = (
    ("U", "R", "F"), ("U", "F", "L"), ("U", "L", "B"), ("U", "B", "R"),
    ("D", "F", "R"), ("D", "L", "F"), ("D", "B", "L"), ("D", "R", "B"),
)
CORNER_NAMES = ("URF", "UFL", "ULB", "UBR", "DFR", "DLF", "DBL", "DRB")

EDGE_FACES: Tuple[Tuple[str, str], ...] = (
    ("U", "R"), ("U", "F"), ("U", "L"), ("U", "B"),
    ("D", "R"), ("D", "F"), ("D", "L"), ("D", "B"),
    ("F", "R"), ("F", "L"), ("B", "L"), ("B", "R"),
)
EDGE_NAMES = ("UR", "UF", "UL", "UB", "DR", "DF", "DL", "DB",
              "FR", "FL", "BL", "BR")

#: facelet indices of each corner slot, in the CORNER_FACES order
CORNER_IDX: Tuple[Tuple[int, int, int], ...] = tuple(
    tuple(_slot(*faces)[f] for f in faces) for faces in CORNER_FACES
)
#: facelet indices of each edge slot, in the EDGE_FACES order
EDGE_IDX: Tuple[Tuple[int, int], ...] = tuple(
    tuple(_slot(*faces)[f] for f in faces) for faces in EDGE_FACES
)

_CORNER_LOOKUP = {frozenset(f): i for i, f in enumerate(CORNER_FACES)}
_EDGE_LOOKUP = {frozenset(f): i for i, f in enumerate(EDGE_FACES)}


class CubieCube:
    """cp/co/ep/eo, the classic representation."""

    __slots__ = ("cp", "co", "ep", "eo")

    def __init__(self, cp=None, co=None, ep=None, eo=None):
        self.cp: List[int] = list(cp) if cp is not None else list(range(8))
        self.co: List[int] = list(co) if co is not None else [0] * 8
        self.ep: List[int] = list(ep) if ep is not None else list(range(12))
        self.eo: List[int] = list(eo) if eo is not None else [0] * 12

    # -- conversions -------------------------------------------------------- #
    @classmethod
    def from_facelets(cls, cube: Cube) -> "CubieCube":
        """Read a cube state into cubie form (colours are matched to centres)."""
        centres = {cube.s[i * 9 + 4]: f for i, f in enumerate("URFDLB")}
        col = lambda i: centres[cube.s[i]]  # noqa: E731

        cp, co = [0] * 8, [0] * 8
        for slot, idx in enumerate(CORNER_IDX):
            faces = [col(i) for i in idx]
            piece = _CORNER_LOOKUP[frozenset(faces)]
            cp[slot] = piece
            # how far round is the U/D sticker from the slot's reference facelet
            for turn in range(3):
                if faces[turn] in "UD":
                    co[slot] = turn
                    break

        ep, eo = [0] * 12, [0] * 12
        for slot, idx in enumerate(EDGE_IDX):
            faces = [col(i) for i in idx]
            piece = _EDGE_LOOKUP[frozenset(faces)]
            ep[slot] = piece
            eo[slot] = 0 if faces[0] == EDGE_FACES[piece][0] else 1
        return cls(cp, co, ep, eo)

    def to_facelets(self) -> Cube:
        s = ["?"] * 54
        for i, f in enumerate("URFDLB"):
            s[i * 9 + 4] = f
        for slot, idx in enumerate(CORNER_IDX):
            piece, ori = self.cp[slot], self.co[slot]
            for k in range(3):
                s[idx[(k + ori) % 3]] = CORNER_FACES[piece][k]
        for slot, idx in enumerate(EDGE_IDX):
            piece, ori = self.ep[slot], self.eo[slot]
            for k in range(2):
                s[idx[(k + ori) % 2]] = EDGE_FACES[piece][k]
        return Cube("".join(s))

    # -- group operations --------------------------------------------------- #
    def multiply(self, other: "CubieCube") -> "CubieCube":
        """Return self followed by other."""
        cp = [self.cp[other.cp[i]] for i in range(8)]
        co = [(self.co[other.cp[i]] + other.co[i]) % 3 for i in range(8)]
        ep = [self.ep[other.ep[i]] for i in range(12)]
        eo = [(self.eo[other.ep[i]] + other.eo[i]) % 2 for i in range(12)]
        return CubieCube(cp, co, ep, eo)

    def copy(self) -> "CubieCube":
        return CubieCube(self.cp, self.co, self.ep, self.eo)

    def is_solved(self) -> bool:
        return (self.cp == list(range(8)) and self.co == [0] * 8
                and self.ep == list(range(12)) and self.eo == [0] * 12)

    def __eq__(self, other) -> bool:
        return (isinstance(other, CubieCube) and self.cp == other.cp
                and self.co == other.co and self.ep == other.ep
                and self.eo == other.eo)


def _build_move_cubes():
    out = {}
    for m in ("U", "R", "F", "D", "L", "B"):
        out[m] = CubieCube.from_facelets(Cube().apply(m))
    return out


#: quarter-turn cubie cubes for the six faces
MOVE_CUBE = _build_move_cubes()

#: the eighteen half-turn-metric moves, in a fixed order
MOVE_NAMES: Tuple[str, ...] = tuple(
    f + s for f in "URFDLB" for s in ("", "2", "'")
)


def _power(cube: CubieCube, n: int) -> CubieCube:
    out = CubieCube()
    for _ in range(n):
        out = out.multiply(cube)
    return out


MOVE_CUBES: Tuple[CubieCube, ...] = tuple(
    _power(MOVE_CUBE[name[0]], {"": 1, "2": 2, "'": 3}[name[1:]])
    for name in MOVE_NAMES
)

MOVE_INDEX = {name: i for i, name in enumerate(MOVE_NAMES)}


def apply_moves(cube: CubieCube, moves: Sequence[str]) -> CubieCube:
    for m in moves:
        cube = cube.multiply(MOVE_CUBES[MOVE_INDEX[m]])
    return cube
