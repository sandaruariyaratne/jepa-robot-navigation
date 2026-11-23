import * as C from "./core.js?v=11";
import { createGraph, deriveGraph } from "./graph.js?v=11";

const $ = (s) => document.querySelector(s);
const board = $("#board");
const REFERENCE_WALLS = [[2, 1], [2, 2], [2, 3], [4, 3], [4, 4]];   // the original single-map layout; not one of the 100 training layouts
// The two worlds, one model each: 6 x 5 with the whole map in every picture, and 10 x 10 with fog of war.
const WORLDS = {
  jepa: { walls: REFERENCE_WALLS, start: [0, 4], random: [3, 7], maze: [8, 12],
          zigzag: [[1, 1], [2, 1], [3, 1], [4, 1], [5, 1], [0, 3], [1, 3], [2, 3], [3, 3], [4, 3]] },   // 10 walls, 19-move route
  fog: { walls: [[0, 3], [0, 4], [0, 5], [1, 2], [1, 3], [1, 8], [2, 2], [3, 6], [3, 7], [3, 8], [4, 0], [4, 2], [4, 3],   // test map 0
                 [4, 9], [5, 0], [5, 2], [5, 3], [5, 4], [6, 6], [7, 6], [7, 7], [7, 9], [9, 1], [9, 4]],
         start: [0, 9], random: [10, 25], maze: [25, 35],
         zigzag: [[0, 2], [1, 2], [2, 2], [3, 2], [4, 2], [5, 2], [6, 2], [3, 5], [4, 5], [5, 5], [6, 5], [7, 5], [8, 5], [9, 5],
                  [0, 8], [1, 8], [2, 8], [3, 8], [4, 8], [5, 8], [6, 8]] },                              // 21 walls, 3 switchbacks
};
const WORLD_NOTES = {
  jepa: "Every picture shows the whole map; only the robot moves.",
  fog: "Every picture shows only the 3 × 3 cells around the robot; the rest is fog, so it finds walls by walking. "
    + "A second model, trained on 70 fogged maps. In tests, “then explore” reached the goal on 100% of new maps and 97.8% of mazes.",
};

const state = {
  walls: new Set(REFERENCE_WALLS.map(([x, y]) => C.key(x, y))),
  start: [0, 4], robot: [0, 4], modelKey: "jepa", world: null, report: null,
  run: null, timer: null, trail: [[0, 4]], plan: null, outcome: null, t: 0, collisions: 0,
  speed: 330, showD: false, seed: 0,
  mode: "full",          // full: picture of every cell; imagine: start + goal pictures only; explore: imagine + correct
  imap: null, match: null, planMatch: null, seen: [], node: undefined, prevNode: undefined,
};
const MODE_NOTES = {
  full: "Before it starts, it is shown a picture of itself on every free cell. This is how the 100% results were measured.",
  imagine: "It gets only the start and goal pictures and imagines the rest. Hatched cells are missing from its imagined map; "
    + "a blue corner marks a picture it has really seen.",
  explore: "Starts the same way, then swaps imagined cells for what it really sees as it walks, and trusts moves it actually "
    + "made. Hatched cells are not imagined yet; a blue corner marks a picture it has really seen.",
};
const imagining = () => state.mode !== "full";
const models = {};
const model = () => models[state.modelKey];

// --- model -----------------------------------------------------------------------------------
async function getModel(k) {
  if (!models[k]) {
    const [meta, buf] = await Promise.all([
      fetch(`models/${k}.json`).then((r) => r.json()),
      fetch(`models/${k}.bin`).then((r) => r.arrayBuffer()),
    ]);
    models[k] = C.loadModel(meta, buf);
  }
  return models[k];
}

function rebuild() {
  if (!model()) return;
  state.world = C.buildWorld(model(), state.walls);
  state.report = C.graphReport(state.world);
}

// --- board ---------------------------------------------------------------------------------------
let cells = [];
const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
svg.classList.add("overlay");
svg.innerHTML = `<g class="futures"></g><polyline class="trail"/><polyline class="planline"/><g class="ghosts"></g>`;
board.appendChild(svg);
const robotEl = document.createElement("div");
robotEl.className = "robot";
robotEl.innerHTML = `<div class="body"><div class="eyes"><span class="eye-w"><span class="pupil"></span></span>`
  + `<span class="eye-w"><span class="pupil"></span></span></div></div>`;
robotEl.setAttribute("aria-label", "Robot (drag to move its start)");
board.appendChild(robotEl);

/** (Re)build everything sized by the grid: board cells, overlays, the imagined graph and the camera view. */
function buildBoard() {
  cells.forEach((b) => b.remove());
  cells = [];
  for (let y = 0; y < C.ROWS; y++) for (let x = 0; x < C.COLS; x++) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "cell";
    b.dataset.x = x; b.dataset.y = y;
    b.setAttribute("role", "gridcell");
    b.innerHTML = `<span class="tile">${x === C.GOAL[0] && y === C.GOAL[1] ? '<span class="goal-label">Goal</span>' : ""}</span>`
      + `<span class="seen-mark"></span><span class="dnum"></span>`;
    board.insertBefore(b, svg);
    cells.push(b);
  }
  svg.setAttribute("viewBox", `0 0 ${C.COLS} ${C.ROWS}`);
  board.setAttribute("aria-label", `${C.COLS} by ${C.ROWS} grid world`);
  const root = document.documentElement.style;
  root.setProperty("--cols", C.COLS); root.setProperty("--rows", C.ROWS);
  root.setProperty("--vw", C.W); root.setProperty("--vh", C.H);
  $("#view").width = C.W; $("#view").height = C.H;
  $("#viewSize").textContent = `${C.W}×${C.H} pixels`;
  board.classList.toggle("fogged", C.VIEW_RADIUS !== null);
  const g = $("#graph");
  g.setAttribute("viewBox", `-0.45 -0.375 ${C.COLS + 0.9} ${C.ROWS + 0.75}`);
  graph = createGraph(g);
  drawnPlan = "";
}

const isGoal = (x, y) => x === C.GOAL[0] && y === C.GOAL[1];
const eq = (a, b) => a[0] === b[0] && a[1] === b[1];
const cellAt = (x, y) => cells[y * C.COLS + x];

function placeRobot() {
  const [x, y] = state.robot;
  robotEl.style.setProperty("--rx", `${x * 100}%`);
  robotEl.style.setProperty("--ry", `${y * 100}%`);
}

/** Where the eyes point: the move it is about to make, else towards the goal. */
function look(dx, dy) {
  const n = Math.hypot(dx, dy) || 1;
  robotEl.style.setProperty("--lx", (dx / n).toFixed(2));
  robotEl.style.setProperty("--ly", (dy / n).toFixed(2));
}
function lookAhead() {
  if (state.plan && !state.outcome) { const [dx, dy] = C.ACTIONS[state.plan.sequence[0]]; look(dx, dy); }
  else if (state.outcome === "goal") look(0, 0);
  else look(C.GOAL[0] - state.robot[0], C.GOAL[1] - state.robot[1]);
}

function drawBoard() {
  const dt = state.report ? state.report.dTrue : C.trueDistances(state.walls);
  const imagined = new Set();
  const planCells = planPath();
  for (const c of planCells) imagined.add(C.key(...c));
  const found = new Map();                 // imagine modes: cell -> smallest D of the nodes matching it
  if (imagining() && state.imap && state.match) {
    state.match.cellOf.forEach((ci, u) => {
      if (ci < 0) return;
      const k = C.key(...state.match.cells[ci]);
      const d = state.imap.D[u];
      const cur = found.get(k);
      if (cur === undefined || (d >= 0 && (cur < 0 || d < cur))) found.set(k, d);
    });
  }
  const seen = new Set(imagining() ? state.seen.map((c) => C.key(...c)) : []);
  for (const b of cells) {
    const x = +b.dataset.x, y = +b.dataset.y, k = C.key(x, y);
    const wall = state.walls.has(k);
    b.classList.toggle("wall", wall);
    b.classList.toggle("goal", isGoal(x, y));
    b.classList.toggle("unreach", !wall && !dt.has(k));
    b.classList.toggle("imag", imagined.has(k));
    b.classList.toggle("fog", imagining() && !wall && !found.has(k));
    b.classList.toggle("seen", seen.has(k));
    b.classList.toggle("outside", !C.inView(state.robot, x, y));     // fog of war: outside the robot's view
    const label = wall ? "wall" : isGoal(x, y) ? "goal" : "floor";
    b.setAttribute("aria-label", `cell ${x},${y}: ${label}`);
    const num = b.querySelector(".dnum");
    num.className = "dnum";
    num.textContent = "";
    if (state.showD && !wall && state.world) {
      const d = imagining() ? (found.has(k) ? found.get(k) : -1) : state.world.D[state.world.index.get(k)];
      const truth = dt.has(k) ? dt.get(k) : -1;
      num.textContent = d < 0 ? "?" : String(d);
      if (d < 0 && truth >= 0) num.classList.add("unk");
      else if (d !== truth) num.classList.add("off");
    }
  }
  board.classList.toggle("show-d", state.showD);
  const pts = (list) => list.map(([x, y]) => `${x + 0.5},${y + 0.5}`).join(" ");
  svg.querySelector(".trail").setAttribute("points", pts(state.trail));
  const plan = planCells.length ? [state.robot, ...planCells] : [];
  svg.querySelector(".planline").setAttribute("points", pts(plan));
  const sig = plan.map(String).join("|");
  if (sig !== drawnPlan) {                       // ghosts of itself where it imagines being, nearest first
    drawnPlan = sig;
    const aim = planCells.length ? planAim() : 0;
    svg.querySelector(".ghosts").innerHTML = planCells.map(([x, y], k) =>
      `<rect class="ghost ghost-in" style="--k:${k}" x="${x + 0.16}" y="${y + 0.16}" width="0.68" height="0.68" rx="0.12" opacity="${k > aim ? 0.22 : 0.95 - k * 0.2}"/>`).join("");
  }
  if (!state.plan || state.outcome) svg.querySelector(".futures").innerHTML = "";
  placeRobot();
  lookAhead();
}
let drawnPlan = "";

/** The step its score comes from: min_k [k + 1 + D(node_k)]. Moves after it are tie-breaks that change nothing. */
function planAim() {
  const { entries } = state.plan;
  const D = !imagining() ? state.world.D : state.plan.how === "frontier" ? state.planMap.dFrontier : state.planMap.D;
  let aim = entries.length - 1, best = Infinity;
  for (let k = 0; k < entries.length; k++) {
    const e = entries[k];
    if (e < 0) break;
    if (D && D[e] >= 0 && k + 1 + D[e] < best) { best = k + 1 + D[e]; aim = k; }
  }
  return aim;
}

/** Cells along the current plan; in the imagine modes a node that matches no real cell ends the line. */
function planPath() {
  if (!state.plan || state.outcome) return [];
  const out = [];
  for (const e of state.plan.entries) {
    if (e < 0) break;
    const ci = imagining() ? state.planMatch.cellOf[e] : e;
    if (ci < 0) break;
    out.push(imagining() ? state.planMatch.cells[ci] : state.world.cells[ci]);
  }
  return out;
}

// --- the imagined graph ---------------------------------------------------------------------------------
let graph = null;

/** Redraw the graph panel. With fresh = true (a new step) also draw every future it rolled out. */
function drawGraph(fresh = false) {
  const g = deriveGraph(state);
  if (!g) { graph.draw(null); return; }
  const extra = {};
  if (state.plan && !state.outcome) {
    // plan nodes live in the map it planned on; in explore mode that can be the map before this step's rebuild
    const same = !imagining() || state.planMap === state.imap;
    const at = (e) => {
      if (e < 0) return null;
      if (same) return g.pos[e] || null;
      const ci = state.planMatch.cellOf[e];
      return ci < 0 ? null : state.planMatch.cells[ci].map((v) => v + 0.5);
    };
    const from = imagining() ? g.pos[state.prevNode] : g.pos[state.world.index.get(C.key(...state.trail[Math.max(0, state.trail.length - 2)]))];
    if (from) {
      const aim = planAim(), line = [from];
      for (let k = 0; k <= aim; k++) { const p = at(state.plan.entries[k]); if (!p) break; line.push(p); }
      extra.plan = line;
      if (fresh && state.plan.futures) {
        const finite = state.plan.futures.map((f) => f.cost).filter(Number.isFinite);
        const best = finite.length ? Math.min(...finite) : 0;
        const segs = new Map();
        for (const f of state.plan.futures) {
          const w = Number.isFinite(f.cost) ? Math.max(0.14, 0.85 * Math.exp(-(f.cost - best) / 1.4)) : 0.08;
          let prev = from;
          for (let k = 0; k < f.entries.length; k++) {
            const p = at(f.entries[k]);
            if (!p) break;
            if (p[0] !== prev[0] || p[1] !== prev[1]) {
              const id = [prev, p].map(String).sort().join("|");
              const sg = segs.get(id);
              if (!sg) segs.set(id, { a: prev, b: p, k, w });
              else { sg.w = Math.max(sg.w, w); sg.k = Math.min(sg.k, k); }
            }
            prev = p;
          }
        }
        extra.futures = [...segs.values()];
      }
    }
  } else extra.futures = [];
  graph.draw(g, extra);
}

// --- side panel ------------------------------------------------------------------------------------
const view = $("#view").getContext("2d");
function drawView() {
  const f = C.render(state.walls, state.robot);
  const img = view.createImageData(C.W, C.H);
  for (let p = 0; p < C.W * C.H; p++) {
    img.data[4 * p] = f[p]; img.data[4 * p + 1] = f[C.W * C.H + p]; img.data[4 * p + 2] = f[2 * C.W * C.H + p];
    img.data[4 * p + 3] = 255;
  }
  view.putImageData(img, 0, 0);
}

const ROT = [0, 180, 270, 90];               // up, down, left, right
const arrow = (a) => `<svg class="arrow" viewBox="0 0 24 24" aria-hidden="true" style="transform:rotate(${ROT[a]}deg)"><path d="M12 3l7 8h-4.5v10h-5V11H5z"/></svg>`;
let lastPlanT = -1;
function drawPlan() {
  const el = $("#plan");
  const why = $("#planWhy");
  if (!state.plan || state.outcome) {
    el.innerHTML = [0, 1, 2].map((k) => `<li class="slot"><span class="n">${k + 1}</span></li>`).join("");
    el.classList.remove("fresh");
    why.textContent = state.outcome ? "Done. Press Run to watch it again." : "Press Run or Step to watch it think.";
    lastPlanT = -1;
    return;
  }
  const { sequence, entries } = state.plan;
  const note = imagining() ? state.plan.how !== "goal" : state.plan.note;
  const D = imagining() ? state.planMap.D : state.world.D;
  const aim = planAim();
  el.innerHTML = sequence.map((a, k) => {
    const e = entries[k];
    const ghost = imagining() && e >= 0 && state.planMatch.cellOf[e] < 0;
    const spare = k > aim && e >= 0;
    const where = e < 0 ? "Not sure what happens" : spare ? "Doesn't change the score" : ghost ? "A place that isn't there"
      : D[e] === 0 ? "Goal" : D[e] < 0 ? "Exploring" : `${D[e]} more to the goal`;
    const cls = e < 0 ? "unsure" : spare ? "spare" : "live";
    return `<li class="slot ${cls}${k === 0 ? " first" : ""}" style="--k:${k}" aria-label="Move ${k + 1}: ${C.ACTION_NAMES[a]}, ${where}">`
      + `<span class="n">${k === 0 ? "Taken" : k + 1}</span>${arrow(a)}<span class="what">${where}</span></li>`;
  }).join("");
  if (state.t !== lastPlanT) { el.classList.remove("fresh"); void el.offsetWidth; el.classList.add("fresh"); lastPlanT = state.t; }
  why.textContent = !note ? "" : imagining() && state.plan.how === "frontier"
    ? "No route in its imagined map, so it goes to look at a cell it has only imagined."
    : "No route it trusts, so it heads for the goal picture.";
}

const withCls = ([dd, frac], cls) => [dd, cls, frac];
function drawStats() {
  const r = state.report;
  if (!r) return;
  const row = (dt, dd, cls = "", frac = null) => `<div class="row ${cls}"><dt>${dt}</dt><dd>${dd}</dd>`
    + (frac === null ? "" : `<span class="meter" aria-hidden="true"><i style="--v:${frac.toFixed(3)}"></i></span>`) + `</div>`;
  const of = (a, b) => [`${a} / ${b}`, b ? a / b : 0];
  if (imagining() && state.imap && state.match) {
    const { cellOf, cells: mc } = state.match;
    const foundCells = new Set(cellOf.filter((c) => c >= 0));
    const ghosts = cellOf.filter((c) => c < 0).length;
    let edges = 0, right = 0;
    cellOf.forEach((ci, u) => {
      if (ci < 0) return;
      for (let a = 0; a < C.ACTIONS.length; a++) {
        edges++;
        const t = state.world.index.get(C.key(...C.transition(state.walls, mc[ci], a).pos));
        if (cellOf[state.imap.next[u][a]] === t) right++;
      }
    });
    $("#stats").innerHTML =
      row("Cells its imagination found", ...withCls(of(foundCells.size, mc.length), foundCells.size === mc.length ? "ok" : "warn")) +
      row("Imagined places that don't exist", ghosts, ghosts ? "warn" : "ok") +
      row("Imagined moves that match reality", ...withCls(of(right, edges), right === edges ? "ok" : "")) +
      row("Real pictures it has used", state.imap.nAnchors) +
      row("Walls on this map", state.walls.size);
  } else $("#stats").innerHTML =
    row("Imagined moves that match reality", ...withCls(of(r.correct, r.edges), r.correct === r.edges ? "ok" : "")) +
    row("Moves it isn't sure about (treated as walls)", r.unknown, r.unknown ? "warn" : "") +
    row("Wrong moves it trusted", r.wrongTrusted, r.wrongTrusted ? "bad" : "ok") +
    row("Cells where it knows the right distance to the goal", ...withCls(of(r.dExact, r.cells), r.dExact === r.cells ? "ok" : "")) +
    row("Walls on this map", state.walls.size);
  const note = $("#wallNote");
  const n = state.walls.size, [lo, hi] = model() ? model().meta.trained_on.walls : [3, 7];
  note.hidden = n >= lo && n <= hi;
  note.textContent = n > hi ? `More walls than it ever trained with (${lo}–${hi}). This tests generalization.`
    : `Fewer walls than it trained with (${lo}–${hi}).`;
}

function setStatus(text, cls = "") {
  const el = $("#status");
  el.className = `status ${cls}`;
  el.textContent = text;
}

function idleStatus() {
  const dt = state.report ? state.report.dTrue : C.trueDistances(state.walls);
  const d = dt.get(C.key(...state.start));
  if (d === undefined) setStatus("No route from the robot to the goal. Move the robot or remove a wall.", "warn");
  else setStatus(`Ready. Shortest route: ${d} moves. The robot doesn't know that; press Run.`);
  $("#run").disabled = $("#step").disabled = d === undefined;
}

function drawAll() { drawBoard(); drawView(); drawPlan(); drawStats(); drawGraph(); }

// --- running -------------------------------------------------------------------------------------
function setRunButton(playing) {
  $("#run").classList.toggle("playing", playing);
  $(".run-label").textContent = playing ? "Pause" : "Run";
}
function stop() { clearInterval(state.timer); state.timer = null; setRunButton(false); }

function resetRun() {
  stop();
  state.run = null; state.plan = null; state.outcome = null; state.t = 0; state.collisions = 0;
  state.robot = [...state.start]; state.trail = [[...state.start]];
  state.imap = state.match = state.planMatch = state.planMap = null; state.seen = [];
  state.node = state.prevNode = state.world ? state.world.index.get(C.key(...state.start)) : undefined;
  if (imagining() && model() && state.world) {
    state.run = newRun();
    const v = state.run.next().value;                 // the imagined map before the first move
    setImagined(v);
    state.node = state.prevNode = v.node;
  }
  idleStatus();
  drawAll();
}

function newRun() {
  return imagining() ? C.runImagined(model(), state.walls, state.start, state.seed, state.mode)
    : C.runEpisode(state.world, state.start, state.seed);
}

function setImagined(v) {
  state.imap = v.map;
  state.match = C.matchCells(model(), state.walls, v.map, state.world.codebook);
  state.seen = state.mode === "explore" ? [...v.path, C.GOAL] : [state.start, C.GOAL];
  if (v.planMap) {
    state.planMap = v.planMap;
    state.planMatch = v.planMap === v.map ? state.match : C.matchCells(model(), state.walls, v.planMap, state.world.codebook);
  }
}

function stepOnce() {
  if (!state.world) return;
  if (state.outcome) resetRun();
  if (!state.run) { if (imagining()) resetRun(); else state.run = newRun(); }
  const { value, done } = state.run.next();
  if (done || !value) { stop(); return; }
  if (imagining()) setImagined(value);
  state.prevNode = state.node;
  state.node = imagining() ? value.node : state.world.index.get(C.key(...value.pos));
  state.robot = value.pos; state.trail = value.path; state.plan = value.plan; state.t = value.t;
  state.collisions = value.collisions;
  if (value.collision) {
    const [dx, dy] = C.ACTIONS[value.plan.action];
    robotEl.style.setProperty("--bx", `${dx * 14}%`); robotEl.style.setProperty("--by", `${dy * 14}%`);
    robotEl.style.setProperty("--sx", dx ? 0.86 : 1.08); robotEl.style.setProperty("--sy", dy ? 0.86 : 1.08);
    robotEl.classList.remove("bump"); void robotEl.offsetWidth; robotEl.classList.add("bump");
  }
  if (value.done) {
    state.outcome = value.outcome;
    stop();
    const opt = state.report.dTrue.get(C.key(...state.start));
    if (value.outcome === "goal") {
      robotEl.classList.remove("win"); void robotEl.offsetWidth; robotEl.classList.add("win");
      const g = cellAt(...C.GOAL); g.classList.remove("reached"); void g.offsetWidth; g.classList.add("reached");
      setStatus(value.t === opt ? `Reached the goal in ${value.t} moves: the shortest possible route.`
        : `Reached the goal in ${value.t} moves (shortest possible: ${opt}).`, "goal");
    } else if (value.outcome === "loop") setStatus(`Stuck: it came back to the same cell 3 times after ${value.t} moves.`, "fail");
    else setStatus(`Gave up after ${value.t} moves without reaching the goal.`, "fail");
  } else {
    const how = value.plan.how;
    const why = how === "frontier" ? ": no route in its imagined map, so it went to look"
      : how === "fallback" ? ": nothing known, heading for the goal picture" : "";
    setStatus(`Move ${value.t}: imagined 64 futures, chose ${C.ACTION_NAMES[value.plan.action]}${why}`
      + (value.collision ? " and bumped into a wall" : "")
      + (value.rebuilt ? ". New cell seen: re-imagined the map around it." : "."), "think");
  }
  drawBoard(); drawView(); drawPlan(); drawStats(); drawGraph(true);
}

function play() {
  if (state.timer) { stop(); return; }
  if (state.outcome) resetRun();
  setRunButton(true);
  stepOnce();
  state.timer = setInterval(() => { if (!state.outcome) stepOnce(); else stop(); }, state.speed);
}

// --- editing ---------------------------------------------------------------------------------------
function edited() { rebuild(); resetRun(); }

/** Motion that answers an edit: a wall drops onto the board, or lifts off it. */
function pulse(x, y, cls) {
  const el = cellAt(x, y);
  el.classList.remove("drop-in", "lift"); void el.offsetWidth; el.classList.add(cls);
}

function canWall(x, y) { return !isGoal(x, y) && !eq([x, y], state.start); }

function toggleWall(x, y) {
  const k = C.key(x, y);
  if (state.walls.has(k)) { state.walls.delete(k); pulse(x, y, "lift"); }
  else if (canWall(x, y)) { state.walls.add(k); pulse(x, y, "drop-in"); }
  else return;
  edited();
}

function cellFromPoint(px, py) {
  const el = document.elementFromPoint(px, py);
  const c = el && el.closest(".cell");
  return c && board.contains(c) ? [+c.dataset.x, +c.dataset.y] : null;
}

let drag = null, ghost = null;
function clearDrop() { cells.forEach((c) => c.classList.remove("drop", "bad")); }

function beginDrag(e, kind, from) {
  if (e.button !== undefined && e.button !== 0) return;
  e.preventDefault();
  drag = { kind, from, x0: e.clientX, y0: e.clientY, moved: false, painted: new Set() };
  if (state.timer || state.outcome || state.run) { stop(); }
}

function makeGhost(kind) {
  ghost = document.createElement("div");
  const size = board.getBoundingClientRect().width / C.COLS - 6;
  ghost.className = `drag-ghost ${kind === "robot" ? "robot-g" : "wall"}`;
  ghost.style.width = ghost.style.height = `${size}px`;
  document.body.appendChild(ghost);
}

window.addEventListener("pointermove", (e) => {
  if (!drag && !state.timer && !(state.plan && !state.outcome)) {
    const r = robotEl.getBoundingClientRect();
    if (r.width) look(e.clientX - (r.left + r.width / 2), e.clientY - (r.top + r.height / 2));
  }
  if (!drag) return;
  if (!drag.moved && Math.hypot(e.clientX - drag.x0, e.clientY - drag.y0) < 6) return;
  if (!drag.moved) {
    drag.moved = true;
    if (drag.kind !== "paint") makeGhost(drag.kind);
    if (drag.kind === "robot") robotEl.classList.add("dragging");
    if (drag.kind === "move") { state.walls.delete(C.key(...drag.from)); drawBoard(); }
    if (drag.kind === "paint") paintAt(drag.from);
  }
  if (ghost) { ghost.style.left = `${e.clientX}px`; ghost.style.top = `${e.clientY}px`; }
  const c = cellFromPoint(e.clientX, e.clientY);
  clearDrop();
  if (drag.kind === "paint") { if (c) paintAt(c); return; }
  if (c) {
    const el = cellAt(...c);
    const ok = drag.kind === "robot" ? !state.walls.has(C.key(...c)) && !isGoal(...c)
      : !state.walls.has(C.key(...c)) && canWall(...c);
    el.classList.add("drop");
    if (!ok) el.classList.add("bad");
  }
});

function paintAt([x, y]) {
  const k = C.key(x, y);
  if (drag.painted.has(k) || state.walls.has(k) || !canWall(x, y)) return;
  drag.painted.add(k);
  state.walls.add(k);
  pulse(x, y, "drop-in");
  drawBoard();
}

window.addEventListener("pointerup", (e) => {
  if (!drag) return;
  const d = drag;
  drag = null;
  clearDrop();
  if (ghost) { ghost.remove(); ghost = null; }
  robotEl.classList.remove("dragging");
  const c = cellFromPoint(e.clientX, e.clientY);
  if (!d.moved) {                                     // a tap
    if ((d.kind === "move" || d.kind === "paint") && d.from) toggleWall(...d.from);
    else if (d.kind === "robot") resetRun();
    return;
  }
  if (d.kind === "robot") {
    if (c && !state.walls.has(C.key(...c)) && !isGoal(...c)) state.start = c;
    resetRun();
    return;
  }
  if (d.kind === "new" || d.kind === "move") {
    if (c && !state.walls.has(C.key(...c)) && canWall(...c)) { state.walls.add(C.key(...c)); pulse(...c, "drop-in"); }
    else if (d.kind === "move" && !c) { /* dropped off the board: removed */ }
    else if (d.kind === "move") state.walls.add(C.key(...d.from));   // invalid target: put it back
  }
  edited();
});
window.addEventListener("pointercancel", () => { if (drag) { drag = null; clearDrop(); ghost?.remove(); ghost = null; edited(); } });

board.addEventListener("pointerdown", (e) => {
  if (e.target.closest(".robot")) { beginDrag(e, "robot", state.robot); return; }
  const c = e.target.closest(".cell");
  if (!c) return;
  const x = +c.dataset.x, y = +c.dataset.y;
  if (isGoal(x, y)) return;
  beginDrag(e, state.walls.has(C.key(x, y)) ? "move" : "paint", [x, y]);
});
board.addEventListener("keydown", (e) => {
  const c = e.target.closest(".cell");
  if (c && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); toggleWall(+c.dataset.x, +c.dataset.y); }
});
$("#wallChip").addEventListener("pointerdown", (e) => beginDrag(e, "new", null));

// --- presets ---------------------------------------------------------------------------------------
function randomLayout(minW, maxW) {
  const all = [];
  for (let y = 0; y < C.ROWS; y++) for (let x = 0; x < C.COLS; x++) if (!isGoal(x, y)) all.push([x, y]);
  for (;;) {
    const n = minW + Math.floor(Math.random() * (maxW - minW + 1));
    const pick = [...all].sort(() => Math.random() - 0.5).slice(0, n);
    const walls = new Set(pick.map(([x, y]) => C.key(x, y)));
    const dt = C.trueDistances(walls);
    if (dt.size === C.COLS * C.ROWS - walls.size) return { walls, dt };   // every free cell reaches the goal
  }
}

function farthest(dt, minFrac = 1) {
  const list = [...dt.entries()].filter(([, d]) => d > 0).sort((a, b) => b[1] - a[1]);
  const top = list.filter(([, d]) => d >= list[0][1] * minFrac);
  return top[Math.floor(Math.random() * top.length)][0].split(",").map(Number);
}

function loadLayout(walls, start) {
  state.walls = walls; state.start = start; state.seed += 1;
  graph.regrow();
  edited();
}

const world = () => WORLDS[state.modelKey];
$("#random").addEventListener("click", () => {
  const { walls, dt } = randomLayout(...world().random);
  loadLayout(walls, farthest(dt, 0.6));
});
$("#maze").addEventListener("click", () => {
  let best = null;
  for (let i = 0; i < 300; i++) {                     // like the test set: the most winding of many dense layouts
    const m = randomLayout(...world().maze);
    const ds = [...m.dt.values()].filter((d) => d > 0);
    const score = ds.reduce((a, b) => a + b, 0) / ds.length;
    if (!best || score > best.score) best = { ...m, score };
  }
  loadLayout(best.walls, farthest(best.dt));
});
$("#zigzag").addEventListener("click", () => {
  loadLayout(new Set(world().zigzag.map(([x, y]) => C.key(x, y))), [...world().start]);
});
$("#clear").addEventListener("click", () => loadLayout(new Set(), [...state.start]));
$("#run").addEventListener("click", play);
$("#step").addEventListener("click", () => { stop(); stepOnce(); });
$("#reset").addEventListener("click", resetRun);
function setMode(mode) {
  state.mode = mode;
  graph.regrow();
  document.querySelectorAll(".seg-mode .seg-btn").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.mode === mode)));
  $(".seg-mode").style.setProperty("--i", ["full", "imagine", "explore"].indexOf(mode));
  $("#modeNote").textContent = MODE_NOTES[mode];
  resetRun();
}
document.querySelectorAll(".seg-mode .seg-btn").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
$(".seg-mode").addEventListener("keydown", (e) => {
  const order = ["full", "imagine", "explore"];
  const d = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
  if (!d) return;
  e.preventDefault();
  const m = order[(order.indexOf(state.mode) + d + order.length) % order.length];
  setMode(m);
  document.querySelector(`.seg-btn[data-mode="${m}"]`).focus();
});

// --- world: 6 x 5 (sees everything) or 10 x 10 (fog of war); each has its own model -------------------
const WORLD_ORDER = ["jepa", "fog"];
let loadingWorld = null;
async function setWorld(k) {
  if (loadingWorld) return;
  stop();
  document.querySelectorAll(".seg-world .seg-btn").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.world === k)));
  $(".seg-world").style.setProperty("--i", WORLD_ORDER.indexOf(k));
  $("#worldNote").textContent = WORLD_NOTES[k];
  if (!models[k]) setStatus("Loading the model for this world…");
  loadingWorld = k;
  try { await getModel(k); }
  catch (err) { setStatus(`Could not load the model: ${err.message}`, "fail"); loadingWorld = null; return; }
  loadingWorld = null;
  state.modelKey = k;
  C.setGrid(models[k].meta.grid);
  state.walls = new Set(WORLDS[k].walls.map(([x, y]) => C.key(x, y)));
  state.start = [...WORLDS[k].start];
  state.seed += 1;
  state.world = state.report = null;
  buildBoard();
  edited();
}
document.querySelectorAll(".seg-world .seg-btn").forEach((b) => b.addEventListener("click", () => {
  if (b.dataset.world !== state.modelKey) setWorld(b.dataset.world);
}));
$(".seg-world").addEventListener("keydown", (e) => {
  const d = ["ArrowRight", "ArrowDown"].includes(e.key) ? 1 : ["ArrowLeft", "ArrowUp"].includes(e.key) ? -1 : 0;
  if (!d) return;
  e.preventDefault();
  const k = WORLD_ORDER[(WORLD_ORDER.indexOf(state.modelKey) + d + WORLD_ORDER.length) % WORLD_ORDER.length];
  setWorld(k).then(() => document.querySelector(`.seg-btn[data-world="${k}"]`).focus());
});
$("#worldNote").textContent = WORLD_NOTES.jepa;
$("#modeNote").textContent = MODE_NOTES.full;
$("#showD").addEventListener("change", (e) => { state.showD = e.target.checked; drawBoard(); });
const TIMING = { 650: [".6s", ".5s"], 330: [".45s", ".32s"], 120: [".2s", ".1s"] };   // move, think
function setSpeed(ms) {
  state.speed = ms;
  document.querySelectorAll(".speed button").forEach((b) => b.setAttribute("aria-checked", String(+b.dataset.speed === ms)));
  board.style.setProperty("--move-dur", TIMING[ms][0]);
  board.style.setProperty("--think", TIMING[ms][1]);
  if (state.timer) { stop(); play(); }
}
document.querySelectorAll(".speed button").forEach((b) => b.addEventListener("click", () => setSpeed(+b.dataset.speed)));

// --- start ---------------------------------------------------------------------------------------
buildBoard();
drawAll();
getModel("jepa").then(() => { edited(); }).catch((err) => setStatus(`Could not load the model: ${err.message}`, "fail"));
