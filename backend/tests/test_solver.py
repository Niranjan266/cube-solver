"""
Regression tests.

Run from the `backend` folder:   python -m pytest tests -q
Or without pytest:               python tests/test_solver.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from cube.model import (  # noqa: E402
    ALL_MOVES,
    CORNERS,
    EDGES,
    MOVE_FACES,
    SOLVED,
    Cube,
    invert,
    random_scramble,
)
from cube.solver import solve as solve_api  # noqa: E402
from cube.solver_beginner import (  # noqa: E402
    CORNER_CYCLE,
    CORNER_TWIST,
    EDGE_CYCLE,
    solve,
)
from cube.validate import CubeError, validate  # noqa: E402
from tests.synth import STICKER_BGR, STICKER_HARD, render_cube  # noqa: E402
from vision import detect  # noqa: E402


# --------------------------------------------------------------------------- #
# engine
# --------------------------------------------------------------------------- #

def test_geometry_is_consistent():
    assert len(EDGES) == 12 and len(CORNERS) == 8
    for f in MOVE_FACES:
        c = Cube()
        for _ in range(4):
            c.apply(f)
        assert str(c) == SOLVED, f"{f} is not a quarter turn"


def test_moves_are_invertible():
    rng = random.Random(1)
    for _ in range(200):
        seq = random_scramble(rng.randint(1, 15), rng)
        assert Cube().apply_many(seq).apply_many(invert(seq)).is_solved


def test_sexy_move_has_order_six():
    c = Cube()
    for _ in range(6):
        c.apply_many("R U R' U'")
    assert c.is_solved


# --------------------------------------------------------------------------- #
# the algorithms the solver leans on
# --------------------------------------------------------------------------- #

def _touched(alg):
    c = Cube().apply_many(list(alg))
    out = []
    for grp in list(EDGES) + list(CORNERS):
        if any(c.s[i] != Cube().s[i] for i in grp):
            out.append(grp)
    return out


def test_corner_cycle_moves_only_three_corners():
    touched = _touched(CORNER_CYCLE)
    assert len(touched) == 3
    assert all(len(g) == 3 for g in touched), "it must not disturb any edge"


def test_edge_cycle_moves_only_three_edges():
    touched = _touched(EDGE_CYCLE)
    assert len(touched) == 3
    assert all(len(g) == 2 for g in touched), "it must not disturb any corner"


def test_corner_twist_is_order_six():
    c = Cube()
    for _ in range(6):
        c.apply_many(CORNER_TWIST)
    assert c.is_solved


# --------------------------------------------------------------------------- #
# solver
# --------------------------------------------------------------------------- #

def test_solver_handles_many_random_cubes():
    rng = random.Random(2024)
    for _ in range(300):
        cube = Cube().apply_many(random_scramble(25, rng))
        moves = [m for m, _ in solve(cube)]
        assert cube.moved(moves).is_solved


def test_solver_on_an_already_solved_cube():
    assert solve(Cube()) == []


def test_two_phase_solves_and_stays_short():
    from cube.twophase import solve as quick

    rng = random.Random(99)
    lengths = []
    for _ in range(40):
        cube = Cube().apply_many(random_scramble(25, rng))
        moves = quick(cube)
        assert cube.moved(moves).is_solved
        lengths.append(len(moves))
    assert max(lengths) <= 24, f"a solution ran to {max(lengths)} turns"
    assert sum(lengths) / len(lengths) < 23


def test_no_solution_ever_exceeds_the_promised_cap():
    """The app tells people 'never more than 30 turns'. Hold it to that."""
    from cube.twophase import HARD_CAP, solve as quick

    rng = random.Random(4242)
    worst = 0
    for _ in range(60):
        # every kind of cube: nearly solved, half mixed, thoroughly scrambled
        n = rng.choice([1, 2, 4, 8, 15, 25, 40, 60])
        cube = Cube().apply_many(random_scramble(n, rng))
        moves = quick(cube)
        assert cube.moved(moves).is_solved
        worst = max(worst, len(moves))
    assert worst <= HARD_CAP, f"a solution ran to {worst} turns, cap is {HARD_CAP}"
    assert worst <= 24, f"unexpectedly long worst case: {worst} turns"


def test_two_phase_on_lightly_scrambled_cubes():
    from cube.twophase import solve as quick

    rng = random.Random(7)
    for n in (0, 1, 2, 3, 5, 9):
        for _ in range(6):
            scramble = random_scramble(n, rng) if n else []
            cube = Cube().apply_many(scramble)
            moves = quick(cube)
            assert cube.moved(moves).is_solved
            assert len(moves) <= max(len(scramble), 20)


def test_cubie_model_matches_facelets():
    from cube.cubie import CubieCube, apply_moves

    rng = random.Random(11)
    for _ in range(150):
        seq = random_scramble(rng.randint(1, 20), rng)
        assert str(apply_moves(CubieCube(), seq).to_facelets()) == str(
            Cube().apply_many(seq)
        )
        cc = CubieCube.from_facelets(Cube().apply_many(seq))
        assert str(cc.to_facelets()) == str(Cube().apply_many(seq))


def test_quick_mode_is_the_default():
    cube = Cube().apply_many(random_scramble(25, random.Random(21)))
    result = solve_api(cube)
    assert result["mode"] == "quick"
    assert result["moveCount"] <= 26
    assert [s["key"] for s in result["stages"]] == ["quick-1", "quick-2"]
    for step in result["steps"]:
        assert step["arrow"] and step["motion"]


def test_solver_stages_are_in_order():
    cube = Cube().apply_many(random_scramble(25, random.Random(5)))
    result = solve_api(cube, mode="learn")
    order = [s["key"] for s in result["stages"]]
    expected = ["cross", "corners", "middle", "top-cross",
                "top-corner-place", "top-corner-turn", "top-edge-place"]
    assert order == expected
    assert len(result["steps"]) == result["moveCount"]
    assert result["steps"][-1]["stateAfter"] == str(cube.moved(result["moves"]))


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #

def test_real_cubes_pass_validation():
    rng = random.Random(3)
    for _ in range(300):
        validate(Cube().apply_many(random_scramble(25, rng)))


def test_twisted_corner_is_rejected():
    c = Cube()
    a, b, d = 8, 9, 20            # the three stickers of one corner
    c.s[a], c.s[b], c.s[d] = c.s[b], c.s[d], c.s[a]
    try:
        validate(c)
    except CubeError:
        return
    raise AssertionError("a single twisted corner should be impossible")


def test_swapped_stickers_are_usually_caught():
    rng = random.Random(4)
    caught = tried = 0
    for _ in range(200):
        c = Cube().apply_many(random_scramble(25, rng))
        i, j = rng.sample(range(54), 2)
        if c.s[i] == c.s[j]:
            continue
        c.s[i], c.s[j] = c.s[j], c.s[i]
        tried += 1
        try:
            validate(c)
        except CubeError:
            caught += 1
    assert caught / tried > 0.95


# --------------------------------------------------------------------------- #
# vision
# --------------------------------------------------------------------------- #

def test_synthetic_scan_round_trip():
    rng = random.Random(5)
    np.random.seed(5)
    for _ in range(10):
        cube = Cube().apply_many(random_scramble(25, rng))
        images = render_cube(str(cube), rng)
        samples = []
        for f in "URFDLB":
            samples.extend(detect.scan_face(images[f])["samples"])
        assert detect.classify(samples)["facelets"] == str(cube)


def _is_real_cube(facelets: str) -> bool:
    try:
        validate(Cube(facelets))
        return True
    except CubeError:
        return False


def _scan(truth: str, rng, palette, difficulty, gate=True, tries=8):
    from tests.synth import render_face

    samples = []
    for i in range(6):
        colours = list(truth[i * 9: i * 9 + 9])
        best = None
        for _ in range(tries):
            img = render_face(colours, rng=rng, palette=palette,
                              difficulty=difficulty)
            read = detect.read_face(img)
            best = best or read
            if not gate or (read["found"] and read["confidence"] >= 0.75):
                best = read
                break
        samples.extend(best["samples"])
    return samples


def test_grid_lands_on_the_stickers_in_hard_photos():
    """The detector must put its cells on the real stickers, not near them."""
    import cv2
    from tests.synth import cell_centres, render_face
    from vision import grid

    rng = random.Random(3)
    np.random.seed(3)
    hits = total = 0
    for _ in range(40):
        colours = list("URFDLB"[i % 6] for i in range(9))
        rng.shuffle(colours)
        img = render_face(colours, rng=rng, difficulty="hard")
        truth = cell_centres(render_face.last_quad)
        cell = np.linalg.norm(render_face.last_quad[1] - render_face.last_quad[0]) / 3
        quad, method, conf = grid.find_face(img)
        if method != "lattice":
            continue                      # the app declines to capture these
        m = cv2.getPerspectiveTransform(
            np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]), quad)
        want = np.float32([[[(c + .5) / 3, (r + .5) / 3]
                            for r in range(3) for c in range(3)]])
        got = cv2.perspectiveTransform(want, m)[0]
        hits += int((np.linalg.norm(got - truth, axis=1) < cell * 0.45).sum())
        total += 9
    assert total >= 9 * 25, "the detector gave up far too often"
    assert hits / total > 0.97, f"only {hits}/{total} cells landed on a sticker"


def test_reads_hard_photos_accurately():
    """End to end, with auto-capture behaving as it does with a real camera."""
    rng = random.Random(3)
    np.random.seed(3)
    perfect = silent = 0
    for _ in range(20):
        truth = str(Cube().apply_many(random_scramble(25, rng)))
        got = detect.classify(_scan(truth, rng, STICKER_BGR, "hard"),
                              is_valid=_is_real_cube)["facelets"]
        if got == truth:
            perfect += 1
        elif _is_real_cube(got):
            silent += 1                   # wrong and the app cannot warn: the bad case
    assert perfect >= 19, f"only {perfect}/20 cubes read perfectly"
    assert silent == 0, f"{silent}/20 cubes were wrong without any warning"


def test_ciede2000_matches_the_published_values():
    """Sharma, Wu & Dalal's test data - the reference for a CIEDE2000."""
    from vision.cubie_resolver import delta_e_2000

    cases = [
        ((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485), 2.0425),
        ((50.0000, 2.5000, 0.0000), (50.0000, 0.0000, -2.5000), 4.3065),
        ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
        ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
        ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
    ]
    for a, b, want in cases:
        got = float(delta_e_2000(np.array([a]), np.array([b]))[0, 0])
        assert abs(got - want) < 1e-3, f"{a} vs {b}: got {got}, want {want}"


def test_piece_matching_is_exact_when_the_colours_are_clean():
    """
    With unmuddied samples the piece matcher must reproduce the cube exactly.

    This is the test that catches a mirrored corner: a corner can only sit in a
    slot of the same handedness, so if the rotation bookkeeping were wrong this
    would fail on most scrambles rather than a rare one.
    """
    from vision import cubie_resolver

    rng = random.Random(1)
    for palette in (STICKER_BGR, STICKER_HARD):
        for _ in range(50):
            truth = str(Cube().apply_many(random_scramble(25, rng)))
            samples = [list(palette[c]) for c in truth]
            assert cubie_resolver.resolve(samples)["facelets"] == truth


def test_reading_the_colours_twice_beats_reading_them_once():
    """The two readings have to earn their keep against either one alone."""
    from vision import colour, cubie_resolver

    rng = random.Random(3)
    np.random.seed(3)
    stickers = pieces = both = 0
    for _ in range(12):
        truth = str(Cube().apply_many(random_scramble(25, rng)))
        samples = _scan(truth, rng, STICKER_HARD, "hard")
        stickers += colour.classify_stickers(
            samples, is_valid=_is_real_cube)["facelets"] == truth
        pieces += cubie_resolver.resolve(samples)["facelets"] == truth
        both += colour.classify(samples, is_valid=_is_real_cube)["facelets"] == truth
    assert both >= stickers and both >= pieces, (
        f"using both ({both}) did not beat stickers alone ({stickers}) "
        f"or pieces alone ({pieces})"
    )


def test_declining_bad_frames_beats_accepting_them():
    """The capture gate has to earn its keep."""
    def run(gate):
        rng = random.Random(5)
        np.random.seed(5)
        good = 0
        for _ in range(12):
            truth = str(Cube().apply_many(random_scramble(25, rng)))
            got = detect.classify(_scan(truth, rng, STICKER_BGR, "hard", gate=gate),
                                  is_valid=_is_real_cube)["facelets"]
            good += got == truth
        return good

    assert run(True) > run(False)


def test_colour_model_shrugs_off_exposure_and_white_balance():
    """The same cube shot with wildly different camera settings reads the same."""
    from vision import colour

    rng = random.Random(8)
    truth = str(Cube().apply_many(random_scramble(25, rng)))
    base = []
    for i in range(6):
        for j in range(9):
            base.append(list(STICKER_BGR[truth[i * 9 + j]]))
    base = np.array(base, float)

    knocked = base.copy()
    for f in range(6):                    # each face gets its own camera settings
        gain = rng.uniform(0.65, 1.45)
        cast = np.array([rng.uniform(0.75, 1.3) for _ in range(3)])
        knocked[f * 9:(f + 1) * 9] = np.clip(
            knocked[f * 9:(f + 1) * 9] * gain * cast, 4, 255)
    for k in range(0, 54, 7):             # and a shadow on scattered stickers
        knocked[k] = np.clip(knocked[k] * 0.55, 4, 255)

    assert colour.classify(knocked.tolist())["facelets"] == truth


def test_scan_survives_a_colour_cast():
    rng = random.Random(6)
    np.random.seed(6)
    warm = {k: tuple(min(255, v * c) for v, c in zip(col, (0.82, 0.97, 1.15)))
            for k, col in STICKER_BGR.items()}
    for _ in range(10):
        cube = Cube().apply_many(random_scramble(25, rng))
        images = render_cube(str(cube), rng, warm)
        samples = []
        for f in "URFDLB":
            samples.extend(detect.scan_face(images[f])["samples"])
        assert detect.classify(samples)["facelets"] == str(cube)


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:                      # noqa: BLE001
            fails += 1
            print(f"  FAIL  {name}: {exc}")
    print("\nall good" if not fails else f"\n{fails} failing test(s)")
    sys.exit(1 if fails else 0)
