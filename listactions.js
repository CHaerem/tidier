// What acts on a part of the list at once (Tidier alone): today's tabs or a folder sorted,
// the tabs around one closed, or the duplicates among today's tabs, tabs moved to the top,
// the bottom or one place along, a whole folder or space reloaded or muted, and going back
// and forward through the tabs used recently. Nothing here is on screen until wanted: it is
// reached from the tab menu's More (sidebar/tabmenu.js), a folder's or a space's menu, the
// command bar (commandbar.js) and the keys (shortcuts.js), and each of them hands over the
// tabs it is about: the selection, else the tab.
//
// "As drawn" is what the sidebar shows (viewFor, sidebar-view.js), not the window's order:
// a window has every space's tabs, in the order they came, and a folder's tabs anywhere.
// A move goes through moveTab (ownfolders.js), so every window follows.

// --- The parts of the list -------------------------------------------------------
// The groups the rows `ids` are drawn in: a folder (`key`) or today's tabs (key null), each
// with all its rows as drawn and those of `ids` among them. A tile is in no group.
function groupsOf(view, ids) {
  const wanted = new Set(ids), groups = [];
  const add = (key, rows, live) => {
    const mine = rows.filter(r => wanted.has(r.id));
    if (mine.length) groups.push({ key, live, rows, mine });
  };
  for (const f of view.folders) add(f.key, f.tabs, !!f.live);
  add(null, view.tabs, false);
  return groups;
}

// What a row stands for, the same for every copy of it: a placeholder that is selected pulls
// its page in under another id (tabsync.js), and an essential has a copy in every window.
const standsFor = id => syncKeyByTab.get(id) ?? (keyByTab.has(id) ? `essential:${keyByTab.get(id)}` : `tab:${id}`);

// When each row's page was last used. A placeholder's own last use is when it was made, which
// says nothing, so it is the real page's: the live tab's, wherever it is, or an essential's
// loaded copy. A page you never looked at has none (0).
async function lastUses(ids) {
  return Promise.all(ids.map(async id => {
    const key = syncKeyByTab.get(id), essential = keyByTab.get(id);
    if (key) {
      const liveId = liveTabId(key);
      const live = liveId === undefined ? null : await browser.tabs.get(liveId).catch(() => null);
      return live && !isGhostUrl(live.url) ? live.lastAccessed || 0 : 0;
    }
    if (essential) return Math.max(0, ...(await copiesOf(essential).catch(() => [])).filter(isLoadedCopy).map(t => t.lastAccessed || 0));
    return (await browser.tabs.get(id).catch(() => null))?.lastAccessed || 0;
  }));
}

// Each row in `current` order put in `target` order (both the same ids), with as few moves as
// can be: the rows already in order among themselves stay (the longest such run), the others
// go, last first, right in front of the one that is to follow them, or to the end. So a sort
// of a list that is nearly sorted moves only what is out of place, and a move to the top is
// one move. The end of the window is the end of any group: a group is drawn in window order.
async function arrange(windowId, current, target) {
  const place = new Map(target.map((id, i) => [id, i]));
  const stays = new Set(longestInOrder(current.map(id => place.get(id))).map(i => target[i]));
  let moved = 0;
  for (let i = target.length - 1; i >= 0; i--) {
    if (stays.has(target[i])) continue;
    await moveTab(windowId, target[i], target[i + 1] ?? null, undefined);
    moved++;
  }
  return moved;
}

// The longest increasing run (not necessarily together) in a list of numbers, as its numbers.
function longestInOrder(xs) {
  const ends = [], before = new Array(xs.length), at = [];
  xs.forEach((x, i) => {
    let lo = 0, hi = ends.length;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (xs[ends[mid]] < x) lo = mid + 1; else hi = mid; }
    before[i] = lo ? ends[lo - 1] : -1;
    ends[lo] = i;
    at[lo] = i;
  });
  const run = [];
  for (let i = ends.at(-1) ?? -1; i >= 0; i = before[i]) run.unshift(xs[i]);
  return run;
}

// --- Sorting ---------------------------------------------------------------------
// By the name shown, by site (what people call it, then the host and the name), or by last
// use, the most recent first. Ties keep their order. Live folders are left alone: the search
// decides what is in them, and their order is the search's.
const SORT_WORDS = { name: "name", site: "site", used: "last use" };
const sortCollator = new Intl.Collator(undefined, { sensitivity: "base", numeric: true });
// Read from the right, so that a site comes before its subdomains: github.com, gist.github.com.
const hostOf = url => { try { return new URL(url).hostname.replace(/^www\./, "").split(".").reverse().join("."); } catch { return ""; } };
const SORTS = {
  name: (a, b) => sortCollator.compare(a.title, b.title),
  // A row with no address (a new tab) goes last.
  site: (a, b) => (!a.url - !b.url) || sortCollator.compare(siteNameOf(a.url), siteNameOf(b.url)) || sortCollator.compare(hostOf(a.url), hostOf(b.url)) || sortCollator.compare(a.title, b.title),
  used: (a, b) => b.used - a.used,
};

// The groups a sort is for: those of the tabs, else, for a tile or nothing, today's tabs.
function sortGroups(view, ids) {
  const groups = groupsOf(view, ids).filter(g => !g.live && g.rows.length > 1);
  return groups.length || groupsOf(view, ids).length ? groups : groupsOf(view, view.tabs.map(r => r.id)).filter(g => g.rows.length > 1);
}

// One line, with Undo: a careful order of your own is easily lost to one click.
async function sortTabs(windowId, ids, by) {
  if (!SORTS[by]) return;
  const view = await viewFor(windowId), all = await getSynced();
  const before = [];
  let moved = 0;
  for (const g of sortGroups(view, ids)) {
    const rowIds = g.rows.map(r => r.id), uses = by === "used" ? await lastUses(rowIds) : [];
    const rows = g.rows.map((r, i) => ({ id: r.id, title: r.title || "", url: all[syncKeyByTab.get(r.id)]?.url ?? null, used: uses[i] ?? 0 }));
    const sorted = [...rows].sort(SORTS[by]).map(r => r.id);
    before.push({ folder: g.key, order: rowIds.map(standsFor) });
    moved += await arrange(windowId, rowIds, sorted);
  }
  if (moved) say(windowId, `Sorted by ${SORT_WORDS[by]}`, { undo: () => putBack(windowId, before) });
}

// Each group back in the order it had, by what its rows stand for: a placeholder selected
// since is the same tab under another id. A row that came meanwhile stays after them.
async function putBack(windowId, groups) {
  const view = await viewFor(windowId);
  for (const { folder, order } of groups) {
    const rows = folder ? view.folders.find(f => f.key === folder)?.tabs : view.tabs;
    if (!rows) continue;
    const now = rows.map(r => r.id), rank = new Map(order.map((k, i) => [k, i]));
    const target = [...now].sort((a, b) => (rank.get(standsFor(a)) ?? Infinity) - (rank.get(standsFor(b)) ?? Infinity));
    await arrange(windowId, now, target);
  }
}

// --- To the top, the bottom, one place along ------------------------------------
// Within the tabs' own folder, or today's tabs: past its end a tab would change what it is
// (saved or not), and that is what dragging is for. A selection moves together, and one at the
// end stays while the others close up to it.
async function moveAlong(windowId, ids, where) {
  const view = await viewFor(windowId);
  for (const g of groupsOf(view, ids)) {
    if (g.live) continue; // their order is the search's
    const all = g.rows.map(r => r.id), mine = new Set(g.mine.map(r => r.id));
    const target = where === "top" ? [...all.filter(id => mine.has(id)), ...all.filter(id => !mine.has(id))]
      : where === "bottom" ? [...all.filter(id => !mine.has(id)), ...all.filter(id => mine.has(id))]
      : stepped(all, mine, where);
    await arrange(windowId, all, target);
  }
}

// Each picked row one place up (-1) or down (1), past the next row that is not picked.
function stepped(ids, mine, by) {
  const order = [...ids];
  const swap = i => { [order[i], order[i + by]] = [order[i + by], order[i]]; };
  if (by < 0) { for (let i = 1; i < order.length; i++) if (mine.has(order[i]) && !mine.has(order[i - 1])) swap(i); }
  else for (let i = order.length - 2; i >= 0; i--) if (mine.has(order[i]) && !mine.has(order[i + 1])) swap(i);
  return order;
}

// --- Closing around a tab, and duplicates ---------------------------------------
// Today's tabs as drawn, around the tabs `ids` among them: those above the first, below the
// last, or all others. Only today's tabs: a folder's tabs are kept on purpose.
function aroundIn(view, ids, which) {
  const today = view.tabs.map(r => r.id), mine = today.filter(id => ids.includes(id));
  if (!mine.length) return [];
  if (which === "above") return today.slice(0, today.indexOf(mine[0]));
  if (which === "below") return today.slice(today.indexOf(mine.at(-1)) + 1);
  return today.filter(id => !mine.includes(id));
}

// Today's tabs with the same address as one drawn before them, by the record's address (a
// placeholder's own is no page) and in the same space: a hidden space's tabs are drawn here
// too, with logins of their own. The one you are on is never the double.
function doublesIn(view, all) {
  const rows = [...view.tabs].sort((a, b) => Number(b.active) - Number(a.active));
  const seen = new Set(), doubles = [];
  for (const r of rows) {
    const entry = all[syncKeyByTab.get(r.id)];
    if (!entry || !isWeb(entry.url)) continue;
    const id = `${entry.cookieStoreId} ${entry.url}`;
    if (seen.has(id)) doubles.push(r.id);
    else seen.add(id);
  }
  return doubles;
}

async function closeAround(windowId, ids, which) {
  const view = await viewFor(windowId);
  const stayOn = view.tabs.find(r => ids.includes(r.id))?.id;
  await closeRows(windowId, which === "duplicates" ? doublesIn(view, await getSynced()) : aroundIn(view, ids, which), stayOn);
}

// The rows closed for good, everywhere, as Clear does it (quiet.js), so that one line can take
// them all back: also saved tabs, which ⌘W would only unload. A page with unsaved input stays,
// without asking. A tab selected in another window stays too, since closing it there would
// make Firefox select another, perhaps a placeholder that would pull its page away from
// here. If you are on one of them, you are first taken to the tab the command was for, so
// that Firefox does not pick one on its way out. A page with no record cannot come back with
// Undo: a new tab page has nothing to lose and goes, anything else (Firefox's own settings) is
// in Firefox's own Recently Closed, and goes too.
async function closeRows(windowId, ids, stayOn) {
  if (!ids.length) return;
  const [all, tabs, here, selected] = await Promise.all([getSynced(), tabsNow(windowId), browser.tabs.query({ windowId }), browser.tabs.query({ active: true })]);
  const inUse = new Set(selected.filter(t => t.windowId !== windowId).map(t => syncKeyByTab.get(t.id)).filter(Boolean));
  const on = here.find(t => t.active);
  if (on && ids.includes(on.id) && stayOn !== undefined) await browser.tabs.update(stayOn, { active: true }).catch(() => {});
  const items = [];
  let stayed = 0;
  for (const id of ids) {
    const key = syncKeyByTab.get(id), entry = all[key];
    if (!entry) { if (here.some(t => t.id === id && !t.pinned)) await browser.tabs.remove(id).catch(() => {}); continue; }
    if (entry.group || inUse.has(key)) continue;
    const item = await rememberTab(key, entry); // first: closesQuietly unloads the page
    if (!(await closesQuietly(key))) { stayed++; continue; }
    await noteArchived(entry, "closed"); // archivelist.js: it can be found again there too
    await closeEverywhere(key, { dismiss: false }).catch(noteError);
    items.push(item);
  }
  const count = n => (n === 1 ? "1 tab" : `${n} tabs`);
  if (items.length) say(windowId, `${count(items.length)} closed${stayed ? `, ${stayed} stayed` : ""}`, { undo: () => bringBack(windowId, items, tabs) });
  else if (stayed) say(windowId, `${count(stayed)} with unsaved input stayed`);
}

// --- Reloading a few at a time ---------------------------------------------------
// A whole folder or space reloaded at once would load every page together, and a busy page
// can hold up the others for long. So a few at a time, each next one once one is done or has
// had long enough. Outside the queue: Tidier must not wait for a slow site. One after
// another, so that a second command waits for the first.
const RELOAD_TOGETHER = 3, RELOAD_LONGEST_MS = 15000;
let reloads = Promise.resolve();
function reloadGently(tabIds) {
  const ids = [...new Set(tabIds)];
  reloads = reloads.then(async () => {
    for (let i = 0; i < ids.length; i += RELOAD_TOGETHER) await Promise.all(ids.slice(i, i + RELOAD_TOGETHER).map(reloadAndWait));
  }).catch(noteError);
  return reloads;
}
function reloadAndWait(tabId) {
  return new Promise(resolve => {
    const done = () => {
      clearTimeout(timer);
      browser.tabs.onUpdated.removeListener(loaded);
      browser.tabs.onRemoved.removeListener(gone);
      resolve();
    };
    const loaded = (id, change) => { if (id === tabId && change.status === "complete") done(); };
    const gone = id => { if (id === tabId) done(); };
    const timer = setTimeout(done, RELOAD_LONGEST_MS);
    browser.tabs.onUpdated.addListener(loaded, { properties: ["status"] });
    browser.tabs.onRemoved.addListener(gone);
    browser.tabs.reload(tabId).catch(done);
  });
}

// --- A whole space -----------------------------------------------------------------
// Its real pages that are loaded, in any window: a row here is often a placeholder of a page
// loaded in another window. Firefox's own pages have nothing to reload or mute.
async function spacePages(space) {
  if (!space) return []; // a query without a container is every space's tabs
  return (await browser.tabs.query({ cookieStoreId: space })).filter(isLoadedCopy);
}

async function spaceAction(windowId, { action, space }) {
  const pages = await spacePages(space);
  if (action === "reload") reloadGently(pages.map(t => t.id));
  else if (action === "mute" || action === "unmute") {
    for (const t of pages) if (!!t.mutedInfo?.muted !== (action === "mute")) await browser.tabs.update(t.id, { muted: action === "mute" }).catch(() => {});
  }
}

// What a space's menu needs to know when it opens: what is loaded and muted there, and, for
// the space this window shows, the duplicates among today's tabs.
async function spaceFacts(windowId, space) {
  const pages = await spacePages(space);
  const view = windowId === undefined ? null : await viewFor(windowId).catch(() => null);
  return {
    loaded: pages.length,
    unmuted: pages.filter(t => !t.mutedInfo?.muted).length,
    muted: pages.filter(t => t.mutedInfo?.muted).length,
    duplicates: view?.space === space ? doublesIn(view, await getSynced()).length : 0,
  };
}
browser.runtime.onMessage.addListener((msg, sender) => {
  if (msg?.type !== "spaceFacts" || sender.id !== browser.runtime.id || !sender.url?.startsWith(browser.runtime.getURL(""))) return;
  return spaceFacts(msg.windowId, msg.space);
});

// --- Copying ---------------------------------------------------------------------
// As Markdown links, one per line, for a note or a chat. A title can hold anything, so what
// would end the link's text is escaped, and an address's spaces and brackets are written as
// an address may write them.
function markdownLink(title, url) {
  const text = String(title || url).replace(/\s+/g, " ").trim().replace(/[\\[\]]/g, "\\$&");
  return `[${text}](${url.replace(/[\s()<>]/g, c => "%" + c.charCodeAt(0).toString(16).toUpperCase().padStart(2, "0"))})`;
}
const copyText = text => navigator.clipboard.writeText(text);

// --- A new tab in a folder ---------------------------------------------------------
// A new tab has no address yet, and only a page with an address has a record (register,
// tabsync.js), which is what puts a tab in a folder. So the folder is kept for it here,
// and register uses it once the tab has its page; until then the view draws it in the
// folder. The same goes for a tab opened again in another space by a drop into a folder there.
const comingIntoFolder = new Map(); // tabId -> folder key
browser.tabs.onRemoved.addListener(tabId => comingIntoFolder.delete(tabId));

// The folder a tab being registered goes into, if it is still one that can take it.
function folderComingFor(tabId, all) {
  const key = comingIntoFolder.get(tabId);
  comingIntoFolder.delete(tabId);
  return isOwnFolder(all[key]) && !all[key].live ? key : null;
}

// Last in the folder: a folder's tabs are drawn in window order, and the end is after all of them.
async function newTabInFolder(windowId, key) {
  const folder = (await getSynced())[key];
  if (!isOwnFolder(folder) || folder.live) return;
  const tab = await createTab({ windowId, cookieStoreId: folder.cookieStoreId, active: true }).catch(ifGone);
  if (tab) comingIntoFolder.set(tab.id, key);
}

// --- Back and forward through the tabs used recently ------------------------------------
// Like ⌃Tab in Firefox's recently used order, but through what this space's list draws (not
// other spaces' essentials, nor tabs resting in a closed folder), and by each page's real last
// use. The order is taken when a walk starts and kept while it goes on, since each step makes
// the tab it reaches the most recent. Going to a tab any other way ends the walk, so the next
// Back is to the tab you came from. Nothing runs between presses.
const recentWalks = new Map(); // windowId -> { space, keys (what each tab stands for, newest first), at }
browser.windows.onRemoved.addListener(windowId => recentWalks.delete(windowId));

async function stepRecent(windowId, by) {
  const view = await viewFor(windowId);
  const rows = tabsAsDrawn(view), here = rows.find(r => r.active); // keys-commands.js
  if (!here) return;
  let walk = recentWalks.get(windowId);
  if (!walk || walk.space !== view.space || walk.keys[walk.at] !== standsFor(here.id)) {
    const uses = await lastUses(rows.map(r => r.id));
    const order = rows.map((r, i) => ({ key: standsFor(r.id), used: r === here ? Infinity : uses[i] })).filter(x => x.used > 0).sort((a, b) => b.used - a.used);
    walk = { space: view.space, keys: order.map(x => x.key), at: 0 };
    recentWalks.set(windowId, walk);
  }
  const byKey = new Map(rows.map(r => [standsFor(r.id), r]));
  for (let at = walk.at + by; at >= 0 && at < walk.keys.length; at += by) {
    const row = byKey.get(walk.keys[at]);
    if (!row) continue; // closed, or folded away, since the walk began
    walk.at = at;
    await selectRow(row); // keys-commands.js: as a click on it
    return;
  }
}
// Whether Forward has anywhere to go: only in a walk that has gone back.
const walkedBack = windowId => (recentWalks.get(windowId)?.at ?? 0) > 0;
