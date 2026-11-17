// Live folders (livefolders.js) of issues and of a feed's entries: Tidier's real background
// scripts on the fake Firefox, with a stand-in for the helper's answers. What a folder of
// pull requests does is in foldrest.test.mjs and the smoke test (live_folders); the helper
// itself (the search it asks GitHub for, reading a feed) is in tests/test_helper.py, which
// this runs too.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { FakeFirefox, wait } from "./fake_firefox.mjs";

const C1 = "firefox-container-1";
const entry = (url, more = {}) => ({ url, title: url, cookieStoreId: C1, parentKey: null, group: false, added: 1, ...more });
const FOLDER = { id: "follow", name: "Followed", cookieStoreId: C1 };

// One window with the tab you are on, and a live folder with nothing in it yet.
async function start() {
  const ff = new FakeFirefox();
  ff.store.syncedTabs = {
    L: { group: true, own: true, name: "Followed", url: null, cookieStoreId: C1, parentKey: null, rank: 1, added: 1, live: "follow" },
    here: entry("https://here.example/"),
  };
  ff.store.liveFolders = { follow: { groupKey: "L", dismissed: [] } };
  const w = ff.addWindow({ focused: true });
  ff.addTab(w.id, { url: "https://here.example/", cookieStoreId: C1, active: true }, { syncKey: "here", syncRole: "live" });
  const x = ff.boot();
  x.b.runtime.onStartup.fire();
  await wait(1200);
  for (let i = 0; i < 300 && !x.started(); i++) await wait(1000);
  await wait(1000);
  const search = async answer => { await x.js("serial")(() => x.js("refreshLiveFolder")(FOLDER, answer)); await wait(500); };
  const rows = async () => Array.from((await x.js("viewFor")(w.id)).folders[0].tabs, t => [t.title, t.pr]);
  const records = () => Object.values(ff.store.syncedTabs).filter(e => e.liveFolder === "follow");
  return { ff, x, w, search, rows, records };
}

test("a folder of your repositories: a row each, named with how many wait for your review, which its icon says too", async () => {
  const { x, search, rows } = await start();
  const repo = (name, waiting) => ({ url: `https://github.com/${name}/pulls`, title: name, repo: name, waiting, recent: 3, what: "repo" });
  await search({ items: [repo("acme/app", 2), repo("acme/site", 0)] });
  assert.deepEqual(await rows(), [["acme/app · 2 to review", "review"], ["acme/site", "repo"]]);
  await search({ items: [repo("acme/app", 0), repo("acme/site", 1)] });
  assert.deepEqual(await rows(), [["acme/app", "repo"], ["acme/site · 1 to review", "review"]], "the counts follow, while the tabs are not opened");
  assert.equal(x.js("liveFolderFrom")({ id: "r1", name: "Repos", space: C1, what: "repos", search: "org:acme" })?.what, "repos");
  assert.deepEqual({ ...x.js("liveAsk")({ what: "repos", search: "org:acme" }) }, { search: "org:acme", what: "repos" });
  assert.deepEqual(x.errors, []);
  x.kill();
});

test("an issue is named as a pull request is, and its row says it is an issue", async () => {
  const { x, search, rows, records } = await start();
  const issue = { url: "https://github.com/acme/app/issues/3", repo: "app", number: 3, title: "Three", what: "issue" };
  await search({ items: [issue, { url: "https://github.com/acme/app/pull/7", repo: "app", number: 7, title: "Seven", draft: true }] });
  assert.deepEqual(await rows(), [["app#3 Three", "issue"], ["app#7 Seven", "draft"]]);
  assert.ok(records().every(e => e.icon?.includes("github")), "GitHub's own mark until the page has its own");
  // Whatever else an answer says of it, an issue waits for nothing.
  assert.equal(x.js("liveState")({ ...issue, draft: true, checks: "failing", mine: true }), "issue");
  await search({ items: [] });
  assert.deepEqual(await rows(), [], "closed on GitHub, it leaves the folder");
  assert.deepEqual(x.errors, []);
  x.kill();
});

test("a feed's entries have their own titles, their own sites, and a quiet mark", async () => {
  const { ff, x, w, search, rows, records } = await start();
  const item = n => ({ url: `https://news.example/${n}`, title: `Story ${n}`, what: "feed" });
  await search({ items: [item(1), item(2)] });
  assert.deepEqual(await rows(), [["Story 1", "feed"], ["Story 2", "feed"]]);
  assert.deepEqual(records().map(e => [e.url, e.icon, e.liveUrl]), [1, 2].map(n => [`https://news.example/${n}`, undefined, `https://news.example/${n}`]),
    "no icon of GitHub's: the page brings its own");
  assert.ok(ff.list(w.id).filter(t => t.url.includes("kind=lazy")).every(t => t.discarded), "each a placeholder, unloaded");

  // One you closed stays closed while the feed still has it; one the feed has let go leaves.
  const first = ff.list(w.id).find(t => t.title === "Story 1");
  await x.b.tabs.remove(first.id);
  await wait(1500);
  await search({ items: [item(3), item(1), item(2)] });
  assert.deepEqual((await rows()).map(r => r[0]).sort(), ["Story 2", "Story 3"]);
  await search({ items: [item(4), item(3)] });
  assert.deepEqual((await rows()).map(r => r[0]).sort(), ["Story 3", "Story 4"]);
  assert.deepEqual(x.errors, []);
  x.kill();
});

test("only a web address gets a tab, whatever the helper lets through", async () => {
  const { ff, x, w, search, rows } = await start();
  const before = ff.list(w.id).length;
  await search({ items: [
    { url: "javascript:alert(1)", title: "Script", what: "feed" }, { url: "file:///etc/passwd", title: "File", what: "feed" },
    { url: "moz-extension://tidier/settings/settings.html", title: "Tidier's own", what: "feed" }, { title: "No address", what: "feed" }, null,
    { url: "https://news.example/ok", title: "A story", what: "feed" },
  ] });
  assert.deepEqual(await rows(), [["A story", "feed"]]);
  assert.equal(ff.list(w.id).length, before + 1);
  x.kill();
});

test("a feed that does not answer leaves the folder as it is, and says which it was", async () => {
  const { x, search, rows } = await start();
  await search({ items: [{ url: "https://news.example/1", title: "Story 1", what: "feed" }] });
  const words = error => x.js("liveTrouble")(error);
  assert.equal(words("feed: <urlopen error [Errno 8] nodename nor servname provided, or not known>"), "its feed did not answer");
  assert.equal(words("feed: HTTP Error 404: Not Found"), "its feed did not answer");
  assert.equal(words("feed: not a feed (syntax error: line 1, column 0)"), "what its address answers with is not a feed");
  assert.equal(words("feed: not a feed (it is <html>)"), "what its address answers with is not a feed");
  await search({ error: "feed: HTTP Error 503: Service Unavailable" });
  assert.deepEqual(await rows(), [["Story 1", "feed"]]);
  assert.deepEqual([...x.js("notices").values()], ['Live folder "Followed" is not updating: its feed did not answer']);
  x.kill();
});

// --- Folders set up on the settings page ------------------------------------------------------
const SETTINGS = { url: "moz-extension://tidier/settings/settings.html" };
const plain = value => JSON.parse(JSON.stringify(value));
// A machine with a helper that answers what it is asked as `answers` says: by the search's
// words or the feed's address. `helper: false`: none installed.
async function own({ helper = true, answers = {} } = {}) {
  const ff = new FakeFirefox();
  ff.store.syncedTabs = { here: entry("https://here.example/") };
  const w = ff.addWindow({ focused: true });
  ff.addTab(w.id, { url: "https://here.example/", cookieStoreId: C1, active: true }, { syncKey: "here", syncRole: "live" });
  const asked = [];
  ff.adapt = b => {
    b.runtime.sendNativeMessage = async (host, msg) => {
      if (!helper) throw new Error("No such native application tidier_github");
      asked.push(plain(msg));
      if (msg.list) return { folders: [] };
      if (msg.ask) return answers[msg.ask.feed ?? msg.ask.search] ?? { error: "not a search or a feed this helper answers" };
      return { error: "unknown folder" };
    };
  };
  const x = ff.boot();
  x.b.runtime.onStartup.fire();
  await wait(1200);
  for (let i = 0; i < 300 && !x.started(); i++) await wait(1000);
  await wait(1000);
  const set = async folders => { const r = plain(await x.send({ type: "live:set", folders }, SETTINGS)); await wait(1500); return r; };
  const view = async () => plain(await x.js("viewFor")(w.id)).folders.map(f => [f.name, !!f.live, f.tabs.map(t => t.title)]);
  return { ff, x, w, asked, set, view, answers };
}
const pr = n => ({ url: `https://github.com/acme/app/pull/${n}`, repo: "app", number: n, title: `Pull ${n}` });

test("a live folder set up on the settings page is asked for by its search, and filled", async () => {
  const { x, asked, set, view } = await own({ answers: { "org:acme": { items: [pr(1), pr(2)] }, "https://news.example/feed.xml": { items: [{ url: "https://news.example/1", title: "Story 1", what: "feed" }] } } });
  const r = await set([{ id: "a1", name: "Reviews", space: C1, what: "prs", search: "  org:acme " },
    { id: "a2", name: "News", space: C1, what: "feed", feed: "https://news.example/feed.xml" }]);
  assert.deepEqual(r.folders.map(f => [f.id, f.search ?? f.feed]), [["a1", "org:acme"], ["a2", "https://news.example/feed.xml"]]);
  assert.equal(r.helper, true);
  assert.deepEqual(asked.filter(m => m.ask).map(m => m.ask), [{ search: "org:acme", what: "prs" }, { feed: "https://news.example/feed.xml" }], "what narrows, and what it is; no id, name or space");
  assert.deepEqual(await view(), [["Reviews", true, ["app#1 Pull 1", "app#2 Pull 2"]], ["News", true, ["Story 1"]]]);
  assert.deepEqual(x.errors, []);
  x.kill();
});

test("only what can be a folder is kept: a name, a space, and a search of words that narrow or a feed on the web", async () => {
  const { x, set } = await own();
  const ok = { id: "ok", name: "All mine", space: C1, what: "issues", search: "" };
  const r = await set([ok,
    { id: "b1", name: "Wide", space: C1, what: "prs", search: "org:acme OR is:pr" },
    { id: "b2", name: "Brackets", space: C1, what: "prs", search: ") OR (author:someone" },
    { id: "b3", name: "Words", space: C1, what: "prs", search: "secret plans" },
    { id: "b4", name: "A file", space: C1, what: "feed", feed: "file:///etc/passwd" },
    { id: "b5", name: "", space: C1, what: "prs", search: "org:acme" },
    { id: "b6", name: "No space", space: "firefox-default", what: "prs", search: "org:acme" },
    { id: "b7", name: "No kind", space: C1, what: "everything", search: "org:acme" },
    { id: "ok", name: "Twice", space: C1, what: "prs", search: "org:acme" },
    "not a folder", null]);
  assert.deepEqual(r.folders, [ok], "a search of no words is everything open that is yours");
  assert.equal(x.send({ type: "live:set", folders: [] }, { url: "https://elsewhere.example/" }), undefined, "from Tidier's own pages only");
  x.kill();
});

test("renamed, its folder is renamed; removed, or moved to another space, its folder goes with its tabs", async () => {
  const { ff, set, view } = await own({ answers: { "org:acme": { items: [pr(1)] } } });
  const f = { id: "a1", name: "Reviews", space: C1, what: "prs", search: "org:acme" };
  await set([f]);
  assert.deepEqual(await view(), [["Reviews", true, ["app#1 Pull 1"]]]);
  await set([{ ...f, name: "To review" }]);
  assert.deepEqual(await view(), [["To review", true, ["app#1 Pull 1"]]], "the same folder, by another name");
  await set([]);
  assert.deepEqual(await view(), []);
  assert.deepEqual(Object.values(ff.store.syncedTabs).filter(e => e.liveFolder || e.live), [], "nothing of it is left in the record");
  assert.deepEqual(ff.store.liveFolders ?? {}, {});
  x_kill(ff);
});
const x_kill = ff => ff.ext.kill();

test("on a machine with no helper a folder that came from another machine is simply not there, and nothing is said", async () => {
  const { x, set, view } = await own({ helper: false });
  const r = await set([{ id: "a1", name: "Reviews", space: C1, what: "prs", search: "org:acme" }]);
  assert.equal(r.helper, false, "the settings page says that nothing fills them here");
  assert.equal(r.folders.length, 1, "kept, for the machines that have one");
  assert.deepEqual(await view(), []);
  assert.deepEqual(plain(await x.send({ type: "settings:get" }, SETTINGS)).notices.filter(n => n.kind === "live"), []);
  x.kill();
});

test("a helper from before this says so, in words that tell what to do", async () => {
  const { x, set } = await own({ answers: { "org:acme": { error: "unknown folder" } } });
  await set([{ id: "a1", name: "Reviews", space: C1, what: "prs", search: "org:acme" }]);
  const notice = plain(await x.send({ type: "settings:get" }, SETTINGS)).notices.find(n => n.kind === "live");
  assert.match(notice?.text ?? "", /Live folder "Reviews" is not updating: its helper is older than Tidier \(git pull where it is installed\)/);
  x.kill();
});

test("the helper (tests/test_helper.py)", () => {
  const run = spawnSync("python3", ["-I", fileURLToPath(new URL("./test_helper.py", import.meta.url))], { encoding: "utf8", timeout: 120000, env: { ...process.env, PYTHONWARNINGS: "ignore" } });
  if (run.error?.code === "ENOENT") return; // no python3 here: the helper is for a Mac, which has one
  assert.equal(run.status, 0, run.stderr);
});
