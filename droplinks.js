// A link dropped in the sidebar, from a page or from another app, as in Zen and Arc: it
// opens as a tab where it was dropped (sidebar/drag.js says where). Among today's tabs,
// in a folder, where it is then a saved tab like any other there; among the essentials;
// or on another space's dot, in that space.
//
// It opens in the background, as a link dropped on Firefox's own tab strip does: you put
// it there for later, and the page you are on stays. No rule sends it elsewhere (a rule is
// for a tab that has no place yet, and this one was given its place by hand), and it opens
// in the space it was dropped in, so nothing of it goes out in another container.

const LINKS_AT_ONCE = 20; // a slip of the hand with a page of links selected must not open hundreds

// Firefox makes a tab on about:blank and gives it its address a moment later. Until then
// nothing can keep it: tab sync, a folder and the essentials all go by the address.
async function tabWithItsAddress(tabId) {
  for (let i = 0; i < 80; i++) {
    const tab = await browser.tabs.get(tabId).catch(() => null);
    if (!tab || isWeb(tab.url)) return tab;
    await sleep(25);
  }
  return null;
}

// `urls`: what was dropped. Then one of: `space` (on that space's dot); `essential` (among
// the tiles, before the tile `before`, or last); else in the list, in `folder` or among
// today's tabs, before the tab `before`, or last there. Several keep the order they came in.
async function openLinksAt(windowId, { urls, folder = null, before = null, essential = false, space = null }) {
  const links = (Array.isArray(urls) ? urls : []).filter(u => typeof u === "string" && isWeb(u)).slice(0, LINKS_AT_ONCE);
  const spaces = await containerSpaces();
  const into = space ?? activeSpace.get(windowId);
  if (!links.length || !spaces.some(s => s.id === into) || isHiddenSpace(into)) return;
  // A folder deleted while the link was on its way, or another space's: then among today's tabs.
  const all = await getSynced();
  const key = !essential && !space && isOwnFolder(all[folder]) && !all[folder].live && all[folder].cookieStoreId === into ? folder : null;
  let opened = 0;
  for (const url of links) {
    // Where it will lie, if that is before another tab: made there, it need not jump there.
    const next = space || essential || before === null ? null : await browser.tabs.get(before).catch(() => null);
    const made = await openUnruled({ windowId, cookieStoreId: into, url, active: false, ...(next && !next.pinned ? { index: next.index } : {}) }).catch(ifGone); // safemoves.js
    if (!made) return; // the window closed meanwhile
    opened++;
    if (space) continue;
    if (key) comingIntoFolder.set(made.id, key); // listactions.js: drawn there at once, and taken in there
    const tab = await tabWithItsAddress(made.id);
    if (!tab) continue; // closed already, or it never got an address: an ordinary tab where it is
    if (essential) await pinFromSidebar(windowId, tab.id, true, before ?? undefined); // sidebar-view.js: as a tab dropped there
    else await moveTab(windowId, tab.id, next ? next.id : null, key); // ownfolders.js: in every window
  }
  // On a dot it goes out of sight: one line says where it went.
  if (space && opened) say(windowId, `${opened > 1 ? `${opened} tabs opened` : "Opened"} in ${spaces.find(s => s.id === into).name}`, { brief: true });
}
