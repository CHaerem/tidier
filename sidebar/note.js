// One quiet line above the bar, and Clear (quiet.js in the background). Both are added
// here, after each draw, so that the list itself knows nothing about them. All of it is
// in a block: the sidebar's scripts share one scope, and a name defined twice would
// stop the second script.
{
  const box = document.getElementById("note");
  const text = el("span", "text"), act = el("button", "act", "Undo");
  const line = el("div", "line");
  line.append(text, act);
  box.append(line);

  // Enter and ⌫ belong to the list (keys.js) only outside these buttons, or Enter on a
  // button you tabbed to would do nothing.
  const ownKeys = e => e.stopPropagation();
  act.onkeydown = ownKeys;

  // The text stays while the line fades out; only its being shown changes. It is set once
  // per note: a screen reader says it again whenever it is set, and every view brings it.
  let shown = null, undoNext = false;
  const drawNote = note => {
    const same = note?.id === shown?.id;
    shown = note;
    box.classList.toggle("shown", !!note);
    if (!note || same) return;
    text.textContent = note.text;
    text.title = note.text;
    act.hidden = !note.undo;
    // Cleared from the keys: the keyboard goes to Undo, right there, not nowhere.
    if (undoNext && note.undo) act.focus();
    undoNext = false;
  };
  act.onclick = e => {
    if (!shown) return;
    send({ type: "undo", note: shown.id });
    drawNote(null); // the tabs take a moment to come back; the line goes at once
    // From the keys, the keyboard stays in the sidebar, on the list (keys.js shows where).
    if (!e.detail) document.getElementById("tabs").focus();
  };

  const clear = e => {
    undoNext = !e?.detail; // Clear goes once it has nothing more to clear, and with it the keyboard
    send({ type: "clearSpace", space: view.space });
  };

  // Clear shows only with the pointer near the line between folders and today's tabs.
  // The area it listens on lies over that gap, so nothing is taller for it.
  const drawClear = () => {
    const divider = document.querySelector("#tabs > .divider");
    if (!divider || !view.alone) return;
    if (!divider.firstChild) {
      const reach = el("div", "clear-reach"), button = el("button", "clear", "Clear");
      button.title = "Close today's tabs, except the one you are on";
      button.onclick = clear;
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
