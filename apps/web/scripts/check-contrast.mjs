// Holds the theme's colour roles to WCAG AA: every text role at least 4.5:1 on every ground, in both themes, and the
// red primary action's white label at least 4.5:1. Reads the variables from app/globals.css, so the check is of
// what ships. No dependencies: `node scripts/check-contrast.mjs` (exits 1 on a failure).
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

function block(selector) {
  const i = css.indexOf(selector + " {");
  if (i < 0) throw new Error(`no ${selector} block in globals.css`);
  const body = css.slice(i, css.indexOf("}", i));
  const vars = {};
  for (const m of body.matchAll(/--c-([a-z]+):\s*(\d+)\s+(\d+)\s+(\d+)/g)) vars[m[1]] = [+m[2], +m[3], +m[4]];
  return vars;
}

const lum = ([r, g, b]) => {
  const c = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b);
};
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

const TEXT = ["fg", "muted", "subtle", "ok", "warn", "danger"];
const GROUNDS = ["bg", "surface", "raised"];
let failures = 0;
for (const [name, sel] of [["dark", ":root"], ["light", '[data-theme="light"]']]) {
  const v = block(sel);
  for (const t of TEXT) for (const g of GROUNDS) {
    const r = ratio(v[t], v[g]);
    if (r < 4.5) { failures++; console.log(`FAIL ${name}: ${t} on ${g} = ${r.toFixed(2)}:1`); }
  }
  const onRed = ratio([255, 255, 255], v.brand);
  if (onRed < 4.5) { failures++; console.log(`FAIL ${name}: white on brand = ${onRed.toFixed(2)}:1`); }
  console.log(`${name}: ${TEXT.length * GROUNDS.length + 1} pairs checked`);
}
if (failures) { console.log(`${failures} pair(s) under 4.5:1`); process.exit(1); }
console.log("every text role is at least 4.5:1 on every ground, in both themes");
