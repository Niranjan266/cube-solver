"""
Kociemba's two-phase algorithm, implemented here rather than pulled from a
package, so a fresh checkout gives ~25-move solutions with nothing to install.

Phase 1 drives the cube into the subgroup G1 = <U, D, R2, L2, F2, B2>, where
every corner and edge is the right way up and the four middle-slice edges are
back in the middle slice.  Phase 2 finishes the job using only those ten moves.

Both phases are IDA* over small coordinate spaces with exact pruning tables.
The tables take a few seconds to build the first time and are then cached in
``cube/_tables``; after that a solve is a fraction of a second.
"""

from __future__ import annotations

import itertools
import os
import time
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .cubie import MOVE_CUBES, MOVE_NAMES, CubieCube
from .model import Cube

TABLE_DIR = os.path.join(os.path.dirname(__file__), "_tables")
TABLE_FILE = os.path.join(TABLE_DIR, "twophase-v2.npz")

N_TWIST = 2187        # corner orientations
N_FLIP = 2048         # edge orientations
N_SLICE = 495         # which four slots hold the middle-slice edges
N_PERM8 = 40320       # 8! - corner permutation, and the eight non-slice edges
N_SSLICE = 24         # 4! - order of the middle-slice edges

#: indices into MOVE_NAMES of the ten moves that stay inside G1
G1_MOVES: Tuple[int, ...] = tuple(
    MOVE_NAMES.index(m) for m in ("U", "U2", "U'", "R2", "F2", "D", "D2", "D'", "L2", "B2")
)

FACE_OF_MOVE: Tuple[int, ...] = tuple("URFDLB".index(m[0]) for m in MOVE_NAMES)
#: faces that share an axis, so U/D and R/L and F/B turns commute
AXIS_PARTNER = {0: 3, 3: 0, 1: 4, 4: 1, 2: 5, 5: 2}


# --------------------------------------------------------------------------- #
# coordinates
# --------------------------------------------------------------------------- #

def _twist(cc: CubieCube) -> int:
    v = 0
    for i in range(7):
        v = v * 3 + cc.co[i]
    return v


def _flip(cc: CubieCube) -> int:
    v = 0
    for i in range(11):
        v = v * 2 + cc.eo[i]
    return v


def _all_twists() -> np.ndarray:
    """(N_TWIST, 8) every corner-orientation vector, indexed by twist."""
    out = np.zeros((N_TWIST, 8), np.int8)
    for v in range(N_TWIST):
        x, total = v, 0
        for i in range(6, -1, -1):
            out[v, i] = x % 3
            total += x % 3
            x //= 3
        out[v, 7] = (-total) % 3
    return out


def _all_flips() -> np.ndarray:
    out = np.zeros((N_FLIP, 12), np.int8)
    for v in range(N_FLIP):
        x, total = v, 0
        for i in range(10, -1, -1):
            out[v, i] = x % 2
            total += x % 2
            x //= 2
        out[v, 11] = total % 2
    return out


def _slice_masks() -> Tuple[np.ndarray, Dict[int, int]]:
    """(N_SLICE, 12) occupancy vectors plus a packed-bits lookup."""
    combos = list(itertools.combinations(range(12), 4))
    occ = np.zeros((len(combos), 12), np.int8)
    lookup: Dict[int, int] = {}
    for n, combo in enumerate(combos):
        bits = 0
        for p in combo:
            occ[n, p] = 1
            bits |= 1 << p
        lookup[bits] = n
    return occ, lookup


def _slice_index(cc: CubieCube) -> int:
    bits = 0
    for p in range(12):
        if cc.ep[p] >= 8:
            bits |= 1 << p
    return _SLICE_LOOKUP[bits]


_PERMS8 = np.array(list(itertools.permutations(range(8))), np.int8)
_PERM8_ID: Dict[bytes, int] = {
    row.tobytes(): i for i, row in enumerate(_PERMS8)
}
_PERMS4 = np.array(list(itertools.permutations(range(4))), np.int8)
_PERM4_ID: Dict[bytes, int] = {
    row.tobytes(): i for i, row in enumerate(_PERMS4)
}


def _corner_perm(cc: CubieCube) -> int:
    return _PERM8_ID[np.array(cc.cp, np.int8).tobytes()]


def _edge8_perm(cc: CubieCube) -> int:
    return _PERM8_ID[np.array(cc.ep[:8], np.int8).tobytes()]


def _sslice_perm(cc: CubieCube) -> int:
    return _PERM4_ID[np.array([e - 8 for e in cc.ep[8:]], np.int8).tobytes()]


_SLICE_OCC, _SLICE_LOOKUP = _slice_masks()

#: the slice coordinate we are aiming for - the four slice edges back in
#: slots 8..11.  (It is *not* zero: index 0 is the combination (0,1,2,3).)
SLICE_GOAL = _SLICE_LOOKUP[sum(1 << p for p in range(8, 12))]


# --------------------------------------------------------------------------- #
# tables
# --------------------------------------------------------------------------- #

def _build_move_tables() -> Dict[str, np.ndarray]:
    twists = _all_twists()
    flips = _all_flips()

    twist_mv = np.zeros((N_TWIST, 18), np.int16)
    flip_mv = np.zeros((N_FLIP, 18), np.int16)
    slice_mv = np.zeros((N_SLICE, 18), np.int16)

    pow3 = 3 ** np.arange(6, -1, -1)
    pow2 = 2 ** np.arange(10, -1, -1)
    bits = 1 << np.arange(12)

    for m, mc in enumerate(MOVE_CUBES):
        cp = np.array(mc.cp)
        co = np.array(mc.co, np.int8)
        ep = np.array(mc.ep)
        eo = np.array(mc.eo, np.int8)

        new_co = (twists[:, cp] + co) % 3
        twist_mv[:, m] = (new_co[:, :7] * pow3).sum(axis=1)

        new_eo = (flips[:, ep] + eo) % 2
        flip_mv[:, m] = (new_eo[:, :11] * pow2).sum(axis=1)

        new_occ = _SLICE_OCC[:, ep]
        packed = (new_occ * bits).sum(axis=1)
        slice_mv[:, m] = [_SLICE_LOOKUP[int(p)] for p in packed]

    n2 = len(G1_MOVES)
    cperm_mv = np.zeros((N_PERM8, n2), np.int32)
    eperm_mv = np.zeros((N_PERM8, n2), np.int32)
    sslice_mv = np.zeros((N_SSLICE, n2), np.int32)

    for j, m in enumerate(G1_MOVES):
        mc = MOVE_CUBES[m]
        cp = np.array(mc.cp)
        ep8 = np.array(mc.ep[:8])
        ep4 = np.array([e - 8 for e in mc.ep[8:]])

        rows = _PERMS8[:, cp]
        cperm_mv[:, j] = [_PERM8_ID[r.tobytes()] for r in rows]
        rows = _PERMS8[:, ep8]
        eperm_mv[:, j] = [_PERM8_ID[r.tobytes()] for r in rows]
        rows = _PERMS4[:, ep4]
        sslice_mv[:, j] = [_PERM4_ID[r.tobytes()] for r in rows]

    return {
        "twist_mv": twist_mv, "flip_mv": flip_mv, "slice_mv": slice_mv,
        "cperm_mv": cperm_mv, "eperm_mv": eperm_mv, "sslice_mv": sslice_mv,
    }


def _bfs(size_a: int, size_b: int, mv_a: np.ndarray, mv_b: np.ndarray,
         goal: int) -> np.ndarray:
    """Exact distance from every (a, b) pair to the goal pair."""
    total = size_a * size_b
    dist = np.full(total, 255, np.uint8)
    dist[goal] = 0
    frontier = np.array([goal], np.int64)
    depth = 0
    n_moves = mv_a.shape[1]
    while frontier.size:
        a = frontier // size_b
        b = frontier % size_b
        nxt = []
        for m in range(n_moves):
            cand = mv_a[a, m].astype(np.int64) * size_b + mv_b[b, m]
            cand = cand[dist[cand] == 255]
            if cand.size:
                cand = np.unique(cand)
                dist[cand] = depth + 1
                nxt.append(cand)
        depth += 1
        frontier = np.unique(np.concatenate(nxt)) if nxt else np.array([], np.int64)
    return dist


def _build_tables() -> Dict[str, np.ndarray]:
    t = _build_move_tables()
    t["prune_flip"] = _bfs(N_FLIP, N_SLICE, t["flip_mv"], t["slice_mv"], SLICE_GOAL)
    t["prune_twist"] = _bfs(N_TWIST, N_SLICE, t["twist_mv"], t["slice_mv"], SLICE_GOAL)
    t["prune_cperm"] = _bfs(N_PERM8, N_SSLICE, t["cperm_mv"], t["sslice_mv"], 0)
    t["prune_eperm"] = _bfs(N_PERM8, N_SSLICE, t["eperm_mv"], t["sslice_mv"], 0)
    return t


_TABLES: Optional[Dict[str, np.ndarray]] = None


def tables(progress=None) -> Dict[str, np.ndarray]:
    """Load the tables, building and caching them on first use."""
    global _TABLES
    if _TABLES is not None:
        return _TABLES
    if os.path.exists(TABLE_FILE):
        try:
            with np.load(TABLE_FILE) as z:
                _TABLES = {k: z[k] for k in z.files}
            return _TABLES
        except Exception:
            pass  # corrupt cache - just rebuild
    if progress:
        progress("building solver tables (one time, a few seconds)")
    _TABLES = _build_tables()
    try:
        os.makedirs(TABLE_DIR, exist_ok=True)
        np.savez_compressed(TABLE_FILE, **_TABLES)
    except OSError:
        pass  # read-only install: just keep them in memory
    return _TABLES


def warm_up() -> None:
    tables()


# --------------------------------------------------------------------------- #
# search
# --------------------------------------------------------------------------- #

class _Search:
    def __init__(self, cc: CubieCube, max_length: int, timeout: float):
        self.t = tables()
        self.start = cc
        self.max_length = max_length
        self.deadline = time.time() + timeout
        self.best: Optional[List[int]] = None
        self.phase1_length = 0

        self.twist_mv = self.t["twist_mv"]
        self.flip_mv = self.t["flip_mv"]
        self.slice_mv = self.t["slice_mv"]
        self.p_flip = self.t["prune_flip"]
        self.p_twist = self.t["prune_twist"]
        self.cperm_mv = self.t["cperm_mv"]
        self.eperm_mv = self.t["eperm_mv"]
        self.sslice_mv = self.t["sslice_mv"]
        self.p_cperm = self.t["prune_cperm"]
        self.p_eperm = self.t["prune_eperm"]

    # -- phase 1 ------------------------------------------------------------ #
    def _h1(self, twist: int, flip: int, sl: int) -> int:
        return max(int(self.p_twist[twist * N_SLICE + sl]),
                   int(self.p_flip[flip * N_SLICE + sl]))

    def run(self) -> Optional[List[int]]:
        cc = self.start
        twist, flip, sl = _twist(cc), _flip(cc), _slice_index(cc)
        if twist == 0 and flip == 0 and sl == SLICE_GOAL:
            self._finish([])
        for depth in range(self._h1(twist, flip, sl), self.max_length + 1):
            if self.best is not None or time.time() > self.deadline:
                break
            self._phase1(twist, flip, sl, depth, [], -1)
        return self.best

    def _phase1(self, twist, flip, sl, left, path, last_face) -> None:
        if self.best is not None or time.time() > self.deadline:
            return
        if left == 0:
            if twist == 0 and flip == 0 and sl == SLICE_GOAL:
                self._finish(path)
            return
        if self._h1(twist, flip, sl) > left:
            return
        for m in range(18):
            face = FACE_OF_MOVE[m]
            if face == last_face:
                continue
            if AXIS_PARTNER[face] == last_face and face > last_face:
                continue
            path.append(m)
            self._phase1(int(self.twist_mv[twist, m]),
                         int(self.flip_mv[flip, m]),
                         int(self.slice_mv[sl, m]),
                         left - 1, path, face)
            path.pop()
            if self.best is not None:
                return

    # -- phase 2 ------------------------------------------------------------ #
    def _finish(self, path1: Sequence[int]) -> None:
        cc = self.start
        for m in path1:
            cc = cc.multiply(MOVE_CUBES[m])
        cp, ep, ss = _corner_perm(cc), _edge8_perm(cc), _sslice_perm(cc)
        budget = self.max_length - len(path1)
        last_face = FACE_OF_MOVE[path1[-1]] if path1 else -1
        for depth in range(self._h2(cp, ep, ss), budget + 1):
            found: List[int] = []
            if self._phase2(cp, ep, ss, depth, found, last_face):
                self.best = list(path1) + [G1_MOVES[i] for i in found]
                self.phase1_length = len(path1)
                return
            if time.time() > self.deadline:
                return

    def _h2(self, cp: int, ep: int, ss: int) -> int:
        return max(int(self.p_cperm[cp * N_SSLICE + ss]),
                   int(self.p_eperm[ep * N_SSLICE + ss]))

    def _phase2(self, cp, ep, ss, left, path, last_face) -> bool:
        if left == 0:
            return cp == 0 and ep == 0 and ss == 0
        if self._h2(cp, ep, ss) > left:
            return False
        for j, m in enumerate(G1_MOVES):
            face = FACE_OF_MOVE[m]
            if face == last_face:
                continue
            if AXIS_PARTNER[face] == last_face and face > last_face:
                continue
            path.append(j)
            if self._phase2(int(self.cperm_mv[cp, j]),
                            int(self.eperm_mv[ep, j]),
                            int(self.sslice_mv[ss, j]),
                            left - 1, path, face):
                return True
            path.pop()
        return False


#: never hand a person a longer solution than this
HARD_CAP = 30


def solve_split(cube: Cube, max_length: int = 22,
                timeout: float = 6.0) -> Tuple[List[str], int]:
    """
    Shortest-ish solution, plus how many of the moves belong to phase 1.

    Raises RuntimeError only if the cube is unsolvable, which callers should
    have ruled out with :func:`cube.validate.validate` first.
    """
    cc = CubieCube.from_facelets(cube)
    if cc.is_solved():
        return [], 0
    # Ask for a short answer first and settle for a longer one only if the
    # short search runs dry.  22 turns is the sweet spot: shorter *and* faster
    # than asking for 24, because the tighter bound prunes far more of the tree.
    for limit, budget in ((max_length, timeout),
                          (max_length + 2, timeout),
                          (HARD_CAP, timeout * 2)):
        search = _Search(cc, limit, budget)
        found = search.run()
        if found is not None:
            return [MOVE_NAMES[m] for m in found], search.phase1_length
    raise RuntimeError(
        f"no solution of {HARD_CAP} turns or fewer was found in time"
    )


def solve(cube: Cube, max_length: int = 22, timeout: float = 6.0) -> List[str]:
    return solve_split(cube, max_length, timeout)[0]
