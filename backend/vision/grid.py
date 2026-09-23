"""
Finding the nine stickers in a photo of one cube face.

The first version of this looked for nine separate squares and gave up if it
did not find exactly nine.  Held at an angle, or on a cluttered desk, that
failed about a third of the time and silently fell back to a fixed box in the
middle of the frame - which is where the wrong colours came from.

This version does what the eye does:

1. Collect *candidate* sticker squares from three different filters, so a
   sticker lost by one of them is usually caught by another.
2. Keep the ones whose size agrees with the median - a cube face is nine
   squares of the same size, which is a strong signal in a cluttered scene.
3. Take the outline of that group and reduce it to a **quadrilateral**.  We
   only need six or seven stickers to pin the outline down; the missing ones
   do not matter.
4. Check the group really spans a full 3x3 - top row to bottom row, left column
   to right column - so we never grid a partial face.
5. Rectify that quadrilateral to a square and read the nine cells off it.

Step 5 is what makes tilt harmless: the face is unwarped before sampling, so a
sticker photographed as a skewed diamond is still measured at its centre.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np

Quad = np.ndarray  # (4, 2) float32, ordered top-left, top-right, bottom-right, bottom-left


# --------------------------------------------------------------------------- #
# candidate squares
# --------------------------------------------------------------------------- #

def _binary_views(grey: np.ndarray) -> List[np.ndarray]:
    """Several ways of finding sticker borders, because none of them is reliable."""
    out = []
    smooth = cv2.bilateralFilter(grey, 7, 60, 60)

    edges = cv2.Canny(smooth, 30, 90)
    out.append(cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2))

    med = float(np.median(smooth))
    edges2 = cv2.Canny(smooth, max(10, 0.55 * med), min(255, 1.35 * med))
    out.append(cv2.dilate(edges2, np.ones((3, 3), np.uint8), iterations=2))

    # sticker gaps are dark lines: an adaptive threshold turns them into borders
    ad = cv2.adaptiveThreshold(smooth, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                               cv2.THRESH_BINARY_INV, 21, 8)
    out.append(cv2.morphologyEx(ad, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)))
    return out


def _squares(image: np.ndarray) -> List[np.ndarray]:
    """Convex four-sided blobs that could be a sticker. Returns 4x2 point arrays."""
    h, w = image.shape[:2]
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    frame = float(w * h)
    found: List[np.ndarray] = []

    for view in _binary_views(grey):
        contours, _ = cv2.findContours(view, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            area = cv2.contourArea(c)
            if area < 0.0025 * frame or area > 0.16 * frame:
                continue
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.09 * peri, True)
            if len(approx) != 4 or not cv2.isContourConvex(approx):
                continue
            pts = approx.reshape(4, 2).astype(np.float32)
            sides = [np.linalg.norm(pts[i] - pts[(i + 1) % 4]) for i in range(4)]
            if min(sides) < 1e-3 or max(sides) / min(sides) > 1.9:
                continue
            if area < 0.55 * max(sides) ** 2:            # too far from a square
                continue
            found.append(pts)

    # de-duplicate: the three filters see the same sticker
    kept: List[np.ndarray] = []
    for pts in sorted(found, key=lambda p: -cv2.contourArea(p)):
        c = pts.mean(axis=0)
        size = np.sqrt(cv2.contourArea(pts))
        if all(np.linalg.norm(c - k.mean(axis=0)) > 0.45 * size for k in kept):
            kept.append(pts)
    return kept


def _consistent(squares: Sequence[np.ndarray]) -> List[np.ndarray]:
    """Nine stickers are the same size. Keep the biggest group that agrees."""
    if len(squares) < 4:
        return list(squares)
    sizes = np.array([np.sqrt(cv2.contourArea(p)) for p in squares])
    best: List[np.ndarray] = []
    for ref in sizes:                       # tiny mode-seek over the sizes
        sel = [p for p, s in zip(squares, sizes) if 0.62 * ref <= s <= 1.55 * ref]
        if len(sel) > len(best):
            best = sel
    return best


# --------------------------------------------------------------------------- #
# quadrilateral
# --------------------------------------------------------------------------- #

def order_quad(pts: np.ndarray) -> Quad:
    pts = np.asarray(pts, np.float32).reshape(-1, 2)
    s, d = pts.sum(axis=1), np.diff(pts, axis=1).ravel()
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)],
                     pts[np.argmax(s)], pts[np.argmax(d)]], np.float32)


def _hull_to_quad(points: np.ndarray) -> Optional[Quad]:
    hull = cv2.convexHull(points.astype(np.float32))
    peri = cv2.arcLength(hull, True)
    for eps in np.linspace(0.01, 0.12, 14):
        approx = cv2.approxPolyDP(hull, eps * peri, True)
        if len(approx) == 4:
            return order_quad(approx.reshape(4, 2))
    if len(hull) >= 4:                       # fall back to the extreme corners
        return order_quad(hull.reshape(-1, 2))
    return None


def _plausible(quad: Optional[Quad], w: int, h: int) -> bool:
    if quad is None:
        return False
    if not np.isfinite(quad).all():
        return False
    area = cv2.contourArea(quad.astype(np.float32))
    if area < 0.035 * w * h or area > 0.96 * w * h:
        return False
    sides = [np.linalg.norm(quad[i] - quad[(i + 1) % 4]) for i in range(4)]
    if min(sides) < 1e-3 or max(sides) / min(sides) > 2.3:
        return False
    diags = [np.linalg.norm(quad[0] - quad[2]), np.linalg.norm(quad[1] - quad[3])]
    if max(diags) / max(min(diags), 1e-3) > 1.8:
        return False
    return cv2.isContourConvex(quad.astype(np.int32).reshape(-1, 1, 2))


def _covers_full_grid(quad: Quad, squares: Sequence[np.ndarray]) -> bool:
    """
    Do the detected stickers actually spread over all three rows and columns?

    Without this a face half-hidden behind a thumb would produce a tidy-looking
    quad around six stickers, and every colour after it would be read from the
    wrong place.
    """
    if len(squares) < 5:
        return False
    inv = cv2.getPerspectiveTransform(
        quad, np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]))
    cent = np.float32([[p.mean(axis=0) for p in squares]])
    uv = cv2.perspectiveTransform(cent, inv)[0]
    inside = uv[(uv[:, 0] > -0.05) & (uv[:, 0] < 1.05)
                & (uv[:, 1] > -0.05) & (uv[:, 1] < 1.05)]
    if len(inside) < 5:
        return False
    cells = np.clip((inside * 3).astype(int), 0, 2)
    rows, cols = set(cells[:, 1].tolist()), set(cells[:, 0].tolist())
    return rows == {0, 1, 2} and cols == {0, 1, 2}


def _cluster(squares: Sequence[np.ndarray]) -> List[np.ndarray]:
    """
    Keep the squares that sit together, drop the ones that do not.

    A desk has plenty of sticker-sized rectangles on it - keys, tiles, the edge
    of a notebook - and they survive the size filter easily.  What they cannot
    fake is being packed into one small patch nine at a time, so seed a
    neighbourhood on each candidate and keep the densest one.
    """
    if len(squares) < 5:
        return list(squares)
    centres = np.float32([p.mean(axis=0) for p in squares])
    size = float(np.median([np.sqrt(cv2.contourArea(p)) for p in squares]))
    best: List[int] = []
    best_spread = 1e18
    for seed in centres:
        near = np.where(np.linalg.norm(centres - seed, axis=1) <= 3.4 * size)[0]
        if len(near) < 4:
            continue
        mid = centres[near].mean(axis=0)
        sel = np.where(np.linalg.norm(centres - mid, axis=1) <= 2.1 * size)[0]
        if len(sel) < 4:
            continue
        spread = float(np.linalg.norm(centres[sel] - mid, axis=1).mean())
        if len(sel) > len(best) or (len(sel) == len(best) and spread < best_spread):
            best, best_spread = sel.tolist(), spread
    return [squares[i] for i in best] if len(best) >= 5 else list(squares)


LATTICE = np.float32(
    [[(c + 0.5) / 3, (r + 0.5) / 3] for r in range(3) for c in range(3)]
)


def _refine(quad: Quad, squares: Sequence[np.ndarray]):
    """
    Fit the quadrilateral to the sticker lattice itself.

    The outline of the detected squares is only as good as its corners, and a
    corner sticker lost to shadow drags the whole quad in.  Every detected
    sticker centre, on the other hand, is a measurement of where the lattice
    is.  So: guess which of the nine positions each detected centre belongs to,
    fit a homography through all of them, and repeat.  Losing a sticker now
    costs one measurement out of nine instead of a whole corner.
    """
    if len(squares) < 4:
        return None, 0, set()
    centres = np.float32([p.mean(axis=0) for p in squares])
    best_quad, best_used, best_cells = None, 0, set()

    for _ in range(4):
        inv = cv2.getPerspectiveTransform(
            quad, np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]))
        uv = cv2.perspectiveTransform(centres[None, :, :], inv)[0]

        # each lattice position takes the single nearest detected centre
        src, dst = [], []
        taken = set()
        d = np.linalg.norm(uv[:, None, :] - LATTICE[None, :, :], axis=2)
        for k in np.argsort(d, axis=None):
            i, j = divmod(int(k), 9)
            if i in taken or j in [x[1] for x in src]:
                continue
            if d[i, j] > 0.12:
                break
            taken.add(i)
            src.append((i, j))
            dst.append(j)
        if len(src) < 4:
            return best_quad, best_used, best_cells

        pts_img = np.float32([centres[i] for i, _ in src])
        pts_lat = np.float32([LATTICE[j] for _, j in src])
        h, _ = cv2.findHomography(pts_lat, pts_img,
                                  cv2.RANSAC if len(src) >= 5 else 0, 3.0)
        if h is None:
            return best_quad, best_used, best_cells
        corners = cv2.perspectiveTransform(
            np.float32([[[0, 0], [1, 0], [1, 1], [0, 1]]]), h)[0]
        new = order_quad(corners)
        moved = float(np.abs(new - quad).max())
        quad, best_quad, best_used = new, new, len(src)
        best_cells = {j for _, j in src}
        if moved < 0.5:
            break
    return best_quad, best_used, best_cells


def _scale_agrees(quad: Quad, squares: Sequence[np.ndarray]) -> bool:
    """
    Does one grid cell come out about the size of one sticker?

    The lattice fit can otherwise settle happily onto a *shifted* 3x3 - using
    six real stickers but treating them as a different six positions - and a
    self-consistent wrong answer is the dangerous kind.  Comparing the fitted
    cell pitch against the measured sticker size catches it, because a shifted
    or partial fit always gets the scale wrong.
    """
    if not len(squares):
        return False
    sides = [np.linalg.norm(quad[i] - quad[(i + 1) % 4]) for i in range(4)]
    pitch = float(np.mean(sides)) / 3.0
    sticker = float(np.median([np.sqrt(cv2.contourArea(p)) for p in squares]))
    if pitch <= 1e-6:
        return False
    return 0.55 <= sticker / pitch <= 1.15


def centred_quad(w: int, h: int, fill: float = 0.72) -> Quad:
    side = min(w, h) * fill
    x0, y0 = (w - side) / 2, (h - side) / 2
    return np.float32([[x0, y0], [x0 + side, y0],
                       [x0 + side, y0 + side], [x0, y0 + side]])


def find_face(image: np.ndarray) -> Tuple[Quad, str, float]:
    """Return (quad, how-we-found-it, confidence 0..1)."""
    h, w = image.shape[:2]

    squares = _cluster(_consistent(_squares(image)))
    if len(squares) >= 5:
        quad = _hull_to_quad(np.concatenate(squares, axis=0))
        if _plausible(quad, w, h):
            fitted, used, cells = _refine(quad, squares)
            spans = {c % 3 for c in cells} == {0, 1, 2} and \
                    {c // 3 for c in cells} == {0, 1, 2}
            if fitted is not None and used >= 6 and spans and _plausible(fitted, w, h) \
                    and _scale_agrees(fitted, squares):
                return fitted, "lattice", round(min(1.0, 0.30 + 0.078 * used), 2)
            if _covers_full_grid(quad, squares):
                return quad, "outline", round(min(0.6, 0.25 + 0.04 * len(squares)), 2)

    # nothing usable: hand back the on-screen guide box, clearly marked
    return centred_quad(w, h), "guide-box", 0.0


# --------------------------------------------------------------------------- #
# sampling
# --------------------------------------------------------------------------- #

RECT = 300


def rectify(image: np.ndarray, quad: Quad, size: int = RECT) -> np.ndarray:
    dst = np.float32([[0, 0], [size, 0], [size, size], [0, size]])
    m = cv2.getPerspectiveTransform(quad.astype(np.float32), dst)
    return cv2.warpPerspective(image, m, (size, size), flags=cv2.INTER_AREA)


def sample_rectified(flat: np.ndarray) -> List[List[float]]:
    """
    One robust BGR reading per cell.

    Two nuisances get filtered out before the median: pixels that are clipped or
    nearly black (they carry no colour), and the brightest quarter of what
    remains, which is where a glare spot lives.
    """
    size = flat.shape[0]
    cell = size / 3
    half = cell * 0.30
    out: List[List[float]] = []
    for r in range(3):
        for c in range(3):
            cx, cy = (c + 0.5) * cell, (r + 0.5) * cell
            x0, y0 = int(cx - half), int(cy - half)
            x1, y1 = int(cx + half), int(cy + half)
            patch = flat[max(0, y0):y1, max(0, x0):x1].reshape(-1, 3).astype(np.float64)
            if patch.size == 0:
                out.append([0.0, 0.0, 0.0])
                continue
            keep = patch[(patch.max(axis=1) < 250) & (patch.min(axis=1) > 10)]
            if len(keep) < 8:
                keep = patch
            lum = keep.sum(axis=1)
            dim = keep[lum <= np.quantile(lum, 0.75)]
            if len(dim) >= 8:
                keep = dim
            out.append([float(v) for v in np.median(keep, axis=0)])
    return out


def cell_polygons(quad: Quad) -> List[List[List[float]]]:
    """The nine cell outlines back in image coordinates, for the camera overlay."""
    m = cv2.getPerspectiveTransform(
        np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]), quad.astype(np.float32))
    polys = []
    for r in range(3):
        for c in range(3):
            corners = np.float32([[[(c + 0.12) / 3, (r + 0.12) / 3],
                                   [(c + 0.88) / 3, (r + 0.12) / 3],
                                   [(c + 0.88) / 3, (r + 0.88) / 3],
                                   [(c + 0.12) / 3, (r + 0.88) / 3]]])
            polys.append(cv2.perspectiveTransform(corners, m)[0].tolist())
    return polys
