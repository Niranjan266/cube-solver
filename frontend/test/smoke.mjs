/**
 * Run the actual page and walk it through a whole session.
 *
 *     node frontend/test/smoke.mjs            # needs a server on :8000
 *     node frontend/test/smoke.mjs --offline  # canned API replies, no server
 *
 * Checking that the script *parses* is not enough. The bug this exists to
 * catch was `FACE_ORDER.filter(...)` - FACE_ORDER is a string, strings have no
 * .filter, and it threw at the exact moment the sixth face finished scanning.
 * Perfect syntax, all element ids present, and the app quietly stopped dead
 * right where it mattered. So: load the real index.html in a DOM, stub only
 * the browser bits that genuinely cannot run headless (WebGL, camera), let
 * everything else run for real, and fail on the first unhandled error.
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { JSDOM, VirtualConsole } from "jsdom";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PAGE = path.join(HERE, "..", "index.html");
const OFFLINE = process.argv.includes("--offline");
const BASE = process.env.CUBE_URL || "http://127.0.0.1:8000";

const SOLVED = [..."URFDLB"].map((f) => f.repeat(9)).join("");
// R U F D2 L' B, from backend/cube/model.py
const OFFLINE_CUBE = "BRBFUUULDFBRFRRLLLBFRBFRUBBRDDBDDDFFUDRULRFLFDULDBLUUL";
const errors = [];
const steps = [];

/* ---- the two things that cannot run in a headless DOM ------------------- */

function fakeThree(win) {
  class Vector3 { constructor(x = 0, y = 0, z = 0) { this.set(x, y, z); }
    set(x, y, z) { this.x = x; this.y = y; this.z = z; return this; } }
  class Quaternion {
    identity() { return this; } setFromEuler() { return this; }
    clone() { return new Quaternion(); } slerpQuaternions() { return this; } }
  class Euler { constructor() { this.x = this.y = this.z = 0; }
    set(x, y, z) { Object.assign(this, { x, y, z }); return this; } }
  class Obj {
    constructor() {
      this.children = []; this.position = new Vector3();
      this.rotation = new Euler(); this.quaternion = new Quaternion();
      this.scale = Object.assign(new Vector3(1, 1, 1),
        { setScalar(v) { this.set(v, v, v); return this; } });
      this.material = arguments[1] !== undefined ? arguments[1]
                    : { color: { set() {} }, opacity: 1 };
      this.renderOrder = 0;
      this.userData = {};
    }
    add(o) { this.children.push(o); return this; }
    remove(o) { this.children = this.children.filter((c) => c !== o); }
    attach(o) { this.add(o); return this; }
    traverse(fn) { fn(this); this.children.forEach((c) => c.traverse && c.traverse(fn)); }
    setRotationFromAxisAngle() { return this; }
    updateMatrixWorld() { return this; }
    lookAt() { return this; }
    updateProjectionMatrix() { return this; }
  }
  class Material { constructor() { this.color = { set() {} }; this.opacity = 1; } }
  class Shape { moveTo() {} lineTo() {} quadraticCurveTo() {} }
  return {
    Scene: Obj, Group: Obj, Mesh: Obj, LineSegments: Obj, Object3D: Obj,
    PerspectiveCamera: Obj, AmbientLight: Obj, DirectionalLight: Obj,
    HemisphereLight: Obj,
    BoxGeometry: class {}, TorusGeometry: class {}, ConeGeometry: class {},
    EdgesGeometry: class {}, PlaneGeometry: class {}, ShapeGeometry: class {},
    CanvasTexture: class {}, Shape, Vector3, Quaternion, Euler,
    MeshLambertMaterial: Material, MeshBasicMaterial: Material,
    MeshStandardMaterial: Material, LineBasicMaterial: Material,
    DoubleSide: 2,
    WebGLRenderer: class {
      constructor() { this.domElement = win.document.createElement("canvas"); }
      setPixelRatio() {} setSize() {} render() {}
    },
  };
}

/** Canned replies, so the harness can run with no backend at all. */
function offlineApi(url, opts) {
  const body = opts && opts.body && typeof opts.body === "string"
    ? JSON.parse(opts.body) : {};
  if (url.includes("/api/health"))
    return { ok: true, solverReady: true, detector: "opencv" };
  if (url.includes("/api/scramble"))
    return { scramble: ["R"], facelets: SOLVED };
  if (url.includes("/api/scan/live") || url.includes("/api/scan/face"))
    return {
      method: "lattice", confidence: 1, faceQuality: 1, found: true,
      gridFound: true,
      cellsNorm: Array.from({ length: 9 }, () => [[0,0],[.1,0],[.1,.1],[0,.1]]),
      samples: Array.from({ length: 9 }, () => [200, 200, 200]),
      hex: Array.from({ length: 9 }, () => "#cccccc"),
      signature: "WWWWWWWWW",
    };
  if (url.includes("/api/classify"))
    return { facelets: OFFLINE_CUBE, palette: {}, valid: true, problem: null,
             badFaces: [], repairedSwaps: 0, agreed: true, method: "both agree" };
  // offline means offline: solving has to happen in the browser
  if (url.includes("/api/solve")) throw new TypeError("Failed to fetch");
  throw new Error("no stub for " + url);
}

/* ---- boot the page ------------------------------------------------------ */

const html = fs.readFileSync(PAGE, "utf8")
  .replace(/<script src="https:\/\/cdnjs[^"]*"><\/script>/, "")
  .replace(/<link[^>]*fonts[^>]*>/g, "")
  // our own scripts are served from /static; inline them from disk
  .replace(/<script src="\/static\/([^"]+)"><\/script>/g, (_, rel) =>
    "<script>" + fs.readFileSync(path.join(HERE, "..", rel), "utf8")
      .replace(/<\/script/gi, "<\\/script") + "</script>");

const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errors.push(e));
vc.on("error", (...a) => errors.push(new Error(a.join(" "))));

// Everything has to be in place *before* the page script runs, because it runs
// as the document parses.
const dom = new JSDOM(html, {
  runScripts: "dangerously",
  pretendToBeVisual: true,
  virtualConsole: vc,
  beforeParse(win) {
    win.THREE = fakeThree(win);
    win.ResizeObserver = class { observe() {} disconnect() {} };
    // real enough that the turn animation actually finishes
    win.requestAnimationFrame = (cb) =>
      setTimeout(() => cb(win.performance.now()), 16);
    win.HTMLCanvasElement.prototype.getContext = () => ({
      clearRect() {}, strokeRect() {}, fillRect() {}, beginPath() {},
      moveTo() {}, lineTo() {}, closePath() {}, fill() {}, stroke() {},
      setLineDash() {}, drawImage() {},
    });
    win.addEventListener("error", (e) =>
      errors.push(e.error || new Error(e.message)));
    win.addEventListener("unhandledrejection", (e) => errors.push(e.reason));
    win.fetch = async (url, opts) => {
      if (OFFLINE) {
        const data = offlineApi(String(url), opts);
        return { ok: true, status: 200, json: async () => data,
                 text: async () => JSON.stringify(data) };
      }
      const r = await fetch(BASE + String(url), opts);
      return { ok: r.ok, status: r.status,
               json: () => r.json(), text: () => r.text() };
    };
  },
});
const win = dom.window;

// The page is a classic script, so its top-level `const` and `let` bindings
// live in the global lexical scope rather than on `window`. eval reaches them.
const G = (expr) => win.eval(expr);

const check = (name, fn) => {
  const before = errors.length;
  try {
    const r = fn();
    if (errors.length > before)
      throw errors[before] instanceof Error ? errors[before] : new Error(String(errors[before]));
    steps.push(["PASS", name, r || ""]);
  } catch (e) {
    steps.push(["FAIL", name, e && e.message ? e.message : String(e)]);
  }
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const withTimeout = (p, ms, what) => Promise.race([
  Promise.resolve(p),
  new Promise((_, rej) => setTimeout(() => rej(new Error(what + " never finished")), ms)),
]);

await new Promise((r) => win.addEventListener("load", r, { once: true }));
await sleep(300);

/* ---- walk through a whole session --------------------------------------- */

const $ = (id) => win.document.getElementById(id);

check("page boots without an error", () => `${errors.length} errors so far`);
check("3D cube built", () => {
  const n = G("cubies.length");
  if (n !== 26) throw new Error(`${n} cubies, expected 26`);
  return `${n} cubies`;
});
check("flat map rendered", () =>
  `${$("liveNet").querySelectorAll(".cell").length} cells (expect 54)`);
check("manual diagrams built", () => {
  const n = $("moveGrid").querySelectorAll(".diacard").length;
  const h = $("holdGrid").querySelectorAll(".diacard").length;
  if (n !== 12 || h !== 6) throw new Error(`moves ${n}, holds ${h}`);
  return `${n} move pictures, ${h} hold pictures`;
});
check("scan tip shows a picture", () => {
  if (!$("tip").querySelector("svg")) throw new Error("no diagram in the tip");
  return "yes";
});

// The exact path that was broken: six faces captured, then classify.
// Feed it the colours of a genuinely scrambled cube, so the real backend has
// something it can actually read and solve rather than 54 identical greys.
const PALETTE = { U: [246, 244, 242], D: [0, 212, 255], F: [68, 168, 38],
                  B: [216, 104, 22], R: [48, 48, 224], L: [24, 120, 240] };
const SCRAMBLED = OFFLINE ? OFFLINE_CUBE
  : await (await fetch(BASE + "/api/scramble", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ moves: 25 }),
    }).then((r) => r.json())).facelets;
const faceSamples = {};
[..."URFDLB"].forEach((f, i) => {
  faceSamples[f] = [...SCRAMBLED.slice(i * 9, i * 9 + 9)]
    .map((c) => PALETTE[c].slice().reverse());       // the page speaks BGR
});
G(`for (const [f, s] of Object.entries(${JSON.stringify(faceSamples)})) {
     S.scanSamples[f] = s;
     S.scanHex[f] = s.map(() => "#888888");
     S.scanQuality[f] = 1;
   }`);
let classifyErr = null;
try {
  await withTimeout(G("classifyAll()"), 8000, "classifying");
} catch (e) {
  classifyErr = e;
}
check("finishing a scan runs to the end", () => {
  if (classifyErr) throw classifyErr;
  const msg = $("scanMsg").textContent.trim();
  if (!msg) throw new Error("no message shown after scanning");
  return JSON.stringify(msg.slice(0, 48));
});

for (let i = 0; i < 60 && !G("S.solution"); i++) await sleep(100);
check("a solution arrived and was listed", () => {
  const count = G("S.solution && S.solution.moveCount");
  if (!count)
    throw new Error("no solution: " + $("solveMsg").textContent.trim().slice(0, 90));
  const n = $("steps").querySelectorAll("li[data-i]").length;
  if (!n) throw new Error("turn list is empty");
  return `${count} turns, ${n} listed`;
});
check("the current turn is shown", () => {
  if ($("moveCard").style.display === "none") throw new Error("move card hidden");
  const a = $("mvArrow").textContent.trim();
  if (!a) throw new Error("no arrow glyph");
  return `arrow ${a}, ${$("mvMotion").textContent.trim()}`;
});

await withTimeout(G("stepForward()"), 5000, "stepping forward");
await sleep(150);
check("stepping forward works", () => {
  if (G("S.index") !== 1) throw new Error("index did not advance");
  return `now on turn ${G("S.index")}`;
});
G("jumpTo(0)");
check("jumping back works", () => `now on turn ${G("S.index")}`);

G("setMode('cfop')");
await withTimeout(G("solve()"), 8000, "CFOP solving");
check("CFOP mode solves in the browser, in named stages", () => {
  const sol = G("S.solution");
  if (!sol || sol.mode !== "cfop") throw new Error("no CFOP solution");
  const heads = [...$("steps").querySelectorAll("li.head b")].map((b) => b.textContent);
  if (!heads.some((h) => h.startsWith("Cross")) || !heads.some((h) => h.startsWith("PLL")))
    throw new Error("stages: " + heads.join(", "));
  return `${sol.moveCount} turns, ${heads.length} stages`;
});

if (OFFLINE) {
  G("setMode('learn')");
  await withTimeout(G("solve()"), 8000, "Beginner solving offline");
  check("Beginner mode explains that it needs the server", () => {
    const msg = $("solveMsg").textContent;
    if (!/server/i.test(msg)) throw new Error(JSON.stringify(msg.slice(0, 80)));
    return "says so";
  });
}
G("setMode('quick')");

await withTimeout(G("setView('cubing')"), 8000, "switching to the cubing.js view");
check("cubing.js view switches without breaking the page", () => {
  if ($("stageCard").dataset.view !== "cubing") throw new Error("view did not change");
  return $("stageCubing").textContent.trim().slice(0, 50) || "player loaded";
});
await withTimeout(G("setView('classic')"), 2000, "switching back");

check("manual opens", () => {
  $("btnManual").click();
  if (!$("sheet").className.includes("open")) throw new Error("sheet did not open");
  $("btnCloseManual").click();
  return "opens and closes";
});
check("hand-editing a sticker works", () => {
  const before = G("S.facelets");
  G("S.paint = 'R'");
  $("net").querySelectorAll(".cell.edit")[0].dispatchEvent(
    new win.MouseEvent("click", { bubbles: true }));
  if (G("S.facelets") === before)
    throw new Error("clicking a sticker changed nothing");
  return "sticker changed";
});

/* ---- report ------------------------------------------------------------- */

let failed = 0;
for (const [status, name, detail] of steps) {
  if (status === "FAIL") failed++;
  console.log(`  ${status}  ${name}${detail ? "  -  " + detail : ""}`);
}
const leftover = errors.filter(Boolean);
if (leftover.length) {
  console.log(`\n${leftover.length} uncaught error(s) on the page:`);
  leftover.slice(0, 5).forEach((e) =>
    console.log("  " + (e.stack || e.message || e).toString().split("\n")[0]));
}
console.log(failed || leftover.length ? "\nFAILED" : "\nall good");
process.exit(failed || leftover.length ? 1 : 0);
