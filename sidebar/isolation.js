// What isolation shows in the sidebar, all of it only when it applies
// (isolation.js in the background does the work):
//
// - One line asking for the permission to stop a page before it loads in the wrong
//   space, until it is given or you say no. Without it, everything else works as before.
// - "Move to space" in a folder's menu, and in the tab menu's table, "Open a copy in
//   space", "Clear this site's cookies in this space" and "New space".
// - While a tab is being dragged, a place on the bar to drop it for a new space.
//
// Nothing here is drawn into the rows or the dots themselves, whose draws reset them. The
// place for a new space is the bar's last child, which the bar's draw keeps (sidebar.js).

const DECLINED = "isolationDeclined"; // localStorage: per browser, and you can still give it on the settings page
const ISOLATION_ASK = { permissions: ["webRequest", "webRequestBlocking"], origins: ["*://*/*"] };
let hostAllowed = false;
const isolationTell = (type, more) => browser.runtime.sendMessage({ type: "isolation:" + type, ...more }).catch(err => console.error("Tidier: isolation", err));
const thisWindow = browser.windows.getCurrent().then(w => w.id);

// --- The line asking for the permission ------------------------------------------------
const askLine = el("div", "notice ask-line");
askLine.hidden = true;
const askButton = el("button", "", "Stop pages loading in the wrong space");
askButton.title = "Firefox will ask to let Tidier see where pages go, on all websites. Nothing leaves your machine.";
const askNo = el("button", "ask-no", "×");
askNo.title = "Not now (it can be given on the settings page)";
askNo.setAttribute("aria-label", "Not now"); // not "×"
askLine.append(askButton, askNo);
document.getElementById("hiding").after(askLine);
// Asking needs your click, so it is here and not in the background.
askButton.onclick = () => browser.permissions.request(ISOLATION_ASK).then(readPermissions);
askNo.onclick = secondClick.acts(() => {
  try { localStorage.setItem(DECLINED, "1"); } catch (err) { /* then it asks again next time */ }
  goQuietly(askLine);
});

// A notice you dismiss fades where it is and keeps its room until the pointer has left it,
// so the list above does not come down under the pointer at the moment of the click.
// (Also the lasting notice, once you have seen it: render, sidebar.js.)
function goQuietly(notice) {
  if (notice.classList.contains("going")) return;
  notice.classList.add("going");
  const pointerIn = e => { const r = notice.getBoundingClientRect(); return e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom; };
  const gone = () => {
    removeEventListener("mousemove", moved, true);
    document.documentElement.removeEventListener("mouseleave", gone);
    if (!notice.classList.contains("going")) return; // shown again meanwhile
    notice.hidden = true;
    notice.classList.remove("going");
  };
  const moved = e => { if (!pointerIn(e)) gone(); };
  addEventListener("mousemove", moved, true);
  document.documentElement.addEventListener("mouseleave", gone);
}

// Each view only looks at this: permissions change rarely, and views come all the time.
let isolationGiven = true;
async function readPermissions() {
  hostAllowed = await browser.permissions.contains({ origins: ["*://*/*"] }).catch(() => false);
  isolationGiven = await browser.permissions.contains(ISOLATION_ASK).catch(() => false);
  drawAskLine();
}
function drawAskLine() {
  if (askLine.classList.contains("going")) return; // it goes by itself
  let declined = false;
  try { declined = !!localStorage.getItem(DECLINED); } catch (err) { /* asks then */ }
  // One thing to click at a time: the line about hiding tabs comes first.
  askLine.hidden = isolationGiven || declined || !view || !!view.needsHiding;
}
port.onMessage.addListener(drawAskLine);
browser.permissions.onAdded.addListener(readPermissions);
browser.permissions.onRemoved.addListener(readPermissions);
readPermissions();

// A notice says what Tidier cannot do or has done by itself until you put it away with its ×.
// One about a space that came back is then gone; one that keeps coming back with the same
// words (a live folder tries every 15 minutes) stays away until Firefox starts again, and
// other words show (putNoticeAway, common.js).
const problemAway = el("button", "ask-no", "×");
problemAway.title = "Put away";
problemAway.onclick = secondClick.acts(() => isolationTell("seen", { text: view?.problem })); // and then it goes: a second click would reach what comes up
document.getElementById("problem").append(problemAway);

// --- Menus ------------------------------------------------------------------------------
const spacesOtherThan = id => (view?.spaces ?? []).filter(s => s.id !== id);

const plainFolderMenu = folderMenu;
window.folderMenu = (key, live) => {
  const items = plainFolderMenu(key, live);
  if (!view) return items;
  const others = spacesOtherThan(view.space).map(s => [s.name, async () => isolationTell("moveFolder", { key, space: s.id, windowId: await thisWindow }), { color: s.color }]);
  return others.length ? [...items, ["Move to space", others]] : items; // a list in place: a narrow sidebar has no room for a menu beside a menu
};

// The tab menu's table (tabmenu.js), with each item put by the one it
// belongs after: the table draws a line between groups. It is one list for one tab or
// many: what can't take many has no `many`, and is left out then.
function addToTabMenu() {
  const after = (id, item) => {
    const at = TAB_MENU.findIndex(i => i.id === id);
    TAB_MENU.splice(at < 0 ? TAB_MENU.length : at + 1, 0, item);
  };
  after("copy", { id: "clearCookies", group: 2, label: () => "Clear this site's cookies in this space",
    when: tabs => hostAllowed && !!tabs[0].address && tabs[0].space !== "firefox-default",
    run: async tabs => isolationTell("clearCookies", { tabId: tabs[0].id, windowId: await thisWindow }) });
  after("space", { id: "copyToSpace", group: 4, many: true, label: n => (n > 1 ? `Open copies of ${n} tabs in space` : "Open a copy in space"),
    when: tabs => tabs.every(t => !!t.address) && spacesOtherThan(tabs[0].space).length > 0,
    choices: tabs => spacesOtherThan(tabs[0].space).map(s => [s.name, async () => isolationTell("copy", { tabIds: tabs.map(t => t.id), space: s.id, windowId: await thisWindow }), { color: s.color }]) });
  const move = TAB_MENU.find(i => i.id === "space");
  if (move) {
    const { choices } = move;
    // A + where the spaces have their dots, so its name lines up with theirs.
    move.choices = tabs => [...choices(tabs), ["New space", () => newSpaceFor(tabs.map(t => t.id)), { plus: true }]];
  }
}

// A new space with these tabs in it, and then its name ready to change, as one made
// from the space's menu is: "New space" is no name to keep.
async function newSpaceFor(tabIds) {
  namingNewSpace = await isolationTell("newSpaceWith", { tabIds, windowId: await thisWindow });
  nameNewSpace();
}

// The space's menu (spacemenu.js): New space, and then its name is
// ready to change on the line above the list. Editing the rest and deleting are on the
// settings page, which that menu leads to.
let namingNewSpace = null;
function addToSpaceMenu() {
  const plainSpaceMenu = spaceMenu;
  window.spaceMenu = space => {
    const items = plainSpaceMenu(space);
    const settings = items.findIndex(i => i?.[0] === "Settings");
    items.splice(settings < 0 ? items.length : settings, 0, ["New space", async () => { namingNewSpace = await isolationTell("new"); nameNewSpace(); }]);
    return items;
  };
}
function nameNewSpace() {
  if (namingNewSpace && view?.spaces.some(s => s.id === namingNewSpace)) {
    openSpaceBox(namingNewSpace);
    namingNewSpace = null;
  }
}
port.onMessage.addListener(nameNewSpace); // its dot comes with the next view
addEventListener("DOMContentLoaded", () => { addToTabMenu(); addToSpaceMenu(); });

// --- A new space by dropping tabs on the bar --------------------------------------------
// The place exists only during a tab's drag, and it is not one of the bar's dots, which
// are for the spaces there are. Dropping is handled here, before drag.js sees the event.
// On the bar's line, after its last dot, so it never lies over one: a drop meant for a space
// must not make a new one. (The bar keeps its dots where they were: sidebar.css.)
const dropForSpace = el("button", "new-space", "+");
dropForSpace.title = "A new space with this tab";
dropForSpace.hidden = true;
document.getElementById("spaces").append(dropForSpace);
let draggedTabs = null;
addEventListener("dragstart", e => {
  const id = Number(e.target.closest?.(".row.tab")?.dataset.tab);
  if (!view || !id) return;
  draggedTabs = selectedTabs(id); // selection.js
  dropForSpace.hidden = false;
}, true);
addEventListener("dragend", () => { draggedTabs = null; dropForSpace.hidden = true; dropForSpace.classList.remove("drop-into"); }, true);
dropForSpace.addEventListener("dragover", e => { e.preventDefault(); e.stopPropagation(); e.dataTransfer.dropEffect = "move"; dropForSpace.classList.add("drop-into"); });
dropForSpace.addEventListener("dragleave", () => dropForSpace.classList.remove("drop-into"));
// The drag ends here: the row goes to the new space, and its dragend, sent to the row, would
// never reach this page.
dropForSpace.addEventListener("drop", async e => {
  e.preventDefault();
  e.stopPropagation();
  const tabIds = draggedTabs;
  draggedTabs = null;
  dropForSpace.hidden = true;
  dropForSpace.classList.remove("drop-into");
  dragging = null; // drag.js
  settleDrag();
  if (tabIds) newSpaceFor(tabIds);
});
