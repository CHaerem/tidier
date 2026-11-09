// Tidier's own folders (Tidier alone): a folder is an entry in the tab record
// (`group`, `own`, with a name and a place among its space's folders), with no tab
// of its own. A tab is in a folder by its `parentKey`, as with Sidebery's folder
// pages, so saved tabs and archiving work the same on both. Only what you do here
// changes a folder; no tab event can delete one.

const newFolderKey = () => crypto.randomUUID();

async function createFolder(name, cookieStoreId, { live, before } = {}) {
  const all = await getSynced();
  const key = newFolderKey();
  const others = foldersOf(all, cookieStoreId);
  all[key] = { group: true, own: true, name, cookieStoreId, parentKey: null, rank: (others.at(-1)?.rank ?? 0) + 1, added: Date.now(), ...(live ? { live } : {}) };
  saveSynced(all);
  if (before !== undefined) await moveFolder(key, before);
  return key;
}

// A space's folders, in the order they are shown.
function foldersOf(all, cookieStoreId) {
  return Object.entries(all).filter(([, e]) => isOwnFolder(e) && e.cookieStoreId === cookieStoreId)
    .map(([key, e]) => ({ key, ...e })).sort((a, b) => a.rank - b.rank);
}

async function renameFolder(key, name) {
  const all = await getSynced();
  if (!isOwnFolder(all[key]) || !name.trim()) return;
  all[key].name = name.trim();
  saveSynced(all);
}

async function foldFolder(key, collapsed) {
  const all = await getSynced();
  if (!isOwnFolder(all[key])) return;
  all[key].collapsed = !!collapsed;
  saveSynced(all);
  for (const w of await normalWindows()) successorSoon(w.id); // spaces.js: closing a tab does not land in a closed folder
  await foldChanged(key); // foldrest.js
}

// Deleting a folder loses nothing: its tabs become ordinary tabs, which archiving
// then tidies as usual. (A live folder's tabs go with it: the search decides them. But a
// page with unsaved input must not make Firefox ask at a moment you did not choose, so
// that one stays, as an ordinary tab.)
// Archiving would otherwise take a tab last used over 12 hours ago at its next look,
// so "its tabs stay" would not be true: a tab that leaves counts as new from here.
// In the sidebar (`windowId`) the line offers to undo it (quiet.js).
async function deleteFolder(key, windowId) {
  const all = await getSynced();
  if (!isOwnFolder(all[key])) return;
  const undo = windowId === undefined ? undefined : await rememberFolder(all, key, windowId);
  const gone = Object.keys(all).filter(k => all[k].parentKey === key);
  for (const k of gone) {
    if (all[k].liveFolder && await closesQuietly(k)) { await closeEverywhere(k, { dismiss: false }); continue; }
    Object.assign(all[k], { parentKey: all[key].parentKey ?? null, added: Date.now() });
    delete all[k].liveFolder;
    delete all[k].liveUrl;
  }
  delete all[key];
  noteSaved(all);
  saveSynced(all);
  await foldChanged(key); // a closed folder's tabs were hidden
  if (undo) say(windowId, "Folder deleted", { undo });
}

// A folder moved among its space's folders (`beforeKey` null: last).
async function moveFolder(key, beforeKey) {
  const all = await getSynced();
  if (!isOwnFolder(all[key])) return;
  const order = foldersOf(all, all[key].cookieStoreId).map(f => f.key).filter(k => k !== key);
  const at = beforeKey ? order.indexOf(beforeKey) : -1;
  order.splice(at < 0 ? order.length : at, 0, key);
  order.forEach((k, i) => { all[k].rank = i + 1; });
  saveSynced(all);
}

// A tab moved in the sidebar: into or out of a folder (`folderKey`, or null) and
// before another tab (`beforeTabId`, or null: last there). Every window follows,
// and without Sidebery's rules about what may move where, any tab can simply move.
async function moveTab(windowId, tabId, beforeTabId, folderKey) {
  // A tab opened or unpinned a moment ago is not in the record yet: tab sync waits for
  // redirects first. You are moving it now, and without a record no folder can take it.
  await register(tabId);
  const all = await getSynced();
  const key = syncKeyByTab.get(tabId);
  if (key && all[key]) {
    if (folderKey !== undefined && !all[key].liveFolder && !all[folderKey]?.live) {
      // Out of its folder it counts as new, or archiving could take it at its next look.
      if (!folderKey && all[key].parentKey) all[key].added = Date.now();
      all[key].parentKey = folderKey;
      noteSaved(all, [key]);
      saveSynced(all);
    }
    // What it goes before can be a tab only this window has, such as a new tab page: the
    // other windows have nothing for that, so there the next tab they do have counts.
    const here = (await browser.tabs.query({ windowId })).sort((a, b) => a.index - b.index);
    const from = here.findIndex(t => t.id === beforeTabId);
    const beforeKey = from < 0 ? null : here.slice(from).map(t => syncKeyByTab.get(t.id)).find(k => k && k !== key) ?? null;
    for (const w of await normalWindows()) {
      const tabs = await browser.tabs.query({ windowId: w.id });
      const reps = repMap(tabs);
      const before = w.id === windowId && from >= 0 ? beforeTabId : beforeKey ? reps.get(beforeKey) : null;
      if (reps.has(key)) await moveInWindow(tabs, reps.get(key), before);
      successorSoon(w.id); // spaces.js: into a closed folder, perhaps with no move Firefox would report
    }
    await restMoved(key); // foldrest.js
  } else {
    await moveInWindow(await browser.tabs.query({ windowId }), tabId, beforeTabId);
  }
  viewSoon(windowId);
}

async function moveInWindow(tabs, tabId, beforeId) {
  const tab = tabs.find(t => t.id === tabId), before = tabs.find(t => t.id === beforeId);
  if (!tab) return;
  let index = before ? before.index : -1;
  if (before && tab.index < before.index) index--;
  if (index === tab.index) return;
  // Not marked as Tidier's own (syncBusy): without Sidebery nothing listens to a move, and for
  // that moment a pin or a new title would go unseen. A tab dragged on to the essentials
  // right after a move stayed in the tab record too, and so was there twice; a new tab
  // dragged and given an address within a second and a half was never synced.
  await browser.tabs.move(tabId, { index }).catch(() => {});
}

// A tab moved to another space: Firefox cannot change a tab's container, so it is
// opened again there and closed here, in every window. A page that may hold unsaved
// input stays, and so does a tab that cannot be opened there; no rule sends it back,
// since you moved it; and you stay where you are (safemoves.js).
//
// The address is the page's own while it is loaded: the record follows a page once it
// has finished loading, and a tab can be moved before that. A placeholder's own address
// says nothing, so then it is the record's.
//
// It loses nothing else either: a page that was not loaded arrives unloaded, with its
// title, so nothing is asked of the site in a space you are not looking at, and a muted
// one stays muted, so a podcast you had silenced does not play there out of sight.
// (What it was is read first: leaving unloads it, to see whether it holds unsaved input.)
// The line says where it went, with Undo (sayMoved); `back` is that Undo, which says nothing.
async function moveToSpace(tabId, space, leaving = [], { back = false } = {}) {
  const tab = await browser.tabs.get(tabId).catch(() => null);
  if (!tab || tab.cookieStoreId === space || tab.pinned) return null;
  const key = syncKeyByTab.get(tabId), live = await pageTab(tab, key), entry = key ? (await getSynced())[key] : null;
  const url = isWeb(live?.url) ? live.url : entry?.url;
  if (!isWeb(url)) return null;
  const unloaded = !live || live.discarded || isGhostUrl(live.url), muted = !!live?.mutedInfo?.muted;
  const title = (isWeb(live?.url) && live.title) || entry?.title || url;
  const was = { space: tab.cookieStoreId, folder: entry?.parentKey ?? null };
  const noSpace = () => void say(tab.windowId, "That space could not be opened, so the tab stayed here");
  // Asked first, since leaving unloads the tab and selects another one. (Only a window
  // closing or a space removed this very moment can still refuse the new tab below.)
  if (await spaceGone(space)) return noSpace();
  if (!(await leavesQuietly(live, key, leaving))) return sayStayed(tab.windowId);
  const opened = await openUnruled({ windowId: tab.windowId, cookieStoreId: space, url, active: false, ...(unloaded ? { discarded: true, title } : {}) }).catch(() => null);
  if (!opened) return noSpace();
  if (muted) await browser.tabs.update(opened.id, { muted: true }).catch(() => {});
  // (A live folder's pull request counts as closed, or the next search brings it back.)
  if (key) await closeEverywhere(key);
  else await browser.tabs.remove(tabId).catch(() => {});
  await forgetClosedPages([url]); // you moved it: ⌘⇧T must not bring it back in the space it left
  if (!back) await sayMoved(tab.windowId, space, opened.id, was);
  return opened;
}

// One line for one move, however its tabs are sent (a selection's tabs, and a drag of
// them onto a dot, arrive one by one): where they went, with Undo, which takes each back
// to the space it came from, and into its folder if that is still there. Without it a moved
// tab simply vanished from the list.
const MOVED_GROUP_MS = 2000;
let movedGroup = null; // { windowId, space, tabs: [{ id, was }], timer }
async function sayMoved(windowId, space, tabId, was) {
  if (movedGroup?.windowId !== windowId || movedGroup.space !== space) movedGroup = { windowId, space, tabs: [] };
  const group = movedGroup;
  group.tabs.push({ id: tabId, was });
  clearTimeout(group.timer);
  group.timer = setTimeout(() => { if (movedGroup === group) movedGroup = null; }, MOVED_GROUP_MS);
  const name = (await containerSpaces()).find(s => s.id === space)?.name ?? "another space";
  const n = group.tabs.length;
  say(windowId, n === 1 ? `Moved to ${name}` : `${n} tabs moved to ${name}`, { undo: () => undoMove(group) });
}
async function undoMove(group) {
  if (movedGroup === group) movedGroup = null;
  const ids = group.tabs.map(t => t.id);
  for (const { id, was } of group.tabs) {
    const back = await moveToSpace(id, was.space, ids, { back: true }).catch(noteError);
    if (back && was.folder && isOwnFolder((await getSynced())[was.folder])) await moveTab(group.windowId, back.id, null, was.folder);
  }
}
