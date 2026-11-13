"""A row and what it can do: its menu and More, its name, new tabs, a saved tab away from its page,
and links dropped on the list.
"""
import time
from testfirefox import EXT_ID
from smokechecks.base import (
    CMD, CTRL, ENTER, ESC, H, bar_keys, bar_open, bar_rows_until,
    check, choose, close_sidebar_page, ext_page, extension_message, in_sidebar, into_page, menu_on,
    more_tabs_here, no_problems, press, seen, sidebar_page, to_folder, wait_for_bar,
)


def real_click(m, path, x, y, button=0):
    """A real click, through Marionette's actions, in one of Tidier's own pages in front."""
    into_page(m, path)
    m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"}, "actions": [
        {"type": "pointerMove", "x": int(x), "y": int(y), "duration": 0},
        {"type": "pointerDown", "button": button}, {"type": "pointerUp", "button": button}]}]})
    m.cmd("WebDriver:ReleaseActions")
    m.chrome()


# In the sidebar's page: right clicks and the menu, waiting for what they lead to.
MENU_PAGE = """
  const until = async (test, ms = 10000) => { const t0 = Date.now(); let r; while (!(r = test()) && Date.now() - t0 < ms) await wait(50); return r; };
  const menu = doc.getElementById("menu");
  const shown = () => [...menu.children].map(c => c.classList.contains("line") ? "|" : c.textContent);
  // Rename has its own checks, below and in alone_tab_names.
  const plain = list => list.filter(x => x !== "Rename").filter((x, i, a) => x !== "|" || a[i - 1] !== "|");
  const rowOf = id => doc.querySelector(`[data-tab="${id}"]`);
  const inFolder = id => rowOf(id)?.closest(".folder")?.querySelector(".head .title")?.textContent ?? null;
  const rightClick = async el => {
    menu.hidden = true;
    const box = el.getBoundingClientRect();
    el.dispatchEvent(new page.MouseEvent("contextmenu", {bubbles: true, cancelable: true, button: 2, clientX: box.left + 8, clientY: box.top + 8}));
    await until(() => !menu.hidden);
    return plain(shown());
  };
  const choose = label => { const b = [...menu.querySelectorAll(".item")].find(x => x.textContent === label); if (!b) throw new Error(label + " is not in " + shown()); b.click(); };
"""


# In the browser: tabs by the id the extension knows them by, and waiting for them.
MENU_TABS = H + """
  const {ExtensionParent} = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
  const idOf = t => ExtensionParent.apiManager.global.tabTracker.getId(t);
  const tabs = () => wins().flatMap(w => w.gBrowser.tabs.map(t => ({w, t})));
  const byId = id => tabs().find(x => idOf(x.t) === id)?.t;
  const until = async (test, ms = 10000) => { const t0 = Date.now(); let r; while (!(r = test()) && Date.now() - t0 < ms) await wait(50); return r; };
  const record = async () => { await wait(400); return (await storage(%r, ["syncedTabs"])).syncedTabs; };
  const entriesOf = (all, text) => Object.entries(all).filter(([, e]) => e.url?.includes(text));
""" % EXT_ID


ROW_MENU = ["Reload", "Mute", "Unload", "|", "Duplicate", "Copy address", "|", "Make essential", "Move to folder", "Move to space", "Open a copy in space", "Always open this site here", "|", "Close", "|", "More"]


def no_cookies_item(labels):
    """The menu without the one item that depends on an optional permission (isolation.js),
    which a run may or may not have (TIDIER_ALONE_ALL_PERMISSIONS)."""
    return [label for label in labels if label != "Clear this site's cookies in this space"]


def alone_tab_menu(m):
    # Tidier's own menu on a row and a tile: what it offers, and what each item does.
    space = sidebar_page(m, "return spaces().find(s => s.active).id;")
    ctx = int(space.split("-")[-1])

    def open_tab(name, where="main()", address=None):
        """A tab in the active space, registered, and its id."""
        return m.js(MENU_TABS + """const w = %s; const t = w.gBrowser.addTrustedTab(args[0], {userContextId: args[1], inBackground: true});
          await until(() => role(w, t) === "live"); return idOf(t);""" % where, address or f"https://example.org/?smoke-menu-{name}", ctx)

    def act(tab, *labels):
        """Right click its row, choose (going through a list if several), and leave the rest to the checks."""
        return sidebar_page(m, MENU_PAGE + """await until(() => rowOf(args[0]));
          await rightClick(rowOf(args[0]));
          for (const label of args.slice(1)) choose(label);
          await wait(50); return 1;""", tab, *labels)

    def clear_rules():
        extension_message(m, {"type": "settings:rules", "rules": []})

    def page_loads(tab):
        return m.js(MENU_TABS + "return byId(args[0]).linkedBrowser.innerWindowID;", tab)

    a, b, c = open_tab("a"), open_tab("b"), open_tab("c")
    try:
        # What it offers.
        r = sidebar_page(m, MENU_PAGE + """
          const row = await until(() => rowOf(args[0]));
          const labels = await rightClick(row), about = row.classList.contains("menu-for");
          page.dispatchEvent(new page.KeyboardEvent("keydown", {key: "Escape", bubbles: true, cancelable: true}));
          const closed = menu.hidden, left = row.classList.contains("menu-for");
          const tile = doc.querySelector("#essentials .tile"), tileLabels = await rightClick(tile);
          menu.hidden = true;
          // The keys: ↑ from the top is the last item, → opens a list with its first item ready, ← goes back.
          await rightClick(row);
          const key = k => doc.activeElement.dispatchEvent(new page.KeyboardEvent("keydown", {key: k, bubbles: true, cancelable: true}));
          const at = () => doc.activeElement.textContent;
          const inMenu = doc.activeElement === menu;
          key("ArrowDown"); const first = at();
          key("ArrowUp"); const last = at();
          const more = [...menu.querySelectorAll(".item")].find(x => x.textContent === "Move to space"); more.focus();
          key("ArrowRight"); const sub = {top: menu.firstChild.textContent, focus: doc.activeElement.classList.contains("back"), at: at()};
          key("ArrowLeft"); const back = menu.querySelectorAll(".back").length;
          // A click outside only closes it: the row under the pointer stays as it is.
          const selectedBefore = doc.querySelector("#tabs .tab.active")?.dataset.tab;
          rowOf(args[1]).click();
          await wait(500);
          const outside = {closed: menu.hidden, selected: doc.querySelector("#tabs .tab.active")?.dataset.tab === selectedBefore};
          return {labels, about, closed, left, tileLabels, keys: {inMenu, first, last, sub, back}, outside};""", a, b)
        check("a right click on a row shows Tidier's menu, in its order", no_cookies_item(r["labels"]) == ROW_MENU, str(r))
        check("the menu marks the row it is about, and Esc closes it", r["about"] and r["closed"] and not r["left"], str(r))
        k = r["keys"]
        check("the arrow keys go through the menu, and into a list and back", k["inMenu"] and k["first"] == "Reload" and k["last"] == "More" and k["sub"]["top"] == "Move to space"
              and not k["sub"]["focus"] and k["sub"]["at"] and k["back"] == 0, str(k))
        check("a click outside the menu only closes it", r["outside"] == {"closed": True, "selected": True}, str(r["outside"]))
        # (No Close on a tile: an essential closed comes back unloaded, which Unload does.)
        # Where it stands: clear of the row or tile it is about, so you see which one; and a
        # list in its place keeps its corner and width, so nothing jumps.
        at = sidebar_page(m, MENU_PAGE + """const clear = (el, box = menu.getBoundingClientRect(), r = el.getBoundingClientRect()) => box.top >= r.bottom || box.bottom <= r.top || box.left >= r.right || box.right <= r.left;
          const row = rowOf(args[0]); await rightClick(row);
          const out = {row: clear(row), marked: row.classList.contains("menu-for")}, was = menu.getBoundingClientRect();
          choose("Move to space"); const now = menu.getBoundingClientRect();
          out.list = {left: now.left === was.left, top: now.top === was.top, width: now.width >= was.width - 0.5};
          menu.hidden = true;
          const tile = doc.querySelector("#essentials .tile"); await rightClick(tile);
          out.tile = clear(tile); out.tileMarked = tile.classList.contains("menu-for");
          menu.hidden = true;
          const head = doc.querySelector("#tabs .folder .head");
          if (head) { head.dispatchEvent(new page.MouseEvent("contextmenu", {bubbles: true, cancelable: true, button: 2, clientX: head.getBoundingClientRect().left + 8, clientY: head.getBoundingClientRect().top + 8}));
            await until(() => !menu.hidden); out.head = clear(head) && head.classList.contains("menu-for"); }
          page.dispatchEvent(new page.KeyboardEvent("keydown", {key: "Escape", bubbles: true, cancelable: true}));
          return out;""", a)
        check("a menu opens clear of the row it is about, which is marked, and a list in its place keeps its corner and width",
              at["row"] and at["marked"] and at["list"] == {"left": True, "top": True, "width": True}, str(at))
        check("on a tile and a folder's head it stands clear of them too, and marks them", at["tile"] and at["tileMarked"] and at.get("head", True), str(at))
        tile_rest = ["Duplicate", "Copy address", "|", "Remove from essentials", "Open a copy in space"]
        check("a right click on a tile offers no folder, move to a space, rule or close", no_cookies_item(r["tileLabels"]) in ([*tile_rest, "|", "More"], ["Reload", "Mute", "Unload", "|", *tile_rest, "|", "More"]), str(r))
        r = sidebar_page(m, MENU_PAGE + """const row = rowOf(args[0]), opts = o => page.JSON.parse(JSON.stringify(o));
          // A redraw of its row (here: the sound mark) resets the row's classes.
          await rightClick(row);
          await page.browser.tabs.update(args[0], opts({muted: true}));
          await until(() => row.querySelector(".sound"));
          const redrawn = {open: !menu.hidden, mark: row.classList.contains("menu-for")};
          await page.browser.tabs.update(args[0], opts({muted: false}));
          await until(() => !row.querySelector(".sound"));
          const data = new page.DataTransfer(), at = {bubbles: true, cancelable: true, dataTransfer: data};
          row.dispatchEvent(new page.DragEvent("dragstart", at));
          const dragged = menu.hidden;
          row.dispatchEvent(new page.DragEvent("dragend", at));
          await rightClick(row);
          doc.activeElement.dispatchEvent(new page.KeyboardEvent("keydown", {key: "Tab", bubbles: true, cancelable: true}));
          const tabbed = menu.hidden;
          await rightClick(row);
          menu.dispatchEvent(new page.WheelEvent("wheel", {bubbles: true, deltaY: 10}));
          const scrolledIn = !menu.hidden;
          doc.getElementById("tabs").dispatchEvent(new page.WheelEvent("wheel", {bubbles: true, deltaY: 10}));
          const scrolled = menu.hidden;
          // A middle click outside only closes it too: the tab under the pointer stays.
          await rightClick(row);
          row.dispatchEvent(new page.MouseEvent("auxclick", {bubbles: true, cancelable: true, button: 1}));
          const middle = menu.hidden;
          await wait(500);
          return {redrawn, dragged, tabbed, scrolledIn, scrolled, middle, here: !!rowOf(args[0]), left: !!doc.querySelector(".menu-for")};""", a)
        check("the mark stays while its row is drawn anew", r["redrawn"] == {"open": True, "mark": True}, str(r))
        check("a drag, the Tab key or scrolling the list closes the menu, and scrolling in it does not", r["dragged"] and r["tabbed"] and r["scrolledIn"] and r["scrolled"] and not r["left"], str(r))
        check("a middle click outside the menu only closes it", r["middle"] and r["here"], str(r))
        g = open_tab("gone")
        r = sidebar_page(m, MENU_PAGE + """await until(() => rowOf(args[0])); await rightClick(rowOf(args[0])); const open = !menu.hidden;
          await page.browser.tabs.remove(args[0]); await until(() => menu.hidden, 3000); return {open, closed: menu.hidden};""", g)
        check("a menu about a tab that has gone closes", r == {"open": True, "closed": True}, str(r))

        # Reload and mute.
        before = page_loads(a)
        act(a, "Reload")
        after = m.js(MENU_TABS + "await until(() => byId(args[0]).linkedBrowser.innerWindowID !== args[1]); return byId(args[0]).linkedBrowser.innerWindowID;", a, before)
        check("Reload loads the page again", after != before, f"{before}, {after}")
        act(a, "Mute")
        muted = m.js(MENU_TABS + "await until(() => byId(args[0]).linkedBrowser.audioMuted); return byId(args[0]).linkedBrowser.audioMuted;", a)
        r = sidebar_page(m, MENU_PAGE + "const l = await rightClick(rowOf(args[0])); choose('Unmute'); return l;", a)
        unmuted = m.js(MENU_TABS + "await until(() => !byId(args[0]).linkedBrowser.audioMuted); return byId(args[0]).linkedBrowser.audioMuted;", a)
        check("Mute mutes, and then the menu offers Unmute", muted and not unmuted and "Unmute" in r and "Mute" not in r, f"{muted}, {unmuted}, {r}")

        # Unload, a tab not selected: it stays, in its place, and the page goes.
        selected = m.js(MENU_TABS + "return idOf(main().gBrowser.selectedTab);")
        act(a, "Unload")
        r = m.js(MENU_TABS + """const t = byId(args[0]); await until(() => !t.linkedPanel); const all = await record();
          return {unloaded: !t.linkedPanel, url: url(t), stored: entriesOf(all, "smoke-menu-a").length, selected: idOf(main().gBrowser.selectedTab)};""", a)
        check("Unload unloads a tab, which stays, and the selection stays too", r["unloaded"] and "smoke-menu-a" in r["url"] and r["stored"] == 1 and r["selected"] == selected, str(r))
        r = sidebar_page(m, MENU_PAGE + "await until(() => rowOf(args[0]).classList.contains('unloaded')); const l = await rightClick(rowOf(args[0])); menu.hidden = true; return {l, faded: rowOf(args[0]).classList.contains('unloaded')};", a)
        check("an unloaded tab's menu has nothing to reload, mute or unload", no_cookies_item(r["l"]) == ROW_MENU[4:] and r["faded"], str(r))

        # Duplicate of what is not loaded: the address, in the same container, an ordinary tab.
        act(a, "Duplicate")
        r = m.js(MENU_TABS + """const has = () => tabs().filter(x => x.t.linkedPanel && idOf(x.t) !== args[0] && url(x.t).includes("smoke-menu-a"));
          await until(() => has().length && role(has()[0].w, has()[0].t) === "live");
          const copy = has()[0]?.t, all = await record();
          return {found: !!copy, id: copy && idOf(copy), container: copy?.userContextId, pinned: copy?.pinned, stored: entriesOf(all, "smoke-menu-a").length, selected: idOf(main().gBrowser.selectedTab)};""", a)
        check("Duplicate of an unloaded tab opens its address in the same container, and you stay", r["found"] and r["container"] == ctx and not r["pinned"] and r["stored"] == 2 and r["selected"] == selected, str(r))
        d = r["id"]

        # Duplicate of a loaded saved tab, with a rule that would send it away: an ordinary
        # tab of its own, here, and the saved tab keeps its record.
        sidebar_page(m, """send({type: "newFolder", space: spaces().find(s => s.active).id, name: "Menu kept"});
          await wait(600);
          const head = [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "Menu kept");
          send({type: "moveTab", tabId: args[0], folder: head.dataset.folderHead, before: null});
          await page.browser.runtime.sendMessage(page.JSON.parse(JSON.stringify({type: "settings:rules", rules: [{url: "smoke-menu-b", space: spaces().find(s => !s.active && s.id !== "firefox-container-4").id}]})));
          await wait(800);
          return 1;""", b)
        r = sidebar_page(m, MENU_PAGE + """const head = [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "Menu kept");
          await rightClick(head); const folder = shown(), list = await rightClick(doc.getElementById("tabs")); menu.hidden = true; return {folder, list};""")
        check("a folder and the empty list keep their own short menus", r["folder"] == ["New tab here", "|", "Rename", "Delete folder (its tabs stay)", "Move to space", "|", "More"] and r["list"][0] == "New folder" and "Reload" not in r["list"], str(r))
        # Rename on a tile and on a saved tab's row opens the box, ready for typing. (What you
        # then do in it is for alone_tab_names.) Esc leaves everything as it was.
        r = sidebar_page(m, MENU_PAGE + """const named = async el => {
            await rightClick(el);
            choose("Rename");
            const box = await until(() => doc.querySelector("input.rename"));
            const out = {open: !!box, focus: !!box && doc.activeElement === box};
            box?.dispatchEvent(new page.KeyboardEvent("keydown", {key: "Escape", bubbles: true, cancelable: true}));
            await until(() => !doc.querySelector("input.rename"));
            return {...out, left: !!doc.querySelector("input.rename")};
          };
          return {tile: await named(doc.querySelector("#essentials .tile")), row: await named(rowOf(args[0]))};""", b)
        check("Rename on a tile opens the box, with the focus in it", r["tile"] == {"open": True, "focus": True, "left": False}, str(r))
        check("Rename on a saved tab's row opens the box, with the focus in it", r["row"] == {"open": True, "focus": True, "left": False}, str(r))
        act(b, "Duplicate")
        r = m.js(MENU_TABS + """const has = () => tabs().filter(x => idOf(x.t) !== args[0] && url(x.t).includes("smoke-menu-b") && x.t.linkedPanel);
          await until(() => has().length && role(has()[0].w, has()[0].t) === "live");
          const copy = has()[0]?.t, w = has()[0]?.w; await wait(1000); const all = await record();
          const list = entriesOf(all, "smoke-menu-b"), mine = list.find(([k]) => JSON.stringify(k) === key(main(), byId(args[0])));
          const theirs = list.find(([k]) => w && JSON.stringify(k) === key(w, copy));
          return {copy: !!copy, container: copy?.userContextId, keys: list.length, saved: !!mine?.[1].saved, parent: !!mine?.[1].parentKey, copySaved: !!theirs?.[1].saved, copyParent: theirs?.[1].parentKey ?? null, id: copy && idOf(copy), left: tabs().filter(x => url(x.t).includes("smoke-menu-b") && x.t.userContextId !== args[1]).length};""", b, ctx)
        check("a copy of a saved tab is an ordinary tab of its own, and the saved tab keeps its record", r["copy"] and r["keys"] == 2 and r["saved"] and r["parent"] and not r["copySaved"] and r["copyParent"] is None, str(r))
        check("a rule does not send a copy to another space", r["container"] == ctx and r["left"] == 0, str(r))
        clear_rules()

        # Unload on the selected tab: to another tab of the space first.
        sidebar_page(m, MENU_PAGE + "rowOf(args[0]).click(); return 1;", c)
        was = m.js(MENU_TABS + "await until(() => idOf(main().gBrowser.selectedTab) === args[0]); return idOf(main().gBrowser.selectedTab);", c)
        act(c, "Unload")
        r = m.js(MENU_TABS + """const t = byId(args[0]); await until(() => !t.linkedPanel); const s = main().gBrowser.selectedTab;
          return {unloaded: !t.linkedPanel, selected: idOf(s), container: s.userContextId};""", c)
        check("Unload on the selected tab goes to another tab of the space, and unloads it", was == c and r["unloaded"] and r["selected"] != c and r["container"] == ctx, str(r))

        # A page with unsaved input stays, selected, without asking.
        u = open_tab("unsaved", address=m.pages + "/unsaved?smoke-menu-unsaved")
        sidebar_page(m, MENU_PAGE + "await until(() => rowOf(args[0])); rowOf(args[0]).click(); return 1;", u)
        m.js(MENU_TABS + "await until(() => idOf(main().gBrowser.selectedTab) === args[0]); await wait(800); return 1;", u)
        act(u, "Unload")
        time.sleep(1.5)
        r = m.js(MENU_TABS + """const t = byId(args[0]); return {loaded: !!t.linkedPanel, selected: main().gBrowser.selectedTab === t};""", u)
        check("Unload leaves a page with unsaved input loaded and selected, without asking", r == {"loaded": True, "selected": True}, str(r))
        m.js(MENU_TABS + """const t = byId(args[0]); const k = key(main(), t);
          for (const w of wins()) for (const x of [...w.gBrowser.tabs]) if (key(w, x) === k) w.gBrowser.removeTab(x, {skipPermitUnload: true});
          await wait(1500); return 1;""", u)

        # Copy address: the page's, never the placeholder's; on the real clipboard of the test Firefox.
        clipboard = MENU_TABS + """const read = () => { const t = Cc["@mozilla.org/widget/transferable;1"].createInstance(Ci.nsITransferable); t.init(null); t.addDataFlavor("text/plain");
          Services.clipboard.getData(t, Ci.nsIClipboard.kGlobalClipboard, main().browsingContext.currentWindowContext);
          const o = {}; try { t.getTransferData("text/plain", o); return o.value.QueryInterface(Ci.nsISupportsString).data; } catch (e) { return ""; } };"""
        m.js(clipboard + 'Cc["@mozilla.org/widget/clipboardhelper;1"].getService(Ci.nsIClipboardHelper).copyString("before"); return 1;')
        act(a, "Copy address")
        copied = m.js(clipboard + 'await until(() => read() !== "before", 3000); return read();')
        # And it says so, where ⇧⌘C says it: on the page where Tidier may write there, else
        # on the sidebar's own line (sayDone, pagenote.js).
        said = sidebar_page(m, """for (let i = 0; i < 60; i++) { const n = doc.getElementById("note");
            if (n.classList.contains("shown")) return doc.querySelector("#note .text").textContent;
            await wait(100); }
          return "";""")
        check("Copy address copies the page's address from an unloaded tab", copied == "https://example.org/?smoke-menu-a", repr(copied))
        check("and says so, as ⇧⌘C does", said == "Address copied", repr(said))

        # A row that is only a placeholder here, with the page loaded in another window.
        opened = m.js(H + """if (other()) return false; const w = main().OpenBrowserWindow(); w.__smoke = true;
          for (let i = 0; i < 100 && !w.gBrowser?.tabs.some(t => key(w, t)); i++) await wait(100); await wait(1500); return true;""")
        far = open_tab("far", where="other()")
        ghost = m.js(MENU_TABS + """const k = key(other(), byId(args[0]));
          await until(() => main().gBrowser.tabs.some(t => key(main(), t) === k)); return idOf(main().gBrowser.tabs.find(t => key(main(), t) === k));""", far)
        before = page_loads(far)
        r = sidebar_page(m, MENU_PAGE + """await until(() => rowOf(args[0])); const l = await rightClick(rowOf(args[0])); choose("Reload"); return l;""", ghost)
        after = m.js(MENU_TABS + "await until(() => byId(args[0]).linkedBrowser.innerWindowID !== args[1]); return byId(args[0]).linkedBrowser.innerWindowID;", far, before)
        check("a placeholder's Reload loads the page in the other window again", ghost != far and no_cookies_item(r) == ROW_MENU and after != before, f"{ghost}, {far}, {r}, {before}, {after}")
        m.js(clipboard + 'Cc["@mozilla.org/widget/clipboardhelper;1"].getService(Ci.nsIClipboardHelper).copyString("before"); return 1;')
        act(ghost, "Copy address")
        copied = m.js(clipboard + 'await until(() => read() !== "before", 3000); return read();')
        check("a placeholder's Copy address is the page's", copied == "https://example.org/?smoke-menu-far", repr(copied))
        act(ghost, "Close")
        r = m.js(MENU_TABS + """await until(() => !byId(args[0]) && !byId(args[1])); return [!!byId(args[0]), !!byId(args[1])];""", far, ghost)
        check("a placeholder's Close closes the page in every window", r == [False, False], str(r))

        def placeholder_of(tab):
            return m.js(MENU_TABS + """const k = key(other(), byId(args[0]));
              await until(() => main().gBrowser.tabs.some(t => key(main(), t) === k)); return idOf(main().gBrowser.tabs.find(t => key(main(), t) === k));""", tab)
        far, far2, far3 = open_tab("far", where="other()"), open_tab("far2", where="other()"), open_tab("far3", where="other()")
        ghost, ghost3 = placeholder_of(far), placeholder_of(far3)

        # Duplicate: Firefox would put the copy over there, and its row at the end of this list.
        act(ghost, "Duplicate")
        r = m.js(MENU_TABS + """const w = main(), page = "https://example.org/?smoke-menu-far", has = () => w.gBrowser.tabs.find(t => url(t) === page);
          await until(() => has() && role(w, has()) === "live");
          const copy = has(), list = [...w.gBrowser.tabs], there = other().gBrowser.tabs.filter(t => url(t) === page && idOf(t) !== args[0]).length;
          return {found: !!copy, next: list.indexOf(copy) === list.indexOf(byId(args[1])) + 1, container: copy?.userContextId, there, id: copy && idOf(copy), selected: copy?.selected};""", far, ghost)
        check("Duplicate of a placeholder opens the page here, next to its row, and you stay", r["found"] and r["next"] and r["container"] == ctx and r["there"] == 0 and not r["selected"], str(r))
        act(r["id"], "Close")

        # Unload: the page in the other window goes, and the placeholder here stays.
        act(ghost, "Unload")
        r = m.js(MENU_TABS + """await until(() => !byId(args[0]).linkedPanel); return {page: !!byId(args[0]).linkedPanel, url: url(byId(args[0])), here: !!byId(args[1])};""", far, ghost)
        check("a placeholder's Unload unloads the page in the other window", r == {"page": False, "url": "https://example.org/?smoke-menu-far", "here": True}, str(r))
        r = sidebar_page(m, MENU_PAGE + "const l = await rightClick(rowOf(args[0])); menu.hidden = true; return l;", ghost)
        check("after which its menu has nothing to reload, mute or unload", no_cookies_item(r) == ROW_MENU[4:], str(r))

        # Make essential: the page itself is pinned where it is, and stays loaded.
        ghost2 = placeholder_of(far2)
        act(ghost2, "Make essential")
        r = m.js(MENU_TABS + """const t = byId(args[0]); await until(() => t.pinned && ek(other(), t) && !byId(args[1]));
          const k = ek(other(), t); await until(() => main().gBrowser.tabs.some(x => ek(main(), x) === k));
          const here = main().gBrowser.tabs.find(x => ek(main(), x) === k);
          return {pinned: t.pinned, loaded: !!t.linkedPanel, placeholder: !!byId(args[1]), tile: here && idOf(here), record: entriesOf(await record(), "smoke-menu-far2").length};""", far2, ghost2)
        check("a placeholder's Make essential pins the page where it is, loaded, with a tile here", r["pinned"] and r["loaded"] and not r["placeholder"] and r["tile"] and r["record"] == 0, str(r))
        act(r["tile"], "Remove from essentials")
        r = m.js(MENU_TABS + """const t = byId(args[0]); await until(() => !t.pinned && role(other(), t) === "live" && !byId(args[1]));
          return {pinned: t.pinned, loaded: !!t.linkedPanel, tile: !!byId(args[1]), record: entriesOf(await record(), "smoke-menu-far2").length};""", far2, r["tile"])
        check("Remove from essentials on its tile leaves the page there as an ordinary tab", r == {"pinned": False, "loaded": True, "tile": False, "record": 1}, str(r))

        # Move to space: the page, wherever it is, and you stay.
        selected = m.js(MENU_TABS + "return idOf(main().gBrowser.selectedTab);")
        act(ghost3, "Move to space", "Space 2")
        r = m.js(MENU_TABS + """await until(() => !byId(args[0]) && !byId(args[1]) && tabs().some(x => url(x.t).includes("smoke-menu-far3")));
          return {gone: [!!byId(args[0]), !!byId(args[1])], there: tabs().filter(x => url(x.t).includes("smoke-menu-far3")).map(x => x.t.userContextId !== args[2]), selected: idOf(main().gBrowser.selectedTab)};""", far3, ghost3, ctx)
        check("a placeholder's Move to space moves the page, and you stay", r["gone"] == [False, False] and r["there"] and all(r["there"]) and r["selected"] == selected, str(r))

        # Close, on a saved tab: closing the placeholder here would remove it for good.
        far4 = open_tab("far4", where="other()")
        ghost4 = placeholder_of(far4)
        sidebar_page(m, MENU_PAGE + """const head = [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "Menu kept");
          send({type: "moveTab", tabId: args[0], folder: head.dataset.folderHead, before: null}); await wait(500); return 1;""", ghost4)
        act(ghost4, "Close")
        r = m.js(MENU_TABS + """await until(() => !byId(args[0])); const list = entriesOf(await record(), "smoke-menu-far4");
          return {page: !!byId(args[0]), here: !!byId(args[1]), kept: list.length, saved: !!list[0]?.[1].saved};""", far4, ghost4)
        check("a placeholder's Close on a saved tab only unloads it", r == {"page": False, "here": True, "kept": 1, "saved": True}, str(r))
        if opened:
            m.js(H + """await close(other()); return 1;""")

        # A tile's own: a copy is an ordinary tab, and its Unload and Close leave the essential.
        tile = sidebar_page(m, "return Number(doc.querySelector('#essentials .tile').dataset.tab);")
        n = sidebar_page(m, "return tiles().length;")
        act(tile, "Duplicate")
        r = m.js(MENU_TABS + """const w = main(), has = () => w.gBrowser.tabs.find(t => !t.pinned && url(t).includes("fixture-essential"));
          await until(() => has() && role(w, has()) === "live");
          const copy = has(), s = await storage(%r, ["essentials"]);
          return {found: !!copy, pinned: copy?.pinned, essential: copy && ek(w, copy), id: copy && idOf(copy), container: copy?.userContextId, list: s.essentials.length};""" % EXT_ID)
        count = sidebar_page(m, "await wait(300); return tiles().length;")
        check("Duplicate of a tile is an ordinary tab of its own, and the essential stays one", r["found"] and not r["pinned"] and not r["essential"] and r["container"] == ctx and count == n, str(r))
        act(r["id"], "Close")
        sidebar_page(m, MENU_PAGE + "rowOf(args[0]).click(); return 1;", tile)
        m.js(MENU_TABS + "await until(() => idOf(main().gBrowser.selectedTab) === args[0]); await wait(800); return 1;", tile)
        act(tile, "Unload")
        r = m.js(MENU_TABS + """const t = byId(args[0]); await until(() => !t.linkedPanel); const s = main().gBrowser.selectedTab;
          return {unloaded: !t.linkedPanel, pinned: t.pinned, selected: idOf(s) !== args[0], container: s.userContextId};""", tile)
        check("Unload on the selected tile goes to another tab of the space, and unloads it", r == {"unloaded": True, "pinned": True, "selected": True, "container": ctx}, str(r))
        # No Close on a tile: on an essential it only did what Unload does, and read as if it went.
        sidebar_page(m, MENU_PAGE + "rowOf(args[0]).click(); return 1;", tile)
        m.js(MENU_TABS + "await until(() => idOf(main().gBrowser.selectedTab) === args[0] && byId(args[0]).linkedPanel); await wait(800); return 1;", tile)
        r = sidebar_page(m, MENU_PAGE + "const l = await rightClick(rowOf(args[0])); menu.hidden = true; return l;", tile)
        check("a loaded tile offers Unload, and no Close", "Unload" in r and "Close" not in r, str(r))

        # Make essential, and back.
        r = sidebar_page(m, MENU_PAGE + """const n = tiles().length; await rightClick(rowOf(args[0])); choose("Make essential");
          await until(() => tiles().length === n + 1 && rowOf(args[0])?.classList.contains("tile"));
          const pinned = tiles().length, tile = rowOf(args[0]); const labels = await rightClick(tile); choose("Remove from essentials");
          await until(() => tiles().length === n && rowOf(args[0])?.classList.contains("tab"));
          return {n, pinned, labels, after: tiles().length, row: rowOf(args[0])?.classList.contains("tab")};""", d)
        check("Make essential makes a tile, and its menu takes it back to an ordinary tab", r["pinned"] == r["n"] + 1 and r["after"] == r["n"] and r["row"] and "Remove from essentials" in r["labels"] and "Move to folder" not in r["labels"], str(r))
        m.js(MENU_TABS + """await until(() => { const t = byId(args[0]); return t && role(main(), t) === "live"; }); return 1;""", d)

        # Move to folder, and a new folder that takes the tab and starts renaming.
        r = sidebar_page(m, MENU_PAGE + """const n = folders().length; await rightClick(rowOf(args[0])); choose("Move to folder");
          const list = shown(), back = menu.firstChild.classList.contains("back");
          choose("New folder");
          const input = await until(() => doc.querySelector("#tabs .folder .rename"));
          await until(() => input?.closest(".folder").contains(rowOf(args[0])));
          const got = {n, list, back, value: input?.value, typing: doc.activeElement === input, selected: input && input.selectionStart === 0 && input.selectionEnd === input.value.length};
          input?.dispatchEvent(new page.KeyboardEvent("keydown", {key: "Enter", bubbles: true, cancelable: true}));
          await until(() => folders().length === n + 1 && folders().every(f => f.name));
          got.name = inFolder(args[0]); got.gone = !doc.querySelector("#tabs .folder .rename");
          return got;""", d)
        check("Move to folder lists the folders, then New folder, with a way back", r["back"] and r["list"][:2] == ["Move to folder", "|"] and "Menu kept" in r["list"] and r["list"][-1] == "New folder", str(r))
        check("a new folder takes the tab, with a good name selected, and Enter accepts it", r["value"] == "Example" and r["typing"] and r["selected"] and r["name"] == "Example" and r["gone"], str(r))
        r = sidebar_page(m, MENU_PAGE + """await rightClick(rowOf(args[0])); choose("Move to folder"); const list = shown(); choose("No folder");
          await until(() => inFolder(args[0]) === null);
          return {list, out: inFolder(args[0]), plain: !!rowOf(args[0]).closest("#tabs > .tab")};""", d)
        check("Move to folder lists No folder and not its own, and No folder takes it out", r["out"] is None and r["plain"] and "No folder" in r["list"] and "Example" not in r["list"], str(r))
        s = m.js(MENU_TABS + "const all = await record(); return Object.values(all).filter(x => x.url?.includes('smoke-menu-a')).map(x => !!x.saved);")
        check("a tab taken out of a folder is not saved any more", not any(s), str(s))

        # Move to space: there, gone here, and you stay.
        selected = m.js(MENU_TABS + "return idOf(main().gBrowser.selectedTab);")
        r = sidebar_page(m, MENU_PAGE + """await rightClick(rowOf(args[0])); choose("Move to space");
          const list = shown(), dots = menu.querySelectorAll(".dot:not(.plus)").length, plus = !!menu.querySelector(".item:last-child .dot.plus");
          menu.querySelector(".back").click(); const again = plain(shown());
          choose("Move to space"); choose(list[2]);
          await until(() => !rowOf(args[0]) && doc.getElementById("note").classList.contains("shown"));
          return {list, dots, plus, again, gone: !rowOf(args[0]), active: spaces().find(s => s.active).id, note: doc.querySelector("#note .text")?.textContent};""", d)
        check("Move to space lists the other spaces with their colours, and the row back goes back", r["dots"] == len(r["list"]) - 3 and r["list"][-1] == "New space" and r["dots"] >= 2 and no_cookies_item(r["again"]) == ROW_MENU, str(r))
        check("New space has a + where the spaces have their dots", r["plus"], str(r))
        moved = m.js(MENU_TABS + """await until(() => tabs().some(x => url(x.t).includes("smoke-menu-a") && x.t.userContextId !== args[0]));
          return {there: tabs().filter(x => url(x.t).includes("smoke-menu-a") && x.t.userContextId !== args[0]).length, selected: idOf(main().gBrowser.selectedTab)};""", ctx)
        check("Move to space moves the tab, and you stay where you are", r["gone"] and r["active"] == space and moved["there"] >= 1 and moved["selected"] == selected, f"{r}, {moved}")
        check("and the line says where it went", r["note"] == "Moved to " + r["list"][2], str(r))

        # A move loses nothing: an unloaded tab arrives unloaded, with no request sent for
        # it, and a muted one muted; one line says where they went, and Undo brings them back
        # as they were. Pages of the test server, which records every request.
        u, mu = open_tab("u", address=m.pages + "/r/smoke-move-unloaded"), open_tab("mu", address=m.pages + "/r/smoke-move-muted")
        m.js(MENU_TABS + """const [a, b] = [byId(args[0]), byId(args[1])]; main().gBrowser.discardBrowser(a); b.toggleMuteAudio();
          await until(() => !a.linkedPanel && b.muted); await wait(500); return 1;""", u, mu)
        asked = len(seen(m, "smoke-move-unloaded"))
        r = sidebar_page(m, MENU_PAGE + """const before = page.selectedTabs, picked = args.slice(0, 2);
          page.selectedTabs = page.Array.prototype.slice.bind(page.JSON.parse(JSON.stringify(picked)), 0, 2);
          try {
            await rightClick(rowOf(picked[0])); choose("Move 2 tabs to space");
            const to = [...menu.querySelectorAll(".item:not(.back)")].find(b => b.querySelector(".dot")).textContent;
            choose(to);
            await until(() => picked.every(id => !rowOf(id)) && doc.getElementById("note").classList.contains("shown"));
            return {to, note: doc.querySelector("#note .text")?.textContent, undo: !doc.querySelector("#note .act")?.hidden};
          } finally { page.selectedTabs = before; }""", u, mu)
        MOVED = MENU_TABS + """const all = await record(), want = args[0];
          const entry = text => Object.entries(all).find(([, e]) => e.url?.includes(text));
          const state = text => { const [k, e] = entry(text) ?? []; const reps = tabs().filter(x => key(x.w, x.t) === JSON.stringify(k));
            return {space: e?.cookieStoreId, loaded: reps.filter(x => x.t.linkedPanel && !url(x.t).includes("ghost.html")).length, muted: reps.length > 0 && reps.every(x => x.t.muted), tabs: reps.length}; };
          await until(() => { const s = state("smoke-move-muted"); return s.space === want && s.loaded === 1; });
          // (Every window: as many as this run has, which is one when the group runs alone.)
          return {unloaded: state("smoke-move-unloaded"), muted: state("smoke-move-muted"), windows: wins().filter(w => w.toolbar.visible).length};"""
        names = sidebar_page(m, "return Object.fromEntries([...doc.querySelectorAll('#spaces .space')].map(b => [b.dataset.space, b.title]));")
        there = next(s for s, n in names.items() if n == r["to"])
        s = m.js(MOVED, there)
        check("an unloaded tab moved to another space arrives unloaded, in every window, and nothing is asked of its site",
              s["unloaded"]["space"] == there and s["unloaded"]["loaded"] == 0 and s["unloaded"]["tabs"] == s["windows"] and len(seen(m, "smoke-move-unloaded")) == asked, f"{s}, requests {asked} -> {len(seen(m, 'smoke-move-unloaded'))}")
        check("a muted tab moved to another space stays muted, in every window", s["muted"]["space"] == there and s["muted"]["muted"], str(s))
        check("the line says where they went, with Undo", r["note"] == f"2 tabs moved to {r['to']}" and r["undo"], str(r))
        sidebar_page(m, """doc.querySelector("#note .act").click(); await wait(100); return 1;""")
        s = m.js(MOVED, space)
        check("Undo brings them back as they were: unloaded, and muted", s["unloaded"]["space"] == space and s["unloaded"]["loaded"] == 0 and s["muted"]["muted"]
              and len(seen(m, "smoke-move-unloaded")) == asked, str(s))
        # (As new tabs, opened in this space again: found by their pages.)
        ids = m.js(MENU_TABS + """const all = await record();
          return Array.from(args, text => { const [k] = Object.entries(all).find(([, e]) => e.url?.includes(text)) ?? [];
            const t = tabs().find(x => x.w === main() && key(x.w, x.t) === JSON.stringify(k))?.t; return t ? idOf(t) : null; });""", "smoke-move-unloaded", "smoke-move-muted")
        r = sidebar_page(m, MENU_PAGE + "const ids = Array.from(args); await until(() => ids.every(id => rowOf(id))); return ids.map(id => !!rowOf(id));", *ids)
        check("and in this space's list again", r == [True, True], f"{ids} {r}")

        # Several tabs, as window.selectedTabs says (a function of the page's own: this is how
        # to make one where no script can be added). What the selection itself does has its own checks.
        s1, s2, s3 = open_tab("s1"), open_tab("s2"), open_tab("s3")

        def several(script):
            return sidebar_page(m, MENU_PAGE + """const before = page.selectedTabs, picked = args.slice(0, 3);
              page.selectedTabs = page.Array.prototype.slice.bind(page.JSON.parse(JSON.stringify(picked)), 0, 3);
              try { """ + script + """ } finally { page.selectedTabs = before; }""", s1, s2, s3)

        sidebar_page(m, MENU_PAGE + "await until(() => rowOf(args[0])); rowOf(args[0]).click(); return 1;", s2)
        m.js(MENU_TABS + "await until(() => idOf(main().gBrowser.selectedTab) === args[0]); await wait(500); return 1;", s2)
        many = ["Reload 3 tabs", "Mute 3 tabs", "Unload 3 tabs", "|", "Copy 3 addresses", "|", "Make 3 tabs essential", "Move 3 tabs to folder", "Move 3 tabs to space", "Open copies of 3 tabs in space", "|", "Close 3 tabs", "|", "More"]
        m.js(clipboard + 'Cc["@mozilla.org/widget/clipboardhelper;1"].getService(Ci.nsIClipboardHelper).copyString("before"); return 1;')
        r = several("""const labels = await rightClick(rowOf(picked[0])), marks = picked.filter(id => rowOf(id).classList.contains("menu-for")).length;
          choose("Copy 3 addresses"); return {labels, marks};""")
        copied = m.js(clipboard + 'await until(() => read() !== "before", 3000); return read();')
        check("with several tabs the menu counts them, marks them all, and leaves out what takes one", r == {"labels": many, "marks": 3}, str(r))
        check("Copy takes one address per line", copied == "https://example.org/?smoke-menu-s1\nhttps://example.org/?smoke-menu-s2\nhttps://example.org/?smoke-menu-s3", repr(copied))
        several("""await rightClick(rowOf(picked[0])); choose("Unload 3 tabs"); return 1;""")
        r = m.js(MENU_TABS + """const ids = [...args], list = ids.map(byId); await until(() => list.every(t => !t.linkedPanel)); const s = main().gBrowser.selectedTab;
          return {unloaded: list.filter(t => !t.linkedPanel).length, stays: !ids.includes(idOf(s)), container: s.userContextId, kept: entriesOf(await record(), "smoke-menu-s").length};""", s1, s2, s3)
        check("Unload takes them all, the selected one too, and the selection goes to another tab", r == {"unloaded": 3, "stays": True, "container": ctx, "kept": 3}, str(r))
        r = several("""const labels = await rightClick(rowOf(picked[0])); choose("Move 3 tabs to folder"); choose("New folder");
          const input = await until(() => doc.querySelector("#tabs .folder .rename"));
          await until(() => picked.every(id => input?.closest(".folder").contains(rowOf(id))));
          const folder = input?.closest(".folder"), value = input?.value;
          input?.dispatchEvent(new page.KeyboardEvent("keydown", {key: "Enter", bubbles: true, cancelable: true}));
          await until(() => !doc.querySelector("#tabs .folder .rename"));
          return {labels, value, order: [...folder.querySelectorAll(".tab")].map(e => Number(e.dataset.tab))};""")
        check("unloaded, they offer what is left, and go to a new folder in the order shown", r == {"labels": many[4:], "value": "Example", "order": [s1, s2, s3]}, str(r))
        r = several("""await rightClick(rowOf(picked[0])); choose("Close 3 tabs"); await until(() => picked.every(id => !rowOf(id))); return picked.filter(id => rowOf(id)).length;""")
        left = m.js(MENU_TABS + """const ids = [...args]; await until(() => ids.every(id => !byId(id))); return {tabs: ids.filter(id => byId(id)).length, kept: entriesOf(await record(), "smoke-menu-s").length};""", s1, s2, s3)
        check("Close takes them all, and saved tabs that are not loaded are gone for good", r == 0 and left == {"tabs": 0, "kept": 0}, f"{r}, {left}")

        # Always open this site here: a rule anchored to the start of the address, for this space.
        e = open_tab("rule")
        act(e, "Always open this site here")
        rules = m.js(MENU_TABS + """await wait(800); return (await storage(%r, ["rules"])).rules;""" % EXT_ID)
        r = sidebar_page(m, MENU_PAGE + "const l = await rightClick(rowOf(args[0])); menu.hidden = true; return l;", e)
        check("Always open this site here adds an anchored rule for this space", rules == [{"url": "/^https?:\\/\\/(www\\.)?example\\.org\\//", "space": space}], str(rules))
        check("the menu no longer offers a rule that is there", "Always open this site here" not in r, str(r))
        clear_rules()

        # Close.
        act(e, "Close")
        r = m.js(MENU_TABS + """await until(() => !byId(args[0])); const all = await record(); return {gone: !byId(args[0]), stored: entriesOf(all, "smoke-menu-rule").length};""", e)
        check("Close closes the tab", r == {"gone": True, "stored": 0}, str(r))

        # A real right click, and a real click on an item: the menu opens, Firefox's own does not.
        m.js(MENU_TABS + """const w = main(); w.__before = w.gBrowser.selectedTab; w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes("/sidebar/sidebar.html")); await wait(500); return 1;""")
        box = sidebar_page(m, MENU_PAGE + "await until(() => rowOf(args[0])); const r = rowOf(args[0]).getBoundingClientRect(); return [r.left + 30, r.top + 8];", b)
        real_click(m, "/sidebar/sidebar.html", box[0], box[1], button=2)
        r = sidebar_page(m, MENU_PAGE + """await until(() => !menu.hidden, 3000);
          const item = [...menu.querySelectorAll(".item")].find(x => x.textContent === "Copy address").getBoundingClientRect();
          return {open: !menu.hidden, labels: plain(shown()), at: [item.left + 8, item.top + 8]};""")
        own = m.js(H + """const d = main().document; return {state: d.getElementById("contentAreaContextMenu")?.state, tabMenu: d.getElementById("tabContextMenu")?.state, ctx: !!main().gContextMenu};""")
        check("a real right click opens Tidier's menu and not Firefox's", r.get("open") and "Copy address" in r["labels"] and own == {"state": "closed", "tabMenu": "closed", "ctx": False}, f"{r}, {own}")
        m.js(clipboard + 'Cc["@mozilla.org/widget/clipboardhelper;1"].getService(Ci.nsIClipboardHelper).copyString("before"); return 1;')
        real_click(m, "/sidebar/sidebar.html", r["at"][0], r["at"][1])
        copied = m.js(clipboard + 'await until(() => read() !== "before", 3000); return read();')
        closed = sidebar_page(m, "return doc.getElementById('menu').hidden;")
        check("a real click on an item does it, and closes the menu", copied == "https://example.org/?smoke-menu-b" and closed, f"{copied!r}, {closed}")
        m.js(H + """const w = main(); if (w.__before && !w.__before.closing) w.gBrowser.selectedTab = w.__before; await wait(300); return 1;""")

        # The same in the real sidebar, where a page in a tab cannot say what it is like: its
        # contents cannot be read from here, but where things are can be, and the clipboard shows the result.
        # Its list has a scroll of its own, so the place of the row is read there too.
        real_row = f"""doc.querySelector('[data-tab="{b}"]')"""
        in_sidebar(m, f"""() => {{ {real_row}.scrollIntoView({{block: "center"}}); return 1; }}""")
        m.js(H + """const w = main(); w.focus(); await wait(300);
          // A panel of Firefox's own (it says when an extension hides tabs) would take the first click.
          for (const p of w.document.querySelectorAll("panel, menupopup")) if (p.state === "open") p.hidePopup();
          await wait(300); return 1;""")
        m.js(clipboard + 'Cc["@mozilla.org/widget/clipboardhelper;1"].getService(Ci.nsIClipboardHelper).copyString("before"); return 1;')
        menu_on(m, real_row)
        choose(m, "Copy address")
        copied = m.js(clipboard + 'await until(() => read() !== "before", 3000); return read();')
        check("in the real sidebar, a real right click opens the menu and its item copies the address", copied == "https://example.org/?smoke-menu-b", repr(copied))
    finally:
        # Nothing of this for the groups after it. The folders' tabs first, as they are saved.
        clear_rules()
        sidebar_page(m, """for (const f of [...doc.querySelectorAll("#tabs .folder .head")]) if (["Menu kept", "Example"].includes(f.querySelector(".title")?.textContent)) send({type: "deleteFolder", key: f.dataset.folderHead});
          await wait(800); return 1;""")
        m.js(MENU_TABS + """const all = await record(), keys = new Set(entriesOf(all, "smoke-menu").map(([k]) => JSON.stringify(k)));
          for (const w of wins()) for (const t of [...w.gBrowser.tabs]) if (keys.has(key(w, t)) || url(t).includes("smoke-menu")) w.gBrowser.removeTab(t, {skipPermitUnload: true});
          await wait(2000); return 1;""")
    no_problems(m, "after the tab menu")


def alone_new_tab(m):
    # New tabs have one place, the top of today's tabs, for the button, ⌘T and a link
    # from another app. Each tab's row is read from the real sidebar, once it has settled.
    settled = """const settled = async (test, ms = 10000) => { const t0 = Date.now(); for (;;) { const v = test(); if (v || Date.now() - t0 > ms) return v; await wait(50); } };"""
    rows = settled + """const ids = () => plainTabs().map(r => Number(r.dataset.tab));"""
    # Waits for a tab to be first among today's, with the others as they were. Every view the
    # sidebar is sent meanwhile is kept: a new row anywhere but first is a jump.
    new_first = rows + """const before = args[0], known = [...doc.querySelectorAll("#tabs > .tab")].map(r => Number(r.dataset.tab)), views = [];
      port.onMessage.addListener(v => views.push(v.tabs.map(t => t.id)));
      await settled(() => !before.includes(ids()[0]) && ids().length === before.length + 1);
      await wait(300);
      const top = plainTabs()[0];
      const jumped = views.filter(v => v.some(id => !known.includes(id)) && known.includes(v[0])).length;
      return {before, after: ids(), active: top.classList.contains("active"), above: top.previousElementSibling?.className, jumped};"""
    # Waits for tab `t` to be in the record and in the second window, and gives each window's order of its space.
    both_orders = """const w = main(), ctx = t.userContextId;
      const order = x => x.gBrowser.tabs.filter(y => !y.pinned && key(x, y) && y.userContextId === ctx).map(y => key(x, y));
      await settled(() => key(w, t) && order(other()).includes(key(w, t)));
      return {me: key(w, t), main: order(w), other: order(other()), ctx};"""
    opened = m.js(H + settled + """if (other()) return false;
      const a = main(), want = a.gBrowser.tabs.filter(t => !t.pinned && role(a, t)).length, w = a.OpenBrowserWindow(); w.__smoke = true;
      await settled(() => w.gBrowser && w.gBrowser.tabs.filter(t => !t.pinned && role(w, t)).length >= want, 20000);
      a.focus(); await wait(500); return true;""")
    more_tabs_here(m, "newtab")

    # The button, with a folder drawn above. (moveTab puts the folder's tab last in the window; the unit test has one before.)
    r = sidebar_page(m, rows + """
      send({type: "newFolder", space: spaces().find(s => s.active).id, name: "Above the new tabs"});
      const head = await settled(() => [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "Above the new tabs"));
      const moved = ids()[0];
      send({type: "moveTab", tabId: moved, folder: head.dataset.folderHead, before: null});
      await settled(() => head.parentElement.querySelector(".tab"));
      const before = ids();
      // On a tab of the list first: on an empty new tab of this space the button opens no second
      // one (newtabs.js), and a group before can leave the window on one.
      await page.browser.tabs.update(before[0], page.JSON.parse(JSON.stringify({active: true})));
      await settled(() => plainTabs()[0]?.classList.contains("active"));
      doc.getElementById("new-tab").click();
      await settled(() => ids().length === before.length + 1);
      const top = plainTabs()[0];
      return {folder: head.dataset.folderHead, moved, before, after: ids(), active: top.classList.contains("active"), above: top.previousElementSibling?.className};""")
    folder, in_folder = r["folder"], r.get("moved")
    check("the new tab button opens the tab first among today's tabs, under the folders, selected",
          r["after"][1:] == r["before"] and r["active"] and r["above"] == "divider", str(r))
    s = m.js(H + settled + """const t = main().gBrowser.selectedTab, was = key(main(), t);
      t.linkedBrowser.loadURI(Services.io.newURI("https://example.org/?smoke-newtab-button"), {triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()});
      """ + both_orders.replace("return {", "return {was, "))
    check("a new tab is not in the other window until it has an address", not s["was"], str(s))
    check("once it has one, the other window shows the same order", s["me"] and s["main"] == s["other"], str(s))

    # ⌘T, through Firefox's own key. The tab comes without a container, and is opened again here.
    before = sidebar_page(m, rows + "return ids();")
    m.js(H + "main().focus(); await wait(300); return 1;")
    press(m, "t", CMD)
    r = sidebar_page(m, new_first, before)
    t = m.js(H + "const t = main().gBrowser.selectedTab; return {ctx: t.userContextId, page: url(t)};")
    check("⌘T opens the tab first among today's tabs, in the space, selected",
          r["after"][1:] == r["before"] and r["active"] and t["ctx"] == s["ctx"], str((r, t)))

    # A link from another app: an address, without a container.
    before = r["after"]
    # (A moment from now, once the views are being kept. Its row must never show at the end. A link
    # is created on about:blank, and its address comes later: how much later is made sure here, or
    # the check would depend on how fast Firefox is.)
    m.js(H + """sT(() => { const t = main().gBrowser.addTrustedTab("about:blank", {inBackground: false});
      sT(() => t.linkedBrowser.loadURI(Services.io.newURI("https://example.org/?smoke-newtab-link"), {triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()}), 800); }, 3000); return 1;""")
    r = sidebar_page(m, new_first, before)
    check("a link without a container opens first among today's tabs, selected", r["after"][1:] == r["before"] and r["active"], str(r))
    check("its row never shows anywhere else first", r["jumped"] == 0, str(r))
    s = m.js(H + settled + "const t = main().gBrowser.tabs.find(x => url(x).includes('smoke-newtab-link'));" + both_orders)
    check("the other window has the link in the same place", s["me"] and s["main"] == s["other"], str(s))
    check("the link is in the space", s["ctx"] == t["ctx"], str(s))

    # A site that takes long to answer: the row shows after a while, in the same place, and stays there.
    before = r["after"]
    m.js(H + """sT(() => { const t = main().gBrowser.addTrustedTab("about:blank", {inBackground: false});
      sT(() => t.linkedBrowser.loadURI(Services.io.newURI("https://example.org/?smoke-newtab-slow"), {triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()}), 4500); }, 3000); return 1;""")
    r = sidebar_page(m, new_first, before)
    check("a link that takes long shows first among today's while it waits", r["after"][1:] == r["before"] and r["jumped"] == 0, str(r))
    r = sidebar_page(m, rows + """const waiting = args[0];
      await settled(() => ids()[0] !== waiting);
      return {waiting, after: ids(), active: plainTabs()[0].classList.contains("active")};""", r["after"][0])
    check("and is still first once the site answers", r["after"][1:] == before and r["active"], str(r))
    before = r["after"]

    # A link from a tab: Firefox puts it next to that tab, in its container, and there it stays, in both windows.
    s = m.js(H + settled + """const first = main(), space = first.gBrowser.selectedTab.userContextId;
      const from = first.gBrowser.tabs.filter(t => !t.pinned && t.userContextId === space && url(t).includes("smoke-newtab-") && !/-(link|button|slow)/.test(url(t)))[1];
      first.gBrowser.selectedTab = from; await settled(() => from.selected); await wait(300);
      const t = first.gBrowser.addTrustedTab("https://example.org/?smoke-newtab-from-tab", {relatedToCurrent: true, inBackground: true});
      """ + both_orders.replace("return {", "return {beside: first.gBrowser.tabs.indexOf(t) === first.gBrowser.tabs.indexOf(from) + 1, opener: key(first, from), "))
    check("a link opened from a tab stays next to it", s["beside"] and s["main"][s["main"].index(s["opener"]) + 1] == s["me"], str(s))
    check("and the other window has it there too", s["main"] == s["other"], str(s))

    # A link from a tab drawn apart has nothing to stay next to. Next to the folder's tab would be the end of
    # the list (moveTab puts it last in the window). A moment from now again, once the views are being kept.
    before = sidebar_page(m, rows + "return ids();")
    # (The folder's tab by its id: the last in the window, where moveTab put it, can be a tab another group left.)
    m.js(H + """const {ExtensionParent} = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
      const w = main(); w.gBrowser.selectedTab = ExtensionParent.apiManager.global.tabTracker.getTab(args[0]);
      sT(() => w.gBrowser.addTrustedTab("https://example.org/?smoke-newtab-from-folder", {relatedToCurrent: true, inBackground: true}), 3000); return 1;""", in_folder)
    r = sidebar_page(m, new_first, before)
    check("a link from a tab in a folder opens first among today's tabs", r["after"][1:] == r["before"], str(r))
    s = m.js(H + settled + "const t = main().gBrowser.tabs.find(x => url(x).includes('smoke-newtab-from-folder'));" + both_orders)
    check("and the other window has it there too (a folder's tab)", s["me"] and s["main"] == s["other"], str(s))
    before = r["after"]
    m.js(H + """const w = main(); w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => t.pinned && t.userContextId === args[0]);
      sT(() => w.gBrowser.addTrustedTab("https://example.org/?smoke-newtab-from-essential", {relatedToCurrent: true, inBackground: true}), 3000); return 1;""", s["ctx"])
    r = sidebar_page(m, new_first, before)
    check("a link from an essential opens first among today's tabs", r["after"][1:] == r["before"], str(r))

    # A double click on the empty part of the list; on a row it is only a click.
    r = sidebar_page(m, rows + """
      const fire = (e, type, detail) => e.dispatchEvent(new page.MouseEvent(type, {bubbles: true, cancelable: true, detail, button: 0}));
      const twice = (first, second = first) => {
        for (const [e, n] of [[first, 1], [second, 2]]) for (const type of ["mousedown", "mouseup", "click"]) fire(e, type, n);
        fire(second, "dblclick", 2);
      };
      const list = doc.getElementById("tabs"), before = ids().length;
      twice(plainTabs()[0]);
      await wait(1200);
      const onRow = ids().length;
      // The row under the pointer can go between the clicks (its ×): the second then lands on the empty part.
      twice(plainTabs()[1], list);
      await wait(1200);
      return {before, onRow, fromRow: ids().length};""")
    check("a double click on a row opens no tab", r["onRow"] == r["before"], str(r))
    check("a double click that began on a row opens no tab", r["fromRow"] == r["before"], str(r))
    # The empty part with Firefox's own mouse events, on the sidebar page in front. Two
    # clicks too far apart on a busy machine are no double click, so it may take another try.
    before = sidebar_page(m, rows + "return ids();")
    for _ in range(3):
        m.js(H + """const w = main(); w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes("/sidebar/sidebar.html")); await wait(500); return 1;""")
        into_page(m, "/sidebar/sidebar.html")
        # (A list longer than the sidebar has no empty part in view, so for the test it gets one at its end.)
        spot = m.cmd("WebDriver:ExecuteScript", {"args": [], "script": """const l = document.getElementById("tabs"), box = l.getBoundingClientRect(), x = Math.round(box.left + box.width / 2), y = Math.round(box.bottom - 4);
          if (l.lastElementChild.getBoundingClientRect().bottom + 16 > box.bottom) { l.style.paddingBottom = "24px"; l.scrollTop = l.scrollHeight; }
          return {x, y, empty: document.elementFromPoint(x, y) === l};"""})
        m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"}, "actions": [
            {"type": "pointerMove", "x": spot["x"], "y": spot["y"], "duration": 0},
            {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}, {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}]}]})
        m.cmd("WebDriver:ReleaseActions")
        m.chrome()
        r = sidebar_page(m, new_first, before)
        if r["after"][1:] == r["before"]:
            break
    sidebar_page(m, """doc.getElementById("tabs").style.paddingBottom = ""; return 1;""")
    check("a double click on the empty part of the list opens a tab first among today's, selected", spot["empty"] and r["after"][1:] == r["before"] and r["active"], str((spot, r)))

    # What this group added goes again. The tabs are live in this window, so the other follows.
    sidebar_page(m, """send({type: "deleteFolder", key: args[0]}); await wait(500); return 1;""", folder)
    r = m.js(H + settled + """const a = main(), ours = t => url(t).includes("smoke-newtab") || /^about:(newtab|home)/.test(url(t));
      for (const t of a.gBrowser.tabs.filter(t => !t.pinned && ours(t))) a.gBrowser.removeTab(t);
      await settled(() => !other().gBrowser.tabs.some(t => !t.pinned && String(t.label).includes("smoke-newtab")));
      await wait(2000);
      if (args[0]) await close(other());
      return 1;""", opened)
    no_problems(m, "after opening new tabs")


def alone_tab_names(m):
    # Real keys and clicks in the sidebar page, in front. renameKept is what the tab
    # menu's Rename calls; everything after that is what you do in the box.
    ENTER, ESC, BACKSPACE = "\ue007", "\ue00c", "\ue003"
    PAGE = "/sidebar/sidebar.html"
    # By the clock: a page in a background tab has its timers slowed to one a second or less.
    UNTIL = """const until = async (f, ms = 10000) => { for (const end = Date.now() + ms; Date.now() < end; await wait(50)) { const v = f(); if (v) return v; } return f(); };
      const row = id => doc.querySelector(`#tabs .tab[data-tab="${id}"]`), tile = id => doc.querySelector(`#essentials .tile[data-tab="${id}"]`);
      const nameOf = id => row(id)?.querySelector(".title")?.textContent;
      const tip = e => e?.title.split("\\n")[0];
      const box = () => doc.querySelector("input.rename");
      const state = () => ({open: !!box(), value: box()?.value ?? null, focused: !!box() && doc.activeElement === box(), caret: box()?.selectionStart ?? null});"""

    def keys(*texts):
        acts = [a for text in texts for ch in text for a in ({"type": "keyDown", "value": ch}, {"type": "keyUp", "value": ch})]
        m.cmd("WebDriver:PerformActions", {"actions": [{"type": "key", "id": "kb", "actions": acts}]})
        m.cmd("WebDriver:ReleaseActions")

    def click(x, y):
        m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"}, "actions": [
            {"type": "pointerMove", "x": int(x), "y": int(y), "duration": 0, "origin": "viewport"},
            {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}]}]})
        m.cmd("WebDriver:ReleaseActions")

    def in_front(script, *args):
        """Run `script` in the sidebar page, which stays in the content context for keys() and click()."""
        return m.cmd("WebDriver:ExecuteAsyncScript", {"script": """
          const args = [...arguments], done = args.pop(), wait = ms => new Promise(r => setTimeout(r, ms));
          const page = window.wrappedJSObject || window, doc = page.document;
          """ + UNTIL + """
          (async () => { """ + script + """ })().then(r => done(JSON.parse(JSON.stringify(r ?? null))), e => done({error: String(e)}));""", "args": list(args)})

    def switch_to(text):
        """To the tab with `text` in its address, once it is there."""
        for _ in range(100):
            try:
                return into_page(m, text)
            except RuntimeError as e:
                if "no tab with" not in str(e) and "no such window" not in str(e):
                    raise
            time.sleep(0.1)
        raise RuntimeError(f"no tab with {text}")

    def front():
        m.js(H + """const w = main(), t = w.gBrowser.tabs.find(x => url(x).includes(args[0])); w.focus();
          if (w.gBrowser.selectedTab !== t) { w.__beforeNames ??= w.gBrowser.selectedTab; w.gBrowser.selectedTab = t; await wait(500); }
          return 1;""", PAGE)
        switch_to(PAGE)

    def behind(body, *args):
        """Something that happens beside the open box, from the browser's side, while the page keeps its focus."""
        m.chrome()
        out = m.js(H + body, *args)
        front()
        return out

    # Firefox's notice that an extension hides tabs opens at every hide until you keep them hidden,
    # and takes the focus, which closes an open box. A person answers it once; so does this.
    m.js(H + """const {ExtensionSettingsStore} = ChromeUtils.importESModule("resource://gre/modules/ExtensionSettingsStore.sys.mjs");
      await ExtensionSettingsStore.initialize();
      await ExtensionSettingsStore.addSetting(args[0], "tabHideNotification", args[0], true, () => false);
      for (const w of wins()) for (const p of w.document.querySelectorAll("panel")) if (p.state === "open") p.hidePopup();
      await wait(300); return 1;""", EXT_ID)

    # Two folders, the first only to go away while the box is open, two saved tabs, and a second window.
    more_tabs_here(m, "names")
    setup = sidebar_page(m, UNTIL + """
      const space = spaces().find(s => s.active).id;
      for (const name of ["Above", "Names"]) { send({type: "newFolder", space, name}); await until(() => folders().some(f => f.name === name)); }
      const heads = [...doc.querySelectorAll("#tabs .folder .head")];
      const headOf = name => heads.find(h => h.querySelector(".title").textContent === name).dataset.folderHead;
      // Its own tabs: the first row can be any page, such as a settings page with no record,
      // which can be neither saved nor named, once earlier groups have closed what came before it.
      const mine = new Set(Array.from(await page.browser.tabs.query({})).filter(t => t.url.includes("smoke-names-")).map(t => t.id));
      const tabs = plainTabs().map(x => Number(x.dataset.tab)).filter(id => mine.has(id));
      send({type: "moveTab", tabId: tabs[0], folder: headOf("Names"), before: null});
      await until(() => row(tabs[0])?.dataset.folder);
      const tileEl = doc.querySelector("#essentials .tile");
      return {space, above: headOf("Above"), names: headOf("Names"), saved: tabs[0], plain: tabs[1], tile: Number(tileEl.dataset.tab), tileTitle: tip(tileEl), page: nameOf(tabs[0])};""")
    check("names: a folder with a saved tab to name", setup.get("saved") and setup.get("page") and setup.get("tile"), str(setup))
    m.js(H + """if (!other()) { const w = main().OpenBrowserWindow(); w.__smoke = true; await wait(4000); } return 1;""")
    saved, tile_id, page_title = setup["saved"], setup["tile"], setup["page"]
    front()
    try:
        # Only what is kept, and only from the menu: an ordinary tab opens no box, and a double click neither.
        r = in_front("""
          page.renameKept(args[0]);
          const plain = !!box();
          row(args[1]).dispatchEvent(new page.MouseEvent("dblclick", {bubbles: true}));
          return {plain, dbl: !!box()};""", setup["plain"], saved)
        check("an ordinary tab gets no box, and a double click on a saved tab opens none", r == {"plain": False, "dbl": False}, str(r))

        # A folder made while Firefox's note about hidden tabs has the keyboard keeps its name: its
        # box would get the keyboard back only once the note goes, with the name still all selected,
        # and the last letters typed meanwhile would become the name (once "re"). With the keyboard
        # here, New folder opens its box as ever.
        def new_folder():
            return in_front("""const heads = () => [...doc.querySelectorAll("#tabs .folder .head")], known = new Set(heads().map(h => h.dataset.folderHead));
              const focus = doc.hasFocus();
              doc.getElementById("new-folder").click();
              const head = await until(() => heads().find(h => !known.has(h.dataset.folderHead)));
              await wait(500);
              const out = {focus, open: !!box(), name: head?.querySelector(".title")?.textContent ?? null};
              box()?.blur(); // which keeps "New folder"
              await wait(300);
              page.folderMenu(head.dataset.folderHead, false).find(i => i?.[0]?.startsWith("Delete"))[1]();
              await until(() => !heads().includes(head));
              return out;""")
        with_keys = new_folder()
        behind("""const {ExtensionSettingsStore} = ChromeUtils.importESModule("resource://gre/modules/ExtensionSettingsStore.sys.mjs");
          await ExtensionSettingsStore.initialize(); await ExtensionSettingsStore.removeSetting(args[0], "tabHideNotification", args[0]); return 1;""", EXT_ID)
        in_front("""await page.browser.tabs.hide([args[0]]); await until(() => !doc.hasFocus(), 3000); return 1;""", setup["plain"])
        away = new_folder()
        behind("""const {ExtensionSettingsStore} = ChromeUtils.importESModule("resource://gre/modules/ExtensionSettingsStore.sys.mjs");
          const note = main().document.getElementById("extension-notification-panel"), was = note?.state;
          note?.hidePopup?.();
          await ExtensionSettingsStore.addSetting(args[0], "tabHideNotification", args[0], true, () => false); await wait(300); return was;""", EXT_ID)
        in_front("""await page.browser.tabs.show([args[0]]); return 1;""", setup["plain"])
        check("New folder opens its box when the sidebar has the keyboard, and not while Firefox's note about hidden tabs has it",
              with_keys.get("focus") and with_keys.get("open") and away.get("focus") is False and away.get("open") is False and away.get("name") == "New folder", f"{with_keys}, {away}")

        # A menu item opens the box from inside a real click, which must not take the focus back.
        # Enter on a box you did not change names nothing, or the title would stop following its page.
        at = in_front("""const line = doc.getElementById("space-name"), b = line.getBoundingClientRect();
          line.addEventListener("click", () => page.renameKept(args[0]), {once: true});
          return {x: b.left + b.width / 2, y: b.top + b.height / 2};""", saved)
        click(at["x"], at["y"])
        r = in_front("return state();")
        check("a box opened by a real click has the focus", r.get("open") and r.get("focused"), str(r))
        keys(ENTER)
        r = in_front("await until(() => !box()); await wait(500); return {open: !!box(), name: nameOf(args[0])};", saved)
        m.chrome()
        named = m.js(H + """return Object.values((await storage("%s", ["syncedTabs"])).syncedTabs).filter(e => !e.group && e.name).length;""" % EXT_ID)
        front()
        check("Enter on an unchanged box names nothing", r == {"open": False, "name": page_title} and named == 0, f"{r}, {named}")

        # A saved tab: the box is in its row, the title selected, and nothing moves.
        r = in_front("""
          const was = row(args[0]).getBoundingClientRect().height;
          page.renameKept(args[0]);
          return {...state(), selected: box().selectionEnd - box().selectionStart, inRow: row(args[0]).contains(box()), same: row(args[0]).getBoundingClientRect().height === was};""", saved)
        check("a saved tab's box opens in its row, with its title selected", r.get("focused") and r.get("inRow") and r.get("same") and r.get("value") == page_title and r.get("selected") == len(page_title), str(r))
        keys("Sprint")

        # What happens elsewhere must not touch the box: a new tab, and a folder above it removed
        # (drawing that moves everything below it, which silently takes the focus away).
        behind("""const w = main(), space = w.gBrowser.tabs.find(t => t.userContextId && !t.hidden && !t.pinned).userContextId;
          w.gBrowser.addTrustedTab("https://example.org/?smoke-names-beside", {userContextId: space, inBackground: true}); await wait(2500); return 1;""")
        r = in_front("return state();")
        check("a view that changes nothing here leaves the open box alone", r.get("open") and r.get("focused") and r.get("value") == "Sprint" and r.get("caret") == 6, str(r))

        side = in_front("""
          const port = page.browser.runtime.connect({name: "sidebar"});
          const send = msg => port.postMessage(page.JSON.parse(JSON.stringify(msg)));
          send({type: "hello", windowId: (await page.browser.windows.getCurrent()).id});
          await wait(100);
          send({type: "deleteFolder", key: args[0]});
          await until(() => ![...doc.querySelectorAll("#tabs .folder .head .title")].some(t => t.textContent === "Above"));
          await wait(300);
          const gone = state();
          // And its own folder moving, with the row in it: it has to be moved, and gets the focus back.
          send({type: "newFolder", space: page.document.documentElement.dataset.space, name: "Last"});
          await until(() => [...doc.querySelectorAll("#tabs .folder .head .title")].some(t => t.textContent === "Last"));
          await wait(300);
          send({type: "moveFolder", key: args[1], before: null});
          await until(() => [...doc.querySelectorAll("#tabs .folder")].at(-1).dataset.key === args[1]);
          await wait(300);
          port.disconnect();
          return {gone, moved: state()};""", setup["above"], setup["names"])
        check("a folder above removed leaves the open box alone", side.get("gone", {}).get("open") and side["gone"]["focused"] and side["gone"]["value"] == "Sprint" and side["gone"]["caret"] == 6, str(side))
        check("its own folder moved: the box stays open, with the focus", side.get("moved", {}).get("open") and side["moved"]["focused"] and side["moved"]["value"] == "Sprint", str(side))
        keys(" board", ENTER)
        r = in_front("""await until(() => !box() && tip(row(args[0])) === "Sprint board");
          return {name: nameOf(args[0]), tip: tip(row(args[0])), open: !!box(), renaming: row(args[0]).classList.contains("renaming"), draggable: row(args[0]).draggable, close: !!row(args[0]).querySelector(".close")};""", saved)
        check("Enter saves a saved tab's name, typed with real keys", r == {"name": "Sprint board", "tip": "Sprint board", "open": False, "renaming": False, "draggable": True, "close": True}, str(r))
        m.chrome()
        r = m.js(H + """const named = async () => Object.entries((await storage("%s", ["syncedTabs"])).syncedTabs).find(([, e]) => e.name === "Sprint board")?.[0];
          let k = await named(); for (let i = 0; i < 100 && !k; i++) { await wait(100); k = await named(); }
          const there = () => other().gBrowser.tabs.find(x => key(other(), x) === JSON.stringify(k));
          for (let i = 0; i < 100 && (there()?.label !== "Sprint board" || there()?.linkedPanel); i++) await wait(100);
          const e = (await storage("%s", ["syncedTabs"])).syncedTabs[k];
          return {k, label: there()?.label, loaded: !!there()?.linkedPanel, title: e?.title, name: e?.name};""" % (EXT_ID, EXT_ID))
        check("the name is kept apart from the page's title, and the other window's placeholder takes it and unloads again", r.get("name") == "Sprint board" and r.get("title") == page_title and r.get("label") == "Sprint board" and r.get("loaded") is False, str(r))
        front()

        # Esc cancels; leaving the box saves; empty brings back the page's title.
        in_front("page.renameKept(args[0]); return 1;", saved)
        keys("Not this", ESC)
        r = in_front("""await until(() => !box()); await wait(300); return {name: nameOf(args[0]), open: !!box()};""", saved)
        check("Esc cancels", r == {"name": "Sprint board", "open": False}, str(r))
        in_front("page.renameKept(args[0]); return 1;", saved)
        keys("Elsewhere")
        at = in_front("""const b = doc.getElementById("space-name").getBoundingClientRect(); return {x: b.left + b.width / 2, y: b.top + b.height / 2};""")
        click(at["x"], at["y"])
        r = in_front("""await until(() => !box() && nameOf(args[0]) === "Elsewhere"); return {name: nameOf(args[0]), open: !!box()};""", saved)
        check("a real click elsewhere saves", r == {"name": "Elsewhere", "open": False}, str(r))
        in_front("page.renameKept(args[0]); return 1;", saved)
        keys(BACKSPACE, ENTER)
        r = in_front("""await until(() => !box() && nameOf(args[0]) === args[1]); return nameOf(args[0]);""", saved, page_title)
        check("an empty box brings back the page's title", r == page_title, str(r))

        # What starts in the box stays there. Text dragged in it (all of it is selected at first) is not its
        # row: a drop on the list would take the tab out of its folder, and its name with it. A folder's box is
        # the same. Headless Firefox starts no drag of its own for a real pointer, so these events are made here.
        # While an input method composes, Enter and Esc are its own.
        drag_in_box = """const dragInBox = over_what => { const data = new page.DataTransfer();
            box().dispatchEvent(new page.DragEvent("dragstart", {bubbles: true, cancelable: true, dataTransfer: data}));
            const over = new page.DragEvent("dragover", {bubbles: true, cancelable: true, dataTransfer: data, clientX: 5, clientY: 5});
            over_what.dispatchEvent(over);
            page.dispatchEvent(new page.DragEvent("dragend", {bubbles: true}));
            return over.defaultPrevented; };"""
        r = in_front(drag_in_box + """
          page.renameKept(args[0]);
          const droppable = dragInBox(doc.getElementById("tabs"));
          for (const key of ["Enter", "Escape"]) box().dispatchEvent(new page.KeyboardEvent("keydown", {key, isComposing: true, bubbles: true}));
          return {droppable, ...state()};""", saved)
        check("text dragged in the box does not pick up its row, and Enter or Esc while composing leave the box open", r.get("droppable") is False and r.get("open") and r.get("focused"), str(r))
        keys(ESC)
        r = in_front(drag_in_box + """await until(() => !box());
          page.rename(args[0]);
          const other = [...doc.querySelectorAll("#tabs .folder")].find(f => f.dataset.key !== args[0]);
          return {droppable: dragInBox(other.querySelector(".head")), open: !!box()};""", setup["names"])
        check("nor in a folder's box", r == {"droppable": False, "open": True}, str(r))
        # And a folder's box keeps the focus when its folder is moved, as a tab's does.
        r = in_front("""
          const port = page.browser.runtime.connect({name: "sidebar"});
          port.postMessage(page.JSON.parse(JSON.stringify({type: "hello", windowId: (await page.browser.windows.getCurrent()).id})));
          await wait(100);
          const keysNow = () => [...doc.querySelectorAll("#tabs .folder")].map(f => f.dataset.key);
          const other = keysNow().find(k => k !== args[0]);
          port.postMessage(page.JSON.parse(JSON.stringify({type: "moveFolder", key: args[0], before: other})));
          await until(() => keysNow()[0] === args[0]);
          await wait(300);
          port.disconnect();
          return state();""", setup["names"])
        check("a folder's box moved with its folder keeps the focus", r.get("open") and r.get("focused"), str(r))
        keys(ESC)
        in_front("await until(() => !box()); return 1;")

        # A tile: the line with the space's name becomes the box, at its height, and the list stays where it was.
        r = in_front("""
          const line = doc.getElementById("space-name"), top = doc.getElementById("tabs").getBoundingClientRect().top, left = line.getBoundingClientRect().left;
          const text = line.textContent;
          page.renameKept(args[0]);
          // Where the text starts, in the line and in the box: the same place, whatever the box's own edge.
          const b = box()?.getBoundingClientRect(), inset = e => { const c = page.getComputedStyle(e); return parseFloat(c.paddingLeft) + parseFloat(c.borderLeftWidth); };
          return {...state(), id: box()?.id, marked: tile(args[0]).classList.contains("renaming"), shifted: doc.getElementById("tabs").getBoundingClientRect().top - top, lineHidden: line.hidden, text,
                  boxText: b && b.left + inset(box()), lineText: left + inset(line)};""", tile_id)
        check("a tile's box takes the space name's line, and the list stays where it was", r.get("focused") and r.get("id") == "name-box" and r.get("marked") and r.get("shifted") == 0 and r.get("lineHidden") and r.get("value") == setup["tileTitle"] and r.get("boxText") == r.get("lineText"), str(r))
        keys("Ji")
        behind("""const w = main(), space = w.gBrowser.tabs.find(t => t.userContextId && !t.hidden && !t.pinned).userContextId;
          w.gBrowser.addTrustedTab("https://example.org/?smoke-names-beside-2", {userContextId: space, inBackground: true}); await wait(2500); return 1;""")
        r = in_front("""return {...state(), line: doc.getElementById("space-name").hidden, boxes: doc.querySelectorAll("input.rename").length};""")
        check("a view does not disturb a tile's box", r.get("open") and r.get("focused") and r.get("value") == "Ji" and r.get("line") and r.get("boxes") == 1, str(r))
        keys("ra", ENTER)
        r = in_front("""await until(() => !box() && tip(tile(args[0])) === "Jira");
          return {tip: tip(tile(args[0])), open: !!box(), line: doc.getElementById("space-name").hidden, text: doc.getElementById("space-name").textContent, marked: tile(args[0]).classList.contains("renaming")};""", tile_id)
        check("Enter saves a tile's name, shown as its tooltip, and the space's name is back", r.get("tip") == "Jira" and not r.get("open") and not r.get("line") and r.get("text") and not r.get("marked"), str(r))
        m.chrome()

        # Every window: the second window's real sidebar, read through the extension's own views, and
        # its placeholder. It may be in another space, whose essentials are others; then to this one and
        # back. (Not the window you are using, so that selects a placeholder without pulling its tab in.)
        m.js(H + """const S = other().SidebarController;
          if (!S.isOpen) await S.show("_6844a953-9931-4334-9ff6-257c246485cb_-sidebar-action");
          await wait(800); return 1;""")
        front()
        r = in_front("""const here = (await page.browser.windows.getCurrent()).id;
          const there = (await page.browser.windows.getAll({windowTypes: ["normal"]})).find(w => w.id !== here).id;
          const [view] = page.browser.extension.getViews({type: "sidebar", windowId: there});
          const second = (view.wrappedJSObject || view).document;
          const names = () => [...second.querySelectorAll("#essentials .tile")].map(tip);
          const button = id => second.querySelector(`#spaces .space[data-space="${id}"]`);
          const was = await until(() => second.documentElement.dataset.space);
          if (was !== args[0]) button(args[0]).click();
          await until(() => names().includes("Jira"));
          const seen = names();
          if (was !== args[0]) button(was).click();
          await until(() => second.documentElement.dataset.space === was);
          return seen;""", setup["space"])
        check("a second window's sidebar shows the same name", "Jira" in (r or []), str(r))
        m.chrome()
        r = m.js(H + """const list = (await storage("%s", ["essentials"])).essentials, e = list.find(x => x.name === "Jira");
          const there = () => other().gBrowser.tabs.find(t => t.pinned && ek(other(), t) === e?.key);
          for (let i = 0; i < 100 && (there()?.label !== "Jira" || there()?.linkedPanel); i++) await wait(100);
          return {name: e?.name, title: e?.title, label: there()?.label, loaded: !!there()?.linkedPanel};""" % EXT_ID)
        check("an essential's name is in its list entry, and its placeholder in the other window takes it and unloads again", r.get("name") == "Jira" and r.get("label") == "Jira" and r.get("loaded") is False, str(r))
        front()
        in_front("page.renameKept(args[0]); return 1;", tile_id)
        keys(BACKSPACE, ENTER)
        r = in_front("""await until(() => !box() && tip(tile(args[0])) !== "Jira"); return tip(tile(args[0]));""", tile_id)
        check("an empty box brings back an essential's title", r == setup["tileTitle"], str(r))

        # What is being named goes away without the box losing the focus: an essential unpinned
        # from another window, or (in a real sidebar, which stays in front) a space left by a key.
        # A box left open here would be a line that never comes back.
        r = in_front("""
          const port = page.browser.runtime.connect({name: "sidebar"});
          page.__names = {port, send: msg => port.postMessage(page.JSON.parse(JSON.stringify(msg)))};
          page.__names.send({type: "hello", windowId: (await page.browser.windows.getCurrent()).id});
          await wait(100);
          page.__names.send({type: "pin", tabId: args[0], pinned: true});
          return !!(await until(() => tile(args[0])));""", setup["plain"])
        check("names: another essential to lose", r is True, str(r))
        in_front("page.renameKept(args[0]); return 1;", setup["plain"])
        keys("Typed")
        r = in_front("""
          page.__names.send({type: "pin", tabId: args[0], pinned: false});
          await until(() => !tile(args[0]) && !box());
          const out = {open: !!box(), line: doc.getElementById("space-name").hidden};
          await until(() => row(args[0])?.title && tip(row(args[0])) !== "Typed", 5000);
          page.__names.port.disconnect();
          return {...out, tip: tip(row(args[0]))};""", setup["plain"])
        check("what is being named goes away: the box closes, and an ordinary tab has no name", r.get("open") is False and r.get("line") is False and r.get("tip") and r.get("tip") != "Typed", str(r))

        # The same in the real sidebar, which a page in a tab cannot stand in for: the page beside it can
        # take the focus, and a key can take its space away. Its contents can be read through the extension's
        # own views. Tidier's menu is another file's; here a real click on the name line stands in for its item.
        m.chrome()
        panel = lambda script, *args: sidebar_page(m, """
          const [view] = page.browser.extension.getViews({type: "sidebar", windowId: (await page.browser.windows.getCurrent()).id});
          const side = view.wrappedJSObject || view;
          return await (async doc => { """ + UNTIL + script + """ })(side.document);""", *args)
        base = m.js(H + """const w = main(); w.focus(); await wait(300);
          for (const p of w.document.querySelectorAll("panel, menupopup")) if (p.state === "open") p.hidePopup();
          await wait(300); const r = w.SidebarController.browser.getBoundingClientRect(); return {x: r.left, y: r.top, right: r.right};""")

        def open_in_panel(tab):
            at = panel("""const line = doc.getElementById("space-name"), b = line.getBoundingClientRect();
              line.addEventListener("click", () => side.renameKept(args[0]), {once: true});
              return {x: b.left + b.width / 2, y: b.top + b.height / 2};""", tab)
            click(base["x"] + at["x"], base["y"] + at["y"])

        def press_in_box_release_on_icon(button):
            at = panel("""const b = box().getBoundingClientRect(), i = row(args[0]).querySelector("img, .letter").getBoundingClientRect();
              return {x0: b.left + 20, y0: b.top + b.height / 2, x1: i.left + 4, y1: i.top + i.height / 2};""", saved)
            m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"}, "actions": [
                {"type": "pointerMove", "x": int(base["x"] + at["x0"]), "y": int(base["y"] + at["y0"]), "duration": 0, "origin": "viewport"}, {"type": "pointerDown", "button": button},
                {"type": "pointerMove", "x": int(base["x"] + at["x1"]), "y": int(base["y"] + at["y1"]), "duration": 50, "origin": "viewport"}, {"type": "pointerUp", "button": button}]}]})
            m.cmd("WebDriver:ReleaseActions")

        open_in_panel(saved)
        r = panel("return {...state(), document: doc.hasFocus()};")
        check("in the real sidebar, a real click opens the box, and the focus is really in it", r.get("focused") and r.get("document"), str(r))
        keys("In the panel", ENTER)
        r = panel("""await until(() => !box() && tip(row(args[0])) === "In the panel"); return {open: !!box(), tip: tip(row(args[0]))};""", saved)
        check("in the real sidebar, real keys type the name and Enter saves it", r == {"open": False, "tip": "In the panel"}, str(r))

        # A press in the box and a release beside it, on its row: a middle click there would close the tab.
        selected = """const w = main(); return w.gBrowser.selectedTab.linkedPanel;"""
        before = m.js(H + selected)
        open_in_panel(saved)
        press_in_box_release_on_icon(1)
        press_in_box_release_on_icon(0)
        r = panel("""await wait(500); return {...state(), there: !!row(args[0])};""", saved)
        check("in the real sidebar, a press in the box and a release on its row neither close nor select the tab", r.get("open") and r.get("there") and r.get("focused") and m.js(H + selected) == before, str(r))

        # The page beside it takes the focus: what was typed is saved, and the box is gone.
        panel("box().select(); return 1;")
        keys("Left for the page")
        # A spot in the page with nothing to it (the page beside is Tidier's sidebar page in a
        # tab): its space's name line, near the top and so in view however long the list is.
        free = sidebar_page(m, """const line = doc.getElementById("space-name"), b = line.getBoundingClientRect(), y = Math.round(b.top + b.height / 2);
          return !line.hidden && b.height && doc.elementFromPoint(300, y) === line ? y : null;""")
        check("in the real sidebar, the page beside has a spot with nothing on it to click", free is not None, str(free))
        click(base["right"] + 300, base["y"] + free)
        r = panel("""await until(() => !box() && tip(row(args[0])) === "Left for the page"); return {open: !!box(), tip: tip(row(args[0]))};""", saved)
        check("in the real sidebar, a real click in the page saves what was typed", r == {"open": False, "tip": "Left for the page"}, str(r))

        # A space left by a real key closes a tile's box, whose line would otherwise never come back.
        m.js(H + """main().focus(); await wait(200); return 1;""")
        open_in_panel(tile_id)
        keys("Short")
        at = panel("""return {index: [...doc.querySelectorAll("#spaces .space")].findIndex(s => s.classList.contains("active")), name: doc.getElementById("space-name").textContent, ...state()};""")
        press(m, "2" if at["index"] == 0 else "1", CTRL)
        r = panel("""await until(() => !box()); await until(() => doc.getElementById("space-name").textContent !== args[0]);
          return {open: !!box(), hidden: doc.getElementById("space-name").hidden, text: doc.getElementById("space-name").textContent};""", at["name"])
        check("in the real sidebar, a space left by a key closes a tile's box and its line is back", r.get("open") is False and r.get("hidden") is False and r.get("text") and r.get("text") != at["name"], str(r))
        press(m, str(at["index"] + 1), CTRL)
        r = panel("""await until(() => tip(tile(args[0])) === "Short"); const out = tip(tile(args[0]));
          send({type: "renameTab", tabId: args[0], name: ""}); await until(() => tip(tile(args[0])) !== "Short"); return out;""", tile_id)
        check("what was typed before the space was left is saved", r == "Short", str(r))
        r = m.js(H + """const loaded = () => other().gBrowser.tabs.filter(t => !t.selected && url(t).includes("ghost.html") && t.linkedPanel).map(t => t.label);
          for (let i = 0; i < 150 && loaded().length; i++) await wait(100);
          return loaded();""")
        check("all this naming left no placeholder loaded in the second window", r == [], str(r))
    finally:
        m.chrome()
        m.js(H + """const w = main(); if (w.__beforeNames && !w.__beforeNames.closing) w.gBrowser.selectedTab = w.__beforeNames; delete w.__beforeNames; await wait(500); return 1;""")
    sidebar_page(m, """const heads = [...doc.querySelectorAll("#tabs .folder")].filter(f => ["Names", "Last", "Above"].includes(f.querySelector(".head .title").textContent));
      for (const f of heads) send({type: "deleteFolder", key: f.dataset.key});
      await wait(4500);""")  # a tab that lost its name tells its placeholders a moment later (refreshGhostsSoon)


def alone_more(m):
    # More in a tab's, a folder's and a space's menu, the keys of the selection, and a dragged
    # tab held over a closed folder or another space (listactions.js, sidebar/moremenu.js), in
    # the real sidebar page with real events. What each does in detail is in the unit tests.
    space = sidebar_page(m, "return spaces().find(s => s.active).id;")
    ctx = int(space.split("-")[-1])
    other = next(s["id"] for s in sidebar_page(m, "return spaces();") if s["id"] != space and s["id"] != "firefox-container-4")

    def open_tab(name):
        return m.js(MENU_TABS + """const w = main(), t = w.gBrowser.addTrustedTab(args[0], {userContextId: args[1], inBackground: true});
          await until(() => role(w, t) === "live" && t.linkedPanel); return idOf(t);""", f"https://example.org/?smoke-more-{name}", ctx)

    def now_id(name):
        """Its row's id now: a tab brought back by Undo is a new tab."""
        return m.js(MENU_TABS + """const t = main().gBrowser.tabs.find(t => !t.pinned && url(t).includes("smoke-more-" + args[0])); return t ? idOf(t) : null;""", name)

    def record_of(name):
        return m.js(MENU_TABS + """const all = await record(); const [k, e] = entriesOf(all, "smoke-more-" + args[0])[0] ?? [];
          return e ? {key: k, space: e.cookieStoreId, folder: e.parentKey, saved: !!e.saved} : null;""", name)

    f1, f2, f3 = open_tab("f1"), open_tab("f2"), open_tab("f3")
    t1, t2, t3 = open_tab("t1"), open_tab("t2"), open_tab("t3")
    try:
        # A folder of three saved tabs, named so that a sort by name has something to do.
        r = sidebar_page(m, MENU_PAGE + """
          send({type: "newFolder", space: args[0], name: "More test"});
          const head = () => [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "More test");
          await until(() => head());
          for (const id of args.slice(1)) send({type: "moveTab", tabId: id, folder: head().dataset.folderHead, before: null});
          await until(() => head().parentElement.querySelectorAll(".tab").length === 3);
          for (const [id, name] of [[args[1], "Charlie"], [args[2], "Alpha"], [args[3], "Bravo"]]) send({type: "renameTab", tabId: id, name});
          await until(() => folders().find(f => f.name === "More test")?.tabs.join() === "Charlie,Alpha,Bravo");
          const labels = await rightClick(head());
          const more = shown().at(-1);
          choose("More");
          const inMore = shown();
          choose("Sort this folder");
          const sortBy = shown();
          choose("By name");
          await until(() => folders().find(f => f.name === "More test")?.tabs.join() === "Alpha,Bravo,Charlie");
          const sorted = folders().find(f => f.name === "More test").tabs;
          const line = await until(() => doc.querySelector("#note .text")?.textContent === "Sorted by name" && doc.querySelector("#note .text").textContent);
          doc.querySelector("#note .act").click();
          await until(() => folders().find(f => f.name === "More test")?.tabs.join() === "Charlie,Alpha,Bravo");
          return {labels, more, inMore, sortBy, sorted, line, back: folders().find(f => f.name === "More test").tabs, key: head().dataset.folderHead};""", space, f1, f2, f3)
        folder = r.get("key")
        check("a folder's menu has New tab here and More at its end", r.get("labels", [])[:1] == ["New tab here"] and r.get("more") == "More", str(r))
        check("More opens in place, with a row back, and a list in it does too",
              (r.get("inMore") or [None])[0] == "More" and "Copy addresses" in r.get("inMore", []) and "Close all its tabs" in r.get("inMore", [])
              and r.get("sortBy") == ["Sort this folder", "|", "By name", "By site", "By last use"], str(r))
        check("Sort by name sorts the folder, says so, and Undo puts it back", r.get("sorted") == ["Alpha", "Bravo", "Charlie"] and r.get("line") == "Sorted by name" and r.get("back") == ["Charlie", "Alpha", "Bravo"], str(r))

        # The tab menu's More: close the tabs below one, and take them back.
        r = sidebar_page(m, MENU_PAGE + """
          await until(() => rowOf(args[0]) && rowOf(args[2]));
          const today = () => [...doc.querySelectorAll("#tabs > .tab")].map(t => Number(t.dataset.tab));
          const below = today().slice(today().indexOf(args[0]) + 1);
          const labels = await rightClick(rowOf(args[0]));
          choose("More");
          const inMore = shown();
          choose("Close tabs below");
          await until(() => below.every(id => !rowOf(id)));
          const gone = below.filter(id => !rowOf(id)).length;
          const line = await until(() => doc.querySelector("#note .text")?.textContent);
          doc.querySelector("#note .act").click();
          await until(() => today().length === below.length + today().indexOf(args[0]) + 1, 15000);
          await wait(500);
          return {last: labels.at(-1), inMore, below: below.length, gone, line, back: today().slice(today().indexOf(args[0]) + 1).length};""", t1, t2, t3)
        check("a row's menu ends with More, which offers what applies to it", r.get("last") == "More" and "Close tabs below" in r.get("inMore", []) and "Sort today's tabs" in r.get("inMore", []) and "Copy as Markdown link" in r.get("inMore", []), str(r))
        check("Close tabs below closes them, with one line, and Undo brings them back", r.get("below", 0) >= 2 and r.get("gone") == r.get("below") and r.get("line") == f"{r.get('below')} tabs closed" and r.get("back") == r.get("below"), str(r))

        # A duplicate, from the space's menu.
        dupe = m.js(MENU_TABS + """const w = main(), t = w.gBrowser.addTrustedTab("https://example.org/?smoke-more-t1", {userContextId: args[0], inBackground: true});
          await until(() => role(w, t) === "live"); await wait(500); return idOf(t);""", ctx)
        r = sidebar_page(m, MENU_PAGE + """
          await until(() => rowOf(args[0]));
          await rightClick(doc.getElementById("space-name"));
          choose("More");
          const inMore = shown(), item = inMore.find(x => /^Close \\d+ duplicates?$/.test(x));
          if (item) choose(item);
          await until(() => !rowOf(args[0]));
          const out = {inMore, item, gone: !rowOf(args[0]), kept: !!doc.querySelector(`[data-tab="${args[1]}"]`)};
          // Others' duplicates may have gone with it: they come back, for the groups after this one.
          (await until(() => doc.querySelector("#note .act")))?.click();
          await wait(1500);
          return out;""", dupe, t1)
        check("a space's More closes today's duplicates, and the first stays", bool(r.get("item")) and r.get("gone") and r.get("kept") and "Reload this space" in r.get("inMore", []), str(r))

        # All the folders of the space at once, from the same More: closed while any is open,
        # and then opened. And the other spaces unloaded, which leaves this one as it is.
        away = m.js(MENU_TABS + """const w = main(), here = w.gBrowser.selectedTab.userContextId;
          const ctx = [...new Set(w.gBrowser.tabs.map(t => t.userContextId))].find(c => c && c !== here);
          if (!ctx) return null;
          const t = w.gBrowser.addTrustedTab("https://example.org/?smoke-more-away", {userContextId: ctx, inBackground: true});
          await until(() => role(w, t) === "live" && t.linkedPanel); await wait(500); return idOf(t);""")
        r = sidebar_page(m, MENU_PAGE + """
          const space = doc.documentElement.dataset.space, name = f => f.querySelector(".head .title").textContent;
          const all = () => [...doc.querySelectorAll("#tabs .folder")], mine = () => all().filter(f => /^More (one|two)$/.test(name(f)));
          for (const n of ["More one", "More two"]) { send({type: "newFolder", space, name: n}); await until(() => all().some(f => name(f) === n)); }
          const closed = () => all().map(f => f.classList.contains("collapsed"));
          const more = async () => { await rightClick(doc.getElementById("space-name")); choose("More"); return shown(); };
          const out = {offered: [], states: []};
          for (let i = 0; i < 2; i++) {
            const label = (await more()).find(x => /^(Close|Open) all folders$/.test(x));
            out.offered.push(label ?? null);
            if (!label) break;
            choose(label);
            const want = label.startsWith("Close");
            await until(() => closed().every(c => c === want));
            out.states.push(closed().every(c => c === want));
          }
          const list = await more();
          out.unloadOthers = list.includes("Unload the other spaces");
          if (out.unloadOthers) choose("Unload the other spaces"); else menu.hidden = true;
          out.said = await until(() => doc.getElementById("note").classList.contains("shown") && doc.querySelector("#note .text").textContent, 5000);
          for (const f of mine()) send({type: "deleteFolder", key: f.querySelector(".head").dataset.folderHead});
          await until(() => !mine().length);
          return out;""")
        unloaded = away is None or m.js(MENU_TABS + """await until(() => !byId(args[0])?.linkedPanel, 5000); const t = byId(args[0]), gone = !t.linkedPanel;
          main().gBrowser.removeTab(t); await wait(500); return gone;""", away)
        check("a space's More closes all its folders at once, and then opens them", sorted(r.get("offered") or [], key=str) == ["Close all folders", "Open all folders"] and r.get("states") == [True, True], str(r))
        check("and unloads the other spaces, saying how many tabs went", away is None or (r.get("unloadOthers") and unloaded and "unloaded in the other spaces" in (r.get("said") or "")), f"{r} {away} {unloaded}")

        # The keys of the selection, in the sidebar: ⌥↓ moves the tab you are on one place along, in
        # every window; ⇧↓ takes the next row too; ⌘A every row.
        sidebar_page(m, MENU_PAGE + "await until(() => rowOf(args[0])); rowOf(args[0]).click(); return 1;", t1)
        m.js(MENU_TABS + "await until(() => idOf(main().gBrowser.selectedTab) === args[0]); await wait(500); return 1;", t1)
        # By the record's key: an unloaded placeholder in the other window has no address to go by.
        ORDER = MENU_TABS + """return wins().map(w => [...args].map(k => w.gBrowser.tabs.findIndex(t => !t.pinned && key(w, t) === JSON.stringify(k))));"""
        pair = [record_of("t1")["key"], record_of("t2")["key"]]
        before = m.js(ORDER, *pair)
        r = sidebar_page(m, MENU_PAGE + """
          const key = (k, more = {}) => page.dispatchEvent(new page.KeyboardEvent("keydown", page.JSON.parse(JSON.stringify({key: k, bubbles: true, cancelable: true, ...more}))));
          const today = () => [...doc.querySelectorAll("#tabs > .tab")].map(t => Number(t.dataset.tab));
          const at = () => today().indexOf(args[0]);
          const was = at();
          // The keys act on the row the keyboard is on before the tab you are on, and it is on a
          // row here: the Undo above was clicked without a pointer, which is how a key presses
          // it, and that leaves the keyboard in the list (note.js). Esc takes it out again.
          if (doc.querySelector(".cursor")) key("Escape");
          key("ArrowDown", {altKey: true});
          await until(() => at() === was + 1);
          const moved = at() - was;
          key("ArrowDown", {shiftKey: true});
          const two = doc.querySelectorAll("#tabs .tab.picked").length;
          key("Escape");
          key("a", {metaKey: true});
          const all = doc.querySelectorAll("#tabs .tab.picked").length, drawn = [...doc.querySelectorAll("#tabs .tab")].filter(t => t.offsetParent).length;
          key("Escape");
          return {moved, two, all, drawn, left: doc.querySelectorAll(".picked").length};""", t1)
        after = m.js(ORDER, *pair)
        check("⌥↓ in the sidebar moves the tab one place down, in every window", r.get("moved") == 1 and all(0 <= b[0] < b[1] for b in before) and all(a[0] > a[1] >= 0 for a in after), f"{r} {before} -> {after}")
        check("⇧↓ takes the next row too, and ⌘A every row shown", r.get("two") == 2 and r.get("all") == r.get("drawn") > 2 and r.get("left") == 0, str(r))

        # Held over a closed folder, a dragged tab opens it; over another space's dot, goes there,
        # and a drop in that space's list moves it there.
        r = sidebar_page(m, MENU_PAGE + """
          const head = () => doc.querySelector(`[data-folder-head="${args[1]}"]`);
          send({type: "foldFolder", key: args[1], collapsed: true});
          await until(() => head()?.parentElement.classList.contains("collapsed"));
          const data = new page.DataTransfer();
          const at = el => { const b = el.getBoundingClientRect(); return page.JSON.parse(JSON.stringify({bubbles: true, cancelable: true, clientX: b.left + 5, clientY: b.top + b.height / 2})); };
          const ev = (type, el) => { const e = new page.DragEvent(type, {...at(el), dataTransfer: data}); el.dispatchEvent(e); return e; };
          const row = rowOf(args[0]), id = args[0];
          ev("dragstart", row);
          ev("dragover", head());
          const opened = !!(await until(() => !head().parentElement.classList.contains("collapsed"), 3000));
          ev("drop", head());
          ev("dragend", row);
          const intoIt = await until(() => inFolder(id) === "More test", 5000);
          // Another space, held over its dot; then dropped into its list.
          const dot = doc.querySelector(`#spaces .space[data-space="${args[2]}"]`), drag = rowOf(args[3]);
          ev("dragstart", drag);
          ev("dragover", dot);
          const went = !!(await until(() => doc.querySelector("#spaces .space.active")?.dataset.space === args[2], 3000));
          await wait(800);
          const list = doc.getElementById("tabs");
          const over = ev("dragover", list), dropped = ev("drop", list);
          ev("dragend", drag);
          await wait(300);
          return {opened, inFolder: !!intoIt, went, accepted: over.defaultPrevented, dropped: dropped.defaultPrevented};""", now_id("t2"), folder, other, now_id("t3"))
        moved = None
        for _ in range(100):
            moved = record_of("t3")
            if moved and moved["space"] == other:
                break
            time.sleep(0.1)
        check("a tab held over a closed folder opens it, and a drop puts it in", r.get("opened") is True and r.get("inFolder") is True and (record_of("t2") or {}).get("folder") == folder, str(r))
        check("held over another space's dot it goes there, and a drop in that list moves the tab there", r.get("went") is True and r.get("accepted") is True and r.get("dropped") is True and (moved or {}).get("space") == other, f"{r} {moved}")
        sidebar_page(m, """send({type: "space", space: args[0]}); await wait(1000); return 1;""", space)

        # New tab here: in the folder at once, and saved there once it has a page.
        r = sidebar_page(m, MENU_PAGE + """
          const head = () => doc.querySelector(`[data-folder-head="${args[0]}"]`);
          const count = () => head().parentElement.querySelectorAll(".tab").length, n = count();
          await rightClick(head());
          choose("New tab here");
          await until(() => count() === n + 1);
          return {added: count() - n, active: !!head().parentElement.querySelector(".tab.active")};""", folder)
        m.js(H + """const t = main().gBrowser.selectedTab; t.linkedBrowser.loadURI(Services.io.newURI("https://example.org/?smoke-more-new"), {triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()}); await wait(500); return 1;""")
        made = None
        for _ in range(100):
            made = record_of("new")
            if made and made["folder"]:
                break
            time.sleep(0.1)
        check("New tab here makes a tab in the folder, which keeps it once it has a page", r.get("added") == 1 and r.get("active") and (made or {}).get("folder") == folder and (made or {}).get("saved"), f"{r} {made}")

        # Close all its tabs, from the folder's More while on one of them: the selection goes to a
        # tab that stays, not to one about to close, and one line takes them all back.
        r = sidebar_page(m, MENU_PAGE + """
          const head = () => doc.querySelector(`[data-folder-head="${args[0]}"]`);
          const rows = () => [...head().parentElement.querySelectorAll(".tab")].map(t => Number(t.dataset.tab));
          const was = rows();
          await until(() => head().parentElement.querySelector(".tab.active"));
          await rightClick(head());
          choose("More");
          choose("Close all its tabs");
          await until(() => rows().length === 0);
          const on = Number(doc.querySelector("#tabs .tab.active, #essentials .tile.active")?.dataset.tab);
          const line = await until(() => doc.querySelector("#note .text")?.textContent);
          doc.querySelector("#note .act").click();
          await until(() => rows().length === was.length, 15000);
          return {was: was.length, onOther: !!on && !was.includes(on), line, back: rows().length};""", folder)
        check("Close all its tabs in a folder's More goes to a tab that stays, and Undo brings them back",
              r.get("was", 0) >= 4 and r.get("onOther") and r.get("line") == f"{r.get('was')} tabs closed" and r.get("back") == r.get("was"), str(r))

        # The command bar has them by name, and the settings page lists their keys under More.
        bar_open(m)
        bar_keys(m, "markdown")
        rows = bar_rows_until(m, lambda rows: any(x["title"].startswith("Copy as Markdown") for x in rows))
        bar_keys(m, [ESC])
        wait_for_bar(m, False)
        check("the command bar finds Copy as Markdown link by its name", any(x["title"].startswith("Copy as Markdown") for x in rows), str(rows[:4]))
        r = ext_page(m, "/settings/settings.html", """
          const more = doc.getElementById("keys-more");
          for (let i = 0; i < 50 && more.hidden; i++) await wait(100);
          const hiddenFirst = doc.getElementById("keys-extra").hidden;
          more.click();
          await wait(300);
          return {button: !more.hidden, hiddenFirst, lines: [...doc.querySelectorAll("#keys-extra .key-label")].map(l => l.textContent)};""")
        check("the settings page keeps the commands with no key under More commands", r.get("button") and r.get("hiddenFirst") and "Sort today's tabs or this folder by name" in r.get("lines", [])
              and "Reload this space" in r.get("lines", []) and "Close this folder's tabs" in r.get("lines", []), str(r))
    finally:
        m.chrome()  # a script that failed in a page leaves Marionette there
        sidebar_page(m, """if (args[0]) send({type: "deleteFolder", key: args[0]}); await wait(800); return 1;""", locals().get("folder"))
        m.js(H + """for (const w of wins()) for (const t of [...w.gBrowser.tabs]) if (url(t).includes("smoke-more-")) w.gBrowser.removeTab(t, {skipPermitUnload: true});
          for (const w of wins()) for (const t of [...w.gBrowser.tabs]) if (/sidebar\\/sidebar\\.html|settings\\/settings\\.html/.test(url(t))) w.gBrowser.removeTab(t);
          await wait(1500); return 1;""")


def alone_away(m):
    # A saved tab you browse on in has left its address: its row says so, and its menu's two
    # ways out do what they say (leftSaved in common.js, tabactions.js, sidebar.js).
    m.js(H + """const w = main(); for (const t of [...w.gBrowser.tabs]) if (url(t).includes("/sidebar/sidebar.html")) w.gBrowser.removeTab(t);
      for (const name of ["home", "beside"]) { w.gBrowser.addTrustedTab("https://example.org/?smoke-away-" + name, {userContextId: 1, inBackground: true}); await wait(300); }
      await wait(3000); return 1;""")
    sidebar_page(m, """send({type: "space", space: "firefox-container-1"}); await wait(1000);
      send({type: "newFolder", space: "firefox-container-1", name: "Away folder"}); await wait(1500); return 1;""")
    for name in ("home", "beside"):
        to_folder(m, f"https://example.org/?smoke-away-{name}", "Away folder")
    r = sidebar_page(m, """
      const obj = o => page.JSON.parse(JSON.stringify(o)), windowId = (await page.browser.windows.getCurrent()).id;
      const side = page.browser.extension.getViews(obj({type: "sidebar", windowId}))[0], sdoc = side.document;
      const until = async (test, ms = 8000) => { for (const t0 = Date.now(); Date.now() - t0 < ms; await wait(50)) if (await test()) return true; return false; };
      const tabs = await page.browser.tabs.query(obj({windowId}));
      const home = tabs.find(t => t.url.endsWith("smoke-away-home")).id, beside = tabs.find(t => t.url.endsWith("smoke-away-beside")).id;
      const row = id => sdoc.querySelector(`#tabs .tab[data-tab="${id}"]`), box = e => e.getBoundingClientRect();
      const line = id => side.getComputedStyle(row(id).querySelector(".close"), "::before").maskImage;
      const facts = async () => (await page.browser.runtime.sendMessage(obj({type: "tabMenu", tabIds: [home]})))[0].away;
      const address = async () => (await page.browser.tabs.get(home)).url;
      const out = {};
      await page.browser.tabs.update(home, obj({active: true}));
      await until(() => row(home)?.classList.contains("active") && !row(home).classList.contains("unloaded"));
      out.before = {mark: !!row(home).querySelector(".away"), unloads: row(home).querySelector(".close").classList.contains("unloads"), away: await facts()};

      await page.browser.tabs.update(home, obj({url: "https://example.org/?smoke-away-elsewhere"}));
      out.marked = await until(() => row(home)?.querySelector(".away"));
      const mark = row(home).querySelector(".away"), icon = row(home).querySelector("img, .letter"), title = row(home).querySelector(".title");
      out.mark = {between: box(icon).right <= box(mark).left && box(mark).right <= box(title).left, width: box(mark).width,
        title: box(title).left === box(row(beside).querySelector(".title")).left, tip: row(home).title.split("\\n").at(-1), away: await facts(),
        line: line(home).includes("M4.25 8h7.5")};

      send({type: "tabAction", action: "saveHere", tabIds: [home]});
      out.saved = await until(() => !row(home)?.querySelector(".away"));
      out.said = sdoc.querySelector("#note .text")?.textContent;
      out.savedFacts = await facts();
      sdoc.querySelector("#note .act")?.click();
      out.undone = await until(() => row(home)?.querySelector(".away"));

      send({type: "tabAction", action: "backToSaved", tabIds: [home]});
      out.back = await until(async () => (await address()).endsWith("smoke-away-home") && !row(home)?.querySelector(".away"));
      out.backFacts = await facts();
      const key = sdoc.querySelector("#tabs .folder .head[title='Away folder']")?.dataset.folderHead;
      if (key) send({type: "deleteFolder", key});
      await wait(800);
      await page.browser.tabs.remove(obj([home, beside]));
      await wait(800);
      return out;""")
    check("a saved tab on its saved page has no mark, and its close button is the one that only unloads", r.get("before") == {"mark": False, "unloads": True, "away": False}, str(r.get("before")))
    mark = r.get("mark") or {}
    check("browsed on in, its row has a small stroke between its icon and its title, and no title has moved for it",
          r.get("marked") is True and mark.get("between") and 0 < mark.get("width", 0) <= 6 and mark.get("title") and mark.get("away") is True, str(mark))
    check("its tooltip says which page it is saved on, and the close button is drawn as a line", mark.get("tip") == "Saved on: Example Domain" and mark.get("line"), str(mark))
    check("Save this address makes where it is its saved page, and says so; Undo takes that back",
          r.get("saved") is True and (r.get("said") or "").startswith("Saved here") and r.get("savedFacts") is False and r.get("undone") is True, str(r))
    check("Back to saved address takes the page back, loaded, and the mark goes", r.get("back") is True and r.get("backFacts") is False, str(r))
    no_problems(m, "after a saved tab left its address and came back")
    close_sidebar_page(m)


def alone_link_drop(m):
    # A link dragged in from a page or another app opens as a tab where it is dropped
    # (sidebar/drag.js, droplinks.js). The drag is made as Firefox hands one to the page.
    m.js(H + """const w = main(); for (const t of [...w.gBrowser.tabs]) if (url(t).includes("/sidebar/sidebar.html")) w.gBrowser.removeTab(t);
      await wait(300); return 1;""")
    sidebar_page(m, """send({type: "space", space: "firefox-container-1"}); await wait(1000);
      send({type: "newFolder", space: "firefox-container-1", name: "Drop folder"}); await wait(1500); return 1;""")
    r = sidebar_page(m, """
      const obj = o => page.JSON.parse(JSON.stringify(o)), windowId = (await page.browser.windows.getCurrent()).id;
      const side = page.browser.extension.getViews(obj({type: "sidebar", windowId}))[0], sdoc = side.document, root = sdoc.documentElement;
      const until = async (test, ms = 8000) => { for (const t0 = Date.now(); Date.now() - t0 < ms; await wait(50)) if (await test()) return true; return false; };
      const carrying = kinds => { const data = new side.DataTransfer(); for (const [kind, text] of kinds) data.setData(kind, text); return data; };
      const link = name => carrying([["text/x-moz-url", "https://example.org/?smoke-drop-" + name + "\\nA link"], ["text/plain", "https://example.org/?smoke-drop-" + name]]);
      // Over `e`, a part of the way down it (and across it).
      const drag = (type, e, data, down = 0.75, across = 0.5) => { const q = e.getBoundingClientRect();
        const event = new side.DragEvent(type, obj({bubbles: true, cancelable: true, clientX: q.left + q.width * across, clientY: q.top + q.height * down}));
        Object.defineProperty(event, "dataTransfer", {value: data});
        e.dispatchEvent(event); return event.defaultPrevented; };
      const marks = () => [...sdoc.querySelectorAll(".drop-before, .drop-after, .drop-into, .drop-left, .drop-right")].length;
      const tabOf = async name => (await page.browser.tabs.query(obj({windowId}))).find(t => t.url.endsWith("smoke-drop-" + name) || t.title.endsWith("smoke-drop-" + name));
      const rowOf = async name => { const t = await tabOf(name); return t ? sdoc.querySelector(`#tabs .tab[data-tab="${t.id}"]`) : null; };
      const out = {}, selected = (await page.browser.tabs.query(obj({windowId, active: true})))[0].id;
      const rows = () => [...sdoc.querySelectorAll("#tabs > .tab")], row = rows()[0];

      // Text and files are no links: nothing is marked, and nothing is taken.
      out.text = {taken: drag("dragover", row, carrying([["text/plain", "https://example.org/?smoke-drop-text"]])), marks: marks(), dragging: root.dataset.dragging ?? null};
      // (A page may not make a drag that carries a file, so here only what such a drag says it carries.)
      out.file = {taken: drag("dragover", row, obj({types: ["text/x-moz-url", "application/x-moz-file"]})), marks: marks(), dragging: root.dataset.dragging ?? null};

      // A link over the lower half of a row: a line after it, as for a tab.
      out.over = {taken: drag("dragover", row, link("list")), after: row.classList.contains("drop-after"), marks: marks(), dragging: root.dataset.dragging ?? null};
      // It leaves the sidebar: nothing stays.
      row.dispatchEvent(new side.DragEvent("dragleave", obj({bubbles: true})));
      out.left = {marks: marks(), dragging: root.dataset.dragging ?? null};
      // It is let go of somewhere else, which this page is not told: gone by itself.
      drag("dragover", row, link("list"));
      await until(() => !marks() && !root.dataset.dragging, 4000);
      out.forgotten = {marks: marks(), dragging: root.dataset.dragging ?? null};

      // Dropped after that row.
      drag("dragover", row, link("list"));
      out.dropped = drag("drop", row, link("list"));
      out.listed = await until(async () => (await rowOf("list"))?.previousElementSibling === row);
      out.after = {marks: marks(), dragging: root.dataset.dragging ?? null, selected: (await page.browser.tabs.query(obj({windowId, active: true})))[0].id === selected,
        space: (await tabOf("list"))?.cookieStoreId};

      // On a folder's head: a saved tab in it.
      const head = sdoc.querySelector("#tabs .folder .head[title='Drop folder']");
      out.onFolder = {taken: drag("dragover", head, link("folder"), 0.5), into: head.classList.contains("drop-into")};
      drag("drop", head, link("folder"), 0.5);
      out.inFolder = await until(async () => (await rowOf("folder"))?.closest(".folder") === head.parentElement);
      await page.browser.runtime.sendMessage(obj({type: "flush"}));
      const all = (await page.browser.storage.local.get("syncedTabs")).syncedTabs;
      out.saved = Object.values(all).find(e => (e.saved?.url ?? "").endsWith("smoke-drop-folder"))?.parentKey === head.dataset.folderHead;

      // On the left half of the first tile: an essential before it.
      const tile = sdoc.querySelector("#essentials .tile"), tiles = sdoc.querySelectorAll("#essentials .tile").length;
      out.onTile = tile ? {taken: drag("dragover", tile, link("tile"), 0.5, 0.25), left: tile.classList.contains("drop-left")} : null;
      if (tile) drag("drop", tile, link("tile"), 0.5, 0.25);
      out.tile = !!tile && await until(async () => { const t = await tabOf("tile"); return t?.pinned && sdoc.querySelector(`#essentials .tile[data-tab="${t.id}"]`)?.nextElementSibling === tile; });
      out.tiles = sdoc.querySelectorAll("#essentials .tile").length - tiles;

      // Where a link has no place, the drop is still taken (Firefox would open it in the sidebar itself), and nothing opens.
      const bar = sdoc.getElementById("spaces"), count = (await page.browser.tabs.query(obj({windowId}))).length;
      out.nowhere = {over: drag("dragover", bar, link("nowhere"), 0.5, 0.02), marks: marks(), drop: drag("drop", bar, link("nowhere"), 0.5, 0.02)};
      await wait(1200);
      out.nowhere.opened = (await page.browser.tabs.query(obj({windowId}))).length - count;

      // Put away again.
      const pinned = await tabOf("tile");
      if (pinned) { send({type: "tabAction", action: "removeEssential", tabIds: [pinned.id]}); await until(async () => !(await page.browser.tabs.get(pinned.id)).pinned); await wait(1500); }
      send({type: "deleteFolder", key: head.dataset.folderHead});
      await wait(800);
      await page.browser.tabs.remove(obj((await page.browser.tabs.query(obj({windowId}))).filter(t => /smoke-drop-/.test(t.url + t.title)).map(t => t.id)));
      await wait(1000);
      return out;""")
    nothing = {"marks": 0, "dragging": None}
    check("text and a file dragged over the sidebar are no link: nothing is marked or taken", r.get("text") == {"taken": False, **nothing} and r.get("file") == {"taken": False, **nothing}, f"{r.get('text')} {r.get('file')}")
    check("a link dragged over a row is marked as a tab would be", r.get("over") == {"taken": True, "after": True, "marks": 1, "dragging": "tab"}, str(r.get("over")))
    check("when it leaves the sidebar, or is let go of elsewhere, nothing stays marked", r.get("left") == nothing and r.get("forgotten") == nothing, f"{r.get('left')} {r.get('forgotten')}")
    check("dropped after a row, the link is a tab right there, in the background and in this space",
          r.get("dropped") is True and r.get("listed") is True and r.get("after") == {**nothing, "selected": True, "space": "firefox-container-1"}, f"{r.get('dropped')} {r.get('listed')} {r.get('after')}")
    check("dropped on a folder, it is a saved tab in it", r.get("onFolder") == {"taken": True, "into": True} and r.get("inFolder") is True and r.get("saved") is True, f"{r.get('onFolder')} {r.get('inFolder')} {r.get('saved')}")
    check("dropped on the left of a tile, it is an essential before it", r.get("onTile") == {"taken": True, "left": True} and r.get("tile") is True and r.get("tiles") == 1, f"{r.get('onTile')} {r.get('tile')} {r.get('tiles')}")
    check("where a link has no place the drop is still taken, so that Firefox does not open it in the sidebar, and nothing opens",
          r.get("nowhere") == {"over": True, "marks": 0, "drop": True, "opened": 0}, str(r.get("nowhere")))
    no_problems(m, "after links were dropped in the sidebar")
    close_sidebar_page(m)
