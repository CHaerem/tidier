// Moving a browser from Sidebery to Tidier's own folders (PLAN.md, part D). Sidebery once
// drew the tab list, folders and spaces; its folders were pages of its own, one in each
// window, with their tabs nested under them, and the record had each page as a folder. A
// browser was moved over by a click on the settings page. One that never was is moved at its
// first start without Sidebery, in the same order:
//
//   1. A copy of everything (copies.js): through the native host, or else in Firefox's own
//      storage (`copyBeforeMove`).
//   2. Sidebery's folders become Tidier's own in the record, which is written before anything
//      else happens: each keeps its tabs, which stay saved tabs, its name and its place, and
//      a live folder stays one. Which of them Sidebery had closed comes from its export, taken
//      in before or after (importSidebery). Tidier's button and sidebar say what happened.
//   3. Only then are the folder pages closed (closeOldFolderPages). A crash at any point
//      leaves either the old record, and the move happens at the next start, or the new one,
//      and pages that close at the next start.
//
// Sidebery should be disabled first: with it running, closing a folded folder's page closes
// the tabs in it. Even then nothing is lost: those tabs close before Tidier has started, which
// it does not take for your doing (tabs.onRemoved, tabsync.js), and as saved tabs they get
// their placeholders back as it starts. A click asked for the optional permissions; a move
// by itself leaves them to the sidebar, which asks for hiding tabs (sidebar/sidebar.js).

// Sidebery's folders were "group" pages served by Sidebery itself, and named in their address.
const isSideberyGroup = url => /^moz-extension:\/\/[^/]+\/sidebery\/group\.html/.test(url || "");
const groupName = url => decodeURIComponent((url.split("#")[1] || "").replace(/~!.*!~$/, "").replace(/(?::id:|%3Aid%3A).*$/, "")); // (":id:" from older Sidebery)

async function moveOverOnce() {
  const all = await getSynced();
  const old = Object.keys(all).filter(k => all[k].group && !all[k].own);
  if (old.length) {
    const copy = await makeCopy();
    if (!copy?.saved) await browser.storage.local.set({ copyBeforeMove: await theCopy() }); // no helper here: at least inside Firefox's storage
    const closed = new Set(listIn((await browser.storage.local.get("importedFolds")).importedFolds)); // importSidebery
    const live = new Map(Object.entries(await liveFolderState.get()).map(([id, s]) => [s.groupKey, id])); // livefolders.js
    // Sidebery's tree put tabs under tabs too. Here a tab is in its nearest folder or in none,
    // and a folder in no other: what Tidier's own folders are, and what deleting one and
    // undoing that count on (ownfolders.js, quiet.js). Looked up before anything changes.
    const folderOf = new Map(Object.keys(all).filter(k => !all[k].group && all[k].parentKey).map(k => [k, folderKeyOf(all, k)]));
    for (const [k, folder] of folderOf) all[k].parentKey = folder;
    for (const k of await inSideberyOrder(old)) {
      const e = all[k];
      // `oldUrl`: its address in Sidebery, by which Sidebery's export says whether it was closed.
      Object.assign(e, { own: true, name: groupName(e.url), oldUrl: e.url, parentKey: null, rank: (foldersOf(all, e.cookieStoreId).at(-1)?.rank ?? 0) + 1 });
      if (closed.has(foldKey(e.cookieStoreId, e.url))) e.collapsed = true;
      // A live folder's page was one of Sidebery's too; as Tidier's own it is marked as one, or
      // it would be shared through sync, kept in copies and take tabs dragged in like any other.
      if (live.has(k)) e.live = live.get(k);
    }
    noteSaved(all);
    saveSynced(all);
    await flushWrites();
    await browser.storage.local.set({ importedFolds: [], movedFromSidebery: Date.now() });
    // Shown on Tidier's button, which is where to look: Sidebery's sidebar has lost its folders,
    // and Tidier's own takes its place. Gone when you have seen it (sidebar/isolation.js).
    setNotice("moved", "Sidebery's folders are now Tidier's own, after a copy of everything. Tidier's sidebar takes Sidebery's place; Sidebery can be removed in about:addons.");
  }
  await closeOldFolderPages();
}

// Folders in the order Sidebery showed them, each space's first and in the same order in every
// window: by where their pages are in the window that has the most of them. One with no page
// there comes last, in the record's order.
async function inSideberyOrder(keys) {
  const pages = (await browser.tabs.query({})).filter(t => isSideberyGroup(t.url));
  const count = new Map();
  for (const t of pages) count.set(t.windowId, (count.get(t.windowId) ?? 0) + 1);
  const most = [...count].sort((a, b) => b[1] - a[1])[0]?.[0];
  const place = new Map();
  for (const t of pages.filter(t => t.windowId === most).sort((a, b) => a.index - b.index)) {
    const key = await browser.sessions.getTabValue(t.id, SYNC_KEY).catch(() => null);
    if (key && !place.has(key)) place.set(key, place.size);
  }
  const at = k => place.get(k) ?? Number.MAX_SAFE_INTEGER;
  return [...keys].sort((a, b) => at(a) - at(b));
}

// The pages of folders that are now Tidier's own, and any Sidebery folder page left, are
// closed once, with nothing else happening to their tabs.
async function closeOldFolderPages() {
  const pages = (await browser.tabs.query({})).filter(t => isSideberyGroup(t.url));
  if (!pages.length) return; // as at every start but the first: reading every tab's values is left for the start itself
  await loadRoles();
  pages.forEach(t => forget(t.id));
  await removeTabs(pages.map(t => t.id), syncBusy).catch(noteError);
}

// --- Sidebery's export -----------------------------------------------------------
// Its rules, order of spaces and closed folders are stored where only Sidebery can read
// them, so its export is the only place they can be read from. It may come from another
// machine, so its containers are matched by name here too, as with a copy (copies.js).
const isSideberyExport = x => !!x && typeof x === "object" && !x.tidier && !!(x.ver || x.sidebar?.panels || x.containers);
const SIDEBERY_INCLUDE_RULE = 1; // reopenRules' type. Sidebery takes any other as "keep out of this container", the opposite of a rule here
const panelContainer = p => p?.newTabCtx && p.newTabCtx !== "none" && p.newTabCtx !== NO_CONTAINER ? p.newTabCtx : null;
const activeRule = r => r?.active && typeof r.url === "string" ? r.url.trim() : ""; // as Sidebery reads it

// A snapshot keeps only what changed: a tab that did not is -1, to be looked up at the
// same place (window, panel, tab) in the snapshots before it. null if it cannot be.
function snapshotTabs(snapshots, n) {
  const windows = snapshots[n]?.tabs, tabs = [];
  if (!Array.isArray(windows)) return null;
  for (const [w, panels] of windows.entries()) for (const [p, panel] of listIn(panels).entries()) for (const [t, tab] of listIn(panel).entries()) {
    let found = tab;
    for (let older = n - 1; found === -1 && older >= 0; older--) found = snapshots[older]?.tabs?.[w]?.[p]?.[t] ?? -1;
    if (!found || found === -1) return null;
    tabs.push(found);
  }
  return tabs;
}

// An address without what differs per install or per load: Sidebery's own extension
// address, the channel suffix ("~!...!~") it adds to a page it has open, and the
// ":id:" of older versions, which its snapshot drops from an open page but not from an
// unloaded one. The same name in two spaces gives one address, so the space is part of the key.
const foldKey = (space, url) => `${space}|${(url || "").split("/sidebery/")[1]?.replace(/~!.*!~$/, "").replace(/(?::id:|%3Aid%3A).*$/, "")}`;

// Which folders the newest readable snapshot has closed, as foldKeys; null if the export
// has no snapshot. Each window has its own page of a folder and may show it otherwise.
// A folder here is the same in every window and a closed one rests, so it comes over
// closed only if it was closed in all of them. `here` gives a container's id on this machine.
function closedFolders(backup, here) {
  const snapshots = listIn(backup?.snapshots);
  let tabs = null;
  for (let n = snapshots.length - 1; n >= 0 && !tabs; n--) tabs = snapshotTabs(snapshots, n);
  if (!tabs) return null;
  const pages = new Map();
  for (const t of tabs) {
    const space = here(t.containerId ?? NO_CONTAINER);
    if (!isSideberyGroup(t.url) || !space) continue;
    const key = foldKey(space, t.url);
    pages.set(key, (pages.get(key) ?? true) && !!t.folded);
  }
  return [...pages].filter(([, closed]) => closed).map(([key]) => key);
}

// Null for a file that is not Sidebery's export. Folds are applied at once to the folders
// that came from Sidebery, known by their old address. (An older Tidier kept them for the
// move instead, `importedFolds`, which moveOverOnce applies.)
async function importSidebery(backup) {
  if (!isSideberyExport(backup)) return null;
  const containers = Object.values(backup.containers || {});
  const panels = backup.sidebar?.panels || {};
  const local = await containerSpaces();
  const named = containers.filter(c => isText(c?.id) && isText(c.name)).map(c => ({ id: c.id, name: c.name, color: c.color, icon: c.icon }));
  const map = mapSpaces({ spaces: named }, local);
  const here = id => localSpace(map, local, id);

  // Rules only by name, as with a copy: an export with its containers left out says
  // nothing about whose logins an id is, and a wrong rule sends tabs to the wrong ones.
  const found = [];
  if (map) for (const c of containers) {
    if (!c?.reopenRulesActive) continue;
    for (const r of listIn(c.reopenRules)) if (activeRule(r) && r.type === SIDEBERY_INCLUDE_RULE) found.push({ url: activeRule(r), space: c.id });
  }
  // A panel's rules move a tab to it. Here the panel is its container's space, so a rule
  // with an address opens it there; one with only a container needs nothing, since the
  // container already decides the space. A rule for tabs in another container stays out:
  // here it would change their logins, which it never did in Sidebery. A panel with no
  // container is no space here.
  let panelsLeftOut = 0;
  for (const p of Object.values(panels)) {
    const urls = listIn(p?.moveRules).filter(r => !r?.containerId || r.containerId === p.newTabCtx).map(activeRule).filter(Boolean);
    if (!urls.length) continue;
    const space = panelContainer(p);
    if (map && space && here(space) !== undefined) found.push(...urls.map(url => ({ url, space })));
    else panelsLeftOut++;
  }
  const order = [...new Set(listIn(backup.sidebar?.nav).map(id => panelContainer(panels[id])))].filter(id => id && here(id) !== undefined);
  const needed = new Set([...found.map(r => r.space), ...order]);
  const newSpaces = map ? await makeMissingSpaces(named, map, id => needed.has(id)) : [];

  const have = await rulesList.get();
  const added = [];
  for (const { url, space } of found) {
    const rule = { url, space: here(space) };
    if (rule.space && ![...have, ...added].some(x => x.url === url && x.space === rule.space)) added.push(rule);
  }
  if (added.length) rulesList.set([...have, ...added]);
  const localOrder = order.map(here).filter(Boolean);
  if (localOrder.length) await browser.storage.local.set({ spaceOrder: localOrder });

  const closed = closedFolders(backup, here);
  let folds = null;
  if (closed) {
    const all = await getSynced(), keys = new Set(closed);
    const matched = Object.keys(all).filter(k => all[k].group && keys.has(foldKey(all[k].cookieStoreId, all[k].oldUrl ?? all[k].url)));
    for (const k of matched) await foldFolder(k, true); // ownfolders.js
    folds = matched.length;
  }
  viewAllSoon(); // the bar's order, if nothing else
  return { rules: added.length, order: localOrder.length, panelsLeftOut, newSpaces, folds };
}

// --- The settings page -------------------------------------------------------------
browser.runtime.onMessage.addListener((msg, sender) => {
  if (!msg?.type?.startsWith("settings:") || sender.id !== browser.runtime.id || !sender.url?.startsWith(browser.runtime.getURL(""))) return;
  return serial(() => settingsAction(msg));
});

async function settingsAction(msg) {
  switch (msg.type.slice("settings:".length)) {
    case "get": {
      const stored = await browser.storage.local.get(["archiveAfterHours", "lastCopy", "movedFromSidebery"]);
      return {
        rules: await rulesList.get(), spaces: await containerSpaces(), archiveHours: stored.archiveAfterHours ?? ARCHIVE_DEFAULT_HOURS,
        lastCopy: stored.lastCopy ?? null, moved: stored.movedFromSidebery ?? null, version: browser.runtime.getManifest().version,
        hiding: !!browser.tabs.hide, notices: [...notices.values()],
      };
    }
    case "archiveHours": await browser.storage.local.set({ archiveAfterHours: Number(msg.hours) }); return true;
    case "rules": rulesList.set(msg.rules.filter(r => r.url && r.space).map(r => ({ url: r.url, space: r.space }))); setNotice("rule", null); viewAllSoon(); return true;
    case "space": await browser.contextualIdentities.update(msg.id, msg.changes).catch(noteError); return true;
    case "importSidebery": return importSidebery(msg.backup);
    case "copyNow": return makeCopy();
    case "copyFile": return theCopy();
    case "copySummary": return copySummary(msg.copy);
    case "merge": return mergeCopy(msg.copy, msg.spaces);
    case "keys": return commandKeys();
    case "setKey": return setCommandKey(msg.name, msg.shortcut);
    case "keysBack": return keysBackToFirst();
  }
}
