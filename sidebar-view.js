// Tidier's own sidebar (sidebar/), like Zen and Arc: the active space's
// essentials at the top, its folders and tabs below, and the spaces at the
// bottom. This part runs in the background: it builds each window's view and
// sends it to that window's sidebar whenever something it shows changes, and
// carries out what you do there.
//
// A space is a Firefox container (spaces.js): its name, colour and icon are the
// container's own (Firefox's settings, or the container menu).
//
// The order shown is the window's tab order. Folders are Tidier's own (ownfolders.js),
// read from tab sync's record.

const sidebarPorts = new Map(); // windowId -> Set of ports (a window has one sidebar; a reload may briefly add a second)
const viewTimers = new Map(); // windowId -> { timer, first }: the next view, and when it was first asked for
const viewsBuilding = new Map(); // windowId -> { since, changed }: the view being built, and whether something changed meanwhile
const viewRest = new Map(); // windowId -> not before when its next view is built
const VIEW_DEBOUNCE_MS = 30; // a burst of tab events becomes one view...
const VIEW_LONGEST_WAIT_MS = 250; // ... and a long burst still shows, every so often
// Times what the last view took, so that views never take most of the time, however
// many tabs. With a limit: a view is slow when Firefox is busy, and what you just did
// must still show soon after.
const VIEW_REST = 3, VIEW_LONGEST_REST_MS = 1000;
const VIEW_STUCK_MS = 15000; // a view Firefox never answers for must not leave a sidebar frozen

// What a tab's tooltip says: its title, then its address without the query part, which
// is seldom readable and may hold a token. A placeholder's own address is ghost.html and
// its own title may be too, so they come from the record (`entry`: the synced tab's, or the
// essential's); a loaded page's own address is newer than the record's.
const TIP_ADDRESS_MAX = 300; // a data: address can be megabytes, and every view would carry it
function tabTip(t, entry) {
  const placeholder = isGhostUrl(t.url);
  const url = (placeholder ? entry?.url : t.url) || "";
  const title = entry?.name || entry?.title || (placeholder ? "" : t.title) || "";
  const bare = url.replace(/\?[^#]*/, "");
  const address = bare.length > TIP_ADDRESS_MAX ? bare.slice(0, TIP_ADDRESS_MAX) + "…" : bare;
  return (title === url || title === address ? [address] : [title, address]).filter(Boolean).join("\n");
}

// Firefox's own spinner goes by the same thing (status is the tab's busy attribute). A
// placeholder "loads" only the tiny local page that gives it a title and an icon.
const tabIsLoading = t => t.status === "loading" && !t.discarded && !isGhostUrl(t.url);

// What the sidebar shows of a tab. A placeholder's own title and icon are the
// page's (see ghost.js); an essential or a saved tab shows its name if it has one (tabnames.js).
// A placeholder has no page (createRep, tabsync.js), and Firefox drops a tab's icon when a
// new page comes in, so the record's comes next, before a letter (iconForView,
// isolation.js; recordIcon below).
const tabItem = (t, title, entry) => ({
  id: t.id, title: title || t.title || t.url,
  icon: iconForView(t, entry), // isolation.js
  tip: tabTip(t, entry),
  active: t.active, loaded: !t.discarded && !isGhostUrl(t.url), audible: !!t.audible, muted: !!t.mutedInfo?.muted,
  sound: ownSound(t), soundTabId: t.id, // what a row shows: the real page's (addSounds)
  news: hasNews(t.id),
  page: isWeb(t.url) || isGhostUrl(t.url), // else a new tab page or the like, which only has a place among the tabs (drag.js)
  blank: NEW_TAB_PAGES.has(t.url) || undefined, // an empty new tab: no page yet, so no letter of a name that is not one (sidebar.js icon)
  note: forYouNotes.get(syncKeyByTab.get(t.id)), // bridge.js
  pr: entry?.liveFolder ? entry.pr || "open" : undefined, // a live folder's pull request: what it waits for (liveState, livefolders.js)
  away: leftSaved(entry) ? entry.saved.title || entry.saved.url : undefined, // a saved tab off its saved page (common.js): what that page is called
});

// The icon in the record, for a placeholder that has none of its own (createRep,
// tabsync.js). One from Firefox's own icon cache (page-icon:) cannot be shown in an
// extension's page, so then the site's, which is what ghost.js would look for. (By
// its origin: this is asked for outside the tab's container, and a login in the address
// must not go along. A record taken in from a copy can hold any address, and one
// that cannot be read must not stop the whole sidebar from drawing.)
const viewableIcon = icon => /^(https?:|data:|moz-extension:)/.test(icon || "") ? icon : null;
function recordIcon(entry) {
  if (!entry) return null;
  if (viewableIcon(entry.icon)) return entry.icon;
  try { return isWeb(entry.url) ? new URL(entry.url).origin + "/favicon.ico" : null; } catch { return null; }
}

// A tab you close with ⌘W (or Firefox's own ways) plays a short animation first, and all that
// time Firefox still lists it (tabs.query goes by the tab strip, which holds it until the
// end). The view asked for by onRemoved comes in that moment, and no event follows when the
// tab has really gone: its row would stay, dead, and a saved tab's would be there twice,
// with its new placeholder. So a tab Firefox has said is removed is never in a view, for
// REMOVED_KEPT_MS, which is far longer than the animation. (× closes with tabs.remove, which
// has no animation; with less motion asked for, nothing has.)
const REMOVED_KEPT_MS = 5000;
const removedTabs = new Set();
browser.tabs.onRemoved.addListener(tabId => {
  removedTabs.add(tabId);
  setTimeout(() => removedTabs.delete(tabId), REMOVED_KEPT_MS);
});
const queryShown = async query => (await browser.tabs.query(query)).filter(t => !removedTabs.has(t.id));

// `apart`: a space other than the window's own, for a glimpse of it (below).
async function viewFor(windowId, apart) {
  // Read first: a view that has it was built entirely after that drop was carried out, so the
  // sidebar can stop putting the row where it was dropped itself (sidebar/drag.js).
  const landed = landedIn.get(windowId) ?? null;
  const list = await getList();
  // Firefox builds a full description of every tab it is asked for, so a view asks only
  // for the space it shows, unless the bar itself depends on the other tabs (spaceList).
  const whole = Array.isArray(await declaredSpaces()) ? await queryShown({ windowId }) : null;
  // Spaces in use: a container with essentials or tabs (also the empty ones are shown).
  const used = new Set(whole ? [...list.map(e => e.cookieStoreId), ...whole.map(t => t.cookieStoreId)] : []);
  const spaces = await spaceList(used);
  const space = apart ?? await spaceOf(windowId, whole, spaces);
  for (const s of spaces) s.news = s.id !== space && spaceHasNews(s.id); // the space you are in shows it in its list
  // Of the space shown: its own tabs, those without a container, and a hidden space's
  // (shownInSpace, hiddenspaces.js), which show wherever you are.
  const tabs = (whole ?? await queryShown({ windowId, cookieStoreId: [...(space ? [space] : []), NO_CONTAINER, ...hiddenSpaceIds] })).sort((a, b) => a.index - b.index);
  // Asked now, of the same moment as `tabs`: once the tab is gone it is no longer in newTabs,
  // and by the line that uses this it may be, while `tabs` still has it.
  const reopening = new Set(tabs.filter(reopensSoon).map(t => t.id));

  const rank = new Map(list.map((e, i) => [e.key, i]));
  const byEssentialKey = new Map(list.map(e => [e.key, e]));
  const pinned = tabs.filter(t => t.pinned && shownInSpace(t, space));
  const keys = await Promise.all(pinned.map(keyOf));
  const essentials = pinned.map((t, i) => ({ t, entry: byEssentialKey.get(keys[i]) }))
    .sort((a, b) => (rank.get(a.entry?.key) ?? Infinity) - (rank.get(b.entry?.key) ?? Infinity))
    .map(({ t, entry }) => tabItem(t, entry?.name || entry?.title, entry));

  // A tab without a container (a new tab) belongs to the space you are in.
  const all = await getSynced();
  const here = tabs.filter(t => !t.pinned && shownInSpace(t, space) && !reopening.has(t.id)); // hiddenspaces.js
  const folders = foldersOf(all, space).map(f => ({ key: f.key, name: f.name, collapsed: !!f.collapsed, live: f.live || null, tabs: [] }));
  const byKey = new Map(folders.map(f => [f.key, f]));
  const rowKey = await rowKeys(here);
  const standIns = started ? await restoredInPlace(here, all) : new Map();
  const replaced = new Set(standIns.values());
  const loose = [];
  for (const t of here) {
    if (replaced.has(t.id)) continue;
    const key = rowKey.get(t.id) ?? (standIns.has(t.id) ? restoredKeys.get(t.id) : undefined);
    // A new tab made in a folder has no record until it has a page (comingIntoFolder, listactions.js).
    const folder = byKey.get(folderKeyOf(all, key) ?? (key === undefined ? comingIntoFolder.get(t.id) : null));
    const record = all[key];
    (folder ? folder.tabs : loose).push(tabItem(t, record?.name || record?.title, record));
  }
  for (const f of folders) f.news = f.tabs.some(t => t.news);
  await addSounds({ essentials, folders, tabs: loose, spaces, space }, windowId);
  // Tabs still loading go apart from their rows: a row is drawn again when anything in it
  // changes, and a load starting and ending must not replace its icon (sidebar/touches.js).
  const loading = tabs.filter(tabIsLoading).map(t => t.id);
  return { needsHiding: !browser.tabs.hide, askHiding: askHidingLine, problem: [...notices.values()][0] ?? null, restart: restartLine(), note: noteFor(windowId), spaces, space, essentials, folders, tabs: loose, loading, little: await littleRows(spaces), landed };
}
const landedIn = new Map(); // windowId -> the name of the last drop carried out there

// A space next to the one a window shows, as its sidebar would draw it once you are there:
// a swipe on the trackpad brings it in beside the list, following the fingers
// (sidebar/swipe.js), before anything is switched. Its selected tab is the one a switch
// would go back to (switchSpace, spaces.js). Asked for when a swipe begins, and built as
// a view is: nothing is kept ready for it, since with nothing happening Tidier does nothing.
async function glimpseOf(windowId, space) {
  if (!(await containerSpaces()).some(s => s.id === space) || !await browser.windows.get(windowId).catch(() => null)) return null;
  const { essentials, folders, tabs } = await viewFor(windowId, space);
  const back = (await lastUsedIn(windowId, space))?.id;
  for (const item of [...essentials, ...folders.flatMap(f => f.tabs), ...tabs]) item.active = item.id === back;
  return { space, essentials, folders, tabs };
}
browser.runtime.onMessage.addListener((msg, sender) => {
  if (msg?.type !== "glimpse" || sender.id !== browser.runtime.id || !sender.url?.startsWith(browser.runtime.getURL(""))) return;
  return glimpseOf(msg.windowId, msg.space).catch(err => (console.error("Tidier: glimpse", err), null));
});

// A tab Firefox gives back (⌘⇧T) has its key among its values at once, but Tidier takes it
// in only once it has settled (registerSoon, tabsync.js). A saved tab's comes back next to the
// placeholder its ⌘W left (unloadSaved), and until it is taken in it would be drawn as a new
// tab, by its place in the window: at the end of today's tabs, since a tab in a folder lies
// last in the window. The list would scroll there to show it, as the selected tab
// (stayput.js), and it would then jump back into its folder. So it is drawn in its
// placeholder's place, as it will be (reopenedSaved): returned as tab id -> placeholder's id.
// (Not where its page is open somewhere: that is a duplicate's key, and it becomes a tab of
// its own.) Each tab is asked once.
const restoredKeys = new Map(); // tabId -> the key among its values, or null, until it is taken in
browser.tabs.onRemoved.addListener(tabId => restoredKeys.delete(tabId));
async function restoredInPlace(tabs, all) {
  const standIns = new Map();
  for (const id of restoredKeys.keys()) if (syncKeyByTab.has(id)) restoredKeys.delete(id);
  const waiting = tabs.filter(t => !syncKeyByTab.has(t.id));
  if (!waiting.length) return standIns;
  await Promise.all(waiting.filter(t => !restoredKeys.has(t.id)).map(t => browser.sessions.getTabValue(t.id, SYNC_KEY).then(key => restoredKeys.set(t.id, key ?? null), () => {})));
  for (const t of waiting) {
    const key = restoredKeys.get(t.id), entry = key ? all[key] : null;
    if (!entry || entry.group || isOwnFolder(entry)) continue;
    const reps = await repsNow(key);
    const placeholder = reps.find(r => r.windowId === t.windowId && isGhostUrl(r.url) && tabs.some(x => x.id === r.id));
    if (placeholder && !reps.some(r => !r.discarded && !isGhostUrl(r.url))) standIns.set(t.id, placeholder.id);
  }
  return standIns;
}

// Which entry of the record each row is. Until Tidier has started (the first seconds after
// Firefox starts, or after the background part starts again behind an open sidebar) the
// roles have not been read, and every tab would be drawn outside its folder and jump into
// it a moment later. So they are read here, for this view only: the rest of Tidier must
// not act on them before it starts (start, tabsync.js). Each tab is asked once: a session
// being restored brings a view after every burst of tabs.
const earlyKeys = new Map(); // tabId -> its key, until Tidier has started
browser.tabs.onRemoved.addListener(tabId => earlyKeys.delete(tabId)); // also with no view to clear it after the start
async function rowKeys(tabs) {
  if (started) { earlyKeys.clear(); return syncKeyByTab; }
  // (Not for a tab closed meanwhile: nothing would take it out again.)
  await Promise.all(tabs.filter(t => !earlyKeys.has(t.id)).map(t => browser.sessions.getTabValue(t.id, SYNC_KEY).then(key => earlyKeys.set(t.id, key), () => {})));
  return earlyKeys;
}

// A window without a sidebar costs nothing here. The next view comes once tab events
// have paused for VIEW_DEBOUNCE_MS, at the latest VIEW_LONGEST_WAIT_MS after the first
// of them, and one at a time: a view started while another is being built could
// otherwise overtake it, and the sidebar would end up showing the older one.
function viewSoon(windowId) {
  if (!sidebarPorts.get(windowId)?.size) return;
  const now = performance.now(), building = viewsBuilding.get(windowId);
  if (building && now - building.since < VIEW_STUCK_MS) { building.changed = true; return; }
  const waiting = viewTimers.get(windowId), first = waiting?.first ?? now;
  if (waiting && now - first >= VIEW_LONGEST_WAIT_MS) return; // it is due: events that keep coming must not put it off again
  clearTimeout(waiting?.timer);
  viewTimers.set(windowId, { first, timer: setTimeout(() => buildView(windowId), viewWait(now, first, viewRest.get(windowId) ?? 0)) });
}
const viewWait = (now, first, restUntil) => Math.max(Math.min(VIEW_DEBOUNCE_MS, first + VIEW_LONGEST_WAIT_MS - now), restUntil - now, 0);
async function buildView(windowId) {
  viewTimers.delete(windowId);
  const t0 = performance.now(), building = { since: t0, changed: false };
  viewsBuilding.set(windowId, building);
  work.views++;
  const view = await viewFor(windowId).catch(err => (console.error("Tidier: sidebar", err), null));
  const ms = performance.now() - t0;
  work.viewMs += ms;
  work.longestViewMs = Math.max(work.longestViewMs, ms);
  if (viewsBuilding.get(windowId) !== building) return; // given up on: a newer one is on its way
  viewsBuilding.delete(windowId);
  if (view) for (const port of sidebarPorts.get(windowId) || []) port.postMessage(view);
  if (sidebarPorts.has(windowId)) viewRest.set(windowId, performance.now() + Math.min(VIEW_REST * ms, VIEW_LONGEST_REST_MS));
  if (building.changed) viewSoon(windowId);
}
// A view without the wait, for what you asked for yourself and are waiting to see: another
// space. The wait is there to make one view of a burst of tab events, and a switch is over
// when this is called: waiting only made the list come a few hundredths of a second later.
// (A view being built is not overtaken: it is told to be followed by another.)
function viewNow(windowId) {
  if (!sidebarPorts.get(windowId)?.size) return;
  const building = viewsBuilding.get(windowId);
  if (building && performance.now() - building.since < VIEW_STUCK_MS) { building.changed = true; return; }
  clearTimeout(viewTimers.get(windowId)?.timer);
  buildView(windowId);
}
const viewAllSoon = () => { for (const windowId of sidebarPorts.keys()) viewSoon(windowId); };
// Only the sidebars that show tabs of this space: a page in another space can change
// its title all day without any sidebar having anything to draw.
const showsSpace = (windowId, space) => { const shown = activeSpace.get(windowId); return !shown || space === shown || space === NO_CONTAINER || isHiddenSpace(space); }; // hiddenspaces.js: shown wherever you are
const viewSpaceSoon = space => { for (const windowId of sidebarPorts.keys()) if (showsSpace(windowId, space)) viewSoon(windowId); };

browser.runtime.onConnect.addListener(port => {
  if (port.name !== "sidebar" || port.sender?.id !== browser.runtime.id) return;
  let windowId = null, holding = null; // the quiet line's note this sidebar holds (holdNote)
  port.onMessage.addListener(async msg => {
    if (msg.type === "hello") {
      windowId = msg.windowId;
      if (!sidebarPorts.has(windowId)) sidebarPorts.set(windowId, new Set());
      sidebarPorts.get(windowId).add(port);
      sidebarHere(windowId); // aftermove.js
      viewSoon(windowId);
    } else if (windowId === null) {
      return;
    } else if (msg.type === "trace") {
      trace(`sidebar ${windowId}: ${String(msg.what).slice(0, 120)}`); // common.js
    } else if (msg.type === "select") {
      await browser.tabs.update(msg.tabId, { active: true }).catch(() => {});
    } else if (msg.type === "close") {
      await closeFromSidebar(windowId, msg.tabId); // quiet.js: remembered for undo
    } else if (msg.type === "space") {
      await serial(() => switchSpace(windowId, msg.space));
    } else if (msg.type === "newTab") {
      await newTabInSpace(windowId, msg.space); // newtabs.js
    } else if (msg.type === "mute") {
      await browser.tabs.update(msg.tabId, { muted: msg.muted }).catch(() => {});
    } else if (msg.type === "undo") {
      await undoNote(windowId, msg.note); // quiet.js: taken at once, carried out in the queue
    } else if (msg.type === "holdNote") {
      holding = msg.held ? msg.note : null;
      holdNote(windowId, msg.note, msg.held); // quiet.js: the line waits while you are on it
    } else if (msg.type === "copied") {
      // The sidebar copied in its own click (the clipboard needs that): the word for it is
      // said here, where the page and the quiet line are, as ⇧⌘C says it (pagenote.js).
      const [tab] = await browser.tabs.query({ windowId, active: true });
      await sayDone(windowId, tab?.id, msg.text);
    } else if (msg.type === "restartFirefox") {
      await restartFirefox(windowId); // firefoxsetup.js: not behind what the queue is doing
    } else if (msg.type === "restartSeen") {
      restartLinePutAway();
    } else if (msg.type === "goToSound") {
      await goToSound(windowId, msg.tabId); // sounds.js; like select, not behind what the queue is doing
    } else if (msg.type === "warmup") {
      // Not a sidebarAction: this changes nothing you can see, so it neither waits in the queue nor asks for a new view.
      await browser.tabs.warmup(msg.tabId).catch(() => {});
    } else {
      // Rows are drawn before Tidier has started; what you do with them waits for that,
      // since a move before the roles are read would act on a row, not on its tab.
      for (let i = 0; i < 300 && !started; i++) await sleep(100);
      if (started) await serial(() => sidebarAction(windowId, msg)).catch(() => {}); // logged by serial()
    }
  });
  port.onDisconnect.addListener(() => {
    // A sidebar closed with the pointer on the line tells no more: the line goes on by itself.
    if (holding !== null) holdNote(windowId, holding, false);
    const set = sidebarPorts.get(windowId);
    if (!set) return;
    set.delete(port);
    if (!set.size) { sidebarPorts.delete(windowId); clearTimeout(viewTimers.get(windowId)?.timer); viewTimers.delete(windowId); viewRest.delete(windowId); viewsBuilding.delete(windowId); landedIn.delete(windowId); }
  });
});

// What you do in the sidebar (ownfolders.js). A drop the sidebar shows in
// its new place before it is done has a name (`landing`), given back with the views built after it.
async function sidebarAction(windowId, msg) {
  try {
    await sidebarActionNow(windowId, msg);
  } finally {
    if (msg.landing) landedIn.set(windowId, String(msg.landing));
    viewSoon(windowId); // also after a refusal: the sidebar must see where things really are
  }
}
async function sidebarActionNow(windowId, msg) {
  if (msg.type === "newFolder") await createFolder(msg.name || "New folder", msg.space);
  else if (msg.type === "renameFolder") await renameFolder(msg.key, msg.name);
  else if (msg.type === "foldFolder") await foldFolder(msg.key, msg.collapsed);
  else if (msg.type === "deleteFolder") await deleteFolder(msg.key, windowId);
  else if (msg.type === "clearSpace") await clearSpace(windowId, msg.space); // quiet.js
  else if (msg.type === "moveFolder") await moveFolder(msg.key, msg.before ?? null);
  else if (msg.type === "moveTab") await moveTab(windowId, msg.tabId, msg.before ?? null, msg.folder);
  else if (msg.type === "moveToSpace") await tabAction(windowId, { action: "space", tabIds: [msg.tabId], space: msg.space, at: msg.at }); // tabactions.js: with its line
  else if (msg.type === "pin") await pinFromSidebar(windowId, msg.tabId, msg.pinned, msg.before, msg.folder);
  else if (msg.type === "moveEssential") await moveEssential(windowId, msg.tabId, msg.before ?? null);
  else if (msg.type === "tabAction") await tabAction(windowId, msg); // tabactions.js
  else if (msg.type === "renameTab") await renameTab(msg.tabId, msg.name);
  else if (msg.type === "unloadSpace") await unloadSpace(msg.space, windowId);
  else if (msg.type === "unloadOtherSpaces") await unloadOtherSpaces(msg.space, windowId); // spaceactions.js
  else if (msg.type === "foldFolders") await foldAllFolders(msg.space, msg.collapsed); // ownfolders.js
  else if (msg.type === "spaceAction") await spaceAction(windowId, msg); // listactions.js
  else if (msg.type === "newTabInFolder") await newTabInFolder(windowId, msg.key);
  else if (msg.type === "openLinks") await openLinksAt(windowId, msg); // droplinks.js
  else if (msg.type === "renameSpace") await renameSpace(msg.space, msg.name);
  else if (msg.type.startsWith("little:")) await littleAction(windowId, msg); // littlewindow.js
  else if (msg.type === "askHidingSeen") askHidingSeen(); // aftermove.js
}

// A tab dropped on a tile is an essential at that place: Firefox pins it after the
// others, and onPinned (essentials.js) gives it its place in the list as it adds it. Moving
// it there afterwards would show the tile at the end first, and then jump.
//
// A tab moved or pinned a moment ago is still in the sets that make the listeners ignore
// Tidier's own changes. This one is yours, and ignored it would leave the tab both an
// essential and a tab with placeholders in the other windows, for good.
//
// A new tab has no page to keep as an essential: pinned, it would only be a stray tile in
// one window, and an essential is in every window. (A placeholder stands for its page.)
//
// Unpinned, it goes where it was dropped among the tabs (`before`, `folder`: as for a tab
// moved, moveTab), once it is in the record (unpinPlaces, essentials.js). Dropped on the list
// with no place, it goes where Firefox puts it: first among the tabs.
async function pinFromSidebar(windowId, tabId, pinned, before, folder) {
  const tab = await browser.tabs.get(tabId).catch(() => null);
  if (!tab || tab.pinned === pinned) return; // closed or pinned meanwhile: no event will use a place
  if (pinned && !isWeb(tab.url) && !isGhostUrl(tab.url)) return;
  busy.delete(tabId);
  syncBusy.delete(tabId);
  if (pinned && before) pinPlaces.set(tabId, before);
  if (!pinned) {
    unpinYourself(tabId);
    if (before !== undefined || folder !== undefined) unpinPlaces.set(tabId, { windowId, before: before ?? null, folder: folder ?? null });
  }
  await browser.tabs.update(tabId, { pinned }).catch(() => { pinPlaces.delete(tabId); unpinPlaces.delete(tabId); });
}

// An essential's tile moved: moving its tab is what the rest of Tidier listens to.
async function moveEssential(windowId, tabId, beforeId) {
  const tabs = await browser.tabs.query({ windowId, pinned: true });
  const before = tabs.find(t => t.id === beforeId), tab = tabs.find(t => t.id === tabId);
  if (!tab) return;
  let index = before ? before.index : tabs.at(-1).index;
  if (before && tab.index < before.index) index--;
  busy.delete(tabId); // yours, also right after its pin (see pinFromSidebar)
  if (index !== tab.index) await browser.tabs.move(tabId, { index }).catch(ifGone);
}

// The toolbar button shows or hides the sidebar: without a sidebar, a window has
// no list of tabs at all (the tab bar is hidden in userChrome.css).
browser.browserAction.onClicked.addListener(() => browser.sidebarAction.toggle());
for (const event of ["onCreated", "onMoved", "onAttached", "onDetached"]) {
  browser.tabs[event].addListener((tabOrId, info) => viewSoon(tabOrId.windowId ?? info?.windowId ?? info?.newWindowId ?? info?.oldWindowId));
}
browser.tabs.onRemoved.addListener((tabId, info) => viewSoon(info.windowId));
browser.tabs.onUpdated.addListener((tabId, change, tab) => { if (showsSpace(tab.windowId, tab.cookieStoreId)) viewSoon(tab.windowId); },
  { properties: ["title", "favIconUrl", "status", "discarded", "audible", "mutedInfo", "pinned", "url"] }); // not "hidden": a switch of space hides hundreds of tabs one by one
for (const event of ["onCreated", "onUpdated", "onRemoved"]) browser.contextualIdentities[event].addListener(viewAllSoon);
