"""
Scanner regression tests on *real* scan data.

The fixtures in ``tests/fixtures/rubiks_color_resolver/`` are per-sticker RGB
readings of physical cubes, copied unmodified from the MIT-licensed
dwalton76/rubiks-color-resolver project (see LICENSE-NOTE.txt there). Unlike
the synthetic renders in test_solver.py they carry genuine camera noise,
lighting casts and lookalike red/orange pairs.

Upstream format: JSON ``{"1": [R, G, B], ..., "54": [R, G, B]}``, faces in the
order U L F R B D, nine squares each, row-major in the standard Kociemba
orientation. Upstream's ``cube_for_kociemba_strict()`` produces its expected
answer by re-ordering those blocks to U R F D L B with no face rotation, which
is exactly our facelet layout (cube/model.py), so the mapping is a pure block
re-order plus RGB -> BGR. The mapping is confirmed by the solved cubes and the
asymmetric patterns (tetris, superflip, cross) matching upstream's answers
exactly.

Run from the `backend` folder:   python tests/test_fixtures.py
(also picked up by python tests/test_solver.py and by pytest)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cube.model import Cube  # noqa: E402
from cube.validate import CubeError, validate  # noqa: E402
from vision import detect  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "rubiks_color_resolver"

# first upstream square number of each face (upstream face order U L F R B D)
UPSTREAM_START = {"U": 1, "L": 10, "F": 19, "R": 28, "B": 37, "D": 46}

# Expected facelets (U R F D L B), from upstream tests/test-cubes.py at the
# commit recorded in LICENSE-NOTE.txt. None = upstream has no expected answer,
# so we can only check that the reading is a physically possible cube.
EXPECTED = {
    "solved-01": "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB",
    "solved-02": "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB",
    "checkerboard": "UDUDUDUDURLRLRLRLRFBFBFBFBFDUDUDUDUDLRLRLRLRLBFBFBFBFB",
    "cross": "DUDUUUDUDFRFRRRFRFRFRFFFRFRUDUDDDUDUBLBLLLBLBLBLBBBLBL",
    "tetris": "FFBFUBFBBUDDURDUUDRLLRFLRRLBBFBDFBFFUDDULDUUDLRRLBRLLR",
    "superflip": "UBULURUFURURFRBRDRFUFLFRFDFDFDLDRDBDLULBLFLDLBUBRBLBDB",
    "random-01": "DURUULDBRFDFLRRLFBRLUUFFUFFLRUDDDRRDLBBDLLBBBDFFBBRLUU",
    "random-02": "BBRLULRBFDDUURFBULDULRFRUDRFBDFDLUFBUFFRLDRDLFLLRBBDUB",
    "random-03": "DFDRULUFDLFLDRBBLRLRFBFLUDURFRRDUUBDFUBBLDLDFBURRBUBLF",
    "random-05": "BRRDUFDFUBDFFRBDDUBRRRFLLUFUBLRDBBFFULLULBRDFDULLBLRUD",
    "random-06": None,
    "random-07": None,
}

# Fixtures our classifier is known to get wrong. A test for one of these
# passes only while it keeps failing, so a fix (or a regression that
# "accidentally" fixes it) forces this set to be updated.
#
# Currently empty: all 12 upstream 3x3x3 fixtures read correctly (the ten with
# upstream answers match exactly; random-06/07 read as valid cubes).
KNOWN_FAILING: set = set()


def _is_real_cube(facelets: str) -> bool:
    # same check backend/app.py hands the classifier
    try:
        validate(Cube(facelets))
        return True
    except CubeError:
        return False


def load_samples(name: str):
    """Upstream fixture -> 54 BGR samples in our U R F D L B reading order."""
    data = json.loads((FIXTURES / f"3x3x3-{name}.txt").read_text())
    samples = []
    for face in "URFDLB":
        for i in range(9):
            r, g, b = data[str(UPSTREAM_START[face] + i)]
            samples.append([float(b), float(g), float(r)])
    return samples


def check_fixture(name: str) -> None:
    expected = EXPECTED[name]
    got = detect.classify(load_samples(name), is_valid=_is_real_cube)["facelets"]

    problems = []
    if not _is_real_cube(got):
        problems.append(f"not a physically valid cube: {got}")
    if expected is not None and got != expected:
        wrong = sum(a != b for a, b in zip(got, expected))
        problems.append(f"{wrong} sticker(s) differ\n    got {got}\n    exp {expected}")

    if name in KNOWN_FAILING:
        assert problems, f"{name} now reads correctly - remove it from KNOWN_FAILING"
        return
    assert not problems, "; ".join(problems)


def test_fixture_expected_answers_are_valid_cubes():
    """Sanity check on the upstream answers themselves."""
    for name, expected in EXPECTED.items():
        if expected is not None:
            assert _is_real_cube(expected), name


def _make_test(name: str):
    def test():
        check_fixture(name)
    test.__name__ = "test_fixture_" + name.replace("-", "_")
    test.__doc__ = f"real scan 3x3x3-{name}.txt reads correctly"
    return test


for _name in EXPECTED:
    _t = _make_test(_name)
    globals()[_t.__name__] = _t
del _name, _t


def collect():
    """name -> test function, for the runner in test_solver.py."""
    return {k: v for k, v in globals().items()
            if k.startswith("test_") and callable(v)}


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(collect().items()):
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:                      # noqa: BLE001
            fails += 1
            print(f"  FAIL  {name}: {exc}")
    print("\nall good" if not fails else f"\n{fails} failing test(s)")
    sys.exit(1 if fails else 0)
