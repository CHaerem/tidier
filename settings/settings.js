// The settings page: everything goes through the background (moveover.js).
const ask = (what, more) => browser.runtime.sendMessage({ type: "settings:" + what, ...more });
const $ = id => document.getElementById(id);
const el = (tag, props = {}, ...kids) => { const e = Object.assign(document.createElement(tag), props); e.append(...kids); return e; };

let state = null;
// Spaces listed on this page come in the bar's order (state.order, from the background), as on the
// bar itself; one that is not on it (hidden here, say) after them, in Firefox's order.
const inBarOrder = list => {
  const rank = new Map((state?.order ?? []).map((id, i) => [id, i]));
  return [...list].sort((a, b) => (rank.get(a.id) ?? Infinity) - (rank.get(b.id) ?? Infinity));
};
let movedNote = null; // what the move from Sidebery did: said once, and kept on this page

async function refresh() {
  state = await ask("get");
  // Firefox can bring this page back before Tidier has started (a restart with the page open), and
  // then the background does not have everything read yet. Asked again until it has started, and
  // the page is drawn afresh then, with every part of it.
  if (!state.started) waitForStart();
  if (state.moved) movedNote = state.moved;
  $("notices").replaceChildren(...state.notices.map(noticeLine));
  $("allow-hiding").hidden = state.hiding;
  drawMovedNote();
  drawSpaces();
  if (document.activeElement?.closest?.("#rules") == null && !rulesUnsaved()) drawRules();
  if (document.activeElement !== $("archive-hours")) $("archive-hours").value = state.archiveHours;
  $("copy-state").textContent = state.lastCopy ? `Last copy: ${new Date(state.lastCopy).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}.` : "No copy made yet.";
  $("version").textContent = "Version " + state.version;
}
// A notice as the background has it, for the sidebar too. One about a space's proxy or user
// agent, not in use for want of the permission, is said here for each space it is about, with
// the click that gives the permission back: Firefox asks only in a click.
function noticeLine({ kind, text }) {
  const line = el("p", { className: "notice" });
  const spaces = kind === "spaceNetwork" ? state.network.map(n => ({ ...n, name: state.spaces.find(s => s.id === n.id)?.name })).filter(n => n.name) : [];
  if (!spaces.length) { line.textContent = text; return line; }
  const what = spaces.map(n => `${n.name}'s ${n.proxy && n.userAgent ? "proxy and user agent" : n.proxy ? "proxy" : "user agent"}`);
  const allow = el("button", { textContent: "Allow again" });
  allow.onclick = async () => {
    const given = await browser.permissions.request({ permissions: ["webRequest", "webRequestBlocking", ...(spaces.some(n => n.proxy) ? ["proxy"] : [])], origins: ["*://*/*"] }).catch(() => false);
    if (!given) allow.textContent = "Not allowed: click to be asked again";
  };
  line.classList.add("with-button");
  line.append(el("span", { textContent: `${andList(what)} ${what.length === 1 && !(spaces[0].proxy && spaces[0].userAgent) ? "is" : "are"} not in use: Tidier no longer has the permission for ${what.length === 1 && !(spaces[0].proxy && spaces[0].userAgent) ? "it" : "them"}.` }), allow);
  return line;
}

let waitingForStart = false;
async function waitForStart() {
  if (waitingForStart) return;
  waitingForStart = true;
  for (let i = 0; i < 120; i++) {
    await new Promise(r => setTimeout(r, 500));
    if ((await ask("get").catch(() => null))?.started) { location.reload(); return; }
  }
}

// --- After the move from Sidebery ------------------------------------------------------
const counted = (n, one, many = one + "s") => `${n} ${n === 1 ? one : many}`;
const andList = parts => parts.length < 2 ? parts.join("") : `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}`;

// After the move from Sidebery, once: what came over and what is left to do. Nobody asked for
// the move, so Tidier opens this page then (afterMoving, moveover.js).
let movedShownSaid = false;
function drawMovedNote() {
  const n = movedNote;
  $("moved-section").hidden = !n && !state.afterMove;
  $("moved").hidden = !n;
  $("moved-ask").hidden = !n || !state.hiding;
  $("moved-allow").hidden = !n || state.hiding;
  sidebarsToOpen();
  if (!n) return;
  // One thing a line: what happened first, then what is left to do, so it reads at a glance.
  const lines = [
    `Tidier now does what Sidebery did here, with its own sidebar, spaces and folders: ${counted(n.folders, "folder")} and ${counted(n.tabs, "tab")} came over${n.closed ? `, ${n.closed} of the folders closed, as in Sidebery` : ""}. A copy of everything was taken first.`,
    n.hidden.length && `${andList(n.hidden)} had no space in Sidebery and ${n.hidden.length === 1 ? "is" : "are"} empty, so ${n.hidden.length === 1 ? "it is" : "they are"} hidden here: tick ${n.hidden.length === 1 ? "it" : "them"} under Shown on this machine to show ${n.hidden.length === 1 ? "it" : "them"}.`,
    "Sidebery is no longer needed: turn it off or remove it in about:addons. Its rules, the order of its spaces and which folders were closed can be read only from its export, so make that first (From Sidebery, below).",
  ];
  $("moved").replaceChildren(...lines.filter(Boolean).map(text => el("span", { className: "note-line", textContent: text })));
  // Drawn, with what to answer (#moved-ask): only now does Tidier hide tabs, and Firefox ask (aftermove.js).
  if (!movedShownSaid) { movedShownSaid = true; ask("movedShown"); }
}

// Firefox opens no sidebar for an extension by itself, so after the move a window has no list
// of tabs of Tidier's until you show it there. Each of them shows this page (aftermove.js),
// with a button: a click in a page of Tidier's is what lets it open the sidebar in that
// window. Said, and taken back as you do it, until Firefox restarts.
const thisWindow = browser.windows.getCurrent().then(w => w.id, () => null);
async function sidebarsToOpen() {
  if (!state.afterMove && !movedNote) { $("windows-without").hidden = true; return; }
  const windows = (await browser.windows.getAll({ windowTypes: ["normal"] })).filter(w => !w.incognito);
  const without = [];
  for (const w of windows) if (!(await browser.sidebarAction.isOpen({ windowId: w.id }).catch(() => true))) without.push(w.id);
  const me = await thisWindow, here = without.includes(me), others = without.filter(id => id !== me).length;
  const key = state.afterMove?.sidebarKey || "the key for Tidier's sidebar";
  $("windows-without").hidden = !without.length;
  $("windows-without-text").textContent = [
    here && "This window does not show Tidier's sidebar yet, so not its list of tabs.",
    others && `${others === 1 ? "Another window does" : `${others} other windows do`} not ${here ? "either" : "show Tidier's sidebar yet"}: ${others === 1 ? "it shows" : "each shows"} this page too, with a button for it, or press ${key} there.`,
  ].filter(Boolean).join(" ");
  $("show-sidebar").hidden = !here;
}
$("show-sidebar").onclick = () => { browser.sidebarAction.open().catch(() => {}); setTimeout(sidebarsToOpen, 500); };
browser.windows.onFocusChanged.addListener(() => { if (state) sidebarsToOpen(); });

// A file you chose, or null if it is no JSON at all. Emptied after reading, or choosing
// the same file again (after making a new export, say) would do nothing.
const readFile = async input => {
  try { return JSON.parse(await input.files[0].text()); } catch (err) { return null; } finally { input.value = ""; }
};
const sideberyResult = r => {
  const parts = [r.rules && counted(r.rules, "rule"), r.order && `the order of ${counted(r.order, "space")}`, r.newFolds && counted(r.newFolds, "closed folder")].filter(Boolean);
  return [
    parts.length ? `Took in ${andList(parts)}.` : "Nothing new: all of it is here already.",
    r.newSpaces.length && `${r.newSpaces.length === 1 ? "A new space" : "New spaces"}: ${r.newSpaces.join(", ")}.`,
    r.panelsLeftOut && `Left out the rules of ${counted(r.panelsLeftOut, "panel")} with no container.`,
    r.folds === null && "There is no snapshot in this export, so folders start open. To keep which are closed: Create snapshot in Sidebery's settings, and export again.",
  ].filter(Boolean).join(" ");
};
// A background error says so here too, rather than leaving the page as it was.
const orSay = (line, job) => job().catch(err => { line.textContent = `That did not work: ${err.message}`; });
$("sidebery-file").onchange = e => orSay($("sidebery-result"), async () => {
  const r = await ask("importSidebery", { backup: await readFile(e.target) });
  $("sidebery-result").textContent = r ? sideberyResult(r) : "This is not Sidebery's export.";
  if (r) refresh();
});

// --- Rules --------------------------------------------------------------------------
const saveRules = () => ask("rules", { rules: [...$("rules").children].map(l => ({ url: l.querySelector("input").value.trim(), space: l.querySelector("select").value })) });
// A line added and not typed in yet is yours, not the record's: a save from another line, or one
// from another machine, draws the rules again, and must not take it away from under your hands.
const rulesUnsaved = () => [...$("rules").querySelectorAll("input")].some(i => !i.value.trim());
function drawRules() {
  $("rules").replaceChildren(...state.rules.map(rule => ruleLine(rule)));
}
function ruleLine(rule) {
  const text = el("input", { type: "text", value: rule.url, placeholder: "address, or /regular expression/", ariaLabel: "Address" });
  // A space that is gone is shown as that. With only the ones there are, the first would
  // look chosen, and the next save would send the rule somewhere you never said.
  const gone = !!rule.space && !state.spaces.some(s => s.id === rule.space);
  const space = el("select", { ariaLabel: "Space" },
    ...(gone ? [el("option", { value: rule.space, textContent: "A space that is gone", selected: true })] : []),
    ...inBarOrder(state.spaces).map(s => el("option", { value: s.id, textContent: s.name, selected: s.id === rule.space })));
  const remove = el("button", { textContent: "×", title: "Remove this rule" });
  const why = el("p", { className: "hint rule-problem" });
  // Why a rule does nothing, as it is typed: otherwise a rule would just never work. A rule made
  // from a tab's menu is a regular expression for its site: said in plain words under it.
  const showWhy = () => {
    const problem = ruleProblem(text.value.trim()) ?? (gone && space.value === rule.space ? "Its space is gone, so the rule does nothing." : "");
    const typed = text.value.trim(), site = !problem && typed.match(SITE_RULE)?.[1].replace(/\\(.)/g, "$1");
    // Begun as a regular expression and never closed, it is text to find (rulematch.js): said, or
    // "/[a-z" would look like a rule for every address with a letter.
    const unclosed = !problem && /^\/.*[[\](){}*+?^$|\\]/.test(typed) && !/^\/.*\/[a-z]*$/.test(typed);
    why.textContent = problem || (site ? `Every page on ${site}.` : unclosed ? "With no / at its end this is not a regular expression: it is text to find in the address." : "");
    why.classList.toggle("wrong", !!problem);
    why.hidden = !why.textContent;
  };
  showWhy();
  const line = el("div", { className: "line" }, text, space, remove, why);
  text.oninput = showWhy;
  text.onchange = space.onchange = () => { showWhy(); saveRules(); };
  // The second click of a double click would land on the rule that moves up under it: it
  // does nothing (sidebar/secondclick.js).
  remove.onclick = secondClick.acts(() => {
    const next = line.nextElementSibling?.querySelector("button") ?? $("add-rule");
    const at = [...$("rules").children].indexOf(line), was = { url: text.value.trim(), space: space.value };
    line.remove();
    saveRules();
    next.focus();
    if (was.url) ruleRemoved(was, at);
  });
  return line;
}
// The rule made from a tab's menu (siteRuleText, tabactions.js).
const SITE_RULE = /^\/\^https\?:\\\/\\\/\(www\\\.\)\?(.+)\\\/\/$/;
// A removed rule can be had back, as everything else in Tidier: one quiet line, for a while.
let undoTimer = null;
function ruleRemoved(rule, at) {
  const line = $("rule-undo"), undo = el("button", { className: "quiet", textContent: "Undo" });
  undo.onclick = () => {
    const lines = [...$("rules").children], back = ruleLine(rule);
    $("rules").insertBefore(back, lines[at] ?? null);
    saveRules();
    line.hidden = true;
    back.querySelector("input").focus();
  };
  line.replaceChildren(el("span", { textContent: `Removed the rule for ${rule.url}.` }), undo);
  line.hidden = false;
  clearTimeout(undoTimer);
  undoTimer = setTimeout(() => { line.hidden = true; }, 15000);
}
$("add-rule").onclick = () => {
  const line = ruleLine({ url: "", space: inBarOrder(state.spaces)[0]?.id });
  $("rules").append(line);
  line.querySelector("input").focus();
};

// --- Tabs that tidy themselves ----------------------------------------------------------
// The background decides what is allowed (archiveHoursFrom, archive.js) and says what it
// stored, which the field then shows: an emptied field or -5 changes nothing.
$("archive-hours").onchange = async e => { e.target.value = await ask("archiveHours", { hours: e.target.value }); };

$("allow-hiding").onclick = () => browser.permissions.request({ permissions: ["tabHide"] }).then(refresh);

// --- Copies -----------------------------------------------------------------------------
$("copy-now").onclick = async () => {
  const r = await ask("copyNow");
  $("copy-state").textContent = r?.saved ? `Saved as ${r.saved}, with the copies of the last two weeks in ~/.config/tidier/copies.` : `No copy was made: ${r?.error}`;
};
$("copy-save").onclick = async () => {
  const copy = await ask("copyFile");
  const name = `tidier-${new Date().toISOString().slice(0, 10)}.json`;
  const a = el("a", { href: URL.createObjectURL(new Blob([JSON.stringify(copy)], { type: "application/json" })), download: name });
  a.click();
  $("copy-state").textContent = `Saved as ${name}, where Firefox saves downloads.`;
};
let incoming = null;
const mergeLine = ([id, n]) => {
  const comes = [counted(n.essentials, "essential"), counted(n.folders, "folder"), counted(n.savedTabs, "saved tab"), counted(n.rules, "rule")].filter(part => !part.startsWith("0 "));
  const text = [...comes, ...(n.isNew ? ["a new space"] : [])].join(", ");
  // A space with nothing new has nothing to choose: said, without a box.
  if (!text) return el("p", { className: "line nothing-new" }, el("span", { className: "dot", ariaHidden: "true", style: `color:${n.color}` }), `${n.name}: nothing new`);
  return el("label", { className: "line" },
    el("input", { type: "checkbox", checked: true, value: id }),
    el("span", { className: "dot", ariaHidden: "true", style: `color:${n.color}` }),
    el("span", { className: "label-text", textContent: `${n.name}: ${text}` }));
};
$("copy-file").onchange = e => orSay($("merge-result"), async () => {
  $("merge-result").textContent = "";
  $("merge").hidden = true;
  incoming = await readFile(e.target);
  const summary = await ask("copySummary", { copy: incoming });
  if (!summary) { $("merge-result").textContent = "This is not a Tidier copy."; return; }
  const lines = Object.entries(summary);
  if (!lines.some(([, n]) => n.essentials || n.folders || n.savedTabs || n.rules || n.isNew)) { $("merge-result").textContent = "Nothing new: all of it is here already."; return; }
  $("merge-spaces").replaceChildren(...lines.map(mergeLine));
  $("merge").hidden = false;
});
$("merge-cancel").onclick = () => { incoming = null; $("merge").hidden = true; $("merge-result").textContent = "Nothing taken in."; };
$("merge-go").onclick = () => orSay($("merge-result"), async () => {
  const spaces = [...$("merge-spaces").querySelectorAll("input:checked")].map(i => i.value);
  $("merge").hidden = true; // at once: a second click would find all of it here, and say only that
  const r = await ask("merge", { copy: incoming, spaces });
  const took = andList([
    r.essentials && counted(r.essentials, "essential"), r.folders && counted(r.folders, "folder"),
    r.tabs && counted(r.tabs, "saved tab"), r.rules && counted(r.rules, "rule"), r.spaces && counted(r.spaces, "new space"),
  ].filter(Boolean));
  $("merge-result").textContent = took ? `Took in ${took}. Nothing here was removed.` : "Nothing taken in.";
  refresh();
});

// A page out of sight is drawn again when it is looked at.
document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
browser.permissions.onAdded.addListener(refresh);
browser.permissions.onRemoved.addListener(refresh);
refresh();
