// Each space's colour (spacelook.js): any colour, the window tinted in it by a theme of its
// own, and the sidebar's surface in the same tint. Tidier's real background scripts on the
// fake Firefox; what a real window draws with the theme is for the smoke test
// (alone_space_colour).
import { test } from "node:test";
import assert from "node:assert/strict";
import { FakeFirefox, wait } from "./fake_firefox.mjs";

const C1 = "firefox-container-1", C2 = "firefox-container-2";

async function start(ff) {
  const x = ff.boot();
  x.b.runtime.onStartup.fire({ reason: "update" });
  await wait(1200);
  for (let i = 0; i < 300 && !x.started(); i++) await wait(1000);
  await wait(1000);
  return x;
}
function twoSpaces(ff) {
  ff.identities = { [C1]: { name: "Personal", colorCode: "#37adff" }, [C2]: { name: "Work", colorCode: "#51cd00" } };
  const w = ff.addWindow({ focused: true });
  const a = ff.addTab(w.id, { url: "https://a.example/", cookieStoreId: C1, active: true });
  const b = ff.addTab(w.id, { url: "https://b.example/", cookieStoreId: C2 });
  return { w, a, b };
}

test("a colour's tint is the hand-picked one the dotfiles had for it, near enough, light and dark", () => {
  const ff = new FakeFirefox();
  const x = ff.boot();
  const tints = x.js("tintsOf");
  // What userChrome.css and tidier.css had for Firefox's blue, orange, green and pink.
  const picked = { "#37adff": ["#e1e8f3", "#1a2130"], "#ff9f00": ["#f3e9de", "#2a2119"], "#51cd00": ["#e2ede3", "#1a261d"], "#ff4bda": ["#f3e3ec", "#2a1a23"] };
  const far = (a, b) => Math.max(...[1, 3, 5].map(i => Math.abs(parseInt(a.slice(i, i + 2), 16) - parseInt(b.slice(i, i + 2), 16))));
  for (const [colour, [light, dark]] of Object.entries(picked)) {
    const t = tints(colour);
    assert.ok(far(t.light, light) <= 6, `${colour} light: ${t.light} for ${light}`);
    assert.ok(far(t.dark, dark) <= 6, `${colour} dark: ${t.dark} for ${dark}`);
  }
  // A grey stays a grey, and black and white give a surface too.
  const grey = tints("#8f8f9d").light;
  assert.ok(far(grey, "#" + grey.slice(1, 3).repeat(3)) <= 4, grey);
  for (const c of ["#000000", "#ffffff"]) assert.match(tints(c).dark, /^#[0-9a-f]{6}$/);
  x.kill();
});

test("a colour is #rrggbb, or none", () => {
  const ff = new FakeFirefox();
  const x = ff.boot(), hex = x.js("hexColour");
  assert.equal(hex("#37ADFF"), "#37adff");
  assert.equal(hex(" #3af "), "#33aaff");
  for (const none of ["blue", "#37adff80", "", null, "url(x)"]) assert.equal(hex(none), null, String(none));
  x.kill();
});

test("each window is tinted in the colour of the space it shows, and only when that changes", async () => {
  const ff = new FakeFirefox();
  const { w, b } = twoSpaces(ff);
  const x = await start(ff);
  const frame = () => ff.themes?.[w.id]?.colors.frame;
  assert.equal(frame(), x.js("tintsOf")("#37adff").light, "the space it shows: Personal's blue");
  assert.equal(ff.themes[w.id].properties.color_scheme, "system", "light or dark as the system is: Tidier's pages follow the window's");
  assert.equal(ff.themes[w.id].colors.icons, x.js("FIREFOX_LOOK").light.icons, "Firefox's own icons, not a theme's black");
  const updates = ff.themeUpdates;
  // Nothing happening, and tabs coming in: nothing new to give.
  await wait(1500);
  ff.addTab(w.id, { url: "https://c.example/", cookieStoreId: C1 });
  await wait(600);
  assert.equal(ff.themeUpdates, updates, "the same tint is not given again");
  await x.send({ type: "x" }); // (nothing)
  await x.js("serial")(() => x.js("switchSpace")(w.id, C2));
  await wait(600);
  assert.equal(frame(), x.js("tintsOf")("#51cd00").light, "Work's green, once the window shows Work");
  assert.ok(b.active);
  // A theme from elsewhere on the window: the tint is given back, once.
  const before = ff.themeUpdates;
  await x.b.theme.reset(w.id);
  await wait(300);
  assert.equal(frame(), x.js("tintsOf")("#51cd00").light);
  assert.equal(ff.themeUpdates, before + 2, "the reset, and the tint again: Tidier's own update does not start another");
  x.kill();
});

test("a colour chosen for a space is its dot's, its surface's and its window's, and its container's comes back", async () => {
  const ff = new FakeFirefox();
  const { w } = twoSpaces(ff);
  const x = await start(ff);
  const spaceIn = async () => (await x.ctx.viewFor(w.id)).spaces.find(s => s.id === C1);
  assert.deepEqual(await spaceIn().then(s => [s.color, s.ownColour]), ["#37adff", false]);
  await x.js("sidebarActionNow")(w.id, { type: "spaceColour", space: C1, colour: "#B5651D" });
  await wait(600);
  const s = await spaceIn(), tint = x.js("tintsOf")("#b5651d");
  assert.deepEqual([s.color, s.ownColour], ["#b5651d", true]);
  assert.equal(ff.themes[w.id].colors.frame, tint.light);
  assert.deepEqual(ff.store.spaceColours, { [C1]: "#b5651d" });
  assert.equal(ff.identityUpdates ?? 0, 0, "the container keeps its own: it can only have one of Firefox's eight");
  // What is no colour changes nothing.
  await x.js("sidebarActionNow")(w.id, { type: "spaceColour", space: C1, colour: "not a colour" });
  assert.deepEqual(ff.store.spaceColours, { [C1]: "#b5651d" });
  // Kept over a restart of the background part.
  const y = await start(ff);
  assert.equal((await y.ctx.viewFor(w.id)).spaces.find(t => t.id === C1).color, "#b5651d");
  await y.js("sidebarActionNow")(w.id, { type: "spaceColour", space: C1, colour: null });
  await wait(600);
  assert.deepEqual(ff.store.spaceColours, {});
  assert.equal(ff.themes[w.id].colors.frame, y.js("tintsOf")("#37adff").light, "its container's colour again");
  y.kill();
});

test("a window has its tint as soon as this part starts, by the space kept with it, before Tidier has looked at the tabs", async () => {
  const ff = new FakeFirefox();
  const { w } = twoSpaces(ff);
  ff.windowValues = { [`${w.id} space`]: C2 };
  const x = ff.boot(); // not started: nothing has said that Firefox is ready
  await wait(400);
  assert.equal(x.started(), false);
  assert.equal(ff.themes?.[w.id]?.colors.frame, x.js("tintsOf")("#51cd00").light, "Work's, as the window was left");
  // A window that comes later, before Tidier has started too.
  const later = ff.addWindow();
  ff.windowValues[`${later.id} space`] = C1;
  x.b.windows.onCreated.fire({ id: later.id, type: "normal", incognito: false });
  await wait(300);
  assert.equal(ff.themes?.[later.id]?.colors.frame, x.js("tintsOf")("#37adff").light);
  x.kill();
});

test("a private window keeps Firefox's own look", async () => {
  const ff = new FakeFirefox();
  twoSpaces(ff);
  const p = ff.addWindow();
  p.incognito = true;
  ff.addTab(p.id, { url: "https://p.example/", active: true });
  const x = await start(ff);
  x.js("tintAllSoon")();
  await wait(300);
  assert.equal(ff.themes?.[p.id], undefined);
  x.kill();
});
