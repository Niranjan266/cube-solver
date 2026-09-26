/*
 * The solving guide's content: four methods, step by step, in plain words.
 *
 * Written for this site in its own words. The move sequences are the standard
 * ones cubers share (see SOURCES at the bottom). Every sequence here carries a
 * `check` naming what it is supposed to do, and frontend/test/guide.test.mjs
 * runs each one on the app's own cube engine to prove it does exactly that -
 * so a typo in a sequence cannot reach the page.
 *
 * `stickering` names the cubing.js view used by the Watch button (it greys
 * out the pieces that do not matter for that step).
 */
(function (global) {
"use strict";

const METHODS = [
/* ======================================================================== */
{
  id: "beginner",
  name: "Beginner (layer by layer)",
  short: "Beginner",
  tagline: "The one to learn first. Solve the cube one layer at a time, bottom to top.",
  level: 1, moves: "about 100–150", learn: "an afternoon", algs: 7,
  bestFor: "Anyone who has never solved a cube.",
  holding: "Hold the cube with the <b>white centre on the bottom</b> and <b>yellow on top</b> for most of the solve. Whatever faces you is the front.",
  steps: [
    {
      title: "The daisy",
      goal: "Four white edges around the yellow centre, like petals round a flower.",
      body: `<p>Turn the cube so <b>yellow is on top</b>. Find the four edge pieces that have
      white on them, and bring each one up so its white sticker sits next to the
      yellow centre. When a white edge is in the way, turn the top layer to make
      room first. You do not need any sequence for this — just turn and watch.</p>`,
      tip: "If a petal is already in place, turn the top (U) to move it out of the way before you bring the next one up.",
      algs: [],
    },
    {
      title: "The white cross",
      goal: "A white plus sign on the bottom, each arm matching the centre beside it.",
      body: `<p>Look at one petal. Its other sticker (not the white one) has a colour.
      Turn the top layer until that sticker sits above the centre of the same
      colour. Then turn that face twice (for example <code>F2</code>) — the petal
      flips down to the bottom. Do the same for all four petals.</p>
      <p>Turn the cube over (white on the bottom): you should see a white cross
      whose arms line up with the side centres.</p>`,
      tip: "Always match first, then turn the face twice. That order is the whole trick.",
      algs: [],
    },
    {
      title: "The white corners",
      goal: "The whole bottom layer done: white face plus a matching row on each side.",
      body: `<p>Find a corner in the top layer that has white on it. Turn the top until
      that corner sits directly <b>above the spot where it belongs</b> — the spot
      between the two centres that match its other two colours. Hold the cube so
      that spot is at the <b>front-right-bottom</b>.</p>
      <p>Now repeat the four-move sequence below until the corner drops in with
      white facing down. It takes 1, 3 or 5 repeats. Then go to the next corner.</p>`,
      tip: "This sequence is so common it has a nickname: “the sexy move”. Doing it six times in a row puts everything back as it was — handy if you get lost.",
      algs: [
        { name: "Corner in, one step at a time", alg: "R U R' U'", check: "order6",
          note: "Repeat until the white corner is in place and white faces down.", stickering: "F2L" },
      ],
    },
    {
      title: "The middle layer",
      goal: "The first two layers finished — only the top is left.",
      body: `<p>Turn the cube so <b>yellow is on top</b> and white on the bottom. Find an
      edge in the top layer that has <b>no yellow</b>. Turn the top until that edge's
      front sticker matches the front centre, making an upside-down “T”.</p>
      <p>Now look at its top sticker: if it matches the <b>right</b> centre, the edge
      goes right; if it matches the <b>left</b> centre, it goes left. Use the matching
      sequence. If an edge is stuck in the middle layer the wrong way round, do
      either sequence once to pop it out, then insert it properly.</p>`,
      tip: "Both sequences are the same idea, mirrored: move the slot away, bring the edge over, put the slot back.",
      algs: [
        { name: "Edge goes to the right", alg: "U R U' R' U' F' U F", check: "midRight",
          note: "Front sticker matches the front; top sticker matches the right centre.", stickering: "F2L" },
        { name: "Edge goes to the left", alg: "U' L' U L U F U' F'", check: "midLeft",
          note: "Front sticker matches the front; top sticker matches the left centre.", stickering: "F2L" },
      ],
    },
    {
      title: "The yellow cross",
      goal: "A yellow plus sign on top (the corners can be anything).",
      body: `<p>Look at the top. You will see one of four shapes made by the yellow edges:
      a <b>dot</b> (just the centre), an <b>L</b>, a <b>line</b>, or already a
      <b>cross</b>.</p>
      <p>Hold an <b>L</b> so it points to the back-left (the corner of the L at the
      back-left), and a <b>line</b> so it runs left to right. Then do the sequence.
      Dot → L → line → cross: each go moves you one shape along.</p>`,
      tip: "From a dot, do it once, hold the L correctly, and carry on.",
      algs: [
        { name: "Dot → L → line → cross", alg: "F R U R' U' F'", check: "f2l",
          note: "Hold an L at the back-left, a line left-to-right.", stickering: "OLL" },
      ],
    },
    {
      title: "Line up the yellow edges",
      goal: "Each yellow edge's side colour matches the centre below it.",
      body: `<p>Turn the top layer until at least two edges match their side centres.
      If two <b>neighbouring</b> edges match, hold them at the <b>back and right</b>.
      If two <b>opposite</b> edges match, do the sequence once from anywhere, then
      look again.</p>
      <p>Do the sequence, then turn the top if needed until all four line up.</p>`,
      tip: "The first seven moves are the Sune — a sequence that comes back in every advanced method, so it is worth learning well.",
      algs: [
        { name: "Swap two yellow edges", alg: "R U R' U R U2 R' U", check: "swapFrontLeft",
          note: "Matching pair at the back and the right; the front and left edges swap.", stickering: "LL" },
      ],
    },
    {
      title: "Put the yellow corners in place",
      goal: "Every yellow corner in its correct spot (it may still be twisted).",
      body: `<p>A corner is “in place” when it sits between the three centres of its
      colours, even if it is twisted. Find one corner that is already in place and
      hold it at the <b>front-right</b>. Do the sequence (once or twice) until all
      four are in place. If none is in place, do it once from anywhere first.</p>`,
      tip: "It cycles the other three corners round, and leaves the front-right one alone.",
      algs: [
        { name: "Cycle three corners", alg: "U R U' L' U R' U' L", check: "cornerCycle",
          note: "The corner at the front-right stays put.", stickering: "LL" },
      ],
    },
    {
      title: "Twist the last corners",
      goal: "Solved!",
      body: `<p>Turn the cube over so <b>yellow faces down</b> and <b>white is on top</b>.
      Hold a corner that needs twisting at the <b>front-right-bottom</b>. Repeat the
      sequence two or four times until yellow faces down on that corner. The rest of
      the cube will look scrambled — <b>that is normal, keep going</b>.</p>
      <p>Now turn only the <b>bottom layer</b> (<code>D</code>) to bring the next
      twisted corner to the front-right-bottom, and repeat. When the last corner is
      done, one final turn of the bottom layer solves the cube.</p>`,
      tip: "Never turn the whole cube during this step — only the bottom layer. The mess fixes itself at the end.",
      algs: [
        { name: "Twist a corner", alg: "R' D' R D", check: "order6",
          note: "Repeat 2 or 4 times per corner. Six repeats undo it completely.", stickering: "full" },
      ],
    },
  ],
},

/* ======================================================================== */
{
  id: "cfop",
  name: "CFOP (Fridrich)",
  short: "CFOP",
  tagline: "What most speedcubers use. Cross, First two layers, Orient and Permute the last layer.",
  level: 3, moves: "about 55–60", learn: "a few weeks (2-look) to months (full)", algs: "16 to start, 78 in full",
  bestFor: "Anyone who can already solve with the beginner method and wants to get fast.",
  holding: "Build the cross on the <b>bottom</b> and keep it there, so you can see the rest of the cube while you work.",
  steps: [
    {
      title: "C — Cross",
      goal: "The white cross on the bottom, in one go.",
      body: `<p>Same cross as the beginner method, but built directly on the bottom
      instead of via a daisy. Good crosses take 8 moves or fewer. Plan the whole
      cross while inspecting the cube, before you start turning.</p>`,
      tip: "Practise solving the cross without looking at the bottom — it is the single biggest early improvement.",
      algs: [],
    },
    {
      title: "F2L — First two layers",
      goal: "The four bottom corners and four middle edges, as four corner-and-edge pairs.",
      body: `<p>Instead of a corner then an edge, CFOP joins each bottom corner with the
      middle edge that belongs next to it, and drops the <b>pair</b> in at once. It
      is mostly intuitive: bring the two pieces together in the top layer, then
      insert them together.</p>
      <p>The basic idea: hide the slot, join the pair, bring the slot back. The three
      short moves below are the building blocks almost every case is made from.</p>`,
      tip: "Learn to solve pairs slowly and without pausing before learning more cases. Smooth beats fast.",
      algs: [
        { name: "Insert a ready pair (right)", alg: "U R U' R'", check: "none",
          note: "Pair joined at the front-top, slot at the front-right.", stickering: "F2L" },
        { name: "Insert a ready pair (right, other way)", alg: "R U R'", check: "none",
          note: "Pair at the right-top, pointing towards you.", stickering: "F2L" },
        { name: "Insert a ready pair (left)", alg: "U' L' U L", check: "none",
          note: "The mirror, for slots on the left.", stickering: "F2L" },
      ],
    },
    {
      title: "OLL — make the top one colour (2-look)",
      goal: "The whole top face yellow.",
      body: `<p><b>Look 1 — the yellow edges.</b> Exactly the beginner's yellow cross,
      with a faster move for the L shape.</p>
      <p><b>Look 2 — the yellow corners.</b> With the cross done, the corners show one
      of seven patterns. Each has its own sequence. Learn Sune and Anti-Sune first:
      they are the most common and every other one can be reached through them.</p>`,
      tip: "Full OLL is 57 cases done in one look. Most people stay with 2-look for months — that is fine.",
      algs: [
        { name: "Line → cross", alg: "F R U R' U' F'", check: "f2l",
          note: "Line held left to right.", stickering: "OLL" },
        { name: "L → cross", alg: "F U R U' R' F'", check: "f2l",
          note: "L held at the back-left (its arms pointing back and left).", stickering: "OLL" },
        { name: "Sune", alg: "R U R' U R U2 R'", check: "f2l",
          note: "One yellow corner on top — hold it at the front-left.", stickering: "OLL" },
        { name: "Anti-Sune", alg: "R U2 R' U' R U' R'", check: "f2l",
          note: "One yellow corner on top — hold it at the back-right.", stickering: "OLL" },
        { name: "H", alg: "R U R' U R U' R' U R U2 R'", check: "f2l",
          note: "No yellow corners on top; left and right sides show two yellows each.", stickering: "OLL" },
        { name: "Pi", alg: "R U2 R2 U' R2 U' R2 U2 R", check: "f2l",
          note: "No yellow corners on top; yellows on the left side face left.", stickering: "OLL" },
        { name: "Headlights", alg: "R2 D R' U2 R D' R' U2 R'", check: "f2l",
          note: "Two yellow corners at the back; two yellows facing you.", stickering: "OLL" },
        { name: "Chameleon", alg: "r U R' U' r' F R F'", check: "f2l",
          note: "Two yellow corners on top, both on the right; the other two show yellow at the front and back.", stickering: "OLL" },
        { name: "Bowtie", alg: "F' r U R' U' r' F R", check: "f2l",
          note: "Two yellow corners on top, diagonal: back-right and front-left.", stickering: "OLL" },
      ],
    },
    {
      title: "PLL — move the top pieces home (2-look)",
      goal: "Solved.",
      body: `<p><b>Look 1 — the corners.</b> Look for two corners on one side with matching
      colours (“headlights”). If you find them, hold them on the <b>left</b> and do
      the T-perm. If there are none anywhere, do the Y-perm.</p>
      <p><b>Look 2 — the edges.</b> Now only the edges are left: three of them need
      cycling one way or the other (Ua, Ub), or they swap in pairs (H, Z).</p>`,
      tip: "Full PLL is 21 cases. Of all the full sets, it is the one most worth learning early.",
      algs: [
        { name: "T-perm (swap two corners)", alg: "R U R' U' R' F R2 U' R' U' R U R' F'", check: "pll",
          note: "Headlights (a matching pair of corners) on the left; it swaps the two corners on the right.", stickering: "PLL" },
        { name: "Y-perm (swap diagonal corners)", alg: "F R U' R' U' R U R' F' R U R' U' R' F R F'", check: "pll",
          note: "No headlights anywhere.", stickering: "PLL" },
        { name: "Ua (cycle three edges)", alg: "R U' R U R U R U' R' U' R2", check: "edgesOnly",
          note: "One edge already right — hold it at the back. Ua and Ub cycle the other three in opposite directions: if one makes it worse, the other is the one you need.", stickering: "PLL" },
        { name: "Ub (cycle three edges, the other way)", alg: "R2 U R U R' U' R' U' R' U R'", check: "edgesOnly",
          note: "Solved edge at the back.", stickering: "PLL" },
        { name: "H (swap opposite edges)", alg: "M2 U M2 U2 M2 U M2", check: "edgesOnly",
          note: "Every side shows a stripe of the opposite colour. M turns the middle slice (like L).", stickering: "PLL" },
        { name: "Z (swap neighbouring edges)", alg: "M' U M2 U M2 U M' U2 M2 U'", check: "edgesOnly",
          note: "Two neighbouring pairs of edges swap. M turns the middle slice, the same way as L.", stickering: "PLL" },
      ],
    },
  ],
},

/* ======================================================================== */
{
  id: "roux",
  name: "Roux",
  short: "Roux",
  tagline: "Build two blocks on the sides, then finish with the middle slice. Few moves, lots of thinking.",
  level: 3, moves: "about 45–50", learn: "weeks", algs: "a handful to start, 42 in full",
  bestFor: "People who like puzzles more than memorising, and one-handed solving.",
  holding: "The two blocks sit on the <b>left</b> and <b>right</b>, at the bottom. The top layer and the middle slice (M) stay free until the end.",
  steps: [
    {
      title: "First block (left)",
      goal: "A 1×2×3 block on the bottom-left: the left centre with its 5 pieces.",
      body: `<p>Solve a block three pieces long, two tall and one wide on the <b>left</b>
      side, at the bottom — the left centre, the bottom-left edge, and the two
      corner-and-edge pairs in front of and behind it. It is built fully
      intuitively, a bit like F2L pairs.</p>`,
      tip: "Start by placing the bottom-left edge next to the left centre, then add one pair at the front and one at the back.",
      algs: [],
    },
    {
      title: "Second block (right)",
      goal: "The same block on the right, without breaking the first.",
      body: `<p>Build the mirror block on the <b>right</b>. You may now use only the right
      layer (<code>R</code>, <code>r</code>), the top (<code>U</code>) and the middle
      slice (<code>M</code>) — any other turn would break the first block.</p>`,
      tip: "M turns are your friend here: they move pieces between front and back without touching either block.",
      algs: [],
    },
    {
      title: "CMLL — the top corners",
      goal: "The four top corners oriented and in place, all at once.",
      body: `<p>With both blocks built, solve the four top corners. The edges and centres
      of the M slice can be anything — Roux ignores them until the last step, which
      is why its corner algorithms are short.</p>
      <p>A gentle way in (2-look): first make the top corners yellow on top with the
      OLL corner sequences (Sune and friends), then swap corners with a corner swap.
      Full CMLL does both in one look.</p>`,
      tip: "Sune and Anti-Sune use only R and U turns, so they never touch your blocks.",
      algs: [
        { name: "Sune", alg: "R U R' U R U2 R'", check: "blocks",
          note: "One yellow corner on top — hold it at the front-left.", stickering: "CMLL" },
        { name: "Anti-Sune", alg: "R U2 R' U' R U' R'", check: "blocks",
          note: "One yellow corner on top — hold it at the back-right.", stickering: "CMLL" },
        { name: "Swap two corners (T-perm)", alg: "R U R' U' R' F R2 U' R' U' R U R' F'", check: "blocks",
          note: "Corners already yellow on top: swaps the two corners on the right. The edges do not matter yet in Roux.", stickering: "CMLL" },
      ],
    },
    {
      title: "LSE — the last six edges",
      goal: "Solved, using only M and U.",
      body: `<p>Six edges are left (four on top, two in the M slice at the front and back
      bottom), plus the M-slice centres. Everything is done with only
      <code>M</code> and <code>U</code> turns, in three parts:</p>
      <ol><li><b>Orient</b> the edges: make every edge's “good” colour face up or
      down (short patterns like <code>M' U M'</code> flip them in groups).</li>
      <li><b>Left and right edges:</b> put the top-left and top-right edges in place.</li>
      <li><b>The M slice:</b> cycle the last four edges home with <code>M2</code> and
      <code>U2</code> moves.</li></ol>`,
      tip: "LSE is best learned by playing: do M and U turns slowly and watch where each edge goes.",
      algs: [
        { name: "Swap opposite edges (M-slice)", alg: "M2 U M2 U2 M2 U M2", check: "edgesOnly",
          note: "The H-perm, done with M and U only — typical of LSE.", stickering: "L6E" },
      ],
    },
  ],
},

/* ======================================================================== */
{
  id: "zz",
  name: "ZZ",
  short: "ZZ",
  tagline: "Fix every edge's orientation first, then solve the rest turning only three faces.",
  level: 3, moves: "about 50–55", learn: "weeks", algs: "same last layer as CFOP",
  bestFor: "People who like smooth, rotation-free turning and planning ahead.",
  holding: "Keep one grip the whole time: after the first step you only ever turn <b>L</b>, <b>U</b> and <b>R</b>.",
  steps: [
    {
      title: "EOLine",
      goal: "Every edge “oriented”, plus the front-bottom and back-bottom edges placed.",
      body: `<p>An edge is <b>oriented</b> (good) if it can be solved using only
      <code>R</code>, <code>L</code>, <code>U</code> and <code>D</code> turns — those
      turns never flip an edge; only <code>F</code> and <code>B</code> do (a quarter
      turn of F or B flips four edges).</p>
      <p>In this step you spot the bad edges and fix them with F or B turns, and at
      the same time place the two bottom edges at the front and back (the “line”).
      From then on, F and B are never needed again.</p>`,
      tip: "A quick check: an edge is bad if its top/bottom-colour sticker faces a side, or its front/back-colour sticker faces up or down.",
      algs: [],
    },
    {
      title: "F2L with three faces",
      goal: "The first two layers, turning only L, U and R.",
      body: `<p>Build a 1×2×3 block on the left and one on the right (around the line),
      like Roux's blocks — but because every edge is already oriented, only
      <code>L</code>, <code>U</code> and <code>R</code> turns are needed. No cube
      rotations, no F or B turns: that is what makes ZZ turning so smooth.</p>`,
      tip: "Solve one side's block completely, then the other: you can turn freely on the side you are not building.",
      algs: [],
    },
    {
      title: "Last layer",
      goal: "Solved.",
      body: `<p>Because every edge was oriented in step one, the top edges are <b>already
      yellow on top</b>: you skip OLL's first look entirely. Finish with the corner
      OLL cases (Sune and friends) and then PLL, exactly as in CFOP.</p>
      <p>Advanced ZZ solvers use ZBLL to finish the whole last layer in one algorithm,
      but that set is large — the 2-look route is plenty for a long time.</p>`,
      tip: "Nothing new to learn here if you already know CFOP's last layer.",
      algs: [
        { name: "Sune", alg: "R U R' U R U2 R'", check: "f2l",
          note: "One yellow corner on top — hold it at the front-left.", stickering: "OLL" },
        { name: "T-perm", alg: "R U R' U' R' F R2 U' R' U' R U R' F'", check: "pll",
          note: "Headlights (a matching pair of corners) on the left; it swaps the two corners on the right.", stickering: "PLL" },
      ],
    },
  ],
},
];

const SOURCES = [
  {name: "Layer-by-layer method (Wikipedia)", url: "https://en.wikipedia.org/wiki/Layer-by-layer_method"},
  {name: "Rubik's official 3×3 solution guide (PDF)", url: "https://assets.ctfassets.net/r3qu44etwf9a/6kAQCoLmbXXu29TTuArrk1/404118e1f9bfb6f9997157a284bbc572/Rubiks_Solution-Guide_3x3.pdf"},
  {name: "CubeSkills — the beginner's method (PDF)", url: "https://www.cubeskills.com/uploads/pdf/tutorials/the-beginners-method-for-solving-the-rubiks-cube.pdf"},
  {name: "Ruwix — beginner's method", url: "https://ruwix.com/the-rubiks-cube/how-to-solve-the-rubiks-cube-beginners-method/"},
  {name: "CFOP method (Wikipedia)", url: "https://en.wikipedia.org/wiki/CFOP_method"},
  {name: "J Perm — CFOP", url: "https://jperm.net/3x3/cfop"},
  {name: "J Perm — 2-look OLL", url: "https://jperm.net/algs/2lookoll"},
  {name: "J Perm — 2-look PLL", url: "https://jperm.net/algs/2lookpll"},
  {name: "Speedsolving wiki — Roux method", url: "https://www.speedsolving.com/wiki/index.php/Roux_method"},
  {name: "Speedsolving wiki — ZZ method", url: "https://www.speedsolving.com/wiki/index.php?title=ZZ_method"},
  {name: "Speedsolving — choosing a speedsolving method", url: "https://www.speedsolving.com/threads/beginners-guide-to-choosing-a-speedsolving-method.43471/"},
];

/*
 * Questions people ask. Shown at the end of the guide and also published as
 * FAQPage structured data (build/prerender-guide.mjs), so keep each answer a
 * plain, self-contained statement; <b> and <code> are the only markup.
 */
const FAQ = [
  {q: "What is the fewest number of moves needed to solve a Rubik's cube?",
   a: "Every position of a 3×3 Rubik's cube can be solved in 20 moves or fewer (counting a half turn as one move). This limit, known as God's number, was proven in 2010. The <b>Shortest</b> mode of Cube Solver uses the two-phase algorithm and usually finds a solution of about 20 moves."},
  {q: "How long does it take to learn to solve a Rubik's cube?",
   a: "With the beginner layer-by-layer method, most people solve their first cube within an afternoon to a few days. It needs only 7 short move sequences. The CFOP speedsolving method takes longer: the 2-look version uses 16 sequences, and full CFOP uses about 78."},
  {q: "What is the easiest way to solve a Rubik's cube for beginners?",
   a: "The layer-by-layer (beginner) method: make a white cross, finish the white layer, solve the middle layer, then the yellow top in four short steps. It is the first method taught in this guide, and the solver can show every turn of it on your own cube in <b>Beginner</b> mode."},
  {q: "Which method do the fastest speedcubers use?",
   a: "CFOP (Cross, F2L, OLL, PLL) is the most widely used speedsolving method. Roux and ZZ are also used by some of the fastest solvers. This guide explains all three, plus the beginner method."},
  {q: "How does Cube Solver read the colours of my cube?",
   a: "Show each side of the cube to your camera, in any order and any way up. The colours are read in your browser from the live camera picture; the video is not uploaded, only the 54 colour readings are sent to the server to double-check them. You can also upload photos of the six sides or enter the colours by hand."},
  {q: "Is Cube Solver free? Do I need an account?",
   a: "Cube Solver is free and needs no account or sign-up. The solver, the guide and the timer all work in a web browser on a phone or a computer. The timer saves your solve times in your own browser only."},
  {q: "Why does the solver say my cube cannot be solved?",
   a: "Usually one sticker was read as the wrong colour, often red and orange under warm light. Use <b>Fix a colour</b> to correct it. If a piece was taken out and put back the wrong way, or a corner was twisted by hand, the cube really cannot be solved until that piece is put back correctly."},
  {q: "What do R, U, F and the apostrophe mean in cube moves?",
   a: "Each letter names a face: <b>R</b> right, <b>L</b> left, <b>U</b> up (top), <b>D</b> down, <b>F</b> front, <b>B</b> back. A letter alone means turn that face a quarter turn clockwise as you look at it; an apostrophe (<code>R'</code>) means anticlockwise; a 2 (<code>R2</code>) means a half turn."},
];

global.GUIDE = { METHODS, SOURCES, FAQ };
})(typeof window !== "undefined" ? window : globalThis);
