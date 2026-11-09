// Right after moving over (moveover.js), at the first start alone: Firefox's question about
// hidden tabs, and the windows that came over without Tidier's sidebar.
//
// Firefox asks about hidden tabs at the first tab Tidier hides, and again at every one until
// it is answered: a note that hangs from the toolbar over the top of the sidebar and takes the
// keyboard, with "Disable Extension" just where "New tab" is. One click or Enter there turns
// Tidier off, and with Sidebery off too the window has no list of tabs at all. Firefox forgets
// the answer whenever the add-on is disabled (ext-tabs.js, onDisable), and starting again
// (runtime.reload) is a disable, so the question cannot be had before the move. So at that
// start no tab is hidden (hidingHeld, spaces.js) until the settings page is back in front and
// says what to choose (afterMoving, moveover.js); Firefox then asks in that window, over the
// page you are reading. Until the first switch of space the sidebar says it too, in one line:
// the note may have been closed without an answer, and then it comes back at the next hide.
//
// Firefox opens Tidier's sidebar again only in a window where it was the last one open: the
// one you clicked Move in (settings.js). With Sidebery off, another window has no list of tabs
// at all. It gets the settings page too, with a button that opens the sidebar there (a click
// in a page of Tidier's is what lets it), and the first key of Tidier's pressed there opens it.

const HOLD_HIDING_MS = 10000; // the page never said it was drawn: hidden anyway
let askHidingLine = false; // the sidebar's line (viewFor, sidebar-view.js)
let movedWindow = null; // where the settings page came back
const wantsSidebar = new Set(); // windowIds, until the sidebar is there (sidebarHere)

// Early in the start, before anything is hidden.
async function holdHidingAfterMove() {
  const { movedNote } = await browser.storage.local.get("movedNote");
  if (!tidierAlone || movedNote?.kind !== "over" || movedNote.opened) return;
  hidingHeld = true;
  askHidingLine = true;
}

// The settings page is back, in this window, in front (or could not be, with null).
function holdUntilShown(windowId) {
  if (!hidingHeld) return;
  movedWindow = windowId;
  if (windowId === null) serial(releaseHiding);
  else setTimeout(() => serial(releaseHiding), HOLD_HIDING_MS);
}

// The page in that window says it is drawn: a moment for it to be read, then the question.
// (A page in another window does not count: Firefox asks in the window in front.)
function movedPageShown(windowId) {
  if (hidingHeld && windowId === movedWindow) sleep(300).then(() => serial(releaseHiding));
}

// Now tabs are hidden, and Firefox asks. If nothing needed hiding, one tab is hidden and
// shown again, so that it asks now and not later over the sidebar. Then each window that has
// no sidebar gets the page, after the one in front has taken what the move did (said once).
async function releaseHiding() {
  if (!hidingHeld) return;
  hidingHeld = false;
  const wins = await normalWindows();
  let hidden = 0;
  for (const w of wins) hidden += await showSpace(w.id);
  if (!hidden && browser.tabs.hide && movedWindow !== null) {
    const [tab] = await browser.tabs.query({ windowId: movedWindow, pinned: false, hidden: false, active: false });
    if (tab) await browser.tabs.hide(tab.id).then(() => browser.tabs.show(tab.id)).catch(() => {});
  }
  const url = browser.runtime.getURL("settings/settings.html");
  for (const w of wins) {
    if (await browser.sidebarAction.isOpen({ windowId: w.id }).catch(() => true)) continue;
    wantsSidebar.add(w.id);
    if (w.id !== movedWindow) await browser.tabs.create({ url, windowId: w.id, active: true }).catch(noteError);
  }
}

// For the settings page: whether this is the start right after moving over, and the key that
// shows the sidebar, as the page writes keys (keys-commands.js).
async function afterMoveState() {
  if (!askHidingLine && !wantsSidebar.size) return null;
  const shortcut = (await browser.commands.getAll()).find(c => c.name === "_execute_sidebar_action")?.shortcut;
  return { sidebarKey: shortcut ? prettyKey(shortcut, (await browser.runtime.getPlatformInfo()).os) : "" };
}

// The line goes at the first switch of space, or with its ×.
function askHidingSeen() {
  if (!askHidingLine) return;
  askHidingLine = false;
  viewAllSoon();
}

// A key, like a click in a page of Tidier's, lets an extension open a sidebar, and only at
// once, while it is being handled: so here, and not in the queue. Until the sidebar is there
// (sidebarHere, sidebar-view.js), or Firefox restarts, which brings back each window's own.
const sidebarHere = windowId => wantsSidebar.delete(windowId);
browser.commands.onCommand.addListener((name, tab) => {
  if (name !== "_execute_sidebar_action" && wantsSidebar.delete(tab?.windowId)) browser.sidebarAction.open().catch(() => {});
});
browser.windows.onRemoved.addListener(id => wantsSidebar.delete(id));
