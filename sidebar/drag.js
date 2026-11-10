// --- Dragging -------------------------------------------------------------------
// A tab can go before or after another tab, into a folder, to a place among the
// essentials (pinned) or to a space on the bar. An essential can go among the
// essentials, or to the list (unpinned). A folder can go among the folders.
//
// A mark means that a drop there does something. Right next to what you are dragging
// nothing would move, so there is no mark, and a drop there sends nothing.
let dragging = null;

// × and the sound button sit inside a draggable row, and a drag can start from any
// child of it, so a hand that shakes during a click would drag the row and lose the
// click. A dragstart only names the row, so what the mouse went down on is noted here.
let pressed = null;
addEventListener("mousedown", e => { pressed = e.target; }, true);

function startDrag(e, what) {
  const onButton = pressed?.closest?.("button");
  pressed = null;
  if (!view || onButton) { e.preventDefault(); return; }
  dragging = what;
  document.documentElement.dataset.dragging = what.kind; // for what shows only during a drag (sidebar.css)
  dragging.source = e.currentTarget; // what the drag is from, kept in the page while it is carried to another space
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", ""); // Firefox starts no drag without data
  e.stopPropagation();
}
addEventListener("dragend", () => { dragging = null; settleDrag(); carried.replaceChildren(); });
// Past the sidebar's edge a drop does nothing here, and no more dragover comes to take
// the mark away. (A leave with no next element is the leaving of the page itself.)
addEventListener("dragleave", e => { if (!e.relatedTarget) settleDrag(); });
const settleDrag = () => { marks(); dragScroll(0); holdOver(null); if (!dragging) delete document.documentElement.dataset.dragging; };

const MARKS = ["drop-before", "drop-after", "drop-left", "drop-right", "drop-into"];
const MARKED = MARKS.map(c => "." + c).join();
// Called for every dragover, many times a second, so what is right already stays untouched.
function marks(target, cls) {
  for (const e of document.querySelectorAll(MARKED)) if (e !== target || !e.classList.contains(cls)) e.classList.remove(...MARKS);
  if (target && !target.classList.contains(cls)) target.classList.add(cls);
}

// What is being dragged, as drawn now. A tab carried to another space is drawn nowhere.
const draggedNow = () => (dragging.away ? dragging.source : kept.get(dragging.kind === "folder" ? "folder:" + dragging.key : (dragging.kind === "essential" ? "tile:" : "tab:") + dragging.tabId));

// A tab event can take it away during the drag (the tab closed, or went to another window
// or space). Its dragend then goes to the removed element and never reaches us. That
// ends the drag here, or a tab coming back later would be moved by the next drag from a
// page that happens to be dropped on the sidebar.
//
// A tab you carried to another space (below) is not drawn there, so its row is kept in the
// page, out of sight: its dragend then still reaches everything here that waits for it. Back
// in its own space it is a tab like any other again.
const carried = el("div");
carried.hidden = true;
document.body.append(carried);
port.onMessage.addListener(() => {
  if (dragging?.away && view.space === dragging.away) dragging.away = null;
  if (dragging?.away && !dragging.source.isConnected) carried.append(dragging.source);
  if (!dragging || draggedNow()) return;
  dragging = null;
  settleDrag();
});

// --- Held over a closed folder or another space ------------------------------------
// A tab held still for a moment over a closed folder opens it, and over another space's dot
// goes to that space, as in Finder and Arc: so it can be put anywhere there. The tab then
// belongs to a space the list does not show (dragging.away: the space it is from), and a drop
// in the list moves it to this one, to that place (moveRealsToSpace, tabactions.js).
const HOLD_MS = 700;
let heldOver = null; // { target, timer } (not "holding": sidebar.js has that name, and the sidebar's scripts share one scope)
function holdOver(target, then) {
  if (heldOver?.target === target) return;
  clearTimeout(heldOver?.timer);
  heldOver = target ? { target, timer: setTimeout(() => { heldOver = null; then(); }, HOLD_MS) } : null;
}
// What a tab is held over that opens: a closed folder that could take it, another space it
// could go to. A new tab page has no page another space could open (dropAt).
function springAt(e) {
  if (dragging?.kind !== "tab") return null;
  const over = e.target.closest ? e.target : e.target.parentElement;
  const head = over?.closest?.("[data-folder-head]");
  if (head && head.parentElement.classList.contains("collapsed") && !head.parentElement.classList.contains("live")) {
    return { target: head, then: () => { head.parentElement.classList.remove("collapsed"); send({ type: "foldFolder", key: head.dataset.folderHead, collapsed: false }); } };
  }
  const dot = over?.closest?.("#spaces .space");
  const bare = [...view.essentials, ...view.tabs].some(i => i.id === dragging.tabId && !i.page);
  if (dot && dot.dataset.space !== view.space && !bare) {
    return { target: dot, then: () => { if (!dragging) return; dragging.away ??= view.space; send({ type: "space", space: dot.dataset.space }); } };
  }
  return null;
}

// --- The list scrolls at its edges ------------------------------------------------
// Firefox has a scroll of its own during a drag (ScrollContainerFrame::DragScroll), but it
// cannot be relied on here: its zone is 20 device pixels, so 10 points on a Retina screen,
// right above the space bar; it takes a fixed step per dragover; and in the test Firefox
// it took one step and no more, however long a drag was held there. So this does it: it
// goes on while the pointer rests there, faster the closer to the edge, and exists only
// during a drag. It ends by itself at the list's end, so nothing can keep it going.
// (A timer: requestAnimationFrame stopped for seconds on end during a drag in the test
// Firefox, with the page in view. The picture follows at its own pace either way.)
const EDGE_ZONE = 40, EDGE_SPEED = 900; // how near the edge in pixels, and pixels a second at the edge
let dragScrolling = null; // { speed, timer, last, carry }

function dragEdgeSpeed(e) {
  const list = document.getElementById("tabs");
  if (!dragging || !list.contains(e.target)) return 0;
  const box = list.getBoundingClientRect();
  const fromTop = e.clientY - box.top, fromBottom = box.bottom - e.clientY, near = Math.min(fromTop, fromBottom);
  if (near >= EDGE_ZONE) return 0;
  const closeness = 1 - Math.max(near, 0) / EDGE_ZONE;
  return (fromTop < fromBottom ? -1 : 1) * EDGE_SPEED * (.1 + .9 * closeness * closeness);
}

function dragScroll(speed) {
  if (!speed) {
    clearInterval(dragScrolling?.timer);
    dragScrolling = null;
  } else if (dragScrolling) {
    dragScrolling.speed = speed;
  } else {
    dragScrolling = { speed, last: performance.now(), carry: 0, timer: setInterval(dragScrollStep, 16) };
  }
}

function dragScrollStep() {
  if (!dragging) { dragScroll(0); return; } // however the drag ended (selection.js ends it too)
  const list = document.getElementById("tabs"), was = list.scrollTop, now = performance.now();
  // By the time passed, as a busy machine has no fixed pace (but no leap after a stall,
  // which would lose your place), and in whole pixels, as a small fraction added to
  // scrollTop would be rounded away and never add up.
  dragScrolling.carry += dragScrolling.speed * Math.min(now - dragScrolling.last, 100) / 1000;
  dragScrolling.last = now;
  const step = Math.trunc(dragScrolling.carry);
  dragScrolling.carry -= step;
  list.scrollTop = was + step;
  if (step && list.scrollTop === was) dragScroll(0); // the end of the list
}

// The place among the essentials under the pointer. They are a grid, so a tile's left
// or right half decides. The nearest tile counts, so the gaps and the empty end of the
// last line are places too, and the line does not flicker on its way across.
function tilePlace(e) {
  const tiles = [...document.querySelectorAll("#essentials .tile")];
  if (!tiles.length) return null;
  const away = tile => {
    const r = tile.getBoundingClientRect();
    return Math.hypot(Math.max(r.left - e.clientX, 0, e.clientX - r.right), Math.max(r.top - e.clientY, 0, e.clientY - r.bottom));
  };
  const tile = tiles.reduce((a, b) => (away(b) < away(a) ? b : a));
  const r = tile.getBoundingClientRect(), right = e.clientX > r.left + r.width / 2;
  return { tile, cls: right ? "drop-right" : "drop-left", before: right ? tile.nextElementSibling : tile };
}

// What dropping here would do: { target, cls, msg }, or null if it would do nothing. A tab
// carried from another space goes to this one, to the place in the list where it is dropped;
// among the essentials it would be an essential of its own space, out of sight.
function dropAt(e) {
  const drop = dropHere(e);
  if (!drop || !dragging?.away) return drop;
  const toSpace = drop.msg.type === "tabAction" && drop.msg.action === "space";
  if (toSpace) return drop.msg.space === dragging.away ? null : drop; // on the dot of the space it is from: it is there already
  if (drop.msg.type !== "moveTab") return null;
  const { tabId, before, folder } = drop.msg;
  // As a drop on a dot, with its line and Undo, and then to this place (moveRealsToSpace, tabactions.js).
  return { ...drop, msg: { type: "tabAction", action: "space", tabIds: [tabId], space: view.space, at: { before: before ?? null, folder: folder ?? null } } };
}
function dropHere(e) {
  // A drag event can be aimed at the text under the pointer, which has no closest().
  const over = e.target.closest ? e.target : e.target.parentElement;
  let t = over?.closest("[data-tab], [data-folder-head], #essentials, #space-name, #tabs, .space");
  if (!t || !dragging) return null;
  const own = draggedNow();
  if (!own) return null;
  const after = el => { const r = el.getBoundingClientRect(); return e.clientY > r.top + r.height / 2; };
  if (dragging.kind === "folder") {
    const box = over.closest(".folder");
    if (!box || box === own) return null;
    const next = b => b.nextElementSibling?.dataset.key ?? null;
    const beyond = after(box.firstChild) ? next(box) : box.dataset.key;
    if (beyond === dragging.key || beyond === next(own)) return null;
    return { target: box, cls: beyond === box.dataset.key ? "drop-before" : "drop-after", msg: { type: "moveFolder", key: dragging.key, before: beyond } };
  }
  // A new tab page or the like: no space can open it and no essential or folder can keep
  // it (moveToSpace, onPinned and moveTab go by the address), so it only has a place among
  // the ordinary tabs. Such a tab is never in a folder, so only the loose ones are looked
  // at. Pinned from Firefox's own menu it has a tile, but no place among the essentials.
  const bare = [...view.essentials, ...view.tabs].some(i => i.id === dragging.tabId && !i.page);
  if (bare && (!t.closest("#tabs") || (dragging.kind === "tab" && (t.dataset.folderHead || t.dataset.folder)))) return null;
  // An essential dragged out of the grid: anywhere in the list takes it, and where a tab
  // would land there, it lands too, into a folder as well; else (a folder's indent, a live
  // folder) where Firefox puts it, first among the tabs, with the whole list as its mark.
  if (dragging.kind === "essential" && t.closest("#tabs")) {
    const place = bare ? null : tabPlace(e, t, over, own);
    if (place) return { ...place, msg: { type: "pin", tabId: dragging.tabId, pinned: false, folder: place.msg.folder, before: place.msg.before } };
    return { target: document.getElementById("tabs"), cls: "drop-into", msg: { type: "pin", tabId: dragging.tabId, pinned: false } };
  }
  // With no essentials the grid takes no room, and the space's name is where it would be.
  if (t.id === "space-name") {
    if (dragging.kind !== "tab" || document.querySelector("#essentials .tile")) return null;
    return { target: t, cls: "drop-into", msg: { type: "pin", tabId: dragging.tabId, pinned: true, before: null } };
  }
  if (t.classList.contains("space")) {
    if (dragging.kind !== "tab" || t.dataset.space === view.space) return null;
    // As the menu's Move to space does, with its line and Undo (tabactions.js).
    return { target: t, cls: "drop-into", msg: { type: "tabAction", action: "space", tabIds: [dragging.tabId], space: t.dataset.space } };
  }
  const inEssentials = t.id === "essentials" || t.classList.contains("tile");
  if (dragging.kind === "essential" && !inEssentials) return null;
  if (inEssentials) {
    const place = tilePlace(e);
    if (!place) return null;
    const before = place.before ? Number(place.before.dataset.tab) : null;
    if (dragging.kind === "tab") return { target: place.tile, cls: place.cls, msg: { type: "pin", tabId: dragging.tabId, pinned: true, before } };
    if (place.before === own || place.before === own.nextElementSibling) return null;
    return { target: place.tile, cls: place.cls, msg: { type: "moveEssential", tabId: dragging.tabId, before } };
  }
  return tabPlace(e, t, over, own);
}

// Where a tab lands in the list, under the pointer: { target, cls, msg }, or null. `t` is
// what the pointer is over (a row, a folder's head, the list), `own` what is dragged.
function tabPlace(e, t, over, own) {
  const after = el => { const r = el.getBoundingClientRect(); return e.clientY > r.top + r.height / 2; };
  // A tab in a live folder stays there, whatever is dropped (the search decides, see
  // moveTab), and it has no order of its own to change.
  const held = !!own.closest(".live");
  if (t.dataset.folderHead) {
    const box = t.parentElement;
    if (held || box.classList.contains("live")) return null;
    if (own.parentElement === box.lastChild && !nextTab(own)) return null; // last in it already
    return { target: t, cls: "drop-into", msg: { type: "moveTab", tabId: dragging.tabId, folder: t.dataset.folderHead, before: null } };
  }
  if (t.id === "tabs") {
    // A folder's indent is not a place. The gap above the ordinary tabs is the top of
    // them, and the empty end of the list is the end of them: a line where the tab
    // will land, not the whole list outlined in passing.
    if (over.closest(".folder")) return null;
    const loose = t.querySelectorAll(":scope > .tab");
    if (!loose.length) return held ? null : { target: t, cls: "drop-into", msg: { type: "moveTab", tabId: dragging.tabId, folder: null, before: null } };
    t = e.clientY < loose[0].getBoundingClientRect().top ? loose[0] : loose[loose.length - 1];
  }
  if (t === own || held || t.closest(".live")) return null;
  const below = after(t), beyond = below ? nextTab(t) : t;
  if (t.parentElement === own.parentElement && (beyond === own || beyond === nextTab(own))) return null;
  return { target: t, cls: below ? "drop-after" : "drop-before", msg: { type: "moveTab", tabId: dragging.tabId, folder: t.dataset.folder || null, before: beyond ? Number(beyond.dataset.tab) : null } };
}
function nextTab(t) {
  for (let n = t.nextElementSibling; n; n = n.nextElementSibling) if (n.dataset.tab) return n;
  return null;
}
addEventListener("dragover", e => {
  const drop = dropAt(e);
  marks(drop?.target, drop?.cls);
  dragScroll(dragEdgeSpeed(e));
  const spring = springAt(e);
  holdOver(spring?.target ?? null, spring?.then);
  if (drop) { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }
});
addEventListener("drop", e => {
  const drop = dropAt(e);
  dragging = null;
  settleDrag();
  if (drop) { e.preventDefault(); sendDrop([drop.msg]); }
});

// --- A drop shows where it lands, at once ----------------------------------------------
// The background moves the tab in every window and then sends a view: on a busy machine a
// few hundred milliseconds later. Until then the row would stand where it was, as if the
// drop had failed, and then jump. So it is put there here, at once, and the view that comes
// once the move is done confirms it, or puts it back if the move could not be made. A view
// built before that knows nothing of the move, and after each such view the row is put in
// its new place again, before anything is drawn. (Each drop is known by a name the
// background gives back in the view that comes after it: sidebarAction, sidebar-view.js.)
//
// Only what can be moved as it is drawn: rows, folders and tiles among their own kind. A
// tab that becomes a tile or a tile that becomes a row waits for its view.
const LANDING_MS = 3000; // no view for that long: the background is not answering, and the next view is the truth
let landing = null; // { name, put, until }
function sendDrop(msgs) {
  const name = `${performance.now()}-${Math.random()}`;
  const put = () => { for (const msg of msgs) putWhereItLands(msg); };
  put();
  landing = { name, put, until: performance.now() + LANDING_MS };
  msgs.forEach((msg, i) => send(i === msgs.length - 1 ? { ...msg, landing: name } : msg));
}
function putWhereItLands(msg) {
  const list = document.getElementById("tabs");
  if (msg.type === "moveTab") {
    const row = kept.get("tab:" + msg.tabId), before = msg.before === null ? null : kept.get("tab:" + msg.before);
    if (!row || (msg.before !== null && !before)) return;
    if (before) before.before(row);
    else if (msg.folder) kept.get("folder:" + msg.folder)?.lastChild.append(row);
    else list.append(row);
    row.dataset.folder = msg.folder ?? "";
  } else if (msg.type === "moveFolder") {
    const box = kept.get("folder:" + msg.key), before = msg.before === null ? null : kept.get("folder:" + msg.before);
    if (!box || (msg.before !== null && !before)) return;
    if (before) before.before(box);
    else [...list.querySelectorAll(":scope > .folder")].at(-1)?.after(box);
  } else if (msg.type === "moveEssential") {
    const tile = kept.get("tile:" + msg.tabId), before = msg.before === null ? null : kept.get("tile:" + msg.before);
    if (!tile || (msg.before !== null && !before)) return;
    if (before) before.before(tile);
    else document.getElementById("essentials").append(tile);
  }
}
port.onMessage.addListener(next => {
  if (!landing) return;
  if (next.landed === landing.name || performance.now() > landing.until) landing = null;
  else landing.put();
});
