// --- Soft motion where something comes or goes ---------------------------------------
// As in Zen and Arc, but short and only for what you did: another space slides in from
// the side it is on, and a folder opens and closes by its height instead of jumping. (A
// new row fades in by itself, sidebar.css; a swipe has motion of its own, swipe.js.)
//
// Nothing here runs while nothing happens: no timer, no frame loop. With less motion asked
// for in the system's settings none of it moves (lessMotion, sidebar.js).
//
// In a block, so that no name here can clash with another sidebar script.
{
  const root = document.documentElement, list = document.getElementById("tabs");
  // The time and curve everything soft here moves by (tokens.css), read once it is needed.
  let soft = null;
  const softly = () => {
    if (soft) return soft;
    const value = getComputedStyle(root).getPropertyValue("--soft");
    return (soft = { duration: 1000 * (parseFloat(value) || 0.18), easing: value.match(/cubic-bezier\([^)]*\)/)?.[0] ?? "ease-out" });
  };

  // --- Another space slides in ----------------------------------------------------------
  // From the side its dot is on, a little way, as it fades in: a list that changed in one
  // frame said nothing of where you went. Only the parts that are the space's own move; the
  // bar stays, as it stays in Zen and Arc. (After a swipe the list is there already, having
  // come with the fingers: swipe.js's picture is still over it when this runs, as this file
  // listens before swipe.js does.)
  const SLIDE_PX = 16;
  const PARTS = ["essentials", "space-name", "actions", "tabs"];
  let shown = null;
  port.onMessage.addListener(next => {
    const was = shown;
    shown = next.space;
    if (!was || was === next.space || lessMotion() || root.classList.contains("swiping")) return;
    const ids = next.spaces.map(s => s.id), from = ids.indexOf(was), to = ids.indexOf(next.space);
    const dir = from < 0 || to < 0 ? 0 : Math.sign(to - from);
    const { duration, easing } = softly();
    for (const id of PARTS) {
      document.getElementById(id).animate(
        { transform: [`translateX(${dir * SLIDE_PX}px)`, "none"], opacity: [0, 1] },
        { duration, easing },
      );
    }
  });

  // --- A folder opens and closes by its height ---------------------------------------------
  // Told by its class (sidebar.js draws it, from a click, a key or a view), so this needs
  // nothing from the drawing. Its old height is had by putting the class back for a moment,
  // in the same turn: nothing is painted in between. Not while a whole space comes in, nor
  // for a folder that is new: only one that was there and changed.
  const folds = new MutationObserver(records => {
    if (lessMotion() || root.classList.contains("space-arriving") || root.classList.contains("swiping")) return;
    const changed = new Set();
    for (const r of records) {
      const box = r.target;
      if (!box.classList?.contains("folder") || r.oldValue === null) continue;
      if (r.oldValue.split(/\s+/).includes("collapsed") !== box.classList.contains("collapsed")) changed.add(box);
    }
    for (const box of changed) foldSoftly(box);
  });
  folds.observe(list, { subtree: true, attributes: true, attributeFilter: ["class"], attributeOldValue: true });

  function foldSoftly(box) {
    const children = box.lastElementChild;
    if (!children?.classList.contains("children")) return;
    // A fold still under way (folded again before it was over, or on a machine too busy to
    // have drawn it yet) holds the height, so both measures below would be that height:
    // nothing moved, and the old fold went on to its end in a folder that was now the other
    // way. So it is stopped first, and this one goes on from where that one had come.
    const under = children.getAnimations().filter(a => a.id === "fold");
    const at = under.length ? Math.round(children.getBoundingClientRect().height) : null;
    for (const running of under) running.cancel();
    const closed = box.classList.contains("collapsed"), to = children.offsetHeight;
    box.classList.toggle("collapsed", !closed);
    const from = at ?? children.offsetHeight;
    box.classList.toggle("collapsed", closed);
    folds.takeRecords(); // the moment back is no fold of its own
    if (from === to) return;
    const { duration, easing } = softly();
    // Clipped while it moves, so what is closing goes under the folder's edge, not over the rows below.
    const anim = children.animate({ height: [`${from}px`, `${to}px`], overflow: ["clip", "clip"] }, { duration, easing });
    anim.id = "fold";
    // Firefox keeps what you look at in its place when rows above it go (scroll anchoring),
    // but not under a box whose height is on the move. Without that, the row you are on, the
    // only one a closed folder still shows, went up with the fold and out of sight. So the
    // list is told (stayput.js): now, where the row is already in its place inside the
    // folder, and when the move is over, for a row below the folder.
    const folded = () => list.dispatchEvent(new Event("folded"));
    folded();
    anim.finished.then(folded, () => {});
  }
}
