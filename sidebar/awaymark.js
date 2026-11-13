// The tab you are on, when it is out of the part of the list you are looking at: a thin
// line at the edge it lies beyond, in the space's own colour, as Zen has it. Clicking it
// takes the list there. Nothing else says where you are once you have scrolled away, and
// the list stays where you left it on purpose (stayput.js).
//
// A line and not a card with a title: the list is for the tabs, and this says one thing,
// which way to go. It is only ever there while the row is wholly out of view, so a list
// you can see all of never has it.
//
// Nothing here runs while nothing happens: it is drawn when the list scrolls, when a view
// comes, when a tab is selected by a key, and when the list changes size.
//
// In a block, so that no name here can clash with another sidebar script.
{
  const list = document.getElementById("tabs");
  const marks = { up: null, down: null };
  for (const way of ["up", "down"]) {
    const mark = el("button", "away-mark " + way);
    mark.id = "away-" + way;
    mark.hidden = true;
    mark.tabIndex = -1; // for the pointer: the keys have the tab you are on anyway (keys.js)
    mark.setAttribute("aria-hidden", "true");
    mark.title = "Go to the tab you are on";
    mark.onclick = e => {
      e.stopPropagation();
      const row = list.querySelector(".tab.active");
      row?.scrollIntoView({ block: "nearest", behavior: lessMotion() ? "auto" : "smooth" }); // sidebar.js
    };
    document.body.append(mark);
    marks[way] = mark;
  }

  // Which way the row lies, if it is wholly out of the list's view: the fades at the list's
  // edges (sidebar.css) hide what is under them, so a row half under one counts as away.
  const FADES = [14, 20];
  function away() {
    const row = list.querySelector(".tab.active");
    if (!row || !row.isConnected) return null;
    const r = row.getBoundingClientRect(), box = list.getBoundingClientRect();
    if (r.bottom <= box.top + FADES[0]) return "up";
    if (r.top >= box.bottom - FADES[1]) return "down";
    return null;
  }

  function draw() {
    const way = away(), box = list.getBoundingClientRect();
    for (const [side, mark] of Object.entries(marks)) {
      const show = side === way;
      if (mark.hidden === !show) continue;
      mark.hidden = !show;
    }
    if (!way) return;
    // Over the list, at the edge the row lies beyond: placed from the list itself, which
    // moves with the notices and the quiet line's room under it.
    const mark = marks[way];
    mark.style.left = `${box.left + box.width / 2}px`;
    mark.style.top = way === "up" ? `${box.top + 4}px` : `${box.bottom - 6}px`;
  }

  list.addEventListener("scroll", draw, { passive: true });
  port.onMessage.addListener(draw);
  list.addEventListener("selectedshown", draw); // marked before its view comes (sidebar.js)
  list.addEventListener("folded", draw); // a folder opening or closing by its height (motion.js)
  new ResizeObserver(draw).observe(list);
}
