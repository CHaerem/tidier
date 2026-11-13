// Which tab you land on when the selected one closes (nextAfterClosing in spaces.js), on
// Tidier's real background scripts and a fake Firefox. What is drawn is in the smoke test
// (alone_stay_put).
import { test } from "node:test";
import assert from "node:assert/strict";
import { FakeFirefox, wait, GHOST } from "./fake_firefox.mjs";

const C1 = "firefox-container-1", C2 = "firefox-container-2";
const entry = (url, more = {}) => ({ url, title: url, cookieStoreId: C1, parentKey: null, group: false, added: 1, ...more });
const folder = collapsed => ({ group: true, own: true, name: "F", cookieStoreId: C1, parentKey: null, rank: 1, collapsed });

async function start(ff) {
  const x = ff.boot();
  x.b.runtime.onStartup.fire({ reason: "update" });
  await wait(1200);
  for (let i = 0; i < 300 && !x.started(); i++) await wait(1000);
  await wait(1000);
  return x;
}

// One window on a selected tab, with tabs given as [key, props], and all of them in the
// record, with a closed folder "shut" and an open one "wide" to put them in by parentKey.
function fill(ff, tabs, recordMore = {}) {
  const w = ff.addWindow({ focused: true });
  const selected = ff.addTab(w.id, { url: "https://selected.example/", active: true, cookieStoreId: C1, lastAccessed: 9000 }, { syncKey: "selected", syncRole: "live" });
  ff.store.syncedTabs = { selected: entry("https://selected.example/"), shut: folder(true), wide: folder(false), ...recordMore };
  const made = {};
  for (const [key, { parentKey = null, ...props }] of tabs) {
    const url = props.url ?? `https://${key}.example/`;
    ff.store.syncedTabs[key] = entry(`https://${key}.example/`, { parentKey });
    made[key] = ff.addTab(w.id, { url, cookieStoreId: C1, ...props }, { syncKey: key, syncRole: "live" });
  }
  return { w, selected, made };
}
const next = async (x, w, selected) => (await x.js("nextAfterClosing")(w.id, C1, selected.id))?.id;

test("a loaded tab is chosen over an unloaded one used later", async () => {
  const ff = new FakeFirefox();
  const { w, selected, made } = fill(ff, [
    ["loaded", { lastAccessed: 1000 }],
    ["discarded", { lastAccessed: 5000, discarded: true }],
    ["placeholder", { lastAccessed: 8000, url: GHOST("ghost", "placeholder"), discarded: true }],
  ]);
  const x = await start(ff);
  assert.equal(await next(x, w, selected), made.loaded.id);
  x.kill();
});

test("a tab in a closed folder is passed over, though loaded and used last; an open folder is no obstacle", async () => {
  const ff = new FakeFirefox();
  const { w, selected, made } = fill(ff, [
    ["outside", { lastAccessed: 1000 }],
    ["inShut", { lastAccessed: 8000, parentKey: "shut" }],
    ["inWide", { lastAccessed: 5000, parentKey: "wide" }],
  ]);
  const x = await start(ff);
  assert.equal(await next(x, w, selected), made.inWide.id);
  x.kill();
});

test("with nothing loaded outside closed folders, it is the unloaded tab used last, by its real page", async () => {
  const ff = new FakeFirefox();
  const { w, selected, made } = fill(ff, [
    ["inShut", { lastAccessed: 8000, parentKey: "shut" }],
    // Its own lastAccessed is only when Tidier made it, and the real page is in the other window.
    ["usedEarlier", { lastAccessed: 7000, url: GHOST("ghost", "usedEarlier"), discarded: true }],
    ["usedLater", { lastAccessed: 1, url: GHOST("ghost", "usedLater"), discarded: true }],
    ["noPage", { lastAccessed: 8500, url: GHOST("ghost", "noPage"), discarded: true }],
  ]);
  const other = ff.addWindow();
  ff.addTab(other.id, { url: "https://usedEarlier.example/", cookieStoreId: C1, lastAccessed: 2000 }, { syncKey: "usedEarlier", syncRole: "live" });
  ff.addTab(other.id, { url: "https://usedLater.example/", cookieStoreId: C1, lastAccessed: 3000 }, { syncKey: "usedLater", syncRole: "live" });
  for (const k of ["usedEarlier", "usedLater"]) ff.values.set(made[k].id, { syncKey: k, syncRole: "ghost" });
  const x = await start(ff);
  assert.equal(await next(x, w, selected), made.usedLater.id);
  x.kill();
});

test("with only tabs in closed folders left, one of them is chosen; with nothing, none", async () => {
  const ff = new FakeFirefox();
  const { w, selected, made } = fill(ff, [["a", { lastAccessed: 1000, parentKey: "shut" }], ["b", { lastAccessed: 2000, parentKey: "shut" }]]);
  const x = await start(ff);
  assert.equal(await next(x, w, selected), made.b.id);
  assert.equal(await x.js("nextAfterClosing")(w.id, C2, -1), undefined);
  x.kill();
});

test("with only closed folders left, a loaded tab there goes before an unloaded one used later", async () => {
  const ff = new FakeFirefox();
  const { w, selected, made } = fill(ff, [
    ["loaded", { lastAccessed: 1000, parentKey: "shut" }],
    ["discarded", { lastAccessed: 5000, parentKey: "shut", discarded: true }],
  ]);
  const x = await start(ff);
  assert.equal(await next(x, w, selected), made.loaded.id);
  x.kill();
});

test("an essential counts, and an unloaded copy of one by its real page", async () => {
  const ff = new FakeFirefox();
  ff.store.essentials = [{ key: "e", url: "https://e.example/", cookieStoreId: C1, title: "E", icon: "x" }];
  const { w, selected, made } = fill(ff, [["plain", { lastAccessed: 1000 }]]);
  const loaded = ff.addTab(w.id, { url: "https://e.example/", pinned: true, cookieStoreId: C1, lastAccessed: 5000 }, { essentialKey: "e" });
  const x = await start(ff);
  assert.equal(await next(x, w, selected), loaded.id, "loaded and used last");
  x.kill();

  // In a window where the essential is only a placeholder, its page having been used in
  // the other window later than the placeholder tab's.
  const ff2 = new FakeFirefox();
  ff2.store.essentials = ff.store.essentials;
  const two = fill(ff2, [["ghost", { lastAccessed: 8000, url: GHOST("ghost", "ghost"), discarded: true }]]);
  const copy = ff2.addTab(two.w.id, { url: GHOST("essential", "e"), pinned: true, discarded: true, cookieStoreId: C1, lastAccessed: 1 }, { essentialKey: "e" });
  ff2.values.set(two.made.ghost.id, { syncKey: "ghost", syncRole: "ghost" });
  const other = ff2.addWindow();
  ff2.addTab(other.id, { url: "https://ghost.example/", cookieStoreId: C1, lastAccessed: 2000 }, { syncKey: "ghost", syncRole: "live" });
  ff2.addTab(other.id, { url: "https://e.example/", pinned: true, cookieStoreId: C1, lastAccessed: 3000 }, { essentialKey: "e" });
  const y = await start(ff2);
  assert.equal(await next(y, two.w, two.selected), copy.id);
  y.kill();
});

test("what Firefox is told follows a fold, an unload and a tab's closing while you stay on a tab", async () => {
  const ff = new FakeFirefox();
  const { w, selected, made } = fill(ff, [
    ["inWide", { lastAccessed: 8000, parentKey: "wide" }],
    ["second", { lastAccessed: 5000 }],
    ["third", { lastAccessed: 2000 }],
  ]);
  // A closed folder's tab rests (foldrest.js), and an unloaded tab is passed over. This one
  // refuses, as a page with unsaved input does, so only the fold says anything here.
  ff.refuseDiscard = new Set([made.inWide.id]);
  const x = await start(ff);
  const told = async want => { for (let i = 0; i < 100 && ff.tabs.get(selected.id).successorTabId !== want; i++) await wait(100); assert.equal(ff.tabs.get(selected.id).successorTabId, want); };
  await told(made.inWide.id);
  await x.js("foldFolder")("wide", true);
  await told(made.second.id);
  assert.equal((await x.js("getSynced")()).wide.collapsed, true, "the fold is what you set");
  await x.js("foldFolder")("wide", false);
  await told(made.inWide.id);
  await x.js("foldFolder")("wide", true);
  await told(made.second.id);
  // Unloaded: Firefox's event only.
  const second = ff.tabs.get(made.second.id);
  second.discarded = true;
  x.b.tabs.onUpdated.fire(second.id, { discarded: true }, ff.snap(second));
  await told(made.third.id);
  ff.rm(made.third.id);
  await told(made.second.id);
  x.kill();
});

test("a page without a container is told the next tab of the space you are in", async () => {
  const ff = new FakeFirefox();
  const { w, selected, made } = fill(ff, [
    ["used", { lastAccessed: 5000 }],
    ["unloaded", { lastAccessed: 8000, discarded: true }],
    ["inShut", { lastAccessed: 8500, parentKey: "shut" }],
  ]);
  const other = ff.addTab(w.id, { url: "https://c2.example/", cookieStoreId: C2, lastAccessed: 8700 });
  const page = ff.addTab(w.id, { url: "about:robots", lastAccessed: 1 });
  const x = await start(ff);
  ff.select(page.id);
  for (let i = 0; i < 100 && ff.tabs.get(page.id).successorTabId === undefined; i++) await wait(100);
  assert.equal(ff.tabs.get(page.id).successorTabId, selected.id, "the space's last used, not its other tabs, nor another space's");
  ff.select(selected.id);
  await wait(300);
  ff.select(page.id);
  ff.tabs.get(selected.id).discarded = true;
  x.b.tabs.onUpdated.fire(selected.id, { discarded: true }, ff.snap(ff.tabs.get(selected.id)));
  for (let i = 0; i < 100 && ff.tabs.get(page.id).successorTabId !== made.used.id; i++) await wait(100);
  assert.equal(ff.tabs.get(page.id).successorTabId, made.used.id, "looked at again while you stay on it");
  assert.notEqual(other.id, made.used.id);
  x.kill();
});

test("a tab put into a closed folder where it already is changes what Firefox is told", async () => {
  const ff = new FakeFirefox();
  const { w, selected, made } = fill(ff, [
    ["moving", { lastAccessed: 8000 }],
    ["beside", { lastAccessed: 2000 }],
  ]);
  const x = await start(ff);
  const told = async want => { for (let i = 0; i < 100 && ff.tabs.get(selected.id).successorTabId !== want; i++) await wait(100); assert.equal(ff.tabs.get(selected.id).successorTabId, want); };
  await told(made.moving.id);
  const moves = ff.log.filter(l => l[0] === "move").length;
  await x.js("moveTab")(w.id, made.moving.id, made.beside.id, "shut"); // it is right before that tab: nothing moves
  assert.equal(ff.log.filter(l => l[0] === "move").length, moves, "no move for Firefox to report");
  await told(made.beside.id);
  x.kill();
});

test("a burst while the queue is busy makes one look, for what is true by then, and leaves nothing behind", async () => {
  const ff = new FakeFirefox();
  const { w, selected, made } = fill(ff, [["other", { lastAccessed: 2000 }]]);
  const x = await start(ff);
  await wait(300);
  const jobs = x.js("work.jobs");
  let done;
  x.js("serial")(() => new Promise(r => { done = r; }));
  for (let i = 0; i < 12; i++) { x.b.tabs.onUpdated.fire(made.other.id, { discarded: false }, ff.snap(ff.tabs.get(made.other.id))); await wait(50); }
  const fresh = ff.addTab(w.id, { url: "https://fresh.example/", cookieStoreId: C1, lastAccessed: 3000 });
  done();
  for (let i = 0; i < 100 && ff.tabs.get(selected.id).successorTabId !== fresh.id; i++) await wait(100);
  assert.equal(ff.tabs.get(selected.id).successorTabId, fresh.id);
  assert.ok(x.js("work.jobs") - jobs <= 3, `${x.js("work.jobs") - jobs} jobs`); // the held one, and one look (a last event may ask for a second)
  assert.equal(x.js("successorDue.size"), 0);
  x.kill();
});

// Going to a space (lastUsedIn, switchSpace in spaces.js): back to the tab you selected
// last there, in any window. Firefox's lastAccessed says when a tab was made for a tab
// opened in the background, moved or copied, and when Tidier made it for a placeholder.
const c2 = (ff, w, key, props = {}, url = `https://${key}.example/`) => {
  ff.store.syncedTabs[key] = entry(url, { cookieStoreId: C2 });
  return ff.addTab(w.id, { url, cookieStoreId: C2, ...props }, { syncKey: key, syncRole: "live" });
};
const onNow = (ff, w) => ff.list(w.id).find(t => t.active);

test("switching space goes back to the tab you selected last there, loaded or not", async () => {
  const ff = new FakeFirefox();
  const { w, selected } = fill(ff, []);
  const loaded = c2(ff, w, "c2a", { lastAccessed: 1000 });
  const unloaded = c2(ff, w, "c2b", { lastAccessed: 500, discarded: true });
  const x = await start(ff);
  ff.select(unloaded.id); await wait(200);
  ff.tabs.get(unloaded.id).discarded = true; // unloaded again since
  ff.select(selected.id); await wait(200);
  // Opened in the background since, and so stamped as accessed later: not one you used.
  const background = c2(ff, w, "c2c", { lastAccessed: Date.now() + 5000 });
  x.b.tabs.onCreated.fire(ff.snap(background));
  await wait(200);
  await x.js("switchSpace")(w.id, C2);
  await wait(300);
  assert.equal(onNow(ff, w).id, unloaded.id);
  assert.notEqual(onNow(ff, w).id, loaded.id);
  assert.notEqual(onNow(ff, w).id, background.id);
  x.kill();
});

test("a space with nothing you used that can be shown opens a new tab: one resting in a closed folder, or moved there, is passed over", async () => {
  const ff = new FakeFirefox();
  const { w, selected } = fill(ff, []);
  ff.store.syncedTabs.shut2 = { ...folder(true), cookieStoreId: C2 };
  const resting = c2(ff, w, "rest", { discarded: true });
  ff.store.syncedTabs.rest.parentKey = "shut2";
  const moved = c2(ff, w, "moved", { discarded: true, lastAccessed: Date.now() + 5000 }); // moved or copied there
  const x = await start(ff);
  await x.js("spacePicks").set({ [C2]: ["rest"] });
  await x.js("switchSpace")(w.id, C2);
  await wait(300);
  const now = onNow(ff, w);
  assert.ok(![resting.id, moved.id, selected.id].includes(now.id), "a new tab");
  assert.equal(now.cookieStoreId, C2);
  assert.equal(now.url, "about:newtab");
  x.kill();
});

test("in another window, going to a space takes the tab you used there, but not one another window is showing", async () => {
  const ff = new FakeFirefox();
  const { w, selected } = fill(ff, []);
  const docs = c2(ff, w, "docs"), chat = c2(ff, w, "chat");
  const v = ff.addWindow();
  ff.addTab(v.id, { url: "https://v.example/", active: true, cookieStoreId: C1 });
  const ghostOf = key => ff.addTab(v.id, { url: GHOST("ghost", key), discarded: true, cookieStoreId: C2, lastAccessed: Date.now() + 9000 }, { syncKey: key, syncRole: "ghost" });
  const docsThere = ghostOf("docs"), chatThere = ghostOf("chat");
  const x = await start(ff);
  ff.select(docs.id); await wait(200);
  ff.select(chat.id); await wait(200);
  await x.js("switchSpace")(v.id, C2);
  await wait(300);
  // (By its key: the window is on docs, which no window shows any more, so its page may have come over, tabsync.js.)
  const onThere = () => ff.list(v.id).find(t => t.active);
  assert.equal(ff.values.get(onThere()?.id)?.syncKey, "docs", "chat is on show in the first window: the one before it");
  assert.ok(docsThere);
  assert.notEqual(chatThere.id, selected.id);
  ff.select(selected.id); await wait(200);
  assert.equal((await x.js("lastUsedIn")(v.id, C2, onThere().id))?.id, chatThere.id, "once that window has left it, it is the one");
  x.kill();
});

test("a tab selected in a window you are not using does not count as used", async () => {
  const ff = new FakeFirefox();
  const { w, selected } = fill(ff, []);
  const a = c2(ff, w, "a"), b = c2(ff, w, "b");
  const x = await start(ff);
  ff.select(a.id); await wait(200);
  ff.select(selected.id); await wait(200);
  const v = ff.addWindow();
  ff.addTab(v.id, { url: "https://v.example/", cookieStoreId: C1 });
  const bThere = ff.addTab(v.id, { url: GHOST("ghost", "b"), cookieStoreId: C2 }, { syncKey: "b", syncRole: "ghost" });
  ff.select(bThere.id); await wait(200); // ff.focused is still the first window
  assert.equal((await x.js("lastUsedIn")(w.id, C2))?.id, a.id);
  assert.notEqual(b.id, a.id);
  x.kill();
});
