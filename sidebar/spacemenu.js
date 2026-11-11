// --- A menu on each space ---------------------------------------------------------
// A right click on a dot, or on the name above the list, opens Tidier's small menu.
// A listener of its own that comes first, so the bar's drawing need not know of it.
//
// It starts with the space's dot and name, as a quiet line: on the bar a space is only an
// 8 px dot, and the menu of another space must say which one it is. Then in groups, as
// the tab menu is: what concerns the space, then the spaces as a whole, then Clear on its
// own, after them, since it closes tabs (as Close does in the tab menu), and More last, as
// there (openSpaceMenuAt, below). Other files add items by the one they go before: Copy
// for Claude (agent.js), New space (isolation.js).
function spaceMenu(space) {
  const s = view.spaces.find(x => x.id === space);
  return [
    { heading: s?.name ?? "", color: s?.color },
    ["Rename", () => openSpaceBox(space)],
    ["Icon", spaceIconMenu(space)],
    ["Unload this space", () => send({ type: "unloadSpace", space })],
    ["Archived tabs", () => openArchived(space)], // archived.js
    null,
    ["Settings", () => browser.runtime.openOptionsPage()],
    ...(space === view.space && clearableHere() ? [null, clearItem()] : []),
  ];
}

// --- An icon of its own: an emoji at the start of the name -----------------------
// A space's icon is the emoji its name starts with ("🏠 Home"). The name is the container's,
// so the icon shows in Firefox's own lists too and goes to your other machines with the name,
// and nothing more is stored. On the bar it is drawn in the dot's place (sidebar.js), as Arc
// and Zen give a space an icon. (A flag, a keycap, or a picture with what joins and tints it.)
const SPACE_ICON = /^((?:\p{Regional_Indicator}{2}|[#*0-9]\uFE0F?\u20E3|\p{Extended_Pictographic}(?:\uFE0F|\p{Emoji_Modifier})?(?:\u200D\p{Extended_Pictographic}(?:\uFE0F|\p{Emoji_Modifier})?)*))\s*/u;
function spaceIcon(name) {
  const m = SPACE_ICON.exec(name ?? "");
  return m ? { icon: m[1], rest: name.slice(m[0].length) } : { icon: "", rest: name ?? "" };
}
// Chosen from a list to search in (emoji.js), drawn in the menu's place; below it, the way
// back to the plain dot, for a space that has an icon.
function spaceIconMenu(space) {
  const has = spaceIcon(view.spaces.find(x => x.id === space)?.name).icon;
  return [
    { part: () => emojiPicker(space) },
    ...(has ? [null, ["No icon", () => setSpaceIcon(space, "")]] : []),
  ];
}
function setSpaceIcon(space, icon) {
  const s = view.spaces.find(x => x.id === space);
  if (!s) return;
  const name = `${icon} ${spaceIcon(s.name).rest}`.trim();
  if (name && name !== s.name) send({ type: "renameSpace", space, name });
}

// Clear closes today's tabs but the selected one, so with no other tab it has nothing
// to do, and a menu holds only what can be done: nothing is ever greyed.
const clearableHere = () => view.tabs.some(t => !t.active);
// The space it was offered for, not the one the window is in by the time of the click:
// this closes tabs.
const clearItem = (space = view.space) => ["Clear today's tabs", () => send({ type: "clearSpace", space })];

addEventListener("contextmenu", e => {
  if (e.target.closest?.("#menu")) return e.preventDefault(); // no menu on a menu
  closeMenu(); // no small menu left open beside Firefox's own
  if (!view) return;
  const dot = e.target.closest?.("#spaces .space");
  if (!dot && e.target.id !== "space-name") return;
  openSpaceMenu(e, dot ? dot.dataset.space : view.space, dot);
}, true);

// With More at its end (moremenu.js), which needs to know what the space's pages are doing:
// they can be loaded in any window. So it is shown once the background has said, a few
// milliseconds later; Firefox's own menu is held back in the click itself.
let spaceMenuAsked = 0;
const spaceMenuWindow = browser.windows.getCurrent().then(w => w.id);
function openSpaceMenu(e, space, dot) {
  holdMenu(e);
  return openSpaceMenuAt(space, e.clientX, e.clientY, !!dot);
}
// From the keys too (keys.js). A menu at the pointer would cover the bar and with it the dot
// it belongs to. Above the bar (menu.js: it stays clear of what it is about), the dot stays
// in sight, marked as long as the menu or its box is open; from the name above the list,
// clear of that line. (Both are found again here: a view can have redrawn them meanwhile.)
async function openSpaceMenuAt(space, x, y, onDot, byKey = false) {
  const asked = ++spaceMenuAsked;
  const facts = await browser.runtime.sendMessage({ type: "spaceFacts", space, windowId: await spaceMenuWindow }).catch(() => null);
  if (asked !== spaceMenuAsked || !view.spaces.some(s => s.id === space)) return; // a newer click, or the space is gone
  const more = spaceMore(space, facts);
  const back = menuReturn; // what the keyboard goes back to (keys.js): showMenu closes the menu before it
  showMenu([...spaceMenu(space), ...(more.length ? [null, ["More", more]] : [])], x, y, document.getElementById(onDot ? "spaces" : "space-name"), byKey);
  menuReturn = back;
  markSpaceDot(onDot ? document.querySelector(`#spaces .space[data-space="${space}"]`) : null);
}

function markSpaceDot(dot) {
  for (const d of document.querySelectorAll("#spaces .menu-for")) d.classList.remove("menu-for");
  dot?.classList.add("menu-for");
}

// --- Renaming: the name line above the list becomes a box -------------------------
// Beside the line, not in it: each view sets the line's text, which would take the
// box away while you type. Enter or leaving the box saves, Esc does not.
//
// Another space's name is edited here too, in its colour and with its dot marked,
// without going there: Firefox moves the focus to the page when a tab is selected, and
// when this was tried with a switch first, what was typed never reached the box. It
// also loads no page just for a name.
//
// The rest of the line's height goes below the box, so the list stays where it is
// whatever the font: a line's height is the system's, and differs per machine.
let spaceBox = null;

function openSpaceBox(space) {
  const line = document.getElementById("space-name"), s = view.spaces.find(x => x.id === space);
  if (spaceBox || !s) return;
  const input = el("input", "space-box");
  input.value = s.name;
  // In the colour of the space it names, which need not be the one you are in. (--accent-line
  // is worked out where it is defined, from the page's --accent, so it is given here too.)
  input.style.setProperty("--accent", s.color);
  input.style.setProperty("--accent-line", `color-mix(in srgb, ${s.color} 62%, transparent)`);
  input.setAttribute("aria-label", "Name of this space");
  const room = line.getBoundingClientRect().height;
  line.hidden = true;
  line.after(input);
  input.style.marginBottom = Math.max(0, room - input.getBoundingClientRect().height) + "px"; // no name: no line
  markSpaceDot(document.querySelector(`#spaces .space[data-space="${space}"]`));
  input.focus();
  input.select();
  const finish = save => {
    if (spaceBox !== input) return;
    spaceBox = null;
    const name = input.value.trim();
    line.hidden = false;
    input.remove();
    markSpaceDot(null);
    if (!save || !name || name === s.name) return;
    if (space === view.space) line.textContent = name; // at once: the view with it comes a moment later
    send({ type: "renameSpace", space, name });
  };
  spaceBox = input;
  input.onblur = () => finish(true);
  input.onkeydown = e => {
    e.stopPropagation(); // these keys are for the box, not for the list (keys.js)
    if (e.key === "Enter") finish(true);
    else if (e.key === "Escape") finish(false);
  };
}
