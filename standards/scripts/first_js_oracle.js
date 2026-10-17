// Score CVSS v4.0 vectors (one per stdin line) with FIRST's unmodified calculator code.
// Usage: node first_js_oracle.js <dir with cvss_lookup.js, max_composed.js, max_severity.js,
//        metrics.js, cvss_score.js>
// Build-time only (scripts/build_subsets.py); tests never execute JavaScript.
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const dir = process.argv[2];
const ctx = { Math, Object, parseInt, isNaN };
vm.createContext(ctx);
for (const f of ["cvss_lookup.js", "max_composed.js", "max_severity.js", "metrics.js", "cvss_score.js"]) {
  vm.runInContext(fs.readFileSync(path.join(dir, f), "utf8"), ctx);
}
const out = [];
for (const vector of fs.readFileSync(0, "utf8").trim().split("\n")) {
  const sel = {};
  for (const k of Object.keys(ctx.expectedMetricOrder)) sel[k] = "X";
  for (const part of vector.split("/").slice(1)) {
    const [k, v] = part.split(":");
    sel[k] = v;
  }
  ctx.sel = sel;
  const score = vm.runInContext("cvss_score(sel, cvssLookup_global, maxSeverity, macroVector(sel))", ctx);
  out.push(`${vector} ${score}`);
}
process.stdout.write(out.join("\n") + "\n");
