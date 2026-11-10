// One quiet line above the bar, and Clear (quiet.js in the background). Both are added
// here, after each draw, so that the list itself knows nothing about them. All of it is
// in a block: the sidebar's scripts share one scope, and a name defined twice would
// stop the second script.
{
  const box = document.getElementById("note");
  const text = el("span", "text"), act = el("button", "act", "Undo");
  const line = el("div", "line raised"); // it floats over the list (tokens.css)
  line.append(text, act);
  box.append(line);

  // Enter and ⌫ belong to the list (keys.js) only outside these buttons, or Enter on a
  // button you tabbed to would do nothing.
  const ownKeys = e => e.stopPropagation();
  act.onkeydown = ownKeys;

  // The line has a room of its own between the list and the bar, so it lies over no row
  // and no row's ×. The list ends above it; the rows do not move, only less of the list
  // shows for a while. When it goes it fades in its room, and the room stays a moment
  // longer (ROOM_AFTER_MS), and for as long as the pointer is in it: a click meant for
  // Undo that comes too late lands on nothing, never on a row come into its place. A
  // click while it fades still counts (goneNotes, quiet.js): it was there to be clicked.
  // Once faded it is out of reach by its own class, not by the fade's end: Firefox moves a
  // transition on only as it draws, and a window it is not drawing would keep Undo there.
  const FADE_MS = 200, ROOM_AFTER_MS = 400; // the fade is sidebar.css's
  let roomTimer = null, roomDue = false;
  let going = null; // the note that has just gone, while its line fades
  const faded = () => {
    going = null;
    box.classList.add("faded");
    roomTimer = setTimeout(closeRoom, ROOM_AFTER_MS);
  };

  // When the room goes, the list grows into it. Scrolled to its end, Firefox would then
  // move every row down to fill the list: instead, with the pointer in the list, the list
  // keeps that much room at its end until the pointer has left it (letRoomsGo, sidebar.js),
  // so nothing moves under the pointer. (With the pointer elsewhere nothing is under it.)
  const closeRoom = () => {
    roomTimer = null;
    if (box.matches(":hover")) { roomDue = true; return; }
    roomDue = false;
    const spare = tabsList.scrollHeight - tabsList.scrollTop - tabsList.clientHeight;
    const room = box.offsetHeight; // the room's height is sidebar.css's (#note.in-room)
    if (tabsList.scrollTop > 0 && spare < room && tabsList.matches(":hover")) tabsList.style.setProperty("--held", room - spare + "px");
    box.classList.remove("in-room");
  };
  box.addEventListener("mouseleave", () => { if (roomDue) closeRoom(); });

  // The text stays while the line fades out; only its being shown changes. It is set once
  // per note: a screen reader says it again whenever it is set, and every view brings it.
  let shown = null, undoNext = false;
  const drawNote = note => {
    const same = note?.id === shown?.id;
    if (shown && !note) {
      going = shown;
      clearTimeout(roomTimer);
      roomTimer = setTimeout(faded, FADE_MS);
    }
    shown = note;
    box.classList.toggle("shown", !!note);
    if (note) {
      clearTimeout(roomTimer);
      roomTimer = null;
      roomDue = false;
      going = null;
      box.classList.remove("faded");
      box.classList.add("in-room");
    }
    tellHeld();
    if (!note || same) return;
    text.textContent = note.text;
    text.title = note.text;
    act.hidden = !note.undo;
    // Cleared from the keys: the keyboard goes to Undo, right there, not nowhere.
    if (undoNext && note.undo) act.focus();
    undoNext = false;
  };

  // While the pointer or the keyboard is on the line, its time stands still (holdNote,
  // quiet.js), so it waits for you. Told only when that changes.
  let held = null; // the note's id, while it is held
  const tellHeld = () => {
    const now = shown && (box.matches(":hover") || box.contains(document.activeElement)) ? shown.id : null;
    if (now === held) return;
    if (held !== null) send({ type: "holdNote", note: held, held: false });
    held = now;
    if (held !== null) send({ type: "holdNote", note: held, held: true });
  };
  box.addEventListener("mouseenter", tellHeld);
  box.addEventListener("mouseleave", tellHeld);
  box.addEventListener("focusin", tellHeld);
  box.addEventListener("focusout", () => setTimeout(tellHeld)); // where the focus went is known after the event

  // The line goes at once: the tabs take a moment to come back. Its room stays as always,
  // and a double click's second click lands on nothing (secondclick.js).
  const undo = e => {
    const note = shown ?? going;
    if (!note?.undo) return false;
    send({ type: "undo", note: note.id });
    drawNote(null);
    going = null;
    // From the keys, the keyboard stays in the sidebar, on the tab you are on (keys.js).
    if (e && !e.detail) moveCursor(startOfKeys());
    return true;
  };
  act.onclick = secondClick.acts(undo);

  // ⌘Z (Ctrl+Z elsewhere) while the line offers Undo, with the keyboard in the sidebar.
  addEventListener("keydown", e => {
    if (e.key.toLowerCase() !== "z" || !(e.metaKey || e.ctrlKey) || e.shiftKey || e.altKey || e.target.closest?.("input")) return;
    if (undo(e)) e.preventDefault();
  });

  const clear = e => {
    undoNext = !e?.detail; // Clear goes once it has nothing more to clear, and with it the keyboard
    send({ type: "clearSpace", space: view.space });
  };

  // Clear shows only with the pointer near the line between folders and today's tabs.
  // The area it listens on lies over that gap, so nothing is taller for it.
  const drawClear = () => {
    const divider = document.querySelector("#tabs > .divider");
    if (!divider) return;
    if (!divider.firstChild) {
      const reach = el("div", "clear-reach"), button = el("button", "clear", "Clear");
      button.title = "Close today's tabs, except the one you are on";
      button.tabIndex = -1; // inside the list, which is one stop for Tab (keys.js); by key it is the list's menu's Clear
      button.onclick = secondClick.acts(clear); // the rows below go, and a second click would reach what comes up
      button.onkeydown = ownKeys;
      reach.oncontextmenu = e => openMenu(e, listMenu());
      reach.append(button);
      divider.append(reach);
    }
    divider.firstChild.hidden = !clearableHere(); // spacemenu.js, as are the menus' Clear
  };

  port.onMessage.addListener(next => {
    drawNote(next.note ?? null);
    drawClear();
  });
}
