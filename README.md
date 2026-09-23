# Cube Solver

Hold your cube up to the camera. It reads each face on its own — no button to
press — fills the 3D cube in as it goes, and then walks you through **about 21
turns and never more than 30**, one arrow at a time.

Built for people who have never solved a cube. Nothing here assumes you know
what "R U R' U'" means. If you want that explained, it is in
[MANUAL.md](MANUAL.md) and behind the *What do R and U mean?* button in the app.

---

## Run it

**Windows** — double-click `run.bat`
**macOS / Linux** — `./run.sh`

Then open <http://127.0.0.1:8000>. First run installs dependencies and takes a
minute; after that it starts instantly.

Manual equivalent:

```bash
python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -r backend/requirements.txt
cd backend && uvicorn app:app --port 8000
```

---

## Using it

### 1. Get your cube into the app

**Camera** — press *Start scanning* and hold a face up. There is no shutter
button: the app watches the live picture, and once the nine colours hold steady
for about a second it captures that face itself, flashes, paints it onto the 3D
cube, and moves on to the next one. The green bar shows how close it is to
locking on. Pick one face to be the "front" and **keep that grip the whole
time**; the app tells you which face to show next and which way up to hold it.

**By hand** — the *Enter by hand* tab shows a flat map of the cube. Click a
colour, then click stickers. The centre squares are fixed, because on a real
cube centres never move — they are what makes a face "the red face".

Either way the app checks the cube is physically possible before solving. If a
colour was misread you get a specific message ("one corner is twisted in
place"), the least-confident stickers pulse on the flat map, and you can fix
them by hand.

### 2. Watch it solve

The screen is in three columns: **your cube goes in on the left, the 3D model
sits in the middle, and the turns you have to make are listed on the right.**

The right-hand panel shows one turn at a time — a big arrow for what your hand
does, the face name, and the same thing spelled out in words:

```
  ↑     Right face
        push the RIGHT column UP
        Turn the RIGHT face 90° clockwise (looking straight at it).
```

- **Play** runs the whole solve. **Next / Back** step one turn. Space = play,
  arrow keys = step, and the slider jumps anywhere.
- On the 3D cube, the layer about to move is outlined and a blue arrow curls
  round it showing which way to turn. The arrow always sits on the side of the
  cube nearest you and is drawn on top of everything, so it can never end up
  hidden round the back — and its direction is always the direction *you* see.
- **Read aloud** speaks each move so you can keep both hands on the cube.
- Drag the middle cube to look from any angle. The flat map underneath it always
  shows where your cube should be right now — compare it with the one in your
  hands if you lose your place.
- The page never scrolls or shifts while you play — the turn list scrolls inside
  its own box.

### 3. Two solving methods

| Method | Turns | Why |
|---|---|---|
| **Shortest** (default) | ~21, capped at 30 | Two-phase search, built in, no install. Fewer turns by hand means fewer chances to go wrong. The cube looks scrambled until near the end — that is normal. |
| **Learn** | ~140 | Layer-by-layer. Every move belongs to a named stage — bottom cross, bottom corners, middle layer, top cross, and so on. Slower, but you can see *why* it works. |

---

## How it works

```
frontend/index.html      one self-contained page: live scanner, flat-map editor,
                         Three.js cube, arrows, narration, manual. No build step.
backend/
  app.py                 FastAPI: /api/scan/live /api/scan/face /api/scan/cube
                         /api/classify /api/solve /api/scramble /api/health
  cube/model.py          the cube itself (facelets + geometry)
  cube/cubie.py          the other view: which piece is where, which way up
  cube/twophase.py       the built-in ~23-turn solver
  cube/solver_beginner.py layer-by-layer solver (Learn mode)
  cube/solver.py         solver front door
  cube/validate.py       "is this cube physically possible?"
  cube/explain.py        move -> arrow, words, per-step cube state
  vision/grid.py         where the nine stickers are (tilt- and clutter-proof)
  vision/colour.py       what colour each one is (exposure- and cast-proof)
  vision/cubie_resolver.py  the same question asked per piece instead
  vision/detect.py       the layer that joins them up for the API
  vision/yolo.py         optional YOLO detector (pluggable)
  tools/bench_vision.py  score the scanner on rendered photos
  tools/train_yolo.py    train your own detector
  tests/                 regression tests + synthetic cube photo renderer
```

### The cube engine

Move permutations are **derived from 3D geometry**, not typed in by hand. Each
of the 54 stickers knows its position and which way it faces; a turn is a 90°
rotation of every sticker in that layer. Hand-written permutation tables are the
usual source of silent bugs in cube programs — this sidesteps them, and the
browser reimplements the same construction so the 3D view can never disagree
with the solver.

### The short solver

Kociemba's two-phase algorithm, written here rather than pulled from a package,
so a fresh checkout gives short solutions with nothing extra to install.

Phase 1 drives the cube into the subgroup where every piece is the right way up
and the four middle-slice edges are back in the middle slice. Phase 2 finishes
using only the ten moves that keep it that way. Both phases are IDA* over small
coordinate spaces with **exact** pruning tables built by breadth-first search —
no heuristics, so a reported distance is a real lower bound.

The tables take about two seconds to build on first run and are cached in
`cube/_tables` (2.7 MB). After that: **average 21.6 turns on a fully scrambled
cube, never more than 22 across 250 cubes, median 0.09 s.**

The search asks for a 22-turn answer first and only relaxes if that comes up
empty. That is counter-intuitively both *shorter and faster* than asking for 24
— a tighter bound prunes far more of the tree. It relaxes to 24, then to a hard
ceiling of 30, and a test fails the build if any cube ever needs more.

### The teaching solver

Layer-by-layer, because a human can follow it. The four algorithms it relies on
were each **verified empirically against the engine** — the tests assert, for
example, that the corner-cycle algorithm moves exactly three corners and not a
single edge — rather than trusted from memory.

Where a stage has awkward cases (the top cross has a dot / L / line progression
that greedy logic gets stuck on), the solver runs a tiny bounded search over
algorithm placements instead of guessing. Result: **1000 out of 1000 random
scrambles solved**, average 143 turns.

### Reading the colours

This is the part that decides whether the app is any good, so it is measured
rather than assumed. `python tools/bench_vision.py` scores it on rendered photos
with the face tilted in 3D, a different exposure and white balance on every
shot, a glare spot, a soft shadow, motion blur, sensor noise, and a background
full of sticker-shaped decoys:

| hard photos | grid found | stickers right | cubes perfect | wrong with no warning |
|---|---|---|---|---|
| where this started | 62% | 62% | **0%** | — |
| one frame, no safety nets | 60% | 92% | 57% | 0% |
| as the app actually behaves | **100%** | **99.9%** | **97–100%** | **0%** |

On evenly lit photos it is 100% across the board. That last column matters most:
every misread that survives is one the app *flags*, so you get told to check
rather than handed a wrong answer.

Three things got it there.

**Finding the stickers (`vision/grid.py`).** Looking for nine separate squares
and giving up otherwise failed a third of the time and quietly fell back to a
fixed box in the middle of the frame — which is where the wrong colours came
from. Instead: gather candidate squares from three different filters, keep the
ones whose size agrees, drop the ones that are not packed together (a desk is
full of sticker-sized rectangles), then **fit a homography to the 3×3 lattice**
rather than trusting the outline. Losing a sticker to shadow now costs one
measurement out of nine instead of dragging a whole corner. A scale check
catches the nasty case where the fit settles onto a *shifted* 3×3 and is
confidently wrong. Cells land on the right sticker **99%** of the time.

**Refusing bad frames.** Every reading reports how it was obtained *and* how
cleanly its nine colours separate. Auto-capture fires only when both are good —
otherwise it just keeps looking while you hold the cube, and the bar under the
camera turns amber to say why. This costs about half a second more per face and
takes cube accuracy from 53% to 97%, because a bad frame is worse than no frame.

**Reading the cube as pieces, not stickers (`vision/cubie_resolver.py`).** This
one is borrowed from [dwalton76/rubiks-color-resolver][dw] and it is the single
biggest idea here. A cube is not 54 independent stickers — it is 8 corner pieces
and 12 edge pieces, and *which pieces exist is known in advance*. There are only
eight possible corner colour-triples and twelve possible edge colour-pairs on any
3×3 ever made. So rather than asking "what colour is this sticker?" 54 times, ask
"which of the eight corners is this?" eight times and "which of the twelve edges
is this?" twelve times. Both are assignment problems, solved optimally in
milliseconds. An impossible piece stops being *representable*, and a sticker that
is ambiguous alone gets decided by the other stickers on the same piece.

**Classifying (`vision/colour.py`).** Per-sticker hue thresholds are what make
most scanners confuse red with orange. The real problem is that a phone
re-meters between shots, so the same sticker is a different RGB on each of the
six photos. So model that: `observed = per-face gain × colour`. In log
chromaticity that is plain addition, which makes per-sticker brightness (shadow,
glare) cancel *exactly* and turns the white-balance drift into one offset per
face that can be estimated. Alternate between estimating the six colours and
the six offsets, assign **exactly nine stickers per colour**, and pin the six
centres — a centre is its own face's colour by definition.

Two more cues close the last gap. Yellow and orange differ mostly in one
direction, so a *relative brightness* axis (each sticker against the median of
its own face, which cancels exposure) is added at a lower weight — tuned by
sweep, not guessed. And if the reading is not a physically possible cube, the
cheapest **swap** that makes it possible is tried in order: since exactly nine
stickers carry each colour, a swap is the smallest possible correction, and it
is precisely the mistake the classifier makes.

**Reading it twice.** The sticker method and the piece method fail *differently*
— the first by swapping two lookalike stickers, the second by mismatching a whole
piece. Measured over 80 hard scans they never once failed on the same cube. So
both run, and the cube arbitrates: if only one produced a physically possible
result, take it; if both did and they disagree, take whichever better explains
the samples. That took 39/40 to **40/40 on both palettes, with zero silent
errors**.

It also finally provides an honest confidence signal. Two independent methods
agreeing means something; when they disagree, the app says so and asks you to
check the flat map.

### What was tried and rejected

**CIEDE2000 in CIE Lab** — the perceptual colour distance [qbr][qbr] uses. It is
implemented in `vision/cubie_resolver.py` and verified against Sharma, Wu &
Dalal's published test data, but it is *not* what ships. Measured head to head
against the log-chromaticity metric on hard photos, at both assignment levels:

| colour metric | per sticker | per piece |
|---|---|---|
| Lab + CIEDE2000 | 6/30 | 22/30 |
| log-chroma + relative luma | 24/30 | **27/30** |

CIEDE2000 is better at telling *clean* colours apart, which is what a fixed
lighting rig has. It is worse here because it takes lightness at face value, and
a soft shadow across half a face is a large lightness change that means nothing
about colour. The shipped metric cancels that by construction. The 2×2 also
isolates the real win: the assignment level, not the metric.

**A per-sticker "confidence" highlight** — dropped. Two measures were tried and
scored against ground truth; neither separated right from wrong, because a
misread sticker is one whose *sample* was corrupted, so the model sits firmly in
the wrong cluster rather than hesitating. The better of the two fired on 100% of
cubes and was right 2% of the time, which would only have taught people to ignore
warnings.

**A Hugging Face colour model** — searched for, does not exist. There is no cube
sticker or sticker-colour model on the Hub (checked models, datasets and spaces).
It would also be the wrong tool: the accuracy here comes from constraints a
network cannot be told about — nine of each colour, only eight legal corners,
only twelve legal edges, and a cube that has to be physically solvable. The YOLO
hook in `vision/yolo.py` remains available for *locating* stickers, which is a
job a network would genuinely be good at.

[dw]: https://github.com/dwalton76/rubiks-color-resolver
[qbr]: https://github.com/kkoomen/qbr

### YOLO (optional)

There is no ready-made cube-sticker model on the Hugging Face Hub, so YOLO is
wired in as a *slot* rather than a promise. Point the app at any Ultralytics
`.pt` file and it takes over grid detection automatically:

```bash
set CUBE_YOLO_MODEL=path\to\best.pt          # Windows
export CUBE_YOLO_MODEL=path/to/best.pt       # macOS/Linux
# or pull from the Hub:
export CUBE_YOLO_HF_REPO=you/your-cube-model
```

`python tools/train_yolo.py --list-datasets` lists the cube image datasets that
*do* exist on the Hub and `--write-yaml` scaffolds a training config. The
header of that file explains the labelling workflow.

---

## Tests

```bash
cd backend
python tests/test_solver.py       # no pytest needed
# or
python -m pytest tests -q
```

And the page itself, which is a separate problem:

```bash
npm install jsdom                       # once
node frontend/test/smoke.mjs --offline  # canned replies, no server needed
node frontend/test/smoke.mjs            # against a server on :8000
```

This loads the real `index.html` in a headless DOM, stubs only what genuinely
cannot run there (WebGL and the camera), and walks a whole session: boot, finish
a scan, get a solution, step through a turn, open the manual, edit a sticker by
hand. It exists because of a bug it would have caught instantly and every other
check missed — `FACE_ORDER.filter(...)`, where `FACE_ORDER` is a string and
strings have no `.filter`. The syntax was valid, every element id resolved, the
Python tests all passed, and the app threw at the precise moment the sixth face
finished scanning, so scanning appeared to do nothing at all. Parsing cleanly and
working are different claims, and only one of them was being tested.

Covers: turn geometry, move inversion, the cubie model against the facelet
model, the four last-layer algorithms, 300 layer-by-layer solves, two-phase
solve length and correctness, cube validation (including rejecting impossible
cubes), and the vision pipeline end to end on rendered cube photos.

---

## The built-in manual

**What do R and U mean?** in the header opens an illustrated guide. Every turn
has a picture: a 3×3 face seen the way you are looking at it, the moving layer
picked out in blue, and an arrow showing which way it goes — twelve of them,
plus half turns. The scanning section has a picture per face showing which side
to point at the camera and which way up to hold the cube, and the same picture
appears beside the instruction while you scan.

The diagrams are drawn in SVG at runtime rather than shipped as image files, so
they stay sharp at any size, cost nothing to load, and cannot drift out of step
with the wording.

Everything in there is also in [MANUAL.md](MANUAL.md) as plain text.

## Credit

The colour work stands on two open-source projects, both worth reading:

- **[dwalton76/rubiks-color-resolver][dw]** — resolving colours per *piece*
  rather than per sticker, matching each corner and edge against the pieces a
  real cube can have. This is the idea that made the difference.
- **[kkoomen/qbr][qbr]** — CIE Lab with a CIEDE2000 distance, and the general
  shape of a webcam cube scanner.

What is different here: both assume one fixed lighting setup, so neither has to
cope with a phone re-metering between six handheld photos. That is what the
per-face exposure fit adds, and it is why the log-chromaticity metric beat
CIEDE2000 in the measurements above. Running both readings and letting the cube
arbitrate is also new.

## Notation, if you want it

`R` = turn the right face 90° clockwise as you look at it.
`R'` = the same turn anticlockwise. `R2` = a half turn.
`U` `D` `L` `R` `F` `B` = up, down, left, right, front, back.
The app shows this in the Notation panel, but you never need to read it.
