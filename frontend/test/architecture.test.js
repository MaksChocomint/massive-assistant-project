import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../src/", import.meta.url));
const layers = ["shared", "features", "widgets", "pages", "app"];
function files(path) {
  return readdirSync(path, { withFileTypes: true }).flatMap((entry) => {
    const full = resolve(path, entry.name);
    return entry.isDirectory() ? files(full) : [full];
  });
}
test("FSD: зависимости идут вниз, независимые features не импортируют друг друга", () => {
  const errors = [];
  for (const file of files(root).filter((file) => /\.(jsx?|css)$/.test(file))) {
    const from = relative(root, file).split(/[\\/]/);
    if (!layers.includes(from[0])) continue;
    const source = readFileSync(file, "utf8");
    for (const match of source.matchAll(/(?:from\s+|import\s*)["'](\.[^"']+)["']/g)) {
      const to = relative(root, resolve(dirname(file), match[1])).split(/[\\/]/);
      if (!layers.includes(to[0])) continue;
      if (layers.indexOf(to[0]) > layers.indexOf(from[0]))
        errors.push(from.join("/") + " -> " + to.join("/"));
      if (
        ["features", "widgets", "pages"].includes(from[0]) &&
        from[0] === to[0] &&
        from[1] !== to[1]
      ) {
        errors.push("cross-slice: " + from.join("/") + " -> " + to.join("/"));
      }
    }
  }
  assert.deepEqual(errors, []);
});
