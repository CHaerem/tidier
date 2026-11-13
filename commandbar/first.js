// Before anything is drawn: the colours of the space the bar opens in. The rows come from
// the background a moment after the window shows, and your own look (dotfiles' tidier.css,
// which tints it per space) from managed storage, later still; until both had come the
// first frames were an untinted grey card. So the space and its colour come in the page's
// address (commandbar.js), and your look as it was the last time, from this page's own
// storage: a copy only, replaced as soon as the real one arrives (commandbar/commandbar.js).
{
  const root = document.documentElement, given = new URLSearchParams(location.search);
  if (given.get("space")) root.dataset.space = given.get("space");
  if (given.get("accent")) root.style.setProperty("--accent", given.get("accent"));
  // In the window itself, as a panel of Firefox's (commandbar.js): a panel is as large as
  // its page, so the page says how large that is, from its first frame. As a window of its
  // own the page fills the window instead.
  const panel = Number(given.get("panel"));
  if (panel > 0) {
    root.classList.add("panel");
    root.style.setProperty("--panel-width", `${panel}px`);
  }
  try {
    const css = localStorage.getItem("commandbar:look");
    if (css) {
      const style = document.createElement("style");
      style.id = "own-look";
      style.textContent = css;
      document.head.append(style);
    }
  } catch (e) {} // no storage (a private window, say): the colours come a moment later
}
