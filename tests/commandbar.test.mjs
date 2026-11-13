// The command bar: what it ranks (no Firefox at all), and what it finds and does with
// Tidier's real background scripts on a fake Firefox. Whether Firefox really behaves so,
// with real keys, is for the smoke test (alone_command_bar).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { FakeFirefox, wait, GHOST } from "./fake_firefox.mjs";

const ctx = vm.createContext({ URL });
vm.runInContext(readFileSync(new URL("../commandbar/rank.js", import.meta.url), "utf8"), ctx);
const { rankResults, resultsFor, emptyResults, addressFrom, completionFor } = ctx;
const NOW = 1_800_000_000_000;
const titles = rows => [...rows].map(r => r.title);
const tab = (title, more = {}) => ({ kind: "tab", id: title, title, url: `https://site.example/${title.replace(/\W/g, "-")}`, lastUsed: NOW - 3600e3, ...more });

test("the start of a word beats the middle of one, and the start of the title beats both", () => {
  const middle = [tab("Airplane"), tab("Annual plan")];
  assert.deepEqual(titles(rankResults("plan", middle, NOW)), ["Annual plan", "Airplane"]);
  const start = [tab("Annual plan"), tab("Plan for today")];
  assert.deepEqual(titles(rankResults("plan", start, NOW)), ["Plan for today", "Annual plan"]);
});

test("the title beats the address", () => {
  const items = [
    { kind: "tab", id: "a", title: "Nothing here", url: "https://github.example/", lastUsed: NOW },
    { kind: "tab", id: "b", title: "My github notes", url: "https://notes.example/", lastUsed: NOW - 3 * 24 * 3600e3 },
  ];
  assert.deepEqual(titles(rankResults("github", items, NOW)), ["My github notes", "Nothing here"]);
});

test("among equal matches, the active space beats the others, and recently used beats old", () => {
  const items = [
    tab("Report old here", { here: true, lastUsed: NOW - 30 * 24 * 3600e3 }),
    tab("Report new there", { here: false, lastUsed: NOW }),
    tab("Report new here", { here: true, lastUsed: NOW }),
  ];
  assert.deepEqual(titles(rankResults("report", items, NOW)), ["Report new here", "Report old here", "Report new there"]);
});

test("the active space does not lift a poor match over a good one", () => {
  const items = [tab("Airplane", { here: true, lastUsed: NOW }), tab("Plan", { here: false, lastUsed: NOW - 30 * 24 * 3600e3 })];
  assert.deepEqual(titles(rankResults("plan", items, NOW)), ["Plan", "Airplane"]);
});

test("the tab you are on comes after other tabs that match as well", () => {
  const items = [tab("Docs one", { here: true, current: true, lastUsed: NOW }), tab("Docs two", { here: true, lastUsed: NOW - 3600e3 })];
  assert.deepEqual(titles(rankResults("docs", items, NOW)), ["Docs two", "Docs one"]);
  const elsewhere = [items[0], tab("Docs three", { here: false, lastUsed: NOW - 30 * 24 * 3600e3 })];
  assert.deepEqual(titles(rankResults("docs", elsewhere, NOW)), ["Docs three", "Docs one"], "also when the other is in another space, and old");
});

test("no fuzzy nonsense: letters must stand together, and one or two must start a word", () => {
  const items = [tab("Calendar", { url: "https://cal.example/" }), tab("Bank", { url: "https://bank.example/" })];
  assert.deepEqual(titles(rankResults("clndr", items, NOW)), []);
  assert.deepEqual(titles(rankResults("al", items, NOW)), []); // inside "Calendar", too short to count there
  assert.deepEqual(titles(rankResults("ca", items, NOW)), ["Calendar"]);
  assert.deepEqual(titles(rankResults("alen", items, NOW)), ["Calendar"]);
  assert.deepEqual(titles(rankResults("", items, NOW)), []);
  assert.deepEqual(titles(rankResults("   ", items, NOW)), []);
});

test("every word must match, in any order, and accents and case do not matter", () => {
  const items = [tab("Møte om Årsrapport"), tab("Møte i morgen"), tab("Crème brûlée")];
  assert.deepEqual(titles(rankResults("ÅRSRAPPORT møte", items, NOW)), ["Møte om Årsrapport"]);
  assert.deepEqual(titles(rankResults("creme", items, NOW)), ["Crème brûlée"]);
  assert.deepEqual(titles(rankResults("møte zzz", items, NOW)), []);
});

test("the scheme and www of an address are not something to find", () => {
  const items = [{ kind: "tab", id: "a", title: "A page", url: "https://www.example.org/" }];
  assert.deepEqual(titles(rankResults("https", items, NOW)), []);
  assert.deepEqual(titles(rankResults("www", items, NOW)), []);
  assert.deepEqual(titles(rankResults("example", items, NOW)), ["A page"]);
});

test("what is open comes before history, bookmarks and what was closed, and is not shown twice", () => {
  const url = "https://site.example/same/";
  const items = [
    { kind: "history", id: "h", title: "Same page", url, lastUsed: NOW },
    { kind: "bookmark", id: "b", title: "Same page again", url: "https://site.example/same#part", lastUsed: NOW },
    { kind: "closed", id: "c", title: "Same closed", url: "https://site.example/same", lastUsed: NOW },
    { kind: "history", id: "h2", title: "Same other", url: "https://site.example/other", lastUsed: NOW },
    { kind: "bookmark", id: "b2", title: "Same other too", url: "https://site.example/other", lastUsed: NOW - 1000 },
    { kind: "tab", id: "t", title: "Same page open", url, lastUsed: NOW - 90 * 24 * 3600e3 },
  ];
  assert.deepEqual([...rankResults("same", items, NOW)].map(r => r.id), ["t", "b2"]);
  // Two open tabs with one address are two tabs, in two spaces perhaps.
  assert.equal(rankResults("same", [items[5], { ...items[5], id: "t2" }], NOW).length, 2);
});

test("an address looks like one", () => {
  for (const [text, url] of [
    ["example.org", "https://example.org/"],
    ["example.org/a?b=c#d", "https://example.org/a?b=c#d"],
    ["sub.example.co.uk:8443/x", "https://sub.example.co.uk:8443/x"],
    ["http://intranet/", "http://intranet/"],
    ["localhost:3000/x", "http://localhost:3000/x"],
    ["localhost", "http://localhost/"],
    ["127.0.0.1:8080", "http://127.0.0.1:8080/"],
    ["wiki/", "https://wiki/"],
    ["wiki:8080", "https://wiki:8080/"],
    ["  example.org  ", "https://example.org/"],
    ["blåbær.no", "https://xn--blbr-roah.no/"],
  ]) assert.equal(addressFrom(text), url, text);
  for (const text of ["", "plain words", "word", "e.g", "1.5", "v1.2", "me@example.org", "about:config", "mailto:me@example.org", "javascript:alert(1)", "file:///etc/passwd", "a b.com", "http://", "ftp://example.org"]) {
    assert.equal(addressFrom(text), null, text);
  }
});

test("an address comes first and a search last; a search comes first when nothing matches well", () => {
  const items = [tab("Example notes", { url: "https://a.test/" }), tab("Airplane", { url: "https://b.test/" })];
  assert.deepEqual([...resultsFor("example.org", items, { now: NOW })].map(r => r.kind), ["address", "search"]);
  assert.deepEqual([...resultsFor("example", items, { now: NOW })].map(r => r.kind), ["tab", "search"]);
  assert.deepEqual([...resultsFor("plan", items, { now: NOW })].map(r => r.kind), ["search", "tab"]); // only inside "Airplane"
  assert.deepEqual([...resultsFor("zzzz", items, { now: NOW })].map(r => r.kind), ["search"]);
  assert.equal(resultsFor("zzzz", items, { now: NOW })[0].query, "zzzz");
  assert.equal(resultsFor("zzzz", items, { now: NOW })[0].title, "Search for “zzzz”");
  assert.equal(resultsFor("zzzz", items, { now: NOW, engine: "Google" })[0].title, "Search Google for “zzzz”", "the engine by name, once the bar may know it");
});

test("typing the address of an open tab goes to that tab", () => {
  const items = [{ kind: "tab", id: "t", title: "Page", url: "https://example.org/a/" }];
  assert.deepEqual([...resultsFor("example.org/a", items, { now: NOW })].map(r => r.kind), ["tab", "address", "search"]);
  const history = [{ kind: "history", id: "h", title: "Page", url: "https://example.org/a/" }];
  assert.deepEqual([...resultsFor("example.org/a", history, { now: NOW })].map(r => r.kind), ["address", "history", "search"]);
});

test("the rows never pass what fits, and the search and the quiet row are among them", () => {
  const many = Array.from({ length: 30 }, (_, i) => tab(`Report ${i}`));
  const rows = resultsFor("report", many, { now: NOW, tail: [{ kind: "ask", id: "ask", title: "Ask" }] });
  assert.equal(rows.length, 8);
  assert.deepEqual([...rows].slice(-2).map(r => r.kind), ["search", "ask"]);
  const go = resultsFor("report.example", many, { now: NOW });
  assert.ok(go.length <= 8);
});

test("with nothing typed: recent tabs of this space, not the one you are on, and the commands you use most", () => {
  const items = [
    tab("Old", { here: true, lastUsed: NOW - 7200e3 }),
    tab("New", { here: true, lastUsed: NOW - 60e3 }),
    tab("Current", { here: true, current: true, lastUsed: NOW }),
    tab("Elsewhere", { here: false, lastUsed: NOW }),
    { kind: "folder", id: "f", title: "A folder", here: true },
    { kind: "closed", id: "c", title: "Closed", url: "https://c.example/", lastUsed: NOW },
    ...["Most used", "Second", "Third", "Fourth"].map(title => ({ kind: "command", id: title, title })),
  ];
  assert.deepEqual(titles(emptyResults(items)), ["New", "Old", "Most used", "Second", "Third", "Fourth"]);
  const crowded = [...Array.from({ length: 20 }, (_, i) => tab(`T${i}`, { here: true })), ...items.slice(-4)];
  const rows = emptyResults(crowded);
  assert.equal(rows.length, 8);
  assert.equal([...rows].filter(r => r.kind === "command").length, 3);
});

test("⇥ completes: a site you are typing, else the address, else the title", () => {
  const row = { kind: "tab", title: "Page", url: "https://www.github.com/a/b" };
  assert.equal(completionFor(row, "git"), "github.com");
  assert.equal(completionFor(row, "page"), "github.com/a/b");
  assert.equal(completionFor({ kind: "command", title: "New folder" }, "new"), "New folder");
  assert.equal(completionFor({ kind: "search", title: "Search for “x”", query: "x" }, "x"), "x");
});

test("a plain Enter never closes tabs for a word that is only somewhere in a command's name", () => {
  // As commandbar.js gives them: in the table's order, Clear and Close marked careful.
  const command = (title, order, more = {}) => ({ kind: "command", id: title, title, here: true, order, ...more });
  const commands = [
    command("New tab", 0), command("Reopen closed tab", 2), command("Clear today's tabs", 4, { careful: true }),
    command("Unload this tab", 8), command("Make this tab an essential", 9), command("Close this tab", 12, { careful: true }),
    command("Next tab", 14), command("Previous tab", 15),
  ];
  const rows = resultsFor("tab", commands, { now: NOW });
  assert.equal(rows[0].title, "New tab", "on an equal score the table's order, not the alphabet");
  assert.deepEqual(titles(rankResults("tab", commands, NOW)).slice(-2), ["Clear today's tabs", "Close this tab"], "what closes comes last");
  // Typed out, the first word of its name is what you meant.
  assert.equal(resultsFor("clear", commands, { now: NOW })[0].title, "Clear today's tabs");
  assert.equal(resultsFor("close", commands, { now: NOW })[0].title, "Close this tab");
  assert.notEqual(resultsFor("cle", commands, { now: NOW })[0].title, "Clear today's tabs");
  // The only match is never the row Enter takes: the search comes first.
  assert.equal(resultsFor("today", commands, { now: NOW })[0].kind, "search");
  assert.equal(resultsFor("today", commands, { now: NOW })[1].title, "Clear today's tabs");
  // The empty bar of an empty space: whatever was used most, never what closes.
  const used = [command("Clear today's tabs", 4, { careful: true }), command("New tab", 0), command("Go to Work", 3)];
  assert.equal(emptyResults(used)[0].title, "New tab");
});

test("Copy page for Claude comes before Ask Claude, as in the table", () => {
  const items = [{ kind: "command", id: "a", title: "Ask Claude about this page", order: 20, here: true }, { kind: "command", id: "c", title: "Copy page for Claude", order: 18, here: true }];
  assert.equal(rankResults("claude", items, NOW)[0].title, "Copy page for Claude");
});

test("a title that is exactly what you typed comes first, also from another space", () => {
  const items = [tab("busy 141", { here: true, lastUsed: NOW }), tab("busy 144", { here: true, lastUsed: NOW }), tab("busy 14", { here: false, lastUsed: NOW - 30 * 24 * 3600e3 })];
  assert.equal(rankResults("busy 14", items, NOW)[0].title, "busy 14");
});

test("ø and æ are found as o and ae, as å is as a", () => {
  const items = [tab("Sommerferie på Sørlandet: reiseplan"), tab("Kjøkkenbenk i bjørk"), tab("Lærebok")];
  assert.deepEqual(titles(rankResults("sorlandet", items, NOW)), ["Sommerferie på Sørlandet: reiseplan"]);
  assert.deepEqual(titles(rankResults("sommerferie pa", items, NOW)), ["Sommerferie på Sørlandet: reiseplan"]);
  assert.deepEqual(titles(rankResults("bjork", items, NOW)), ["Kjøkkenbenk i bjørk"]);
  assert.deepEqual(titles(rankResults("laerebok", items, NOW)), ["Lærebok"]);
  assert.deepEqual(titles(rankResults("Sørlandet", items, NOW)), ["Sommerferie på Sørlandet: reiseplan"]);
});

test("the manifest asks for nothing new: the keys are given at the first start, and only optional permissions", () => {
  const manifest = JSON.parse(readFileSync(new URL("../manifest.json", import.meta.url), "utf8"));
  for (const name of ["command-bar", "command-bar-t"]) {
    assert.ok(manifest.commands[name], name);
    assert.equal(manifest.commands[name].suggested_key, undefined, name);
  }
  for (const permission of ["search", "history", "bookmarks"]) {
    assert.ok(manifest.optional_permissions.includes(permission), permission);
    assert.ok(!manifest.permissions.includes(permission), permission);
  }
});

// --- On a fake Firefox --------------------------------------------------------------
const C1 = "firefox-container-1", C2 = "firefox-container-2";

// One window in the first space and a second window: the same tabs as placeholders.
function world(ff) {
  ff.managed = { ...ff.managedMore };
  ff.store.essentials = [{ key: "e1", url: "https://essential.example/", title: "Mail", icon: "data:mail", cookieStoreId: C2 }];
  ff.store.syncedTabs = {
    here: { url: "https://here.example/", title: "Here", cookieStoreId: C1, parentKey: null, added: 1 },
    there: { url: "https://there.example/page", title: "There", cookieStoreId: C2, parentKey: null, added: 1, icon: "data:there" },
    saved: { url: "https://saved.example/", title: "Kept", cookieStoreId: C2, parentKey: "folder", added: 1, saved: { url: "https://saved.example/" } },
    folder: { group: true, own: true, name: "Work things", cookieStoreId: C2, parentKey: null, rank: 1, collapsed: true, added: 1 },
  };
  const w = ff.addWindow({ focused: true });
  const a = ff.addTab(w.id, { url: "https://here.example/", title: "Here", active: true, cookieStoreId: C1 }, { syncKey: "here", syncRole: "live" });
  ff.addTab(w.id, { url: GHOST("essential", "e1"), title: "Mail", pinned: true, cookieStoreId: C2, discarded: true }, { essentialKey: "e1" });
  ff.addTab(w.id, { url: "https://there.example/page", title: "There", cookieStoreId: C2, lastAccessed: 5000 }, { syncKey: "there", syncRole: "live" });
  ff.addTab(w.id, { url: GHOST("ghost", "saved"), title: "A placeholder's own title", cookieStoreId: C2, discarded: true, lastAccessed: 9_000_000_000_000 }, { syncKey: "saved", syncRole: "live" });
  const v = ff.addWindow();
  ff.addTab(v.id, { url: GHOST("essential", "e1"), title: "Mail", pinned: true, cookieStoreId: C2, discarded: true }, { essentialKey: "e1" });
  ff.addTab(v.id, { url: GHOST("ghost", "here"), title: "Here", active: true, cookieStoreId: C1, discarded: true }, { syncKey: "here", syncRole: "ghost" });
  const ghost = ff.addTab(v.id, { url: GHOST("ghost", "there"), title: "There", cookieStoreId: C2, discarded: true }, { syncKey: "there", syncRole: "ghost" });
  ff.addTab(v.id, { url: GHOST("ghost", "saved"), title: "A placeholder's own title", cookieStoreId: C2, discarded: true }, { syncKey: "saved", syncRole: "ghost" });
  return { w, v, a, ghost };
}

async function started(ff) {
  const x = ff.boot();
  x.b.runtime.onStartup.fire();
  for (let i = 0; i < 400 && !x.started(); i++) await wait(1000);
  await wait(500);
  return x;
}

// The bar's page, as far as the background can tell: it connects, and gets one message.
function connectPage(ff, x) {
  const bar = [...ff.wins.values()].at(-1);
  const tab = ff.tabs.get(bar.order[0]);
  const listeners = [], gone = [], sent = [];
  const port = {
    name: "commandbar", sender: { id: "tidier", url: tab.url, tab: ff.snap(tab) }, postMessage: m => sent.push(m),
    onMessage: { addListener: f => listeners.push(f) }, onDisconnect: { addListener: f => gone.push(f) },
  };
  for (const { f } of x.b.runtime.onConnect.ls) f(port);
  return { port, sent, tell: async m => { for (const f of listeners) await f(m); }, bar, disconnect: () => gone.forEach(f => f()) };
}

const pressKey = async (ff, x, windowId) => {
  x.b.commands.onCommand.fire("command-bar", ff.snap(ff.tabs.get(ff.wins.get(windowId).order.find(id => ff.tabs.get(id).active))));
  await wait(200);
};
async function openBar(ff, x, windowId) {
  await pressKey(ff, x, windowId);
  const page = connectPage(ff, x);
  for (let i = 0; i < 100 && !page.sent.length; i++) await wait(100);
  return page;
}
const barWindows = ff => [...ff.wins.values()].filter(w => w.type === "popup");

test("the command gets its keys, and a key you changed stays", async () => {
  const ff = new FakeFirefox();
  ff.commands = [{ name: "command-bar", shortcut: "" }, { name: "command-bar-t", shortcut: "Alt+T" }];
  world(ff);
  const x = await started(ff);
  assert.equal(ff.commandsSet["command-bar"], "Ctrl+Shift+K");
  assert.equal(ff.commandsSet["command-bar-t"], undefined);
  x.kill();
});

test("the bar finds a placeholder by the real tab's address, unloaded tabs, essentials and folders", async () => {
  const ff = new FakeFirefox();
  const { v } = world(ff);
  const x = await started(ff);
  ff.synced.nowhere = { url: "https://nowhere.example/", title: "In no window", cookieStoreId: C1, parentKey: null, added: 1 };
  const page = await openBar(ff, x, v.id);
  const { items, space } = page.sent[0];
  assert.ok(!items.some(i => i.id === "tab:nowhere"), "a tab no window has is nothing to go to");
  assert.equal(space, C1);
  const byId = id => items.find(i => i.id === id);
  assert.equal(byId("tab:there").url, "https://there.example/page"); // here only a placeholder
  assert.equal(byId("tab:there").title, "There");
  assert.equal(byId("tab:there").here, false);
  assert.equal(byId("tab:here").here, true);
  assert.equal(byId("tab:here").current, true);
  assert.equal(byId("tab:saved").url, "https://saved.example/"); // unloaded everywhere
  assert.equal(byId("tab:saved").title, "Kept");
  assert.ok(byId("tab:saved").lastUsed < 1000, "a placeholder's own last use says nothing");
  assert.equal(byId("essential:e1").url, "https://essential.example/");
  assert.equal(byId("essential:e1").title, "Mail");
  assert.equal(byId("essential:e1").space, C2);
  assert.equal(byId("folder:folder").title, "Work things");
  assert.ok(!items.some(i => /ghost\.html/.test(i.url || "")), "no placeholder's own address");
  assert.equal(items.filter(i => i.id === "tab:there").length, 1, "one row per tab, whatever the number of windows");
  x.kill();
});

test("the window opens centred over the one you are in, and the key closes it", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  await pressKey(ff, x, w.id);
  const [bar] = barWindows(ff);
  assert.ok(bar);
  assert.equal(bar.left, 100 + (1200 - 640) / 2);
  const url = ff.tabs.get(bar.order[0]).url;
  assert.match(url, /^commandbar\/commandbar\.html(\?[^#]*)?#\d+$/);
  assert.equal(new URLSearchParams(url.split("?")[1]?.split("#")[0]).get("space"), C1, "so its first frame is in the space's colours");
  await pressKey(ff, x, w.id);
  assert.equal(barWindows(ff).length, 0);
  assert.equal(ff.focused, w.id);
  x.kill();
});

test("the key pressed again before the window is there leaves no window behind", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const fire = () => x.b.commands.onCommand.fire("command-bar", ff.snap(ff.tabs.get(w.order[0])));
  fire(); fire();
  await wait(300);
  assert.equal(barWindows(ff).length, 0);
  fire();
  await wait(300);
  assert.equal(barWindows(ff).length, 1);
  fire();
  await wait(300);
  fire(); fire(); fire();
  await wait(300);
  assert.equal(barWindows(ff).length, 1, "three presses are the same as one");
  x.kill();
});

test("a bar brought back with the session closes itself, and never a normal window", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const stray = ff.addWindow({ type: "popup" }); // what Firefox's session could bring back
  ff.addTab(stray.id, { url: "commandbar/commandbar.html", active: true });
  const page = connectPage(ff, x);
  await wait(100);
  assert.equal(page.sent.length, 0);
  assert.ok(!ff.wins.has(stray.id));
  // The page opened by hand as a tab: only that tab goes.
  const t = ff.addTab(w.id, { url: "commandbar/commandbar.html" });
  for (const { f } of x.b.runtime.onConnect.ls) f({ name: "commandbar", sender: { id: "tidier", tab: ff.snap(t) }, postMessage() {}, onMessage: { addListener() {} }, onDisconnect: { addListener() {} } });
  await wait(100);
  assert.ok(ff.wins.has(w.id));
  assert.ok(!ff.tabs.has(t.id));
  x.kill();
});

test("a closed bar is not left under Recently Closed Windows, but a real window is", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  ff.recentlyClosed = [{ lastModified: 1, window: { sessionId: "real", tabs: [{ url: "https://real.example/" }] } }];
  await pressKey(ff, x, w.id);
  const bar = barWindows(ff)[0];
  ff.tabs.get(bar.order[0]).url = "moz-extension://tidier/commandbar/commandbar.html";
  await pressKey(ff, x, w.id);
  await wait(300);
  assert.deepEqual(Array.from(ff.recentlyClosed, c => c.window.sessionId), ["real"]);
  // Long after, a window with the same page in it is not looked for any more.
  x.js("barForgetUntil = 0");
  ff.recentlyClosed.unshift({ lastModified: 2, window: { sessionId: "later", tabs: [{ url: "moz-extension://tidier/commandbar/commandbar.html" }] } });
  x.b.sessions.onChanged.fire();
  await wait(100);
  assert.equal(ff.recentlyClosed.length, 2);
  x.kill();
});

test("the keys typed before the bar has the keyboard are caught where they go, and handed to it", async () => {
  const ff = new FakeFirefox();
  const { w, a } = world(ff);
  const x = await started(ff);
  const asked = [], told = [];
  x.b.tabs.sendMessage = async (tabId, msg) => { asked.push([tabId, msg]); };
  const send = x.b.runtime.sendMessage;
  x.b.runtime.sendMessage = async msg => { if (msg.type === "bar:catch") told.push(msg); return send(msg); };
  const page = await openBar(ff, x, w.id);
  const pressedAt = asked[0]?.[1].pressedAt;
  assert.deepEqual(asked.map(([id, m]) => [id, m.type]), [[a.id, "bar:catch"], [a.id, "bar:stop"]], "the page you were in, until the bar's page is there");
  assert.deepEqual(told.map(m => [m.windowId, m.pressedAt]), [[w.id, pressedAt]], "and this window's sidebar");
  assert.ok(asked.every(([, m]) => m.pressedAt === pressedAt));
  assert.ok(page.port.sender.url.endsWith(`#${pressedAt}`));
  // Another press's keys, or a page's own message, are not this bar's.
  x.send({ type: "bar:early", pressedAt: pressedAt - 1, text: "old" });
  x.send({ type: "bar:early", pressedAt, text: "from a page" }, { id: "someone-else" });
  x.send({ type: "bar:early", pressedAt, text: "ferry", enter: { inNewTab: false }, escape: false });
  await wait(50);
  const early = page.sent.filter(m => m.type === "early");
  assert.deepEqual(early.map(m => [m.text, m.enter?.inNewTab, m.escape]), [["ferry", false, false]], "once, and only this press's");
  x.kill();
});

test("caught before the page is there, they wait for it, and go before the rows", async () => {
  // The page keeps an Enter until the rows are there (commandbar/commandbar.js), so the
  // letters typed first must be there before them: "ferry" + Enter is not a search for "rry".
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  let pressedAt;
  x.b.tabs.sendMessage = async (tabId, msg) => { pressedAt = msg.pressedAt; };
  await pressKey(ff, x, w.id);
  x.send({ type: "bar:early", pressedAt, text: "w" });
  const page = connectPage(ff, x);
  for (let i = 0; i < 100 && page.sent.length < 2; i++) await wait(50);
  assert.deepEqual(page.sent.map(m => m.type ?? "rows"), ["early", "rows"]);
  assert.equal(page.sent[0].text, "w");
  x.kill();
});

test("over a narrow window the bar is narrower, and stays centred over it", async () => {
  const ff = new FakeFirefox();
  world(ff);
  const narrow = ff.addWindow({ focused: true, left: 900, width: 500, height: 600 });
  ff.addTab(narrow.id, { url: "https://narrow.example/", active: true, cookieStoreId: C1 });
  const x = await started(ff);
  await pressKey(ff, x, narrow.id);
  const [bar] = barWindows(ff);
  assert.equal(bar.width, 500 - 48);
  assert.equal(bar.left + bar.width / 2, 900 + 500 / 2);
  x.kill();
});

test("a command's question says what it is for, and a move names what moves", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const page = await openBar(ff, x, w.id);
  const items = page.sent[0].items, byName = name => items.find(i => i.name === name);
  assert.match(byName("new-folder").ask.heading, /^New folder in /);
  assert.equal(byName("new-folder").ask.confirm, "Create “#”");
  assert.equal(byName("new-folder").ask.empty, "Create “New folder”");
  assert.equal(byName("move-to-space").heading, "Move “Here” to");
  x.kill();
});

test("if the page goes away the window goes with it", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const page = await openBar(ff, x, w.id);
  page.disconnect();
  await wait(100);
  assert.equal(barWindows(ff).length, 0);
  x.kill();
});

test("choosing a tab in another space switches space and pulls it in", async () => {
  const ff = new FakeFirefox();
  const { v, ghost } = world(ff);
  const x = await started(ff);
  const page = await openBar(ff, x, v.id);
  const row = page.sent[0].items.find(i => i.id === "tab:there");
  await page.tell({ type: "choose", row: { kind: "tab", key: row.key, url: row.url } });
  await wait(1500);
  assert.equal(barWindows(ff).length, 0);
  assert.equal(ff.focused, v.id);
  const selected = ff.list(v.id).find(t => t.active);
  assert.equal(selected.url, "https://there.example/page", "the real tab is here now");
  assert.equal(selected.cookieStoreId, C2);
  assert.ok(!ff.tabs.has(ghost.id), "and its placeholder is gone");
  assert.equal(x.js("activeSpace").get(v.id), C2);
  x.kill();
});

test("choosing an essential selects this window's copy", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const page = await openBar(ff, x, w.id);
  const row = page.sent[0].items.find(i => i.id === "essential:e1");
  await page.tell({ type: "choose", row: { kind: "essential", key: row.key, url: row.url } });
  await wait(600);
  assert.ok(ff.list(w.id).find(t => t.active).pinned);
  assert.equal(x.js("activeSpace").get(w.id), C2);
  x.kill();
});

test("pages in no record can be found and gone to, but no empty new tab or placeholder without a record", async () => {
  const ff = new FakeFirefox();
  const { w, v } = world(ff);
  const settings = ff.addTab(w.id, { url: "about:preferences", title: "Settings" });
  ff.addTab(w.id, { url: "moz-extension://tidier/settings/settings.html", title: "Tidier settings" });
  ff.addTab(w.id, { url: "about:newtab", title: "New Tab" });
  const x = await started(ff);
  const page = await openBar(ff, x, v.id);
  const pages = page.sent[0].items.filter(i => String(i.id).startsWith("page:"));
  assert.deepEqual(Array.from(pages, i => i.title).sort(), ["Settings", "Tidier settings"]);
  assert.equal(pages.find(i => i.title === "Tidier settings").url, undefined, "an extension's address is nothing to search or show");
  // In a new tab there is no such thing: it goes to the page, also from another window.
  await page.tell({ type: "choose", inNewTab: true, row: { kind: "tab", tabId: settings.id, url: "about:preferences" } });
  await wait(300);
  assert.equal(ff.focused, w.id);
  assert.ok(ff.tabs.get(settings.id).active);
  assert.ok(!x.js("problems").length);
  x.kill();
});

test("a tab that has gone since the bar opened opens its address instead, in its own space", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const page = await openBar(ff, x, w.id);
  await page.tell({ type: "choose", row: { kind: "tab", key: "no-longer", url: "https://gone.example/", space: C2 } });
  await wait(300);
  const t = ff.list(w.id).find(t => t.url === "https://gone.example/");
  assert.equal(t?.cookieStoreId, C2, "the active space's container would be the wrong logins");
  x.kill();
});

test("if the window it was opened from has closed, another one is used", async () => {
  const ff = new FakeFirefox();
  const { w, v } = world(ff);
  const x = await started(ff);
  const page = await openBar(ff, x, v.id);
  await x.b.windows.remove(v.id);
  await wait(500);
  await page.tell({ type: "choose", row: { kind: "address", url: "https://still.example/" } });
  await wait(300);
  assert.equal(ff.list(w.id).filter(t => t.url === "https://still.example/").length, 1);
  assert.deepEqual(Array.from(x.errors), [], "and nothing goes wrong");
  x.kill();
});

test("an address and ⌘↵ open a new tab in the active space, in the place new tabs go", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  x.js("globalThis.topOfToday = async () => 2");
  let page = await openBar(ff, x, w.id);
  await page.tell({ type: "choose", row: { kind: "address", url: "https://typed.example/" } });
  await wait(300);
  const typed = ff.list(w.id).find(t => t.url === "https://typed.example/");
  assert.equal(typed.cookieStoreId, C1);
  assert.equal(typed.index, 2);
  page = await openBar(ff, x, w.id);
  await page.tell({ type: "choose", inNewTab: true, row: { kind: "tab", key: "there", url: "https://there.example/page" } });
  await wait(300);
  const copies = ff.list(w.id).filter(t => t.url === "https://there.example/page");
  assert.deepEqual(copies.map(t => t.cookieStoreId).sort(), [C1, C2].sort(), "a new one here, and the other left alone");
  x.kill();
});

test("a search opens a tab in the active space first, as Firefox's search cannot pick a container", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const searches = [];
  x.b.search = { search: async s => { searches.push(s); } };
  const page = await openBar(ff, x, w.id);
  await page.tell({ type: "choose", row: { kind: "search", query: "some words" } });
  await wait(300);
  assert.equal(searches.length, 1);
  assert.equal(searches[0].query, "some words");
  assert.equal(ff.tabs.get(searches[0].tabId).cookieStoreId, C1);
  assert.equal(ff.tabs.get(searches[0].tabId).windowId, w.id);
  x.kill();
});

test("the commands table: only what applies, each with a name and a label, the most used first", async () => {
  const ff = new FakeFirefox();
  ff.commands = [{ name: "copy-url", shortcut: "Ctrl+Shift+C" }, { name: "next-tab", shortcut: "Ctrl+MacCtrl+Down" }, { name: "toggle-essential", shortcut: "Ctrl+D" }];
  // What the dotfiles cleared in about:keyboard (keys-commands.js): ⌘⇧C's picker, not ⌘D's bookmark.
  ff.managedMore = { firefoxKeys: { key_inspectorMac: {} } };
  const { w } = world(ff);
  const x = await started(ff);
  let page = await openBar(ff, x, w.id);
  const commands = page.sent[0].items.filter(i => i.kind === "command");
  const names = commands.map(c => c.name);
  for (const name of ["new-tab", "new-folder", "go-to-space", "copy-url", "unload", "toggle-essential", "move-to-space", "close-tab", "settings"]) assert.ok(names.includes(name), name);
  assert.ok(!names.includes("reopen-closed"), "nothing closed yet");
  assert.ok(names.includes("clear-today"), "quiet.js clears");
  assert.ok(!names.includes("rename-folder"), "this tab is in no folder");
  assert.ok(commands.every(c => c.title && c.id), "every command has a label");
  assert.deepEqual(Array.from(commands.filter(c => c.name === "go-to-space"), c => c.value).sort(), ["firefox-container-2", "firefox-container-3"]);
  assert.equal(commands.find(c => c.name === "copy-url").shortcut, "⇧⌘C", "as a Mac writes it, the same as on the settings page");
  assert.equal(commands.find(c => c.name === "next-tab").shortcut, "⌃⌘↓");
  assert.equal(commands.find(c => c.name === "toggle-essential").shortcut, null, "a key Firefox still has is not shown as working");
  assert.equal(new Set(commands.map(c => c.id)).size, commands.length);
  assert.ok(!names.includes("move-to-folder"), "no folder in this space, and the tab in none: nothing to choose from");
  assert.deepEqual(Array.from(commands.find(c => c.name === "move-to-space").list, c => c.value).sort(), ["firefox-container-2", "firefox-container-3"]);
  assert.deepEqual(Array.from(commands.filter(c => c.careful), c => c.name).sort(), ["clear-today", "close-tab"]);
  assert.equal(commands[0].name, "new-tab", "with nothing used yet, in the table's order");
  // Used once, a later command comes first next time; what closes tabs never moves up.
  await page.tell({ type: "choose", row: { kind: "command", name: "settings" } }).catch(() => {});
  await wait(300);
  page = await openBar(ff, x, w.id);
  assert.equal(page.sent[0].items.filter(i => i.kind === "command")[0].name, "settings");
  x.js(`barUses.set({ "clear-today": 50, "close-tab": 40, settings: 1 })`);
  await page.tell({ type: "close", refocus: true });
  await wait(200);
  page = await openBar(ff, x, w.id);
  const after = page.sent[0].items.filter(i => i.kind === "command").map(c => c.name);
  assert.equal(after[0], "settings");
  assert.ok(after.indexOf("clear-today") > after.indexOf("new-tab"), String(after));
  x.kill();
});

test("commands that need a tab act on the real one, through what the sidebar uses", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  // New folder, with the name given in the bar.
  let page = await openBar(ff, x, w.id);
  await page.tell({ type: "choose", value: "From the bar", row: { kind: "command", name: "new-folder" } });
  await wait(300);
  const made = Object.entries(ff.synced).find(([, e]) => e.name === "From the bar");
  assert.equal(made?.[1].cookieStoreId, C1);
  // Move to folder.
  page = await openBar(ff, x, w.id);
  await page.tell({ type: "choose", value: made[0], row: { kind: "command", name: "move-to-folder" } });
  await wait(300);
  assert.equal(ff.synced.here.parentKey, made[0]);
  assert.ok(ff.synced.here.saved, "in a folder a tab is saved");
  // Then the folder can be renamed, from the tab in it.
  page = await openBar(ff, x, w.id);
  const rename = page.sent[0].items.find(i => i.name === "rename-folder");
  assert.equal(rename.ask.value, "From the bar");
  await page.tell({ type: "choose", value: "Renamed", row: { kind: "command", name: "rename-folder" } });
  await wait(300);
  assert.equal(ff.synced[made[0]].name, "Renamed");
  // And Go to space.
  page = await openBar(ff, x, w.id);
  await page.tell({ type: "choose", row: { kind: "command", name: "go-to-space", value: C2 } });
  await wait(500);
  assert.equal(x.js("activeSpace").get(w.id), C2);
  x.kill();
});

test("Enter pressed twice is one choice", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const page = await openBar(ff, x, w.id);
  const row = { kind: "address", url: "https://once.example/" };
  await Promise.all([page.tell({ type: "choose", row }), page.tell({ type: "choose", row })]);
  await wait(300);
  assert.equal(ff.list(w.id).filter(t => t.url === row.url).length, 1);
  x.kill();
});

test("a space switched to is the one that comes back after a restart", async () => {
  // Found by the bar: going to a tab in another space saved that space, and ⌃1 back then
  // saved nothing, so a restart came back showing the other space's tabs.
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const saved = new Map();
  x.b.sessions.setWindowValue = async (id, key, value) => { saved.set(id, value); };
  await x.js(`switchSpace(${w.id}, "${C2}")`);
  await wait(300);
  assert.equal(saved.get(w.id), C2);
  await x.js(`switchSpace(${w.id}, "${C1}")`);
  await wait(300);
  assert.equal(saved.get(w.id), C1);
  x.kill();
});

test("a closed folder chosen in the bar opens, in its space", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const page = await openBar(ff, x, w.id);
  const told = [];
  x.b.runtime.sendMessage = async msg => { told.push(msg); };
  await page.tell({ type: "choose", row: { kind: "folder", key: "folder" } });
  await wait(500);
  assert.equal(ff.synced.folder.collapsed, false);
  assert.equal(x.js("activeSpace").get(w.id), C2);
  assert.ok(told.some(m => m.type === "commandBarMark" && m.windowId === w.id && m.folder === "folder"), "and this window's sidebar marks it for a moment");
  x.kill();
});

test("an empty new tab is not offered to be unloaded", async () => {
  const ff = new FakeFirefox();
  const { w, a } = world(ff);
  const x = await started(ff);
  const blank = await ff.ext.b.tabs.create({ windowId: w.id, url: "about:newtab", active: true });
  await wait(300);
  let page = await openBar(ff, x, w.id);
  assert.ok(!page.sent[0].items.some(i => i.name === "unload"), "nothing in it to unload");
  await page.tell({ type: "close", refocus: true });
  await wait(100);
  await ff.ext.b.tabs.update(a.id, { active: true });
  await wait(300);
  page = await openBar(ff, x, w.id);
  assert.ok(page.sent[0].items.some(i => i.name === "unload"), "a page is");
  assert.ok(blank);
  x.kill();
});

test("the commands of shortcuts.js come along, without the numbered ones, and run outside the queue", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  // shortcuts.js's own table, with one action watched.
  x.js(`COMMANDS.find(c => c.name === "next-space").action = async id => { globalThis.ran = id; };`);
  const page = await openBar(ff, x, w.id);
  const names = page.sent[0].items.filter(i => i.kind === "command").map(c => c.name);
  assert.ok(names.includes("next-space"));
  assert.ok(!names.includes("tab-1") && !names.includes("space-1") && !names.includes("_execute_sidebar_action"));
  assert.ok(!names.includes("command-bar") && !names.includes("command-bar-t"), "the bar's own keys are no command in it");
  assert.equal(names.filter(n => n === "copy-url").length, 1);
  await page.tell({ type: "choose", row: { kind: "command", name: "next-space" } });
  await wait(100);
  assert.equal(x.js("globalThis.ran"), w.id);
  x.kill();
});

test("Clear and Rename are there once what they use is, and go to it", async () => {
  const ff = new FakeFirefox();
  const { w, a } = world(ff);
  const x = await started(ff);
  x.js(`globalThis.cleared = []; globalThis.renamed = [];
    var clearSpace = async (windowId, space) => { cleared.push([windowId, space]); };
    var renameTab = async (tabId, name) => { renamed.push([tabId, name]); };`);
  let page = await openBar(ff, x, w.id);
  let names = page.sent[0].items.filter(i => i.kind === "command").map(c => c.name);
  assert.ok(names.includes("clear-today"));
  assert.ok(!names.includes("rename-tab"), "an ordinary tab has no name to keep");
  await page.tell({ type: "choose", row: { kind: "command", name: "clear-today" } });
  await wait(200);
  assert.equal(JSON.stringify(x.js("cleared")), JSON.stringify([[w.id, C1]]));
  await ff.ext.b.tabs.update(a.id, { pinned: true });
  await wait(300);
  page = await openBar(ff, x, w.id);
  const rename = page.sent[0].items.find(i => i.name === "rename-tab");
  assert.ok(rename?.ask, "an essential has one");
  assert.equal(rename.ask.value, "Here", "the page's title while it has no name of its own");
  await page.tell({ type: "close", refocus: true });
  await wait(100);
  x.js("getList()").then(list => { list.find(e => e.url === "https://here.example/").name = "Called this"; });
  await wait(50);
  page = await openBar(ff, x, w.id);
  assert.equal(page.sent[0].items.find(i => i.name === "rename-tab").ask.value, "Called this", "what it is called, to change that");
  await page.tell({ type: "choose", value: "Short", row: { kind: "command", name: "rename-tab" } });
  await wait(200);
  assert.equal(JSON.stringify(x.js("renamed")), JSON.stringify([[a.id, "Short"]]));
  x.kill();
});

test("while the quiet line offers Undo, the bar does too, and it undoes that", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  let page = await openBar(ff, x, w.id);
  assert.ok(!page.sent[0].items.some(i => i.name === "undo"), "nothing to undo");
  await page.tell({ type: "close", refocus: true });
  x.js(`globalThis.undone = 0; say(${w.id}, "2 tabs closed", { undo: async () => { undone++; } })`);
  page = await openBar(ff, x, w.id);
  const undo = page.sent[0].items.find(i => i.name === "undo");
  assert.equal(undo?.title, "Undo: 2 tabs closed");
  await page.tell({ type: "choose", row: undo });
  await wait(200);
  assert.equal(x.js("undone"), 1);
  assert.equal(x.js("noteFor")(w.id), null, "and the line goes");
  x.kill();
});

test("what you selected in the sidebar is what the commands act on", async () => {
  const ff = new FakeFirefox();
  const { w, a } = world(ff);
  const x = await started(ff);
  const second = ff.list(w.id).find(t => t.url === "https://there.example/page");
  x.b.runtime.sendMessage = async msg => (msg.type === "commandBarSelection" && msg.windowId === w.id ? [a.id, second.id] : undefined);
  const page = await openBar(ff, x, w.id);
  const items = page.sent[0].items;
  assert.equal(items.find(i => i.name === "close-tab").title, "Close 2 tabs");
  assert.equal(items.find(i => i.name === "unload").title, "Unload 2 tabs");
  assert.ok(!items.some(i => i.name === "toggle-essential"), "what cannot act on them all is left out");
  await page.tell({ type: "choose", row: { kind: "command", name: "copy-url" } }).catch(() => {});
  x.kill();
});

test("a sidebar that does not answer does not hold up the bar", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  x.b.runtime.sendMessage = () => new Promise(() => {});
  const page = await openBar(ff, x, w.id);
  assert.equal(page.sent[0].items.find(i => i.name === "close-tab").title, "Close this tab");
  x.kill();
});

test("what archiving closed and what was closed can be found, and come back", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  ff.recentlyClosed = [ // after the start, or Tidier has already forgotten the placeholder
    { lastModified: 5, tab: { sessionId: "s1", url: "https://closed.example/", title: "Closed one", windowId: w.id } },
    { lastModified: 4, tab: { sessionId: "s2", url: GHOST("ghost", "x"), title: "A placeholder", windowId: w.id } },
  ];
  x.js(`globalThis.archivedTabs = async () => [{ url: "https://old.example/", title: "Archived one", icon: null, when: 3, space: "${C2}" },
    { url: "https://closed.example/", title: "Closed one", icon: null, when: 6, space: "${C2}" }];`); // also in Firefox's list
  let restored = null;
  x.b.sessions.restore = async id => { restored = id; };
  let page = await openBar(ff, x, w.id);
  const items = page.sent[0].items;
  assert.equal(items.filter(i => i.kind === "closed").length, 1, "never a placeholder");
  assert.equal(items.find(i => i.kind === "closed").title, "Closed one");
  assert.equal(items.filter(i => i.url === "https://closed.example/").length, 1, "a tab in both lists is shown once, as Firefox's");
  const archived = items.find(i => i.kind === "archived");
  assert.equal(archived.space, C2);
  const closed = items.find(i => i.kind === "closed");
  assert.equal(closed.space, C2, "Firefox's entry has no container: Tidier's list knows the space");
  assert.ok(items.some(i => i.name === "reopen-closed"));
  await page.tell({ type: "choose", row: { kind: "closed", sessionId: "s1", url: "https://closed.example/" } });
  await wait(200);
  assert.equal(restored, "s1");
  // Through Tidier's own list, which also takes it off the list.
  x.js(`globalThis.reopened = []; globalThis.reopenArchived = async (item, windowId) => { reopened.push([item.space, item.url, windowId]); };`);
  page = await openBar(ff, x, w.id);
  await page.tell({ type: "choose", row: { kind: "archived", url: archived.url, space: archived.space, archived: archived.archived } });
  await wait(200);
  assert.equal(JSON.stringify(x.js("reopened")), JSON.stringify([[C2, archived.url, w.id]]));
  x.kill();
});

test("the question about history and bookmarks is asked once", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  let page = await openBar(ff, x, w.id);
  assert.equal(page.sent[0].asked, false);
  await page.tell({ type: "asked" });
  await page.tell({ type: "close", refocus: true });
  await wait(100);
  page = await openBar(ff, x, w.id);
  assert.equal(page.sent[0].asked, true);
  x.kill();
});

test("with nothing happening, an open or a closed bar does nothing", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const page = await openBar(ff, x, w.id);
  await wait(3000); // what the focus moving causes is done by then
  const before = { ...x.js("work") };
  await wait(5000);
  assert.deepEqual({ ...x.js("work") }, before, "open");
  await page.tell({ type: "close", refocus: true });
  await wait(3000);
  const closed = { ...x.js("work") };
  await wait(5000);
  assert.deepEqual({ ...x.js("work") }, closed, "closed");
  x.kill();
});

// --- Found by trying to break it ------------------------------------------------------
test("a page that is not this key press's cannot pass for the bar while it opens", async () => {
  const ff = new FakeFirefox();
  const { w, a } = world(ff);
  const x = await started(ff);
  // The window takes its time, and meanwhile the page turns up in a tab of a normal window.
  const create = x.b.windows.create;
  let go;
  x.b.windows.create = props => new Promise(resolve => { go = () => resolve(create(props)); });
  x.b.commands.onCommand.fire("command-bar", ff.snap(a));
  await wait(200);
  const byHand = ff.addTab(w.id, { url: "moz-extension://tidier/commandbar/commandbar.html" });
  const stray = { name: "commandbar", sender: { id: "tidier", url: byHand.url, tab: ff.snap(byHand) }, postMessage() { assert.fail("it gets nothing"); }, onMessage: { addListener() {} }, onDisconnect: { addListener() {} } };
  for (const { f } of x.b.runtime.onConnect.ls) f(stray);
  await wait(100);
  assert.ok(!ff.tabs.has(byHand.id), "only that tab goes");
  go();
  await wait(200);
  const page = connectPage(ff, x);
  for (let i = 0; i < 100 && !page.sent.length; i++) await wait(100);
  assert.ok(page.sent.length, "the real one still gets its rows");
  await page.tell({ type: "close", refocus: true });
  await wait(100);
  assert.ok(ff.wins.has(w.id), "and closing the bar closes no normal window");
  assert.equal(barWindows(ff).length, 0);
  x.kill();
});

test("a stray bar closed by Tidier is not kept under Recently Closed Windows either", async () => {
  const ff = new FakeFirefox();
  world(ff);
  const x = await started(ff);
  const stray = ff.addWindow({ type: "popup" }); // what Firefox's session brought back
  const t = ff.addTab(stray.id, { url: "moz-extension://tidier/commandbar/commandbar.html#123", active: true });
  for (const { f } of x.b.runtime.onConnect.ls) f({ name: "commandbar", sender: { id: "tidier", url: t.url, tab: ff.snap(t) }, postMessage() {}, onMessage: { addListener() {} }, onDisconnect: { addListener() {} } });
  await wait(300);
  assert.ok(!ff.wins.has(stray.id));
  assert.ok(!(ff.recentlyClosed || []).some(c => c.window), "forgotten once Firefox lists it");
  x.kill();
});

test("the key pressed again before the rows are ready is no error", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  await pressKey(ff, x, w.id);
  const bar = barWindows(ff)[0], tab = ff.tabs.get(bar.order[0]);
  const gone = [];
  // As Firefox's port does once the page has gone.
  for (const { f } of x.b.runtime.onConnect.ls) {
    f({ name: "commandbar", sender: { id: "tidier", url: tab.url, tab: ff.snap(tab) }, postMessage() { throw new Error("Attempt to postMessage on disconnected port"); },
      onMessage: { addListener() {} }, onDisconnect: { addListener: l => gone.push(l) } });
  }
  await wait(300);
  assert.deepEqual([...x.js("problems")], []);
  gone.forEach(l => l());
  x.kill();
});

test("a space key with the bar open puts no tab in the bar's window", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const page = await openBar(ff, x, w.id);
  const tabs = ff.list(w.id).length;
  x.b.commands.onCommand.fire("space-2");
  await wait(300);
  assert.equal(ff.list(page.bar.id).length, 1, "a small window has no spaces");
  assert.equal(ff.list(w.id).length, tabs);
  assert.equal(x.js("activeSpace").get(w.id), C1);
  x.kill();
});

test("one other tab selected in the sidebar: what needs this tab is left out, and the rest acts on that tab", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const other = ff.list(w.id).find(t => t.url === "https://there.example/page");
  x.b.runtime.sendMessage = async msg => (msg.type === "commandBarSelection" ? [other.id] : undefined);
  const page = await openBar(ff, x, w.id);
  const names = page.sent[0].items.filter(i => i.kind === "command").map(c => c.name);
  assert.ok(!names.includes("toggle-essential"), "it would pin the tab you are on, not the one selected");
  assert.ok(names.includes("close-tab"));
  await page.tell({ type: "choose", row: { kind: "command", name: "close-tab" } });
  await wait(300);
  assert.ok(!ff.tabs.has(other.id));
  assert.ok(ff.list(w.id).some(t => t.url === "https://here.example/"), "the tab you are on stays");
  x.kill();
});

test("closing several goes through the selected tab last, and a page's question holds up nothing else", async () => {
  const ff = new FakeFirefox();
  const { w, a } = world(ff);
  const x = await started(ff);
  const other = ff.list(w.id).find(t => t.url === "https://there.example/page");
  x.b.runtime.sendMessage = async msg => (msg.type === "commandBarSelection" ? [a.id, other.id] : undefined);
  const remove = x.b.tabs.remove, removed = [];
  let answer;
  x.b.tabs.remove = id => { removed.push(id); return id === a.id ? new Promise(r => { answer = () => r(remove(id)); }) : remove(id); };
  const page = await openBar(ff, x, w.id);
  page.tell({ type: "choose", row: { kind: "command", name: "close-tab" } });
  await wait(300);
  assert.deepEqual(removed.filter(id => id === a.id || id === other.id), [other.id, a.id]); // (and the other window's copy, by tab sync)
  // The page is still asking whether you mean it: the queue goes on meanwhile.
  assert.equal(await Promise.race([x.js("serial(async () => 'free')"), new Promise(r => setTimeout(r, 200, "stuck"))]), "free");
  answer();
  await wait(200);
  assert.ok(!ff.tabs.has(a.id));
  x.kill();
});

test("moving several to a space keeps their order, as the tab menu does", async () => {
  const ff = new FakeFirefox();
  const { w, a } = world(ff);
  const x = await started(ff);
  const other = ff.list(w.id).find(t => t.url === "https://there.example/page");
  x.b.runtime.sendMessage = async msg => (msg.type === "commandBarSelection" ? [a.id, other.id] : undefined);
  const moved = [];
  x.js("globalThis.moved = []");
  const page = await openBar(ff, x, w.id);
  const create = x.b.tabs.create;
  x.b.tabs.create = p => { moved.push(p.url); return create(p); };
  await page.tell({ type: "choose", value: "firefox-container-3", row: { kind: "command", name: "move-to-space" } });
  await wait(300);
  const opened = moved.filter(u => /^https:/.test(u));
  assert.deepEqual(opened, ["https://here.example/", "https://there.example/page"]); // in order; the selected tab steps onto none of them (leaving, safemoves.js)
  x.kill();
});

test("a command with nothing to choose from is left out, and the folder a tab is in is not a choice", async () => {
  const ff = new FakeFirefox({ containers: ["firefox-default", "firefox-container-1"] });
  ff.managed = { ...ff.managedMore };
  ff.store.syncedTabs = {
    t: { url: "https://t.example/", title: "T", cookieStoreId: C1, parentKey: "f1", added: 1 },
    f1: { group: true, own: true, name: "One", cookieStoreId: C1, parentKey: null, rank: 1, added: 1 },
    f2: { group: true, own: true, name: "Two", cookieStoreId: C1, parentKey: null, rank: 2, added: 1 },
    live: { group: true, own: true, name: "Pull requests", live: { search: "x" }, cookieStoreId: C1, parentKey: null, rank: 3, added: 1 },
  };
  const w = ff.addWindow({ focused: true });
  ff.addTab(w.id, { url: "https://t.example/", title: "T", active: true, cookieStoreId: C1 }, { syncKey: "t", syncRole: "live" });
  const x = await started(ff);
  const page = await openBar(ff, x, w.id);
  const commands = page.sent[0].items.filter(i => i.kind === "command");
  assert.ok(!commands.some(c => c.name === "move-to-space"), "one space: nowhere to go");
  assert.deepEqual(Array.from(commands.find(c => c.name === "move-to-folder").list, c => c.title), ["No folder", "Two"]);
  x.kill();
});

test("a page with no address is not offered a move to another space", async () => {
  const ff = new FakeFirefox();
  const { w, a } = world(ff);
  const settings = ff.addTab(w.id, { url: "about:preferences", title: "Settings", active: true });
  ff.tabs.get(a.id).active = false;
  const x = await started(ff);
  const page = await openBar(ff, x, w.id);
  assert.ok(!page.sent[0].items.some(i => i.name === "move-to-space"), `${settings.id}: it could only do nothing`);
  x.kill();
});

test("an essential closed a moment ago does not empty the bar", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const copy = ff.list(w.id).find(t => t.pinned);
  x.js("keyByTab").delete(copy.id);
  const read = x.b.sessions.getTabValue;
  x.b.sessions.getTabValue = (id, name) => (id === copy.id ? Promise.reject(new Error(`Invalid tab ID: ${id}`)) : read(id, name));
  const page = await openBar(ff, x, w.id);
  assert.ok(page.sent[0].items.some(i => i.id === "tab:there"));
  assert.deepEqual([...x.js("problems")], []);
  x.kill();
});

test("a list that fails does not empty the bar", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  x.js("globalThis.archivedTabs = async () => { throw new Error('no list today'); }");
  const page = await openBar(ff, x, w.id);
  assert.ok(page.sent[0].items.some(i => i.id === "tab:there"));
  x.kill();
});

test("a tab reopened in another window takes you there", async () => {
  const ff = new FakeFirefox();
  const { w, v } = world(ff);
  const x = await started(ff);
  x.b.sessions.restore = async () => ({ tab: { id: 1, windowId: w.id } });
  const page = await openBar(ff, x, v.id);
  await page.tell({ type: "choose", row: { kind: "closed", sessionId: "s", url: "https://closed.example/" } });
  await wait(100);
  assert.equal(ff.focused, w.id);
  x.kill();
});

test("a closed tab Firefox can no longer bring back opens in its own space", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  x.b.sessions.restore = async () => { throw new Error("no such session"); };
  const page = await openBar(ff, x, w.id);
  await page.tell({ type: "choose", row: { kind: "closed", sessionId: "s", url: "https://closed.example/", space: C2 } });
  await wait(100);
  assert.equal(ff.list(w.id).find(t => t.url === "https://closed.example/")?.cookieStoreId, C2);
  x.kill();
});

test("making a tab Tidier has just moved an essential is not missed", async () => {
  const ff = new FakeFirefox();
  const { w, a } = world(ff);
  const x = await started(ff);
  x.js(`syncBusy.add(${a.id})`); // for a moment after a move or a pull
  const page = await openBar(ff, x, w.id);
  await page.tell({ type: "choose", row: { kind: "command", name: "toggle-essential" } });
  await wait(1500);
  assert.equal(ff.synced.here, undefined, "it has left tab sync");
  assert.ok(ff.store.essentials.some(e => e.url === "https://here.example/"), "and is an essential");
  x.kill();
});

// The sidebar's side, with the selection package's own rule for selectedTabs.
function sidebarLink({ selection, picked = [], heads = [] }) {
  const messages = [];
  const sandbox = {
    browser: { windows: { getCurrent: async () => ({ id: 7 }) }, runtime: { onMessage: { addListener: f => messages.push(f) } } },
    document: {
      querySelector: selector => (selector === ".picked[data-tab]" && picked.length ? { dataset: { tab: String(picked[0]) } } : null),
      querySelectorAll: selector => (selector === "[data-folder-head]" ? heads : []),
    },
    window: selection ? { selectedTabs: id => (picked.includes(Number(id)) ? picked : [id]) } : {},
    Promise, Date, setTimeout,
  };
  vm.runInNewContext(readFileSync(new URL("../sidebar/commandbar-link.js", import.meta.url), "utf8"), sandbox);
  return msg => { for (const f of messages) { const r = f(msg); if (r !== undefined) return r; } };
}

test("a folder chosen in the bar is scrolled to and marked a moment, in its own window only", async () => {
  const head = key => { const classes = new Set(); return { dataset: { folderHead: key }, scrolled: 0, classList: { add: c => classes.add(c), remove: c => classes.delete(c) }, classes, scrollIntoView() { this.scrolled++; } }; };
  const heads = [head("a"), head("b")];
  const link = sidebarLink({ heads });
  await new Promise(r => setTimeout(r, 5));
  link({ type: "commandBarMark", windowId: 8, folder: "b" });
  link({ type: "commandBarMark", windowId: 7, folder: "b" });
  assert.deepEqual([heads[0].scrolled, heads[1].scrolled], [0, 1]);
  assert.ok(heads[1].classes.has("marked"));
  await new Promise(r => setTimeout(r, 1300));
  assert.ok(!heads[1].classes.has("marked"), "only for a moment");
});

test("the sidebar answers with the selection, also when the tab you are on is not in it", async () => {
  await new Promise(r => setTimeout(r, 5));
  const ask = async link => { await new Promise(r => setTimeout(r, 5)); return link({ type: "commandBarSelection", windowId: 7, tabId: 1 }); };
  assert.deepEqual([...await ask(sidebarLink({ selection: true, picked: [2, 3] }))], [2, 3], "you are on an essential and selected two rows");
  assert.deepEqual([...await ask(sidebarLink({ selection: true, picked: [1, 2] }))], [1, 2]);
  assert.deepEqual([...await ask(sidebarLink({ selection: true }))], [1], "nothing selected: this tab");
  const link = sidebarLink({ selection: true, picked: [2] });
  await new Promise(r => setTimeout(r, 5));
  assert.equal(link({ type: "commandBarSelection", windowId: 8, tabId: 1 }), undefined, "another window's question");
});

test("closing a selected placeholder closes what the tab menu's rule says, where that is there", async () => {
  // A saved tab closed unloaded is removed for good; with its page loaded in another window
  // closing the page itself only unloads it (closeTargetOf, tabactions.js).
  const ff = new FakeFirefox();
  const { w, v } = world(ff);
  const x = await started(ff);
  const placeholder = ff.list(v.id).find(t => t.url === GHOST("ghost", "there")), page_ = ff.list(w.id).find(t => t.url === "https://there.example/page");
  x.js(`globalThis.closeTargetOf = async id => (id === ${placeholder.id} ? ${page_.id} : id)`);
  x.b.runtime.sendMessage = async msg => (msg.type === "commandBarSelection" && msg.windowId === v.id ? [placeholder.id] : undefined);
  const removed = [], remove = x.b.tabs.remove;
  x.b.tabs.remove = id => { removed.push(id); return remove(id); };
  const page = await openBar(ff, x, v.id);
  await page.tell({ type: "choose", row: { kind: "command", name: "close-tab" } });
  await wait(100);
  assert.equal(removed[0], page_.id);
  x.kill();
});

test("taking an essential away from a copy Tidier has just made is not missed", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const copy = ff.list(w.id).find(t => t.pinned);
  ff.tabs.get(copy.id).active = true;
  ff.tabs.get(ff.list(w.id).find(t => t.url === "https://here.example/").id).active = false;
  const x = await started(ff);
  x.js(`busy.add(${copy.id})`);
  const page = await openBar(ff, x, w.id);
  assert.equal(page.sent[0].items.find(i => i.name === "toggle-essential").title, "Remove from essentials");
  await page.tell({ type: "choose", row: { kind: "command", name: "toggle-essential" } });
  await wait(1500);
  assert.ok(!ff.store.essentials.length, "it is no essential any more");
  x.kill();
});

test("Reopen closed tab brings back the last one that was a page", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  ff.recentlyClosed = [
    { lastModified: 9, tab: { sessionId: "placeholder", url: GHOST("ghost", "x"), title: "A placeholder", windowId: w.id } },
    { lastModified: 8, tab: { sessionId: "page", url: "https://closed.example/", title: "A page", windowId: w.id } },
    { lastModified: 7, tab: { sessionId: "older", url: "https://older.example/", title: "Older", windowId: w.id } },
  ];
  let restored = null;
  x.b.sessions.restore = async id => { restored = id; };
  const page = await openBar(ff, x, w.id);
  await page.tell({ type: "choose", row: { kind: "command", name: "reopen-closed" } });
  await wait(100);
  assert.equal(restored, "page");
  x.kill();
});

// --- In the window itself: the bar as the toolbar button's popup ------------------------
// A Firefox that opens the popup (the fake has no openPopup unless a test gives it one, so
// everything above is the bar as a window of its own, which is what Tidier falls back to).
function withPanel(x) {
  const panel = { popups: [], opened: [], refuse: null };
  x.b.browserAction.setPopup = async ({ popup }) => { panel.popups.push(popup); };
  x.b.browserAction.openPopup = async ({ windowId }) => { if (panel.refuse) throw new Error(panel.refuse); panel.opened.push(windowId); };
  return panel;
}
// Its page: in no tab, so the background knows it only by its address.
function connectPanel(x, url) {
  const listeners = [], gone = [], sent = [];
  let cut = false;
  const port = {
    name: "commandbar", sender: { id: "tidier", url }, postMessage: m => sent.push(m), disconnect: () => { cut = true; },
    onMessage: { addListener: f => listeners.push(f) }, onDisconnect: { addListener: f => gone.push(f) },
  };
  for (const { f } of x.b.runtime.onConnect.ls) f(port);
  return { port, sent, tell: async m => { for (const f of listeners) await f(m); }, close: () => gone.forEach(f => f()), wasCut: () => cut };
}

test("the bar opens in the window you are in, as wide as the floating address bar, and the button keeps its click", async () => {
  const ff = new FakeFirefox();
  const { w, v } = world(ff);
  const x = await started(ff);
  const panel = withPanel(x);
  await pressKey(ff, x, v.id);
  assert.deepEqual(panel.opened, [v.id], "in the window the key was pressed in, not the first one");
  assert.equal(barWindows(ff).length, 0, "no window of its own");
  assert.equal(panel.popups.length, 2);
  assert.equal(panel.popups[1], null, "the button's click still shows and hides the sidebar");
  const given = new URLSearchParams(panel.popups[0].split("?")[1].split("#")[0]);
  assert.equal(given.get("panel"), "760", "min(760px, 70vw) of a window 1200 wide");
  assert.equal(given.get("space"), C1);
  const page = connectPanel(x, panel.popups[0]);
  for (let i = 0; i < 100 && !page.sent.length; i++) await wait(100);
  assert.ok(page.sent[0].items.length > 0, "its rows");
  // A narrow window: seven tenths of it, and never narrower than the bar can be.
  page.close();
  ff.wins.get(w.id).width = 800;
  await pressKey(ff, x, w.id);
  assert.equal(new URLSearchParams(panel.popups.at(-2).split("?")[1].split("#")[0]).get("panel"), "560");
  x.kill();
});

test("in the window, the key again closes it by its page, and then opens a new one at the first press", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const panel = withPanel(x);
  await pressKey(ff, x, w.id);
  const page = connectPanel(x, panel.popups[0]);
  await wait(100);
  await pressKey(ff, x, w.id);
  assert.equal(page.sent.at(-1)?.type, "close", "only its page can close a panel");
  assert.equal(panel.opened.length, 1, "and no second one opened");
  page.close(); // the page has gone
  await pressKey(ff, x, w.id);
  assert.equal(panel.opened.length, 2);
  // Closed by Firefox (a click beside it): heard from the page going, with nothing told to it.
  const second = connectPanel(x, panel.popups.at(-2));
  await wait(50);
  second.close();
  await pressKey(ff, x, w.id);
  assert.equal(panel.opened.length, 3, "the key opens it, and does not close a bar that is no longer there");
  x.kill();
});

test("in the window, the key pressed again before the page is there closes it as soon as it is", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const panel = withPanel(x);
  const fire = () => x.b.commands.onCommand.fire("command-bar", ff.snap(ff.tabs.get(w.order[0])));
  fire(); fire();
  await wait(300);
  assert.equal(panel.opened.length, 1);
  const page = connectPanel(x, panel.popups[0]);
  await wait(50);
  assert.deepEqual(page.sent.map(m => m.type), ["close"], "told to go, and given nothing to show");
  page.close();
  fire();
  await wait(300);
  assert.equal(panel.opened.length, 2, "the next press opens it");
  x.kill();
});

test("in the window, what you choose is carried out once the bar has gone", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const panel = withPanel(x);
  await pressKey(ff, x, w.id);
  const page = connectPanel(x, panel.popups[0]);
  for (let i = 0; i < 100 && !page.sent.length; i++) await wait(100);
  const before = ff.list(w.id).length;
  const done = page.tell({ type: "choose", row: { kind: "command", name: "new-tab" } });
  await wait(50);
  assert.equal(page.sent.at(-1)?.type, "close");
  assert.equal(ff.list(w.id).length, before, "not under an open panel: the tab would not get the keyboard");
  page.close();
  await done;
  await wait(100);
  assert.equal(ff.list(w.id).length, before + 1);
  assert.equal(ff.focused, w.id);
  // A page that never says it has gone does not hold what you chose for long.
  await pressKey(ff, x, w.id);
  const stuck = connectPanel(x, panel.popups.at(-2));
  for (let i = 0; i < 100 && !stuck.sent.length; i++) await wait(100);
  await stuck.tell({ type: "choose", row: { kind: "command", name: "new-tab" } });
  await wait(100);
  assert.equal(ff.list(w.id).length, before + 2);
  x.kill();
});

test("in the window, Tidier's other keys do nothing while the bar has the keyboard, and the bar goes when its tab is no longer in front", async () => {
  const ff = new FakeFirefox();
  const { w, a } = world(ff);
  const x = await started(ff);
  const panel = withPanel(x);
  await pressKey(ff, x, w.id);
  const page = connectPanel(x, panel.popups[0]);
  for (let i = 0; i < 100 && !page.sent.length; i++) await wait(100);
  const copied = [];
  x.ctx.navigator.clipboard = { writeText: async t => { copied.push(t); } };
  x.b.commands.onCommand.fire("copy-url", ff.snap(a));
  x.b.commands.onCommand.fire("next-space", ff.snap(a));
  await wait(300);
  assert.deepEqual(copied, [], "the window's keys reach Tidier from a panel");
  assert.equal(x.js("activeSpace").get(w.id), C1);
  // ⌘W is Firefox's own, and closes the tab you are on also from a panel: another comes to the front.
  const other = ff.list(w.id).find(t => t.id !== a.id && !t.pinned);
  ff.select(other.id);
  await wait(100);
  assert.equal(page.sent.at(-1)?.type, "close");
  page.close();
  x.b.commands.onCommand.fire("copy-url", ff.snap(ff.tabs.get(other.id)));
  await wait(300);
  assert.equal(copied.length, 1, "and the keys are Tidier's again");
  x.kill();
});

test("a Firefox that will not open the panel gets the bar as a window of its own, and a page of an earlier press is sent away", async () => {
  const ff = new FakeFirefox();
  const { w } = world(ff);
  const x = await started(ff);
  const panel = withPanel(x);
  panel.refuse = "openPopup() cannot be called while another panel is open";
  await pressKey(ff, x, w.id);
  assert.equal(barWindows(ff).length, 1);
  assert.equal(panel.popups.at(-1), null, "the button is not left with a popup");
  assert.ok(!ff.tabs.get(barWindows(ff)[0].order[0]).url.includes("panel="), "the page fills its window");
  await pressKey(ff, x, w.id);
  assert.equal(barWindows(ff).length, 0);
  // The button's popup shown some other way, with the address of a press long gone.
  panel.refuse = null;
  const stray = connectPanel(x, "commandbar/commandbar.html?panel=760#1");
  await wait(50);
  assert.equal(stray.wasCut(), true, "its page closes it when it hears that");
  assert.equal(stray.sent.length, 0);
  x.kill();
});
