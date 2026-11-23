// Mini-JEPA in the browser: renderer, networks, imagined graph, BFS and the P2 planner.
// A line-by-line port of environment/renderer.py, models/{encoder,predictor}.py,
// planning/{imagination,latent_graph,planner,mpc}.py. No DOM here, so Node can test it
// against PyTorch (web/test/check.mjs).

export const COLS = 6, ROWS = 5, CELL_PX = 8, H = ROWS * CELL_PX, W = COLS * CELL_PX;
export const GOAL = [5, 0];
export const ACTIONS = [[0, -1], [0, 1], [-1, 0], [1, 0]];          // UP, DOWN, LEFT, RIGHT
export const ACTION_NAMES = ["up", "down", "left", "right"];
export const COLORS = {
  line: [200, 208, 216], floor: [227, 233, 239], wall: [127, 138, 150], goal: [13, 122, 112], robot: [42, 94, 168],
};

export const key = (x, y) => `${x},${y}`;
export const inBounds = (x, y) => x >= 0 && x < COLS && y >= 0 && y < ROWS;

// --- the world (only used to execute actions and to score) ----------------------------
export function freeCells(walls) {
  const out = [];
  for (let y = 0; y < ROWS; y++) for (let x = 0; x < COLS; x++) if (!walls.has(key(x, y))) out.push([x, y]);
  return out;
}

export function transition(walls, [x, y], a) {
  const nx = x + ACTIONS[a][0], ny = y + ACTIONS[a][1];
  if (!inBounds(nx, ny) || walls.has(key(nx, ny))) return { pos: [x, y], collision: true, wall: inBounds(nx, ny) };
  return { pos: [nx, ny], collision: false, wall: false };
}

/** True shortest-path length to the goal per cell (BFS), -1 if unreachable. Keyed "x,y". */
export function trueDistances(walls) {
  const d = new Map([[key(...GOAL), 0]]);
  const queue = [GOAL];
  while (queue.length) {
    const [x, y] = queue.shift();
    for (const [dx, dy] of ACTIONS) {
      const nx = x + dx, ny = y + dy, k = key(nx, ny);
      if (inBounds(nx, ny) && !walls.has(k) && !d.has(k)) { d.set(k, d.get(key(x, y)) + 1); queue.push([nx, ny]); }
    }
  }
  return d;
}

// --- renderer: exactly environment/renderer.py ------------------------------------------
/** Frame with the robot at pos: Uint8Array, CHW 3 x 40 x 48. */
export function render(walls, pos) {
  const img = new Uint8Array(3 * H * W);
  const put = (px, py, c) => { for (let ch = 0; ch < 3; ch++) img[ch * H * W + py * W + px] = c[ch]; };
  for (let py = 0; py < H; py++) for (let px = 0; px < W; px++) put(px, py, COLORS.line);
  for (let y = 0; y < ROWS; y++) for (let x = 0; x < COLS; x++) {
    const isRobot = pos && x === pos[0] && y === pos[1];
    const c = isRobot ? COLORS.robot : walls.has(key(x, y)) ? COLORS.wall
      : (x === GOAL[0] && y === GOAL[1]) ? COLORS.goal : COLORS.floor;
    for (let py = y * CELL_PX + 1; py < (y + 1) * CELL_PX; py++)
      for (let px = x * CELL_PX + 1; px < (x + 1) * CELL_PX; px++) put(px, py, c);
  }
  return img;
}

// --- networks ------------------------------------------------------------------------------
function conv2dS2(input, cin, h, w, weight, bias, cout) {
  // Conv2d(k=3, stride=2, padding=1) + ReLU; weight [cout, cin, 3, 3]
  const oh = (h + 1) >> 1, ow = (w + 1) >> 1, out = new Float32Array(cout * oh * ow);
  for (let o = 0; o < cout; o++) for (let i = 0; i < oh; i++) for (let j = 0; j < ow; j++) {
    let s = bias[o];
    for (let c = 0; c < cin; c++) for (let ky = 0; ky < 3; ky++) {
      const yy = 2 * i + ky - 1;
      if (yy < 0 || yy >= h) continue;
      for (let kx = 0; kx < 3; kx++) {
        const xx = 2 * j + kx - 1;
        if (xx < 0 || xx >= w) continue;
        s += weight[((o * cin + c) * 3 + ky) * 3 + kx] * input[(c * h + yy) * w + xx];
      }
    }
    out[(o * oh + i) * ow + j] = s > 0 ? s : 0;
  }
  return { out, h: oh, w: ow };
}

function linear(x, weight, bias, nout, relu) {
  const nin = x.length, out = new Float32Array(nout);
  for (let o = 0; o < nout; o++) {
    let s = bias[o];
    const row = o * nin;
    for (let i = 0; i < nin; i++) s += weight[row + i] * x[i];
    out[o] = relu && s < 0 ? 0 : s;
  }
  return out;
}

/** meta = models/<key>.json, buffer = models/<key>.bin (ArrayBuffer). */
export function loadModel(meta, buffer) {
  const all = new Float32Array(buffer);
  const t = {};
  for (const s of meta.tensors) t[s.name] = all.subarray(s.offset, s.offset + s.size);
  const D = meta.latent_dim, hidden = meta.hidden, A = meta.n_actions;
  const encode = (frame) => {
    let x = new Float32Array(frame.length);
    for (let i = 0; i < frame.length; i++) x[i] = frame[i] / 255;
    let r = conv2dS2(x, 3, H, W, t["encoder.conv.0.weight"], t["encoder.conv.0.bias"], 16);
    r = conv2dS2(r.out, 16, r.h, r.w, t["encoder.conv.2.weight"], t["encoder.conv.2.bias"], 32);
    r = conv2dS2(r.out, 32, r.h, r.w, t["encoder.conv.4.weight"], t["encoder.conv.4.bias"], 64);
    const z = linear(r.out, t["encoder.fc.weight"], t["encoder.fc.bias"], D, false);
    const mean = t["encoder.z_mean"], std = t["encoder.z_std"];
    for (let i = 0; i < D; i++) z[i] = (z[i] - mean[i]) / std[i];
    return z;
  };
  const layers = [];
  for (let i = 0, n = hidden.length + 1; i < n; i++)
    layers.push([t[`predictor.f.${2 * i}.weight`], t[`predictor.f.${2 * i}.bias`], i < hidden.length ? hidden[i] : D]);
  const step = (z, a) => {                       // z + f([z, onehot(a)])
    let x = new Float32Array(D + A);
    x.set(z);
    x[D + a] = 1;
    layers.forEach(([w, b, n], i) => { x = linear(x, w, b, n, i < layers.length - 1); });
    const out = new Float32Array(D);
    for (let i = 0; i < D; i++) out[i] = z[i] + x[i];
    return out;
  };
  const threshold = meta.unknown_threshold ?? meta.unknown_factor * meta.median_one_step_error;
  return { meta, encode, step, threshold };
}

// --- imagination: per-map codebook, snapping, imagined graph, D(c) ------------------------
function snap(z, codebook) {
  let best = Infinity, idx = -1;
  for (let i = 0; i < codebook.length; i++) {
    const c = codebook[i];
    let s = 0;
    for (let j = 0; j < z.length; j++) { const d = z[j] - c[j]; s += d * d; }
    if (s < best) { best = s; idx = i; }
  }
  return { index: idx, distance: Math.sqrt(best) };
}

/** Everything the model "knows" about one layout: codebook (one frame per free cell), graph, D(c). */
export function buildWorld(model, walls) {
  const cells = freeCells(walls);
  const index = new Map(cells.map((c, i) => [key(...c), i]));
  const codebook = cells.map((c) => model.encode(render(walls, c)));
  const thr = model.threshold;
  const n = cells.length, A = ACTIONS.length;
  const next = [], predicted = [], known = [], distance = [];
  for (let i = 0; i < n; i++) {
    const row = { next: [], predicted: [], known: [], distance: [] };
    for (let a = 0; a < A; a++) {
      const s = snap(model.step(codebook[i], a), codebook);
      const ok = s.distance <= thr;
      row.predicted.push(s.index); row.known.push(ok); row.distance.push(s.distance); row.next.push(ok ? s.index : i);
    }
    next.push(row.next); predicted.push(row.predicted); known.push(row.known); distance.push(row.distance);
  }
  const goalFrame = render(walls, GOAL);
  const zGoal = model.encode(goalFrame);
  const goal = snap(zGoal, codebook).index;
  // BFS backwards from the goal entry over imagined edges (self-loops ignored)
  const preds = Array.from({ length: n }, () => new Set());
  for (let u = 0; u < n; u++) for (const v of next[u]) if (v !== u) preds[v].add(u);
  const D = new Array(n).fill(-1);
  D[goal] = 0;
  const queue = [goal];
  while (queue.length) {
    const v = queue.shift();
    for (const u of [...preds[v]].sort((p, q) => p - q)) if (D[u] === -1) { D[u] = D[v] + 1; queue.push(u); }
  }
  return { model, walls, cells, index, codebook, next, predicted, known, distance, goal, zGoal, D, threshold: thr };
}

/** Compare the imagined graph and D(c) with the true dynamics (for display only). */
export function graphReport(world) {
  const dt = trueDistances(world.walls);
  let edges = 0, correct = 0, unknown = 0, wrongTrusted = 0, dExact = 0;
  world.cells.forEach((c, i) => {
    for (let a = 0; a < ACTIONS.length; a++) {
      const t = world.index.get(key(...transition(world.walls, c, a).pos));
      edges++;
      if (world.next[i][a] === t) correct++;
      if (!world.known[i][a]) unknown++;
      else if (world.next[i][a] !== t) wrongTrusted++;
    }
    if ((dt.get(key(...c)) ?? -1) === world.D[i]) dExact++;
  });
  return { edges, correct, unknown, wrongTrusted, dExact, cells: world.cells.length, dTrue: dt };
}

// --- P2 planner and the MPC loop -----------------------------------------------------------
export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** P2: all 4^H action sequences; cost = min_k [k + D(snap(z_k))] + revisit penalty; ties broken by rng.
 *  With planning.snap_each_step every imagined step continues from the codebook entry the previous
 *  prediction snapped to, so the look-ahead is a walk on the imagined graph and cannot drift. */
export function planP2(world, z, visits, rng) {
  const { model, codebook, D, threshold } = world;
  const { horizon, revisit_penalty: penalty, snap_each_step: snapEach = false } = model.meta.planning;
  const A = ACTIONS.length, S = A ** horizon;
  // imagine every sequence, sharing prefixes (identical to rolling each one out)
  let level = [{ state: z, seq: [] }];
  const traj = [];
  for (let k = 0; k < horizon; k++) {
    const nxt = [];
    for (const node of level) for (let a = 0; a < A; a++) {
      const pred = model.step(node.state, a);
      const sn = snap(pred, codebook);
      nxt.push({ pred, sn, state: snapEach ? codebook[sn.index] : pred, seq: [...node.seq, a], parent: node });
    }
    level = nxt;
  }
  for (const leaf of level) {               // lexicographic order, like itertools.product
    const states = [], snaps = [];
    for (let n = leaf; n.parent; n = n.parent) { states.unshift(n.pred); snaps.unshift(n.sn); }
    traj.push({ seq: leaf.seq, states, snaps });
  }
  const cost = new Array(S), entries = new Array(S);
  let anyFinite = false;
  traj.forEach((t, s) => {
    let best = Infinity, trusted = true;
    entries[s] = [];
    t.snaps.forEach((sn, k) => {
      trusted = trusted && sn.distance <= threshold;
      entries[s].push(trusted ? sn.index : -1);
      if (trusted && D[sn.index] >= 0) best = Math.min(best, k + 1 + D[sn.index]);
    });
    const first = t.snaps[0];
    const rev = first.distance <= threshold ? penalty * (visits.get(first.index) || 0) : 0;
    cost[s] = best + rev;
    t.revisit = rev;
    if (Number.isFinite(cost[s])) anyFinite = true;
  });
  let note = "";
  if (!anyFinite) {                          // nothing known reaches the goal: final latent distance
    traj.forEach((t, s) => {
      const zl = t.states[t.states.length - 1];
      let d = 0;
      for (let j = 0; j < zl.length; j++) d += (zl[j] - world.zGoal[j]) ** 2;
      cost[s] = d + t.revisit;
    });
    note = "fallback";
  }
  const min = Math.min(...cost);
  const ties = cost.map((c, i) => (c === min ? i : -1)).filter((i) => i >= 0);
  const i = ties.length === 1 ? ties[0] : ties[Math.floor(rng() * ties.length)];
  const firstActionCosts = Array.from({ length: A }, (_, a) => Math.min(...cost.filter((_, s) => traj[s].seq[0] === a)));
  const futures = traj.map((t, s) => ({ seq: t.seq, entries: entries[s], cost: cost[s] }));   // every imagined sequence
  return { action: traj[i].seq[0], sequence: traj[i].seq, cost: cost[i], entries: entries[i], firstActionCosts, note,
           futures, chosen: i };
}

/** The MPC loop as a generator: yields after every executed action. */
export function* runEpisode(world, start, seed = 0) {
  const { max_actions: maxActions, max_visits: maxVisits } = world.model.meta.planning;
  const rng = mulberry32(seed);
  const walls = world.walls;
  let pos = start;
  const cellVisits = new Map([[key(...pos), 1]]);
  const entryVisits = new Map();
  const noteVisit = (p) => { const e = world.index.get(key(...p)); entryVisits.set(e, (entryVisits.get(e) || 0) + 1); };
  noteVisit(pos);                           // the current frame snaps exactly to its own codebook entry
  const path = [pos];
  let collisions = 0;
  for (let t = 0; t < maxActions; t++) {
    const z = world.codebook[world.index.get(key(...pos))];   // = encode(current observation)
    const plan = planP2(world, z, entryVisits, rng);
    const r = transition(walls, pos, plan.action);
    pos = r.pos;
    path.push(pos);
    collisions += r.collision ? 1 : 0;
    const k = key(...pos);
    cellVisits.set(k, (cellVisits.get(k) || 0) + 1);
    noteVisit(pos);
    const atGoal = pos[0] === GOAL[0] && pos[1] === GOAL[1];
    const loop = !atGoal && cellVisits.get(k) >= maxVisits;
    const done = atGoal || loop || t === maxActions - 1;
    yield { t: t + 1, pos, plan, collision: r.collision, collisions, path: [...path], done,
            outcome: atGoal ? "goal" : loop ? "loop" : done ? "timeout" : null };
    if (done) return;
  }
}

export function runToEnd(world, start, seed = 0) {
  let last = null;
  for (const s of runEpisode(world, start, seed)) last = s;
  return last;
}
