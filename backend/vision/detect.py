"""
Reading a cube face from a photo.

The work is split in two, because the two halves fail for completely different
reasons and are best fixed separately:

* :mod:`vision.grid`   - *where* the nine stickers are.  Robust to tilt and to
  a cluttered desk; rectifies the face before sampling.
* :mod:`vision.colour` - *what colour* each one is.  Robust to the phone
  changing its exposure and white balance between shots.

This module is the thin layer that joins them and shapes the result for the
API.  The important promise it makes: if the grid was not found confidently,
say so, so the app can decline to capture rather than guess.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import cv2
import numpy as np

from . import colour as _colour
from . import grid as _grid

FACE_ORDER = "URFDLB"
Sample = Sequence[float]  # BGR

#: only this method is trusted enough to capture from automatically
GOOD_METHOD = "lattice"
#: and the nine colours have to separate at least this cleanly
MIN_FACE_QUALITY = 0.20

classify = _colour.classify
log_chroma = _colour.log_chroma


# --------------------------------------------------------------------------- #
# coarse labels, used only to tell whether a live frame has settled
# --------------------------------------------------------------------------- #

def rough_labels(samples: Sequence[Sample]) -> str:
    """A quick per-sticker guess, good enough to compare two frames."""
    arr = np.array(samples, np.float32).reshape(-1, 1, 3)
    hsv = cv2.cvtColor(np.clip(arr, 0, 255).astype(np.uint8),
                       cv2.COLOR_BGR2HSV).reshape(-1, 3)
    out = []
    for h, s, v in hsv:
        if s < 65 and v > 85:
            out.append("W")
        elif h < 9 or h >= 168:
            out.append("R")
        elif h < 23:
            out.append("O")
        elif h < 39:
            out.append("Y")
        elif h < 96:
            out.append("G")
        elif h < 142:
            out.append("B")
        else:
            out.append("R")
    return "".join(out)


def _hex(bgr: Sample) -> str:
    b, g, r = (int(max(0, min(255, v))) for v in bgr)
    return f"#{r:02x}{g:02x}{b:02x}"


# --------------------------------------------------------------------------- #
# one face
# --------------------------------------------------------------------------- #

def read_face(image: np.ndarray, quad=None, method: str = "given",
              confidence: float = 1.0) -> Dict:
    """Everything the app needs about one photo of one face."""
    if quad is None:
        quad, method, confidence = _grid.find_face(image)
    flat = _grid.rectify(image, quad)
    samples = _grid.sample_rectified(flat)

    h, w = image.shape[:2]
    polys = _grid.cell_polygons(quad)
    quality = _colour.face_quality(samples)
    return {
        "method": method,
        "confidence": confidence,
        "faceQuality": round(float(quality), 2),
        # "found" needs both halves happy: the grid was located properly *and*
        # the nine colours separate cleanly.  Anything less and the app keeps
        # looking rather than recording a guess.
        "found": method == GOOD_METHOD and quality >= MIN_FACE_QUALITY,
        "gridFound": method == GOOD_METHOD,
        "quad": [[float(x), float(y)] for x, y in quad],
        "cellsNorm": [[[round(x / w, 4), round(y / h, 4)] for x, y in poly]
                      for poly in polys],
        "samples": [[round(v, 1) for v in s] for s in samples],
        "hex": [_hex(s) for s in samples],
        "signature": rough_labels(samples),
    }


def scan_face(image: np.ndarray) -> Dict:
    return read_face(image)


def find_grid(image: np.ndarray) -> Tuple[List[Tuple[int, int, int, int]], str]:
    """Backwards-compatible box view of the grid (used by the YOLO path)."""
    quad, method, _ = _grid.find_face(image)
    boxes = []
    for poly in _grid.cell_polygons(quad):
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        boxes.append((int(min(xs)), int(min(ys)),
                      int(max(xs) - min(xs)), int(max(ys) - min(ys))))
    return boxes, method


def sample_cells(image: np.ndarray,
                 boxes: Sequence[Tuple[int, int, int, int]]) -> List[Sample]:
    """Sample nine axis-aligned boxes (the YOLO detector hands us these)."""
    out: List[Sample] = []
    for x, y, w, h in boxes:
        px, py = int(w * 0.24), int(h * 0.24)
        patch = image[y + py: y + h - py, x + px: x + w - px]
        if patch.size == 0:
            patch = image[max(0, y): y + h, max(0, x): x + w]
        flat = patch.reshape(-1, 3).astype(np.float64)
        keep = flat[(flat.max(axis=1) < 250) & (flat.min(axis=1) > 10)]
        if len(keep) < 8:
            keep = flat
        lum = keep.sum(axis=1)
        dim = keep[lum <= np.quantile(lum, 0.75)]
        if len(dim) >= 8:
            keep = dim
        out.append([float(v) for v in np.median(keep, axis=0)])
    return out


def face_payload(image: np.ndarray, boxes, method: str, samples) -> Dict:
    """Shape a YOLO-detected face like :func:`read_face` does."""
    h, w = image.shape[:2]
    return {
        "method": method,
        "confidence": 1.0,
        "faceQuality": round(float(_colour.face_quality(samples)), 2),
        "found": True,
        "gridFound": True,
        "quad": [],
        "cellsNorm": [[[round(b[0] / w, 4), round(b[1] / h, 4)],
                       [round((b[0] + b[2]) / w, 4), round(b[1] / h, 4)],
                       [round((b[0] + b[2]) / w, 4), round((b[1] + b[3]) / h, 4)],
                       [round(b[0] / w, 4), round((b[1] + b[3]) / h, 4)]]
                      for b in boxes],
        "samples": [[round(v, 1) for v in s] for s in samples],
        "hex": [_hex(s) for s in samples],
        "signature": rough_labels(samples),
    }


def decode_image(data: bytes, max_side: int = 900) -> np.ndarray:
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("could not decode image")
    h, w = img.shape[:2]
    if max(h, w) > max_side:
        s = max_side / max(h, w)
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return img
