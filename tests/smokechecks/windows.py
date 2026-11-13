"""The small window for links from other apps."""
from testfirefox import EXT_ID
from smokechecks.base import CTRL, H, LITTLE, check, ext_page, extension_message, into_page, press, sidebar_page


def little_page(m, handle_part, selector):
    """The element `selector` in the page of a tab with this address, that tab selected. Only that
    tab: selecting each tab on the way would take the window through all its spaces."""
    into_page(m, handle_part, focus=True)  # not through every tab: that loads each unloaded one
    return m.cmd("WebDriver:FindElement", {"using": "css selector", "value": selector})


def little_menu(m, handle_part, selector, item):
    """Right-click `selector` in the page of a tab with this address, for real, and choose `item` in Firefox's menu."""
    found = little_page(m, handle_part, selector)
    m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "little", "parameters": {"pointerType": "mouse"}, "actions": [
        {"type": "pointerMove", "x": 0, "y": 0, "origin": {"element-6066-11e4-a52e-4f735466cecf": list(found.values())[0]}},
        {"type": "pointerDown", "button": 2}, {"type": "pointerUp", "button": 2}]}]})
    m.chrome()
    return m.js(LITTLE + """const [part, item] = args;
      const w = wins().find(w => url(w.gBrowser.selectedTab).includes(part)), menu = w.document.getElementById("contentAreaContextMenu");
      await until(() => menu.state === "open");
      await wait(300); // Tidier fills it in as it opens
      const items = () => [...menu.querySelectorAll("menuitem, menu")].filter(e => e.id.includes("tidier") && !e.hidden);
      const seen = items().map(e => e.label);
      const chosen = items().find(e => e.label === item);
      const inside = chosen?.closest("menu") ? [...chosen.closest("menu").querySelectorAll("menuitem")].map(e => e.label) : [];
      chosen?.doCommand(); // a hidden submenu's item cannot be activated, and its command is what counts
      await wait(200);
      menu.hidePopup();
      return {seen, inside, chosen: !!chosen};""", handle_part, item)


def little_click(m, handle_part, selector):
    """Click `selector` for real, in the page of a tab with this address."""
    found = little_page(m, handle_part, selector)
    m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "little-click", "parameters": {"pointerType": "mouse"}, "actions": [
        {"type": "pointerMove", "x": 0, "y": 0, "origin": {"element-6066-11e4-a52e-4f735466cecf": list(found.values())[0]}},
        {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}]}]})
    m.cmd("WebDriver:ReleaseActions")
    m.chrome()


def little_alt_click(m, handle_part, selector):
    """⌥-click `selector` for real, in the page of a tab with this address."""
    found = little_page(m, handle_part, selector)
    alt = "\ue00a"
    m.cmd("WebDriver:PerformActions", {"actions": [
        {"type": "key", "id": "little-keys", "actions": [{"type": "keyDown", "value": alt}, {"type": "pause"}, {"type": "pause"}, {"type": "pause"}, {"type": "keyUp", "value": alt}]},
        {"type": "pointer", "id": "little-mouse", "parameters": {"pointerType": "mouse"}, "actions": [
            {"type": "pause"}, {"type": "pointerMove", "x": 0, "y": 0, "origin": {"element-6066-11e4-a52e-4f735466cecf": list(found.values())[0]}},
            {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}, {"type": "pause"}]}]})
    m.cmd("WebDriver:ReleaseActions")
    m.chrome()


def alone_little_window(m):
    base = m.pages + "/links?little-"
    # Two windows, as tabs show in both. (alone_second_window may have opened one.)
    opened = m.js(H + """if (other()) return false;
      const w = main().OpenBrowserWindow(); w.__smoke = true;
      for (let i = 0; i < 100 && !(w.gBrowser && w.gBrowser.tabs.filter(t => role(w, t)).length); i++) await wait(100);
      await wait(1500); main().focus(); await wait(300); return true;""")

    # Off until you turn it on: a link from another app is an ordinary tab. Then on, with a
    # real click on the settings page.
    r = m.js(LITTLE + """const w = main(); await onSpaceTab();
      external(args[0]); await wait(2500);
      return {popups: popups().length, here: w.gBrowser.tabs.some(t => url(t).includes("little-default"))};""", base + "default")
    check("the small window is off until you turn it on: a link from another app is an ordinary tab", r["popups"] == 0 and r["here"], str(r))
    r = ext_page(m, "/settings/settings.html", """
      const box = doc.getElementById("little-window");
      for (let i = 0; i < 50 && doc.getElementById("little-section").hidden; i++) await wait(100);
      const shown = !doc.getElementById("little-section").hidden, was = box.checked;
      box.click(); await wait(400);
      return {shown, was, now: box.checked};""")
    check("the settings page has the on-off, off by default", r["shown"] and not r["was"] and r["now"], str(r))
    m.js(LITTLE + """await removeWhere((x, y) => url(y).includes("little-default") || url(y).includes("settings/settings.html")); main().focus(); await wait(300); return 1;""")

    # A link from another app, with a space's tab selected.
    r = m.js(LITTLE + """const w = main(); const on = await onSpaceTab(), n = w.gBrowser.tabs.length;
      external(args[0]);
      const p = await until(() => popups()[0]);
      if (!p) return {none: true};
      await until(() => url(p.gBrowser.selectedTab).includes("little-one"));
      await wait(2500); // long past the moment tab sync registers a new tab
      return {...shownIn(p), wanted: on.userContextId, back: w.gBrowser.selectedTab === on, more: w.gBrowser.tabs.length - n,
              elsewhere: wins().filter(x => x !== p).flatMap(x => x.gBrowser.tabs.filter(t => url(t).includes("little-one") || String(t.label).includes("little-one"))).length,
              recorded: (await record()).some(e => (e.url || "").includes("little-one")), active: Services.focus.activeWindow === p,
              inTitle: p.document.title.includes("127.0.0.1")};""", base + "one")
    check("a link from another app opens in a small window", not r.get("none") and r["tabs"] == 1, str(r))
    check("about 900 by 700", r.get("width") == 900 and r.get("height") == 700, str(r))
    check("in the space you are in", r.get("space") == r.get("wanted"), str(r))
    check("and it has the keyboard", r.get("active"), str(r))
    check("its address is in the title, for want of an address bar", r.get("inTitle"), str(r))
    check("your window stays as it was, on the same tab", r.get("more") == 0 and r.get("back"), str(r))
    check("it is not in tab sync until kept", r.get("elsewhere") == 0 and not r.get("recorded"), str(r))

    # The row in the sidebar, which brings it back and keeps it.
    r = sidebar_page(m, """
      for (let i = 0; i < 100 && !doc.querySelector("#little .little"); i++) await wait(100);
      const row = doc.querySelector("#little .little");
      if (!row) return {none: true};
      const seen = {keep: row.querySelector(".keep").textContent, rows: doc.querySelectorAll("#little .little").length, height: row.getBoundingClientRect().height};
      return seen;""")
    check("the sidebar has one quiet row for it, naming the space", r.get("rows") == 1 and r.get("keep", "").startswith("Keep in "), str(r))
    r = m.js(LITTLE + "return {front: Services.focus.activeWindow === popups()[0]};")
    check("(the test's own page took the keyboard)", not r["front"], str(r))
    sidebar_page(m, """doc.querySelector("#little .little").click(); await wait(600);""")
    r = m.js(LITTLE + "return {front: Services.focus.activeWindow === popups()[0]};")
    check("a click on the row brings the small window back", r["front"], str(r))

    page = m.js(LITTLE + "return popups()[0].gBrowser.selectedBrowser.innerWindowID;")
    r = sidebar_page(m, """
      doc.querySelector("#little .keep").click();
      for (let i = 0; i < 100 && doc.querySelector("#little .little"); i++) await wait(100);
      await wait(800);
      const first = doc.querySelector("#tabs > .tab");
      return {rowGone: !doc.querySelector("#little .little"), firstIsSelected: first?.classList.contains("active"), first: first?.title};""")
    check("Keep is one click, and the row goes", r.get("rowGone"), str(r))
    check("kept, it is first among today's tabs, and selected", r.get("firstIsSelected"), str(r))
    r = m.js(LITTLE + """await wait(800); const w = main(), o = other();
      const t = w.gBrowser.tabs.find(t => url(t).includes("little-one"));
      if (!t) return {none: true, popups: popups().length};
      const k = key(w, t), there = o.gBrowser.tabs.filter(x => key(o, x) === k);
      const rows = x => x.gBrowser.tabs.filter(y => !y.pinned && key(x, y) && y.userContextId === t.userContextId && !value(x, y, "folder"));
      return {popups: popups().length, selected: w.gBrowser.selectedTab === t, space: t.userContextId, page: t.linkedBrowser.innerWindowID, role: role(w, t),
              there: there.length, thereRole: there[0] && role(o, there[0]), firstHere: key(w, rows(w)[0]) === k, firstThere: key(o, rows(o)[0]) === k,
              recorded: (await record()).some(e => (e.url || "").includes("little-one"))};""")
    check("the small window closes with it", r.get("popups") == 0, str(r))
    check("it is your tab now: live here, a placeholder in the other window, in the record",
          r.get("role") == "live" and r.get("there") == 1 and r.get("thereRole") == "ghost" and r.get("recorded"), str(r))
    check("in the same place in both windows", r.get("firstHere") and r.get("firstThere"), str(r))
    check("the page was not loaded again", page and r.get("page") == page, f"{page} then {r}")
    r = m.js(LITTLE + """await wait(1500); const data = main().SessionStore.getClosedWindowData(), closed = typeof data === "string" ? JSON.parse(data) : data;
      return {kept: closed.filter(x => (x.tabs ?? []).some(t => (t.entries ?? []).some(e => (e.url || "").includes("little-one")))).length};""")
    check("a kept small window is not among the closed windows, so ⌘⇧N cannot bring its page back twice", r.get("kept") == 0, str(r))

    # The same link twice, as a double click in another app sends it: one small window.
    r = m.js(LITTLE + """await onSpaceTab(); external(args[0]); await wait(100); external(args[0]);
      await until(() => popups().length); await wait(2500);
      const got = {popups: popups().length, left: main().gBrowser.tabs.filter(t => url(t).includes("little-twice")).length};
      for (const p of popups()) p.close(); await until(() => !popups().length); await wait(500); return got;""", base + "twice")
    check("the same link twice opens one small window, and leaves nothing behind", r.get("popups") == 1 and r.get("left") == 0, str(r))

    # Closing it leaves nothing.
    r = m.js(LITTLE + """await onSpaceTab(); const before = (await record()).length, w0 = main();
      external(args[0]);
      const p = await until(() => popups()[0]);
      await until(() => url(p.gBrowser.selectedTab).includes("little-two"));
      // Its mark, which ⌘⇧T below needs to know it again (sessions.setWindowValue, littlewindow.js).
      await until(() => w0.SessionStore.getCustomWindowValue(p, "extension:EXT:little"), 5000);
      const mark = w0.SessionStore.getCustomWindowValue(p, "extension:EXT:little");
      p.BrowserCommands.closeTabOrWindow(); // ⌘W
      await until(() => !popups().length); await wait(800);
      return {mark, popups: popups().length, more: (await record()).length - before,
              left: wins().flatMap(x => x.gBrowser.tabs.filter(t => url(t).includes("little-two"))).length};""".replace("EXT", EXT_ID), base + "two")
    check("a small window carries its mark, for Firefox to keep with it", r["mark"] == "true", str(r))
    check("⌘W closes it, and it leaves nothing", r["popups"] == 0 and r["more"] == 0 and r["left"] == 0, str(r))
    r = sidebar_page(m, """await wait(300); return {rows: doc.querySelectorAll("#little .little").length};""")
    check("and the row goes with it", r["rows"] == 0, str(r))

    # ⌘⇧T right after: Firefox reopens the window, and it is a small window again.
    r = m.js(LITTLE + """const w = main(); w.focus(); await wait(300);
      (w.SessionWindowUI ?? w).restoreLastClosedTabOrWindowOrSession(w);
      const p = await until(() => popups()[0]);
      if (!p) return {none: true};
      await until(() => p.document.title.includes(" · "));
      // (And whether Firefox gave it back its mark, sessions.setWindowValue: what Tidier knows it by.)
      // (And whether Firefox gave it back as a popup to extensions: windows.onCreated's type.)
      const flags = p.docShell.treeOwner.QueryInterface(Ci.nsIInterfaceRequestor).getInterface(Ci.nsIAppWindow).chromeFlags;
      return {...shownIn(p), mark: w.SessionStore.getCustomWindowValue(p, "extension:%s:little"), dialog: !!(flags & Ci.nsIWebBrowserChrome.CHROME_OPENAS_DIALOG)};""" % EXT_ID)
    check("⌘⇧T brings it back as a small window, with its space in its title", "little-two" in r.get("url", "") and " · " in r.get("title", ""), str(r))
    r = sidebar_page(m, """for (let i = 0; i < 100 && !doc.querySelector("#little .little"); i++) await wait(100);
      const row = doc.querySelector("#little .little"); if (!row) return {none: true};
      const keep = row.querySelector(".keep").textContent; row.querySelector(".close").click();
      for (let i = 0; i < 100 && doc.querySelector("#little .little"); i++) await wait(100);
      return {keep, rows: doc.querySelectorAll("#little .little").length};""")
    check("with its row, whose × closes it", r.get("keep", "").startswith("Keep in ") and r["rows"] == 0, str(r))
    r = m.js(LITTLE + """await until(() => !popups().length); return {popups: popups().length};""")
    check("(and that window is gone)", r["popups"] == 0, str(r))

    # What Firefox gives a link: no container, or, if a visible tab is on the same host, that
    # tab's (URILoadingHelper.guessUserContextId). "localhost" is on no tab until these open it.
    other = m.pages.replace("127.0.0.1", "localhost") + "/links?little-"
    watch = """const w = main(), c = w.gBrowser.tabContainer, seen = {opened: [], adopted: 0, shown: 0};
      const opened = e => seen.opened.push(e.target.userContextId), closed = e => { if (e.detail?.adoptedBy) seen.adopted++; }, shown = () => seen.shown++;
      c.addEventListener("TabOpen", opened); c.addEventListener("TabClose", closed); c.addEventListener("TabShow", shown);
      const unwatch = () => { c.removeEventListener("TabOpen", opened); c.removeEventListener("TabClose", closed); c.removeEventListener("TabShow", shown); };
      const around = async (name, u) => { const on = w.gBrowser.selectedTab, closedTabs = w.SessionStore.getClosedTabCountForWindow(w); external(u);
        const p = await until(() => popups().find(x => url(x.gBrowser.selectedTab).includes(name)));
        if (!p) { unwatch(); return {none: true}; }
        await wait(1200); unwatch();
        const got = {...shownIn(p), on: on.userContextId, same: w.gBrowser.selectedTab === on, ...seen, left: w.gBrowser.tabs.filter(t => url(t).includes(name)).length, closed: w.SessionStore.getClosedTabCountForWindow(w) - closedTabs};
        p.close(); await until(() => !popups().length); await wait(500); return got; };"""
    r = m.js(LITTLE + """await onSpaceTab();""" + watch + """return around("little-fresh", args[0]);""", other + "fresh")
    check("a link to a site no tab is on has no container, and opens again in your space", r.get("opened") == [0] and r.get("space") == r.get("on") and not r.get("adopted") and r.get("left") == 0, str(r))
    check("your window stays on the same tab", r.get("same"), str(r))
    check("and ⌘⇧T does not bring back that first tab instead of what you closed", r.get("closed") == 0, str(r))

    r = m.js(LITTLE + """const here = await onSpaceTab();
      const same = main().gBrowser.addTrustedTab(args[0] + "same-host", {userContextId: here.userContextId, inBackground: true}); await wait(1500);""" + watch + """
      const got = await around("little-guess-here", args[0] + "guess-here"); w.gBrowser.removeTab(same); await wait(500); return got;""", other)
    check("a link to a site you have a tab on in this space moves as it is, not loaded twice", r.get("opened") == [r.get("on")] and r.get("adopted") == 1 and r.get("space") == r.get("on") and r.get("same"), str(r))
    check("with its space in its title too", " · " in r.get("title", ""), str(r))

    # An essential of another space is always visible to that guess. Selected in that container,
    # the new tab must not take your window there, not even until the page answers.
    r = m.js(LITTLE + """const here = await onSpaceTab(); const there = here.userContextId === 1 ? 2 : 1;
      const pin = main().gBrowser.addTrustedTab(args[0] + "essential", {userContextId: there, inBackground: true}); await wait(800); main().gBrowser.pinTab(pin); await wait(1500);""" + watch + """
      const got = await around("little-guess-there", args[0] + "guess-there");
      w.gBrowser.unpinTab(pin); await wait(300); w.gBrowser.removeTab(pin); await wait(1200);
      return {...got, there};""", other)
    check("a link Firefox puts in another space's container opens in your space", r.get("opened") == [r.get("there")] and r.get("space") == r.get("on") and r.get("left") == 0, str(r))
    check("and your window does not go there, not even for a moment", r.get("same") and r.get("shown") == 0, str(r))

    # A key that changes space, while a small window has the keyboard, has nothing to do there.
    r = m.js(LITTLE + """await onSpaceTab(); external(args[0]); const p = await until(() => popups()[0]);
      await until(() => url(p.gBrowser.selectedTab).includes("little-key")); await wait(600); p.focus(); await wait(500);
      return {front: Services.focus.activeWindow === p};""", other + "key")
    press(m, "2", CTRL)
    r = {**r, **m.js(LITTLE + """await wait(1500); const p = popups()[0], got = {tabs: p?.gBrowser.tabs.length, stays: p && url(p.gBrowser.selectedTab).includes("little-key")};
      p?.close(); await until(() => !popups().length); await wait(500); return got;""")}
    check("⌃2 in a small window adds nothing to it", r["front"] and r["tabs"] == 1 and r["stays"], str(r))

    # A tab opened any other way is what it always was.
    r = m.js(LITTLE + """const w = main(); await onSpaceTab();
      const out = {};
      const tryIt = async (name, open) => {
        const n = wins().length; open(); await wait(1500);
        out[name] = popups().length;
        for (const p of popups()) p.close();
        await until(() => !popups().length);
      };
      const principal = Services.scriptSecurityManager.getSystemPrincipal();
      await tryIt("bookmark", () => w.openTrustedLinkIn(args[0] + "bookmark", "tab"));
      await tryIt("address", () => { w.gURLBar.value = args[0] + "address"; w.gURLBar.focus(); w.gURLBar.handleCommand(new w.KeyboardEvent("keydown", {altKey: true, key: "Enter"})); });
      await tryIt("related", () => w.openLinkIn(args[0] + "related", "tab", {triggeringPrincipal: principal, relatedToCurrent: true}));
      await tryIt("background", () => w.gBrowser.addTrustedTab(args[0] + "background", {inBackground: true}));
      await tryIt("newtab", () => w.BrowserCommands.openTab());
      const closed = w.gBrowser.tabs.find(t => url(t).includes("little-bookmark"));
      if (closed) { w.gBrowser.removeTab(closed); await wait(800); await tryIt("reopened", () => w.SessionStore.undoCloseTab(w, 0)); }
      for (const name of ["bookmark", "address", "related", "background"]) out[name + "Here"] = w.gBrowser.tabs.some(t => url(t).includes("little-" + name));
      return out;""", base)
    check("a bookmark, an address, a link from a page and a new tab are not small windows",
          not any(r.get(k) for k in ("bookmark", "address", "related", "background", "newtab", "reopened")), str(r))
    check("they stay in your list", r.get("addressHere") and r.get("relatedHere") and r.get("backgroundHere"), str(r))
    m.js(LITTLE + """await removeWhere((x, y) => url(y).includes("little-")); return 1;""")

    # A real click on a page's own links: a new tab, and a sign-in's window.
    m.js(H + """const w = main(); w.focus(); const t = w.gBrowser.addTrustedTab(args[0], {userContextId: 1}); w.gBrowser.selectedTab = t; await wait(1500); return 1;""", m.pages + "/links?little-page")
    little_click(m, "little-page", "#new")
    r = m.js(LITTLE + """const w = main(); const t = await until(() => w.gBrowser.tabs.find(t => url(t).includes("little-new-tab"))); await wait(1500);
      return {here: !!t, popups: popups().length, selected: w.gBrowser.selectedTab === t};""")
    check("a page's own link to a new tab stays in your list", r["here"] and r["popups"] == 0, str(r))
    m.js(H + """const w = main(), t = w.gBrowser.tabs.find(t => url(t).includes("little-page")); w.gBrowser.selectedTab = t; await wait(600); return 1;""")
    little_click(m, "little-page", "#sign-in")
    r = m.js(LITTLE + """const p = await until(() => popups()[0]); if (!p) return {none: true}; await until(() => url(p.gBrowser.selectedTab).includes("little-sign-in")); await wait(1500);
      const got = shownIn(p); p.close(); await until(() => !popups().length); await wait(500); return got;""")
    check("a sign-in's window stays what its page opened: no small window", "little-sign-in" in r.get("url", "") and r.get("width") != 900 and " · " not in r.get("title", ""), str(r))
    m.js(LITTLE + """await removeWhere((x, y) => url(y).includes("little-")); return 1;""")

    # While another app has the keyboard. A window Firefox does not count as a browser is the
    # nearest a headless Firefox has: extensions are told that no window has the focus.
    r = m.js(LITTLE + """await onSpaceTab();
      const d = Services.ww.openWindow(null, "chrome://browser/content/aboutDialog.xhtml", "_blank", "chrome,all,dialog=no", null);
      await wait(1000); d.focus(); await wait(600);
      const away = Services.focus.activeWindow === d;
      external(args[0]);
      const p = await until(() => popups()[0]);
      await wait(600);
      const got = p ? {...shownIn(p), front: Services.focus.activeWindow === p} : {none: true};
      d.close(); p?.close(); await until(() => !popups().length); main().focus(); await wait(300);
      return {away, ...got};""", base + "away")
    check("a link from another app while Firefox is behind it", r.get("away") and r.get("tabs") == 1 and r.get("front"), str(r))

    # A selected tab with no container (a page like this one): into the space you are in.
    # A rule: into its space. Both are opened again there, and the first tab goes.
    r = m.js(LITTLE + """const w = main(); const space = (await onSpaceTab()).userContextId;
      const plain = w.gBrowser.addTrustedTab("about:about"); w.gBrowser.selectedTab = plain; await wait(600);
      external(args[0]);
      const p = await until(() => popups()[0]);
      if (!p) return {none: true};
      await until(() => url(p.gBrowser.selectedTab).includes("little-plain"));
      const got = {...shownIn(p), wanted: space, left: w.gBrowser.tabs.filter(t => url(t).includes("little-plain")).length};
      p.close(); await until(() => !popups().length); w.gBrowser.removeTab(plain); await wait(300);
      return got;""", base + "plain")
    check("with a page without a container selected, it opens in the space you are in", r.get("space") == r.get("wanted") and r.get("left") == 0, str(r))
    extension_message(m, {"type": "settings:rules", "rules": [{"url": "little-ruled", "space": "firefox-container-2"}]})
    r = m.js(LITTLE + """const w = main(); await onSpaceTab(); w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => !t.hidden && !t.pinned && t.userContextId === 1) ?? w.gBrowser.selectedTab; await wait(400);
      const on = w.gBrowser.selectedTab.userContextId;
      external(args[0]);
      const p = await until(() => popups()[0]);
      if (!p) return {none: true};
      await until(() => url(p.gBrowser.selectedTab).includes("little-ruled"));
      await wait(800);
      return {...shownIn(p), on, left: w.gBrowser.tabs.filter(t => url(t).includes("little-ruled")).length, popups: popups().length};""", base + "ruled")
    check("a rule decides its space, and nothing sends it back", r.get("space") == 2 and r.get("left") == 0 and r.get("popups") == 1, str(r))
    # Kept from there: it is selected, so you go along to its space, as with any tab you select.
    r = sidebar_page(m, """const keep = doc.querySelector("#little .keep"); const label = keep?.textContent; keep?.click();
      for (let i = 0; i < 100 && doc.querySelector("#little .little"); i++) await wait(100);
      await wait(800);
      return {label, active: spaces().find(s => s.active).id, first: doc.querySelector("#tabs > .tab")?.classList.contains("active")};""")
    check("kept, you go along to its space", r["label"] == "Keep in Space 2" and r["active"] == "firefox-container-2" and r["first"], str(r))
    extension_message(m, {"type": "settings:rules", "rules": []})
    sidebar_page(m, """doc.querySelector('#spaces .space[data-space="firefox-container-1"]').click(); await wait(800);""")

    # Firefox's own menus, opened for real on a real page.
    m.js(H + """const w = main(); w.focus(); const t = w.gBrowser.addTrustedTab(args[0], {userContextId: 1}); w.gBrowser.selectedTab = t; await wait(1500); return 1;""", m.pages + "/links?little-page")
    r = little_menu(m, "little-page", "#a", "Small window")
    check("a link's menu offers a small window and the other spaces", "Small window" in r["inside"] and len(r["inside"]) >= 3, str(r))
    r = m.js(LITTLE + """const p = await until(() => popups()[0]);
      if (!p) return {none: true};
      await until(() => url(p.gBrowser.selectedTab).includes("little-from-a-link"));
      return shownIn(p);""")
    check("it opens in a small window, in the page's space", r.get("space") == 1 and r.get("tabs") == 1, str(r))
    r = little_menu(m, "little-from-a-link", "body", "Keep in Space 1")
    check("in a small window the page's menu has Keep", r["chosen"], str(r))
    r = m.js(LITTLE + """await until(() => !popups().length); await wait(600); const w = main();
      const t = w.gBrowser.tabs.find(t => url(t).includes("little-from-a-link"));
      return {popups: popups().length, here: !!t, selected: w.gBrowser.selectedTab === t, role: t && role(w, t)};""")
    check("and Keep from there keeps it", r["popups"] == 0 and r["here"] and r["selected"] and r["role"] == "live", str(r))
    m.js(H + """const w = main(); w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes("little-page")); await wait(500); return 1;""")
    r = little_menu(m, "little-page", "#a", "Space 2")
    check("a link can be opened in another space", r["chosen"], str(r))
    r = m.js(LITTLE + """const w = main(); const t = await until(() => w.gBrowser.tabs.find(t => t.userContextId === 2 && url(t).includes("little-from-a-link")));
      await wait(1500);
      return {there: !!t, hidden: t?.hidden, stayed: url(w.gBrowser.selectedTab).includes("little-page"), popups: popups().length};""")
    check("in that space, out of sight, and you stay where you are", r["there"] and r["hidden"] and r["stayed"] and r["popups"] == 0, str(r))
    r = little_menu(m, "little-page", "body", "Keep")
    check("outside a small window, the page's menu has no Keep", not r["chosen"], str(r))
    m.js(LITTLE + """await removeWhere((x, y) => url(y).includes("little-")); return 1;""")

    # ⌥-click: a real one, with the access given, and then taken back.
    access = """const {ExtensionPermissions} = ChromeUtils.importESModule("resource://gre/modules/ExtensionPermissions.sys.mjs");
      const id = args[0], ext = WebExtensionPolicy.getByID(id).extension;
      await ExtensionPermissions.%s(id, {permissions: [], origins: ["<all_urls>"]}, ext); await wait(800); return 1;"""
    open_page = """const w = main(); w.focus(); await removeWhere((x, y) => url(y).includes("little-from-a-link") || url(y).includes("little-page")); const t = w.gBrowser.addTrustedTab(args[0], {userContextId: 1}); w.gBrowser.selectedTab = t; await wait(1500); return 1;"""
    state = LITTLE + """await wait(1500); return {popups: popups().length, spaces: popups().map(p => p.gBrowser.selectedTab.userContextId), stayed: url(main().gBrowser.selectedTab).includes("little-page")};"""
    m.js(H + access % "add", EXT_ID)
    m.js(H + open_page, m.pages + "/links?little-page")
    little_alt_click(m, "little-page", "#a")
    r = m.js(state)
    check("with the access given, ⌥-click opens a link in a small window, in the page's space", r["popups"] == 1 and r["spaces"] == [1] and r["stayed"], str(r))
    m.js(LITTLE + """for (const p of popups()) p.close(); await until(() => !popups().length); return 1;""")
    into_page(m, "little-page")  # not through every tab: that loads each unloaded one
    m.cmd("WebDriver:ExecuteScript", {"script": """document.querySelector("#a").addEventListener("click", e => e.preventDefault());
      document.querySelector("#a").dispatchEvent(new MouseEvent("click", {altKey: true, bubbles: true, cancelable: true}));"""})
    m.chrome()
    r = m.js(state)
    check("a page cannot open one by sending itself the click", r["popups"] == 0, str(r))
    m.js(H + access % "remove", EXT_ID)
    m.js(H + open_page, m.pages + "/links?little-page")
    little_alt_click(m, "little-page", "#a")
    r = m.js(state)
    check("without the access, there is no script and ⌥-click is Firefox's", r["popups"] == 0, str(r))
    m.js(LITTLE + """await removeWhere((x, y) => url(y).includes("little-")); return 1;""")

    # Off in the settings, with a real click there.
    r = ext_page(m, "/settings/settings.html", """
      const box = doc.getElementById("little-window");
      for (let i = 0; i < 50 && doc.getElementById("little-section").hidden; i++) await wait(100);
      const shown = !doc.getElementById("little-section").hidden, was = box.checked;
      box.click(); await wait(400);
      return {shown, was, now: box.checked};""")
    check("and it is turned off there again", r["shown"] and r["was"] and not r["now"], str(r))
    r = m.js(LITTLE + """const w = main(); await onSpaceTab();
      external(args[0]); await wait(2500);
      return {popups: popups().length, here: w.gBrowser.tabs.some(t => url(t).includes("little-off"))};""", base + "off")
    check("off, a link is an ordinary tab", r["popups"] == 0 and r["here"], str(r))

    m.js(LITTLE + """await removeWhere((x, y) => url(y).includes("little-") || url(y).includes("settings/settings.html")); main().focus(); await wait(300);
      if (args[0]) { other().close(); await wait(1500); } return 1;""", opened)
    m.chrome()
    kept = extension_message(m, {"type": "stats"})["sizes"]
    check("nothing is kept of them in memory", kept["littles"] == 0 and kept["newBlanks"] == 0, str(kept))


def alone_little_restart(m):
    if not m.can_restart:
        print("SKIP  alone_little_restart (needs Tidier installed for real: Developer Edition, or --xpi)", flush=True)
        return
    extension_message(m, {"type": "little:set", "on": True})  # off until you turn it on
    m.js(LITTLE + """await onSpaceTab(); external(args[0]); const p = await until(() => popups()[0]); await until(() => url(p.gBrowser.selectedTab).includes("little-restart")); await wait(2500); return 1;""", m.pages + "/links?little-restart")
    m.restart()
    r = m.js(LITTLE + """const p = await until(() => popups()[0], 30000); await wait(12000);
      await removeWhere((x, y) => url(y).includes("sidebar/sidebar.html") || url(y).includes("settings/settings.html")); // restored, and not loaded
      return {back: !!p, url: p ? url(p.gBrowser.selectedTab) : null, title: p?.document.title};""")
    check("a small window comes back after a restart", r["back"] and "little-restart" in r["url"], str(r))
    check("with its space in its title", " · " in (r["title"] or ""), str(r))
    if r["back"]:
        r = sidebar_page(m, """for (let i = 0; i < 100 && !doc.querySelector("#little .little"); i++) await wait(100);
          const keep = doc.querySelector("#little .keep"); const label = keep?.textContent; keep?.click(); await wait(1500); return {label};""")
        check("and it can still be kept", (r.get("label") or "").startswith("Keep in "), str(r))
        r = m.js(LITTLE + """await until(() => !popups().length); const w = main(); return {popups: popups().length, here: w.gBrowser.tabs.some(t => url(t).includes("little-restart"))};""")
        check("from there, into your list", r["popups"] == 0 and r["here"], str(r))
