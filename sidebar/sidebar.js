// Draws the view the background sends (sidebar-view.js) and sends back what
// you do. Text is only ever set with textContent, so a page title cannot add
// anything to the sidebar.
//
// A tab event can arrive at any moment, so rows are kept and only what changed is
// redrawn (see row, place): replacing them all would lose a click or a drag that
// is under way.

const port = browser.runtime.connect({ name: "sidebar" });
const hello = () => browser.windows.getCurrent().then(w => port.postMessage({ type: "hello", windowId: w.id })); // answered with a view
hello();
port.onMessage.addListener(render);

// Your own look, from managed storage (dotfiles' tidier.css, given to Firefox
// as a file in ~/Library/Application Support/Mozilla/ManagedStorage): the
// sidebar cannot be transparent, so the window's tint per space (userChrome.css)
// is repeated there, keyed on html[data-space].
browser.storage.managed.get("sidebarCSS").then(({ sidebarCSS }) => {
  if (!sidebarCSS) return;
  const style = document.createElement("style");
  style.textContent = sidebarCSS;
  document.head.append(style);
}, () => {});

let view = null;
const send = msg => port.postMessage(msg);
// Folds with Sidebery's folder pages are kept for this sidebar only; Tidier's own
// folders keep theirs in the record.
const collapsed = new Set();

const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

// Put `nodes` in `parent` in this order, touching only what is out of place.
function place(parent, nodes) {
  let at = parent.firstChild;
  for (const n of nodes) {
    if (n === at) at = at.nextSibling;
    else parent.insertBefore(n, at);
  }
  while (at) { const next = at.nextSibling; at.remove(); at = next; }
}

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
function icon(item) {
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

// --- Essentials ----------------------------------------------------------------
function tile(item) {
  const e = keep("tile:" + item.id, () => {
    const t = el("div");
    t.dataset.tab = item.id;
    t.draggable = !!view?.alone;
    t.onclick = () => send({ type: "select", tabId: item.id });
    t.onmousedown = noAutoscroll;
    t.onauxclick = e => { if (e.button === 1) send({ type: "close", tabId: item.id }); };
    t.oncontextmenu = e => { if (view?.alone) openTabMenu(e, item.id); else browser.menus.overrideContext({ context: "tab", tabId: item.id }); };
    t.ondragstart = e => startDrag(e, { kind: "essential", tabId: item.id });
    return t;
  }, { ...item, tip: undefined }, t => {
    t.className = "tile" + (item.active ? " active" : "") + (item.loaded ? "" : " unloaded");
    t.replaceChildren(icon(item), ...(view.alone ? soundMark(item) : []));
  });
  e.title = item.tip || item.title;
  return e;
}

// --- Tabs ----------------------------------------------------------------------
function row(item, folderKey) {
  const r = keep("tab:" + item.id, () => {
    const e = el("div");
    e.dataset.tab = item.id;
    e.draggable = !!view?.alone;
    e.onclick = ev => { if (byHand(ev)) pickedByHand = true; send({ type: "select", tabId: item.id }); };
    e.onmousedown = noAutoscroll;
    e.onmouseleave = () => { if (stillDim.delete(e.dataset.tab)) e.classList.remove("still-dim"); };
    e.onauxclick = secondClick.acts(ev => { if (ev.button === 1) closeByPointer(item.id, ev); });
    e.oncontextmenu = ev => { if (view?.alone) openTabMenu(ev, item.id); else browser.menus.overrideContext({ context: "tab", tabId: item.id }); };
    e.ondragstart = ev => startDrag(ev, { kind: "tab", tabId: item.id });
    return e;
  }, { ...item, tip: undefined, folderKey: folderKey ?? null }, e => { // a tooltip is not drawn: some pages change their address as you scroll, and a row drawn again can lose a click or a drag
    e.className = "row tab" + (item.active ? " active" : "") + (item.loaded ? "" : " unloaded");
    const parts = [icon(item), el("span", "title", item.title)];
    parts.push(...soundMark(item));
    const close = el("button", "close", "×");
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
  r.title = item.tip || item.title;
  r.dataset.folder = folderKey ?? "";
  return r;
}

// What × does says itself, as it is not the same on every row (closeAction, common.js): a
// saved tab that is loaded only unloads, in its place, and a second click would remove it.
// (A live folder's pull requests are not saved: the search decides what is in them.)
const savedIn = folderKey => !!folderKey && !!view?.alone && !view.folders.find(f => f.key === folderKey)?.live;
const closeTitle = (item, folderKey) => (!savedIn(folderKey) ? "Close" : item.loaded ? "Unload (it stays in the folder)" : "Remove from the folder");

// --- A row you close keeps its room -----------------------------------------------
// A row closed with the mouse (its ×, a middle click) leaves an empty room of its own
// height while the pointer is in the list, so the row below does not slide up under the
// pointer, and at the end of a scrolled list the rows above do not slide down; it closes
// once the pointer has left the list. So does a row that a closed folder shows because its
// tab was selected (sidebar.css): you selected another, and it stays until you leave.
// Nothing else is held: what you did not point at goes at once. (Only for the real mouse:
// a key has no place in the list, and a script's click is no pointer.)
const byHand = e => e.isTrusted && e.detail > 0;
let pickedByHand = false; // the last row selected was clicked with the mouse
const tabsList = document.getElementById("tabs");
const keepsRoom = new Set(); // tab ids closed with the pointer, as strings like dataset.tab
const lingering = new Set(); // tab ids of rows a closed folder keeps showing for now
const stillDim = new Set(); // tab ids of saved tabs just unloaded with their ×, until the mouse leaves them
let roomsInSpace = null;
const holding = () => tabsList.matches(":hover");
function closeByPointer(id, e) {
  if (byHand(e) && holding()) keepsRoom.add(String(id));
  send({ type: "close", tabId: id });
}
// `nodes` for `parent`, with a room where a row has gone that is to keep one, after
// whatever came before it. A row that comes in just there takes the room instead: a saved
// tab closed while loaded becomes a new placeholder in its place (unloadSaved, tabsync.js),
// and stays dim if it was to.
function withRooms(parent, nodes) {
  if (!holding() || !view?.alone) return nodes;
  const wanted = new Set(nodes), out = [...nodes];
  let at = 0;
  for (const child of [...parent.children]) {
    if (wanted.has(child)) { at = out.indexOf(child) + 1; continue; }
    let room = child.classList.contains("room") ? child : null;
    if (!room && keepsRoom.delete(child.dataset.tab)) {
      room = el("div", "room");
      if (stillDim.delete(child.dataset.tab)) room.dataset.dim = "1";
    }
    if (!room) continue;
    const comes = out[at];
    if (comes?.classList.contains("tab") && comes.parentNode !== parent) {
      if (room.dataset.dim) stillDim.add(comes.dataset.tab);
      continue;
    }
    out.splice(at++, 0, room);
  }
  return out;
}
function letRoomsGo() {
  for (const room of tabsList.querySelectorAll(".room")) room.remove();
  for (const row of tabsList.querySelectorAll(".lingers, .still-dim")) row.classList.remove("lingers", "still-dim");
  keepsRoom.clear();
  lingering.clear();
  stillDim.clear();
  tabsList.style.removeProperty("--held"); // the end the quiet line's room left (note.js)
}
tabsList.addEventListener("mouseleave", letRoomsGo);
// After a view: the row a closed folder showed for the selected tab, which is no longer
// selected, stays while the pointer is in the list. (Its draw resets its classes.)
let selectedRow = null;
function keepLingering() {
  const was = selectedRow;
  selectedRow = tabsList.querySelector(".tab.active")?.dataset.tab ?? null;
  if (was && was !== selectedRow && pickedByHand && holding() && kept.get("tab:" + was)?.closest(".folder.collapsed")) lingering.add(was);
  if (was !== selectedRow) pickedByHand = false;
  for (const id of lingering) kept.get("tab:" + id)?.classList.add("lingers");
  for (const id of stillDim) kept.get("tab:" + id)?.classList.add("still-dim");
}

// --- Folders -------------------------------------------------------------------
const DOUBLE_CLICK_MS = 500; // the longest a second click usually takes (a Mac's default)
const FOLD_SHOWS_MS = 250; // most double clicks have their second click by then
const foldsWaiting = new Map(); // folder key -> whether a click closed it, while it waits for a second click
function folder(f) {
  const closed = view.alone ? foldsWaiting.get(f.key) ?? f.collapsed : collapsed.has(f.key);
  const box = keep("folder:" + f.key, () => {
    const b = el("div", "folder");
    const head = el("div", "row head");
    head.dataset.folderHead = f.key;
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
      head.querySelector(".count").textContent = closing && b.lastChild.querySelectorAll(".tab").length || "";
      if (closing) for (const room of b.querySelectorAll(".room")) room.remove(); // a closed folder shows no tab, nor where one was
    };
    const wait = () => { clearTimeout(foldSoon); clearTimeout(showSoon); };
    const undoShown = () => { if (foldsWaiting.has(f.key)) show(!foldsWaiting.get(f.key)); foldsWaiting.delete(f.key); };
    head.onclick = e => {
      if (b.classList.contains("renaming")) return;
      if (view.alone) {
        wait();
        const closing = !(foldsWaiting.get(f.key) ?? b.classList.contains("collapsed"));
        const fold = () => { foldsWaiting.delete(f.key); send({ type: "foldFolder", key: f.key, collapsed: closing }); };
        if (!e.detail) { show(closing); return fold(); }
        if (e.detail > 1) return undoShown(); // the second of a double click, which renames
        foldSoon = setTimeout(fold, DOUBLE_CLICK_MS);
        showSoon = setTimeout(() => { foldsWaiting.set(f.key, closing); show(closing); }, FOLD_SHOWS_MS);
      } else {
        if (collapsed.has(f.key)) collapsed.delete(f.key); else collapsed.add(f.key);
        b.classList.toggle("collapsed");
      }
    };
    head.ondblclick = () => {
      wait();
      undoShown();
      if (view.alone && !f.live) rename(f.key);
    };
    head.oncontextmenu = e => { if (view.alone) openMenu(e, folderMenu(f.key, f.live)); };
    head.draggable = !!view?.alone;
    head.ondragstart = e => startDrag(e, { kind: "folder", key: f.key });
    b.append(head, el("div", "children"));
    return b;
  }, { name: f.name, closed, live: f.live, n: f.tabs.length, sound: f.sound, soundTabId: f.soundTabId }, b => {
    b.classList.toggle("collapsed", closed);
    b.classList.toggle("live", !!f.live);
    b.dataset.key = f.key;
    b.firstChild.title = f.name;
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
  if (view.space !== roomsInSpace) { roomsInSpace = view.space; letRoomsGo(); } // another list: nothing in it was where you pointed
  const space = view.spaces.find(s => s.id === view.space);
  document.documentElement.style.setProperty("--accent", space?.color || "#7a7a80");
  document.documentElement.dataset.space = view.space || "";
  document.documentElement.classList.toggle("alone", !!view.alone);

  document.getElementById("hiding").hidden = !view.needsHiding;
  // The lasting notice goes once you put it away with its × (isolation.js): under the pointer
  // it fades in place first, so the list does not come into its room at the moment of the click.
  const problem = document.getElementById("problem");
  if (view.problem) {
    problem.classList.remove("going");
    problem.hidden = false;
    problemText.textContent = view.problem;
  } else if (!problem.hidden && problem.matches(":hover")) goQuietly(problem);
  else if (!problem.classList.contains("going")) problem.hidden = true;

  place(document.getElementById("essentials"), view.essentials.map(tile));
  document.getElementById("space-name").textContent = view.alone ? space?.name || "" : "";

  const list = view.folders.map(folder);
  if (view.folders.length && view.tabs.length) list.push(keep("divider", () => el("div", "divider"), 0, () => {}));
  list.push(...view.tabs.map(t => row(t, null)));
  place(tabsList, withRooms(tabsList, list));
  keepLingering();

  place(document.getElementById("spaces"), view.spaces.map(s => keep("space:" + s.id, () => {
    const b = el("button", "space");
    b.dataset.space = s.id;
    b.onclick = () => send({ type: "space", space: s.id });
    b.append(el("span", "dot"));
    return b;
  }, { s, active: s.id === view.space }, b => {
    b.classList.toggle("active", s.id === view.space);
    b.title = s.name;
    b.style.setProperty("--color", s.color);
    spaceSound(b, s);
  })));

  for (const id of kept.keys()) if (!drawn.has(id)) kept.delete(id);
  const keys = new Set(view.folders.map(f => f.key));
  if (renameNext) for (const k of keys) if (!folderKeys.has(k)) { renameNext = false; rename(k); }
  folderKeys = keys;
}

document.getElementById("new-tab").onclick = () => send({ type: "newTab", space: view?.space });
document.getElementById("new-folder").onclick = () => { renameNext = true; send({ type: "newFolder", space: view?.space }); };
document.getElementById("tabs").oncontextmenu = e => {
  if (view?.alone && e.target.id === "tabs") openMenu(e, listMenu());
};
// Asking needs your click, so it is here and not in the background.
document.getElementById("allow-hiding").onclick = () => browser.permissions.request({ permissions: ["tabHide"] });
