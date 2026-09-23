# The two-minute manual

You do not need to know anything about cubes to use this app. Read this once
and the instructions on screen will make complete sense.

> The same guide, **with a picture for every turn**, is built into the app —
> press **What do R and U mean?** in the top bar. Each move gets a diagram of
> the face as you are looking at it, with the moving layer picked out and an
> arrow showing which way it goes. This file is the text version.

---

## Step 1 — Scan your cube

Press **Start scanning**. Hold a face flat to the camera.

You do not press anything. The app watches the picture, and the moment it can
see all nine stickers clearly *and* the colours hold still for about a second,
it captures that face on its own, flashes, and paints it onto the 3D cube on the
right. Then it asks for the next face.

The detected stickers are drawn back over the video in the colours it read, so
you can see what it thinks before it commits. The bar underneath fills as the
reading settles — **green** means it has locked onto the grid, **amber** means
it can see something but not nine proper stickers, and it will not capture on
amber. If it stays amber: more light, hold the face flatter to the camera, and
put the cube on a plain surface.

That refusal is deliberate. A face captured from a frame the app was not sure
about is worse than no capture at all, because a single wrong sticker sends the
whole solve off course.

**The one rule: pick a face to be the FRONT and never change your grip.**
Turn the cube to show each face, but keep the same side "front" in your head the
whole time. The app tells you which face it wants next and which way up, and
shows a small picture of exactly how to hold it:

| # | Show this face | Keep this side pointing up |
|---|---|---|
| 1 | Top | the **back** of the cube |
| 2 | Right | the **top** |
| 3 | Front — the one you chose | the **top** |
| 4 | Bottom | the **front** |
| 5 | Left | the **top** |
| 6 | Back | the **top** |

If the camera will not play along, switch to **Enter by hand** and click the
colours in. Same result.

---

## Step 2 — Hold the cube still and follow the arrow

Once scanning finishes it solves automatically, usually in **about 20 turns**
and never more than 22.

The screen is in three columns: your cube goes in on the **left**, the 3D model
is in the **middle**, and the turns you have to make are on the **right**.

The right-hand panel shows one turn at a time:

```
  ↑     Right face
        push the RIGHT column UP
        Turn the RIGHT face 90° clockwise (looking straight at it).
```

The big arrow is what your hand does. The 3D cube in the middle shows the same
thing: the layer that moves is outlined, with a blue arrow curling round it. That
arrow always sits on the side of the cube facing you, so it is never hidden round
the back, and it always turns the way you see it — even for the back, left and
bottom faces, where "clockwise" would otherwise look backwards.

If you only look at the arrow and the words next to it, you will solve the cube.
Everything below is just background.

---

## Step 3 — What the letters mean

Each letter is one side of the cube, **from where you are sitting**:

| Letter | Side | The arrow | What actually moves |
|---|---|---|---|
| **U** | Up — the top layer | ← | the top layer spins; its front row slides left |
| **D** | Down — the bottom layer | → | the bottom layer spins; its front row slides right |
| **R** | Right — the right column | ↑ | the right column rolls up at the front |
| **L** | Left — the left column | ↓ | the left column rolls down at the front |
| **F** | Front — the side facing you | ↻ | the front face spins like a clock hand |
| **B** | Back — the side facing away | ↺ | looks anti-clockwise from where you stand |

Then there are two endings:

- **R** — turn that side a quarter turn **clockwise**, as if you were looking
  straight at it.
- **R'** — say it "R prime". Same side, **the other way**, anti-clockwise.
- **R2** — turn it **twice**, a half turn. Direction does not matter here.

That is the entire language. Six letters, three endings, nothing else.

---

## The bit that trips everyone up

"Clockwise" always means *looking straight at that face* — not looking at the
cube from where you sit.

So for the **back** face, a clockwise turn looks anti-clockwise to you. And for
the **left** face, the column comes *down* at the front, not up.

This is exactly why the app shows an arrow drawn the way **you** see it. Follow
the arrow and you cannot get this backwards. The letters are only there so you
can look things up later.

---

## Handy things

| You want to | Do this |
|---|---|
| Undo a turn on screen | **Back**, or the ← arrow key |
| Do the next turn | **Next**, or the → arrow key |
| Play the whole thing | **Play**, or the space bar |
| Jump anywhere | drag the slider |
| Check you are on track | compare your cube with the 3D one — it always shows where you should be |
| Hear the moves | tick **Read aloud** and keep both hands on the cube |
| Look from another angle | drag the 3D cube in the middle |
| Fix a colour it got wrong | **Enter by hand**, pick a colour, click the sticker |
| See it in another 3D style | **cubing.js** above the cube (needs internet); **Classic 3D** to go back |
| Light or dark screen | the ◐ button in the top bar |

---

## Three ways to solve

Pick one under your cube, before or after pressing **Solve it**.

**Shortest** (the default) — about 20 turns, and never more than 22 however
badly mixed your cube is. Two solvers race for it, one in your browser and one
on the server, and you get whichever answer is shorter. Fair warning: the cube
looks scrambled almost until the final move, then everything falls into place at
once. That is normal, not a bug.

**Beginner** — around 140 turns, and slower to watch, but it solves the cube the
way a person would: bottom cross, bottom corners, middle layer, top cross, top
corners, top edges. Each stage has a goal you can see happening.

**CFOP** — about 65 turns. This is how speedcubers solve: the **C**ross, then the
**F**irst two layers as four corner-and-edge pairs, then **O**rient the last
layer (one algorithm makes the top one colour), then **P**ermute it (one
algorithm slides the pieces home). You still never turn the whole cube over.

If you are trying to *understand* the cube rather than just fix it, try
Beginner once, then CFOP, then use Shortest from then on.

---

## When something looks wrong

**"One corner is twisted in place"** or similar — a sticker was misread. That
combination of colours cannot exist on a real cube, so the app stops rather than
sending you on a wild goose chase. Open **Enter by hand**, compare the flat map
with your cube, click the stickers that are wrong, and solve again.

**The colours on screen do not match my cube** — same fix: open **Enter by
hand** and click the wrong ones. Yellow and orange are the usual culprits under
warm indoor light. The app tells you when it had to make a judgement call
between two close colours, and marks any face it found harder to read than the
rest, so those are the ones worth checking first.

**Nothing captures** — the app is refusing frames it is not sure about, which is
working as intended. It needs to see nine distinct squares in a proper 3×3.
Put the cube on a plain surface, get more light on it, hold the face square to
the camera rather than at an angle, and fill more of the frame. If you are in a
hurry, **Snap** captures the current frame regardless.
