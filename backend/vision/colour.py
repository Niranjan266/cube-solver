"""
Turning 54 colour samples into 54 face letters.

The naive approach - threshold each sticker's hue on its own - is what makes
most cube scanners misread red as orange.  It fails because a phone re-meters
between shots: every face arrives with its own exposure and its own white
balance, so the same orange sticker is a different RGB on each of the six
photos.

So model that instead of fighting it:

    observed(face i, sticker j)  =  gain(i)  x  colour(label(i, j))

In *log chromaticity* - (log R - log G, log B - log G) - that becomes plain
addition, and two useful things fall out for free:

* per-sticker brightness cancels exactly, so a shadow across half the face or a
  glare spot does not move a sticker's coordinates at all;
* per-shot exposure cancels exactly, and the white-balance cast becomes a
  single 2-D offset per face, which we can estimate.

We then alternate: estimate the six colours, estimate the six face offsets,
repeat.  Assignment is *balanced* (exactly nine stickers per colour) and the
six centre stickers are pinned, since a centre is by definition its own face's
colour.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np

FACE_ORDER = "URFDLB"
Sample = Sequence[float]  # BGR


#: how much the brightness cue counts next to the two colour cues.  Tuned on
#: rendered photos: 0 loses yellow-vs-orange, much above 1 loses everything to
#: shadows.  0.8 was the best of the sweep on both an easy and a mean palette.
LUMA_WEIGHT = 0.8


def log_chroma(samples: np.ndarray) -> np.ndarray:
    """(n, 3) BGR -> (n, 2) log-chromaticity, immune to brightness and exposure."""
    x = np.asarray(samples, np.float64).reshape(-1, 3)
    x = np.clip(x, 6.0, None)              # keep the logs finite on near-black
    b, g, r = x[:, 0], x[:, 1], x[:, 2]
    return np.stack([np.log(r) - np.log(g), np.log(b) - np.log(g)], axis=1)


def features(samples: np.ndarray, faces: int = 6) -> np.ndarray:
    """
    Two colour axes plus one brightness axis.

    Colour alone cannot separate yellow from orange reliably - they differ
    mostly in one direction and warm light pushes them together.  Brightness
    tells them apart easily (yellow is far lighter), but raw brightness is
    useless because of shadows and exposure.  So use brightness *relative to
    the rest of the same face*, which cancels the exposure of that shot, and
    give it less weight than the colour axes.
    """
    raw = np.asarray(samples, np.float64).reshape(-1, 3)
    X = log_chroma(raw)
    lum = np.log(np.clip(raw.sum(axis=1), 18.0, None))
    for f in range(faces):
        s = slice(f * 9, (f + 1) * 9)
        lum[s] -= np.median(lum[s])
    return np.concatenate([X, (lum * LUMA_WEIGHT)[:, None]], axis=1)


#: two samples this close in feature space are certainly the same colour
SAME_COLOUR = 0.22
#: this far apart, certainly different
DIFFERENT_COLOUR = 0.60


def face_quality(samples: Sequence[Sample]) -> float:
    """
    How cleanly do the nine stickers on one face separate into colours? 0 to 1.

    A face where every sticker is either clearly the same as its neighbour or
    clearly different is safe to capture.  A face with two groups sitting in
    the grey area between - which is what dim or very warm light does to yellow
    and orange - is not, and it is better to ask the user to hold it again than
    to record a coin flip.
    """
    x = np.asarray(samples, np.float64).reshape(-1, 3)
    if len(x) < 2:
        return 1.0
    f = log_chroma(x)
    lum = np.log(np.clip(x.sum(axis=1), 18.0, None))
    f = np.concatenate([f, ((lum - np.median(lum)) * LUMA_WEIGHT)[:, None]], axis=1)

    # single-link grouping at the "certainly the same" radius
    groups: List[List[int]] = []
    for i in range(len(f)):
        hit = [g for g in groups
               if min(np.linalg.norm(f[i] - f[j]) for j in g) <= SAME_COLOUR]
        if hit:
            merged = [i]
            for g in hit:
                merged += g
                groups.remove(g)
            groups.append(merged)
        else:
            groups.append([i])

    if len(groups) < 2:
        return 1.0
    gap = min(
        min(np.linalg.norm(f[i] - f[j]) for i in a for j in b)
        for n, a in enumerate(groups) for b in groups[n + 1:]
    )
    span = DIFFERENT_COLOUR - SAME_COLOUR
    return float(np.clip((gap - SAME_COLOUR) / span, 0.0, 1.0))


def balanced_assign(cost: np.ndarray, per_class: int) -> np.ndarray:
    """Assign rows to classes so each class receives exactly `per_class` rows."""
    n, k = cost.shape
    try:
        from scipy.optimize import linear_sum_assignment

        _, col = linear_sum_assignment(np.repeat(cost, per_class, axis=1))
        return col // per_class
    except Exception:
        pass
    order = np.argsort(cost.min(axis=1) - np.partition(cost, 1, axis=1)[:, 1])
    room = [per_class] * k
    out = np.full(n, -1, dtype=int)
    for i in order:
        for c in np.argsort(cost[i]):
            if room[c]:
                room[c] -= 1
                out[i] = c
                break
    for _ in range(400):                    # pairwise repair
        improved = False
        for i in range(n):
            for j in range(i + 1, n):
                a, b = out[i], out[j]
                if a == b:
                    continue
                if cost[i, b] + cost[j, a] < cost[i, a] + cost[j, b] - 1e-9:
                    out[i], out[j] = b, a
                    improved = True
        if not improved:
            break
    return out


def _hex(bgr: Sequence[float]) -> str:
    b, g, r = (int(max(0, min(255, v))) for v in bgr)
    return f"#{r:02x}{g:02x}{b:02x}"


def _repair(labels: np.ndarray, cost: np.ndarray, is_valid, faces: int):
    """
    If the reading is not a physically possible cube, look for the cheapest fix.

    Because exactly nine stickers carry each colour, the smallest possible
    change is to *swap* two stickers' labels - which is precisely the mistake
    the classifier makes when two colours sit close together (yellow and orange
    under warm light).  Being a real cube is a very strong constraint, so trying
    the cheapest swaps in order finds the true reading almost every time.
    """
    n = len(labels)
    letters = np.array(list(FACE_ORDER))
    centres = set((np.arange(faces) * 9 + 4).tolist())

    def word(lab):
        return "".join(letters[lab])

    if is_valid(word(labels)):
        return labels, 0

    base = cost[np.arange(n), labels]
    pairs = []
    for i in range(n):
        if i in centres:
            continue
        for j in range(i + 1, n):
            if j in centres or labels[i] == labels[j]:
                continue
            delta = (cost[i, labels[j]] + cost[j, labels[i]]) - (base[i] + base[j])
            pairs.append((delta, i, j))
    pairs.sort()

    for _, i, j in pairs[:400]:
        trial = labels.copy()
        trial[i], trial[j] = labels[j], labels[i]
        if is_valid(word(trial)):
            return trial, 1

    for a in range(min(30, len(pairs))):                 # two swaps, if we must
        _, i, j = pairs[a]
        first = labels.copy()
        first[i], first[j] = labels[j], labels[i]
        for b in range(a + 1, min(30, len(pairs))):
            _, k, l = pairs[b]
            if len({i, j, k, l}) < 4:
                continue
            trial = first.copy()
            trial[k], trial[l] = first[l], first[k]
            if is_valid(word(trial)):
                return trial, 2
    return labels, -1


def _explains(samples: np.ndarray, facelets: str, faces: int = 6) -> float:
    """
    How well does a candidate reading account for what the camera saw?

    Fit the per-face colour shifts that this reading implies, then add up how
    far every sticker still sits from the colour it was called. Lower is a
    better explanation of the samples.
    """
    X = features(samples, faces)
    idx = np.array([FACE_ORDER.index(c) for c in facelets])
    face_of = np.arange(faces * 9) // 9
    centres = np.arange(faces) * 9 + 4
    offsets = np.zeros((faces, X.shape[1]))
    for _ in range(4):
        box = (X - offsets[face_of])[centres]
        resid = X - box[idx]
        offsets = np.stack(
            [np.median(resid[face_of == f], axis=0) for f in range(faces)]
        )
    Xc = X - offsets[face_of]
    box = Xc[centres]
    return float(np.linalg.norm(Xc - box[idx], axis=1).sum())


def classify(all_samples: Sequence[Sample], faces: int = 6, is_valid=None) -> Dict:
    """
    Read 54 colour samples two independent ways and let the cube decide.

    * :func:`classify_stickers` treats the 54 stickers as 54 decisions,
      constrained so that exactly nine end up each colour.
    * :func:`vision.cubie_resolver.resolve` treats them as 8 corner pieces and
      12 edge pieces and matches each to a real cube piece.

    They fail differently - the first by swapping two lookalike stickers, the
    second by mismatching a whole piece - and measured over 80 hard scans they
    never once failed on the same cube. So run both: if only one produced a
    physically possible cube, take it; if both did and they disagree, take
    whichever better explains the samples. Two methods agreeing is also the
    only honest confidence signal available here, and it is reported.
    """
    if faces == 6:
        try:
            from . import cubie_resolver

            piece = cubie_resolver.resolve(all_samples)["facelets"]
        except Exception:
            piece = None
    else:
        piece = None

    sticker = classify_stickers(all_samples, faces, is_valid)
    if piece is None or piece == sticker["facelets"]:
        sticker["agreed"] = piece is not None
        sticker["method"] = "both agree" if piece is not None else "stickers"
        return sticker

    raw = np.asarray(all_samples, np.float64)
    ok_sticker = is_valid(sticker["facelets"]) if is_valid else True
    ok_piece = is_valid(piece) if is_valid else True

    if ok_piece and not ok_sticker:
        chosen, how = piece, "pieces"
    elif ok_sticker and not ok_piece:
        chosen, how = sticker["facelets"], "stickers"
    elif not ok_sticker and not ok_piece:
        chosen, how = sticker["facelets"], "stickers"
    else:
        by_piece = _explains(raw, piece, faces)
        by_sticker = _explains(raw, sticker["facelets"], faces)
        chosen, how = ((piece, "pieces") if by_piece < by_sticker
                       else (sticker["facelets"], "stickers"))

    labels = np.array([FACE_ORDER.index(c) for c in chosen])
    out = dict(sticker)
    out["facelets"] = chosen
    out["agreed"] = False
    out["method"] = how
    out["palette"] = {
        FACE_ORDER[i]: _hex(np.median(raw[labels == i], axis=0))
        if (labels == i).any() else "#888888"
        for i in range(faces)
    }
    return out


def classify_stickers(all_samples: Sequence[Sample], faces: int = 6, is_valid=None) -> Dict:
    """
    54 BGR samples (face order U R F D L B, reading order inside a face)
    -> facelet string, per-sticker confidence, and a palette for the UI.

    `is_valid` is an optional ``facelets -> bool`` check.  Supplying it lets the
    classifier reject readings that could not come off a real cube and repair
    them, which is where most of the accuracy comes from.
    """
    n = faces * 9
    if len(all_samples) != n:
        raise ValueError(f"expected {n} colour samples, got {len(all_samples)}")

    raw = np.asarray(all_samples, np.float64)
    X = features(raw, faces)
    face_of = np.arange(n) // 9
    centres = np.arange(faces) * 9 + 4

    offsets = np.zeros((faces, X.shape[1]))
    means = X[centres].copy()
    labels = np.repeat(np.arange(faces), 9)

    for _ in range(12):
        Xc = X - offsets[face_of]
        cost = ((Xc[:, None, :] - means[None, :, :]) ** 2).sum(axis=2)
        # a centre sticker *is* its face's colour - no argument
        for k, ci in enumerate(centres):
            cost[ci] = 1e9
            cost[ci, k] = 0.0
        new = balanced_assign(cost, 9)

        for c in range(faces):                       # re-estimate the six colours
            sel = Xc[new == c]
            if len(sel):
                means[c] = np.median(sel, axis=0)
        resid = X - means[new]                       # re-estimate the six casts
        for f in range(faces):
            offsets[f] = np.median(resid[face_of == f], axis=0)
        offsets -= offsets.mean(axis=0)              # fix the free global shift

        if np.array_equal(new, labels):
            labels = new
            break
        labels = new

    Xc = X - offsets[face_of]
    final_cost = ((Xc[:, None, :] - means[None, :, :]) ** 2).sum(axis=2)
    for k, ci in enumerate(centres):
        final_cost[ci] = 1e9
        final_cost[ci, k] = 0.0

    repaired = 0
    if is_valid is not None:
        labels, repaired = _repair(labels, final_cost, is_valid, faces)

    palette = {}
    for i in range(faces):
        sel = raw[labels == i]
        palette[FACE_ORDER[i]] = _hex(np.median(sel, axis=0)) if len(sel) else "#888888"

    # Deliberately no per-sticker confidence here.  Two candidate measures were
    # tried - distance margin to the runner-up colour, and how cheap it would be
    # to swap this sticker with another - and both were measured against ground
    # truth on rendered photos.  Neither separated right from wrong: a misread
    # sticker is one whose *sample* was corrupted, so the model sits firmly in
    # the wrong cluster rather than hesitating between two.  A warning that
    # fires on every cube and is right 2% of the time is worse than no warning,
    # because it teaches people to ignore warnings.  What is left below is only
    # what actually carries information.
    return {
        "facelets": "".join(FACE_ORDER[c] for c in labels),
        "palette": palette,
        #: > 0 means the raw reading was not a possible cube and had to be
        #: corrected, which is a real reason to double-check
        "repairedSwaps": repaired,
    }
