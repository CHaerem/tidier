// --- A second click where the first one acted -------------------------------------------
// Some clicks take away what is under the pointer at once: a row's × closes the row, Undo,
// Stop and a notice's × take their line away, a menu item closes the menu or draws another
// list in its place. Something else is under the pointer then, and a double click (people
// double-click when a click seems not to take) would act on it: the next tab closed, the
// tab under the menu selected, a space chosen that you never saw, an essential opened.
//
// So after such a click, the click that comes next there does nothing: the second (and
// third) of a double click, as the system counts one (`detail`), and a click of the real
// mouse on the same spot within SECOND_CLICK_MS. A click from the keys has detail 0, and is
// never held back. Any other click ends it, so a double click you mean somewhere else
// (renaming a folder) is yours as ever.
//
// For every page that has such controls (the sidebar, the settings page): one rule, one
// place. It is loaded before the page's other scripts, so that its listeners come first and
// what it swallows reaches nothing else. The controls themselves say when they acted.
const secondClick = (() => {
  const SECOND_CLICK_MS = 400; // longer than a hand takes to click twice, shorter than to aim again
  const NEAR_PX = 6;
  const DOUBLE_CLICK_MS = 1500; // the slowest double click a Mac can be set to count is longer; this is the part that matters
  let last = null; // the click that acted: where, when, and its place in a double click

  const byMouse = e => e.detail > 0;
  const now = () => performance.now();

  // `e`: the click that acted.
  function acted(e) {
    last = byMouse(e) ? { x: e.clientX, y: e.clientY, at: now(), detail: e.detail, real: e.isTrusted } : null;
  }

  function isSecond(e) {
    if (!last || !byMouse(e)) return false;
    const since = now() - last.at;
    // A dblclick has the detail of the click it follows, which was swallowed already.
    const goesOn = e.type === "dblclick" ? e.detail >= last.detail : e.detail > last.detail;
    // (Not for a script's click, which has no real place.)
    const near = e.isTrusted && last.real && Math.abs(e.clientX - last.x) <= NEAR_PX && Math.abs(e.clientY - last.y) <= NEAR_PX;
    return (goesOn && since < DOUBLE_CLICK_MS) || (since < SECOND_CLICK_MS && near);
  }

  for (const type of ["click", "auxclick", "dblclick"]) {
    addEventListener(type, e => {
      if (!isSecond(e)) {
        if (type !== "dblclick" && byMouse(e)) last = null; // a click of its own: what came before is over
        return;
      }
      if (type !== "dblclick") last.detail = e.detail; // a third click goes on from this one
      e.stopImmediatePropagation();
      e.preventDefault();
    }, true);
  }

  // What a control's handler becomes: it acts, and the click after it there does nothing.
  const acts = handler => function (e) { acted(e); return handler.call(this, e); };
  return { acted, acts, isSecond };
})();
