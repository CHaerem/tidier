"""Spaces: switching, their keys and menu, and what Firefox Sync carries."""
import json
import re
import time
from testfirefox import EXT_ID
from smokechecks.base import (
    CTRL, ENTER, ESC, H, SNAP_ALONE, check, choose, ext_page,
    extension_message, in_sidebar, menu_on, no_problems, press, seen, sidebar_key, sidebar_mouse,
    sidebar_page, sidebar_until, until,
)
from smokechecks.core import essentials


def alone_setup(m):
    r = m.js(H + """const w = main(); await wait(1500);
      return {panel: w.SidebarController.currentID, hidden: w.gBrowser.tabs.filter(t => t.hidden).length, visible: w.gBrowser.tabs.filter(t => !t.hidden).length};""")
    check("Tidier's sidebar is the sidebar", "6844a953" in (r["panel"] or ""), str(r))
    check("Tidier hides the other spaces' tabs", r["hidden"] > 0, str(r))


def alone_second_window(m):
    # A new window gets every essential and tab, in one go.
    r = m.js(H + """const a = main(), pinned0 = a.gBrowser.tabs.filter(t => t.pinned).length, want = a.gBrowser.tabs.filter(t => !t.pinned && role(a, t)).length;
      const t0 = Date.now(), w = a.OpenBrowserWindow(); w.__smoke = true;
      let ms = null;
      for (let i = 0; i < 200 && ms === null; i++) { await wait(50);
        if (w.gBrowser && w.gBrowser.tabs.filter(t => t.pinned).length >= pinned0 && w.gBrowser.tabs.filter(t => !t.pinned && role(w, t)).length >= want) ms = Date.now() - t0; }
      await wait(3000);
      const loaded = w.gBrowser.tabs.filter(t => t.linkedPanel && !t.selected && url(t).includes("ghost.html")).map(t => t.label);
      return {ms, want: [pinned0, want], got: [w.gBrowser.tabs.filter(t => t.pinned).length, w.gBrowser.tabs.filter(t => !t.pinned && role(w, t)).length], loaded,
              pins: w.gBrowser.tabs.filter(t => t.pinned).map(t => t.userContextId), hidden: w.gBrowser.tabs.filter(t => t.hidden).length};""")
    check(f"a new window gets every essential and tab ({r['ms']} ms)", r["want"] == r["got"] and r["ms"] is not None, str(r))
    check("a new window's placeholders unload", not r["loaded"], str(r))
    check("a new window shows one space", r["hidden"] > 0, str(r))

    # Going to a space in the new window takes you to the tab you used last there, in the
    # first window: not the placeholder made last, nor a tab opened there in the background.
    r = m.js(H + """const a = main(), b = other(); a.focus(); await wait(300);
      const {ExtensionParent} = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
      const used = a.gBrowser.tabs.find(t => url(t).includes("fixture-tab-2-1"));
      a.gBrowser.selectedTab = used; await wait(1200);
      a.gBrowser.selectedTab = a.gBrowser.tabs.find(t => url(t).includes("fixture-tab-1-1")); await wait(1200);
      a.gBrowser.addTrustedTab(args[0], {userContextId: 2, inBackground: true}); await wait(2500);
      b.focus(); await wait(300);
      return {key: key(a, used), window: ExtensionParent.apiManager.global.windowTracker.getId(b)};""", m.pages + "/r/behind-opened")  # (not "/r/opened…": alone_crossing looks for that one's requests)
    sidebar_page(m, """const p = page.browser.runtime.connect({name: "sidebar"}), say = msg => p.postMessage(page.JSON.parse(JSON.stringify(msg)));
      say({type: "hello", windowId: args[0]}); await wait(100); say({type: "space", space: "firefox-container-2"}); await wait(1500); p.disconnect();""", r["window"])
    # (The test's own page has taken the focus: the page comes as you go to that window.)
    got = m.js(H + """const a = main(), b = other(); b.focus(); await wait(1500); const on = b.gBrowser.selectedTab;
      const got = {key: key(b, on), space: on.userContextId, loaded: !!on.linkedPanel && url(on).includes("fixture-tab-2-1"), firstStays: url(a.gBrowser.selectedTab).includes("fixture-tab-1-1"),
                   behind: wins().some(w => url(w.gBrowser.selectedTab).includes("behind-opened"))};
      await removeWhere((w, t) => url(t).includes("behind-opened")); a.focus(); await wait(300); return got;""")
    check("in a new window, going to a space lands on the tab you used last there, with its page", got.get("key") == r["key"] and got.get("loaded"), f"{r} {got}")
    check("not on a tab opened there in the background since, and the first window stays where it is", not got.get("behind") and got.get("firstStays"), str(got))

    # Closed and reopened (⌘⇧N): the window comes back in its own space, on its own tab, and
    # the window you are in keeps its tab. Its pages loading again are no news, and an
    # essential you had unloaded, with its page, stays unloaded: sent to its placeholder, it
    # was loaded first, and what its title said on the way was taken for news.
    r = m.js(H + """const a = main(), b = other(); a.focus(); await wait(300);
      const was = {key: key(b, b.gBrowser.selectedTab), space: b.gBrowser.selectedTab.userContextId, mine: key(a, a.gBrowser.selectedTab)};
      const asleep = a.gBrowser.tabs.find(t => t.pinned && !t.selected && t.linkedPanel && /^https?:/.test(url(t)));
      if (asleep) { a.gBrowser.discardBrowser(asleep); await wait(500); }
      b.gBrowser.selectedTab.toggleMuteAudio(); await wait(300); // you muted the page there
      await close(b); a.focus(); await wait(1500);
      const heir = a.gBrowser.tabs.find(t => key(a, t) === was.key), heirMuted = !!heir?.muted;
      const w = a.SessionStore.undoCloseWindow(0); w.__smoke = true;
      for (let i = 0; i < 100 && !(w.gBrowser && w.gBrowser.tabs.length > 2); i++) await wait(100);
      await wait(7000); // past news's five seconds of quiet
      return {...was, back: key(w, w.gBrowser.selectedTab), backSpace: w.gBrowser.selectedTab.userContextId, mineNow: key(a, a.gBrowser.selectedTab),
              asleep: asleep ? {still: !asleep.linkedPanel && /^https?:/.test(url(asleep))} : null, heirMuted,
              loaded: wins().flatMap(x => x.gBrowser.tabs.filter(t => t.pinned && t.linkedPanel && !url(t).includes("ghost.html")).map(t => key(x, t) ?? ek(x, t))).length};""")
    marks = extension_message(m, {"type": "stats"})["sizes"].get("newsMarks")
    check("a muted page whose window closes stays muted in the window that takes it over", r.get("heirMuted"), str(r))
    check("a window reopened with ⌘⇧N is back in its own space, on its own tab", r.get("back") == r.get("key") and r.get("backSpace") == r.get("space"), str(r))
    check("and the window you are in keeps its tab", r.get("mineNow") == r.get("mine"), str(r))
    check("(an essential with its page, unloaded, to see what a reopen does with it)", r.get("asleep") is not None, str(r))
    check("an unloaded essential stays unloaded when a window is reopened", (r.get("asleep") or {}).get("still"), str(r))
    check("its pages loading again put no news marks anywhere", marks == 0, f"{marks} {r}")


def alone_spaces(m):
    r = sidebar_page(m, """
      await wait(500);
      const before = spaces(), other = before.find(s => !s.active);
      doc.querySelector(`#spaces .space[data-space="${other.id}"]`).click();
      await wait(1500);
      return {before, after: spaces(), wanted: other.id, essentials: tiles().length, name: doc.getElementById("space-name").textContent};""")
    check("the bar shows the spaces, and one is active", len(r["before"]) >= 3 and sum(s["active"] for s in r["before"]) == 1, str(r))
    check("the bar switches space", [s["id"] for s in r["after"] if s["active"]] == [r["wanted"]], str(r))
    check("a space shows its own essentials and its name", r["essentials"] == 2 and r["name"], str(r))
    # A space comes in as one piece: its folders do not fade in after everything else, as a
    # folder that appears does (sidebar.css). Their opacity as soon as they are there.
    m.js(H + "main().__selectedBefore = main().gBrowser.selectedTab; return 1;")
    r = sidebar_page(m, """
      const list = doc.getElementById("tabs"), seen = [];
      const back = spaces().find(s => s.active).id, other = spaces().find(s => !s.active && s.id !== "firefox-container-4").id;
      const before = new Set([...list.querySelectorAll(".folder")].map(f => f.dataset.key));
      send({type: "newFolder", space: back});
      for (let i = 0; i < 50 && list.querySelectorAll(".folder").length === before.size; i++) await wait(100);
      const made = [...list.querySelectorAll(".folder")].find(f => !before.has(f.dataset.key))?.dataset.key;
      await wait(500);
      const o = new page.MutationObserver(() => { for (const c of list.querySelectorAll(".folder > .children")) seen.push(Number(page.getComputedStyle(c).opacity)); });
      o.observe(list, {childList: true});
      doc.querySelector(`#spaces .space[data-space="${other}"]`).click(); await wait(1200);
      doc.querySelector(`#spaces .space[data-space="${back}"]`).click(); await wait(1200);
      o.disconnect();
      const folders = list.querySelectorAll(".folder").length;
      if (made) { send({type: "deleteFolder", key: made}); await wait(800); }
      return {seen, folders, made: !!made, marked: [...doc.documentElement.classList].filter(c => c !== "alone")};""")
    check("a space comes in at once, its folders too, and nothing stays marked", r["folders"] and r["seen"] and min(r["seen"]) == 1 and r["marked"] == [], str(r))
    # What you click shows as selected at once, and the view then agrees.
    r = sidebar_page(m, """
      const shown = () => [...doc.querySelectorAll("#tabs .tab")].filter(e => e.offsetParent && e.querySelector(".title").textContent !== "Tidier");
      const rows = shown(), next = rows.find(e => !e.classList.contains("active")), at = rows.indexOf(next), title = next.querySelector(".title").textContent;
      next.click();
      const atOnce = {next: next.classList.contains("active"), others: doc.querySelectorAll("#tabs .tab.active, #essentials .active").length};
      await wait(1500);
      // By its place and title: a placeholder clicked has its page pulled in, under another
      // tab id (tabsync.js), so its row is a new one.
      const now = shown(), active = now.filter(e => e.classList.contains("active"));
      return {atOnce, title, after: active.length === 1 && now.indexOf(active[0]) === at && active[0].querySelector(".title").textContent === title};""")
    check("a clicked row shows as selected at once, and stays so", r["atOnce"] == {"next": True, "others": 1} and r["after"], str(r))
    # So does a tab selected without the sidebar (a key, Firefox's own tab strip): marked when
    # Firefox tells of it, not a view later. Read in a listener added after the sidebar's own,
    # which Firefox calls right after it, before any view can have come.
    r = sidebar_page(m, """
      const shown = () => [...doc.querySelectorAll("#tabs .tab")].filter(e => e.offsetParent && e.querySelector(".title").textContent !== "Tidier");
      const rows = shown(), next = rows.find(e => !e.classList.contains("active")), at = rows.indexOf(next), title = next.querySelector(".title").textContent, id = Number(next.dataset.tab);
      let atOnce = null;
      const heard = ({tabId}) => { if (tabId === id && !atOnce) atOnce = {next: next.classList.contains("active"), others: doc.querySelectorAll("#tabs .tab.active, #essentials .active").length}; };
      page.browser.tabs.onActivated.addListener(heard);
      await page.browser.tabs.update(id, page.JSON.parse('{"active": true}'));
      await wait(1500);
      page.browser.tabs.onActivated.removeListener(heard);
      const now = shown(), active = now.filter(e => e.classList.contains("active"));
      return {atOnce, title, after: active.length === 1 && now.indexOf(active[0]) === at && active[0].querySelector(".title").textContent === title};""")
    m.js(H + "const w = main(); w.gBrowser.selectedTab = w.__selectedBefore; delete w.__selectedBefore; await wait(800); return 1;")  # back where it was, for what follows
    check("a tab selected with a key shows as selected at once in the sidebar, and stays so", r.get("atOnce") == {"next": True, "others": 1} and r.get("after"), str(r))
    shown = m.js(H + """const w = main(), selected = w.gBrowser.selectedTab;
      return {space: selected.userContextId, shown: [...new Set(w.gBrowser.tabs.filter(t => !t.pinned && !t.hidden && t.userContextId).map(t => t.userContextId))],
              ctrlTab: w.gBrowser.visibleTabs.filter(t => !t.pinned && t.userContextId && t.userContextId !== selected.userContextId).length};""")
    check("switching hides the other spaces' tabs and shows this one's", shown["shown"] == [shown["space"]] and shown["ctrlTab"] == 0, str(shown))
    r = m.js(H + """const w = main(); w.focus(); await wait(300); const space = w.gBrowser.selectedTab.userContextId;
      // ⌘T: Firefox opens a tab without a container, Tidier opens it again in the space.
      const t = w.gBrowser.addTrustedTab("about:newtab"); w.gBrowser.selectedTab = t; await wait(1500);
      const s = w.gBrowser.selectedTab, got = {space, newTab: s.userContextId, page: url(s), gone: !t.linkedBrowser};
      w.gBrowser.removeTab(s); await wait(800);
      got.afterClose = w.gBrowser.selectedTab.userContextId;
      // A link from another app: an address, without a container.
      const l = w.gBrowser.addTrustedTab("https://example.org/?smoke-alone-link", {inBackground: false}); await wait(4000);
      got.link = wins().map(x => x.gBrowser.tabs.filter(y => url(y).includes("smoke-alone-link")).map(y => y.userContextId));
      await removeWhere((x, y) => url(y).includes("smoke-alone-link") || (y.linkedBrowser && value(x, y, "syncKey") && String(y.label).includes("smoke-alone-link")));
      return got;""")
    check("a new tab opens in the active space", r["newTab"] == r["space"], str(r))
    check("closing it stays in the space", r["afterClose"] == r["space"], str(r))
    check("a link without a container opens in the active space", r["link"][0] == [r["space"]], str(r))
    # An empty space: a new tab there, and closing the last tab stays there.
    r = sidebar_page(m, """
      const empty = doc.querySelector('#spaces .space[data-space="firefox-container-4"]');
      if (!empty) return {missing: true};
      empty.click();
      await wait(1500);
      return {active: spaces().find(s => s.active).id};""")
    check("an empty space can be switched to", r.get("active") == "firefox-container-4", str(r))
    r = m.js(H + """const w = main(); w.focus();
      for (const t of [...w.gBrowser.tabs]) if (url(t).includes("/sidebar/sidebar.html")) w.gBrowser.removeTab(t);  // the test's own
      await wait(500);
      const before = w.gBrowser.selectedTab, got = {before: before.userContextId};
      w.gBrowser.removeTab(before); await wait(1500);
      got.after = w.gBrowser.selectedTab.userContextId;
      got.page = url(w.gBrowser.selectedTab);
      return got;""")
    check("closing the last tab of a space stays in the space, with a new tab", r["before"] == 4 and r["after"] == 4, str(r))
    press(m, "1", CTRL)
    time.sleep(1)
    m.js(H + """const w = main(); await removeWhere((x, t) => !t.pinned && t.userContextId === 4); return 1;""")


def alone_keys(m):
    r = []
    for digit in ("1", "2", "3"):
        press(m, digit, CTRL)
        time.sleep(1)
        r.append(m.js(H + "const w = main(); return {selected: w.gBrowser.selectedTab.userContextId, shown: [...new Set(w.gBrowser.tabs.filter(t => !t.pinned && !t.hidden && t.userContextId).map(t => t.userContextId))]};"))
    check("⌃1, ⌃2 and ⌃3 switch space", len({x["selected"] for x in r}) == 3 and all(x["shown"] == [x["selected"]] for x in r), str(r))


def alone_sync_hide(m):
    # Through the real storage.sync. In a test Firefox it reaches no server, so another machine is played
    # by writing what it would write there, which fires onChanged as Firefox Sync does.
    settings = "/settings/settings.html"
    sidebar_page(m, """
      send({type: "newFolder", space: spaces().find(s => s.active).id, name: "Synced folder"});
      await wait(1000);
      const key = [...doc.querySelectorAll("#tabs .folder .head")].at(-1).dataset.folderHead;
      send({type: "moveTab", tabId: Number(plainTabs()[0].dataset.tab), folder: key, before: null});
      await wait(2000);
      return key;""")
    r = ext_page(m, settings, """
      await wait(800);
      const tick = doc.getElementById("sync-on");
      const before = {shown: !doc.getElementById("sync-section").hidden, on: tick.checked, items: Object.keys(await page.browser.storage.sync.get(null)).length};
      // Firefox's limits, as MDN gives them: the key's length plus the value as JSON.
      const sync = page.browser.storage.sync, fits = async o => sync.set(page.JSON.parse(JSON.stringify(o))).then(() => true, () => false);
      const size = (key, n) => ({[key]: "x".repeat(n - key.length - 2)});
      const limits = {item: await fits(size("limit-a", 8192)), itemOver: await fits(size("limit-b", 8193))};
      const many = {}; for (let i = 0; i < 12; i++) Object.assign(many, size("limit-m" + i, 8000));
      await sync.clear();
      limits.total = await fits(many);
      limits.totalOver = await fits(size("limit-n", 8000));
      await sync.clear();
      const small = {}; for (let i = 0; i < 512; i++) small["limit-" + i] = 1;
      limits.items = await fits(small);
      limits.itemsOver = await fits({"limit-one-more": 1});
      await sync.clear();
      tick.click();
      for (let i = 0; i < 100 && !/KB of/.test(doc.getElementById("sync-state").textContent); i++) await wait(100);
      return {before, limits, state: doc.getElementById("sync-state").textContent, items: JSON.parse(JSON.stringify(await sync.get(null))), bytes: await sync.getBytesInUse(null)};""")
    check("sync is off by default, on the settings page, with nothing written", r["before"] == {"shown": True, "on": False, "items": 0}, str(r["before"]))
    check("Firefox's limits are what Tidier counts on: 8192 per item, 102400 in all, 512 items",
          r["limits"] == {"item": True, "itemOver": False, "total": True, "totalOver": False, "items": True, "itemsOver": False}, str(r["limits"]))
    text = json.dumps(r["items"])
    check("turned on, the page says how much is used", "KB of the 100 KB" in r["state"] and r["bytes"] > 0, r["state"])
    check("essentials, folders and saved tabs go into storage.sync, with no container id and no icon",
          all(f'["{kind}",' in text for kind in "eft") and "firefox-container" not in text and "favicon" not in text and "data:image" not in text, text[:300])
    rows = {row[3]: row for row in r["items"].get("1/m.0", []) if row[0] == "s"}
    check("the spaces go by name", {"Space 1", "Space 2", "Space 3"} <= set(rows), str(sorted(rows)))
    sid = rows["Space 2"][1]
    now = int(time.time() * 1000) + 1000

    def from_elsewhere(items):
        ext_page(m, settings, "await page.browser.storage.sync.set(page.JSON.parse(JSON.stringify(args[0]))); return 1;", items)

    # A real Firefox refuses a whole write with half a character in it, and sync cuts long titles.
    m.js(H + """const w = main(), t = w.gBrowser.addTrustedTab(args[0] + "/long-title", {userContextId: 1, inBackground: true});
      await wait(2500); w.gBrowser.pinTab(t); return 1;""", m.pages)
    r = ext_page(m, settings, """let items; for (let i = 0; i < 100; i++) { items = await page.browser.storage.sync.get(null); if (JSON.stringify(items).includes("/long-title")) break; await wait(200); }
      return {written: JSON.stringify(items).includes("/long-title"), state: doc.getElementById("sync-state").textContent};""")
    check("a title cut just where a character is goes into storage.sync like any other", r["written"] and "Stopped" not in r["state"], str(r))
    m.js(H + """for (const w of wins()) for (const t of [...w.gBrowser.tabs]) if (t.pinned && url(t).includes("/long-title")) w.gBrowser.unpinTab(t);
      await wait(2500); await removeWhere((w, t) => url(t).includes("/long-title")); return 1;""")

    # An essential added on another machine: in every window, unloaded, in the container called that here.
    from_elsewhere({f"1/{sid}.77": [["e", "smoke-synced", now, "https://example.org/?smoke-synced", "From elsewhere"]]})
    r = until(m, """const got = wins().map(w => w.gBrowser.tabs.filter(t => t.pinned && ek(w, t) === "smoke-synced").map(t => [t.userContextId, !!t.linkedPanel && !t.selected]));
      return {ok: got.every(g => g.length === 1) && got.every(g => !g[0][1]), got};""")
    check("an essential from another machine arrives in every window, in the right container, and unloads", r["ok"] and all(g[0][0] == 2 for g in r["got"]), str(r))
    r = ext_page(m, settings, """
      for (let i = 0; i < 100; i++) { const items = await page.browser.storage.sync.get(null); if (!Object.keys(items).some(k => k.endsWith(".77"))) break; await wait(200); }
      const items = await page.browser.storage.sync.get(null);
      return {keys: Object.keys(items), has: JSON.stringify(items).includes("smoke-synced")};""")
    check("it is written back in Tidier's own items, and the other machine's is taken over", r["has"] and not any(k.endswith(".77") for k in r["keys"]), str(r))

    # A folder and a saved tab from another machine.
    from_elsewhere({f"1/{sid}.76": [["f", "smoke-folder", now, "Folder from elsewhere"], ["t", "smoke-saved", now, "https://example.org/?smoke-saved", "Saved elsewhere", "smoke-folder"]]})
    r = until(m, """const got = wins().map(w => w.gBrowser.tabs.filter(t => key(w, t) === '"smoke-saved"').map(t => [t.userContextId, role(w, t), !!t.linkedPanel && !t.selected]));
      return {ok: got.every(g => g.length === 1) && got.every(g => !g[0][2]), got};""")
    check("a folder's saved tab from another machine arrives in every window, in the right container, and unloads", r["ok"] and all(g[0][0] == 2 for g in r["got"]), str(r))
    from_elsewhere({f"1/{sid}.76": [["F", "smoke-folder", now + 1000, None, "Folder from elsewhere"], ["T", "smoke-saved", now + 1000]]})
    r = until(m, """const all = (await storage(args[1], ["syncedTabs"])).syncedTabs;
      const got = wins().map(w => w.gBrowser.tabs.filter(t => key(w, t) === '"smoke-saved"').length);
      return {ok: got.every(g => g === 0) && !all["smoke-folder"] && !all["smoke-saved"], got};""", EXT_ID)
    check("deleted on another machine, they go", r["ok"], str(r))

    # Renamed elsewhere: the same container, and what is in it stays.
    from_elsewhere({f"1/{sid}.78": [["s", sid, now + 2000, "Renamed elsewhere", rows["Space 2"][4], rows["Space 2"][5]]]})
    r = ext_page(m, settings, """
      let name; for (let i = 0; i < 100; i++) { name = (await page.browser.contextualIdentities.query({})).find(c => c.cookieStoreId === "firefox-container-2")?.name; if (name === "Renamed elsewhere") break; await wait(200); }
      return name;""")
    check("a space renamed on another machine is renamed here", r == "Renamed elsewhere", str(r))
    from_elsewhere({f"1/{sid}.78": [["s", sid, now + 4000, "Space 2", rows["Space 2"][4], rows["Space 2"][5]]]})
    r = ext_page(m, settings, """
      let name; for (let i = 0; i < 100; i++) { name = (await page.browser.contextualIdentities.query({})).find(c => c.cookieStoreId === "firefox-container-2")?.name; if (name === "Space 2") break; await wait(200); }
      return name;""")
    # Deleted elsewhere: the copies go, and only the copies.
    pinned_before = m.js(H + 'return wins().map(w => w.gBrowser.tabs.filter(t => t.pinned && ek(w, t) !== "smoke-synced").length);')
    from_elsewhere({f"1/{sid}.79": [["E", "smoke-synced", now + 6000]]})
    # Until it is out of the record as well, which is written a moment after its copies have gone:
    # the hiding checks below compare the record before and after.
    r = until(m, """const got = wins().map(w => w.gBrowser.tabs.filter(t => t.pinned).map(t => ek(w, t)));
      const stored = (await storage(args[1], ["essentials"])).essentials.some(e => e.key === "smoke-synced");
      return {ok: got.every(g => !g.includes("smoke-synced")) && !stored, got: got.map(g => g.length), stored};""", EXT_ID)
    check("an essential deleted on another machine goes from every window, and nothing else does", r["ok"] and r["got"] == pinned_before, f"{r}, {pinned_before}")

    # Hiding: the space you are in, from the settings page.
    before = m.js(SNAP_ALONE)
    space = m.js(H + "return main().gBrowser.selectedTab.userContextId;")
    name = f"Space {space}"
    stored_before = m.js(H + """const s = await storage("%s", ["essentials", "syncedTabs"]);
      return {essentials: s.essentials.filter(e => e.cookieStoreId === args[0]).map(e => e.key).sort(), saved: Object.keys(s.syncedTabs).filter(k => s.syncedTabs[k].cookieStoreId === args[0]).sort()};""" % EXT_ID, f"firefox-container-{space}")
    click_tick = """const line = [...doc.querySelectorAll("#spaces-here label")].find(l => l.textContent.includes(args[0]));
      line.querySelector("input").click(); await wait(300);"""
    tab_order = """const n = args[0]; return main().gBrowser.tabs.filter(t => !t.pinned && t.userContextId === n).map(t => key(main(), t));"""
    order_before = m.js(H + tab_order, space)
    open_pages = m.js(H + """const n = args[0]; return wins().flatMap(w => w.gBrowser.tabs.filter(t => t.userContextId === n && t.linkedPanel && url(t).startsWith("http")).map(url));""", space)
    # One page in it holds unsaved input: that one must stay, and be where you can reach it.
    unsaved = m.js(H + """const w = main(), t = w.gBrowser.addTrustedTab(args[0] + "/unsaved", {userContextId: args[1], inBackground: true});
      await wait(4000); return key(w, t);""", m.pages, space)
    ext_page(m, settings, click_tick + "return 1;", name)
    r = until(m, """const n = args[1], k = args[2];
      const others = wins().flatMap(w => w.gBrowser.tabs.filter(t => t.userContextId === n && key(w, t) !== k && !url(t).includes("/settings/")).map(t => t.label));
      const selected = wins().map(w => w.gBrowser.selectedTab.userContextId);
      const kept = main().gBrowser.tabs.filter(t => url(t).includes("/unsaved")).map(t => t.hidden);
      return {ok: !others.length && !selected.includes(n), others, selected, kept};""", space, unsaved)
    check("a hidden space has no other tab in any window, and every window has left it", r["ok"], str(r))
    check("a page with unsaved input stays open, and is not hidden away", r["kept"] == [False], str(r))
    r = ext_page(m, settings, "await wait(1000); return (await page.browser.sessions.getRecentlyClosed({})).map(c => c.tab?.url);")
    check("hiding is not closing: its pages are not in Recently Closed", open_pages and not set(open_pages) & set(r), f"{open_pages}, {r}")
    # Closed, it goes like any tab, and the rest stays as it was.
    r = until(m, """const n = args[1], k = args[2];
      for (const w of wins()) for (const t of [...w.gBrowser.tabs]) if (key(w, t) === k) w.gBrowser.removeTab(t, {skipPermitUnload: true});
      const left = wins().flatMap(w => w.gBrowser.tabs.filter(t => t.userContextId === n && !url(t).includes("/settings/")).map(t => t.label));
      return {ok: !left.length, left};""", space, unsaved)
    check("closed, it leaves the hidden space with no tab at all", r["ok"], str(r))
    r = sidebar_page(m, "await wait(500); return {spaces: spaces(), name: doc.getElementById('space-name').textContent};")
    check("a hidden space has no dot on the bar", f"firefox-container-{space}" not in [s["id"] for s in r["spaces"]] and len(r["spaces"]) >= 2 and sum(s["active"] for s in r["spaces"]) == 1, str(r))
    stored = m.js(H + """const s = await storage("%s", ["essentials", "syncedTabs", "hiddenSpaces"]);
      return {essentials: s.essentials.filter(e => e.cookieStoreId === args[0]).map(e => e.key).sort(), saved: Object.keys(s.syncedTabs).filter(k => s.syncedTabs[k].cookieStoreId === args[0]).sort(), hidden: s.hiddenSpaces};""" % EXT_ID, f"firefox-container-{space}")
    check("hiding deletes nothing: its essentials and tabs stay in the record", stored["essentials"] == stored_before["essentials"] and stored["saved"] == stored_before["saved"], f"{stored}, {stored_before}")
    # ⌃1, ⌃2 and ⌃3 skip it.
    seen = []
    for digit in ("1", "2", "3"):
        press(m, digit, CTRL)
        time.sleep(1)
        seen.append(m.js(H + "return main().gBrowser.selectedTab.userContextId;"))
    check("⌃1, ⌃2 and ⌃3 skip a hidden space", space not in seen, str(seen))
    # A rule pointing at it: the tab opens in the space you are in. (A link from another app: no container.)
    extension_message(m, {"type": "settings:rules", "rules": [{"url": "smoke-hidden-rule", "space": f"firefox-container-{space}"}]})
    r = m.js(H + """const w = main(); w.focus(); await wait(300);
      const active = w.gBrowser.selectedTab.userContextId;
      w.gBrowser.addTrustedTab("https://example.org/?smoke-hidden-rule", {inBackground: false}); await wait(4000);
      const got = wins().flatMap(x => x.gBrowser.tabs.filter(y => url(y).includes("smoke-hidden-rule") || y.label.includes("smoke-hidden-rule")).map(y => y.userContextId));
      await removeWhere((x, y) => url(y).includes("smoke-hidden-rule"));
      return {active, got};""")
    check("a rule pointing at a hidden space opens the tab in the space you are in", r["got"] and space not in r["got"] and r["active"] in r["got"], str(r))
    extension_message(m, {"type": "settings:rules", "rules": []})
    # A page you open in it from Firefox's own menu: the record does not know it, so nothing could bring it back.
    other = next(n for n in (1, 2, 3) if n != space)
    m.js(H + """main().gBrowser.addTrustedTab(args[0] + "/ticking", {userContextId: args[1], inBackground: true}); await wait(3000); return 1;""", m.pages, space)
    ext_page(m, settings, click_tick + "return 1;", f"Space {other}")
    r = until(m, """const n = args[1], left = wins().flatMap(w => w.gBrowser.tabs.filter(t => t.userContextId === n).map(t => t.label));
      return {ok: !left.length, left, mine: main().gBrowser.tabs.filter(t => url(t).includes("/ticking")).length};""", other)
    check("a page you opened in a hidden container yourself stays when more is hidden", r["ok"] and r["mine"] == 1, str(r))
    ext_page(m, settings, click_tick + "return 1;", f"Space {other}")
    m.js(H + """await removeWhere((w, t) => url(t).includes("/ticking")); return 1;""")
    # It stays hidden after a restart, also where the session would bring something of it back.
    if m.can_restart:
        # (The test's own pages are closed first: restored unloaded, they could not be scripted.)
        m.js(H + """for (const w of wins()) for (const t of [...w.gBrowser.tabs]) if (url(t).includes("/settings/settings.html") || url(t).includes("/sidebar/sidebar.html")) w.gBrowser.removeTab(t); await wait(500); return 1;""")
        m.restart()
        m.js(H + """for (let i = 0; i < 100 && wins().length < 2; i++) await wait(200); await wait(12000); return 1;""")
        r = m.js(H + """const n = args[0]; return wins().flatMap(w => w.gBrowser.tabs.filter(t => t.userContextId === n && !url(t).includes("/settings/")).map(t => t.label));""", space)
        check("after a restart a hidden space still has no tab in any window", not r, str(r))
        r = sidebar_page(m, "await wait(500); return spaces();")
        check("after a restart it is still not on the bar", f"firefox-container-{space}" not in [s["id"] for s in r], str(r))
        r = ext_page(m, settings, "await wait(500); return doc.getElementById('sync-on').checked;")
        check("after a restart sync is still on", r is True, str(r))
    # And back.
    ext_page(m, settings, click_tick + "return 1;", name)
    r = until(m, """const n = args[1], want = args[2];
      const got = wins().map(w => w.gBrowser.tabs.filter(t => t.userContextId === n && t.pinned).length);
      return {ok: got.every(x => x === want), got};""", space, len(stored_before["essentials"]))
    check("shown again, its essentials are back in every window", r["ok"], str(r))
    def tabs_of(snap):
        return [(sorted(w["essentials"]), sorted(w["tabs"])) for w in snap["windows"]]
    r = until(m, """const all = (await storage(args[1], ["syncedTabs"])).syncedTabs, n = args[2];
      const keys = Object.keys(all).filter(k => all[k].cookieStoreId === "firefox-container-" + n && !all[k].group);
      const got = wins().map(w => keys.filter(k => w.gBrowser.tabs.some(t => key(w, t) === JSON.stringify(k))).length);
      return {ok: got.every(x => x === keys.length), got, want: keys.length};""", EXT_ID, space)
    check("shown again, its tabs are back in every window", r["ok"] and r["want"] > 0, str(r))
    order_after = m.js(H + tab_order, space)
    check("shown again, its tabs are in the order they were", order_after == order_before and order_before, f"{order_before}, {order_after}")
    # Declared for this machine, by name, in its managed storage file. Firefox reads that file once
    # each time Tidier starts, so Tidier is started again; which is also what an update does.
    def start_tidier_again():
        m.js(H + """const {AddonManager} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
          await (await AddonManager.getAddonByID(args[0])).reload(); await wait(9000); return 1;""", EXT_ID)
    with open(m.tidier_managed) as f:
        managed = json.load(f)
    as_found = json.dumps(managed)
    managed["data"]["hiddenSpaces"] = [f"Space {other}"]
    with open(m.tidier_managed, "w") as f:
        json.dump(managed, f)
    start_tidier_again()
    r = until(m, """const n = args[1], left = wins().flatMap(w => w.gBrowser.tabs.filter(t => t.userContextId === n).map(t => t.label));
      return {ok: !left.length, left};""", other)
    check("a space declared hidden for this machine by name leaves every window", r["ok"], str(r))
    r = ext_page(m, settings, "for (let i = 0; i < 50 && !/setup/.test(doc.getElementById('spaces-here').textContent); i++) await wait(100); return doc.getElementById('spaces-here').textContent;")
    check("the settings page says this machine's setup hides it", f"Space {other}: hidden by this machine's setup" in r, r)
    rename = "await page.browser.contextualIdentities.update(args[0], {name: args[1]}); await wait(1000); return 1;"
    ext_page(m, settings, rename, f"firefox-container-{other}", "Renamed here")
    r = sidebar_page(m, "await wait(500); return spaces();")
    check("renamed, it stays hidden: the name was all that said so", f"firefox-container-{other}" not in [x["id"] for x in r], str(r))
    ext_page(m, settings, rename, f"firefox-container-{other}", f"Space {other}")
    with open(m.tidier_managed, "w") as f:
        f.write(as_found)
    start_tidier_again()
    ext_page(m, settings, "for (let i = 0; i < 50 && !doc.querySelector('#spaces-here label input:not(:checked)'); i++) await wait(100);" + click_tick + "return 1;", f"Space {other}")
    r = until(m, """const n = args[1], left = main().gBrowser.tabs.filter(t => t.userContextId === n).length; return {ok: left > 0, left};""", other)
    check("the declaration taken away, it can be shown again on the settings page", r["ok"], str(r))
    # With sync on and nothing happening: nothing at all, and nothing written.
    # (Once the space shown again has settled, however long this machine takes over it. What was
    # picked last in a space and a page's title are written up to half a minute later, which is
    # not idle work: written now, until nothing more is.)
    ext_page(m, settings, """await wait(4000); page.__smokeWrites = []; page.browser.storage.onChanged.addListener((changes, area) => { page.__smokeWrites.push(area + ": " + Object.keys(changes).join(" ")); }); return 1;""")
    for _ in range(10):
        extension_message(m, {"type": "flush"})
        if not ext_page(m, settings, "await wait(3000); return page.__smokeWrites.splice(0).length;"):
            break
    idle = extension_message(m, {"type": "idle", "ms": 12000})
    written = ext_page(m, settings, "return [...page.__smokeWrites];")  # (what, should anything be)
    writes = len(written)
    if idle["alarms"]:
        print(f"SKIP  idle check with sync on: a timed check ran meanwhile ({idle})", flush=True)
    else:
        check("with sync on and nothing happening, Tidier does nothing and writes nothing", idle["jobs"] == 0 and idle["views"] == 0 and idle["lookups"] == 0 and writes == 0, f"{idle}, {written}")
    # As found, for the groups after this one.
    r = ext_page(m, settings, """doc.getElementById("sync-on").click(); await wait(800); await page.browser.storage.sync.clear();
      return doc.getElementById("sync-on").checked;""")
    check("sync can be turned off again", r is False, str(r))
    # Back in the space hiding moved you out of: later groups (alone_restart's names) expect its essentials.
    sidebar_page(m, """send({type: "space", space: args[0]}); for (let i = 0; i < 40 && spaces().find(s => s.active)?.id !== args[0]; i++) await wait(100); return 1;""", f"firefox-container-{space}")
    m.js(H + """const w = main(); for (const t of [...w.gBrowser.tabs]) if (url(t).includes("/settings/settings.html") || url(t).includes("/sidebar/sidebar.html")) w.gBrowser.removeTab(t); await wait(500); return 1;""")


# (A list longer than the sidebar has no empty part in view, so for the test it gets one at its end.
# Below the last row without that is the bar, with a menu of its own.)
EMPTY_LIST = """({getBoundingClientRect: () => { const list = doc.getElementById("tabs");
  if (list.lastElementChild.getBoundingClientRect().bottom + 16 > list.getBoundingClientRect().bottom) { list.style.paddingBottom = "24px"; list.scrollTop = list.scrollHeight; }
  const r = list.getBoundingClientRect(); return {x: r.x, y: list.lastElementChild.getBoundingClientRect().bottom + 8, width: r.width, height: 2}; }})"""


def alone_space_menu(m):
    # Copies of Tidier's pages are rows too, and stay loaded: they have no container.
    m.js(H + """const w = main(); w.focus();
      for (const t of [...w.gBrowser.tabs]) if (/sidebar\\/sidebar\\.html|settings\\/settings\\.html/.test(url(t))) w.gBrowser.removeTab(t);
      await wait(500); return 1;""")
    here = sidebar_until(m, """() => doc.querySelector("#spaces .space.active")?.dataset.space""")
    all_spaces = in_sidebar(m, """() => [...doc.querySelectorAll("#spaces .space")].map(b => b.dataset.space)""")
    there = next(s for s in all_spaces if s != here and s != "firefox-container-4")
    # Loaded tabs in two spaces, and you are on one of them.
    SPACE_TABS = H + """const ctxOfId = id => Number(id.split("-").pop());
      const ordinary = (w, ctx) => w.gBrowser.tabs.filter(t => !t.pinned && t.userContextId === ctx && role(w, t) === "live");
      const pins = (w, ctx) => w.gBrowser.tabs.filter(t => t.pinned && t.userContextId === ctx);"""
    m.js(SPACE_TABS + """const w = main();
      for (const [space, name] of args[0]) for (const i of [1, 2, 3]) { w.gBrowser.addTrustedTab("https://example.org/?smoke-menu-" + name + "-" + i, {userContextId: ctxOfId(space), inBackground: true}); await wait(200); }
      const ready = () => w.gBrowser.tabs.filter(t => url(t).includes("smoke-menu-") && t.linkedPanel && role(w, t) === "live").length;
      for (let i = 0; i < 300 && ready() < 6; i++) await wait(100);
      w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes("smoke-menu-here-1"));
      await wait(1000); return 1;""", [[here, "here"], [there, "there"]])

    # What it offers.
    # Clear, which closes tabs, comes on its own after the rest (spacemenu.js), and More last,
    # as in a tab's menu (both spaces have pages loaded, so both have it).
    ELSEWHERE, IN_SPACE = ["Rename", "Icon", "Unload this space", "Archived tabs", "New space", "Settings", "More"], ["Rename", "Icon", "Unload this space", "Archived tabs", "New space", "Settings", "Clear today's tabs", "More"]
    r = menu_on(m, f"dot({json.dumps(there)})", ELSEWHERE)
    place = in_sidebar(m, """(id) => ({menuBottom: doc.getElementById("menu").getBoundingClientRect().bottom, bar: doc.getElementById("spaces").getBoundingClientRect().top, marked: dot(id).classList.contains("menu-for"), active: doc.querySelector("#spaces .space.active").dataset.space,
      heading: doc.querySelector("#menu .heading")?.textContent, name: dot(id).title, lines: doc.querySelectorAll("#menu .line").length})""", there)
    check("a right click on another space's dot opens its menu", r == ELSEWHERE, str(r))
    check("which starts with that space's name, and has its groups", place["heading"] == place["name"] and place["lines"] == 2, str(place))
    check("the menu opens above the bar, and its dot is marked", place["menuBottom"] <= place["bar"] and place["marked"] and place["active"] == here, str(place))
    sidebar_key(m, ESC)
    closed = sidebar_until(m, """(id) => !labels().length && !dot(id).classList.contains("menu-for")""", there)
    if closed is not True:  # says where the key went
        closed = {"sidebar": in_sidebar(m, """(id) => ({labels: labels(), marked: dot(id).classList.contains("menu-for"), has: doc.hasFocus()})""", there),
                  "focus": m.js(H + """const b = Services.focus.focusedContentBrowsingContext; return b?.currentURI?.spec?.slice(0, 70) ?? null;""")}
    check("Esc closes it, and the mark goes", closed is True, str(closed))
    r = menu_on(m, f"dot({json.dumps(here)})", IN_SPACE)
    check("the space you are in also has Clear", r == IN_SPACE, str(r))
    # A right click elsewhere takes the open menu away, and the list has its own.
    # (A long list's empty part lies under that menu, which stands above the bar, and a right
    # click on a menu does nothing, so there it goes first.)
    if in_sidebar(m, f"""() => {{ const p = {EMPTY_LIST}.getBoundingClientRect(), box = doc.getElementById("menu").getBoundingClientRect(); return p.y + 1 >= box.top && p.y <= box.bottom; }}"""):
        sidebar_key(m, ESC)
        sidebar_until(m, "() => !labels().length")
    r = menu_on(m, EMPTY_LIST, ["New folder", "Clear today's tabs", "Archived tabs", "Settings"])
    check("the empty part of the list has its own short menu", r == ["New folder", "Clear today's tabs", "Archived tabs", "Settings"], str(r))
    r = menu_on(m, 'doc.getElementById("space-name")', IN_SPACE)
    check("the name above the list has the space's menu", r == IN_SPACE, str(r))
    sidebar_key(m, ESC)
    sidebar_until(m, "() => !labels().length")

    # Unloading another space: you stay where you are.
    STATE = SPACE_TABS + """const w = main(), ctx = ctxOfId(args[0]);
      return {loaded: ordinary(w, ctx).filter(t => t.linkedPanel).map(t => url(t)), essentials: pins(w, ctx).filter(t => t.linkedPanel && !url(t).includes("ghost.html")).length, selected: url(w.gBrowser.selectedTab)};"""
    before = m.js(STATE, there)
    menu_on(m, f"dot({json.dumps(there)})")
    choose(m, "Unload this space")
    for _ in range(100):
        after = m.js(STATE, there)
        if not after["loaded"]:
            break
        time.sleep(0.1)
    check("unloading another space unloads its tabs", len(before["loaded"]) >= 3 and not after["loaded"], f"{before} -> {after}")
    # (The line may still show what came before, the Clear above, for a moment.)
    note = sidebar_until(m, """(id) => doc.getElementById("note").classList.contains("shown") && /unload/i.test(doc.querySelector("#note .text").textContent) ? {text: doc.querySelector("#note .text").textContent, name: dot(id).title} : {wait: doc.querySelector("#note .text")?.textContent ?? ""}""", there)
    check("and says so, since nothing you see changes", bool(note) and not note.get("wait") and re.fullmatch(rf"\d+ tabs? unloaded in {re.escape(note['name'])}", note["text"]) is not None, str(note))
    check("and leaves its essentials, and you where you are", after["essentials"] == before["essentials"] > 0 and after["selected"] == before["selected"], f"{before} -> {after}")

    # Unloading this one: the rows dim, except the selected tab, and a page with unsaved input stays.
    m.js(H + """const t = main().gBrowser.tabs.find(t => url(t).includes("smoke-menu-here-2"));
      t.linkedBrowser.messageManager.loadFrameScript("data:,content.addEventListener('beforeunload', e => e.preventDefault()); content.document.notifyUserGestureActivation();", false);
      await wait(300); return 1;""")
    # (Tidier's own pages left out: the test's sidebar page is a row of the space it belongs to,
    # and a page of Tidier's is not the user's to unload.)
    ROWS = """() => [...doc.querySelectorAll("#tabs .tab")].filter(r => !r.classList.contains("unloaded") && r.querySelector(".title").textContent !== "Tidier" && !r.title.includes("moz-extension:")).map(r => r.classList.contains("active") ? "selected" : "loaded")"""
    before = in_sidebar(m, ROWS)
    essentials = m.js(STATE, here)["essentials"]
    # (A tab of this space selected in another window stays loaded too, as Clear leaves it: spaceactions.js.)
    elsewhere = m.js(H + """const a = main(), on = a.gBrowser.selectedTab;
      return new Set(wins().filter(w => w !== a && w.toolbar.visible).map(w => [w, w.gBrowser.selectedTab]).filter(([w, t]) => !t.pinned && t.userContextId === on.userContextId && key(w, t) && key(w, t) !== key(a, on)).map(([w, t]) => key(w, t))).size;""")
    menu_on(m, f"dot({json.dumps(here)})")
    choose(m, "Unload this space")
    for _ in range(100):
        rows = in_sidebar(m, ROWS)
        if rows.count("loaded") <= 1 + elsewhere:
            break
        time.sleep(0.1)
    state = m.js(STATE, here)
    check("unloading the space you are in dims its rows", before.count("loaded") >= 2 and rows.count("loaded") == 1 + elsewhere and "selected" in rows, f"{before} -> {rows}, {elsewhere} selected elsewhere")
    check("and leaves the selected tab, its essentials and a page with unsaved input, without asking", "smoke-menu-here-1" in state["selected"] and any("smoke-menu-here-1" in u for u in state["loaded"]) and any("smoke-menu-here-2" in u for u in state["loaded"]) and state["essentials"] == essentials, str(state))
    # (Closed here, or the page would ask later.) A dim row's page comes back when selected.
    m.js(H + """const w = main(), t = w.gBrowser.tabs.find(t => url(t).includes("smoke-menu-here-2")); w.gBrowser.removeTab(t, {skipPermitUnload: true}); await wait(1000); return 1;""")
    sidebar_mouse(m, """doc.querySelector("#tabs .tab.unloaded")""")
    for _ in range(100):
        back = m.js(H + """const t = main().gBrowser.selectedTab; return {page: url(t), loaded: !!t.linkedPanel, was: url(t).includes("smoke-menu-here-1")};""")
        if not back["was"] and back["loaded"] and "ghost.html" not in back["page"]:
            break
        time.sleep(0.1)
    check("an unloaded row's page comes back when you select it", not back["was"] and back["loaded"], str(back))
    # Back on a tab of this test, for the checks below.
    m.js(H + """const w = main(); w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes("smoke-menu-here-1")); await wait(800); return 1;""")

    # A page loaded in another window: the row here is a placeholder, and the page goes too.
    # Selecting the placeholder then brings the page here, once.
    other = m.js(SPACE_TABS + """const a = main(), w = a.OpenBrowserWindow(); w.__extra = true;
      for (let i = 0; i < 100 && !(w.gBrowser?.tabs.some(t => t.pinned)); i++) await wait(100);
      const t = w.gBrowser.addTrustedTab("https://example.org/?smoke-menu-other-window", {userContextId: ctxOfId(args[0]), inBackground: true});
      const placeholder = () => a.gBrowser.tabs.find(g => key(w, t) && key(a, g) === key(w, t));
      for (let i = 0; i < 200 && !(t.linkedPanel && url(t).includes("smoke-menu") && placeholder()); i++) await wait(100);
      a.focus(); await wait(500);
      return {role: role(w, t), key: key(w, t), placeholder: !!placeholder()};""", here)
    menu_on(m, f"dot({json.dumps(here)})")
    choose(m, "Unload this space")
    GONE = H + """const t = wins().find(w => w.__extra).gBrowser.tabs.find(t => url(t).includes("smoke-menu-other-window")); return {loaded: !!t?.linkedPanel, kept: !!t};"""
    for _ in range(100):
        gone = m.js(GONE)
        if not gone["loaded"]:
            break
        time.sleep(0.1)
    check("unloading reaches a page loaded in another window", other["role"] == "live" and other["placeholder"] and gone == {"loaded": False, "kept": True}, f"{other} -> {gone}")
    m.js(H + """const a = main(); a.gBrowser.selectedTab = a.gBrowser.tabs.find(t => key(a, t) === args[0]); return 1;""", other["key"])
    settled = lambda b: "smoke-menu-other-window" in b["page"] and b["loaded"] and sorted(set(s for w in b["everywhere"] for s in w)) == ["ghost/unloaded", "live/loaded"] and sum(w.count("live/loaded") for w in b["everywhere"]) == 1
    for _ in range(300):  # the pull has steps: only its end says anything
        back = m.js(H + """const a = main(), t = a.gBrowser.selectedTab; return {page: url(t), loaded: !!t.linkedPanel, everywhere: find(args[0])};""", other["key"])
        if settled(back):
            break
        time.sleep(0.1)
    check("and its placeholder brings it here, once", settled(back), str(back))
    m.js(H + """const w = wins().find(w => w.__extra), a = main(); await close(w); a.focus(); a.gBrowser.selectedTab = a.gBrowser.tabs.find(t => url(t).includes("smoke-menu-here-1")); await wait(800); return 1;""")

    # Rename, with real typing. Reading the container's name is reading what Firefox has.
    NAME = H + """return main().ContextualIdentityService.getPublicIdentityFromId(Number(args[0].split("-").pop())).name;"""
    name_here, name_there = m.js(NAME, here), m.js(NAME, there)
    line = in_sidebar(m, """() => top("actions")""")
    menu_on(m, f"dot({json.dumps(here)})")
    choose(m, "Rename")
    r = sidebar_until(m, """() => box() ? {value: box().value, selected: [box().selectionStart, box().selectionEnd], focus: doc.activeElement === box() && doc.hasFocus(), lineHidden: doc.getElementById("space-name").hidden, actions: top("actions")} : {wait: 1}""")
    check("Rename turns the name line into a box, with the name selected", r.get("value") == name_here and r["selected"] == [0, len(name_here)] and r["focus"] and r["lineHidden"], str(r))
    check("and the list does not move", r.get("actions") == line, f"{line} -> {r.get('actions')}")
    for ch in "Smoked":
        sidebar_key(m, ch)
    sidebar_key(m, ENTER)
    r = sidebar_until(m, """() => !box() && doc.querySelector("#spaces .space.active").title === "Smoked" ? {name: doc.getElementById("space-name").textContent, hidden: doc.getElementById("space-name").hidden} : {wait: 1}""")
    check("typing and Enter rename the space: the line, the dot and the container", r.get("name") == "Smoked" and r.get("hidden") is False and m.js(NAME, here) == "Smoked", f"{r}, {m.js(NAME, here)}")
    # The list stays put whatever the name is called and whatever the font: a long name
    # stays on one line, and the box takes the height of the line it replaces.
    r = in_sidebar(m, """() => { const line = doc.getElementById("space-name"), name = line.textContent, before = top("actions");
      line.textContent = name + " and a very long name that goes on".repeat(9); const after = top("actions"); line.textContent = name; return {before, after}; }""")
    check("a long name stays on one line, and the list does not move", r["before"] == r["after"], str(r))
    in_sidebar(m, """() => { doc.getElementById("space-name").style.fontSize = "19px"; return 1; }""")
    line = in_sidebar(m, """() => top("actions")""")
    menu_on(m, f"dot({json.dumps(here)})")
    choose(m, "Rename")
    r = sidebar_until(m, """() => box() ? {actions: top("actions")} : {wait: 1}""")
    check("with another font too", r.get("actions") == line, f"{line} -> {r}")
    sidebar_key(m, ESC)
    sidebar_until(m, "() => !box()")
    in_sidebar(m, """() => { doc.getElementById("space-name").style.fontSize = ""; return 1; }""")
    # A space without a name has no line, so the box is simply put there, over nothing.
    in_sidebar(m, """() => { const line = doc.getElementById("space-name"); line.dataset.was = line.textContent; line.textContent = ""; return 1; }""")
    menu_on(m, f"dot({json.dumps(here)})")
    choose(m, "Rename")
    r = sidebar_until(m, """() => { if (!box()) return {wait: 1}; const b = box().getBoundingClientRect(); return {bottom: b.bottom, actions: top("actions")}; }""")
    check("a space with no name opens a box that covers nothing", r.get("bottom", 1e9) <= r.get("actions", 0), str(r))
    sidebar_key(m, ESC)
    sidebar_until(m, "() => !box()")
    in_sidebar(m, """() => { const line = doc.getElementById("space-name"); line.textContent = line.dataset.was; delete line.dataset.was; return 1; }""")
    # Esc leaves it as it was; leaving the box saves.
    menu_on(m, f"dot({json.dumps(here)})")
    choose(m, "Rename")
    sidebar_until(m, "() => !!box()")
    for ch in "xy":
        sidebar_key(m, ch)
    sidebar_key(m, ESC)
    r = sidebar_until(m, """() => box() ? {wait: 1} : {name: doc.getElementById("space-name").textContent}""")
    check("Esc leaves the name as it was", r.get("name") == "Smoked" and m.js(NAME, here) == "Smoked", str(r))
    # Another space: in its place on the bar and in the box, and you stay.
    menu_on(m, f"dot({json.dumps(there)})")
    choose(m, "Rename")
    r = sidebar_until(m, """(id, here) => box() ? {value: box().value, focus: doc.activeElement === box() && doc.hasFocus(), marked: dot(id).classList.contains("menu-for"), active: dot(here).classList.contains("active")} : {wait: 1}""", there, here)
    check("another space's name opens in the box, its dot marked, and you stay in your space", r.get("value") == name_there and r["focus"] and r["marked"] and r["active"], str(r))
    for ch in "Other":
        sidebar_key(m, ch)
    sidebar_mouse(m, EMPTY_LIST)
    r = sidebar_until(m, """(id) => box() || dot(id).title !== "Other" ? {wait: 1} : {line: doc.getElementById("space-name").textContent, marked: dot(id).classList.contains("menu-for")}""", there)
    check("leaving the box saves it, and this space's name stays on the line", r.get("line") == "Smoked" and r.get("marked") is False and m.js(NAME, there) == "Other", f"{r}, {m.js(NAME, there)}")
    extension_message(m, {"type": "settings:space", "id": here, "changes": {"name": name_here}})
    extension_message(m, {"type": "settings:space", "id": there, "changes": {"name": name_there}})

    # An icon: chosen from a list to search in (sidebar/emoji.js), drawn in the menu's place,
    # with the keyboard in its field. (Icon is clicked, not chosen: the menu stays, as its list.)
    sidebar_until(m, "(id, name) => dot(id).title === name", there, name_there)
    menu_on(m, f"dot({json.dumps(there)})")
    sidebar_mouse(m, 'item("Icon")')
    FIELD = """() => { const f = doc.querySelector("#menu .find"), box = doc.getElementById("menu").getBoundingClientRect();
      return f ? {focus: doc.activeElement === f && doc.hasFocus(), shown: doc.querySelectorAll("#menu .emoji").length, fits: box.left >= 0 && box.right <= content.innerWidth && box.top >= 0 && box.bottom <= content.innerHeight,
        back: labels()} : {wait: 1}; }"""
    r = sidebar_until(m, FIELD)
    check("Icon opens emoji to choose from in the menu's place, with the keyboard in the field to search in", bool(r) and r.get("focus") and r["shown"] > 250 and r["fits"] and r["back"] == ["Icon"], str(r))
    for ch in "lightn":
        sidebar_key(m, ch)
    r = sidebar_until(m, """() => { const all = [...doc.querySelectorAll("#menu .emoji")]; return all.length === 1 ? {found: all[0].textContent, marked: all[0].classList.contains("at")} : {wait: all.length || 1}; }""")
    check("typing finds one by its name, marked as the one Enter takes", r.get("found") == "⚡" and r.get("marked"), str(r))
    sidebar_key(m, ENTER)
    r = sidebar_until(m, """(id) => labels().length || !dot(id).querySelector(".dot.emoji") ? {wait: 1} : {icon: dot(id).querySelector(".dot.emoji").textContent}""", there)
    check("Enter makes it the space's icon: on the bar, and first in the space's name", r.get("icon") == "⚡" and m.js(NAME, there) == "⚡ " + name_there, f"{r}, {m.js(NAME, there)}")
    menu_on(m, f"dot({json.dumps(there)})")
    sidebar_mouse(m, 'item("Icon")')
    sidebar_until(m, FIELD)
    r = in_sidebar(m, "() => labels()")
    choose(m, "No icon")
    for _ in range(100):
        if m.js(NAME, there) == name_there:
            break
        time.sleep(0.1)
    # The bar is drawn again a moment after the name changed.
    gone = sidebar_until(m, """(id) => labels().length || dot(id).querySelector(".dot.emoji") ? {wait: 1} : {icon: ""}""", there)
    check("a space with an icon can have its dot back (No icon)", r == ["Icon", "No icon"] and m.js(NAME, there) == name_there and gone == {"icon": ""}, f"{r}, {m.js(NAME, there)}, {gone}")

    # Settings: the page, selected, in the window you are in, and you stay in your space.
    menu_on(m, f"dot({json.dumps(there)})")
    choose(m, "Settings")
    for _ in range(100):
        r = m.js(H + """const t = main().gBrowser.selectedTab; return url(t);""")
        if "settings/settings.html" in r:
            break
        time.sleep(0.1)
    check("Settings opens the settings page", "settings/settings.html" in r, r)
    active = in_sidebar(m, """() => doc.querySelector("#spaces .space.active").dataset.space""")
    check("and you stay in your space", active == here, active)
    m.js(H + """const w = main(); w.gBrowser.removeTab(w.gBrowser.selectedTab); await wait(1000); return 1;""")
    in_sidebar(m, """() => { doc.getElementById("tabs").style.paddingBottom = ""; return 1; }""")
    no_problems(m, "after a space's menu")
