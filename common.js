// Shared helpers for essentials.js and tabsync.js.

// All changes run one after another, so two events never race each other
// into duplicate tabs. Both features share this one queue.
//
// One job that never ends would stop everything after it, until Firefox restarts
// (a tab Firefox never finishes creating, say), so a job has a time limit. It is
// far above any real job: past it the next job can overlap with this one.
const JOB_LIMIT_MS = 5 * 60000;
let queue = Promise.resolve();
function serial(fn) {
  const run = queue.then(async () => {
    const t0 = performance.now();
    work.jobs++;
    let limit;
    try {
      return await Promise.race([fn(), new Promise((_, reject) => {
        limit = setTimeout(() => reject(new Error("a job did not finish within the time limit")), JOB_LIMIT_MS);
      })]);
    } finally {
      clearTimeout(limit);
      const ms = performance.now() - t0;
      work.queueMs += ms;
      work.longestJobMs = Math.max(work.longestJobMs, ms);
    }
  });
  queue = run.catch(err => noteError(err, fn));
  return run;
}

// Errors inside Tidier. Firefox only shows them in a console nobody looks at,
// so they are also kept for the smoke test ("stats" in tabsync.js), which fails
// on any: an error there is a tab that was not handled.
const problems = [];
function noteError(err, job) {
  console.error("Tidier:", err);
  work.errors++;
  // Where it happened, shortly: a message alone does not say which of many calls it was.
  // Firefox's own refusals have no stack, so the job they stopped says it instead.
  const where = String(err?.stack ?? "").split("\n").filter(Boolean).slice(0, 3).map(f => f.replace(/@.*\//, " ").replace(/:\d+$/, "")).join(" < ")
    || String(job ?? "").replace(/\s+/g, " ").slice(0, 80);
  problems.push(String(err?.message ?? err) + (where ? ` (${where})` : ""));
  if (problems.length > 20) problems.shift();
}
globalThis.addEventListener?.("unhandledrejection", event => noteError(event.reason));

// How much Tidier does, for the smoke test (the "stats" message, tabsync.js):
// jobs run in the queue and how long they held it, tab lookups made outside it (noteOrder, tabsync.js), the timed
// checks (archiving, live folders), the only work with nothing happening, and
// the sidebar's views: how many were built and how long that took.
const work = { jobs: 0, queueMs: 0, longestJobMs: 0, lookups: 0, alarms: 0, errors: 0, views: 0, viewMs: 0, longestViewMs: 0 };
browser.alarms.onAlarm.addListener(() => { work.alarms++; });

// Tidier once ran beside Sidebery, with its own sidebar, spaces and folders behind a
// setting, `tidierAlone`. Every browser is Tidier alone now: a browser that had the setting
// keeps it in its storage (or a machine in managed storage), and nothing reads it. One that
// never moved over is moved at its first start (moveover.js).

// Something you should know and would otherwise not see, such as a live folder that
// has stopped: shown on Tidier's button (in the Extensions menu) and in its sidebar.
const notices = new Map(); // kind -> text
function setNotice(kind, text) {
  if ((notices.get(kind) ?? null) === (text ?? null)) return;
  if (text) notices.set(kind, text); else notices.delete(kind);
  const first = [...notices.values()][0];
  browser.browserAction.setBadgeText({ text: first ? "!" : "" });
  browser.browserAction.setTitle({ title: first ? "Tidier: " + first : "Tidier" });
  viewAllSoon();
}

const sleep = ms => new Promise(r => setTimeout(r, ms));
// A tab or window can close at any moment, between one call and the next, and Firefox then
// refuses the next call about it. That is no error, and must not stop the job halfway: the
// tab is simply gone. Anything else Firefox refuses still counts.
const isGone = err => /^Invalid (tab|window) ID/.test(err?.message);
const ifGone = err => { if (!isGone(err)) throw err; };
// Closed one by one: Firefox refuses a whole list if one of them has already closed. `marks`
// tells the listeners it is Tidier closing them; a tab that closed before it was marked gets
// no event that would unmark it, so that is done here. (The event comes before the answer.)
async function removeTabs(ids, marks) {
  ids.forEach(id => marks?.add(id));
  try {
    await Promise.all(ids.map(id => browser.tabs.remove(id).catch(ifGone)));
  } finally {
    ids.forEach(id => marks?.delete(id));
  }
}
// A tab moved to another window: Firefox announces the move while it is still closing the
// tab in the old window, under the same ID, so for a moment the old window lists it. Looked
// at then, the window it left seems to have it still, and is not given its copy. (`stale`
// says whether a tab listed with that ID is still the old one.)
async function movedAway(tabId, stale) {
  for (let i = 0; i < 40; i++) {
    if (!(await browser.tabs.query({}).catch(() => [])).some(t => t.id === tabId && stale(t))) return;
    await sleep(25);
  }
}
// A new tab, or nothing if its window has closed meanwhile: a window you close at any
// moment is no error, and must not stop the work for the other windows. Any other
// refusal is passed on. Firefox answers only once a new window has finished starting, and
// never if it is closed before that: the whole queue would wait for the answer, for a job's
// time limit, so the closing of the window is an answer too.
const tabsOnTheirWay = new Set(); // what to do when a window closes (one listener: each new one is a message to Firefox)
browser.windows.onRemoved.addListener(windowId => { for (const heard of tabsOnTheirWay) heard(windowId); });
function createTab(props) {
  const { windowId } = props;
  const made = browser.tabs.create(props).catch(async err => {
    if (windowId !== undefined && !(await browser.windows.get(windowId).catch(() => null))) return null;
    throw err;
  });
  let heard;
  const closed = new Promise(resolve => {
    heard = id => { if (id === windowId) resolve(null); };
    tabsOnTheirWay.add(heard);
  });
  return Promise.race([made, closed]).finally(() => tabsOnTheirWay.delete(heard));
}
const isWeb = url => /^https?:/i.test(url || "");
// Same host, ignoring a leading "www.".
const sameSite = (a, b) => {
  try { const h = u => new URL(u).hostname.replace(/^www\./, ""); return h(a) === h(b); } catch (e) { return false; }
};

// Placeholder page for ghosts and essential copies (see ghost.js). Asked for once:
// it never changes while Tidier runs, and this is looked at for every tab in a view.
const GHOST_PAGE = browser.runtime.getURL("ghost.html");
const ghostUrl = (kind, key) => `${GHOST_PAGE}?kind=${kind}&key=${encodeURIComponent(key)}`;
const isGhostUrl = url => (url || "").startsWith(GHOST_PAGE);
// What a placeholder stands for, from its own address: a tab's session values can be lost
// (Firefox loses them for an unloaded tab moved to another window), this cannot.
const placeholderOf = url => {
  if (!isGhostUrl(url)) return {};
  const params = new URL(url).searchParams;
  return { kind: params.get("kind"), key: params.get("key") };
};

// Placeholders we close ourselves would show up in Recently Closed Tabs, and
// ⌘⇧T would bring one back instead of the tab you closed. Only real pages
// should be there, so they are forgotten. A loaded tab reaches Recently Closed
// a moment after it is closed (Firefox saves its state first), so each is
// looked for again whenever that list changes, for FORGET_MS. (An essential
// copy made beside Sidebery has an address that ends in "&placed=N": it was
// loaded again so that Sidebery would see it. Such copies stay until they close.)
//
// The same goes for a real page Tidier closed because it is open elsewhere (opened again in
// its space, say). That is looked for only until it is found, and not for long: a moment
// later you may close the page itself, and that one ⌘⇧T must bring back.
//
// Closing many tabs changes that list once per tab, and a look makes Firefox copy
// everything in it, also a closed window with all its tabs. So nobody waits for a look,
// one runs at a time, and if the list changed meanwhile, another follows after a rest in
// proportion to what this one took. With a few tabs that rest is hardly anything. It has
// a limit, well below FORGET_PAGE_MS: past that a placeholder would no longer be looked for,
// and would stay in the list, on a machine that is merely busy.
const FORGET_MS = 10000, FORGET_PAGE_MS = 3000, FORGET_REST = 9, FORGET_LONGEST_REST_MS = 1000;
const toForget = new Map(); // address -> { until when to look for it, whether once is enough }
let forgetTimer = null, forgetBusy = false, forgetAgain = false;
function forgetClosedPlaceholders(kind, keys) {
  // A synced tab's placeholder is a "ghost", or "lazy" if it stands for a pull request
  // never opened (createLiveItem); ⌘⇧T would bring that back with nothing to show.
  const kinds = kind === "ghost" ? ["ghost", "lazy"] : [kind];
  forgetClosed(keys.flatMap(k => kinds.map(x => ghostUrl(x, k))), FORGET_MS, false);
}
const forgetClosedPages = urls => forgetClosed(urls, FORGET_PAGE_MS, true);
function forgetClosed(urls, ms, once) {
  if (!urls.length) return;
  for (const url of urls) toForget.set(url, { until: Date.now() + ms, once });
  // So the list empties also if nothing else changes: at the last of them.
  clearTimeout(forgetTimer);
  const last = Math.max(...[...toForget.values()].map(f => f.until));
  forgetTimer = setTimeout(forgetClosedNow, last - Date.now() + 100);
  forgetClosedNow();
}
async function forgetClosedNow() {
  if (forgetBusy) { forgetAgain = true; return; }
  for (const [url, { until }] of toForget) if (until < Date.now()) toForget.delete(url);
  if (!toForget.size) return;
  forgetBusy = true;
  const t0 = performance.now();
  // (An essential copy made beside Sidebery has "&placed=N" after it, see above.)
  const ours = url => toForget.has(url) ? url : [...toForget.keys()].find(p => url?.startsWith(p + "&"));
  try {
    const closed = await browser.sessions.getRecentlyClosed().catch(() => []);
    for (const t of closed.map(item => item.tab).filter(Boolean)) {
      const found = ours(t.url);
      if (found === undefined) continue;
      if (toForget.get(found)?.once) toForget.delete(found);
      await browser.sessions.forgetClosedTab(t.windowId, t.sessionId).catch(() => {});
    }
  } finally {
    // The rest counts as busy, so that what changes during it waits for the look after it.
    setTimeout(() => {
      forgetBusy = false;
      if (forgetAgain) { forgetAgain = false; forgetClosedNow(); }
    }, Math.min(FORGET_REST * (performance.now() - t0), FORGET_LONGEST_REST_MS));
  }
}
browser.sessions.onChanged.addListener(() => { forgetClosedNow(); });

// A tab with no container: Firefox's own, outside every space.
const NO_CONTAINER = "firefox-default";

async function normalWindows() {
  return (await browser.windows.getAll({ windowTypes: ["normal"] })).filter(w => !w.incognito);
}

// A tab refused while filling a window: if the window has been closed meanwhile, that is
// no error, and there is nothing left to do there (with many tabs, each of them would be
// refused in turn). Returns whether to go on with the next tab.
async function refusedInWindow(windowId, err) {
  if (!(await browser.windows.get(windowId).catch(() => null))) return false;
  noteError(err);
  return true;
}

// A new window is filled NEW_WINDOW_DELAY_MS after Firefox announces it, once its
// first tab is there; a reopened window can get its tabs' values RESTORED_LATE_MS later
// (see windows.onCreated in tabsync.js).
const NEW_WINDOW_DELAY_MS = 200;
const RESTORED_LATE_MS = 3000;

// A folder: only an entry in the tab record, with no tab of its own, so no tab event can
// delete it (ownfolders.js). Every folder is one (`own`); a folder of Sidebery's had a
// page, and a browser that had those is moved over at its first start (moveover.js).
const isOwnFolder = entry => !!entry?.group && !!entry.own;

// --- Saved tabs --------------------------------------------------------------
// A tab in a folder (at any depth) is *saved*, like a tab in Arc's
// pinned section: ⌘W unloads it instead of closing it, and it goes back to the
// address it had when it came into the folder (`saved` in its synced entry).
// Closing it while it is unloaded removes it; so does dragging it out of the
// folder, which makes it an ordinary tab again. A live folder's pull requests
// are not saved: the search decides what is in them (livefolders.js).

// The nearest folder above the stored entry `key`, by the stored parents.
function folderKeyOf(all, key) {
  for (let k = all[key]?.parentKey, seen = new Set(); k && all[k] && !seen.has(k); k = all[k].parentKey) {
    seen.add(k);
    if (all[k].group) return k;
  }
  return null;
}
function storedInFolder(all, key) { return folderKeyOf(all, key) !== null; }

// Keep each entry's `saved` address current: set it when a tab is first seen
// in a folder (from its address then), remove it when the tab leaves. Only
// `keys` when given (a page load concerns its own tab only).
function noteSaved(all, keys = Object.keys(all)) {
  for (const key of keys) {
    const e = all[key];
    if (!e) continue;
    if (e.group || e.liveFolder || !storedInFolder(all, key)) delete e.saved;
    else if (!e.saved && isWeb(e.url)) e.saved = { url: e.url, title: e.title, icon: e.icon };
    // An ordinary tab has no name (tabnames.js), and its placeholders must stop showing it. A folder's is its own.
    if (!e.group && !e.saved && e.name) { delete e.name; refreshGhostsSoon(key); }
  }
}

// What closing a synced tab (not by closing its window) means:
//   "unload" a saved tab you closed while it was loaded
//   "close"  everything else: closed in every window
function closeAction({ inFolder, liveFolder, unloaded }) {
  return inFolder && !liveFolder && !unloaded ? "unload" : "close";
}

// The focused window, tracked here so tab events need no round trip to ask.
// Registered before the other scripts' listeners, so it is current when they run.
let focusedWindowId = browser.windows.WINDOW_ID_NONE;
browser.windows.getLastFocused().then(w => { if (w.focused) focusedWindowId = w.id; }).catch(() => {});
browser.windows.onFocusChanged.addListener(id => { focusedWindowId = id; });

// A value saved to storage.local a moment after the last change, so bursts of
// changes become one write. Reads come from memory.
//
// A change that is only a title or an icon is `lazy`: a page whose title ticks (a
// timer, an unread count) would otherwise rewrite everything at every tick, all day.
// It is written at most once every LAZY_WRITE_MS; a title lost in a crash comes back
// with the page. Any other change is written at once and takes the lazy one along.
const WRITE_DELAY_MS = 300, LAZY_WRITE_MS = 30000;
const unwritten = new Set(); // what `flushWrites` must write now
function storedValue(storageKey, empty) {
  let value = null, timer = null, lastWrite = 0;
  const write = () => {
    clearTimeout(timer);
    timer = null;
    unwritten.delete(write);
    lastWrite = Date.now();
    // Refused (a full disk, say): tried again later, or only memory would have it, and a
    // start would lose what no other change happened to write.
    return browser.storage.local.set({ [storageKey]: value }).catch(err => {
      noteError(err);
      unwritten.add(write);
      timer ??= setTimeout(write, LAZY_WRITE_MS);
    });
  };
  return {
    async get() {
      if (value === null) value = (await browser.storage.local.get(storageKey))[storageKey] ?? empty();
      return value;
    },
    set(next, { lazy = false } = {}) {
      value = next;
      unwritten.add(write);
      if (lazy && timer !== null) return; // a write is on its way anyway
      clearTimeout(timer);
      timer = setTimeout(write, lazy ? Math.max(WRITE_DELAY_MS, lastWrite + LAZY_WRITE_MS - Date.now()) : WRITE_DELAY_MS);
    },
  };
}

const flushWrites = () => Promise.all([...unwritten].map(write => write()));
