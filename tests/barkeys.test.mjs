// barkeys.js, the keys typed right after the command bar's key, before its window has the
// keyboard: on a stand-in for a page, with no Firefox. Whether Firefox really sends them so is
// for the smoke test (alone_command_bar).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const SOURCE = readFileSync(new URL("../barkeys.js", import.meta.url), "utf8");

// A page: its listeners, the messages it sends, and what lands in its field.
function page({ keys = ["Ctrl+Shift+K"], focused = true } = {}) {
  const listeners = new Map(), onMessage = [], sent = [], timers = [];
  let field = "";
  const ctx = {
    globalThis: null, tidierBarKeys: keys, navigator: { platform: "MacIntel" },
    document: { hasFocus: () => focused, execCommand: (cmd, ui, text) => { if (cmd === "insertText") field += text; return true; } },
    addEventListener: (type, f) => { (listeners.get(type) ?? listeners.set(type, []).get(type)).push(f); },
    removeEventListener: (type, f) => { const all = listeners.get(type) ?? []; if (all.includes(f)) all.splice(all.indexOf(f), 1); },
    setTimeout: (f, ms) => { timers.push({ f, ms }); return timers.length; }, clearTimeout: id => { if (timers[id - 1]) timers[id - 1].f = () => {}; },
    browser: { runtime: { onMessage: { addListener: f => onMessage.push(f) }, sendMessage: async m => { sent.push(m); } } },
  };
  ctx.globalThis = ctx;
  vm.runInNewContext(SOURCE, ctx);
  // A key as Firefox gives it to the page; what the page itself would do with it, unless stopped.
  const key = (k, mods = {}) => {
    const e = { type: "keydown", isTrusted: true, key: k, code: /^[a-z]$/i.test(k) ? `Key${k.toUpperCase()}` : k, metaKey: false, ctrlKey: false, altKey: false, shiftKey: false, repeat: false, ...mods,
      stopped: false, prevented: false, preventDefault() { this.prevented = true; }, stopImmediatePropagation() { this.stopped = true; } };
    for (const f of [...(listeners.get("keydown") ?? [])]) { if (e.stopped) break; f(e); }
    if (!e.prevented && [...k].length === 1 && !e.metaKey) field += k;
    return e;
  };
  const tell = msg => { for (const f of onMessage) f(msg); };
  const later = () => { for (const t of timers.splice(0)) t.f(); };
  return { key, tell, later, sent, plainSent: () => JSON.parse(JSON.stringify(sent)), field: () => field };
}

test("on the bar's key the page starts to catch, and the bar gets the letters and the Enter", () => {
  const p = page();
  const press = p.key("K", { metaKey: true, shiftKey: true });
  assert.ok(!press.prevented, "the key itself is Firefox's, to open the bar");
  for (const k of "ferry") p.key(k);
  p.key("Enter");
  assert.equal(p.field(), "", "nothing went into the page");
  assert.deepEqual(p.sent, [], "which press this was is not known yet");
  p.tell({ type: "bar:catch", pressedAt: 7 });
  assert.deepEqual(p.plainSent(), [{ type: "bar:early", pressedAt: 7, text: "ferry", enter: { inNewTab: false }, escape: false }]);
  p.key("x");
  assert.equal(p.field(), "x", "after Enter, the page has its keys again");
});

test("started by the background, it stops when the bar has the keyboard", () => {
  const p = page();
  p.tell({ type: "bar:catch", pressedAt: 3 });
  p.key("w");
  p.key("e");
  p.key("Backspace");
  p.key("a");
  p.tell({ type: "bar:stop", pressedAt: 3 });
  assert.deepEqual(p.sent.map(m => m.text), ["wa"]);
  p.key("z");
  assert.equal(p.field(), "z");
});

test("keys with ⌘, a page's own keys, and a page that does not have the keyboard are left alone", () => {
  const p = page();
  p.tell({ type: "bar:catch", pressedAt: 1 });
  assert.ok(!p.key("c", { metaKey: true }).prevented, "⌘C stays the page's");
  assert.ok(!p.key("ArrowDown").prevented);
  const fake = p.key("q", { isTrusted: false });
  assert.ok(!fake.prevented, "a page cannot type into the bar");
  p.tell({ type: "bar:stop", pressedAt: 1 });
  assert.deepEqual(p.sent, []);
  const away = page({ focused: false });
  away.tell({ type: "bar:catch", pressedAt: 1 });
  away.key("a");
  assert.equal(away.field(), "a");
});

test("if the bar never comes, what was typed goes into the page after all", () => {
  const p = page();
  p.key("K", { metaKey: true, shiftKey: true });
  p.key("h");
  p.key("i");
  p.later();
  assert.equal(p.field(), "hi");
  assert.deepEqual(p.sent, []);
});

test("Esc is the bar's too, and another press's stop changes nothing", () => {
  const p = page();
  p.tell({ type: "bar:catch", pressedAt: 5 });
  p.key("a");
  p.tell({ type: "bar:stop", pressedAt: 4 });
  p.key("Escape");
  assert.deepEqual(p.plainSent(), [{ type: "bar:early", pressedAt: 5, text: "a", enter: null, escape: true }]);
});

test("only the bar's own keys start it, as Firefox writes them", () => {
  const p = page({ keys: ["Ctrl+T", "MacCtrl+Shift+Space"] });
  p.key("K", { metaKey: true, shiftKey: true });
  p.key("a");
  assert.equal(p.field(), "a", "⌘⇧K is no key of the bar's here");
  p.key("T", { metaKey: true });
  p.key("b");
  assert.equal(p.field(), "a");
  p.tell({ type: "bar:stop", pressedAt: 1 }); // not known yet: nothing
  p.tell({ type: "bar:catch", pressedAt: 9 });
  p.tell({ type: "bar:stop", pressedAt: 9 });
  assert.deepEqual(p.sent.map(m => m.text), ["b"]);
});
