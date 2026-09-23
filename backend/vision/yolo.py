"""
Optional YOLO sticker detector.

There is no ready-made Rubik's-cube sticker model on the Hugging Face Hub
today, so this module is written as a *slot* rather than a promise:

* point ``CUBE_YOLO_MODEL`` at any local Ultralytics ``.pt`` file, **or**
* point ``CUBE_YOLO_HF_REPO`` (+ optional ``CUBE_YOLO_HF_FILE``) at a Hub repo
  and the weights are pulled with ``huggingface_hub``.

If neither is set, or ultralytics is not installed, :func:`available` returns
False and the API quietly stays on the classical detector.  Train your own with
``tools/train_yolo.py`` - it uses the cube datasets that *are* on the Hub.
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

import numpy as np

_MODEL = None
_TRIED = False
_REASON = "not loaded yet"


def _load():
    global _MODEL, _TRIED, _REASON
    if _TRIED:
        return _MODEL
    _TRIED = True

    path: Optional[str] = os.getenv("CUBE_YOLO_MODEL")
    repo = os.getenv("CUBE_YOLO_HF_REPO")
    if not path and repo:
        try:
            from huggingface_hub import hf_hub_download

            path = hf_hub_download(
                repo_id=repo,
                filename=os.getenv("CUBE_YOLO_HF_FILE", "best.pt"),
            )
        except Exception as exc:
            _REASON = f"could not download weights from {repo}: {exc}"
            return None
    if not path:
        _REASON = "no CUBE_YOLO_MODEL or CUBE_YOLO_HF_REPO configured"
        return None
    try:
        from ultralytics import YOLO

        _MODEL = YOLO(path)
        _REASON = f"loaded {path}"
    except Exception as exc:
        _REASON = f"ultralytics not usable: {exc}"
    return _MODEL


def available() -> bool:
    return _load() is not None


def status() -> str:
    _load()
    return _REASON


def _pick_nine(xyxy: np.ndarray) -> np.ndarray:
    """Choose the nine boxes that best form one 3x3 face.

    A model trained on multi-face photos (e.g. the Hub dataset prepared by
    ``tools/train_yolo.py``) returns up to 27 boxes from three faces.  Taking
    the nine largest mixes faces, so every box is tried as the *centre*
    sticker and its nine nearest neighbours are taken - "near" meaning close in
    position (in sticker widths), in box shape and in size.  Shape matters
    most: on an angled cube the top face gives wide, flat boxes and the side
    faces tall, narrow ones.  The candidate cluster that is tightest, most
    uniform and slightly larger wins.  Exactly nine boxes are returned as-is.

    On the 197 labelled images of the Hub dataset this picks nine stickers of
    a single face 80% of the time (top-9-by-area: 4%).
    """
    if len(xyxy) <= 9:
        return xyxy
    w = np.maximum(xyxy[:, 2] - xyxy[:, 0], 1e-6)
    h = np.maximum(xyxy[:, 3] - xyxy[:, 1], 1e-6)
    side = np.sqrt(w * h)
    shape = np.log(w / h)
    centres = np.stack([(xyxy[:, 0] + xyxy[:, 2]) / 2, (xyxy[:, 1] + xyxy[:, 3]) / 2], 1)
    global_side = float(np.median(side))
    pos = np.linalg.norm(centres[:, None, :] - centres[None, :, :], axis=2)
    feat = (pos / global_side
            + _SHAPE_W * np.abs(shape[:, None] - shape[None, :])
            + np.abs(np.log(side[:, None] / side[None, :])))

    best, best_score = None, np.inf
    for i in range(len(xyxy)):
        nn = np.argsort(feat[i])[:9]
        med = float(np.median(side[nn]))
        # centre-to-corner of a 3x3 grid is ~1.4 pitches; anything wider means
        # the cluster is reaching into another face or into stray detections
        radius = float(pos[i, nn].max()) / med
        score = (radius
                 + 2.0 * float(np.std(side[nn])) / med
                 + _SHAPE_W * float(np.std(shape[nn]))
                 - 0.3 * np.log(med / global_side))
        if score < best_score:
            best, best_score = nn, score
    return xyxy[best]


_SHAPE_W = 10.0  # weight of box aspect ratio when grouping stickers into faces


def find_grid(
    image: np.ndarray, conf: float = 0.25
) -> Optional[List[Tuple[int, int, int, int]]]:
    """Nine sticker boxes in reading order, or None if the model is unsure."""
    model = _load()
    if model is None:
        return None
    try:
        res = model.predict(image, conf=conf, verbose=False)[0]
        xyxy = res.boxes.xyxy.cpu().numpy()
    except Exception:
        return None
    if len(xyxy) < 9:
        return None

    xyxy = _pick_nine(xyxy)
    centres = np.stack(
        [(xyxy[:, 0] + xyxy[:, 2]) / 2, (xyxy[:, 1] + xyxy[:, 3]) / 2], axis=1
    )
    order: List[int] = []
    by_y = np.argsort(centres[:, 1])
    for r in range(3):
        row = by_y[r * 3: r * 3 + 3]
        order.extend(row[np.argsort(centres[row][:, 0])].tolist())
    return [
        (
            int(xyxy[i][0]),
            int(xyxy[i][1]),
            int(xyxy[i][2] - xyxy[i][0]),
            int(xyxy[i][3] - xyxy[i][1]),
        )
        for i in order
    ]
