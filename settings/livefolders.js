// Live folders on the settings page (livefolders.js): each a name, a space, what it is filled
// from, and the search's words or the feed's address. Saved as a line is changed; what cannot
// be a folder is said under its line, and is not saved until it can.
(async () => {
  const list = $("live-folders"), status = $("live-state");
  const tell = msg => browser.runtime.sendMessage(msg);
  const KINDS = [["prs", "Pull requests"], ["issues", "Issues"], ["repos", "Your repositories"], ["feed", "A feed"]];
  const HINTS = { prs: "org:your-company, or nothing for all of yours", issues: "org:your-company, or nothing for all of yours", repos: "org:your-company, or nothing for all of yours", feed: "https://…/feed.xml" };
  let spaces = [];

  const read = line => {
    const [name, text] = line.querySelectorAll("input"), [space, what] = line.querySelectorAll("select");
    return { id: line.dataset.id, name: name.value.trim(), space: space.value, what: what.value, ...(what.value === "feed" ? { feed: text.value.trim() } : { search: text.value.trim() }) };
  };
  // Every line that is a folder goes to the background, which keeps what it can; a line it
  // did not keep says why, and stays as typed.
  async function save() {
    const lines = [...list.children], wanted = lines.map(read);
    const { folders } = await tell({ type: "live:set", folders: wanted.filter(f => f.name) });
    for (const [i, line] of lines.entries()) {
      const kept = folders.some(f => f.id === line.dataset.id), why = line.querySelector(".rule-problem");
      why.textContent = kept ? "" : !wanted[i].name ? "It needs a name." : wanted[i].what === "feed" ? "A feed is an address that starts with http:// or https://."
        : "Only words that narrow the search, such as org:name, repo:owner/name or -label:wip.";
      why.hidden = kept;
    }
  }

  function folderLine(f) {
    const name = el("input", { type: "text", value: f.name ?? "", placeholder: "Name of the folder", ariaLabel: "Name" });
    const gone = !!f.space && !spaces.some(s => s.id === f.space);
    const space = el("select", { ariaLabel: "Space" },
      ...(gone ? [el("option", { value: f.space, textContent: "A space that is gone", selected: true })] : []),
      ...inBarOrder(spaces).map(s => el("option", { value: s.id, textContent: s.name, selected: s.id === f.space })));
    const what = el("select", { ariaLabel: "Filled from" }, ...KINDS.map(([value, textContent]) => el("option", { value, textContent, selected: value === f.what })));
    const text = el("input", { type: "text", value: f.what === "feed" ? f.feed ?? "" : f.search ?? "", ariaLabel: "The search's words, or the feed's address" });
    const remove = el("button", { textContent: "×", title: "Remove this live folder, with its tabs" });
    const why = el("p", { className: "hint rule-problem wrong", hidden: true });
    const line = el("div", { className: "line" }, name, space, what, text, remove, why);
    line.dataset.id = f.id;
    const hint = () => { text.placeholder = HINTS[what.value]; };
    hint();
    name.onchange = space.onchange = text.onchange = save;
    what.onchange = () => { hint(); save(); };
    // The second click of a double click would land on the line that moves up under it
    // (sidebar/secondclick.js).
    remove.onclick = secondClick.acts(() => {
      const next = line.nextElementSibling?.querySelector("button") ?? $("add-live");
      line.remove();
      save();
      next.focus();
    });
    return line;
  }

  function say({ helper, file }) {
    const parts = [
      !helper && "No helper answers on this machine, so nothing fills them here: run native/install.sh in Tidier's folder.",
      file.length > 0 && `The helper's own file on this machine has ${file.length === 1 ? "one more" : `${file.length} more`}: ${file.map(f => f.name).join(", ")}.`,
    ].filter(Boolean);
    status.textContent = parts.join(" ");
    status.hidden = !parts.length;
  }

  async function draw() {
    spaces = (await browser.contextualIdentities.query({}).catch(() => [])).map(c => ({ id: c.cookieStoreId, name: c.name }));
    const got = await tell({ type: "live:get" });
    // (Not from under your hands: a line being typed in is yours until it is saved.)
    if (!list.contains(document.activeElement)) list.replaceChildren(...got.folders.map(folderLine));
    say(got);
  }
  $("add-live").onclick = () => {
    const line = folderLine({ id: crypto.randomUUID(), name: "", space: inBarOrder(spaces)[0]?.id, what: "prs", search: "" });
    list.append(line);
    line.querySelector("input").focus();
  };
  // Another machine's change comes through storage (syncprefs.js).
  browser.storage.onChanged.addListener((changes, area) => { if (area === "local" && "liveOwnFolders" in changes) draw(); });
  await draw();
})();
