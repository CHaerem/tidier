// A page in its own fullscreen stays where it is (fullscreen.js): Tidier's real background
// scripts on the fake Firefox. That a real page in a real fullscreen stays in it is for the
// smoke test (alone_fullscreen).
import { test } from "node:test";
import assert from "node:assert/strict";
import { FakeFirefox, wait, GHOST } from "./fake_firefox.mjs";

const C1 = "firefox-container-1";
const plain = value => JSON.parse(JSON.stringify(value)); // (made in the scripts' own world)
const entry = (url, more = {}) => ({ url, title: url, cookieStoreId: C1, parentKey: null, group: false, added: 1, ...more });

async function start(ff) {
  const x = ff.boot();
  x.b.runtime.onStartup.fire({ reason: "update" });
  await wait(1200);
  for (let i = 0; i < 300 && !x.started(); i++) await wait(1000);
  await wait(1000);
  return x;
}
// Window A shows a film, and is in fullscreen; window B, the one in front, has its placeholder
// and is on another tab. `page`: what the film's page answers when asked whether it is in
// fullscreen (null: Tidier may not ask).
async function cinema({ page = true, state = "fullscreen", setting } = {}) {
  const ff = new FakeFirefox();
  ff.store.syncedTabs = { film: entry("https://film.example/watch"), other: entry("https://other.example/") };
  if (setting !== undefined) ff.store.fullscreenStays = setting;
  const a = ff.addWindow(), b = ff.addWindow({ focused: true });
  a.state = state;
  const film = ff.addTab(a.id, { url: "https://film.example/watch", cookieStoreId: C1, active: true }, { syncKey: "film", syncRole: "live" });
  ff.addTab(a.id, { url: GHOST("ghost", "other"), cookieStoreId: C1, discarded: true }, { syncKey: "other", syncRole: "ghost" });
  const other = ff.addTab(b.id, { url: "https://other.example/", cookieStoreId: C1, active: true }, { syncKey: "other", syncRole: "live" });
  const ghost = ff.addTab(b.id, { url: GHOST("ghost", "film"), cookieStoreId: C1, discarded: true }, { syncKey: "film", syncRole: "ghost" });
  const asked = [];
  if (page !== null) ff.scriptable = (id, code) => { asked.push([id, code]); return page; };
  const x = await start(ff);
  const where = () => ({ film: film.windowId === a.id ? "A" : "B", front: ff.focused === a.id ? "A" : "B", selectedInB: ff.list(b.id).find(t => t.active)?.id === ghost.id ? "placeholder" : ff.list(b.id).find(t => t.active)?.id === film.id ? "film" : "other" });
  return { ff, x, a, b, film, other, ghost, asked, where };
}

test("a page in its own fullscreen stays in its window when its placeholder is selected in another, and nothing takes you away", async () => {
  const { ff, x, film, ghost, asked, where } = await cinema();
  ff.select(ghost.id); // as closing the tab beside it does, or a key that steps through the tabs
  await wait(800);
  assert.deepEqual(where(), { film: "A", front: "B", selectedInB: "placeholder" });
  assert.deepEqual(asked.at(-1), [film.id, "!!document.fullscreenElement"], "the page is asked, and only that");
  assert.deepEqual(ff.log.filter(l => l[0] === "move"), [], "nothing moved");
  // Its placeholder says why it does not come.
  assert.deepEqual(plain(await x.send({ type: "ghostShown" }, { tab: ff.snap(ghost), url: ghost.url })), { load: false, fullscreen: true });
  x.kill();
});

test("clicked in the sidebar, it stays too, and you are taken to the window that has it", async () => {
  const { ff, x, b, ghost, where } = await cinema();
  const port = sidebarOf(x, b.id);
  port.say({ type: "select", tabId: ghost.id });
  await wait(800);
  assert.deepEqual(where(), { film: "A", front: "A", selectedInB: "placeholder" });
  // Back in the other window while the film is still in fullscreen: it stays, and you stay.
  await x.b.windows.update(b.id, { focused: true });
  await wait(800);
  assert.deepEqual(where(), { film: "A", front: "B", selectedInB: "placeholder" });
  x.kill();
});

test("once it has left fullscreen it comes: by a click on its row, selected as it is, or by coming back to the window", async () => {
  for (const how of ["click", "focus"]) {
    const { ff, x, a, b, ghost, where } = await cinema();
    const port = sidebarOf(x, b.id);
    port.say({ type: "select", tabId: ghost.id });
    await wait(800);
    assert.equal(where().film, "A");
    a.state = "normal"; // Esc
    ff.scriptable = () => false;
    await x.b.windows.update(b.id, { focused: true });
    if (how === "click") {
      // In the window that has it selected already, where nothing is selected anew by a click.
      ff.scriptable = () => true; a.state = "fullscreen";
      await wait(800);
      assert.equal(where().film, "A", "still in fullscreen as you came back");
      a.state = "normal"; ff.scriptable = () => false;
      port.say({ type: "select", tabId: ghost.id });
    }
    await wait(1200);
    assert.deepEqual(where(), { film: "B", front: "B", selectedInB: "film" }, how);
    x.kill();
  }
});

test("what is not a page's own fullscreen is pulled as ever: the window's fullscreen, no access to ask, or the choice turned off", async () => {
  for (const [name, options] of [["the window's own fullscreen", { page: false }], ["no access to websites", { page: null }], ["an ordinary window", { state: "normal" }], ["turned off", { setting: false }]]) {
    const { ff, x, ghost, asked, where } = await cinema(options);
    ff.select(ghost.id);
    await wait(1200);
    assert.deepEqual(where(), { film: "B", front: "B", selectedInB: "film" }, name);
    if (options.state === "normal" || options.setting === false) assert.deepEqual(asked, [], `${name}: no page is asked anything`);
    x.kill();
  }
});

test("an essential's page in fullscreen stays too", async () => {
  const ff = new FakeFirefox();
  ff.store.essentials = [{ key: "e", url: "https://film.example/", cookieStoreId: C1, title: "Film" }];
  const a = ff.addWindow(), b = ff.addWindow({ focused: true });
  a.state = "fullscreen";
  const page = ff.addTab(a.id, { url: "https://film.example/", pinned: true, active: true, cookieStoreId: C1 }, { essentialKey: "e" });
  const copy = ff.addTab(b.id, { url: GHOST("essential", "e"), pinned: true, discarded: true, cookieStoreId: C1 }, { essentialKey: "e" });
  ff.addTab(b.id, { url: "https://other.example/", active: true, cookieStoreId: C1 });
  ff.scriptable = () => true;
  const x = await start(ff);
  ff.select(copy.id);
  await wait(300);
  assert.deepEqual(plain(await x.send({ type: "essentialShown" }, { tab: ff.snap(copy), url: copy.url })), { load: false, fullscreen: true });
  assert.equal(page.windowId, a.id);
  assert.equal(ff.list(a.id).filter(t => t.pinned).length, 1, "no placeholder was made for a page that stays");
  // Out of fullscreen, and asked for again by its tile: it comes.
  a.state = "normal";
  ff.scriptable = () => false;
  sidebarOf(x, b.id).say({ type: "select", tabId: copy.id });
  await wait(1200);
  assert.equal(page.windowId, b.id);
  x.kill();
});

test("the settings page reads the choice and changes it", async () => {
  const { ff, x } = await cinema();
  const page = { url: "moz-extension://tidier/settings/settings.html" };
  assert.deepEqual(plain(await x.send({ type: "fullscreen:get" }, page)), { on: true }, "on until turned off");
  assert.deepEqual(plain(await x.send({ type: "fullscreen:set", on: false }, page)), { on: false });
  await x.js("flushWrites")();
  assert.equal(ff.store.fullscreenStays, false);
  assert.equal(x.send({ type: "fullscreen:set", on: true }, { url: "https://elsewhere.example/" }), undefined, "from Tidier's own pages only");
  x.kill();
});

// A window's sidebar, connected as the real one is.
function sidebarOf(x, windowId) {
  const heard = [], listeners = [];
  const port = { name: "sidebar", sender: { id: "tidier" }, onMessage: { addListener: f => listeners.push(f) }, onDisconnect: { addListener() {} }, postMessage: m => heard.push(m) };
  for (const { f } of x.b.runtime.onConnect.ls) f(port);
  const say = msg => { for (const f of listeners) f(msg); };
  say({ type: "hello", windowId });
  return { say, heard };
}
