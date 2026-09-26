/*
 * Look for a shorter solution off the main thread.
 *
 * The page finds an answer of at most 20 turns straight away (every cube has
 * one). Proving that a cube has no shorter answer can take min2phase many
 * seconds, and it cannot be interrupted - so that part runs here, where the
 * page can simply stop the worker when its time budget is up.
 *
 * In:  {facelets, below}   look for answers shorter than `below` turns
 * Out: {raw, length}       each time a shorter answer turns up (raw is
 *                          min2phase's text, phase break marked with ".")
 */
/* global min2phase */
importScripts("/static/vendor/min2phase.js");

self.onmessage = (e) => {
  const {facelets, below} = e.data;
  min2phase.initialize();
  for (let target = below - 1; target > 0; target--) {
    const raw = min2phase.solvePattern(facelets, 1, target);
    if (!raw || /^Error/.test(raw)) break;        // nothing that short exists
    const length = raw.replace(".", " ").trim().split(/\s+/).filter(Boolean).length;
    self.postMessage({raw, length});
    target = length;                              // continue below what we found
  }
  self.postMessage({done: true});
};
