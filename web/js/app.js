import * as C from "./core.js";

const $ = (s) => document.querySelector(s);
const board = $("#board");
const REFERENCE_WALLS = [[2, 1], [2, 2], [2, 3], [4, 3], [4, 4]];   // the original single-map layout; not one of the 100 training layouts

const state = {
  walls: new Set(REFERENCE_WALLS.map(([x, y]) => C.key(x, y))),
  start: [0, 4], robot: [0, 4], modelKey: "jepa", world: null, report: null,
  run: null, timer: null, trail: [[0, 4]], plan: null, outcome: null, t: 0, collisions: 0,
  speed: 330, showD: false, seed: 0,
  mode: "full",          // full: picture of every cell; imagine: start + goal pictures only; explore: imagine + correct
  imap: null, match: null, planMatch: null, seen: [],
};
const MODE_NOTES = {
  full: "It is handed a picture of itself on every free cell before it starts (how the 100% results were measured).",
  imagine: "Only the start and goal pictures: it imagines the rest. Faded cells are missing from its imagined map; "
    + "dots mark the pictures it has really seen.",
  explore: "Starts like Imagination only, then swaps imagined cells for what it really sees as it walks, and trusts "
    + "moves it actually made. Faded = not imagined yet; dots = seen for real.",
};
const imagining = () => state.mode !== "full";
const models = {};

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
  const model = models[state.modelKey];
  if (!model) return;
  state.world = C.buildWorld(model, state.walls);
  state.report = C.graphReport(state.world);
}

// --- board ---------------------------------------------------------------------------------------
const cells = [];
for (let y = 0; y < C.ROWS; y++) for (let x = 0; x < C.COLS; x++) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "cell";
  b.dataset.x = x; b.dataset.y = y;
  b.setAttribute("role", "gridcell");
  b.innerHTML = `<span class="tile"></span><span class="dnum"></span>`;
  board.appendChild(b);
  cells.push(b);
}
const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
svg.setAttribute("viewBox", "0 0 6 5");
svg.classList.add("overlay");
svg.innerHTML = `<polyline class="trail"/><polyline class="planline"/><g class="plandots"></g>`;
board.appendChild(svg);
const robotEl = document.createElement("div");
robotEl.className = "robot";
robotEl.innerHTML = `<div class="body"></div>`;
robotEl.setAttribute("aria-label", "Robot (drag to move its start)");
board.appendChild(robotEl);

const isGoal = (x, y) => x === C.GOAL[0] && y === C.GOAL[1];
const eq = (a, b) => a[0] === b[0] && a[1] === b[1];
const cellAt = (x, y) => cells[y * C.COLS + x];

function placeRobot() {
  const [x, y] = state.robot;
  robotEl.style.transform = `translate(${x * 100}%, ${y * 100}%)`;
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
  const pts = (list) => list.map(([x, y]) => `${x + 0.5},${y + 0.5}`).join(" ");
  svg.querySelector(".trail").setAttribute("points", pts(state.trail));
  const plan = planCells.length ? [state.robot, ...planCells] : [];
  svg.querySelector(".planline").setAttribute("points", pts(plan));
  svg.querySelector(".plandots").innerHTML = plan.slice(1)
    .map(([x, y]) => `<circle class="plandot" cx="${x + 0.5}" cy="${y + 0.5}" r="0.09"/>`).join("");
  placeRobot();
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

const ARROW = ["↑", "↓", "←", "→"];
function drawPlan() {
  const el = $("#plan");
  if (!state.plan || state.outcome) {
    el.innerHTML = `<span class="muted small">${state.outcome ? "Done." : "Press Run or Step."}</span>`;
    return;
  }
  const { sequence, entries } = state.plan;
  const note = imagining() ? state.plan.how !== "goal" : state.plan.note;
  const D = imagining() ? state.planMap.D : state.world.D;
  const parts = sequence.map((a, k) => {
    const e = entries[k];
    const ghost = imagining() && e >= 0 && state.planMatch.cellOf[e] < 0;
    const where = e < 0 ? "unsure" : ghost ? "a place that isn't there" : D[e] === 0 ? "goal" : D[e] < 0 ? "exploring" : `${D[e]} to go`;
    return `<span class="mv${k === 0 ? " first" : ""}${e < 0 ? " unk" : ""}">${ARROW[a]} <span class="small muted">${where}</span></span>`;
  });
  const why = !note ? "" : imagining() && state.plan.how === "frontier"
    ? "no route in its imagined map: going to look at a cell it has only imagined"
    : "no trusted route: heading for the goal picture";
  el.innerHTML = parts.join("") + (why ? `<span class="small muted">${why}</span>` : "");
}

function drawStats() {
  const r = state.report;
  if (!r) return;
  const row = (dt, dd, cls = "") => `<dt>${dt}</dt><dd class="${cls}">${dd}</dd>`;
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
      row("Cells its imagination found", `${foundCells.size} / ${mc.length}`, foundCells.size === mc.length ? "ok" : "warn") +
      row("Imagined places that don't exist", ghosts, ghosts ? "warn" : "ok") +
      row("Imagined moves that match reality", `${right} / ${edges}`, right === edges ? "ok" : "") +
      row("Real pictures it has used", state.imap.nAnchors) +
      row("Walls on this map", state.walls.size);
  } else $("#stats").innerHTML =
    row("Imagined moves that match reality", `${r.correct} / ${r.edges}`, r.correct === r.edges ? "ok" : "") +
    row("Moves it isn't sure about (treated as walls)", r.unknown, r.unknown ? "warn" : "") +
    row("Wrong moves it trusted", r.wrongTrusted, r.wrongTrusted ? "bad" : "ok") +
    row("Cells with the right steps-to-goal", `${r.dExact} / ${r.cells}`, r.dExact === r.cells ? "ok" : "") +
    row("Walls on this map", state.walls.size);
  const note = $("#wallNote");
  const n = state.walls.size;
  note.hidden = n >= 3 && n <= 7;
  note.textContent = n > 7 ? `More walls than it ever trained with (3–7). This tests generalization.`
    : `Fewer walls than it trained with (3–7).`;
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

function drawAll() { drawBoard(); drawView(); drawPlan(); drawStats(); }

// --- running -------------------------------------------------------------------------------------
function stop() { clearInterval(state.timer); state.timer = null; $("#run").textContent = "▶ Run"; }

function resetRun() {
  stop();
  state.run = null; state.plan = null; state.outcome = null; state.t = 0; state.collisions = 0;
  state.robot = [...state.start]; state.trail = [[...state.start]];
  state.imap = state.match = state.planMatch = state.planMap = null; state.seen = [];
  if (imagining() && models.jepa && state.world) {
    state.run = newRun();
    const v = state.run.next().value;                 // the imagined map before the first move
    setImagined(v);
  }
  idleStatus();
  drawAll();
}

function newRun() {
  return imagining() ? C.runImagined(models.jepa, state.walls, state.start, state.seed, state.mode)
    : C.runEpisode(state.world, state.start, state.seed);
}

function setImagined(v) {
  state.imap = v.map;
  state.match = C.matchCells(models.jepa, state.walls, v.map, state.world.codebook);
  state.seen = state.mode === "explore" ? [...v.path, C.GOAL] : [state.start, C.GOAL];
  if (v.planMap) {
    state.planMap = v.planMap;
    state.planMatch = v.planMap === v.map ? state.match : C.matchCells(models.jepa, state.walls, v.planMap, state.world.codebook);
  }
}

function stepOnce() {
  if (!state.world) return;
  if (state.outcome) resetRun();
  if (!state.run) { if (imagining()) resetRun(); else state.run = newRun(); }
  const { value, done } = state.run.next();
  if (done || !value) { stop(); return; }
  if (imagining()) setImagined(value);
  state.robot = value.pos; state.trail = value.path; state.plan = value.plan; state.t = value.t;
  state.collisions = value.collisions;
  if (value.collision) {
    const [dx, dy] = C.ACTIONS[value.plan.action];
    robotEl.style.setProperty("--bx", `${dx * 14}%`); robotEl.style.setProperty("--by", `${dy * 14}%`);
    robotEl.classList.remove("bump"); void robotEl.offsetWidth; robotEl.classList.add("bump");
  }
  if (value.done) {
    state.outcome = value.outcome;
    stop();
    const opt = state.report.dTrue.get(C.key(...state.start));
    if (value.outcome === "goal") {
      robotEl.classList.remove("win"); void robotEl.offsetWidth; robotEl.classList.add("win");
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
      + (value.rebuilt ? ". New cell seen: re-imagined the map around it." : "."));
  }
  drawAll();
}

function play() {
  if (state.timer) { stop(); return; }
  if (state.outcome) resetRun();
  $("#run").textContent = "❚❚ Pause";
  stepOnce();
  state.timer = setInterval(() => { if (!state.outcome) stepOnce(); else stop(); }, state.speed);
}

// --- editing ---------------------------------------------------------------------------------------
function edited() { rebuild(); resetRun(); }

function canWall(x, y) { return !isGoal(x, y) && !eq([x, y], state.start); }

function toggleWall(x, y) {
  const k = C.key(x, y);
  if (state.walls.has(k)) state.walls.delete(k);
  else if (canWall(x, y)) state.walls.add(k);
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
    if (c && !state.walls.has(C.key(...c)) && canWall(...c)) state.walls.add(C.key(...c));
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
  edited();
}

$("#random").addEventListener("click", () => {
  const { walls, dt } = randomLayout(3, 7);
  loadLayout(walls, farthest(dt, 0.6));
});
$("#maze").addEventListener("click", () => {
  let best = null;
  for (let i = 0; i < 300; i++) {                     // like the test set: the most winding of many 8-12-wall layouts
    const m = randomLayout(8, 12);
    const ds = [...m.dt.values()].filter((d) => d > 0);
    const score = ds.reduce((a, b) => a + b, 0) / ds.length;
    if (!best || score > best.score) best = { ...m, score };
  }
  loadLayout(best.walls, farthest(best.dt));
});
$("#zigzag").addEventListener("click", () => {     // 10 walls (more than it trained on), 19-move route
  const zig = [[1, 1], [2, 1], [3, 1], [4, 1], [5, 1], [0, 3], [1, 3], [2, 3], [3, 3], [4, 3]];
  loadLayout(new Set(zig.map(([x, y]) => C.key(x, y))), [0, 4]);
});
$("#clear").addEventListener("click", () => loadLayout(new Set(), [...state.start]));
$("#run").addEventListener("click", play);
$("#step").addEventListener("click", () => { stop(); stepOnce(); });
$("#reset").addEventListener("click", resetRun);
function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".seg-btn").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.mode === mode)));
  $("#modeNote").textContent = MODE_NOTES[mode];
  resetRun();
}
document.querySelectorAll(".seg-btn").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
$(".seg").addEventListener("keydown", (e) => {
  const order = ["full", "imagine", "explore"];
  const d = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
  if (!d) return;
  e.preventDefault();
  const m = order[(order.indexOf(state.mode) + d + order.length) % order.length];
  setMode(m);
  document.querySelector(`.seg-btn[data-mode="${m}"]`).focus();
});
$("#modeNote").textContent = MODE_NOTES.full;
$("#showD").addEventListener("change", (e) => { state.showD = e.target.checked; drawBoard(); });
$("#speed").addEventListener("change", (e) => {
  state.speed = +e.target.value;
  if (state.timer) { stop(); play(); }
});

// --- start ---------------------------------------------------------------------------------------
drawAll();
getModel("jepa").then(() => { edited(); }).catch((err) => setStatus(`Could not load the model: ${err.message}`, "fail"));
