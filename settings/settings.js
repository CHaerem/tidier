// The settings page: everything goes through the background (moveover.js).
const ask = (what, more) => browser.runtime.sendMessage({ type: "settings:" + what, ...more });
const $ = id => document.getElementById(id);
const el = (tag, props = {}, ...kids) => { const e = Object.assign(document.createElement(tag), props); e.append(...kids); return e; };

let state = null;

async function refresh() {
  state = await ask("get");
  $("notices").replaceChildren(...state.notices.map(text => el("p", { className: "notice", textContent: text })));
  const r = state.report;
  $("alone-state").textContent = r.alone ? "Tidier is on its own here: no Sidebery needed." : "This browser uses Sidebery for its tab list, spaces and folders.";
  $("allow-hiding").hidden = !r.alone || state.hiding;
  $("move").hidden = r.alone;
  $("move-back").hidden = !(r.alone && r.canMoveBack);
  // Each step needs Sidebery in one state (moveover.js refuses it otherwise): what it is in
  // now, once Tidier may look, and as it changes in about:addons.
  const sidebery = state.sidebery;
  $("move-said").textContent = { on: "Sidebery is still on: disable it first.", off: "Sidebery is off: ready to move." }[sidebery] ?? "";
  $("back-said").textContent = { on: "Sidebery is on: ready to go back.", off: "Sidebery is off: enable it first.", none: "Sidebery is not installed here." }[sidebery] ?? "";
  watchSidebery();
  drawMoved();
  $("report").replaceChildren(
    el("li", { textContent: `${r.essentials} essentials and ${r.tabs} tabs stay as they are.` }),
    el("li", { textContent: `${r.folders.length} folders become Tidier's own: ` + r.folders.map(f => `${f.name} (${f.tabs})`).join(", ") }),
    el("li", { textContent: `${r.rules} rules. Sidebery's own rules, and which folders are closed, can only be read from its export: import it below first, with a snapshot in it.` }),
  );
  drawSpaces();
  if (document.activeElement?.closest?.("#rules") == null) drawRules();
  if (document.activeElement !== $("archive-hours")) $("archive-hours").value = state.archiveHours;
  $("copy-state").textContent = state.lastCopy ? `Last copy: ${new Date(state.lastCopy).toLocaleString()}.` : "No copy made yet.";
  $("version").textContent = "Version " + state.version;
}

function drawRules() {
  const save = () => ask("rules", { rules: [...$("rules").children].map(l => ({ url: l.querySelector("input").value.trim(), space: l.querySelector("select").value })) });
  $("rules").replaceChildren(...state.rules.map(rule => ruleLine(rule, save)));
}
function ruleLine(rule, save) {
  const text = el("input", { type: "text", value: rule.url, placeholder: "address, or /regular expression/" });
  // A space that is gone is shown as that. With only the ones there are, the first would
  // look chosen, and the next save would send the rule somewhere you never said.
  const gone = !!rule.space && !state.spaces.some(s => s.id === rule.space);
  const space = el("select", {},
    ...(gone ? [el("option", { value: rule.space, textContent: "A space that is gone", selected: true })] : []),
    ...state.spaces.map(s => el("option", { value: s.id, textContent: s.name, selected: s.id === rule.space })));
  const remove = el("button", { textContent: "×", title: "Remove" });
  const why = el("p", { className: "hint rule-problem" });
  // Why a rule does nothing, as it is typed: otherwise a rule would just never work.
  const showWhy = () => {
    why.textContent = ruleProblem(text.value.trim()) ?? (gone && space.value === rule.space ? "Its space is gone, so the rule does nothing." : "");
    why.hidden = !why.textContent;
  };
  showWhy();
  const line = el("div", { className: "line" }, text, space, remove, why);
  text.oninput = showWhy;
  text.onchange = space.onchange = () => { showWhy(); save(); };
  remove.onclick = () => { line.remove(); save(); };
  return line;
}
$("add-rule").onclick = () => {
  const save = () => ask("rules", { rules: [...$("rules").children].map(l => ({ url: l.querySelector("input").value.trim(), space: l.querySelector("select").value })) });
  $("rules").append(ruleLine({ url: "", space: state.spaces[0]?.id }, save));
};

$("archive-hours").onchange = e => ask("archiveHours", { hours: e.target.value });
$("allow-hiding").onclick = () => browser.permissions.request({ permissions: ["tabHide"] }).then(refresh);

let watching = false;
function watchSidebery() {
  if (watching || !browser.management?.onEnabled) return; // until the management permission is given
  watching = true;
  for (const event of ["onEnabled", "onDisabled", "onInstalled", "onUninstalled"]) browser.management[event].addListener(() => refresh());
}

$("move-over").onclick = async () => {
  if (state?.sidebery === "on") { $("move-said").textContent = "Sidebery is still on: disable it first."; return; }
  // Both need your click, so they come before the first wait. Firefox gives a sidebar only
  // to the window in front, and brings Tidier's back where it was open when Tidier starts
  // again alone: with Sidebery off a window has no sidebar, and with the tab bar hidden no
  // list of tabs at all. (Another window is not brought to the front to be given it too: it
  // may be on another desktop, and Firefox may bring it only a moment later, too late. It
  // gets this page instead, with a button for it: drawMoved.)
  browser.sidebarAction.open().catch(() => {});
  // Asked here, in one go. Without them, tabs are simply not hidden yet, and a page's first
  // request can go out in the wrong container; management is to see whether Sidebery is off.
  await browser.permissions.request({ permissions: ["tabHide", "webRequest", "webRequestBlocking", "management"], origins: ["<all_urls>"] }).catch(() => {});
  const r = await ask("moveOver");
  if (r?.refused) $("move-said").textContent = r.refused;
};
$("do-move-back").onclick = async () => {
  await browser.permissions.request({ permissions: ["management"] }).catch(() => {});
  const r = await ask("moveBack");
  if (r?.refused) $("back-said").textContent = r.refused;
};

// A file you chose, or null if it is no JSON at all. Emptied after reading, or choosing
// the same file again (after making a new export, say) would do nothing.
const readFile = async input => {
  try { return JSON.parse(await input.files[0].text()); } catch (err) { return null; } finally { input.value = ""; }
};
const counted = (n, one) => `${n} ${one}${n === 1 ? "" : "s"}`;
const andList = parts => parts.length < 2 ? parts.join("") : `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}`;
const sideberyResult = r => {
  const parts = [r.rules && counted(r.rules, "rule"), r.order && `the order of ${counted(r.order, "space")}`, r.folds && counted(r.folds, "closed folder")].filter(Boolean);
  return [
    parts.length ? `Imported ${andList(parts)}.` : "Nothing new to import.",
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
$("copy-now").onclick = async () => {
  const r = await ask("copyNow");
  $("copy-state").textContent = r?.saved ? `Saved as ${r.saved}.` : `No copy was made: ${r?.error}`;
};
$("copy-save").onclick = async () => {
  const copy = await ask("copyFile");
  const a = el("a", { href: URL.createObjectURL(new Blob([JSON.stringify(copy)], { type: "application/json" })), download: `tidier-${new Date().toISOString().slice(0, 10)}.json` });
  a.click();
};
let incoming = null;
const mergeLine = ([id, n]) => {
  const comes = [counted(n.essentials, "essential"), counted(n.folders, "folder"), counted(n.savedTabs, "saved tab"), counted(n.rules, "rule")].filter(part => !part.startsWith("0 "));
  const text = [...comes, ...(n.isNew ? ["a new space"] : [])].join(", ") || "nothing new";
  return el("label", { className: "line" },
    el("input", { type: "checkbox", checked: true, value: id }),
    el("span", { textContent: "●", style: `color:${n.color}` }),
    `${n.name}: ${text}`);
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

// Right after moving over (afterMovingOver, moveover.js), this page comes back in front:
// what happened, and the one thing to do next. Firefox asks about hidden tabs once this
// is drawn, and Tidier waits for it to be. A window that came over without Tidier's
// sidebar shows it too, with the button for it: a click here is what lets Tidier open it.
let movedTold = false;
const thisWindow = browser.windows.getCurrent().then(w => w.id);
async function drawMoved() {
  const moved = location.hash === "#moved" ? state.moved : null;
  $("moved").hidden = !moved;
  if (!moved) return;
  const me = await thisWindow, r = state.report;
  const lacking = moved.noSidebar.includes(me), others = moved.noSidebar.filter(id => id !== me).length;
  const show = el("button", { textContent: "Show Tidier's sidebar in this window" });
  show.onclick = () => { browser.sidebarAction.open().catch(() => {}); show.disabled = true; setTimeout(refresh, 600); };
  $("moved").replaceChildren(
    el("h2", { textContent: "Moved over" }),
    el("p", { textContent: `${counted(r.essentials, "essential")}, ${counted(r.tabs, "tab")} and ${counted(r.folders.length, "folder")} are Tidier's own now. Going back is below.` }),
    el("p", { className: "notice" }, "When Firefox asks whether Tidier may hide tabs, choose ", el("strong", { textContent: "Keep Tabs Hidden" }), ". Disable Extension would turn Tidier off."),
    ...(lacking ? [el("p", { textContent: "This window has no list of tabs yet." }), show] : []),
    ...(others ? [el("p", { textContent: `${others === 1 ? "Your other window shows this page too, with a button for its sidebar" : `Your ${others} other windows show this page too, with a button for their sidebar`} (or press ${moved.sidebarKey || "the key for Tidier's sidebar"} there).` })] : []),
  );
  if (!movedTold) { movedTold = true; ask("moved"); }
}

browser.permissions.onAdded.addListener(refresh);
refresh();
