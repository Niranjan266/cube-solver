"""
Layer-by-layer ("beginner method") solver.

Chosen deliberately over an optimal two-phase solver because every stage maps
to something a human can understand and watch:

    1. bottom cross          2. bottom corners      3. middle layer
    4. top cross             5. top corners placed  6. top corners turned
    7. top edges placed

Every algorithm used here was verified empirically against the geometric cube
engine (see tests/test_solver.py) rather than copied from memory.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from .model import (
    Cube,
    SIDES,
    _slot,
    face_of,
    invert,
    left_of,
    right_of,
)

# --------------------------------------------------------------------------- #
# Verified algorithms
# --------------------------------------------------------------------------- #

#: inserts an up-facing edge sitting at UF, flipped, into the DF slot
CROSS_FLIP = "U' {r}' {f} {r}"

#: cycles the three corners UBL -> UBR -> UFL, leaving UFR untouched
CORNER_CYCLE = "U R U' L' U R' U' L".split()

#: orients the UFR corner in place (apply an even number of times)
CORNER_TWIST = "R' D' R D".split()

#: makes the top cross
TOP_CROSS = "F R U R' U' F'".split()

#: cycles the three edges UF -> UR -> UL, leaving UB untouched
EDGE_CYCLE = "R U' R U R U R U' R' U' R2".split()

STAGE_NAMES = {
    "cross": "Bottom cross",
    "corners": "Bottom corners",
    "middle": "Middle layer",
    "top-cross": "Top cross",
    "top-corner-place": "Position top corners",
    "top-corner-turn": "Turn top corners",
    "top-edge-place": "Position top edges",
}

_U_TURNS = {0: [], 1: ["U"], 2: ["U2"], 3: ["U'"]}


def _u_align(frm: str, to: str) -> List[str]:
    """U turns that carry a top-layer piece sitting over `frm` to over `to`."""
    return _U_TURNS[(SIDES.index(frm) - SIDES.index(to)) % 4]


def _right_insert(f: str, r: str) -> List[str]:
    return ["U", r, "U'", r + "'", "U'", f + "'", "U", f]


def _left_insert(f: str, l: str) -> List[str]:
    return ["U'", l + "'", "U", l, "U", f, "U'", f + "'"]


def _conjugate(alg: Sequence[str], j: int) -> List[str]:
    return _U_TURNS[j % 4] + list(alg) + _U_TURNS[(4 - j) % 4]


class SolveError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #

class _Solver:
    def __init__(self, cube: Cube):
        self.c = cube.copy()
        self.tagged: List[Tuple[str, str]] = []  # (move, stage)
        self.col = {f: self.c.colour(f) for f in "URFDLB"}

    # -- plumbing ---------------------------------------------------------- #
    def do(self, moves: Sequence[str] | str, stage: str) -> None:
        if isinstance(moves, str):
            moves = moves.split()
        for m in moves:
            if not m:
                continue
            self.c.apply(m)
            self.tagged.append((m, stage))

    def peek(self, moves: Sequence[str]) -> Cube:
        return self.c.moved(list(moves))

    # -- predicates -------------------------------------------------------- #
    def edge_done(self, a: str, b: str, cube: Cube | None = None) -> bool:
        cube = cube or self.c
        s = _slot(a, b)
        return cube.s[s[a]] == self.col[a] and cube.s[s[b]] == self.col[b]

    def corner_done(self, a: str, b: str, cc: str, cube: Cube | None = None) -> bool:
        cube = cube or self.c
        s = _slot(a, b, cc)
        return all(cube.s[s[f]] == self.col[f] for f in (a, b, cc))

    def corner_placed(self, a: str, b: str, cc: str, cube: Cube | None = None) -> bool:
        """Right cubie in the right slot, orientation ignored."""
        cube = cube or self.c
        s = _slot(a, b, cc)
        return {cube.s[i] for i in s.values()} == {self.col[a], self.col[b], self.col[cc]}

    # ===================================================================== #
    # Stage 1 - bottom cross
    # ===================================================================== #
    def solve_cross(self) -> None:
        d = self.col["D"]
        for side in SIDES:
            sc = self.col[side]
            for _ in range(16):
                if self.edge_done("D", side):
                    break
                found = self.c.find_edge(d, sc)
                if found is None:
                    raise SolveError(f"missing {d}{sc} edge")
                a, b = found
                fa, fb = face_of(a), face_of(b)

                if "D" in (fa, fb):                      # wrong slot / flipped
                    x = fb if fa == "D" else fa
                    self.do([x + "2"], "cross")
                elif "U" in (fa, fb):                    # ready to insert
                    x = fb if fa == "U" else fa
                    self.do(_u_align(x, side), "cross")
                    s = _slot("U", side)
                    if self.c.s[s["U"]] == d:
                        self.do([side + "2"], "cross")
                    else:
                        r = right_of(side)
                        self.do(
                            CROSS_FLIP.format(f=side, r=r).split(), "cross"
                        )
                else:                                    # stuck in middle layer
                    for cand in (fa, fa + "'"):
                        t = self.peek([cand])
                        na, nb = t.find_edge(d, sc)
                        if "U" in (face_of(na), face_of(nb)):
                            self.do([cand, "U", invert([cand])[0]], "cross")
                            break
                    else:
                        raise SolveError("cannot lift middle-layer cross edge")
            else:
                raise SolveError(f"bottom cross stalled on {side}")

    # ===================================================================== #
    # Stage 2 - bottom corners
    # ===================================================================== #
    def solve_bottom_corners(self) -> None:
        d = self.col["D"]
        for side in SIDES:
            r = right_of(side)
            for _ in range(12):
                if self.corner_done("D", side, r):
                    break
                pos = self.c.find_corner(d, self.col[side], self.col[r])
                if pos is None:
                    raise SolveError("missing bottom corner")
                faces = {face_of(i) for i in pos}

                if "U" not in faces:                     # trapped in bottom layer
                    here = [f for f in faces if f != "D"]
                    a = here[0] if right_of(here[0]) in here else here[1]
                    b = right_of(a)
                    self.do([b, "U", b + "'"], "corners")
                    continue

                here = sorted(f for f in faces if f != "U")
                a = here[0] if right_of(here[0]) in here else here[1]
                self.do(_u_align(a, side), "corners")

                shortcut = self._corner_insert(side, r)
                if shortcut is not None:
                    self.do(shortcut, "corners")
                    continue
                sexy = [r, "U", r + "'", "U'"]
                for _ in range(6):
                    self.do(sexy, "corners")
                    if self.corner_done("D", side, r):
                        break
            else:
                raise SolveError(f"bottom corners stalled on {side}")

    #: short inserts for a bottom corner already sitting in the top layer
    _INSERTS = (
        "{r} U {r}'", "{r} U' {r}'", "{f}' U {f}", "{f}' U' {f}",
        "{r} U2 {r}' U' {r} U {r}'", "{f}' U2 {f} U {f}' U' {f}",
        "{r} U' {r}' U' {r} U {r}'", "{f}' U {f} U {f}' U' {f}",
        "{r} U2 {r}' U2 {r} U' {r}'", "{f}' U2 {f} U2 {f}' U {f}",
    )

    def _corner_insert(self, f: str, r: str) -> List[str] | None:
        """Shortest known insert that seats the D-f-r corner without breaking anything."""
        best = None
        for k in range(4):
            for tpl in self._INSERTS:
                cand = _U_TURNS[k] + tpl.format(f=f, r=r).split()
                if best is not None and len(cand) >= len(best):
                    continue
                t = self.peek(cand)
                if not self.corner_done("D", f, r, t):
                    continue
                if not self._bottom_intact(t, upto=f):
                    continue
                best = cand
        return best

    def _bottom_intact(self, cube: Cube, upto: str) -> bool:
        """Bottom cross plus every bottom corner solved before `upto` still fine."""
        if any(not self.edge_done("D", s, cube) for s in SIDES):
            return False
        return all(
            self.corner_done("D", s, right_of(s), cube)
            for s in SIDES[: SIDES.index(upto)]
        )

    # ===================================================================== #
    # Stage 3 - middle layer
    # ===================================================================== #
    def solve_middle(self) -> None:
        for side in SIDES:
            r = right_of(side)
            for _ in range(10):
                if self.edge_done(side, r):
                    break
                pos = self.c.find_edge(self.col[side], self.col[r])
                if pos is None:
                    raise SolveError("missing middle edge")
                faces = [face_of(i) for i in pos]

                if "U" not in faces:                     # wrong middle slot
                    a = faces[0] if right_of(faces[0]) == faces[1] else faces[1]
                    self.do(_right_insert(a, right_of(a)), "middle")
                    continue

                iu = pos[0] if face_of(pos[0]) == "U" else pos[1]
                ix = pos[1] if iu is pos[0] else pos[0]
                cu, cx = self.c.s[iu], self.c.s[ix]
                home = next(f for f in SIDES if self.col[f] == cx)
                self.do(_u_align(face_of(ix), home), "middle")
                if cu == self.col[right_of(home)]:
                    self.do(_right_insert(home, right_of(home)), "middle")
                else:
                    self.do(_left_insert(home, left_of(home)), "middle")
            else:
                raise SolveError(f"middle layer stalled on {side}")

    # ===================================================================== #
    # Stage 4 - top cross
    # ===================================================================== #
    def _n_top_edges_up(self, cube: Cube | None = None) -> int:
        cube = cube or self.c
        u = self.col["U"]
        return sum(1 for s in SIDES if cube.s[_slot("U", s)["U"]] == u)

    def solve_top_cross(self) -> None:
        """Dot -> L -> line -> cross, found by a tiny search over AUF + F R U R' U' F'."""
        if self._n_top_edges_up() == 4:
            return
        blocks = [_U_TURNS[k] + TOP_CROSS for k in range(4)]
        frontier: List[List[str]] = [[]]
        for _ in range(4):
            nxt: List[List[str]] = []
            for seq in frontier:
                for b in blocks:
                    cand = seq + b
                    if self._n_top_edges_up(self.peek(cand)) == 4:
                        self.do(cand, "top-cross")
                        return
                    nxt.append(cand)
            frontier = nxt
        raise SolveError("top cross stalled")

    # ===================================================================== #
    # Stage 5 - place top corners
    # ===================================================================== #
    def _placed_corners(self, cube: Cube) -> List[str]:
        return [
            s for s in SIDES
            if self.corner_placed("U", s, right_of(s), cube)
        ]

    def _best_auf_corners(self) -> Tuple[int, List[str]]:
        best = (-1, [])
        for k in range(4):
            n = len(self._placed_corners(self.peek(_U_TURNS[k])))
            if n > best[0]:
                best = (n, _U_TURNS[k])
        return best

    def _candidates(self, alg: Sequence[str], pre_auf: bool = True) -> List[List[str]]:
        """Every useful placement of a 3-cycle: pre-AUF x conjugation x direction."""
        out = []
        for k in range(4 if pre_auf else 1):
            for j in range(4):
                for a in (alg, invert(alg)):
                    out.append(_U_TURNS[k] + _conjugate(a, j))
        return out

    def _corner_score(self, cube: Cube) -> int:
        return max(
            len(self._placed_corners(cube.moved(_U_TURNS[k]))) for k in range(4)
        )

    def solve_top_corner_places(self) -> None:
        stage = "top-corner-place"
        for _ in range(4):
            n, auf = self._best_auf_corners()
            if n == 4:
                self.do(auf, stage)
                return
            cands = self._candidates(CORNER_CYCLE)
            best = max(cands, key=lambda cd: self._corner_score(self.peek(cd)))
            if self._corner_score(self.peek(best)) <= n:
                best = cands[0]
            self.do(best, stage)
        raise SolveError("top corner placement stalled")

    # ===================================================================== #
    # Stage 6 - turn top corners
    # ===================================================================== #
    def solve_top_corner_turns(self) -> None:
        stage = "top-corner-turn"
        u = self.col["U"]
        top = _slot("U", "F", "R")["U"]
        for _ in range(4):
            for _ in range(2):
                if self.c.s[top] == u:
                    break
                self.do(CORNER_TWIST * 2, stage)
            if self.c.s[top] != u:
                raise SolveError("corner refuses to orient")
            self.do(["U"], stage)
        n, auf = self._best_auf_corners()
        if n != 4:
            raise SolveError("top corners lost during orientation")
        self.do(auf, stage)

    # ===================================================================== #
    # Stage 7 - place top edges
    # ===================================================================== #
    def _placed_edges(self, cube: Cube) -> List[str]:
        return [s for s in SIDES if self.edge_done("U", s, cube)]

    def solve_top_edges(self) -> None:
        stage = "top-edge-place"
        for _ in range(4):
            n = len(self._placed_edges(self.c))
            if n == 4:
                return
            cands = self._candidates(EDGE_CYCLE, pre_auf=False)
            best = max(cands, key=lambda cd: len(self._placed_edges(self.peek(cd))))
            if len(self._placed_edges(self.peek(best))) <= n:
                best = cands[0]
            self.do(best, stage)
        if len(self._placed_edges(self.c)) != 4:
            raise SolveError("top edge placement stalled")

    # ===================================================================== #
    def run(self) -> List[Tuple[str, str]]:
        self.solve_cross()
        self.solve_bottom_corners()
        self.solve_middle()
        self.solve_top_cross()
        self.solve_top_corner_places()
        self.solve_top_corner_turns()
        self.solve_top_edges()
        if not self.c.is_solved:
            raise SolveError("solver finished but cube is not solved")
        return self.tagged


def _tidy_tagged(tagged: Sequence[Tuple[str, str]]) -> List[Tuple[str, str]]:
    amount = {"": 1, "'": 3, "2": 2}
    suffix = {1: "", 2: "2", 3: "'"}
    stack: List[List] = []  # [face, amount, stage]
    for move, stage in tagged:
        f, a = move[0], amount[move[1:]]
        if stack and stack[-1][0] == f:
            total = (stack[-1][1] + a) % 4
            st = stack.pop()[2]
            if total:
                stack.append([f, total, st])
        else:
            stack.append([f, a, stage])
    return [(f + suffix[a], st) for f, a, st in stack]


def solve(cube: Cube) -> List[Tuple[str, str]]:
    """Solve `cube`, returning a tidied list of (move, stage-key) pairs."""
    return _tidy_tagged(_Solver(cube).run())


def solve_moves(cube: Cube) -> List[str]:
    return [m for m, _ in solve(cube)]
