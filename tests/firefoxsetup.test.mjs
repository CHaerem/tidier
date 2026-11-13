// Firefox must be started again to read its setup files (firefoxsetup.js), on the fake
// Firefox with a stand-in for Tidier's helper program. What the helper itself does (which
// files, quitting and opening the Firefox that started it) is tried in a real test Firefox:
// the smoke test's alone_setup_files, and the whole restart by hand (PLAN.md).
import { test } from "node:test";
import assert from "node:assert/strict";
import { FakeFirefox, wait, realSleep, SCALE } from "./fake_firefox.mjs";

const C1 = "firefox-container-1";
const entry = url => ({ url, title: url, cookieStoreId: C1, parentKey: null, group: false, added: 1 });

// One window, and a helper that answers what the test says: `helper.changed` (the files
// newer than this Firefox), `helper.restart` (what it answers when asked to start Firefox
// again), or nothing at all (`helper.none`: no helper on this machine).
async function start({ changed = [], none = false } = {}) {
  const ff = new FakeFirefox();
  ff.store.syncedTabs = { a: entry("https://a.example/") };
  const w = ff.addWindow({ focused: true });
  ff.addTab(w.id, { url: "https://a.example/", active: true, cookieStoreId: C1 }, { syncKey: "a", syncRole: "live" });
  const helper = { changed, none, restart: { restarting: true }, asked: [] };
  const x = ff.boot();
  x.b.runtime.sendNativeMessage = async (host, msg) => {
    helper.asked.push({ host, ...msg });
    if (helper.none) throw new Error("No such native application tidier_github");
    if (msg.firefox === "changed") return helper.answer ?? { changed: helper.changed.length > 0, files: helper.changed };
    if (msg.firefox === "restart") return helper.restart;
    return { error: "unknown folder" };
  };
  x.b.runtime.onStartup.fire({ reason: "update" });
  await wait(1200);
  for (let i = 0; i < 300 && !x.started(); i++) await wait(1000);
  await wait(1000);
  x.said = [];
  x.ctx.say = (windowId, text) => x.said.push(text);
  return { ff, x, w, helper };
}
function sidebar(x, windowId) {
  const event = () => { const ls = []; return { addListener: f => ls.push(f), fire: m => Promise.all(ls.map(f => f(m))) }; };
  const views = [];
  const port = { name: "sidebar", sender: { id: "tidier" }, onMessage: event(), onDisconnect: event(), postMessage: v => views.push(JSON.parse(JSON.stringify(v))) };
  x.b.runtime.onConnect.fire(port);
  port.onMessage.fire({ type: "hello", windowId });
  return { views, send: m => port.onMessage.fire(m), get view() { return views.at(-1); } };
}
const settle = () => realSleep(600 / SCALE + 40);
const asked = (helper, what) => helper.asked.filter(m => m.firefox === what).length;

test("a setup file newer than this Firefox: the sidebar has the line, with the files, a little after Tidier starts", async () => {
  const { x, w, helper } = await start({ changed: ["userChrome.css"] });
  const side = sidebar(x, w.id);
  await wait(11000);
  await settle();
  assert.equal(asked(helper, "changed"), 1, "asked once, by itself");
  assert.equal(helper.asked.find(m => m.firefox).host, "tidier_github");
  assert.deepEqual(side.view.restart, { files: ["userChrome.css"] });
  x.kill();
});

test("nothing newer, no helper, or a helper that does not know the question: nothing is said", async () => {
  for (const world of [{ changed: [] }, { none: true }]) {
    const { x, w } = await start(world);
    const side = sidebar(x, w.id);
    await wait(11000);
    await settle();
    assert.equal(side.view.restart, null, JSON.stringify(world));
    assert.deepEqual(x.errors, [], "no helper is no error");
    x.kill();
  }
  // An older helper answers as it does to a folder it does not know.
  const { x, w, helper } = await start();
  helper.answer = { error: "unknown folder" };
  const side = sidebar(x, w.id);
  await wait(11000);
  await settle();
  assert.equal(side.view.restart, null);
  x.kill();
});

test("it is asked again on the beat the live folders wake the helper on, and the line comes and goes with the answer", async () => {
  const { x, w, helper } = await start();
  const side = sidebar(x, w.id);
  await wait(11000);
  await settle();
  assert.equal(side.view.restart, null);
  helper.changed = ["user.js", "userChrome.css"];
  x.b.alarms.onAlarm.fire({ name: "archive" });
  await settle();
  assert.equal(asked(helper, "changed"), 1, "not on another alarm");
  x.b.alarms.onAlarm.fire({ name: "liveFolders" });
  await settle();
  assert.deepEqual(side.view.restart, { files: ["user.js", "userChrome.css"] });
  const views = side.views.length;
  x.b.alarms.onAlarm.fire({ name: "liveFolders" });
  await settle();
  assert.equal(side.views.length, views, "the same answer draws nothing again");
  helper.changed = [];
  x.b.alarms.onAlarm.fire({ name: "liveFolders" });
  await settle();
  assert.equal(side.view.restart, null);
  x.kill();
});

test("put away, the line stays away for those files, and comes back when another has changed", async () => {
  const { x, w, helper } = await start({ changed: ["userChrome.css"] });
  const side = sidebar(x, w.id);
  await wait(11000);
  await settle();
  await side.send({ type: "restartSeen" });
  await settle();
  assert.equal(side.view.restart, null);
  x.b.alarms.onAlarm.fire({ name: "liveFolders" });
  await settle();
  assert.equal(side.view.restart, null, "asked again, the same files: still away");
  helper.changed = ["user.js", "userChrome.css"];
  x.b.alarms.onAlarm.fire({ name: "liveFolders" });
  await settle();
  assert.deepEqual(side.view.restart, { files: ["user.js", "userChrome.css"] });
  x.kill();
});

test("the button has the helper start Firefox again, once what Tidier holds is written", async () => {
  const { ff, x, w, helper } = await start({ changed: ["userChrome.css"] });
  const side = sidebar(x, w.id);
  await wait(11000);
  await settle();
  // Something Tidier has not written yet: it must be in the store before Firefox quits.
  const all = await x.js("getSynced")();
  all.a.title = "Written before the quit";
  x.js("saveSynced")(all, { lazy: true });
  const written = () => ff.store.syncedTabs.a.title;
  helper.restart = new Promise(resolve => { helper.go = () => resolve({ restarting: true }); });
  const sent = side.send({ type: "restartFirefox" });
  for (let i = 0; i < 100 && !asked(helper, "restart"); i++) await wait(50);
  assert.equal(asked(helper, "restart"), 1);
  assert.equal(written(), "Written before the quit");
  helper.go();
  await sent;
  assert.deepEqual(x.said, [], "nothing to say: Firefox is on its way out");
  assert.ok(x.js("traces").some(t => t.includes("restart Firefox: asked")));
  x.kill();
});

test("a helper that cannot do it: the sidebar says so, and the line stays", async () => {
  for (const restart of [{ error: "not started by a Firefox" }, { error: "unknown folder" }, null]) {
    const { x, w, helper } = await start({ changed: ["userChrome.css"] });
    helper.restart = restart;
    const side = sidebar(x, w.id);
    await wait(11000);
    await settle();
    await side.send({ type: "restartFirefox" });
    await settle();
    assert.deepEqual(x.said, ["Firefox could not be started again from here"], JSON.stringify(restart));
    assert.deepEqual(side.view.restart, { files: ["userChrome.css"] });
    x.kill();
  }
});

test("one of Tidier's own pages can ask now, and only they", async () => {
  const { x, helper } = await start({ changed: ["userChrome.css"] });
  const own = await x.send({ type: "firefoxSetup:check" }, { id: "tidier", url: "moz-extension://tidier/settings/settings.html" });
  assert.deepEqual(JSON.parse(JSON.stringify(own)), { files: ["userChrome.css"] });
  const before = asked(helper, "changed");
  assert.equal(x.send({ type: "firefoxSetup:check" }, { id: "another", url: "moz-extension://another/page.html" }), undefined);
  assert.equal(x.send({ type: "firefoxSetup:check" }, { id: "tidier", url: "https://a.example/" }), undefined);
  assert.equal(asked(helper, "changed"), before);
  x.kill();
});
