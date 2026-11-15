// Tabs not used for a while are unloaded (unloadidle.js): Tidier's real background scripts on
// the fake Firefox. That a real Firefox frees the page and brings it back when the tab is
// selected is for the smoke test (alone_idle_unload).
import { test } from "node:test";
import assert from "node:assert/strict";
import { FakeFirefox, wait, GHOST } from "./fake_firefox.mjs";

const C1 = "firefox-container-1", C2 = "firefox-container-2";
const HOUR = 3600e3, NOW = Date.now();
const entry = (url, more = {}) => ({ url, title: url, cookieStoreId: C1, parentKey: null, group: false, added: 1, ...more });
const folder = { group: true, own: true, name: "F", cookieStoreId: C1, parentKey: null, rank: 1, collapsed: false };

async function start(ff) {
  const x = ff.boot();
  x.b.runtime.onStartup.fire({ reason: "update" });
  await wait(1200);
  for (let i = 0; i < 300 && !x.started(); i++) await wait(1000);
  await wait(1000);
  return x;
}

// Two windows. In the first: the tab you are on, and tabs last used `ago` hours back, by
// name. In the second: its own selected tab, and placeholders of the first window's tabs.
function session(ff, ages) {
  ff.store.syncedTabs = { F: folder, here: entry("https://here.example/"), there: entry("https://there.example/") };
  const a = ff.addWindow({ focused: true }), b = ff.addWindow();
  const tabs = {
    here: ff.addTab(a.id, { url: "https://here.example/", cookieStoreId: C1, active: true, lastAccessed: NOW - 9 * HOUR }, { syncKey: "here", syncRole: "live" }),
    there: ff.addTab(b.id, { url: "https://there.example/", cookieStoreId: C1, active: true, lastAccessed: NOW - 9 * HOUR }, { syncKey: "there", syncRole: "live" }),
  };
  const ghosts = {};
  for (const [name, { ago, ...more }] of Object.entries(ages)) {
    const { parentKey = null, space = C1, ...props } = more;
    ff.store.syncedTabs[name] = entry(`https://${name}.example/`, { parentKey, cookieStoreId: space, ...(parentKey ? { saved: { url: `https://${name}.example/`, title: name } } : {}) });
    tabs[name] = ff.addTab(a.id, { url: `https://${name}.example/`, cookieStoreId: space, lastAccessed: NOW - ago * HOUR, ...props }, { syncKey: name, syncRole: "live" });
    ghosts[name] = ff.addTab(b.id, { url: GHOST("ghost", name), cookieStoreId: space, discarded: true, lastAccessed: NOW - 9 * HOUR }, { syncKey: name, syncRole: "ghost" });
  }
  return { a, b, tabs, ghosts };
}
const loaded = tabs => Object.fromEntries(Object.entries(tabs).map(([name, t]) => [name, !t.discarded]));

test("with no time set nothing is unloaded, however long ago a tab was used", async () => {
  const ff = new FakeFirefox();
  const { tabs } = session(ff, { old: { ago: 500 } });
  const x = await start(ff);
  assert.equal(await x.js("unloadIdleTabs")({ now: NOW }), 0);
  x.b.alarms.onAlarm.fire({ name: "archive" });
  await wait(500);
  assert.equal(tabs.old.discarded, false);
  assert.ok(!ff.log.some(l => l[0] === "discard"), "and nothing is even asked of Firefox");
  x.kill();
});

test("a tab not used for the time set is unloaded where it is, and what is in use stays loaded", async () => {
  const ff = new FakeFirefox();
  ff.store.unloadAfterHours = 2;
  const { tabs, ghosts } = session(ff, {
    old: { ago: 3 }, recent: { ago: 1 }, inFolder: { ago: 5, parentKey: "F" }, otherSpace: { ago: 4, space: C2 },
    playing: { ago: 6, audible: true }, call: { ago: 6, sharingState: { camera: false, microphone: true, screen: undefined } },
    refuses: { ago: 6 }, onItsWay: { ago: 6 },
  });
  const essential = ff.addTab(tabs.here.windowId, { url: "https://essential.example/", cookieStoreId: C1, pinned: true, lastAccessed: NOW - 50 * HOUR });
  ff.refuseDiscard = new Set([tabs.refuses.id]);
  const x = await start(ff);
  // Its placeholder is selected in the other window: the page is on its way there.
  ff.tabs.get(tabs.there.id).active = false;
  ff.tabs.get(ghosts.onItsWay.id).active = true;
  const before = Object.keys(ff.synced).length, placed = name => ff.index(ff.tabs.get(tabs[name].id));
  const places = Object.fromEntries(Object.keys(tabs).map(name => [name, placed(name)]));
  assert.equal(await x.js("unloadIdleTabs")({ now: NOW }), 4);
  assert.deepEqual(loaded(tabs), {
    here: true, there: false, old: false, recent: true, inFolder: false, otherSpace: false,
    playing: true, call: true, refuses: true, onItsWay: true,
  });
  assert.equal(essential.discarded, false, "an essential is always there and ready");
  assert.equal(Object.keys(ff.synced).length, before, "nothing left the record");
  for (const name of Object.keys(tabs)) assert.equal(placed(name), places[name], `${name} is where it was`);
  for (const g of Object.values(ghosts)) assert.equal(ff.tabs.get(g.id).url.startsWith("moz-extension:"), true, "a placeholder is not touched");
  assert.deepEqual(x.errors, []);
  x.kill();
});

test("it is looked at on archiving's beat, and on no other", async () => {
  const ff = new FakeFirefox();
  ff.store.unloadAfterHours = 1;
  ff.store.archiveAfterHours = 0;
  const { tabs } = session(ff, { old: { ago: 30 } });
  const x = await start(ff);
  x.b.alarms.onAlarm.fire({ name: "liveFolders" });
  await wait(500);
  assert.equal(tabs.old.discarded, false);
  x.b.alarms.onAlarm.fire({ name: "archive" });
  await wait(500);
  assert.equal(tabs.old.discarded, true);
  assert.ok(x.js("traces").some(t => t.includes("unloaded 1 tab not used for 1 h")));
  x.kill();
});

test("the time is hours from 0 up, by quarters, and an answer that is none changes nothing", async () => {
  const ff = new FakeFirefox();
  session(ff, {});
  const x = await start(ff);
  const set = hours => x.js("settingsAction")({ type: "settings:unloadHours", hours });
  assert.equal((await x.js("settingsAction")({ type: "settings:get" })).unloadHours, 0, "off until you set a time");
  for (const none of ["", " ", "e", "Infinity", "-2", null]) assert.equal(await set(none), 0, String(none));
  assert.equal(ff.store.unloadAfterHours, undefined);
  assert.equal(await set("0.5"), 0.5);
  assert.equal(await set("1.3"), 1.25);
  assert.equal(await set("99999"), 24 * 365);
  assert.equal(await set("0"), 0, "0 is never");
  assert.equal((await x.js("settingsAction")({ type: "settings:get" })).unloadHours, 0);
  x.kill();
});
