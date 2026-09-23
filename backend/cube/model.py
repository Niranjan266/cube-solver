"""
Geometric 3x3x3 Rubik's Cube model.

Every move permutation is *derived from 3D geometry* rather than hand-typed
tables, which removes the usual source of bugs in cube programs.

Facelet layout (Kociemba standard, 54 chars, order U R F D L B):

                 |U0 U1 U2|
                 |U3 U4 U5|
                 |U6 U7 U8|
     |L0 L1 L2|  |F0 F1 F2|  |R0 R1 R2|  |B0 B1 B2|
     |L3 L4 L5|  |F3 F4 F5|  |R3 R4 R5|  |B3 B4 B5|
     |L6 L7 L8|  |F6 F7 F8|  |R6 R7 R8|  |B6 B7 B8|
                 |D0 D1 D2|
                 |D3 D4 D5|
                 |D6 D7 D8|

Coordinate frame: +x = right, +y = up, +z = front (towards the viewer).
"""

from __future__ import annotations

import random
from typing import Dict, List, Sequence, Tuple

FACE_ORDER = "URFDLB"

# outward normal of each face
NORMAL: Dict[str, Tuple[int, int, int]] = {
    "U": (0, 1, 0),
    "R": (1, 0, 0),
    "F": (0, 0, 1),
    "D": (0, -1, 0),
    "L": (-1, 0, 0),
    "B": (0, 0, -1),
}

# (column-direction, row-direction) for each face, looking at it from outside
AXES: Dict[str, Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = {
    "U": ((1, 0, 0), (0, 0, 1)),    # cols left->right, rows back->front
    "R": ((0, 0, -1), (0, -1, 0)),  # cols front->back, rows top->bottom
    "F": ((1, 0, 0), (0, -1, 0)),
    "D": ((1, 0, 0), (0, 0, -1)),   # cols left->right, rows front->back
    "L": ((0, 0, 1), (0, -1, 0)),   # cols back->front
    "B": ((-1, 0, 0), (0, -1, 0)),  # cols right->left
}

MOVE_FACES = "URFDLB"


def _build_stickers() -> List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]]:
    """index -> (position, outward normal). Coordinates scaled by 2 to stay integral."""
    out = []
    for f in FACE_ORDER:
        n = NORMAL[f]
        u, v = AXES[f]
        for row in range(3):
            for col in range(3):
                pos = tuple(
                    n[i] * 3 + u[i] * (col - 1) * 2 + v[i] * (row - 1) * 2
                    for i in range(3)
                )
                out.append((pos, n))
    return out


STICKERS = _build_stickers()
POS_INDEX = {(p, n): i for i, (p, n) in enumerate(STICKERS)}


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _rot_cw(vec, axis):
    """Rotate `vec` by -90 degrees about `axis` (i.e. clockwise seen from +axis)."""
    d = _dot(axis, vec)
    c = _cross(axis, vec)
    return (
        axis[0] * d - c[0],
        axis[1] * d - c[1],
        axis[2] * d - c[2],
    )


def _build_move(face: str) -> List[int]:
    """perm[i] = index the sticker currently at i moves TO."""
    axis = NORMAL[face]
    perm = list(range(54))
    for i, (pos, nor) in enumerate(STICKERS):
        if _dot(pos, axis) > 1:  # this sticker belongs to the turning layer
            perm[i] = POS_INDEX[(_rot_cw(pos, axis), _rot_cw(nor, axis))]
    return perm


BASE_MOVES: Dict[str, List[int]] = {f: _build_move(f) for f in MOVE_FACES}


def _compose(p: Sequence[int], q: Sequence[int]) -> List[int]:
    """Apply p then q."""
    return [q[p[i]] for i in range(54)]


def _identity() -> List[int]:
    return list(range(54))


MOVE_PERMS: Dict[str, List[int]] = {}
for _f in MOVE_FACES:
    _p = BASE_MOVES[_f]
    MOVE_PERMS[_f] = _p
    MOVE_PERMS[_f + "2"] = _compose(_p, _p)
    MOVE_PERMS[_f + "'"] = _compose(_compose(_p, _p), _p)

ALL_MOVES: List[str] = [f + s for f in MOVE_FACES for s in ("", "'", "2")]

SOLVED = "".join(FACE_ORDER[i // 9] for i in range(54))


# --------------------------------------------------------------------------- #
# Cubie tables (derived from the same geometry)
# --------------------------------------------------------------------------- #

def _sign(v):
    return (v > 0) - (v < 0)


def _cubie_key(i: int) -> Tuple[int, int, int]:
    return tuple(_sign(c) for c in STICKERS[i][0])


_CUBIES: Dict[Tuple[int, int, int], List[int]] = {}
for _i in range(54):
    _CUBIES.setdefault(_cubie_key(_i), []).append(_i)

#: list of (idx_a, idx_b) sticker pairs, one per edge cubie (12 of them)
EDGES: List[Tuple[int, ...]] = sorted(
    tuple(v) for v in _CUBIES.values() if len(v) == 2
)
#: list of (idx_a, idx_b, idx_c) sticker triples, one per corner cubie (8)
CORNERS: List[Tuple[int, ...]] = sorted(
    tuple(v) for v in _CUBIES.values() if len(v) == 3
)
#: face letter -> centre sticker index
CENTRE = {f: FACE_ORDER.index(f) * 9 + 4 for f in FACE_ORDER}


def face_of(index: int) -> str:
    """Which face a sticker index lives on."""
    return FACE_ORDER[index // 9]


def _slot(*faces: str) -> Dict[str, int]:
    key = tuple(
        _sign(sum(NORMAL[f][i] for f in faces)) for i in range(3)
    )
    return {face_of(i): i for i in _CUBIES[key]}


def edge_pos(on: str, other: str) -> int:
    """Sticker index lying on face `on`, belonging to the `on`/`other` edge cubie."""
    return _slot(on, other)[on]


def corner_pos(on: str, o1: str, o2: str) -> int:
    """Sticker index lying on face `on`, belonging to the `on`/`o1`/`o2` corner."""
    return _slot(on, o1, o2)[on]


#: side faces in clockwise order when looking down at U
SIDES = ("F", "R", "B", "L")


def right_of(side: str) -> str:
    return SIDES[(SIDES.index(side) + 1) % 4]


def left_of(side: str) -> str:
    return SIDES[(SIDES.index(side) - 1) % 4]


class Cube:
    """A cube state: 54 colour labels (any hashable, usually face letters)."""

    __slots__ = ("s",)

    def __init__(self, state: str | Sequence[str] | None = None):
        self.s: List[str] = list(state if state is not None else SOLVED)
        if len(self.s) != 54:
            raise ValueError("a cube state needs exactly 54 stickers")

    # -- basics ------------------------------------------------------------ #
    def copy(self) -> "Cube":
        c = Cube.__new__(Cube)
        c.s = list(self.s)
        return c

    def __str__(self) -> str:
        return "".join(self.s)

    def __eq__(self, other) -> bool:
        return isinstance(other, Cube) and self.s == other.s

    def __hash__(self):
        return hash(tuple(self.s))

    @property
    def is_solved(self) -> bool:
        return all(
            self.s[i] == self.s[CENTRE[face_of(i)]] for i in range(54)
        )

    # -- moves ------------------------------------------------------------- #
    def apply(self, move: str) -> "Cube":
        perm = MOVE_PERMS[move]
        old = self.s
        new = [None] * 54
        for i in range(54):
            new[perm[i]] = old[i]
        self.s = new
        return self

    def apply_many(self, moves: Sequence[str] | str) -> "Cube":
        if isinstance(moves, str):
            moves = moves.split()
        for m in moves:
            self.apply(m)
        return self

    def moved(self, moves: Sequence[str] | str) -> "Cube":
        return self.copy().apply_many(moves)

    # -- colour helpers ---------------------------------------------------- #
    def colour(self, face: str) -> str:
        return self.s[CENTRE[face]]

    def face_grid(self, face: str) -> List[List[str]]:
        base = FACE_ORDER.index(face) * 9
        return [self.s[base + r * 3: base + r * 3 + 3] for r in range(3)]

    # -- piece lookup ------------------------------------------------------ #
    def find_edge(self, c1: str, c2: str) -> Tuple[int, int] | None:
        """Return (idx_of_c1, idx_of_c2) for the edge cubie carrying both colours."""
        want = {c1, c2}
        for a, b in EDGES:
            if {self.s[a], self.s[b]} == want:
                return (a, b) if self.s[a] == c1 else (b, a)
        return None

    def find_corner(self, c1: str, c2: str, c3: str) -> Tuple[int, int, int] | None:
        want = {c1, c2, c3}
        for a, b, c in CORNERS:
            if {self.s[a], self.s[b], self.s[c]} == want:
                by = {self.s[a]: a, self.s[b]: b, self.s[c]: c}
                return (by[c1], by[c2], by[c3])
        return None


# --------------------------------------------------------------------------- #
# Move utilities
# --------------------------------------------------------------------------- #

def invert(moves: Sequence[str]) -> List[str]:
    out = []
    for m in reversed(moves):
        if m.endswith("2"):
            out.append(m)
        elif m.endswith("'"):
            out.append(m[0])
        else:
            out.append(m + "'")
    return out


_AMOUNT = {"": 1, "'": 3, "2": 2}
_SUFFIX = {1: "", 2: "2", 3: "'"}


def tidy(moves: Sequence[str]) -> List[str]:
    """Collapse consecutive turns of the same face; drop no-ops."""
    stack: List[Tuple[str, int]] = []
    for m in moves:
        f, s = m[0], m[1:]
        amt = _AMOUNT[s]
        if stack and stack[-1][0] == f:
            total = (stack[-1][1] + amt) % 4
            stack.pop()
            if total:
                stack.append((f, total))
        else:
            stack.append((f, amt))
    return [f + _SUFFIX[a] for f, a in stack]


def random_scramble(n: int = 25, rng: random.Random | None = None) -> List[str]:
    rng = rng or random
    moves: List[str] = []
    last = ""
    while len(moves) < n:
        m = rng.choice(ALL_MOVES)
        if m[0] == last:
            continue
        last = m[0]
        moves.append(m)
    return moves
