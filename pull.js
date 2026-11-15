// The page comes to the window that uses it: the second half of tab sync (tabsync.js).
//
// Every tab is live in one window and a placeholder (a ghost) in the others. This file is
// what moves the page: selecting a placeholder in the window you are using pulls the live
// tab in, and the window it leaves gets a placeholder; a window that stays on a page
// another window took shows it as it was, under a grey layer (the veil), and gets the page
// back when the window that took it has left it, or when you go to that window.
//
// tabsync.js has what this stands on: the record, each tab's key and role, what is busy
// (`syncBusy`, `pulling`, `beingPulled`), and placeholders being made (createRep). Its
// listeners come before these, as the scripts load (manifest.json).

// A placeholder asks once what to do when it is shown (ghostShown), and it is told to
// wait if another tab is live. If it then becomes the live tab itself while it is the
// selected tab (that tab's window closed, say), nothing will ask again, and you are looking
// at an empty page. So in the window you are using, it opens its page now. `also`: in a
// window you are not using too, which is on this page and is the only one that is.
async function openIfBlank(windowId, also = false) {
  if (windowId !== focusedWindowId && !also) return; // when you switch to it, see pullSelected
  const [active] = await browser.tabs.query({ windowId, active: true }).catch(() => []);
  if (!active || syncRoleByTab.get(active.id) !== "live" || !isGhostUrl(active.url)) return;
  await openPlaceholder(active.id, syncKeyByTab.get(active.id));
}

// What a page looked like as it left a window that stays on it: its placeholder there shows
// that picture under a grey layer (ghost.js), as Zen and Arc show a tab another window has.
// Only where you have let Tidier take pictures of pages (the settings page asks; Firefox
// gives an extension none without "<all_urls>"): the placeholder then says which page it is
// in words. Kept in memory only. One for each window at most, of the tab it is on, and gone
// when that window goes to another tab or closes: a picture nobody sees is only memory.
const veilPictures = new Map(); // windowId -> { tabId: the placeholder it is for, picture: a data: address, drawn: called when the placeholder shows it }
browser.tabs.onActivated.addListener(({ tabId, windowId }) => { if (veilPictures.has(windowId) && veilPictures.get(windowId).tabId !== tabId) veilPictures.delete(windowId); });
browser.windows.onRemoved.addListener(windowId => veilPictures.delete(windowId));
const VEIL_WAIT_MS = 300; // for the picture, and then for its placeholder to draw it: the window you use waits no longer for its page

// Taken while the page is still shown where it is (about 30 ms): once it has left, Firefox
// draws it at the size of the window it came to.
async function pictureFor(tabId) {
  // Firefox has the function only for an extension given "<all_urls>" itself (its schema says
  // so), and from the moment it is given; with every website given as "*://*/*" it is not there.
  if (typeof browser.tabs.captureTab !== "function") return null;
  const picture = await Promise.race([browser.tabs.captureTab(tabId, { format: "jpeg", quality: 80 }).catch(() => null), sleep(VEIL_WAIT_MS)]);
  return /^data:image\//.test(picture || "") ? picture : null;
}

// The placeholder `tabId` gets the picture before it is selected: a window that went from
// its page to an empty one and then to the picture flickered, beside the window you use,
// which is the opposite of calm. So it is loaded where it is, unseen (a placeholder is made
// unloaded, createRep), and says when the picture is drawn (ghostDrawn).
async function veilFirst(windowId, tabId, picture) {
  if (!picture) return;
  const drawn = new Promise(resolve => veilPictures.set(windowId, { tabId, picture, drawn: resolve }));
  const tab = await browser.tabs.get(tabId).catch(() => null);
  if (!tab) return;
  await browser.tabs.update(tabId, { url: tab.url }).catch(() => {});
  await Promise.race([drawn, sleep(VEIL_WAIT_MS)]);
}
const holdsVeil = tabId => [...veilPictures.values()].some(v => v.tabId === tabId);
// The page stayed after all (closed meanwhile, say): its placeholder need not stay loaded.
function dropVeil(windowId) {
  const tabId = veilPictures.get(windowId)?.tabId;
  if (veilPictures.delete(windowId)) browser.tabs.discard(tabId).catch(() => {});
}

// The tab selected in each window, as Firefox last said, for a pull to know without asking
// whether you have gone on to another tab while it moved the page (below).
const selectedNow = new Map(); // windowId -> tab id
browser.tabs.onActivated.addListener(({ tabId, windowId }) => selectedNow.set(windowId, tabId));
browser.windows.onRemoved.addListener(windowId => selectedNow.delete(windowId));

// Pull the live tab for `ghostId` into the ghost's window. The part you see
// (moving the tab in and selecting it) happens first; the bookkeeping after.
// `back`: to a window you are not using, which is still on this page while the window that
// took it has gone on to another tab (backToWhoIsOnIt, below).
async function pull(ghostId, { back = false } = {}) {
  const key = syncKeyByTab.get(ghostId);
  if (!key || syncRoleByTab.get(ghostId) !== "ghost") return;
  const liveId = liveTabId(key);
  const [ghost, live] = await Promise.all([
    browser.tabs.get(ghostId).catch(() => null),
    liveId === undefined ? null : browser.tabs.get(liveId).catch(() => null),
  ]);
  if (!ghost) return;
  // You may have moved on while this waited in the queue: it must not take the
  // selection back. And a page goes back only while the window that has it is not on it.
  if (!ghost.active) return;
  if (back ? live?.active && live.windowId !== ghost.windowId : ghost.windowId !== focusedWindowId) return;
  veilPictures.delete(ghost.windowId); // of the page as it was when it left this window
  if (!live || live.windowId === ghost.windowId) {
    // No live tab to pull: the ghost becomes the live tab and loads itself.
    await setRole(ghostId, key, "live");
    await openIfBlank(ghost.windowId, back);
    return;
  }
  pulling++;
  syncBusy.add(live.id); syncBusy.add(ghostId);
  try {
    const fromWindow = live.windowId, fromIndex = live.index;
    // Firefox closes a window when the last tab it can show leaves it, whatever is hidden
    // in it. Using a tab in another window must not close this one: it gets its ghost first.
    const others = await browser.tabs.query({ windowId: fromWindow, hidden: false });
    const entryNow = (await getSynced())[key];
    // The window it leaves stays on it, if it was the tab there, as in Zen and Arc: the window
    // you use has the page, and the other one shows its placeholder under a veil (ghost.js),
    // until you come back to it and the page comes back with you (pullSelected). Sent to
    // another tab instead, that window changed under you, and no longer showed where the page
    // was. So it gets its placeholder first, selected before the page leaves: Firefox would
    // else choose a tab itself, and load it.
    const picture = entryNow && live.active ? await pictureFor(live.id) : null;
    const leftBehind = entryNow && (live.active || !others.some(t => t.id !== live.id))
      ? await createRep(fromWindow, key, entryNow, fromIndex + 1) : null;
    if (live.active && leftBehind) {
      await veilFirst(fromWindow, leftBehind.id, picture);
      await browser.tabs.update(leftBehind.id, { active: true }).catch(() => {});
    }
    // Bookkeeping too. A tab moved before it was ever loaded (a live folder's pull
    // request) can arrive without its sessions values, so they are set again. Any of
    // it is refused if you close the tab or the window meanwhile: ⌘W right after a
    // click. The ghost then stays what it was, for closing that tab to deal with: it
    // would otherwise be left behind, unknown to Tidier, as a tab you closed coming back.
    //
    // The page is selected as it arrives only if its placeholder still is: the move takes
    // its time (and the picture before it), and on a busy machine you had selected another
    // placeholder by then. Selected anyway, the page took you back from the tab you had
    // gone on to, and that one was then never pulled in, as it was no longer the one you
    // were on. Not selected, it is simply here, in its placeholder's place.
    // (Known from what Firefox has said meanwhile, selectedNow, and not asked for now: the
    // page is selected in the same breath as it arrives, or the list would be drawn with the
    // page's row beside its placeholder's, still selected, and end a little off its place.)
    beingPulled.add(live.id);
    selectedNow.set(ghost.windowId, ghostId);
    const moved = await browser.tabs.move(live.id, { windowId: ghost.windowId, index: ghost.index })
      .finally(() => beingPulled.delete(live.id))
      .then(() => (selectedNow.get(ghost.windowId) === ghostId ? browser.tabs.update(live.id, { active: true }) : null))
      .then(() => setRole(live.id, key, "live"), () => false);
    if (!moved) { dropVeil(fromWindow); return; }
    forget(ghostId);
    const all = await getSynced();
    const entry = all[key];
    await browser.tabs.remove(ghostId).catch(ifGone);
    await forgetClosedReps(key, [ghost]);
    if (entry) {
      // A never-loaded live tab is still a placeholder page; keep the real URL then.
      if (isWeb(live.url)) Object.assign(entry, { url: live.url, title: live.title, icon: keptIcon(entry, live) });
      saveSynced(all);
      // The old window gets a ghost where the live tab was, unless you have closed it by now.
      // (One was left there already if this was its last tab: Firefox would have closed it. A
      // window closed meanwhile wants none.)
      if (!leftBehind && await browser.windows.get(fromWindow).catch(() => null)) await createRep(fromWindow, key, entry, fromIndex);
    }
  } catch (err) {
    ifGone(err); // the tab you selected, or the one to bring in, closed meanwhile: nothing to pull
  } finally {
    setTimeout(() => { syncBusy.delete(live.id); syncBusy.delete(ghostId); pulling--; }, 600);
  }
}

// Selecting a ghost in the window you are using pulls the live tab in. (A pull
// selects tabs itself too, but never a ghost in the window you are using.)
browser.tabs.onActivated.addListener(({ tabId, windowId, previousTabId }) => {
  if (!started) return;
  if (syncRoleByTab.get(previousTabId) === "ghost") serial(() => unloadLeftPage(previousTabId));
  if (syncRoleByTab.get(tabId) === "ghost" && windowId === focusedWindowId) serial(() => pull(tabId));
});

// A window that stays on a page another window has taken shows it under a veil (pull). It
// got the page back only when you went to that window: with two windows side by side, the
// one you were not in stayed grey on a page that no window showed any more. So the page goes
// back as soon as the window that took it leaves it for another tab, to a window that is
// still on it. A moment after, and only if you have not come back to it: stepping through
// tabs passes over many, and each would otherwise send its page across.
const VEIL_BACK_MS = 600;
const leftTabs = new Map(); // tabId -> the timer for a tab you have just left
browser.tabs.onActivated.addListener(({ previousTabId }) => {
  // (With one window there is nobody to give a page back to: nothing is looked at.)
  if (!started || previousTabId === undefined || activeSpace.size < 2) return;
  if (syncRoleByTab.get(previousTabId) !== "live" && !keyByTab.has(previousTabId)) return;
  clearTimeout(leftTabs.get(previousTabId));
  leftTabs.set(previousTabId, setTimeout(() => { leftTabs.delete(previousTabId); serial(() => backToWhoIsOnIt(previousTabId)); }, VEIL_BACK_MS));
});
browser.tabs.onRemoved.addListener(tabId => { clearTimeout(leftTabs.get(tabId)); leftTabs.delete(tabId); });
async function backToWhoIsOnIt(tabId) {
  const left = await browser.tabs.get(tabId).catch(() => null);
  if (!left || left.active) return; // closed, or you are on it again
  const on = (await browser.tabs.query({ active: true }).catch(() => [])).filter(t => t.windowId !== left.windowId);
  if (left.pinned) return essentialBackTo(left, on); // essentials.js
  const key = syncKeyByTab.get(tabId);
  if (!key || syncRoleByTab.get(tabId) !== "live") return;
  const waiting = on.find(t => syncKeyByTab.get(t.id) === key && syncRoleByTab.get(t.id) === "ghost");
  if (waiting) await pull(waiting.id, { back: true });
}

// A ghost that shows the page itself stays loaded while it is selected (in a window you
// were not using, as reconcileAll leaves it). Click another tab there as you come back, and
// the focus finds no ghost selected to pull in: the page would stay loaded twice for good.
// It is only a copy, so it is unloaded, like the other copies.
async function unloadLeftPage(tabId) {
  const tab = await browser.tabs.get(tabId).catch(() => null);
  if (tab && !tab.active && !tab.discarded && isWeb(tab.url) && syncRoleByTab.get(tabId) === "ghost") await browser.tabs.discard(tabId).catch(() => {});
}

// Switching to a window whose selected tab is a ghost pulls the live tab in.
function pullSelected(windowId) {
  return serial(async () => {
    const [active] = await browser.tabs.query({ windowId, active: true });
    if (active && syncRoleByTab.get(active.id) === "ghost") await pull(active.id);
    else await openIfBlank(windowId);
  });
}
// A placeholder you are looking at that has become the live tab (the window with the real
// page closed, say). It asked once if it should open, when it was selected, and was told no;
// switching to its window does not make it ask again, and it would stay blank.
async function openPlaceholder(tabId, key) {
  const url = (await getSynced())[key]?.url;
  if (isWeb(url)) await browser.tabs.update(tabId, { url }).catch(ifGone);
}
browser.windows.onFocusChanged.addListener(windowId => {
  if (started && windowId !== browser.windows.WINDOW_ID_NONE) pullSelected(windowId);
});
