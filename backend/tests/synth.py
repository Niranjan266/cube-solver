"""
Render synthetic photos of cube faces so the vision stack can be measured
offline, without a cube and a webcam.

Two difficulty levels:

``easy``  - flat on, even light. What a scanner demo looks like.
``hard``  - what a real phone actually produces: the face tilted in 3D, a
            different exposure and white balance on every shot (auto-exposure
            re-metering as you turn the cube), a specular highlight, a soft
            shadow across one corner, motion blur, sensor noise, and a
            cluttered background full of rectangles that look like stickers.

The hard preset is the one that matters. If the pipeline survives it, it will
survive a kitchen table.
"""

from __future__ import annotations

import random
from typing import Dict, List, Tuple

import cv2
import numpy as np

# BGR colours of a typical retail cube, deliberately un-saturated
STICKER_BGR: Dict[str, tuple] = {
    "U": (232, 236, 238),   # white
    "D": (40, 205, 240),    # yellow
    "F": (52, 138, 22),     # green
    "B": (168, 82, 20),     # blue
    "R": (36, 32, 190),     # red
    "L": (24, 96, 226),     # orange
}

# a second, meaner palette: red and orange much closer together
STICKER_HARD: Dict[str, tuple] = {
    "U": (226, 230, 225),
    "D": (62, 198, 222),
    "F": (72, 142, 48),
    "B": (162, 92, 38),
    "R": (46, 44, 172),
    "L": (42, 108, 208),
}


def _clutter(size: int, rng: random.Random) -> np.ndarray:
    """A background with plenty of sticker-shaped decoys."""
    img = np.zeros((size, size, 3), np.uint8)
    img[:] = (rng.randint(28, 105),) * 3
    for _ in range(rng.randint(4, 9)):
        x, y = rng.randint(-40, size), rng.randint(-40, size)
        w, h = rng.randint(30, 110), rng.randint(30, 110)
        col = (rng.randint(20, 190), rng.randint(20, 190), rng.randint(20, 190))
        cv2.rectangle(img, (x, y), (x + w, y + h), col, -1)
        cv2.rectangle(img, (x, y), (x + w, y + h), (15, 15, 15), 2)
    return img


def _flat_face(colours: List[str], side: int, palette: Dict[str, tuple]) -> np.ndarray:
    """The face, straight on, on a black plastic body."""
    img = np.zeros((side, side, 3), np.uint8)
    cell = side // 3
    pad = max(2, int(cell * 0.075))
    for i, col in enumerate(colours):
        r, c = divmod(i, 3)
        x, y = c * cell, r * cell
        cv2.rectangle(img, (x + pad, y + pad),
                      (x + cell - pad, y + cell - pad), palette[col], -1)
    return img


def render_face(
    colours: List[str],
    size: int = 480,
    rng: random.Random | None = None,
    palette: Dict[str, tuple] | None = None,
    difficulty: str = "easy",
) -> np.ndarray:
    rng = rng or random.Random()
    palette = palette or STICKER_BGR
    hard = difficulty == "hard"

    face_px = int(size * (0.60 if hard else 0.72))
    face = _flat_face(colours, face_px, palette)

    bg = _clutter(size, rng) if hard else None
    if bg is None:
        bg = np.zeros((size, size, 3), np.uint8)
        bg[:] = (rng.randint(30, 90),) * 3
        cv2.circle(bg, (rng.randint(0, size), rng.randint(0, size)),
                   size // 3, (rng.randint(20, 120),) * 3, -1)

    # --- place the face in the frame, tilted in 3D if we are being mean ----- #
    m = (size - face_px) // 2
    dst = np.float32([[m, m], [m + face_px, m],
                      [m + face_px, m + face_px], [m, m + face_px]])
    if hard:
        jitter = face_px * 0.16
        dst += np.float32([[rng.uniform(-jitter, jitter), rng.uniform(-jitter, jitter)]
                           for _ in range(4)])
        dst += np.float32([[rng.uniform(-m * .5, m * .5), rng.uniform(-m * .5, m * .5)]] * 4)
    else:
        dst += np.float32([[rng.uniform(-6, 6), rng.uniform(-6, 6)]] * 4)

    src = np.float32([[0, 0], [face_px, 0], [face_px, face_px], [0, face_px]])
    warp = cv2.getPerspectiveTransform(src, dst)

    body = cv2.warpPerspective(
        np.full_like(face, 18), warp, (size, size),
        borderMode=cv2.BORDER_TRANSPARENT, dst=bg.copy())
    hull = cv2.convexHull(dst.astype(np.int32))
    cv2.fillConvexPoly(body, cv2.convexHull(
        (dst + np.float32([[-6, -6], [6, -6], [6, 6], [-6, 6]])).astype(np.int32)),
        (18, 18, 18))
    img = cv2.warpPerspective(face, warp, (size, size),
                              borderMode=cv2.BORDER_TRANSPARENT, dst=body)
    del hull

    # --- lighting ---------------------------------------------------------- #
    gx, gy = np.meshgrid(np.linspace(-1, 1, size), np.linspace(-1, 1, size))
    swing = 0.34 if hard else 0.22
    gain = 1.0 + swing * (gx * rng.uniform(-1, 1) + gy * rng.uniform(-1, 1))
    img = np.clip(img * gain[..., None], 0, 255).astype(np.uint8)

    if hard:  # a soft shadow falling across part of the face
        sh = np.ones((size, size), np.float32)
        pts = np.int32([[rng.randint(-size // 2, size), rng.randint(-size // 2, size)],
                        [rng.randint(0, size), size], [size, size], [size, 0]])
        cv2.fillPoly(sh, [pts], rng.uniform(0.55, 0.8))
        sh = cv2.GaussianBlur(sh, (0, 0), size * 0.08)
        img = np.clip(img * sh[..., None], 0, 255).astype(np.uint8)

    # specular highlight
    hl = np.zeros_like(img)
    cell = face_px // 3
    cv2.circle(hl, (rng.randint(m, m + face_px), rng.randint(m, m + face_px)),
               int(cell * (0.55 if hard else 0.35)), (255, 255, 255), -1)
    hl = cv2.GaussianBlur(hl, (0, 0), cell * 0.3)
    img = cv2.addWeighted(img, 1.0, hl, 0.6 if hard else 0.45, 0)

    if hard:
        # auto-exposure and auto-white-balance drift, different on every shot
        img = np.clip(img.astype(np.float32) * rng.uniform(0.72, 1.32), 0, 255)
        cast = np.float32([rng.uniform(0.80, 1.22) for _ in range(3)])
        img = np.clip(img * cast, 0, 255).astype(np.uint8)
        if rng.random() < 0.5:                       # slight motion blur
            k = rng.choice([3, 5])
            img = cv2.blur(img, (k, 1) if rng.random() < 0.5 else (1, k))

    sigma = 8 if hard else 5
    img = np.clip(img.astype(np.int16) + np.random.normal(0, sigma, img.shape),
                  0, 255).astype(np.uint8)
    render_face.last_quad = dst.copy()   # where the face really is, for benchmarks
    return img


def cell_centres(quad: np.ndarray) -> np.ndarray:
    """The true centre of each of the nine stickers, in image pixels."""
    src = np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])
    warp = cv2.getPerspectiveTransform(src, quad.astype(np.float32))
    pts = np.float32([[[(c + 0.5) / 3, (r + 0.5) / 3]
                       for r in range(3) for c in range(3)]])
    return cv2.perspectiveTransform(pts, warp)[0]


def render_cube(facelets: str, rng: random.Random | None = None,
                palette: Dict[str, tuple] | None = None,
                difficulty: str = "easy") -> Dict[str, np.ndarray]:
    rng = rng or random.Random()
    out, quads = {}, {}
    for i, f in enumerate("URFDLB"):
        out[f] = render_face(list(facelets[i * 9: i * 9 + 9]), rng=rng,
                             palette=palette, difficulty=difficulty)
        quads[f] = render_face.last_quad
    render_cube.last_quads = quads
    return out
