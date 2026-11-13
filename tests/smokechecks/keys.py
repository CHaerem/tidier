"""The command bar, the shortcuts, and the keyboard in the sidebar."""
import json
import time
from testfirefox import EXT_ID
from smokechecks.base import (
    BAR, CMD, CTRL, DOWN, ENTER, ESC, H, SHIFT,
    TAB, UP, bar_is_open, bar_keys, bar_open, bar_page, bar_rows_until, check,
    ext_page, extension_message, into_page, press, press_in, sidebar_page, wait_for_bar,
)


def alone_shortcuts(m):
    ALT, UP, DOWN, LEFT, RIGHT, ENTER, BACKSPACE = "", "", "", "", "", "", ""
    # A row or tile by what stays the same when a placeholder's real tab is pulled in: its record's key.
    ident = H + """const {ExtensionParent} = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
      const tabId = t => ExtensionParent.apiManager.global.tabTracker.getId(t), who = (w, t) => key(w, t) || ek(w, t);
      const selected = () => { const w = main(); return who(w, w.gBrowser.selectedTab); };"""

    def drawn():
        """What the sidebar draws, top to bottom, without the test's own page, and as records' keys."""
        ids = sidebar_page(m, """await wait(300); const me = (await page.browser.tabs.getCurrent()).id;
          return [...doc.querySelectorAll(".tile, #tabs .tab")].filter(e => e.offsetParent !== null).map(e => Number(e.dataset.tab)).filter(id => id !== me);""")
        return m.js(ident + """const w = main(); await removeWhere((x, t) => url(t).includes("/sidebar/sidebar.html"));
          return args[0].map(id => { const t = w.gBrowser.tabs.find(x => tabId(x) === id); return t ? who(w, t) : null; });""", ids)

    def selects(want):
        return m.js(ident + "for (let i = 0; i < 100; i++) { if (selected() === args[0]) return true; await wait(100); } return false;", want)

    def go(*keys):
        m.js(H + "main().focus(); await wait(100); return 1;")
        press(m, *keys)

    def hold(key, *mods):
        """A key held down: each further keyDown is a repeat, and fires the command again, as a real keyboard's do."""
        m.js(H + "main().focus(); await wait(100); return 1;")
        acts = [{"type": "keyDown", "value": k} for k in mods] + [{"type": "keyDown", "value": key}] * 4 + [{"type": "keyUp", "value": key}]
        acts += [{"type": "keyUp", "value": k} for k in reversed(mods)]
        m.cmd("WebDriver:PerformActions", {"actions": [{"type": "key", "id": "kb", "actions": acts}]})
        m.cmd("WebDriver:ReleaseActions")

    # The real sidebar panel, not its page in a tab: what has the keyboard is what these checks are about.
    panel = """const v = page.browser.extension.getViews({type: "sidebar", windowId: (await page.browser.windows.getCurrent()).id})[0];
      return {focus: v.document.hasFocus(), renaming: v.document.querySelectorAll(".renaming").length};"""
    keyboard_on_page = H + "const w = main(); w.focus(); w.gBrowser.selectedBrowser.focus(); await wait(300); return 1;"
    keyboard_in_panel = H + """const w = main(), outer = w.SidebarController.browser; w.focus(); outer.focus(); await wait(100);
      outer.contentDocument.getElementById("webext-panels-browser").focus(); await wait(400); return 1;"""

    # ⌘1 to ⌘9 and ⌘D are Firefox's too until they are cleared in about:keyboard (customKeys.json
    # in the dotfiles, reported to the owner), and with the keyboard in a page both would act.
    firefox_keys = ["addBookmarkAsKb", "key_selectLastTab"] + [f"key_selectTab{n}" for n in range(1, 9)]
    custom_keys = """const {CustomKeys} = ChromeUtils.importESModule("moz-src:///browser/components/customkeys/CustomKeys.sys.mjs");
      for (const id of args[0]) CustomKeys[args[1]](id); return 1;"""
    m.js(custom_keys, firefox_keys, "clearKey")
    # The pages of the checks before this one would be rows too.
    m.js(H + """await removeWhere((x, t) => /\\/(settings\\/settings|sidebar\\/sidebar)\\.html/.test(url(t))); return 1;""")

    # In the second space, with a tab of that space in a folder: Firefox's own keys would go to
    # the first space's essentials, and to the tabs in the window's order.
    press(m, "2", CTRL)
    time.sleep(1)
    setup = sidebar_page(m, """await wait(300);
      const space = spaces().find(s => s.active).id;
      send({type: "newFolder", space, name: "Keys folder"}); await wait(800);
      const box = [...doc.querySelectorAll("#tabs .folder")].find(f => f.querySelector(".title").textContent === "Keys folder");
      const me = (await page.browser.tabs.getCurrent()).id;
      const rows = [...doc.querySelectorAll("#tabs > .tab")].map(r => Number(r.dataset.tab)).filter(id => id !== me);
      send({type: "moveTab", tabId: rows.at(-1), folder: box.dataset.key, before: null}); await wait(800);
      return {folder: box.dataset.key, space, inFolder: rows.at(-1)};""")
    order = drawn()
    # Nothing selected in the folder, so closing it below keeps the list simple.
    check("the test's list has essentials, a folder's tab and today's tabs", len(order) >= 4 and None not in order, str(order))
    start = order.index(m.js(ident + "return selected();"))
    # A quick press over an unloaded tab can be lost in Firefox before it reaches any extension
    # (README, Testing; about one in eight in a slowed-down test Firefox). Such a press, and only
    # one Tidier never heard of (its "key" line, common.js trace), with the selection where it
    # was, is pressed again, as a hand would; one Tidier heard and got wrong still fails.
    heard = H + """return Cc["@mozilla.org/consoleAPI-storage;1"].getService(Ci.nsIConsoleAPIStorage).getEvents()
      .filter(e => e.arguments?.[0] === "Tidier:" && / key next-tab$/.test(e.arguments?.[1] ?? "")).length;"""
    walked, lost = [], 0
    for i in range(1, len(order) + 1):
        want, was, before = order[(start + i) % len(order)], m.js(ident + "return selected();"), m.js(heard)
        go(DOWN, CMD, CTRL)
        ok = selects(want)
        if not ok and m.js(heard) == before and m.js(ident + "return selected();") == was:
            lost += 1
            go(DOWN, CMD, CTRL)
            ok = selects(want)
        walked.append(ok)
    if lost:
        print(f"INFO  ⌃⌘↓ presses lost before they reached Tidier, and pressed again: {lost} of {len(order)}", flush=True)
    check("⌃⌘↓ goes to the next tab as shown, and round the end", all(walked), f"{walked} on {order}, {lost} lost")
    go(UP, CMD, CTRL)
    check("⌃⌘↑ goes to the previous tab as shown", selects(order[(start - 1) % len(order)]), str(order))
    # Held down: each press goes on from where the one before it got to, with placeholders being pulled in.
    go("1", CMD)
    selects(order[0])
    for _ in range(3):
        press(m, DOWN, CMD, CTRL)
    check("⌃⌘↓ pressed quickly goes just as far", selects(order[3]), str(order))

    go("1", CMD)
    check("⌘1 goes to this space's first essential", selects(order[0]), str(order))
    go("3", CMD)
    check("⌘3 goes to the third tab as shown, essentials first", selects(order[2]), str(order))
    was = m.js(ident + "return selected();")
    go("9", CMD)
    time.sleep(0.5)
    check("⌘9 past the end of the list does nothing", m.js(ident + "return selected();") == was or len(order) >= 9, str(order))

    # A closed folder's tabs are not in the list. The selection is outside it, as a click would leave it.
    go("1", CMD)
    selects(order[0])
    sidebar_page(m, """await wait(200); send({type: "foldFolder", key: arguments[0], collapsed: true}); await wait(600); return 1;""".replace("arguments[0]", "args[0]"), setup["folder"])
    closed = drawn()
    check("a closed folder's tab is not drawn", len(closed) == len(order) - 1, f"{closed} of {order}")
    walked = []
    at = closed.index(order[0])
    for i in range(1, len(closed) + 1):
        go(DOWN, CMD, CTRL)
        walked.append(selects(closed[(at + i) % len(closed)]))
    check("⌃⌘↓ passes over a closed folder", all(walked), f"{walked} on {closed}")

    # Spaces, along the bar.
    r = sidebar_page(m, "await wait(300); return spaces();")
    bar = [s["id"] for s in r]
    here = next(s["id"] for s in r if s["active"])
    space_now = H + """for (let i = 0; i < 100; i++) { if (ctxOf(main().gBrowser.selectedTab) === args[0]) return true; await wait(100); } return false;"""
    m.js(H + """await removeWhere((x, t) => url(t).includes("/sidebar/sidebar.html")); return 1;""")
    go(LEFT, CMD, CTRL)
    check("⌃⌘← goes to the previous space on the bar", m.js(space_now, bar[bar.index(here) - 1]), f"{here} on {bar}")
    go(RIGHT, CMD, CTRL)
    check("⌃⌘→ goes to the next space on the bar", m.js(space_now, here), f"{here} on {bar}")

    # The last tab ⌘ and a digit reaches: earlier groups can leave more than nine.
    last = min(len(closed), 9)
    go(str(last), CMD)
    selects(closed[last - 1])
    r0 = m.js(ident + "const w = main(); return {who: selected(), pinned: w.gBrowser.selectedTab.pinned};")
    hold("d", CMD)
    pinned = m.js(H + "for (let i = 0; i < 50 && !main().gBrowser.selectedTab.pinned; i++) await wait(100); await wait(1000); return main().gBrowser.selectedTab.pinned;")
    tiles = sidebar_page(m, "await wait(300); return doc.querySelectorAll('#essentials .tile.active').length;")
    check("⌘D makes the selected tab an essential, however long it is held", r0["pinned"] is False and pinned and tiles == 1, f"{r0}, {pinned}, {tiles}")
    m.js(H + """await removeWhere((x, t) => url(t).includes("/sidebar/sidebar.html")); return 1;""")
    go("d", CMD)
    unpinned = m.js(H + "for (let i = 0; i < 50 && main().gBrowser.selectedTab.pinned; i++) await wait(100); await wait(500); return !main().gBrowser.selectedTab.pinned;")
    check("⌘D again makes it an ordinary tab", unpinned, "")

    # New folder. With the keyboard on the page it is simply there: Firefox lets no frame take the
    # keyboard from another, so nothing can ask for its name. With the keyboard in the sidebar it can.
    folders_now = H + """await wait(800); const all = (await storage(args[0], ["syncedTabs"])).syncedTabs; return Object.values(all).filter(e => e.own).map(e => e.name);"""
    before = m.js(folders_now, EXT_ID)
    m.js(keyboard_on_page)
    hold("n", CMD, ALT)
    after = m.js(folders_now, EXT_ID)
    check("⌘⌥N makes one folder in this space, however long it is held", sorted(after) == sorted(before + ["New folder"]), f"{before} -> {after}")
    state = sidebar_page(m, panel)
    active = sidebar_page(m, "await wait(300); return spaces().find(s => s.active).id;")
    check("and with the keyboard on the page, no name field waits for it in the sidebar", state == {"focus": False, "renaming": 0} and active == setup["space"], f"{state} {active}")
    m.js(H + """await removeWhere((x, t) => url(t).includes("/sidebar/sidebar.html")); return 1;""")
    time.sleep(1.1)  # two presses, not a key held down
    m.js(keyboard_in_panel)
    press(m, "n", CMD, ALT)
    m.js(H + "await wait(800); return 1;")
    state = sidebar_page(m, panel)
    check("with the keyboard in the sidebar, the name field takes it", state == {"focus": True, "renaming": 1}, str(state))
    for letter in "Typed":
        press(m, letter)
    press(m, ENTER)
    after = m.js(folders_now, EXT_ID)
    check("and what you type next is the folder's name", "Typed" in after, f"{before} -> {after}")
    # The others work from there too: the sidebar lets through what its own keys do not use.
    m.js(H + """await removeWhere((x, t) => url(t).includes("/sidebar/sidebar.html")); return 1;""")
    go("1", CMD)
    selects(closed[0])
    m.js(keyboard_in_panel)
    press(m, DOWN, CMD, CTRL)
    check("with the keyboard in the sidebar, ⌃⌘↓ goes to the next tab", selects(closed[1]), str(closed))
    m.js(keyboard_on_page)

    # The settings page lists them, and changes one with a real key press.
    def settings(script, *args):
        return ext_page(m, "/settings/settings.html", script, *args)
    listed = settings("""await wait(800); return {shown: !doc.getElementById("keys-section").hidden,
      lines: [...doc.querySelectorAll("#keys [data-command]")].map(k => [k.dataset.command, k.textContent])};""")
    keys = dict(listed["lines"])
    check("the settings page lists the commands with their keys", listed["shown"] and keys.get("next-tab") == "⌃⌘↓" and keys.get("tab-1") == "⌘1"
          and keys.get("space-1") == "⌃1" and keys.get("toggle-essential") == "⌘D" and keys.get("copy-url") == "⇧⌘C" and len(keys) >= 20, str(listed))

    def in_settings():
        into_page(m, "/settings/settings.html")  # not through every tab's handle, which would load them all

    went_away = []

    def record(command, *keys_pressed):
        """A real click on the command's key, in the page in front, then a real key press in the window,
        which Tidier's own keys are listening to as well."""
        m.js(H + """const w = main(); w.focus(); w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes("/settings/settings.html")); await wait(500); w.gBrowser.selectedBrowser.focus(); await wait(200); return 1;""")
        in_settings()
        button = m.cmd("WebDriver:FindElement", {"using": "css selector", "value": f'[data-command="{command}"]'})
        m.cmd("WebDriver:ElementClick", {"id": list(button.values())[0] if isinstance(button, dict) else button})
        m.chrome()
        press(m, *keys_pressed)
        time.sleep(0.6)
        if not m.js(H + """return url(main().gBrowser.selectedTab).includes("/settings/settings.html");"""):
            went_away.append(keys_pressed)
        in_settings()
        reply = m.cmd("WebDriver:ExecuteScript", {"script": """const k = document.querySelector('[data-command="' + arguments[0] + '"]'), n = k.closest("#keys > div").querySelector(".key-note");
          return {key: k.textContent, note: n.hidden ? "" : n.textContent, focused: document.activeElement === k};""", "args": [command]})
        m.chrome()
        return reply

    stored = """return (await WebExtensionPolicy.getByID(args[0]).extension.shortcuts.allCommands()).find(c => c.name === args[1]).shortcut;"""
    r = record("next-tab", "j", ALT, SHIFT)
    check("pressing a new key on the settings page changes it", r["key"] == "⌥⇧J" and m.js(stored, EXT_ID, "next-tab") == "Alt+Shift+J", str(r))
    r = record("next-tab", "1", CMD)
    check("a key another command has is refused, and said", "already" in r["note"] and r["key"] == "⌥⇧J" and m.js(stored, EXT_ID, "next-tab") == "Alt+Shift+J", str(r))
    r = record("previous-tab", "l", CMD)
    check("a letter Firefox uses is said", "about:keyboard" in r["note"] and r["key"] == "⌘L", str(r))
    r = record("previous-tab", "j", ALT, SHIFT, CMD)
    check("a key Firefox cannot take is refused, and said", "cannot be used" in r["note"] and r["key"] == "⌘L", str(r))
    r = record("previous-tab", "j")
    check("a letter alone is no key, and said, and it waits for a real one", "needs" in r["note"] and r["key"] == "Press a key…" and m.js(stored, EXT_ID, "previous-tab") == "Command+L", str(r))
    r = record("previous-tab", LEFT, CMD)
    check("a key on an arrow Firefox uses is said", "both happen" in r["note"] and r["key"] == "⌘←", str(r))
    r = record("previous-tab", BACKSPACE)
    check("⌫ removes a key", r["key"] == "none" and m.js(stored, EXT_ID, "previous-tab") == "", str(r))
    r = record("previous-tab", "")  # Esc
    check("Esc keeps what it was", r["key"] == "none", str(r))
    r = settings("""await wait(300); const back = doc.getElementById("keys-back"), shown = !back.hidden; back.click(); await wait(800);
      return {shown, gone: back.hidden, key: doc.querySelector('[data-command="previous-tab"]').textContent};""")
    check("a button brings the usual keys back, and goes", r == {"shown": True, "gone": True, "key": "⌃⌘↑"}, str(r))
    record("next-tab", "j", ALT, SHIFT)
    r = record("previous-tab", BACKSPACE)
    check("a key pressed while choosing only chooses: it does not do what it is the key for", not went_away, str(went_away))

    # The key you chose works, and you keep what you did with them after a start.
    m.js(H + """await removeWhere((x, t) => url(t).includes("/settings/settings.html")); return 1;""")
    go("1", CMD)
    selects(closed[0])
    go("j", ALT, SHIFT)
    check("the key you chose does what it is for", selects(closed[1]), str(closed))
    m.js("""const {AddonManager} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs"); await (await AddonManager.getAddonByID(args[0])).reload(); return 1;""", EXT_ID)
    for _ in range(40):
        time.sleep(1)
        if m.js(H + """const p = WebExtensionPolicy.getByID(args[0]); return !!p && !!p.extension && (await storage(args[0], ["keysGiven"])).keysGiven?.length > 0;""", EXT_ID):
            break
    time.sleep(6)
    kept = [m.js(stored, EXT_ID, name) for name in ("next-tab", "previous-tab", "tab-2")]
    check("after a start, a key you changed stays, one you removed stays gone, and the others are there", kept == ["Alt+Shift+J", "", "Ctrl+2"], str(kept))
    go("1", CMD)
    selects(closed[0])
    go("j", ALT, SHIFT)
    check("and it still works", selects(closed[1]), str(closed))

    # Back as it was for the checks after this one.
    sidebar_page(m, """await wait(300);
      for (const f of [...doc.querySelectorAll("#tabs .folder")]) if (["Typed", "Keys folder", "New folder"].includes(f.querySelector(".title").textContent)) send({type: "deleteFolder", key: f.dataset.key});
      await wait(800); return 1;""")
    m.js(H + """await removeWhere((x, t) => url(t).includes("/sidebar/sidebar.html")); return 1;""")
    extension_message(m, {"type": "settings:keysBack"})
    m.js(custom_keys, firefox_keys, "resetKey")


def alone_keyboard(m):
    """The sidebar by the keyboard alone, in the real panel: one place for the keyboard, a button's own
    keys, menus by key, the essentials' grid, renaming, and names and states for a screen reader."""
    ENTER, DOWN, UP, RIGHT, HOME, END, F2, F10, SPACE, BACKSPACE = "\ue007", "\ue015", "\ue013", "\ue014", "\ue011", "\ue010", "\ue032", "\ue03a", "\ue00d", "\ue003"
    into_panel = H + """const w = main(), outer = w.SidebarController.browser; w.focus(); outer.focus(); await wait(100);
      outer.contentDocument.getElementById("webext-panels-browser").focus(); await wait(400); return 1;"""
    # The real panel's page, from Tidier's sidebar page in a tab (the same process); a tab in the background,
    # so the keyboard stays where it is.
    the_panel = """const v = page.browser.extension.getViews({type: "sidebar", windowId: (await page.browser.windows.getCurrent()).id})[0], d = v.document;
      const at = () => { const a = d.activeElement; return {cursor: a?.classList.contains("cursor") ?? false, tab: a?.dataset?.tab ?? null, head: a?.dataset?.folderHead ?? null,
        tile: a?.classList.contains("tile") ?? false, id: a?.id ?? "", menu: !!a?.closest?.("#menu"), rings: d.querySelectorAll(".cursor").length, focus: d.hasFocus()}; };"""

    def panel(script, *args):
        return sidebar_page(m, the_panel + script, *args)

    m.js(H + """await removeWhere((x, t) => /\\/(settings\\/settings|sidebar\\/sidebar)\\.html/.test(url(t))); return 1;""")
    panel("await wait(300); return 1;")  # the test's page, made once: from here on it is a row in the background

    # A button you Tab to is pressed by Enter, and the arrows take the keyboard to the list: one place, one ring.
    m.js(into_panel)
    before = m.js(H + "return main().gBrowser.tabs.length;")
    panel("""d.getElementById("new-tab").focus(); await wait(100); return 1;""")
    press(m, DOWN)
    r = panel("await wait(200); return at();")
    check("with a button focused, ↓ takes the keyboard to the list: one place and one ring", r["cursor"] and r["rings"] == 1 and r["id"] != "new-tab", str(r))
    # Tab comes into the list on the selected tab, with the cursor, and ⇧Tab gets out again: no trap.
    # (A tab of the list selected: an essential's tile comes before New tab.)
    m.js(H + """const w = main(), t = w.gBrowser.visibleTabs.find(t => !t.pinned && !url(t).includes("/sidebar/sidebar.html"));
      if (t) w.gBrowser.selectedTab = t; await wait(1000); return 1;""")
    m.js(into_panel)
    panel("""d.getElementById("new-tab").focus(); await wait(100); return 1;""")
    landed = None
    for _ in range(8):
        press(m, "\ue004")
        landed = panel("await wait(150); return {...at(), selected: d.activeElement?.classList.contains('active') ?? false};")
        if landed["tab"] or landed["head"] or landed["tile"]:
            break
    check("Tab from New tab comes into the list on the selected tab, with the cursor on it", landed["cursor"] and landed["selected"] and landed["rings"] == 1, str(landed))
    press(m, "\ue004", SHIFT)
    out = panel("await wait(150); return {...at(), inList: !!d.activeElement?.closest('#tabs')};")
    check("and ⇧Tab takes the keyboard out of the list again", not out["inList"] and not out["cursor"] and out["focus"], str(out))
    panel("""d.getElementById("new-tab").focus(); await wait(100); return 1;""")
    press(m, ENTER)
    after = m.js(H + "for (let i = 0; i < 30 && main().gBrowser.tabs.length === args[0]; i++) await wait(100); return main().gBrowser.tabs.length;", before)
    check("Enter presses a button you tabbed to (New tab)", after == before + 1, f"{before} -> {after}")
    m.js(H + """const w = main(), t = w.gBrowser.selectedTab; if (/about:(newtab|home|blank)/.test(url(t))) w.gBrowser.removeTab(t); await wait(800); return 1;""")

    # Menus by key, and the keyboard back where it was.
    m.js(into_panel)
    press(m, DOWN)
    r0 = panel("await wait(200); return at();")
    press(m, F10, SHIFT)
    r = panel("await wait(500); return {...at(), shown: !d.getElementById('menu').hidden, items: [...d.querySelectorAll('#menu .item')].map(b => b.textContent)};")
    check("⇧F10 opens the menu of the cursor's row, with the keyboard on its first item", r["shown"] and r["menu"] and r["items"], str(r))
    press(m, ESC)
    r = panel("await wait(300); return {...at(), shown: !d.getElementById('menu').hidden};")
    check("Esc closes it and gives the keyboard back to that row", not r["shown"] and r["tab"] == r0["tab"] and r["cursor"], f"{r0} {r}")
    press(m, ENTER, CTRL)
    r = panel("await wait(500); const shown = !d.getElementById('menu').hidden; return {...at(), shown};")
    check("⌃↵ opens it too", r["shown"] and r["menu"], str(r))
    press(m, ESC)

    # The essentials' grid, Home and End.
    tiles = panel("await wait(200); return [...d.querySelectorAll('#essentials .tile')].map(t => t.dataset.tab);")
    press(m, HOME)
    r1 = panel("await wait(200); return at();")
    press(m, RIGHT)
    r2 = panel("await wait(200); return at();")
    press(m, DOWN)
    r3 = panel("await wait(200); return {...at(), last: [...d.querySelectorAll('#essentials .tile')].map(t => t.getBoundingClientRect().top).every((y, i, a) => y === a[0])};")
    press(m, END)
    r4 = panel("""await wait(200); const all = [...d.querySelectorAll(".tile, #tabs .head, #tabs .tab")].filter(e => e.offsetParent !== null); return {...at(), last: all.at(-1)?.dataset.tab ?? all.at(-1)?.dataset.folderHead};""")
    check("Home goes to the first essential, and → along the grid", len(tiles) >= 2 and r1["tile"] and r1["tab"] == tiles[0] and r2["tab"] == tiles[1], f"{tiles} {r1} {r2}")
    check("↓ from the grid's last row goes into the list", r3["last"] is False or (not r3["tile"] and r3["cursor"]), str(r3))
    check("End goes to the last row", r4["cursor"] and (r4["tab"] or r4["head"]) == r4["last"], str(r4))

    # F2 renames a folder; Esc keeps its name.
    panel("""send({type: "newFolder", space: spaces().find(s => s.active).id, name: "Keys F2"}); await wait(800); return 1;""")
    r = panel("""await wait(200); const head = [...d.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "Keys F2"); if (!head) return {none: true};
      v.moveCursor(head); return {name: head.querySelector(".title").textContent, key: head.dataset.folderHead};""")
    press(m, F2)
    box = panel("await wait(400); const a = d.activeElement; return {box: a?.classList.contains('rename') ?? false, value: a?.value ?? null};")
    check("F2 renames the folder under the cursor", box["box"] and box["value"] == r.get("name"), f"{r} {box}")
    press(m, ESC)
    panel("""send({type: "deleteFolder", key: args[0]}); await wait(600); return 1;""", r.get("key"))

    # ⌫ on a tab that is not the selected one: the keyboard stays, on the next row.
    space = m.js(H + "return main().gBrowser.selectedTab.userContextId;")
    m.js(H + """const w = main(); w.gBrowser.addTrustedTab(args[0] + "/?smoke-keyboard-close", {userContextId: args[1], inBackground: true}); await wait(1500); return 1;""", m.pages, space)
    m.js(into_panel)
    r = panel("""await wait(300); const row = [...d.querySelectorAll("#tabs .tab")].find(x => x.title.includes("smoke-keyboard-close")); if (!row) return null;
      v.moveCursor(row); return row.dataset.tab;""")
    press(m, BACKSPACE)
    r2 = panel("await wait(1500); return {...at(), gone: !d.querySelector(`[data-tab=\"${args[0]}\"]`)};", r)
    check("⌫ on a tab you are not on closes it, and the keyboard stays in the list, on the next row", r and r2["gone"] and r2["focus"] and r2["cursor"], f"{r} {r2}")

    # What a screen reader is told: a tree of tabs and folders, essentials to choose from, spaces by name.
    r = panel("""await wait(200); const rows = [...d.querySelectorAll("#tabs .tab")], heads = [...d.querySelectorAll("#tabs .head")], dots = [...d.querySelectorAll("#spaces .space")];
      return {tree: d.getElementById("tabs").getAttribute("role"), grid: d.getElementById("essentials").getAttribute("role"),
        rows: rows.every(x => x.getAttribute("role") === "treeitem" && x.getAttribute("aria-label") === x.querySelector(".title").textContent && ["true", "false"].includes(x.getAttribute("aria-selected"))),
        selected: rows.filter(x => x.getAttribute("aria-selected") === "true").length, heads: heads.every(x => ["true", "false"].includes(x.getAttribute("aria-expanded"))),
        tiles: [...d.querySelectorAll("#essentials .tile")].every(x => x.getAttribute("role") === "option"),
        dots: dots.every(b => b.getAttribute("aria-label") === b.title), current: dots.filter(b => b.getAttribute("aria-current") === "true").length};""")
    check("a screen reader is told what each row is: a tree of tabs and folders, with what is selected and open", r["tree"] == "tree" and r["rows"] and r["selected"] <= 1 and r["heads"], str(r))
    check("and the essentials are a list to choose from, and a space's dot is named by its space, the one you are in marked", r["grid"] == "listbox" and r["tiles"] and r["dots"] and r["current"] == 1, str(r))
    m.js(H + """await removeWhere((x, t) => /\\/sidebar\\/sidebar\\.html|smoke-keyboard-close/.test(url(t))); return 1;""")

    # A key Firefox still has is not shown as Tidier's: what about:keyboard was told, as the dotfiles hand it over.
    cleared = json.load(open(m.tidier_managed))["data"].get("firefoxKeys", {})
    marked = ext_page(m, "/settings/settings.html", """await wait(800); return Object.fromEntries([...doc.querySelectorAll("#keys [data-command]")].map(k => [k.dataset.command, k.classList.contains("firefox")]));""")
    want = {"toggle-essential": "addBookmarkAsKb" not in cleared, "tab-1": "key_selectTab1" not in cleared, "command-bar-t": "key_newNavigatorTab" not in cleared, "next-tab": False}
    check("the settings page marks a key Firefox still has, and only that", all(marked.get(k) == v for k, v in want.items()), f"{want} {marked}")
    m.js(H + """await removeWhere((x, t) => url(t).includes("/settings/settings.html")); return 1;""")


# Tidier's own keys in Firefox's list for the window, among them the bar's two, if it has them.
BAR_KEYS = H + """const w = main(); w.focus(); await wait(300); const mine = [...w.document.querySelectorAll('keyset[id^="ext-keyset"]')].filter(k => k.id.includes("6844a953"));
  return mine.flatMap(k => [...k.children]).map(k => [k.getAttribute("key"), k.getAttribute("modifiers")].join(" ")).filter(k => k === "K accel,shift" || k === "T accel");"""


def bar_field_until(m, test, tries=50):
    """The bar's field, once `test(field)` holds: a key reaches the bar's page a moment after it is sent."""
    field = {}
    for _ in range(tries):
        field = bar_page(m, """return {value: doc.getElementById("field").value, focused: doc.activeElement?.id === "field"};""") or {}
        if field and test(field):
            return field
        time.sleep(0.05)
    return field


def alone_command_bar(m):
    start = m.js(H + """const w = main(); w.focus(); await wait(300); const space = w.gBrowser.selectedTab.userContextId;
      const others = [1, 2, 3].filter(c => c !== space);
      const t = w.gBrowser.addTrustedTab("https://example.org/?smoke-bar-one", {userContextId: others[0], inBackground: true});
      for (let i = 0; i < 100 && !key(w, t); i++) await wait(100);
      return {space, other: others[0], selected: url(w.gBrowser.selectedTab), hidden: t.hidden, normal: wins().length, tabs: w.gBrowser.tabs.length};""")
    ready = bar_open(m)
    print(f"INFO  the command bar is ready {ready} ms after the key", flush=True)
    r = bar_page(m, """return {focused: doc.activeElement?.id === "field" && doc.hasFocus(), rows: doc.querySelectorAll(".row").length};""")
    check("the key opens the bar, ready to type", r["focused"] and r["rows"] > 0, str(r))
    # The dotfiles' stylesheet puts the panel where its floating address bar is: in the middle,
    # 18 % down, 760 px wide or seven tenths of a narrower window (Tidier gives it that width).
    place = m.js(BAR + """const w = main(), b = bar(), r = b.panel.getOuterScreenRect(), bar_ = w.document.getElementById("urlbar");
      return {own: barWindows().length, windows: wins().length, off: Math.round(Math.abs(r.x + r.width / 2 - (w.mozInnerScreenX + w.innerWidth / 2))),
              top: Math.round(r.y - w.mozInnerScreenY), width: Math.round(r.width), inner: [w.innerWidth, w.innerHeight], tabs: w.gBrowser.tabs.length};""")
    check("it is a panel in the window you are in, not a window of its own, and no tab",
          place["own"] == 0 and place["windows"] == start["normal"] and place["tabs"] == start["tabs"], f"{place} {start}")
    check("it floats in the middle of the window, where the address bar does, and as wide",
          place["off"] <= 2 and abs(place["top"] - 0.18 * place["inner"][1]) <= 3 and abs(place["width"] - min(760, 0.7 * place["inner"][0])) <= 4, str(place))
    # Esc, the key again, and the focus going elsewhere each close it, and nothing has moved.
    bar_keys(m, [ESC])
    closed = wait_for_bar(m, False)
    r = m.js(BAR + """await wait(200); const w = main(); return {selected: url(w.gBrowser.selectedTab), focus: Services.focus.activeWindow === w};""")
    check("Esc closes it, back in the same tab of the same window", closed and r["selected"] == start["selected"] and r["focus"], str(r))
    bar_open(m)
    press_in(m, "main()", "k", CMD, SHIFT)
    check("the key closes it again", wait_for_bar(m, False))
    # A click beside it: Firefox closes a panel then, by itself. Tidier hears of it from the
    # bar's page going, and the key must open a new bar at the first press, not close a ghost.
    bar_open(m)
    # (Not sooner than a hand could: a panel gone the moment it has the keyboard is one Firefox
    # never showed, and the bar then comes as a window, commandbar.js.)
    m.js(BAR + "await wait(400); bar().panel.hidePopup(); return 1;")
    gone = wait_for_bar(m, False)
    ready = bar_open(m)
    check("closed by Firefox (a click beside it), it is gone, and the key opens it again at the first press", gone and ready >= 0, f"{gone} {ready}")
    bar_keys(m, [ESC])
    wait_for_bar(m, False)

    # Typing at once after the key, from a field in a page: what goes there before the bar
    # has the keyboard is caught in the page (barkeys.js, with the access to all
    # websites) and handed to the bar, so none of it lands in the page.
    had_access = m.js(H + """const {ExtensionPermissions} = ChromeUtils.importESModule("resource://gre/modules/ExtensionPermissions.sys.mjs");
      const policy = WebExtensionPolicy.getByID(args[0]), had = (await ExtensionPermissions.get(args[0])).origins.includes("<all_urls>");
      await ExtensionPermissions.add(args[0], {permissions: [], origins: ["<all_urls>"]}, policy.extension);
      for (let i = 0; i < 50 && !policy.contentScripts.some(s => s.jsPaths.some(p => p.endsWith("/barkeys.js"))); i++) await wait(100);
      const w = main(); w.focus();
      const t = w.gBrowser.addTrustedTab(args[1] + "/message-box?smoke-bar-typed", {userContextId: w.gBrowser.selectedTab.userContextId}); w.gBrowser.selectedTab = t;
      for (let i = 0; i < 100 && (!key(w, t) || t.linkedBrowser.webProgress?.isLoadingDocument); i++) await wait(100);
      await wait(500); w.gBrowser.selectedBrowser.focus(); await wait(200); return had;""", EXT_ID, m.pages)
    typed = "smoke typed"
    # Where Firefox sends each of them. Until the bar's window is the active one and its page's
    # place in it has the focus, the keys still go to the page you were in. From then on Firefox
    # sends them to the bar's page, also in the 10 to 20 ms before that page is there, and what
    # is typed then is lost: no extension sees it. A hand types one key in that time at the
    # most, but these come within a few milliseconds, and so do or do not land in it together
    # (seven of them did, on GitHub and here). So the check is exact about Tidier's part: every
    # key that went to the page you were in is in the bar, and those lost are the first ones
    # sent to the bar's window, and no other.
    m.js(H + """const w = main(), sent = w.smokeBarKeys = [];
      w.smokeBarKeysOn = e => { if ([...e.key].length === 1 && !e.metaKey) sent.push({key: e.key, toBar: Services.focus.focusedElement !== w.gBrowser.selectedBrowser}); };
      w.addEventListener("keydown", w.smokeBarKeysOn, true); return 1;""")
    acts = [{"type": "keyDown", "value": k} for k in (CMD, SHIFT, "k")] + [{"type": "keyUp", "value": k} for k in ("k", SHIFT, CMD)]
    for k in typed:
        acts += [{"type": "keyDown", "value": k}, {"type": "keyUp", "value": k}]
    m.cmd("WebDriver:PerformActions", {"actions": [{"type": "key", "id": "kb", "actions": acts}]})
    m.cmd("WebDriver:ReleaseActions")
    wait_for_bar(m)
    sent = m.js(H + """const w = main(); w.removeEventListener("keydown", w.smokeBarKeysOn, true); return w.smokeBarKeys;""")
    to_page = next((i for i, k in enumerate(sent) if k["toBar"]), len(sent))  # so many went to the page you were in
    field = ""
    for _ in range(50):
        field = bar_page(m, """return doc.getElementById("field").value;""") or ""
        if field == typed:
            break
        time.sleep(0.1)
    into_page(m, "smoke-bar-typed")
    box = m.cmd("WebDriver:ExecuteScript", {"script": "return document.getElementById('box').value;", "args": []})
    m.chrome()
    check("keys typed at once after the key go to the bar, none to the page",
          box == "" and "".join(k["key"] for k in sent) == typed and to_page > 0 and field.startswith(typed[:to_page]) and typed[to_page:].endswith(field[to_page:]),
          f"page {box!r}, bar {field!r}, sent to the page {typed[:to_page]!r}, to the bar's window {typed[to_page:]!r}")
    if field != typed:
        print(f"INFO  the bar got {field!r} of {typed!r}: Firefox sent {typed[to_page:]!r} to its window, the first of them before its page was there", flush=True)
    bar_keys(m, [ESC])
    wait_for_bar(m, False)
    m.js(H + """await removeWhere((w, t) => url(t).includes("smoke-bar-typed"));
      if (!args[1]) { const {ExtensionPermissions} = ChromeUtils.importESModule("resource://gre/modules/ExtensionPermissions.sys.mjs");
        await ExtensionPermissions.remove(args[0], {permissions: [], origins: ["<all_urls>"]}, WebExtensionPolicy.getByID(args[0]).extension); await wait(1000); }
      return 1;""", EXT_ID, had_access)  # as it was, for the groups after this one

    # Firefox lists a closed popup under Recently Closed Windows: ⌘⇧T would bring the bar back.
    r = {}
    for _ in range(50):
        r = m.js(H + """return main().SessionStore.getClosedWindowData().map(w => w.tabs[0]?.entries?.[0]?.url).filter(u => u?.includes("/commandbar/commandbar.html")).length;""")
        if not r:
            break
        time.sleep(0.1)
    check("a closed bar is not kept under Recently Closed Windows", r == 0, str(r))
    m.js(H + """const w = main(); w.focus(); const t = w.gBrowser.addTrustedTab("https://example.org/?smoke-bar-undo", {userContextId: w.gBrowser.selectedTab.userContextId}); w.gBrowser.selectedTab = t;
      for (let i = 0; i < 100 && (!key(w, t) || t.linkedBrowser.webProgress?.isLoadingDocument); i++) await wait(100); await wait(1500); w.gBrowser.removeTab(t); await wait(1000); return 1;""")
    bar_open(m)
    bar_keys(m, [ESC])
    wait_for_bar(m, False)
    m.js(H + "const w = main(); w.focus(); for (let i = 0; i < 100 && Services.focus.activeWindow !== w; i++) await wait(50); await wait(1500); return 1;")
    press(m, "t", CMD, SHIFT)
    r = m.js(BAR + """const w = main(); for (let i = 0; i < 50 && !url(w.gBrowser.selectedTab).includes("smoke-bar-undo"); i++) await wait(100);
      const u = url(w.gBrowser.selectedTab); return {url: u, bar: !!bar()};""")
    check("⌘⇧T after the bar brings back the tab you closed", "smoke-bar-undo" in r["url"] and not r["bar"], str(r))
    m.js(H + """await removeWhere((w, t) => url(t).includes("smoke-bar-undo") || t.label.includes("smoke-bar-undo")); const w = main(); w.focus(); return 1;""")
    press(m, str(start["space"]), CTRL)
    time.sleep(1)

    # A tab of another space: unloaded here or not, Enter goes to it and takes you there.
    bar_open(m)
    bar_keys(m, "smoke-bar-one")
    rows = bar_rows_until(m, lambda rows: rows and "smoke-bar-one" in (rows[0]["url"] or ""))
    check("typing finds a tab of another space, by its address", rows and rows[0]["kind"] == "tab" and rows[0]["selected"], str(rows[:3]))
    bar_keys(m, [ENTER])
    closed = wait_for_bar(m, False)
    r = m.js(BAR + """const w = main(); await wait(800); const t = w.gBrowser.selectedTab;
      return {url: url(t), space: t.userContextId, shown: [...new Set(w.gBrowser.tabs.filter(x => !x.pinned && !x.hidden && x.userContextId).map(x => x.userContextId))]};""")
    check("Enter goes to it, in its space, and the bar closes", closed and "smoke-bar-one" in r["url"] and r["space"] == start["other"] and r["shown"] == [start["other"]], str(r))
    m.js(H + "const w = main(); w.focus(); return 1;")
    press(m, str(start["space"]), CTRL)
    time.sleep(1)

    # From a second window the tab is a placeholder there: its real address is found, and it is pulled in.
    second = m.js(H + """let w = other(), made = false;
      if (!w) { w = main().OpenBrowserWindow(); w.__smoke = true; made = true; for (let i = 0; i < 200 && !w.gBrowserInit?.delayedStartupFinished; i++) await wait(50); await wait(2500); }
      const t = w.gBrowser.tabs.find(x => { const k = key(w, x), m0 = main().gBrowser.tabs.find(y => url(y).includes("smoke-bar-one")); return k && m0 && k === key(main(), m0); });
      return {made, role: t ? role(w, t) : null, own: t ? url(t) : null};""")
    bar_open(m, "other()")
    bar_keys(m, "smoke-bar-one")
    rows = bar_rows_until(m, lambda rows: rows and rows[0]["kind"] == "tab")
    check("a placeholder is found by the real tab's address", second["role"] == "ghost" and "ghost.html" in second["own"] and rows and "smoke-bar-one" in (rows[0]["url"] or "") and "ghost.html" not in rows[0]["url"], f"{second} {rows[:2]}")
    bar_keys(m, [ENTER])
    closed = wait_for_bar(m, False)
    r = m.js(BAR + """await wait(1500); const w = other(), t = w.gBrowser.selectedTab, k = key(w, t);
      return {url: url(t), role: role(w, t), loaded: !!t.linkedPanel, inMain: main().gBrowser.tabs.filter(x => key(main(), x) === k).map(x => role(main(), x)), space: t.userContextId};""")
    check("choosing it from there pulls the real tab in", closed and "smoke-bar-one" in r["url"] and r["role"] == "live" and r["inMain"] == ["ghost"] and r["space"] == start["other"], str(r))
    if second["made"]:
        m.js(H + "other().close(); await wait(1500); return 1;")
    m.js(H + "main().focus(); await wait(300); return 1;")
    press(m, str(start["space"]), CTRL)
    time.sleep(1)

    # An address goes there, in the active space; a search too; ⌘↵ opens instead of going.
    bar_open(m)
    bar_keys(m, "example.org/?smoke-bar-address")
    rows = bar_rows_until(m, lambda rows: rows and rows[0]["kind"] == "address")
    check("what looks like an address comes first", rows and rows[0]["kind"] == "address" and any(x["kind"] == "search" for x in rows), str(rows[:2]))
    bar_keys(m, [ENTER])
    wait_for_bar(m, False)
    r = m.js(BAR + """const w = main(); for (let i = 0; i < 50 && !url(w.gBrowser.selectedTab).includes("smoke-bar-address"); i++) await wait(100);
      const t = w.gBrowser.selectedTab; return {url: url(t), space: t.userContextId, bar: !!bar()};""")
    check("Enter on an address opens it in the active space", "smoke-bar-address" in r["url"] and r["space"] == start["space"], str(r))
    # With an engine of the test's own as Firefox's default, so this stays out of a real search engine's logs.
    SEARCH = H + """const {SearchService: s} = ChromeUtils.importESModule("moz-src:///toolkit/components/search/SearchService.sys.mjs");"""
    m.js(SEARCH + """await s.init(); main().__engineBefore = (await s.getDefault()).name;
      await s.addUserEngine({name: "Smoke bar engine", url: args[0] + "/smoke-engine?q={searchTerms}", alias: ""});
      await s.setDefault(await s.getEngineByName("Smoke bar engine"), s.CHANGE_REASON.UNKNOWN); return 1;""", m.pages)
    bar_open(m)
    bar_keys(m, "smoke bar search words")
    rows = bar_rows_until(m, lambda rows: rows and rows[0]["kind"] == "search")
    check("plain text with no good match is a search", rows and rows[0]["kind"] == "search", str(rows[:2]))
    bar_keys(m, [ENTER])
    closed = wait_for_bar(m, False)
    r = m.js(BAR + """const w = main(); for (let i = 0; i < 80 && !url(w.gBrowser.selectedTab).includes("smoke-engine"); i++) await wait(100);
      const t = w.gBrowser.selectedTab; return {url: url(t), space: t.userContextId};""")
    check("a search opens with Firefox's default engine, in the active space, and asks nothing", closed and "smoke-engine" in r["url"] and "smoke" in r["url"].split("q=")[-1] and r["space"] == start["space"], str(r))
    m.js(SEARCH + """await s.setDefault(await s.getEngineByName(main().__engineBefore), s.CHANGE_REASON.UNKNOWN);
      await s.removeEngine(await s.getEngineByName("Smoke bar engine")); await removeWhere((w, t) => url(t).includes("smoke-engine") || t.label.includes("smoke-engine")); return 1;""")
    bar_open(m)
    bar_keys(m, "smoke-bar-one")
    bar_rows_until(m, lambda rows: rows and rows[0]["kind"] == "tab")
    bar_keys(m, [ENTER], CMD)
    closed = wait_for_bar(m, False)
    r = m.js(BAR + """const w = main(); for (let i = 0; i < 50 && !url(w.gBrowser.selectedTab).includes("smoke-bar-one"); i++) await wait(100);
      const t = w.gBrowser.selectedTab; return {url: url(t), space: t.userContextId};""")
    check("⌘↵ opens it in a new tab here instead of going to the one in its own space", closed and "smoke-bar-one" in r["url"] and r["space"] == start["space"], str(r))

    # ↑↓ move, ⇥ completes, and a real click chooses too.
    bar_open(m)
    bar_keys(m, "example.org/?smoke-bar-a")
    bar_rows_until(m, lambda rows: rows and rows[0]["kind"] == "address")
    bar_keys(m, [DOWN])
    rows = bar_rows_until(m, lambda rows: len(rows) > 1 and rows[1]["selected"])
    check("↓ moves down the rows", len(rows) > 1 and rows[1]["selected"] and not rows[0]["selected"], str(rows[:2]))
    bar_page(m, """doc.getElementById("field").select();""")
    bar_keys(m, "smoke-bar-address")
    bar_rows_until(m, lambda rows: rows and rows[0]["kind"] == "tab")
    bar_keys(m, [TAB])
    field = bar_field_until(m, lambda f: f["value"] != "smoke-bar-address")
    check("⇥ completes to the address of the row, and stays in the field", field.get("value") == "example.org/?smoke-bar-address" and field["focused"], str(field))
    # A real click, made in the page's own process (Marionette cannot be pointed at a panel's page).
    bar_page(m, """const r = doc.querySelector(".row[data-kind=tab]").getBoundingClientRect(), u = content.windowUtils, x = r.left + r.width / 2, y = r.top + r.height / 2;
      for (const type of ["mousemove", "mousedown", "mouseup"]) {
        if (content.synthesizeMouseEvent) content.synthesizeMouseEvent(type, x, y, {button: 0, clickCount: type === "mousemove" ? 0 : 1}, {});
        else u.sendMouseEvent(type, x, y, 0, type === "mousemove" ? 0 : 1, 0);  // (before Firefox moved it to the window)
      }""")
    closed = wait_for_bar(m, False)
    r = m.js(H + """await wait(500); return url(main().gBrowser.selectedTab);""")
    check("a click on a row chooses it", closed and "smoke-bar-address" in r, str(r))

    # What was closed can be found, and comes back in its space.
    r = m.js(H + """const w = main(), t = w.gBrowser.selectedTab; await wait(1000); w.gBrowser.removeTab(t); await wait(1500); return 1;""")
    bar_open(m)
    bar_keys(m, "smoke-bar-address")
    rows = bar_rows_until(m, lambda rows: any(x["kind"] == "closed" for x in rows))
    check("a closed tab can be found", any(x["kind"] == "closed" and "smoke-bar-address" in x["url"] for x in rows), str(rows[:3]))
    at = next((i for i, x in enumerate(rows) if x["kind"] == "closed"), 0)
    bar_keys(m, [DOWN] * at + [ENTER])
    closed = wait_for_bar(m, False)
    r = m.js(H + """const w = main(); for (let i = 0; i < 50 && !url(w.gBrowser.selectedTab).includes("smoke-bar-address"); i++) await wait(100);
      const t = w.gBrowser.selectedTab; return {url: url(t), space: t.userContextId};""")
    check("and Enter brings it back in its space", closed and "smoke-bar-address" in r["url"] and r["space"] == start["space"], str(r))

    # Commands: a question in the field, a choice from a list, and Esc goes back one step.
    bar_open(m)
    bar_keys(m, "new folder")
    rows = bar_rows_until(m, lambda rows: rows and rows[0]["kind"] == "command")
    bar_keys(m, [ENTER])
    time.sleep(0.2)
    bar_keys(m, [ESC])
    still = bar_field_until(m, lambda f: f["value"]).get("value")
    check("Esc in a question goes back one step", still == "new folder", repr(still))
    bar_keys(m, [ENTER])
    time.sleep(0.2)
    bar_keys(m, "Smoke bar folder")
    bar_keys(m, [ENTER])
    closed = wait_for_bar(m, False)
    r = m.js(BAR + """const w = main(), space = "firefox-container-" + w.gBrowser.selectedTab.userContextId; let folders = [];
      for (let i = 0; i < 50 && !folders.length; i++) { await wait(100); folders = Object.values((await storage("%s", ["syncedTabs"])).syncedTabs).filter(e => e.own && e.name === "Smoke bar folder").map(e => e.cookieStoreId); }
      return {folders, space};""" % EXT_ID)
    check("the command makes a folder, asking its name in the field", closed and r["folders"] == [r["space"]], str(r))
    bar_open(m)
    bar_keys(m, "move to folder")
    bar_rows_until(m, lambda rows: rows and rows[0]["kind"] == "command")
    bar_keys(m, [ENTER])
    time.sleep(0.2)
    bar_keys(m, "smoke bar")
    rows = bar_rows_until(m, lambda rows: len(rows) == 1 and rows[0]["title"] == "Smoke bar folder")
    check("a command with a list asks in the bar, and typing narrows it", len(rows) == 1, str(rows))
    bar_keys(m, [ENTER])
    wait_for_bar(m, False)
    r = m.js(BAR + """const w = main(), k = JSON.parse(key(w, w.gBrowser.selectedTab)); let all = {};
      for (let i = 0; i < 50 && all[all[k]?.parentKey]?.name !== "Smoke bar folder"; i++) { await wait(100); all = (await storage("%s", ["syncedTabs"])).syncedTabs; }
      return {url: all[k]?.url, folder: all[all[k]?.parentKey]?.name};""" % EXT_ID)
    check("Move to folder moves the tab you are on", r["folder"] == "Smoke bar folder", str(r))
    bar_open(m)
    bar_keys(m, "go to space")
    rows = bar_rows_until(m, lambda rows: sum(x["kind"] == "command" for x in rows) >= 2)
    bar_keys(m, [DOWN, UP, ENTER])
    closed = wait_for_bar(m, False)
    r = m.js(BAR + """await wait(1000); const w = main(); return w.gBrowser.selectedTab.userContextId;""")
    check("Go to space switches space", closed and r != start["space"], f"{r} {start} {rows}")
    m.js(H + "main().focus(); await wait(200); return 1;")
    press(m, str(start["space"]), CTRL)
    time.sleep(1)

    # What needs Firefox itself: the clipboard, unloading, the settings page.
    m.js(H + """Cc["@mozilla.org/widget/clipboardhelper;1"].getService(Ci.nsIClipboardHelper).copyString("before"); return 1;""")
    want = m.js(H + "return url(main().gBrowser.selectedTab);")
    bar_open(m)
    bar_keys(m, "copy address")
    bar_rows_until(m, lambda rows: rows and rows[0]["title"] == "Copy address")
    bar_keys(m, [ENTER])
    wait_for_bar(m, False)
    copied = ""
    for _ in range(30):
        copied = m.js(H + """const t = Cc["@mozilla.org/widget/transferable;1"].createInstance(Ci.nsITransferable); t.init(null); t.addDataFlavor("text/plain");
          Services.clipboard.getData(t, Ci.nsIClipboard.kGlobalClipboard, main().browsingContext.currentWindowContext);
          const o = {}; try { t.getTransferData("text/plain", o); return o.value.QueryInterface(Ci.nsISupportsString).data; } catch (e) { return ""; }""")
        if copied == want:
            break
        time.sleep(0.1)
    check("Copy address copies the tab you are on", copied == want, f"{copied!r} {want!r}")
    bar_open(m)
    bar_keys(m, "unload")
    bar_rows_until(m, lambda rows: rows and rows[0]["title"] == "Unload this tab")
    bar_keys(m, [ENTER])
    wait_for_bar(m, False)
    r = m.js(H + """const w = main(); let t; for (let i = 0; i < 50; i++) { t = w.gBrowser.tabs.find(x => url(x) === args[0]); if (t && !t.linkedPanel && !t.selected) break; await wait(100); }
      return {tab: !!t, unloaded: t && !t.linkedPanel, selected: t?.selected, now: w.gBrowser.selectedTab.userContextId};""", want)
    check("Unload unloads it, and you stay in the space", r["tab"] and r["unloaded"] and not r["selected"] and r["now"] == start["space"], str(r))
    bar_open(m)
    bar_keys(m, "settings")
    bar_rows_until(m, lambda rows: rows and rows[0]["title"] == "Settings")
    bar_keys(m, [ENTER])
    wait_for_bar(m, False)
    r = m.js(H + """const w = main(); for (let i = 0; i < 50 && !url(w.gBrowser.selectedTab).includes("/settings/settings.html"); i++) await wait(100);
      const u = url(w.gBrowser.selectedTab); w.gBrowser.removeTab(w.gBrowser.selectedTab); await wait(800); return u;""")
    check("Settings opens Tidier's settings", "/settings/settings.html" in r, str(r))

    # What you selected in the sidebar is what the commands act on. Its page in a tab stands
    # in for the sidebar, which is closed meanwhile: only one must answer, and a page's own
    # code can be given a stand-in for the selection only from a function of that page.
    m.js(H + "await main().SidebarController.hide(); await wait(300); return 1;")
    ids = sidebar_page(m, """await wait(500); const ids = [...doc.querySelectorAll("#tabs .tab")].slice(0, 2).map(r => Number(r.dataset.tab));
      page.selectedTabs = page.JSON.parse.bind(page.JSON, JSON.stringify(ids)); return ids;""")
    bar_open(m)
    bar_keys(m, "close")
    # (The sidebar's selection is asked for as the bar opens, and on a slow machine its answer
    # can come after the first rows are drawn: so the rows are read until it has come.)
    rows = bar_rows_until(m, lambda rows: any(x["title"] == "Close 2 tabs" for x in rows))
    check("commands act on what is selected in the sidebar", len(ids) == 2 and any(x["title"] == "Close 2 tabs" for x in rows), f"{ids} {rows}")
    bar_keys(m, [ESC])
    wait_for_bar(m, False)
    m.js(H + """const w = main(); for (const t of [...w.gBrowser.tabs]) if (url(t).includes("/sidebar/sidebar.html")) w.gBrowser.removeTab(t);
      await w.SidebarController.show("_6844a953-9931-4334-9ff6-257c246485cb_-sidebar-action"); await wait(500); return 1;""")

    # ⌘T: Firefox's own until it lets go of it (customKeys.json), and then the bar's.
    r = m.js(H + """const w = main(); w.focus(); for (let i = 0; i < 100 && Services.focus.activeWindow !== w; i++) await wait(50);
      return {freed: !w.document.getElementById("key_newNavigatorTab")?.getAttribute("key"), tabs: w.gBrowser.tabs.length};""")
    press(m, "t", CMD)
    if r["freed"]:
        check("⌘T opens the bar, now that Firefox has let go of it", wait_for_bar(m))
        bar_keys(m, [ESC])
        wait_for_bar(m, False)
    else:
        time.sleep(1)
        after = m.js(BAR + """const w = main(); const n = w.gBrowser.tabs.length; return {bar: !!bar(), tabs: n};""")
        check("until Firefox lets go of ⌘T it stays a new tab", not after["bar"] and after["tabs"] > r["tabs"], f"{r} {after}")
        m.js(H + """const w = main(); for (const t of [...w.gBrowser.tabs]) if (!t.pinned && !key(w, t) && /about:(newtab|home|blank)/.test(url(t))) w.gBrowser.removeTab(t); await wait(800); return 1;""")

    # History and bookmarks, once allowed: one quiet row, asked in the bar's own window.
    bar_open(m)
    bar_keys(m, "example")
    rows = bar_rows_until(m, lambda rows: rows and rows[-1]["kind"] == "ask")
    check("one quiet row offers history and bookmarks", rows and rows[-1]["kind"] == "ask", str(rows[-2:]))
    bar_keys(m, [UP, ENTER])  # round from the top to the last row
    r = {}
    for _ in range(50):
        r = m.js(BAR + """const w = main(), n = w.PopupNotifications.getNotification("addon-webext-permissions", w.gBrowser.selectedBrowser), box = w.document.getElementById("addon-webext-permissions-notification");
          return {bar: !!bar(), prompt: !!n, shown: n ? box?.getBoundingClientRect().height > 0 : false, panel: w.document.getElementById("notification-popup")?.state, own: barWindows().length};""")
        if r["shown"]:
            break
        time.sleep(0.1)
    check("Firefox asks, in the window you are in, and the bar waits for the answer", r.get("bar") and r.get("shown") and not r.get("own"), str(r))
    m.js(BAR + """main().document.getElementById("addon-webext-permissions-notification")?.button.click(); await wait(500); return 1;""")
    rows = bar_rows_until(m, lambda rows: not any(x["kind"] == "ask" for x in rows))
    check("once allowed the row is gone and the bar still open", bar_is_open(m) and not any(x["kind"] == "ask" for x in rows), str(rows[-2:]))
    r = bar_page(m, """const f = doc.getElementById("field"); for (let i = 0; i < 40 && !(doc.activeElement === f && doc.hasFocus()); i++) await new Promise(r => content.setTimeout(r, 25));
      return {focused: doc.activeElement === f && doc.hasFocus(), history: !!page.browser.history};""")
    check("and you can go on typing", r["focused"] and r["history"], str(r))
    bar_keys(m, [ESC])
    wait_for_bar(m, False)
    m.js(H + """const {PlacesUtils} = ChromeUtils.importESModule("resource://gre/modules/PlacesUtils.sys.mjs");
      await PlacesUtils.bookmarks.insert({url: "https://example.org/?smoke-bar-bookmark", title: "Smoke bar saved page", parentGuid: PlacesUtils.bookmarks.unfiledGuid});
      await PlacesUtils.history.insert({url: "https://example.org/?smoke-bar-visited", title: "Smoke bar visited page", visits: [{date: new Date()}]});
      return 1;""")
    bar_open(m)
    bar_keys(m, "smoke bar")
    rows = bar_rows_until(m, lambda rows: {"history", "bookmark"} <= {x["kind"] for x in rows})
    check("history and bookmarks are searched too, after what is open", {"history", "bookmark"} <= {x["kind"] for x in rows}, str(rows))
    at = next((i for i, x in enumerate(rows) if x["kind"] == "bookmark"), 0)
    bar_keys(m, [DOWN] * at + [ENTER])
    closed = wait_for_bar(m, False)
    r = m.js(H + """const w = main(); for (let i = 0; i < 50 && !url(w.gBrowser.selectedTab).includes("smoke-bar-bookmark"); i++) await wait(100);
      const t = w.gBrowser.selectedTab; return {url: url(t), space: t.userContextId};""")
    check("and open a new tab in the active space", closed and "smoke-bar-bookmark" in r["url"] and r["space"] == start["space"], str(r))
    m.js(H + """const {PlacesUtils} = ChromeUtils.importESModule("resource://gre/modules/PlacesUtils.sys.mjs");
      await PlacesUtils.bookmarks.remove((await PlacesUtils.bookmarks.fetch({url: "https://example.org/?smoke-bar-bookmark"})).guid);
      await PlacesUtils.history.remove(["https://example.org/?smoke-bar-visited", "https://example.org/?smoke-bar-bookmark"]);
      return 1;""")

    # Nothing stays behind.
    sidebar_page(m, """await wait(300); const key = [...doc.querySelectorAll(".folder")].find(x => x.querySelector(".head .title")?.textContent === "Smoke bar folder")?.dataset.key;
      if (key) { send({type: "deleteFolder", key}); await wait(500); }""")
    left = m.js(BAR + """await removeWhere((w, t) => /smoke.bar/.test(url(t)) || /smoke.bar/.test(t.label) || url(t).includes("/sidebar/sidebar.html"));
      return {bars: wins().filter(w => !w.toolbar.visible).map(w => url(w.gBrowser.selectedTab))};""")
    check("no window stays behind", not left["bars"], str(left))
    m.js(H + "main().focus(); return 1;")
    press(m, "1", CTRL)
    time.sleep(1)


def alone_bar_edges(m):
    """Around the bar: other keys, things changing while it is open, a prompt left behind."""
    start = m.js(H + """const w = main(); w.focus(); await wait(300); return {space: w.gBrowser.selectedTab.userContextId, tabs: w.gBrowser.tabs.length};""")
    kept_before = extension_message(m, {"type": "stats"})["sizes"]
    keys = m.js(BAR_KEYS)
    check("the command bar has its keys", len(keys) == 2, str(keys))

    # A space key while the bar has the keyboard: the window's keys still reach Tidier from a
    # panel, and the space would change under a bar that was opened in another.
    bar_open(m)
    press_in(m, "main()", "2" if start["space"] != 2 else "3", CTRL)
    time.sleep(1)
    r = m.js(BAR + """const w = main(); return {open: !!bar(), space: w.gBrowser.selectedTab.userContextId, here: w.gBrowser.tabs.length};""")
    check("a space key with the bar open changes nothing: the bar has the keyboard", r["open"] and r["space"] == start["space"] and r["here"] == start["tabs"], f"{r} {start}")
    bar_keys(m, [ESC])
    check("and Esc still closes it", wait_for_bar(m, False))

    # ⌘W is Firefox's own, and no page can take it: with the bar open it closes the tab you
    # are on, as it does from Firefox's own address bar. The bar was opened for that tab (its
    # commands act on it), so it goes too, rather than stay over another tab.
    m.js(H + """const w = main(); w.focus(); const t = w.gBrowser.addTrustedTab("https://example.org/?smoke-edge-w", {userContextId: w.gBrowser.selectedTab.userContextId}); w.gBrowser.selectedTab = t;
      for (let i = 0; i < 100 && (!key(w, t) || t.linkedBrowser.webProgress?.isLoadingDocument); i++) await wait(100); await wait(500); return 1;""")
    bar_open(m)
    press_in(m, "main()", "w", CMD)
    closed = wait_for_bar(m, False)
    r = m.js(H + """const w = main(); await wait(500); return {left: w.gBrowser.tabs.filter(t => url(t).includes("smoke-edge-w")).length, tabs: w.gBrowser.tabs.length};""")
    ready = bar_open(m)
    check("⌘W with the bar open closes the tab you are on, as from Firefox's address bar; the bar goes with it, and the key opens it again at the first press",
          closed and r["left"] == 0 and r["tabs"] == start["tabs"] and ready >= 0, f"{closed} {r} {start}")
    bar_keys(m, [ESC])
    wait_for_bar(m, False)
    m.js(H + """await removeWhere((w, t) => t.label.includes("smoke-edge-w")); return 1;""")

    # Enter held down: its repeats must not answer the question its first press brought up.
    bar_open(m)
    bar_keys(m, "new folder")
    bar_rows_until(m, lambda rows: rows and rows[0]["title"] == "New folder")
    bar_keys(m, [ENTER])
    time.sleep(0.2)
    bar_page(m, """for (let i = 0; i < 3; i++) doc.getElementById("field").dispatchEvent(new page.KeyboardEvent("keydown", {key: "Enter", repeat: true, bubbles: true, cancelable: true}));""")
    time.sleep(0.3)
    r = bar_page(m, """return {asks: doc.getElementById("field").placeholder};""")
    check("Enter held down does not answer the question it brought up", bool(r) and "Name" in r["asks"], str(r))
    bar_keys(m, [ESC])
    bar_keys(m, [ESC])
    wait_for_bar(m, False)

    # A tab of another space closed while the bar is open: Enter opens it again, in its own space.
    other = m.js(H + """const w = main(); w.focus(); const c = [1, 2, 3].find(c => c !== w.gBrowser.selectedTab.userContextId);
      const t = w.gBrowser.addTrustedTab("https://example.org/?smoke-edge-gone", {userContextId: c, inBackground: true});
      for (let i = 0; i < 100 && !key(w, t); i++) await wait(100); return c;""")
    bar_open(m)
    bar_keys(m, "smoke-edge-gone")
    rows = bar_rows_until(m, lambda rows: rows and rows[0]["kind"] == "tab")
    m.js(H + """for (const w of wins()) for (const t of [...w.gBrowser.tabs]) if (key(w, t) && url(t).includes("smoke-edge-gone")) w.gBrowser.removeTab(t); await wait(300); return 1;""")
    still = bar_is_open(m)
    bar_keys(m, [ENTER])
    closed = wait_for_bar(m, False)
    r = m.js(H + """const w = main(); let t; for (let i = 0; i < 50 && !t; i++) { await wait(100); t = w.gBrowser.tabs.find(x => url(x).includes("smoke-edge-gone")); }
      return {space: t?.userContextId, count: w.gBrowser.tabs.filter(x => url(x).includes("smoke-edge-gone")).length};""")
    check("a tab closed while the bar is open comes back in its own space, never with another space's logins",
          still and closed and rows and r["space"] == other and r["count"] == 1, f"{rows[:1]} {r} other space {other}")
    m.js(H + """await removeWhere((w, t) => url(t).includes("smoke-edge-gone") || t.label.includes("smoke-edge-gone")); main().focus(); return 1;""")
    press(m, str(start["space"]), CTRL)
    time.sleep(1)

    # Firefox's question left unanswered: you click beside it, and Firefox puts both panels away.
    sidebar_page(m, """await page.browser.permissions.remove({permissions: ["history", "bookmarks"]}); await page.browser.storage.local.remove("commandBarAsked");""")
    m.js(H + """await removeWhere((w, t) => url(t).includes("/sidebar/sidebar.html")); main().focus(); return 1;""")
    bar_open(m)
    bar_keys(m, "example")
    rows = bar_rows_until(m, lambda rows: rows and rows[-1]["kind"] == "ask")
    bar_keys(m, [UP, ENTER])
    r = {}
    for _ in range(50):
        r = m.js(BAR + """const panel = main().document.getElementById("notification-popup"); return {open: panel?.state === "open", bar: !!bar()};""")
        if r["open"]:
            break
        time.sleep(0.1)
    check("Firefox's question shows in the window you are in, with the bar still there", r["open"] and r["bar"], f"{rows[-1:]} {r}")
    m.js(BAR + """bar()?.panel.hidePopup(); main().document.getElementById("notification-popup")?.hidePopup(); await wait(300); return 1;""")
    gone = wait_for_bar(m, False)
    ready = bar_open(m)
    r = bar_page(m, """return !!page.browser.history;""")
    check("put away unanswered, it grants nothing, and the key opens the bar again at the first press", gone and ready >= 0 and r is False, f"{gone} {r}")
    bar_keys(m, "example")
    rows = bar_rows_until(m, lambda rows: rows and rows[0]["kind"] != "ask")
    check("and it is not asked a second time", bool(rows) and not any(x["kind"] == "ask" for x in rows), str(rows[-2:]))
    bar_keys(m, [ESC])
    wait_for_bar(m, False)

    # Another panel of Firefox's open (its menu, a question it asks): Firefox opens no second
    # one beside it, and the bar is then a small window of its own over the one you are in.
    m.js(BAR + """const w = main(); w.focus(); await w.PanelUI.show(); for (let i = 0; i < 40 && w.PanelUI.panel.state !== "open"; i++) await wait(50); return 1;""")
    press_in(m, "main()", "k", CMD, SHIFT)
    r = {}
    for _ in range(60):
        r = m.js(BAR + """const w = main(), [b] = barWindows(); if (!b) return {own: 0, panel: !!bar()};
          return {own: barWindows().length, panel: !!bar(), centre: Math.abs((b.screenX + b.outerWidth / 2) - (w.screenX + w.outerWidth / 2)),
                  inside: b.screenY >= w.screenY && b.screenY + b.outerHeight <= w.screenY + w.outerHeight, tabs: b.gBrowser.tabs.length, kept: b.gBrowser.tabs.filter(t => key(b, t) || role(b, t)).length};""")
        if r["own"]:
            break
        time.sleep(0.1)
    check("with another panel of Firefox's open, the bar is a small window of its own, centred over the one you are in, and no part of tab sync",
          r.get("own") == 1 and not r["panel"] and r["centre"] < 8 and r["inside"] and r["tabs"] == 1 and r["kept"] == 0, str(r))
    # Esc, with real keys, in that window.
    m.chrome()
    for h in m.cmd("WebDriver:GetWindowHandles"):
        m.cmd("WebDriver:SwitchToWindow", {"handle": h, "focus": False})
        if m.js("return !window.toolbar.visible;"):
            m.cmd("WebDriver:SwitchToWindow", {"handle": h, "focus": True})
            m.js(H + """for (let i = 0; i < 60 && !(Services.focus.activeWindow === window && window.gBrowser.selectedBrowser.currentURI.spec.includes("commandbar.html")); i++) await wait(50); await wait(400); return 1;""")
            try:
                press(m, ESC)
            except RuntimeError as err:
                if "no such window" not in str(err):
                    raise
            break
    m.chrome()
    r = {}
    for _ in range(50):
        r = m.js(BAR + """const w = main(); return {own: barWindows().length, focus: Services.focus.activeWindow === w,
          closed: w.SessionStore.getClosedWindowData().filter(x => x.tabs[0]?.entries?.[0]?.url?.includes("/commandbar/commandbar.html")).length};""")
        if not r["own"] and r["focus"] and not r["closed"]:
            break
        time.sleep(0.1)
    check("Esc closes that window, back in the window you were in, and it is not kept under Recently Closed Windows", r == {"own": 0, "focus": True, "closed": 0}, str(r))
    m.js(H + """main().PanelUI.hide(); await wait(300); return 1;""")
    ready = bar_open(m)
    check("and with that panel gone the bar is in the window again", ready >= 0 and m.js(BAR + "return barWindows().length;") == 0)
    bar_keys(m, [ESC])
    wait_for_bar(m, False)

    # A toolbar button Firefox cannot show (a stylesheet that hides the toolbar and does not
    # hold it in place for the bar, as the dotfiles' did before it knew of the bar): Firefox
    # says it opened the panel and takes it away unseen. The key must not be dead for it.
    m.js(BAR + """const w = main(); w.__noButton = "data:text/css," + encodeURIComponent("#unified-extensions-button { display: none !important; }");
      w.windowUtils.loadSheetUsingURIString(w.__noButton, w.windowUtils.USER_SHEET); w.focus(); w.gBrowser.selectedBrowser.focus(); await wait(500); return 1;""")
    press_in(m, "main()", "k", CMD, SHIFT)
    r = {}
    for _ in range(60):
        r = m.js(BAR + """return {own: barWindows().length, panel: !!bar()};""")
        if r["own"]:
            break
        time.sleep(0.1)
    m.js(BAR + """for (const b of barWindows()) b.close(); const w = main(); w.windowUtils.removeSheetUsingURIString(w.__noButton, w.windowUtils.USER_SHEET);
      for (let i = 0; i < 50 && barWindows().length; i++) await wait(100); w.focus(); await wait(500); return 1;""")
    check("where Firefox cannot show the panel, the bar comes as a window of its own for the same press", r == {"own": 1, "panel": False},
          f"""{r} {[t for t in extension_message(m, {"type": "stats"}).get("traces", []) if "bar" in t][-4:] if r != {"own": 1, "panel": False} else ""}""")
    ready = bar_open(m)
    check("and it is in the window again as soon as Firefox can show it there", ready >= 0 and m.js(BAR + "return barWindows().length;") == 0)
    bar_keys(m, [ESC])
    wait_for_bar(m, False)

    # The window it was opened in closes under it: the bar goes with it, and the key works at once in another.
    windows = m.js(H + """const n = wins().length, w = main().OpenBrowserWindow(); w.__extra = true; for (let i = 0; i < 200 && !w.gBrowserInit?.delayedStartupFinished; i++) await wait(50); await wait(2500); return n;""")
    bar_open(m, "wins().find(w => w.__extra)")
    # (In it, or as a window of its own over it: a window this new can still take the keyboard
    # from a panel as it settles, on a busy machine, and the bar then comes as a window.)
    where = m.js(BAR + "return bar().window.__extra === true || barWindows().length === 1;")
    m.js(H + """Services.prefs.setBoolPref("browser.tabs.warnOnClose", false); wins().find(w => w.__extra).close(); for (let i = 0; i < 50 && wins().some(w => w.__extra); i++) await wait(100); return 1;""")
    gone = wait_for_bar(m, False)
    ready = bar_open(m)
    bar_keys(m, "example.org/?smoke-edge-source")
    bar_rows_until(m, lambda rows: rows and rows[0]["kind"] == "address")
    bar_keys(m, [ENTER])
    wait_for_bar(m, False)
    r = m.js(H + """const w = main(); for (let i = 0; i < 50 && !w.gBrowser.tabs.some(x => url(x).includes("smoke-edge-source")); i++) await wait(100);
      return {here: w.gBrowser.tabs.filter(x => url(x).includes("smoke-edge-source")).length, windows: wins().length};""")
    check("the bar opens in the window the key was pressed in; that window closing takes the bar with it, and the key works at once in another",
          where and gone and ready >= 0 and r["here"] == 1 and r["windows"] == windows, f"{where} {gone} {r} {windows}")
    m.js(H + """await removeWhere((w, t) => url(t).includes("smoke-edge-source") || t.label.includes("smoke-edge-source")); main().focus(); return 1;""")
    press(m, str(start["space"]), CTRL)
    time.sleep(1)
    left = m.js(H + """return wins().filter(w => !w.toolbar.visible).length;""")
    check("no window stays behind after all that", left == 0, str(left))
    m.js(H + "await wait(%d); return 1;" % 2500)  # marks on tabs made a moment ago last that long
    # (The placeholders of the window closed a moment ago are looked for in Recently Closed for
    # ten seconds, FORGET_MS in common.js, and the bar is quick now: so until that has passed.)
    grown = {}
    for _ in range(6):
        kept = extension_message(m, {"type": "stats"})["sizes"]
        grown = {name: (kept_before[name], kept[name]) for name in kept if kept[name] > kept_before[name]}
        if not grown:
            break
        time.sleep(2)
    check("and no list in memory has grown with all those bars", not grown, str(grown))
