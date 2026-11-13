// A swipe on the trackpad switches space: what counts as one (sidebar/swipetrack.js, which
// needs no page), and the glimpse of the next space the background gives the sidebar for it
// (glimpseOf in sidebar-view.js, on the real background scripts and a fake Firefox). How it
// is drawn is in the smoke test (alone_swipe).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { FakeFirefox, wait, GHOST } from "./fake_firefox.mjs";

const read = f => readFileSync(new URL("../" + f, import.meta.url), "utf8");
const swipeTracker = vm.runInNewContext(read("sidebar/swipetrack.js") + "\n;swipeTracker");

// A sidebar 300 px wide with a space on each side, unless said otherwise.
const ENV = { width: 300, next: true, prev: true, still: false };
// Fingers on a trackpad, as the wheel events they become: one every 16 ms unless told.
function fingers(env = ENV) {
  const track = swipeTracker();
  let now = 1000;
  const acts = [];
  const note = act => { if (act) acts.push(JSON.parse(JSON.stringify(act))); return act; };
  const f = {
    track, acts,
    // Each move is [dx, dy]; `every` ms apart.
    move(moves, every = 16) { for (const [dx, dy] of moves) { now += every; note(track.wheel(dx, dy, now, env)); } return f; },
    // The fingers lift or rest: no event for the pause, and the page's timer says so.
    pause(ms = 200) { now += ms; if (track.swiping()) note(track.rest(env)); return f; },
    last: () => acts.at(-1),
    went: () => acts.filter(a => a.go),
  };
  return f;
}
const times = (n, move) => Array.from({ length: n }, () => move);
// What a trackpad sends after the fingers have left at speed: smaller and smaller.
const gliding = (from, axis = "x") => { const out = []; for (let d = from; d >= 1; d *= 0.9) out.push(axis === "x" ? [Math.round(d), 0] : [0, Math.round(d)]); return out; };

// --- A scroll is never a swipe -------------------------------------------------------------
test("scrolling up and down does nothing, however far it drifts sideways afterwards", () => {
  const f = fingers().move([[0, 3], [1, 6], [1, 9]]); // a scroll, by its first pixels
  f.move(times(30, [25, 1])); // then all the way across, without a pause
  f.move(gliding(40));
  assert.deepEqual(f.acts, []);
  assert.equal(f.track.swiping(), false);
});

test("the hook at the end of a scroll, and what is neither up nor sideways, is a scroll", () => {
  assert.deepEqual(fingers().move([...times(10, [0, 12]), ...times(6, [14, 2]), ...gliding(30)]).acts, [], "a hook at the end");
  assert.deepEqual(fingers().move(times(20, [8, 8])).acts, [], "at 45 degrees");
  assert.deepEqual(fingers().move(times(20, [9, 5])).acts, [], "less than twice as far sideways as down");
  assert.deepEqual(fingers().move([[4, 0], [3, 1], ...times(20, [0, 10]), ...times(10, [20, 0])]).acts, [], "a sideways start too short to count, then a scroll");
});

test("a scroll that glides on stays a scroll for fingers that come back sideways before it has stopped", () => {
  const f = fingers().move(times(8, [0, 20])).move(gliding(30, "y").slice(0, 12));
  f.move(times(12, [22, 0])); // no pause between: Firefox says nothing of the fingers
  assert.deepEqual(f.acts, []);
  f.pause().move(times(3, [6, 0]));
  assert.equal(f.acts[0]?.first, true, "after a pause, a clear sideways movement is a swipe");
});

test("random scrolling, with any drift and any hook, never switches or moves the list", () => {
  let seed = 7;
  const random = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let run = 0; run < 400; run++) {
    const f = fingers();
    // Begins as a scroll: more up or down than half the sideways part, each event.
    const sign = random() < 0.5 ? -1 : 1, start = Array.from({ length: 3 }, () => { const y = 2 + random() * 20; return [(random() - 0.5) * 3.9 * y, sign * y]; });
    const rest = Array.from({ length: 40 }, () => [(random() - 0.5) * 120, (random() - 0.5) * 40]);
    f.move([...start, ...rest], 4 + random() * 30);
    assert.deepEqual(f.acts, [], `run ${run}`);
  }
});

// --- A swipe follows the fingers ------------------------------------------------------------
test("a sideways movement becomes a swipe after 12 px, and the list starts where it lies", () => {
  const f = fingers().move([[4, 0], [4, 1]]);
  assert.deepEqual(f.acts, [], "not yet");
  f.move([[5, 0]]);
  assert.deepEqual(f.acts, [{ at: 0, first: true }], "no jump by what the fingers moved before it counted");
  f.move([[3, 0], [4, 2], [-2, 0]]);
  assert.deepEqual(f.acts.slice(1), [{ at: 3 }, { at: 7 }, { at: 5 }], "then one to one, back as well as forth, whatever goes up or down");
});

test("let go beyond four tenths of the width it goes there, short of that it comes back", () => {
  const far = fingers().move(times(34, [4, 0])).pause(); // slowly: 4 px every 16 ms is no flick
  assert.deepEqual(far.last(), { go: 1, from: 124, speed: 0 });
  const near = fingers().move(times(30, [4, 0])).pause();
  assert.deepEqual(near.last(), { back: true, from: 108 });
  const left = fingers().move(times(34, [-4, 0])).pause();
  assert.deepEqual(left.last(), { go: -1, from: -124, speed: 0 });
  assert.equal(far.track.swiping(), false, "and that is the end of it");
});

test("where Firefox says that the fingers have left, the list goes on at once, by where it is and how fast it was", () => {
  // An event of no size: nothing to wait for, and the speed at that moment counts.
  const slow = fingers().move(times(20, [4, 0])).move([[0, 0]]); // 68 px, at a quarter of a pixel a ms
  assert.equal(slow.last().back, true, "68 px and what it would coast (30 px) is short of 120");
  const quicker = fingers().move(times(12, [8, 0])).move([[0, 0]]); // 80 px, at half a pixel a ms: no flick
  assert.equal(quicker.last().go, 1, "80 px and what it would coast (60 px) is past 120");
  assert.ok(quicker.last().speed > 0.3 && quicker.last().speed < 0.7, String(quicker.last().speed));
  quicker.move(gliding(8)); // the trackpad glides on: that is no new swipe
  assert.equal(quicker.acts.filter(a => a.first).length, 1);
  assert.equal(quicker.went().length, 1);
  // Outside a swipe it says nothing: fingers that only touched, a scroll that ended.
  assert.deepEqual(fingers().move([[0, 0], [0, 0]]).acts, []);
  assert.deepEqual(fingers().move([...times(5, [0, 9]), [0, 0]]).acts, []);
  // Moving back towards where it came from, it does not go on to the other side.
  const back = fingers().move(times(20, [4, 0])).move(times(3, [-10, 0])).move([[0, 0]]);
  assert.equal(back.last().back, true);
});

test("a flick goes there at once, at the fingers' speed, and what the trackpad glides on with counts for nothing", () => {
  const f = fingers().move([[6, 0], [10, 0], [18, 0], [24, 0], [30, 1]]);
  const go = f.last();
  assert.equal(go.go, 1);
  assert.ok(go.from >= 16 && go.from < 80, `while the list has barely moved: ${go.from}`);
  assert.ok(go.speed > 0.7 && go.speed < 3, `${go.speed} px a ms`);
  f.move([[34, 0], [36, 0]]); // the fingers still on their way
  f.move(gliding(36)); // and a second of gliding, far more than a sidebar's width
  assert.equal(f.went().length, 1, "one flick, one space");
  assert.deepEqual(f.last(), go, "and nothing else");
});

test("a second flick right after the first is one more space, also before the gliding has stopped", () => {
  const f = fingers().move([[6, 0], [10, 0], [18, 0], [24, 0], [30, 0]]).move(gliding(30).slice(0, 14)); // 224 ms of gliding
  assert.equal(f.went().length, 1);
  f.move([[2, 0], [5, 0], [9, 0], [16, 0], [24, 0], [30, 0], [34, 0]]); // fingers again: it grows, which gliding never does
  assert.equal(f.went().length, 2);
  assert.equal(f.acts.filter(a => a.first).length, 2);
});

test("fingers that go on after a flick do not make it two", () => {
  // Faster and faster for a while after the flick was decided: still the same movement.
  const f = fingers().move([[6, 0], [10, 0], [18, 0], [24, 0], [30, 0], [40, 0], [52, 0], [66, 0], [80, 0]]).move(gliding(80));
  assert.equal(f.went().length, 1);
});

test("flicked back, the list comes back and does not go on to the space on the other side", () => {
  const f = fingers().move(times(20, [4, 0])); // 68 px towards the next space
  f.move(times(12, [-30, 0])); // and a hard flick the other way
  assert.equal(f.went().length, 0);
  assert.deepEqual(f.last(), { at: 0 });
  assert.deepEqual(f.pause().last(), { back: true, from: 0 });
});

test("at the first and the last space the list gives a little and comes back", () => {
  const f = fingers({ ...ENV, next: false }).move(times(40, [20, 0])); // a hard flick towards nothing
  assert.equal(f.went().length, 0);
  const shown = f.acts.filter(a => "at" in a).map(a => a.at);
  assert.ok(shown.every((at, i) => i === 0 || at >= shown[i - 1]), "it follows, less and less");
  assert.ok(shown.at(-1) > 40 && shown.at(-1) < 120, `never far: ${shown.at(-1)}`);
  assert.equal(f.pause().last().back, true);
  // The other way there is a space, as always.
  assert.equal(fingers({ ...ENV, next: false }).move(times(34, [-4, 0])).pause().last().go, -1);
});

test("a swipe never goes further than the space next to it", () => {
  const f = fingers().move(times(200, [4, 0])); // 800 px, slowly, in a sidebar of 300
  assert.equal(Math.max(...f.acts.filter(a => "at" in a).map(a => a.at)), 300);
  assert.deepEqual(f.pause().last(), { go: 1, from: 300, speed: 0 });
});

test("a swipe the list was on its way back from is taken where it is", () => {
  const f = fingers().move(times(20, [4, 0])).pause(100); // back, from 68 px
  f.move(times(3, [4, 0])); // again, at once
  assert.equal(f.last().first, true);
  f.track.from(50); // the page: it had come back to here
  assert.deepEqual(f.move([[4, 0]]).last(), { at: 54 });
});

test("what the page says is not a swipe (a menu is open, a tab is being dragged) is none until the pause", () => {
  const f = fingers().move(times(4, [4, 0]));
  f.track.ignore(1000 + 4 * 16);
  f.acts.length = 0;
  f.move(times(30, [6, 0]));
  assert.deepEqual(f.acts, []);
  assert.equal(f.pause().move(times(3, [4, 0])).last().first, true);
});

test("with less motion asked for nothing follows the fingers: a clear swipe switches, once", () => {
  const f = fingers({ ...ENV, still: true }).move(times(17, [4, 0]));
  assert.deepEqual(f.acts, [], "56 px: not yet");
  f.move(times(40, [4, 0]));
  assert.deepEqual(f.acts, [{ go: 1, still: true }]);
  assert.deepEqual(fingers({ ...ENV, still: true }).move(times(10, [4, 0])).pause().acts, [], "a short one does nothing, and nothing comes back");
  assert.deepEqual(fingers({ ...ENV, still: true, prev: false }).move(times(60, [-4, 0])).acts, [], "nor towards no space");
  assert.deepEqual(fingers({ ...ENV, still: true }).move(times(10, [0, 9])).move(times(60, [9, 0])).acts, [], "and a scroll is a scroll");
});

test("any movement at all ends in at most one switch, and never moves the list after it", () => {
  let seed = 11;
  const random = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let run = 0; run < 400; run++) {
    const f = fingers({ width: 220 + Math.floor(random() * 260), next: random() < 0.8, prev: random() < 0.8, still: false });
    const speed = 1 + random() * 60, every = 8 + random() * 12;
    // One movement: fingers that never pause or nearly stop, however unevenly they go and
    // however long, also back and forth, and then what the trackpad glides on with.
    const moves = Array.from({ length: 5 + Math.floor(random() * 120) }, () => [(random() < 0.85 ? 1 : -1) * (4 + random() * speed), (random() - 0.5) * speed * 0.3]);
    f.move(moves, every).move(gliding(Math.abs(moves.at(-1)[0])), every);
    const settled = f.acts.findIndex(a => a.go || a.back);
    if (settled >= 0) assert.equal(f.acts.length, settled + 1, `run ${run}: ${JSON.stringify(f.acts.slice(settled))}`);
    f.pause();
    assert.ok(f.went().length <= 1, `run ${run}`);
    assert.equal(f.track.swiping(), false);
  }
});

// --- The page ---------------------------------------------------------------------------------
test("the sidebar loads the swipe after what it draws with, and listens without holding scrolling back", () => {
  const scripts = [...read("sidebar/sidebar.html").matchAll(/<script src="([^"]+)"/g)].map(m => m[1]);
  const at = name => scripts.indexOf(name);
  assert.ok(at("swipetrack.js") > 0 && at("swipetrack.js") < at("swipe.js"));
  for (const before of ["sidebar.js", "stayput.js", "drag.js", "menu.js", "archived.js"]) assert.ok(at(before) < at("swipe.js"), before);
  const page = read("sidebar/swipe.js");
  assert.match(page, /addEventListener\("wheel", [\s\S]*\{ passive: true, capture: true \}\);/);
  assert.doesNotMatch(page, /preventDefault\(\)[^\n]*wheel|setInterval|requestAnimationFrame/, "no work of its own between events");
});

test("the picture of a space is drawn by the list's own styles", () => {
  const css = read("sidebar/sidebar.css");
  // Each part of the page that a swipe copies, by the class it has in the picture (AS, swipe.js).
  for (const [id, cls] of [["essentials", "essentials"], ["tabs", "list"], ["space-name", "space-name"], ["actions", "actions"], ["new-tab", "new-tab"]]) {
    assert.match(read("sidebar/swipe.js"), new RegExp(`"?${id}"?: "${cls}"`), id);
    assert.match(css, new RegExp(`#${id}, #swipe \\.${cls} \\{`), `#${id} and its picture share a rule`);
  }
  assert.match(css, /html\.swiping :is\(#essentials, #space-name, #actions, #tabs\) \{ opacity: 0; \}/);
  // A space drawn in its own colour has the names made from that colour made again (tokens.css).
  assert.match(read("sidebar/tokens.css"), /:root, \.own-accent \{[^}]*--accent-soft:[^}]*--accent-line:[^}]*--space-name:/s);
  assert.match(read("sidebar/swipe.js"), /"pane own-accent "/);
});

// --- The glimpse --------------------------------------------------------------------------------
const C1 = "firefox-container-1", C2 = "firefox-container-2";
const entry = (url, more = {}) => ({ url, title: url, cookieStoreId: C1, parentKey: null, group: false, added: 1, ...more });
async function start(ff) {
  const x = ff.boot();
  x.b.runtime.onStartup.fire({ reason: "update" });
  await wait(1200);
  for (let i = 0; i < 300 && !x.started(); i++) await wait(1000);
  await wait(1000);
  return x;
}

test("a glimpse is the other space as its view will be, with the tab a switch goes back to selected, and changes nothing", async () => {
  const ff = new FakeFirefox();
  const w = ff.addWindow({ focused: true });
  ff.store.essentials = [{ key: "e2", url: "https://e2.example/", cookieStoreId: C2, title: "E2", icon: "x" }];
  ff.store.syncedTabs = {
    here: entry("https://here.example/"),
    f2: { group: true, own: true, name: "Folder two", cookieStoreId: C2, parentKey: null, rank: 1, collapsed: false },
    kept: entry("https://kept.example/", { cookieStoreId: C2, parentKey: "f2" }),
    a: entry("https://a.example/", { cookieStoreId: C2 }), b: entry("https://b.example/", { cookieStoreId: C2 }),
  };
  const here = ff.addTab(w.id, { url: "https://here.example/", active: true, cookieStoreId: C1 }, { syncKey: "here", syncRole: "live" });
  ff.addTab(w.id, { url: GHOST("essential", "e2"), pinned: true, discarded: true, cookieStoreId: C2 }, { essentialKey: "e2" });
  ff.addTab(w.id, { url: "https://kept.example/", title: "Kept", cookieStoreId: C2 }, { syncKey: "kept", syncRole: "live" });
  const a = ff.addTab(w.id, { url: "https://a.example/", title: "A", cookieStoreId: C2 }, { syncKey: "a", syncRole: "live" });
  const b = ff.addTab(w.id, { url: "https://b.example/", title: "B", cookieStoreId: C2 }, { syncKey: "b", syncRole: "live" });
  const x = await start(ff);
  ff.select(a.id); await wait(300); // the tab used last in the second space
  ff.select(here.id); await wait(300);
  const before = JSON.stringify([ff.list(w.id).map(t => [t.id, t.active, t.hidden]), x.js("activeSpace").get(w.id)]);
  const jobs = x.js("work.jobs"), views = x.js("work.views");

  const g = JSON.parse(JSON.stringify(await x.js("glimpseOf")(w.id, C2)));
  assert.equal(g.space, C2);
  assert.deepEqual(g.essentials.map(t => t.title), ["E2"]);
  assert.deepEqual(g.folders.map(f => [f.name, f.tabs.map(t => t.title)]), [["Folder two", ["Kept"]]]);
  assert.deepEqual(g.tabs.map(t => [t.title, t.active]), [["A", true], ["B", false]], "the one a switch goes back to, not the one selected now");
  assert.ok(![...g.essentials, ...g.tabs].some(t => t.id === here.id), "nothing of the space you are in");

  await wait(300);
  assert.equal(JSON.stringify([ff.list(w.id).map(t => [t.id, t.active, t.hidden]), x.js("activeSpace").get(w.id)]), before, "nothing is selected, hidden or switched");
  assert.equal(x.js("work.jobs"), jobs, "and nothing went through the queue");
  assert.equal(x.js("work.views"), views);
  assert.equal(await x.js("glimpseOf")(w.id, "firefox-container-99"), null, "no such space");
  assert.equal(await x.js("glimpseOf")(9999, C2), null, "no such window");
  assert.notEqual(b.id, a.id);
  x.kill();
});

test("only Tidier's own pages are given a glimpse", async () => {
  const ff = new FakeFirefox();
  const w = ff.addWindow({ focused: true });
  ff.addTab(w.id, { url: "https://here.example/", active: true, cookieStoreId: C1 });
  const x = await start(ff);
  const ask = sender => Promise.all(x.b.runtime.onMessage.ls.map(({ f }) => f({ type: "glimpse", windowId: w.id, space: C1 }, sender))).then(r => r.filter(v => v !== undefined));
  const own = x.b.runtime.getURL("sidebar/sidebar.html");
  assert.equal((await ask({ id: x.b.runtime.id, url: own })).length, 1);
  assert.deepEqual(await ask({ id: "another@extension", url: own }), []);
  assert.deepEqual(await ask({ id: x.b.runtime.id, url: "https://site.example/" }), []);
  x.kill();
});
