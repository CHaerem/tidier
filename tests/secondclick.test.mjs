// A second click where the first one acted does nothing (sidebar/secondclick.js): the rule,
// on a page of its own with nothing but its listeners. The real clicks are in the smoke test
// (alone_hand: a double click on ×, the menu, the quiet line).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

function page() {
  const listeners = {};
  let now = 1000;
  const ctx = {
    performance: { now: () => now },
    addEventListener: (type, f, capture) => { assert.equal(capture, true, "before anything else on the page"); listeners[type] = f; },
  };
  vm.runInNewContext(readFileSync(new URL("../sidebar/secondclick.js", import.meta.url), "utf8") + ";this.secondClick = secondClick;", ctx);
  // What reaches the page's own handlers: true, or false when it was swallowed.
  const fire = (type, { detail = 1, x = 10, y = 10, trusted = true } = {}) => {
    const e = { type, detail, clientX: x, clientY: y, isTrusted: trusted, stopped: false, stopImmediatePropagation() { e.stopped = true; }, preventDefault() {} };
    listeners[type](e);
    return !e.stopped ? e : null;
  };
  return {
    later: ms => { now += ms; },
    // A click on a control that acts, as its handler would see it.
    act: (props = {}) => { const e = fire("click", props); if (e) ctx.secondClick.acted(e); return !!e; },
    reaches: (type, props) => !!fire(type, props),
  };
}

test("the second click of a double click on something that acts reaches nothing, nor does its dblclick", () => {
  const p = page();
  assert.ok(p.act({ detail: 1 }));
  p.later(120);
  assert.equal(p.reaches("click", { detail: 2 }), false, "what came under the pointer does not get it");
  assert.equal(p.reaches("dblclick", { detail: 2 }), false, "nor a folder's rename, nor a new tab on the empty list");
  p.later(120);
  assert.equal(p.reaches("click", { detail: 3 }), false, "a third click goes the same way");
});

test("so does a quick second click of the real mouse on the same spot, but not one that took aim again", () => {
  const p = page();
  p.act();
  p.later(250);
  assert.equal(p.reaches("click", { detail: 1, x: 12, y: 9 }), false, "the system counted no double click, and it is still the same click");
  const q = page();
  q.act();
  q.later(450);
  assert.ok(q.reaches("click", { detail: 1 }), "later, on the same spot, it is a click of its own");
  const r = page();
  r.act();
  r.later(150);
  assert.ok(r.reaches("click", { detail: 1, x: 60 }), "somewhere else");
});

test("a double click you mean, after a click of your own, is yours", () => {
  const p = page();
  p.act();
  p.later(800);
  assert.ok(p.reaches("click", { detail: 1, x: 80, y: 200 }), "a click elsewhere ends it");
  p.later(100);
  assert.ok(p.reaches("click", { detail: 2, x: 80, y: 200 }));
  assert.ok(p.reaches("dblclick", { detail: 2, x: 80, y: 200 }), "a folder renamed by a double click");
});

test("a click that only selects acts on nothing: the next is not held back", () => {
  const p = page();
  assert.ok(p.reaches("click", { detail: 1 }));
  p.later(100);
  assert.ok(p.reaches("click", { detail: 2 }));
});

test("the keys' clicks and a script's are never held back, and a script's has no place", () => {
  const p = page();
  p.act({ detail: 0 });
  assert.ok(p.reaches("click", { detail: 0 }), "Enter, and Enter again");
  p.act({ detail: 1, trusted: false });
  p.later(100);
  assert.ok(p.reaches("click", { detail: 1, trusted: false }), "two × closed by a script, one after the other");
  const q = page();
  q.act({ detail: 1, trusted: false });
  assert.equal(q.reaches("click", { detail: 2, trusted: false }), false, "a script's double click is still one");
});

test("after a close, a second middle click is held back too", () => {
  const p = page();
  p.act();
  p.later(100);
  assert.equal(p.reaches("auxclick", { detail: 2 }), false);
});
