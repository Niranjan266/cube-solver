/**
 * Pre-render the solving guide so its words are in the HTML itself.
 *
 *     node tools/prerender-guide.mjs          # writes frontend/guide.static.html
 *     node tools/prerender-guide.mjs --check  # fails if that file is out of date
 *
 * The guide draws its methods, table, FAQ and so on with JavaScript. Browsers
 * and Google run that, but many crawlers (including the ones AI assistants use
 * to read the web) do not, and would see an almost empty page. This runs the
 * page once in jsdom, copies what it drew into the empty containers of
 * guide.html, adds the FAQ as FAQPage structured data, and saves the result.
 * The page's script still runs for visitors and simply redraws the same thing.
 *
 * Run it after changing guide.html or js/guide-data.js; the server sends
 * guide.static.html for /guide when it exists.
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { JSDOM, VirtualConsole } from "jsdom";

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const FRONT = path.join(ROOT, "frontend");
const SRC = path.join(FRONT, "guide.html");
const OUT = path.join(FRONT, "guide.static.html");
const FILLED = ["picker", "moveGrid", "toc", "chips", "methods", "compareTable", "faqList", "sourceList"];

const source = fs.readFileSync(SRC, "utf8");
// run the page with its data script inlined, so nothing has to be fetched
const DATA_TAG = '<script src="/static/js/guide-data.js"></script>';
if (!source.includes(DATA_TAG)) { console.error("guide.html no longer loads js/guide-data.js as expected"); process.exit(1); }
const runnable = source.replace(DATA_TAG,
  () => `<script>${fs.readFileSync(path.join(FRONT, "js/guide-data.js"), "utf8")}</script>`);
const errors = [];
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errors.push(e.message));
const dom = new JSDOM(runnable, {
  url: "https://cube.niranjand.in/guide", runScripts: "dangerously",
  pretendToBeVisual: true, virtualConsole: vc,
  beforeParse(w) { w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} }); },
});
if (dom.window.document.readyState !== "complete")
  await new Promise((r) => dom.window.addEventListener("load", r));
if (errors.length) { console.error("the guide page threw while drawing:\n  " + errors.join("\n  ")); process.exit(1); }

let out = source;
for (const id of FILLED) {
  const html = dom.window.document.getElementById(id)?.innerHTML;
  if (!html) { console.error(`#${id} came out empty`); process.exit(1); }
  const re = new RegExp(`(<(\\w+)[^>]*\\bid="${id}"[^>]*>)(</\\2>)`);
  if (!re.test(out)) { console.error(`#${id} is not an empty container in guide.html`); process.exit(1); }
  out = out.replace(re, (_, open, _tag, close) => open + html + close);
}

// the FAQ as structured data, from the same words the page shows
const plain = (s) => s.replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
const faq = {
  "@context": "https://schema.org", "@type": "FAQPage",
  mainEntity: dom.window.GUIDE.FAQ.map((f) => ({
    "@type": "Question", name: plain(f.q),
    acceptedAnswer: { "@type": "Answer", text: plain(f.a) },
  })),
};
out = out.replace("</head>", `<script type="application/ld+json">\n${JSON.stringify(faq, null, 1)}\n</script>\n</head>`);
out = out.replace("<!doctype html>", "<!doctype html>\n<!-- generated from guide.html by tools/prerender-guide.mjs - edit that file, not this one -->");

if (process.argv.includes("--check")) {
  const now = fs.existsSync(OUT) ? fs.readFileSync(OUT, "utf8") : "";
  if (now.replace(/\r\n/g, "\n") !== out.replace(/\r\n/g, "\n")) {
    console.error("frontend/guide.static.html is out of date: run node tools/prerender-guide.mjs");
    process.exit(1);
  }
  console.log("guide.static.html is up to date");
} else {
  fs.writeFileSync(OUT, out);
  const words = plain(out.replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/g, "")).split(" ").length;
  console.log(`wrote frontend/guide.static.html (${words} words of text in the HTML)`);
}
dom.window.close();
