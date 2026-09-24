/**
 * The timer's numbers: penalties, WCA averages, rolling trends, days, bins.
 *
 *     node frontend/test/timer.test.mjs
 */
import fs from "fs";
import path from "path";
import vm from "vm";
import { fileURLToPath } from "url";

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const ctx = { console, Math, Date };
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(ROOT, "js/timer-stats.js"), "utf8"), ctx);
const T = ctx.TimerStats;

let failed = 0;
function check(name, got, want){
  const ok = Object.is(got, want) || (typeof want === "number" && Math.abs(got - want) < 1e-9);
  if (!ok) failed++;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${ok ? "" : `  -  got ${got}, want ${want}`}`);
}
const S = (ms, pen = "", at = 0) => ({ ms, pen, scr: "", at });

// penalties and formatting
check("+2 adds two seconds", T.effective(S(10000, "+2")), 12000);
check("DNF never counts", T.effective(S(10000, "DNF")), Infinity);
check("inspection 15.0 s is free", T.inspectionPenalty(15000), "");
check("inspection 16 s is +2", T.inspectionPenalty(16000), "+2");
check("inspection 17.5 s is DNF", T.inspectionPenalty(17500), "DNF");
check("format seconds", T.fmt(12345), "12.34");
check("format minutes", T.fmt(62500), "1:02.50");
check("format keeps .x9 (no float rounding up)", T.fmt(12990), "12.99");
check("format +2 solve", T.fmtSolve(S(12340, "+2")), "14.34+");
check("format DNF solve", T.fmtSolve(S(12340, "DNF")), "DNF(12.34)");

// averages, WCA style
const five = [10, 12, 11, 30, 9].map((s) => S(s * 1000));
check("Ao5 drops best and worst", T.aoN(five, 5), 11000);
check("Ao5 with one DNF: the DNF is the one trimmed", T.aoN([...five.slice(0, 4), S(1, "DNF")], 5), (12000 + 11000 + 30000) / 3);
check("Ao5 with two DNFs is DNF",
      T.aoN([S(10000), S(11000), S(12000), S(1, "DNF"), S(1, "DNF")], 5), Infinity);
check("Ao5 needs five solves", T.aoN(five.slice(0, 4), 5), null);
check("Ao12 trims one each end", T.trimFor(12), 1);
check("Ao100 trims five each end", T.trimFor(100), 5);
const hundred = Array.from({ length: 100 }, (_, i) => S((i + 1) * 100));
check("Ao100 of 0.1..10.0 s", T.aoN(hundred, 100), 5050);

// rolling trend and bests
const r = T.rolling([...five, S(8000)], 5);
check("rolling: nothing before 5 solves", r[3], null);
check("rolling: first Ao5", r[4], 11000);
check("rolling: next Ao5 (12,11,30,9,8)", r[5], (12000 + 11000 + 9000) / 3);
const sum = T.summary([...five, S(8000)]);
check("best single", sum.single.best.value, 8000);
check("best Ao5 is the lower rolling value", sum.ao5.best.value, 32000 / 3);
check("mean leaves out DNFs", T.mean([S(10000), S(20000), S(5, "DNF")]), 15000);

// days and histogram
const day1 = new Date(2026, 0, 5, 9).getTime(), day2 = new Date(2026, 0, 6, 22).getTime();
const days = T.daily([S(10000, "", day1), S(20000, "", day1), S(8000, "", day2)]);
check("two practice days", days.length, 2);
check("day 1 mean", days[0].mean, 15000);
check("day 2 best", days[1].best, 8000);
check("local day key", T.dayKey(day1), "2026-01-05");
const bins = T.histogram([S(10100), S(10900), S(11500), S(14200), S(1, "DNF")], 12);
check("histogram counts every finished solve", bins.reduce((a, b) => a + b.count, 0), 4);
check("histogram edges are round", bins[0].from % 100, 0);

// scrambles
let seed = 7;
const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
let bad = 0;
const AX = { U: 0, D: 0, R: 1, L: 1, F: 2, B: 2 };
for (let k = 0; k < 500; k++) {
  const s = T.scramble(20, rand);
  if (s.length !== 20) bad++;
  for (let i = 1; i < s.length; i++) {
    if (s[i][0] === s[i - 1][0]) bad++;
    if (i > 1 && AX[s[i][0]] === AX[s[i - 1][0]] && AX[s[i][0]] === AX[s[i - 2][0]]) bad++;
    if (!/^[URFDLB]['2]?$/.test(s[i])) bad++;
  }
}
check("500 scrambles: 20 turns, no repeats, no triple axis", bad, 0);

console.log(failed ? "\nFAILED" : "\nall good");
process.exit(failed ? 1 : 0);
