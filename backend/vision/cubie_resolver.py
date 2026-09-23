"""
Resolving the 54 samples into colours by working on *pieces*, not stickers.

Credit where it is due: this is the approach used by
`dwalton76/rubiks-color-resolver <https://github.com/dwalton76/rubiks-color-resolver>`_,
and the CIE Lab / CIEDE2000 colour distance is what
`kkoomen/qbr <https://github.com/kkoomen/qbr>`_ uses. Both are worth reading.

Why it beats classifying stickers one at a time
-----------------------------------------------
A cube is not 54 independent stickers. It is 8 corner pieces, 12 edge pieces
and 6 fixed centres, and the *pieces are known in advance*: the corner carrying
white must also carry exactly one of green/blue and one of red/orange, and so
on. There are only 8 possible corner colour-triples and 12 possible edge
colour-pairs on any 3x3 cube ever made.

So instead of asking "what colour is this sticker?" 54 times, ask "which of the
eight corner pieces is this?" eight times, and "which of the twelve edge pieces
is this?" twelve times. Both are assignment problems and both are solved
optimally in milliseconds. Two things fall out for free:

* every corner gets three colours that can actually sit together on a corner,
  and every edge gets a legal pair - guessing an impossible piece is no longer
  representable;
* a sticker that is ambiguous on its own (yellow or orange under warm light)
  gets decided by the *other two stickers on the same piece*, which are usually
  not ambiguous at all.

The per-face exposure correction from :mod:`vision.colour` still runs first.
Neither reference project needs it, because both assume one fixed lighting
setup - a phone re-metering between six handheld shots does not.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np

from cube.cubie import CORNER_FACES, CORNER_IDX, EDGE_FACES, EDGE_IDX

FACE_ORDER = "URFDLB"
CENTRES = [i * 9 + 4 for i in range(6)]


# --------------------------------------------------------------------------- #
# colour space
# --------------------------------------------------------------------------- #

def bgr_to_lab(bgr: np.ndarray) -> np.ndarray:
    """(n, 3) BGR 0-255 -> (n, 3) CIE L*a*b* with the usual D65 white point."""
    x = np.clip(np.asarray(bgr, np.float64).reshape(-1, 3), 0, 255) / 255.0
    rgb = x[:, ::-1]
    lin = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92) * 100.0
    m = np.array([[0.4124, 0.3576, 0.1805],
                  [0.2126, 0.7152, 0.0722],
                  [0.0193, 0.1192, 0.9505]])
    xyz = lin @ m.T / np.array([95.047, 100.0, 108.883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16.0 / 116.0)
    return np.stack([116 * f[:, 1] - 16,
                     500 * (f[:, 0] - f[:, 1]),
                     200 * (f[:, 1] - f[:, 2])], axis=1)


def delta_e_2000(lab1: np.ndarray, lab2: np.ndarray) -> np.ndarray:
    """
    CIEDE2000 difference between every row of `lab1` and every row of `lab2`.

    Plain Euclidean distance in Lab treats a given numerical gap as equally
    visible everywhere, which it is not - the space is stretched in the
    yellow-orange region, exactly where cube colours are hardest to tell apart.
    CIEDE2000 corrects for that, so "these two look alike to a person" and
    "these two are close in the metric" finally mean the same thing.
    """
    L1, a1, b1 = (lab1[:, None, 0], lab1[:, None, 1], lab1[:, None, 2])
    L2, a2, b2 = (lab2[None, :, 0], lab2[None, :, 1], lab2[None, :, 2])

    C1 = np.hypot(a1, b1)
    C2 = np.hypot(a2, b2)
    Cbar = (C1 + C2) / 2.0
    G = 0.5 * (1 - np.sqrt(Cbar ** 7 / (Cbar ** 7 + 25.0 ** 7 + 1e-12)))
    a1p, a2p = a1 * (1 + G), a2 * (1 + G)
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)

    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360

    dLp = L2 - L1
    dCp = C2p - C1p
    dhp = h2p - h1p
    dhp = np.where(dhp > 180, dhp - 360, np.where(dhp < -180, dhp + 360, dhp))
    dhp = np.where(C1p * C2p == 0, 0.0, dhp)
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dhp) / 2.0)

    Lbar = (L1 + L2) / 2.0
    Cbarp = (C1p + C2p) / 2.0
    hsum = h1p + h2p
    hbar = np.where(np.abs(h1p - h2p) > 180, (hsum + 360) / 2.0, hsum / 2.0)
    hbar = np.where(C1p * C2p == 0, hsum, hbar)

    T = (1 - 0.17 * np.cos(np.radians(hbar - 30))
           + 0.24 * np.cos(np.radians(2 * hbar))
           + 0.32 * np.cos(np.radians(3 * hbar + 6))
           - 0.20 * np.cos(np.radians(4 * hbar - 63)))
    SL = 1 + (0.015 * (Lbar - 50) ** 2) / np.sqrt(20 + (Lbar - 50) ** 2)
    SC = 1 + 0.045 * Cbarp
    SH = 1 + 0.015 * Cbarp * T
    RT = (-2 * np.sqrt(Cbarp ** 7 / (Cbarp ** 7 + 25.0 ** 7 + 1e-12))
          * np.sin(np.radians(60 * np.exp(-(((hbar - 275) / 25.0) ** 2)))))

    return np.sqrt((dLp / SL) ** 2 + (dCp / SC) ** 2 + (dHp / SH) ** 2
                   + RT * (dCp / SC) * (dHp / SH))


# --------------------------------------------------------------------------- #
# the pieces a 3x3 cube can have
# --------------------------------------------------------------------------- #

def _assign(cost: np.ndarray) -> np.ndarray:
    """Optimal one-to-one assignment; falls back to greedy without scipy."""
    try:
        from scipy.optimize import linear_sum_assignment

        return linear_sum_assignment(cost)[1]
    except Exception:
        n = cost.shape[0]
        out = np.full(n, -1, int)
        taken = set()
        for i in np.argsort(cost.min(axis=1)):
            for j in np.argsort(cost[i]):
                if j not in taken:
                    taken.add(int(j))
                    out[i] = j
                    break
        return out


FACE_OF = np.arange(54) // 9


def _one_pass(sticker_cost: np.ndarray) -> Tuple[List[str], np.ndarray, Dict[str, float]]:
    """
    Match every corner and edge to a real cube piece.

    `sticker_cost` is (54, 6): how much it costs to call each sticker each of
    the six colours. Any sensible colour metric can produce it.
    """
    face_of_colour = {f: i for i, f in enumerate(FACE_ORDER)}

    letters = ["?"] * 54
    colour_index = np.zeros(54, int)
    for i, f in enumerate(FACE_ORDER):
        letters[i * 9 + 4] = f
        colour_index[i * 9 + 4] = i

    detail = {}
    for name, slots, pieces in (("corners", CORNER_IDX, CORNER_FACES),
                                ("edges", EDGE_IDX, EDGE_FACES)):
        k = len(pieces[0])                   # 3 for corners, 2 for edges
        n = len(pieces)

        flat = np.concatenate([np.asarray(s) for s in slots])
        d = sticker_cost[flat].reshape(n, k, 6)

        # cost of calling slot i "piece j", trying every way round the piece
        # can sit in the slot (3 rotations for a corner, 2 for an edge)
        cost = np.full((n, n), np.inf)
        best_turn = np.zeros((n, n), int)
        for j, piece in enumerate(pieces):
            cols = [face_of_colour[c] for c in piece]
            for t in range(k):
                turned = cols[t:] + cols[:t]
                c = sum(d[:, s, turned[s]] for s in range(k))
                better = c < cost[:, j]
                cost[better, j] = c[better]
                best_turn[better, j] = t

        pick = _assign(cost)
        for i, j in enumerate(pick):
            t = best_turn[i, j]
            piece = pieces[j]
            for s, idx in enumerate(slots[i]):
                letters[idx] = piece[(s + t) % k]
                colour_index[idx] = face_of_colour[piece[(s + t) % k]]
        detail[name] = float(cost[np.arange(n), pick].sum())
    return letters, colour_index, detail


def resolve(samples: Sequence[Sequence[float]], passes: int = 4) -> Dict:
    """
    54 raw BGR samples -> a 54-character facelet string.

    Runs the piece matching a few times, and between passes re-estimates one
    colour shift per face from how far that face's stickers landed from the
    colours they were matched to.  That soaks up the exposure and white-balance
    change between the six handheld photos, which is the one thing the fixed-rig
    projects this is based on never have to deal with.

    The six centres anchor everything: a centre *is* its face's colour, so the
    correction cannot quietly slide all six colours somewhere else.
    """
    from . import colour as _colour        # local import: avoids a cycle

    raw = np.clip(np.asarray(samples, np.float64).reshape(-1, 3), 4.0, 255.0)
    X = _colour.features(raw)
    offsets = np.zeros((6, X.shape[1]))
    letters, colour_index, detail = _one_pass(np.zeros((54, 6)))

    for _ in range(passes):
        Xc = X - offsets[FACE_OF]
        box = Xc[CENTRES]                    # the six reference colours
        cost = np.sqrt(((Xc[:, None, :] - box[None, :, :]) ** 2).sum(axis=2))
        letters, colour_index, detail = _one_pass(cost)

        # re-estimate one colour shift per face from how far that face's
        # stickers landed from the colours they were matched to
        resid = X - box[colour_index]
        new = np.stack([np.median(resid[FACE_OF == f], axis=0) for f in range(6)])
        if np.abs(new - offsets).max() < 0.005:
            offsets = new
            break
        offsets = new

    return {"facelets": "".join(letters),
            "cornerCost": round(detail["corners"], 1),
            "edgeCost": round(detail["edges"], 1),
            "faceShift": [round(float(np.linalg.norm(o)), 2) for o in offsets]}
