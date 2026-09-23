/**
 * Every move sequence in the solving guide does what the guide says it does.
 *
 *     node frontend/test/guide.test.mjs
 *
 * Each sequence in js/guide-data.js names a `check`. This runs the sequence on
 * the app's own cube engine (wide and slice turns go through the same
 * translation the CFOP mode uses) and holds it to that claim:
 *
 *   f2l          leaves the first two layers (bottom + middle) untouched
 *   pll          as f2l, keeps the top face one colour, and does something
 *   cornerCycle  as f2l and leaves every top edge where it was
 *   edgesOnly    as pll, and every top corner stays exactly where it was
 *   swapFrontLeft as f2l, the back and right top edges stay, front and left swap
 *   midRight     only the top layer and the front-right middle edge change
 *   midLeft      only the top layer and the front-left middle edge change
 *   blocks       Roux: the left and right 1x2x3 blocks are untouched
 *   order6       doing it six times puts everything back
 *   none         a short building block; only checked that it parses
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
for (const f of ["vendor/min2phase.js", "js/engine.js", "js/guide-data.js"])
  vm.runInContext(fs.readFileSync(path.join(ROOT, f), "utf8"), ctx, { filename: f });
const E = ctx.CubeEngine, G = ctx.GUIDE;

/** Plain face turns for a sequence; the grip must end where it started. */
function plain(alg){
  const r = E.fromCfop(alg.split(/\s+/).filter(Boolean));
  const grip = [..."URFDLB"].map((k) => r.frame[k]).join("");
  if (grip !== "URFDLB") throw new Error(`leaves the whole cube turned (${grip})`);
  return r.moves;
}

const F = E.FACELET;
// which sticker indices belong to which kind of piece
const at = (pred) => F.map((s, i) => pred(s.cubie) ? i : -1).filter((i) => i >= 0);
const LOWER = at((c) => c[1] <= 0);                                   // bottom + middle layers
const TOP_EDGES = at((c) => c[1] === 1 && (c[0] === 0) !== (c[2] === 0));
const TOP_FACE = [...Array(9).keys()];                                // the U face stickers
const TOP_CORNERS = at((c) => c[1] === 1 && c[0] !== 0 && c[2] !== 0);
const cubie = (x, y, z) => at((c) => c[0] === x && c[1] === y && c[2] === z);
const exceptCubie = (list, cx, cy, cz) => list.filter((i) => {
  const c = F[i].cubie; return !(c[0] === cx && c[1] === cy && c[2] === cz); });
const BLOCKS = at((c) => c[0] !== 0 && c[1] <= 0);                    // Roux left + right blocks

const same = (state, idx) => idx.every((i) => state[i] === E.SOLVED[i]);

const CHECKS = {
  f2l: (s) => same(s, LOWER) || "disturbs the first two layers",
  pll: (s) => !same(s, LOWER) ? "disturbs the first two layers"
            : !same(s, TOP_FACE) ? "does not keep the top face one colour"
            : s === E.SOLVED ? "does nothing" : true,
  cornerCycle: (s) => !same(s, LOWER) ? "disturbs the first two layers"
            : !same(s, TOP_EDGES) ? "moves top edges" : true,
  edgesOnly: (s) => { const p = CHECKS.pll(s); return p !== true ? p
            : same(s, TOP_CORNERS) || "moves top corners too"; },
  swapFrontLeft: (s) => !same(s, LOWER) ? "disturbs the first two layers"
            : !same(s, [...cubie(0, 1, -1), ...cubie(1, 1, 0)]) ? "moves the back or right edge"
            : (same(s, cubie(0, 1, 1)) || same(s, cubie(-1, 1, 0))) ? "does not swap the front and left edges" : true,
  midRight: (s) => same(s, exceptCubie(LOWER, 1, 0, 1)) || "changes more than the front-right slot",
  midLeft:  (s) => same(s, exceptCubie(LOWER, -1, 0, 1)) || "changes more than the front-left slot",
  blocks: (s) => same(s, BLOCKS) || "breaks a Roux block",
  order6: (s, moves) => {
    let x = E.SOLVED;
    for (let i = 0; i < 6; i++) x = E.applyAll(x, moves);
    return x === E.SOLVED || "six repeats do not return to solved";
  },
  none: () => true,
};

const results = [];
let count = 0;
for (const m of G.METHODS) for (const st of m.steps) for (const a of st.algs) {
  count++;
  const label = `${m.short} · ${st.title} · ${a.name}  [${a.alg}]`;
  try {
    const moves = plain(a.alg);
    const s = E.applyAll(E.SOLVED, moves);
    const verdict = CHECKS[a.check](s, moves);
    results.push([verdict === true ? "PASS" : "FAIL", label, verdict === true ? a.check : verdict]);
  } catch (e) { results.push(["FAIL", label, e.message]); }
}

// every method has steps and every step says what it achieves
for (const m of G.METHODS) {
  const bad = m.steps.filter((s) => !s.title || !s.goal || !s.body);
  results.push([bad.length ? "FAIL" : "PASS", `${m.short}: every step has a title, a goal and an explanation`,
                `${m.steps.length} steps`]);
}

let failed = 0;
for (const [s, n, d] of results) {
  if (s === "FAIL") failed++;
  console.log(`  ${s}  ${n}${d ? "  -  " + d : ""}`);
}
console.log(`\n${count} sequences checked on the cube engine`);
console.log(failed ? "FAILED" : "all good");
process.exit(failed ? 1 : 0);
