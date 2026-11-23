// The imagined transition graph, drawn beside the board. Display only: nothing here feeds the agent.
// Nodes sit at the cell whose frame they match (the agent itself never sees coordinates). Edges are the
// predictor's snapped transitions; each is checked against the real environment to colour it.
import * as C from "./core.js?v=20";

const NS = "http://www.w3.org/2000/svg";
const DUP = [[0, 0], [0.24, -0.22], [-0.24, 0.22], [0.24, 0.22], [-0.24, -0.22], [0, 0.3], [0, -0.3]];
const fmt = (v) => +v.toFixed(3);

/** Everything the panel needs, from the app state. */
export function deriveGraph(s) {
  const imag = s.mode !== "full";
  const map = imag ? s.imap : s.world;
  if (!map) return null;
  const dTrue = s.report ? s.report.dTrue : C.trueDistances(s.walls);
  const n = map.codebook.length;
  // the real cell each node stands for (-1: none)
  const cellOf = imag ? s.match.cellOf.map((ci) => (ci < 0 ? null : s.match.cells[ci])) : map.cells;
  const realIndex = new Map(C.freeCells(s.walls).map((c, i) => [C.key(...c), i]));

  // positions
  const pos = new Array(n), keys = new Array(n), used = new Map();
  for (let u = 0; u < n; u++) {
    const c = cellOf[u];
    if (!c) continue;
    const k = C.key(...c), d = used.get(k) || 0;
    used.set(k, d + 1);
    const [ox, oy] = DUP[d % DUP.length];
    pos[u] = [c[0] + 0.5 + ox, c[1] + 0.5 + oy];
    keys[u] = `c${k}#${d}`;
  }
  let stray = 0;
  for (let u = 0; u < n; u++) {               // hallucinated nodes: next to the node they were imagined from
    if (pos[u]) continue;
    let placed = false;
    for (let p = 0; p < n && !placed; p++) {
      if (!pos[p] || p === u) continue;
      for (let a = 0; a < 4; a++) if (map.known[p][a] && map.next[p][a] === u) {
        const [dx, dy] = C.ACTIONS[a];
        // chains of imagined places can run on far past the grid (fog world): keep them on the board
        const clamp = (v, hi) => Math.min(hi - 0.12, Math.max(0.12, v));
        pos[u] = [clamp(pos[p][0] + dx * 0.56 + 0.08 * (stray % 5), C.COLS), clamp(pos[p][1] + dy * 0.56 + 0.08 * (stray % 5), C.ROWS)];
        keys[u] = `h${keys[p]}>${a}`;
        placed = true;
        break;
      }
    }
    if (!placed) { pos[u] = [0.3 + (0.36 * stray) % C.COLS, C.ROWS + 0.2]; keys[u] = `h-${stray}`; }
    stray++;
  }

  const nodes = [];
  for (let u = 0; u < n; u++) {
    const c = cellOf[u];
    const kind = !c ? "halluc" : imag && u >= map.nAnchors ? "imag" : "real";
    const D = map.D[u];
    const truth = c ? (dTrue.has(C.key(...c)) ? dTrue.get(C.key(...c)) : -1) : null;
    nodes.push({ u, key: keys[u], p: pos[u], kind, goal: u === map.goal, D, off: truth !== null && D >= 0 && D !== truth });
  }

  // edges, merged per node pair
  const pairs = new Map(), stubs = [];
  for (let u = 0; u < n; u++) for (let a = 0; a < 4; a++) {
    if (!map.known[u][a]) { stubs.push({ u, a, key: `${keys[u]}?${a}` }); continue; }
    const v = map.next[u][a];
    if (v === u) continue;                   // it imagines a bump: nothing to draw
    let wrong = true;                        // a move from a place that doesn't exist can't be right
    if (cellOf[u]) {
      const t = C.transition(s.walls, cellOf[u], a).pos;
      wrong = !cellOf[v] || realIndex.get(C.key(...t)) !== realIndex.get(C.key(...cellOf[v]));
    }
    const [lo, hi] = u < v ? [u, v] : [v, u];
    const id = `${lo}-${hi}`;
    const e = pairs.get(id) || { lo, hi, dirs: 0, wrong: false };
    e.dirs++; e.wrong = e.wrong || wrong;
    pairs.set(id, e);
  }
  const edges = [...pairs.values()].map((e) => ({ ...e, key: `${keys[e.lo]}~${keys[e.hi]}${e.wrong ? "!" : ""}${e.dirs > 1 ? "" : "1"}` }));

  // breadth-first depth from where the robot believes it is, for the growing animation
  const you = s.node ?? (imag ? 0 : map.index.get(C.key(...s.robot)));
  const depth = new Array(n).fill(9);
  if (you !== undefined && you >= 0 && you < n) {
    depth[you] = 0;
    const q = [you];
    while (q.length) {
      const x = q.shift();
      for (let a = 0; a < 4; a++) {
        const y = map.next[x][a];
        if (depth[y] > depth[x] + 1) { depth[y] = depth[x] + 1; q.push(y); }
      }
    }
  }
  return { imag, map, pos, nodes, edges, stubs, you, depth };
}

export function createGraph(svg) {
  svg.innerHTML = "";
  const layer = (cls) => { const g = document.createElementNS(NS, "g"); g.setAttribute("class", cls); svg.appendChild(g); return g; };
  const cellsL = layer("g-cells"), edgesL = layer("g-edges"), futL = layer("g-futs"), planL = layer("g-plans"),
        nodesL = layer("g-nodes"), youL = layer("g-you");
  let cellsHtml = "";
  for (let y = 0; y < C.ROWS; y++) for (let x = 0; x < C.COLS; x++)
    cellsHtml += `<rect class="g-cell" x="${x + 0.06}" y="${y + 0.06}" width="0.88" height="0.88" rx="0.08"/>`;
  cellsL.innerHTML = cellsHtml;
  youL.innerHTML = `<circle class="halo" r="0.3"/><circle r="0.3"/>`;
  let seen = new Set();

  return {
    regrow() { seen = new Set(); },
    draw(g, extra = {}) {
      if (!g) { edgesL.innerHTML = nodesL.innerHTML = futL.innerHTML = planL.innerHTML = ""; youL.style.opacity = 0; return; }
      const now = new Set();
      const fresh = (k) => { now.add(k); return !seen.has(k); };
      const P = g.pos;
      edgesL.innerHTML = g.edges.map((e) => {
        const [a, b] = [P[e.lo], P[e.hi]];
        const cls = `g-edge${e.wrong ? " wrong" : ""}${e.dirs > 1 ? "" : " one-way"}${fresh(e.key) ? " g-new" : ""}`;
        return `<line class="${cls}" pathLength="1" style="--d:${Math.min(g.depth[e.lo], g.depth[e.hi])}" x1="${fmt(a[0])}" y1="${fmt(a[1])}" x2="${fmt(b[0])}" y2="${fmt(b[1])}"/>`;
      }).join("") + g.stubs.map((st) => {
        const p = P[st.u], [dx, dy] = C.ACTIONS[st.a];
        return `<line class="g-stub${fresh(st.key) ? " g-new" : ""}" style="--d:${g.depth[st.u]}" x1="${fmt(p[0] + dx * 0.2)}" y1="${fmt(p[1] + dy * 0.2)}" x2="${fmt(p[0] + dx * 0.42)}" y2="${fmt(p[1] + dy * 0.42)}"/>`;
      }).join("");
      nodesL.innerHTML = g.nodes.map((nd) => {
        const label = nd.goal ? "G" : nd.D >= 0 ? nd.D : "?";
        const r = nd.kind === "real" || nd.goal ? 0.19 : 0.16;
        const cls = `g-node ${nd.kind}${nd.goal ? " goal" : ""}${nd.off ? " off" : ""}${fresh(nd.key) ? " pop" : ""}`;
        return `<g class="${cls}" style="--d:${g.depth[nd.u]}"><circle cx="${fmt(nd.p[0])}" cy="${fmt(nd.p[1])}" r="${r}"/>`
          + `<text x="${fmt(nd.p[0])}" y="${fmt(nd.p[1])}">${label}</text></g>`;
      }).join("");
      seen = now;

      // where it believes it is
      const yp = g.you !== undefined && g.you >= 0 ? P[g.you] : null;
      youL.style.opacity = yp ? 1 : 0;
      if (yp) youL.style.transform = `translate(${yp[0]}px, ${yp[1]}px)`;

      // the plan it chose (up to the step its score comes from) and, on a fresh step, every future it rolled out
      planL.innerHTML = extra.plan && extra.plan.length > 1
        ? `<polyline class="g-plan" points="${extra.plan.map((p) => `${fmt(p[0])},${fmt(p[1])}`).join(" ")}"/>` : "";
      if (extra.futures !== undefined) futL.innerHTML = extra.futures.map(({ a, b, k, w }) =>
        `<line class="g-fut" pathLength="1" style="--k:${k}" stroke-opacity="${w.toFixed(2)}" x1="${fmt(a[0])}" y1="${fmt(a[1])}" x2="${fmt(b[0])}" y2="${fmt(b[1])}"/>`).join("");
    },
  };
}
