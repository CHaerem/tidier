// The keys you type right after the command bar's key, before the bar has the keyboard.
// The bar is a panel Firefox opens in the window (commandbar.js), or a window of its own
// where Firefox opens no panel, and Firefox takes some 30 ms to open a panel and give it the
// keyboard, and 60 to 150 ms for a window. Until then the
// keys go to the page you were in: a "w" landed in a message box, and "ferry" and Enter
// searched the web for "rry". So for that moment they are caught here and handed to the bar.
//
// In every frame of every page while Tidier has the access to all websites (commandbar.js
// registers it, with the bar's keys in tidierBarKeys), and in Tidier's sidebar (sidebar.html).
// It starts on the bar's key itself, which reaches the page before Tidier hears of it, or
// when the background says the key was pressed ("bar:catch"), and only where the keyboard is.
// It stops when the bar says it has the keyboard ("bar:stop"), at Enter or Esc, and after a
// moment at the latest. Not when this window loses the keyboard: Firefox can go on sending
// keys here a little longer, until the bar's page is ready for them. Only keys you really
// typed count, so a page cannot type into the bar.
{
  const CATCH_MS = 1500; // the bar is there long before; if it never comes, the keys go back
  const MOST = 200; // letters: a page has no say in this, but nothing unbounded goes anywhere
  const mac = navigator.platform.startsWith("Mac");
  let thisWindow; // in the sidebar only: a content script has no windows API, and needs none
  let barKeys = globalThis.tidierBarKeys ?? [];
  if (browser.windows) browser.windows.getCurrent().then(w => { thisWindow = w.id; }, () => {});
  if (browser.commands) browser.commands.getAll().then(all => { barKeys = all.filter(c => c.name.startsWith("command-bar") && c.shortcut).map(c => c.shortcut); }, () => {});

  // A key as Firefox writes a shortcut ("Ctrl+Shift+K": on a Mac Ctrl is ⌘ and MacCtrl is ⌃).
  const ARROWS = { Up: "ArrowUp", Down: "ArrowDown", Left: "ArrowLeft", Right: "ArrowRight" };
  const isKey = (e, shortcut) => {
    const parts = shortcut.split("+"), key = parts.pop(), has = m => parts.includes(m);
    const command = has("Ctrl") || has("Command"), control = mac ? has("MacCtrl") : has("Ctrl");
    if (e.altKey !== has("Alt") || e.shiftKey !== has("Shift") || e.ctrlKey !== control || e.metaKey !== (mac && command)) return false;
    return e.code === (/^[A-Z]$/.test(key) ? `Key${key}` : /^\d$/.test(key) ? `Digit${key}` : ARROWS[key] ?? key);
  };

  let catching = null; // { pressedAt (null until "bar:catch" says it), stop, known }
  const catchKeys = pressedAt => {
    let text = "", enter = null, escape = false, done = false, waiting = false;
    const swallowed = new Set();
    const send = () => { browser.runtime.sendMessage({ type: "bar:early", pressedAt: catching.pressedAt, text, enter, escape }).catch(() => {}); catching = null; };
    const stop = giveBack => {
      if (done) return;
      done = true;
      removeEventListener("keydown", onKey, true);
      setTimeout(() => removeEventListener("keyup", onUp, true), 300); // the last key's release
      clearTimeout(timer);
      if (giveBack) {
        // The bar never came: what you typed goes where it was going after all.
        catching = null;
        try { if (text) document.execCommand("insertText", false, text); } catch (e) {}
      } else if (!(text || enter || escape)) catching = null;
      else if (catching.pressedAt) send();
      else { waiting = true; timer = setTimeout(() => { catching = null; }, CATCH_MS); } // which press this was comes with "bar:catch"
    };
    const known = at => { catching.pressedAt = at; if (waiting) { clearTimeout(timer); send(); } };
    const onKey = e => {
      if (!e.isTrusted || e.isComposing) return;
      const plain = !e.metaKey && !e.ctrlKey;
      if (e.key === "Enter") enter = { inNewTab: e.metaKey || e.ctrlKey };
      else if (e.key === "Escape") escape = true;
      else if (e.key === "Backspace" && plain) text = text.slice(0, -1);
      else if ([...e.key].length === 1 && plain && text.length < MOST) text += e.key;
      else return; // anything else stays the page's: a key with ⌘, an arrow, ⇥
      e.preventDefault();
      e.stopImmediatePropagation();
      swallowed.add(e.code);
      if (enter || escape) stop(false);
    };
    // The page saw no key go down, so it sees none come up.
    const onUp = e => { if (swallowed.has(e.code)) { swallowed.delete(e.code); e.stopImmediatePropagation(); } };
    addEventListener("keydown", onKey, true);
    addEventListener("keyup", onUp, true);
    let timer = setTimeout(() => stop(true), CATCH_MS);
    catching = { pressedAt, stop, known };
  };

  // The bar's own key, as it goes down here. Firefox carries out the command once the page has
  // had it, so it is let through.
  addEventListener("keydown", e => {
    if (e.isTrusted && !e.repeat && !catching && barKeys.some(k => isKey(e, k))) catchKeys(null);
  }, true);

  browser.runtime.onMessage.addListener(msg => {
    if (msg?.type !== "bar:catch" && msg?.type !== "bar:stop") return;
    if (msg.windowId !== undefined && msg.windowId !== thisWindow) return; // the sidebar of another window
    if (msg.type === "bar:stop") { if (catching?.pressedAt === msg.pressedAt) catching.stop(false); return; }
    if (catching && !catching.pressedAt) return catching.known(msg.pressedAt); // started on the key itself
    catching?.stop(false);
    if (document.hasFocus()) catchKeys(msg.pressedAt);
  });
}
