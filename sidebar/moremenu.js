// --- More: what a tab list does beyond the common items ------------------------------
// One "More" at the end of the tab menu, a folder's menu and a space's menu, holding what is
// wanted now and then (sorting, closing around a tab, a whole folder or space at once), so
// that the menus stay short. It opens in place, with a row back, as the menu's other lists
// do. The same things are commands in the command bar and in the shortcut table, with no key
// until you give one. What each does is in the background (listactions.js), through the tab
// menu's own message: one list, the selection, else the tab.
//
// A function around it, so that its names cannot meet those of the other scripts here.
(() => {
  const sortChoices = tabs => [["By name", "name"], ["By site", "site"], ["By last use", "used"]].map(([label, by]) => [label, () => tabAct("sort", tabs, { by })]);
  const many = (n, one, more) => (n > 1 ? more.replace("#", n) : one);

  // The group a row is drawn in, as the sidebar draws it: its folder, or today's tabs.
  const groupOf = id => {
    const f = view.folders.find(x => x.tabs.some(t => t.id === id));
    if (f) return { key: f.key, live: !!f.live, rows: f.tabs.map(t => t.id) };
    return view.tabs.some(t => t.id === id) ? { key: null, live: false, rows: view.tabs.map(t => t.id) } : null;
  };

  // Whether the tabs `ids` already are where "to the top" (or bottom) would put them.
  const already = (group, ids, top) => {
    const mine = group.rows.filter(id => ids.includes(id)), end = top ? group.rows.slice(0, mine.length) : group.rows.slice(-mine.length);
    return mine.every((id, i) => end[i] === id);
  };

  // The tab menu's More, for these tabs (what tabMenuFacts said of each).
  function tabMore(tabs) {
    const n = tabs.length, ids = tabs.map(t => t.id);
    const copy = tabs.every(t => !!t.address) ? [[many(n, "Copy as Markdown link", "Copy # as Markdown links"), () => tabAct("copyMarkdown", tabs)]] : [];
    if (tabs.some(t => t.tile)) return copy;
    const groups = [...new Map(ids.map(groupOf).filter(Boolean).map(g => [g.key, g])).values()];
    const movable = groups.filter(g => !g.live && g.rows.length > 1); // a live folder's order is the search's
    const today = groups.length === 1 && groups[0].key === null ? groups[0] : null;
    const items = [];
    if (movable.length) items.push([movable.every(g => !g.key) ? "Sort today's tabs" : movable.length === 1 ? "Sort this folder" : "Sort their folders", sortChoices(tabs)]);
    if (movable.some(g => !already(g, ids, true))) items.push([many(n, "Move to the top", "Move # tabs to the top"), () => tabAct("top", tabs)]);
    if (movable.some(g => !already(g, ids, false))) items.push([many(n, "Move to the bottom", "Move # tabs to the bottom"), () => tabAct("bottom", tabs)]);
    if (tabs.every(t => t.folder && !t.liveFolder)) items.push([many(n, "Take out of folder", "Take # tabs out of their folders"), () => tabAct("takeOut", tabs)]);
    const closing = [];
    if (today) {
      const at = today.rows.map(id => ids.includes(id)), first = at.indexOf(true), last = at.lastIndexOf(true);
      const dupes = tabs[0].duplicates ?? 0;
      if (dupes) closing.push([dupes === 1 ? "Close 1 duplicate" : `Close ${dupes} duplicates`, () => tabAct("closeDuplicates", tabs)]);
      if (at.some(x => !x)) closing.push(["Close other tabs", () => tabAct("closeOthers", tabs)]);
      if (first > 0) closing.push(["Close tabs above", () => tabAct("closeAbove", tabs)]);
      if (last < at.length - 1) closing.push(["Close tabs below", () => tabAct("closeBelow", tabs)]);
    }
    return [items, copy, closing].filter(part => part.length).flatMap((part, i) => (i ? [null, ...part] : part));
  }

  // At the end of the table (tabmenu.js), after a line.
  TAB_MENU.push({ id: "more", group: 9, many: true, label: () => "More", when: tabs => tabMore(tabs).length > 0, choices: tabMore });

  // A folder's More (menu.js), for its tabs (what tabMenuFacts said of each).
  window.folderMore = (key, live, tabs) => {
    if (!tabs.length) return [];
    const n = tabs.length, loaded = tabs.filter(t => t.loaded), withAddress = tabs.filter(t => t.address);
    const parts = [
      [
        ...(!live && n > 1 ? [["Sort this folder", sortChoices(tabs)]] : []),
        ...(withAddress.length ? [[withAddress.length > 1 ? "Copy addresses" : "Copy address", () => copyHere(withAddress.map(t => t.address), tabsWord(withAddress.length, "Address copied", "# addresses copied"))],
          [withAddress.length > 1 ? "Copy as Markdown links" : "Copy as Markdown link", () => tabAct("copyMarkdown", withAddress)]] : []),
      ],
      [
        ...(loaded.length ? [["Reload all", () => tabAct("reload", loaded)]] : []),
        ...(loaded.some(t => !t.muted) ? [["Mute all", () => tabAct("mute", loaded)]] : []),
        ...(loaded.some(t => t.muted) ? [["Unmute all", () => tabAct("unmute", loaded)]] : []),
        ...(loaded.length ? [["Unload all", () => tabAct("unload", loaded)]] : []),
      ],
      // The search decides what is in a live folder: a pull request closed comes back with it.
      live ? [] : [["Close all its tabs", () => tabAct("closeAll", tabs)]],
    ];
    return parts.filter(part => part.length).flatMap((part, i) => (i ? [null, ...part] : part));
  };

  // A space's More (spacemenu.js), from what spaceFacts (listactions.js) said of it. Sorting
  // and duplicates only for the space you see: the others' lists are not in front of you.
  window.spaceMore = (space, facts) => {
    const here = space === view.space, anyOpen = () => view.folders.some(f => !f.collapsed);
    const parts = [
      [
        ...(here && view.tabs.length > 1 ? [["Sort today's tabs", sortChoices(view.tabs)]] : []),
        ...(here && facts?.duplicates ? [[facts.duplicates === 1 ? "Close 1 duplicate" : `Close ${facts.duplicates} duplicates`, () => tabAct("closeDuplicates", view.tabs)]] : []),
        // All of them at once, where there is more than one: one is a click on its head.
        ...(here && view.folders.length > 1 ? [[anyOpen() ? "Close all folders" : "Open all folders", () => send({ type: "foldFolders", space, collapsed: anyOpen() })]] : []),
      ],
      [
        ...(facts?.loaded ? [["Reload this space", () => send({ type: "spaceAction", action: "reload", space })]] : []),
        ...(facts?.unmuted ? [["Mute this space", () => send({ type: "spaceAction", action: "mute", space })]] : []),
        ...(facts?.muted ? [["Unmute this space", () => send({ type: "spaceAction", action: "unmute", space })]] : []),
        ...(facts?.elsewhere ? [["Unload the other spaces", () => send({ type: "unloadOtherSpaces", space })]] : []),
      ],
    ];
    return parts.filter(part => part.length).flatMap((part, i) => (i ? [null, ...part] : part));
  };
})();
