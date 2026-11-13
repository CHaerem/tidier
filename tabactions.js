// What the menu on a tab does (sidebar/tabmenu.js).
//
// A row or a tile is not its tab. A row can be a placeholder, with the real page in
// another window, unloaded, or nowhere yet; a tile is one window's copy of an essential,
// with the loaded copy perhaps elsewhere. A placeholder's own address is ghost.html, and
// its own sound and last use say nothing. So everything here starts from realOf, and
// acts on the real tab, in whichever window that is.

// The tab behind a row or a tile.
//   own      the tab the row stands for in this window
//   tab      the real tab: the live one, or an essential's loaded copy; else `own`
//   key, entry   its record (the tab record, or the list of essentials), if it has one
//   address  the page's web address (null for a page that has none, like a new tab)
//   title    what the page is called
//   loaded   whether the page is really loaded, in some window
//   space    its container
async function realOf(tabId) {
  const own = await browser.tabs.get(tabId).catch(() => null);
  if (!own) return null;
  let key, entry = null, tab = own;
  if (own.pinned) {
    // (Firefox refuses to read the values of a tab closed a moment ago.)
    key = await keyOf(own).catch(() => undefined);
    entry = (await getList()).find(e => e.key === key) ?? null;
    // Its own page if it has one: for a moment two copies can be loaded (oneLoaded), and
    // an action on this tile must not land on the other.
    if (entry && !isLoadedCopy(own)) tab = (await copiesOf(key).catch(() => [])).find(isLoadedCopy) ?? own;
  } else {
    key = syncKeyByTab.get(tabId);
    entry = key ? (await getSynced())[key] ?? null : null;
    const liveId = entry ? liveTabId(key) : undefined;
    if (liveId !== undefined) tab = await browser.tabs.get(liveId).catch(() => null) ?? own;
  }
  return {
    own, tab, key, entry,
    address: [tab.url, entry?.url, own.url].find(isWeb) ?? null,
    title: entry?.name || entry?.title || tab.title || "",
    // A new tab page is no page to reload, mute or unload.
    loaded: isLoadedCopy(tab) && !NEW_TAB_PAGES.has(tab.url),
    space: entry?.cookieStoreId ?? own.cookieStoreId,
  };
}

// What the menu needs to know, asked for when it opens: whether a page is loaded or
// muted can change in a window this sidebar gets no view for, so a view cannot say.
//
// `duplicates`, the same on each: how many of today's tabs in the window of the first
// repeat one drawn before them (doublesIn, listactions.js), for More's Close duplicates.
async function tabMenuFacts(tabIds) {
  const all = await getSynced(), rules = await rulesList.get();
  const reals = (await Promise.all(tabIds.map(realOf))).filter(Boolean);
  const view = reals.length ? await viewFor(reals[0].own.windowId).catch(() => null) : null;
  const duplicates = view ? doublesIn(view, all).length : 0;
  return reals.map(r => ({
    id: r.own.id,
    tile: r.own.pinned,
    active: r.own.active,
    kept: r.own.pinned || !!r.entry?.saved,
    away: awayFromSaved(r),
    loaded: r.loaded,
    muted: !!r.tab.mutedInfo?.muted,
    address: r.address,
    folder: r.own.pinned ? null : folderKeyOf(all, r.key),
    liveFolder: !!r.entry?.liveFolder,
    space: r.space,
    ruled: !!r.address && rules.find(rule => ruleMatches(rule.url, r.address))?.space === r.space,
    duplicates,
  }));
}
// Whether a kept tab is somewhere other than the address kept for it. A saved tab by its
// record (leftSaved, common.js). An essential's address never follows its page, so it is
// its loaded copy that says where it is; one that is not loaded is nowhere else.
const awayFromSaved = r => (r.own.pinned ? r.loaded && !!r.entry && isWeb(r.tab.url) && !samePage(r.tab.url, r.entry.url) : leftSaved(r.entry));

browser.runtime.onMessage.addListener((msg, sender) => {
  if (msg?.type !== "tabMenu" || sender.id !== browser.runtime.id || !sender.url?.startsWith(browser.runtime.getURL(""))) return;
  return tabMenuFacts(msg.tabIds);
});

// Which tab to close for a row. A saved tab closed while it is unloaded is removed for
// good, so closing only its placeholder here, with the page loaded in another window,
// would lose it where closing the page itself only unloads it.
async function closeTargetOf(tabId) {
  const real = await realOf(tabId).catch(noteError); // a × must close something, whatever else went wrong
  return real?.loaded ? real.tab.id : tabId;
}

// What the menu asks for: { action, tabIds, ... }, one list for one tab or many.
async function tabAction(windowId, { action, tabIds, ...more }) {
  const reals = (await Promise.all(tabIds.map(realOf))).filter(Boolean);
  if (reals.length) await TAB_ACTIONS[action]?.(windowId, reals, more);
}

const TAB_ACTIONS = {
  // A few at a time, outside the queue (reloadGently, listactions.js): a whole folder at once
  // would load every page together.
  reload: (windowId, reals) => { reloadGently(reals.filter(r => r.loaded).map(r => r.tab.id)); },
  mute: (windowId, reals) => setRealsMuted(reals, true),
  unmute: (windowId, reals) => setRealsMuted(reals, false),
  unload: unloadReals,
  duplicate: async (windowId, reals) => { for (const r of reals) await duplicateReal(r); },
  // The listeners that make a pinned tab an essential ignore a tab Tidier is busy with, and
  // a tab just moved or made stays marked so for a moment (syncBusy, busy). This change is
  // yours: missed, the tab would be an essential and an ordinary tab at once, for good.
  essential: async (windowId, reals) => {
    // The real tab, so a page loaded in another window stays loaded as the essential.
    for (const r of reals) {
      if (!r.address || r.own.pinned) continue;
      syncBusy.delete(r.tab.id);
      await browser.tabs.update(r.tab.id, { pinned: true }).catch(() => {});
    }
  },
  removeEssential: async (windowId, reals) => {
    for (const r of reals) {
      if (!r.own.pinned) continue;
      busy.delete(r.tab.id);
      unpinYourself(r.tab.id); // essentials.js: the other windows follow at once
      await browser.tabs.update(r.tab.id, { pinned: false }).catch(() => {});
    }
  },
  // A folder deleted in another window while this menu was open: a tab whose folder is not
  // there is drawn as an ordinary tab and stops being saved, so nothing moves.
  folder: async (windowId, reals, { folder }) => {
    if (!folder || isOwnFolder((await getSynced())[folder])) await moveRealsTo(windowId, reals, folder ?? null);
  },
  // Only what a folder can keep: the menu offers it for those alone, but a key or the command
  // bar can be pressed on an essential or a live folder's tab.
  newFolder: async (windowId, reals, { space }) => {
    const movable = reals.filter(r => !r.own.pinned && r.address && !r.entry?.liveFolder);
    if (movable.length && space) await moveRealsTo(windowId, movable, await createFolder(folderNameFor(movable), space));
  },
  // Out of the folder they are in, to the end of today's tabs, as Move to folder's No folder.
  // A tab in no folder stays where it is.
  takeOut: async (windowId, reals) => {
    const all = await getSynced();
    await moveRealsTo(windowId, reals.filter(r => !r.own.pinned && !r.entry?.liveFolder && folderKeyOf(all, r.key)), null);
  },
  space: (windowId, reals, { space, newSpace, at }) => moveRealsToSpace(windowId, reals, space, { newSpace, at }),
  backToSaved: async (windowId, reals) => { for (const r of reals) await backToSaved(r); },
  saveHere: (windowId, reals) => saveHere(windowId, reals[0]),
  rule: (windowId, reals) => alwaysOpenHere(windowId, reals[0]),
  // What More holds, the folder's and the space's menus, the command bar and the keys
  // (listactions.js). They go by the rows: what is drawn where, and in which order.
  sort: (windowId, reals, { by }) => sortTabs(windowId, reals.map(r => r.own.id), by),
  top: (windowId, reals) => moveAlong(windowId, reals.map(r => r.own.id), "top"),
  bottom: (windowId, reals) => moveAlong(windowId, reals.map(r => r.own.id), "bottom"),
  step: (windowId, reals, { by }) => moveAlong(windowId, reals.map(r => r.own.id), by < 0 ? -1 : 1),
  closeOthers: (windowId, reals) => closeAround(windowId, reals.map(r => r.own.id), "others"),
  closeAbove: (windowId, reals) => closeAround(windowId, reals.map(r => r.own.id), "above"),
  closeBelow: (windowId, reals) => closeAround(windowId, reals.map(r => r.own.id), "below"),
  closeDuplicates: (windowId, reals) => closeAround(windowId, reals.map(r => r.own.id), "duplicates"),
  // A folder's tabs, closed for good with one line to take them back: closing a saved tab
  // one by one would only unload it.
  closeAll: (windowId, reals) => closeRows(windowId, reals.map(r => r.own.id)),
  copy: (windowId, reals) => copyText(reals.filter(r => r.address).map(r => r.address).join("\n")),
  copyMarkdown: (windowId, reals) => copyText(reals.filter(r => r.address).map(r => markdownLink(r.title, r.address)).join("\n")),
};

// A kept tab back on the address kept for it, as closing it would take it, but without
// closing it: the page is loaded there. Firefox's own Back goes the other way again.
// With no page anywhere (only placeholders, the window that had it closed), the record goes
// back, and the placeholders show the saved page again, as after a close (unloadSaved).
async function backToSaved(r) {
  if (!awayFromSaved(r)) return;
  if (r.own.pinned) return void await browser.tabs.update(r.tab.id, { url: r.entry.url }).catch(() => {});
  if (!isGhostUrl(r.tab.url)) return void await browser.tabs.update(r.tab.id, { url: r.entry.saved.url }).catch(() => {});
  const all = await getSynced();
  if (!all[r.key]?.saved) return;
  Object.assign(all[r.key], all[r.key].saved);
  saveSynced(all);
  await redrawPlaceholders(await repsNow(r.key)); // tabnames.js
}

// The address a kept tab is on now becomes the one kept for it: what closing it takes it
// back to, and what its placeholders open. One line says so, with Undo, as it changes
// something that lasts and shows nowhere else (a tile is only an icon).
async function saveHere(windowId, r) {
  if (!awayFromSaved(r)) return;
  if (r.own.pinned) {
    const { url, title, icon, name } = r.entry;
    const put = async fields => {
      const list = await getList(), entry = list.find(e => e.key === r.key);
      if (!entry) return; // no longer an essential
      Object.assign(entry, fields);
      setList([...list]);
      viewAllSoon(); // the list, unlike the record, tells no sidebar by itself
      await redrawPlaceholders(await copiesOf(r.key));
    };
    await put({ url: r.tab.url, title: r.tab.title || title, icon: r.tab.favIconUrl || icon });
    return say(windowId, `Saved here: ${name || r.tab.title || title}`, { undo: () => put({ url, title, icon }) });
  }
  const all = await getSynced(), entry = all[r.key];
  const before = { ...entry.saved };
  entry.saved = { url: entry.url, title: entry.title, icon: entry.icon };
  saveSynced(all);
  viewAllSoon();
  say(windowId, `Saved here: ${entry.name || entry.title}`, { undo: async () => {
    const now = await getSynced();
    if (!now[r.key]?.saved) return; // taken out of its folder meanwhile: nothing is saved for it
    now[r.key].saved = before;
    saveSynced(now);
    viewAllSoon();
  } });
}

async function setRealsMuted(reals, muted) {
  for (const r of reals) if (r.loaded) await browser.tabs.update(r.tab.id, { muted }).catch(() => {});
}

// Tabs to another space, from the menu, a drop on a dot or the command bar alike, with one
// line for all of them that says where they went, and Undo. Without it a tab would just
// vanish from the list, and a move made by mistake would have to be looked for.
//
// In order, so that they arrive in order; the selected tab must then not step onto one
// still to come (leavesQuietly, safemoves.js). A row can be a placeholder, so both ids count.
//
// Undo moves each back as it is by then (reopenIn, safemoves.js), into the folder it was in
// and to its place there, with its saved address and its name, as if it had never left.
const MOVE_FIELDS = ["parentKey", "saved", "name", "added", "liveFolder", "liveUrl"];
const copyOf = value => (value && typeof value === "object" ? { ...value } : value); // a saved address is the one object among them
//
// `at` ({ before, folder }): a place in that space's list, where a drag that went to the space
// put the tab down (drag.js). Each is put there once it has arrived, as a drop in its own
// space would put it, so in every window; without it they land at the end of today's tabs.
async function moveRealsToSpace(windowId, reals, space, { newSpace = false, at = null } = {}) {
  const leaving = reals.flatMap(r => [r.own.id, r.tab.id]);
  const order = await tabsNow(windowId); // quiet.js: where each was, to put it back
  const moved = [];
  let stayed = 0, gone = 0;
  for (const r of reals) {
    await register(r.own.id); // opened a moment ago, it has no record yet
    const key = syncKeyByTab.get(r.own.id), entry = key ? (await getSynced())[key] : undefined;
    const was = entry ? { key, from: entry.cookieStoreId, fields: Object.fromEntries(MOVE_FIELDS.map(f => [f, copyOf(entry[f])])) } : null;
    const result = await moveToSpace(r.own.id, space, leaving, { quiet: true });
    if (result === "moved" && was && at) {
      const there = repMap(await browser.tabs.query({ windowId })).get(key);
      if (there !== undefined) await moveTab(windowId, there, at.before ?? null, at.folder ?? null).catch(noteError);
    }
    if (result === "moved" && was) moved.push(was);
    else if (result === "stayed") stayed++;
    else if (result === "gone") gone++;
  }
  if (gone && !moved.length) return say(windowId, "That space could not be opened, so the tab stayed here");
  if (!moved.length) return stayed && sayStayed(windowId);
  const name = newSpace ? "a new space" : (await containerSpaces()).find(s => s.id === space)?.name ?? "that space";
  const tabs = n => (n === 1 ? "1 tab" : `${n} tabs`);
  const text = stayed ? `${tabs(moved.length)} moved to ${name}, ${stayed} stayed` : moved.length === 1 ? `Moved to ${name}` : `${tabs(moved.length)} moved to ${name}`;
  say(windowId, text, { undo: () => moveBackFromSpace(windowId, moved, space, order) });
}

async function moveBackFromSpace(windowId, moved, space, order) {
  const all = await getSynced();
  const back = [];
  for (const { key, from, fields } of moved) {
    const entry = all[key];
    if (entry?.cookieStoreId !== space) continue; // closed or moved on since
    const reps = await repsNow(key);
    const live = reps.find(t => syncRoleByTab.get(t.id) === "live") ?? null;
    const was = pageState(live, reps[0]);
    if (!(await leavesQuietly(live, key, moved.flatMap(m => syncKeyByTab.tabsOf(m.key))))) continue;
    if (!(await reopenIn(key, from, was, all))) continue;
    for (const f of MOVE_FIELDS) { if (fields[f] === undefined) delete entry[f]; else entry[f] = copyOf(fields[f]); }
    // Its folder gone, or gone to another space, meanwhile: an ordinary tab, as when a folder is deleted.
    const folder = all[entry.parentKey];
    if (entry.parentKey && !(isOwnFolder(folder) && folder.cookieStoreId === from)) { entry.parentKey = null; entry.added = Date.now(); }
    noteSaved(all, [key]);
    if (entry.liveFolder) await forgetDismissed(entry); // quiet.js
    back.push(key);
  }
  saveSynced(all);
  // Each in its place, from the last to the first, so that the one it goes before is there already (as bringBack, quiet.js).
  const here = repMap(await browser.tabs.query({ windowId }));
  const wanted = new Set(back);
  for (let n = order.length - 1; n >= 0; n--) {
    if (!wanted.has(order[n].key) || !here.has(order[n].key)) continue;
    const next = order.slice(n + 1).find(t => t.space === order[n].space && here.has(t.key));
    await moveTab(windowId, here.get(order[n].key), next ? here.get(next.key) : null);
  }
}

// A tab opened a moment ago has no record yet, and a move would only change its place.
async function moveRealsTo(windowId, reals, folderKey) {
  for (const r of reals) {
    await register(r.own.id);
    await moveTab(windowId, r.own.id, null, folderKey);
  }
}

// Unloading keeps a tab's place, address and title; only its page goes. Firefox refuses
// to unload the selected tab, so the selection goes first to the tab used last in the
// space, and comes back if the page refuses after all (unsaved input): it would otherwise
// be out of sight, still asking for your attention. Those not selected go first, so that
// the selection goes neither onto a tab about to be unloaded nor, with one that refused
// there to take it, to a new tab.
async function unloadReals(windowId, reals) {
  const pages = reals.filter(r => r.loaded).sort((a, b) => a.tab.active - b.tab.active);
  const leaving = new Set(pages.map(r => r.tab.id));
  let refused = 0;
  for (const { tab } of pages) {
    if (tab.active) await stepAwayFrom(tab, leaving);
    await browser.tabs.discard(tab.id).catch(() => {});
    const now = await browser.tabs.get(tab.id).catch(() => null);
    if (!now || now.discarded) continue;
    refused++;
    leaving.delete(tab.id);
    if (tab.active) await browser.tabs.update(tab.id, { active: true }).catch(() => {});
  }
  if (refused) say(windowId, refused > 1 ? `${refused} pages hold unsaved input and stayed loaded` : "This page holds unsaved input and stayed loaded");
}

// Off the selected tab. A placeholder's own last use says nothing, and selecting one
// would load a page just as another is unloaded, so loaded pages come first.
async function stepAwayFrom(tab, leaving) {
  const space = tab.cookieStoreId === NO_CONTAINER ? activeSpace.get(tab.windowId) ?? NO_CONTAINER : tab.cookieStoreId;
  const others = (await browser.tabs.query({ windowId: tab.windowId, cookieStoreId: space })).filter(t => !leaving.has(t.id));
  const next = others.sort((a, b) => isLoadedCopy(b) - isLoadedCopy(a) || (b.lastAccessed || 0) - (a.lastAccessed || 0))[0];
  if (next) await browser.tabs.update(next.id, { active: true }).catch(() => {});
  else await browser.tabs.create({ windowId: tab.windowId, cookieStoreId: space, active: true }).catch(noteError);
}

// A copy is always an ordinary tab, next to the original and not selected. A loaded page
// in this window is duplicated with its history. SessionStore copies Tidier's values along,
// and with them the copy would count as the same tab: it would take over a saved tab's
// record once the original is closed, and be an essential's copy after a restart. Nor is
// the copy a tab's first page: a rule must not send it to another space.
//
// A page loaded in another window is opened again here. Firefox duplicates a tab only in
// its own window, so the copy would be over there, and its row here at the end of the list
// instead of next to the one you clicked.
//
// The queue does not wait for this: Firefox answers when the copy starts to restore, and
// never if the copy is closed first, which would stop everything for minutes. The answer
// still comes before the copy's address is reported, and long before it is registered.
async function duplicateReal(r) {
  if (!r.address) return;
  if (r.loaded && r.tab.windowId === r.own.windowId) {
    browser.tabs.duplicate(r.tab.id, { active: false, index: r.tab.index + 1 }).then(copy => {
      firstPage.delete(copy.id);
      return Promise.all([SYNC_KEY, SYNC_ROLE, TAB_KEY].map(name => browser.sessions.removeTabValue(copy.id, name).catch(() => {})));
    }).catch(noteError);
    return;
  }
  const props = { windowId: r.own.windowId, cookieStoreId: r.space, url: r.address, active: false, index: r.own.index + 1 };
  await openUnruled(props);
}

// A rule for this site and this space. It goes first, so that it wins over an older rule
// that also matches, and is anchored to the start of the address: plain text would also
// match a sign-in passing through with this address in it (see "Tabs in the wrong space"
// in the README).
async function alwaysOpenHere(windowId, r) {
  if (!r.address) return;
  const url = siteRuleText(r.address), before = await rulesList.get();
  rulesList.set([{ url, space: r.space }, ...before.filter(rule => rule.url !== url)]);
  const name = (await containerSpaces()).find(s => s.id === r.space)?.name ?? "this space";
  // The space first: in a narrow sidebar the end of the line is cut, and that is what was asked.
  say(windowId, `${name}: ${new URL(r.address).host.replace(/^www\./, "")} always opens here`, { undo: () => rulesList.set(before) });
}

function siteRuleText(address) {
  const host = new URL(address).host.replace(/^www\./, "");
  return `/^https?:\\/\\/(www\\.)?${host.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\//`;
}

// What people call a site: "github.com" is Github, "bbc.co.uk" Bbc. A name to accept with
// Enter or type over, so a good guess will do; a list of every public suffix would not be
// worth carrying for it. A short label before the last one (co, com, org) is such a suffix.
function siteNameOf(address) {
  let host = "";
  try { host = new URL(address).hostname.replace(/^www\./, ""); } catch (err) { return ""; }
  if (!host || /^[\d.]+$/.test(host) || host.includes(":")) return host; // an IP address has no name
  const labels = host.split(".");
  if (labels.length > 1) labels.pop();
  if (labels.length > 1 && labels.at(-1).length <= 3) labels.pop();
  const name = labels.at(-1);
  return name ? name[0].toUpperCase() + name.slice(1) : host;
}

// A name for a new folder from the tabs going into it ({ title, address }), so that
// Enter accepts it. One tab gives its site. Several give what their titles share, a
// capitalised word of four letters or more ("Jira" in "Jira - Board" and "Backlog - Jira"),
// else the site they share, else the first title.
function folderNameFor(tabs) {
  const titles = tabs.map(t => (t.title || "").trim());
  const words = title => title.match(/\p{Lu}\p{L}{3,}/gu) ?? [];
  const shared = tabs.length > 1 && words(titles[0]).find(word => titles.every(title => words(title).includes(word)));
  const sites = tabs.map(t => siteNameOf(t.address));
  const site = sites.every(s => s === sites[0]) && sites[0];
  // Short: a page decides its title, and this goes in the record and on the row.
  return (shared || site || titles.find(Boolean) || "New folder").slice(0, 40);
}
