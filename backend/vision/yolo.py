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

    areas = (xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])
    xyxy = xyxy[np.argsort(-areas)][:9]
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
