"""Many tabs, random use, nothing happening, an update and a restart."""
import json
import os
import time
from testfirefox import EXT_ID
from smokechecks.base import (
    CTRL, H, IN_SIDEBAR, PROC_INFO, RECENTLY_CLOSED_PLACEHOLDERS, SNAP_ALONE, bar_open, check,
    ext_page, extension_message, in_sidebar, into_page, more_tabs_here, no_problems, press, seen,
    sidebar_page,
)
from smokechecks.core import look


def alone_chaos(m):
    # Tidier tells its own moves and closes from yours by marks it takes away when Firefox
    # answers (a pull: beingPulled, a sort: ownMoves, a close: removeTabs). That rests on Firefox
    # telling of what happened before it answers the call, which only a real Firefox can show.
    r = ext_page(m, "/settings/settings.html", """
      const b = page.browser, seen = {attached: 0, moved: 0, pinned: 0, removed: 0}, late = [];
      const [space] = await b.contextualIdentities.query({});
      const here = (await b.windows.getCurrent()).id, other = await b.windows.create({url: "about:blank"});
      await wait(2000);
      const t = await b.tabs.create({windowId: here, url: "https://example.org/?smoke-event-order", active: false, cookieStoreId: space.cookieStoreId});
      await wait(3000);
      const count = kind => id => { if (id === t.id) seen[kind]++; };
      const listeners = [[b.tabs.onAttached, count("attached")], [b.tabs.onMoved, count("moved")], [b.tabs.onRemoved, count("removed")],
        [b.tabs.onUpdated, (id, change) => { if (id === t.id && "pinned" in change) seen.pinned++; }]];
      for (const [event, f] of listeners) event.addListener(f);
      const answered = (kind, n) => { if (seen[kind] < n) late.push(kind + " " + n); };
      for (let i = 1; i <= 6; i++) { await b.tabs.move(t.id, {windowId: i % 2 ? other.id : here, index: -1}); answered("attached", i); await wait(300); }
      const first = (await b.tabs.query({windowId: here, pinned: true})).length; // a move out of the pinned part is ignored
      for (let i = 1; i <= 6; i++) { await b.tabs.move(t.id, {index: i % 2 ? first : -1}); answered("moved", i); await wait(100); }
      await b.tabs.update(t.id, {pinned: true}); answered("pinned", 1); await wait(300);
      await b.tabs.update(t.id, {pinned: false}); answered("pinned", 2); await wait(800);
      await b.tabs.remove(t.id); answered("removed", 1);
      for (const [event, f] of listeners) event.removeListener(f);
      await b.windows.remove(other.id); await wait(1500);
      return {late, seen};""")
    check("Firefox tells of a move or a close before it answers the call", r.get("late") == [] and r["seen"]["attached"] == 6, str(r))
    # What the unit tests cannot show: that a real page Tidier closes reaches Recently Closed
    # under the address it had, and is found there.
    r = m.js(H + """const w = main(), mark = "smoke-chaos-link";
      const closed = () => w.SessionStore.getClosedTabDataForWindow(w).map(c => c.state.entries?.[c.state.index - 1]?.url || "").filter(u => u.includes(mark)).length;
      w.gBrowser.addTrustedTab("https://example.org/?" + mark, {inBackground: true});  // no container, as from another app
      const inSpace = () => w.gBrowser.tabs.filter(t => url(t).includes(mark) && t.userContextId);
      for (let i = 0; i < 100 && !inSpace().length; i++) await wait(100);
      await wait(1500);  // a copy left there would be there by now
      const here = w.gBrowser.tabs.filter(t => url(t).includes(mark)), spaces = here.map(ctxOf), first = closed();
      w.gBrowser.removeTab(here[0]);
      for (let i = 0; i < 100 && !closed(); i++) await wait(100);
      return {spaces, first, then: closed()};""")
    check("a link from another app is opened in a space, and its first copy is not in Recently Closed", len(r["spaces"]) == 1 and r["spaces"][0] != "firefox-default" and r["first"] == 0, str(r))
    check("closed a moment later, ⌘⇧T brings it back", r["then"] == 1, str(r))


def alone_idle(m):
    # What the groups before did can still have a timer running, started by what they did:
    # the quiet line (10 s) and a placeholder's new title (up to a minute, refreshGhostsSoon).
    # Nothing is happening only once those have run out.
    for _ in range(150):
        sizes = extension_message(m, {"type": "stats"})["sizes"]
        if not sizes["quietNotes"] and not sizes["refreshTimers"]:
            break
        time.sleep(0.5)
    idle = extension_message(m, {"type": "idle", "ms": 15000})
    if idle["alarms"]:
        print(f"SKIP  idle check: a timed check ran meanwhile ({idle})", flush=True)
    else:
        check("with nothing happening, Tidier and its sidebar do nothing (15 s)", idle["jobs"] == 0 and idle["lookups"] == 0 and idle["views"] == 0, str(idle))


def alone_update(m):
    # An update shows every tab Tidier hid again (the permission is an optional one): hidden again by the time it has started.
    if not m.can_restart:
        print("SKIP  alone_update (needs Tidier installed for real: Developer Edition, or --xpi)", flush=True)
        return
    before = m.js(SNAP_ALONE)
    look = """() => ({url: doc.URL, born: Math.round(content.performance.timeOrigin), ready: doc.readyState, space: doc.documentElement.dataset.space || null,
      own: doc.head ? doc.head.querySelectorAll("style").length : 0, rows: doc.querySelectorAll("#tabs .tab").length})"""
    was = in_sidebar(m, look)
    bar_open(m)  # an update can come at any moment, also with the bar open
    m.cmd("Addon:Install", {"path": m.update_xpi(), "temporary": False})
    # The sidebar while Tidier starts again: in the space's look from its first moment, not a
    # blank, untinted panel until the background part answers.
    seen, t0 = [], time.time()
    while time.time() - t0 < 6:
        try:  # (a page being replaced may never answer, or not be there yet)
            s = m.js(H + IN_SIDEBAR + "return await Promise.race([inSidebar(...args), wait(800).then(() => null)]);", look)
        except Exception:
            m.chrome()
            s = None
        if isinstance(s, dict) and s.get("url", "").endswith("/sidebar/sidebar.html") and s.get("ready") != "loading" and s != (seen[-1] if seen else None):
            seen.append(s)
        time.sleep(0.05)
    m.js(H + "await wait(6000); return 1;")
    again = [s for s in seen if s["born"] != was.get("born")]  # the page as it is loaded again
    bare = [s for s in again if not s["space"] or (was.get("own") and not s["own"])]
    check("during an update the sidebar keeps its space's look until it has its view", again and not bare, f"before {was}, then {seen[:6]}")
    after = m.js(SNAP_ALONE)
    check("after an update, the same tabs, folders and one space shown", before == after, f"{before} -> {after}")
    left = m.js(H + """return wins().filter(w => !w.toolbar.visible).length;""")
    check("an update with the command bar open leaves no window of it behind", left == 0, str(left))
    r = m.js(H + "return main().SidebarController.currentID;")
    check("after an update, Tidier's sidebar is still the sidebar", "6844a953" in (r or ""), str(r))


def alone_restart(m):
    if not m.can_restart:
        print("SKIP  alone_restart (needs Tidier installed for real: Developer Edition, or --xpi)", flush=True)
        return
    no_problems(m, "before a restart")
    # Two windows, as after alone_second_window: a placeholder is another window's copy of a page.
    m.js(H + """if (!other()) { const w = main().OpenBrowserWindow(); w.__smoke = true; await wait(4000); } return 1;""")
    # Names, as the record and the list keep them: an essential's, and a saved tab's.
    more_tabs_here(m, "restart")
    named = sidebar_page(m, """
      const until = async f => { for (const end = Date.now() + 8000; Date.now() < end; await wait(50)) { const v = f(); if (v) return v; } return f(); };
      const tile = doc.querySelector("#essentials .tile"), space = spaces().find(s => s.active).id;
      send({type: "newFolder", space, name: "Named"});
      const head = await until(() => [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "Named"));
      const tab = Number(plainTabs().at(-1).dataset.tab);
      send({type: "moveTab", tabId: tab, folder: head.dataset.folderHead, before: null});
      await until(() => doc.querySelector(`#tabs .tab[data-tab="${tab}"]`)?.dataset.folder);
      send({type: "renameTab", tabId: Number(tile.dataset.tab), name: "Named essential"});
      send({type: "renameTab", tabId: tab, name: "Named tab"});
      await until(() => tile.title.startsWith("Named essential") && rows().includes("Named tab"));
      return {tile: tile.title, rows: rows(), space};""")
    check("names: an essential and a saved tab named before the restart", named.get("tile", "").startswith("Named essential") and "Named tab" in named.get("rows", []), str(named))
    # Which tab each window is on says why a page has moved between them.
    on_now = H + """return wins().map(w => { const t = w.gBrowser.selectedTab; return [url(t).slice(0, 60), role(w, t) ?? null, !!t.pinned]; });"""
    archived = extension_message(m, {"type": "archivedTabs"})
    before, on_before = m.js(SNAP_ALONE), m.js(on_now)
    # A settings page selected in a window when Firefox quits is loaded again as it starts, maybe
    # before Tidier has: it must still be whole then.
    m.js(H + """const w = wins().find(w => w !== main()) ?? main();
      w.gBrowser.selectedTab = w.gBrowser.addTrustedTab("moz-extension://" + JSON.parse(Services.prefs.getStringPref("extensions.webextensions.uuids"))[args[0]] + "/settings/settings.html?restart", {}); await wait(1500); return 1;""", EXT_ID)
    bar_open(m)  # quit with the command bar open: Firefox brings popups back with the session
    m.restart()
    m.js(H + """for (let i = 0; i < 100 && wins().length < 2; i++) await wait(200); await wait(12000); return 1;""")
    after, on_after = m.js(SNAP_ALONE), m.js(on_now)
    # As many pages, not in the same windows: a window you are not using can be on a placeholder,
    # which waits unloaded until you use that window (pull, tabsync.js), and Firefox can come
    # back with that window in front. Its page then comes over, as it would for a click.
    def wherever(snap):
        return {**snap, "windows": [{k: v for k, v in w.items() if k != "live"} for w in snap["windows"]], "pages": sum(w["live"] for w in snap["windows"])}
    check("after a restart, the same tabs, folders and one space shown", wherever(before) == wherever(after), f"on {on_before} -> {on_after}; {before} -> {after}")
    r = m.js(H + """return {left: wins().filter(w => !w.toolbar.visible && url(w.gBrowser.selectedTab).includes("/commandbar/commandbar.html")).length,
      closed: main().SessionStore.getClosedWindowData().filter(w => w.tabs[0]?.entries?.[0]?.url?.includes("/commandbar/commandbar.html")).length};""")
    check("a command bar left open at a restart does not come back, and is not kept as a closed window", r == {"left": 0, "closed": 0}, str(r))
    into_page(m, "settings.html?restart")
    r = m.cmd("WebDriver:ExecuteScript", {"script": """const d = (window.wrappedJSObject || window).document;
      return {agents: !d.getElementById("claude-section").hidden, keys: !d.getElementById("keys-section").hidden, moved: !d.getElementById("moved-section").hidden};"""})
    m.chrome()
    m.js(H + """await removeWhere((w, t) => url(t).includes("settings.html?restart")); return 1;""")
    check("a settings page Firefox brings back at a start shows its agents and keys, and nothing about a move", r["agents"] and r["keys"] and not r["moved"], str(r))
    check("after a restart, the list of archived tabs is still there", extension_message(m, {"type": "archivedTabs"}) == archived, str(archived))
    # Its rows, not only the tabs: in a sidebar page opened now, and in the window's own sidebar.
    r = ext_page(m, "/sidebar/sidebar.html?after-restart", """for (let i = 0; i < 40 && !rows().length; i++) await wait(250);
      const own = page.browser.extension.getViews({type: "sidebar"}).map(v => [...v.document.querySelectorAll("#tabs .tab")]);
      return {rows: rows().length, spaces: spaces().length, reals: own.map(list => list.length), fixed: own.flat().filter(e => !e.draggable).length};""")
    check("after a restart the sidebar shows its list", r["rows"] > 0 and r["spaces"] > 0, str(r))
    check("after a restart the window's own sidebar has connected and shows its list", any(r["reals"]), str(r))
    check("after a restart the rows of the window's own sidebar can be dragged", r["fixed"] == 0, str(r))
    # The page from before the restart is not loaded again by itself: a new one.
    m.js(H + """for (const t of [...main().gBrowser.tabs]) if (url(t).includes("/sidebar/sidebar.html")) main().gBrowser.removeTab(t); await wait(300); return 1;""")
    # (In the space they were named in: which window comes first after a restart is not given, and
    # the other one may show another space, with its own essentials.)
    r = sidebar_page(m, """const there = () => spaces().find(s => s.active)?.id === args[0];
      for (const end = Date.now() + 8000; Date.now() < end && !spaces().length; await wait(50));
      if (!there()) doc.querySelector(`#spaces .space[data-space="${args[0]}"]`)?.click();
      for (const end = Date.now() + 8000; Date.now() < end && !(there() && tiles().length); await wait(50));
      await wait(500);
      return {tiles: tiles().map(t => t.split("\\n")[0]), rows: rows(), space: spaces().find(s => s.active)?.id};""", named.get("space"))
    check("after a restart, an essential and a saved tab keep their names", "Named essential" in r.get("tiles", []) and "Named tab" in r.get("rows", []), str(r))
    r = m.js(H + """const labels = w => w.gBrowser.tabs.filter(t => !t.selected && !t.linkedPanel).map(t => t.label); return wins().map(labels).flat();""")
    every = m.js(H + """return wins().map(w => w.gBrowser.tabs.map(t => [t.label, role(w, t) ?? null, t.selected ? "selected" : t.linkedPanel ? "loaded" : "unloaded"]));""")
    check("after a restart, their placeholders still show them", "Named essential" in r and "Named tab" in r, str(every))


# How many tabs alone_many uses; TIDIER_MANY=1000 measures more (the limits below
# are for its default).
MANY = int(os.environ.get("TIDIER_MANY", "300"))


# In the sidebar's page, which is a background tab: its timers are slowed to one a
# second, but a change on the page is seen at once.
MANY_PAGE = """
  const ask = async msg => JSON.parse(page.JSON.stringify(await page.browser.runtime.sendMessage(page.JSON.parse(JSON.stringify(msg)))));
  const bg = obj => page.JSON.parse(JSON.stringify(obj));
  const until = test => new Promise(resolve => {
    if (test()) return resolve(true);
    const o = new MutationObserver(() => { if (test()) { o.disconnect(); resolve(true); } });
    o.observe(doc.documentElement, {subtree: true, childList: true, attributes: true, attributeFilter: ["class"]});
    setTimeout(() => { o.disconnect(); resolve(false); }, 60000);
  });
  const median = list => [...list].sort((a, b) => a - b)[list.length >> 1];
  const rowOf = id => doc.querySelector(`[data-tab="${id}"]`);
  const windowId = (await page.browser.windows.getCurrent()).id;
"""


MANY_COUNT = H + """const w = main(), keys = new Set(w.gBrowser.tabs.filter(t => url(t).includes("smoke-many-") && role(w, t) === "live").map(t => key(w, t)));
  return wins().map(x => x.gBrowser.tabs.filter(t => keys.has(key(x, t))).length);"""


def many_wait(m, test, limit):
    """Ask Firefox until `test` holds of the answer, and say how long that took (None: never)."""
    t0 = time.time()
    while time.time() - t0 < limit:
        reply = m.js(test)
        if reply is True or (isinstance(reply, list) and reply and reply[0] is True):
            return round(time.time() - t0, 1)
        time.sleep(0.25)
    return None


def many_diff(before, after):
    return {k: round(after[k] - before[k]) for k in ("jobs", "queueMs", "lookups", "views", "viewMs")}


def alone_many(m):
    # The owner has about 33 essentials and 53 tabs; this is well beyond that. All of it
    # in the real test Firefox, with tabs that were never loaded, as after a restart, so
    # it measures Tidier and not page loads. Each limit is far above what it takes, so a
    # busy machine does not fail it; the numbers are printed to compare with.
    n = MANY
    numbers = {"tabs": n}
    made_window = m.js(H + """const a = main(); if (other()) return false;
      const w = a.OpenBrowserWindow(); w.__smoke = true;
      for (let i = 0; i < 100 && !w.gBrowser; i++) await wait(100);
      await wait(4000); return true;""")
    stats = sidebar_page(m, MANY_PAGE + """return {stats: await ask({type: "stats"}), active: spaces().find(s => s.active).id};""")
    stats, space0 = stats["stats"], stats["active"]
    numbers["memory0"] = m.js(PROC_INFO)["mb"]
    t0 = time.time()
    m.js(H + """const w = main();
      for (let i = 0; i < args[0]; i++) {
        w.gBrowser.addTrustedTab("https://example.org/?smoke-many-" + i, {userContextId: 1 + i % 3, inBackground: true, createLazyBrowser: true});
        if (i % 10 === 9) await wait(0);
      }
      return 1;""", n)
    numbers["createdS"] = round(time.time() - t0, 1)
    spread = None
    while time.time() - t0 < 900:
        spread = m.js(MANY_COUNT)
        if len(spread) >= 2 and all(c == n for c in spread):
            break
        time.sleep(1)
    numbers["burstS"] = round(time.time() - t0, 1)
    check(f"{n} tabs opened at once are in both windows ({numbers['burstS']} s)", len(spread) >= 2 and all(c == n for c in spread), str(spread))
    r = sidebar_page(m, MANY_PAGE + """return {stats: await ask({type: "stats"}), rows: doc.querySelectorAll("#tabs .tab").length};""")
    burst = many_diff(stats, r["stats"])
    numbers["burst"] = {**burst, "longestJobMs": round(r["stats"]["longestJobMs"]), "longestViewMs": round(r["stats"]["longestViewMs"])}
    numbers["memory1"] = m.js(PROC_INFO)["mb"]
    check("the sidebar shows them", r["rows"] >= n // 3, str(r))
    check(f"a burst of tabs does not build a view per tab ({burst['views']})", burst["views"] < n, str(burst))
    check(f"and the queue is not held for long ({burst['queueMs']} ms for {n} tabs)", burst["queueMs"] < n * 60, str(burst))
    # Placeholders load no page, which is what would take the memory.
    loaded = many_wait(m, H + """return wins().every(w => !w.gBrowser.tabs.some(t => t.linkedPanel && !t.selected && url(t).includes("ghost.html")));""", 20)
    staying = [] if loaded is not None else m.js(H + """return wins().flatMap(w => w.gBrowser.tabs.filter(t => t.linkedPanel && !t.selected && url(t).includes("ghost.html"))
      .map(t => ({window: w === main() ? "main" : w.__smoke ? "other" : "more", hidden: t.hidden, pinned: t.pinned, role: role(w, t), title: t.label.slice(0, 40), url: url(t).split("?")[1]?.slice(0, 80)})));""")
    check("no placeholder stays loaded", loaded is not None, f"{staying}, {numbers}")

    # A placeholder without a page still shows its page's title and icon, from the record.
    number = int(space0.rsplit("-", 1)[1])
    m.js(H + """other().gBrowser.addTrustedTab(args[0] + "/icon-png", {userContextId: args[1], inBackground: true}); await wait(4000); return 1;""", m.pages, number)
    # (Its row in view, in the page shown: an image out of view is not asked for.)
    m.js(H + """const w = main(); w.__before = w.gBrowser.selectedTab; w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes("/sidebar/sidebar.html")); await wait(300); return 1;""")
    r = sidebar_page(m, MANY_PAGE + """const row = [...doc.querySelectorAll("#tabs .tab")].find(x => x.querySelector(".title").textContent === "With an icon");
      if (!row) return {missing: rows().slice(-3)};
      row.scrollIntoView();
      const seen = await new Promise(resolve => { const look = n => { const i = row.querySelector("img"); if ((i && i.naturalWidth) || !n) resolve(i); else setTimeout(() => look(n - 1), 100); }; look(50); });
      doc.getElementById("tabs").scrollTop = 0;
      // An icon that does not load becomes the letter, and is not asked for again at the next draw.
      const bad = {icon: args[0] + "/no-icon-here.png", title: "Letter"}, first = page.icon(bad);
      first.style.position = "fixed"; first.style.top = "0"; doc.body.append(first);
      const letter = await new Promise(resolve => { const look = n => { const l = doc.body.querySelector(":scope > .letter"); if (l || !n) resolve(l); else setTimeout(() => look(n - 1), 100); }; look(50); });
      const again = page.icon(bad).tagName;
      letter?.remove(); first.remove();
      // Far out of view it is not asked for at all, and is once it comes into view.
      const far = page.icon({icon: args[0] + "/no-icon-far-away.png", title: "Far"});
      far.style.position = "fixed"; far.style.top = "100000px"; doc.body.append(far);
      await wait(1500);
      const asked = !far.isConnected || far.complete;
      far.style.top = "0";
      const inView = await new Promise(resolve => { const look = n => { if (!far.isConnected || !n) resolve(!far.isConnected); else setTimeout(() => look(n - 1), 100); }; look(50); });
      doc.body.querySelector(":scope > .letter")?.remove(); far.remove();
      return {unloaded: row.classList.contains("unloaded"), icon: seen?.src.slice(0, 22), drawn: seen?.naturalWidth, firstTag: first.tagName, letter: letter?.textContent, again, asked, inView};""", m.pages)
    check("a placeholder made without a page shows its page's title and icon", r.get("unloaded") and r.get("icon") == "data:image/png;base64," and r.get("drawn") == 16, str(r))
    check("an icon that does not load shows the letter, and is not asked for at every draw", r.get("firstTag") == "IMG" and r.get("letter") == "L" and r.get("again") == "SPAN", str(r))
    check("an icon far out of view is not asked for, and is when it comes into view", r.get("asked") is False and r.get("inView") is True, str(r))
    m.js(H + """const w = main(); w.gBrowser.selectedTab = w.__before; await removeWhere((x, t) => url(t).endsWith("/icon-png")); return 1;""")

    # From the event to the sidebar showing it, and a view's build, one at a time.
    r = sidebar_page(m, MANY_PAGE + """
      const space = spaces().find(s => s.active).id, before = await ask({type: "stats"}), shown = [], gone = [];
      for (let i = 0; i < 3; i++) {
        const t0 = performance.now();
        const tab = await page.browser.tabs.create(bg({windowId, cookieStoreId: space, url: "https://example.org/?smoke-many-probe-" + i, active: false, discarded: true}));
        if (!await until(() => rowOf(tab.id))) return {missing: tab.id};
        shown.push(performance.now() - t0);
        await wait(2500);  // tab sync takes it in after a moment
        const t1 = performance.now();
        await page.browser.tabs.remove(tab.id);
        if (!await until(() => !rowOf(tab.id))) return {stays: tab.id};
        gone.push(performance.now() - t1);
        await wait(500);
      }
      const after = await ask({type: "stats"});
      return {shown: Math.round(median(shown)), gone: Math.round(median(gone)), views: after.views - before.views, viewMs: Math.round((after.viewMs - before.viewMs) / Math.max(1, after.views - before.views))};""")
    numbers["newTabShownMs"], numbers["closedGoneMs"], numbers["viewMs"] = r.get("shown"), r.get("gone"), r.get("viewMs")
    check(f"a new tab is in the sidebar soon ({r.get('shown')} ms; gone {r.get('gone')} ms when closed)", (r.get("shown") or 1e9) < 3000 and (r.get("gone") or 1e9) < 3000, str(r))
    check(f"a view is quick to build ({r.get('viewMs')} ms)", (r.get("viewMs") or 1e9) < 300, str(r))

    # What drawing costs with nothing to change, and how big a view is.
    r = sidebar_page(m, MANY_PAGE + """
      let last = null;
      port.onMessage.addListener(v => { last = v; });
      send({type: "hello", windowId});
      for (let i = 0; i < 40 && !last; i++) await wait(100);
      const text = page.JSON.stringify(last), times = [], first = [];
      const draw = view => { const t0 = performance.now(); page.render(view); doc.documentElement.getBoundingClientRect(); return performance.now() - t0; };
      for (let i = 0; i < 5; i++) times.push(draw(page.JSON.parse(text)));
      // All rows new, as when a sidebar opens or a space is shown for the first time.
      for (let i = 0; i < 3; i++) {
        const view = page.JSON.parse(text);
        for (const tab of view.tabs) tab.id += 1e6 * (i + 1);
        first.push(draw(view));
        draw(page.JSON.parse(text));
      }
      return {bytes: text.length, rows: last.tabs.length, drawMs: Math.round(median(times) * 10) / 10, firstDrawMs: Math.round(median(first))};""")
    numbers["view"] = r
    check(f"drawing {r.get('rows')} rows is quick ({r.get('firstDrawMs')} ms all new, {r.get('drawMs')} ms with nothing to change)", (r.get("firstDrawMs") or 1e9) < 2000 and r["drawMs"] < 500, str(r))

    # A page whose title ticks: nothing to do for a sidebar showing another space,
    # and at most a view per tick where it is shown.
    r = sidebar_page(m, MANY_PAGE + """
      // Away: the last space, which no window shows (the first ones may be another window's).
      const here = spaces().find(s => s.active).id, away = spaces().filter(s => !s.active).at(-1).id, out = {};
      for (const [name, space] of [["away", away], ["here", here]]) {
        const tab = await page.browser.tabs.create(bg({windowId, cookieStoreId: space, url: args[0] + "/ticking", active: false}));
        await wait(2000);
        const before = await ask({type: "stats"});
        await wait(3000);
        const after = await ask({type: "stats"});
        out[name] = {views: after.views - before.views, ms: Math.round(after.viewMs - before.viewMs), jobs: after.jobs - before.jobs};
        await page.browser.tabs.remove(tab.id);
        await wait(1000);
      }
      return out;""", m.pages)
    numbers["ticking"] = r
    check("a page ticking in another space builds no view", r["away"]["views"] == 0, str(r))
    check("a page ticking in this one is drawn, with at most a view per tick", 1 <= r["here"]["views"] <= 25, str(r))

    # Selecting a ghost, in the window you are using.
    r = m.js(H + """const x = other(), times = []; x.focus(); await wait(500);
      for (const g of x.gBrowser.tabs.filter(t => !t.pinned && !t.hidden && role(x, t) === "ghost").slice(0, 5)) {
        const k = key(x, g), t0 = Date.now();
        x.gBrowser.selectedTab = g;
        for (let i = 0; i < 1000; i++) { const s = x.gBrowser.selectedTab; if (key(x, s) === k && role(x, s) === "live" && !url(s).includes("ghost.html")) { times.push(Date.now() - t0); break; } await wait(10); }
        await wait(800);
      }
      main().focus(); await wait(300);
      return times.sort((a, b) => a - b);""")
    numbers["ghostPullMs"] = r[len(r) >> 1] if r else None
    check(f"selecting a ghost brings its tab soon ({numbers['ghostPullMs']} ms)", len(r) == 5 and numbers["ghostPullMs"] < 5000, str(r))

    # Switching space, from a click to the sidebar having drawn that space's list. The dot
    # says so at the click itself, before anything has come back: until the list is there,
    # that is all that shows the click was taken.
    r = sidebar_page(m, MANY_PAGE + """
      const times = [], marked = [], order = spaces().map(s => s.id), shown = () => doc.documentElement.dataset.space, from = shown();
      const click = id => doc.querySelector(`#spaces .space[data-space="${id}"]`).click();
      for (const id of [...order.filter(s => s !== from).slice(0, 2), from, ...order.filter(s => s !== from).slice(0, 2), from]) {
        if (shown() === id) continue;
        const t0 = performance.now();
        click(id);
        marked.push(doc.querySelector("#spaces .space.going")?.dataset.space === id && shown() !== id);
        if (!await until(() => shown() === id && spaces().find(s => s.active).id === id && !doc.querySelector("#spaces.going, #spaces .going"))) return {stuck: id};
        times.push(performance.now() - t0);
        await wait(1000);
      }
      return {ms: Math.round(median(times)), most: Math.round(Math.max(...times)), marked};""")
    numbers["spaceSwitch"] = {k: v for k, v in r.items() if k != "marked"}
    check(f"switching space is quick ({r.get('ms')} ms)", (r.get("ms") or 1e9) < 3000, str(r))
    check("the dot of the space you go to is marked at the click, before its list has come, and the mark goes when it has", len(r.get("marked") or []) >= 4 and all(r["marked"]), str(r))
    shown = m.js(H + """const w = main(); await wait(500); return [...new Set(w.gBrowser.tabs.filter(t => !t.pinned && !t.hidden && t.userContextId).map(t => t.userContextId))];""")
    check("and shows one space", len(shown) == 1, str(shown))

    # Back in a space, the tab you used there, not one opened in another window meanwhile:
    # its placeholder here is newer, and selecting that would pull it out of that window.
    space = number
    m.js(H + """const w = main(); w.focus(); await wait(300);
      w.gBrowser.selectedTab = w.gBrowser.addTrustedTab(args[0] + "/icon?used", {userContextId: args[1]}); await wait(2500); return 1;""", m.pages, space)
    press(m, "2" if space == 1 else "1", CTRL)
    time.sleep(1.5)
    m.js(H + """other().gBrowser.addTrustedTab(args[0] + "/icon?elsewhere", {userContextId: args[1], inBackground: true}); await wait(3500); return 1;""", m.pages, space)
    press(m, str(space), CTRL)
    time.sleep(2)
    extension_message(m, {"type": "flush"})
    r = m.js(H + """const w = main(), s = w.gBrowser.selectedTab, used = w.gBrowser.tabs.find(t => url(t).endsWith("/icon?used"));
      const r = {selected: url(s), elsewhere: other().gBrowser.tabs.some(t => url(t).endsWith("/icon?elsewhere")), in: s.userContextId, used: used && key(w, used),
        picks: ((await storage("%s", ["spacePicks"])).spacePicks ?? {})["firefox-container-" + args[0]], inFront: wins().map(x => Services.focus.activeWindow === x)};
      await removeWhere((x, t) => url(t).includes("/icon?")); return r;""" % EXT_ID, space)
    check("back in a space, the tab you used is selected, and a tab opened elsewhere stays there", r["selected"].endswith("/icon?used") and r["elsewhere"], str(r))

    # A new window, on top of the two.
    before = sidebar_page(m, MANY_PAGE + """return await ask({type: "stats"});""")
    t0 = time.time()
    want = m.js(H + """const w = main(), want = [w.gBrowser.tabs.filter(t => t.pinned).length, w.gBrowser.tabs.filter(t => !t.pinned && role(w, t)).length];
      const n = w.OpenBrowserWindow(); n.__extra = true;
      for (let i = 0; i < 100 && !n.gBrowser; i++) await wait(100);
      return want;""")
    full = many_wait(m, H + """const n = wins().find(w => w.__extra); if (!n?.gBrowser) return false;
      return n.gBrowser.tabs.filter(t => t.pinned).length >= %d && n.gBrowser.tabs.filter(t => !t.pinned && role(n, t)).length >= %d;""" % tuple(want), 600)
    numbers["newWindowS"] = None if full is None else round(time.time() - t0, 1)
    settled = many_wait(m, H + """const n = wins().find(w => w.__extra); return n.gBrowser.tabs.filter(t => t.linkedPanel && !t.selected && url(t).includes("ghost.html")).length === 0;""", 600)
    numbers["newWindowSettledS"] = None if settled is None else round(time.time() - t0, 1)
    after = sidebar_page(m, MANY_PAGE + """return await ask({type: "stats"});""")
    numbers["newWindow"] = many_diff(before, after)
    numbers["memory2"] = m.js(PROC_INFO)["mb"]
    check(f"a new window gets all {n} tabs soon ({numbers['newWindowS']} s, {numbers['newWindowSettledS']} s until unloaded)",
          numbers["newWindowS"] is not None and numbers["newWindowS"] < n * 0.07 and settled is not None, str(numbers["newWindow"]))
    check(f"and takes little memory ({numbers['memory0']} MB before the tabs, {numbers['memory2']} MB after)", numbers["memory2"] - numbers["memory0"] < n * 1.5, str(numbers))
    m.js(H + """await close(wins().find(w => w.__extra)); return 1;""")

    # Nothing happening, with this many tabs: nothing done.
    idle = sidebar_page(m, MANY_PAGE + """return await ask({type: "idle", ms: 5000});""")
    numbers["idle"] = idle
    if idle["alarms"]:
        print(f"SKIP  idle check: a timed check ran meanwhile ({idle})", flush=True)
    else:
        check(f"with {n} tabs and nothing happening, Tidier does nothing", idle["jobs"] == 0 and idle["lookups"] == 0 and idle["views"] == 0, str(idle))

    # And all of them closed at once, everywhere.
    t0 = time.time()
    m.js(H + """for (const w of wins()) w.gBrowser.removeTabs(w.gBrowser.tabs.filter(t => url(t).includes("smoke-many-"))); return 1;""")
    gone = many_wait(m, H + """const all = (await storage("%s", ["syncedTabs"])).syncedTabs; return !Object.values(all).some(e => (e.url || "").includes("smoke-many-"));""" % EXT_ID, 600)
    numbers["closedAllS"] = gone
    left = many_wait(m, H + """const keys = new Set(Object.keys((await storage("%s", ["syncedTabs"])).syncedTabs));
      return !wins().some(w => w.gBrowser.tabs.some(t => { const k = value(w, t, "syncKey"); return k && !keys.has(k); }));""" % EXT_ID, 300)
    numbers["closedAllTabsS"] = None if left is None else round(time.time() - t0, 1)
    check(f"closing them all closes them everywhere ({numbers['closedAllTabsS']} s)", gone is not None and left is not None, str(numbers))
    r = sidebar_page(m, RECENTLY_CLOSED_PLACEHOLDERS)
    check("and leaves no placeholder in Recently Closed", not r["left"], str(r))
    m.js(H + """await removeWhere((x, t) => url(t).includes("ticking")); return 1;""")
    sidebar_page(m, MANY_PAGE + """const id = args[0]; if (spaces().find(s => s.active).id !== id) { doc.querySelector(`#spaces .space[data-space="${id}"]`).click(); await wait(1000); } return 1;""", space0)
    if made_window:
        m.js(H + """await close(other()); return 1;""")
    print("INFO  " + json.dumps(numbers), flush=True)


def alone_end(m):
    no_problems(m, "by the end of the chain")
