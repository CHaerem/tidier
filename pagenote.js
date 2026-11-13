// A word on the page itself, for what a key did with nothing else to show for it: ⇧⌘C
// has copied the address. Arc and Zen say so over the page, where you are looking. The
// sidebar's quiet line (quiet.js) is at the far end of the sidebar, and compact mode hides
// the sidebar altogether, so from there the key seemed to do nothing.
//
// An extension cannot draw over a page from outside it, so the word is put in the page: an
// element of its own, there for a moment and gone. Firefox lets a script into the tab you
// pressed one of Tidier's keys in (activeTab), with or without the access to all websites.
// A page Firefox keeps extensions out of (its own pages, addons.mozilla.org, a PDF) takes
// none, and then the quiet line says it after all.
//
// The page can see that an element came and went, and nothing more: its text is in a
// closed part of it, it holds nothing of yours, and it takes no click and no key.

const PAGE_NOTE_MS = 1400; // long enough to read two words, and gone before it is in the way
const PAGE_NOTE_WAIT_MS = 400; // a page answers in a few milliseconds

// Runs in the page, as a content script: its source is what is sent, so it uses nothing
// from here. Everything is set on the elements themselves: a page's own rules for styles
// (its Content Security Policy) refuse a stylesheet Tidier would add, but not these.
function pageNote(text, ms) {
  const XHTML = "http://www.w3.org/1999/xhtml";
  const root = document.documentElement;
  // (An SVG or XML file shown by itself draws no HTML element.)
  if (!root || root.namespaceURI !== XHTML) return false;
  const set = (el, styles) => { for (const [name, value] of Object.entries(styles)) el.style.setProperty(name, value, "important"); };
  globalThis.tidierPageNote?.remove(); // the key again: the same word, from the start
  const host = document.createElementNS(XHTML, "div");
  set(host, {
    all: "initial", position: "fixed", top: "14px", left: "0", right: "0", "z-index": "2147483647",
    display: "flex", "justify-content": "center", "pointer-events": "none",
  });
  // The sidebar's raised surface (sidebar/tokens.css), in the light or dark you have chosen
  // for Firefox, whatever the page's own colours are.
  const pill = document.createElementNS(XHTML, "div");
  pill.setAttribute("role", "status");
  set(pill, {
    "color-scheme": "light dark", display: "flex", "align-items": "center", gap: "7px",
    height: "30px", padding: "0 13px 0 10px", "border-radius": "10px", "box-sizing": "border-box",
    font: "13px / 1 system-ui, -apple-system, sans-serif", "white-space": "nowrap", "user-select": "none",
    color: "light-dark(rgb(28 25 23 / .93), rgb(255 252 248 / .93))",
    background: "light-dark(rgb(253 252 251 / .97), rgb(58 57 62 / .97))",
    "box-shadow": "0 0 0 .5px light-dark(rgb(40 30 20 / .1), rgb(255 255 255 / .09)), 0 2px 4px light-dark(rgb(40 30 20 / .06), rgb(0 0 0 / .24)), 0 10px 28px light-dark(rgb(40 30 20 / .14), rgb(0 0 0 / .4))",
  });
  const SVG = "http://www.w3.org/2000/svg";
  const check = document.createElementNS(SVG, "svg"), mark = document.createElementNS(SVG, "path");
  check.setAttribute("viewBox", "0 0 16 16");
  check.setAttribute("aria-hidden", "true");
  set(check, { width: "14px", height: "14px", flex: "none", opacity: ".7" });
  mark.setAttribute("d", "M3.4 8.4l3 3 6.2-6.6");
  for (const [name, value] of Object.entries({ fill: "none", stroke: "currentColor", "stroke-width": "1.5", "stroke-linecap": "round", "stroke-linejoin": "round" })) mark.setAttribute(name, value);
  check.append(mark);
  pill.append(check, text);
  host.attachShadow({ mode: "closed" }).append(pill);
  root.append(host);
  globalThis.tidierPageNote = host;
  // It comes down a little as it comes, unless you have asked for less motion.
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  pill.animate([{ opacity: 0, transform: still ? "none" : "translateY(-6px)" }, { opacity: 1, transform: "none" }], { duration: 180, easing: "cubic-bezier(.2, .7, .2, 1)", fill: "both" });
  setTimeout(() => {
    const going = pill.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 220, easing: "ease-in", fill: "both" });
    going.onfinish = going.oncancel = () => {
      host.remove();
      if (globalThis.tidierPageNote === host) globalThis.tidierPageNote = null;
    };
  }, ms);
  return true;
}

// Whether it could be said there. At once, also in a page still loading: by the time the
// page has finished, the word would be about something you did a while ago.
async function sayInPage(tabId, text) {
  if (tabId === undefined) return false; // no tab to say it in: the quiet line then
  const said = browser.tabs.executeScript(tabId, { code: `(${pageNote})(${JSON.stringify(text)}, ${PAGE_NOTE_MS})`, runAt: "document_start" })
    .then(([there]) => there === true, () => false); // refused: Firefox lets no extension into this page
  // A page too busy to answer must not leave the key without a word.
  return Promise.race([said, sleep(PAGE_NOTE_WAIT_MS).then(() => false)]);
}

// What a key did, said once: on the page you are in, or else on the quiet line.
async function sayDone(windowId, tabId, text) {
  if (!(await sayInPage(tabId, text))) say(windowId, text, { brief: true }); // quiet.js
}
