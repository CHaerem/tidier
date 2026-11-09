// Moving a browser from Sidebery to Tidier alone (PLAN.md, part D). Never by an
// update, only by your click on the settings page, and in this order:
//
//   1. A report of what will happen, and a copy of everything (copies.js).
//   2. You disable Sidebery yourself: an extension cannot, and with Sidebery still
//      running, closing a folded folder's page would close the tabs in it. So moveOver
//      refuses while Sidebery runs, and moveBack while it does not (sideberyState).
//   3. moveOver: Sidebery's folder pages become Tidier's folders in the record, which
//      is written before anything else happens, and Tidier starts again alone. Only
//      then are the folder pages closed (closeOldFolderPages). A crash at any point
//      leaves either the old record, or the new one and pages that close at the next start.
//      The settings page comes back in front, and says what Firefox asks next (afterMovingOver).
//   4. Sidebery stays installed for a few weeks. moveBack undoes it all.

// Sidebery's id, the same everywhere (it comes from addons.mozilla.org).
const SIDEBERY_ID = "{3c078156-979c-498b-8990-85f7987dd929}";

// "on", "off", or "none" when it is not installed; null when Tidier may not look, which
// takes the optional management permission (asked for in the click that moves).
async function sideberyState() {
  if (!browser.management?.get) return null;
  try {
    return (await browser.management.get(SIDEBERY_ID)).enabled ? "on" : "off";
  } catch (err) {
    return "none"; // Firefox's answer for an add-on that is not there
  }
}
const SIDEBERY_STILL_ON = "Sidebery is still on. Disable it in about:addons first (keep it installed), then move.";
const SIDEBERY_OFF = "Sidebery is off. Enable it in about:addons first: its folders can only come back while it runs.";
const SIDEBERY_GONE = "Sidebery is not installed here. Install it first, then go back.";

async function moveReport() {
  const all = await getSynced();
  const entries = Object.entries(all);
  return {
    alone: tidierAlone,
    canMoveBack: entries.some(([, e]) => e.oldUrl),
    essentials: (await getList()).length,
    tabs: entries.filter(([, e]) => !e.group).length,
    folders: entries.filter(([, e]) => e.group).map(([key, e]) => ({
      name: e.own ? e.name : groupName(e.url), space: e.cookieStoreId, tabs: entries.filter(([k]) => folderKeyOf(all, k) === key).length,
    })),
    rules: (await rulesList.get()).length,
  };
}

// `from`: the settings page's tab, where the page comes back once Tidier has started again.
// Nothing, or why not, in words for the page.
async function moveOver(from) {
  if (tidierAlone) return null;
  if (await sideberyState() === "on") return SIDEBERY_STILL_ON;
  const copy = await makeCopy();
  if (!copy?.saved) await browser.storage.local.set({ copyBeforeMove: await theCopy() }); // no helper here: at least inside Firefox's storage
  const all = await getSynced();
  const closed = new Set(listIn((await browser.storage.local.get("importedFolds")).importedFolds)); // importSidebery
  let rank = 0;
  for (const e of Object.values(all)) {
    if (!e.group || e.own) continue;
    Object.assign(e, { own: true, name: groupName(e.url), oldUrl: e.url, rank: ++rank });
    if (closed.has(foldKey(e.cookieStoreId, e.url))) e.collapsed = true;
  }
  saveSynced(all);
  await flushWrites();
  await browser.storage.local.set({ tidierAlone: true, importedFolds: [], justMoved: { windowId: from?.windowId ?? null, index: from?.index ?? null } });
  await guardAfterReload();
  browser.runtime.reload();
  return null;
}

// --- Right after moving over -----------------------------------------------------------
// Firefox asks about hidden tabs at the first tab Tidier hides, and again at every one
// until it is answered: a note that hangs from the toolbar over the top of the sidebar,
// with "Disable Extension" just where "New tab" is. One click there turns Tidier off, and
// with Sidebery off too the window has no list of tabs at all. Firefox forgets the answer
// whenever the add-on is disabled, and starting again (runtime.reload) is a disable, so
// the question cannot be had before the move. So, at the first start alone, the settings
// page comes back in front first, saying what to choose, and only once it is there are
// tabs hidden (hidingHeld, spaces.js). Until the first switch of space the sidebar says it
// too, in one line: the note may have been closed without an answer, and then comes back.
const HOLD_HIDING_MS = 10000; // the page did not come: hidden anyway
let askHidingLine = false; // the sidebar's line (viewFor, sidebar-view.js)
let movedOver = false; // for the settings page, until Firefox restarts
async function afterMovingOver() {
  const { justMoved } = await browser.storage.local.get("justMoved");
  if (!justMoved) return;
  await browser.storage.local.remove("justMoved");
  if (!tidierAlone) return;
  hidingHeld = true;
  askHidingLine = true;
  setTimeout(() => serial(releaseHiding), HOLD_HIDING_MS);
  // Firefox opens a sidebar again where it was open before Tidier started again: only the
  // window you clicked in (settings.js). One without has no list of tabs, so it shows the
  // page too, with a button for it, and gets it at the first key of Tidier's pressed there.
  movedOver = true;
  const wins = await normalWindows();
  for (const w of wins) if (!(await browser.sidebarAction.isOpen({ windowId: w.id }).catch(() => true))) wantsSidebar.add(w.id);
  const win = wins.find(w => w.id === justMoved.windowId) ?? wins.find(w => w.focused) ?? wins[0];
  if (!win) return;
  const url = browser.runtime.getURL("settings/settings.html#moved");
  for (const w of wins) {
    if (w.id !== win.id && !wantsSidebar.has(w.id)) continue;
    const open = (await browser.tabs.query({ windowId: w.id })).find(t => t.url?.startsWith(url.split("#")[0]));
    const index = w.id === win.id && Number.isInteger(justMoved.index) ? justMoved.index : undefined;
    if (open) await browser.tabs.update(open.id, { url, active: true }).catch(noteError); // Firefox closes it as Tidier stops; just in case it did not
    else await browser.tabs.create({ url, windowId: w.id, index, active: true }).catch(noteError);
  }
  await browser.windows.update(win.id, { focused: true }).catch(() => {});
}

// The key that shows the sidebar, as the settings page writes keys (keys-commands.js).
async function sidebarKey() {
  const shortcut = (await browser.commands.getAll()).find(c => c.name === "_execute_sidebar_action")?.shortcut;
  return shortcut ? prettyKey(shortcut, (await browser.runtime.getPlatformInfo()).os) : "";
}

// The line goes at the first switch of space, or its ×.
function askHidingSeen() {
  if (!askHidingLine) return;
  askHidingLine = false;
  viewAllSoon();
}

// The page says it is there, drawn: a moment for it to be seen, then the question.
const releaseHidingSoon = () => sleep(300).then(() => serial(releaseHiding));

// The settings page is in front and says it (or it never came): now tabs are hidden, and
// Firefox asks, in the window in front. If nothing needed hiding, one tab is hidden and
// shown again, so that it asks now and not later over the sidebar.
async function releaseHiding() {
  if (!hidingHeld) return;
  hidingHeld = false;
  let hidden = 0;
  for (const w of await normalWindows()) hidden += await showSpace(w.id);
  if (hidden || !browser.tabs.hide) return;
  const [front] = await browser.windows.getAll({ windowTypes: ["normal"] }).then(ws => ws.filter(w => w.focused));
  const tab = front && (await browser.tabs.query({ windowId: front.id, pinned: false, hidden: false, active: false }))[0];
  if (!tab) return;
  await browser.tabs.hide(tab.id).catch(() => {});
  await browser.tabs.show(tab.id).catch(() => {});
}

// A window that came over without Tidier's sidebar gets it at the first key of Tidier's
// pressed there: a key, like a click in a page of Tidier's, is what lets an extension open
// a sidebar, and it has to be at once, while the key is being handled. Until the sidebar
// is there (sidebarHere, sidebar-view.js), or Firefox restarts, which brings back each
// window's own sidebar.
const wantsSidebar = new Set(); // windowId
const sidebarHere = windowId => wantsSidebar.delete(windowId);
browser.commands.onCommand.addListener((name, tab) => {
  if (name !== "_execute_sidebar_action" && wantsSidebar.delete(tab?.windowId)) browser.sidebarAction.open().catch(() => {});
});
browser.windows.onRemoved.addListener(id => wantsSidebar.delete(id));

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

// Back to Sidebery: you enable it first, since its folder pages are its own. Each
// window gets its folder pages back, and Tidier starts again without the setting.
async function moveBack() {
  if (!tidierAlone) return null;
  // A folder page opened while Sidebery is off cannot load: Firefox leaves a blank tab named
  // after its address, which Sidebery, once on, takes for an ordinary tab. Every folder would
  // be gone there, and turning Sidebery on afterwards does not mend them.
  const sidebery = await sideberyState();
  if (sidebery === "off") return SIDEBERY_OFF;
  if (sidebery === "none") return SIDEBERY_GONE;
  const all = await getSynced();
  const wins = await normalWindows();
  for (const [key, e] of Object.entries(all)) {
    if (!isOwnFolder(e)) continue;
    if (!e.oldUrl) { // made since the move: Sidebery has no page for it, so its tabs become ordinary tabs
      for (const x of Object.values(all)) if (x.parentKey === key) x.parentKey = null;
      delete all[key];
      continue;
    }
    Object.assign(e, { url: e.oldUrl });
    delete e.own; delete e.name; delete e.oldUrl; delete e.rank; delete e.collapsed;
    for (const w of wins) await createRep(w.id, key, e).catch(noteError);
  }
  noteSaved(all);
  saveSynced(all);
  await flushWrites();
  await browser.tabs.show((await browser.tabs.query({ hidden: true })).map(t => t.id)).catch(() => {});
  await takeKeysBack(); // Sidebery's again, the command bar's too (keys-commands.js)
  stopIsolation();
  await browser.storage.local.set({ tidierAlone: false, placeholdersNeedPages: true });
  browser.runtime.reload();
  return null;
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
  const localOrder = order.map(here).filter(Boolean);
  if (localOrder.length) await browser.storage.local.set({ spaceOrder: localOrder });

  const closed = closedFolders(backup, here);
  let folds = null;
  if (closed) {
    const all = await getSynced(), keys = new Set(closed);
    const matched = Object.keys(all).filter(k => all[k].group && keys.has(foldKey(all[k].cookieStoreId, all[k].oldUrl ?? all[k].url)));
    if (tidierAlone) for (const k of matched) await foldFolder(k, true); // ownfolders.js
    else await browser.storage.local.set({ importedFolds: closed });
    folds = matched.length;
  }
  viewAllSoon(); // the bar's order, if nothing else
  return { rules: added.length, order: localOrder.length, panelsLeftOut, newSpaces, folds };
}

// --- The settings page -------------------------------------------------------------
browser.runtime.onMessage.addListener((msg, sender) => {
  if (!msg?.type?.startsWith("settings:") || sender.id !== browser.runtime.id || !sender.url?.startsWith(browser.runtime.getURL(""))) return;
  // The page is back in front after a move: tabs may be hidden now (afterMovingOver).
  if (msg.type === "settings:moved") return releaseHidingSoon().then(() => true);
  return serial(() => settingsAction(msg, sender));
});

async function settingsAction(msg, sender) {
  switch (msg.type.slice("settings:".length)) {
    case "get": {
      const stored = await browser.storage.local.get(["archiveAfterHours", "lastCopy"]);
      return {
        report: await moveReport(), rules: await rulesList.get(), spaces: await containerSpaces(), archiveHours: stored.archiveAfterHours ?? ARCHIVE_DEFAULT_HOURS,
        lastCopy: stored.lastCopy ?? null, version: browser.runtime.getManifest().version, hiding: !!browser.tabs.hide, notices: [...notices.values()],
        sidebery: await sideberyState(), moved: movedOver && { noSidebar: [...wantsSidebar], sidebarKey: await sidebarKey() },
      };
    }
    case "archiveHours": await browser.storage.local.set({ archiveAfterHours: Number(msg.hours) }); return true;
    case "rules": rulesList.set(msg.rules.filter(r => r.url && r.space).map(r => ({ url: r.url, space: r.space }))); setNotice("rule", null); viewAllSoon(); return true;
    case "space": await browser.contextualIdentities.update(msg.id, msg.changes).catch(noteError); return true;
    case "moveOver": return { refused: await moveOver(sender.tab) };
    case "moveBack": return { refused: await moveBack() };
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
