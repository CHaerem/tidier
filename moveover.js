// Moving a browser from Sidebery to Tidier alone (PLAN.md, part D), and back. Never by an
// update, only by your clicks on the settings page, in steps the page checks itself:
//
//   1. Sidebery's export is taken in (importSidebery, below): its rules, order of spaces and
//      closed folders exist nowhere else, and only Sidebery, running, can make it.
//   2. One click gives what Tidier alone needs (MOVE_PERMISSIONS), and with it the sight of
//      whether Sidebery is on (management), which every step after this depends on.
//   3. You turn Sidebery off yourself: an extension cannot, and with Sidebery running,
//      closing a folded folder's page would close the tabs in it.
//   4. moveOver, refused while Sidebery runs: Sidebery's folder pages become Tidier's folders
//      in the record, which is written before anything else happens, and Tidier starts again
//      alone. Only then are the folder pages closed (closeOldFolderPages). A crash at any
//      point leaves either the old record, or the new one and pages that close at the next
//      start. The settings page then opens again and says what came over (afterMoving).
//
// Sidebery stays installed for a few weeks, and moveBack undoes it all, again with Sidebery
// off: Tidier puts its folder pages back first (foldersBackToSidebery), and Sidebery, turned on
// after that, builds its tree from them in every window.

const SIDEBERY_ADDON_ID = "{3c078156-979c-498b-8990-85f7987dd929}"; // its manifest's, the same everywhere
const MOVE_PERMISSIONS = { permissions: ["tabHide", "webRequest", "webRequestBlocking", "management"], origins: ["*://*/*"] };

// "on", "off" or "missing" (not installed), or null when Tidier may not see it: the optional
// management permission, given in step 2's click (or in the click that goes back).
// browser.management is not touched before the permission is there: Firefox makes the part
// of it a page may use when the page first touches it, and keeps that.
const mayManage = () => browser.permissions.contains({ permissions: ["management"] }).catch(() => false);
async function sideberyState() {
  if (!(await mayManage()) || !browser.management?.get) return null;
  const info = await browser.management.get(SIDEBERY_ADDON_ID).catch(() => null);
  return !info ? "missing" : info.enabled ? "on" : "off";
}

// Where Sidebery's pages are ("moz-extension://<its id on this machine>/"): from a folder that
// came from it, else from the address of its settings page.
async function sideberyBase(all) {
  const old = Object.values(all).map(e => e.oldUrl).find(isSideberyGroup);
  if (old) return old.slice(0, old.indexOf("sidebery/group.html"));
  const info = await mayManage() && browser.management?.get ? await browser.management.get(SIDEBERY_ADDON_ID).catch(() => null) : null;
  return info?.optionsUrl?.match(/^moz-extension:\/\/[^/]+\//)?.[0] ?? null;
}
// A folder page of Sidebery's, as it makes them: the name is all there is to it. (Sidebery adds
// a part of its own when the page loads, which groupBaseUrl, tabsync.js, takes off again.)
const sideberyGroupUrl = (base, name) => `${base}sidebery/group.html#${encodeURIComponent(name)}`;

// What going back does with each folder: one that came from Sidebery gets its page again, under
// the name it has now; one made since gets a new page, if Sidebery's address is known. Only
// whether a folder is closed cannot come back (Sidebery keeps that itself), so it opens.
function foldersGoingBack(all, base) {
  const folders = Object.entries(all).filter(([, e]) => isOwnFolder(e)).sort((a, b) => (a[1].rank ?? 0) - (b[1].rank ?? 0));
  return folders.map(([key, e]) => {
    const name = e.name || (e.oldUrl ? groupName(e.oldUrl) : "") || "Folder";
    const url = e.oldUrl && groupName(e.oldUrl) === name ? e.oldUrl : (base || e.oldUrl) ? sideberyGroupUrl(base || e.oldUrl.slice(0, e.oldUrl.indexOf("sidebery/group.html")), name) : null;
    return { key, name, url, made: !e.oldUrl, renamed: !!e.oldUrl && groupName(e.oldUrl) !== name, closed: !!e.collapsed };
  });
}

async function moveReport() {
  const all = await getSynced();
  const entries = Object.entries(all);
  const stored = await browser.storage.local.get(["sideberyImported", "movedFromSidebery"]);
  const back = tidierAlone ? foldersGoingBack(all, await sideberyBase(all)) : [];
  return {
    alone: tidierAlone,
    sidebery: await sideberyState(),
    allowed: await browser.permissions.contains(MOVE_PERMISSIONS).catch(() => false),
    imported: stored.sideberyImported ?? null,
    canMoveBack: !!stored.movedFromSidebery || entries.some(([, e]) => e.oldUrl),
    declared: !!(await browser.storage.managed.get("tidierAlone").catch(() => ({}))).tidierAlone, // set for this machine: no going back here
    essentials: (await getList()).length,
    tabs: entries.filter(([, e]) => !e.group).length,
    folders: entries.filter(([, e]) => e.group).map(([key, e]) => ({
      name: e.own ? e.name : groupName(e.url), space: e.cookieStoreId, tabs: entries.filter(([k]) => folderKeyOf(all, k) === key).length,
    })),
    back: {
      folders: back.filter(f => f.url).length, made: back.filter(f => f.url && f.made).length, renamed: back.filter(f => f.renamed).length,
      closed: back.filter(f => f.url && f.closed).length, lost: back.filter(f => !f.url).map(f => f.name),
    },
    rules: (await rulesList.get()).length,
  };
}

const SIDEBERY_ON = "Sidebery is still on. Turn it off in about:addons first, and keep it installed.";
const SIDEBERY_UNSEEN = "Tidier cannot see whether Sidebery is on: it needs to be allowed that first.";

async function moveOver() {
  if (tidierAlone) return { refused: "This browser is on Tidier alone already." };
  // Both at once would fight over every tab, and Sidebery would close a closed folder's tabs
  // with its page. Asked here, not only on the page: the page may be an old one.
  const sidebery = await sideberyState();
  if (sidebery === null) return { refused: SIDEBERY_UNSEEN };
  if (sidebery === "on") return { refused: SIDEBERY_ON };
  const copy = await makeCopy();
  if (!copy?.saved) await browser.storage.local.set({ copyBeforeMove: await theCopy() }); // no helper here: at least inside Firefox's storage
  const all = await getSynced();
  const closed = new Set(listIn((await browser.storage.local.get("importedFolds")).importedFolds)); // importSidebery
  let rank = 0, folders = 0, closedNow = 0;
  for (const e of Object.values(all)) {
    if (!e.group || e.own) continue;
    Object.assign(e, { own: true, name: groupName(e.url), oldUrl: e.url, rank: ++rank });
    folders++;
    if (closed.has(foldKey(e.cookieStoreId, e.url))) { e.collapsed = true; closedNow++; }
  }
  const hidden = await spacesSideberyHadNot(all);
  saveSynced(all);
  await flushWrites();
  await browser.storage.local.set({
    tidierAlone: true, importedFolds: [], movedFromSidebery: true,
    // What the settings page says when it opens again (afterMoving): the move closes it.
    movedNote: { kind: "over", folders, closed: closedNow, tabs: Object.values(all).filter(e => !e.group).length, hidden: hidden.map(s => s.name), windows: (await normalWindows()).length },
    ...(hidden.length ? { [HIDDEN_KEY]: [...new Set([...listIn((await browser.storage.local.get(HIDDEN_KEY))[HIDDEN_KEY]), ...hidden.map(s => s.id)])] } : {}),
  });
  await guardAfterReload();
  browser.runtime.reload();
  return { moving: true };
}

// A container Sidebery had no space for (Firefox's own "Shopping", say) is a space with
// Tidier alone, new on the bar, that nobody asked for. One that holds nothing is hidden on
// this machine (hiddenspaces.js), and the settings page says how to show it. Known only from
// Sidebery's export (sideberyPanels, importSidebery); without it every container stays.
async function spacesSideberyHadNot(all) {
  const { sideberyPanels } = await browser.storage.local.get("sideberyPanels");
  if (!Array.isArray(sideberyPanels) || !sideberyPanels.length) return [];
  const used = new Set([...Object.values(all), ...await getList(), ...await browser.tabs.query({})].map(x => x.cookieStoreId));
  const hiddenAlready = listIn((await browser.storage.local.get(HIDDEN_KEY))[HIDDEN_KEY]);
  const spaces = await containerSpaces();
  const extra = spaces.filter(s => !sideberyPanels.includes(s.id) && !used.has(s.id) && !hiddenAlready.includes(s.id));
  return extra.length < spaces.length ? extra : [];
}

// Tidier alone: the pages of folders that are now Tidier's own, and any Sidebery folder
// page left, are closed once, with nothing else happening to their tabs.
async function closeOldFolderPages() {
  await readAlone();
  if (!tidierAlone) return;
  const pages = (await browser.tabs.query({})).filter(t => isSideberyGroup(t.url));
  if (!pages.length) return; // as at every start but the first: reading every tab's values is left for the start itself
  await loadRoles();
  pages.forEach(t => forget(t.id));
  await removeTabs(pages.map(t => t.id), syncBusy).catch(noteError);
}

// Back to Sidebery, with Sidebery off. The record gets Sidebery's folders back, and Tidier
// starts again without the setting; its folder pages are made then (foldersBackToSidebery).
async function moveBack() {
  if (!tidierAlone) return { refused: "This browser uses Sidebery already." };
  if ((await browser.storage.managed.get("tidierAlone").catch(() => ({}))).tidierAlone) {
    return { refused: "This machine is set to Tidier alone in its setup (managed storage), so it cannot go back from here." };
  }
  const sidebery = await sideberyState();
  if (sidebery === null) return { refused: SIDEBERY_UNSEEN };
  if (sidebery === "missing") return { refused: "Sidebery is not installed. Install it again, turn it off in about:addons, and go back then." };
  // Running, Sidebery would take each page as a new tab of the space it shows, and the
  // tabs that were in the folder would stay outside it (it reads a tab's parent only when
  // the tab is new, or when it starts).
  if (sidebery === "on") return { refused: "Sidebery is on. Turn it off in about:addons first: Tidier puts its folders back while it is off, and you turn it on afterwards." };
  const all = await getSynced();
  const going = foldersGoingBack(all, await sideberyBase(all));
  for (const f of going) {
    const e = all[f.key];
    if (!f.url) { // no address of Sidebery's known for it: its tabs become ordinary tabs, as the page said
      for (const x of Object.values(all)) if (x.parentKey === f.key) x.parentKey = null;
      delete all[f.key];
      continue;
    }
    Object.assign(e, { url: f.url, title: f.name });
    delete e.own; delete e.name; delete e.oldUrl; delete e.rank; delete e.collapsed;
  }
  noteSaved(all);
  saveSynced(all);
  await flushWrites();
  await browser.tabs.show((await browser.tabs.query({ hidden: true })).map(t => t.id)).catch(() => {});
  await takeKeysBack(); // Sidebery's again, the command bar's too (keys-commands.js)
  stopIsolation();
  const kept = going.filter(f => f.url);
  await browser.storage.local.set({
    tidierAlone: false, placeholdersNeedPages: true, foldersBack: kept.map(f => f.key),
    movedNote: { kind: "back", folders: kept.length, closed: kept.filter(f => f.closed).length, lost: going.filter(f => !f.url).map(f => f.name), windows: (await normalWindows()).length },
  });
  browser.runtime.reload();
  return { moving: true };
}

// After going back, at the start, with Sidebery still off: each window gets its folder pages,
// unloaded, each right before the tabs in it, and every tab an opener (openerTabId) that makes
// Sidebery's tree once it is turned on. Sidebery takes a tab's parent only when the tab is
// created, or when its sidebar starts in a window and the tab has no parent of its own there
// (restoreTabsState, 5.6): then the opener is the parent, if it comes before the tab. A tab
// Sidebery has never seen, such as a page made now, goes to the space its sidebar shows,
// unless it has such a parent: so a page, and any other tab, has an essential of its own
// space as its opener (Sidebery makes a pinned tab nobody's parent). A tab in a folder has its
// folder's page. Running, Sidebery would only have taken the pages as new tabs.
async function foldersBackToSidebery() {
  if (tidierAlone) return;
  const { foldersBack } = await browser.storage.local.get("foldersBack");
  if (!Array.isArray(foldersBack)) return;
  const all = await getSynced();
  const folders = foldersBack.filter(k => all[k]?.group && !isOwnFolder(all[k]));
  for (const w of await normalWindows()) await foldersBackIn(w.id, all, folders).catch(err => { if (!isGone(err)) noteError(err); });
  await browser.storage.local.remove("foldersBack");
}

async function foldersBackIn(windowId, all, folders) {
  const query = async () => (await browser.tabs.query({ windowId })).sort((a, b) => a.index - b.index);
  let tabs = await query();
  const reps = repMap(tabs);
  const keyOf = t => syncKeyByTab.get(t.id);
  for (const key of folders) {
    if (reps.has(key)) continue;
    const e = all[key];
    const first = tabs.find(t => !t.pinned && all[keyOf(t)]?.parentKey === key) ?? tabs.find(t => !t.pinned && t.cookieStoreId === e.cookieStoreId);
    const page = await createTab({ windowId, url: groupBaseUrl(e.url), title: groupName(e.url) || e.title, cookieStoreId: e.cookieStoreId, active: false, discarded: true, ...(first ? { index: first.index } : {}) });
    if (!page) return; // the window closed meanwhile
    syncBusy.add(page.id);
    setTimeout(() => syncBusy.delete(page.id), SETTLE_MS);
    await setRole(page.id, key, "copy");
    reps.set(key, page.id);
    tabs = await query();
  }
  // Sidebery's order: each space one run, its folders first, each right before its tabs.
  const parentOf = t => reps.get(all[keyOf(t)]?.parentKey);
  const unpinned = tabs.filter(t => !t.pinned), firstUnpinned = tabs.length - unpinned.length;
  const order = treeOrder(unpinned.map(t => ({ id: t.id, parent: parentOf(t), space: t.cookieStoreId, folder: isSideberyGroup(t.url) })));
  const moved = [];
  for (const [i, id] of order.entries()) {
    const at = (await browser.tabs.get(id).catch(() => null))?.index;
    if (at === undefined || at === firstUnpinned + i) continue;
    ownFolderMoves.add(id); syncBusy.add(id); moved.push(id); // folders.js, tabsync.js: not yours
    await browser.tabs.move(id, { windowId, index: firstUnpinned + i }).catch(ifGone);
  }
  setTimeout(() => moved.forEach(id => { ownFolderMoves.delete(id); syncBusy.delete(id); }), SETTLE_MS);
  const essentialOf = new Map();
  for (const t of tabs) if (t.pinned && !essentialOf.has(t.cookieStoreId)) essentialOf.set(t.cookieStoreId, t.id);
  for (const t of (await query()).filter(t => !t.pinned)) {
    const opener = parentOf(t) ?? essentialOf.get(t.cookieStoreId) ?? t.id;
    if (t.openerTabId !== opener) await browser.tabs.update(t.id, { openerTabId: opener }).catch(ifGone);
  }
}

// Placeholders made with Tidier alone have no page (placeholderWithoutPage), but Sidebery
// draws the tab itself. Once, after moving back and with Tidier started again, those
// without an icon load their page, which sets title and icon and unloads itself.
async function pagesAfterMovingBack() {
  if (tidierAlone || !(await browser.storage.local.get("placeholdersNeedPages")).placeholdersNeedPages) return;
  for (const t of await browser.tabs.query({ discarded: true })) {
    if (isGhostUrl(t.url) && !t.favIconUrl) await browser.tabs.update(t.id, { url: t.url }).catch(() => {});
  }
  await browser.storage.local.remove("placeholdersNeedPages");
}

// Moving closes the settings page (Tidier starts again), so it is opened again once Tidier has
// started, to say what happened and what is left to do. Once: the note goes as it is shown.
async function afterMoving() {
  const { movedNote } = await browser.storage.local.get("movedNote");
  if (!movedNote || movedNote.opened) return;
  await browser.storage.local.set({ movedNote: { ...movedNote, opened: true } });
  await browser.runtime.openOptionsPage().catch(noteError);
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
// address, the channel suffix it adds to a page it has open (groupBaseUrl), and the
// ":id:" of older versions, which its snapshot drops from an open page but not from an
// unloaded one. The same name in two spaces gives one address, so the space is part of the key.
const foldKey = (space, url) => `${space}|${(url || "").split("/sidebery/")[1]?.replace(/~!.*!~$/, "").replace(/(?::id:|%3Aid%3A).*$/, "")}`;

// Which folders the newest readable snapshot has closed, as foldKeys; null if the export
// has no snapshot. Each window has its own page of a folder, and a new window opens all of
// them, so a folder closed where you work is often open in another. A folder here is the
// same in every window, so one closed in any window comes over closed: a closed folder only
// rests (foldrest.js), and opening it again loses nothing. `here` gives a container's id here.
function closedFolders(backup, here) {
  const snapshots = listIn(backup?.snapshots);
  let tabs = null;
  for (let n = snapshots.length - 1; n >= 0 && !tabs; n--) tabs = snapshotTabs(snapshots, n);
  if (!tabs) return null;
  const closed = new Set();
  for (const t of tabs) {
    const space = here(t.containerId ?? NO_CONTAINER);
    if (isSideberyGroup(t.url) && space && t.folded) closed.add(foldKey(space, t.url));
  }
  return [...closed];
}

// Null for a file that is not Sidebery's export. Folds are applied at once if this
// browser has moved over, else kept in storage until moveOver applies them: until then
// the folders are Sidebery's, and Tidier's mark on them would mean nothing.
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
  // What is new is counted, so that taking in the same export again says that nothing is.
  const localOrder = order.map(here).filter(Boolean);
  const before = await browser.storage.local.get(["spaceOrder", "importedFolds"]);
  const orderChanged = localOrder.length && localOrder.join() !== listIn(before.spaceOrder).join();
  if (orderChanged) await browser.storage.local.set({ spaceOrder: localOrder });

  const closed = closedFolders(backup, here);
  let folds = null, newFolds = 0;
  if (closed) {
    const all = await getSynced(), keys = new Set(closed);
    const matched = Object.keys(all).filter(k => all[k].group && keys.has(foldKey(all[k].cookieStoreId, all[k].oldUrl ?? all[k].url)));
    const waiting = new Set(listIn(before.importedFolds));
    newFolds = matched.filter(k => tidierAlone ? !all[k].collapsed : !waiting.has(foldKey(all[k].cookieStoreId, all[k].url))).length;
    if (tidierAlone) for (const k of matched) await foldFolder(k, true); // ownfolders.js
    else await browser.storage.local.set({ importedFolds: closed });
    folds = matched.length;
  }
  // Which containers had a space in Sidebery: one that had none is hidden at the move, if
  // it holds nothing (spacesSideberyHadNot). And that step 1 of moving over is done.
  const panelSpaces = [...new Set(Object.values(panels).map(panelContainer).map(id => id && here(id)).filter(Boolean))];
  await browser.storage.local.set({ sideberyImported: Date.now(), ...(panelSpaces.length ? { sideberyPanels: panelSpaces } : {}) });
  viewAllSoon(); // the bar's order, if nothing else
  return { rules: added.length, order: orderChanged ? localOrder.length : 0, panelsLeftOut, newSpaces, folds, newFolds };
}

// --- The settings page -------------------------------------------------------------
browser.runtime.onMessage.addListener((msg, sender) => {
  if (!msg?.type?.startsWith("settings:") || sender.id !== browser.runtime.id || !sender.url?.startsWith(browser.runtime.getURL(""))) return;
  return serial(() => settingsAction(msg));
});

async function settingsAction(msg) {
  switch (msg.type.slice("settings:".length)) {
    case "get": {
      const stored = await browser.storage.local.get(["archiveAfterHours", "lastCopy", "movedNote"]);
      // What moving over or back did, said once on the page it opens (afterMoving).
      if (stored.movedNote?.opened) await browser.storage.local.remove("movedNote");
      const network = notices.has("spaceNetwork") ? await spaceNetwork.get() : {}; // isolation.js: which spaces that notice is about
      return {
        report: await moveReport(), rules: await rulesList.get(), spaces: await containerSpaces(), archiveHours: archiveHours(stored.archiveAfterHours),
        lastCopy: stored.lastCopy ?? null, version: browser.runtime.getManifest().version, hiding: !!browser.tabs.hide,
        notices: [...notices].map(([kind, text]) => ({ kind, text })),
        network: Object.entries(network).filter(([, n]) => n?.proxy || n?.userAgent).map(([id, n]) => ({ id, proxy: !!n.proxy, userAgent: !!n.userAgent })),
        moved: stored.movedNote?.opened ? stored.movedNote : null, started,
        // The bar's order (spaces.js), which the page's lists of spaces follow.
        order: tidierAlone ? (await spaceList(new Set((await containerSpaces()).map(s => s.id)))).map(s => s.id) : [],
      };
    }
    case "archiveHours": { // what is stored, which the page then shows: an hour count that is no answer changes nothing
      const hours = archiveHoursFrom(msg.hours);
      if (hours !== null) await browser.storage.local.set({ archiveAfterHours: hours });
      return archiveHours((await browser.storage.local.get("archiveAfterHours")).archiveAfterHours);
    }
    case "rules": rulesList.set(msg.rules.filter(r => r.url && r.space).map(r => ({ url: r.url, space: r.space }))); setNotice("rule", null); viewAllSoon(); return true;
    case "space": await browser.contextualIdentities.update(msg.id, msg.changes).catch(noteError); return true;
    case "moveOver": return moveOver();
    case "moveBack": return moveBack();
    case "sidebery": return sideberyState();
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
