/**
 * The in-browser scanner on simulated scans.
 *
 *     node frontend/test/scanner.test.mjs
 *
 * Each trial: a random cube; every face gets its own exposure and colour
 * cast (a phone re-metering between shots), every sticker some noise, a few
 * stickers a shadow; the six faces are shown in a random order, each held at
 * a random rotation. Then: is each face recognised from its centre, is the
 * way-up recovered, and does the whole cube come out right?
 */
import fs from "fs";
import path from "path";
import vm from "vm";
import { fileURLToPath } from "url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(HERE, "..");
const ctx = { console };
ctx.window = ctx;
vm.createContext(ctx);
for (const f of ["vendor/min2phase.js", "js/engine.js", "js/scanner.js"])
  vm.runInContext(fs.readFileSync(path.join(ROOT, f), "utf8"), ctx, { filename: f });
const E = ctx.CubeEngine, SC = ctx.CubeScanner;

let seed = 12345;
const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
const between = (a, b) => a + (b - a) * rnd();
const shuffle = (a) => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };

/** A photographed sticker: true colour x face exposure x face cast, + noise. */
function shoot(state, face, light){
  const base = [..."URFDLB"].indexOf(face) * 9;
  return [...state.slice(base, base + 9)].map((c) => {
    const [r, g, b] = SC.REF_RGB[c];
    const shade = rnd() < 0.08 ? 0.62 : 1;               // a shadow now and then
    const px = [b * light.cast[2], g * light.cast[1], r * light.cast[0]]
      .map((v) => v * light.gain * shade + between(-9, 9));
    return px.map((v) => Math.max(0, Math.min(255, v)));
  });
}

const TRIALS = +(process.env.TRIALS || 400);
let idOk = 0, rotOk = 0, cubeOk = 0, allOk = 0, ambiguous = 0;
const misses = [];
for (let t = 0; t < TRIALS; t++) {
  const state = E.applyAll(E.SOLVED, E.randomScramble(30));
  const captured = {}, centres = {};
  let ids = true;
  for (const f of shuffle([..."URFDLB"])) {
    const light = { gain: between(0.62, 1.2),
                    cast: [between(0.88, 1.12), between(0.9, 1.08), between(0.86, 1.14)] };
    const truth = shoot(state, f, light);
    const k = Math.floor(rnd() * 4);
    const shown = SC.rotate9(truth, (4 - k) % 4);      // held at a random rotation
    const id = SC.identifyFace(shown[4], centres);
    if (id.face !== f) { ids = false; misses.push(`live: ${f} named ${id.face}`); }
    captured[id.face] = shown; centres[id.face] = shown[4];
  }
  if (ids) idOk++;
  if (Object.keys(captured).length !== 6) continue;     // two faces took one name
  const r = SC.resolveRotations(captured);
  if (r.ambiguous) ambiguous++;
  if (r.labels === state) { rotOk++; allOk++; }
  else if (misses.length < 12) misses.push(`final: score ${r.score}, ${[...r.labels].filter((c, i) => c !== state[i]).length} stickers off`);
  if (SC.classifyOffline(r.samples) === state) cubeOk++;
}

const pct = (n) => `${n}/${TRIALS} (${(100 * n / TRIALS).toFixed(1)}%)`;
console.log(`  faces named right while scanning     ${pct(idOk)}`);
console.log(`  WHOLE CUBE RIGHT (after the fixes)   ${pct(allOk)}`);
console.log(`  ...without the one-swap repair       ${pct(cubeOk)}`);
console.log(`  more than one possible way-up        ${ambiguous}`);
if (misses.length) console.log("  e.g. " + misses.slice(0, 6).join("; "));

/* ---- sampling: a drawn face with black gaps and a glare spot ---------- */
function drawFace(colours, W = 300){
  const data = new Uint8ClampedArray(W * W * 4).fill(20);
  const side = W * 0.66, x0 = (W - side) / 2, cell = side / 3;
  for (let i = 0; i < W * W; i++) data[i * 4 + 3] = 255;
  colours.forEach(([r, g, b], n) => {
    const cx = x0 + (n % 3) * cell, cy = x0 + Math.floor(n / 3) * cell;
    for (let y = Math.round(cy + 5); y < cy + cell - 5; y++)
      for (let x = Math.round(cx + 5); x < cx + cell - 5; x++) {
        const i = (y * W + x) * 4;
        const glare = n === 4 && Math.hypot(x - cx - cell / 2, y - cy - cell / 2) < 7;
        data[i] = glare ? 255 : r; data[i + 1] = glare ? 255 : g; data[i + 2] = glare ? 252 : b;
      }
  });
  return { width: W, height: W, data };
}
const face = [..."RLFBUDRRF"].map((c) => SC.REF_RGB[c]);
const { samples, spread } = SC.sampleGrid(drawFace(face));
const worst = Math.max(...samples.map((s, i) =>
  Math.max(Math.abs(s[2] - face[i][0]), Math.abs(s[1] - face[i][1]), Math.abs(s[0] - face[i][2]))));
console.log(`  sampling a drawn face: worst channel error ${worst}, `
  + `max spread ${Math.max(...spread).toFixed(3)} (glare ignored)`);

/* ---- only a real face may pass the "is this a cube?" check ------------- */
const flatImage = (rgb, W = 240) => {
  const data = new Uint8ClampedArray(W * W * 4);
  for (let i = 0; i < W * W; i++) data.set([...rgb, 255], i * 4);
  return { width: W, height: W, data };
};
const GRID_DARK = 0.72;   // as in index.html
const gate = {
  face: SC.sampleGrid(drawFace(face), 0.66).lines,
  "dim face (blue, in shade)": SC.sampleGrid(drawFace([..."BBBBBBBBB"].map((c) =>
    SC.REF_RGB[c].map((v) => v * 0.8))), 0.66).lines,
  "black frame": SC.sampleGrid(flatImage([0, 0, 0]), 0.66).lines,
  "plain wall": SC.sampleGrid(flatImage([200, 190, 170]), 0.66).lines,
  "wooden desk": SC.sampleGrid(flatImage([107, 91, 74]), 0.66).lines,
};
const gateOk = gate.face < GRID_DARK && gate["dim face (blue, in shade)"] < GRID_DARK
  && gate["black frame"] >= GRID_DARK && gate["plain wall"] >= GRID_DARK && gate["wooden desk"] >= GRID_DARK;
console.log("  is-it-a-cube check: " + Object.entries(gate)
  .map(([k, v]) => `${k} ${v.toFixed(2)} ${v < GRID_DARK ? "accept" : "reject"}`).join(", "));

const fail = allOk < TRIALS * 0.97 || worst > 3 || !gateOk;
console.log(fail ? "\nFAILED" : "\nall good");
process.exit(fail ? 1 : 0);
