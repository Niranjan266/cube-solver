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

/*
 * A more honest camera. Stickers reflect light (linear values); the room light
 * is warm or cool and differs a little from side to side; the camera's
 * automatic white balance only half-corrects it; auto-exposure sometimes
 * over-exposes, so bright channels clip; then the sensor applies the sRGB
 * tone curve and adds noise. Red and orange are squeezed together by exactly
 * these steps - warm light and a clipped red channel both push red towards
 * orange - which is where real scans mix them up.
 */
const toLin = (v) => ((v /= 255) <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
const toSrgb = (v) => { v = Math.max(0, Math.min(1, v));
  return 255 * (v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055); };
function cameraShot(state, face, scene){
  const w = scene.warmth + between(-0.25, 0.25);
  const illum = [1 + 0.35 * w, 1, 1 - 0.45 * w];                  // R, G, B
  const awb = between(0, 0.6);                                   // how much the camera corrects
  const eff = illum.map((v) => v ** (1 - awb));
  const gain = between(0.8, scene.harsh ? 3.4 : 2.6);            // sometimes over-exposed
  const base = [..."URFDLB"].indexOf(face) * 9;
  return [...state.slice(base, base + 9)].map((c) => {
    const shade = rnd() < 0.08 ? 0.5 : 1;
    const rgb = SC.REF_RGB[c].map(toLin).map((v, i) => v * eff[i] * gain * shade);
    const out = rgb.map((v) => toSrgb(v * (1 + between(-0.03, 0.03))) + between(-4, 4));
    return [out[2], out[1], out[0]].map((v) => Math.max(0, Math.min(255, v)));   // B, G, R
  });
}

function trial(model){
  const state = E.applyAll(E.SOLVED, E.randomScramble(30));
  // indoor light is often warm; "harsh" = a cheap webcam under a warm bulb
  const scene = model === "harsh" ? { warmth: between(0.5, 1.3), harsh: true }
                                  : { warmth: between(-0.2, 0.9) };
  const captured = {}, centres = {}, truthOf = {};
  const out = { ids: true, chips: 0, chipRO: 0, names: 0, namesRight: 0 };
  for (const f of shuffle([..."URFDLB"])) {
    const truth = model !== "simple" ? cameraShot(state, f, scene)
      : shoot(state, f, { gain: between(0.62, 1.2),
                          cast: [between(0.88, 1.12), between(0.9, 1.08), between(0.86, 1.14)] });
    const k = Math.floor(rnd() * 4);
    const shown = SC.rotate9(truth, (4 - k) % 4);      // held at a random rotation
    const id = SC.identifyFace(shown[4], centres);
    // the live preview dots, with whatever centres are known at this moment
    const base = [..."URFDLB"].indexOf(f) * 9;
    const want = SC.rotate9([...state.slice(base, base + 9)], (4 - k) % 4);
    SC.classifyLive(shown, centres).forEach((x, i) => {
      if (want[i] === "R" || want[i] === "L") { out.chips++; if (x.face !== want[i]) out.chipRO++; }
    });
    captured[id.face] = shown; centres[id.face] = shown[4];
    truthOf[id.face] = f;
    // as the page does: re-name every side captured so far, together
    const rename = SC.settlePairs(captured);
    const moved = {}, movedTruth = {}, movedCentres = {};
    for (const [from, to] of Object.entries(rename)) if (captured[from]) {
      moved[to] = captured[from]; movedTruth[to] = truthOf[from]; movedCentres[to] = centres[from];
    }
    for (const key of Object.keys(captured)) { delete captured[key]; delete centres[key]; delete truthOf[key]; }
    Object.assign(captured, moved); Object.assign(centres, movedCentres); Object.assign(truthOf, movedTruth);
    out.names++;
    if (Object.entries(truthOf).every(([name, real]) => name === real)) out.namesRight++;
  }
  out.ids = Object.entries(truthOf).every(([name, real]) => name === real) && out.namesRight === out.names;
  if (Object.keys(captured).length !== 6) return { ...out, ok: false, ro: 0 };
  const r = SC.resolveRotations(captured);
  out.ok = r.labels === state;
  out.ro = [...r.labels].filter((c, i) => c !== state[i] && "RL".includes(c) && "RL".includes(state[i])).length;
  out.off = [...r.labels].filter((c, i) => c !== state[i]).length;
  out.samples = r.samples; out.state = state; out.labels = r.labels;
  return out;
}

const TRIALS = +(process.env.TRIALS || 400);
const results = {};
const DUMP = [];
for (const model of ["simple", "camera", "harsh"]) {
  const s = { ids: 0, ok: 0, roCubes: 0, chips: 0, chipRO: 0, names: 0, namesRight: 0 };
  for (let t = 0; t < TRIALS; t++) {
    const r = trial(model);
    s.ids += r.ids; s.ok += r.ok; s.names += r.names; s.namesRight += r.namesRight; s.roCubes += r.ro > 0; s.chips += r.chips; s.chipRO += r.chipRO;
    if (model !== "simple" && r.samples) DUMP.push({ state: r.state, samples: r.samples, browser: r.labels });
  }
  results[model] = s;
}
if (process.env.DUMP_TO) fs.writeFileSync(process.env.DUMP_TO, JSON.stringify(DUMP));

const pct = (n, of = TRIALS) => `${String(n).padStart(3)}/${of} (${(100 * n / of).toFixed(1)}%)`;
for (const [model, s] of Object.entries(results)) {
  console.log(`  [${model} light]`);
  console.log(`    names shown right after a capture  ${pct(s.namesRight, s.names)}`);
  console.log(`    every name right throughout        ${pct(s.ids)}`);
  console.log(`    live dots: red/orange shown wrong  ${pct(s.chipRO, s.chips)}`);
  console.log(`    cubes with a red/orange mix-up     ${pct(s.roCubes)}`);
  console.log(`    WHOLE CUBE RIGHT                   ${pct(s.ok)}`);
}
const allOk = results.simple.ok;

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
