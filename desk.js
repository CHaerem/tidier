// Every tab at once, as Zigzag's desk: each space under its name, large and light, and every
// tab of it as a card, a picture of its page where Firefox gives one. Type to find a tab,
// the arrows and Enter to go to it, Esc to go back where you were.
//
// An extension cannot draw over the window, so the desk is a page of Tidier's own in a tab of
// the window you are in, next to the tab you were on, and it goes as soon as you leave it:
// chosen, Esc, or another tab selected. It is no page of any space and is in no record: tab
// sync takes in only what is on the web (syncable, tabsync.js), and the sidebar leaves it out
// of the list (deskTab, below).
//
// Pictures only with "Pictures of pages" allowed on the settings page (captureTab comes with
// <all_urls>, settings/pictures.js), and only of pages that are loaded: an unloaded tab has
// none to give, and its card shows its icon. Asked for by the page one at a time, the cards
// in sight first, never kept: nothing is done until the desk is opened.

const DESK_PAGE = browser.runtime.getURL("desk/desk.html");
const isDeskUrl = url => String(url ?? "").startsWith(DESK_PAGE);
const desks = new Map(); // windowId -> { tabId: the desk's, from: the tab you were on }
const deskTab = t => isDeskUrl(t.url);

async function toggleDesk(windowId) {
  if (desks.has(windowId)) return closeDesk(windowId, { back: true });
  const [from] = await browser.tabs.query({ windowId, active: true });
  desks.set(windowId, { tabId: null, from: from?.id });
  const tab = await browser.tabs.create({ windowId, url: `${DESK_PAGE}#${windowId}`, active: true, ...(from && !from.pinned ? { index: from.index + 1 } : {}) })
    .catch(err => { desks.delete(windowId); throw err; });
  if (desks.has(windowId)) desks.get(windowId).tabId = tab.id;
  else browser.tabs.remove(tab.id).catch(() => {}); // closed again before it was there
}

// `back`: to the tab you were on (Esc, the key again); else what was chosen is selected first.
async function closeDesk(windowId, { back = false } = {}) {
  const desk = desks.get(windowId);
  if (!desk) return;
  desks.delete(windowId);
  if (back && desk.from !== undefined) await browser.tabs.update(desk.from, { active: true }).catch(() => {});
  if (desk.tabId !== null) await browser.tabs.remove(desk.tabId).catch(() => {});
}
browser.tabs.onRemoved.addListener(tabId => { for (const [w, d] of desks) if (d.tabId === tabId) desks.delete(w); });
// Another tab selected (a click in the sidebar, a key): the desk has done its work.
browser.tabs.onActivated.addListener(({ tabId, windowId }) => {
  const desk = desks.get(windowId);
  if (desk?.tabId !== null && desk?.tabId !== undefined && desk.tabId !== tabId) closeDesk(windowId).catch(noteError);
});

// Every space of the window, in the bar's order, with its cards as its list draws them:
// essentials, each folder's tabs, today's tabs.
async function deskView(windowId) {
  const all = await getSynced();
  const first = await viewFor(windowId); // sidebar-view.js
  const views = await Promise.all(first.spaces.map(s => (s.id === first.space ? first : viewFor(windowId, s.id))));
  const own = (await browser.tabs.query({ windowId })).filter(t => !deskTab(t));
  const urlOf = new Map(own.map(t => [t.id, all[syncKeyByTab.get(t.id)]?.url ?? (isWeb(t.url) ? t.url : null)]));
  const card = (t, more) => ({ id: t.id, title: t.title, icon: t.icon, url: urlOf.get(t.id) ?? null, loaded: !!t.loaded, ...more });
  return {
    space: first.space,
    spaces: first.spaces.map((s, i) => {
      const v = views[i];
      const cards = [
        ...v.essentials.map(t => card(t, { essential: true })),
        ...v.folders.flatMap(f => f.tabs.map(t => card(t, { folder: f.name }))),
        ...v.tabs.map(t => card(t, {})),
      ].filter(c => urlOf.has(c.id)); // (not the desk itself)
      // The window's own tint (spacelook.js), as the page cannot be sure to work it out the
      // same from the colour alone.
      const hex = hexColour(s.color);
      return { id: s.id, name: s.name, color: s.color, tint: hex ? tintsOf(hex) : null, cards };
    }),
    from: desks.get(windowId)?.from ?? null,
    pictures: typeof browser.tabs.captureTab === "function",
  };
}

// A picture of the card's page: of this window's tab if its page is here, else of the tab
// that has it in another window. None of an unloaded page.
const DESK_PICTURE = { format: "jpeg", quality: 70, scale: 0.4 };
async function deskPicture(tabId) {
  if (typeof browser.tabs.captureTab !== "function") return null;
  const tab = await browser.tabs.get(tabId).catch(() => null);
  if (!tab) return null;
  const live = isGhostUrl(tab.url) ? liveTabId(syncKeyByTab.get(tabId)) : tabId; // tabsync.js
  const page = live !== undefined && live !== null && await browser.tabs.get(live).catch(() => null);
  if (!page || page.discarded || !isWeb(page.url)) return null;
  return browser.tabs.captureTab(page.id, DESK_PICTURE).catch(() => null);
}

// Only from the desk's own page.
browser.runtime.onMessage.addListener((msg, sender) => {
  if (!String(msg?.type).startsWith("desk:") || sender.id !== browser.runtime.id || !isDeskUrl(sender.url)) return;
  const windowId = sender.tab?.windowId;
  if (msg.type === "desk:view") return deskView(windowId);
  if (msg.type === "desk:picture") return deskPicture(msg.tabId);
  if (msg.type === "desk:go") return (async () => {
    clickedInSidebar(windowId, msg.tabId); // fullscreen.js: as a click in the sidebar
    await browser.tabs.update(msg.tabId, { active: true }).catch(() => {}); // the desk goes as it is left (onActivated)
  })();
  if (msg.type === "desk:space") return serial(() => switchSpace(windowId, msg.space)).then(() => closeDesk(windowId));
  if (msg.type === "desk:close") return closeFromSidebar(windowId, msg.tabId); // quiet.js: with Undo in the sidebar
  if (msg.type === "desk:back") return closeDesk(windowId, { back: true });
});
