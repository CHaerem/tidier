// A list that shows where you are, and stays as you left it.
//
// Each space keeps how far down its list you were, while this sidebar is open. And the
// list moves by itself for one thing only: the selected tab became another one, which is
// wholly out of view. Then it moves by the least distance, and leaves you alone from
// there. A clicked row is in view, so the list does not move under the pointer; a tab
// opened in the background is not selected, so it does not move the list at all. (One
// exception: leaving a selected tab in a closed folder takes its row out of the list, so
// rows below it in view come up by one row. With that row above the view nothing shows,
// since Firefox keeps what you see in place.)
//
// In a block, so that no name here can clash with another sidebar script: a clash in a
// plain script stops that whole script.
{
  const list = document.getElementById("tabs");
  const positions = new Map(); // space -> scrollTop
  let shown, selected;

  // The scroll events a redraw causes need no care: this listener and render run in
  // one go when a view arrives, and scroll events come later, so an event always reads
  // the position of the space on screen, never another space's.
  list.addEventListener("scroll", () => { if (shown) positions.set(shown, list.scrollTop); }, { passive: true });
  // Where a space's list was left, for what draws it before you are there (swipe.js).
  window.placeLeftIn = space => positions.get(space) ?? 0;

  const outOfView = row => {
    const r = row.getBoundingClientRect(), box = list.getBoundingClientRect();
    return r.bottom <= box.top || r.top >= box.bottom;
  };

  port.onMessage.addListener(next => {
    cursor?.classList.add("cursor"); // a row drawn again has lost its mark, and you your place
    if (next.space !== shown) {
      shown = next.space;
      list.scrollTop = positions.get(shown) ?? 0;
    }
    // Restored first, so a row in view at the place you left is not moved to.
    follow();
  });
  // An essential's tile is always in view, so only rows count. A row in a closed folder
  // is drawn while selected (sidebar.css), so it can be measured here.
  function follow() {
    const row = list.querySelector(".tab.active"), id = row?.dataset.tab;
    if (id !== selected) {
      selected = id;
      if (row && outOfView(row)) row.scrollIntoView({ block: "nearest" });
    }
  }

  // A sidebar made narrower wraps the lines above the list onto more lines, and a notice
  // under the list (or one that now takes two lines) makes it shorter: the list shows less,
  // and a selected tab that was in view would end up under the fade at its end, or below
  // it. So when the list's size changes, a selected row that was in view, even in part, is
  // brought wholly into view by the least distance (the list's scroll-padding keeps it clear
  // of the fades). One that you scrolled away from stays away. The quiet line's room is the
  // exception (note.js): it makes the list shorter only for a while, and its promise is that
  // no row moves for it. Whether the row was in view is read when you scroll and when a
  // view comes, which is when it can change otherwise.
  const FADES = [14, 20]; // the list's fades at its top and end (sidebar.css #tabs), which hide what is under them
  const wholly = row => {
    const r = row.getBoundingClientRect(), box = list.getBoundingClientRect();
    return r.top >= box.top + FADES[0] - 2 && r.bottom <= box.bottom - FADES[1] + 2;
  };
  const noteBox = document.getElementById("note");
  let size = null, selectedInView = false;
  const notice = () => { const row = list.querySelector(".tab.active"); selectedInView = !!row && !outOfView(row); };
  list.addEventListener("scroll", notice, { passive: true });
  port.onMessage.addListener(notice);
  // A tab selected with a key is marked before its view comes (sidebar.js): the list goes
  // to it then, not a moment after its mark has left the part in view.
  list.addEventListener("selectedshown", () => { follow(); notice(); });
  // The room's part is told apart by its height: the list and the room together keep theirs
  // when only the room comes or goes, also when something else changes in the same moment.
  // The width is the list's with its scroll bar: where a scroll bar takes room (a Mac with
  // a mouse), a list long enough to scroll is narrower inside than a short one, so coming
  // from a short space to a long one looked like a sidebar made narrower, and moved the list
  // from the place you left it.
  new ResizeObserver(() => {
    const was = size;
    size = { width: list.offsetWidth, height: list.clientHeight + noteBox.offsetHeight }; // (no room: no height, sidebar.css)
    const resized = was && (was.width !== size.width || was.height !== size.height);
    const row = list.querySelector(".tab.active");
    if (resized && row && selectedInView && !wholly(row)) row.scrollIntoView({ block: "nearest" });
    notice();
  }).observe(list);

  // You went back to the page: the cursor's mark is no longer true, and the next key
  // starts at the tab you are on then, not where you once left the cursor.
  addEventListener("blur", () => { if (view) moveCursor(null); });
}
