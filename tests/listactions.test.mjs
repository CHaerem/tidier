// What acts on a part of the list at once (listactions.js), on Tidier's real background
// scripts and the fake Firefox: sorting, moving along, closing around a tab and duplicates,
// a whole folder or space, back and forward through the tabs used recently, a new tab in a
// folder and a tab carried to another space. Above all: what is drawn is what counts, every
// window follows, and what closes can be taken back. The menus' items are in
// tests/tabmenu.test.mjs and tests/spacemenu.test.mjs; real clicks in alone_more (smoke.py).
import { test } from "node:test";
import assert from "node:assert/strict";
import { FakeFirefox, wait } from "./fake_firefox.mjs";

const C1 = "firefox-container-1", C2 = "firefox-container-2";
const entry = (url, more = {}) => ({ url, title: more.title ?? url, cookieStoreId: C1, parentKey: null, group: false, added: 1, ...more });
const folder = (name, rank, more = {}) => ({ group: true, own: true, name, cookieStoreId: C1, parentKey: null, rank, added: 1, ...more });
const saved = (url, parentKey, more = {}) => entry(url, { parentKey, saved: { url, title: url }, ...more });

// Recently Closed and sessions.restore as Firefox's source has them (as in tests/quiet.test.mjs):
// Undo brings a page back from there.
function closedList(ff) {
  const rm = ff.rm.bind(ff);
  let id = 0;
  ff.recentlyClosed = [];
  ff.rm = (tabId, o) => {
    const t = ff.tabs.get(tabId);
    if (t && !t.url.startsWith("about:")) ff.recentlyClosed.unshift({ lastModified: Date.now(), tab: { sessionId: String(++id), url: t.url, title: t.title, windowId: t.windowId, was: { ...t }, values: { ...ff.values.get(tabId) } } });
    rm(tabId, o);
  };
}
function sessionsRestore(ff, x) {
  x.b.sessions.restore = async sessionId => {
    const at = ff.recentlyClosed.findIndex(c => c.tab.sessionId === sessionId);
    if (at < 0) throw new Error(`Could not restore object using sessionId ${sessionId}.`);
    const [{ tab: c }] = ff.recentlyClosed.splice(at, 1);
    const t = ff.addTab(c.windowId, { url: "about:blank", title: c.title, cookieStoreId: c.was.cookieStoreId }, c.values);
    x.b.tabs.onCreated.fire(ff.snap(t));
    ff.select(t.id);
    setTimeout(() => { const now = ff.tabs.get(t.id); if (!now) return; const { discarded } = now; ff.navigate(t.id, c.url, c.title); now.discarded = discarded; }, 0);
    return { lastModified: Date.now(), tab: ff.snap(t) };
  };
}

async function alone(ff) {
  closedList(ff);
  ff.managed = { tidierAlone: true };
  const x = ff.boot();
  x.b.runtime.onStartup.fire({});
  await wait(1200);
  for (let i = 0; i < 300 && !x.started(); i++) await wait(1000);
  await wait(1000);
  x.said = [];
  x.ctx.say = (windowId, text, options) => x.said.push({ text, ...options });
  x.copied = [];
  x.ctx.navigator.clipboard = { writeText: async t => { x.copied.push(t); } };
  sessionsRestore(ff, x);
  return x;
}

// Two windows with the same tabs: today's tabs `today` (key: title) in the order given, in the
// first window live and in the second as placeholders, a folder F with `inF`, another space's
// tab between them, and the first of today's tabs selected unless `active` says otherwise. The
// second window is on an essential, out of the way. No page has been used (lastAccessed 0).
async function world({ today = ["b", "a", "c"], inF = ["f2", "f1"], records = {}, active = today[0], liveFolder = null } = {}) {
  const ff = new FakeFirefox();
  ff.store.essentials = [{ key: "e", url: "https://e.example/", cookieStoreId: C1, title: "E" }];
  ff.store.syncedTabs = {
    F: folder("F", 1),
    ...(liveFolder ? { L: folder("Pull requests", 2, { live: "prs" }) } : {}),
    other: entry("https://other.example/", { cookieStoreId: C2, title: "other" }),
    ...Object.fromEntries(today.map(k => [k, entry(`https://${k}.example/`, { title: k })])),
    ...Object.fromEntries(inF.map(k => [k, saved(`https://${k}.example/`, "F", { title: k })])),
    ...Object.fromEntries((liveFolder ?? []).map(k => [k, entry(`https://${k}.example/`, { parentKey: "L", liveFolder: "prs", title: k })])),
    ...records,
  };
  const w = ff.addWindow({ focused: true }), v = ff.addWindow();
  const tab = {}, copy = {};
  tab.e = ff.addTab(w.id, { url: "https://e.example/", title: "E", cookieStoreId: C1, pinned: true, discarded: true, lastAccessed: 0 }, { essentialKey: "e" });
  copy.e = ff.addTab(v.id, { url: "https://e.example/", title: "E", cookieStoreId: C1, pinned: true, active: true, lastAccessed: 0 }, { essentialKey: "e" });
  const keys = [...inF.slice(0, 1), "other", ...today, ...inF.slice(1), ...(liveFolder ?? [])];
  for (const k of keys) {
    const e = ff.store.syncedTabs[k];
    tab[k] = ff.addTab(w.id, { url: e.url, title: e.title, cookieStoreId: e.cookieStoreId, active: k === active, lastAccessed: 0 }, { syncKey: k, syncRole: "live" });
    copy[k] = ff.addTab(v.id, { url: e.url, title: e.title, cookieStoreId: e.cookieStoreId, discarded: true, lastAccessed: 0 }, { syncKey: k, syncRole: "ghost" });
  }
  const x = await alone(ff);
  const view = async (windowId = w.id) => {
    const v = JSON.parse(JSON.stringify(await x.js("viewFor")(windowId))); // arrays of another realm compare as different
    return { today: v.tabs.map(t => t.title), folders: Object.fromEntries(v.folders.map(f => [f.name, f.tabs.map(t => t.title)])) };
  };
  // A row by its title, as drawn now: a tab brought back by Undo is a new tab.
  const idOf = async title => {
    const v = await x.js("viewFor")(w.id);
    return [...v.tabs, ...v.folders.flatMap(f => f.tabs)].find(t => t.title === title)?.id ?? tab[title].id;
  };
  const act = async (action, keysOrIds, more = {}) => {
    const tabIds = await Promise.all(keysOrIds.map(k => (typeof k === "number" ? k : idOf(k))));
    await x.js("serial")(() => x.js("tabAction")(w.id, { action, tabIds, ...more }));
    await wait(500);
  };
  const moves = () => ff.log.filter(l => l[0] === "move" && l[2] === w.id).length;
  return { ff, x, w, v, tab, copy, view, act, moves };
}

// --- Sorting ---------------------------------------------------------------------
test("sorting today's tabs by name moves only what is out of place, in every window, and Undo puts it back", async () => {
  const s = await world({ today: ["b", "a", "c", "d"] });
  const moved = s.moves();
  await s.act("sort", ["c"], { by: "name" });
  assert.deepEqual((await s.view()).today, ["a", "b", "c", "d"]);
  assert.deepEqual((await s.view(s.v.id)).today, ["a", "b", "c", "d"], "the other window follows");
  assert.equal(s.moves() - moved, 1, "one tab was out of place");
  assert.deepEqual((await s.view()).folders, { F: ["f2", "f1"] }, "the folder is not today's tabs");
  assert.deepEqual(s.x.said.map(m => m.text), ["Sorted by name"]);
  await s.x.js("serial")(s.x.said[0].undo);
  await wait(500);
  assert.deepEqual((await s.view()).today, ["b", "a", "c", "d"]);
  assert.deepEqual((await s.view(s.v.id)).today, ["b", "a", "c", "d"]);
  // Sorted already: nothing moves, and nothing is said.
  await s.act("sort", ["c"], { by: "name" });
  s.x.said = [];
  const before = s.moves();
  await s.act("sort", ["c"], { by: "name" });
  assert.equal(s.moves(), before);
  assert.deepEqual(s.x.said, []);
  s.x.kill();
});

test("a folder sorts within itself; a tile sorts today's tabs; a live folder is the search's", async () => {
  const s = await world({ today: ["b", "a"], inF: ["f2", "f3", "f1"], liveFolder: ["p2", "p1"] });
  await s.act("sort", ["f3"], { by: "name" });
  assert.deepEqual(await s.view(), { today: ["b", "a"], folders: { F: ["f1", "f2", "f3"], "Pull requests": ["p2", "p1"] } });
  await s.act("sort", ["p2"], { by: "name" });
  assert.deepEqual((await s.view()).folders["Pull requests"], ["p2", "p1"]);
  s.x.kill();
});

test("by site goes by what people call a site, then the host; by last use by the real page's use", async () => {
  const s = await world({
    today: ["z", "y", "x", "w"],
    records: {
      z: entry("https://www.zeta.example.org/", { title: "z" }), y: entry("https://gist.github.com/1", { title: "y" }),
      x: entry("https://github.com/a", { title: "x" }), w: entry("https://alpha.example/", { title: "w" }),
    },
  });
  await s.act("sort", ["z"], { by: "site" });
  assert.deepEqual((await s.view()).today, ["w", "z", "x", "y"], "Alpha, Example (zeta.example.org), then Github: github.com before gist.github.com");
  // A placeholder's own last use is when it was made: the live tab's counts.
  for (const [k, at] of [["z", 4000], ["y", 1000], ["x", 3000], ["w", 2000]]) { s.tab[k].lastAccessed = at; s.copy[k].lastAccessed = 9e12; }
  await s.act("sort", ["z"], { by: "used" });
  assert.deepEqual((await s.view()).today, ["z", "x", "w", "y"]);
  s.x.kill();
});

test("the order of the moves leaves every row where it should be, whatever the start", async () => {
  const s = await world({ today: ["e", "d", "c", "b", "a"] });
  await s.act("sort", ["a"], { by: "name" });
  assert.deepEqual((await s.view()).today, ["a", "b", "c", "d", "e"]);
  assert.deepEqual((await s.view(s.v.id)).today, ["a", "b", "c", "d", "e"]);
  const run = s.x.js("longestInOrder");
  assert.deepEqual(Array.from(run([2, 0, 1, 4, 3])), [0, 1, 3]);
  assert.deepEqual(Array.from(run([])), []);
  s.x.kill();
});

// --- Along the list ---------------------------------------------------------------
test("to the top, the bottom and one place along stay within the tab's folder or today's tabs", async () => {
  const s = await world({ today: ["a", "b", "c", "d"], inF: ["f1", "f2", "f3"] });
  await s.act("bottom", ["a"]);
  assert.deepEqual((await s.view()).today, ["b", "c", "d", "a"]);
  await s.act("top", ["c", "a"]);
  assert.deepEqual((await s.view()).today, ["c", "a", "b", "d"], "a selection keeps its order");
  await s.act("step", ["b"], { by: -1 });
  assert.deepEqual((await s.view()).today, ["c", "b", "a", "d"]);
  await s.act("step", ["c", "b"], { by: -1 });
  assert.deepEqual((await s.view()).today, ["c", "b", "a", "d"], "already at the top: they stay");
  await s.act("step", ["c", "a"], { by: 1 });
  assert.deepEqual((await s.view()).today, ["b", "c", "d", "a"], "each past the next that is not moving");
  await s.act("step", ["f1"], { by: -1 });
  await s.act("step", ["f3"], { by: 1 });
  assert.deepEqual((await s.view()).folders.F, ["f1", "f2", "f3"], "a folder's ends are its own");
  assert.deepEqual((await s.view(s.v.id)).today, ["b", "c", "d", "a"], "and every window follows");
  s.x.kill();
});

test("taking tabs out of their folder; a new folder of a selection leaves an essential alone", async () => {
  const s = await world({ today: ["a"], inF: ["f1", "f2"] });
  await s.act("takeOut", ["f2", "a"]);
  assert.deepEqual(await s.view(), { today: ["a", "f2"], folders: { F: ["f1"] } });
  assert.equal(s.ff.synced.f2.saved, undefined, "an ordinary tab again");
  const pinned = s.ff.addTab(s.w.id, { url: "https://e.example/", pinned: true, cookieStoreId: C1, index: 0 });
  const folders = () => Object.values(s.ff.synced).filter(e => e.own).length;
  const had = folders();
  await s.x.js("serial")(() => s.x.js("tabAction")(s.w.id, { action: "newFolder", tabIds: [pinned.id], space: C1 }));
  assert.equal(folders(), had, "nothing to put in it: no folder");
  await s.act("newFolder", ["a", "f2"], { space: C1 });
  assert.equal(folders(), had + 1);
  assert.deepEqual((await s.view()).today, []);
  s.x.kill();
});

// --- Closing around a tab ---------------------------------------------------------
test("close tabs below, above and the others: today's tabs as drawn, one line, and Undo", async () => {
  const s = await world({ today: ["a", "b", "c", "d", "e"], active: "a" });
  await s.act("closeBelow", ["d"]);
  assert.deepEqual((await s.view()).today, ["a", "b", "c", "d"]);
  assert.deepEqual(s.x.said.map(m => m.text), ["1 tab closed"]);
  await s.act("closeAbove", ["c"]);
  assert.deepEqual((await s.view()).today, ["c", "d"], "the one you were on too");
  assert.equal(s.ff.list(s.w.id).find(t => t.active).title, "c", "you are taken to the tab it was for");
  assert.deepEqual(s.x.said.at(-1).text, "2 tabs closed");
  assert.deepEqual((await s.view()).folders.F, ["f2", "f1"], "a folder's tabs are kept");
  await s.x.js("serial")(s.x.said.at(-1).undo);
  await wait(800);
  assert.deepEqual((await s.view()).today, ["a", "b", "c", "d"], "back, in their places");
  assert.deepEqual((await s.view(s.v.id)).today, ["a", "b", "c", "d"]);
  await s.act("closeOthers", ["b", "d"]);
  assert.deepEqual((await s.view()).today, ["b", "d"]);
  assert.deepEqual((await s.view(s.v.id)).today, ["b", "d"], "closed everywhere");
  s.x.kill();
});

test("close duplicates: by the record's address and space, the tab you are on stays, and Undo", async () => {
  const s = await world({
    today: ["a", "a2", "b", "a3", "b2", "c"], active: "a3",
    records: {
      a2: entry("https://a.example/", { title: "a2" }), a3: entry("https://a.example/", { title: "a3" }),
      b2: entry("https://b.example/", { title: "b2" }), c: entry("https://a.example/", { title: "c", cookieStoreId: C2 }),
    },
  });
  const facts = await s.x.send({ type: "tabMenu", tabIds: [s.tab.a.id] });
  assert.equal(facts[0].duplicates, 3, "the menu is told");
  await s.act("closeDuplicates", ["b"]);
  assert.deepEqual((await s.view()).today, ["b", "a3"], "the one you are on, and the first of the others");
  assert.deepEqual(s.x.said.map(m => m.text), ["3 tabs closed"]);
  await s.x.js("serial")(s.x.said[0].undo);
  await wait(800);
  assert.deepEqual((await s.view()).today, ["a", "a2", "b", "a3", "b2"]);
  s.x.kill();
});

test("a page with unsaved input stays without asking, and a tab selected in another window stays", async () => {
  const s = await world({ today: ["a", "b", "c", "d"], active: "a" });
  s.ff.refuseDiscard = new Set([s.tab.c.id]);
  s.ff.select(s.copy.d.id); // looked at in the other window
  await s.act("closeOthers", ["a"]);
  assert.deepEqual((await s.view()).today, ["a", "c", "d"]);
  assert.deepEqual(s.x.said.map(m => m.text), ["1 tab closed, 1 stayed"]);
  s.x.kill();
});

test("all of a folder's tabs closed: saved tabs go for good, with one line to bring them back into it", async () => {
  const s = await world({ today: ["a"], inF: ["f1", "f2"] });
  await s.act("closeAll", ["f1", "f2"]);
  assert.deepEqual((await s.view()).folders, { F: [] });
  assert.equal(s.ff.synced.f1, undefined, "not just unloaded");
  assert.deepEqual(s.x.said.map(m => m.text), ["2 tabs closed"]);
  await s.x.js("serial")(s.x.said[0].undo);
  await wait(800);
  assert.deepEqual((await s.view()).folders, { F: ["f1", "f2"] });
  assert.equal(s.ff.synced.f1.saved.url, "https://f1.example/", "saved again");
  s.x.kill();
});

// --- Reloading, muting, copying ----------------------------------------------------
test("reloading many goes a few at a time, each next once one has loaded", async () => {
  const s = await world({ today: ["a", "b", "c", "d", "e"] });
  const reloads = () => s.ff.log.filter(l => l[0] === "reload").map(l => l[1]);
  await s.x.js("reloadGently")([]);
  s.x.js("reloadGently")(["a", "b", "c", "d", "e"].map(k => s.tab[k].id));
  await wait(10);
  assert.equal(reloads().length, 3, "three at once");
  s.x.b.tabs.onUpdated.fire(s.tab.a.id, { status: "complete" }, s.ff.snap(s.tab.a));
  await wait(10);
  assert.equal(reloads().length, 3, "the others of the three still load");
  s.x.b.tabs.onUpdated.fire(s.tab.b.id, { status: "complete" }, s.ff.snap(s.tab.b));
  s.ff.rm(s.tab.c.id);
  await wait(10);
  assert.equal(reloads().length, 5, "then the next ones");
  s.x.kill();
});

test("a whole space: its loaded pages in any window are reloaded or muted, and its menu is told", async () => {
  const s = await world({ today: ["a", "b"] });
  s.copy.b.discarded = false; // loaded in the other window too, for a moment: both are pages
  s.tab.a.discarded = true;
  // b twice, the folder's two and the essential.
  assert.deepEqual({ ...await s.x.send({ type: "spaceFacts", space: C1, windowId: s.w.id }) }, { loaded: 5, unmuted: 5, muted: 0, duplicates: 0 });
  await s.x.js("spaceAction")(s.w.id, { action: "mute", space: C1 });
  assert.equal(s.tab.a.mutedInfo, undefined, "an unloaded tab has no sound to mute");
  assert.equal(s.tab.b.mutedInfo.muted, true);
  assert.equal(s.copy.b.mutedInfo.muted, true);
  assert.equal(s.tab.other.mutedInfo, undefined, "another space");
  assert.deepEqual({ ...await s.x.send({ type: "spaceFacts", space: C1 }) }, { loaded: 5, unmuted: 0, muted: 5, duplicates: 0 });
  await s.x.js("spaceAction")(s.w.id, { action: "reload", space: C1 });
  await wait(20000); // three at a time, the next once one has loaded or had long enough
  assert.ok(s.ff.log.some(l => l[0] === "reload" && l[1] === s.copy.b.id));
  assert.ok(!s.ff.log.some(l => l[0] === "reload" && l[1] === s.tab.a.id));
  s.x.kill();
});

test("copying as Markdown links: one per line, and a title cannot end its link", async () => {
  const s = await world({ today: ["a", "b"], records: { b: entry("https://b.example/x (1)", { title: "A [draft]\nnotes" }) } });
  await s.act("copyMarkdown", ["a", "b"]);
  assert.deepEqual(s.x.copied, ["[a](https://a.example/)\n[A \\[draft\\] notes](https://b.example/x%20%281%29)"]);
  await s.act("copy", ["a", "b"]);
  assert.equal(s.x.copied.at(-1), "https://a.example/\nhttps://b.example/x (1)");
  s.x.kill();
});

// --- Back and forward ------------------------------------------------------------------
test("back and forward go through this space's tabs by their real last use, and a walk ends when you go elsewhere", async () => {
  const s = await world({ today: ["a", "b", "c", "d"], active: "a" });
  for (const [k, at] of [["a", 9000], ["b", 3000], ["c", 7000], ["d", 0], ["f1", 5000], ["other", 8000]]) { s.tab[k].lastAccessed = at; s.copy[k].lastAccessed = 9e12; }
  const on = () => s.ff.list(s.w.id).find(t => t.active).title;
  const step = async by => { await s.x.js("stepRecent")(s.w.id, by); await wait(300); };
  await step(1);
  assert.equal(on(), "c", "the one used before");
  await step(1);
  assert.equal(on(), "f1", "a folder's tab too, but no other space's");
  await step(-1);
  assert.equal(on(), "c");
  assert.equal(s.x.js("walkedBack")(s.w.id), true);
  await step(1);
  await step(1);
  await step(1);
  assert.equal(on(), "b", "and no further than a tab you used: d never was");
  // Gone elsewhere: the next walk starts from there.
  s.ff.select(s.tab.d.id);
  s.tab.d.lastAccessed = 9500;
  await step(1);
  assert.equal(on(), "a");
  s.x.kill();
});

// --- Into a folder before there is a record ---------------------------------------------
test("a new tab made in a folder is drawn there, and goes into it once it has a page", async () => {
  const s = await world({ today: ["a"], inF: ["f1"] });
  await s.x.js("serial")(() => s.x.js("sidebarAction")(s.w.id, { type: "newTabInFolder", key: "F" }));
  const made = s.ff.list(s.w.id).find(t => t.url === "about:newtab");
  assert.ok(made?.active, "selected, ready for an address");
  assert.deepEqual(Array.from((await s.x.js("viewFor")(s.w.id)).folders[0].tabs, t => t.id), [s.tab.f1.id, made.id]);
  s.ff.navigate(made.id, "https://new.example/", "New");
  await wait(3000);
  const key = Object.keys(s.ff.synced).find(k => s.ff.synced[k].url === "https://new.example/");
  assert.equal(s.ff.synced[key]?.parentKey, "F");
  assert.equal(s.ff.synced[key]?.saved?.url, "https://new.example/", "a saved tab");
  assert.deepEqual((await s.view(s.v.id)).folders.F, ["f1", "New"], "and in the other window");
  s.x.kill();
});

test("a tab carried to another space goes to the place it was dropped there, into a folder", async () => {
  const s = await world({ today: ["a"], inF: ["f1"], records: { G: folder("G", 1, { cookieStoreId: C2 }) } });
  await s.x.js("serial")(() => s.x.js("sidebarAction")(s.w.id, { type: "space", space: C2 }));
  await s.x.js("serial")(() => s.x.js("sidebarAction")(s.w.id, { type: "moveToSpace", tabId: s.tab.a.id, space: C2, at: { before: null, folder: "G" } }));
  await wait(3000);
  const key = Object.keys(s.ff.synced).find(k => s.ff.synced[k].url === "https://a.example/");
  assert.equal(s.ff.synced[key].cookieStoreId, C2);
  assert.equal(s.ff.synced[key].parentKey, "G");
  assert.ok(!s.ff.synced.a, "the tab it was is gone");
  s.x.kill();
});

// --- Keys and the command bar -------------------------------------------------------------
test("a key acts on the sidebar's selection, else on the tab you are on", async () => {
  const s = await world({ today: ["c", "b", "a"], active: "c" });
  const press = async name => { s.x.b.commands.onCommand.fire(name, s.ff.snap(s.tab.c)); await wait(800); };
  await press("move-bottom");
  assert.deepEqual((await s.view()).today, ["b", "a", "c"]);
  s.x.b.runtime.sendMessage = async msg => (msg.type === "commandBarSelection" ? [s.tab.a.id, s.tab.b.id] : undefined);
  await press("move-bottom");
  assert.deepEqual((await s.view()).today, ["c", "b", "a"], "both of the selection, in their order");
  await press("sort-name");
  assert.deepEqual((await s.view()).today, ["a", "b", "c"]);
  await press("copy-markdown");
  assert.deepEqual(s.x.copied, ["[a](https://a.example/)\n[b](https://b.example/)"], "as the sidebar gave them");
  s.x.kill();
});

test("the command bar has them by name, where they apply, and acts on what is selected", async () => {
  const s = await world({ today: ["a", "b", "c"], inF: ["f1", "f2"], active: "b", records: { c: entry("https://a.example/", { title: "c" }) } });
  const ctx = await s.x.js("barContext")(s.w.id);
  const rows = s.x.js("barCommandRows")(ctx, {}, new Map());
  const names = rows.map(r => r.name), title = name => rows.find(r => r.name === name)?.title;
  for (const name of ["sort-name", "sort-site", "sort-used", "move-top", "move-bottom", "close-others", "close-above", "close-below", "close-duplicates", "copy-markdown", "recent-back", "space-reload", "folder-from-selection"]) assert.ok(names.includes(name), name);
  for (const name of ["take-out", "recent-forward", "folder-new-tab", "folder-close", "space-unmute"]) assert.ok(!names.includes(name), name);
  assert.equal(title("sort-name"), "Sort today's tabs by name");
  assert.equal(title("close-duplicates"), "Close 1 duplicate tab");
  await s.x.js("barRunCommand")(ctx, rows.find(r => r.name === "close-below"));
  await wait(500);
  assert.deepEqual((await s.view()).today, ["a", "b"]);
  // On a tab in a folder: that folder.
  s.ff.select(s.tab.f1.id);
  const inFolder = await s.x.js("barContext")(s.w.id);
  const there = s.x.js("barCommandRows")(inFolder, {}, new Map());
  assert.equal(there.find(r => r.name === "sort-name")?.title, "Sort this folder by name");
  for (const name of ["take-out", "folder-new-tab", "folder-reload", "folder-close"]) assert.ok(there.some(r => r.name === name), name);
  assert.ok(!there.some(r => r.name === "close-others"), "nothing closes around a folder's tab");
  s.x.kill();
});
