// JS imagination (A) / exploration (B) on the benchmark maps, to compare with the Python numbers:
//   node web/test/explore_bench.mjs [maze_maps|new_maps] [number of maps]
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { freeCells, key, loadModel, runImaginedToEnd, trueDistances, GOAL } from "../js/core.js";

const here = dirname(fileURLToPath(import.meta.url));
const meta = JSON.parse(readFileSync(join(here, "..", "models", "jepa.json"), "utf8"));
const buf = readFileSync(join(here, "..", "models", "jepa.bin"));
const model = loadModel(meta, buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
const set = process.argv[2] || "maze_maps", n = +(process.argv[3] || 50);
const maps = JSON.parse(readFileSync(join(here, "bench_maps.json"), "utf8"))[set].slice(0, n);
for (const mode of ["imagine", "explore"]) {
  let eps = 0, ok = 0, opt = 0;
  const t0 = Date.now();
  for (const w of maps) {
    const walls = new Set(w.map(([x, y]) => key(x, y)));
    const dt = trueDistances(walls);
    for (const c of freeCells(walls)) {
      if (c[0] === GOAL[0] && c[1] === GOAL[1]) continue;
      for (const seed of [0, 1]) {
        const r = runImaginedToEnd(model, walls, c, seed, mode);
        eps++;
        if (r.outcome === "goal") { ok++; if (r.t === dt.get(key(...c))) opt++; }
      }
    }
  }
  console.log(`${set} (${maps.length} maps) ${mode}: success ${(100 * ok / eps).toFixed(1)}%, `
    + `shortest ${(100 * opt / eps).toFixed(1)}% (${eps} episodes, ${((Date.now() - t0) / 1000).toFixed(0)}s)`);
}
