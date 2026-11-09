// --- A small menu, drawn by Tidier ---------------------------------------------------
function folderMenu(key, live) {
  return live ? [["Delete folder", () => send({ type: "deleteFolder", key })]] : [
    ["Rename", () => rename(key)],
    ["Delete folder (its tabs stay)", () => send({ type: "deleteFolder", key })],
  ];
}
const listMenu = () => [
  ["New folder", () => { renameNext = true; send({ type: "newFolder", space: view.space }); }],
  ...(clearableHere() ? [clearItem()] : []), // spacemenu.js
  ["Archived tabs", () => openArchived()], // archived.js
  ["Settings", () => browser.runtime.openOptionsPage()],
];

// Items: [label, what it does, { color, plus }], { heading, color } for a quiet first line
// that says what the menu is about, or null for a line. Instead of what it does an item can
// have a list of items, which replaces the menu's contents in place, with a row back: a
// narrow sidebar has no room for a menu beside a menu.
//
// The menu stays clear of what it is about (`about`, found from the click if not given): a
// row, a tile or a folder's head stays in sight, so you can see which one it is for, which
// on a tile, with no text, is all there is to go by.
function openMenu(e, items, about = e.target?.closest?.(MENU_ABOUT)) {
  holdMenu(e);
  showMenu(items, e.clientX, e.clientY, about);
}
const MENU_ABOUT = "[data-tab], [data-folder-head], #space-name, #spaces";

// Firefox's own menu must not open: this has to happen in the right click itself.
function holdMenu(e) {
  e.preventDefault();
  e.stopPropagation();
  browser.menus.overrideContext({ showDefaults: false });
}

let menuAt = { x: 0, y: 0, about: null };
function showMenu(items, x, y, about = null) {
  closeMenu();
  // Measured now: by the time a tab's menu comes from the background, the list can have moved.
  menuAt = { x, y, about: about?.getBoundingClientRect?.() ?? null };
  drawMenu(items);
}

const MENU_GAP = 4, MENU_EDGE = 4;
const MENU_SHORTEST = 120; // less room than this beside what it is about: it may cover it, rather than be a slit
function drawMenu(items, back = null, byKey = false) {
  const menu = document.getElementById("menu");
  const inPlace = !menu.hidden && menu.childElementCount > 0;
  const was = inPlace ? { left: parseFloat(menu.style.left) || 0, top: parseFloat(menu.style.top) || 0, width: menu.offsetWidth } : null;
  const rows = items.map(item => {
    if (!item) {
      const line = el("div", "line");
      line.setAttribute("role", "separator");
      return line;
    }
    if (item.heading !== undefined) {
      const heading = el("div", "heading");
      heading.append(el("span", "label", item.heading));
      if (item.color) {
        const dot = el("span", "dot");
        dot.style.setProperty("--color", item.color);
        heading.prepend(dot);
      }
      return heading;
    }
    const [label, act, { color, plus } = {}] = item;
    const b = el("button", "item");
    b.setAttribute("role", "menuitem");
    b.append(el("span", "label", label));
    if (plus) b.prepend(el("span", "dot plus")); // where the others have their dots, so its name lines up with theirs
    if (color) {
      const dot = el("span", "dot");
      dot.style.setProperty("--color", color);
      b.prepend(dot);
    }
    // Every item takes away what is under the pointer: the menu goes, or another list is
    // drawn in its place, so a double click's second click would choose from that list, or
    // reach the row under the menu (secondclick.js).
    if (Array.isArray(act)) {
      b.classList.add("more");
      b.setAttribute("aria-haspopup", "menu");
      b.onclick = secondClick.acts(ev => drawMenu(act, { label, items }, !ev.detail));
    } else {
      b.onclick = secondClick.acts(() => { closeMenu(); send({ type: "trace", what: `menu: ${label}` }); act(); });
    }
    // A press that never becomes a click (once, Archived tabs did nothing) shows as a press
    // alone in Tidier's traces (common.js): the click went elsewhere, as to Firefox's own note.
    b.onpointerdown = () => send({ type: "trace", what: `menu: press on ${label}` });
    return b;
  });
  if (back) {
    const b = el("button", "item back");
    b.setAttribute("role", "menuitem");
    b.append(el("span", "label", back.label));
    b.onclick = secondClick.acts(ev => drawMenu(back.items, null, !ev.detail));
    rows.unshift(b, el("div", "line"));
  }
  menu.replaceChildren(...rows);
  menu.hidden = false;
  if (was) {
    // A list in place of the menu, or the menu back: the same corner and at least the same
    // width, so the row back is where the item you clicked was, and nothing jumps.
    menu.style.minWidth = was.width + "px";
    menu.style.maxHeight = "";
    menu.style.left = Math.max(MENU_EDGE, Math.min(was.left, innerWidth - menu.offsetWidth - MENU_EDGE)) + "px";
    menu.style.top = Math.max(MENU_EDGE, Math.min(was.top, innerHeight - menu.offsetHeight - MENU_EDGE)) + "px";
  } else {
    placeMenu(menu);
  }
  menu.scrollTop = 0;
  // In the menu, so the arrow keys are for it (keys.js leaves them alone there).
  (byKey ? menu.querySelector(".item:not(.back)") : menu).focus({ preventScroll: true });
}
// Just below what it is about, from the pointer's side, or just above it if it does not fit
// below; on the side with more room, scrolling, if it fits on neither. With nothing it is
// about (the empty part of the list), at the pointer. Measured from the corner: where it
// stood last would limit how wide it can be.
function placeMenu(menu) {
  Object.assign(menu.style, { left: "0", top: "0", minWidth: "", maxHeight: "" });
  const { about } = menuAt, height = menu.offsetHeight;
  menu.style.left = Math.max(MENU_EDGE, Math.min(menuAt.x, innerWidth - menu.offsetWidth - MENU_EDGE)) + "px";
  if (!about) {
    menu.style.top = Math.max(MENU_EDGE, Math.min(menuAt.y, innerHeight - height - MENU_EDGE)) + "px";
    return;
  }
  const below = innerHeight - MENU_EDGE - (about.bottom + MENU_GAP), above = about.top - MENU_GAP - MENU_EDGE;
  if (height <= below) menu.style.top = about.bottom + MENU_GAP + "px";
  else if (height <= above) menu.style.top = about.top - MENU_GAP - height + "px";
  else if (Math.max(below, above) >= MENU_SHORTEST) {
    menu.style.maxHeight = Math.max(below, above) + "px";
    menu.style.top = (below >= above ? about.bottom + MENU_GAP : MENU_EDGE) + "px";
  } else menu.style.top = MENU_EDGE + "px"; // a window too short for that: the whole height, scrolling
}

const closeMenu = () => {
  document.getElementById("menu").hidden = true;
  menuFor = [];
  for (const e of document.querySelectorAll(".menu-for")) e.classList.remove("menu-for");
};
addEventListener("blur", closeMenu);
addEventListener("keydown", e => { if (e.key === "Escape") closeMenu(); });
addEventListener("dragstart", closeMenu, true);

// What an open menu is about, marked: its tabs' rows or tiles, or a folder's head, by
// selector. A row's draw resets its classes (a title that ticks, say), so the mark goes back
// after each view. A menu about things no longer drawn (closed in another window, another
// space) is about nothing, and goes.
let menuFor = [];
function markMenuFor() {
  if (!menuFor.length) return;
  const marked = menuFor.map(selector => document.querySelector(selector)).filter(Boolean);
  if (!marked.length) closeMenu();
  for (const e of marked) e.classList.add("menu-for");
}
const markMenuAbout = selectors => { menuFor = selectors; markMenuFor(); };
port.onMessage.addListener(markMenuFor);

// A click outside only closes the menu, as with a menu of Firefox's own: the × or the row
// under the pointer must not act on the way. (The right button's release is no such click:
// the menu is open by then.) Scrolling the list would leave the menu about nothing in view.
const outsideMenu = e => !document.getElementById("menu").hidden && !e.target.closest?.("#menu");
function clickOutsideMenu(e) {
  if (!outsideMenu(e)) return;
  e.stopImmediatePropagation();
  e.preventDefault();
  secondClick.acted(e); // and a double click there is still that one click
  closeMenu();
}
addEventListener("click", clickOutsideMenu, true);
addEventListener("auxclick", e => { if (e.button === 1) clickOutsideMenu(e); }, true);
addEventListener("wheel", e => { if (outsideMenu(e)) closeMenu(); }, { passive: true });

// ↑ and ↓ move through it, → opens a list, ← goes back, Enter is the button's own. The
// pointer moves the same highlight, so there is never more than one.
{
  const menu = document.getElementById("menu");
  menu.tabIndex = -1;
  menu.setAttribute("role", "menu");
  menu.oncontextmenu = e => e.preventDefault();
  menu.addEventListener("mouseover", e => e.target.closest?.(".item")?.focus({ preventScroll: true }));
  menu.addEventListener("mouseleave", () => menu.focus({ preventScroll: true }));
  menu.addEventListener("keydown", e => {
    const items = [...menu.querySelectorAll(".item")], at = items.indexOf(document.activeElement);
    if (e.key === "ArrowDown") items[(at + 1) % items.length]?.focus();
    else if (e.key === "ArrowUp") items[(at < 1 ? items.length : at) - 1]?.focus();
    else if (e.key === "ArrowRight") { if (items[at]?.classList.contains("more")) items[at].click(); }
    else if (e.key === "ArrowLeft") menu.querySelector(".back")?.click();
    else if (e.key === "Tab") closeMenu(); // as with a menu of Firefox's own, not on to what is behind it
    else return;
    e.preventDefault();
  });
}
