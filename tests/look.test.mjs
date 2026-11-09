// What can be checked of the look without a Firefox: that every page shares one set of
// names, keeps the names other work builds on, and loads nothing from outside. How it
// looks is for tools/shoot.py and a person's eyes.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = path => readFileSync(new URL("../" + path, import.meta.url), "utf8");
const PAGES = ["sidebar/sidebar.html", "settings/settings.html", "commandbar/commandbar.html"];
const STYLES = ["sidebar/tokens.css", "sidebar/sidebar.css", "settings/settings.css", "commandbar/commandbar.css"];

test("every page links the design's names before its own styles", () => {
  for (const page of PAGES) {
    const links = [...read(page).matchAll(/<link rel="stylesheet" href="([^"]+)"/g)].map(m => m[1]);
    assert.ok(links[0]?.endsWith("tokens.css"), `${page} starts with ${links[0]}`);
  }
});

test("the names other work builds on are in tokens.css", () => {
  const tokens = read("sidebar/tokens.css");
  for (const name of ["--text", "--muted", "--faint", "--hover", "--selected", "--tile", "--accent", "--radius", "--row", "--frame", "--raised"]) {
    assert.match(tokens, new RegExp(`^\\s*${name}:`, "m"), name);
  }
});

test("nothing is loaded from outside: no web fonts, no addresses, no imports", () => {
  for (const file of [...STYLES, ...PAGES]) {
    // An SVG's own namespace is a name, not something loaded.
    const text = read(file).replaceAll("http://www.w3.org/2000/svg", "");
    assert.doesNotMatch(text, /https?:\/\/|@font-face|@import/, file);
    assert.doesNotMatch(text, /url\((?!["']?data:)/, file);
  }
});

test("what moves stops for those who ask for no motion", () => {
  assert.match(read("sidebar/tokens.css"), /prefers-reduced-motion: reduce[^}]*transition: none !important; animation: none !important;/);
});

test("the surface stays a plain :root name, which the owner's tidier.css overrides per space", () => {
  assert.match(read("sidebar/tokens.css"), /:root \{[^}]*--frame: light-dark\(#ececf0, #1f1f23\);/s);
  assert.match(read("sidebar/sidebar.css"), /html \{ background: var\(--frame\);/);
});

test("the command bar is drawn from the same names: no colours of its own, and drawn icons", () => {
  const css = read("commandbar/commandbar.css");
  // Its colours are the design's (a tint mixed from the space's colour, as the sidebar's). A
  // mask's black is no colour, and an icon's halo is the sidebar's.
  const own = css.replace(/color-mix\([^;]*\)|mask-image:[^;]*;|filter: drop-shadow[^;]*;/g, "").match(/#[0-9a-f]{3,8}\b|rgba?\(/gi) ?? [];
  assert.deepEqual(own, [], "colours of its own");
  for (const name of ["var(--row)", "var(--radius)", "var(--selected)", "var(--shadow-card)", "var(--muted)", "var(--icon)"]) assert.ok(css.includes(name), name);
  // No text characters standing in for icons, which come in other sizes and weights.
  assert.doesNotMatch(read("commandbar/commandbar.js"), /["'][›⌕＋▾→]["']/);
});

test("a class the sidebar puts on the whole page is no element's own class", () => {
  // A space switch once marked html with "new-space", which is also the round button for a
  // new space: until the mark went, the whole sidebar was laid out as that button.
  const files = ["sidebar/sidebar.html", ...[...read("sidebar/sidebar.html").matchAll(/<script src="([^"]+)"/g)].map(m => "sidebar/" + m[1])];
  const code = files.map(read).join("\n");
  const onPage = new Set([...code.matchAll(/(?:root|documentElement)\.classList\.(?:add|toggle|remove)\("([\w-]+)"/g)].map(m => m[1]));
  assert.ok(onPage.has("alone") && onPage.has("space-arriving"), [...onPage].join());
  // Classes given to elements: el("tag", "a b"), class="a b", className = "a b", classList.add("a") on anything else.
  const given = [
    ...[...code.matchAll(/\bel\("\w+", "([\w -]+)"/g)].map(m => m[1]),
    ...[...code.matchAll(/class="([\w -]+)"/g)].map(m => m[1]),
    ...[...code.matchAll(/className = "([\w -]+)"/g)].map(m => m[1]),
    ...[...code.matchAll(/(?<!root|documentElement)\.classList\.(?:add|toggle)\("([\w-]+)"/g)].map(m => m[1]),
  ].flatMap(c => c.split(/\s+/));
  assert.ok(given.includes("new-space"), "the button for a new space is found");
  for (const name of onPage) assert.ok(!given.includes(name), `.${name} is the page's and an element's`);
});
