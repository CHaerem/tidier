// --- A swipe on the trackpad switches space ------------------------------------------
// Two fingers sideways anywhere in the sidebar, as in Zen and Arc: the list follows the
// fingers, the space next to it comes in beside it, and letting go lands on one of them.
// What counts as a swipe, and that a scroll never is one, is swipetrack.js; this draws it.
//
// What moves is a picture (sidebar.css, #swipe): a copy of the list as it stands, and
// beside it the next space, drawn by what draws the list (drawApart, sidebar.js) from
// what the background says is there (glimpseOf, sidebar-view.js). The real list stays in
// its place, out of sight, so a view that comes meanwhile is drawn as always. The switch
// itself is asked for the moment the swipe is decided, while the picture is still on its
// way: the page changes as the list arrives, not after it. The picture goes when it has
// arrived and the new space's view is drawn under it.
//
// Nothing is kept ready for a swipe that may never come: the next space is asked for when
// one begins. Until the answer is there (a few frames), the space is drawn as it was when
// this sidebar last showed it, if it has.
//
// In a block, so that no name here can clash with another sidebar script.
{
  const track = swipeTracker();
  const root = document.documentElement, list = document.getElementById("tabs");
  const overlay = el("div"), strip = el("div", "strip");
  overlay.id = "swipe";
  overlay.hidden = true;
  overlay.setAttribute("aria-hidden", "true"); // a picture of what is already there
  overlay.append(strip);
  document.body.append(overlay);
  // A press on the picture does nothing, and does not take the keyboard from where it is.
  // Caught before it reaches what is under it: the space coming in is drawn by what draws
  // the list, so its rows would answer a click as the list's do.
  for (const type of ["mousedown", "click", "auxclick", "dblclick", "contextmenu", "dragstart"]) {
    overlay.addEventListener(type, e => { e.preventDefault(); e.stopPropagation(); }, true);
  }

  const stillAsked = matchMedia("(prefers-reduced-motion: reduce)");
  const GIVE_UP_MS = 2000; // no view of the new space for this long: the list as it is, is the truth
  const STRAY_PX = 24; // what a swipe's own up and down can have scrolled the list under the picture
  let swipe = null; // { space, top, home, panes, anim, backing, going, slid, arrived, giveUp }
  let quiet = null; // the timer for the pause that ends a swipe
  const lastViews = new Map(); // space -> its view when this sidebar last drew it

  const neighbour = dir => { const ids = view.spaces.map(s => s.id); return ids[ids.indexOf(view.space) + dir] ?? null; };
  const env = () => ({ width: innerWidth, next: !!neighbour(1), prev: !!neighbour(-1), still: stillAsked.matches });
  // A swipe is for the list as it lies: not over a menu, a drag, a name being typed or the archived tabs.
  const taken = () => !view || !!dragging || !document.getElementById("menu").hidden || archivedSpace !== null || !!document.activeElement?.closest?.("input");

  // --- The picture ---------------------------------------------------------------------
  // A part of the page as a picture of it: nothing in it is found by what looks for a
  // tab's row, takes the keyboard, or can be dragged. The parts keep their looks by the
  // classes sidebar.css knows them by here.
  const AS = { essentials: "essentials", "space-name": "space-name", actions: "actions", "new-tab": "new-tab", tabs: "list" };
  function still(part) {
    for (const e of [part, ...part.querySelectorAll("[id], [data-tab], [data-folder-head], [data-key], [draggable], [tabindex]")]) {
      if (e.id === "new-folder") { e.remove(); continue; } // shown only under the pointer
      if (AS[e.id]) e.classList.add(AS[e.id]);
      for (const name of ["id", "data-tab", "data-folder-head", "data-key", "draggable", "tabindex"]) e.removeAttribute(name);
    }
    return part;
  }
  const copyOf = id => still(document.getElementById(id).cloneNode(true));

  // The space this sidebar shows, as it stands now.
  function homePane() {
    const pane = el("div", "pane");
    pane.append(...["essentials", "space-name", "actions", "tabs"].map(copyOf));
    return pane;
  }
  // Another space, from a view of it, in its own colour.
  function paneOf(v, dir) {
    const s = view.spaces.find(x => x.id === v.space);
    const pane = el("div", "pane own-accent " + (dir > 0 ? "next" : "previous"));
    pane.style.setProperty("--accent", s?.color || "#7a7a80");
    const tiles = el("section", "essentials"), rows = el("main", "list");
    drawApart(drawn => {
      place(tiles, v.essentials.map(tile));
      const items = v.folders.map(folder);
      if (v.folders.length && v.tabs.length) items.push(el("div", "divider"));
      place(rows, [...items, ...v.tabs.map(t => row(t, null))]);
      // The marks of news.js, which come with a view and not with a row.
      const mark = (id, on) => { if (on) drawn.get(id)?.classList.add("news"); };
      for (const item of v.essentials) mark("tile:" + item.id, item.news);
      for (const item of [...v.tabs, ...v.folders.flatMap(f => f.tabs)]) mark("tab:" + item.id, item.news);
      for (const f of v.folders) mark("folder:" + f.key, f.tabs.some(t => t.news));
    });
    pane.append(still(tiles), el("div", "space-name", s?.name || ""), copyOf("actions"), still(rows));
    pane.dataset.drawn = JSON.stringify([v.essentials, v.folders, v.tabs]);
    return pane;
  }
  // Its list where you left it, and with the tab you will land on in view, as the list
  // itself will be (stayput.js): by the least distance, and only if none of it shows.
  function asLeft(pane, space) {
    const rows = pane.querySelector(".list"), on = rows.querySelector(".tab.active");
    rows.scrollTop = placeLeftIn(space);
    if (!on) return;
    const r = on.getBoundingClientRect(), box = rows.getBoundingClientRect(), css = getComputedStyle(rows);
    if (r.bottom > box.top && r.top < box.bottom) return;
    const top = box.top + (parseFloat(css.scrollPaddingTop) || 0), bottom = box.bottom - (parseFloat(css.scrollPaddingBottom) || 0);
    rows.scrollTop += r.top < top ? r.top - top : r.bottom - bottom;
  }

  // The space on that side comes into the picture: as last seen here, and then as it is.
  function bring(dir) {
    if (dir in swipe.panes) return;
    swipe.panes[dir] = null;
    const space = neighbour(dir), mine = swipe;
    if (!space) return;
    const put = v => {
      if (swipe !== mine || !v) return;
      const was = swipe.panes[dir], pane = paneOf(v, dir);
      if (was?.dataset.drawn === pane.dataset.drawn) return;
      if (was) was.replaceWith(pane); else strip.append(pane);
      swipe.panes[dir] = pane;
      asLeft(pane, space);
    };
    put(lastViews.get(space));
    sidebarWindow.then(windowId => browser.runtime.sendMessage({ type: "glimpse", windowId, space })).then(put, () => {});
  }

  function begin() {
    // A space that is still sliding in (motion.js) is taken where it is going: the picture
    // is of the list as it will stand, and nothing of the list may show through it.
    for (const id of ["essentials", "space-name", "actions", "tabs"]) for (const running of document.getElementById(id).getAnimations()) running.finish();
    swipe = { space: view.space, top: list.scrollTop, panes: {}, home: homePane() };
    overlay.style.height = list.getBoundingClientRect().bottom + "px";
    strip.replaceChildren(swipe.home);
    strip.style.transform = "";
    overlay.hidden = false;
    swipe.home.querySelector(".list").scrollTop = list.scrollTop;
    root.classList.add("swiping");
  }
  function end() {
    if (!swipe) return;
    clearTimeout(swipe.giveUp);
    clearTimeout(quiet);
    swipe.anim?.cancel();
    // Back where it was: the up and down in a swipe scrolled the list a little, unseen.
    if (!swipe.going && view?.space === swipe.space && Math.abs(list.scrollTop - swipe.top) <= STRAY_PX) list.scrollTop = swipe.top;
    swipe = null;
    root.classList.remove("swiping");
    overlay.hidden = true;
    strip.replaceChildren();
    strip.style.transform = "";
  }

  // --- Moving it -------------------------------------------------------------------------
  const moveTo = at => {
    strip.style.transform = `translateX(${-at}px)`;
    if (at) bring(Math.sign(at));
  };
  // The rest of the way by itself, on the curve everything soft here moves on (tokens.css).
  let curve = null;
  function slide(to, ms, then) {
    curve ??= getComputedStyle(root).getPropertyValue("--soft").match(/cubic-bezier\([^)]*\)/)?.[0] ?? "ease-out";
    const mine = swipe, from = getComputedStyle(strip).transform;
    const done = () => { if (swipe === mine && mine.anim === anim) then(); };
    const anim = swipe.anim = strip.animate({ transform: [from === "none" ? "translateX(0)" : from, `translateX(${-to}px)`] }, { duration: ms, easing: curve, fill: "forwards" });
    anim.finished.then(done, () => {});
  }
  const between = (low, x, high) => Math.max(low, Math.min(high, x));

  function goTo(dir, from, speed) {
    const space = neighbour(dir);
    if (!space) return back(from);
    swipe.going = space;
    bring(dir);
    send({ type: "space", space });
    // The bar says so at once; the view that comes draws it again, whatever it says.
    for (const dot of document.querySelectorAll("#spaces .space")) {
      const on = dot.dataset.space === space;
      if (dot.classList.contains("active") !== on) { dot.classList.toggle("active", on); delete dot.dataset.state; }
    }
    // A flick goes on at the fingers' speed, or a little faster, never slower.
    const left = innerWidth - Math.abs(from);
    slide(dir * innerWidth, speed ? between(140, 3.5 * left / speed, 280) : 140 + 120 * left / innerWidth, () => { swipe.slid = true; land(); });
    swipe.giveUp = setTimeout(end, GIVE_UP_MS);
  }
  function back(from) {
    swipe.backing = true;
    slide(0, 120 + 100 * Math.min(1, Math.abs(from) / innerWidth), end);
  }
  // There, and the new space's list is drawn under the picture: they change places.
  const land = () => { if (swipe?.slid && swipe.arrived) end(); };

  // --- What the fingers do ---------------------------------------------------------------
  function carry(act, now) {
    if (act.first) {
      // A new swipe while the list is on its way back takes it where it is. While it is on
      // its way to another space there is nothing to take: that swipe is over.
      if (swipe?.going) return track.ignore(now);
      if (swipe?.backing) {
        const at = -new DOMMatrix(getComputedStyle(strip).transform).m41;
        swipe.anim?.cancel();
        swipe.anim = null;
        swipe.backing = false;
        track.from(at);
        return moveTo(at);
      }
      begin();
    }
    if (act.go && act.still) return send({ type: "space", space: neighbour(act.go) });
    if (!swipe || swipe.going || swipe.backing) return;
    if (act.go) goTo(act.go, act.from, act.speed);
    else if (act.back) back(act.from);
    else moveTo(act.at);
  }
  // Passive: nothing is held back, so scrolling never waits for this. (A swipe needs
  // nothing held back: there is nothing sideways to scroll, and the picture lies over the list.)
  addEventListener("wheel", e => {
    if (e.deltaMode !== 0 || e.ctrlKey) return; // a wheel that goes by lines is no trackpad; ⌃ is a pinch
    if (!view) return;
    const act = track.wheel(e.deltaX, e.deltaY, e.timeStamp, env());
    if (!swipe && taken()) return track.ignore(e.timeStamp);
    if (act) carry(act, e.timeStamp);
    if (track.swiping()) {
      clearTimeout(quiet);
      quiet = setTimeout(() => { const settled = track.rest(env()); if (settled) carry(settled, performance.now()); }, track.QUIET_MS);
    }
  }, { passive: true, capture: true });

  // After render (sidebar.js) and the list's place (stayput.js), in the same turn.
  port.onMessage.addListener(next => {
    lastViews.set(next.space, next);
    for (const space of lastViews.keys()) if (!next.spaces.some(s => s.id === space)) lastViews.delete(space);
    if (!swipe) return;
    if (next.space === swipe.going) { swipe.arrived = true; land(); }
    else if (next.space !== swipe.space) end(); // taken to another space some other way: that is where you are
  });
}
