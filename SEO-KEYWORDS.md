# Keyword map: cube.niranjand.in

What people search for, and which page answers it. Built from what actually
ranks for these phrases (November 2026: ruwix, grubiks, cubeunstuck,
rubiks-cube-solver.com, onlinecube, J Perm, solvethecube, cstimer,
rubiks.com). Use it when writing titles, headings and FAQ questions: phrase
things the way people type them, and keep every page true.

| Cluster | Page | Primary phrase | Secondary phrases | Intent |
|---|---|---|---|---|
| Solver | `/` | rubik's cube solver | rubik's cube solver online, 3x3 solver, solve rubik's cube online, rubik's cube solver with camera / scan, rubik's cube solution step by step, free, no download, no sign-up | Tool (do it for me) |
| Learn to solve | `/guide` | how to solve a rubik's cube step by step | how to solve a rubik's cube for beginners, beginner method, layer by layer, white cross, daisy, white corners, second layer, CFOP / Roux / ZZ method | How-to (teach me) |
| Notation | `/notation` (new) | rubik's cube notation | cube notation, how to read rubik's cube algorithms, what does R U R' U' mean, what does the apostrophe mean, M slice, wide moves (r, Rw), x y z rotations, Singmaster notation, HTM / QTM, God's number | Informational (reference) |
| Algorithms | `/algorithms` (new) | rubik's cube algorithms | algorithms cheat sheet, beginner algorithms, how to solve the last layer, last layer algorithms, 2-look OLL, 2-look PLL, T-perm, Sune, yellow cross algorithm | Informational (reference / cheat sheet) |
| Timer | `/timer` | rubik's cube timer | cube timer, speedcubing timer, online cube timer, scramble generator, 3x3 scramble, Ao5 / Ao12, WCA inspection, csTimer alternative | Tool |
| Support | `/support` | (brand) | 2x2 solver request, report a bug | Navigational |

## Notes per cluster

- **Solver.** Competitors lead with "camera scan", "free", "no download",
  "step by step". This app does all four, so those words go in the title,
  description and FAQ. It solves the 3×3 only: do not target "2x2 solver",
  "4x4 solver" or "NxN solver" until it really does.
- **Learn to solve.** Results are 7/8-step beginner tutorials. The guide's
  beginner method has the same steps (daisy, white cross, corners, middle
  layer, yellow cross, yellow edges, corner positions, corner twist), and
  the FAQ now answers "how do you make the white cross" and "how do you solve
  the last layer" in the words people use.
- **Notation / Algorithms.** Distinct intent from the guide: people want a
  reference page, not a tutorial. Every sequence on both pages is checked
  on the cube engine by `node frontend/test/guide.test.mjs`.
- **Timer.** The timer really generates scrambles, so "scramble generator"
  is fair. They are random-move scrambles (15/20/25 turns), not WCA
  random-state ones; the page says so.
- **Not targeted (yet):** Tamil / other-language tutorials (results are all
  YouTube videos, and the site has no Tamil content), "rubik's cube
  simulator" (no free-play cube on the site), bigger puzzles.
