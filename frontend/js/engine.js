/*
 * The cube engine, in the browser.
 *
 * A line-for-line port of backend/cube/model.py (geometry -> move
 * permutations) and backend/cube/explain.py (move -> arrow, words, per-step
 * state), so the page can solve, check and explain a cube with no server at
 * all. frontend/test/engine.test.mjs holds both ports to the Python output.
 *
 * Also here: the glue for the two vendored solvers (vendor/min2phase.js and
 * vendor/rubiks-cube-solver.js), because both speak slightly different
 * dialects of cube notation and every answer gets replayed before it is shown.
 */
(function (global) {
"use strict";

const FACE_ORDER = "URFDLB";
const NORMAL = {U:[0,1,0], R:[1,0,0], F:[0,0,1], D:[0,-1,0], L:[-1,0,0], B:[0,0,-1]};
const AXES = {                       // (column direction, row direction)
  U:[[1,0,0],[0,0,1]],  R:[[0,0,-1],[0,-1,0]], F:[[1,0,0],[0,-1,0]],
  D:[[1,0,0],[0,0,-1]], L:[[0,0,1],[0,-1,0]],  B:[[-1,0,0],[0,-1,0]],
};
const sgn = v => (v > 0) - (v < 0);
const dot = (a, b) => a[0]*b[0] + a[1]*b[1] + a[2]*b[2];
const cross = (a, b) => [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];
const key = (p, n) => p.join(",") + "|" + n.join(",");

/** index -> {face, pos, dir, cubie}; coordinates scaled by 2 to stay integral */
const FACELET = [];
for (const f of FACE_ORDER) {
  const n = NORMAL[f], [u, v] = AXES[f];
  for (let row = 0; row < 3; row++) for (let col = 0; col < 3; col++) {
    const p = [0,1,2].map(i => n[i]*3 + u[i]*(col-1)*2 + v[i]*(row-1)*2);
    FACELET.push({face: f, pos: p, dir: n, cubie: p.map(sgn)});
  }
}
const POS_INDEX = new Map(FACELET.map((s, i) => [key(s.pos, s.dir), i]));

/** -90 degrees about `axis`: clockwise seen from the +axis end */
function rotCw(vec, axis){
  const d = dot(axis, vec), c = cross(axis, vec);
  return [axis[0]*d - c[0], axis[1]*d - c[1], axis[2]*d - c[2]];
}

/** perm[i] = where the sticker now at i goes */
function buildMove(face){
  const axis = NORMAL[face], perm = [...Array(54).keys()];
  FACELET.forEach((s, i) => {
    if (dot(s.pos, axis) > 1) perm[i] = POS_INDEX.get(key(rotCw(s.pos, axis), rotCw(s.dir, axis)));
  });
  return perm;
}
const compose = (p, q) => p.map(i => q[i]);           // p, then q
const MOVE_PERMS = {};
for (const f of FACE_ORDER) {
  const p = buildMove(f);
  MOVE_PERMS[f] = p;
  MOVE_PERMS[f + "2"] = compose(p, p);
  MOVE_PERMS[f + "'"] = compose(compose(p, p), p);
}
const ALL_MOVES = [...FACE_ORDER].flatMap(f => [f, f + "'", f + "2"]);
const SOLVED = [...FACE_ORDER].map(f => f.repeat(9)).join("");

function apply(state, move){
  const perm = MOVE_PERMS[move];
  if (!perm) throw new Error("unknown move " + move);
  const out = new Array(54);
  for (let i = 0; i < 54; i++) out[perm[i]] = state[i];
  return out.join("");
}
const applyAll = (state, moves) => moves.reduce(apply, state);
const isSolved = s => [...s].every((c, i) => c === s[Math.floor(i/9)*9 + 4]);

function invert(moves){
  return moves.slice().reverse().map(m =>
    m.endsWith("2") ? m : m.endsWith("'") ? m[0] : m + "'");
}

/**
 * Merge consecutive turns of one face and drop the ones that cancel.
 * Works on [move, label] pairs; a merged turn keeps the earlier label.
 */
function tidyTagged(tagged){
  const AMT = {"": 1, "'": 3, "2": 2}, SUF = {1: "", 2: "2", 3: "'"};
  const stack = [];
  for (const [m, label] of tagged) {
    const f = m[0], a = AMT[m.slice(1)];
    const top = stack[stack.length - 1];
    if (top && top[0] === f) {
      stack.pop();
      const t = (top[1] + a) % 4;
      if (t) stack.push([f, t, top[2]]);
    } else stack.push([f, a, label]);
  }
  return stack.map(([f, a, label]) => [f + SUF[a], label]);
}
const tidy = moves => tidyTagged(moves.map(m => [m])).map(([m]) => m);

function randomScramble(n = 25){
  const out = []; let last = "";
  while (out.length < n) {
    const m = ALL_MOVES[Math.floor(Math.random() * ALL_MOVES.length)];
    if (m[0] === last) continue;
    last = m[0]; out.push(m);
  }
  return out;
}

/* ------------------------------------------------------------------------- *
 * explain.py
 * ------------------------------------------------------------------------- */
const FACE_NAME = {U:"top", D:"bottom", L:"left", R:"right", F:"front", B:"back"};
const FACE_AXIS = {R:["x",2], L:["x",0], U:["y",2], D:["y",0], F:["z",2], B:["z",0]};
const HINT_CW = {
  U: "the top layer spins so the front row slides to the LEFT",
  D: "the bottom layer spins so the front row slides to the RIGHT",
  R: "the right column rolls UP at the front",
  L: "the left column rolls DOWN at the front",
  F: "the front face spins like a clock hand",
  B: "the back face spins anti-clockwise when seen from the front",
};
const HINT_CCW = {
  U: "the top layer spins so the front row slides to the RIGHT",
  D: "the bottom layer spins so the front row slides to the LEFT",
  R: "the right column rolls DOWN at the front",
  L: "the left column rolls UP at the front",
  F: "the front face spins anti-clockwise",
  B: "the back face spins like a clock hand when seen from the front",
};
const MOTION_CW = {
  U: ["←", "push the TOP layer LEFT"],
  D: ["→", "push the BOTTOM layer RIGHT"],
  R: ["↑", "push the RIGHT column UP"],
  L: ["↓", "push the LEFT column DOWN"],
  F: ["↻", "spin the FRONT face CLOCKWISE"],
  B: ["↺", "spin the BACK face ANTI-CLOCKWISE (as you see it from the front)"],
};
const MOTION_CCW = {
  U: ["→", "push the TOP layer RIGHT"],
  D: ["←", "push the BOTTOM layer LEFT"],
  R: ["↓", "push the RIGHT column DOWN"],
  L: ["↑", "push the LEFT column UP"],
  F: ["↺", "spin the FRONT face ANTI-CLOCKWISE"],
  B: ["↻", "spin the BACK face CLOCKWISE (as you see it from the front)"],
};
const cap = s => s[0].toUpperCase() + s.slice(1);

function describe(move){
  const face = move[0], suffix = move.slice(1);
  const [axis, layer] = FACE_AXIS[face];
  const name = FACE_NAME[face];
  let angle, direction, arrow, motion, text, hint, speech;
  if (suffix === "2") {
    angle = 180; direction = "half";
    arrow = MOTION_CW[face][0]; motion = MOTION_CW[face][1] + " TWICE";
    text = `Turn the ${name.toUpperCase()} face TWICE (a half turn).`;
    hint = "Either direction works for a half turn - just go round twice.";
    speech = `${name} face, half turn`;
  } else if (suffix === "'") {
    angle = -90; direction = "anticlockwise";
    [arrow, motion] = MOTION_CCW[face];
    text = `Turn the ${name.toUpperCase()} face 90° ANTI-CLOCKWISE (looking straight at it).`;
    hint = cap(HINT_CCW[face]) + ".";
    speech = `${name} face, anti clockwise`;
  } else {
    angle = 90; direction = "clockwise";
    [arrow, motion] = MOTION_CW[face];
    text = `Turn the ${name.toUpperCase()} face 90° CLOCKWISE (looking straight at it).`;
    hint = cap(HINT_CW[face]) + ".";
    speech = `${name} face, clockwise`;
  }
  return {
    move, face, faceName: name, axis, layer,
    angle: layer === 2 ? -angle : angle,
    turns: suffix === "2" ? 2 : 1,
    direction, arrow, motion, text, hint, speech,
  };
}

/** Stages that only exist in the browser (the server names its own). */
const STAGES = {
  "quick-1": ["Part 1 - tidy the cube up",
              "Get every piece facing the right way. The cube will still look " +
              "mixed up - that is normal, keep going."],
  "quick-2": ["Part 2 - finish it off",
              "Slide every piece home. Watch the colours snap together."],
  "cfop-cross": ["Cross",
                 "Build a plus sign on the bottom, with each arm matching the side centre."],
  "cfop-f2l-1": ["F2L - pair 1", "Pair a bottom corner with its edge and drop them in together."],
  "cfop-f2l-2": ["F2L - pair 2", "Same idea, next slot."],
  "cfop-f2l-3": ["F2L - pair 3", "Third slot."],
  "cfop-f2l-4": ["F2L - pair 4", "Last slot - the first two layers are now done."],
  "cfop-oll":   ["OLL - top colour", "One algorithm turns the whole top face the same colour."],
  "cfop-pll":   ["PLL - finish", "One algorithm slides the top layer pieces home. Solved!"],
};

/**
 * One entry per move carrying the state it produces - the same shape the
 * server's /api/solve returns, so the page renders either without caring.
 */
function buildSolution(start, tagged, extra = {}){
  const counts = {};
  tagged.forEach(([, st]) => counts[st] = (counts[st] || 0) + 1);
  const seen = {};
  let c = start;
  const steps = tagged.map(([move, stage], i) => {
    c = apply(c, move);
    seen[stage] = (seen[stage] || 0) + 1;
    const [stageName, stageGoal] = STAGES[stage] || [stage, ""];
    return Object.assign(describe(move), {
      index: i + 1, stage, stageName, stageGoal,
      stageStep: seen[stage], stageTotal: counts[stage], stateAfter: c,
    });
  });
  const stages = [];
  tagged.forEach(([move, stage], i) => {
    const last = stages[stages.length - 1];
    if (!last || last.key !== stage) {
      const [name, goal] = STAGES[stage] || [stage, ""];
      stages.push({key: stage, name, goal, from: i, to: i, moves: []});
    }
    stages[stages.length - 1].to = i;
    stages[stages.length - 1].moves.push(move);
  });
  const moves = tagged.map(([m]) => m);
  return Object.assign({
    ok: true, note: null, moveCount: moves.length, moves,
    notation: moves.join(" "), start, steps, stages,
  }, extra);
}

/* ------------------------------------------------------------------------- *
 * min2phase (vendor/min2phase.js)
 * ------------------------------------------------------------------------- */
let m2pReady = false;
function min2phaseReady(){
  if (!m2pReady && global.min2phase) { global.min2phase.initialize(); m2pReady = true; }
  return m2pReady;
}

/**
 * Shortest-route solve in the browser. Returns tagged moves, or throws with a
 * reason if the cube is not a real one. min2phase's "Error n" codes are its
 * own validity check (wrong colour counts, twisted corner, flipped edge,
 * parity) - so this doubles as an offline validator.
 */
const M2P_ERRORS = {
  1: "Some colour does not appear exactly nine times.",
  2: "Not all twelve edges exist - a sticker was probably misread.",
  3: "One edge is flipped in place, which cannot happen on a real cube.",
  4: "Not all eight corners exist - a sticker was probably misread.",
  5: "One corner is twisted in place, which cannot happen on a real cube.",
  6: "Two pieces are swapped, which cannot happen on a real cube.",
};
function solveShortest(facelets){
  if (!min2phaseReady()) throw new Error("the browser solver did not load");
  if (isSolved(facelets)) return [];
  const raw = global.min2phase.solvePattern(facelets, 1).trim();
  const err = /^Error (\d+)/.exec(raw);
  if (err) throw new Error(M2P_ERRORS[err[1]] || "That cube cannot be solved.");
  if (!raw) throw new Error("That cube cannot be solved - a sticker was probably misread.");
  const [p1, p2 = ""] = raw.split(".");
  const toks = s => s.trim().split(/\s+/).filter(Boolean);
  const tagged = [...toks(p1).map(m => [m, "quick-1"]),
                  ...toks(p2).map(m => [m, "quick-2"])];
  if (!isSolved(applyAll(facelets, tagged.map(([m]) => m))))
    throw new Error("internal check failed: the browser answer does not solve the cube");
  return tagged;
}

/* ------------------------------------------------------------------------- *
 * CFOP (vendor/rubiks-cube-solver.js)
 * ------------------------------------------------------------------------- */
// Whole-cube rotations, as a relabelling: after x, the solver's "U" is the
// face that is physically F, and so on.  new[k] = old[v].
const ROT = {
  x: {U:"F", F:"D", D:"B", B:"U", R:"R", L:"L"},
  y: {F:"R", R:"B", B:"L", L:"F", U:"U", D:"D"},
  z: {R:"U", U:"L", L:"D", D:"R", F:"F", B:"B"},
};
// Wide and slice turns as (plain face turn | rotation, direction multiplier).
const EXPAND = {
  r: [["L",1],["x",1]],  l: [["R",1],["x",-1]], u: [["D",1],["y",1]],
  d: [["U",1],["y",-1]], f: [["B",1],["z",1]],  b: [["F",1],["z",-1]],
  M: [["R",1],["L",-1],["x",-1]], E: [["U",1],["D",-1],["y",-1]],
  S: [["F",-1],["B",1],["z",1]],
};
const SUFFIX = {1: "", 2: "2", 3: "'"};

function rotate(frame, axis, n){
  for (let i = 0; i < ((n % 4) + 4) % 4; i++) {
    const next = {};
    for (const [k, v] of Object.entries(ROT[axis])) next[k] = frame[v];
    frame = next;
  }
  return frame;
}

/**
 * Rewrite the CFOP solver's notation as plain face turns. Wide and slice
 * turns become an outer-face turn plus a relabelling of the faces, so the
 * person keeps the same grip throughout and never rotates the whole cube.
 */
function fromCfop(tokens, frame = {U:"U",R:"R",F:"F",D:"D",L:"L",B:"B"}){
  const out = [];
  for (let t of tokens) {
    t = t.replace(/prime/ig, "'");
    const base = t[0], suf = t.slice(1);
    const n = suf.includes("2") ? 2 : suf.includes("'") ? 3 : 1;
    if ("URFDLB".includes(base)) { out.push(frame[base] + SUFFIX[n]); continue; }
    if ("xyz".includes(base)) { frame = rotate(frame, base, n); continue; }
    if (!EXPAND[base]) throw new Error("CFOP solver used an unknown turn: " + t);
    for (const [part, sign] of EXPAND[base]) {
      const k = (((n * sign) % 4) + 4) % 4;
      if ("xyz".includes(part)) frame = rotate(frame, part, k);
      else if (k) out.push(frame[part] + SUFFIX[k]);
    }
  }
  return {moves: out, frame};
}

/** CFOP solve with stages. Validate first - the library loops on bad input. */
function solveCfop(facelets){
  if (!global.rubiksCubeSolver) throw new Error("the CFOP solver did not load");
  solveShortest(facelets);                          // throws if impossible
  if (isSolved(facelets)) return [];
  const blk = i => facelets.slice(i*9, i*9 + 9);
  // the library wants faces in F R U D L B order, lower case
  const theirs = (blk(2) + blk(1) + blk(0) + blk(3) + blk(4) + blk(5)).toLowerCase();
  const lib = global.rubiksCubeSolver.default || global.rubiksCubeSolver;
  const p = lib(theirs, {partitioned: true});
  const parts = [["cfop-cross", [].concat(p.cross).join(" ")],
                 ...[].concat(p.f2l).map((s, i) => [`cfop-f2l-${i+1}`, s]),
                 ["cfop-oll", p.oll], ["cfop-pll", p.pll]];
  let frame, raw = [];
  for (const [stage, alg] of parts) {
    const r = fromCfop(String(alg || "").split(/\s+/).filter(Boolean), frame);
    frame = r.frame;
    r.moves.forEach(m => raw.push([m, stage]));
  }
  const tagged = tidyTagged(raw);      // also cancels across stage joins
  if (!isSolved(applyAll(facelets, tagged.map(([m]) => m))))
    throw new Error("internal check failed: the CFOP answer does not solve the cube");
  return tagged;
}

global.CubeEngine = {
  FACE_ORDER, FACELET, SOLVED, ALL_MOVES, MOVE_PERMS,
  apply, applyAll, isSolved, invert, tidy, tidyTagged, randomScramble,
  describe, buildSolution, STAGES,
  solveShortest, solveCfop, fromCfop, min2phaseReady,
};
})(typeof window !== "undefined" ? window : globalThis);
