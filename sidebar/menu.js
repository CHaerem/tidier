// --- A small menu, drawn by Tidier ---------------------------------------------------
function folderMenu(key, live) {
  return live ? [["Delete folder", () => send({ type: "deleteFolder", key })]] : [
    ["New tab here", () => send({ type: "newTabInFolder", key })],
    null,
    ["Rename", () => rename(key)],
    ["Delete folder (its tabs stay)", () => send({ type: "deleteFolder", key })],
  ];
}

// A folder's menu, with More at its end (moremenu.js), which needs to know what its tabs'
// pages are doing: a row here is often a placeholder of a page loaded in another window. So,
// as the tab menu, it is shown once the background has said, a few milliseconds later; Firefox's
// own menu is held back in the click itself.
let folderMenuAsked = 0;
function openFolderMenu(e, key, live) {
  holdMenu(e);
  const asked = ++folderMenuAsked, { clientX: x, clientY: y } = e;
  const ids = view.folders.find(f => f.key === key)?.tabs.map(t => t.id) ?? [];
  (ids.length ? browser.runtime.sendMessage({ type: "tabMenu", tabIds: ids }) : Promise.resolve([])).then(facts => {
    if (asked !== folderMenuAsked || !view.folders.some(f => f.key === key)) return; // a newer click, or the folder is gone
    const more = folderMore(key, live, facts ?? []); // moremenu.js
    showMenu([...folderMenu(key, live), ...(more.length ? [null, ["More", more]] : [])], x, y);
  }, err => console.error("Tidier: folder menu", err));
}
const listMenu = () => [
  ["New folder", () => { renameNext = true; send({ type: "newFolder", space: view.space }); }],
  ...(clearableHere() ? [clearItem()] : []), // spacemenu.js
  ["Archived tabs", () => openArchived()], // archived.js
  ["Settings", () => browser.runtime.openOptionsPage()],
];

// Items: [label, what it does, { color }], or null for a line. Instead of what it does an
// item can have a list of items, which replaces the menu's contents in place, with a row
// back: a narrow sidebar has no room for a menu beside a menu.
function openMenu(e, items) {
  holdMenu(e);
  showMenu(items, e.clientX, e.clientY);
}

// Firefox's own menu must not open: this has to happen in the right click itself.
function holdMenu(e) {
  e.preventDefault();
  e.stopPropagation();
  browser.menus.overrideContext({ showDefaults: false });
}

// `above`: a line the menu must stay above, also once a list in it has replaced it (a space's
// menu, so that its dot stays in sight).
let menuAt = { x: 0, y: 0, above: null };
function showMenu(items, x, y, above = null) {
  menuAt = { x, y, above };
  closeMenu();
  drawMenu(items);
}

function drawMenu(items, back = null, byKey = false) {
  const menu = document.getElementById("menu");
  const rows = items.map(item => {
    if (!item) {
      const line = el("div", "line");
      line.setAttribute("role", "separator");
      return line;
    }
    const [label, act, { color } = {}] = item;
    const b = el("button", "item");
    b.setAttribute("role", "menuitem");
    b.append(el("span", "label", label));
    if (color) {
      const dot = el("span", "dot");
      dot.style.setProperty("--color", color);
      b.prepend(dot);
    }
    if (Array.isArray(act)) {
      b.classList.add("more");
      b.setAttribute("aria-haspopup", "menu");
      b.onclick = ev => drawMenu(act, { label, items, back }, !ev.detail); // a list in a list goes back one step at a time
    } else {
      b.onclick = () => { closeMenu(); act(); };
    }
    return b;
  });
  if (back) {
    const b = el("button", "item back");
    b.setAttribute("role", "menuitem");
    b.append(el("span", "label", back.label));
    b.onclick = ev => drawMenu(back.items, back.back ?? null, !ev.detail);
    rows.unshift(b, el("div", "line"));
  }
  menu.replaceChildren(...rows);
  menu.hidden = false;
  // Measured from the corner: where it stood last would limit how wide it can be.
  menu.style.left = menu.style.top = "0";
  menu.style.left = Math.max(4, Math.min(menuAt.x, innerWidth - menu.offsetWidth - 4)) + "px";
  menu.style.top = Math.max(4, Math.min(menuAt.y, (menuAt.above ?? innerHeight - 4) - menu.offsetHeight)) + "px";
  menu.scrollTop = 0;
  // In the menu, so the arrow keys are for it (keys.js leaves them alone there).
  (byKey ? menu.querySelector(".item:not(.back)") : menu).focus({ preventScroll: true });
}

const closeMenu = () => {
  document.getElementById("menu").hidden = true;
  menuFor = [];
  for (const e of document.querySelectorAll(".menu-for")) e.classList.remove("menu-for");
};
addEventListener("blur", closeMenu);
addEventListener("keydown", e => { if (e.key === "Escape") closeMenu(); });
addEventListener("dragstart", closeMenu, true);

// Which tabs an open menu is about, marked on their rows. A row's draw resets its classes
// (a title that ticks, say), so the mark goes back after each view. A menu about tabs that
// are no longer drawn (closed in another window, another space) is about nothing, and goes.
let menuFor = [];
function markMenuFor() {
  if (!menuFor.length) return;
  const rows = menuFor.map(id => document.querySelector(`[data-tab="${id}"]`)).filter(Boolean);
  if (!rows.length) closeMenu();
  for (const r of rows) r.classList.add("menu-for");
}
port.onMessage.addListener(markMenuFor);

// A click outside only closes the menu, as with a menu of Firefox's own: the × or the row
// under the pointer must not act on the way. (The right button's release is no such click:
// the menu is open by then.) Scrolling the list would leave the menu about nothing in view.
const outsideMenu = e => !document.getElementById("menu").hidden && !e.target.closest?.("#menu");
function clickOutsideMenu(e) {
  if (!outsideMenu(e)) return;
  e.stopImmediatePropagation();
  e.preventDefault();
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
