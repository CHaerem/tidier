"""Folders: making and moving, dragging, live folders, closed folders that rest, moves that lose
nothing, and archiving.
"""
import json
import re
import time
from testfirefox import EXT_ID
from smokechecks.base import (
    DOWN, ENTER, H, RECENTLY_CLOSED_PLACEHOLDERS, check, ext_page, extension_message, into_page,
    more_tabs_here, no_problems, press, seen, sidebar_page, until,
)


def alone_folders(m):
    r = sidebar_page(m, """
      const n0 = folders().length;
      send({type: "newFolder", space: spaces().find(s => s.active).id, name: "Smoke folder"});
      await wait(1000);
      const made = folders();
      const tab = plainTabs()[0];
      const title = tab.querySelector(".title").textContent, tabId = Number(tab.dataset.tab);
      const head = doc.querySelector("#tabs .folder .head"), key = head.dataset.folderHead;
      send({type: "moveTab", tabId, folder: key, before: null});
      await wait(2500);
      const moved = folders();
      head.click(); await wait(800);
      const closed = folders();
      head.click(); await wait(800);
      send({type: "renameFolder", key, name: "Renamed"});
      await wait(800);
      const renamed = folders();
      return {n0, made, title, tabId, key, moved, closed, renamed};""")
    check("a folder is made in the sidebar", len(r["made"]) == r["n0"] + 1 and r["made"][-1]["name"] == "Smoke folder", str(r))
    check("a tab goes into a folder", r["title"] in r["moved"][-1]["tabs"], str(r))
    check("a folder folds and unfolds", r["closed"][-1]["collapsed"] is True and r["renamed"][-1]["collapsed"] is False, str(r))
    check("a folder is renamed", r["renamed"][-1]["name"] == "Renamed", str(r))
    s = m.js(H + """const all = (await storage("%s", ["syncedTabs"])).syncedTabs, f = all[args[0]];
      const tabs = Object.entries(all).filter(([, e]) => e.parentKey === args[0]);
      return {folder: f && {name: f.name, own: f.own}, saved: tabs.map(([k, e]) => !!e.saved), key: tabs[0]?.[0],
              pages: wins().flatMap(w => w.gBrowser.tabs).filter(t => url(t).includes("group.html")).length,
              reps: tabs[0] ? wins().map(w => w.gBrowser.tabs.filter(t => key(w, t) === JSON.stringify(tabs[0][0])).length) : []};""" % EXT_ID, r["key"])
    check("a folder is Tidier's own data, with no tab of its own, and its tab is saved", s["folder"] == {"name": "Renamed", "own": True} and s["saved"] == [True] and s["pages"] == 0, str(s))
    # ⌘W on a saved tab unloads it, in its place; closing it unloaded removes it.
    k = json.dumps(s["key"])
    u = m.js(H + """const k = args[0], w = main(), t = w.gBrowser.tabs.find(x => key(w, x) === k);
      w.gBrowser.selectedTab = t; await wait(2000);
      const live = w.gBrowser.tabs.find(x => key(w, x) === k);
      w.gBrowser.removeTab(live); await wait(2500);
      return {state: find(k), stored: !!(await storage("%s", ["syncedTabs"])).syncedTabs[JSON.parse(k)]};""" % EXT_ID, k)
    check("⌘W on a tab in a folder unloads it, in every window", u["stored"] and all(len(x) == 1 and x[0].endswith("/unloaded") for x in u["state"]), str(u))
    # The folder survives a tab event, a restart of the background, and deleting it keeps its tabs.
    r = sidebar_page(m, """
      const key = args[0];
      send({type: "deleteFolder", key});
      await wait(1500);
      return {folders: folders(), rows: rows()};""", r["key"])
    check("deleting a folder keeps its tabs, as ordinary tabs", not [f for f in r["folders"] if f["name"] == "Renamed"], str(r))


def alone_moves(m):
    # Tabs moved in the sidebar move in every window; essentials too.
    r = sidebar_page(m, """
      const tabs = plainTabs().map(x => Number(x.dataset.tab));
      const first = tabs[0], last = tabs.at(-1);
      // Each is waited for until it shows, not for a set time: a busy machine takes its own.
      const until = async f => { for (let i = 0; i < 100 && !f(); i++) await wait(100); };
      send({type: "moveTab", tabId: last, before: first, folder: null});
      await until(() => Number(plainTabs()[0]?.dataset.tab) === last);
      const tiles0 = [...doc.querySelectorAll("#essentials .tile")].map(t => Number(t.dataset.tab));
      send({type: "moveEssential", tabId: tiles0.at(-1), before: tiles0[0]});
      await until(() => Number(doc.querySelector("#essentials .tile")?.dataset.tab) === tiles0.at(-1));
      await wait(500); // and in the other window
      return {count: tabs.length, moved: last, was: first, order: plainTabs().map(x => Number(x.dataset.tab)), tiles0, tiles1: [...doc.querySelectorAll("#essentials .tile")].map(t => Number(t.dataset.tab))};""")
    check("a tab moved in the sidebar is where you put it", r["order"][0] == r["moved"] and r["order"][1] == r["was"], str(r))
    check("an essential moved in the sidebar is where you put it", r["tiles1"][0] == r["tiles0"][-1], str(r))
    same = m.js(H + """const order = w => w.gBrowser.tabs.filter(t => !t.pinned && key(w, t) && t.userContextId === main().gBrowser.selectedTab.userContextId).map(t => key(w, t));
      const pins = w => w.gBrowser.tabs.filter(t => t.pinned).map(t => ek(w, t));
      return {tabs: wins().map(order), pins: wins().map(pins)};""")
    check("other windows have the same order of tabs", all(x == same["tabs"][0] for x in same["tabs"]) and same["tabs"][0], str(same))
    check("other windows have the same order of essentials", all(x == same["pins"][0] for x in same["pins"]), str(same))
    # Pinned and unpinned from the sidebar: an essential in every window, and back.
    r = sidebar_page(m, """
      const tab = plainTabs()[0], tabId = Number(tab.dataset.tab), n = tiles().length, was = tab.querySelector(".title").textContent;
      send({type: "pin", tabId, pinned: true});
      await wait(2000);
      const pinned = tiles().length;
      send({type: "pin", tabId, pinned: false});
      await wait(2500);
      return {n, pinned, after: tiles().length, url: was};""")
    check("a tab pinned in the sidebar is an essential, and unpinned an ordinary tab again", r["pinned"] == r["n"] + 1 and r["after"] == r["n"], str(r))
    r = m.js(H + """let counts;
      for (let i = 0; i < 60; i++) { counts = wins().map(w => w.gBrowser.tabs.filter(t => !t.pinned && t.linkedBrowser && !key(w, t) && /^https:/.test(url(t))).length); if (counts.every(x => x === 0)) break; await wait(100); }
      return counts;""")
    check("an essential unpinned while loaded is synced again, with a ghost in every window", all(x == 0 for x in r), str(r))
    # Moved to another space: there, and gone here, in every window.
    r = sidebar_page(m, """
      const tab = plainTabs()[0], tabId = Number(tab.dataset.tab), there = spaces().find(s => !s.active && s.id !== "firefox-container-4").id;
      const before = plainTabs().length;
      send({type: "moveToSpace", tabId, space: there});
      await wait(3500);
      return {before, after: plainTabs().length, there};""")
    check("a tab moved to another space is gone from this one", r["after"] == r["before"] - 1, str(r))


def alone_live_folders(m):
    # A live folder is one of Tidier's own folders, with no tab of its own.
    m.js(H + """return 1;""")
    open(m.fake_prs, "w").write(json.dumps({"folders": [{"id": "prs", "name": "Pull requests", "container": "firefox-container-1"}],
                                            "items": {"prs": [{"url": "https://example.org/?smoke-pr-1", "title": "One", "number": 1, "repo": "r"},
                                                              {"url": "https://example.org/?smoke-pr-2", "title": "Two", "number": 2, "repo": "r"}]}}))
    extension_message(m, {"type": "refreshLiveFolders"})
    r = m.js(H + """await wait(1500); const all = (await storage("%s", ["syncedTabs"])).syncedTabs;
      const f = Object.entries(all).find(([, e]) => e.live === "prs"), tabs = Object.entries(all).filter(([, e]) => e.liveFolder === "prs");
      return {folder: f && {own: f[1].own, name: f[1].name}, tabs: tabs.map(([, e]) => [e.parentKey === f[0], !!e.saved]), reps: tabs.map(([k]) => find(JSON.stringify(k)))};""" % EXT_ID)
    check("a live folder is Tidier's own folder, with its pull requests unloaded in every window", r["folder"] == {"own": True, "name": "Pull requests"}
          and r["tabs"] == [[True, False], [True, False]] and all(all(len(x) == 1 and x[0].endswith("/unloaded") for x in rep) for rep in r["reps"]), str(r))
    open(m.fake_prs, "w").write(json.dumps({"folders": [{"id": "prs", "name": "Pull requests", "container": "firefox-container-1"}], "items": {"prs": []}}))
    extension_message(m, {"type": "refreshLiveFolders"})
    r = m.js(H + """await wait(1500); const all = (await storage("%s", ["syncedTabs"])).syncedTabs;
      return {tabs: Object.values(all).filter(e => e.liveFolder === "prs").length, left: wins().flatMap(w => w.gBrowser.tabs).filter(t => t.label.includes("r#")).length, folder: Object.values(all).some(e => e.live === "prs")};""" % EXT_ID)
    check("a pull request that leaves the search is removed, and the folder stays", r["tabs"] == 0 and r["left"] == 0 and r["folder"], str(r))
    r = sidebar_page(m, RECENTLY_CLOSED_PLACEHOLDERS)
    check("and it leaves no placeholder in Recently Closed, for ⌘⇧T to bring back", not r["left"], str(r))


def alone_safe_moves(m):
    # Moves that cannot lose anything (safemoves.js), and a sidebar that comes back.
    # Where the tab with this address is: the container of each tab that has it (only the
    # real tab does), and of every copy in every window once it is in the record.
    where_script = H + """const pairs = wins().flatMap(w => w.gBrowser.tabs.filter(t => url(t).includes(args[0])).map(t => [w, t]));
      const k = pairs[0] && key(pairs[0][0], pairs[0][1]);
      return {at: pairs.map(([w, t]) => ctxOf(t)), selected: pairs.some(([w, t]) => t.selected && w === main()), loaded: pairs.every(([w, t]) => !!t.linkedPanel),
              registered: !!k, copies: k ? wins().flatMap(w => w.gBrowser.tabs.filter(t => key(w, t) === k).map(t => ctxOf(t))) : [], windows: wins().length};"""
    # In the sidebar: a real drag of a tab's row onto a space's dot, and the queue done with it.
    drop_on_space = """
      const dropOnSpace = async (tabId, space) => {
        const from = doc.querySelector(`#tabs .tab[data-tab="${tabId}"]`), to = doc.querySelector(`#spaces .space[data-space="${space}"]`);
        if (!from || !to) return false;
        const data = new page.DataTransfer(), box = to.getBoundingClientRect();
        const at = {bubbles: true, cancelable: true, clientX: box.left + 2, clientY: box.top + 2, dataTransfer: data};
        from.dispatchEvent(new page.DragEvent("dragstart", at));
        to.dispatchEvent(new page.DragEvent("dragover", at));
        to.dispatchEvent(new page.DragEvent("drop", at));
        from.dispatchEvent(new page.DragEvent("dragend", at));
        await wait(300);
        await page.browser.runtime.sendMessage(page.JSON.parse(JSON.stringify({type: "stats"})));
        return true;
      };
      const tabWith = async text => (await page.browser.tabs.query({})).find(t => t.url.includes(text))?.id;
    """

    def until(what, tries=60):
        """What `what()` returns, as soon as its "done" says so, tried for up to 15 s."""
        for _ in range(tries):
            r = what()
            if r.get("done"):
                break
            time.sleep(0.25)
        return r

    def registered_where(text):
        """Where it is, once it is in the record and has a copy in every window."""
        def seen():
            r = m.js(where_script, text)
            return {**r, "done": r["registered"] and len(r["copies"]) == r["windows"]}
        return until(seen)

    def set_rules(rules):
        sidebar_page(m, """await page.browser.runtime.sendMessage(page.JSON.parse(JSON.stringify({type: "settings:rules", rules: args[0]}))); return 1;""", rules)

    def open_in(address, space):
        m.js(H + """main().gBrowser.addTrustedTab(args[0], {userContextId: Number(args[1].split("-").pop()), inBackground: true}); return 1;""", address, space)

    def select_tab(text):
        m.js(H + """const w = main(); w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes(args[0])); await wait(400); return 1;""", text)

    def in_page(text, script):
        """Run `script` in the web page whose address has this text."""
        into_page(m, text)
        reply = m.cmd("WebDriver:ExecuteScript", {"script": script, "args": []})
        m.chrome()
        return reply

    spaces = sidebar_page(m, """return {here: spaces().find(s => s.active).id, there: spaces().find(s => !s.active && s.id !== "firefox-container-4").id};""")
    here, there = spaces["here"], spaces["there"]

    # A rule for a site in this space; the tab moved by hand to another stays there.
    set_rules([{"url": "smoke-safe-rule", "space": here}])
    open_in("https://example.org/?smoke-safe-rule", here)
    r = registered_where("smoke-safe-rule")
    check("a tab that matches a rule for its own space stays there", r["at"] == [here], str(r))
    moved = sidebar_page(m, drop_on_space + """return await dropOnSpace(await tabWith("smoke-safe-rule"), args[0]);""", there)
    check("a tab can be dropped on a space", moved is True, str(moved))
    r = registered_where("smoke-safe-rule")
    check("a tab moved by hand is not sent back by a rule", r["at"] == [there] and set(r["copies"]) == {there}, str(r))
    time.sleep(1)
    r = m.js(where_script, "smoke-safe-rule")
    check("and it is still there a moment later, once", r["at"] == [there], str(r))
    set_rules([])

    # What a tab was goes with it: an unloaded one arrives unloaded, so nothing is asked of
    # the site in a space you are not looking at, and a muted one stays muted, so it cannot
    # play there out of sight. One line says where they went, and Undo brings them back.
    for part in ("smoke-safe-muted", "smoke-safe-asleep"):
        open_in(f"https://example.org/?{part}", here)
        registered_where(part)
    m.js(H + """const w = main(), byPart = p => w.gBrowser.tabs.find(t => url(t).includes(p));
      byPart("smoke-safe-muted").toggleMuteAudio(); w.gBrowser.discardBrowser(byPart("smoke-safe-asleep")); await wait(800); return 1;""")
    # A tab by the page it holds, or, a placeholder (an unloaded tab arrives as one, tabsync.js),
    # by the address its record keeps for it.
    state = """const state = async space => { const all = (await page.browser.storage.local.get("syncedTabs")).syncedTabs ?? {};
      const address = t => { const k = new URL(t.url).searchParams.get("key"); return t.url.startsWith(page.browser.runtime.getURL("")) && k ? all[k]?.url ?? "" : t.url; };
      return Object.fromEntries((await page.browser.tabs.query({cookieStoreId: space})).filter(t => /smoke-safe-(muted|asleep)/.test(address(t)))
        .map(t => [address(t).includes("muted") ? "muted" : "asleep", {muted: !!t.mutedInfo?.muted, unloaded: t.discarded, title: t.title}])); };"""
    r = sidebar_page(m, drop_on_space + state + """const ids = [await tabWith("smoke-safe-muted"), await tabWith("smoke-safe-asleep")];
      // Both in one move, as the menu and a drag of several selected tabs send it (tabactions.js).
      send({type: "tabAction", action: "space", tabIds: ids, space: args[0]});
      for (let i = 0; i < 50 && Object.keys(await state(args[0])).length < 2; i++) await wait(100);
      await wait(800);
      const out = {there: await state(args[0]), line: doc.querySelector("#note .text")?.textContent ?? null, undo: doc.querySelector("#note .act")?.textContent ?? null};
      doc.querySelector("#note .act")?.click();
      for (let i = 0; i < 50 && Object.keys(await state(args[1])).length < 2; i++) await wait(100);
      await wait(800);
      out.back = await state(args[1]);
      return out;""", there, here)
    check("a muted tab moved to another space stays muted, and an unloaded one arrives unloaded, with its title",
          r.get("there", {}).get("muted", {}).get("muted") and r["there"].get("asleep", {}).get("unloaded") and not (r["there"].get("asleep", {}).get("title") or "http").startswith(("http", "about:")), str(r))
    check("one line says where they went, with Undo", re.fullmatch(r"2 tabs moved to .+", r.get("line") or "") and r.get("undo") == "Undo", str(r))
    check("and Undo brings them back as they were", r.get("back", {}).get("muted", {}).get("muted") and r["back"].get("asleep", {}).get("unloaded"), str(r))
    # (Placeholders too, by their record's address: an unloaded one has no page to close.)
    m.js(H + """const all = (await storage("%s", ["syncedTabs"])).syncedTabs, address = (w, t) => { const k = key(w, t); return url(t) + " " + (k ? all[JSON.parse(k)]?.url ?? "" : ""); };
      for (const w of wins()) for (const t of w.gBrowser.tabs.filter(t => /smoke-safe-(muted|asleep)/.test(address(w, t)))) w.gBrowser.removeTab(t); await wait(1200); return 1;""" % EXT_ID)

    # The selected tab: it goes, and you stay in the space, on a tab that was there.
    open_in("https://example.org/?smoke-safe-selected", here)
    registered_where("smoke-safe-selected")
    select_tab("smoke-safe-selected")
    r = sidebar_page(m, drop_on_space + """const id = await tabWith("smoke-safe-selected"), dropped = await dropOnSpace(id, args[0]);
      const [on] = await page.browser.tabs.query({active: true, windowId: (await page.browser.windows.getCurrent()).id});
      return {dropped, on: on.cookieStoreId, gone: !doc.querySelector(`#tabs .tab[data-tab="${id}"]`), active: spaces().find(s => s.active).id};""", there)
    where = registered_where("smoke-safe-selected")
    check("the selected tab can be moved, and you stay in your space", r["dropped"] and r["on"] == here and r["active"] == here and where["at"] == [there] and not where["selected"], f"{r} {where}")

    # A page still loading has its new address, and the record follows when it has finished.
    open_in(m.pages + "/plain?smoke-safe-app", here)
    registered_where("smoke-safe-app")
    in_page("smoke-safe-app", """location.href = "/slow?smoke-safe-deeper"; return 1;""")

    def going():
        state = m.js(where_script, "smoke-safe-deeper")
        return {**state, "done": state["at"] == [here]}
    until(going)
    moved = sidebar_page(m, drop_on_space + """return await dropOnSpace(await tabWith("smoke-safe-deeper"), args[0]);""", there)

    def deeper():
        state = m.js(where_script, "smoke-safe-deeper")
        return {**state, "done": state["at"] == [there]}
    r = until(deeper)
    left = m.js(where_script, "smoke-safe-app")
    check("a page still loading, moved, takes its new address", moved is True and r["at"] == [there] and left["at"] == [], f"{moved} {r} {left}")

    # A space that is gone by the time of the move: nothing happens to the tab, selected or not.
    open_in("https://example.org/?smoke-safe-nowhere", here)
    registered_where("smoke-safe-nowhere")
    for selected in (False, True):
        if selected:
            select_tab("smoke-safe-nowhere")
        r = sidebar_page(m, drop_on_space + """const id = await tabWith("smoke-safe-nowhere"); send({type: "moveToSpace", tabId: id, space: "firefox-container-99"}); await wait(300);
          await page.browser.runtime.sendMessage(page.JSON.parse(JSON.stringify({type: "stats"})));
          const t = await page.browser.tabs.get(id); return {active: t.active, loaded: !t.discarded};""")
        where = m.js(where_script, "smoke-safe-nowhere")
        check(f"a move to a space that is gone leaves the tab {'selected' if selected else 'where it is'}, loaded", r == {"active": selected, "loaded": True} and where["at"] == [here], f"{r} {where}")

    # A row that is a placeholder: its page is loaded and selected in the other window.
    if m.js(H + """return wins().length;""") < 2:
        print("SKIP  a placeholder with its page in the other window (needs alone_second_window)", flush=True)
    else:
        open_in("https://example.org/?smoke-safe-away", here)
        registered_where("smoke-safe-away")
        away = sidebar_page(m, """const here = (await page.browser.windows.getCurrent()).id, all = (await page.browser.tabs.query({})).filter(t => t.url.includes("smoke-safe-away") || t.title.includes("smoke-safe-away"));
          const windows = await page.browser.windows.getAll({windowTypes: ["normal"]}), other = windows.find(w => w.id !== here);
          const keys = await Promise.all((await page.browser.tabs.query({windowId: other.id})).map(async t => [t.id, await page.browser.sessions.getTabValue(t.id, "syncKey")]));
          const live = all[0], key = await page.browser.sessions.getTabValue(live.id, "syncKey");
          return {here, other: other.id, ghost: keys.find(([, k]) => k === key)[0], live: live.id, key};""")
        m.js(H + """const w = wins().find(x => x.gBrowser.tabs.some(t => key(x, t) === JSON.stringify(args[0]) && !url(t).includes("smoke-safe-away")));
          w.focus(); await wait(300);
          w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => key(w, t) === JSON.stringify(args[0]));
          for (let i = 0; i < 40 && !url(w.gBrowser.selectedTab).includes("smoke-safe-away"); i++) await wait(100);
          main().focus(); await wait(300); return 1;""", away["key"])
        r = sidebar_page(m, """const rep = (await page.browser.tabs.query({windowId: args[0]})), keys = await Promise.all(rep.map(t => page.browser.sessions.getTabValue(t.id, "syncKey")));
          const row = rep[keys.indexOf(args[1])], real = (await page.browser.tabs.query({})).find(t => t.url.includes("smoke-safe-away"));
          send({type: "moveToSpace", tabId: row.id, space: args[2]}); await wait(300);
          await page.browser.runtime.sendMessage(page.JSON.parse(JSON.stringify({type: "stats"})));
          return {rowUnloaded: row.discarded || row.url.includes("ghost.html"), realElsewhere: real.windowId !== args[0], realSelected: real.active};""", away["here"], away["key"], there)
        where = registered_where("smoke-safe-away")
        selected_there = m.js(H + """const w = wins().find(x => x !== main()); return w.gBrowser.selectedTab.userContextId ? "firefox-container-" + w.gBrowser.selectedTab.userContextId : "firefox-default";""")
        check("a placeholder moves, with its page selected in the other window: once, and that window stays in its space", r["rowUnloaded"] and r["realElsewhere"] and r["realSelected"] and where["at"] == [there] and set(where["copies"]) == {there} and selected_there == here, f"{r} {where} {selected_there}")

    # Tabs Firefox brings back: not sent away by a rule, for they are not new.
    set_rules([{"url": "smoke-safe-back", "space": here}])
    open_in("https://example.org/?smoke-safe-back", there)  # a tab opened with an address goes by the rule, so to `here`
    r = registered_where("smoke-safe-back")
    check("a new tab goes by the rule", r["at"] == [here], str(r))
    sidebar_page(m, drop_on_space + """return await dropOnSpace(await tabWith("smoke-safe-back"), args[0]);""", there)
    r = registered_where("smoke-safe-back")
    check("(moved by hand, it stays)", r["at"] == [there], str(r))
    # Closed for good, then ⌘⇧T: Firefox's own undo, with the tab's own values.
    m.js(H + """const w = main(), t = w.gBrowser.tabs.find(x => url(x).includes("smoke-safe-back")); w.gBrowser.removeTab(t); await wait(1500); return 1;""")
    gone = m.js(where_script, "smoke-safe-back")
    m.js(H + """main().SessionStore.undoCloseTab(main(), 0); await wait(3000); return 1;""")
    r = registered_where("smoke-safe-back")
    check("a tab brought back with ⌘⇧T is not sent away by a rule", gone["at"] == [] and r["at"] == [there], f"{gone} {r}")
    # In a folder, closed while loaded, and selected again: its placeholder loads itself.
    folder = sidebar_page(m, """send({type: "newFolder", space: args[0], name: "smoke-safe-folder"}); await wait(500);
      const all = (await page.browser.storage.local.get("syncedTabs")).syncedTabs; return Object.entries(all).find(([, e]) => e.name === "smoke-safe-folder")?.[0];""", there)
    sidebar_page(m, """const id = (await page.browser.tabs.query({})).find(t => t.url.includes("smoke-safe-back")).id;
      send({type: "moveTab", tabId: id, before: null, folder: args[0]}); await wait(500); return 1;""", folder)
    m.js(H + """const w = main(), t = w.gBrowser.tabs.find(x => url(x).includes("smoke-safe-back")); w.gBrowser.removeTab(t); await wait(1500); return 1;""")
    unloaded = sidebar_page(m, """const all = (await page.browser.storage.local.get("syncedTabs")).syncedTabs, k = Object.keys(all).find(k => all[k].url?.includes("smoke-safe-back"));
      const windowId = (await page.browser.windows.getCurrent()).id, tabs = await page.browser.tabs.query({windowId});
      const keys = await Promise.all(tabs.map(t => page.browser.sessions.getTabValue(t.id, "syncKey")));
      const t = tabs[keys.indexOf(k)]; return t ? {id: t.id, placeholder: t.url.includes("ghost.html")} : null;""")
    r = sidebar_page(m, """await page.browser.tabs.update(args[0], {active: true}); for (let i = 0; i < 60; i++) { const t = await page.browser.tabs.get(args[0]); if (t.url.includes("smoke-safe-back")) break; await wait(100); }
      await wait(600); const t = await page.browser.tabs.get(args[0]); return {at: t.cookieStoreId, url: t.url};""", unloaded["id"])
    where = m.js(where_script, "smoke-safe-back")
    check("a saved tab's placeholder that loads itself is not sent away by a rule", unloaded["placeholder"] and r["at"] == there and "smoke-safe-back" in r["url"] and where["at"] == [there], f"{unloaded} {r} {where}")
    sidebar_page(m, """send({type: "deleteFolder", key: args[0]}); await wait(300); const id = (await page.browser.tabs.query({})).find(t => t.url.includes("smoke-safe-back")).id; send({type: "close", tabId: id}); await wait(500);
      send({type: "space", space: args[1]}); for (let i = 0; i < 40 && spaces().find(s => s.active)?.id !== args[1]; i++) await wait(100); return 1;""", folder, here)
    set_rules([])

    # A page with unsaved input stays, unasked: first in the background, then selected.
    open_in(m.pages + "/unsaved?smoke-safe-input", here)
    r = registered_where("smoke-safe-input")
    check("a page with unsaved input is here to begin with", r["at"] == [here] and r["loaded"], str(r))
    in_page("smoke-safe-input", """document.querySelector("input").value = "typed here"; return 1;""")
    r = sidebar_page(m, drop_on_space + """const dropped = await dropOnSpace(await tabWith("smoke-safe-input"), args[0]); await wait(200);
      return {dropped, line: doc.querySelector("#note")?.textContent ?? null};""", there)
    where = m.js(where_script, "smoke-safe-input")
    check("a page with unsaved input stays where it is, and stays loaded", r["dropped"] and where["at"] == [here] and where["loaded"], f"{r} {where}")
    if r["line"] is None:  # quiet.js draws the line; what is said is checked on the fake Firefox
        print("SKIP  the line about the page that stayed (no line in this build)", flush=True)
    else:
        check("the line says the page stayed", "unsaved input" in r["line"], str(r))
    select_tab("smoke-safe-input")
    r = sidebar_page(m, drop_on_space + """const id = await tabWith("smoke-safe-input"); const dropped = await dropOnSpace(id, args[0]);
      const on = await page.browser.tabs.get(id); return {dropped, selected: on.active, loaded: !on.discarded};""", there)
    where = m.js(where_script, "smoke-safe-input")
    check("selected, it stays too, and you stay on it", r == {"dropped": True, "selected": True, "loaded": True} and where["at"] == [here], f"{r} {where}")
    typed = in_page("smoke-safe-input", """return document.querySelector("input").value;""")
    check("and what was typed is still there", typed == "typed here", str(typed))
    # Closing it for real would ask: this check must leave no question open for what follows.
    m.js(H + """const w = main(), t = w.gBrowser.tabs.find(x => url(x).includes("smoke-safe-input"));
      w.gBrowser.selectedTab = w.gBrowser.tabs.find(x => !x.pinned && x !== t && x.userContextId === t.userContextId && !x.hidden);
      w.gBrowser.removeTab(t, {skipPermitUnload: true}); await wait(800); return 1;""")

    # The last tab of a space, selected: it can only step aside onto a new tab there, which goes
    # again if the page refuses, and stays if it does not, so that you stay in that space.
    alone_there = sidebar_page(m, """return (await page.browser.contextualIdentities.create(page.JSON.parse(JSON.stringify({name: "smoke-last", color: "orange", icon: "circle"})))).cookieStoreId;""")
    open_in(m.pages + "/unsaved?smoke-last-input", alone_there)
    registered_where("smoke-last-input")
    sidebar_page(m, """send({type: "space", space: args[0]}); for (let i = 0; i < 40 && spaces().find(s => s.active)?.id !== args[0]; i++) await wait(100); return 1;""", alone_there)
    select_tab("smoke-last-input")
    last_state = """const windowId = (await page.browser.windows.getCurrent()).id, [on] = await page.browser.tabs.query({active: true, windowId});
      return {on: on.url, space: on.cookieStoreId, active: spaces().find(s => s.active)?.id, inSpace: (await page.browser.tabs.query({cookieStoreId: args[0], windowId})).length};"""
    # (The list is drawn for the page's own window, whose rows are now this space's.)
    sidebar_page(m, drop_on_space + """return await dropOnSpace(await tabWith("smoke-last-input"), args[1]);""", alone_there, here)
    r = sidebar_page(m, last_state, alone_there)
    check("the last tab of a space with unsaved input stays selected, and nothing is left beside it", "smoke-last-input" in r["on"] and r["space"] == alone_there and r["active"] == alone_there and r["inSpace"] == 1, str(r))
    m.js(H + """const w = main(), t = w.gBrowser.tabs.find(x => url(x).includes("smoke-last-input")); w.gBrowser.addTrustedTab(args[0] + "/plain?smoke-last-plain", {userContextId: t.userContextId, inBackground: true}); await wait(600);
      w.gBrowser.selectedTab = w.gBrowser.tabs.find(x => url(x).includes("smoke-last-plain")); w.gBrowser.removeTab(t, {skipPermitUnload: true}); await wait(800); return 1;""", m.pages)
    registered_where("smoke-last-plain")
    select_tab("smoke-last-plain")
    sidebar_page(m, drop_on_space + """return await dropOnSpace(await tabWith("smoke-last-plain"), args[1]);""", alone_there, here)
    where = registered_where("smoke-last-plain")
    r = sidebar_page(m, last_state, alone_there)
    check("the last tab of a space moves, and you stay in that space, on a new tab", where["at"] == [here] and r["space"] == alone_there and r["active"] == alone_there and r["inSpace"] == 1 and "smoke-last" not in r["on"], f"{where} {r}")
    sidebar_page(m, """send({type: "space", space: args[0]}); for (let i = 0; i < 40 && spaces().find(s => s.active)?.id !== args[0]; i++) await wait(100);
      await page.browser.contextualIdentities.remove(args[1]); await wait(600); return 1;""", here, alone_there)

    # A rule pointing at a space that does not exist: the link stays, and you see which rule.
    set_rules([{"url": "smoke-safe-dead", "space": "firefox-container-99"}])
    open_in("https://example.org/?smoke-safe-dead", here)
    r = registered_where("smoke-safe-dead")
    shown = sidebar_page(m, """const p = doc.getElementById("problem"); for (let i = 0; i < 30 && p.hidden; i++) await wait(100); return p.hidden ? null : p.textContent;""")
    check("a rule whose space is gone leaves the tab where it is", r["at"] == [here], str(r))
    check("and the sidebar says which rule", "smoke-safe-dead" in (shown or ""), str(shown))
    set_rules([])
    gone = sidebar_page(m, """const p = doc.getElementById("problem"); for (let i = 0; i < 30 && !p.hidden; i++) await wait(100); return p.hidden;""")
    check("and it says so no longer once the rule is changed", gone is True, str(gone))
    # In the settings such a rule shows as it is, and saving another rule does not send it elsewhere.
    set_rules([{"url": "smoke-safe-dead", "space": "firefox-container-99"}])
    r = ext_page(m, "/settings/settings.html?safe-moves", """const select = () => doc.querySelector("#rules select"); for (let i = 0; i < 40 && !select(); i++) await wait(100);
      const shown = select().selectedOptions[0].textContent;
      doc.querySelector("#rules input").dispatchEvent(new page.Event("change")); await wait(300);
      return {shown, saved: (await page.browser.runtime.sendMessage(page.JSON.parse(JSON.stringify({type: "settings:get"})))).rules};""")
    check("the settings show a rule whose space is gone as gone, and saving keeps it", "gone" in r["shown"] and r["saved"] == [{"url": "smoke-safe-dead", "space": "firefox-container-99"}], str(r))
    m.chrome()
    m.js(H + """await removeWhere((w, t) => url(t).includes("settings.html?safe-moves")); return 1;""")
    set_rules([])

    # A removed container takes its rules, folders and saved tabs along.
    made = sidebar_page(m, """const c = await page.browser.contextualIdentities.create(page.JSON.parse(JSON.stringify({name: "smoke-gone", color: "blue", icon: "circle"})));
      await wait(300); return c.cookieStoreId;""")
    keep = {"url": "smoke-kept-rule", "space": here}
    set_rules([{"url": "smoke-gone-rule", "space": made}, keep])
    open_in("https://example.org/?smoke-gone-saved", made)
    open_in("https://example.org/?smoke-gone-plain", made)
    registered_where("smoke-gone-saved")
    registered_where("smoke-gone-plain")
    folder = sidebar_page(m, """send({type: "newFolder", space: args[0], name: "smoke-gone-folder"}); await wait(600);
      const all = (await page.browser.storage.local.get("syncedTabs")).syncedTabs; return Object.entries(all).find(([, e]) => e.name === "smoke-gone-folder")?.[0];""", made)
    sidebar_page(m, """const id = (await page.browser.tabs.query({})).find(t => t.url.includes("smoke-gone-saved")).id;
      send({type: "moveTab", tabId: id, before: null, folder: args[0]}); await wait(600); return 1;""", folder)
    sidebar_page(m, """await page.browser.contextualIdentities.remove(args[0]); await wait(200); return 1;""", made)

    def after_removal():
        state = m.js(H + """const all = await storage("%s", ["syncedTabs", "rules"]);
          return {tabs: wins().flatMap(w => w.gBrowser.tabs).filter(t => ctxOf(t) === args[0]).map(t => url(t)), rules: all.rules, record: Object.values(all.syncedTabs).filter(e => e.cookieStoreId === args[0]).map(e => e.name || e.url)};""" % EXT_ID, made)
        return {**state, "done": not state["tabs"] and not state["record"] and len(state["rules"]) == 1}
    r = until(after_removal)
    check("a removed container's rules, folders and tabs go with it, and other rules stay", r["done"] and r["rules"] == [keep], str(r))
    set_rules([])

    # The space you are in is removed: you land in another one, with its tabs shown.
    made = sidebar_page(m, """return (await page.browser.contextualIdentities.create(page.JSON.parse(JSON.stringify({name: "smoke-gone-here", color: "red", icon: "circle"})))).cookieStoreId;""")
    open_in("https://example.org/?smoke-gone-here-tab", made)
    registered_where("smoke-gone-here-tab")
    r = sidebar_page(m, """send({type: "space", space: args[0]}); for (let i = 0; i < 40 && spaces().find(s => s.active)?.id !== args[0]; i++) await wait(100);
      return spaces().find(s => s.active)?.id;""", made)
    check("a new space can be gone into", r == made, str(r))
    sidebar_page(m, """await page.browser.contextualIdentities.remove(args[0]); return 1;""", made)

    def fell_back():
        state = sidebar_page(m, """const windowId = (await page.browser.windows.getCurrent()).id, active = spaces().find(s => s.active)?.id;
          const [on] = await page.browser.tabs.query({active: true, windowId}), tabs = await page.browser.tabs.query({windowId, pinned: false});
          return {active, on: on.cookieStoreId, onUrl: on.url, left: (await page.browser.tabs.query({cookieStoreId: args[0]})).length,
                  hiddenHere: tabs.filter(t => t.cookieStoreId === active && t.hidden).length,
                  shownElsewhere: tabs.filter(t => t.cookieStoreId !== active && t.cookieStoreId !== "firefox-default" && !t.hidden && !t.active).length};""", made)
        return {**state, "done": state["left"] == 0 and state["active"] not in (None, made) and state["on"] == state["active"] and state["hiddenHere"] == 0 and state["shownElsewhere"] == 0}
    r = until(fell_back)
    check("the space you are in removed: you are in another space, on one of its tabs, with only its tabs shown", r["done"], str(r))
    sidebar_page(m, """send({type: "space", space: args[0]}); for (let i = 0; i < 40 && spaces().find(s => s.active)?.id !== args[0]; i++) await wait(100); return 1;""", here)

    # The same from Firefox's settings page, as that page does it: it closes the tabs, then removes
    # the container. There the selected tab is in no space, and stays selected.
    made = sidebar_page(m, """return (await page.browser.contextualIdentities.create(page.JSON.parse(JSON.stringify({name: "smoke-gone-settings", color: "green", icon: "circle"})))).cookieStoreId;""")
    open_in("https://example.org/?smoke-gone-settings-tab", made)
    registered_where("smoke-gone-settings-tab")
    r = sidebar_page(m, """send({type: "space", space: args[0]}); for (let i = 0; i < 40 && spaces().find(s => s.active)?.id !== args[0]; i++) await wait(100);
      return spaces().find(s => s.active)?.id;""", made)
    m.js(H + """const w = main(); w.gBrowser.selectedTab = w.gBrowser.addTrustedTab("about:preferences#containers", {}); await wait(800);
      const svc = w.ContextualIdentityService ?? ChromeUtils.importESModule("moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs").ContextualIdentityService;
      const id = Number(args[0].split("-").pop());
      await svc.closeContainerTabs(id); svc.remove(id); await wait(600); return 1;""", made)

    def left_settings():
        state = sidebar_page(m, """const windowId = (await page.browser.windows.getCurrent()).id, active = spaces().find(s => s.active)?.id;
          const [on] = await page.browser.tabs.query({active: true, windowId}), tabs = await page.browser.tabs.query({windowId, pinned: false});
          return {active, on: on.url, left: (await page.browser.tabs.query({cookieStoreId: args[0]})).length, record: Object.values((await page.browser.storage.local.get("syncedTabs")).syncedTabs).filter(e => e.cookieStoreId === args[0]).length,
                  hiddenHere: tabs.filter(t => t.cookieStoreId === active && t.hidden).length};""", made)
        return {**state, "done": state["left"] == 0 and state["record"] == 0 and state["active"] not in (None, made) and state["hiddenHere"] == 0}
    r = until(left_settings)
    check("a space removed from Firefox's settings page: the page stays selected, and the window is in another space, its tabs shown", r["done"] and r["on"].startswith("about:preferences"), str(r))
    m.js(H + """await removeWhere((w, t) => url(t).startsWith("about:preferences")); return 1;""")
    sidebar_page(m, """send({type: "space", space: args[0]}); for (let i = 0; i < 40 && spaces().find(s => s.active)?.id !== args[0]; i++) await wait(100); return 1;""", here)
    no_problems(m, "after moves and a removed container")

    # The background part starts again: the sidebar's connection is dead, and it comes back.
    views = """page.browser.extension.getViews({type: "sidebar"})"""
    before = sidebar_page(m, """for (const v of %s) v.document.documentElement.dataset.old = "1";
      doc.documentElement.dataset.old = "1";
      const bg = page.browser.extension.getBackgroundPage(); setTimeout(() => bg.location.reload(), 100);
      return {rows: rows().length, reals: %s.map(v => v.document.querySelectorAll("#tabs .tab").length)};""" % (views, views))
    check("before: the sidebar has its list, in its tab and in the window", before["rows"] > 0 and any(before["reals"]), str(before))
    time.sleep(0.5)

    def back():
        state = sidebar_page(m, """return {old: doc.documentElement.dataset.old ?? null, rows: rows().length,
          reals: %s.map(v => ({old: v.document.documentElement.dataset.old ?? null, rows: v.document.querySelectorAll("#tabs .tab").length}))};""" % views)
        # (A window's own sidebar can rightly be empty: its space may have no tabs.)
        return {**state, "done": state["old"] is None and state["rows"] > 0 and all(v["old"] is None for v in state["reals"]) and any(v["rows"] for v in state["reals"])}
    r = until(back)
    check("after the background part starts again, the sidebar has connected anew and shows its list", r["done"], str(r))
    # In one piece again before the next group: the tabs known again, and the queue done with that.
    until(lambda: {"done": sidebar_page(m, """return (await page.browser.runtime.sendMessage(page.JSON.parse(JSON.stringify({type: "stats"})))).sizes.syncKeyByTab > 0;""") is True})


def alone_archived(m):
    # Tidier's own list of what was closed: reached from the list's menu, on the real
    # sidebar, with Firefox's own mouse where it matters (the × shows on hover only).
    # Every group before has closed tabs, which are all in it by now: it starts empty here.
    sidebar_page(m, """const ask = msg => page.browser.runtime.sendMessage(page.JSON.parse(JSON.stringify(msg)));
      for (const {space, url} of await ask({type: "archivedTabs"})) await ask({type: "forgetArchived", item: {space, url}});
      return 1;""")
    settled = """const settled = async (test, ms = 15000) => { const t0 = Date.now(); for (;;) { const v = await test(); if (v || Date.now() - t0 > ms) return v; await wait(50); } };"""
    opened = m.js(H + settled + """if (other()) return false;
      const a = main(), want = a.gBrowser.tabs.filter(t => !t.pinned && role(a, t)).length, w = a.OpenBrowserWindow(); w.__smoke = true;
      await settled(() => w.gBrowser && w.gBrowser.tabs.filter(t => !t.pinned && role(w, t)).length >= want, 20000);
      a.focus(); await wait(500); return true;""")
    space = sidebar_page(m, "return spaces().find(s => s.active).id;")
    ctx = int(space.rsplit("-", 1)[1])
    TITLE = "A page with a title"
    s = m.js(H + settled + """const w = main(), [pages, ctx] = args, away = ctx === 1 ? 2 : 1;
      const open = (q, c) => w.gBrowser.addTrustedTab(pages + "/with-title?smoke-archived-" + q, {userContextId: c, inBackground: true});
      const made = [open("forget", ctx), open("back-slow", ctx), open("away", away)];
      await settled(() => made.every(t => key(w, t) && t.label === %s && other().gBrowser.tabs.some(x => key(other(), x) === key(w, t))));
      await wait(500);
      return {keys: made.map(t => JSON.parse(key(w, t))), urls: made.map(url), away: "firefox-container-" + away, labels: made.map(t => t.label)};""" % json.dumps(TITLE), m.pages, ctx)
    forget_url, back_url, away_url = s["urls"]

    now = int(time.time() * 1000)
    late = extension_message(m, {"type": "archiveNow", "now": now + 13 * 3600 * 1000, "keys": s["keys"], "explain": True})
    check("archiving closes tabs unused for longer than the limit (for the list)", sorted(late.get("archived", [])) == sorted(s["urls"]), str(late))

    # The sidebar page in front, as a sidebar always is: a page behind others is not drawn.
    m.js(H + """const w = main(); w.focus(); w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes("/sidebar/sidebar.html")); await wait(500); return 1;""")

    def mouse(x, y, click=True, double=False):
        """Firefox's own mouse, on the sidebar page in front. A double click has the slide's time between its clicks."""
        into_page(m, "/sidebar/sidebar.html")  # not through every tab: that loads each unloaded one
        acts = [{"type": "pointerMove", "x": round(x), "y": round(y), "duration": 0}]
        press = [{"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}]
        if click:
            acts += press
        if double:
            acts += [{"type": "pause", "duration": 350}] + press
        m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"}, "actions": acts}]})
        m.cmd("WebDriver:ReleaseActions")
        m.chrome()

    box = settled + """const box = doc.getElementById("archived"), open = () => box.classList.contains("open");
      const rowsHere = () => [...box.querySelectorAll(".rows .row")];
      const middle = e => { const r = e.getBoundingClientRect(); return {x: r.left + r.width / 2, y: r.top + r.height / 2}; };
      const describe = r => ({title: r.querySelector(".title").textContent, age: r.querySelector(".age").textContent, tip: r.title});
      const key = k => page.dispatchEvent(new page.KeyboardEvent("keydown", {key: k, bubbles: true, cancelable: true}));"""

    # The list's menu opens the view, over the list, and the list stays as it is.
    r = sidebar_page(m, box + """
      const list = doc.getElementById("tabs"), around = list.getBoundingClientRect();
      const before = rows();
      list.dispatchEvent(new page.MouseEvent("contextmenu", {bubbles: true, cancelable: true, button: 2, clientX: around.left + 8, clientY: around.bottom - 4}));
      const items = [...doc.querySelectorAll("#menu .item")], labels = items.map(b => b.textContent);
      items.find(b => b.textContent === "Archived tabs").click();
      await settled(() => open() && rowsHere().length);
      await settled(() => box.getBoundingClientRect().left === 0);
      const r = box.getBoundingClientRect(), actions = doc.getElementById("actions").getBoundingClientRect(), at = middle(rowsHere()[0]);
      return {labels, rows: rowsHere().map(describe), under: doc.elementFromPoint(at.x, at.y) === rowsHere()[0] || rowsHere()[0].contains(doc.elementFromPoint(at.x, at.y)), covers: r.top === actions.top && r.bottom === around.bottom,
              list: before.length === rows().length, back: box.querySelector(".back").textContent};""")
    check("the list's menu has Archived tabs", "Archived tabs" in r.get("labels", []), str(r))
    check("the view shows this space's tabs, newest first, each with its title and age", [x["tip"].split("\n")[1] for x in r.get("rows", [])] == [back_url, forget_url]
          and all(x["title"] == TITLE and re.fullmatch(r"now|\d+ min", x["age"]) for x in r["rows"]), str(r))
    check("the view lies over the list, on top, and the list is still there under it", r.get("under") and r.get("covers") and r.get("list"), str(r))

    # Esc goes back; the keys stay out of the list under it.
    r = sidebar_page(m, box + """
      const under = doc.querySelector("#tabs .cursor");  // the list keeps its own, if an earlier check left one
      key("ArrowDown");
      const cursor = rowsHere()[0].classList.contains("cursor"), moved = doc.querySelector("#tabs .cursor") !== under;
      key("Escape");
      const closed = !open();
      page.openArchived();
      await settled(() => open());
      await settled(() => box.getBoundingClientRect().left === 0);
      return {cursor, moved, closed, back: middle(box.querySelector(".back"))};""")
    check("the arrow keys move in the view, not in the list under it", r.get("cursor") and r.get("moved") is False, str(r))
    check("Esc goes back to the list", r.get("closed"), str(r))
    mouse(r["back"]["x"], r["back"]["y"])
    r = sidebar_page(m, box + """await settled(() => !open()); return {open: open()};""")
    check("the back row goes back to the list", r["open"] is False, str(r))

    # The × shows on hover, and forgets. Two rows, one for each.
    r = sidebar_page(m, box + """
      page.openArchived();
      await settled(() => open() && rowsHere().length === 2);
      await settled(() => box.getBoundingClientRect().left === 0);
      const row = rowsHere().find(x => x.title.includes("smoke-archived-forget"));
      return {x: row.getBoundingClientRect().right - 16, y: middle(row).y, shows: page.getComputedStyle(row.querySelector(".close")).visibility};""")
    check("the × of a row does not show without the pointer on it", r.get("shows") == "hidden", str(r))
    mouse(r["x"], r["y"], click=False)
    h = sidebar_page(m, box + """const row = rowsHere().find(x => x.title.includes("smoke-archived-forget"));
      return {close: page.getComputedStyle(row.querySelector(".close")).visibility, age: page.getComputedStyle(row.querySelector(".age")).visibility};""")
    check("with the pointer on it, the × takes the age's place", h == {"close": "visible", "age": "hidden"}, str(h))
    mouse(r["x"], r["y"])
    r = sidebar_page(m, box + """await settled(() => rowsHere().length === 1);
      return {tips: rowsHere().map(x => x.title), open: open(), reply: await page.browser.runtime.sendMessage({type: "archivedTabs", space: args[0]}).then(l => JSON.parse(JSON.stringify(l)))};""", space)
    check("the × forgets it, and the view stays", r["open"] and len(r["tips"]) == 1 and [x["url"] for x in r["reply"]] == [back_url], str(r))

    # A tab you close while it is open comes in by itself, marked as closed, not archived.
    closing = m.js(H + settled + """const w = main(), t = w.gBrowser.addTrustedTab(args[0] + "/with-title?smoke-archived-closing", {userContextId: args[1], inBackground: true});
      await settled(() => key(w, t) && t.label === %s && other().gBrowser.tabs.some(x => key(other(), x) === key(w, t)));
      const u = url(t); w.gBrowser.removeTab(t); return u;""" % json.dumps(TITLE), m.pages, ctx)
    r = sidebar_page(m, box + """await settled(() => rowsHere().length === 2);
      return {tip: rowsHere()[0].title, older: rowsHere()[1].title};""")
    check("a tab you close while the view is open comes in by itself, as closed", closing in r.get("tip", "") and "\nClosed " in r["tip"] and "\nArchived " in r.get("older", ""), str(r))
    # ⌘⇧T brings it back: it leaves the list by itself. (Firefox's own way back, with its history.)
    m.js(H + settled + """const w = main(), page = w.gBrowser.selectedTab; w.SessionStore.undoCloseTab(w, 0);
      await settled(() => w.gBrowser.tabs.some(t => url(t) === args[0] && key(w, t)));
      w.gBrowser.selectedTab = page; await wait(300); return 1;""", closing)
    r = sidebar_page(m, box + """await settled(() => rowsHere().length === 1); return {tips: rowsHere().map(x => x.title), open: open()};""")
    check("a tab that comes back by ⌘⇧T leaves the list", r["open"] and len(r["tips"]) == 1 and closing not in r["tips"][0], str(r))

    # A click outside the view closes it, and still does what it does.
    r = sidebar_page(m, box + """
      const dot = doc.querySelector("#spaces .space:not(.active)"), to = dot.dataset.space;
      dot.click();
      const closed = !open();
      await settled(() => spaces().find(s => s.active).id === to);
      const then = spaces().find(s => s.active).id;
      send({type: "space", space: args[0]});
      await settled(() => spaces().find(s => s.active).id === args[0]);
      return {closed, went: then === to};""", space)
    check("a click on a space closes the view, and goes there", r.get("closed") and r.get("went"), str(r))
    r = sidebar_page(m, box + """page.openArchived(); await settled(() => open() && rowsHere().length); await settled(() => box.getBoundingClientRect().left === 0); return rowsHere().length;""")

    # A click brings it back: with its title from the very first view, long before its page
    # has answered, selected, in its space, also with a rule for its address: it is coming
    # back to where it was, not a new tab.
    extension_message(m, {"type": "settings:rules", "rules": [{"url": "smoke-archived-back", "space": s["away"]}]})
    # (Firefox can find a title in its history by itself; the list must not depend on that.)
    m.js(H + """await main().PlacesUtils.history.remove(args[0]); return 1;""", back_url)
    r = sidebar_page(m, box + """
      const seen = [];
      port.onMessage.addListener(v => { for (const t of v.tabs) if (!seen.some(x => x.id === t.id)) seen.push({id: t.id, title: t.title}); });
      const known = new Set(rows()), n0 = plainTabs().length;
      await wait(200);
      seen.length = 0;
      const had = new Set([...doc.querySelectorAll("#tabs > .tab")].map(x => Number(x.dataset.tab)));
      rowsHere()[0].click();
      const closed = !open();
      await settled(() => plainTabs().length === n0 + 1);
      await settled(() => doc.querySelector("#tabs > .tab.active"));
      const row = doc.querySelector("#tabs > .tab.active");
      const fresh = seen.filter(x => !had.has(x.id));
      const title = row.querySelector(".title").textContent;
      await wait(1000);
      return {closed, title, later: row.querySelector(".title").textContent, first: fresh.map(x => x.title),
              list: await page.browser.runtime.sendMessage({type: "archivedTabs", space: args[0]}).then(l => JSON.parse(JSON.stringify(l)))};""", space)
    check("a click on a row closes the view, and the tab comes back selected, with its title at once", r.get("closed") and r.get("title") == TITLE and r.get("later") == TITLE and r.get("first") and r["first"][0] == TITLE, str(r))
    check("it leaves the list", r.get("list") == [], str(r))
    t = m.js(H + settled + """const u = args[0];
      await settled(() => wins().every(w => w.gBrowser.tabs.some(t => key(w, t) && (url(t) === u || value(w, t, "syncRole") === "ghost" && String(t.label) === %s))));
      await settled(() => other().gBrowser.tabs.some(t => t.label === %s && !t.linkedPanel));
      await wait(1500);
      const a = main(), here = a.gBrowser.tabs.find(t => url(t) === u), k = here && key(a, here);
      const there = other().gBrowser.tabs.filter(t => key(other(), t) === k);
      const all = (await storage("%s", ["syncedTabs"])).syncedTabs;
      return {selected: here?.selected, ctx: here?.userContextId, role: here && role(a, here), there: there.map(t => ({role: role(other(), t), ctx: t.userContextId, label: t.label, unloaded: !t.linkedPanel})), record: k && all[JSON.parse(k)]?.title};""" % (json.dumps(TITLE), json.dumps(TITLE), EXT_ID), back_url)
    check("it opens in its space, live here and a placeholder in the second window, with its title",
          t["selected"] and t["ctx"] == ctx and t["role"] == "live" and t["record"] == TITLE and t["there"] == [{"role": "ghost", "ctx": ctx, "label": TITLE, "unloaded": True}], str(t))

    extension_message(m, {"type": "settings:rules", "rules": []})

    # Another space's list can be looked at without going there; opening a row goes there.
    r = sidebar_page(m, box + """
      page.openArchived(args[0]);
      await settled(() => open() && rowsHere().length);
      const shown = rowsHere().map(x => x.title.split("\\n")[1]), back = box.querySelector(".back").textContent, stayed = spaces().find(s => s.active).id;
      rowsHere()[0].click();
      await settled(() => spaces().find(s => s.active).id === args[0]);
      return {shown, back, stayed, then: spaces().find(s => s.active).id};""", s["away"])
    check("another space's list shows without going there", r.get("shown") == [away_url] and r.get("stayed") == space and "Archived tabs in" in r.get("back", ""), str(r))
    check("opening a row from it goes to that space", r.get("then") == s["away"], str(r))
    t = m.js(H + settled + """const u = args[0], ctx = args[1];
      await settled(() => main().gBrowser.selectedTab.userContextId === ctx && url(main().gBrowser.selectedTab) === u);
      const t = main().gBrowser.selectedTab; return {ctx: t.userContextId, url: url(t)};""", away_url, int(s["away"].rsplit("-", 1)[1]))
    check("that tab is selected, in its own container", t == {"ctx": int(s["away"].rsplit("-", 1)[1]), "url": away_url}, str(t))
    sidebar_page(m, """send({type: "space", space: args[0]}); await wait(1000); return 1;""", space)

    # A tab whose real page was in a window you closed: only a placeholder is left, and the list has its real address.
    h = m.js(H + settled + """const a = main(), [pages, ctx] = args, w = a.OpenBrowserWindow(); w.__extra = true;
      await settled(() => w.gBrowser && w.gBrowser.tabs.some(t => role(w, t)));
      const t = w.gBrowser.addTrustedTab(pages + "/with-title?smoke-archived-held", {userContextId: ctx, inBackground: true});
      await settled(() => key(w, t) && t.label === %s && wins().every(x => x.gBrowser.tabs.some(y => key(x, y) === key(w, t))));
      await wait(500);
      const k = key(w, t), u = url(t);
      await close(w);
      await settled(() => wins().some(x => x.gBrowser.tabs.some(y => key(x, y) === k && role(x, y) === "live")));
      return {key: JSON.parse(k), url: u, live: wins().flatMap(x => x.gBrowser.tabs.filter(y => key(x, y) === k && role(x, y) === "live").map(url))};""" % json.dumps(TITLE), m.pages, ctx)
    check("a closed window's tab is live as a placeholder elsewhere", len(h["live"]) == 1 and "ghost.html" in h["live"][0], str(h))
    now = int(time.time() * 1000)
    first = extension_message(m, {"type": "archiveNow", "now": now, "keys": [h["key"]], "explain": True})
    check("a placeholder's time starts when it became one", str(first.get("kept", {}).get(h["key"])).startswith("used"), str(first))
    late = extension_message(m, {"type": "archiveNow", "now": now + 13 * 3600 * 1000, "keys": [h["key"]], "explain": True})
    check("a tab that is only a placeholder is archived after that time", late.get("archived") == [h["url"]], str(late))
    r = sidebar_page(m, box + """page.openArchived(); await settled(() => open() && rowsHere().length);
      const shown = rowsHere().map(describe); key("Escape"); return shown;""")
    check("the list has its real address and title", [x["tip"].split("\n")[1] for x in r] == [h["url"]] and r[0]["title"] == TITLE, str(r))
    c = m.js(H + """return {left: wins().flatMap(w => w.gBrowser.tabs.filter(t => key(w, t) === JSON.stringify(args[0]))).length,
              recently: wins().flatMap(w => w.SessionStore.getClosedTabDataForWindow(w).map(c => c.state.entries.at(-1)?.url)).filter(u => u?.includes("ghost.html") && u.includes(encodeURIComponent(args[0]))).length};""", h["key"])
    check("nothing of it is left, in the tabs or as a placeholder in Recently Closed", c == {"left": 0, "recently": 0}, str(c))

    # A double click is one click: what comes under the pointer after the first does not get
    # the second. Three rows of their own, with the sidebar page in front again.
    urls = m.js(H + settled + """const w = main(), [pages, ctx] = args;
      const made = ["a", "b", "c"].map(q => w.gBrowser.addTrustedTab(pages + "/with-title?smoke-archived-twice-" + q, {userContextId: ctx, inBackground: true}));
      await settled(() => made.every(t => key(w, t) && t.label === %s));
      const urls = made.map(url);
      for (const t of made) { w.gBrowser.removeTab(t); await wait(150); }
      w.focus(); w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes("/sidebar/sidebar.html")); await wait(500);
      return urls;""" % json.dumps(TITLE), m.pages, ctx)
    tab_count = """return main().gBrowser.tabs.length;"""
    opened_view = box + """page.openArchived(); await settled(() => open() && rowsHere().length >= args[0]); await settled(() => box.getBoundingClientRect().left === 0);"""
    r = sidebar_page(m, opened_view + """const row = rowsHere()[0]; return {x: row.getBoundingClientRect().right - 16, y: middle(row).y, n: rowsHere().length};""", 3)
    n0 = m.js(H + tab_count)
    mouse(r["x"], r["y"], double=True)
    t = sidebar_page(m, box + """await settled(() => rowsHere().length < args[0]); await wait(500); return {n: rowsHere().length, open: open(), first: rowsHere()[0]?.title};""", r["n"])
    check("a double click on × forgets one row, and opens nothing", t.get("n") == r["n"] - 1 and t.get("open") and m.js(H + tab_count) == n0 and urls[1] in t.get("first", ""), str(t))
    b = sidebar_page(m, box + """return middle(box.querySelector(".back"));""")
    mouse(b["x"], b["y"], double=True)
    t = sidebar_page(m, box + """await settled(() => !open()); await wait(500); return {open: open()};""")
    check("a double click on the back row goes back, and presses nothing under it", t.get("open") is False and m.js(H + tab_count) == n0, f"{t} {n0} -> {m.js(H + tab_count)}")
    # A row selects its tab, and then this page is behind it and gets no real mouse here, so the
    # second click is the same event Firefox would send to the row of the list come into sight.
    r = sidebar_page(m, opened_view + """
      const under = doc.querySelector("#tabs > .tab"), row = rowsHere()[0], tip = row.title;
      const click = (e, detail) => e.dispatchEvent(new page.MouseEvent("click", {bubbles: true, cancelable: true, detail}));
      click(row, 1);
      const closed = !open();
      await wait(300);
      click(under, 2);
      await wait(800);
      return {closed, tip};""", 2)
    t = m.js(H + settled + """const w = main(); await settled(() => url(w.gBrowser.selectedTab) === args[0], 5000); return url(w.gBrowser.selectedTab);""", urls[1])
    check("a double click on a row opens that tab, and the list under it does not get the second click", r.get("closed") and t == urls[1], f"{r} {t}")

    # With the view closed nothing of it is kept, and it opens again at the top.
    m.js(H + """const w = main(); w.focus(); w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes("/sidebar/sidebar.html")); await wait(500); return 1;""")
    r = sidebar_page(m, opened_view + """
      const scroller = box.querySelector(".rows");
      scroller.style.maxHeight = "20px"; scroller.scrollTop = 20;
      const scrolled = scroller.scrollTop;
      key("Escape");
      await settled(() => !rowsHere().length, 3000);
      const left = rowsHere().length;
      scroller.style.maxHeight = "";
      page.openArchived();
      await settled(() => open() && rowsHere().length);
      return {scrolled, left, top: scroller.scrollTop};""", 1)
    check("a closed view keeps no rows, and opens again at the top", r.get("scrolled") and r.get("left") == 0 and r.get("top") == 0, str(r))

    # The age changes with the minute, and only the age: a row redrawn under a click would take
    # the click from its × (the row then opens instead of forgets), and fetch its icon again.
    r = sidebar_page(m, box + """
      await settled(() => open() && rowsHere().length);
      const row = rowsHere()[0], close = row.querySelector(".close"), title = row.querySelector(".title"), now = page.Date.now;
      page.Date.now = page.Function.prototype.bind.call(page.Number, null, Date.now() + 5 * 3600e3 + 60000);
      await page.refreshArchived();
      page.Date.now = now;
      return {same: row.isConnected && row.querySelector(".close") === close && row.querySelector(".title") === title, age: row.querySelector(".age").textContent};""")
    check("when only time has passed a row shows its new age, and nothing else of it is drawn again", r.get("same") and r.get("age") == "5 h", str(r))

    # A key or a link can change the space under the view: it was about the space you were in.
    r = sidebar_page(m, box + """
      await settled(() => open());
      const away = spaces().find(s => !s.active).id;
      send({type: "space", space: away});
      await settled(() => spaces().find(s => s.active).id === away);
      await settled(() => !open(), 3000);
      const closed = !open();
      send({type: "space", space: args[0]});
      await settled(() => spaces().find(s => s.active).id === args[0]);
      return {closed};""", space)
    check("a space changed by a key closes the view", r.get("closed"), str(r))

    # A container removed in Firefox's settings: its tabs close first, each one lands in the
    # list, and then the container goes. Neither its rows nor a view of them are left.
    c = m.js(H + settled + """const w = main(), C = w.ContextualIdentityService, made = C.create("Smoke gone", "circle", "blue");
      const t = w.gBrowser.addTrustedTab(args[0] + "/with-title?smoke-archived-gone", {userContextId: made.userContextId, inBackground: true});
      await settled(() => key(w, t) && t.label === %s);
      return {id: made.userContextId, url: url(t)};""" % json.dumps(TITLE), m.pages)
    gone = "firefox-container-%d" % c["id"]
    r = sidebar_page(m, box + """await settled(() => doc.querySelector(`#spaces .space[data-space="${args[0]}"]`));
      page.openArchived(args[0]); await settled(() => open()); return open();""", gone)
    m.js(H + settled + """const C = main().ContextualIdentityService; await C.closeContainerTabs(args[0]); C.remove(args[0]); return 1;""", c["id"])
    r = sidebar_page(m, box + """await settled(() => !open(), 5000);
      await settled(() => !doc.querySelector(`#spaces .space[data-space="${args[0]}"]`), 5000);
      await wait(1000);
      const every = await page.browser.runtime.sendMessage({type: "archivedTabs"}).then(l => JSON.parse(JSON.stringify(l)));
      const stored = await page.browser.storage.local.get("archivedTabs").then(l => JSON.parse(JSON.stringify(l)));
      return {open: open(), every: every.filter(x => x.space === args[0]), stored: Object.keys(stored.archivedTabs || {}).includes(args[0])};""", gone)
    check("a removed container's rows and its open view go with it", r.get("open") is False and r.get("every") == [], str(r))

    # Firefox's own keyboard, on the sidebar page in front: ↓ moves, ⌫ forgets, ← goes back, Enter opens.
    def keyboard(*keys):
        into_page(m, "/sidebar/sidebar.html")  # not through every tab: that loads each unloaded one
        acts = [a for k in keys for a in ({"type": "keyDown", "value": k}, {"type": "keyUp", "value": k})]
        m.cmd("WebDriver:PerformActions", {"actions": [{"type": "key", "id": "keyboard", "actions": acts}]})
        m.cmd("WebDriver:ReleaseActions")
        m.chrome()
    DOWN, LEFT, BACKSPACE, ENTER = "\uE015", "\uE012", "\uE003", "\uE007"
    r = sidebar_page(m, opened_view + """return {tips: rowsHere().map(x => x.title.split("\\n")[1]), under: doc.querySelector("#tabs .cursor")?.dataset.tab ?? null};""", 2)
    keyboard(DOWN, BACKSPACE)
    t = sidebar_page(m, box + """await settled(() => rowsHere().length === args[0] - 1, 5000);
      return {tips: rowsHere().map(x => x.title.split("\\n")[1]), open: open(), cursor: rowsHere().findIndex(x => x.classList.contains("cursor")), under: doc.querySelector("#tabs .cursor")?.dataset.tab ?? null};""", len(r["tips"]))
    check("↓ and ⌫ on the keyboard forget the first row, and stay in the view", t.get("tips") == r["tips"][1:] and t.get("open") and t.get("cursor") == 0 and t.get("under") == r["under"], f"{r} {t}")
    keyboard(LEFT)
    t = sidebar_page(m, box + """await settled(() => !open(), 5000); return {open: open()};""")
    check("← on the keyboard goes back", t.get("open") is False, str(t))
    r = sidebar_page(m, opened_view + """return rowsHere().map(x => x.title.split("\\n")[1]);""", 1)
    keyboard(DOWN, ENTER)
    t = m.js(H + settled + """const w = main(); await settled(() => url(w.gBrowser.selectedTab) === args[0], 8000); return url(w.gBrowser.selectedTab);""", r[0])
    check("↓ and Enter on the keyboard open the first row", t == r[0], f"{r} {t}")

    # What this group added goes again.
    m.js(H + settled + """const a = main(), ours = (w, t) => url(t).includes("smoke-archived") || String(t.label) === %s;
      await removeWhere(ours);
      if (args[0]) await close(other());
      return 1;""" % json.dumps(TITLE), opened)
    no_problems(m, "after using the list of archived tabs")


def alone_drag(m):
    # Real drag events on the real sidebar: into a folder, among the tabs, to the essentials.
    more_tabs_here(m, "drag")
    r = sidebar_page(m, """
      const drag = async (from, to, below = false, atOnce = () => null) => {
        const data = new page.DataTransfer(), box = to.getBoundingClientRect();
        const at = {bubbles: true, cancelable: true, clientX: box.left + 5, clientY: box.top + (below ? box.height - 1 : 1), dataTransfer: data};
        from.dispatchEvent(new page.DragEvent("dragstart", at));
        to.dispatchEvent(new page.DragEvent("dragover", at));
        to.dispatchEvent(new page.DragEvent("drop", at));
        from.dispatchEvent(new page.DragEvent("dragend", at));
        const seen = atOnce(); // before any view has come back
        await wait(1800);
        return seen;
      };
      send({type: "newFolder", space: spaces().find(s => s.active).id, name: "Dragged"});
      await wait(1000);
      const row = () => plainTabs(), head = () => [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "Dragged");
      const out = {};
      const a = row()[0], aTitle = Number(a.dataset.tab);
      const n0 = row().length, inFolder0 = head().parentElement.querySelectorAll(".tab").length;
      await drag(a, head());
      out.into = {left: row().length === n0 - 1, inFolder: head().parentElement.querySelectorAll(".tab").length === inFolder0 + 1};
      const back = head().parentElement.querySelector(".tab");
      await drag(back, row().at(-1), true);
      out.out = {back: row().length === n0, last: Number(row().at(-1).dataset.tab) === aTitle};
      const first = row()[0], last = row().at(-1), lastId = Number(last.dataset.tab);
      out.atOnce = await drag(last, first, false, () => Number(row()[0].dataset.tab) === lastId);
      out.before = Number(row()[0].dataset.tab) === lastId;
      const tiles0 = tiles().length;
      const pinned = row()[0], pinnedId = Number(pinned.dataset.tab);
      await drag(pinned, doc.getElementById("essentials"));
      out.pinned = tiles().length === tiles0 + 1;
      const tile = doc.querySelector(`#essentials .tile[data-tab="${pinnedId}"]`);
      if (tile) await drag(tile, doc.getElementById("tabs"));
      out.unpinned = tiles().length === tiles0;
      send({type: "deleteFolder", key: head().dataset.folderHead});
      await wait(1000);
      // Keys: down to a tab, Enter selects it. (Home to the top; in the essentials' grid ↓ goes a row at a time.)
      const key = k => page.dispatchEvent(new page.KeyboardEvent("keydown", {key: k, bubbles: true, cancelable: true}));
      const reach = [...doc.querySelectorAll(".tile, #tabs .head, #tabs .tab")];
      key("Home");
      for (let i = 0; i < reach.length && doc.querySelector(".cursor") !== plainTabs()[0]; i++) key("ArrowDown");
      const chosen = doc.querySelector(".cursor");
      out.cursor = chosen === plainTabs()[0];
      await wait(100);
      return out;""")
    check("the arrow keys move through the sidebar", r.get("cursor") is True, str(r))
    check("a tab dragged onto a folder goes into it", r.get("into") == {"left": True, "inFolder": True}, str(r))
    check("a tab dragged out of a folder is an ordinary tab, where you put it", r.get("out") == {"back": True, "last": True}, str(r))
    check("a tab dragged above another is there", r.get("before") is True, str(r))
    check("and is there at once, not a view later", r.get("atOnce") is True, str(r))
    check("a tab dragged to the essentials is an essential, and dragged back an ordinary tab", r.get("pinned") is True and r.get("unpinned") is True, str(r))


# What a drag shows, for the checks below: dragover says whether a drop would do something
# (drag.js cancels it, and only then does a drop send anything), and what is marked.
DRAG_TOOLS = """
  const list = doc.getElementById("tabs"), grid = doc.getElementById("essentials");
  const marked = () => [...doc.querySelectorAll(".drop-before, .drop-after, .drop-left, .drop-right, .drop-into")].map(e => [...e.classList].find(c => c.startsWith("drop-")));
  const ev = (type, el, x = .5, y = .5) => { const b = el.getBoundingClientRect();
    return new page.DragEvent(type, {bubbles: true, cancelable: true, clientX: b.left + b.width * x, clientY: b.top + b.height * y, dataTransfer: new page.DataTransfer()}); };
  const start = el => el.dispatchEvent(ev("dragstart", el));
  const end = el => el.dispatchEvent(ev("dragend", el));
  const over = (el, x, y) => [!el.dispatchEvent(ev("dragover", el, x, y)), ...marked()];
  const drop = (el, x, y) => !el.dispatchEvent(ev("drop", el, x, y));
  // By the clock: this page is a background tab here, where each wait can take a second.
  const until = async (test, ms = 8000) => { for (const t0 = Date.now(); Date.now() - t0 < ms && !test();) await wait(50); return !!test(); };
  const ids = els => [...els].map(e => Number(e.dataset.tab));
  const tileEls = () => [...doc.querySelectorAll("#essentials .tile")];
"""


def alone_drag_details(m):
    # Honest dragging, in drag events on the real sidebar: a mark only where a drop does
    # something, places among the essentials, and a click that shakes. A second window to follow.
    more_tabs_here(m, "details")
    m.js(H + """if (other()) return 1;
      const a = main(), n = a.gBrowser.tabs.filter(t => t.pinned).length, w = a.OpenBrowserWindow(); w.__smoke = true;
      for (let i = 0; i < 200 && !(w.gBrowser && w.gBrowser.tabs.filter(t => t.pinned).length >= n); i++) await wait(50);
      await wait(2000); return 1;""")
    r = sidebar_page(m, DRAG_TOOLS + """
      // The newest three: side by side, with nothing of the test's own between them.
      const out = {}, rows = plainTabs(), [a, b, c] = rows.slice(-3), last = c, order = ids(rows);
      start(b);
      out.belowPrevious = over(a, .5, .8);
      out.aboveNext = over(c, .5, .2);
      out.itself = over(b);
      out.dropNext = drop(c, .5, .2);
      end(b);
      start(b);
      out.belowNext = over(c, .5, .8);
      out.abovePrevious = over(a, .5, .2);
      doc.body.dispatchEvent(new page.DragEvent("dragleave", {bubbles: true, relatedTarget: null}));
      out.leftTheSidebar = marked();
      out.back = over(a, .5, .2);
      end(b);
      out.afterEnd = marked();
      start(last);
      out.endFromLast = over(list, .5, .999);
      end(last);
      start(a);
      out.end = over(list, .5, .999);
      end(a);
      out.stayed = JSON.stringify(ids(plainTabs())) === JSON.stringify(order);
      return out;""")
    check("no mark and nothing sent right above or below the dragged row, or on it",
          r["belowPrevious"] == [False] and r["aboveNext"] == [False] and r["itself"] == [False] and r["dropNext"] is False and r["stayed"], str(r))
    check("a mark where a drop does move the row", r["belowNext"] == [True, "drop-after"] and r["abovePrevious"] == [True, "drop-before"], str(r))
    check("a mark goes when the drag leaves the sidebar, and comes back, and goes at the end of the drag",
          r["leftTheSidebar"] == [] and r["back"] == [True, "drop-before"] and r["afterEnd"] == [], str(r))
    check("the empty end of the list is a line after the last tab, and nothing for the last tab itself",
          r["end"] == [True, "drop-after"] and r["endFromLast"] == [False], str(r))

    # A drop shows where it lands at once, and the row never jumps back while the move is
    # carried out and every window follows (drag.js, sendDrop).
    r = sidebar_page(m, DRAG_TOOLS + """
      const rows = plainTabs(), [a, b, c] = rows.slice(-3), want = ids(rows).filter(id => id !== Number(b.dataset.tab));
      want.splice(want.indexOf(Number(c.dataset.tab)) + 1, 0, Number(b.dataset.tab));
      const same = () => JSON.stringify(ids(plainTabs())) === JSON.stringify(want);
      start(b); const placed = drop(c, .5, .8); end(b);
      const atOnce = same();
      let back = 0;
      for (const t0 = Date.now(); Date.now() - t0 < 2500; await wait(20)) if (!same()) back++;
      start(b); drop(a, .5, .8); end(b); // and back where it was
      await until(() => ids(plainTabs()).indexOf(Number(b.dataset.tab)) === ids(plainTabs()).indexOf(Number(a.dataset.tab)) + 1);
      return {placed, atOnce, back, after: same()};""")
    check("a dropped row stands in its new place at once, and stays there", r["placed"] and r["atOnce"] and r["back"] == 0, str(r))

    r = sidebar_page(m, DRAG_TOOLS + """
      const out = {}, space = spaces().find(s => s.active).id;
      const head = name => [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === name);
      for (const name of ["Drag 1", "Drag 2", "Drag 3"]) { send({type: "newFolder", space, name}); await until(() => head(name)); }
      const [h1, h2, h3] = ["Drag 1", "Drag 2", "Drag 3"].map(head);
      start(h2);
      out.belowPrevious = over(h1, .5, .8);
      out.aboveNext = over(h3, .5, .2);
      out.itself = over(h2);
      out.belowNext = over(h3, .5, .8);
      out.abovePrevious = over(h1, .5, .2);
      end(h2);
      // A tab in a folder.
      const row = plainTabs()[0], rowId = Number(row.dataset.tab);
      start(row); drop(h1); end(row);
      await until(() => h1.parentElement.querySelector(".tab"));
      const inside = h1.parentElement.querySelector(".tab");
      start(inside);
      out.ownFolderLast = over(h1);
      out.otherFolder = over(h2);
      out.indent = over(h1.parentElement.lastChild, .01, .5);
      out.gap = over(doc.querySelector("#tabs .divider"));
      // A live folder keeps its tabs: nothing but the essentials or a space is a place for them.
      h1.parentElement.classList.add("live");
      out.liveToRow = over(plainTabs()[0], .5, .2);
      out.liveToFolder = over(h2);
      out.liveToEnd = over(list, .5, .999);
      h1.parentElement.classList.remove("live");
      end(inside);
      // A new tab page: no folder, essential or other space can have it, only a place among the tabs.
      const known = new Set(plainTabs().map(r => r.dataset.tab));
      send({type: "newTab", space});
      await until(() => plainTabs().some(r => !known.has(r.dataset.tab)));
      const bareId = plainTabs().find(r => !known.has(r.dataset.tab)).dataset.tab, bareRow = () => plainTabs().find(r => r.dataset.tab === bareId);
      // (A new tab is the first of today's tabs, so the row after it is the next one, and right above that is no move.)
      const bare = bareRow(), web = plainTabs().find(r => r !== bare);
      start(bare);
      out.bareTile = over(tileEls()[0], .25);
      out.bareSpace = over(doc.querySelector(".space:not(.active)"));
      out.bareFolder = over(h2);
      out.bareInFolder = over(inside, .5, .2);
      out.bareAmong = over(web, .5, .8);
      end(bare);
      // Pinned, as Firefox's own menu can: a tile with no essential behind it, so no place among them.
      // (The sidebar's own pin keeps a new tab a tab: pinFromSidebar, sidebar-view.js.)
      await page.browser.tabs.update(Number(bareId), {pinned: true});
      await until(() => !bareRow());
      const bareTile = doc.querySelector(`#essentials .tile[data-tab="${bareId}"]`);
      start(bareTile);
      out.bareAmongTiles = over(tileEls()[0], .25);
      out.bareToList = over(list, .5, .999);
      end(bareTile);
      send({type: "pin", tabId: Number(bareId), pinned: false});
      await until(() => bareRow());
      // A tab dropped right above it lands there, not past it at the end.
      out.aboveBare = {want: Number(web.dataset.tab)};
      start(web); drop(bareRow(), .5, .2); end(web);
      await until(() => plainTabs().indexOf(web) === plainTabs().indexOf(bareRow()) - 1);
      out.aboveBare.got = Number(plainTabs()[plainTabs().indexOf(bareRow()) - 1]?.dataset.tab);
      send({type: "close", tabId: Number(bareId)});
      await until(() => !bareRow());
      start(inside); drop(plainTabs()[0], .5, .2); end(inside);
      await until(() => !h1.parentElement.querySelector(".tab"));
      for (const h of [h1, h2, h3]) send({type: "deleteFolder", key: h.dataset.folderHead});
      await until(() => !doc.querySelector("#tabs .folder"));
      return out;""")
    check("no mark and nothing sent right above or below a dragged folder, or on it",
          r["belowPrevious"] == [False] and r["aboveNext"] == [False] and r["itself"] == [False]
          and r["belowNext"] == [True, "drop-after"] and r["abovePrevious"] == [True, "drop-before"], str(r))
    check("no mark on the folder a tab is last in already; a mark on another", r["ownFolderLast"] == [False] and r["otherFolder"] == [True, "drop-into"], str(r))
    check("a folder's indent is no place, and the gap above the tabs is the top of them", r["indent"] == [False] and r["gap"] == [True, "drop-before"], str(r))
    check("a tab in a live folder has no place among the other tabs", r["liveToRow"] == [False] and r["liveToFolder"] == [False] and r["liveToEnd"] == [False], str(r))
    check("a new tab page has no mark on an essential, a space or a folder, only among the tabs",
          r["bareTile"] == [False] and r["bareSpace"] == [False] and r["bareFolder"] == [False] and r["bareInFolder"] == [False] and r["bareAmong"][0] is True, str(r))
    check("and pinned it has no place among the essentials, only the way back", r["bareAmongTiles"] == [False] and r["bareToList"] == [True, "drop-into"], str(r))
    check("a tab dropped right above a new tab page lands there", r["aboveBare"]["got"] == r["aboveBare"]["want"], str(r))

    def essentials_here():
        return m.js(H + """const ctx = main().gBrowser.selectedTab.userContextId || Number(args[0].split("-").pop());
          return wins().map(w => w.gBrowser.tabs.filter(t => t.pinned && t.userContextId === ctx).map(t => ek(w, t)));""", space)
    space = sidebar_page(m, "return spaces().find(s => s.active).id;")
    keys0 = essentials_here()
    r = sidebar_page(m, DRAG_TOOLS + """
      const out = {}, [t0, t1] = tileEls(), first = Number(t0.dataset.tab), second = Number(t1.dataset.tab);
      start(t0);
      out.itselfLeft = over(t0, .25);
      out.itselfRight = over(t0, .75);
      out.nextLeft = over(t1, .25);
      out.nextRight = over(t1, .75);
      out.emptyEnd = over(grid, .999, .5);
      out.placed = drop(t1, .75);
      end(t0);
      out.order = await until(() => ids(tileEls())[1] === first) && ids(tileEls());
      out.want = [second, first];
      const row = plainTabs()[0];
      start(row);
      out.tabGap = over(grid, 0, .5);
      out.tabLeft = over(t1, .25);
      out.tabRight = over(t1, .75);
      out.nameWithTiles = over(doc.getElementById("space-name"));
      end(row);
      return out;""")
    # (The sidebar shows a drop at once, before every window has it: so this waits for the windows.)
    want_keys = keys0[0][1:] + keys0[0][:1]
    for _ in range(50):
        keys1 = essentials_here()
        if len(keys1) > 1 and all(k == want_keys for k in keys1):
            break
        time.sleep(0.1)
    check("no mark on a tile itself or at the place right after it", r["itselfLeft"] == [False] and r["itselfRight"] == [False] and r["nextLeft"] == [False], str(r))
    check("a tile's left or right half decides the side of the line", r["nextRight"] == [True, "drop-right"] and r["tabLeft"] == [True, "drop-left"] and r["tabRight"] == [True, "drop-right"], str(r))
    check("the empty end of the essentials' last line is the last place", r["emptyEnd"] == [True, "drop-right"], str(r))
    check("the gaps of the grid are places too, so a line does not flicker on its way", r["tabGap"][0] is True, str(r))
    check("the space's name is no place while it has essentials", r["nameWithTiles"] == [False], str(r))
    check("a tile dragged to the right half of the last tile lands last", r["placed"] is True and r["order"] == r["want"], str(r))
    check("and last in every window", len(keys1) > 1 and all(k == keys0[0][1:] + keys0[0][:1] for k in keys1), f"{keys0} -> {keys1}")

    keys0 = essentials_here()
    r = sidebar_page(m, DRAG_TOOLS + """
      const out = {}, [t0, t1] = tileEls(), row = plainTabs()[0], id = Number(row.dataset.tab);
      out.want = [Number(t0.dataset.tab), id, Number(t1.dataset.tab)];
      start(row); out.placed = drop(t1, .25); end(row);
      out.order = await until(() => tileEls().length === 3) && ids(tileEls());
      out.left = !plainTabs().some(r => Number(r.dataset.tab) === id);
      return {...out, id};""")
    keys1 = essentials_here()
    check("a tab dropped on a tile's left half is an essential right before it", r["placed"] is True and r["order"] == r["want"] and r["left"], str(r))
    check("and in that place in every window", len(keys1) > 1 and all(len(k) == 3 and k[0] == keys0[0][0] and k[2] == keys0[0][1] and k[1] == keys1[0][1] for k in keys1), f"{keys0} -> {keys1}")
    r = sidebar_page(m, DRAG_TOOLS + """
      const tile = tileEls().find(t => Number(t.dataset.tab) === args[0]);
      start(tile); drop(list); end(tile);
      await until(() => tileEls().length === 2);
      const row = plainTabs().find(r => Number(r.dataset.tab) === args[0]) || plainTabs()[0], id = Number(row.dataset.tab), [, t1] = tileEls();
      const want = [...ids(tileEls()), id];
      await wait(1000); // an unpin counts only after a moment (essentials.js, UNPIN_SETTLE_MS)
      start(row); const placed = drop(t1, .75); end(row);
      const order = await until(() => tileEls().length === 3) && ids(tileEls());
      const tile2 = tileEls().at(-1);
      start(tile2); drop(list); end(tile2);
      await until(() => tileEls().length === 2);
      await wait(1000);
      return {placed, order, want};""", r["id"])
    check("a tab dropped on the right half of the last tile is the last essential", r["placed"] is True and r["order"] == r["want"], str(r))

    # As in Arc, an essential dragged out lands where it is dropped, with the line a row shows.
    r = sidebar_page(m, DRAG_TOOLS + """
      const rows = plainTabs(), target = rows[1], tile = tileEls().at(-1), id = Number(tile.dataset.tab);
      start(tile); const mark = over(target, .5, .2); const placed = drop(target, .5, .2); end(tile);
      const landed = await until(() => { const now = ids(plainTabs()); return now.includes(id) && now[now.indexOf(Number(target.dataset.tab)) - 1] === id; });
      const out = {mark, placed, landed};
      // Back among the essentials, as it was.
      await wait(1000);
      const row = plainTabs().find(r => Number(r.dataset.tab) === id);
      if (row) { start(row); drop(tileEls().at(-1), .75); end(row); await until(() => tileEls().some(t => Number(t.dataset.tab) === id)); }
      await wait(1500);
      return out;""")
    check("an essential dragged out shows the line where it will land, and lands there", r["mark"] == [True, "drop-before"] and r["placed"] and r["landed"], str(r))

    # A move, and at once a drop on a tile: tab sync still counts the tab as moved by itself.
    row = sidebar_page(m, "return Number(plainTabs()[0].dataset.tab);")
    sync_key = m.js(H + """const {ExtensionParent} = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
      const ids = ExtensionParent.apiManager.global.tabTracker;
      for (const w of wins()) for (const t of w.gBrowser.tabs) if (ids.getId(t) === args[0]) return key(w, t);""", row)
    r = sidebar_page(m, DRAG_TOOLS + """
      const [row, next] = plainTabs(), id = Number(row.dataset.tab);
      start(row); const moved = drop(next, .5, .8); end(row);
      start(row); const pinned = drop(tileEls()[0], .25); end(row);
      await until(() => tileEls().some(t => Number(t.dataset.tab) === id));
      return {moved, pinned, id};""")
    left = m.js(H + """for (let i = 0; i < 100 && find(args[0]).flat().length; i++) await wait(50);
      await wait(2000); // a placeholder that comes back would do it by now
      return {left: find(args[0]), copies: wins().map(w => w.gBrowser.tabs.filter(t => t.pinned).length)};""", sync_key)
    check("a tab moved and at once dropped on a tile is an essential in every window, and no longer a tab in any",
          sync_key and r["moved"] is True and r["pinned"] is True and r["id"] == row and all(not x for x in left["left"]) and len(set(left["copies"])) == 1, f"{sync_key} {r} {left}")
    sidebar_page(m, DRAG_TOOLS + """
      const tile = tileEls().find(t => Number(t.dataset.tab) === args[0]);
      start(tile); drop(list); end(tile);
      await until(() => !tile.isConnected);
      await wait(2500);
      return 1;""", r["id"])

    # What is being dragged goes during the drag: no mark, and no drag left over for it.
    more_tabs_here(m, "gone")
    r = sidebar_page(m, DRAG_TOOLS + """
      const out = {}, rows = plainTabs(), gone = rows.at(-1), row = rows[0], other = rows[1], id = Number(row.dataset.tab);
      start(gone);
      out.before = over(rows[0], .5, .2);
      send({type: "close", tabId: Number(gone.dataset.tab)});
      await until(() => !gone.isConnected);
      out.markGone = marked();
      out.after = over(rows[0], .5, .2);
      // A space and back: the row is drawn anew, and its dragend will never come.
      const here = spaces().find(s => s.active).id, away = spaces().find(s => !s.active && s.id !== "firefox-container-4").id;
      start(row);
      send({type: "space", space: away});
      await until(() => !doc.querySelector(`#tabs [data-tab="${id}"]`));
      send({type: "space", space: here});
      await until(() => doc.querySelector(`#tabs [data-tab="${id}"]`));
      out.cameBack = over(doc.querySelector(`#tabs [data-tab="${id}"]`).nextElementSibling, .5, .8);
      return out;""")
    check("a tab closing during its own drag takes the mark with it, and marks nothing after", r["before"][0] is True and r["markGone"] == [] and r["after"] == [False], str(r))
    check("a drag whose row went does not start again when the row comes back", r["cameBack"] == [False], str(r))

    # A space with no essentials has no grid: its name is where the first one goes.
    m.js(H + """main().gBrowser.addTrustedTab("https://example.org/?smoke-first-essential", {userContextId: 4, inBackground: true}); await wait(2500); return 1;""")
    r = sidebar_page(m, DRAG_TOOLS + """
      const out = {}, here = spaces().find(s => s.active).id, name = doc.getElementById("space-name");
      send({type: "space", space: "firefox-container-4"});
      await until(() => spaces().find(s => s.active).id === "firefox-container-4" && !tileEls().length && plainTabs().length);
      const row = plainTabs()[0], id = Number(row.dataset.tab);
      const hint = () => page.getComputedStyle(name, "::after").content;
      out.hintAtRest = hint();
      start(row);
      out.hintInDrag = hint();
      out.over = over(name);
      out.placed = drop(name);
      end(row);
      out.tiles = await until(() => tileEls().length === 1) && ids(tileEls());
      out.want = [id];
      send({type: "space", space: here});
      await until(() => spaces().find(s => s.active).id === here);
      return out;""")
    check("a space's first essential is dropped on the space's name, where the grid would be", r["over"] == [True, "drop-into"] and r["placed"] is True and r["tiles"] == r["want"], str(r))
    check("which says so while a tab is dragged", r["hintInDrag"] == '"Make essential"' and r["hintAtRest"] in ("none", "normal"), str(r))
    r = m.js(H + """for (let i = 0; i < 100 && wins().some(w => !w.gBrowser.tabs.some(t => t.pinned && t.userContextId === 4)); i++) await wait(50);
      const copies = wins().map(w => w.gBrowser.tabs.filter(t => t.pinned && t.userContextId === 4).map(t => !!ek(w, t)));
      const tile = main().gBrowser.tabs.find(t => t.pinned && t.userContextId === 4);
      if (tile) main().gBrowser.unpinTab(tile);
      await wait(3000);
      await removeWhere((w, t) => t.userContextId === 4);
      return copies;""")
    check("and every window has it", len(r) > 1 and r == [[True]] * len(r), str(r))

    # × inside a draggable row. A drag from it is refused, and the next drag is not.
    r = sidebar_page(m, DRAG_TOOLS + """
      const out = {}, [row, other] = plainTabs(), x = row.querySelector(".close"), press = el => el.dispatchEvent(new page.MouseEvent("mousedown", {bubbles: true}));
      press(x);
      out.refused = !start(row);
      out.over = over(other, .5, .8);
      out.drop = drop(other, .5, .8);
      end(row);
      press(row.querySelector(".title"));
      out.fromTitle = start(row);
      out.overAfter = over(other, .5, .8);
      end(row);
      send({type: "mute", tabId: Number(row.dataset.tab), muted: true});
      await until(() => row.querySelector(".sound"));
      press(row.querySelector(".sound"));
      out.soundRefused = !start(row);
      end(row);
      send({type: "mute", tabId: Number(row.dataset.tab), muted: false});
      await until(() => !row.querySelector(".sound"));
      const icon = doc.createElement("img");
      row.append(icon);
      out.iconTakesNoMouse = page.getComputedStyle(icon).pointerEvents === "none";
      icon.remove();
      return out;""")
    check("a drag that starts on × or the sound button is refused, and does nothing", r["refused"] is True and r["soundRefused"] is True and r["over"] == [False] and r["drop"] is False, str(r))
    check("a drag that starts on the row itself still works", r["fromTitle"] is True and r["overAfter"] == [True, "drop-after"], str(r))
    check("a row is dragged whole, also when grabbed by its icon", r["iconTakesNoMouse"] is True, str(r))

    # The rest with what only a real pointer does, in the sidebar page as the selected tab:
    # real mouse events, a real drag session, and what Firefox itself does with them.
    m.js(H + """const w = main(); w.__beforeDrag = w.gBrowser.selectedTab;
      w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes("/sidebar/sidebar.html")); await wait(500); return 1;""")
    into_page(m, "/sidebar/sidebar.html")

    def here(script):
        return m.cmd("WebDriver:ExecuteAsyncScript", {"sandbox": "system", "script": """
          const done = arguments[arguments.length - 1], wait = ms => new Promise(r => setTimeout(r, ms));
          const until = async (test, ms = 8000) => { for (const t0 = Date.now(); Date.now() - t0 < ms && !test();) await wait(50); return !!test(); };
          const rows = () => [...document.querySelectorAll("#tabs > .tab")].filter(r => r.querySelector(".title").textContent !== "Tidier");
          const list = document.getElementById("tabs");
          (async () => { """ + script + """ })().then(r => done(r ?? null), e => done({error: String(e)}));""", "args": []})

    def pointer(*steps):
        m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "drag", "parameters": {"pointerType": "mouse"}, "actions": list(steps)}]})

    def to(x, y):
        return {"type": "pointerMove", "x": x, "y": y, "origin": "viewport", "duration": 0}
    down, up, pause = {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}, {"type": "pause", "duration": 40}

    try:
        # A click whose hand shakes, on ×: past the distance that starts a drag, still on the button.
        at = here("""const [row] = rows(), b = row.querySelector(".close").getBoundingClientRect();
          return {n: rows().length, id: row.dataset.tab, order: rows().slice(1).map(r => r.dataset.tab), x: Math.round(b.left + b.width / 2), y: Math.round(b.top + b.height / 2)};""")
        pointer(to(at["x"] - 40, at["y"]), pause, to(at["x"], at["y"]), pause)
        here("""window.__heard = 0; window.addEventListener("dragstart", () => window.__heard++, {capture: true, once: true}); return 1;""")
        pointer(down, to(at["x"] + 3, at["y"] + 3), to(at["x"] + 6, at["y"] + 6), pause, up)
        r = here("""await until(() => rows().length < arguments[0]); return {n: rows().length, heard: window.__heard, order: rows().map(r => r.dataset.tab)};""".replace("arguments[0]", str(at["n"])))
        check("a click on × that shakes (Firefox starts a drag) stays a click, and closes the tab",
              r["heard"] == 1 and r["n"] == at["n"] - 1 and r["order"] == at["order"], f"{at} -> {r}")

        # A long list: the pointer resting at its edge in a real drag session. Firefox's own
        # scrolling takes one step at most here, so anything more is Tidier's (drag.js).
        m.chrome()
        m.js(H + """const w = main(), ctx = Number(args[0].split("-").pop());
          for (let i = 0; i < 40; i++) w.gBrowser.addTrustedTab("https://example.org/?smoke-long-" + i, {userContextId: ctx, inBackground: true});
          for (let i = 0; i < 200 && w.gBrowser.tabs.filter(t => url(t).includes("smoke-long")).length < 40; i++) await wait(100);
          return 1;""", space)
        into_page(m, "/sidebar/sidebar.html")
        at = here("""await until(() => list.scrollHeight > list.clientHeight + 200);
          list.scrollTop = 0; await wait(100);
          const box = list.getBoundingClientRect(), b = rows()[1].getBoundingClientRect();
          return {x: Math.round(b.left + 60), y: Math.round(b.top + b.height / 2), top: Math.ceil(box.top), bottom: Math.floor(box.bottom), overflow: list.scrollHeight - list.clientHeight};""")
        pointer(to(at["x"], at["y"]), pause, down, to(at["x"], at["y"] + 8), pause, to(at["x"], at["y"] + 16), pause, to(at["x"], at["bottom"] - 200), pause)
        r0 = here("""const session = !!window.windowUtils.dragSession; await wait(100); return {session, top: list.scrollTop, marks: document.querySelectorAll(".drop-before, .drop-after").length};""")
        check("a real drag starts from a row, and marks where it would land", r0["session"] and r0["top"] == 0 and r0["marks"] == 1, str(r0))

        def rate():  # how far the list goes in a while, with the pointer resting
            return here("""const a = list.scrollTop, t = performance.now(); await wait(600); return (list.scrollTop - a) / (performance.now() - t);""")

        # The pointer to a place in the list, and then the drag event a Firefox in use sends
        # for it: at the pointer. The test Firefox's own, made from the move (EventUtils.js,
        # _maybeSynthesizeDragOver), is aimed at the middle of the element under the pointer
        # instead: half a row from it, and in the gap between two rows, where that element is
        # the list itself, the middle of the list, far from either edge (seen: 551 for a
        # pointer at 941). With that alone the list scrolled at the edge or not by which row
        # happened to be there.
        def rest(y, dx=0):
            pointer(to(at["x"] + dx, y), pause)
            here("""const x = AT_X, y = AT_Y, e = document.elementFromPoint(x, y) ?? list;
              e.dispatchEvent(new DragEvent("dragover", {bubbles: true, cancelable: true, clientX: x, clientY: y, dataTransfer: new DataTransfer()})); return 1;"""
                 .replace("AT_X", str(at["x"] + dx)).replace("AT_Y", str(y)))
        rest(at["bottom"] - 35)
        slow = rate()
        rest(at["bottom"] - 2)
        fast = rate()
        # (What is under the pointer there, should it not scroll: the list's own, or something over it.)
        hit = here("""const at = y => { const e = document.elementFromPoint(X, y); return e ? e.tagName + "#" + e.id + "." + [...e.classList].join(".") + (list.contains(e) ? " in list" : "") : null; };
          return [at(BOTTOM - 35), at(BOTTOM - 2)];""".replace("X", str(at["x"])).replace("BOTTOM", str(at["bottom"])))
        check("with the pointer resting at the bottom edge the list goes on scrolling, faster the closer", 0 < slow and slow * 2 < fast, f"{slow} {fast} {hit}")
        r1 = here("""await until(() => list.scrollTop >= list.scrollHeight - list.clientHeight - 1);
          await wait(300); // the last step or two
          return {top: list.scrollTop, marks: document.querySelectorAll(".drop-before, .drop-after").length};""")
        # More to scroll, with the pointer still there and no new dragover: nothing keeps it running at the end.
        r1b = here("""const a = list.scrollTop; list.style.paddingBottom = "600px"; await wait(500); const b = list.scrollTop; list.style.paddingBottom = ""; await wait(100); return [a, b];""")
        check("it reaches the end of the list, with a mark, and stops there", r1["marks"] == 1 and r1["top"] >= at["overflow"] - 2 and r1b[0] == r1b[1], f"{at} {r1} {r1b}")
        rest(at["top"] + 6)
        back = here("""const a = list.scrollTop; await until(() => list.scrollTop < a - 100, 3000); return [a, list.scrollTop];""")
        check("at the top edge it scrolls back up", back[1] < back[0] - 100, str(back))
        rest(at["bottom"] - 200, 1)
        r2 = here("""await wait(100); const a = list.scrollTop; await wait(500); return [a, list.scrollTop];""")
        rest(at["bottom"] - 2)  # back at the edge
        r3 = here("""const a = WAS; await until(() => list.scrollTop > a + 40, 3000); const moving = list.scrollTop > a + 40;
          window.windowUtils.dragSession.endDragSession(true); await wait(300);
          const b = list.scrollTop; await wait(500); return {moving, session: !!window.windowUtils.dragSession, top: [b, list.scrollTop], marks: document.querySelectorAll(".drop-before, .drop-after").length};""".replace("WAS", str(r2[1])))
        check("away from the edge it does not, and after the drag nothing moves or stays marked", r2[0] == r2[1] and r3["moving"] and not r3["session"] and r3["top"][0] == r3["top"][1] and r3["marks"] == 0, f"{r2} {r3}")
        # Other ways a drag ends or leaves, and an essential: with events alone, so no scrolling of Firefox's own.
        r = here("""const ev = (type, el, y) => new DragEvent(type, {bubbles: true, cancelable: true, clientX: 60, clientY: y, dataTransfer: new DataTransfer()});
          const bottom = list.getBoundingClientRect().bottom - 2, tile = document.querySelector("#essentials .tile"), out = {};
          const moves = async () => { const a = list.scrollTop; await wait(300); return list.scrollTop !== a; };
          list.scrollTop = 0;
          const row = rows()[0];
          row.dispatchEvent(ev("dragstart", row, 0)); list.dispatchEvent(ev("dragover", list, bottom));
          out.scrolls = await moves();
          document.body.dispatchEvent(new DragEvent("dragleave", {bubbles: true, relatedTarget: null}));
          out.afterLeaving = await moves();
          list.dispatchEvent(ev("dragover", list, bottom));
          out.back = await moves();
          document.getElementById("spaces").dispatchEvent(ev("dragover", document.getElementById("spaces"), bottom + 40));
          out.overTheBar = await moves();
          list.dispatchEvent(ev("dragover", list, bottom));
          list.dispatchEvent(ev("drop", list, 200)); row.dispatchEvent(ev("dragend", row, 0));
          out.afterDrop = await moves();
          list.scrollTop = 0;
          tile.dispatchEvent(ev("dragstart", tile, 0)); list.dispatchEvent(ev("dragover", list, bottom));
          out.essential = await moves();
          tile.dispatchEvent(ev("dragend", tile, 0));
          return out;""")
        check("it stops when the drag leaves the sidebar, goes on when it is back, and stops over the bar and after a drop",
              r["scrolls"] is True and r["afterLeaving"] is False and r["back"] is True and r["overTheBar"] is False and r["afterDrop"] is False, str(r))
        check("an essential dragged over the list's edge scrolls it too: it lands where it is dropped there", r["essential"] is True, str(r))
    finally:
        here("""window.windowUtils.dragSession?.endDragSession(true); return 1;""")
        pointer(up)
        m.cmd("WebDriver:ReleaseActions")
        m.chrome()
        m.js(H + """const w = main(); for (const t of [...w.gBrowser.tabs]) if (url(t).includes("smoke-long")) w.gBrowser.removeTab(t);
          if (w.__beforeDrag?.isConnected) w.gBrowser.selectedTab = w.__beforeDrag; await wait(2500); return 1;""")

    # Last, after the real drags: in the test Firefox a real drag session that follows this
    # scripted drop on the bar (a space made, its name box, the space removed) gets drag
    # events at places the pointer never was, and the list's edge is never reached.
    # The place for a new space: after the last dot on the bar's line, never over one; lit
    # when a tab is over it; and the space made there opens its name box, as from the menu.
    r = sidebar_page(m, DRAG_TOOLS + """
      const out = {}, row = plainTabs().at(-1), id = Number(row.dataset.tab), plus = doc.querySelector(".new-space");
      const box = e => e.getBoundingClientRect(), bg = () => page.getComputedStyle(plus).backgroundColor;
      const known = new Set(spaces().map(s => s.id));
      out.atRest = plus.hidden;
      const dotsAt = () => [...doc.querySelectorAll("#spaces .space")].map(d => box(d.querySelector(".dot")));
      const was = dotsAt();
      start(row);
      const dots = dotsAt(), p = box(plus);
      out.dotsStay = dots.every((d, i) => Math.abs(d.left - was[i].left) < 0.5);
      out.inBar = plus.parentElement.id === "spaces";
      out.afterLast = p.left >= dots.at(-1).right;
      out.onLine = Math.abs((p.top + p.bottom) / 2 - (dots[0].top + dots[0].bottom) / 2) < 1;
      const rest = bg();
      plus.dispatchEvent(ev("dragover", plus));
      out.lit = plus.classList.contains("drop-into") && bg() !== rest;
      out.placed = drop(plus);
      end(row);
      const made = await until(() => doc.querySelector(".space-box") && spaces().some(s => !known.has(s.id)));
      const input = doc.querySelector(".space-box");
      out.box = made && {value: input.value, focus: doc.activeElement === input};
      out.space = spaces().find(s => !known.has(s.id))?.id;
      input?.dispatchEvent(new page.KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
      out.note = await until(() => doc.getElementById("note").classList.contains("shown")) && doc.querySelector("#note .text").textContent;
      if (out.space) await page.browser.contextualIdentities.remove(out.space);
      await until(() => !spaces().some(s => s.id === out.space));
      return out;""")
    check("the place for a new space shows only during a drag, on the bar's line after the last dot",
          r["atRest"] is True and r["inBar"] and r["afterLast"] and r["onLine"], str(r))
    check("and the dots stay where they were when it comes", r["dotsStay"], str(r))
    check("it lights up when a tab is over it", r["lit"], str(r))
    check("a tab dropped there makes a space whose name box opens, ready to type, and the line says where the tab went",
          r["placed"] and r["box"] == {"value": "New space", "focus": True} and r["note"] == "Moved to a new space", str(r))


def alone_archive(m):
    # A tab in a folder is kept by archiving; an ordinary one goes.
    more_tabs_here(m, "archive")
    r = sidebar_page(m, """
      send({type: "newFolder", space: spaces().find(s => s.active).id, name: "Kept"});
      await wait(1000);
      const key = [...doc.querySelectorAll("#tabs .folder .head")].at(-1).dataset.folderHead;
      const [a, b] = plainTabs().map(x => Number(x.dataset.tab));
      send({type: "moveTab", tabId: a, folder: key, before: null});
      await wait(2000);
      return {key, a, b};""")
    s = m.js(H + """const all = (await storage("%s", ["syncedTabs"])).syncedTabs;
      return {kept: Object.keys(all).find(k => all[k].parentKey === args[0])};""" % EXT_ID, r["key"])
    now = int(time.time() * 1000)
    late = extension_message(m, {"type": "archiveNow", "now": now + 13 * 3600 * 1000, "keys": [s["kept"]], "explain": True})
    check("archiving keeps a tab in a folder", late.get("kept", {}).get(s["kept"]) == "folder", str(late))


# A folder's tabs as Firefox itself has them, in the main window and a window of this
# group's own: hidden or not, and loaded or not (an unloaded tab has no linkedPanel).
# `k` is a tab's key as it is stored.
REST = H + """
  const until = async (test, ms = 12000) => { for (const t0 = Date.now(); Date.now() - t0 < ms; await wait(50)) if (test()) return true; return false; };
  const rest = () => wins().find(w => w.__rest), two = () => [main(), rest()];
  const tabsOf = (w, k) => w.gBrowser.tabs.filter(t => key(w, t) === JSON.stringify(k));
  const state = k => two().map(w => tabsOf(w, k).map(t => (t.hidden ? "hidden" : "shown") + (t.linkedPanel ? "/loaded" : "/unloaded")).join());
  const roles = k => two().map(w => tabsOf(w, k).map(t => role(w, t) + (t.linkedPanel ? "/loaded" : "/unloaded")).join());
  const rep = (w, k) => tabsOf(w, k)[0];
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const resting = (ks, wanted = ["hidden/unloaded", "hidden/unloaded"]) => ks.every(k => same(state(k), wanted));
  const each = ks => Object.fromEntries(ks.map(k => [k, state(k)]));
"""


def real_clicks(m, x, y, clicks):
    """Clicks with the mouse, from Firefox itself: unlike .click() in a page they count as a
    double click when they come quickly, and the page must be in the selected tab."""
    press_release = [{"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}]
    acts = [{"type": "pointerMove", "x": x, "y": y, "duration": 0, "origin": "viewport"}] + press_release
    for _ in range(clicks - 1):
        acts += [{"type": "pause", "duration": 60}] + press_release
    into_page(m, "/sidebar/sidebar.html")
    m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"}, "actions": acts}]})
    m.cmd("WebDriver:ReleaseActions")
    m.chrome()


def alone_folds_rest(m):
    # A closed folder rests, with real clicks and drags on the real sidebar, and read from
    # Firefox itself rather than from what Tidier thinks. In two windows, since a fold is
    # the same in every window and a tab is only loaded in one. The second is a new one,
    # since it starts in the space you are in, while other groups leave theirs anywhere.
    sidebar_page(m, "return 1;")
    m.js(H + """const a = main(); a.focus(); await wait(500);
      const want = a.gBrowser.tabs.filter(t => !t.pinned && role(a, t)).length, w = a.OpenBrowserWindow(); w.__rest = w.__extra = true;
      for (let i = 0; i < 200 && !(w.gBrowser && w.gBrowser.tabs.filter(t => !t.pinned && role(w, t)).length >= want); i++) await wait(50);
      await wait(2000); a.focus(); await wait(500); return 1;""")
    more_tabs_here(m, "rest")
    more_tabs_here(m, "drop")
    s = sidebar_page(m, """
      const space = spaces().find(s => s.active).id;
      send({type: "newFolder", space, name: "Resting"});
      await wait(1000);
      const key = [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "Resting").dataset.folderHead;
      const tabs = [...await page.browser.tabs.query({})];
      const rest = tabs.filter(t => t.url.includes("smoke-rest-")).map(t => t.id);
      for (const tabId of rest) { send({type: "moveTab", tabId, folder: key, before: null}); await wait(200); }
      await wait(1500);
      return {space, key, ctx: Number(space.split("-").pop()), rest, drop: tabs.filter(t => t.url.includes("smoke-drop-")).map(t => t.id)};""")
    ctx = s["ctx"]
    keys = m.js(REST + """const all = (await storage("%s", ["syncedTabs"])).syncedTabs;
      return Object.keys(all).filter(k => all[k].parentKey === args[0]);""" % EXT_ID, s["key"])
    click_head = lambda name="Resting": sidebar_page(m, """
      [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === args[0]).click();
      await wait(50); return 1;""", name)
    first, second, selected = keys
    before = m.js(REST + """await until(() => resting(args[0], ["shown/loaded", "shown/unloaded"])); return each(args[0]);""", keys)

    # Renaming by a double click must not cost the pages: its first click closes the folder.
    # With the mouse, so with the page in front, which is put back afterwards.
    m.js(H + """const w = main(); w.__beforeRename = w.gBrowser.selectedTab; w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes("/sidebar/sidebar.html")); await wait(500); return 1;""")
    # (In view first: in a list grown long it can be below the window, and the clicks would land elsewhere.)
    head_at = sidebar_page(m, """const h = doc.querySelector(`[data-folder-head="${args[0]}"]`); h.scrollIntoView({block: "center"}); await wait(300);
      const b = h.getBoundingClientRect(); return {x: Math.round(b.left + b.width / 2), y: Math.round(b.top + b.height / 2)};""", s["key"])
    real_clicks(m, head_at["x"], head_at["y"], 2)
    r = sidebar_page(m, """await wait(1200);  // longer than a click waits for a second one
      const box = doc.querySelector(`[data-folder-head="${args[0]}"]`).parentElement, input = box.querySelector("input.rename");
      const was = {renaming: !!input, closed: box.classList.contains("collapsed")};
      input?.dispatchEvent(new page.KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
      await wait(100);
      return {...was, name: box.querySelector(".head .title").textContent};""", s["key"])
    t = m.js(REST + """return {tabs: each(args[0]), still: resting(args[0], ["shown/loaded", "shown/unloaded"])};""", keys)
    check("a double click on a folder renames it, and leaves it open", r["renaming"] and not r["closed"] and r["name"] == "Resting", str(r))
    check("a double click on a folder unloads and hides nothing", t["still"], str(t))
    # Closed, by one click with the mouse: the head shows it as soon as most double clicks would
    # have had their second click (FOLD_SHOWS_MS, a quarter of a second, so that a double click
    # renames with nothing folding first), and once no second click has come the tabs are hidden
    # in both windows, and the real ones unloaded, on the address they had. Then the page's tab
    # gives way to the tab that was selected.
    real_clicks(m, head_at["x"], head_at["y"], 1)
    fold_seen = sidebar_page(m, """const box = doc.querySelector(`[data-folder-head="${args[0]}"]`).parentElement;
      for (let i = 0; i < 20 && !box.classList.contains("collapsed"); i++) await wait(50);
      return {closed: box.classList.contains("collapsed"), count: box.querySelector(".count").textContent};""", s["key"])
    m.js(H + "const w = main(); w.gBrowser.selectedTab = w.__beforeRename; delete w.__beforeRename; return 1;")
    check("one click with the mouse closes a folder within a moment, with its count", fold_seen == {"closed": True, "count": "3"}, str(fold_seen))
    r = m.js(REST + """const ok = await until(() => resting(args[0]));
      return {ok, tabs: each(args[0]), urls: args[0].map(k => url(rep(main(), k))), selected: url(main().gBrowser.selectedTab),
              ctrlTab: args[0].filter(k => main().ctrlTab.tabList.includes(rep(main(), k))).length};""", keys)
    check("a folder's tabs are loaded and shown before it closes", all(v[0] == "shown/loaded" and v[1] == "shown/unloaded" for v in before.values()), str(before))
    check("closing a folder hides its tabs in both windows and unloads them", r["ok"], str(r))
    check("a tab that rests keeps the address it was on", all("smoke-rest-" in u for u in r["urls"]), str(r))
    check("a closed folder's tabs are out of Firefox's own ⌃Tab list", r["ctrlTab"] == 0, str(r))
    # Its height goes to nothing in a soft move (sidebar/motion.js), so the room it leaves is
    # read once that is over, not in the middle of it.
    r = sidebar_page(m, """const f = folders().find(f => f.name === "Resting"), head = [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "Resting");
      const children = head.parentElement.querySelector(".children");
      for (let i = 0; i < 60 && children.offsetHeight; i++) await wait(50);
      return {collapsed: f.collapsed, count: head.querySelector(".count").textContent, height: children.offsetHeight};""")
    check("the closed folder shows how many tabs it holds, and no rows", r["collapsed"] and r["count"] == "3" and r["height"] == 0, str(r))

    # Opened: shown again, and nothing loads by itself.
    click_head()
    r = m.js(REST + """const ok = await until(() => resting(args[0], ["shown/unloaded", "shown/unloaded"])); await wait(1500);
      return {ok, tabs: each(args[0]), still: resting(args[0], ["shown/unloaded", "shown/unloaded"]), ctrlTab: args[0].filter(k => main().ctrlTab.tabList.includes(rep(main(), k))).length};""", keys)
    check("opening a folder shows its tabs and loads nothing", r["ok"] and r["still"], str(r))
    check("an open folder's tabs are back in ⌃Tab's list", r["ctrlTab"] == 3, str(r))

    # The selected tab stays until you leave it, then rests too.
    r = m.js(REST + """const w = main(), t = rep(w, args[0]); w.__beforeRest = w.gBrowser.selectedTab;
      w.gBrowser.selectedTab = t; return await until(() => t.linkedPanel && !url(t).includes("ghost.html"));""", selected)
    check("a tab in a folder is selected and loaded", r, str(r))
    click_head()
    r = m.js(REST + """const ok = await until(() => resting(args[0])); await wait(500);
      const w = main(), during = state(args[1]);
      w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes("smoke-drop-3"));
      const left = await until(() => resting([args[1]]));
      return {ok, during, left, after: state(args[1])};""", [first, second], selected)
    check("the selected tab stays shown and loaded when its folder closes", r["ok"] and r["during"] == ["shown/loaded", "hidden/unloaded"], str(r))
    check("leaving a tab in a closed folder hides and unloads it", r["left"], str(r))

    # Selected again, Firefox shows and loads it; left again, it rests again.
    r = m.js(REST + """const w = main(), t = rep(w, args[0]), back = w.gBrowser.selectedTab;
      w.gBrowser.selectedTab = t;
      const shown = await until(() => !t.hidden && t.linkedPanel && t.linkedBrowser.browsingContext?.currentWindowContext); await wait(500);
      const during = state(args[0]), folder = args[1].map(state);
      w.gBrowser.selectedTab = back;
      return {shown, during, folder, left: await until(() => resting([args[0]])), after: state(args[0])};""", selected, [first, second])
    check("selecting a resting tab shows and loads it, and only it", r["shown"] and r["during"][0] == "shown/loaded" and all(x == ["hidden/unloaded", "hidden/unloaded"] for x in r["folder"]), str(r))
    check("left again, it rests again", r["left"], str(r))

    # Selected in the other window: the real tab comes along, loaded; left there, it rests there.
    r = m.js(REST + """const w = rest(), back = w.gBrowser.selectedTab; w.focus(); await wait(800);
      w.gBrowser.selectedTab = rep(w, args[0]);
      // The placeholder it leaves behind unloads itself once it shows its icon.
      const came = await until(() => same(roles(args[0]), ["ghost/unloaded", "live/loaded"]) && same(state(args[0]), ["hidden/unloaded", "shown/loaded"]) && !url(rep(w, args[0])).includes("ghost.html"));
      const during = {roles: roles(args[0]), state: state(args[0]), selected: rep(w, args[0]).selected};
      w.gBrowser.selectedTab = back;
      const left = await until(() => resting([args[0]]));
      main().focus(); await wait(800);
      return {came, during, left, after: state(args[0])};""", first)
    check("a resting tab selected in another window comes loaded, and its placeholder is hidden", r["came"] and r["during"]["selected"], str(r))
    check("left in that window, it rests there", r["left"], str(r))

    # Dropped on the closed folder's head, with a real drag: it rests, and the folder stays closed.
    drop = sidebar_page(m, """
      const head = [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "Resting");
      const from = doc.querySelector(`#tabs .tab[data-tab="${args[0]}"]`);
      const data = new page.DataTransfer(), box = head.getBoundingClientRect();
      const at = {bubbles: true, cancelable: true, clientX: box.left + 5, clientY: box.top + 5, dataTransfer: data};
      from.dispatchEvent(new page.DragEvent("dragstart", at));
      head.dispatchEvent(new page.DragEvent("dragover", at));
      head.dispatchEvent(new page.DragEvent("drop", at));
      from.dispatchEvent(new page.DragEvent("dragend", at));
      await wait(50);
      return 1;""", s["drop"][0])
    r = m.js(REST + """const all = (await storage("%s", ["syncedTabs"])).syncedTabs, k = () => Object.keys(all).find(k => !args[1].includes(k) && all[k].parentKey === args[0]);
      let dropped; await until(() => { for (const w of wins()) for (const t of w.gBrowser.tabs) if (url(t).includes("smoke-drop-1")) dropped = JSON.parse(key(w, t)); return dropped; });
      const ok = await until(() => resting([dropped]));
      return {ok, dropped, tabs: state(dropped), url: url(rep(main(), dropped))};""" % EXT_ID, s["key"], keys)
    check("a tab dropped on a closed folder's head is hidden and unloaded, in both windows", r["ok"], str(r))
    dropped = r["dropped"]
    r = sidebar_page(m, """await wait(500); const f = folders().find(f => f.name === "Resting"), head = [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "Resting");
      return {collapsed: f.collapsed, count: head.querySelector(".count").textContent};""")
    check("the folder stays closed, and counts the tab", r == {"collapsed": True, "count": "4"}, str(r))

    # What keeps working stays loaded: a page with unsaved input refuses, without asking,
    # and a tab playing sound is left alone. Hidden, both.
    r = m.js(REST + """const w = main(), selected = w.gBrowser.selectedTab;
      const typed = w.gBrowser.addTrustedTab(args[0] + "/unsaved", {userContextId: args[1], inBackground: true});
      await until(() => key(w, typed) && typed.linkedPanel);
      await wait(800);
      const loud = w.gBrowser.tabs.find(t => url(t).includes("smoke-drop-2"));
      loud.setAttribute("soundplaying", "true");
      return {typed: JSON.parse(key(w, typed)), loud: JSON.parse(key(w, loud))};""", m.pages, ctx)
    ids = sidebar_page(m, """const tabs = [...await page.browser.tabs.query({})];
      const typed = tabs.find(t => t.url.includes("/unsaved")), loud = tabs.find(t => t.url.includes("smoke-drop-2"));
      send({type: "moveTab", tabId: typed.id, folder: args[0], before: null}); await wait(300);
      send({type: "moveTab", tabId: loud.id, folder: args[0], before: null}); await wait(300);
      return {typed: typed.id, loud: loud.id, audible: loud.audible};""", s["key"])
    t = m.js(REST + """const w = main(), selected = w.gBrowser.selectedTab, was = url(selected);
      const ok = await until(() => state(args[0])[0].startsWith("hidden") && state(args[1])[0].startsWith("hidden"));
      await wait(1500);
      return {ok, typed: state(args[0]), loud: state(args[1]), selected: url(w.gBrowser.selectedTab) === was};""", r["typed"], r["loud"])
    check("Firefox reports the test's tab as playing sound", ids["audible"] is True, str(ids))
    check("a page with unsaved input is hidden and stays loaded, without asking", t["ok"] and t["typed"] == ["hidden/loaded", "hidden/unloaded"] and t["selected"], str(t))
    check("a tab playing sound is hidden and stays loaded", t["loud"] == ["hidden/loaded", "hidden/unloaded"], str(t))
    # Out again, and gone: shown again everywhere, and still as it was.
    sidebar_page(m, """send({type: "moveTab", tabId: args[0], folder: null, before: null}); await wait(300);
      send({type: "moveTab", tabId: args[1], folder: null, before: null}); await wait(300); return 1;""", ids["typed"], ids["loud"])
    o = m.js(REST + """const shown = await until(() => [args[0], args[1]].every(k => state(k)[0] === "shown/loaded" && state(k)[1] === "shown/unloaded"));
      const during = each([args[0], args[1]]);
      main().gBrowser.removeTab(rep(main(), args[0]), {skipPermitUnload: true});
      await until(() => !rep(main(), args[0]) && !rep(rest(), args[0]));
      rep(main(), args[1]).removeAttribute("soundplaying");
      return {shown, during};""", r["typed"], r["loud"])
    check("a tab moved out of a closed folder is shown again", o["shown"], str(o))

    # Deleting a closed folder gives its tabs back, shown and unloaded.
    sidebar_page(m, """send({type: "deleteFolder", key: args[0]}); await wait(50); return 1;""", s["key"])
    gone = keys + [dropped]
    r = m.js(REST + """const ok = await until(() => resting(args[0], ["shown/unloaded", "shown/unloaded"])); return {ok, tabs: each(args[0])};""", gone)
    check("deleting a closed folder shows its tabs again, unloaded", r["ok"], str(r))
    m.js(REST + """const w = main(); if (w.__beforeRest && !w.__beforeRest.closing) w.gBrowser.selectedTab = w.__beforeRest; await wait(300);
      for (const k of args[0]) { const t = rep(w, k); if (t) w.gBrowser.removeTab(t); await wait(100); }
      await until(() => args[0].every(k => !rep(w, k) && !rep(rest(), k))); return 1;""", gone)

    # Left closed, for the checks after an update and a restart (alone_folds_rest_kept).
    s = sidebar_page(m, """
      send({type: "newFolder", space: args[0], name: "Resting still"}); await wait(1000);
      const key = [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "Resting still").dataset.folderHead;
      const tab = [...await page.browser.tabs.query({})].find(t => t.url.includes("smoke-drop-2"));
      send({type: "moveTab", tabId: tab.id, folder: key, before: null}); await wait(1200);
      return {key};""", s["space"])
    click_head("Resting still")
    r = m.js(REST + """const all = (await storage("%s", ["syncedTabs"])).syncedTabs, k = Object.keys(all).find(k => all[k].parentKey === args[0]);
      return {k, ok: await until(() => resting([k])), tabs: state(k)};""" % EXT_ID, s["key"])
    check("another folder closes the same way, to stay closed", r["ok"], str(r))
    # A window you close and reopen comes back with its tabs hidden as they were. Reopened,
    # it knows them only once Tidier has taken them back, which is after it showed them.
    k = r["k"]
    r = m.js(REST + """await close(rest()); main().focus(); await wait(500);
      const w = main().SessionStore.undoCloseWindow(0); w.__rest = w.__extra = true;
      for (let i = 0; i < 200 && !w.gBrowser; i++) await wait(50);
      // Past the moment it is taken back, or a tab that was shown later would not be seen.
      for (let i = 0; i < 200 && !tabsOf(w, args[0]).length; i++) await wait(50);
      await wait(3000);
      return {ok: await until(() => resting([args[0]])), tabs: state(args[0])};""", k)
    check("a closed folder's tabs stay hidden in a window you reopen", r["ok"], str(r))
    m.js(REST + "await close(rest()); main().focus(); await wait(500); return 1;")
    no_problems(m, "with closed folders")


def alone_folds_rest_kept(m):
    # Firefox shows every hidden tab again at an update, and a start only hides (nothing is
    # unloaded then): a closed folder's tabs are hidden again by the time Tidier has started.
    r = m.js(H + """const all = (await storage("%s", ["syncedTabs"])).syncedTabs, f = Object.keys(all).find(k => all[k].name === "Resting still");
      const ks = Object.keys(all).filter(k => f && all[k].parentKey === f).map(k => JSON.stringify(k));
      const tabs = () => wins().flatMap(w => w.gBrowser.tabs.filter(t => ks.includes(key(w, t))).map(t => (t.hidden ? "hidden" : "shown") + (t.linkedPanel ? "/loaded" : "/unloaded")));
      for (let i = 0; i < 300 && !(tabs().length && tabs().every(t => t === "hidden/unloaded")); i++) await wait(50);
      return {f, tabs: tabs(), collapsed: f && all[f].collapsed};""" % EXT_ID)
    if not r["f"]:
        print("SKIP  alone_folds_rest_kept (needs alone_folds_rest before it)", flush=True)
        return
    check("a closed folder stays closed and its tabs hidden and unloaded, also after an update and a restart", r["collapsed"] and r["tabs"] and all(t == "hidden/unloaded" for t in r["tabs"]), str(r))
