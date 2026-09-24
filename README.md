# Cube Solver

Hold your cube up to the camera. It reads each face on its own — no button to
press — fills the 3D cube in as it goes, and then walks you through **about 20
turns and never more than 22**, one arrow at a time.

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

**Camera** — press *Start scanning* and fill the square with **any side** of the
cube, in **any order, held any way up**. There is no shutter button: the colours
are read in your browser about ten times a second, and the moment they hold
steady (about 0.3 s) the side is captured, painted onto the 3D cube, and named
from its centre sticker ("Red side"). The chips in the square show what each
sticker is being read as before it commits. When all six are in, the app works
out which way up each side was held on its own. It assumes the standard colour
layout (white opposite yellow, green opposite blue, red opposite orange); when
solving, hold the cube with white on top and green facing you.

**Photos** — no webcam, or the laptop camera is switched off? Press *Upload
photos* and pick pictures of the faces (a phone camera is ideal). They go
through the same scanner, one face per photo, in the order the app shows. Pick
several at once and it reads them in turn. If the camera will not start, the
message says why: no camera found (on laptops, usually the camera key or a
privacy shutter), permission blocked, or the camera busy in another app.

**By hand** — the *Enter by hand* tab shows a flat map of the cube. Click a
colour, then click stickers. The centre squares are fixed, because on a real
cube centres never move — they are what makes a face "the red face".

Either way the app checks the cube is physically possible before solving. If a
colour was misread you get a specific message ("one corner is twisted in
place"), the least-confident stickers pulse on the flat map, and you can fix
them by hand.

### 2. Watch it solve

**On a phone** the app is three screens behind a bottom tab bar: *Scan*,
*Check* and *Solve*. It moves on by itself: to *Check* once all six sides are
read, and to *Solve* once there is a solution. On *Solve* the current turn,
the controls and the speed stay on screen, and *All turns* slides the full
list up from the bottom. Every control is at least 44 px tall, and the layout
respects the notch and home bar.

**The 3D cube** fills in live while you scan. The side you are holding up is
painted onto it as the camera reads it, and the cube swings round to show that
side. On a phone a small live cube sits in the corner of the camera view.
**+ / − / reset** on the 3D view change its size (remembered). Dragging it
keeps some momentum and glides to a stop. When nothing is happening, it turns
slowly on its own, and any touch stops that. Layer turns spring into place,
lifting slightly as they go, with a light haptic click on phones.

**Speed** is three buttons: *Slow*, *Normal* and *Fast*. They set how quickly
the 3D cube turns and how long *Play* pauses between turns (Slow leaves time
to copy each turn by hand). The choice is remembered.

The design for both layouts is kept as a design canvas (phone Scan, Check,
Solve and turn list, plus the desktop view), and the app follows it.


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
- **Classic 3D / cubing.js** above the cube switches the viewer. *Classic 3D*
  is the app's own cube, with the arrow and the outlined layer. *cubing.js* is
  the [twisty-player][cubingjs] used on speedcubing sites, with floating
  stickers for the hidden faces. It loads on demand from cdn.cubing.net, so it
  needs an internet connection. The choice is remembered.
- Light and dark follow your system; the ◐ button in the top bar overrides it.
- Drag the middle cube to look from any angle. The flat map underneath it always
  shows where your cube should be right now — compare it with the one in your
  hands if you lose your place.
- The page never scrolls or shifts while you play — the turn list scrolls inside
  its own box.

### 3. Three solving methods

| Method | Turns | Where it runs | Why |
|---|---|---|---|
| **Shortest** (default) | ~20, never over 22 | browser **and** server, shorter wins | Fewer turns by hand means fewer chances to go wrong. The cube looks scrambled until near the end — that is normal. |
| **Beginner** | ~140 | server | Layer-by-layer. Every move belongs to a named stage — bottom cross, bottom corners, middle layer, top cross, and so on. Slower, but you can see *why* it works. |
| **CFOP** | ~65 | browser | The speedcuber method: Cross, four F2L pairs, OLL, PLL — each a named stage. You still never rotate the whole cube. |

**Shortest is a race.** The browser solves the cube itself in about 10 ms with
[min2phase][m2p] and shows that answer at once. Meanwhile the server's own
two-phase search spends up to a second looking for something shorter. If it
beats the browser before you have started turning, its answer replaces the
browser's, and the message says so. Every answer, from either solver, is
replayed on the app's own cube engine before it is shown. If the server is
down, Shortest and CFOP still work; only the camera and Beginner need it.

---

## How it works

```
frontend/index.html      the page: live scanner, flat-map editor, Three.js cube,
                         cubing.js view, arrows, narration, manual. No build step.
frontend/js/scanner.js   the live scanner: sampling, naming a side by its centre,
                         lighting-corrected colours, which-way-up resolution
frontend/js/engine.js    model.py + explain.py ported to JS, plus the glue that
                         runs and checks the two browser solvers
frontend/vendor/         min2phase.js and rubiks-cube-solver.js (both MIT, see
                         vendor/LICENSES.md)
backend/
  app.py                 FastAPI: /api/scan/live /api/scan/face /api/scan/cube
                         /api/classify /api/solve /api/scramble /api/health
  cube/model.py          the cube itself (facelets + geometry)
  cube/cubie.py          the other view: which piece is where, which way up
  cube/twophase.py       the built-in ~21-turn solver
  cube/solver_beginner.py layer-by-layer solver (Beginner mode)
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
`cube/_tables` (2.7 MB). After that: **average 20.6 turns on a fully scrambled
cube, never more than 22, about 1 s per solve.**

The first answer arrives in a median 0.09 s (21.6 turns on average). The search
then spends up to one more second hunting for a shorter answer, the way
Kociemba's reference solver does: it tries longer phase-1 paths, because a
longer phase 1 often buys a much shorter phase 2. It also skips any phase 1 that
ends on a move already inside G1, since a shorter phase 1 reaches the same
state. Measured on 60 cubes, that second is worth one turn fewer (21.65 →
20.63). The window is `IMPROVE_SECONDS` in `twophase.py`; set it to 0 to take
the first answer.

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

**Live, in the browser (`frontend/js/scanner.js`).** Scanning used to upload
several camera frames a second to the server, which was slow anywhere and very
slow over the internet. Now nothing leaves the browser until all six sides are
in:

- **Sampling** mirrors the server's `sample_cells`: the middle half of each
  cell, blown-out and black pixels dropped, the brightest quarter dropped as
  glare, then the median.
- **"Is this a cube?"** Nine flat cells are not enough, because a desk is flat
  too. There must also be dark lines between the cells (black plastic, or the
  gaps of a stickerless cube), searched for in a band so an off-centre cube
  still counts. The stickers must also be bright enough: black has no colour,
  so a covered lens would otherwise read as white.
- **Which side?** The centre sticker names it, compared as colour *ratios*
  (log R/G, log B/G), which shading does not move. Once a colour is in, a new
  centre can only be one of the colours still missing. When all six are in,
  red/orange, white/yellow and green/blue are settled by comparing the two
  centres of each pair with each other. That is far safer than judging each
  one against a textbook colour.
- **Which way up?** Each sticker is labelled with a small port of the server's
  lighting fit (a colour cast per side, nine of each colour). Then all
  4⁶ = 4096 combinations of side rotations are scored by how many of the 20
  pieces are real pieces. The right one stands out at 20/20, and if two
  stickers were read the wrong way round, the cheapest one-swap repair
  finishes the job. This cannot catch a red/orange swap: a mirror-image cube
  with two colours swapped is a valid cube. That is why the pairs are settled
  by comparison first.
- The rotated samples then go to the server's classifier as before. If the
  browser's reading and the server's disagree, the app says so instead of
  solving.

**Red and orange** are the pair cameras mix up most. Warm light pushes red
towards orange, and an over-exposed orange clips its red channel and looks
yellow. Three things deal with that:

- Colour ratios are taken in *linear light*: the camera's sRGB tone curve
  is undone first, which roughly doubles the gap between red and orange.
- Side names are decided *jointly*: all captured centres are matched to
  colours together, with one shared room cast. They are re-checked after
  every capture, so a side briefly called "orange" is renamed as soon as the
  real orange side appears. The camera is asked for slightly darker exposure
  where it allows it.
- The piece check requires every piece exactly once. Red and orange sit on
  opposite sides, so misreading one red sticker as orange produces another
  *real* piece (white-orange instead of white-red), just a duplicate one. A
  check that did not look for duplicates could never catch that mistake.

`node frontend/test/scanner.test.mjs` measures this under three lighting
models, 400 random cubes each (random order, rotation, noise and shadows):

| light | cubes with a red/orange mix-up | whole cube right |
|---|---|---|
| simple casts | 0% | 99% |
| realistic camera (tone curve, warm/cool light, half-working white balance, some clipping) | 0% | 99.5% |
| harsh (warm bulb, heavy over-exposure) | 0.5% (was 19%) | 99% (was 72.5%) |

In a real browser fed that harsh-light scene, the old version got 34 of 54
stickers wrong and could not solve. The new one read every sticker right.

**On the server:**

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
wired in as a *slot* rather than a promise. **No weights ship with this repo**,
and the classical detector stays the default. Point the app at any Ultralytics
`.pt` file and it takes over grid detection automatically:

```bash
set CUBE_YOLO_MODEL=path\to\best.pt          # Windows
export CUBE_YOLO_MODEL=path/to/best.pt       # macOS/Linux
# or pull from the Hub:
export CUBE_YOLO_HF_REPO=you/your-cube-model
```

YOLO is only used to *locate* the nine stickers. Colours still come from the
app's own classifier. If the model finds more than nine boxes (several faces in
view), `find_grid` keeps the nine that best form one face by position, size and
box shape.

**Training data, in two commands** (run from `backend/`):

```bash
pip install huggingface_hub
python tools/train_yolo.py --prepare-hf   # download + convert -> data/yolo_stickers
pip install ultralytics
python tools/train_yolo.py --train        # trains, or prints the exact `yolo` command
```

`--prepare-hf` fetches
[`seandavidreed/rubiks_cube_segmentation`](https://huggingface.co/datasets/seandavidreed/rubiks_cube_segmentation):
197 photos (168 train / 20 valid / 9 test). Each photo shows a cube from a
corner with 3 faces visible, and all 27 visible stickers are labelled as YOLOv8
segmentation polygons across 162 classes (`B_1` … `Y_27`, which is the colour
plus a position number). The script turns every polygon into an axis-aligned box
and every class into a single `sticker` class, then writes `data.yaml`.
`--classes colour` keeps the six colours instead. The output goes in
`backend/data/`, which is git-ignored.

The dataset is by seandavidreed and was exported from
[Roboflow Universe](https://universe.roboflow.com/seandavidreed/rubiks_cube_segmentation).
It is Apache-2.0 on the Hub, but the Roboflow export notes say CC BY 4.0, so
credit the author if you redistribute it or models trained on it.

Caveats: the dataset is small. It has 197 images, and some training images are
augmented copies of the same photo (random rotation, brightness and noise). The
photos are also oblique 3-face views, not the app's face-on scans, so a model
trained on them may not transfer well. Before you switch the default, check
a trained model against the classical detector with `tools/bench_vision.py`.
`--list-datasets` lists other cube datasets on the Hub.

---

## The timer

`/timer` (linked from the top bar) is a speedcubing timer on its own page:

- **Press space (or tap) to start**; any key or tap stops it. `Esc` cancels. Settings has **Hold to start** (hold until green, then let go) for the competition feel.
- A fresh **scramble** for every solve, with an optional picture of the scrambled cube.
- Optional **15-second inspection** (over 15 s is +2, over 17 s is DNF), and **+2 / DNF / delete** on any solve.
- The **Progress, Solves and Stats** buttons open a side panel: every time with Ao5 and Ao12 trend lines, an average per day, how your times spread, and best / current single, Ao5, Ao12, Ao50 and Ao100 (trimmed the way competitions count them).

Solves are saved in the browser on that device only, and nothing is sent to the server.
The numbers live in `frontend/js/timer-stats.js` and are checked by `frontend/test/timer.test.mjs`.

## The solving guide

`/guide` (linked from the top bar) teaches four methods step by step, in
plain words for people who have never held a cube: **Beginner** (layer by
layer), **CFOP**, **Roux** and **ZZ**. It starts with the pieces and the
turn letters, and ends with a comparison table, "which should I learn?",
practice tips and sources. Every move sequence has **Watch** (the cubing.js
3D player, showing the case and solving it) and **Copy**. The Beginner and
CFOP sections link straight into the solver in that mode.

The content lives in `frontend/js/guide-data.js`, written in our own words.
The sequences are the standard ones, and **each one is checked on the app's
own engine** against what the guide says it does: "leaves the first two
layers alone", "moves only the top edges", "swaps the front and left edges",
"six repeats undo it", and so on. Writing that test caught five wrong notes
on how to hold the cube and one sequence that needed an extra `U`. Deliberate
one-letter typos fail it.

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
node frontend/test/engine.test.mjs      # the JS engine and both browser solvers
node frontend/test/scanner.test.mjs     # the live scanner on 400 simulated scans
node frontend/test/guide.test.mjs       # every sequence in the solving guide, on the engine
node frontend/test/timer.test.mjs       # timer averages, penalties, days, scrambles
node frontend/test/smoke.mjs --offline  # canned replies, no server needed
node frontend/test/smoke.mjs            # against a server on :8000
```

`engine.test.mjs` holds `js/engine.js` to the Python engine's own output
(`engine-fixture.json`: 30 scrambles and all 18 move descriptions). It then
runs both browser solvers on 150 random cubes and replays every answer. The
smoke test's offline mode makes the server refuse to solve, so the browser
solvers have to do the work. It also checks CFOP's named stages, Beginner's
"needs the server" message, and switching to the cubing.js view.

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

The colour classifier is also checked against real scans: twelve 3×3×3 sticker
readings from actual cubes (solved, checkerboard, cross, tetris, superflip and
six random scrambles) in `backend/tests/fixtures/rubiks_color_resolver/`, copied
from [dwalton76/rubiks-color-resolver][dw] under its MIT license (commit and
licence text in `LICENSE-NOTE.txt` there). `tests/test_fixtures.py` requires
each to read as a physically valid cube and, where upstream publishes the
answer, to match it sticker for sticker; it also runs on its own with
`python tests/test_fixtures.py`.

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

The real-scan test fixtures (and their expected answers) also come from
[rubiks-color-resolver][dw], © 2019 Daniel Walton, MIT license.

Solving and viewing in the browser:

- **[min2phase][m2p]** by Chen Shuang: the browser's two-phase solver. The
  copy is the MIT-licensed one vendored in cubing.js.
- **[rubiks-cube-solver][cfop]** by Scott McKenzie (MIT): the CFOP mode. Its
  wide and slice turns are rewritten as plain face turns in `js/engine.js`.
- **[cubing.js][cubingjs]** (MPL-2.0): the twisty-player view, loaded
  unmodified from its own CDN at runtime.

[m2p]: https://github.com/cs0x7f/min2phase.js
[cfop]: https://github.com/slammayjammay/rubiks-cube-solver
[cubingjs]: https://github.com/cubing/cubing.js

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
