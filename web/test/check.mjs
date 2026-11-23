// Check the JavaScript port against PyTorch: node web/test/check.mjs [--bench]
// Exact: frames, imagined graph, D(c). Close: latents, P2 first-plan costs.
// --bench also runs the JS planner on 200 maze maps and 100 new maps and compares
// the success rate with the Python evaluation.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { buildWorld, freeCells, key, loadModel, render, runToEnd, trueDistances, GOAL } from "../js/core.js";

const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, "..");
const vec = JSON.parse(readFileSync(join(here, "vectors.json"), "utf8"));
const load = (k) => {
  const meta = JSON.parse(readFileSync(join(web, "models", `${k}.json`), "utf8"));
  const buf = readFileSync(join(web, "models", `${k}.bin`));
  return loadModel(meta, buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
};
const wallSet = (walls) => new Set(walls.map(([x, y]) => key(x, y)));
let failures = 0;
const check = (ok, msg) => { if (!ok) { failures++; console.log("  FAIL", msg); } };

for (const [mk, layouts] of Object.entries(vec.models)) {
  const model = load(mk);
  for (const [name, v] of Object.entries(layouts)) {
    const walls = wallSet(v.walls);
    const cells = freeCells(walls);
    check(JSON.stringify(cells) === JSON.stringify(v.cells), `${mk}/${name}: cell order`);
    cells.forEach((c, i) => {
      const h = createHash("sha1").update(render(walls, c)).digest("hex");
      check(h === v.frame_sha1[i], `${mk}/${name}: frame ${c}`);
    });
    const world = buildWorld(model, walls);
    let maxDz = 0;
    world.codebook.forEach((z, i) => z.forEach((x, j) => { maxDz = Math.max(maxDz, Math.abs(x - v.latents[i][j])); }));
    check(maxDz < 1e-3, `${mk}/${name}: latents differ by ${maxDz}`);
    check(JSON.stringify(world.next) === JSON.stringify(v.next), `${mk}/${name}: imagined graph`);
    check(JSON.stringify(world.known) === JSON.stringify(v.known), `${mk}/${name}: unknown flags`);
    check(world.goal === v.goal_entry, `${mk}/${name}: goal entry`);
    check(JSON.stringify(world.D) === JSON.stringify(v.d), `${mk}/${name}: D(c)`);
    const dt = trueDistances(walls);
    check(JSON.stringify(cells.map((c) => dt.get(key(...c)) ?? -1)) === JSON.stringify(v.d_true), `${mk}/${name}: true BFS`);
    let maxDc = 0;
    for (const p of v.plans) {
      const i = world.index.get(key(...p.start));
      // reuse the planner via a 1-step episode context: visits = {own entry: 1}
      const { planP2, mulberry32 } = await import("../js/core.js");
      const plan = planP2(world, world.codebook[i], new Map([[i, 1]]), mulberry32(0));
      plan.firstActionCosts.forEach((c, a) => {
        const ref = p.first_action_costs[a];
        const bothInf = !Number.isFinite(c) && (ref === null || !Number.isFinite(ref));
        if (!bothInf) maxDc = Math.max(maxDc, Math.abs(c - ref));
      });
      check((plan.note === "fallback") === p.note.startsWith("fallback"), `${mk}/${name}: fallback at ${p.start}`);
    }
    check(maxDc < 1e-3, `${mk}/${name}: P2 costs differ by ${maxDc}`);
    console.log(`${mk.padEnd(4)} ${name.padEnd(10)} latents max |diff| ${maxDz.toExponential(1)}, P2 costs ${maxDc.toExponential(1)}`);
  }
}

if (process.argv.includes("--bench")) {
  const bench = JSON.parse(readFileSync(join(here, "bench_maps.json"), "utf8"));
  for (const mk of Object.keys(vec.models)) {
    const model = load(mk);
    for (const [set, maps] of Object.entries(bench)) {
      let n = 0, ok = 0, opt = 0;
      const t0 = Date.now();
      for (const w of maps) {
        const walls = wallSet(w);
        const world = buildWorld(model, walls);
        const dt = trueDistances(walls);
        for (const c of freeCells(walls)) {
          if (c[0] === GOAL[0] && c[1] === GOAL[1]) continue;
          for (const seed of [0, 1]) {
            const r = runToEnd(world, c, seed);
            n++;
            if (r.outcome === "goal") { ok++; if (r.t === dt.get(key(...c))) opt++; }
          }
        }
      }
      console.log(`bench ${mk} ${set}: success ${(100 * ok / n).toFixed(1)}%, shortest path ${(100 * opt / n).toFixed(1)}% `
        + `(${n} episodes, ${((Date.now() - t0) / 1000).toFixed(0)}s)`);
    }
  }
}

console.log(failures ? `\n${failures} check(s) failed` : "\nall checks passed");
process.exit(failures ? 1 : 0);
