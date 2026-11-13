// The command bar, like Arc's: one key, one field, and everything is reached from it.
// Tabs of all spaces, essentials, folders, what was closed, history and bookmarks if
// you allow it, and commands.
//
// An extension cannot draw over a page, but Firefox can for it: the bar is the popup of
// Tidier's toolbar button, opened by the key (browserAction.openPopup). That is a panel
// of Firefox's own, in the window you are in, with no frame and no title, which takes the
// keyboard, gives it back to where it was, and goes when you click beside it. It was once a
// small window of its own (windows.create type popup): that had a title bar, took a moment
// longer, stood in Mission Control and ⌘`, and had to be placed, focused and forgotten by
// Tidier. Firefox hangs the panel from the Extensions button, where Tidier's own button is. The
// dotfiles' stylesheet puts it in the middle of the window, where the address bar floats:
// only a stylesheet of the browser's own can say where a panel goes.
//
// The window is still there, for a Firefox that will not open the panel: then the bar is a
// small window centred over the one you are in. Tab sync and essentials only look at normal
// windows, so they leave it alone.
//
// This part gathers what can be found when the key is pressed, without waiting for the
// queue, since the bar must open at once also when Tidier is busy, and carries out what
// you choose. The bar's page (commandbar/) ranks by itself on every key press. Nothing
// here runs unless you press the key: while the bar is open it works on what it was
// given, and it is short-lived enough that nothing has to keep that up to date.

const BAR_PAGE = "commandbar/commandbar.html";
// In the window: as wide as the dotfiles' floating address bar (760 px, or seven tenths of a
// narrower window), so the two are one thing in two guises. Its height is the page's own
// (commandbar.css): a field and eight rows. Firefox gives a panel 800 px at the most.
const BAR_PANEL_WIDTH = 760, BAR_PANEL_SHARE = 0.7;
// As a window: a field and eight rows of the sidebar's height, under a title bar on a Mac.
// It never changes while the bar is open, so nothing jumps while you type. As wide as the
// window allows, with some of it showing on both sides.
const BAR_WIDTH = 640, BAR_MIN_WIDTH = 360, BAR_SIDES = 48, BAR_HEIGHT = 380;
const BAR_OPEN_LIMIT_MS = 10000; // a bar that never came must not take the key for good
const BAR_GONE_MS = 500; // a panel is gone a few milliseconds after its page is told; what you chose does not wait longer
// Firefox shows no panel from a toolbar button it cannot show: a toolbar hidden by a
// stylesheet that does not hold it in place for the bar, as after an update of Tidier with
// Firefox still running on the stylesheet it started with (the dotfiles' is read at a
// start). It says nothing of it: it answers that the panel is open, loads the panel's page,
// and takes it away again some 60 ms later, unseen. So the key seemed dead. A panel that
// goes by itself, with nothing closing it, was such a one if it went sooner than anyone
// could have seen it and closed it (BAR_UNSEEN_MS), or a little later (BAR_SEEN_MS) without
// its page ever having had the keyboard, which a panel that shows gets within a few
// hundredths of a second ("seen", from its page). The bar is then a window, for the same press. The panel is asked for again at the next press
// (it costs those 60 ms, and nothing shows), so the bar is in the window again as soon as
// Firefox can show it there.
//
// A panel whose page is not there at all after BAR_PANEL_MS will not come (a page is there
// well within a tenth of a second; the wait is generous, since a busy machine must not make
// a window of a panel that is on its way). That wait is long, so then the bar is a window
// for a while (BAR_PANEL_AGAIN_MS) before the panel is tried again.
const BAR_UNSEEN_MS = 150, BAR_SEEN_MS = 400, BAR_PANEL_MS = 2000, BAR_PANEL_AGAIN_MS = 10 * 60 * 1000;
let barPanelNotBefore = 0; // when the panel is tried again, after one that never came (performance.now())
const BAR_FORGET_MS = 10000; // Firefox lists a closed window a moment after it has closed, once it has its last state
// A sidebar answers in a few milliseconds, and with none open Firefox says so at once; only a
// sidebar that is there but slow (a busy machine: 100 ms was too short there) waits this long,
// meanwhile the bar's window is still being made. Acting on one tab when you had selected two
// would be the wrong tabs.
const BAR_ASK_SIDEBAR_MS = 300;
const CLOSED_LOOKED_AT = 25; // Firefox's list of closed tabs holds about this many anyway
const BAR_ASKED = "commandBarAsked"; // storage: history and bookmarks have been asked for, so the row does not come back

let commandBar = null; // the open bar: { ownWindow (its id, where the bar is a window), from, pressedAt, snapshot (a promise), ctx, closeOnOpen, early (keys caught before it), port (once its page is there), caughtIn (the tab they were caught in), gone (called when its page has gone) }

const barUses = storedValue("commandUses", () => ({})); // command name -> how often: "the most used"
const barAccents = new Map(); // space -> its colour, as the last bar was given it

// Where the bar is: Firefox's panel in the window you are in, also while it is on its way
// there, unless it has been given a window of its own (the way back, toggleCommandBar).
const barInPanel = bar => bar.ownWindow === null;
// Open in the window itself, with its page there: the keyboard is the bar's (shortcuts.js).
const barHasKeyboard = () => !!commandBar?.port && barInPanel(commandBar);

// The window to open from: the one you are in. A sign-in popup or another bar is not a
// window to open tabs in, so then any normal window.
async function barSourceWindow(tab) {
  const id = tab?.windowId ?? focusedWindowId;
  const win = await browser.windows.get(id).catch(() => null);
  return win?.type === "normal" && !win.incognito ? win : (await normalWindows())[0] ?? null;
}

// The key: opens the bar, or closes the one that is open.
//
// The bar is made at each press: a panel is only there while it shows, and a window made in
// advance could not be hidden (Firefox keeps every window an extension moves on the screen,
// a minimised one goes into the Dock and comes back out of it slowly, and one kept behind
// the window you are in shows in Mission Control and ⌘`). What you type before it has the
// keyboard is caught where it goes (barkeys.js) and handed to it.
async function toggleCommandBar(tab) {
  // "There" is when its page has said so (the port): a panel has nothing else to go by.
  const opening = commandBar && !commandBar.port && barInPanel(commandBar);
  if (opening && Date.now() - commandBar.pressedAt > BAR_OPEN_LIMIT_MS) commandBar = null;
  else if (opening) { commandBar.closeOnOpen = !commandBar.closeOnOpen; return; } // what the presses add up to is settled once it is there
  if (commandBar) return barClose(commandBar, true);
  const bar = commandBar = { ownWindow: null, from: null, pressedAt: Date.now(), snapshot: null, ctx: null, closeOnOpen: false, early: null, port: null, gone: null, there: null, noPanel: false, closed: false, seen: false, asWindow: null };
  barCatchKeys(tab, bar); // first of all: the next key can be on its way already
  try {
    const from = await barSourceWindow(tab);
    if (!from) { commandBar = null; return; }
    bar.from = from.id;
    bar.snapshot = barSnapshot(bar).catch(err => { noteError(err); return null; }); // ready by the time the page asks
    // The space and its colour go along, so the page is in them from its first frame
    // (commandbar/first.js). Its colour as the bar last saw it: asking would hold the window up.
    const space = activeSpace.get(from.id), accent = barAccents.get(space);
    const given = [...(space ? [["space", space]] : []), ...(accent ? [["accent", accent]] : [])];
    const address = more => { const all = new URLSearchParams([...given, ...more]); return `${BAR_PAGE}${all.size ? `?${all}` : ""}#${bar.pressedAt}`; };
    bar.asWindow = { url: address([]), ...barPlaceOver(from) }; // the way back, also for a panel that goes unseen
    if (await barOpenInWindow(bar, from, address([["panel", String(barPanelWidth(from))]]))) return; // closeOnOpen is settled when its page is there
    await barOpenAsWindow(bar);
  } catch (err) {
    if (commandBar === bar) commandBar = null;
    noteError(err);
  }
}

// As a small window of its own: where Firefox has no panel to give, will not open one, or
// opened one nobody saw.
async function barOpenAsWindow(bar) {
  if (commandBar !== bar || bar.closed || bar.ownWindow !== null) return; // closed meanwhile, or a window already
  const { url, ...place } = bar.asWindow;
  const win = await browser.windows.create({ type: "popup", url, allowScriptsToClose: true, ...place });
  bar.ownWindow = win.id;
  if (bar.closeOnOpen) await barClose(bar, true);
}
// The panel did not show: no more of it for this bar, which is a window now. A page of it
// that comes after all is sent away.
function barPanelFailed(bar, how) {
  bar.noPanel = true;
  trace(`the bar ${how} in the window: a window of its own`);
}

// As the toolbar button's popup, in `from`. The button has no popup of its own (a click on it
// shows or hides the sidebar, sidebar-view.js), so it is given this one for the moment of
// opening only: Firefox reads it as it opens the panel. Returns whether the bar is there:
// its page has said so. What Firefox answers is not enough, since it can answer that it
// opened a panel nobody sees, or never answer at all (BAR_PANEL_MS, above).
async function barOpenInWindow(bar, from, url) {
  if (typeof browser.browserAction.openPopup !== "function" || performance.now() < barPanelNotBefore) return false;
  const there = new Promise(resolve => { bar.there = resolve; }); // called when its page connects, below
  try {
    await browser.browserAction.setPopup({ popup: url });
    const opened = browser.browserAction.openPopup({ windowId: from.id }).then(() => there);
    opened.catch(() => {}); // heard below, or after the wait is over, when it no longer matters
    if (await Promise.race([opened.then(() => true), sleep(BAR_PANEL_MS).then(() => false)])) return true;
    barPanelFailed(bar, "did not come");
    barPanelNotBefore = performance.now() + BAR_PANEL_AGAIN_MS;
    return false;
  } catch (err) {
    trace(`the bar could not open in the window: ${err?.message ?? err}`);
    return false;
  } finally {
    bar.there = null;
    await browser.browserAction.setPopup({ popup: null }).catch(() => {});
  }
}

// The dotfiles' floating address bar is min(760px, 70vw); so is this, from the window's width.
const barPanelWidth = win => Math.round(Math.max(BAR_MIN_WIDTH, Math.min(BAR_PANEL_WIDTH, Number.isFinite(win.width) ? win.width * BAR_PANEL_SHARE : BAR_PANEL_WIDTH)));

// As a window: in the middle of the one you are in, a bit above the middle, where you look. A window with no
// position to tell (a minimised one) leaves it to Firefox, which centres it on the screen.
function barPlaceOver(win) {
  const known = [win.left, win.top, win.width, win.height].every(Number.isFinite);
  const width = known ? Math.round(Math.max(BAR_MIN_WIDTH, Math.min(BAR_WIDTH, win.width - BAR_SIDES))) : BAR_WIDTH;
  if (!known) return { width, height: BAR_HEIGHT };
  return { width, height: BAR_HEIGHT, left: Math.round(win.left + (win.width - width) / 2), top: Math.round(win.top + Math.max(48, (win.height - BAR_HEIGHT) / 4)) };
}

// Where the keyboard is now: the page (in every frame of it; only one has the keyboard) and
// this window's sidebar. Neither may be there to answer: a page Tidier has no access to, or
// none at all. What comes back, comes back as "bar:early" (below), once the bar's page says it
// has the keyboard ("bar:stop").
function barCatchKeys(tab, bar, type = "bar:catch") {
  const msg = { type, pressedAt: bar.pressedAt };
  if (tab?.id !== undefined && isWeb(tab.url)) browser.tabs.sendMessage(tab.id, msg).catch(() => {});
  if (tab?.windowId !== undefined) browser.runtime.sendMessage({ ...msg, windowId: tab.windowId }).catch(() => {});
  bar.caughtIn = tab;
}

// barkeys.js, in every frame of every page while Tidier has the access to all websites (a
// field you type in can be in a frame), with littlewindow.js's peek.js. It is given the bar's
// keys, so it can start catching on the key itself, which reaches the page before Tidier
// hears of it: "bar:catch" can come after the first letter. Given again when they change,
// which the bar finds out when it opens.
let barKeysScript = null, barKeysGiven = null;
async function startBarKeys(given) {
  const keys = given ? JSON.stringify((await browser.commands.getAll()).filter(c => c.name.startsWith("command-bar") && c.shortcut).map(c => c.shortcut)) : null;
  if (barKeysScript && keys === barKeysGiven) return;
  await barKeysScript?.unregister().catch(() => {});
  barKeysScript = barKeysGiven = null;
  if (!given) return;
  barKeysScript = await browser.contentScripts.register({
    matches: ["http://*/*", "https://*/*"], runAt: "document_start", allFrames: true,
    js: [{ code: `globalThis.tidierBarKeys = ${keys};` }, { file: "barkeys.js" }],
  });
  barKeysGiven = keys;
}

// The keys caught for this press, to the bar's page, once it is there.
function barEarly(bar, msg) {
  const early = { type: "early", text: typeof msg.text === "string" ? msg.text.slice(0, 200) : "", enter: msg.enter ? { inNewTab: !!msg.enter.inNewTab } : null, escape: !!msg.escape };
  bar.early = early;
  bar.port?.postMessage(early);
}
browser.runtime.onMessage.addListener((msg, sender) => {
  if (msg?.type !== "bar:early" || sender?.id !== browser.runtime.id) return;
  if (commandBar && msg.pressedAt === commandBar.pressedAt && !commandBar.early) barEarly(commandBar, msg);
});

async function barClose(bar, refocus) {
  bar.closed = true; // by you or by Tidier: a panel that goes now was not one that failed to show
  if (commandBar === bar) commandBar = null;
  if (barInPanel(bar)) {
    // In the window: its page closes it (only the page can), and Firefox gives the keyboard
    // back to where it was. Waited for, since what you chose is carried out after this, and a
    // tab selected under an open panel would not get the keyboard.
    if (!bar.port) return;
    const gone = new Promise(resolve => { bar.gone = resolve; });
    try { bar.port.postMessage({ type: "close" }); } catch (e) { return; } // gone already
    await Promise.race([gone, sleep(BAR_GONE_MS)]);
    return;
  }
  barForgetUntil = Date.now() + BAR_FORGET_MS;
  await browser.windows.remove(bar.ownWindow).catch(() => {});
  // Not after losing the focus: you clicked somewhere else, and that is where you want to be.
  if (refocus) await browser.windows.update(bar.from, { focused: true }).catch(() => {});
}

// Firefox keeps every closed window with a page in it under History, Recently Closed
// Windows, popups too: ⌘⇧T would bring the bar back rather than the tab you closed. It is
// only ever forgotten after the fact, and that list holds three by default, so with
// three real windows in it the oldest goes the first time; from then on it keeps two.
let barForgetUntil = 0;
async function barForgetClosed() {
  if (Date.now() > barForgetUntil) return;
  const page = browser.runtime.getURL(BAR_PAGE);
  for (const { window: win } of await browser.sessions.getRecentlyClosed().catch(() => [])) {
    if (win?.tabs?.length === 1 && win.tabs[0].url?.startsWith(page)) await browser.sessions.forgetClosedWindow(win.sessionId).catch(() => {});
  }
}
browser.sessions.onChanged.addListener(barForgetClosed);

browser.windows.onRemoved.addListener(id => {
  if (commandBar?.ownWindow !== id) return;
  commandBar = null; // closed by something else than the bar itself: ⌘W, say
  barForgetUntil = Date.now() + BAR_FORGET_MS;
});
// In the window, the bar lies over the tab it was opened for, and its commands act on that
// tab. Another tab coming to the front under it (⌘W is Firefox's own, and closes the tab you
// are on also from a panel; a link from another app) leaves it over a tab it knows nothing
// of: it goes. (What you chose is carried out after the bar has gone, so never under it.)
browser.tabs.onActivated.addListener(({ tabId, windowId }) => {
  const bar = commandBar;
  if (bar && barHasKeyboard() && windowId === bar.from && bar.ctx?.tab && tabId !== bar.ctx.tab.id) barClose(bar, false).catch(noteError);
});
browser.commands.onCommand.addListener((name, tab) => {
  if ((name === "command-bar" || name === "command-bar-t") && started) toggleCommandBar(tab).catch(noteError);
});

// --- What the bar works on ---------------------------------------------------------
// The selection lives only in the sidebar, which answers for its own window
// (sidebar/commandbar-link.js). No sidebar, or nothing selected: this tab.
async function barPickedTabs(windowId, tab, tabs) {
  if (!tab) return [];
  const answer = await Promise.race([
    browser.runtime.sendMessage({ type: "commandBarSelection", windowId, tabId: tab.id }).catch(() => null),
    sleep(BAR_ASK_SIDEBAR_MS).then(() => null),
  ]);
  const picked = (Array.isArray(answer) ? answer : []).map(id => tabs.find(t => t.id === id)).filter(Boolean);
  return picked.length ? picked : [tab];
}

// A row is not its tab: a placeholder's own address, title and last use say nothing.
function barAddressOf(tab, all, list) {
  if (isWeb(tab.url)) return tab.url;
  return all[syncKeyByTab.get(tab.id)]?.url ?? list.find(e => e.key === keyByTab.get(tab.id))?.url ?? null;
}

async function barContext(windowId) {
  const tabs = await browser.tabs.query({ windowId });
  const list = await getList();
  const used = new Set([...list.map(e => e.cookieStoreId), ...tabs.map(t => t.cookieStoreId)]);
  const spaces = await spaceList(used);
  const space = await spaceOf(windowId, tabs, spaces);
  const all = await getSynced();
  const tab = tabs.find(t => t.active) ?? null;
  const picked = await barPickedTabs(windowId, tab, tabs);
  const closed = (await browser.sessions.getRecentlyClosed({ maxResults: CLOSED_LOOKED_AT }).catch(() => []))
    .filter(c => c.tab && isWeb(c.tab.url));
  // What is drawn where, for the commands that act on a part of the list (listactions.js),
  // and what the pages of the selection's folder are doing: loaded or muted in any window.
  const view = await viewFor(windowId), folder = folderOfRows(view, picked.map(t => t.id));
  return {
    windowId, spaces, space, tab, picked, closed, all, list, view, folder,
    folderReals: folder ? (await Promise.all(folder.tabs.map(t => realOf(t.id)))).filter(Boolean) : [],
    doubles: doublesIn(view, all), pages: await spacePages(space), elsewhere: (await pagesOfOtherSpaces(space)).length,
    addresses: picked.map(t => barAddressOf(t, all, list)).filter(Boolean),
    key: tab ? syncKeyByTab.get(tab.id) : undefined,
  };
}

// A number in a label, when there are several: "Close 3 tabs".
const barCount = (ctx, one, many) => ctx.picked.length > 1 ? many.replace("#", ctx.picked.length) : one;
// Only the tab you are on. One other tab selected in the sidebar is not that: a command
// with no way to act on the selection is then left out, rather than acting on another tab.
const barOnlyThisTab = ctx => ctx.picked.length === 1 && ctx.picked[0].id === ctx.tab?.id;
const barMovable = ctx => ctx.picked.length > 0 && ctx.picked.every(t => !t.pinned);
// The tab you are on goes last. Closed first, it would make Firefox select another that
// may be about to go too, and a placeholder that is selected starts pulling its real tab in.
const barSelectedLast = ctx => [...ctx.picked].sort((a, b) => Number(a.active) - Number(b.active));
// A row in the bar is opened in its own space where its address is all that is left,
// so that a page of one space never opens with the logins of another.
const barInItsSpace = (ctx, row) => (row.space ? { ...ctx, space: row.space } : ctx);

// What the picked tabs can be moved to. "No folder" only for a tab that is in one, and not
// the folder they are all in already; a command with nothing to choose from is left out.
function barFolderChoices(ctx) {
  const now = new Set(ctx.picked.map(t => folderKeyOf(ctx.all, syncKeyByTab.get(t.id))));
  const folders = foldersOf(ctx.all, ctx.picked[0].cookieStoreId).filter(f => !f.live && !(now.size === 1 && now.has(f.key)));
  return [...([...now].some(Boolean) ? [{ label: "No folder", value: "" }] : []), ...folders.map(f => ({ label: f.name, value: f.key }))];
}
const barSpaceChoices = ctx => ctx.spaces.filter(s => !ctx.picked.every(t => t.cookieStoreId === s.id)).map(s => ({ label: s.name, value: s.id, space: s.id }));

// What a step of a command says above its field, so you can see what Enter will act on.
const barSpaceName = ctx => ctx.spaces.find(s => s.id === ctx.space)?.name ?? "this space";
const barTitleOf = (ctx, t) => { const e = ctx.all[syncKeyByTab.get(t.id)]; return barShort(e?.name || e?.title || t.title); }; // a placeholder's own title is the placeholder's
// A title in a sentence, short enough that the sentence still ends inside the bar.
const barShort = (text, most = 48) => { const t = String(text ?? "").trim(); return t.length > most ? `${t.slice(0, most - 1).trimEnd()}…` : t; };
const barMoving = ctx => (ctx.picked.length > 1 ? `Move ${ctx.picked.length} tabs to` : `Move “${barTitleOf(ctx, ctx.picked[0])}” to`);

// --- The commands ------------------------------------------------------------------
// One table: a name (the same as the shortcut's in manifest.json, if it has one, so the
// row can show its key), a label, when it applies, and what it does. What it needs from
// you the bar asks in its own field, a text (`ask`) or one of a list (`list`), so no
// other window or menu is involved. The commands of shortcuts.js come along at the end.
// A command that does not apply is left out; nothing is ever greyed.
//
// `run` is carried out in the queue, and everything goes through what the sidebar uses,
// so other windows follow. `free` is for what may wait for you (a page that asks before it
// closes): all of Tidier would wait with it in the queue, and the sidebar's close is not in it.
// `careful` is for what closes tabs: never moved up by use, and never what a plain Enter takes
// for a word that is only somewhere in its name (rank.js). The order here is the order among
// commands that match as well: going and making first, closing last.
const BAR_COMMANDS = [
  { name: "new-tab", label: "New tab", run: ctx => barOpenTab(ctx) },
  // A question asked in the field says what it is for (`heading`), and the row under it what
  // Enter does with what you typed (`confirm`, # for the text; `empty` with nothing typed).
  { name: "new-folder", label: "New folder", ask: ctx => ({ placeholder: "Name of the new folder", heading: `New folder in ${barSpaceName(ctx)}`, confirm: "Create “#”", empty: "Create “New folder”" }),
    run: (ctx, name) => createFolder(name || "New folder", ctx.space) },
  { name: "reopen-closed", label: "Reopen closed tab", when: ctx => ctx.closed.length > 0,
    run: ctx => barReopenClosed(ctx, barClosedItems(ctx)[0]) },
  { name: "go-to-space", each: ctx => ctx.spaces.filter(s => s.id !== ctx.space).map(s => ({ label: `Go to ${s.name}`, value: s.id, space: s.id })),
    run: (ctx, space) => switchSpace(ctx.windowId, space) },
  { name: "clear-today", label: "Clear today's tabs", careful: true, run: ctx => clearSpace(ctx.windowId, ctx.space) },
  // While the sidebar's quiet line offers Undo, here too, for the same note (quiet.js). Not
  // in the queue: Undo puts itself there.
  { name: "undo", each: ctx => { const note = quietNotes.get(ctx.windowId); return note?.undo ? [{ label: `Undo: ${note.text}`, value: String(note.id) }] : []; }, free: true,
    run: (ctx, id) => undoNote(ctx.windowId, Number(id)) },
  { name: "copy-url", label: ctx => barCount(ctx, "Copy address", "Copy # addresses"), when: ctx => ctx.addresses.length > 0,
    run: async ctx => { // and says so, as ⇧⌘C does (copyUrl, shortcuts.js)
      await navigator.clipboard.writeText(ctx.addresses.join("\n"));
      const copied = ctx.addresses.length > 1 ? `${ctx.addresses.length} addresses copied` : "Address copied";
      // (Not waited for: the queue this runs in must not stand still for a page that is slow to take it.)
      if (ctx.tab) sayDone(ctx.windowId, ctx.tab.id, copied).catch(noteError); // pagenote.js
      else say(ctx.windowId, copied, { brief: true });
    } },
  { name: "rename-tab", label: "Rename this tab", when: ctx => barOnlyThisTab(ctx) && barIsKept(ctx),
    ask: ctx => ({ placeholder: "A name, or nothing for the page's title", value: barNameOf(ctx), heading: `Rename “${barShort(barNameOf(ctx))}”`, confirm: "Call it “#”", empty: "Use the page's own title" }),
    run: (ctx, name) => renameTab(ctx.tab.id, name) },
  { name: "rename-folder", label: "Rename this folder", when: ctx => barOnlyThisTab(ctx) && !!barOwnFolderOf(ctx),
    ask: ctx => ({ placeholder: "Name of the folder", value: barOwnFolderOf(ctx).name, heading: `Rename the folder “${barShort(barOwnFolderOf(ctx).name)}”`, confirm: "Call it “#”" }),
    run: (ctx, name) => renameFolder(barFolderKey(ctx), name) },
  // (An empty new tab holds nothing to unload.)
  { name: "unload", label: ctx => barCount(ctx, "Unload this tab", "Unload # tabs"), when: ctx => ctx.picked.some(t => !t.discarded && !isGhostUrl(t.url) && !NEW_TAB_PAGES.has(t.url)), run: barUnload },
  { name: "toggle-essential", label: ctx => ctx.tab.pinned ? "Remove from essentials" : "Make this tab an essential",
    when: ctx => barOnlyThisTab(ctx) && (ctx.tab.pinned || isWeb(ctx.tab.url)),
    run: ctx => {
      // A tab Tidier has just moved or made stays marked for a moment, and what makes a pinned
      // tab an essential ignores a marked tab. This change is yours: missed, the tab would be an
      // essential and an ordinary tab at once, for good.
      syncBusy.delete(ctx.tab.id);
      busy.delete(ctx.tab.id);
      return sidebarAction(ctx.windowId, { type: "pin", tabId: ctx.tab.id, pinned: !ctx.tab.pinned });
    } },
  { name: "move-to-folder", label: ctx => barCount(ctx, "Move to folder", "Move # tabs to folder"), when: ctx => barMovable(ctx) && ctx.picked.every(t => syncKeyByTab.has(t.id) || isWeb(t.url)) && barFolderChoices(ctx).length > 0,
    list: barFolderChoices, heading: barMoving,
    placeholder: "Which folder?",
    run: async (ctx, folder) => {
      for (const t of ctx.picked) {
        await register(t.id); // a tab opened a moment ago may have no record yet, and a move would only change its place
        await sidebarAction(ctx.windowId, { type: "moveTab", tabId: t.id, folder: folder || null });
      }
    } },
  { name: "move-to-space", label: ctx => barCount(ctx, "Move to space", "Move # tabs to space"),
    when: ctx => barMovable(ctx) && ctx.addresses.length === ctx.picked.length && barSpaceChoices(ctx).length > 0, // moving is opening it again there: no address, no move
    list: barSpaceChoices, heading: barMoving,
    placeholder: "Which space?",
    // The tab menu's way (tabactions.js): in order, so they arrive in order, and the tab you
    // are on never steps onto one still to come.
    run: (ctx, space) => tabAction(ctx.windowId, { action: "space", tabIds: ctx.picked.map(t => t.id), space }) },
  { name: "close-tab", label: ctx => barCount(ctx, "Close this tab", "Close # tabs"), when: ctx => ctx.picked.length > 0, free: true, careful: true,
    run: async ctx => {
      for (const t of barSelectedLast(ctx)) {
        await closeFromSidebar(ctx.windowId, await closeTargetOf(t.id)); // what a saved placeholder with its page in another window closes (tabactions.js)
      }
    } },
  ...barListCommands(),
  { name: "settings", label: "Settings", run: () => browser.runtime.openOptionsPage() },
];

// What the tab menu's More has, and a folder's and a space's menus (listactions.js), each by
// the name it has in the shortcut table, so that its key shows. Through tabAction, as the
// menu's: one list, the selection, else the tab.
function barListCommands() {
  const act = (action, more = {}) => ctx => tabAction(ctx.windowId, { action, tabIds: ctx.picked.map(t => t.id), ...more });
  const ids = ctx => ctx.picked.map(t => t.id);
  const along = ctx => groupsOf(ctx.view, ids(ctx)).some(g => !g.live && g.rows.length > 1);
  const around = which => ctx => aroundIn(ctx.view, ids(ctx), which).length > 0;
  const inFolders = ctx => { const groups = groupsOf(ctx.view, ids(ctx)); return groups.length > 0 && groups.every(g => g.key && !g.live) && groups.reduce((n, g) => n + g.mine.length, 0) === ctx.picked.length; };
  const sortLabel = word => ctx => {
    const groups = sortGroups(ctx.view, ids(ctx));
    return groups.every(g => !g.key) ? `Sort today's tabs by ${word}` : groups.length === 1 ? `Sort this folder by ${word}` : `Sort by ${word}`;
  };
  // The folder of the selection, else of the tab you are on, as a key has it (folderCommand).
  const onFolder = action => ctx => folderCommand(ctx.windowId, ids(ctx), action);
  const folderLoaded = ctx => ctx.folderReals.filter(r => r.loaded), folderAddressed = ctx => ctx.folderReals.some(r => r.address);
  const plural = (n, one, many) => (n === 1 ? one : many.replace("#", n));
  return [
    ...Object.entries(SORT_WORDS).map(([by, word]) => ({ name: `sort-${by}`, label: sortLabel(word), when: ctx => sortGroups(ctx.view, ids(ctx)).length > 0, run: act("sort", { by }) })),
    { name: "move-top", label: ctx => barCount(ctx, "Move to the top", "Move # tabs to the top"), when: along, run: act("top") },
    { name: "move-bottom", label: ctx => barCount(ctx, "Move to the bottom", "Move # tabs to the bottom"), when: along, run: act("bottom") },
    { name: "move-up", label: ctx => barCount(ctx, "Move up one place", "Move # tabs up one place"), when: along, run: act("step", { by: -1 }) },
    { name: "move-down", label: ctx => barCount(ctx, "Move down one place", "Move # tabs down one place"), when: along, run: act("step", { by: 1 }) },
    { name: "take-out", label: ctx => barCount(ctx, "Take out of its folder", "Take # tabs out of their folders"), when: inFolders, run: act("takeOut") },
    { name: "folder-from-selection", label: ctx => barCount(ctx, "New folder with this tab", "New folder with these # tabs"),
      when: ctx => barMovable(ctx) && ctx.addresses.length === ctx.picked.length && groupsOf(ctx.view, ids(ctx)).every(g => !g.live),
      run: ctx => tabAction(ctx.windowId, { action: "newFolder", tabIds: ids(ctx), space: ctx.space }) },
    { name: "copy-markdown", label: ctx => barCount(ctx, "Copy as Markdown link", "Copy # as Markdown links"), when: ctx => ctx.addresses.length > 0, run: act("copyMarkdown") },
    { name: "close-duplicates", label: ctx => plural(ctx.doubles.length, "Close 1 duplicate tab", "Close # duplicate tabs"), when: ctx => ctx.doubles.length > 0, run: act("closeDuplicates") },
    { name: "close-others", label: "Close other tabs", when: around("others"), run: act("closeOthers") },
    { name: "close-above", label: "Close tabs above", when: around("above"), run: act("closeAbove") },
    { name: "close-below", label: "Close tabs below", when: around("below"), run: act("closeBelow") },
    { name: "recent-back", label: "Back to the tab used before", when: ctx => tabsAsDrawn(ctx.view).length > 1, run: ctx => stepRecent(ctx.windowId, 1) },
    { name: "recent-forward", label: "Forward to the tab used after", when: ctx => walkedBack(ctx.windowId), run: ctx => stepRecent(ctx.windowId, -1) },
    // The folder of the selection, else of the tab you are on, as a whole.
    { name: "folder-new-tab", label: "New tab in this folder", when: ctx => !!ctx.folder && !ctx.folder.live, run: onFolder("newTab") },
    { name: "folder-copy", label: "Copy this folder's addresses", when: folderAddressed, run: onFolder("copy") },
    { name: "folder-copy-markdown", label: "Copy this folder as Markdown links", when: folderAddressed, run: onFolder("copyMarkdown") },
    { name: "folder-reload", label: "Reload this folder", when: ctx => folderLoaded(ctx).length > 0, run: onFolder("reload") },
    { name: "folder-mute", label: "Mute this folder", when: ctx => folderLoaded(ctx).some(r => !r.tab.mutedInfo?.muted), run: onFolder("mute") },
    { name: "folder-unmute", label: "Unmute this folder", when: ctx => folderLoaded(ctx).some(r => r.tab.mutedInfo?.muted), run: onFolder("unmute") },
    { name: "folder-unload", label: "Unload this folder", when: ctx => folderLoaded(ctx).length > 0, run: onFolder("unload") },
    { name: "folder-close", label: "Close this folder's tabs", when: ctx => ctx.folder?.tabs.length > 0 && !ctx.folder.live, run: onFolder("closeAll") },
    // The space you are in, as a whole: its pages that are loaded, wherever.
    { name: "space-reload", label: "Reload this space", when: ctx => ctx.pages.length > 0, run: ctx => spaceAction(ctx.windowId, { action: "reload", space: ctx.space }) },
    { name: "space-mute", label: "Mute this space", when: ctx => ctx.pages.some(t => !t.mutedInfo?.muted), run: ctx => spaceAction(ctx.windowId, { action: "mute", space: ctx.space }) },
    { name: "space-unmute", label: "Unmute this space", when: ctx => ctx.pages.some(t => t.mutedInfo?.muted), run: ctx => spaceAction(ctx.windowId, { action: "unmute", space: ctx.space }) },
    { name: "space-unload", label: "Unload this space", when: ctx => ctx.pages.length > 0, run: ctx => unloadSpace(ctx.space, ctx.windowId) },
    { name: "space-unload-others", label: "Unload the other spaces", when: ctx => ctx.elsewhere > 0, run: ctx => unloadOtherSpaces(ctx.space, ctx.windowId) },
    { name: "folders-fold", label: ctx => (ctx.view.folders.some(f => !f.collapsed) ? "Close all folders" : "Open all folders"), when: ctx => ctx.view.folders.length > 1, run: ctx => toggleAllFolders(ctx.space) },
  ];
}

const barFolderKey = ctx => folderKeyOf(ctx.all, ctx.key);
const barOwnFolderOf = ctx => { const f = ctx.all[barFolderKey(ctx)]; return isOwnFolder(f) && !f.live ? f : null; };
const barIsKept = ctx => ctx.tab.pinned || !!ctx.all[ctx.key]?.saved;
// What you have called it, to change that, or else what the page calls itself.
const barNameOf = ctx => (ctx.tab.pinned ? ctx.list.find(e => e.key === keyByTab.get(ctx.tab.id))?.name : ctx.all[ctx.key]?.name) || ctx.tab.title;

// The tab's real page, also of a placeholder, is what can be unloaded, the tab menu's own
// way (tabactions.js): the tab you are on makes way first, as Firefox will not unload a selected tab.
function barUnload(ctx) {
  return tabAction(ctx.windowId, { action: "unload", tabIds: ctx.picked.map(t => t.id) });
}

// What shortcuts.js can do and this table does not have. A numbered key has no use here,
// and Firefox only carries out the sidebar's own command itself, on a key press.
// The bar's own keys have no action there either.
const barSharedCommands = () => COMMANDS
  .filter(c => c.action && !/^(space|tab)-\d$/.test(c.name) && c.name !== "_execute_sidebar_action" && !BAR_COMMANDS.some(b => b.name === c.name));

// The rows for the commands that apply, most used first, except what closes tabs. Each
// carries its place in the table (`order`), and its key as a Mac writes it (keys-commands.js),
// the same as on the settings page.
function barCommandRows(ctx, uses, shortcuts, os) {
  const rows = [];
  const row = (command, shown) => rows.push({
    kind: "command", id: `command:${command.name}:${shown.value ?? ""}`, name: command.name, title: shown.label, value: shown.value, space: shown.space, here: true,
    order: rows.length, careful: !!command.careful, shortcut: prettyKey(shortcuts.get(command.name), os) || null, placeholder: command.placeholder, heading: command.heading?.(ctx),
    ask: command.ask?.(ctx), list: command.list?.(ctx).map(c => ({ kind: "choice", id: `choice:${c.value}`, title: c.label, value: c.value, space: c.space, here: true })),
  });
  for (const command of BAR_COMMANDS) {
    if (command.when && !command.when(ctx)) continue;
    if (command.each) for (const shown of command.each(ctx)) row(command, shown);
    else row(command, { label: typeof command.label === "function" ? command.label(ctx) : command.label });
  }
  for (const command of barSharedCommands()) row(command, { label: command.label });
  const used = r => (r.careful ? 0 : uses[r.name] ?? 0);
  return rows.sort((a, b) => used(b) - used(a) || a.order - b.order);
}

// --- What can be found -------------------------------------------------------------
// Firefox refuses to read the values of a tab closed a moment ago. That one tab is simply
// not there; the bar must still find all the others.
const barKeysOf = pinned => Promise.all(pinned.map(t => keyOf(t).catch(() => undefined)));

// Every tab of every space, from the record: a placeholder's own address, title and last
// use are the placeholder's. Only the tab's real, live copy says when it was last used.
async function barTabItems(ctx) {
  const all = ctx.all;
  const list = await getList();
  const normal = new Set((await normalWindows()).map(w => w.id));
  const tabs = (await browser.tabs.query({})).filter(t => normal.has(t.windowId));
  const here = s => s === ctx.space || s === NO_CONTAINER; // as the sidebar shows them
  const repsByKey = new Map();
  for (const t of tabs) {
    const key = syncKeyByTab.get(t.id);
    if (key) (repsByKey.get(key) ?? repsByKey.set(key, []).get(key)).push(t);
  }
  const items = [];
  for (const [key, entry] of Object.entries(all)) {
    if (isOwnFolder(entry)) {
      items.push({ kind: "folder", id: `folder:${key}`, key, title: entry.name, space: entry.cookieStoreId, here: here(entry.cookieStoreId), live: !!entry.live });
      continue;
    }
    const reps = repsByKey.get(key);
    if (entry.group || !reps) continue; // a folder, or a tab no window has any more
    const live = reps.find(t => syncRoleByTab.get(t.id) === "live");
    const used = live && !isGhostUrl(live.url) ? live.lastAccessed : 0;
    items.push({
      kind: "tab", id: `tab:${key}`, key, title: entry.name || entry.title || entry.url, url: entry.url, icon: iconForView({ cookieStoreId: entry.cookieStoreId }, entry),
      space: entry.cookieStoreId, here: here(entry.cookieStoreId), lastUsed: Math.max(used || 0, entry.added || 0), current: reps.some(t => t.id === ctx.tab?.id),
    });
  }
  const pinned = tabs.filter(t => t.pinned);
  const keys = await barKeysOf(pinned);
  for (const e of list) {
    const copies = pinned.filter((t, i) => keys[i] === e.key);
    if (!copies.length) continue;
    items.push({
      kind: "essential", id: `essential:${e.key}`, key: e.key, title: e.name || e.title || e.url, url: e.url, icon: iconForView({ cookieStoreId: e.cookieStoreId }, e),
      space: e.cookieStoreId, here: here(e.cookieStoreId), lastUsed: Math.max(0, ...copies.filter(t => isWeb(t.url)).map(t => t.lastAccessed || 0)),
      current: copies.some(t => t.id === ctx.tab?.id),
    });
  }
  // Pages that are in no record (settings, about: pages), but not an empty new tab. An
  // extension page's address is a meaningless number, nothing to find it by or to show.
  for (const t of tabs) {
    if (t.pinned || syncKeyByTab.has(t.id) || isGhostUrl(t.url) || NEW_TAB_PAGES.has(t.url)) continue;
    const space = t.cookieStoreId === NO_CONTAINER ? null : t.cookieStoreId;
    items.push({
      kind: "tab", id: `page:${t.id}`, tabId: t.id, title: t.title || t.url, url: t.url.startsWith("moz-extension:") ? undefined : t.url, icon: iconForView(t),
      space, here: !space || here(space), lastUsed: t.lastAccessed || 0, current: t.id === ctx.tab?.id,
    });
  }
  return items;
}

// Firefox's list has the container only sometimes. Tidier's own list (archivelist.js) knows
// the space of what it holds, and whether archiving closed it or you did: a tab in both is
// shown once, as Firefox's, which brings it back with its history as ⌘⇧T does, but with
// Tidier's space and word for it.
function barClosedItems(ctx, archived = []) {
  return ctx.closed.map(({ tab, lastModified }) => {
    const ours = archived.find(a => a.url === tab.url);
    const space = tab.cookieStoreId && tab.cookieStoreId !== NO_CONTAINER ? tab.cookieStoreId : ours?.space && ours.space !== NO_CONTAINER ? ours.space : null;
    return {
      kind: "closed", id: `closed:${tab.sessionId}`, sessionId: tab.sessionId, title: tab.title || tab.url, url: tab.url, icon: iconForView(tab),
      space, here: !space || space === ctx.space, lastUsed: lastModified, why: ours && ours.why !== "closed" ? "archived" : "closed",
    };
  });
}

// From Tidier's own list of what archiving closed, when it has one (archivelist.js).
async function barArchivedItems(ctx) {
  const archived = await archivedTabs().catch(err => { noteError(err); return []; });
  return archived.map((a, i) => {
    const space = a.space && a.space !== NO_CONTAINER ? a.space : null;
    return {
      kind: "archived", id: `archived:${i}:${a.url}`, title: a.title || a.url, url: a.url, icon: a.icon || null, space, here: !space || space === ctx.space,
      lastUsed: a.when, why: a.why, archived: { space: a.space, url: a.url },
    };
  });
}

// All the bar's page needs, once.
async function barSnapshot(bar) {
  const ctx = bar.ctx = await barContext(bar.from);
  const [tabs, archived, uses, stored, commands, { os }] = await Promise.all([
    barTabItems(ctx), barArchivedItems(ctx), barUses.get(), browser.storage.local.get(BAR_ASKED),
    browser.commands.getAll(), browser.runtime.getPlatformInfo(),
  ]);
  // Only keys that work: one Firefox still has for itself (⌘D until about:keyboard clears it)
  // would be a promise the key does not keep (keys-commands.js).
  const shortcuts = await workingShortcuts(commands, os);
  if (barKeysScript) startPeek(); // the bar's keys may have changed since barkeys.js was given them
  const space = ctx.spaces.find(s => s.id === ctx.space);
  barAccents.clear();
  for (const s of ctx.spaces) if (s.color) barAccents.set(s.id, s.color);
  const closed = barClosedItems(ctx, archived), closedUrls = new Set(closed.map(c => c.url));
  return {
    pressedAt: bar.pressedAt, space: ctx.space, color: space?.color ?? null, asked: !!stored[BAR_ASKED],
    spaces: ctx.spaces.map(s => ({ id: s.id, name: s.name, color: s.color })),
    items: [...tabs, ...closed, ...archived.filter(a => !closedUrls.has(a.url)), ...barCommandRows(ctx, uses, shortcuts, os)],
  };
}

// --- Carrying out what you chose -----------------------------------------------------
// In the active space, in the place new tabs go.
async function barNewTabProps(ctx, url) {
  const index = await topOfToday(ctx.windowId, ctx.space);
  return {
    windowId: ctx.windowId, active: true,
    ...(ctx.space && ctx.space !== NO_CONTAINER ? { cookieStoreId: ctx.space } : {}),
    ...(url ? { url } : {}), ...(index === undefined ? {} : { index }),
  };
}
async function barOpenTab(ctx, url) {
  return browser.tabs.create(await barNewTabProps(ctx, url));
}

// A search you asked for here stays here, also where a rule knows the search engine's
// address. Firefox's default engine, whichever that is: only Firefox itself can read
// that, and the tab must exist first, as search.search cannot pick a container.
async function barSearch(ctx, query) {
  if (!browser.search) return; // the bar's page asks for the permission first
  const props = await barNewTabProps(ctx, "about:blank");
  const tab = await openUnruled(props);
  await browser.search.search({ query, tabId: tab.id });
}

// Selecting this window's copy of the tab does the rest, as a click in the sidebar does:
// the selected tab decides the space (spaces.js), and a placeholder pulls in its real
// tab (tabsync.js). A page in no record can be in another window only.
async function barGoToTab(ctx, row) {
  const here = await browser.tabs.query({ windowId: ctx.windowId });
  let target;
  if (row.kind === "essential") {
    const pinned = here.filter(t => t.pinned);
    target = pinned[(await barKeysOf(pinned)).indexOf(row.key)];
  } else if (row.key) {
    // (A window still being filled may not have its copy yet.)
    const live = liveTabId(row.key);
    // (Firefox throws at once on an id that is no number, rather than refusing it later.)
    target = here.find(t => syncKeyByTab.get(t.id) === row.key) ?? (live === undefined ? null : await browser.tabs.get(live).catch(() => null));
  } else {
    target = await browser.tabs.get(row.tabId).catch(() => null);
  }
  if (!target) return row.url ? barOpenTab(barInItsSpace(ctx, row), row.url) : undefined; // it has gone since the bar opened
  // (Either can go between the look above and these. As with a click in the sidebar, that is simply that.)
  if (target.windowId !== ctx.windowId) await browser.windows.update(target.windowId, { focused: true }).catch(() => {});
  await browser.tabs.update(target.id, { active: true }).catch(() => {});
}

async function barGoToFolder(ctx, key) {
  const entry = (await getSynced())[key];
  if (!isOwnFolder(entry)) return;
  if (entry.collapsed) await foldFolder(key, false); // you asked for it, so this one opens
  if (entry.cookieStoreId !== ctx.space) await switchSpace(ctx.windowId, entry.cookieStoreId);
  viewSoon(ctx.windowId);
  // With several folders open you would have to look for it: its head is marked a moment.
  browser.runtime.sendMessage({ type: "commandBarMark", windowId: ctx.windowId, folder: key }).catch(() => {});
}

// Firefox brings a tab back in the window it was closed in. If that is another one, you are
// taken there: from here it would look as if nothing had happened.
async function barReopenClosed(ctx, row) {
  const back = await browser.sessions.restore(row.sessionId).catch(err => (row.url ? barOpenTab(barInItsSpace(ctx, row), row.url) : Promise.reject(err)));
  const windowId = back?.tab?.windowId;
  if (windowId !== undefined && windowId !== ctx.windowId) await browser.windows.update(windowId, { focused: true }).catch(() => {});
}

// Through its own list when it is there: that takes it off the list too.
async function barReopenArchived(ctx, row) {
  return reopenArchived(row.archived, ctx.windowId);
}

async function barRunCommand(ctx, row, value) {
  const shared = barSharedCommands().find(c => c.name === row.name);
  const command = BAR_COMMANDS.find(c => c.name === row.name);
  if (shared) await shared.action(ctx.windowId); // goes through the queue by itself where it must
  else if (command?.free) await command.run(ctx, value ?? row.value);
  else if (command) await serial(() => command.run(ctx, value ?? row.value));
  else return;
  const uses = await barUses.get();
  barUses.set({ ...uses, [row.name]: (uses[row.name] ?? 0) + 1 });
}

async function barCarryOut(ctx, { row, inNewTab, value }) {
  if (row.kind === "command") return barRunCommand(ctx, row, value);
  if (row.kind === "search") return barSearch(ctx, row.query);
  if (row.kind === "folder") return serial(() => barGoToFolder(ctx, row.key));
  if (row.kind === "closed") return barReopenClosed(ctx, row);
  if (row.kind === "archived") return barReopenArchived(ctx, row);
  if (row.kind === "tab" || row.kind === "essential") return inNewTab && isWeb(row.url) ? barOpenTab(ctx, row.url) : barGoToTab(ctx, row); // Firefox opens no about: page for an extension
  if (row.url) return barOpenTab(ctx, row.url); // an address, a bookmark, something from history
}

// --- The bar's page ------------------------------------------------------------------
browser.runtime.onConnect.addListener(port => {
  if (port.name !== "commandbar" || port.sender?.id !== browser.runtime.id) return;
  const windowId = port.sender.tab?.windowId; // none for a panel: its page is in no tab
  const bar = commandBar;
  // The page carries the key press it was opened for, so nothing else can pass for it while
  // a bar is still opening: a bar Firefox brought back with the session, or the page opened
  // by hand, which would make its normal window "the bar", to be closed with it. The window
  // is only removed if it is the bar's own: the page could be a tab in a normal window. A
  // panel with a page of an earlier press is closed by its page, when it hears of this.
  if (!bar || !port.sender.url?.endsWith(`#${bar.pressedAt}`) || (windowId === undefined && bar.noPanel)) {
    if (windowId === undefined) { port.disconnect(); return; }
    barForgetUntil = Date.now() + BAR_FORGET_MS;
    browser.windows.get(windowId).then(win => (win.type === "popup" ? browser.windows.remove(windowId) : browser.tabs.remove(port.sender.tab.id))).catch(() => {});
    return;
  }
  if (windowId !== undefined) bar.ownWindow = windowId; // the page can be here before windows.create has answered
  barCatchKeys(bar.caughtIn, bar, "bar:stop"); // its field has the keyboard (commandbar/commandbar.js focuses it first)
  // What was typed before the page had the keyboard goes to it as soon as it is known, also
  // before the rows: the page keeps an Enter until it has rows to choose from, and it must
  // have the first letters before it chooses. (The port can be gone by then: the key pressed
  // again, say.)
  bar.port = port;
  bar.there?.(); // barOpenInWindow waits for this
  if (bar.closeOnOpen && barInPanel(bar)) { barClose(bar, true); return; } // in the window: the key was pressed again before it was there
  if (bar.early) port.postMessage(bar.early);
  bar.snapshot.then(snapshot => port.postMessage(snapshot ?? { pressedAt: bar.pressedAt, items: [], spaces: [] })).catch(() => {});
  port.onMessage.addListener(async msg => {
    if (msg.type === "close") await barClose(bar, msg.refocus);
    else if (msg.type === "seen") bar.seen = true; // a panel that has the keyboard is there (BAR_SEEN_MS)
    else if (msg.type === "asked") await browser.storage.local.set({ [BAR_ASKED]: true });
    else if (msg.type === "choose" && !bar.chosen) { // Enter pressed twice is one choice
      bar.chosen = true;
      await barClose(bar, true); // first: only the window you are in may pull a tab in, and Firefox opens what follows in the top window
      if (!bar.ctx) return;
      // The window it was opened from can have closed meanwhile: then any other will do.
      const windowId = (await browser.windows.get(bar.ctx.windowId).catch(() => null))?.id ?? (await normalWindows())[0]?.id;
      if (windowId !== undefined) await barCarryOut({ ...bar.ctx, windowId }, msg).catch(noteError);
    }
  });
  const cameAt = performance.now();
  port.onDisconnect.addListener(() => { // also when the page crashed: no window stays behind
    bar.gone?.();
    bar.port = null;
    // A panel gone as soon as it came, with nothing having closed it, was never shown
    // (BAR_SEEN_MS, above): the bar opens as a window instead, for the same press.
    const age = performance.now() - cameAt;
    if (windowId === undefined && commandBar === bar && !bar.closed && !bar.noPanel && (age < BAR_UNSEEN_MS || (!bar.seen && age < BAR_SEEN_MS))) {
      barPanelFailed(bar, "went as soon as it came");
      barOpenAsWindow(bar).catch(err => { if (commandBar === bar) commandBar = null; noteError(err); });
      return;
    }
    if (commandBar === bar) barClose(bar, false);
  });
});

