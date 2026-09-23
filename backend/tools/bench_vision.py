"""
Measure how accurately the app reads a cube.

    python tools/bench_vision.py
    python tools/bench_vision.py --hard 200

Photos are rendered, not real, so the numbers are only as honest as the
renderer - see tests/synth.py.  The ``hard`` preset tilts the face in 3D, gives
every shot its own exposure and white balance, adds a glare spot, a soft
shadow, motion blur and sensor noise, and fills the background with
sticker-shaped decoys.

Two rows are printed per difficulty, because they answer different questions:

``one frame``  what a single photo gets you, with none of the app's safety
               nets.  This is the raw quality of the vision code.
``as shipped`` what the app actually does: keep looking until the detector is
               confident, then use the physical-possibility check to reject and
               repair readings that could not come off a real cube.

Columns
    grid      faces whose sticker grid was located rather than guessed
    sticker   share of the 54 stickers labelled correctly
    cube      share of cubes with all 54 correct
    silent    cubes read wrong that still looked like a real cube - the only
              genuinely bad outcome, because the user gets no warning
    agreed    cubes where both independent colour readings gave the same answer
    frames    camera frames used per face
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cube.model import Cube, random_scramble          # noqa: E402
from cube.validate import CubeError, validate         # noqa: E402
from tests.synth import STICKER_BGR, STICKER_HARD, render_face  # noqa: E402
from vision import detect                             # noqa: E402

MIN_CONFIDENCE = 0.75


def is_real_cube(facelets: str) -> bool:
    try:
        validate(Cube(facelets))
        return True
    except CubeError:
        return False


def read_cube(truth: str, rng, palette, difficulty, *, gate: bool, tries: int):
    samples, frames, located = [], 0, 0
    for i in range(6):
        colours = list(truth[i * 9: i * 9 + 9])
        chosen = None
        for _ in range(tries if gate else 1):
            frames += 1
            img = render_face(colours, rng=rng, palette=palette,
                              difficulty=difficulty)
            read = detect.read_face(img)
            chosen = chosen or read
            if read["found"] and read["confidence"] >= MIN_CONFIDENCE:
                chosen = read
                break
        located += bool(chosen["found"])
        samples.extend(chosen["samples"])
    return samples, frames, located


def run(n: int, difficulty: str, *, shipped: bool, seed: int) -> dict:
    rng = random.Random(seed)
    np.random.seed(seed)
    right = perfect = silent = located = frames = agreed = 0

    for _ in range(n):
        truth = str(Cube().apply_many(random_scramble(25, rng)))
        palette = (STICKER_HARD if difficulty == "hard" and rng.random() < 0.5
                   else STICKER_BGR)
        samples, f, loc = read_cube(truth, rng, palette, difficulty,
                                    gate=shipped, tries=8)
        frames += f
        located += loc
        result = detect.classify(
            samples, is_valid=is_real_cube if shipped else None)
        got = result["facelets"]
        agreed += bool(result.get("agreed"))
        right += sum(a == b for a, b in zip(got, truth))
        if got == truth:
            perfect += 1
        elif is_real_cube(got):
            silent += 1

    return {
        "grid": 100 * located / (6 * n),
        "sticker": 100 * right / (54 * n),
        "cube": 100 * perfect / n,
        "silent": 100 * silent / n,
        "agreed": 100 * agreed / n,
        "frames": frames / (6 * n),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--easy", type=int, default=25)
    p.add_argument("--hard", type=int, default=40)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()

    print(f"{'photos':7} {'mode':<12} {'grid':>7} {'sticker':>8} {'cube':>7} "
          f"{'silent':>7} {'agreed':>7} {'frames':>7}")
    for level, n in (("easy", a.easy), ("hard", a.hard)):
        if not n:
            continue
        for label, shipped in (("one frame", False), ("as shipped", True)):
            t0 = time.time()
            r = run(n, level, shipped=shipped, seed=a.seed)
            print(f"{level:7} {label:<12} {r['grid']:6.1f}% {r['sticker']:7.1f}% "
                  f"{r['cube']:6.1f}% {r['silent']:6.1f}% {r['agreed']:6.1f}% "
                  f"{r['frames']:6.2f}   ({time.time() - t0:.0f}s, {n} cubes)")
    print("\nsilent = wrong AND looked like a real cube, so the user got no warning")


if __name__ == "__main__":
    main()
