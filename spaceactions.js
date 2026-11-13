// What a space's menu does (sidebar/spacemenu.js), carried out through sidebarAction
// in sidebar-view.js.

// Unload a space, to free its memory, without losing anything: a row dims and its
// page comes back when you select it.
//
// Every window is asked, since the row you right-clicked is often a placeholder and
// its page is loaded in another window. Only tabs with a page are unloaded: a loaded
// placeholder unloads itself once it has its icon (unloadGhost, tabsync.js), and would
// have none if unloaded sooner. A selected placeholder is a page on its way to you, so
// a tab whose placeholder is selected in any window stays too.
//
// Stays: essentials (always there and ready, as in Zen and Arc; one can be unloaded by
// hand), the selected tabs, tabs playing sound, and tabs using the camera, microphone or
// screen (unloading would end a call, and one with everybody quiet plays no sound). A
// page with unsaved input refuses without asking (closesQuietly, tabsync.js), and stays.
// One call per tab, since Firefox refuses a whole list for one tab closed meanwhile.
//
// No space, nothing to do: a query without a container is every space's tabs.
//
// The line says what it did (`windowId`: the sidebar it was asked from): unloading a space
// you are not looking at changes nothing you can see.
async function unloadSpace(space, windowId) {
  if (!space) return;
  const unloaded = await unloadPages(unloadable(await browser.tabs.query({ cookieStoreId: space, pinned: false })));
  if (windowId === undefined) return;
  const name = (await containerSpaces()).find(s => s.id === space)?.name ?? "this space";
  say(windowId, unloaded ? `${tabCount(unloaded)} unloaded in ${name}` : `Nothing to unload in ${name}`);
}
const tabCount = n => (n === 1 ? "1 tab" : `${n} tabs`);
// Of these tabs, the pages that unloading takes: what is in use stays (above).
function unloadable(tabs) {
  const selected = new Set(tabs.filter(t => t.active && syncKeyByTab.has(t.id)).map(t => syncKeyByTab.get(t.id)));
  const inUse = t => t.active || t.audible || selected.has(syncKeyByTab.get(t.id)) || Object.values(t.sharingState ?? {}).some(Boolean);
  return tabs.filter(t => !t.discarded && !isGhostUrl(t.url) && !inUse(t));
}
// How many of them went: a page with unsaved input stays.
async function unloadPages(pages) {
  await Promise.all(pages.map(t => browser.tabs.discard(t.id).catch(() => {})));
  return (await Promise.all(pages.map(t => browser.tabs.get(t.id).catch(() => null)))).filter(t => t?.discarded).length;
}

// Every space but this one, as Zen has it: the space you work in stays as it is, and the
// rest give their memory back, by the same rules. Not a space hidden on this machine: its
// tabs show wherever you are (hiddenspaces.js), so they are not another space's here. Nor
// a tab without a container, which belongs to the space you are in.
async function pagesOfOtherSpaces(space) {
  const others = new Set((await containerSpaces()).map(s => s.id).filter(id => id !== space && !isHiddenSpace(id)));
  return unloadable((await browser.tabs.query({ pinned: false })).filter(t => others.has(t.cookieStoreId)));
}
async function unloadOtherSpaces(space, windowId) {
  if (!space) return;
  const unloaded = await unloadPages(await pagesOfOtherSpaces(space));
  if (windowId !== undefined) say(windowId, unloaded ? `${tabCount(unloaded)} unloaded in the other spaces` : "Nothing to unload in the other spaces");
}

// A space's name is its container's, so Firefox's own settings show it too. Firefox
// tells every sidebar (contextualIdentities.onUpdated, sidebar-view.js).
async function renameSpace(space, name) {
  name = String(name ?? "").trim();
  if (name) await browser.contextualIdentities.update(space, { name }).catch(noteError);
}
