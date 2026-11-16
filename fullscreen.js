// A page in its own fullscreen stays where it is.
//
// A video or a presentation in fullscreen in one window, and its tab selected in another:
// pulled across (pull.js, essentials.js), the page left fullscreen as it moved, and the
// window it left dropped out of it. Nobody watching means that, and a tab is selected by
// more than a click: closing the tab beside its placeholder, or stepping through the tabs
// by key, lands on it too. So such a page stays, its placeholder says why (ghost.js), and
// when it was your click on its row or tile that asked for it, you are taken to the window
// that has it. Selected again once it has left fullscreen, it comes as ever. On unless turned
// off on the settings page.
//
// Firefox says "fullscreen" of a window for the page's own fullscreen and for the window's
// (the green button) alike, and of a tab nothing, so the page itself is asked. That needs
// the access to websites Tidier asks for elsewhere; without it nothing is known, and the
// page is pulled as before.

const FULLSCREEN_SETTING = "fullscreenStays";
const fullscreenSetting = storedValue(FULLSCREEN_SETTING, () => true);
// The page answers at once; one that does not (busy, or gone in this moment) must not hold
// the queue this is asked in.
const FULLSCREEN_ASK_MS = 500;

async function inOwnFullscreen(tab) {
  // (Only the tab a window shows can be in fullscreen.)
  if (!tab.active || !isWeb(tab.url) || !await fullscreenSetting.get()) return false;
  if ((await browser.windows.get(tab.windowId).catch(() => null))?.state !== "fullscreen") return false;
  const asked = browser.tabs.executeScript(tab.id, { code: "!!document.fullscreenElement", runAt: "document_start" }).then(([full]) => full === true, () => false);
  return Promise.race([asked, sleep(FULLSCREEN_ASK_MS).then(() => false)]);
}

// The row or tile you clicked last in each window's sidebar (sidebar-view.js), for a moment.
const HAND_MS = 3000;
const pickedByHand = new Map(); // windowId -> { tabId, at }
browser.windows.onRemoved.addListener(windowId => pickedByHand.delete(windowId));
// The placeholders whose page was kept where it was, when last asked for.
const keptByFullscreen = new Set(); // tab ids
browser.tabs.onRemoved.addListener(tabId => keptByFullscreen.delete(tabId));

// Whether `page`, asked for by its placeholder `own` in another window, stays where it is.
async function staysInFullscreen(own, page) {
  if (!await inOwnFullscreen(page)) { keptByFullscreen.delete(own.id); return false; }
  keptByFullscreen.add(own.id);
  const hand = pickedByHand.get(own.windowId);
  pickedByHand.delete(own.windowId);
  if (hand?.tabId === own.id && performance.now() - hand.at < HAND_MS) await browser.windows.update(page.windowId, { focused: true }).catch(() => {});
  return true;
}

// A click in the sidebar on `tabId`. One on a placeholder that is selected already, kept out
// by fullscreen a while ago, selects nothing anew, so its page is asked for here.
function clickedInSidebar(windowId, tabId) {
  pickedByHand.set(windowId, { tabId, at: performance.now() });
  if (!keptByFullscreen.has(tabId) || !started) return;
  pullSelected(windowId); // pull.js
  selectedEssential(windowId); // essentials.js
}

// The settings page (settings/fullscreen.js).
browser.runtime.onMessage.addListener((msg, sender) => {
  if (!msg?.type?.startsWith?.("fullscreen:") || sender.id !== browser.runtime.id || !sender.url?.startsWith(browser.runtime.getURL(""))) return;
  return (async () => {
    if (msg.type === "fullscreen:set") fullscreenSetting.set(!!msg.on);
    return { on: await fullscreenSetting.get() };
  })();
});
