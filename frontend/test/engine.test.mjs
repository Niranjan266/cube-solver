/**
 * The browser engine must agree with the Python one, and every answer the two
 * vendored solvers give must actually solve the cube.
 *
 *     node frontend/test/engine.test.mjs
 *
 * engine-fixture.json is Python's own output (regenerate it with the snippet
 * at the bottom of this file if backend/cube/model.py or explain.py changes).
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
for (const f of ["vendor/min2phase.js", "vendor/rubiks-cube-solver.js", "js/engine.js"])
  vm.runInContext(fs.readFileSync(path.join(ROOT, f), "utf8"), ctx, { filename: f });
const E = ctx.CubeEngine;
const fx = JSON.parse(fs.readFileSync(path.join(HERE, "engine-fixture.json"), "utf8"));

const results = [];
const test = (name, fn) => {
  try { results.push(["PASS", name, fn() || ""]); }
  catch (e) { results.push(["FAIL", name, e.message]); }
  const [s, n, d] = results[results.length - 1];
  console.log(`  ${s}  ${n}${d ? "  -  " + d : ""}`);
};
const eq = (a, b, what) => {
  if (JSON.stringify(a) !== JSON.stringify(b))
    throw new Error(`${what}: ${JSON.stringify(a)} != ${JSON.stringify(b)}`);
};

test("move geometry matches Python on 30 scrambles", () => {
  for (const c of fx.cases) eq(E.applyAll(E.SOLVED, c.moves), c.state, c.moves.join(" "));
  return `${fx.cases.length} scrambles`;
});

test("move descriptions match Python for all 18 moves", () => {
  for (const [m, want] of Object.entries(fx.describe)) eq(E.describe(m), want, m);
  return "18 moves";
});

test("moves are invertible", () => {
  for (const c of fx.cases)
    if (E.applyAll(c.state, E.invert(c.moves)) !== E.SOLVED) throw new Error(c.moves.join(" "));
});

test("tidy cancels and merges", () => {
  eq(E.tidy(["R", "R", "U", "U'", "R"]), ["R'"], "R R U U' R");
  eq(E.tidy(["F2", "F2"]), [], "F2 F2");
});

test("wide and slice turns become plain face turns", () => {
  // a turn and its inverse must leave the cube (and the grip) where it was
  for (const pair of [["M", "M'"], ["dprime", "d"], ["r", "r'"], ["S2", "S2"], ["E", "E'"]]) {
    const r = E.fromCfop(pair);
    eq(E.applyAll(E.SOLVED, r.moves), E.SOLVED, pair.join(" "));
    eq([..."URFDLB"].map((k) => r.frame[k]).join(""), "URFDLB", pair.join(" ") + " grip");
  }
  eq(E.fromCfop(["MPRIME2"]).moves, ["R2", "L2"], "M'2");
});

const cubes = Array.from({ length: 150 }, () => E.applyAll(E.SOLVED, E.randomScramble(30)));

test("browser shortest solver: 150 random cubes, all verified", () => {
  const lens = cubes.map((c) => {
    const t = E.solveShortest(c).map(([m]) => m);
    if (!E.isSolved(E.applyAll(c, t))) throw new Error("does not solve " + c);
    return t.length;
  });
  const avg = lens.reduce((a, b) => a + b) / lens.length;
  if (Math.max(...lens) > 22) throw new Error("longer than 22: " + Math.max(...lens));
  return `avg ${avg.toFixed(2)} turns, max ${Math.max(...lens)}`;
});

test("CFOP solver: 150 random cubes, all verified, four named stages", () => {
  const lens = cubes.map((c) => {
    const t = E.solveCfop(c);
    if (!E.isSolved(E.applyAll(c, t.map(([m]) => m)))) throw new Error("does not solve " + c);
    const stages = new Set(t.map(([, s]) => s.replace(/-\d$/, "")));
    for (const s of ["cfop-cross", "cfop-f2l", "cfop-pll"])
      if (![...stages].some((x) => x.startsWith(s))) throw new Error("missing stage " + s);
    return t.length;
  });
  return `avg ${(lens.reduce((a, b) => a + b) / lens.length).toFixed(1)} turns`;
});

test("impossible cubes are refused with a reason, not solved", () => {
  const s = E.SOLVED.split("");
  [s[0], s[9]] = [s[9], s[0]];                     // swap two stickers
  try { E.solveShortest(s.join("")); } catch (e) { return e.message; }
  throw new Error("an impossible cube was 'solved'");
});

test("solved cube needs no turns", () => {
  eq(E.solveShortest(E.SOLVED), [], "shortest");
  eq(E.solveCfop(E.SOLVED), [], "cfop");
});

test("buildSolution has the server's shape", () => {
  const c = cubes[0];
  const sol = E.buildSolution(c, E.solveShortest(c), { mode: "quick" });
  for (const k of ["moveCount", "moves", "notation", "start", "steps", "stages"])
    if (!(k in sol)) throw new Error("missing " + k);
  const last = sol.steps[sol.steps.length - 1];
  if (!E.isSolved(last.stateAfter)) throw new Error("last state is not solved");
  for (const k of ["arrow", "motion", "axis", "layer", "angle", "stageName", "stateAfter"])
    if (!(k in last)) throw new Error("step missing " + k);
});

const failed = results.filter(([s]) => s === "FAIL").length;
console.log(failed ? "\nFAILED" : "\nall good");
process.exit(failed ? 1 : 0);

/* Regenerate engine-fixture.json (run from backend/):
python -c "
import json,random
from cube.model import Cube, random_scramble, ALL_MOVES
from cube.explain import describe
random.seed(3)
cases=[]
for _ in range(30):
    s=random_scramble(20); cases.append({'moves':s,'state':str(Cube().apply_many(s))})
print(json.dumps({'describe':{m:describe(m) for m in ALL_MOVES},'cases':cases}))" > ../frontend/test/engine-fixture.json
*/
