// Draws the view the background sends (sidebar-view.js) and sends back what
// you do. Text is only ever set with textContent, so a page title cannot add
// anything to the sidebar.
//
// A tab event can arrive at any moment, so rows are kept and only what changed is
// redrawn (see row, place): replacing them all would lose a click or a drag that
// is under way.

const port = browser.runtime.connect({ name: "sidebar" });
const sidebarWindow = browser.windows.getCurrent().then(w => w.id); // answered by Firefox itself, not the background part
const hello = () => sidebarWindow.then(windowId => port.postMessage({ type: "hello", windowId })); // answered with a view
// Only once every script of the page is there: Firefox can hand over the answer between two
// of them, and drawing it then stopped at the first part of another script (a tile's sound
// mark, sound.js), leaving the list undrawn until the next view, which may not come soon.
if (document.readyState === "loading") addEventListener("DOMContentLoaded", hello, { once: true });
else hello();
port.onMessage.addListener(render);

// Your own look, from managed storage (dotfiles' tidier.css, given to Firefox
// as a file in ~/Library/Application Support/Mozilla/ManagedStorage): the
// sidebar cannot be transparent, so the window's tint per space (userChrome.css)
// is repeated there, keyed on html[data-space].
const ownLook = css => {
  const style = document.createElement("style");
  style.textContent = css;
  document.head.append(style);
};
// The look of each window's sidebar when it was last drawn, put back at once. After an
// update the background part takes a second or so to answer, and until then the sidebar
// was a blank, untinted panel beside a tinted window. In localStorage: the page after an
// update is a new one, whose sessionStorage starts empty. By window, since each has its own
// space. (Window numbers start over after a restart, so the first moment there can show
// another window's space, where it showed none.)
const LAST_LOOK = "lastLook";
const readLook = () => { try { return JSON.parse(localStorage.getItem(LAST_LOOK) || "null") ?? {}; } catch (err) { return {}; } };
// Each part only when it changed: every view brings it, and a write is work for Firefox.
const showLook = look => {
  const root = document.documentElement;
  if (root.style.getPropertyValue("--accent") !== look.accent) root.style.setProperty("--accent", look.accent);
  if (root.getAttribute("data-space") !== look.space) root.setAttribute("data-space", look.space);
};
const keptLook = readLook();
let cssShown = null, viewShown = false;
if (keptLook.css) ownLook(cssShown = keptLook.css);
sidebarWindow.then(id => { if (!viewShown && keptLook.windows?.[id]) showLook(keptLook.windows[id]); }, () => {});
const keepLook = change => {
  try { localStorage.setItem(LAST_LOOK, JSON.stringify({ ...readLook(), ...change })); } catch (err) { /* then it is drawn with the first view */ }
};
browser.storage.managed.get("sidebarCSS").then(({ sidebarCSS }) => {
  if (keptLook.css !== (sidebarCSS || undefined)) keepLook({ css: sidebarCSS || undefined });
  if (sidebarCSS && sidebarCSS !== cssShown) ownLook(sidebarCSS); // (shown already, from the last view)
}, () => {});
// This window's look, kept when it changes. Windows that have closed are left out.
let lookKept = "";
async function keepWindowLook(look) {
  const id = await sidebarWindow, text = JSON.stringify(look);
  if (text === lookKept) return;
  lookKept = text;
  const open = new Set((await browser.windows.getAll().catch(() => [])).map(w => String(w.id)));
  const windows = Object.fromEntries(Object.entries(readLook().windows ?? {}).filter(([w]) => open.has(w)));
  keepLook({ windows: { ...windows, [id]: look } });
}

let view = null;
const send = msg => port.postMessage(msg);
const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

// Put `nodes` in `parent` in this order, touching only what is out of place. What goes is
// taken out first: with a row gone, each row after it would otherwise be moved up past it,
// and a row that is moved loses the keyboard's focus (keys.js) and a press under way.
function place(parent, nodes) {
  const wanted = new Set(nodes);
  let at = parent.firstChild;
  const skipGone = () => { while (at && !wanted.has(at)) { const next = at.nextSibling; at.remove(); at = next; } };
  for (const n of nodes) {
    skipGone();
    if (n === at) at = at.nextSibling;
    else parent.insertBefore(n, at);
  }
  skipGone();
}

// An attribute set only when it changes. Setting one to the value it has still counts as a
// change for Firefox, with an observer about, and a page whose title ticks makes every row's
// and every tile's be set again on each view.
const setIf = (e, name, value) => { if (e.getAttribute(name) !== value) e.setAttribute(name, value); };
const textIf = (e, text) => { if (e.textContent !== text) e.textContent = text; };

// The kept element for `id`, its content drawn again only if `state` changed.
// Not while it is being pressed: drawing replaces what is under the pointer, and
// Firefox then sends no click at all, so a page whose title ticks could not be muted
// or closed. It is drawn once it is let go, from a new view, so that everything
// reacting to a view sees it too.
const kept = new Map();
let drawn = new Set();
let heldBack = false;
function keep(id, make, state, draw) {
  drawn.add(id);
  let e = kept.get(id);
  if (!e) { e = make(); kept.set(id, e); }
  const text = JSON.stringify(state);
  if (e.dataset.state !== text && !e.classList.contains("renaming")) {
    if (e.matches(":active")) heldBack = true;
    else {
      e.dataset.state = text;
      draw(e);
    }
  }
  return e;
}
for (const type of ["pointerup", "pointercancel", "dragend"]) {
  addEventListener(type, () => { if (heldBack) { heldBack = false; setTimeout(hello); } }, true);
}

// A row that is drawn again gets a new image. One that has loaded comes straight from
// Firefox's cache, so it does not blink. One not seen yet is asked for only once its row
// comes near the view: with many tabs most rows are not. One that failed is not asked
// for again for a while (it may have been the network): a site without an icon would
// otherwise be asked at every redraw.
//
// All this only saves asking again, so it can be forgotten, and is: a sidebar stays open
// as long as its window, and a page can change its icon all day. A data: address (a
// counter drawn as an icon, say) asks nobody and can be large, so it is not remembered
// at all, and is drawn at once.
const ICON_RETRY_MS = 5 * 60000, ICONS_REMEMBERED = 1000;
const iconsLoaded = new Set(), iconsFailed = new Map(); // URL -> when it failed
const roomFor = list => { if (list.size >= ICONS_REMEMBERED) list.clear(); };
// The first letter of a title, or its first digit if it has no letter: many start with
// something else, such as "(2) Inbox" while a message waits. A title with neither gets an
// empty tile, as quiet as can be.
const letterOf = title => (String(title || "").match(/\p{L}/u) ?? String(title || "").match(/\p{N}/u))?.[0] ?? "";
// A live folder's pull request shows what it waits for where its icon would be (liveState,
// livefolders.js): they would all have GitHub's mark. Said in words in its tooltip.
const PR_WORDS = {
  review: "Waits for your review", draft: "A draft", failing: "Its checks fail", conflict: "Conflicts with its base branch",
  changes: "Changes are asked for", approved: "Approved", running: "Its checks are running", open: "Open",
};
function icon(item) {
  if (item.pr) return el("span", "pr " + (PR_WORDS[item.pr] ? item.pr : "open"));
  const failed = iconsFailed.get(item.icon);
  if (item.icon && /^(https?:|data:|moz-extension:)/.test(item.icon) && !(Date.now() - failed < ICON_RETRY_MS)) {
    const img = el("img"), asks = !item.icon.startsWith("data:");
    if (asks && !iconsLoaded.has(item.icon)) img.loading = "lazy";
    img.src = item.icon;
    img.alt = "";
    img.onload = () => { if (asks) { roomFor(iconsLoaded); iconsLoaded.add(item.icon); iconsFailed.delete(item.icon); } };
    img.onerror = () => {
      if (asks) { roomFor(iconsFailed); iconsFailed.set(item.icon, Date.now()); }
      img.replaceWith(el("span", "letter", letterOf(item.title)));
    };
    return img;
  }
  return el("span", "letter", item.blank ? "" : letterOf(item.title)); // an empty new tab: "New Tab" is no name to take a letter from
}

// A middle press in a list that can scroll starts Firefox's autoscroll (general.autoScroll,
// on by default on a Mac), and then no middle click comes at all, and the next click only
// ends the autoscroll. Firefox's own tab strip keeps it off its tabs the same way. (Not in
// a row's rename box, which starts no autoscroll, and which that would take the focus from.)
const noAutoscroll = e => { if (e.button === 1 && !e.target.closest?.("input")) e.preventDefault(); };

// Light to dark (or back) is not a change of tint, so nothing fades then (sidebar.css): only
// for the frame in which the colours change, and nothing is done until they do.
globalThis.matchMedia?.("(prefers-color-scheme: dark)").addEventListener("change", () => {
  const root = document.documentElement;
  root.classList.add("scheme-change");
  requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove("scheme-change")));
});

// What you click shows as selected at once, as in Firefox's own tab strip, rather than a
// view later (0.1 to 0.45 s with Tidier busy). Both are drawn again from the next view
// whatever it says, so a click that selected nothing shows that too. A row that is only
// shown because it was selected, in a closed folder, stays until then (.was-active): going
// now, it would pull the rows below it up under the pointer.
function showSelected(e) {
  if (e.classList.contains("active")) return; // already so: no view will come to draw it again
  for (const was of document.querySelectorAll("#essentials .active, #tabs .active")) {
    if (was === e) continue;
    was.classList.remove("active");
    was.classList.add("was-active");
    delete was.dataset.state;
  }
  e.classList.add("active");
  delete e.dataset.state;
}
// So does a tab selected any other way: a key (⌃⌘↓), a tab closing, Firefox's own tab
// strip. Firefox tells this page itself; the view that draws it comes a moment later, after
// Tidier's queue, a pause for more events and a timer of the background part's, which runs
// late when Firefox is not the app in front (0.07 to 0.25 s from the key to the view,
// measured on a Mac; the tab itself is selected in 0.02 to 0.04 s). A tab with no row here,
// another space's, waits for the view that brings its space. The list follows it
// (stayput.js).
let ownWindow = null; // not `await sidebarWindow` at each event: the mark must be there before anything else runs
sidebarWindow.then(id => { ownWindow = id; });
browser.tabs.onActivated.addListener(({ tabId, windowId }) => {
  if (windowId !== ownWindow) return;
  const e = document.querySelector(`#essentials [data-tab="${Number(tabId)}"], #tabs [data-tab="${Number(tabId)}"]`);
  if (!e) return;
  showSelected(e);
  tabsList.dispatchEvent(new Event("selectedshown"));
});

// --- Essentials ----------------------------------------------------------------
function tile(item) {
  const e = keep("tile:" + item.id, () => {
    const t = el("div");
    t.dataset.tab = item.id;
    t.setAttribute("role", "option"); // the essentials are a list to choose from (sidebar.html)
    t.draggable = true;
    t.onclick = () => { showSelected(t); send({ type: "select", tabId: item.id }); };
    t.onmousedown = noAutoscroll;
    t.onauxclick = e => { if (e.button === 1) send({ type: "close", tabId: item.id }); };
    t.oncontextmenu = e => openTabMenu(e, item.id);
    t.ondragstart = e => startDrag(e, { kind: "essential", tabId: item.id });
    return t;
  }, { ...item, tip: undefined }, t => {
    t.className = "tile" + (item.active ? " active" : "") + (item.loaded ? "" : " unloaded");
    // Named by its title alone: the tooltip with the address is its description.
    t.setAttribute("aria-label", item.title || "");
    t.setAttribute("aria-selected", String(!!item.active));
    t.replaceChildren(icon(item), ...soundMark(item));
  });
  setIf(e, "title", item.tip || item.title);
  return e;
}

// --- Tabs ----------------------------------------------------------------------
function row(item, folderKey) {
  const r = keep("tab:" + item.id, () => {
    const e = el("div");
    e.dataset.tab = item.id;
    e.setAttribute("role", "treeitem"); // a flat tree, by level: folders' heads and loose tabs 1, their tabs 2
    e.draggable = true;
    e.onclick = ev => { if (byHand(ev)) pickedByHand = true; showSelected(e); send({ type: "select", tabId: item.id }); };
    e.onmousedown = noAutoscroll;
    e.onmouseleave = () => { if (stillDim.delete(e.dataset.tab)) e.classList.remove("still-dim"); };
    e.onauxclick = secondClick.acts(ev => { if (ev.button === 1) closeByPointer(item.id, ev); });
    e.oncontextmenu = ev => openTabMenu(ev, item.id);
    e.ondragstart = ev => startDrag(ev, { kind: "tab", tabId: item.id });
    return e;
  }, { ...item, tip: undefined, folderKey: folderKey ?? null }, e => { // a tooltip is not drawn: some pages change their address as you scroll, and a row drawn again can lose a click or a drag
    e.className = "row tab" + (item.active ? " active" : "") + (item.loaded ? "" : " unloaded");
    e.setAttribute("aria-label", item.title || "");
    e.setAttribute("aria-selected", String(!!item.active));
    const parts = [icon(item), el("span", "title", item.title)];
    parts.push(...soundMark(item));
    const close = el("button", "close", "×");
    // The list is one stop for Tab (keys.js): a row's × is for the pointer, and ⌫ closes by key.
    // As a stop of its own, ⇧Tab from the cursor's row would land on the × of the row above.
    close.tabIndex = -1;
    close.title = closeTitle(item, folderKey);
    close.onclick = secondClick.acts(ev => {
      ev.stopPropagation();
      // A loaded saved tab only unloads, in its place. An unloaded row lights up under the
      // mouse, so it would look as if nothing happened, and a second click would remove it:
      // it stays as quiet as it now is until the mouse leaves it.
      if (item.loaded && savedIn(folderKey) && byHand(ev)) stillDim.add(String(item.id));
      closeByPointer(item.id, ev);
    });
    parts.push(close);
    e.replaceChildren(...parts);
  });
  setIf(r, "title", (item.pr ? (PR_WORDS[item.pr] ?? PR_WORDS.open) + "\n" : "") + (item.tip || item.title));
  setIf(r, "data-folder", folderKey ?? "");
  const level = folderKey == null ? "1" : "2";
  setIf(r, "aria-level", level); // only when it moved: a view comes with every tab event
  return r;
}

// What × does says itself, as it is not the same on every row (closeAction, common.js): a
// saved tab that is loaded only unloads, in its place, and a second click would remove it.
// (A live folder's pull requests are not saved: the search decides what is in them.)
const savedIn = folderKey => !!folderKey && !!view && !view.folders.find(f => f.key === folderKey)?.live;
const closeTitle = (item, folderKey) => (!savedIn(folderKey) ? "Close" : item.loaded ? "Unload (it stays in the folder)" : "Remove from the folder");

// --- A row that closes folds away ---------------------------------------------------
// A row you close folds away at once, and the rows below come up into its place in one soft
// move, as in Zen and Arc. The click itself starts it, before the tab has closed, so the
// list answers the hand and not the round trip; and a row that goes for any other reason (⌘W,
// another window, archiving) leaves a room that folds the same way, from the height the row
// had. It was not always so: a row closed with the mouse once left an empty room while the
// pointer was in the list, so that nothing slid under the pointer. That left holes in the
// list, which then filled late and all at once. A double click on × still closes one tab
// only: the click that follows one that acted does nothing (secondclick.js).
//
// A row whose tab did not close after all comes back: a page that asks before it closes and
// that you keep, or anything else that refused.
//
// Two things are still held while the pointer is in the list, and let go when it leaves or
// has rested there a few seconds (Firefox does not always say that the pointer has left:
// another app taken with the keyboard, a menu opened over the list): the row a closed
// folder shows because its tab was selected, when you select another (sidebar.css), and a
// saved tab just unloaded with its ×, which stays as dim as it now is.
const byHand = e => e.isTrusted && e.detail > 0;
let pickedByHand = false; // the last row selected was clicked with the mouse
const tabsList = document.getElementById("tabs");
const lingering = new Set(); // tab ids of rows a closed folder keeps showing for now
const stillDim = new Set(); // tab ids of saved tabs just unloaded with their ×, until the mouse leaves them
let roomsInSpace = null;
let foldsRows = false; // this view is of the list drawn before it: what has gone from it folds away
const holding = () => tabsList.matches(":hover");
const HELD_MS = 3000; // longer than the next click takes, shorter than a row out of place is looked at
let heldTimer = null;
function heldFromNow() {
  if (!heldTimer) tabsList.addEventListener("mousemove", heldFromNow, { passive: true });
  clearTimeout(heldTimer);
  heldTimer = setTimeout(letRoomsGo, HELD_MS);
}

const ROW_FOLD_MS = 180, ROW_FOLD_EASE = "cubic-bezier(.2, .7, .2, 1)"; // tokens.css's --soft, for the room; the row's own is sidebar.css
const CLOSE_REFUSED_MS = 1500; // a tab that is still there by then did not close
const lessMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const closingRows = new Map(); // tab id, as dataset.tab -> the timer that lets its row back
// What × does to a row is not the same on every row (closeTitle, below): a saved tab that is
// loaded only unloads, in its place, and its row stays.
const rowStays = row => savedIn(row.dataset.folder || null) && !row.classList.contains("unloaded");
// Close a tab from its row, by the pointer or a key: the row folds away as it is asked.
function closeRow(id) {
  const row = kept.get("tab:" + id), key = String(id);
  if (row?.isConnected && !rowStays(row)) {
    row.classList.add("closing");
    clearTimeout(closingRows.get(key));
    closingRows.set(key, setTimeout(() => { closingRows.delete(key); kept.get("tab:" + id)?.classList.remove("closing"); }, CLOSE_REFUSED_MS));
  }
  send({ type: "close", tabId: id });
}
function closeByPointer(id, e) {
  if (byHand(e) && holding()) heldFromNow(); // for a row that stays dim (stillDim)
  closeRow(id);
}
// A row drawn again has lost its classes: one still folding keeps folding.
function keepClosing() {
  for (const key of closingRows.keys()) kept.get("tab:" + key)?.classList.add("closing");
}

// The room a row leaves as it goes: as high as the row is at that moment (its own fold may
// be half way), folding to nothing and then gone. None for a row that has folded already,
// one that was not shown, or where less motion is asked for: the rows below are then
// simply where they belong.
function foldingRoom(row) {
  if (!foldsRows || lessMotion()) return null;
  const height = row.getBoundingClientRect().height;
  if (height < 1) return null;
  const style = getComputedStyle(row), full = parseFloat(style.getPropertyValue("--row")) || height;
  const room = el("div", "room");
  const fold = room.animate([{ height: `${height}px`, marginBottom: style.marginBottom }, { height: "0px", marginBottom: "0px" }],
    { duration: Math.max(40, ROW_FOLD_MS * Math.min(1, height / full)), easing: ROW_FOLD_EASE });
  fold.onfinish = fold.oncancel = () => room.remove();
  return room;
}

// `nodes` for `parent`, with a folding room where a row has gone, after whatever came
// before it. A row that comes in just there takes the place instead: a saved tab closed
// while loaded becomes a new placeholder in its place (unloadSaved, tabsync.js), and stays
// dim if it was to. A room still folding from the view before stays where it is.
function withRooms(parent, nodes) {
  if (!view) return nodes;
  const wanted = new Set(nodes), out = [...nodes];
  let at = 0;
  for (const child of [...parent.children]) {
    if (wanted.has(child)) { at = out.indexOf(child) + 1; continue; }
    const comes = out[at], takesItsPlace = comes?.classList.contains("tab") && comes.parentNode !== parent;
    let room = child.classList.contains("room") ? child : null;
    if (!room && child.classList.contains("tab")) {
      if (takesItsPlace) { if (stillDim.delete(child.dataset.tab)) stillDim.add(comes.dataset.tab); continue; }
      room = foldingRoom(child);
    }
    if (!room || takesItsPlace) continue;
    out.splice(at++, 0, room);
  }
  return out;
}
function letRoomsGo() {
  for (const row of tabsList.querySelectorAll(".lingers, .still-dim")) row.classList.remove("lingers", "still-dim");
  lingering.clear();
  stillDim.clear();
  tabsList.style.removeProperty("--held"); // the end the quiet line's room left (note.js)
  clearTimeout(heldTimer);
  heldTimer = null;
  tabsList.removeEventListener("mousemove", heldFromNow);
}
tabsList.addEventListener("mouseleave", letRoomsGo);
// After a view: the row a closed folder showed for the selected tab, which is no longer
// selected, stays while the pointer is in the list. (Its draw resets its classes.)
let selectedRow = null;
function keepLingering() {
  const was = selectedRow;
  selectedRow = tabsList.querySelector(".tab.active")?.dataset.tab ?? null;
  if (was && was !== selectedRow && pickedByHand && holding() && kept.get("tab:" + was)?.closest(".folder.collapsed")) { lingering.add(was); heldFromNow(); }
  if (was !== selectedRow) pickedByHand = false;
  for (const id of lingering) kept.get("tab:" + id)?.classList.add("lingers");
  for (const id of stillDim) kept.get("tab:" + id)?.classList.add("still-dim");
}

// --- Folders -------------------------------------------------------------------
const DOUBLE_CLICK_MS = 500; // the longest a second click usually takes (a Mac's default)
const FOLD_SHOWS_MS = 250; // most double clicks have their second click by then
const foldsWaiting = new Map(); // folder key -> whether a click closed it, while it waits for a second click
function folder(f) {
  const closed = foldsWaiting.get(f.key) ?? f.collapsed;
  const box = keep("folder:" + f.key, () => {
    const b = el("div", "folder");
    b.setAttribute("role", "none");
    const head = el("div", "row head");
    head.dataset.folderHead = f.key;
    head.setAttribute("role", "treeitem");
    head.setAttribute("aria-level", "1");
    // A double click renames. Its first click would fold the folder, and that unloads the
    // tabs in it (foldrest.js): a new name must not cost you your pages. So the background
    // is told of a click with the mouse only once no second click has come, and the fold
    // shows only after FOLD_SHOWS_MS: a double click mostly renames with nothing folding and
    // unfolding first, and the list below stays where it is. A slower one undoes what showed,
    // and nothing is sent. A click from the keys (detail 0) has no second one: it folds at once.
    // (Only the class and the count change here: Firefox sends no dblclick if the click
    // before it took the element under the pointer away, as drawing the head again would.)
    let foldSoon = null, showSoon = null;
    const show = closing => {
      b.classList.toggle("collapsed", closing);
      head.setAttribute("aria-expanded", String(!closing));
      head.querySelector(".count").textContent = closing && b.lastChild.querySelectorAll(".tab").length || "";
      if (closing) for (const room of b.querySelectorAll(".room")) room.remove(); // a closed folder shows no tab, nor where one was
    };
    const wait = () => { clearTimeout(foldSoon); clearTimeout(showSoon); };
    const undoShown = () => { if (foldsWaiting.has(f.key)) show(!foldsWaiting.get(f.key)); foldsWaiting.delete(f.key); };
    head.onclick = e => {
      if (b.classList.contains("renaming")) return;
      wait();
      const closing = !(foldsWaiting.get(f.key) ?? b.classList.contains("collapsed"));
      const fold = () => { foldsWaiting.delete(f.key); send({ type: "foldFolder", key: f.key, collapsed: closing }); };
      if (!e.detail) { show(closing); return fold(); }
      if (e.detail > 1) return undoShown(); // the second of a double click, which renames
      foldSoon = setTimeout(fold, DOUBLE_CLICK_MS);
      showSoon = setTimeout(() => { foldsWaiting.set(f.key, closing); show(closing); }, FOLD_SHOWS_MS);
    };
    head.ondblclick = () => {
      wait();
      undoShown();
      if (!f.live) rename(f.key);
    };
    head.oncontextmenu = e => openFolderMenu(e, f.key, f.live); // menu.js: with More, and marked as a row and a dot are
    head.draggable = true;
    head.ondragstart = e => startDrag(e, { kind: "folder", key: f.key });
    const children = el("div", "children");
    children.setAttribute("role", "none");
    b.append(head, children);
    return b;
  }, { name: f.name, closed, live: f.live, n: f.tabs.length, sound: f.sound, soundTabId: f.soundTabId }, b => {
    b.classList.toggle("collapsed", closed);
    b.classList.toggle("live", !!f.live);
    b.dataset.key = f.key;
    b.firstChild.title = f.name;
    b.firstChild.setAttribute("aria-label", f.name);
    b.firstChild.setAttribute("aria-expanded", String(!closed));
    b.firstChild.replaceChildren(el("span", "chevron", "▾"), el("span", "title", f.name), ...soundMark(f), el("span", "count", closed && f.tabs.length ? String(f.tabs.length) : ""));
  });
  place(box.lastChild, withRooms(box.lastChild, f.tabs.map(t => row(t, f.key))));
  return box;
}

function rename(key) {
  const box = kept.get("folder:" + key);
  if (!box || box.classList.contains("renaming")) return;
  const head = box.firstChild, title = head.querySelector(".title");
  const input = el("input", "rename");
  input.value = title.textContent;
  box.classList.add("renaming");
  head.draggable = false;
  title.replaceWith(input);
  input.focus();
  input.select();
  let done = false;
  const finish = save => {
    if (done) return;
    done = true;
    box.classList.remove("renaming");
    head.draggable = true;
    input.replaceWith(el("span", "title", save ? input.value.trim() || title.textContent : title.textContent));
    if (save && input.value.trim()) send({ type: "renameFolder", key, name: input.value.trim() });
    delete box.dataset.state; // drawn anew with the next view
  };
  input.onblur = () => finish(true);
  input.onclick = e => e.stopPropagation();
  input.onkeydown = e => {
    e.stopPropagation();
    if (e.key === "Enter") finish(true);
    else if (e.key === "Escape") finish(false);
  };
}

// --- Everything -------------------------------------------------------------------
// The notice's words; its × to put it away is sidebar/isolation.js's.
const problemText = el("span", "text");
document.getElementById("problem").append(problemText);
let renameNext = false;
let folderKeys = new Set();
function render(next) {
  view = next;
  drawn = new Set();
  const space = view.spaces.find(s => s.id === view.space), root = document.documentElement;
  foldsRows = view.space === roomsInSpace; // another space's list is not this one with rows gone
  if (!foldsRows) { roomsInSpace = view.space; letRoomsGo(); } // another list: nothing in it was where you pointed
  const look = { space: view.space || "", accent: space?.color || "#7a7a80" };
  // A space comes in as one piece: a folder drawn for it now does not fade in on its own,
  // after everything else (sidebar.css, html.space-arriving), as a folder that appears does.
  // The class goes once what is new has its style, also when drawing stops half way (a
  // view can come before every script of this page is there), so it can never stay.
  if (root.getAttribute("data-space") !== look.space) {
    root.classList.add("space-arriving");
    queueMicrotask(() => { root.getBoundingClientRect(); root.classList.remove("space-arriving"); });
  }
  viewShown = true;
  showLook(look);
  keepWindowLook(look).catch(() => {}); // (only the first moment after an update depends on it)

  const hiding = document.getElementById("hiding");
  if (hiding.hidden !== !view.needsHiding) hiding.hidden = !view.needsHiding;
  // Right after moving over (aftermove.js); put away with its ×, it fades in place first.
  const askHiding = document.getElementById("ask-hiding");
  if (view.askHiding && askHiding.hidden) askHiding.hidden = false;
  else if (!view.askHiding && !askHiding.hidden && !askHiding.classList.contains("going")) askHiding.hidden = true;
  // The lasting notice goes once you put it away with its × (isolation.js): under the pointer
  // it fades in place first, so the list does not come into its room at the moment of the click.
  const problem = document.getElementById("problem");
  if (view.problem) {
    if (problem.classList.contains("going")) problem.classList.remove("going");
    if (problem.hidden) problem.hidden = false;
    textIf(problemText, view.problem);
  } else if (!problem.hidden && problem.matches(":hover")) goQuietly(problem);
  else if (!problem.hidden && !problem.classList.contains("going")) problem.hidden = true;

  place(document.getElementById("essentials"), view.essentials.map(tile));
  textIf(document.getElementById("space-name"), space?.name || "");

  const list = view.folders.map(folder);
  if (view.folders.length && view.tabs.length) list.push(keep("divider", () => { const d = el("div", "divider"); d.setAttribute("role", "none"); return d; }, 0, () => {}));
  list.push(...view.tabs.map(t => row(t, null)));
  place(tabsList, withRooms(tabsList, list));
  keepLingering();
  keepClosing();

  // (What another file put at the end of the bar stays there: the place to drop a tab for a new space, isolation.js.)
  const bar = document.getElementById("spaces");
  place(bar, [...view.spaces.map(s => keep("space:" + s.id, () => {
    const b = el("button", "space");
    b.dataset.space = s.id;
    b.onclick = () => send({ type: "space", space: s.id });
    b.append(el("span", "dot"));
    return b;
  }, { s, active: s.id === view.space }, b => {
    b.classList.toggle("active", s.id === view.space);
    b.title = s.name;
    // Named by its space, whatever marks it has (a speaker's own tooltip was its name), and
    // the one you are in said to be so.
    b.setAttribute("aria-label", s.name);
    if (s.id === view.space) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current");
    b.style.setProperty("--color", s.color);
    // Its own icon, if its name starts with one (spaceIcon, spacemenu.js), in the dot's place.
    const dot = b.querySelector(".dot"), { icon } = spaceIcon(s.name);
    if (dot.textContent !== icon) dot.textContent = icon;
    dot.classList.toggle("emoji", !!icon);
    spaceSound(b, s);
  })), ...bar.querySelectorAll(":scope > .new-space")]);

  for (const id of kept.keys()) if (!drawn.has(id)) kept.delete(id);
  const keys = new Set(view.folders.map(f => f.key));
  // Not while something else has the keyboard, such as Firefox's note about hidden tabs: the
  // box would get it back only later, with its name still all selected, and the letters typed
  // meanwhile went elsewhere, so the last few would silently become the name (once "re").
  // The folder keeps its name, and you rename it, which shows that nothing was taken.
  // (A page not on show has no keyboard to lose and nothing over it: Tidier's sidebar page
  // in a background tab, as the smoke test has it, which is never focused.)
  if (renameNext) for (const k of keys) if (!folderKeys.has(k)) { renameNext = false; if ((document.hasFocus?.() ?? true) || document.hidden) rename(k); }
  folderKeys = keys;
}

document.getElementById("new-tab").onclick = () => send({ type: "newTab", space: view?.space });
document.getElementById("new-folder").onclick = () => { renameNext = true; send({ type: "newFolder", space: view?.space }); };
document.getElementById("tabs").oncontextmenu = e => {
  if (view && e.target.id === "tabs") openMenu(e, listMenu());
};
// Asking needs your click, so it is here and not in the background.
document.getElementById("allow-hiding").onclick = () => browser.permissions.request({ permissions: ["tabHide"] });
// Right after moving over, until the first switch of space (aftermove.js): Firefox's note
// about hidden tabs hangs over this part of the sidebar, with Disable Extension where New tab is.
// Put away, it fades where it is (goQuietly, isolation.js), and the next click there does nothing.
document.getElementById("ask-hiding-no").onclick = secondClick.acts(() => {
  goQuietly(document.getElementById("ask-hiding"));
  send({ type: "askHidingSeen" });
});
