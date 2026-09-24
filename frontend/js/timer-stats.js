/*
 * The solve timer's arithmetic: penalties, WCA-style averages, rolling trends,
 * daily summaries, histogram bins and scrambles. No DOM in here, so
 * frontend/test/timer.test.mjs can check every number the page shows.
 *
 * A solve is {ms, pen, scr, at}: raw time in ms, penalty "" | "+2" | "DNF",
 * the scramble, and when it happened (epoch ms).
 */
(function (global) {
"use strict";

const DNF = Infinity;

/** The time that counts: +2 adds two seconds, a DNF never counts. */
const effective = (s) => s.pen === "DNF" ? DNF : s.ms + (s.pen === "+2" ? 2000 : 0);

/** WCA inspection: up to 15 s is free, up to 17 s costs +2, after that DNF. */
const inspectionPenalty = (ms) => ms <= 15000 ? "" : ms <= 17000 ? "+2" : "DNF";

/** How many results an average of n throws away at each end (WCA: 5 %, at least 1). */
const trimFor = (n) => Math.max(1, Math.ceil(n * 0.05));

/**
 * Average of the times given (already effective): drop the best and worst
 * `trimFor(n)`, mean the rest. More DNFs than can be trimmed makes it a DNF.
 */
function averageOf(times){
  const n = times.length;
  if (n < 3) return null;
  const k = trimFor(n);
  const sorted = times.slice().sort((a, b) => a - b);
  if (sorted.filter((t) => t === DNF).length > k) return DNF;
  const mid = sorted.slice(k, n - k);
  return mid.reduce((a, b) => a + b, 0) / mid.length;
}

/** aoN over the last n solves, or null while there are fewer than n. */
function aoN(solves, n, end = solves.length){
  if (end < n) return null;
  return averageOf(solves.slice(end - n, end).map(effective));
}

/** aoN after every solve: null until there are n, then the rolling value. */
function rolling(solves, n){
  const eff = solves.map(effective), out = [];
  for (let i = 0; i < eff.length; i++)
    out.push(i + 1 < n ? null : averageOf(eff.slice(i + 1 - n, i + 1)));
  return out;
}

/** The lowest finite value in a list, with its index; null if none. */
function bestOf(values){
  let best = null, at = -1;
  values.forEach((v, i) => {
    if (v != null && v !== DNF && (best === null || v < best)) { best = v; at = i; }
  });
  return best === null ? null : {value: best, index: at};
}

/** Mean of every finished solve (DNFs left out). */
function mean(solves){
  const ok = solves.map(effective).filter((t) => t !== DNF);
  return ok.length ? ok.reduce((a, b) => a + b, 0) / ok.length : null;
}

/** Everything the stats table shows. */
function summary(solves){
  const row = (n) => {
    if (n === 1) {
      const eff = solves.map(effective);
      return {current: eff.length ? eff[eff.length - 1] : null, best: bestOf(eff)};
    }
    return {current: aoN(solves, n), best: bestOf(rolling(solves, n))};
  };
  const finished = solves.filter((s) => s.pen !== "DNF").length;
  return {
    count: solves.length, finished, mean: mean(solves),
    single: row(1), ao5: row(5), ao12: row(12), ao50: row(50), ao100: row(100),
  };
}

/** Local calendar day, "YYYY-MM-DD". */
function dayKey(at){
  const d = new Date(at);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** One row per day with solves: mean and best of that day, and how many. */
function daily(solves){
  const days = new Map();
  for (const s of solves) {
    const k = dayKey(s.at);
    if (!days.has(k)) days.set(k, []);
    days.get(k).push(s);
  }
  return [...days.entries()].sort(([a], [b]) => a < b ? -1 : 1).map(([day, list]) => ({
    day, count: list.length, mean: mean(list), best: bestOf(list.map(effective))?.value ?? null,
  }));
}

/** A tidy bin width (0.5, 1, 2, 5, 10 ... seconds) for about `target` bins. */
function niceStep(range, target){
  const raw = Math.max(range / target, 100);
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const m of [1, 2, 5, 10]) if (m * mag >= raw) return m * mag;
  return 10 * mag;
}

/** Histogram of finished times: [{from, to, count}], edges on round numbers. */
function histogram(solves, target = 12){
  const t = solves.map(effective).filter((x) => x !== DNF);
  if (!t.length) return [];
  const lo = Math.min(...t), hi = Math.max(...t);
  const step = niceStep(hi - lo, target);
  const start = Math.floor(lo / step) * step;
  const bins = [];
  for (let from = start; from <= hi; from += step) bins.push({from, to: from + step, count: 0});
  for (const x of t) bins[Math.min(bins.length - 1, Math.floor((x - start) / step))].count++;
  return bins;
}

/** 12.34 / 1:02.50 / DNF, with the +2 shown as "12.34+" when asked. */
function fmt(ms, {plus = false} = {}){
  if (ms == null) return "–";
  if (ms === DNF) return "DNF";
  const cs = Math.floor(ms / 10 + 1e-9);
  const m = Math.floor(cs / 6000), s = Math.floor(cs / 100) % 60, c = cs % 100;
  const body = m ? `${m}:${String(s).padStart(2, "0")}.${String(c).padStart(2, "0")}`
                 : `${s}.${String(c).padStart(2, "0")}`;
  return body + (plus ? "+" : "");
}

/** How a single solve is written in the log: "DNF(12.34)", "14.34+", "12.34". */
function fmtSolve(s){
  if (s.pen === "DNF") return `DNF(${fmt(s.ms)})`;
  return fmt(effective(s), {plus: s.pen === "+2"});
}

/**
 * A random-move scramble in the usual style: never the same face twice in a
 * row, and never three turns on one axis in a row (R L R' just wastes turns).
 */
const AXIS = {U: 0, D: 0, R: 1, L: 1, F: 2, B: 2};
function scramble(n = 20, rand = Math.random){
  const faces = "URFDLB", suf = ["", "'", "2"], out = [];
  while (out.length < n) {
    const f = faces[Math.floor(rand() * 6)];
    const a = out[out.length - 1], b = out[out.length - 2];
    if (a && a[0] === f) continue;
    if (a && b && AXIS[a[0]] === AXIS[f] && AXIS[b[0]] === AXIS[f]) continue;
    out.push(f + suf[Math.floor(rand() * 3)]);
  }
  return out;
}

global.TimerStats = {
  DNF, effective, inspectionPenalty, trimFor, averageOf, aoN, rolling, bestOf, mean,
  summary, dayKey, daily, histogram, niceStep, fmt, fmtSolve, scramble,
};
})(typeof window !== "undefined" ? window : globalThis);
