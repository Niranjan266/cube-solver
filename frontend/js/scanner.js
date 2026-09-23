/*
 * The live scanner, in the browser.
 *
 * Reading a face used to mean uploading a camera frame to the server several
 * times a second and waiting for the answer - slow anywhere, and very slow
 * over the internet. Everything a live preview needs happens here instead,
 * on the video frame itself, about ten times a second:
 *
 *   sampleGrid      nine sticker colours from a 3x3 guide square, sampled
 *                   exactly the way backend/vision/detect.py samples them
 *   classifyLive    a colour name per sticker, for the instant preview
 *   identifyFace    which side this is, from its centre sticker - so faces
 *                   can be shown in any order
 *   resolveRotations  which way up each face was held, found by trying all
 *                   4^6 rotations and keeping the one that makes real pieces
 *
 * The final, careful reading of all 54 colours still goes to the server's
 * classifier (per-face exposure fit, nine-of-each, piece matching); if the
 * server is unreachable, classifyOffline does a simpler balanced version.
 */
(function (global) {
"use strict";

const FACE_ORDER = "URFDLB";

/** Standard colour scheme, holding white on top and green towards you. */
const SCHEME = {U: "White", R: "Red", F: "Green", D: "Yellow", L: "Orange", B: "Blue"};
/** First-guess colours (RGB) before any centre has been seen. */
const REF_RGB = {U: [228, 230, 232], R: [196, 30, 40], F: [22, 158, 72],
                 D: [236, 212, 30], L: [246, 118, 24], B: [24, 84, 196]};

/* ------------------------------------------------------------------ colour */
function srgbToLinear(c){ c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }
function rgbToLab([r, g, b]){
  const R = srgbToLinear(r), G = srgbToLinear(g), B = srgbToLinear(b);
  const X = (R*0.4124 + G*0.3576 + B*0.1805) / 0.95047;
  const Y = (R*0.2126 + G*0.7152 + B*0.0722);
  const Z = (R*0.0193 + G*0.1192 + B*0.9505) / 1.08883;
  const f = t => t > 0.008856 ? Math.cbrt(t) : 7.787*t + 16/116;
  const fx = f(X), fy = f(Y), fz = f(Z);
  return [116*fy - 16, 500*(fx - fy), 200*(fy - fz)];
}
const bgrToLab = s => rgbToLab([s[2], s[1], s[0]]);

/**
 * Colour distance that cares mostly about hue and saturation: lightness is
 * half-weighted, because a shadow across a sticker changes lightness a lot
 * and its colour hardly at all (the same reason the server works in
 * log-chromaticity).
 */
function dist(labA, labB){
  const dL = (labA[0] - labB[0]) * 0.5, da = labA[1] - labB[1], db = labA[2] - labB[2];
  return Math.sqrt(dL*dL + da*da + db*db);
}

const hex = s => "#" + [s[2], s[1], s[0]]
  .map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("");

/* ------------------------------------------------------------------ sampling */
/**
 * Nine BGR samples from a square RGBA image (a canvas ImageData), read inside
 * a guide square covering `frac` of it. Each cell: the middle half only
 * (sticker edges and the black plastic stay out), drop blown-out and black
 * pixels, drop the brightest quarter (glare), take the median. This is
 * detect.sample_cells, pixel for pixel in spirit, so the server's classifier
 * sees the same kind of numbers either way.
 *
 * Also returns how uniform each cell was - a sticker is one flat colour,
 * a hand or a background usually is not.
 */
function sampleGrid(img, frac = 0.66){
  const {width: W, height: H, data} = img;
  const side = Math.min(W, H) * frac;
  const x0 = (W - side) / 2, y0 = (H - side) / 2, cell = side / 3;
  const samples = [], spread = [];
  for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) {
    const m = cell * 0.25;
    const ax = Math.round(x0 + c*cell + m), bx = Math.round(x0 + (c+1)*cell - m);
    const ay = Math.round(y0 + r*cell + m), by = Math.round(y0 + (r+1)*cell - m);
    const step = Math.max(1, Math.floor((bx - ax) / 14));
    const px = [];
    for (let y = ay; y < by; y += step) for (let x = ax; x < bx; x += step) {
      const i = (y*W + x) * 4;
      const R = data[i], G = data[i+1], B = data[i+2];
      const hi = Math.max(R, G, B), lo = Math.min(R, G, B);
      if (hi < 250 && lo > 10) px.push([B, G, R]);
    }
    let keep = px.length >= 8 ? px : (() => {
      const all = [];
      for (let y = ay; y < by; y += step) for (let x = ax; x < bx; x += step) {
        const i = (y*W + x) * 4; all.push([data[i+2], data[i+1], data[i]]);
      }
      return all;
    })();
    const lum = keep.map(p => p[0] + p[1] + p[2]).sort((a, b) => a - b);
    const q75 = lum[Math.floor(lum.length * 0.75)];
    const dim = keep.filter(p => p[0] + p[1] + p[2] <= q75);
    if (dim.length >= 8) keep = dim;
    const med = [0, 1, 2].map(k => {
      const v = keep.map(p => p[k]).sort((a, b) => a - b);
      return v[v.length >> 1];
    });
    samples.push(med);
    // uniformity: median absolute deviation of brightness, relative
    const L = keep.map(p => p[0] + p[1] + p[2]).sort((a, b) => a - b);
    const mid = L[L.length >> 1] || 1;
    const dev = L.map(v => Math.abs(v - mid)).sort((a, b) => a - b);
    spread.push((dev[dev.length >> 1] || 0) / Math.max(mid, 30));
  }
  return {samples, spread, lines: gridLines(img, x0, y0, side)};
}

/**
 * Is there a 3x3 grid here? A cube face has dark lines between its stickers
 * (black plastic, or the gaps on a stickerless cube); a desk, a wall or a
 * hand does not. For each of the four inner lines, search a band around
 * where it should be for its darkest row/column - so a cube a little off
 * centre still counts - and compare with the stickers' brightness.
 * Returns the worst (lightest) line as a fraction of sticker brightness:
 * well under 1 for a real face, about 1 for a flat surface.
 */
const MIN_STICKER_LUM = 110;   // R+G+B; the dimmest real sticker (blue, in shade) is well above
function gridLines(img, x0, y0, side){
  const {width: W, data} = img, c = side / 3, band = Math.max(2, Math.round(c * 0.16));
  const lum = (x, y) => { const i = (Math.round(y) * W + Math.round(x)) * 4; return data[i] + data[i+1] + data[i+2]; };
  const along = [];
  for (let t = 0.08; t < 0.92; t += 0.06) along.push(t * side);
  const darkest = (pos, vertical) => {
    let best = Infinity;
    for (let d = -band; d <= band; d++) {
      let sum = 0;
      for (const a of along) sum += vertical ? lum(x0 + pos + d, y0 + a) : lum(x0 + a, y0 + pos + d);
      best = Math.min(best, sum / along.length);
    }
    return best;
  };
  const cells = [];
  for (let r = 0; r < 3; r++) for (let q = 0; q < 3; q++) cells.push(lum(x0 + (q + .5) * c, y0 + (r + .5) * c));
  cells.sort((a, b) => a - b);
  // too dark to be stickers at all (lens covered, camera starting, a dark
  // room): black has no colour, so it would otherwise read as white
  if (cells[1] < MIN_STICKER_LUM) return 1;
  const ref = cells[4];
  return Math.max(darkest(c, true), darkest(2 * c, true), darkest(c, false), darkest(2 * c, false)) / ref;
}

/* ------------------------------------------------------------------ references */
/** Reference Lab colour for every face: its real centre once seen, else a default. */
function references(centres){
  const out = {};
  for (const f of FACE_ORDER)
    out[f] = centres && centres[f] ? bgrToLab(centres[f]) : rgbToLab(REF_RGB[f]);
  return out;
}

function nearest(lab, refs, faces = FACE_ORDER){
  let best = null, bd = Infinity, second = Infinity;
  for (const f of faces) {
    const d = dist(lab, refs[f]);
    if (d < bd) { second = bd; bd = d; best = f; } else if (d < second) second = d;
  }
  return {face: best, d: bd, margin: second - bd};
}

/** A face letter per sticker, for the live preview. */
function classifyLive(samples, centres){
  const refs = references(centres);
  return samples.map(s => nearest(bgrToLab(s), refs));
}

/* ------------------------------------------------------------------ which face? */
/**
 * Colour of a sticker as log-chromaticity: log(R/G), log(B/G). Brightness
 * cancels exactly (a shadow multiplies all three channels alike), and a
 * face's colour cast - the phone re-metering between shots - becomes one
 * constant offset for every sticker on that face.
 */
const chroma = s => [Math.log((s[2] + 4) / (s[1] + 4)), Math.log((s[0] + 4) / (s[1] + 4))];
const cdist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const REF_CHROMA = {};
for (const f of FACE_ORDER) { const [r, g, b] = REF_RGB[f]; REF_CHROMA[f] = chroma([b, g, r]); }
const SAME_FACE = 0.22;   // chroma distance under which two centres are one colour

/**
 * Which side is this, from its centre sticker? If it matches a centre already
 * captured, it is that face again. Otherwise it is the nearest colour among
 * the faces not captured yet - so once red is in, an orange that looked a bit
 * red cannot be mistaken for it. Compared as colour ratios, which a change
 * of brightness does not move at all.
 */
function identifyFace(centre, centres){
  const x = chroma(centre);
  let same = null, sd = Infinity;
  for (const f of FACE_ORDER) if (centres[f]) {
    const d = cdist(x, chroma(centres[f]));
    if (d < sd) { sd = d; same = f; }
  }
  if (same && sd < SAME_FACE) return {face: same, again: true, d: sd};
  const open = [...FACE_ORDER].filter(f => !centres[f]);
  if (!open.length) return {face: same, again: true, d: sd};
  let best = null, bd = Infinity;
  for (const f of open) { const d = cdist(x, REF_CHROMA[f]); if (d < bd) { bd = d; best = f; } }
  return {face: best, again: false, d: bd};
}

/**
 * Settle the look-alike pairs once all six centres are in. Red and orange
 * differ enormously in R/G - far more than any lighting cast - so comparing
 * the two centres with each other is much safer than judging each against a
 * textbook colour. Likewise white/yellow and blue/green on B/G. Checking the
 * pieces cannot do this job: a cube with red and orange exchanged is a mirror
 * image, and a mirror image with two colours exchanged is a valid cube.
 * Returns {captured-as -> really}.
 */
const PAIRS = [["R", "L", 0], ["U", "D", 1], ["B", "F", 1]];   // [larger, smaller, axis]
function settlePairs(faces){
  const rename = {};
  for (const f of FACE_ORDER) rename[f] = f;
  for (const [hi, lo, axis] of PAIRS) {
    if (!faces[hi] || !faces[lo]) continue;
    if (chroma(faces[hi][4])[axis] < chroma(faces[lo][4])[axis]) { rename[hi] = lo; rename[lo] = hi; }
  }
  return rename;
}

/* ------------------------------------------------------------------ pieces */
// corner and edge slots from the engine's geometry; each corner's stickers
// are put in a fixed right-handed order so a mirror-image corner (right
// colours, impossible twist) does not count as real
const E = global.CubeEngine;
const det3 = (a, b, c) =>
  a[0]*(b[1]*c[2] - b[2]*c[1]) - a[1]*(b[0]*c[2] - b[2]*c[0]) + a[2]*(b[0]*c[1] - b[1]*c[0]);
const SLOTS = (() => {
  const groups = new Map();
  E.FACELET.forEach((s, i) => {
    const k = s.cubie.join(",");
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(i);
  });
  const corners = [], edges = [];
  for (const g of groups.values()) {
    if (g.length === 2) edges.push(g);
    if (g.length === 3) {
      const [a, b, c] = g, D = i => E.FACELET[i].dir;
      corners.push(det3(D(a), D(b), D(c)) > 0 ? [a, b, c] : [a, c, b]);
    }
  }
  return {corners, edges};
})();
const REAL = (() => {
  const s = E.SOLVED, corners = new Set(), edges = new Set();
  for (const [a, b, c] of SLOTS.corners) {
    const t = [s[a], s[b], s[c]];
    for (let k = 0; k < 3; k++) corners.add(t[k] + t[(k+1)%3] + t[(k+2)%3]);
  }
  for (const [a, b] of SLOTS.edges) { edges.add(s[a] + s[b]); edges.add(s[b] + s[a]); }
  return {corners, edges};
})();

/** How many of the 20 pieces in a 54-letter state are pieces a real cube has. */
function realPieces(state){
  let n = 0;
  for (const [a, b, c] of SLOTS.corners) if (REAL.corners.has(state[a] + state[b] + state[c])) n++;
  for (const [a, b] of SLOTS.edges) if (REAL.edges.has(state[a] + state[b])) n++;
  return n;
}

/* ------------------------------------------------------------------ labelling */
/**
 * Least-cost assignment with capacity: every colour gets exactly nine
 * stickers, and the six centres are pinned to their own face. Greedy over
 * sorted (cost, sticker, colour) - close to optimal here and instant.
 */
function balanced(cost, pinned){
  const n = cost.length, out = new Array(n), room = {};
  for (const f of FACE_ORDER) room[f] = 9;
  for (const [i, f] of pinned) { out[i] = f; room[f]--; }
  const pairs = [];
  for (let i = 0; i < n; i++) if (!out[i]) for (const f of FACE_ORDER) pairs.push([cost[i][f], i, f]);
  pairs.sort((a, b) => a[0] - b[0]);
  for (const [, i, f] of pairs) if (!out[i] && room[f] > 0) { out[i] = f; room[f]--; }
  return out;
}

/**
 * Label all 54 stickers, fitting the lighting as it goes - the same model
 * the server uses (observed = per-face gain x colour, additive in log
 * chromaticity). Alternate: assign stickers to colours; re-estimate each
 * colour; re-estimate each face's cast. `faces` maps face -> nine BGR samples
 * (any rotation); returns face -> nine letters in the same order.
 */
function labelFaces(faces){
  const items = [];
  for (const f of FACE_ORDER) faces[f].forEach((s, k) => items.push({f, k, x: chroma(s)}));
  const off = {}, mean = {};
  for (const f of FACE_ORDER) { off[f] = [0, 0]; mean[f] = chroma(faces[f][4]); }
  const pinned = items.map((it, i) => [i, it]).filter(([, it]) => it.k === 4).map(([i, it]) => [i, it.f]);
  let labels = [];
  for (let iter = 0; iter < 8; iter++) {
    const cost = items.map(it => {
      const c = {}, x0 = it.x[0] - off[it.f][0], x1 = it.x[1] - off[it.f][1];
      for (const g of FACE_ORDER) c[g] = (x0 - mean[g][0]) ** 2 + (x1 - mean[g][1]) ** 2;
      return c;
    });
    labels = balanced(cost, pinned);
    for (const g of FACE_ORDER) {
      let a = 0, b = 0, n = 0;
      items.forEach((it, i) => { if (labels[i] === g) { a += it.x[0] - off[it.f][0]; b += it.x[1] - off[it.f][1]; n++; } });
      if (n) mean[g] = [a / n, b / n];
    }
    let ga = 0, gb = 0;
    for (const f of FACE_ORDER) {
      let a = 0, b = 0, n = 0;
      items.forEach((it, i) => { if (it.f === f) { a += it.x[0] - mean[labels[i]][0]; b += it.x[1] - mean[labels[i]][1]; n++; } });
      off[f] = [a / n, b / n]; ga += off[f][0]; gb += off[f][1];
    }
    for (const f of FACE_ORDER) { off[f][0] -= ga / 6; off[f][1] -= gb / 6; }   // only differences matter
  }
  // letters, plus what each colour would cost each sticker (for repairs)
  const out = {}, cost = {};
  for (const f of FACE_ORDER) { out[f] = []; cost[f] = []; }
  items.forEach((it, i) => {
    out[it.f][it.k] = labels[i];
    const c = {};
    for (const g of FACE_ORDER)
      c[g] = (it.x[0] - off[it.f][0] - mean[g][0]) ** 2 + (it.x[1] - off[it.f][1] - mean[g][1]) ** 2;
    cost[it.f][it.k] = c;
  });
  Object.defineProperty(out, "cost", {value: cost, enumerable: false});
  return out;
}

/* ------------------------------------------------------------------ rotations */
/** Turn a face's nine stickers a quarter turn clockwise, `k` times. */
function rotate9(nine, k){
  let v = nine.slice();
  for (let t = 0; t < ((k % 4) + 4) % 4; t++)
    v = [6, 3, 0, 7, 4, 1, 8, 5, 2].map(i => v[i]);
  return v;
}

/**
 * The cheapest swap of two stickers' colours that makes every piece real, or
 * null. A swap keeps nine of each colour, and it is exactly the mistake a
 * colour reader makes: two look-alike stickers the wrong way round (the
 * server's classifier repairs the same way).
 */
function repairOnce(state, costAt){
  let best = null;
  const a = state.split("");
  for (let i = 0; i < 54; i++) for (let j = i + 1; j < 54; j++) {
    if (a[i] === a[j] || i % 9 === 4 || j % 9 === 4) continue;
    const extra = costAt(i, a[j]) + costAt(j, a[i]) - costAt(i, a[i]) - costAt(j, a[j]);
    if (best && extra >= best.extra) continue;
    [a[i], a[j]] = [a[j], a[i]];
    if (realPieces(a.join("")) === 20) best = {state: a.join(""), extra};
    [a[i], a[j]] = [a[j], a[i]];
  }
  return best;
}

const ROT_IDX = [0, 1, 2, 3].map(k => rotate9([0, 1, 2, 3, 4, 5, 6, 7, 8], k));

/**
 * Which way up was each face held?
 *
 * Settle the look-alike centre pairs, label every sticker with the
 * lighting-corrected fit, then try all 4^6 = 4096 combinations of face
 * rotations and score each by how many of the 20 pieces are pieces a real
 * cube has. A wrong rotation puts stickers from different pieces together,
 * so on a real scramble the right one stands out at 20 of 20. If the best
 * falls short because two stickers were read the wrong way round, the
 * leading candidates each get the cheapest one-swap repair, and the one that
 * becomes a real cube most cheaply wins. Ties go to the way the app asked
 * the faces to be held.
 *
 * `captured` maps face letter -> nine BGR samples as captured. Returns the 54
 * samples in U R F D L B order (ready for the server's classifier), the
 * letters, and what was changed.
 */
function resolveRotations(captured){
  const rename = settlePairs(captured);
  const faces = {}, source = {};
  for (const f of FACE_ORDER) { faces[rename[f]] = captured[f]; source[rename[f]] = f; }
  const labelled = labelFaces(faces);
  const rot = {};
  for (const f of FACE_ORDER) rot[f] = [0, 1, 2, 3].map(k => rotate9(labelled[f], k).join(""));

  const all = [];
  const k = [0, 0, 0, 0, 0, 0];
  let top = 0;
  for (let n = 0; n < 4096; n++) {
    for (let i = 0, q = n; i < 6; i++, q >>= 2) k[i] = q & 3;
    const state = rot.U[k[0]] + rot.R[k[1]] + rot.F[k[2]] + rot.D[k[3]] + rot.L[k[4]] + rot.B[k[5]];
    const score = realPieces(state);
    if (score > top) top = score;
    if (score >= top - 2) all.push({k: k.slice(), state, score, turns: k.filter(v => v).length});
  }
  const pool = all.filter(c => c.score >= top - 2)
    .sort((a, b) => b.score - a.score || a.turns - b.turns).slice(0, 40);

  let best = null, perfect = 0;
  for (const c of pool) {
    let state = c.state, swaps = 0, extra = 0;
    if (c.score === 20) perfect++;
    else {
      // what colour g costs the sticker now at index i, under this rotation
      const costAt = (i, g) => {
        const fi = Math.floor(i / 9), f = FACE_ORDER[fi];
        return labelled.cost[f][ROT_IDX[c.k[fi]][i % 9]][g];
      };
      const fix = repairOnce(state, costAt);
      if (!fix) continue;
      state = fix.state; swaps = 1; extra = fix.extra;
    }
    const key = [swaps, c.turns, extra];
    if (!best || key[0] < best.key[0] || (key[0] === best.key[0] &&
        (key[1] < best.key[1] || (key[1] === best.key[1] && key[2] < best.key[2]))))
      best = {key, c, state, swaps};
  }
  if (!best) best = {c: pool[0], state: pool[0].state, swaps: 0};

  const rotations = {};
  FACE_ORDER.split("").forEach((f, i) => rotations[f] = best.c.k[i]);
  const samples = [];
  for (const f of FACE_ORDER) samples.push(...rotate9(faces[f], rotations[f]));
  const renamed = Object.entries(rename).filter(([a, b]) => a !== b).map(([a, b]) => a + "->" + b);
  return {rotations, samples, score: realPieces(best.state), repaired: best.swaps,
          ambiguous: perfect > 1, labels: best.state, renamed, source};
}

/* ------------------------------------------------------------------ offline */
/** No server: the lighting-corrected fit on the 54 samples (U R F D L B order). */
function classifyOffline(samples54){
  const faces = {};
  FACE_ORDER.split("").forEach((f, i) => faces[f] = samples54.slice(i*9, i*9 + 9));
  const lab = labelFaces(faces);
  return FACE_ORDER.split("").map(f => lab[f].join("")).join("");
}

global.CubeScanner = {
  SCHEME, REF_RGB, FACE_ORDER, sampleGrid, classifyLive, identifyFace,
  resolveRotations, settlePairs, classifyOffline, labelFaces, realPieces, rotate9,
  hex, bgrToLab, dist, chroma,
};
})(typeof window !== "undefined" ? window : globalThis);
