// What you have chosen follows you through Firefox Sync (syncprefs.js): a space's colour and
// the settings. Tidier's real background scripts on fake Firefoxes whose containers are
// numbered differently, with Firefox Sync between them as MDN describes it (firefoxSyncNow).
import { test } from "node:test";
import assert from "node:assert/strict";
import { FakeFirefox, firefoxSyncNow, wait } from "./fake_firefox.mjs";

const SETTINGS = { url: "moz-extension://tidier/settings/settings.html" };
const c = n => `firefox-container-${n}`;
const plain = value => JSON.parse(JSON.stringify(value)); // (made in the scripts' own world)

function machine(names) {
  const ids = Object.keys(names).map(c);
  const ff = new FakeFirefox({ containers: ["firefox-default", ...ids] });
  ff.managed = {};
  ff.identities = Object.fromEntries(Object.entries(names).map(([n, name]) => [c(n), { name, color: "blue", colorCode: "#37adff", icon: "circle" }]));
  const w = ff.addWindow({ focused: true });
  ff.addTab(w.id, { url: "https://home.example/", title: "Home", active: true, cookieStoreId: ids[0] });
  return { ff, w };
}
async function boot(ff) {
  const x = ff.boot();
  x.b.runtime.onStartup.fire({ reason: "update" });
  await wait(1200);
  for (let i = 0; i < 300 && !x.started(); i++) await wait(1000);
  await wait(1000);
  return x;
}
const turnOn = x => x.send({ type: "sync:turn", on: true }, SETTINGS);
async function settled(x) {
  for (let i = 0; i < 400; i++) {
    await wait(100);
    if (x.js("syncTimer") === null) {
      await x.js("serial")(() => {});
      if (x.js("syncTimer") === null) return;
    }
  }
  throw new Error("a round never ended");
}
async function syncAround(server, machines, times = 3) {
  for (let i = 0; i < times; i++) {
    for (const m of machines) { await settled(m.x); firefoxSyncNow(m.ff, server); await settled(m.x); }
  }
}
// Two machines with the same two spaces, numbered the other way round, both with sync on.
async function two({ before } = {}) {
  const A = machine({ 1: "Work", 2: "Private" }), B = machine({ 1: "Private", 2: "Work" }), server = {};
  A.x = await boot(A.ff); B.x = await boot(B.ff);
  await before?.(A, B);
  await turnOn(A.x); await turnOn(B.x);
  await syncAround(server, [A, B]);
  return { A, B, server };
}
const colour = (m, space, value) => m.x.js("sidebarActionNow")(m.w.id, { type: "spaceColour", space, colour: value });
const set = (m, type, more) => m.x.send({ type, ...more }, SETTINGS);
// What a machine has chosen, as it would act on it.
const chosen = async m => ({
  colours: plain(m.x.js("chosenColours")), archive: plain(await set(m, "settings:get")).archiveHours, unload: plain(await set(m, "settings:get")).unloadHours,
  fullscreen: plain(await set(m, "fullscreen:get")).on, little: plain(await set(m, "little:get")).on,
});
const PLAIN = { archive: 12, unload: 0, fullscreen: true, little: false };

test("a colour chosen for a space, and the settings, are the same on the other machine: the colour on its own container of that space", async () => {
  const { A, B, server } = await two();
  await colour(A, c(1), "#b5651d"); // Work, which is container 2 on the other machine
  await set(A, "settings:unloadHours", { hours: 4 });
  await set(A, "settings:archiveHours", { hours: 6 });
  await set(A, "fullscreen:set", { on: false });
  await set(A, "little:set", { on: true });
  await syncAround(server, [A, B]);
  assert.deepEqual(await chosen(B), { colours: { [c(2)]: "#b5651d" }, archive: 6, unload: 4, fullscreen: false, little: true });
  assert.equal(B.ff.themes[B.w.id].colors.frame, B.x.js("tintsOf")("#37adff").light, "its window shows Private, which has no colour of its own");
  assert.deepEqual(B.ff.store.spaceColours, { [c(2)]: "#b5651d" }, "and it is kept there");
  // And back to the container's colour, from the other machine.
  await colour(B, c(2), null);
  await syncAround(server, [A, B]);
  assert.deepEqual((await chosen(A)).colours, {});
  A.x.kill(); B.x.kill();
});

test("each thing is its own: two machines that change different settings both keep their change, and the newest of one wins", async () => {
  const { A, B, server } = await two();
  await set(A, "settings:archiveHours", { hours: 6 });
  await set(B, "little:set", { on: true });
  await colour(B, c(1), "#2f6f4f"); // Private there
  await syncAround(server, [A, B]);
  for (const m of [A, B]) assert.deepEqual({ ...(await chosen(m)), colours: undefined }, { ...PLAIN, archive: 6, little: true, colours: undefined });
  assert.deepEqual((await chosen(A)).colours, { [c(2)]: "#2f6f4f" });
  // The same setting on both, one after the other: the later one.
  await set(A, "settings:unloadHours", { hours: 4 });
  await settled(A.x);
  await wait(50);
  await set(B, "settings:unloadHours", { hours: 2 });
  await syncAround(server, [A, B]);
  assert.deepEqual([(await chosen(A)).unload, (await chosen(B)).unload], [2, 2]);
  A.x.kill(); B.x.kill();
});

test("a machine with everything as it came does not overrule one where something was chosen before", async () => {
  // Chosen on one machine long before either had this, so nobody knows when.
  const { A, B, server } = await two({ before: async A => { await set(A, "settings:unloadHours", { hours: 4 }); await colour(A, c(2), "#8e4585"); } });
  assert.deepEqual([(await chosen(A)).unload, (await chosen(B)).unload], [4, 4]);
  assert.deepEqual([(await chosen(A)).colours, (await chosen(B)).colours], [{ [c(2)]: "#8e4585" }, { [c(1)]: "#8e4585" }]);
  assert.deepEqual(Object.keys(server["p/1"]).sort(), ["colour:" + Object.entries(plain(A.x.js("syncMemory")).map).find(([, id]) => id === c(2))[0], "unload"], "only what was chosen is there");
  A.x.kill(); B.x.kill();
});

test("with nothing chosen nothing is written, and nothing is written again when nothing changes", async () => {
  const { A, B, server } = await two();
  assert.equal(server["p/1"], undefined);
  await set(A, "fullscreen:set", { on: false });
  await syncAround(server, [A, B]);
  const writes = [A.ff.syncWrites, B.ff.syncWrites];
  await syncAround(server, [A, B], 2);
  A.x.js("syncSoon")(); B.x.js("syncSoon")();
  await syncAround(server, [A, B], 2);
  assert.deepEqual([A.ff.syncWrites, B.ff.syncWrites], writes, "the rounds do not answer each other");
  assert.ok(!Object.keys(server).some(k => k.startsWith("1/") && k.includes("p/")), "apart from the items a version from before this removes as its own");
  A.x.kill(); B.x.kill();
});

test("what this version does not know is carried along as it came, and a value that is none is not taken", async () => {
  const { A, B, server } = await two();
  server["p/1"] = { later: ["something", 5], "colour:not-here": ["#111111", 7], unload: ["soon", 99], fullscreen: ["no", 99], little: [true, 3], archive: "12" };
  await syncAround(server, [A, B]);
  assert.deepEqual(await chosen(A), { ...PLAIN, colours: {}, little: true });
  assert.deepEqual(plain(server["p/1"]), { later: ["something", 5], "colour:not-here": ["#111111", 7], little: [true, 3] });
  A.x.kill(); B.x.kill();
});

test("turning sync off and on again agrees anew, and keeps what the other machines chose", async () => {
  const { A, B, server } = await two();
  await set(A, "settings:unloadHours", { hours: 4 });
  await syncAround(server, [A, B]);
  await B.x.send({ type: "sync:turn", on: false }, SETTINGS);
  await set(B, "settings:unloadHours", { hours: 0 }); // as it came, while off
  await set(A, "settings:unloadHours", { hours: 8 });
  await turnOn(B.x);
  await syncAround(server, [A, B]);
  assert.deepEqual([(await chosen(A)).unload, (await chosen(B)).unload], [8, 8]);
  A.x.kill(); B.x.kill();
});
