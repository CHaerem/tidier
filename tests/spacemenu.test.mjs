// A space's menu: what it offers (sidebar/spacemenu.js, sidebar/menu.js) and what it
// does (spaceactions.js, on the fake Firefox). What it looks like, real clicks and
// real typing are in the smoke test (alone_space_menu).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { FakeFirefox, wait, GHOST } from "./fake_firefox.mjs";

const C1 = "firefox-container-1", C2 = "firefox-container-2";

// --- What it does ---------------------------------------------------------------
async function alone(ff) {
  const x = ff.boot();
  x.b.runtime.onStartup.fire();
  await wait(1200);
  for (let i = 0; i < 300 && !x.started(); i++) await wait(1000);
  await wait(1000);
  return x;
}
const entry = (url, more = {}) => ({ url, title: url, cookieStoreId: C1, parentKey: null, group: false, added: 1, ...more });
const live = key => ({ syncKey: key, syncRole: "live" });

// A space with what must stay and what must go, in two windows.
function session(ff) {
  ff.store.syncedTabs = {
    here: entry("https://here.example/"), selected: entry("https://selected.example/"),
    sound: entry("https://sound.example/"), there: entry("https://there.example/"), call: entry("https://call.example/"),
    refuses: entry("https://refuses.example/"), selected2: entry("https://selected2.example/"),
    elsewhere: entry("https://elsewhere.example/", { cookieStoreId: C2 }),
  };
  const a = ff.addWindow({ focused: true }), b = ff.addWindow();
  const tab = (w, key, url, props = {}) => ff.addTab(w.id, { url, cookieStoreId: C1, ...props }, live(key));
  const placeholder = (w, key, props = {}) => ff.addTab(w.id, { url: GHOST("ghost", key), cookieStoreId: C1, discarded: true, ...props }, { syncKey: key, syncRole: "ghost" });
  const tabs = {
    here: tab(a, "here", "https://here.example/"),
    selected: tab(a, "selected", "https://selected.example/", { active: true }),
    sound: tab(a, "sound", "https://sound.example/", { audible: true }),
    call: tab(a, "call", "https://call.example/", { sharingState: { camera: false, microphone: true, screen: undefined } }),
    refuses: tab(a, "refuses", "https://refuses.example/"),
    // Its page is loaded in the other window, as a row in this window does not show.
    there: tab(b, "there", "https://there.example/"),
    // The other window's selected tab is one you are looking at too.
    otherSelected: tab(b, "selected2", "https://selected2.example/", { active: true }),
    elsewhere: ff.addTab(a.id, { url: "https://elsewhere.example/", cookieStoreId: C2 }, live("elsewhere")),
    essential: ff.addTab(a.id, { url: "https://essential.example/", cookieStoreId: C1, pinned: true }),
  };
  placeholder(a, "there");
  for (const key of ["selected", "sound", "call", "refuses"]) placeholder(b, key);
  // Still waiting for its icon: unloaded now, it would have none (unloadGhost, tabsync.js).
  tabs.gettingIcon = placeholder(b, "here", { discarded: false });
  return { a, b, tabs };
}

test("unloading a space leaves essentials, selected tabs, sound and calls, and reaches another window", async () => {
  const ff = new FakeFirefox();
  const { a, tabs } = session(ff);
  ff.refuseDiscard = new Set([tabs.refuses.id]);
  const x = await alone(ff);
  await x.js(`sidebarAction(${a.id}, { type: "unloadSpace", space: "${C1}" })`);
  assert.equal(tabs.here.discarded, true, "an ordinary loaded tab");
  assert.equal(tabs.there.discarded, true, "a tab whose page is in another window");
  for (const name of ["selected", "otherSelected", "sound", "call", "essential", "elsewhere", "refuses", "gettingIcon"]) assert.equal(tabs[name].discarded, false, name);
  assert.deepEqual(x.errors, []);
  x.kill();
});

test("unloading a space says what it did, also for a space you are not looking at, where nothing you see changes", async () => {
  const ff = new FakeFirefox();
  const { a } = session(ff);
  const x = await alone(ff);
  const said = [];
  x.ctx.say = (windowId, text) => said.push([windowId, text]);
  await x.js(`sidebarAction(${a.id}, { type: "unloadSpace", space: "${C1}" })`);
  await x.js(`sidebarAction(${a.id}, { type: "unloadSpace", space: "${C1}" })`);
  assert.deepEqual(said, [[a.id, "3 tabs unloaded in firefox-container-1"], [a.id, "Nothing to unload in firefox-container-1"]]);
  x.kill();
});

test("a selected tab that is not in the tab record yet stays too", async () => {
  // A new tab page, which is never in the record, or a tab opened a moment ago.
  const ff = new FakeFirefox();
  session(ff);
  const w = ff.addWindow();
  const tab = ff.addTab(w.id, { url: "about:newtab", cookieStoreId: C1, active: true });
  const x = await alone(ff);
  await x.js(`unloadSpace("${C1}")`);
  assert.equal(tab.discarded, false);
  x.kill();
});

test("a tab whose placeholder is selected is on its way to you, and stays", async () => {
  const ff = new FakeFirefox();
  const { a, tabs } = session(ff);
  const x = await alone(ff);
  // As after a click on a row, before the page has been pulled into this window.
  const ghost = ff.list(a.id).find(t => t.url === GHOST("ghost", "there"));
  ff.tabs.get(ghost.id).active = true;
  ff.tabs.get(tabs.selected.id).active = false;
  await x.js(`unloadSpace("${C1}")`);
  assert.equal(tabs.there.discarded, false);
  assert.equal(tabs.selected.discarded, true, "the one you left");
  assert.equal(ff.tabs.get(ghost.id).url, GHOST("ghost", "there"), "and the placeholder is not touched");
  x.kill();
});

test("one tab closed meanwhile does not stop the others from unloading", async () => {
  const ff = new FakeFirefox();
  const { tabs } = session(ff);
  const x = await alone(ff);
  const discard = x.b.tabs.discard;
  x.b.tabs.discard = async id => { if (id === tabs.here.id) throw new Error(`Invalid tab ID: ${id}`); return discard(id); };
  await x.js(`unloadSpace("${C1}")`);
  assert.equal(tabs.there.discarded, true);
  assert.deepEqual(x.errors, []);
  x.kill();
});

test("no space given unloads nothing: a query without a container is every space's tabs", async () => {
  const ff = new FakeFirefox();
  const { a, tabs } = session(ff);
  const x = await alone(ff);
  await x.js(`sidebarAction(${a.id}, { type: "unloadSpace" })`);
  await x.js(`unloadSpace(null)`);
  for (const name of ["here", "there", "elsewhere"]) assert.equal(tabs[name].discarded, false, name);
  x.kill();
});

test("renaming a space changes its container, and an empty name does nothing", async () => {
  const ff = new FakeFirefox();
  const { a } = session(ff);
  const x = await alone(ff);
  const calls = [];
  x.b.contextualIdentities.update = async (id, changes) => { calls.push([id, changes]); };
  await x.js(`sidebarAction(${a.id}, { type: "renameSpace", space: "${C2}", name: "  Home " })`);
  await x.js(`sidebarAction(${a.id}, { type: "renameSpace", space: "${C2}", name: "   " })`);
  assert.deepEqual(calls.map(c => [c[0], { ...c[1] }]), [[C2, { name: "Home" }]]);
  x.kill();
});

// The way in from a sidebar: what its port does with a message.
async function sidebarPort(x, windowId) {
  const heard = [];
  x.b.runtime.onConnect.fire({ name: "sidebar", sender: { id: x.b.runtime.id }, postMessage() {}, onMessage: { addListener: f => heard.push(f) }, onDisconnect: { addListener() {} } });
  const say = msg => Promise.all(heard.map(f => f(msg)));
  await say({ type: "hello", windowId });
  return say;
}

test("a space's messages from the sidebar do what they say", async () => {
  const ff = new FakeFirefox();
  const { a, tabs } = session(ff);
  const x = await alone(ff);
  const calls = [];
  x.b.contextualIdentities.update = async id => { calls.push(id); };
  const say = await sidebarPort(x, a.id);
  await say({ type: "unloadSpace", space: C1 });
  await say({ type: "renameSpace", space: C1, name: "Home" });
  assert.equal(tabs.here.discarded, true);
  assert.equal(calls.length, 1);
  x.kill();
});

// --- What it offers ---------------------------------------------------------------
// The sidebar's own scripts, with the little of a page that they need. Text-only, as a
// menu is: what is drawn is for the smoke test.
// `facts`: what the background says of the space when its menu opens (spaceFacts, listactions.js).
function sidebar({ active = C1, tabs = [{ id: 1, active: true }, { id: 2 }], facts = { loaded: 0, unmuted: 0, muted: 0, duplicates: 0 } } = {}) {
  const listeners = {}, sent = [], menus = [], options = [], asked = [];
  const box = { hidden: true, style: {}, offsetHeight: 90, getBoundingClientRect: () => ({ top: 500 }), addEventListener() {}, setAttribute() {} };
  const ctx = vm.createContext({
    browser: {
      runtime: { openOptionsPage: async () => { options.push(1); }, sendMessage: async msg => { asked.push({ ...msg }); return facts; } },
      menus: { overrideContext() {} }, windows: { getCurrent: async () => ({ id: 7 }) },
    },
    document: { getElementById: () => box, querySelector: () => null, querySelectorAll: () => [] },
    addEventListener: (type, f, capture) => { (listeners[type] ??= []).push({ f, capture }); },
    port: { onMessage: { addListener() {} } },
    send: msg => sent.push(msg),
    renameNext: false, innerWidth: 300, innerHeight: 600,
    el() {},
  });
  ctx.window = ctx;
  const REPO = new URL("../", import.meta.url);
  vm.runInContext(`let view = ${JSON.stringify({ space: active, tabs, spaces: [{ id: C1, name: "One", color: "#000" }, { id: C2, name: "Two", color: "#000" }] })};`, ctx);
  for (const f of ["sidebar/menu.js", "sidebar/tabmenu.js", "sidebar/spacemenu.js", "sidebar/emoji.js", "sidebar/moremenu.js"]) vm.runInContext(readFileSync(new URL(f, REPO), "utf8"), ctx, { filename: f });
  vm.runInContext("var showMenu = items => __opened(items)", Object.assign(ctx, { __opened: items => menus.push(items) }));
  // Firefox's own menu is held back in the click; Tidier's comes once the background has answered.
  const rightClick = async (selector, dataset) => {
    const prevented = [];
    const target = { closest: s => (s === selector ? { dataset, classList: { add() {}, remove() {} } } : null), id: selector === "#space-name" ? "space-name" : "" };
    for (const { f, capture } of listeners.contextmenu) if (capture) f({ target, preventDefault: () => prevented.push(1), stopPropagation() {} });
    await new Promise(r => setTimeout(r, 5));
    return prevented.length > 0;
  };
  // (Arrays of another realm.) A line is "|", the quiet first line its name in brackets.
  const labels = items => Array.from(items, i => (i === null ? "|" : i.heading !== undefined ? `(${i.heading})` : i[0]));
  return { ctx, sent, menus, options, asked, rightClick, labels, list: () => vm.runInContext("listMenu()", ctx) };
}

// A space is only a dot on the bar, so its menu says which one it is first; Clear, which
// closes tabs, is apart after the rest, as Close is in the tab menu, and More comes last, as
// it does there (the space you see has tabs to sort, so it has More).
const OWN = ["(One)", "Rename", "Icon", "Unload this space", "Archived tabs", "|", "Settings", "|", "Clear today's tabs", "|", "More"];
test("a space's menu: its name first, then in groups; Clear apart, only for the space you are in, and only with something to clear", async () => {
  const s = sidebar();
  assert.ok(await s.rightClick("#spaces .space", { space: C1 }));
  assert.deepEqual(s.labels(s.menus.at(-1)), OWN);
  assert.ok(await s.rightClick("#spaces .space", { space: C2 }));
  assert.deepEqual(s.labels(s.menus.at(-1)), ["(Two)", "Rename", "Icon", "Unload this space", "Archived tabs", "|", "Settings"]);
  assert.equal(s.menus.at(-1)[0].color, "#000", "with its dot's colour");
  const lone = sidebar({ tabs: [{ id: 1, active: true }] });
  await lone.rightClick("#spaces .space", { space: C1 });
  assert.deepEqual(lone.labels(lone.menus.at(-1)), ["(One)", "Rename", "Icon", "Unload this space", "Archived tabs", "|", "Settings"]);
});

// A space's icon is the emoji its name starts with, so it is set by renaming the container:
// nothing more is stored, and it follows the name to Firefox's own lists and to other machines.
test("a space's icon is the emoji its name starts with, and choosing one renames the space", async () => {
  const s = sidebar();
  const icon = name => { const r = vm.runInContext(`spaceIcon(${JSON.stringify(name)})`, s.ctx); return [r.icon, r.rest]; };
  assert.deepEqual(icon("🏠 Home"), ["🏠", "Home"]);
  assert.deepEqual(icon("✈️Travel"), ["✈️", "Travel"], "with or without a space after it");
  assert.deepEqual(icon("👩‍💻 Work"), ["👩‍💻", "Work"], "a joined one is one icon");
  assert.deepEqual(icon("🇳🇴 Norge"), ["🇳🇴", "Norge"], "a flag");
  assert.deepEqual(icon("Home 🏠"), ["", "Home 🏠"], "only at the start");
  assert.deepEqual(icon("2024 plans"), ["", "2024 plans"], "a digit is no icon");
  await s.rightClick("#spaces .space", { space: C1 });
  const choices = s.menus.at(-1).find(i => i?.[0] === "Icon")[1];
  assert.equal(choices.length, 1, "no icon yet: nothing to take away, only the ones to choose from");
  assert.equal(typeof choices[0].part, "function", "which draw themselves (emojiPicker, emoji.js)");
  const choose = icon => vm.runInContext(`setSpaceIcon("${C1}", ${JSON.stringify(icon)})`, s.ctx);
  choose("🏠");
  assert.deepEqual({ ...s.sent.at(-1) }, { type: "renameSpace", space: C1, name: "🏠 One" });
  vm.runInContext(`view.spaces[0].name = "🏠 One"`, s.ctx);
  choose("⚡");
  assert.deepEqual({ ...s.sent.at(-1) }, { type: "renameSpace", space: C1, name: "⚡ One" }, "another icon takes the first one's place");
  await s.rightClick("#spaces .space", { space: C1 });
  const again = s.menus.at(-1).find(i => i?.[0] === "Icon")[1];
  assert.deepEqual(s.labels(again).slice(1), ["|", "No icon"]);
  again.at(-1)[1]();
  assert.deepEqual({ ...s.sent.at(-1) }, { type: "renameSpace", space: C1, name: "One" });
});

// The ones to choose from are a list of Tidier's own, searched by English words. Each must be
// an icon as a space's name has one, or choosing it would only add a sign to the name.
test("the icons to choose from are each one whole emoji, found by its words", () => {
  const s = sidebar();
  const list = JSON.parse(vm.runInContext("JSON.stringify(emojiList())", s.ctx));
  assert.ok(list.length > 250, `${list.length} to choose from`);
  assert.equal(new Set(list.map(e => e.icon)).size, list.length, "none twice");
  for (const { icon, words } of list) {
    const r = vm.runInContext(`spaceIcon(${JSON.stringify(icon + " Name")})`, s.ctx);
    assert.deepEqual([r.icon, r.rest], [icon, "Name"], `${icon} is one icon`);
    // A sign like ✈ is text by itself: with the mark that makes it a picture, or drawn as one anyway.
    assert.match(icon, /^(\p{Emoji_Presentation}|\p{Regional_Indicator})|\uFE0F/u, `${icon} is drawn as a picture`);
    assert.ok(words.length && words.every(w => /^[a-z]+$/.test(w)), `${icon} has words to be found by`);
  }
  const found = text => JSON.parse(vm.runInContext(`JSON.stringify(emojiSearch(${JSON.stringify(text)}).map(e => e.icon))`, s.ctx));
  assert.equal(found("").length, list.length, "nothing typed: all of them");
  assert.equal(found("lightning")[0], "⚡");
  assert.equal(found("Lightn")[0], "⚡", "the start of a word, in any case");
  assert.deepEqual(found("chart up"), ["📈"], "every word typed");
  assert.deepEqual(found("fire").slice(0, 2), ["🔥", "🦊"], "the whole word before the start of one");
  assert.deepEqual(found("⚡"), ["⚡"], "an emoji typed is the one found");
  assert.deepEqual(found(" 🫠 "), ["🫠"], "also one that is not in the list");
  assert.deepEqual(found("no such thing"), []);
});

test("the name above the list has the same menu, for the space you are in", async () => {
  const s = sidebar();
  assert.ok(await s.rightClick("#space-name"));
  assert.deepEqual(s.labels(s.menus.at(-1)), OWN);
  assert.deepEqual(s.asked, [{ type: "spaceFacts", space: C1, windowId: 7 }]);
});

// More, at the end (sidebar/moremenu.js): what the background said, and sorting and
// duplicates only for the space you see.
test("More holds what applies: sorting and duplicates here, a whole space reloaded or muted anywhere", async () => {
  const facts = { loaded: 2, unmuted: 1, muted: 1, duplicates: 2 };
  const s = sidebar({ facts });
  await s.rightClick("#spaces .space", { space: C1 });
  const items = s.menus.at(-1);
  assert.deepEqual(s.labels(items).slice(-2), ["|", "More"]);
  const more = items.at(-1)[1];
  assert.deepEqual(s.labels(more), ["Sort today's tabs", "Close 2 duplicates", "|", "Reload this space", "Mute this space", "Unmute this space"]);
  assert.deepEqual(s.labels(more[0][1]), ["By name", "By site", "By last use"]);
  more[0][1][2][1]();
  more[1][1]();
  more[3][1]();
  assert.deepEqual(JSON.parse(JSON.stringify(s.sent)), [
    { type: "tabAction", action: "sort", tabIds: [1, 2], by: "used" },
    { type: "tabAction", action: "closeDuplicates", tabIds: [1, 2] },
    { type: "spaceAction", action: "reload", space: C1 },
  ]);
  await s.rightClick("#spaces .space", { space: C2 });
  assert.deepEqual(s.labels(s.menus.at(-1).at(-1)[1]), ["Reload this space", "Mute this space", "Unmute this space"], "another space's list is not in front of you");
  const quiet = sidebar({ tabs: [{ id: 1, active: true }] });
  await quiet.rightClick("#spaces .space", { space: C2 });
  assert.ok(!quiet.labels(quiet.menus.at(-1)).includes("More"), "nothing to do: no More");
});

test("the items send what the background knows, and Settings needs no message", async () => {
  const s = sidebar();
  await s.rightClick("#spaces .space", { space: C1 });
  const item = name => s.menus.at(-1).find(i => i?.[0] === name)[1];
  item("Unload this space")();
  item("Clear today's tabs")();
  assert.deepEqual(s.sent.map(m => ({ ...m })), [{ type: "unloadSpace", space: C1 }, { type: "clearSpace", space: C1 }]);
  item("Settings")();
  assert.equal(s.options.length, 1);
});

test("Archived tabs in a space's menu is that space's list, also of a space you are not in", async () => {
  const s = sidebar();
  const asked = [];
  s.ctx.openArchived = space => asked.push(space);
  await s.rightClick("#spaces .space", { space: C2 });
  s.menus.at(-1).find(i => i?.[0] === "Archived tabs")[1]();
  assert.deepEqual(asked, [C2]);
});

test("Clear acts on the space it was offered for, wherever the window is by the time of the click", async () => {
  const s = sidebar();
  await s.rightClick("#spaces .space", { space: C1 });
  const fromDot = s.menus.at(-1).find(i => i?.[0] === "Clear today's tabs")[1], fromList = s.list()[1][1];
  vm.runInContext(`view.space = ${JSON.stringify(C2)}`, s.ctx);
  fromDot();
  fromList();
  assert.deepEqual(s.sent.map(m => m.space), [C1, C1]);
});

test("the list's menu is New folder, Clear today's tabs, Archived tabs, Settings, and stays that short", () => {
  const s = sidebar();
  assert.deepEqual(s.labels(s.list()), ["New folder", "Clear today's tabs", "Archived tabs", "Settings"]);
  s.list()[1][1]();
  assert.deepEqual({ ...s.sent.at(-1) }, { type: "clearSpace", space: C1 });
  s.list()[3][1]();
  assert.equal(s.options.length, 1);
  const lone = sidebar({ tabs: [{ id: 1, active: true }] });
  assert.deepEqual(lone.labels(lone.list()), ["New folder", "Archived tabs", "Settings"]);
});

// The sidebar's scripts share one scope as well, and here it is worse than in the
// background: a `const` declared again stops the whole later script from loading.
test("no two sidebar scripts define the same top-level name", () => {
  const page = readFileSync(new URL("../sidebar/sidebar.html", import.meta.url), "utf8");
  const seen = new Map(), twice = [];
  for (const [, file] of page.matchAll(/<script src="([^"]+)"/g)) {
    const src = readFileSync(new URL("../sidebar/" + file, import.meta.url), "utf8");
    for (const [, name] of src.matchAll(/^(?:async\s+)?(?:function\*?|const|let|var|class)\s+([A-Za-z_$][\w$]*)/gm)) {
      if (seen.has(name)) twice.push(`${name} (${seen.get(name)}, ${file})`);
      else seen.set(name, file);
    }
  }
  assert.deepEqual(twice, []);
});
