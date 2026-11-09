// What can be checked of the look without a Firefox: that every page shares one set of
// names, keeps the names other work builds on, and loads nothing from outside. How it
// looks is for tools/shoot.py and a person's eyes.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const read = path => readFileSync(new URL("../" + path, import.meta.url), "utf8");
const PAGES = ["sidebar/sidebar.html", "settings/settings.html", "commandbar/commandbar.html"];
const STYLES = ["sidebar/tokens.css", "sidebar/sidebar.css", "sidebar/archived.css", "sidebar/agent.css", "settings/settings.css", "settings/bridge.css", "commandbar/commandbar.css"];
// What the sidebar and the command bar draw: on the design's names throughout.
const OWN = ["sidebar/sidebar.css", "sidebar/archived.css", "sidebar/agent.css", "commandbar/commandbar.css"];

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

// --- A stylesheet read as Firefox reads it ----------------------------------------------
// Comments and strings out (a data: icon is full of quotes and slashes), then the blocks.
function blocks(css) {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g, '""');
  const rules = [], open = [];
  let from = 0;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === "{") {
      const prelude = text.slice(from, i).trim();
      const rule = { prelude, at: prelude.startsWith("@"), parent: open.at(-1) ?? null, body: "" };
      if (rule.parent) rule.parent.body += " ";
      rules.push(rule);
      open.push(rule);
      from = i + 1;
    } else if (c === "}" || c === ";") {
      const declaration = text.slice(from, i);
      if (open.length) open.at(-1).body += declaration + (c === ";" ? ";" : "");
      if (c === "}") {
        if (!open.length) throw new Error(`a } with no block, after "${text.slice(Math.max(0, i - 60), i).trim()}"`);
        open.pop();
      }
      from = i + 1;
    }
  }
  if (open.length) throw new Error(`"${open.at(-1).prelude}" is never closed`);
  return rules;
}
const declarations = (rule, property) => [...rule.body.matchAll(new RegExp(`(?:^|;)\\s*${property}\\s*:\\s*([^;]+)`, "g"))].map(m => m[1].trim());

test("no rule is nested in another by accident: a block left open swallows the rules after it", () => {
  // CSS nesting makes a rule after an unclosed one apply only inside it, which matches
  // nothing: the renaming box for a space was a plain browser field so. A rule inside a
  // rule is never meant here; an at-rule inside one (@starting-style) is.
  for (const file of STYLES) {
    const nested = blocks(read(file)).filter(r => !r.at && r.parent && !r.parent.at);
    assert.deepEqual(nested.map(r => `${r.parent.prelude} > ${r.prelude}`), [], file);
  }
  assert.throws(() => blocks(".a { color: red;\n.b { color: blue; }"), /never closed/);
  assert.throws(() => blocks(".a { color: red; }\n.b { color: blue; } }"), /no block/);
});

test("corners, type and motion come from the design's names", () => {
  // (999px: round ends on a line, whatever its length.)
  const radius = /^(0|50%|999px|var\(--radius(-sm|-lg)?\)|calc\(var\(--radius(-sm|-lg)?\) [+-] [\d.]+px\))$/;
  const size = /^(0|inherit|var\(--size(-small|-title)?\)|calc\(var\(--[\w-]+\) \* [\d.]+\))$/;
  for (const file of OWN) {
    for (const rule of blocks(read(file))) {
      const where = `${file}: ${rule.prelude}`;
      for (const v of declarations(rule, "border-radius")) assert.match(v, radius, where);
      for (const v of declarations(rule, "font-size")) assert.match(v, size, where);
      for (const v of declarations(rule, "font")) assert.doesNotMatch(v, /\d+(\.\d+)?px/, where);
      // A time is a name (--quick, --soft, --spring, --tint-change); only "at once" is written out.
      for (const v of declarations(rule, "transition")) {
        const times = v.replace(/var\(--[\w-]+\)/g, "").match(/\b\d*\.?\d+m?s\b/g) ?? [];
        assert.ok(times.every(t => t === "0s"), `${where}: ${v}`);
      }
    }
  }
});

test("what is a line is a row's height: the menu's items, the quiet line and the agent's line", () => {
  const all = OWN.flatMap(file => blocks(read(file)));
  for (const selector of ["#menu .item", "#note .line", "#agent-line"]) {
    const heights = all.filter(r => r.prelude === selector).flatMap(r => declarations(r, "height"));
    assert.deepEqual(heights, ["var(--row)"], selector);
  }
  // And none of them is darker than the surface: the quiet line is raised (note.js), the agent's lies on it.
  assert.match(read("sidebar/note.js"), /el\("div", "line raised"\)/);
  const agent = all.find(r => r.prelude === "#agent-line");
  assert.deepEqual(declarations(agent, "background"), ["var(--tile)"]);
});

test("Clear has room from the rows on both sides of its line, also from a selected card", () => {
  const sidebar = blocks(read("sidebar/sidebar.css")), tokens = read("sidebar/tokens.css");
  const px = s => Number(s.match(/([\d.]+)px/)[1]);
  const gap = px(tokens.match(/--row-gap: ([\d.]+px)/)[1]);
  const [top, , bottom] = declarations(sidebar.find(r => r.prelude === ".divider" && /margin/.test(r.body)), "margin")[0].split(/\s+/).map(v => (v.endsWith("px") ? px(v) : null));
  const clear = px(declarations(sidebar.find(r => r.prelude === ".clear"), "height")[0]);
  // The line is 1 px; Clear is in its middle.
  const above = gap + top + 0.5 - clear / 2, below = bottom + 0.5 - clear / 2;
  assert.ok(above >= 4 && below >= 4, `${above} px above, ${below} px below`);
});

// --- The letter of a page with no icon ----------------------------------------------------
function sidebarPage() {
  const element = () => ({ dataset: {}, style: { setProperty() {} }, classList: { toggle() {}, add() {}, remove() {}, contains: () => false }, append() {}, replaceWith() {}, replaceChildren() {} });
  const ctx = vm.createContext({
    browser: { runtime: { connect: () => ({ onMessage: { addListener() {} }, postMessage() {} }) }, windows: { getCurrent: async () => ({ id: 1 }) }, storage: { managed: { get: async () => ({}) } } },
    document: { createElement: element, getElementById: element, documentElement: element(), head: element(), addEventListener() {} },
    addEventListener() {},
  });
  vm.runInContext(read("sidebar/sidebar.js"), ctx);
  return code => vm.runInContext(code, ctx);
}

test("a page with no icon gets its first letter (a digit if it has none), in the sidebar and in the command bar", () => {
  const bar = vm.createContext({ URL });
  vm.runInContext(read("commandbar/rank.js"), bar);
  const sidebar = sidebarPage();
  const cases = [["(2) Inbox one", "I"], ["  Ærlig talt", "Æ"], ["#42: a ticket", "a"], ["2048", "2"], ["— Notes", "N"], ["!!!", ""], ["", ""], [undefined, ""]];
  for (const letterOf of [sidebar("letterOf"), bar.letterOf]) {
    for (const [title, letter] of cases) assert.equal(letterOf(title), letter, String(title));
  }
  assert.equal(sidebar("icon")({ title: "(2) Inbox one" }).textContent, "I", "and the row draws it");
  assert.equal(sidebar("icon")({ title: "New Tab", blank: true }).textContent, "", "an empty new tab has no name to take a letter from");
});
