// --- Keys ---------------------------------------------------------------------------
// ↑ and ↓ move through what the sidebar shows; in the essentials' grid ← and → go along it
// and ↑ and ↓ between its rows. Home and End go to the first and the last. Enter or Space
// selects (or folds a folder), ⌫ closes a tab, ← and → fold and unfold a folder (← on a tab
// in one goes to its head), F2 renames, and ⇧F10, ⌃↵ or the menu key open the menu of what
// the cursor is on. Only while the sidebar has the focus: Firefox gives an extension no key
// that could put it there, and moves it to the page whenever the selected tab changes.
//
// The keyboard has one place. The row or tile under the cursor has the focus itself (a
// roving focus: it is the one Tab comes to, the rows it has been on can only be clicked),
// so there is one ring, a screen reader says where it is, and Enter and Space act on the
// same thing. A button you Tab to keeps its own Enter and Space, and the cursor goes when
// the focus does.
let cursor = null;
const reachable = () => [...document.querySelectorAll(".tile, #tabs .head, #tabs .tab")].filter(e => e.offsetParent !== null);
function moveCursor(to) {
  cursor?.classList.remove("cursor");
  cursor = to || null;
  keepEntry();
  if (!cursor) return;
  cursor.classList.add("cursor");
  if (document.activeElement !== cursor) cursor.focus({ preventScroll: true });
  cursor.scrollIntoView({ block: "nearest" });
}

// One row is where Tab comes into the list: the cursor's, else the selected tab's. Not the
// list itself (sidebar.html gives it tabindex -1): from a row inside it ⇧Tab would land on
// the list, which would hand it straight back, and the keyboard could not get out.
let keysEntry = null;
function keepEntry() {
  const next = cursor ?? document.querySelector("#tabs .tab.active, #essentials .tile.active") ?? document.querySelector("#tabs .head, #tabs .tab");
  if (next === keysEntry) return;
  if (keysEntry) keysEntry.tabIndex = -1;
  keysEntry = next;
  if (keysEntry) keysEntry.tabIndex = 0;
}
port.onMessage.addListener(() => { if (view?.alone) keepEntry(); }); // after render: the selected tab may be another

// Tabbed to a button, or clicked elsewhere: the keyboard is there now. (Not the menu, which
// is about the cursor's row, and gives the focus back when it closes: menu.js.) A click on
// what takes no focus leaves it nowhere, and the ring must not stay behind there either.
addEventListener("focusout", e => {
  if (e.target === cursor && !e.relatedTarget?.closest?.("#menu")) moveCursor(null);
});
addEventListener("focusin", e => {
  if (cursor && e.target !== cursor && !e.target.closest?.("#menu")) moveCursor(null);
  // Tabbed into the list, onto its entry: the cursor shows where you are at once. (Not for a
  // click, which focuses what it lands on too.)
  if (view?.alone && e.target !== cursor && e.target.matches?.(".tile:focus-visible, #tabs .head:focus-visible, #tabs .tab:focus-visible")) moveCursor(e.target);
});

// The first key starts at the tab you are on, not at the top of the sidebar. (Also after
// the cursor's row has gone, or the sidebar lost the focus: stayput.js.)
const startOfKeys = (all = reachable()) => (view?.alone && all.find(r => r.classList.contains("active"))) || all[0];

// The essentials are a grid. Its rows by where they are drawn: the grid's width decides.
function gridStep(all, from, by) {
  const tiles = all.filter(e => e.classList.contains("tile"));
  const box = e => e.getBoundingClientRect(), mid = e => box(e).left + box(e).width / 2;
  const tops = [...new Set(tiles.map(t => Math.round(box(t).top)))].sort((a, b) => a - b);
  const x = from.classList.contains("tile") ? mid(from) : box(from).left + 20; // a row's icon
  const nearest = top => tiles.filter(t => Math.round(box(t).top) === top).sort((a, b) => Math.abs(mid(a) - x) - Math.abs(mid(b) - x))[0];
  if (!from.classList.contains("tile")) return by < 0 && tops.length ? nearest(tops.at(-1)) : null;
  const row = tops.indexOf(Math.round(box(from).top)) + by;
  if (row < 0) return null;
  return row < tops.length ? nearest(tops[row]) : all.find(e => !e.classList.contains("tile")) ?? null;
}

// Its menu, where the pointer's would open: below the start of the row, or by the tile.
function openMenuOf(target) {
  const r = target.getBoundingClientRect(), x = r.left + 8, y = r.bottom - 4;
  if (target.matches("#spaces .space")) {
    showMenu(spaceMenu(target.dataset.space), x, y, document.getElementById("spaces"), true); // spacemenu.js: above the bar, clear of it
    markSpaceDot(target);
  } else if (target.dataset.folderHead) {
    showMenu(folderMenu(target.dataset.folderHead, target.parentElement.classList.contains("live")), x, y, target, true);
  } else if (target.dataset.tab) {
    openTabMenuAt(Number(target.dataset.tab), x, y, true, target); // tabmenu.js
  } else {
    showMenu(listMenu(), x, y, null, true);
  }
  menuReturn = target; // menu.js: Esc gives the keyboard back here
}

// F2, as in Firefox's own lists and the Finder: a folder's name, or the name you gave a saved
// tab or an essential. A tab that keeps no name of its own (an ordinary one) has none to give.
function renameByKey(target) {
  if (target.dataset.folderHead) {
    if (!target.parentElement.classList.contains("live")) rename(target.dataset.folderHead);
    return;
  }
  const id = Number(target.dataset.tab);
  browser.runtime.sendMessage({ type: "tabMenu", tabIds: [id] }).then(tabs => { if (tabs?.[0]?.kept) renameKept(id); }, err => console.error("Tidier: rename", err));
}

addEventListener("keydown", e => {
  // Taken already (the menu's own keys, menu.js), or for a field or the menu. The menu's item
  // can be gone from the page by now, when → has drawn a list in its place.
  if (e.defaultPrevented || e.target.closest?.("input, #menu")) return;
  const plain = !e.metaKey && !e.ctrlKey && !e.altKey;
  const menuKey = e.key === "ContextMenu" || (e.key === "F10" && e.shiftKey && plain) || (e.key === "Enter" && e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey);
  if (menuKey && view?.alone) {
    const on = cursor ?? e.target.closest?.("#spaces .space, #tabs");
    if (!on) return;
    openMenuOf(on);
    e.preventDefault();
    return;
  }
  if (!plain) return;
  // A button you tabbed to (New tab, a space's dot, a notice's ×) is pressed by its own keys.
  if (e.target.closest?.("button") && (e.key === "Enter" || e.key === " ")) return;
  const all = reachable(), at = all.indexOf(cursor);
  // Its row has gone, or is out of sight in a folder folded since: Enter and ⌫ must not act
  // on a tab you cannot see.
  if (at < 0 && view?.alone) moveCursor(null);
  const tab = cursor?.dataset.tab && Number(cursor.dataset.tab);
  const fold = closed => { if (cursor?.dataset.folderHead && cursor.parentElement.classList.contains("collapsed") !== closed) cursor.click(); };
  const inGrid = cursor?.classList.contains("tile");
  switch (e.key) {
    case "ArrowDown":
      if (e.shiftKey) return;
      moveCursor(at < 0 ? startOfKeys(all) : inGrid ? gridStep(all, cursor, 1) ?? cursor : all[Math.min(at + 1, all.length - 1)]);
      break;
    case "ArrowUp":
      if (e.shiftKey) return;
      moveCursor(at < 0 ? startOfKeys(all) : inGrid ? gridStep(all, cursor, -1) ?? cursor : at > 0 && all[at - 1].classList.contains("tile") ? gridStep(all, cursor, -1) ?? all[at - 1] : all[Math.max(at - 1, 0)]);
      break;
    case "ArrowLeft":
      if (at < 0) moveCursor(startOfKeys(all));
      else if (inGrid) moveCursor(at > 0 && all[at - 1].classList.contains("tile") ? all[at - 1] : cursor);
      else if (cursor.dataset.folderHead) fold(true);
      else if (cursor.dataset.folder) moveCursor(cursor.closest(".folder")?.querySelector(".head") ?? cursor);
      break;
    case "ArrowRight":
      if (at < 0) moveCursor(startOfKeys(all));
      else if (inGrid) moveCursor(all[at + 1]?.classList.contains("tile") ? all[at + 1] : cursor);
      else fold(false);
      break;
    case "Home": moveCursor(all[0]); break;
    case "End": moveCursor(all.at(-1)); break;
    case "Enter": case " ":
      if (!cursor) return; // Space then scrolls the list, as it does anywhere
      cursor.click();
      break;
    case "F2":
      if (!cursor || !view?.alone || e.shiftKey) return;
      renameByKey(cursor);
      break;
    case "Backspace": case "Delete":
      if (!tab) return; // (held down, it closes one tab: selection.js)
      moveCursor(all[at + 1] || all[at - 1]);
      send({ type: "close", tabId: tab });
      break;
    default: return;
  }
  e.preventDefault();
});
