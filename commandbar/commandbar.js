// The command bar's page: a field and the rows for what is typed. What can be found comes
// once from the background (commandbar.js) when the page connects; ranking happens here
// (rank.js), so typing needs no round trip. History and bookmarks are asked on each change
// of the text, only if you allowed them, and only because you typed.
//
// Text is only ever set with textContent, so a page title cannot add anything to the bar.

const field = document.getElementById("field"), list = document.getElementById("rows");
const stepLine = document.getElementById("step"), what = document.getElementById("what");
const PLACEHOLDER = "Search, or type an address";
const HISTORY_RESULTS = 25, HISTORY_WAIT_MS = 40; // a few keys in a row are one lookup
field.placeholder = PLACEHOLDER;
field.focus(); // typing works from here on, also before anything has come back

let data = null; // what the background sent
let found = []; // from history and bookmarks, for the text as it is
let rows = [], selected = 0;
let step = null; // a command asking something: { row, kind: "ask" | "list", text (what was typed before) }
let asking = false; // a permission prompt is open, and must not close the bar
let enterWaiting = null; // Enter before anything has come back
let historyTimer = null, historySeq = 0;
let engine = null; // the name of Firefox's search engine, once the bar may know it

// As a panel in the window you are in, or as a window of its own (first.js). A panel is
// closed by its page alone, and Firefox closes it when you click beside it.
const inPanel = document.documentElement.classList.contains("panel");

const port = browser.runtime.connect({ name: "commandbar" });
const send = msg => port.postMessage(msg);
port.onDisconnect.addListener(() => window.close());
port.onMessage.addListener(msg => {
  if (msg.type === "close") return window.close();
  if (msg.type === "early") return typedBefore(msg);
  data = msg;
  if (data.color) document.documentElement.style.setProperty("--accent", data.color);
  if (data.space) document.documentElement.dataset.space = data.space;
  update();
  // For the smoke test, which prints it: from the key to the bar in use.
  document.documentElement.dataset.readyMs = Date.now() - data.pressedAt;
  if (enterWaiting !== null) { const inNewTab = enterWaiting; enterWaiting = null; choose(rows[selected], inNewTab); }
});

// What you typed after the key but before this window had the keyboard, caught where it went
// (barkeys.js): it comes before anything typed here since.
function typedBefore({ text, enter, escape }) {
  if (escape) return closeBar(true);
  if (text && !step) {
    field.value = text + field.value;
    field.setSelectionRange(field.value.length, field.value.length);
    lookUpMore();
    update();
  }
  if (enter) choose(rows[selected], enter.inNewTab);
}

// Your own look (dotfiles' tidier.css), as in the sidebar: the tint of the active space. Kept
// for the next bar's first frame (first.js), which cannot wait for managed storage.
browser.storage.managed.get("sidebarCSS").then(({ sidebarCSS }) => {
  try { if ((localStorage.getItem("commandbar:look") ?? "") !== (sidebarCSS ?? "")) sidebarCSS ? localStorage.setItem("commandbar:look", sidebarCSS) : localStorage.removeItem("commandbar:look"); } catch (e) {}
  const style = document.getElementById("own-look") ?? document.head.appendChild(Object.assign(document.createElement("style"), { id: "own-look" }));
  if (style.textContent !== (sidebarCSS ?? "")) style.textContent = sidebarCSS ?? "";
}, () => {});

// Which engine a search goes to, once the bar may ask (the permission comes with the first search).
browser.search?.get().then(engines => { engine = engines.find(e => e.isDefault)?.name ?? null; if (data) update({ keepSelected: true }); }, () => {});

const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};
const icon = name => { const e = el("span", "icon"); e.dataset.icon = name; return e; };
const spaceOf = id => data?.spaces.find(s => s.id === id);

// --- Rows ---------------------------------------------------------------------------
// The one row asking for history and bookmarks: quiet, last, and gone once you answered.
// Firefox's question then covers the field, so the row says it is coming.
function askRow() {
  if (!data || data.asked || (browser.history && browser.bookmarks)) return [];
  return [{ kind: "ask", id: "ask", title: "Also search history and bookmarks", note: "Firefox asks you first", quiet: true }];
}

// The row under a question: what Enter does with what you typed.
function confirmRow() {
  const ask = step.row.ask, text = field.value.trim();
  const title = text ? ask.confirm?.replace("#", text) : ask.empty;
  return title ? [{ kind: "confirm", id: "confirm", title, icon: iconOfCommand(step.row) }] : [];
}

function rowsNow() {
  const text = field.value;
  if (step?.kind === "ask") return confirmRow();
  if (step?.kind === "list") {
    const choices = step.row.list;
    return text.trim() ? rankResults(text, choices) : choices;
  }
  if (!data) return addressFrom(text) ? resultsFor(text, [], { engine }) : [];
  return resultsFor(text, [...data.items, ...found], { tail: text.trim() ? askRow() : [], engine });
}

// After the title: where it is (the space in words when it is not this one), what it is
// when it is not an open tab, or a command's key.
const KIND_WORD = { closed: "closed", bookmark: "bookmark", history: "history" };
function second(row) {
  if (row.kind === "command" || row.kind === "choice") return null; // a choice of space is the space itself
  const parts = [];
  const elsewhere = row.space && row.space !== data?.space && spaceOf(row.space);
  if (elsewhere) parts.push(elsewhere.name);
  if (row.kind === "folder") parts.push("Folder");
  else if (row.url && row.kind !== "address" && row.kind !== "search") parts.push(siteOf(row.url));
  if (KIND_WORD[row.kind]) parts.push(row.kind === "closed" && row.why === "archived" ? "archived" : KIND_WORD[row.kind]);
  if (row.kind === "archived") parts.push(row.why === "closed" ? "closed" : "archived");
  if (row.note) parts.push(row.note);
  if (!parts.length) return null;
  const e = el("span", "site", parts.join(" · "));
  if (elsewhere) { const dot = el("span", "dot"); dot.style.setProperty("--color", elsewhere.color); e.prepend(dot); }
  return e;
}

// On the selected row, when Enter takes you to another space: that it does.
function enterSays(row) {
  if (step || row.kind === "command" || row.kind === "choice") return null;
  const elsewhere = row.space && row.space !== data?.space && spaceOf(row.space);
  if (!elsewhere) return null;
  const how = row.kind === "closed" || row.kind === "archived" ? `Reopen in ${elsewhere.name}` : `Switch to ${elsewhere.name}`;
  return el("span", "enter", `${how}  ↵`);
}

// What a command does, drawn in the folders' line (tokens.css), all the same size and weight.
const COMMAND_ICONS = {
  "new-tab": "plus", "new-folder": "folder-plus", "reopen-closed": "undo", "clear-today": "close", "copy-url": "copy",
  "rename-tab": "rename", "rename-folder": "rename", unload: "unload", "toggle-essential": "pin", "move-to-folder": "folder",
  "move-to-space": "go", "close-tab": "close", settings: "settings", "next-tab": "down", "previous-tab": "up",
  "next-space": "go", "previous-space": "back", "claude-copy-page": "copy", "claude-copy-tabs": "copy", "claude-ask": "open",
};
const iconOfCommand = row => COMMAND_ICONS[row.name] ?? "go";
const KIND_ICONS = { search: "search", address: "address", ask: "history", history: "history", bookmark: "bookmark" };

// A page with no icon gets its first letter or digit, not a bracket: "(2) Inbox" is an I.
const letterOf = title => String(title ?? "").match(/[\p{L}\p{N}]/u)?.[0] ?? "·";

function picture(row) {
  const space = spaceOf(row.space);
  if ((row.kind === "command" && row.name === "go-to-space" || row.kind === "choice") && space) {
    const e = el("span", "icon space");
    e.style.setProperty("--color", space.color);
    return e;
  }
  if (row.kind === "command") return icon(iconOfCommand(row));
  if (row.kind === "confirm") return icon(row.icon);
  if (row.kind === "choice") return icon(row.value ? "folder" : "back");
  if (row.kind === "folder") return icon(row.live ? "live" : "folder");
  if (KIND_ICONS[row.kind] && !row.icon) return icon(KIND_ICONS[row.kind]);
  const letter = () => el("span", "letter", letterOf(row.title));
  if (!row.icon || !/^(https?:|data:|moz-extension:)/.test(row.icon)) return letter();
  const img = el("img");
  img.src = row.icon;
  img.alt = "";
  img.onerror = () => img.replaceWith(letter());
  return img;
}

function draw() {
  field.removeAttribute("aria-activedescendant");
  list.replaceChildren(...rows.map((row, i) => {
    const e = el("div", "row" + (row.quiet ? " quiet" : "") + (i === selected ? " selected" : ""));
    e.id = "row-" + i;
    e.dataset.i = i;
    e.dataset.kind = row.kind;
    e.setAttribute("role", "option");
    if (row.url) e.dataset.url = row.url;
    e.append(picture(row), el("span", "title", row.title));
    const after = second(row), enter = enterSays(row);
    if (after) e.append(after);
    if (enter) e.append(enter);
    if (row.kind === "command" && row.shortcut) e.append(el("span", "key", row.shortcut));
    return e;
  }));
  if (rows.length) field.setAttribute("aria-activedescendant", "row-" + selected);
}

function select(i) {
  if (i === selected || !rows[i]) return;
  list.children[selected]?.classList.remove("selected");
  selected = i;
  list.children[i].classList.add("selected");
  list.children[i].scrollIntoView({ block: "nearest" });
  field.setAttribute("aria-activedescendant", "row-" + i);
}

// Rows anew for the text as it is. The row you moved to stays selected if it is still there,
// when something arrives from history a moment later.
function update({ keepSelected = false } = {}) {
  const was = keepSelected ? rows[selected]?.id : null;
  rows = rowsNow();
  const at = was ? rows.findIndex(r => r.id === was) : 0;
  selected = Math.max(at, 0);
  draw();
}

// --- History and bookmarks ----------------------------------------------------------
function lookUpMore() {
  clearTimeout(historyTimer);
  const text = field.value.trim();
  const seq = ++historySeq;
  // What is found stays until the next answer: ranking drops what no longer matches, and
  // the rows do not flicker on every key.
  if (!text || step || !(browser.history || browser.bookmarks)) { found = []; return; }
  historyTimer = setTimeout(async () => {
    const [history, bookmarks] = await Promise.all([
      browser.history?.search({ text, maxResults: HISTORY_RESULTS, startTime: 0 }).catch(() => []) ?? [],
      browser.bookmarks?.search(text).catch(() => []) ?? [],
    ]);
    if (seq !== historySeq) return;
    found = [
      ...history.filter(h => h.url && /^https?:/.test(h.url)).map(h => ({ kind: "history", id: `history:${h.id}`, title: h.title || h.url, url: h.url, lastUsed: h.lastVisitTime })),
      ...bookmarks.filter(b => b.url && /^https?:/.test(b.url)).map(b => ({ kind: "bookmark", id: `bookmark:${b.id}`, title: b.title || b.url, url: b.url, lastUsed: b.dateAdded })),
    ];
    update({ keepSelected: true });
  }, HISTORY_WAIT_MS);
}

async function askForMore() {
  asking = true;
  // First: Firefox's question is a panel too, and opening it closes a bar that is one, with
  // this page. The answer still counts, and the next bar has what you allowed.
  send({ type: "asked" });
  const allowed = await browser.permissions.request({ permissions: ["history", "bookmarks"] }).catch(() => false);
  asking = false;
  field.focus();
  data.asked = true;
  lookUpMore();
  update({ keepSelected: allowed });
}

// --- Choosing -----------------------------------------------------------------------
const closeBar = refocus => send({ type: "close", refocus });

// A command's question: the field asks, the line above says what for, and the icon in the
// field becomes the command's.
function startStep(row, kind) {
  step = { row, kind, text: field.value };
  field.value = kind === "ask" ? row.ask.value ?? "" : "";
  field.placeholder = kind === "ask" ? row.ask.placeholder : row.placeholder ?? row.title;
  stepLine.textContent = (kind === "ask" ? row.ask.heading : row.heading) ?? row.title;
  stepLine.hidden = false;
  what.dataset.icon = iconOfCommand(row);
  field.select();
  lookUpMore();
  update();
}

function endStep() {
  field.value = step.text;
  field.placeholder = PLACEHOLDER;
  stepLine.hidden = true;
  what.dataset.icon = "search";
  step = null;
  lookUpMore();
  update();
}

// Only what the background needs to know which row this was.
const chosen = (row, more) => send({
  type: "choose", ...more,
  row: { kind: row.kind, key: row.key, tabId: row.tabId, url: row.url, sessionId: row.sessionId, query: row.query, name: row.name, value: row.value, space: row.space, archived: row.archived },
});

async function searchFor(row) {
  // A permission without a prompt, but asked for here, in the key press: the manifest gets
  // no new required permission, since that reaches machines before anyone looks.
  if (!browser.search) {
    asking = true;
    const allowed = await browser.permissions.request({ permissions: ["search"] }).catch(() => false);
    asking = false;
    if (!allowed) return;
  }
  chosen(row);
}

function choose(row, inNewTab) {
  if (step?.kind === "ask") return row && chosen(step.row, { value: field.value.trim() }); // no row: nothing to do with an empty name
  if (step?.kind === "list") return row && chosen(step.row, { value: row.value });
  if (!data) { enterWaiting = inNewTab; return; } // a moment: the rows are on their way
  // ⌘↵ with nothing typed is the shortest way to an empty new tab.
  if (inNewTab && !field.value.trim()) {
    const newTab = data.items.find(i => i.name === "new-tab");
    if (newTab) return chosen(newTab);
  }
  if (!row) return;
  if (row.kind === "ask") return askForMore();
  if (row.kind === "search") return searchFor(row);
  if (row.kind === "command" && row.ask) return startStep(row, "ask");
  if (row.kind === "command" && row.list) return startStep(row, "list");
  chosen(row, { inNewTab });
}

// --- Keys and pointer ----------------------------------------------------------------
field.addEventListener("input", () => { lookUpMore(); update(); });

addEventListener("keydown", e => {
  if (e.isComposing) return; // a key that belongs to composing a letter
  const n = rows.length;
  switch (e.key) {
    case "ArrowDown": if (n) select((selected + 1) % n); break;
    case "ArrowUp": if (n) select((selected - 1 + n) % n); break;
    case "Enter": if (!e.repeat) choose(rows[selected], e.metaKey || e.ctrlKey); break; // held down, it would answer the question it has just brought up
    case "Escape": if (step) endStep(); else closeBar(true); break;
    case "Tab":
      if (rows[selected] && !step) { field.value = completionFor(rows[selected], field.value); lookUpMore(); update(); }
      break;
    // ⌫ in an empty question goes back one step, as in Arc. Held down, it only empties the field.
    case "Backspace": if (step && !field.value && !e.repeat) { endStep(); break; } return;
    default: return;
  }
  e.preventDefault();
}, true);

// A pointer that lies still must not take the selection from the keys: only a move counts.
list.addEventListener("mousemove", e => {
  const row = e.target.closest?.(".row");
  if (row) select(Number(row.dataset.i));
});
list.addEventListener("mousedown", e => e.preventDefault()); // the field keeps the focus
// And has it whenever the bar does. Firefox gives a panel the keyboard a moment after its
// page has loaded, and now and then that leaves it on the page as a whole, not on the field
// the page had put it in: the bar was there, and what you typed went nowhere.
addEventListener("focus", () => { if (!asking && document.activeElement !== field) field.focus(); });
// As a panel, the bar says when it has the keyboard, once: that is when it is there to be
// seen. Firefox can load a panel's page and take it away again unshown, and then it never
// has (commandbar.js in the background, BAR_SEEN_MS).
// (Heard on its way down, so that the field getting the keyboard counts too: Firefox does
// not always tell the window itself.)
if (inPanel) {
  const seen = () => { if (!document.hasFocus()) return; removeEventListener("focus", seen, true); send({ type: "seen" }); };
  addEventListener("focus", seen, true);
  seen();
}
list.addEventListener("click", e => {
  const row = e.target.closest?.(".row");
  if (row) choose(rows[Number(row.dataset.i)], e.metaKey || e.ctrlKey);
});

// Losing the focus closes it, like Arc's. As a window of its own, what counts is the window: inside it the focus can
// hop away from the page and back (Firefox settles the new window), and then you can simply
// go on typing, unless it is Firefox's own prompt that has it. A moment later, for a window
// that is still getting the focus.
//
// With the prompt open the page has already lost the focus, so going to another window brings
// it no blur, and the bar would stay behind that window with its prompt, until the key closed
// it instead of opening it. So then the window's own event counts too, and only then: a new
// window's focus can pass through "none" on its way here, which must not close the bar.
function focusWent() {
  if (inPanel) return; // Firefox closes a panel that has lost the focus by itself
  setTimeout(async () => {
    if (document.hasFocus()) return;
    const win = await browser.windows.getCurrent();
    if (!win.focused) closeBar(false);
    else if (!asking) { window.focus(); field.focus(); }
  }, 50);
}
addEventListener("blur", e => { if (e.target === window) focusWent(); });
browser.windows.onFocusChanged.addListener(() => { if (asking) focusWent(); });
