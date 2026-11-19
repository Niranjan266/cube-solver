// Tells Bing (and the other IndexNow search engines: Yandex, Seznam, Naver...) that the pages
// on cube.niranjand.in are new or changed, so they are crawled now instead of whenever the engine next looks.
//
//   node tools/indexnow.mjs        every page in the live sitemap
//
// Run it after a deploy has finished: it reads https://cube.niranjand.in/sitemap.xml, checks the key file
// is live (waiting up to three minutes), and sends the whole URL list.
//
// The key is INDEXNOW_KEY in backend/app.py, which serves it at /<key>.txt, a public value that proves the requests come from this site.
// It is not a secret; IndexNow only needs it to be served at that address.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const HOST = 'cube.niranjand.in';
const SITE = `https://${HOST}`;

const app = fs.readFileSync(path.join(repo, 'backend', 'app.py'), 'utf8');
const key = (app.match(/INDEXNOW_KEY\s*=\s*"([0-9a-f]{32})"/) || [])[1];
if (!key) throw new Error('No INDEXNOW_KEY in backend/app.py.');
const keyUrl = `${SITE}/${key}.txt`;

async function live(url, check) {
  for (let attempt = 0; attempt < 18; attempt++) {
    const res = await fetch(url, { redirect: 'manual', cache: 'no-store' }).catch(() => null);
    if (res && res.status === 200) { const body = await res.text(); if (check(body)) return body; }
    await new Promise((r) => setTimeout(r, 10_000));
  }
  return null;
}
if (!(await live(keyUrl, (b) => b.trim() === key))) throw new Error(`The key file is not live at ${keyUrl} yet. Deploy first.`);
const xml = await live(`${SITE}/sitemap.xml`, (b) => b.includes('<loc>'));
if (!xml) throw new Error(`No sitemap at ${SITE}/sitemap.xml.`);
const urls = [...new Set([...xml.matchAll(/<loc>\s*([^<\s]+)\s*<\/loc>/g)].map((m) => m[1]))]
  .filter((u) => new URL(u).host === HOST);
if (!urls.length) { console.log('IndexNow: the sitemap lists no pages; nothing to send.'); process.exit(0); }

const res = await fetch('https://api.indexnow.org/indexnow', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json; charset=utf-8' },
  body: JSON.stringify({ host: HOST, key, keyLocation: keyUrl, urlList: urls }),
});
// 200 and 202 both mean accepted; 202 is "received, the key is still being checked".
const ok = res.status === 200 || res.status === 202;
console.log(`IndexNow: ${urls.length} page(s) sent, answer ${res.status}${ok ? ' (accepted)' : ': ' + (await res.text()).slice(0, 200)}`);
urls.slice(0, 10).forEach((u) => console.log('  ' + u));
if (urls.length > 10) console.log(`  ...and ${urls.length - 10} more`);
process.exit(ok ? 0 : 1);
