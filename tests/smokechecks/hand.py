"""The list under the hand: real clicks and what they close, the quiet line and Undo, selections,
and the list staying put.
"""
import time
from testfirefox import EXT_ID
from smokechecks.base import (
    CMD, CTRL, ESC, GIVE_PERMISSIONS, H, IN_SIDEBAR, SIDEBAR_AT, check,
    click_at, extension_message, in_sidebar, look_in_sidebar, more_tabs_here, no_problems, press, sidebar_key,
    sidebar_mouse, sidebar_page, sidebar_until,
)


def alone_quiet_undo(m):
    # Clear by a real click, the quiet line, and Undo, compared with before in two windows;
    # closes with the ×, a saved tab removed for good, and a folder deleted (quiet.js).
    more_tabs_here(m, "quiet")
    # Two windows; alone_second_window has usually opened the other one, and it stays open.
    m.js(H + """if (!other()) { const w = main().OpenBrowserWindow(); w.__smoke = true; await wait(4000); } return 1;""")
    # What is compared: the tabs of the active space, in order, per window.
    # (Each window's tab strip can have them in another order; what counts is the list drawn.)
    LIST = H + """const ctx = Number(args[0].split("-").pop()), all = (await storage("%s", ["syncedTabs"])).syncedTabs;
      return wins().map(w => { const keys = w.gBrowser.tabs.filter(t => !t.pinned && t.userContextId === ctx && key(w, t)).map(t => key(w, t));
        return [keys.filter(k => !all[JSON.parse(k)]?.parentKey), keys.filter(k => all[JSON.parse(k)]?.parentKey)]; });""" % EXT_ID
    setup = sidebar_page(m, """
      const space = spaces().find(s => s.active).id;
      send({type: "newFolder", space, name: "Quiet"});
      for (let i = 0; i < 50 && !folders().some(f => f.name === "Quiet"); i++) await wait(100);
      const head = () => [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "Quiet");
      const [inside, also] = plainTabs().map(r => Number(r.dataset.tab));
      send({type: "moveTab", tabId: inside, folder: head().dataset.folderHead, before: null});
      send({type: "moveTab", tabId: also, folder: head().dataset.folderHead, before: null});
      // A placeholder with no page anywhere: into a folder, unloaded there, and out again.
      const third = plainTabs()[2], thirdId = Number(third.dataset.tab);
      send({type: "moveTab", tabId: thirdId, folder: head().dataset.folderHead, before: null});
      for (let i = 0; i < 60 && folders().find(f => f.name === "Quiet").tabs.length < 3; i++) await wait(100);
      await wait(800);
      doc.querySelector(`#tabs .folder .tab[data-tab="${thirdId}"] .close`).click();
      for (let i = 0; i < 60 && !doc.querySelector("#tabs .folder .tab.unloaded"); i++) await wait(100);
      await wait(1500);
      const placeholder = doc.querySelector("#tabs .folder .tab.unloaded");
      send({type: "moveTab", tabId: Number(placeholder.dataset.tab), folder: null, before: null});
      for (let i = 0; i < 60 && folders().find(f => f.name === "Quiet").tabs.length > 2; i++) await wait(100);
      // A page with unsaved input.
      await page.browser.tabs.create(page.JSON.parse(JSON.stringify({url: args[0] + "/unsaved", cookieStoreId: space, active: false})));
      for (let i = 0; i < 60 && !rows().includes("Unsaved"); i++) await wait(100);
      // A tab that has never been loaded, as a link opened in the background can be.
      await page.browser.tabs.create(page.JSON.parse(JSON.stringify({url: "https://example.org/?smoke-quiet-never", title: "Never loaded", cookieStoreId: space, discarded: true, active: false})));
      for (let i = 0; i < 60 && folders().find(f => f.name === "Quiet").tabs.length < 2; i++) await wait(100);
      for (let i = 0; i < 60 && !rows().includes("Never loaded"); i++) await wait(100);
      // A tab with a page before this one, which only Firefox's own memory can give back.
      const history = await page.browser.tabs.create(page.JSON.parse(JSON.stringify({url: "https://example.org/?smoke-quiet-one", cookieStoreId: space, active: false})));
      await wait(1500);
      await page.browser.tabs.update(history.id, page.JSON.parse(JSON.stringify({url: "https://example.org/?smoke-quiet-two"})));
      await wait(3000); // all of it is in the other window too
      // Stand on one of today's tabs, with a real click.
      const here = plainTabs()[0];
      here.click();
      await wait(1500);
      return {space, key: head().dataset.folderHead, here: Number(here.dataset.tab), rows: rows(), folders: folders()};""", m.pages)
    space = setup["space"]
    before = m.js(LIST, space)
    check("a tab that was never loaded is on today's list, for Clear to take", "Never loaded" in setup["rows"], str(setup))
    # Placeholders of today's tabs with no page anywhere, in this window.
    NO_PAGE = H + """const ctx = Number(args[0].split("-").pop()), all = (await storage("%s", ["syncedTabs"])).syncedTabs, w = main();
      return w.gBrowser.tabs.filter(t => !t.pinned && t.userContextId === ctx && url(t).includes("ghost.html") && key(w, t) && !all[JSON.parse(key(w, t))]?.parentKey
        && !wins().some(o => o.gBrowser.tabs.some(x => key(o, x) === key(w, t) && role(o, x) === "live"))).map(t => key(w, t));""" % EXT_ID
    no_page = m.js(NO_PAGE, space)
    check("a tab with no page anywhere is on today's list, as a placeholder", len(no_page) == 1, str(no_page))

    # A tab selected in either window stays, so that nothing jumps there; so does the page
    # with unsaved input, which is not on the list of what is compared with this.
    selected = m.js(H + """return wins().map(w => key(w, w.gBrowser.selectedTab));""")
    stays = len(set(before[0][0]) & set(selected))
    goes = len(before[0][0]) - stays - 1
    # Pages with no record stay too, such as the settings page a group before this left
    # open. This sidebar page itself, which plainTabs leaves out, is listed here only if this
    # is the space it is listed in (pageHomes, spaces.js): a page with no container is in one.
    strangers = len(setup["rows"]) - len(before[0][0]) - len(before[0][1]) - setup["rows"].count("Tidier")
    r = sidebar_page(m, """
      const out = {};
      const button = doc.querySelector("#tabs .divider .clear"), box = button.parentElement.getBoundingClientRect();
      out.reach = box.height; out.divider = doc.querySelector("#tabs .divider").getBoundingClientRect().height;
      out.faded = page.getComputedStyle(button).opacity;
      // The area is the gap and no more: the rows next to it keep all of themselves.
      const line = doc.querySelector("#tabs .divider").getBoundingClientRect(), at = y => doc.elementFromPoint(line.left + 40, y);
      out.gap = [line.top - 4, line.bottom + 4].map(y => !!at(y)?.closest(".clear-reach"));
      out.neighbours = [line.top - 13, line.bottom + 13].map(y => !!at(y)?.closest(".row"));  // the gap is 11 px each way (sidebar.css, .divider)
      // A button you tabbed to keeps Enter, which the list takes everywhere else (keys.js).
      const enter = e => e.dispatchEvent(new page.KeyboardEvent("keydown", {key: "Enter", bubbles: true, cancelable: true}));
      out.enter = enter(button);
      const act = doc.querySelector("#note .act");
      out.undoHidden = page.getComputedStyle(act).visibility;  // so that no key can reach it
      button.click();
      for (let i = 0; i < 100 && !doc.getElementById("note").classList.contains("shown"); i++) await wait(100);
      out.shown = doc.getElementById("note").classList.contains("shown");
      out.line = doc.querySelector("#note .text").textContent;
      out.undoShown = page.getComputedStyle(act).visibility;
      out.enterUndo = enter(act);
      out.rows = plainTabs().filter(r => r.querySelector(".title").textContent !== "Unsaved").map(r => Number(r.dataset.tab));
      out.stayed = rows().includes("Unsaved");
      out.asked = !!page.browser.tabs && (await page.browser.tabs.query({active: true, currentWindow: true}))[0].title;
      out.folders = folders();
      out.tiles = tiles().length;
      return out;""", setup["here"])
    check("Clear shows only near the line, in an area that takes no room", r["reach"] >= 16 and r["divider"] <= 2 and r["faded"] == "0", str(r))
    check("the area Clear listens on covers the gap and no part of a row", r["gap"] == [True, True] and r["neighbours"] == [True, True], str(r))
    check("Undo cannot be reached by a key while there is no line, and Enter works on it and on Clear", r["undoHidden"] == "hidden" and r["undoShown"] == "visible" and r["enter"] and r["enterUndo"], str(r))
    check("Clear by a real click closes today's tabs, except any selected in a window", setup["here"] in r["rows"] and len(r["rows"]) == stays + strangers, f"{stays} stay, and {strangers} with no record: {r}")
    check("Clear leaves the folders", r["folders"] == setup["folders"], str(r))
    check("the line says how many went, and how many stayed", r["shown"] and r["line"] == f"{goes} tabs closed, 1 stayed", f"{goes} go: {r}")
    check("a page with unsaved input stays, without asking", r["stayed"] and r["asked"] != "Unsaved", str(r))
    after = m.js(LIST, space)
    check("Clear closes them in the other window too", len(after) == 2 and after[0] == after[1] and len(after[0][0]) == stays + 1 and after[0][1] == before[0][1], f"{before} -> {after}")

    r = sidebar_page(m, """
      const selected = async () => (await page.browser.tabs.query({active: true, currentWindow: true}))[0].id;
      const was = await selected();
      doc.querySelector("#note .act").click();
      const gone = !doc.getElementById("note").classList.contains("shown");
      for (let i = 0; i < 100 && rows().length < args[0].length; i++) await wait(100);
      await wait(1500);
      return {gone, rows: rows(), folders: folders(), still: was === await selected()};""", setup["rows"])
    check("Undo brings the same list back, in order", r["rows"] == setup["rows"], f"{setup['rows']} -> {r['rows']}")
    check("Undo leaves the folders as they were", r["folders"] == setup["folders"], str(r))
    check("Undo stays on the tab you are on, and the line goes at once", r["still"] and r["gone"], str(r))
    back = m.js(LIST, space)
    check("Undo brings them back under their own keys, in order, in both windows", back == before, f"{before} -> {back}")
    loaded = m.js(H + """await wait(1500); const w = main(), ctx = Number(args[0].split("-").pop());
      return wins().flatMap(w => w.gBrowser.tabs.filter(t => !t.pinned && t.userContextId === ctx && t.linkedPanel && !t.selected && key(w, t)).map(t => t.label));""", space)
    check("nothing loads because of Clear and Undo but what was loaded and not cleared", not [x for x in loaded if x == "Never loaded" or "smoke-quiet" in x], str(loaded))

    again = m.js(NO_PAGE, space)
    check("a tab with no page anywhere comes back as a placeholder, unloaded, under its own key", again == no_page, f"{no_page} -> {again}")
    m.js(H + """const w = main(), t = w.gBrowser.tabs.find(x => x.label === "Unsaved"); if (t) w.gBrowser.removeTab(t, {skipPermitUnload: true}); await wait(1500); return 1;""")

    # The page's history is back, once it is selected and loads.
    h = m.js(H + """const w = main(), was = w.gBrowser.selectedTab, t = w.gBrowser.tabs.find(x => url(x).includes("smoke-quiet-two"));
      if (!t) return {missing: true};
      const unloaded = !t.linkedPanel;
      w.gBrowser.selectedTab = t; await wait(2500);
      const out = {unloaded, count: t.linkedBrowser.browsingContext?.sessionHistory?.count, at: url(t), ctx: t.userContextId};
      w.gBrowser.selectedTab = was; await wait(800);
      return out;""")
    check("a page brought back is unloaded, in its container, and keeps its history", h.get("unloaded") and h.get("count", 0) >= 2 and "smoke-quiet-two" in h.get("at", "") and h.get("ctx") == int(space.split("-")[-1]), str(h))

    # Two closed with the ×: a group, and the line goes by itself.
    r = sidebar_page(m, """
      const chosen = plainTabs().filter(r => !r.classList.contains("active")).slice(0, 2);
      const ids = chosen.map(r => Number(r.dataset.tab));
      for (const r of chosen) r.querySelector(".close").click();
      const note = doc.getElementById("note");
      for (let i = 0; i < 50 && !note.classList.contains("shown"); i++) await wait(100);
      const line = doc.querySelector("#note .text").textContent, t0 = Date.now();
      for (let i = 0; i < 300 && note.classList.contains("shown"); i++) await wait(100);
      return {line, ids, ms: Date.now() - t0, shown: note.classList.contains("shown"), rows: plainTabs().map(r => Number(r.dataset.tab))};""")
    check("two tabs closed with the × are one line", r["line"] == "2 tabs closed", str(r))
    check("the line goes by itself, after about ten seconds", not r["shown"] and 8000 < r["ms"] < 13000, str(r))
    check("they stay closed", not set(r["ids"]) & set(r["rows"]), str(r))

    # A saved tab: closing it loaded says nothing, closing its placeholder removes it for good.
    s = m.js(H + """const all = (await storage("%s", ["syncedTabs"])).syncedTabs;
      return Object.keys(all).filter(k => all[k].parentKey === args[0]);""" % EXT_ID, setup["key"])
    inside_before = m.js(LIST, space)
    r = sidebar_page(m, """
      const row = () => [...doc.querySelectorAll("#tabs .folder")].find(f => f.querySelector(".head .title").textContent === "Quiet").querySelector(".tab");
      const note = doc.getElementById("note"), count = () => folders().find(f => f.name === "Quiet").tabs;
      row().querySelector(".close").click();
      await wait(1500);
      const unloaded = {said: note.classList.contains("shown"), tabs: count(), dim: row().classList.contains("unloaded")};
      row().querySelector(".close").click();
      for (let i = 0; i < 50 && !note.classList.contains("shown"); i++) await wait(100);
      const line = doc.querySelector("#note .text").textContent, gone = count();
      doc.querySelector("#note .act").click();
      for (let i = 0; i < 50 && folders().find(f => f.name === "Quiet").tabs.length < unloaded.tabs.length; i++) await wait(100);
      await wait(1000);
      return {unloaded, line, gone, tabs: count()};""")
    check("a loaded saved tab only unloads, with no line", r["unloaded"]["said"] is False and r["unloaded"]["dim"] and len(r["unloaded"]["tabs"]) == 2, str(r))
    check("its placeholder closed is removed for good, and the line offers it back", r["line"] == "Tab removed" and len(r["gone"]) == 1, str(r))
    check("Undo puts it back in its place in the folder", r["tabs"] == r["unloaded"]["tabs"], str(r))
    check("and in both windows", m.js(LIST, space) == inside_before, str(m.js(LIST, space)))
    stored = m.js(H + """const all = (await storage("%s", ["syncedTabs"])).syncedTabs; await wait(800);
      return Object.keys((await storage("%s", ["syncedTabs"])).syncedTabs).filter(k => all[k]?.parentKey === args[0]);""" % (EXT_ID, EXT_ID), setup["key"])
    check("under its own key, in its folder", sorted(stored) == sorted(s), f"{s} -> {stored}")

    # A folder deleted: its tabs stay, and Undo gives it back.
    r = sidebar_page(m, """
      const note = doc.getElementById("note"), was = folders();
      send({type: "deleteFolder", key: args[0]});
      for (let i = 0; i < 50 && !note.classList.contains("shown"); i++) await wait(100);
      const line = doc.querySelector("#note .text").textContent, without = folders(), rowsThen = rows();
      doc.querySelector("#note .act").click();
      for (let i = 0; i < 50 && !folders().some(f => f.name === "Quiet"); i++) await wait(100);
      await wait(500);
      return {was, line, without, rowsThen, folders: folders()};""", setup["key"])
    check("a folder deleted keeps its tabs, and says so with an undo", r["line"] == "Folder deleted" and not [f for f in r["without"] if f["name"] == "Quiet"]
          and all(t in r["rowsThen"] for t in [t for f in r["was"] if f["name"] == "Quiet" for t in f["tabs"]]), str(r))
    check("Undo gives the folder back, with its name, place and tabs", r["folders"] == r["was"], str(r))

    # Clear by a real pointer: it fades in anywhere near the line, and out again away from it.
    # (Only in the selected tab has the sidebar's page a pointer, so it is selected for this.)
    m.js(H + """const w = main(); w.__was = w.gBrowser.selectedTab; w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes("/sidebar/sidebar.html")); await wait(800); return 1;""")
    near = sidebar_page(m, """const r = doc.querySelector("#tabs .divider").getBoundingClientRect(), row = doc.querySelector("#tabs > .tab").getBoundingClientRect();
      return {line: [Math.round(r.left + 30), Math.round(r.top) - 4], away: [Math.round(row.left + 30), Math.round(row.top + row.height / 2)]};""")
    def pointer_to(at):
        m.cmd("Marionette:SetContext", {"value": "content"})
        m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"}, "actions": [{"type": "pointerMove", "x": at[0], "y": at[1], "duration": 0, "origin": "viewport"}]}]})
        m.chrome()
    OPACITY = """const b = doc.querySelector("#tabs .clear");
      for (let i = 0; i < 40 && page.getComputedStyle(b).opacity !== args[0]; i++) await wait(50);
      return page.getComputedStyle(b).opacity;"""
    pointer_to(near["line"])
    shows_near = sidebar_page(m, OPACITY, "1")
    pointer_to(near["away"])
    goes_away = sidebar_page(m, OPACITY, "0")
    m.js(H + """const w = main(); w.gBrowser.selectedTab = w.__was; delete w.__was; await wait(800); return 1;""")
    check("Clear fades in with a real pointer near the line, and out away from it", shows_near == "1" and goes_away == "0", f"{near} {shows_near} {goes_away}")

    # Undo from another space: the tabs come back there, and this window stays where it is.
    more_tabs_here(m, "quiet-away")
    # (Going through a space would show its hidden tabs for a moment, too quick for the list.)
    m.js(H + """const w = main(); w.__shows = []; w.__onShow = () => w.__shows.push(Date.now()); w.gBrowser.tabContainer.addEventListener("TabShow", w.__onShow); return 1;""")
    r = sidebar_page(m, """
      const note = doc.getElementById("note"), n = plainTabs().length;
      const chosen = plainTabs().filter(r => !r.classList.contains("active")).slice(-2);
      for (const r of chosen) r.querySelector(".close").click();
      for (let i = 0; i < 50 && !note.classList.contains("shown"); i++) await wait(100);
      const home = spaces().find(s => s.active).id, away = spaces().find(s => !s.active).id;
      doc.querySelector(`#spaces .space[data-space="${away}"]`).click();
      for (let i = 0; i < 50 && spaces().find(s => s.active).id !== away; i++) await wait(100);
      await wait(300);
      const selected = async () => (await page.browser.tabs.query({active: true, currentWindow: true}))[0].id;
      const was = await selected(), seen = [];
      const watch = new page.MutationObserver(() => seen.push(doc.documentElement.dataset.space));
      watch.observe(doc.documentElement, {attributes: true, attributeFilter: ["data-space"]});
      const shown = note.classList.contains("shown"), t0 = Date.now();
      doc.querySelector("#note .act").click();
      await wait(2500);
      watch.disconnect();
      const t1 = Date.now(), still = was === await selected(), stayed = spaces().find(s => s.active).id === away;
      doc.querySelector(`#spaces .space[data-space="${home}"]`).click();
      for (let i = 0; i < 50 && plainTabs().length < n; i++) await wait(100);
      return {shown, away, seen, still, stayed, n, t0, t1, back: plainTabs().length};""")
    shows = m.js(H + """const w = main(); w.gBrowser.tabContainer.removeEventListener("TabShow", w.__onShow); return w.__shows;""")
    check("Undo from another space brings the tabs back there", r["shown"] and r["back"] == r["n"], str(r))
    check("and this window stays where it is, with no other space shown for a moment", r["stayed"] and r["still"] and all(x == r["away"] for x in r["seen"]) and not [t for t in shows if r["t0"] <= t <= r["t1"]], f"{r} {shows}")

    # With no line between folders and tabs, Clear is in the list's menu. Then quiet
    # again, for alone_idle: the line gone, and its timer with it.
    r = sidebar_page(m, """
      const note = doc.getElementById("note");
      send({type: "deleteFolder", key: args[0]});
      for (let i = 0; i < 50 && folders().some(f => f.name === "Quiet"); i++) await wait(100);
      const others = folders();
      const menu = doc.getElementById("tabs");
      menu.dispatchEvent(new page.MouseEvent("contextmenu", {bubbles: true, cancelable: true, clientX: 40, clientY: 200}));
      const items = [...doc.querySelectorAll("#menu .item")];
      const labels = items.map(b => b.textContent), n = plainTabs().length;
      items.find(b => b.textContent === "Clear today's tabs")?.click();
      await wait(1500);
      const line = doc.querySelector("#note .text").textContent, left = plainTabs().length;
      doc.querySelector("#note .act").click();
      for (let i = 0; i < 50 && plainTabs().length < n; i++) await wait(100);
      const back = plainTabs().length;
      for (let i = 0; i < 20 && !doc.getElementById("note").classList.contains("shown"); i++) await wait(50);
      return {others, labels, line, left, n, back, shown: note.classList.contains("shown")};""", setup["key"])
    check("the list's menu has Clear too, and it can be undone", "Clear today's tabs" in r["labels"] and r["line"].endswith("closed") and 1 <= r["left"] <= 2 and r["back"] == r["n"], str(r))
    check("Undo leaves no line behind", r["shown"] is False, str(r))
    sizes = extension_message(m, {"type": "stats"})["sizes"]
    check("and nothing is kept for it", sizes["quietNotes"] == 0 and sizes["closeGroups"] == 0, str(sizes))
    # The placeholders with no page have done their work: an update would give each a live
    # tab (reconcileAll), which alone_update would see as a change.
    m.js(H + """await removeWhere((w, t) => args[0].includes(key(w, t))); return 1;""", m.js(NO_PAGE, space))
    no_problems(m, "after Clear and Undo")


# --- The sidebar under your hand ----------------------------------------------------------
# Real pointer and keys, from Firefox's own input, on the real sidebar in the window: what a
# double click, a middle click or a click a little late does, as a hand does them.
def hand(m, *acts):
    """A real pointer in the main window: WebDriver pointer actions at the window's coordinates."""
    m.js(H + """main().focus(); return 1;""")
    m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"}, "actions": list(acts)}]})
    m.cmd("WebDriver:ReleaseActions")


def hand_to(p, dx=0, dy=0):
    return {"type": "pointerMove", "x": int(p["x"] + dx), "y": int(p["y"] + dy), "duration": 0, "origin": "viewport"}


def hand_click(button=0, hold=0):
    return [{"type": "pointerDown", "button": button}, *([{"type": "pause", "duration": hold}] if hold else []), {"type": "pointerUp", "button": button}]


def hand_pause(ms):
    return {"type": "pause", "duration": ms}


# In the real sidebar: rows by title, boxes, and a point in the window's coordinates.
HAND_JS = """const row = t => [...doc.querySelectorAll("#tabs .tab")].find(r => r.title.split("\\n")[0] === t);
  const box = e => { const b = e.getBoundingClientRect(); return {x: b.x + b.width / 2, y: b.y + b.height / 2, top: Math.round(b.top), bottom: Math.round(b.bottom), left: b.left, right: b.right}; };"""


def hand_spot(m, body, *args):
    """What `body` (a function body in the real sidebar, with HAND_JS) returns, its x and y moved into the window."""
    p = in_sidebar(m, "(...args) => { " + HAND_JS + body + " }", *args)
    if not isinstance(p, dict) or "x" not in p:
        return p
    o = m.js(SIDEBAR_AT)
    return {**p, "x": o["x"] + p["x"], "y": o["y"] + p["y"]}


def alone_hand(m):
    m.js(H + """const w = main(); w.focus(); for (const t of [...w.gBrowser.tabs]) if (/sidebar\\/sidebar\\.html|settings\\/settings\\.html/.test(url(t))) w.gBrowser.removeTab(t);
      Services.prefs.setBoolPref("general.autoScroll", true); // Firefox's own default on a Mac, which the dotfiles leave
      await wait(300); return 1;""")
    here = sidebar_until(m, """() => doc.querySelector("#spaces .space.active")?.dataset.space""")
    m.js(H + """const w = main(), [pages, ctx] = args;
      for (let i = 1; i <= 12; i++) { w.gBrowser.addTrustedTab(pages + "/titled?hand-" + i, {userContextId: ctx, inBackground: true}); await wait(80); }
      for (let i = 0; i < 100 && w.gBrowser.tabs.filter(t => t.label.startsWith("hand-")).length < 12; i++) await wait(100);
      await wait(2500); return 1;""", m.pages, int(here.split("-")[-1]))
    away = m.js(H + """const w = main(), s = w.SidebarController.browser.getBoundingClientRect(); return {x: s.right + 300, y: s.top + 200};""")
    hands = lambda: m.js(H + """return main().gBrowser.tabs.filter(t => t.label.startsWith("hand-")).map(t => t.label).sort();""")
    sidebar_until(m, """() => [...doc.querySelectorAll("#tabs .tab")].filter(r => r.title.startsWith("hand-")).length >= 12""")

    # A double click on × closes one tab: the click that follows one that acted does nothing
    # (secondclick.js). The row folds away at once, from the click, and the rows below come up
    # into its place in one soft move, with the pointer still in the list: no hole is left where
    # it was. Where the row below is, is read at every frame from the click on.
    m.js(H + """Services.prefs.setIntPref("ui.prefersReducedMotion", 0); await wait(300); return 1;""")
    p = hand_spot(m, """const r = row("hand-3"); r.scrollIntoView({block: "center"}); const c = box(r.querySelector(".close")), b = r.nextElementSibling, a = r.previousElementSibling;
      const seen = content.handFold = [], t0 = content.performance.now();
      const look = () => { const now = row(b.title.split("\\n")[0]); if (now) seen.push([Math.round(content.performance.now() - t0), Math.round(box(now).top * 10) / 10, !row("hand-3") || row("hand-3").classList.contains("closing")]);
        if (content.performance.now() - t0 < 2500) content.requestAnimationFrame(look); };
      r.querySelector(".close").addEventListener("click", () => { seen.length = 0; seen.push(["click", Math.round(content.performance.now() - t0)]); }, {capture: true, once: true});
      content.requestAnimationFrame(look);
      return {x: c.x, y: c.y, below: b.title.split("\\n")[0], top: box(b).top, above: a.title.split("\\n")[0], aboveTop: box(a).top, list: doc.getElementById("tabs").scrollTop};""")
    hand(m, hand_to(p), hand_pause(300), *hand_click(), hand_pause(60), *hand_click())
    time.sleep(1.5)
    after = hand_spot(m, """const b = row(args[0]), a = row(args[1]), seen = content.handFold, clicked = seen[0][1], frames = seen.slice(1).map(([at, top, going]) => [at - clicked, top, going]);
      return {top: b && box(b).top, aboveTop: a && box(a).top, rooms: doc.querySelectorAll("#tabs .room").length, gone: !row("hand-3"), pointed: doc.getElementById("tabs").matches(":hover"), frames};""", p["below"], p["above"])
    left = hands()
    check("a double click on × closes one tab", "hand-3" not in left and len(left) == 11 and after["gone"], f"{left} {after}")
    # (At the end of a scrolled list, which gets shorter, the rows above come down instead.)
    comes_up = p["top"] - after["top"] == 32 and after["aboveTop"] == p["aboveTop"]
    come_down = after["aboveTop"] - p["aboveTop"] >= 32 and after["top"] >= p["top"]
    # How the rows came up: a frame comes every 16 ms on a Mac at rest, and every 200 ms on a
    # busy one, so what is asked of every run is that the fold starts with the click and ends;
    # that the way there is a move and not a jump is asked where there were frames to see it.
    tops = [top for _, top, _ in after["frames"]]
    moved = [(at, top) for at, top, _ in after["frames"] if top not in (tops[0], tops[-1])]
    started = next((at for at, top, going in after["frames"] if going or top != tops[0]), None)
    settled = next((at for at, top, _ in after["frames"] if top == tops[-1]), None)
    often = len([1 for at, _, _ in after["frames"] if at <= 300]) >= 10
    check("the closed row's place is taken at once, with the pointer still in the list, and no hole is left", after["pointed"] and after["rooms"] == 0 and (comes_up or come_down), f"{p} {after['top']} {after['aboveTop']} rooms {after['rooms']}")
    check("the row folds away from the click itself, before its tab has closed", started is not None and started == after["frames"][0][0] and after["frames"][0][2], f"{after['frames'][:6]}")
    if often and comes_up:
        check("the rows below come up in one soft move, over well within half a second",
              settled is not None and settled <= 450 and len(moved) >= 3 and all(a[1] >= b[1] for a, b in zip(moved, moved[1:])),
              f"settled {settled} ms, {len(moved)} frames on the way: {after['frames'][:40]}")
    else:
        print(f"INFO  too few frames to see the rows move ({len(after['frames'])} in {after['frames'][-1][0] if after['frames'] else 0} ms): settled {settled} ms after the click", flush=True)
    hand(m, hand_to(away))
    time.sleep(0.3)

    # With less motion asked for, the row is simply gone, and the row below is in its place.
    m.js(H + """const w = main(), [pages, ctx] = args; Services.prefs.setIntPref("ui.prefersReducedMotion", 1);
      w.gBrowser.addTrustedTab(pages + "/titled?hand-still", {userContextId: ctx, inBackground: true});
      for (let i = 0; i < 100 && !w.gBrowser.tabs.some(t => t.label === "hand-still"); i++) await wait(100); return 1;""", m.pages, int(here.split("-")[-1]))
    sidebar_until(m, """() => [...doc.querySelectorAll("#tabs .tab")].some(r => r.title.split("\\n")[0] === "hand-still") && content.matchMedia("(prefers-reduced-motion: reduce)").matches""")
    p = hand_spot(m, """const r = row("hand-still"); r.scrollIntoView({block: "center"}); const seen = content.handStill = [];
      new content.MutationObserver(() => { if (doc.querySelector("#tabs .room")) seen.push("room"); }).observe(doc.getElementById("tabs"), {childList: true, subtree: true});
      return box(r.querySelector(".close"));""")
    hand(m, hand_to(p), hand_pause(300), *hand_click())
    r = sidebar_until(m, """() => ![...doc.querySelectorAll("#tabs .tab")].some(r => r.title.split("\\n")[0] === "hand-still") && {rooms: content.handStill.length}""", timeout=10)
    left = hands()
    hand(m, hand_to(away))
    m.js(H + """Services.prefs.clearUserPref("ui.prefersReducedMotion"); await wait(300); return 1;""")
    check("with less motion asked for, a closed row is gone at once, with nothing folding", bool(r) and r["rooms"] == 0 and "hand-still" not in left, f"{r} {left}")

    # A middle click closes, with Firefox's autoscroll on, and the next click works. (Firefox
    # starts it only in what can scroll, so the list gets room at its end for this.)
    p = hand_spot(m, """doc.getElementById("tabs").style.paddingBottom = "2000px"; const r = row("hand-5"); r.scrollIntoView({block: "center"}); return box(r);""")
    hand(m, hand_to(p), hand_pause(200), *hand_click(1, hold=80))
    time.sleep(1)
    scrolling = m.js(H + """return main().SidebarController.browser.contentDocument.getElementById("autoscroller")?.state ?? "none";""")
    in_sidebar(m, """() => { doc.getElementById("tabs").style.paddingBottom = ""; return 1; }""")
    q = hand_spot(m, """const r = row("hand-6"); r.scrollIntoView({block: "nearest"}); return box(r);""")
    hand(m, hand_to(q), *hand_click())
    selected = m.js(H + """const w = main(); for (let i = 0; i < 30 && w.gBrowser.selectedTab.label !== "hand-6"; i++) await wait(100); return w.gBrowser.selectedTab.label;""")
    check("a middle click on a row closes its tab, with autoscroll on", "hand-5" not in hands() and scrolling != "open", f"{hands()} {scrolling}")
    check("and the click after it is not lost", selected == "hand-6", selected)

    # The speaker stays where it is under the pointer: a click on the one you see mutes.
    m.js(H + """const w = main(), t = w.gBrowser.tabs.find(x => x.label === "hand-6"); t.toggleAttribute("soundplaying", true); w.gBrowser._tabAttrModified(t, ["soundplaying"]); return 1;""")
    hand(m, hand_to(away))
    sidebar_until(m, """() => !![...doc.querySelectorAll("#tabs .tab")].find(r => r.title.startsWith("hand-6"))?.querySelector(".sound")""")
    rest = hand_spot(m, """const r = row("hand-6"); r.scrollIntoView({block: "nearest"}); return box(r.querySelector(".sound"));""")
    hand(m, hand_to(rest), hand_pause(150))
    over = hand_spot(m, """return box(row("hand-6").querySelector(".sound"));""")
    hand(m, hand_to(away), hand_to(rest), hand_pause(150), *hand_click())  # (a chain starts where the last one left the pointer: it is told again)
    s = m.js(H + """const w = main(), t = w.gBrowser.tabs.find(x => x.label === "hand-6"); for (let i = 0; i < 30 && t && !t.muted; i++) await wait(100);
      return {open: w.gBrowser.tabs.includes(t), muted: !!t?.muted};""")
    check("a click on a playing tab's speaker, where it was before the pointer came, mutes it", s == {"open": True, "muted": True} and over["x"] == rest["x"], f"{s} {rest} {over}")
    m.js(H + """const w = main(), t = w.gBrowser.tabs.find(x => x.label === "hand-6"); t.toggleAttribute("soundplaying", false); w.gBrowser._tabAttrModified(t, ["soundplaying"]); if (t.muted) t.toggleMuteAudio(); return 1;""")

    # A notice dismissed with a double click on its ×: it fades where it is, so the list above it
    # does not come down under the pointer, and the second click reaches nothing. Its room goes
    # once the pointer has left it. (The line that asks for the isolation permission; where the test
    # Firefox has given it, it is taken away for a moment.)
    given = m.js("""return WebExtensionPolicy.getByID(args[0]).hasPermission("webRequestBlocking");""", EXT_ID)
    if given:
        m.js("""const [id] = args; const {ExtensionPermissions} = ChromeUtils.importESModule("resource://gre/modules/ExtensionPermissions.sys.mjs");
          await ExtensionPermissions.remove(id, {permissions: ["webRequest", "webRequestBlocking"], origins: ["<all_urls>"]}, WebExtensionPolicy.getByID(id).extension);
          await new Promise(r => ChromeUtils.importESModule("resource://gre/modules/Timer.sys.mjs").setTimeout(r, 800)); return 1;""", EXT_ID)
    hand(m, hand_to(away))
    sidebar_until(m, """() => !doc.querySelector(".ask-line").hidden""")
    p = hand_spot(m, """return {...box(doc.querySelector(".ask-line .ask-no")), list: Math.round(doc.getElementById("tabs").getBoundingClientRect().bottom)};""")
    picked = m.js(H + """return main().gBrowser.selectedTab.label;""")
    hand(m, hand_to(p), hand_pause(150), *hand_click(), hand_pause(60), *hand_click())
    time.sleep(0.8)
    at = in_sidebar(m, """() => ({shown: !doc.querySelector(".ask-line").hidden, list: Math.round(doc.getElementById("tabs").getBoundingClientRect().bottom)})""")
    still = m.js(H + """return main().gBrowser.selectedTab.label;""")
    hand(m, hand_to(away))
    time.sleep(0.5)
    left = in_sidebar(m, """() => ({shown: !doc.querySelector(".ask-line").hidden, list: Math.round(doc.getElementById("tabs").getBoundingClientRect().bottom)})""")
    in_sidebar(m, """() => { content.localStorage.removeItem("isolationDeclined"); return 1; }""")  # as it was: the line asks again
    if given:
        m.js(GIVE_PERMISSIONS, EXT_ID, ["webRequest", "webRequestBlocking"], ["<all_urls>"])
    check("a double click on a notice's × fades it in place, and the second click reaches nothing", at["shown"] and at["list"] == p["list"] and still == picked, f"{p} {at} {picked} -> {still}")
    check("and its room goes once the pointer has left it", not left["shown"] and left["list"] > p["list"], str(left))

    def close_two(a, b):
        # Two clicks within the moment that makes them one thing you did (CLOSE_GROUP_MS), so the
        # second × is where it was seen before the first click. A closed row folds away, and the
        # rows below it come up (at the end of a scrolled list, the rows above come down instead):
        # so the row that goes first is the one whose going leaves the other where it is. On a
        # slow machine the second click otherwise found the next row under it, and closed that.
        before = hands()
        p = hand_spot(m, """const [a, b] = args, list = doc.getElementById("tabs"); row(a).scrollIntoView({block: "center"});
          const atEnd = list.scrollTop > 0 && list.scrollHeight - list.scrollTop - list.clientHeight < 40;
          const [upper, lower] = [row(a), row(b)].sort((x, y) => box(x).top - box(y).top), [first, second] = atEnd ? [upper, lower] : [lower, upper];
          return {...box(first.querySelector(".close")), second: box(second.querySelector(".close"))};""", a, b)
        o = m.js(SIDEBAR_AT)
        hand(m, hand_to(p), hand_pause(150), *hand_click(), hand_to({"x": o["x"] + p["second"]["x"], "y": o["y"] + p["second"]["y"]}), *hand_click())
        said = sidebar_until(m, """() => doc.getElementById("note").classList.contains("shown") && doc.querySelector("#note .text").textContent""")
        gone = sorted(set(before) - set(hands()))
        if gone != sorted([a, b]):
            check(f"× on {a} and on {b} closes those two", False, f"closed {gone}")
        return said

    # The quiet line has a room of its own, waits while the pointer is on it, and goes a while after.
    said = close_two("hand-1", "hand-2")
    line = hand_spot(m, """const n = doc.querySelector("#note .line"), b = box(n), list = doc.getElementById("tabs").getBoundingClientRect();
      return {x: b.left + 30, y: b.y, top: b.top, listBottom: Math.round(list.bottom), under: doc.elementFromPoint(b.right - 20, b.y)?.closest("#note") ? "note" : "other"};""")
    hand(m, hand_to(line))
    time.sleep(12)
    held = in_sidebar(m, """() => doc.getElementById("note").classList.contains("shown")""")
    hand(m, hand_to(away))
    t0 = time.time()
    sidebar_until(m, """() => !doc.getElementById("note").classList.contains("shown")""", timeout=15)
    gone_after = round(time.time() - t0, 1)
    check("two tabs closed with their × are one line, in a room of its own that covers no row", said == "2 tabs closed" and line["top"] >= line["listBottom"] and line["under"] == "note", f"{said} {line}")
    check("the line waits while the pointer is on it, and goes on from there when it leaves, with two seconds at least", held and 1.5 <= gone_after <= 12, f"held {held}, gone {gone_after} s after")

    # A click on Undo just after the line has faded lands on nothing. (One while it fades still
    # brings them back: the line was there to be clicked, quiet.test.mjs.)
    close_two("hand-4", "hand-7")
    undo = hand_spot(m, """return box(doc.querySelector("#note .act"));""")
    before = (hands(), m.js(H + """return main().gBrowser.selectedTab.label;"""))
    hand(m, hand_to(away))
    sidebar_until(m, """() => !doc.getElementById("note").classList.contains("shown")""", timeout=20)
    time.sleep(0.25)  # its fade takes 0.2 s
    hand(m, hand_to(undo), *hand_click())
    time.sleep(1.5)
    after = (hands(), m.js(H + """return main().gBrowser.selectedTab.label;"""))
    hand(m, hand_to(away))
    check("a click on Undo just after the line faded closes, brings back and selects nothing", after == before, f"{before} -> {after}")

    # ⌘Z in the sidebar, while the line offers Undo.
    said = close_two("hand-8", "hand-9")
    n = len(hands())
    look_in_sidebar(m, """async () => { const bg = page.browser.extension.getBackgroundPage(); bg.smokeStale = await bg.viewFor((await page.browser.windows.getCurrent()).id); }""")  # the view as it is now, for below
    m.js(FOCUS_SIDEBAR)
    press(m, "z", CMD)
    back = m.js(H + """const w = main(); for (let i = 0; i < 50 && w.gBrowser.tabs.filter(t => /^hand-[89]$/.test(t.label)).length < 2; i++) await wait(100);
      return w.gBrowser.tabs.filter(t => /^hand-[89]$/.test(t.label)).length;""")
    now = in_sidebar(m, """() => doc.getElementById("note").classList.contains("shown") && doc.querySelector("#note .text").textContent""")
    check("⌘Z in the sidebar undoes what the line offers", back == 2 and len(hands()) == n + 2 and not now, f"{back} {n} {hands()}, the line: {said!r}, and after: {now!r}" + (f""", {look_in_sidebar(m, "() => page.browser.extension.getBackgroundPage().traces.slice(-8)")}""" if now else ""))

    # A view made before the background heard of Undo, and drawn after it: the line stays gone.
    # (The two cross on their way on a busy machine; here that view is sent again, by hand.)
    r = look_in_sidebar(m, """async () => {
      const bg = page.browser.extension.getBackgroundPage(), win = (await page.browser.windows.getCurrent()).id;
      const note = doc.getElementById("note"), stale = bg.smokeStale, real = bg.viewFor; let shown = 0;
      const o = new content.MutationObserver(() => { if (note.classList.contains("shown")) shown++; });
      o.observe(note, {attributes: true, attributeFilter: ["class"]});
      bg.viewFor = Components.utils.exportFunction(w => w === win ? bg.Promise.resolve(stale) : real.call(bg, w), bg);
      bg.viewSoon(win);
      await sleep(600);
      bg.viewFor = real; delete bg.smokeStale; o.disconnect();
      bg.viewSoon(win);
      await sleep(600);
      return {stale: !!stale?.note?.undo, shown, now: note.classList.contains("shown"), rows: [...doc.querySelectorAll("#tabs .tab .title")].filter(e => /^hand-[89]$/.test(e.textContent)).length};
    }""")
    check("a view made before Undo was heard does not bring the line back", r.get("stale") and r.get("shown") == 0 and not r.get("now") and r.get("rows") == 2, str(r))

    # ⌘W, with Firefox's closing animation: the row goes at once and does not come back.
    gone = m.js(H + IN_SIDEBAR + """const w = main(); Services.prefs.setIntPref("ui.prefersReducedMotion", 0); await wait(200);
      const t = w.gBrowser.tabs.find(x => x.label === "hand-10"); w.gBrowser.selectedTab = t; await wait(1500);
      w.gBrowser.removeTab(t, {animate: true});
      const animating = w.gBrowser.tabs.includes(t), seen = [];
      for (let i = 0; i < 25; i++) { await wait(100); seen.push(await inSidebar(() => !![...doc.querySelectorAll("#tabs .tab")].find(r => r.title.startsWith("hand-10")))); }
      Services.prefs.clearUserPref("ui.prefersReducedMotion");
      return {animating, seen: seen.join("").replace(/true/g, "1").replace(/false/g, "0")};""")
    check("⌘W's row goes at once, though Firefox keeps the tab a moment for its animation", gone["animating"] and "1" not in gone["seen"][10:], str(gone))

    # A double click on a menu item that draws a list in its place chooses nothing from that list.
    sidebar_mouse(m, """[...doc.querySelectorAll("#tabs .tab")].find(r => r.title.startsWith("hand-6"))""", 2)
    sidebar_until(m, """() => labels().includes("Move to space")""")
    item = hand_spot(m, """return box([...doc.querySelectorAll("#menu .item")].find(i => i.textContent === "Move to space"));""")
    hand(m, hand_to(item), hand_pause(100), *hand_click(), hand_pause(60), *hand_click())
    time.sleep(1)
    r = in_sidebar(m, """() => ({labels: labels(), back: !!doc.querySelector("#menu:not([hidden]) .item.back"), still: !![...doc.querySelectorAll("#tabs .tab")].find(r => r.title.startsWith("hand-6"))})""")
    sidebar_key(m, ESC)
    check("a double click on Move to space shows the spaces and chooses none", r["still"] and r["back"] and len(r["labels"]) > 2, str(r))

    # A saved tab's ×: it says it unloads, and the row stays as quiet as it now is under the pointer.
    folder = sidebar_page(m, """const space = spaces().find(s => s.active).id;
      send({type: "newFolder", space, name: "Hand"});
      for (let i = 0; i < 50 && !folders().some(f => f.name === "Hand"); i++) await wait(100);
      const key = [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "Hand").dataset.folderHead;
      for (const name of ["hand-11", "hand-12"]) send({type: "moveTab", tabId: Number([...doc.querySelectorAll("#tabs .tab")].find(r => r.title.startsWith(name)).dataset.tab), folder: key, before: null});
      for (let i = 0; i < 50 && folders().find(f => f.name === "Hand").tabs.length < 2; i++) await wait(100);
      return key;""")
    m.js(H + """const w = main(); for (const t of [...w.gBrowser.tabs]) if (url(t).includes("/sidebar/sidebar.html")) w.gBrowser.removeTab(t); await wait(800); return 1;""")
    p = hand_spot(m, """const r = row("hand-11"); r.scrollIntoView({block: "center"}); const c = r.querySelector(".close"); return {...box(c), tip: c.title, loaded: !r.classList.contains("unloaded")};""")
    hand(m, hand_to(p), hand_pause(200), *hand_click())
    r = sidebar_until(m, """() => { const r = [...doc.querySelectorAll("#tabs .tab")].find(r => r.title.startsWith("hand-11")); if (!r?.classList.contains("unloaded")) return null;
      const muted = content.getComputedStyle(doc.documentElement).getPropertyValue("--muted"), probe = doc.createElement("span"); probe.style.color = muted; doc.body.append(probe);
      const out = {dim: r.classList.contains("still-dim"), quiet: content.getComputedStyle(r.querySelector(".title")).color === content.getComputedStyle(probe).color, tip: r.querySelector(".close").title, inFolder: !!r.closest(".folder")};
      probe.remove(); return out; }""")
    hand(m, hand_to(away))
    awake = in_sidebar(m, """() => [...doc.querySelectorAll("#tabs .tab")].find(r => r.title.startsWith("hand-11"))?.classList.contains("still-dim")""")
    check("× on a loaded saved tab says it unloads, and afterwards that it removes", p["loaded"] and p["tip"].startswith("Unload") and r and r["tip"] == "Remove from the folder", f"{p} {r}")
    check("the row it unloads stays dim under the pointer, in its folder, until the pointer leaves", r and r["dim"] and r["quiet"] and r["inFolder"] and awake is False, f"{r} {awake}")

    # A closed folder shows its selected tab; a click on another row leaves that row there,
    # so the row clicked does not jump up under the pointer, until the pointer leaves the list.
    m.js(H + """const w = main(); w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => t.label === "hand-12"); await wait(1500); return 1;""")
    head = hand_spot(m, """const h = [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.title === "Hand"); h.scrollIntoView({block: "center"}); return box(h);""")
    hand(m, hand_to(head), *hand_click())
    sidebar_until(m, """() => [...doc.querySelectorAll("#tabs .folder")].find(f => f.querySelector(".head").title === "Hand")?.classList.contains("collapsed")""")
    time.sleep(1)
    p = hand_spot(m, """const r = row("hand-6"); r.scrollIntoView({block: "nearest"}); return {...box(r), shown: row("hand-12")?.offsetParent !== null};""")
    hand(m, hand_to(p), *hand_click())
    m.js(H + """const w = main(); for (let i = 0; i < 30 && w.gBrowser.selectedTab.label !== "hand-6"; i++) await wait(100); await wait(800); return 1;""")
    clicked = hand_spot(m, """return {top: box(row("hand-6")).top, shown: row("hand-12")?.offsetParent !== null};""")
    hand(m, hand_to(away))
    time.sleep(0.5)
    left = hand_spot(m, """return {top: box(row("hand-6")).top, shown: row("hand-12")?.offsetParent !== null};""")
    check("a click below a closed folder leaves its selected tab's row there until the pointer leaves the list", p["shown"] and clicked["shown"] and clicked["top"] == p["top"] and not left["shown"], f"{p} {clicked} {left}")

    # A double click on a folder's head renames it, with nothing folding first.
    in_sidebar(m, """() => { const f = [...doc.querySelectorAll("#tabs .folder")].find(f => f.querySelector(".head").title === "Hand");
      doc.documentElement.dataset.folds = ""; new content.MutationObserver(() => { doc.documentElement.dataset.folds += f.classList.contains("collapsed") ? "c" : "o"; }).observe(f, {attributes: true, attributeFilter: ["class"]});
      return f.classList.contains("collapsed"); }""")
    # (In view first: in a list grown long it can be out of view, and the clicks would land elsewhere.)
    head = hand_spot(m, """const h = [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.title === "Hand"); h.scrollIntoView({block: "nearest"}); return box(h);""")
    hand(m, hand_to(head), hand_pause(100), *hand_click(), *hand_click())  # (no pause: a busy machine adds its own)
    r = sidebar_until(m, """() => doc.querySelector("#tabs .folder.renaming input") && {folds: doc.documentElement.dataset.folds, collapsed: doc.querySelector("#tabs .folder.renaming").classList.contains("collapsed")}""")
    sidebar_key(m, ESC)
    check("a double click on a closed folder's head renames it, and nothing folds or unfolds first", r and r["collapsed"] and "o" not in r["folds"], str(r))
    hand(m, hand_to(away))

    # ⌘W and ⌘⇧T on a saved tab, with the list at its top: the list does not move by itself,
    # and the tab is back in its folder. Then removed for good (× on its placeholder) and
    # brought back with ⌘⇧T: in its folder again, not among today's tabs.
    m.js(H + """const w = main(), [pages, ctx] = args;
      for (let i = 1; i <= 30; i++) { w.gBrowser.addTrustedTab(pages + "/titled?fill-" + i, {userContextId: ctx, inBackground: true}); await wait(40); }
      for (let i = 0; i < 100 && w.gBrowser.tabs.filter(t => t.label.startsWith("fill-")).length < 30; i++) await wait(100);
      await wait(2000); return 1;""", m.pages, int(here.split("-")[-1]))
    # (Moved into its folder again, so that it lies last in the window, as a tab put in a folder
    # does: given back before Tidier has taken it in, it would be drawn there, below all of today's.)
    sidebar_page(m, """send({type: "foldFolder", key: args[0], collapsed: false});
      for (const name of ["hand-11", "hand-12"]) send({type: "moveTab", tabId: Number([...doc.querySelectorAll("#tabs .tab")].find(r => r.title.startsWith(name)).dataset.tab), folder: args[0], before: null});
      await wait(800); return 1;""", folder)
    m.js(H + """const w = main(); for (const t of [...w.gBrowser.tabs]) if (url(t).includes("/sidebar/sidebar.html")) w.gBrowser.removeTab(t); await wait(500); return 1;""")
    order = m.js(H + """return main().gBrowser.tabs.filter(t => !t.hidden).slice(-2).map(t => t.label);""")
    long = in_sidebar(m, """() => { const l = doc.getElementById("tabs"); return l.scrollHeight - l.clientHeight; }""")
    ctrl_w = H + IN_SIDEBAR + """const w = main(), name = args[0]; Services.prefs.setIntPref("ui.prefersReducedMotion", 0); w.focus();
      w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => t.label === name); await wait(1500);
      await inSidebar(() => { doc.getElementById("tabs").scrollTop = 0; return 1; }); await wait(300);
      w.BrowserCommands.closeTabOrWindow(); await wait(2000);
      const where = () => inSidebar(n => { const rows = [...doc.querySelectorAll("#tabs .tab")].filter(r => r.title.startsWith(n));
        return {top: doc.getElementById("tabs").scrollTop, rows: rows.length, inFolder: rows.every(r => !!r.closest(".folder")), loaded: rows.some(r => !r.classList.contains("unloaded"))}; }, name);
      return {closed: await where()};"""
    ctrl_shift_t = H + IN_SIDEBAR + """const w = main(), name = args[0];
      const where = () => inSidebar(n => { const rows = [...doc.querySelectorAll("#tabs .tab")].filter(r => r.title.startsWith(n));
        return {top: doc.getElementById("tabs").scrollTop, rows: rows.length, inFolder: rows.every(r => !!r.closest(".folder")), loaded: rows.some(r => !r.classList.contains("unloaded"))}; }, name);
      w.SessionStore.undoCloseTab(w, 0); const seen = [];
      for (let i = 0; i < 30; i++) { await wait(100); seen.push(await where()); }
      Services.prefs.clearUserPref("ui.prefersReducedMotion");
      return {tops: [...new Set(seen.map(s => s.top))], last: seen.at(-1), selected: w.gBrowser.selectedTab.label};"""
    closed = m.js(ctrl_w, "hand-12")
    back = m.js(ctrl_shift_t, "hand-12")
    check("⌘W on a loaded saved tab leaves its row in its folder, unloaded", closed["closed"]["rows"] == 1 and closed["closed"]["inFolder"] and not closed["closed"]["loaded"], str(closed))
    check("⌘⇧T brings it back in its folder, loaded, and the list does not move by itself", len(back["tops"]) == 1 and back["last"]["rows"] == 1 and back["last"]["inFolder"] and back["last"]["loaded"] and back["selected"] == "hand-12" and order == ["hand-11", "hand-12"] and long > 200, f"{back} {order} {long}")
    # Removed for good: × on its placeholder, after a ⌘W that left the page in Recently Closed.
    m.js(ctrl_w, "hand-11")
    p = hand_spot(m, """const r = row("hand-11"); r.scrollIntoView({block: "center"}); return box(r.querySelector(".close"));""")
    hand(m, hand_to(p), hand_pause(150), *hand_click(), hand_to(away))
    gone = m.js(H + """const w = main(); for (let i = 0; i < 30 && w.gBrowser.tabs.some(t => t.label === "hand-11"); i++) await wait(100); await wait(1500);
      return !w.gBrowser.tabs.some(t => t.label === "hand-11");""")
    back = m.js(ctrl_shift_t, "hand-11")
    check("a saved tab removed for good and brought back with ⌘⇧T is in its folder again", gone and back["last"]["rows"] == 1 and back["last"]["inFolder"] and back["selected"] == "hand-11", f"{gone} {back}")

    # The sidebar made narrower: the lines above the list wrap and the list shows less, and the
    # selected tab, the last row and wholly in view, stays wholly in view (clear of the fade at the end).
    # (Once the quiet line has gone: its room makes the list shorter for a while.)
    sidebar_until(m, """() => !doc.getElementById("note").classList.contains("in-room")""", timeout=25)
    r = m.js(H + IN_SIDEBAR + """const w = main(), box = w.document.getElementById("sidebar-box"), before = box.style.width;
      box.style.width = "420px"; await wait(500);
      const name = await inSidebar(() => [...doc.querySelectorAll("#tabs .tab")].at(-1).title.split("\\n")[0]);
      w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => t.label === name); await wait(1500);
      await inSidebar(() => { const l = doc.getElementById("tabs"); l.scrollTop = l.scrollHeight; return 1; }); await wait(300);
      const where = () => inSidebar(() => { const l = doc.getElementById("tabs").getBoundingClientRect(), r = doc.querySelector("#tabs .tab.active")?.getBoundingClientRect();
        return {bottom: Math.round(r?.bottom), end: Math.round(l.bottom), height: Math.round(l.height)}; });
      const wide = await where();
      box.style.width = "220px"; await wait(800);
      const narrow = await where();
      box.style.width = before; await wait(500);
      return {name, wide, narrow};""")
    check("a narrower sidebar keeps the selected tab wholly in view", r["narrow"]["height"] < r["wide"]["height"] and r["narrow"]["bottom"] <= r["narrow"]["end"] - 18, str(r))

    sidebar_page(m, """send({type: "deleteFolder", key: args[0]}); await wait(800); return 1;""", folder)
    m.js(H + """Services.prefs.clearUserPref("general.autoScroll"); await removeWhere((w, t) => /^(hand|fill)-/.test(t.label) || url(t).includes("/sidebar/sidebar.html")); return 1;""")
    # The pointer left where it reaches nothing: at rest over the page it would be over the rows
    # of a sidebar page the next groups open in a tab, and Firefox tells a row that comes under it.
    hand(m, {"type": "pointerMove", "x": 1, "y": 1, "duration": 0, "origin": "viewport"})


# What the selection's checks do in the sidebar: real events on the real rows, carrying
# the modifier this machine uses, and waits for a state rather than for a time.
PICKING = """
      const MOD = (await page.browser.runtime.getPlatformInfo()).os === "mac" ? "metaKey" : "ctrlKey";
      const press = (e, mods = {}) => { for (const type of ["mousedown", "mouseup", "click"]) e.dispatchEvent(new page.MouseEvent(type, {bubbles: true, cancelable: true, button: 0, ...mods})); };
      const add = e => press(e, {[MOD]: true}), range = e => press(e, {shiftKey: true});
      const idOf = e => Number(e.dataset.tab);
      const picks = () => [...doc.querySelectorAll(".picked")].map(idOf);
      const row = id => doc.querySelector(`#tabs .tab[data-tab="${id}"]`), tile = id => doc.querySelector(`#essentials .tile[data-tab="${id}"]`);
      const ids = () => plainTabs().map(idOf), tileIds = () => [...doc.querySelectorAll("#essentials .tile")].map(idOf);
      const head = name => [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === name);
      const inFolder = name => [...head(name).parentElement.querySelectorAll(".tab")].map(idOf);
      const activeId = async () => (await page.browser.tabs.query({active: true, currentWindow: true}))[0].id;
      const activeSpace = () => spaces().find(s => s.active).id;
      const until = async (test, ms = 15000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (test()) return true; await wait(50); } return !!test(); };
      const key = k => doc.body.dispatchEvent(new page.KeyboardEvent("keydown", {key: k, bubbles: true, cancelable: true}));
      const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
      // A click shows as selected at once (sidebar.js, showSelected); selected it is once a view agrees, which draws it with its state.
      const shownSelected = id => { const e = row(id) || tile(id); return !!e?.classList.contains("active") && e.dataset.state !== undefined; };
      const select = async e => { const id = idOf(e); press(e); await until(() => shownSelected(id)); };
      const keysOf = list => Promise.all(list.map(id => page.browser.sessions.getTabValue(id, "syncKey")));
      const drag = (from, to, below = false, right = false) => {
        const data = new page.DataTransfer(), box = to.getBoundingClientRect();
        const at = {bubbles: true, cancelable: true, clientX: right ? box.right - 2 : box.left + 5, clientY: box.top + (below ? box.height - 1 : 1), dataTransfer: data};
        from.dispatchEvent(new page.DragEvent("dragstart", at));
        to.dispatchEvent(new page.DragEvent("dragover", at));
        to.dispatchEvent(new page.DragEvent("drop", at));
        from.dispatchEvent(new page.DragEvent("dragend", at));
      };
"""


def order_everywhere(m, keys):
    """Each window's order of these tabs, once it is as wanted (or the time is up)."""
    return m.js(H + """const [want] = args; let got;
      for (let i = 0; i < 100; i++) {
        got = wins().map(w => w.gBrowser.tabs.map(t => value(w, t, "syncKey")).filter(k => want.includes(k)));
        if (got.every(g => JSON.stringify(g) === JSON.stringify(want))) break;
        await wait(100);
      }
      return got;""", keys)


def alone_selection(m):
    # Tabs to use up: at once, so this group need not wait for each lot. The last two
    # are opened in the second window, so here they are placeholders.
    space = sidebar_page(m, """return spaces().find(s => s.active).id;""")
    fresh = m.js(H + """const ctx = Number(args[0].split("-").pop());
      if (!other()) { const w = main().OpenBrowserWindow(); w.__smoke = true; await wait(4000); }
      main().focus();
      for (let i = 0; i < 28; i++) { (i < 26 ? main() : other()).gBrowser.addTrustedTab("https://example.org/?smoke-pick-" + i, {userContextId: ctx, inBackground: true}); await wait(100); }
      let keys;
      for (let i = 0; i < 300; i++) {  // until each window has all of them, with a record
        const all = (await storage(args[1], ["syncedTabs"])).syncedTabs;
        keys = Object.keys(all).filter(k => (all[k].url || "").includes("smoke-pick"));
        if (keys.length === 28 && wins().every(w => w.gBrowser.tabs.filter(t => keys.includes(value(w, t, "syncKey"))).length === 28)) break;
        await wait(100);
      }
      return keys;""", space, EXT_ID)
    r = sidebar_page(m, PICKING + """
      // The test's own page is a row too: last, out of the way.
      const own = [...doc.querySelectorAll("#tabs > .tab")].find(x => x.querySelector(".title").textContent === "Tidier");
      if (own) { send({type: "moveTab", tabId: idOf(own), before: null, folder: null}); await until(() => [...doc.querySelectorAll("#tabs > .tab")].at(-1) === own); }
      const space = activeSpace();
      send({type: "newFolder", space, name: "Picks"});
      await until(() => head("Picks"));
      send({type: "newFolder", space, name: "Picks closed"});
      await until(() => head("Picks closed"));
      const rowsNow = ids(), rowKeys = await keysOf(rowsNow), fresh = rowsNow.filter((id, i) => args[0].includes(rowKeys[i]));
      const unloaded = id => row(id).classList.contains("unloaded");
      const [f1, f2, g1, r0, r1, r2, r3, r4, r5, a, b, c, d, e, f, y1, y2, y3, s1, s2, s3, h1, h2, h3, h4, h5] = fresh.filter(id => !unloaded(id)), [p1, p2] = fresh.filter(unloaded);
      const open = head("Picks").dataset.folderHead, closed = head("Picks closed").dataset.folderHead;
      send({type: "moveTab", tabId: f1, before: null, folder: open});
      send({type: "moveTab", tabId: f2, before: null, folder: open});
      send({type: "moveTab", tabId: g1, before: null, folder: closed});
      await until(() => inFolder("Picks").length === 2 && inFolder("Picks closed").length === 1);
      send({type: "foldFolder", key: closed, collapsed: true});
      await until(() => head("Picks closed").parentElement.classList.contains("collapsed"));
      const out = {};

      // Add and remove; the first click takes the selected tab in; the page stays.
      await select(row(r0));
      const selected = await activeId();
      out.selectedFirst = selected === r0;
      add(row(r2));
      out.first = same(picks(), [r0, r2]);
      add(row(r3));
      out.added = same(picks(), [r0, r2, r3]);
      add(row(r2));
      out.removed = same(picks(), [r0, r3]);
      out.forMenu = same(Array.from(page.selectedTabs(r3)), [r0, r3]) && same(Array.from(page.selectedTabs(r1)), [r1]);
      await wait(400);
      out.pageStays = (await activeId()) === selected && row(r0).classList.contains("active");

      // A press on a picked row keeps them until release, and a plain click then ends it.
      row(r3).dispatchEvent(new page.MouseEvent("mousedown", {bubbles: true, cancelable: true, button: 0}));
      out.pressed = same(picks(), [r0, r3]);
      row(r3).dispatchEvent(new page.MouseEvent("mouseup", {bubbles: true, cancelable: true, button: 0}));
      row(r3).dispatchEvent(new page.MouseEvent("click", {bubbles: true, cancelable: true, button: 0}));
      out.released = picks().length === 0;
      await until(() => shownSelected(r3));
      out.plainSelects = (await activeId()) === r3;

      // A range: from the selected tab, again from there, over a folder as drawn.
      range(row(r5));
      out.range = same(picks(), [r3, r4, r5]);
      range(row(r1));
      out.rangeAgain = same(picks(), [r1, r2, r3]);
      range(row(f1));
      out.overFolders = same(picks(), [f1, f2, ...ids().slice(0, ids().indexOf(r3) + 1)]);
      out.notClosedFolder = !picks().includes(g1) && !doc.querySelector(".folder.collapsed .picked");
      await wait(400);
      out.pageStaysRange = (await activeId()) === r3;

      // What clears: empty space, Esc after the menu, a space switch.
      press(doc.getElementById("tabs"));
      out.emptySpace = picks().length === 0;
      add(row(r1));
      doc.getElementById("menu").hidden = false;
      key("Escape");
      out.escMenu = doc.getElementById("menu").hidden && same(picks(), [r1, r3]);
      key("Escape");
      out.escPicks = picks().length === 0;
      key("ArrowDown");
      const hadCursor = !!doc.querySelector(".cursor");
      key("Escape");
      out.escCursor = hadCursor && !doc.querySelector(".cursor");
      add(row(r2));
      const there = spaces().find(s => !s.active && s.id !== "firefox-container-4").id;
      const hadPicks = picks().length === 2;
      send({type: "space", space: there});
      await until(() => activeSpace() === there);
      out.spaceSwitch = hadPicks && picks().length === 0;
      send({type: "space", space});
      await until(() => activeSpace() === space && row(r3)?.classList.contains("active"));
      out.spaceBack = picks().length === 0;

      // Another tab selected by other means than a click here: you have moved on.
      add(row(r2));
      const hadThem = same(picks(), [r2, r3]);
      await page.browser.tabs.update(r1, {active: true});
      await until(() => row(r1).classList.contains("active") && !picks().length);
      out.movedOn = hadThem && picks().length === 0;
      await select(row(r3));

      // One kind: a tile and a row cannot both be picked.
      add(row(r2));
      add(doc.querySelector("#essentials .tile"));
      out.tileAlone = doc.querySelectorAll(".tile.picked").length === 1 && !doc.querySelector(".tab.picked");
      range(row(r2));
      out.rowsAlone = !doc.querySelector(".tile.picked") && same(picks(), [r2, r3]);

      // A row drawn again keeps its mark.
      send({type: "mute", tabId: r2, muted: true});
      await until(() => row(r2).querySelector(".sound"));
      out.redraw = !!row(r2).querySelector(".sound") && same(picks(), [r2, r3]);
      send({type: "mute", tabId: r2, muted: false});
      await until(() => !row(r2).querySelector(".sound"));
      out.redrawBack = same(picks(), [r2, r3]);

      // A row in a folder you close leaves the selection: nothing acts on what you cannot see.
      add(row(f1));
      const hadF1 = picks().includes(f1);
      send({type: "foldFolder", key: open, collapsed: true});
      await until(() => !picks().includes(f1));
      out.foldLeaves = hadF1 && same(picks(), [r2, r3]);
      send({type: "foldFolder", key: open, collapsed: false});
      await until(() => !head("Picks").parentElement.classList.contains("collapsed"));
      out.unfoldStaysOut = same(picks(), [r2, r3]);
      key("Escape");
      return {out, f1, f2, g1, r0, r1, r2, r3, r4, r5, a, b, c, d, e, f, y1, y2, y3, s1, s2, s3, h1, h2, h3, h4, h5, p1, p2, space, there, open, closed};""", fresh)
    out = r.get("out", {})
    check("the first ⌘-click takes the selected tab in", out.get("selectedFirst") and out.get("first"), str(r))
    check("⌘-click adds and removes", out.get("added") and out.get("removed"), str(out))
    check("the tab menu's list is the selection if the tab is in it, else that tab", out.get("forMenu"), str(out))
    check("the selected page does not change while you pick", out.get("pageStays") and out.get("pageStaysRange"), str(out))
    check("a press on a picked row keeps the selection until release; a plain click then ends it and selects", out.get("pressed") and out.get("released") and out.get("plainSelects"), str(out))
    check("⇧-click takes a range from the selected tab, and again changes it", out.get("range") and out.get("rangeAgain"), str(out))
    check("a range goes over the rows as drawn, past a folder, not into a closed one", out.get("overFolders") and out.get("notClosedFolder"), str(out))
    check("a click on empty space clears", out.get("emptySpace"), str(out))
    check("Esc goes back a step at a time: menu, selection, cursor", out.get("escMenu") and out.get("escPicks") and out.get("escCursor"), str(out))
    check("a space switch clears", out.get("spaceSwitch") and out.get("spaceBack"), str(out))
    check("another tab selected (⌃Tab, a link) ends the selection", out.get("movedOn"), str(out))
    check("a tile and a row cannot both be picked", out.get("tileAlone") and out.get("rowsAlone"), str(out))
    check("the selection survives a redraw", out.get("redraw") and out.get("redrawBack"), str(out))
    check("a row in a folder you close leaves the selection", out.get("foldLeaves") and out.get("unfoldStaysOut"), str(out))
    tabs = {k: v for k, v in r.items() if k != "out"}

    # Carrying: three rows that are not together go into a folder, in order, in every window.
    r = sidebar_page(m, PICKING + """
      const [{f1, f2, r0, r2, r3}] = args, out = {};
      await select(doc.querySelector("#essentials .tile"));
      add(row(r0)); add(row(r2)); add(row(r3));
      out.picked = same(picks(), [r0, r2, r3]);
      drag(row(r2), head("Picks"));
      await until(() => inFolder("Picks").length === 5);
      out.intoFolder = same(inFolder("Picks"), [f1, f2, r0, r2, r3]);
      out.stillPicked = same(picks(), [r0, r2, r3]);
      return {out, keys: await keysOf([f1, f2, r0, r2, r3])};""", tabs)
    out = r.get("out", {})
    check("a drag from a picked row carries them all into a folder, in order", out.get("picked") and out.get("intoFolder") and out.get("stillPicked"), str(r))
    got = order_everywhere(m, r.get("keys"))
    check("a second window has the same order in the folder", len(got) > 1 and all(g == r.get("keys") for g in got), str(got))

    # Out of the folder to a place; a row that is not picked moves alone; dropped on their own, the order holds.
    r = sidebar_page(m, PICKING + """
      const [{f1, f2, r0, r1, r2, r3, r4, r5}] = args, out = {};
      const mine = () => ids().filter(x => [r0, r1, r2, r3, r4, r5].includes(x));
      drag(row(r0), row(r1));
      await until(() => inFolder("Picks").length === 2 && same(mine(), [r0, r2, r3, r1, r4, r5]));
      out.outOfFolder = same(inFolder("Picks"), [f1, f2]) && same(mine(), [r0, r2, r3, r1, r4, r5]);
      drag(row(r4), row(r0));
      await until(() => same(mine(), [r4, r0, r2, r3, r1, r5]));
      out.loneRow = same(mine(), [r4, r0, r2, r3, r1, r5]) && same(picks(), [r0, r2, r3]);
      drag(row(r0), row(r3), true);
      await wait(800);
      out.ontoOwn = same(mine(), [r4, r0, r2, r3, r1, r5]) && same(picks(), [r0, r2, r3]);
      add(row(r5));
      drag(row(r5), row(r2), true);
      await until(() => same(mine(), [r4, r0, r2, r3, r5, r1]));
      out.gathered = same(mine(), [r4, r0, r2, r3, r5, r1]);
      // A row with no record (the test's own page, like a new tab page) is a place too.
      const own = [...doc.querySelectorAll("#tabs > .tab")].at(-1);
      drag(row(r4), own);
      await until(() => row(r4).nextElementSibling === own);
      out.beforeUnsynced = row(r4).nextElementSibling === own;
      return {out, keys: await keysOf(mine())};""", tabs)
    out = r.get("out", {})
    check("picked rows dragged out of a folder are ordinary tabs, in order, where you put them", out.get("outOfFolder"), str(r))
    check("a row that is not picked moves alone, and the selection stays", out.get("loneRow"), str(out))
    check("dropped on themselves, picked rows stay as they were", out.get("ontoOwn"), str(out))
    check("picked rows apart are brought together where you drop them", out.get("gathered"), str(out))
    check("a tab dropped above a row with no record lands there", out.get("beforeUnsynced"), str(out))
    got = order_everywhere(m, r.get("keys"))
    check("a second window has the same order of the tabs", len(got) > 1 and all(g == r.get("keys") for g in got), str(got))

    # To a space's dot, the selected tab among them: there in order, in every window, and you stay.
    r = sidebar_page(m, PICKING + """
      const [{r0, r2, r3}] = args;
      press(doc.getElementById("tabs"));
      await select(row(r0));
      add(row(r2)); add(row(r3));
      return {picked: same(picks(), [r0, r2, r3]), keys: await keysOf([r0, r2, r3])};""", tabs)
    urls = m.js(H + """const all = (await storage(args[1], ["syncedTabs"])).syncedTabs; return args[0].map(k => all[k]?.url);""", r.get("keys"), EXT_ID)
    r = sidebar_page(m, PICKING + """
      const [{r0, r2, r3, space, there}] = args;
      drag(row(r2), doc.querySelector(`#spaces .space[data-space="${there}"]`));
      await until(() => !row(r0) && !row(r2) && !row(r3));
      await until(() => tileIds().length && doc.querySelector(".active"));
      return {gone: !row(r0) && !row(r2) && !row(r3), stayed: activeSpace() === space, picks: picks().length};""", tabs)
    check("picked rows dragged to a space's dot leave this space, and you stay", r.get("gone") and r.get("stayed") and r.get("picks") == 0, str(r))
    moved = m.js(H + """const [urls, ctx, ext] = args, wanted = JSON.stringify(urls); let got;
      for (let i = 0; i < 100; i++) {
        const all = (await storage(ext, ["syncedTabs"])).syncedTabs;
        got = wins().map(w => w.gBrowser.tabs.filter(t => urls.includes(all[value(w, t, "syncKey")]?.url) && t.userContextId === ctx).map(t => all[value(w, t, "syncKey")].url));
        if (got.every(g => JSON.stringify(g) === wanted)) break;
        await wait(100);
      }
      return got;""", urls, int(tabs["there"].split("-")[-1]), EXT_ID)
    check("they are in the other space in order, in every window", len(moved) > 1 and all(g == urls for g in moved), str(moved))

    # Closing: ⌫ with the selected tab among them; × and a middle click; another row's own ×.
    r = sidebar_page(m, PICKING + """
      const [{r1, r4, r5, space}] = args;
      await select(row(r1));
      add(row(r4)); add(row(r5));
      const had = same(picks(), [r5, r1, r4]);
      key("Backspace");
      await until(() => !row(r1) && !row(r4) && !row(r5));
      await until(() => doc.querySelector(".active"));
      return {had, gone: !row(r1) && !row(r4) && !row(r5), stayed: activeSpace() === space, picks: picks().length};""", tabs)
    check("⌫ closes all picked rows, and you stay in the space", r.get("had") and r.get("gone") and r.get("stayed") and r.get("picks") == 0, str(r))
    r = sidebar_page(m, PICKING + """
      const [{a, b, c, d, e, f}] = args, out = {};
      await select(doc.querySelector("#essentials .tile"));
      add(row(a)); add(row(b));
      press(row(c).querySelector(".close"));
      await until(() => !row(c));
      out.ownClose = !row(c) && same(picks(), [a, b]);
      press(row(a).querySelector(".close"));
      await until(() => !row(a) && !row(b));
      out.close = !row(a) && !row(b) && picks().length === 0;
      add(row(d)); add(row(e));
      row(e).dispatchEvent(new page.MouseEvent("auxclick", {bubbles: true, cancelable: true, button: 1}));
      await until(() => !row(d) && !row(e));
      out.middle = !row(d) && !row(e) && !!row(f) && picks().length === 0;
      row(f).dispatchEvent(new page.MouseEvent("auxclick", {bubbles: true, cancelable: true, button: 1}));
      await until(() => !row(f));
      out.middleOne = !row(f);
      return out;""", tabs)
    check("× on a row that is not picked closes that row only", r.get("ownClose"), str(r))
    check("× on a picked row closes them all", r.get("close"), str(r))
    check("a middle click on a picked row closes them all", r.get("middle"), str(r))
    check("a middle click with nothing picked closes that row", r.get("middleOne"), str(r))

    # Saved tabs closed together come back as placeholders where they were, here and elsewhere.
    r = sidebar_page(m, PICKING + """
      const [{f1, f2, s1, s2, s3, open}] = args;
      for (const tabId of [s1, s2, s3]) send({type: "moveTab", tabId, before: f2, folder: open});
      await until(() => same(inFolder("Picks"), [f1, s1, s2, s3, f2]));
      const keys = await keysOf(inFolder("Picks"));
      await wait(300);
      await select(row(s2));
      add(row(s1)); add(row(s3));
      const had = same(picks(), [s1, s2, s3]);
      key("Backspace");
      await until(() => ![s1, s2, s3].some(row) && inFolder("Picks").length === 5);
      let got;
      for (let i = 0; i < 100; i++) { got = await keysOf(inFolder("Picks")); if (same(got, keys)) break; await wait(100); }
      await until(() => doc.querySelector(".active"));
      return {had, keys, got, unloaded: inFolder("Picks").slice(1, 4).every(id => row(id).classList.contains("unloaded"))};""", tabs)
    check("saved tabs closed together are unloaded where they were, in order", r.get("had") and r.get("keys") == r.get("got") and r.get("unloaded"), str(r))
    got = order_everywhere(m, r.get("keys"))
    check("a second window has the same order in the folder after closing them", len(got) > 1 and all(g == r.get("keys") for g in got), str(got))

    # What is left behind by a row that goes at the wrong moment.
    r = sidebar_page(m, PICKING + """
      const [{h1, h2, h3, h4, h5}] = args, out = {};
      await select(doc.querySelector("#essentials .tile"));
      add(row(h2)); add(row(h3));
      for (let i = 0; i < 80 && !doc.querySelector(`.cursor[data-tab="${h1}"]`); i++) key("ArrowDown");
      out.cursorOn = !!doc.querySelector(`.cursor[data-tab="${h1}"]`);
      send({type: "close", tabId: h1});
      await until(() => !row(h1) && !doc.querySelector(".cursor"));
      out.cursorGone = !doc.querySelector(".cursor");
      const tiles0 = tileIds().length;
      key("Backspace");
      await until(() => !row(h2) && !row(h3));
      out.backspace = !row(h2) && !row(h3) && tileIds().length === tiles0;
      add(row(h4)); add(row(h5));
      const carrying = () => doc.documentElement.classList.contains("carrying");
      row(h4).dispatchEvent(new page.DragEvent("dragstart", {bubbles: true, cancelable: true, dataTransfer: new page.DataTransfer()}));
      await until(carrying);
      out.carrying = carrying();
      send({type: "close", tabId: h4});
      await until(() => !row(h4) && !carrying());
      out.notFaded = !carrying() && same(picks(), [h5]);
      key("Escape");
      return out;""", tabs)
    check("a cursor on a tab that has gone is gone too, and ⌫ closes the picked rows, not another", r.get("cursorOn") and r.get("cursorGone") and r.get("backspace"), str(r))
    check("the row you drag closes meanwhile: the others do not stay faded", r.get("carrying") and r.get("notFaded"), str(r))

    # The selected tab, and placeholders Firefox would select in turn: all closed, in every window.
    r = sidebar_page(m, PICKING + """
      const [{y3, p1, p2}] = args;
      const placeholders = row(p1).classList.contains("unloaded") && row(p2).classList.contains("unloaded");
      await select(row(y3));
      add(row(p1)); add(row(p2));
      const keys = await keysOf([y3, p1, p2]);
      key("Backspace");
      await until(() => !row(y3) && !row(p1) && !row(p2));
      return {placeholders, keys, gone: !row(y3) && !row(p1) && !row(p2)};""", tabs)
    left = m.js(H + """const [keys] = args; let left;
      for (let i = 0; i < 100; i++) { left = wins().flatMap(w => w.gBrowser.tabs.filter(t => keys.includes(value(w, t, "syncKey")))).length; if (!left) break; await wait(100); }
      return left;""", r.get("keys"))
    check("closing the selected tab and placeholders together closes them all, in every window", r.get("placeholders") and r.get("gone") and left == 0, str([r, left]))

    # Essentials: two rows to the essentials, the two tiles among them, and back, each in order.
    r = sidebar_page(m, PICKING + """
      const [{y1, y2}] = args, out = {};
      await select(doc.querySelector("#essentials .tile"));
      const tiles0 = tileIds();
      add(row(y1)); add(row(y2));
      out.rowsOnly = same(picks(), [y1, y2]);
      out.keys = await keysOf([y1, y2]);
      // Carried, and at once on to the essentials: the selection stays after a drop for this.
      drag(row(y1), doc.getElementById("tabs"));
      drag(row(y1), tile(tiles0.at(-1)), false, true);  // on the right of the last tile: after it
      await until(() => tileIds().length === tiles0.length + 2);
      out.pinned = same(tileIds(), [...tiles0, y1, y2]);
      out.pinnedLeft = picks().length === 0;
      await select(plainTabs()[0]);
      add(tile(y1)); add(tile(y2));
      out.tilesOnly = same(picks(), [y1, y2]);
      drag(tile(y2), tile(tiles0[0]));
      await until(() => same(tileIds(), [y1, y2, ...tiles0]));
      out.tilesMoved = same(tileIds(), [y1, y2, ...tiles0]);
      return out;""", tabs)
    check("picked rows dragged to the essentials are essentials, in order", r.get("rowsOnly") and r.get("pinned") and r.get("pinnedLeft"), str(r))
    left = m.js(H + """const [keys, ext] = args; let left;
      for (let i = 0; i < 100; i++) {
        const all = (await storage(ext, ["syncedTabs"])).syncedTabs;
        left = {records: keys.filter(k => all[k]).length, tabs: wins().flatMap(w => w.gBrowser.tabs.filter(t => keys.includes(value(w, t, "syncKey")))).length};
        if (!left.records && !left.tabs) break;
        await wait(100);
      }
      return left;""", r.get("keys"), EXT_ID)
    check("carried and at once dragged to the essentials, they are not ordinary tabs as well", left == {"records": 0, "tabs": 0}, str(left))
    check("picked essentials dragged among the essentials stay in order", r.get("tilesOnly") and r.get("tilesMoved"), str(r))
    pins = m.js(H + """let got;
      for (let i = 0; i < 100; i++) { got = wins().map(w => w.gBrowser.tabs.filter(t => t.pinned).map(t => ek(w, t))); if (got.every(g => JSON.stringify(g) === JSON.stringify(got[0]))) break; await wait(100); }
      return got;""")
    check("a second window has the same order of essentials", len(pins) > 1 and all(g == pins[0] for g in pins), str(pins))
    # Closed together, with the selected one: back in their places, unloaded, once each.
    r = sidebar_page(m, PICKING + """
      const [{y1, y2}] = args, before = tileIds(), two = before.filter(id => id !== y1 && id !== y2).slice(0, 2);
      await select(tile(two[0]));
      add(tile(two[1]));
      const had = same(picks(), two);
      key("Backspace");
      await until(() => tileIds().length === before.length && !two.some(tile));
      await until(() => tileIds().every(id => tile(id)) && doc.querySelector(".active"));
      const at = tileIds();
      return {had, n: at.length === before.length, kept: at.includes(y1) && at.includes(y2), unloaded: at.filter(id => !before.includes(id)).every(id => tile(id).classList.contains("unloaded"))};""", tabs)
    back = m.js(H + """const [want] = args; let got;
      for (let i = 0; i < 100; i++) { got = wins().map(w => w.gBrowser.tabs.filter(t => t.pinned).map(t => ek(w, t))); if (got.every(g => JSON.stringify(g) === JSON.stringify(want))) break; await wait(100); }
      return got;""", pins[0])
    check("picked essentials closed together come back in their places, unloaded, once each", r.get("had") and r.get("n") and r.get("kept") and r.get("unloaded") and all(g == pins[0] for g in back), str([r, back]))
    r = sidebar_page(m, PICKING + """
      const [{y1, y2}] = args, tiles0 = tileIds().length;
      await select(plainTabs()[0]);
      add(tile(y1)); add(tile(y2));
      drag(tile(y1), doc.getElementById("tabs"));
      await until(() => tileIds().length === tiles0 - 2 && row(y1) && row(y2));
      const list = ids();
      let keys;
      for (let i = 0; i < 100; i++) { keys = await keysOf([y1, y2]); if (keys.every(Boolean)) break; await wait(100); }
      return {back: !!row(y1) && !!row(y2) && list.indexOf(y2) === list.indexOf(y1) + 1, list, y1, y2, keys};""", tabs)
    check("picked essentials dragged to the list are ordinary tabs, in order", r.get("back"), str(r))
    got = order_everywhere(m, r.get("keys"))
    check("a second window has them in the same order", len(got) > 1 and all(g == r.get("keys") for g in got), str(got))

    # What this group added goes again.
    sidebar_page(m, PICKING + """
      const [{f1, f2, g1, y1, y2, open, closed}] = args;
      send({type: "deleteFolder", key: open});
      send({type: "deleteFolder", key: closed});
      await until(() => !head("Picks") && !head("Picks closed"));
      for (const tabId of [f1, f2, g1, y1, y2]) send({type: "close", tabId});
      await until(() => ![f1, f2, g1, y1, y2].some(row));
      return 1;""", tabs)
    m.js(H + """const all = (await storage(args[0], ["syncedTabs"])).syncedTabs;
      await removeWhere((w, t) => (all[value(w, t, "syncKey")]?.url || "").includes("smoke-pick"));
      return 1;""", EXT_ID)


# Helpers for alone_stay_put. These checks work on the real sidebar, not on its page in a
# tab: a background tab gets its scroll events some seconds late, and its timers at most
# once a second, so waiting goes by the sidebar's clock too. The list is made shorter,
# which takes the place of some fifty tabs.
STAY_PUT = """
  const obj = o => page.JSON.parse(JSON.stringify(o));
  const side = page.browser.extension.getViews(obj({type: "sidebar", windowId: (await page.browser.windows.getCurrent()).id}))[0], doc = side.document;
  const wait = ms => new Promise(done => side.setTimeout(() => done(), ms));
  const list = doc.getElementById("tabs");
  list.style.cssText = "flex:none;height:160px";
  const plainTabs = () => [...doc.querySelectorAll("#tabs > .tab")];
  const folders = () => [...doc.querySelectorAll("#tabs .folder")].map(f => ({name: f.querySelector(".head .title")?.textContent}));
  const spaces = () => [...doc.querySelectorAll("#spaces .space")].map(b => ({id: b.dataset.space, active: b.classList.contains("active")}));
  const until = async (test, ms = 8000) => { for (const t0 = Date.now(); Date.now() - t0 < ms; await wait(30)) if (await test()) return true; return false; };
  const tabs = page.browser.tabs;
  const activeRow = () => doc.querySelector("#tabs .tab.active");
  // The list's edges as a row brought into view meets them: inside its fades (scroll-padding,
  // sidebar.css), which a row scrolled to by the least distance stops at.
  const box = () => { const b = list.getBoundingClientRect(), css = side.getComputedStyle(list);
    return { top: b.top + (parseFloat(css.scrollPaddingTop) || 0), bottom: b.bottom - (parseFloat(css.scrollPaddingBottom) || 0) }; };
  const fromTop = r => Math.round(r.getBoundingClientRect().top - box().top), fromBottom = r => Math.round(box().bottom - r.getBoundingClientRect().bottom);
  const inView = r => fromTop(r) >= 0 && fromBottom(r) >= 0;
  const mine = async () => {
    const ids = new Set((await tabs.query(obj({windowId: (await page.browser.windows.getCurrent()).id}))).filter(t => t.url.includes("smoke-stay")).map(t => t.id));
    return () => plainTabs().filter(r => ids.has(Number(r.dataset.tab)));
  };
  // The sidebar marks a selected tab's row before the view that draws it comes (sidebar.js),
  // so the mark alone does not say the list is up to date: a row a view has drawn says so
  // itself (keep(), sidebar.js), and a closed tab's row is gone only with its view.
  const drawn = r => !!r && r.dataset.state !== undefined;
  const rowOf = id => doc.querySelector(`#tabs .tab[data-tab="${id}"]`);
  const select = async r => { const id = r.dataset.tab; await tabs.update(Number(id), obj({active: true})); await until(() => activeRow()?.dataset.tab === id && drawn(activeRow())); await wait(50); };
  const landedAfter = id => until(() => drawn(activeRow()) && activeRow().dataset.tab !== String(id) && !rowOf(id));
  const scrollTo = y => new Promise(done => {
    const was = list.scrollTop;
    list.addEventListener("scroll", () => done(), {once: true});
    list.scrollTop = y;
    if (list.scrollTop === was) done();  // already there: no event comes
    wait(3000).then(() => done("no scroll event"));
  });
  const switchTo = async id => {
    doc.querySelector(`#spaces .space[data-space="${id}"]`).click();
    await until(() => spaces().find(s => s.active).id === id && doc.querySelector(".tab.active, .tile.active"));
    await wait(300);  // nothing may move after this either
  };
"""


FOCUS_SIDEBAR = H + """const w = main(); w.focus(); w.SidebarController.browser.contentDocument.getElementById("webext-panels-browser").focus(); await wait(200); return 1;"""


def real_wheel(m, at, x, y, dy):
    m.cmd("WebDriver:PerformActions", {"actions": [{"type": "wheel", "id": "wheel", "actions": [
        {"type": "scroll", "x": int(at["x"] + x), "y": int(at["y"] + y), "deltaX": 0, "deltaY": dy, "duration": 0, "origin": "viewport"}]}]})
    m.cmd("WebDriver:ReleaseActions")


def alone_stay_put(m):
    m.js(H + """const w = main(); for (const t of [...w.gBrowser.tabs]) if (url(t).includes("/sidebar/sidebar.html")) w.gBrowser.removeTab(t);
      await wait(300); return 1;""")
    home, second = sidebar_page(m, STAY_PUT + """await wait(300);
      side.dispatchEvent(new side.Event("blur"));
      const a = spaces().find(s => s.active).id, others = spaces().filter(s => !s.active).map(s => s.id);
      return [a, ...others];""")[:2]
    # A space of its own, which is sure to be short: the groups before this one can have filled the others.
    short = sidebar_page(m, """const id = (await page.browser.contextualIdentities.create(page.JSON.parse(JSON.stringify({name: "smoke-short", color: "pink", icon: "circle"})))).cookieStoreId;
      await wait(500); return id;""")
    m.js(H + """const w = main(); for (const ctx of args) { for (let i = 0; i < 8; i++) { w.gBrowser.addTrustedTab("https://example.org/?smoke-stay-" + ctx + "-" + i, {userContextId: ctx, inBackground: true}); await wait(60); } }
      return 1;""", int(home.split("-")[-1]), int(second.split("-")[-1]))

    # Each space keeps its place: also over a space too short to scroll, whose
    # position of 0 must not be written to another.
    r = sidebar_page(m, STAY_PUT + """
      const [home, second, short] = args, out = {};
      let rows = await mine();
      await until(() => rows().length >= 8);
      await select(rows()[5]);
      await scrollTo(list.scrollTop - 17);
      out.home = list.scrollTop;
      await switchTo(second);
      rows = await mine();
      await until(() => rows().length >= 8);
      await select(rows()[4]);
      await scrollTo(list.scrollTop - 5);
      out.second = list.scrollTop;
      await switchTo(short);
      out.short = list.scrollTop;
      await switchTo(home);
      out.homeBack = list.scrollTop;
      await switchTo(second);
      out.secondBack = list.scrollTop;
      await switchTo(home);
      out.homeAgain = list.scrollTop;
      // Back and forth faster than the views come: nothing is mixed up. The last click is on
      // the one space not clicked before it: Tidier takes the clicks one at a time, so that
      // space showing says they are all done. (A space clicked earlier shows on the way too,
      // and home showed before the first click: on a busy machine the list was read there,
      // in the middle of it all.)
      for (const id of [second, home, second, home, short]) { doc.querySelector(`#spaces .space[data-space="${id}"]`).click(); await wait(10); }
      await until(() => spaces().find(s => s.active).id === short && doc.querySelector(".tab.active, .tile.active"));
      await wait(300);
      out.shortQuick = list.scrollTop;
      await switchTo(home);
      out.homeQuick = list.scrollTop;
      await switchTo(second);
      out.secondQuick = list.scrollTop;
      await switchTo(home);
      // Restored first, then the selected tab shown by the least distance: from where
      // you left the list, the row comes in at the top edge; from the top of the list, at the bottom.
      rows = await mine();
      await select(rows()[1]);
      await scrollTo(list.scrollHeight);
      out.away = !inView(activeRow());
      // The line at the edge the tab you are on lies beyond (awaymark.js), and a click on it.
      const marks = () => ["up", "down"].filter(way => !doc.getElementById("away-" + way).hidden);
      out.markUp = marks();
      const upBox = doc.getElementById("away-up").getBoundingClientRect(), listBox = list.getBoundingClientRect();
      out.markPlace = {inside: upBox.top >= listBox.top - 1 && upBox.bottom <= listBox.bottom,
        middle: Math.abs((upBox.left + upBox.right) / 2 - (listBox.left + listBox.right) / 2) <= 2, thin: upBox.height <= 4};
      doc.getElementById("away-up").click();
      await until(() => inView(activeRow()) && !marks().length);
      out.afterClick = {shown: inView(activeRow()), marks: marks()};
      await scrollTo(0);
      await until(() => marks().length > 0);
      out.markDown = marks();
      // And back as the checks below it expect: the tab you are on above the part in view.
      await scrollTo(list.scrollHeight);
      await until(() => marks().join() === "up");
      await switchTo(short);
      await switchTo(home);
      out.restoredThenShown = {top: fromTop(activeRow()), bottom: fromBottom(activeRow())};
      out.marksBack = marks();
      return out;""", home, second, short)
    # Scroll bars that take room, as a Mac shows them with a mouse (and GitHub's Macs always):
    # a list long enough to scroll is then narrower than a short one, which is no change of
    # the sidebar's size, so a selected tab partly in view stays where you left it.
    m.js(H + """Services.prefs.setIntPref("ui.useOverlayScrollbars", 0); await wait(500); return 1;""")
    bars = sidebar_page(m, STAY_PUT + """
      const [home, short] = args, out = {};
      const rows = await mine();
      await scrollTo(0);
      await select(rows()[5]);
      await scrollTo(list.scrollTop - 17);
      out.bar = list.offsetWidth - list.clientWidth;
      out.partly = !inView(activeRow()) && fromBottom(activeRow()) > -20;
      out.home = list.scrollTop;
      await switchTo(short);
      out.shortBar = list.offsetWidth - list.clientWidth;
      await switchTo(home);
      out.homeBack = list.scrollTop;
      return out;""", home, short)
    m.js(H + """Services.prefs.clearUserPref("ui.useOverlayScrollbars"); await wait(500); return 1;""")
    sidebar_page(m, STAY_PUT + """await switchTo(args[0]); await page.browser.contextualIdentities.remove(args[1]); await wait(600); return 1;""", home, short)
    check("each space keeps its place in the list", r.get("home") and r["homeBack"] == r["home"] and r["homeAgain"] == r["home"] and r["secondBack"] == r["second"], str(r))
    check("a space too short to scroll does not change another's place", r.get("short") == 0 and r["home"] != r["second"], str(r))
    check("switching back and forth quickly mixes up no place", r.get("homeQuick") == r.get("home") and r.get("secondQuick") == r.get("second") and r.get("shortQuick") == 0, str(r))
    check("a selected tab you scrolled away from comes back by the least distance from your place", r.get("away") and r["restoredThenShown"]["top"] == 0, str(r))
    check("a thin line at the list's edge says the tab you are on is that way, and a click on it goes there",
          r.get("markUp") == ["up"] and r.get("markDown") == ["down"] and (r.get("markPlace") or {}) == {"inside": True, "middle": True, "thin": True}
          and (r.get("afterClick") or {}) == {"shown": True, "marks": []} and r.get("marksBack") == [], str(r))
    if bars.get("bar") and not bars.get("shortBar"):
        check("with scroll bars that take room, a space keeps its place too", bars.get("partly") and bars["homeBack"] == bars["home"], str(bars))
    else:
        print(f"SKIP  with scroll bars that take room, a space keeps its place too (no such scroll bar in this Firefox: {bars})", flush=True)

    # The list moves only for a selected tab wholly out of view.
    r = sidebar_page(m, STAY_PUT + """
      const out = {}, rows = await mine(), r = rows();
      await scrollTo(1 + list.scrollHeight);
      await select(r[0]);
      out.up = fromTop(r[0]);
      await select(r.at(-1));
      out.down = fromBottom(r.at(-1));
      // Partly in view: it stays where it is.
      const part = r[2], y = list.scrollTop + fromTop(part) + 10;
      await scrollTo(y);
      await select(part);
      await wait(200);
      out.partly = {moved: list.scrollTop - y, cut: fromTop(part)};
      // A click on a row in view.
      const y1 = list.scrollTop, seen = r.find(x => inView(x) && x !== activeRow());
      seen.click();
      await until(() => activeRow() === seen);
      await wait(200);
      out.clicked = {selected: activeRow() === seen, moved: list.scrollTop - y1};
      // A tab opened in the background, below what is shown.
      const before = plainTabs().length;
      await tabs.create(obj({url: "https://example.org/?smoke-stay-background", active: false, cookieStoreId: doc.documentElement.dataset.space}));
      await until(() => plainTabs().length > before);
      await wait(200);
      out.background = {added: plainTabs().length > before, moved: list.scrollTop - y1};
      // And nothing moves by itself when the selected tab is out of view and something else changes.
      await select(r.at(-1));
      await scrollTo(0);
      const out0 = !inView(activeRow());
      await tabs.create(obj({url: "https://example.org/?smoke-stay-background2", active: false, cookieStoreId: doc.documentElement.dataset.space}));
      await wait(500);
      out.staysAway = {away: out0, moved: list.scrollTop};
      // A tab that comes in above what is shown (moved there here or in another window).
      await scrollTo(list.scrollTop + fromTop(r[1]));
      const shown = r[1], top = fromTop(shown), mover = r.at(-1), first = plainTabs()[0];
      send({type: "moveTab", tabId: Number(mover.dataset.tab), before: Number(first.dataset.tab), folder: null});
      await until(() => plainTabs()[0] === mover);
      await wait(200);
      out.above = {arrived: plainTabs()[0] === mover, moved: fromTop(shown) - top};
      return out;""")
    check("a selected tab above the list comes in at the top edge, below it at the bottom edge", r.get("up") == 0 and r.get("down") == 0, str(r))
    check("a partly shown selected tab does not move the list", r.get("partly", {}).get("moved") == 0 and r["partly"]["cut"] < 0, str(r))
    check("clicking a row in view does not move the list", r.get("clicked") == {"selected": True, "moved": 0}, str(r))
    check("a tab opened in the background does not move the list", r.get("background") == {"added": True, "moved": 0}, str(r))
    check("with the selected tab scrolled away, other changes leave the list alone", r.get("staysAway") == {"away": True, "moved": 0}, str(r))
    check("a tab that comes in above what is shown does not move what you see", r.get("above") == {"arrived": True, "moved": 0}, str(r))

    # A closed folder shows the selected tab, and only that; nothing is unfolded or written.
    r = sidebar_page(m, STAY_PUT + """
      const out = {}, rows = await mine();
      const space = doc.documentElement.dataset.space;
      send({type: "newFolder", space, name: "Stay"});
      await until(() => folders().some(f => f.name === "Stay"));
      const head = [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "Stay"), folder = head.parentElement, key = head.dataset.folderHead;
      for (const r of rows().slice(0, 3)) send({type: "moveTab", tabId: Number(r.dataset.tab), folder: key, before: null});
      const inFolder = () => [...folder.querySelectorAll(".tab")];
      await until(() => inFolder().length === 3);
      const shown = () => inFolder().filter(r => r.offsetParent !== null).map(r => r.dataset.tab);
      const stored = async () => (await page.browser.storage.local.get("syncedTabs")).syncedTabs[key]?.collapsed;  // written a moment later
      const a = inFolder()[0], b = inFolder()[1];
      await select(b);
      head.click();
      await until(() => folder.classList.contains("collapsed") && shown().length < 3);
      await until(async () => (await stored()) === true);
      await until(() => inView(b), 3000);  // the list follows the fold a moment later on a busy machine
      out.foldedHere = {shown: shown(), want: [b.dataset.tab], stored: await stored(), inView: inView(b)};
      await select(rows()[0]);
      await wait(150);
      out.left = {shown: shown(), stored: await stored(), closed: folder.classList.contains("collapsed")};
      await scrollTo(list.scrollHeight);
      await select(a);
      await wait(150);
      out.selectedInside = {shown: shown(), want: [a.dataset.tab], stored: await stored(), closed: folder.classList.contains("collapsed"), inView: inView(a), headInView: inView(head)};
      // Its row goes when you leave it: from above what is shown, without moving what you see.
      await scrollTo(list.scrollHeight);
      const seen = rows().filter(inView).at(-1), seenAt = fromTop(seen), above = !inView(a);
      seen.click();
      await until(() => activeRow() === seen && shown().length === 0);
      await wait(150);
      out.leftFromBelow = {above, gone: shown().length, moved: fromTop(seen) - seenAt};
      head.click();
      await until(() => !folder.classList.contains("collapsed"));
      await until(async () => (await stored()) === false);
      out.unfolded = {shown: shown().length, stored: await stored()};
      return {...out, key};""")
    check("folding the selected tab's folder keeps that row and hides the others", r.get("foldedHere") and r["foldedHere"]["shown"] == r["foldedHere"]["want"] and r["foldedHere"]["stored"] is True and r["foldedHere"]["inView"], str(r))
    check("leaving the tab hides it, and the folder stays closed", r.get("left") == {"shown": [], "stored": True, "closed": True}, str(r))
    check("selecting a tab in a closed folder shows it, in view, and unfolds nothing", r.get("selectedInside") and r["selectedInside"]["shown"] == r["selectedInside"]["want"] and r["selectedInside"]["stored"] is True and r["selectedInside"]["closed"] and r["selectedInside"]["inView"] and r["selectedInside"]["headInView"], str(r))
    check("leaving a tab in a closed folder above the view does not move what you see", r.get("leftFromBelow") == {"above": True, "gone": 0, "moved": 0}, str(r))
    check("unfolding brings back all its tabs", r.get("unfolded") == {"shown": 3, "stored": False}, str(r))
    folder_key = r.get("key")

    # After closing: not an unloaded tab, even if used later, and not into a closed folder.
    r = sidebar_page(m, STAY_PUT + """
      const out = {}, rows = await mine();
      const folder = doc.querySelector(`.folder[data-key="${args[0]}"]`), head = folder.firstChild, inFolder = () => [...folder.querySelectorAll(".tab")];
      const told = (id, next) => until(async () => (await tabs.get(id)).successorTabId === next);
      const id = r => Number(r.dataset.tab);
      const [l, u, s] = rows().slice(-3).map(id);
      for (const r of rows().slice(-3)) await select(r);
      await tabs.discard(u);
      out.unloaded = (await tabs.get(u)).discarded;
      out.toldLoaded = await told(s, l);
      await tabs.remove(s);
      await landedAfter(s);
      out.afterUnloaded = {selected: id(activeRow()), want: l};
      // Used just before, in a folder you then close while on another tab.
      const f = inFolder()[0], t = rows().at(-1);
      await select(f);
      await select(t);
      out.toldFolder = await told(id(t), id(f));
      head.click();
      await until(() => folder.classList.contains("collapsed"));
      out.toldOutside = await until(async () => { const n = (await tabs.get(id(t))).successorTabId; return n !== id(f) && n !== undefined; });
      const tId = id(t);
      await tabs.remove(tId);
      await landedAfter(tId);
      out.afterFolded = {outside: !folder.contains(activeRow()), closed: folder.classList.contains("collapsed")};
      // Closing the selected tab inside a closed folder: a tab in a folder only unloads, in its
      // place, so nothing is lost; you land outside, and its row goes with the folder still closed.
      const kept = inFolder()[0], keptId = id(kept), count = inFolder().length; // (unloaded, as a closed folder's tabs are: selecting it loads it)
      await select(kept);
      await until(() => !kept.classList.contains("unloaded")); // only a loaded tab that closes stays, unloaded: an unloaded one you close is gone
      out.toldOut = await until(async () => { const n = (await tabs.get(keptId)).successorTabId; return n !== undefined && !inFolder().some(r => id(r) === n); });
      await tabs.remove(keptId);
      await until(() => drawn(activeRow()) && activeRow().dataset.tab !== String(keptId) && inFolder().length === count && !inFolder().some(r => id(r) === keptId));
      await wait(200);
      out.counted = [count, inFolder().length];
      out.closedInside = {landedOutside: !folder.contains(activeRow()), kept: inFolder().length === count, hidden: inFolder().every(r => r.offsetParent === null), closed: folder.classList.contains("collapsed")};
      // Put into the closed folder with no move for Firefox to report: the window's last
      // tab, used just before this one, once Tidier has it in its record.
      const last = (await tabs.create(obj({url: "https://example.org/?smoke-stay-last", active: true, cookieStoreId: doc.documentElement.dataset.space}))).id;
      await until(() => activeRow()?.dataset.tab === String(last));
      await wait(2000);
      const on = rows()[2];
      await select(on);
      out.toldLast = await told(id(on), last);
      out.lastIsLast = (await tabs.get(last)).index === (await tabs.query(obj({windowId: (await page.browser.windows.getCurrent()).id}))).length - 1;
      send({type: "moveTab", tabId: last, folder: args[0], before: null});
      await until(() => inFolder().some(r => id(r) === last));
      out.inClosed = inFolder().some(r => id(r) === last);
      out.toldNotLast = await until(async () => { const n = (await tabs.get(id(on))).successorTabId; return n !== last && n !== undefined; });
      return out;""", folder_key)
    check("Firefox knows the next tab as soon as a tab is unloaded", r.get("unloaded") is True and r.get("toldLoaded") is True, str(r))
    check("closing a tab selects a loaded tab, not an unloaded one used later", r.get("afterUnloaded", {}).get("selected") == r.get("afterUnloaded", {}).get("want"), str(r))
    check("closing a tab does not select into a folder closed meanwhile", r.get("toldFolder") is True and r.get("toldOutside") is True and r.get("afterFolded") == {"outside": True, "closed": True}, str(r))
    check("closing the selected tab in a closed folder keeps it there unloaded, and lands outside", r.get("toldOut") and r.get("closedInside") == {"landedOutside": True, "kept": True, "hidden": True, "closed": True}, str(r))
    check("nor into a closed folder a tab was put in without moving", r.get("toldLast") and r.get("lastIsLast") and r.get("inClosed") and r.get("toldNotLast"), str(r))

    # A page without a container (about:, Tidier's settings) belongs to no space, and is
    # shown in the one you are in: closing it lands as closing any tab there does, not on
    # the unloaded tab Firefox would take for being next to it.
    m.js(H + """main().gBrowser.addTrustedTab("about:robots", {inBackground: true}); await wait(500); return 1;""")
    r = sidebar_page(m, STAY_PUT + """
      const out = {}, rows = await mine(), id = r => Number(r.dataset.tab);
      const windowId = (await page.browser.windows.getCurrent()).id;
      const all = await tabs.query(obj({windowId})), robots = all.find(t => t.url === "about:robots").id;
      const visible = all.filter(t => !t.hidden && !t.pinned && t.id !== robots).sort((a, b) => a.index - b.index);
      const beside = visible.at(-1).id, used = rows().find(r => id(r) !== beside);
      await select(used);
      await tabs.discard(beside);
      await tabs.update(robots, obj({active: true}));
      await until(() => activeRow()?.dataset.tab === String(robots));
      out.besideUnloaded = (await tabs.get(beside)).discarded;
      out.told = await until(async () => (await tabs.get(robots)).successorTabId === id(used));
      await tabs.remove(robots);
      await landedAfter(robots);
      await wait(200);
      out.landed = activeRow()?.dataset.tab === String(id(used));
      return out;""")
    check("closing a page without a container lands on the loaded tab used last, not the unloaded one beside it", r == {"besideUnloaded": True, "told": True, "landed": True}, str(r))

    # The first key starts at the selected row, also after going away.
    r = sidebar_page(m, STAY_PUT + """
      const out = {}, rows = await mine(), key = k => side.dispatchEvent(new side.KeyboardEvent("keydown", {key: k, bubbles: true, cancelable: true}));
      const cursor = () => doc.querySelector(".cursor"), reach = () => [...doc.querySelectorAll(".tile, #tabs .head, #tabs .tab")].filter(e => e.offsetParent !== null);
      const r = rows()[3];
      await select(r);
      out.none = !cursor();
      key("ArrowDown");
      out.first = cursor() === r;
      key("ArrowDown");
      out.second = reach().indexOf(cursor()) === reach().indexOf(r) + 1;
      side.dispatchEvent(new side.Event("blur"));
      out.gone = !cursor();
      key("ArrowUp");
      out.againUp = cursor() === r;
      // Its row drawn again (a page's title, a sound): the mark stays, or you lose your place.
      await tabs.update(Number(r.dataset.tab), obj({muted: true}));
      await until(() => r.querySelector(".sound"));
      out.markStays = !!r.querySelector(".sound") && r.classList.contains("cursor");
      await tabs.update(Number(r.dataset.tab), obj({muted: false}));
      await until(() => !r.querySelector(".sound"));
      side.dispatchEvent(new side.Event("blur"));
      const tile = doc.querySelector("#essentials .tile");
      await tabs.update(Number(tile.dataset.tab), obj({active: true}));
      await until(() => tile.classList.contains("active"));
      key("ArrowDown");
      out.onTile = cursor() === tile;
      side.dispatchEvent(new side.Event("blur"));
      // Walking by key: the cursor brings a row in by the least distance, and Enter selects
      // it without moving the list again.
      await select(r);
      await scrollTo(0);
      key("ArrowDown");
      for (let i = 0; i < 30 && cursor() !== rows().at(-1); i++) key("ArrowDown");
      out.walked = {on: cursor() === rows().at(-1), bottom: fromBottom(cursor())};
      const y = list.scrollTop;
      key("Enter");
      await until(() => activeRow() === rows().at(-1));
      await wait(200);
      out.entered = {selected: activeRow() === rows().at(-1), moved: list.scrollTop - y};
      side.dispatchEvent(new side.Event("blur"));
      // A cursor on a row that is hidden since (its folder folded by a click): ⌫ and Enter do
      // nothing to a tab you cannot see, and the next arrow key starts at the selected row.
      const space = doc.documentElement.dataset.space, name = "Fold under cursor";
      send({type: "newFolder", space, name});
      await until(() => folders().some(f => f.name === name));
      const hide = [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === name), child = rows()[0], childId = Number(child.dataset.tab);
      send({type: "moveTab", tabId: childId, folder: hide.dataset.folderHead, before: null});
      await until(() => hide.parentElement.contains(child));
      await select(rows().at(-1));
      side.dispatchEvent(new side.Event("blur"));
      for (let i = 0; i < 40 && cursor() !== child; i++) key("ArrowUp");
      out.onChild = cursor() === child;
      hide.click();
      await until(() => child.offsetParent === null);
      key("Backspace");
      key("Enter");
      await wait(300);
      out.hiddenAlive = await tabs.get(childId).then(() => true, () => false);
      out.hiddenNotSelected = activeRow() === rows().at(-1);
      key("ArrowDown");
      out.fromSelected = cursor() === rows().at(-1);
      side.dispatchEvent(new side.Event("blur"));
      send({type: "deleteFolder", key: hide.dataset.folderHead});
      await until(() => !folders().some(f => f.name === name));
      // Ready for a real ⌃Tab from outside the sidebar, whichever way Firefox orders it: to the
      // tab after this one or the tab used before it, the same one here, below what is shown.
      // Firefox has caught up first: the tab of the folder just deleted is shown again, and
      // its tabs are in the list's order, which is what "the tab after this one" goes by.
      const inFirefox = async () => (await tabs.query(obj({windowId: (await page.browser.windows.getCurrent()).id, hidden: false}))).map(t => String(t.id));
      out.caughtUp = await until(async () => { const ids = rows().map(r => r.dataset.tab); return (await inFirefox()).filter(t => ids.includes(t)).join() === ids.join(); });
      await select(rows().at(-1));
      await select(rows().at(-2));
      await scrollTo(0);
      out.target = rows().at(-1).dataset.tab;
      return out;""")
    check("the first arrow key starts at the selected row", r.get("none") and r.get("first") and r.get("second"), str(r))
    check("the cursor goes when the sidebar loses the focus, and the next key starts at the selected row", r.get("gone") and r.get("againUp"), str(r))
    check("the cursor's mark stays when its row is drawn again", r.get("markStays") is True, str(r))
    check("the first arrow key starts at the selected essential", r.get("onTile") is True, str(r))
    check("walking down by key brings a row in by the least distance, and Enter leaves the list where it is",
          r.get("walked") == {"on": True, "bottom": 0} and r.get("entered") == {"selected": True, "moved": 0}, str(r))
    check("a cursor on a row hidden since closes and selects nothing, and the next key starts at the selected row",
          r.get("onChild") and r.get("hiddenAlive") and r.get("hiddenNotSelected") and r.get("fromSelected"), str(r))
    m.js(H + "main().focus(); await wait(300); return 1;")
    press(m, "\ue004", CTRL)
    k = sidebar_page(m, STAY_PUT + """
      await until(() => activeRow()?.dataset.tab === args[0]);
      await wait(100);
      const rows = (await mine())(), on = activeRow();
      return {selected: on?.dataset.tab === args[0], bottom: on && fromBottom(on), on: on ? rows.indexOf(on) + " of " + rows.length : "an essential", caughtUp: args[1]};""", r.get("target"), r.get("caughtUp"))
    check("⌃Tab to a tab below the list brings it in at the bottom edge", k.get("selected") is True and k.get("bottom") == 0, str(k))

    # The same for real: the wheel, clicks on the bar and on a row, and keys.
    at = m.js(SIDEBAR_AT)
    settled = """let last = -1; await until(async () => { const same = list.scrollTop === last; last = list.scrollTop; await wait(100); return same; });"""
    centre = """const middle = e => { const q = e.getBoundingClientRect(); return {x: q.x + q.width / 2, y: q.y + q.height / 2}; };
      const dot = id => middle(doc.querySelector(`#spaces .space[data-space="${id}"]`));
      const until_space = id => until(() => spaces().find(s => s.active).id === id && doc.querySelector(".tab.active, .tile.active"));"""
    place_home = sidebar_page(m, STAY_PUT + centre + """
      const rows = await mine(), r = rows()[4];
      await select(r);
      await scrollTo(list.scrollTop + fromTop(r) - 64);
      return {list: middle(list), was: list.scrollTop};""")
    real_wheel(m, at, place_home["list"]["x"], place_home["list"]["y"], -25)
    wheeled = sidebar_page(m, STAY_PUT + centre + "await until(() => list.scrollTop !== args[1]);" + settled + "return {y: list.scrollTop, dot: dot(args[0])};", second, place_home["was"])
    click_at(m, at, wheeled["dot"]["x"], wheeled["dot"]["y"])
    there = sidebar_page(m, STAY_PUT + centre + """
      await until_space(args[0]);
      const rows = await mine(), r = rows()[3];
      await select(r);
      await scrollTo(list.scrollTop + fromTop(r) - 32);
      return {list: middle(list), was: list.scrollTop, dot: dot(args[1])};""", second, home)
    real_wheel(m, at, there["list"]["x"], there["list"]["y"], -15)
    y2 = sidebar_page(m, STAY_PUT + "await until(() => list.scrollTop !== args[0]);" + settled + "return list.scrollTop;", there["was"])
    click_at(m, at, there["dot"]["x"], there["dot"]["y"])
    back = sidebar_page(m, STAY_PUT + centre + """
      await until_space(args[0]);
      await wait(300);
      const rows = await mine(), seen = rows().find(x => inView(x) && x !== activeRow());
      return {y: list.scrollTop, row: middle(seen), tab: seen.dataset.tab, active: activeRow()?.dataset.tab};""", home)
    check("with a real wheel and real clicks on the bar, each space keeps its place",
          wheeled["y"] < place_home["was"] and y2 < there["was"] and back.get("y") == wheeled["y"], f"{place_home} {wheeled} {there} {y2} {back}")
    click_at(m, at, back["row"]["x"], back["row"]["y"])
    clicked = sidebar_page(m, STAY_PUT + """
      await until(() => activeRow()?.dataset.tab === args[0]);
      await wait(200);
      return {selected: activeRow()?.dataset.tab === args[0], y: list.scrollTop, focus: doc.hasFocus(), cursor: !!doc.querySelector(".cursor")};""", back["tab"])
    check("a real click on a row in view selects it and does not move the list, and the page has the focus after",
          clicked == {"selected": True, "y": back["y"], "focus": False, "cursor": False}, str(clicked))
    m.js(FOCUS_SIDEBAR)
    press(m, "\ue015")  # ↓
    first = sidebar_page(m, STAY_PUT + """await until(() => doc.querySelector(".cursor"));
      return {on: doc.querySelector(".cursor")?.dataset.tab, selected: activeRow()?.dataset.tab, focus: doc.hasFocus()};""")
    m.js(FOCUS_SIDEBAR)
    press(m, "\ue015")
    second_key = sidebar_page(m, STAY_PUT + """const c = () => doc.querySelector(".cursor"), reach = [...doc.querySelectorAll(".tile, #tabs .head, #tabs .tab")].filter(e => e.offsetParent !== null);
      await until(() => c()?.dataset.tab !== args[0]);
      return {next: reach.indexOf(c()) === reach.findIndex(e => e.dataset.tab === args[0]) + 1, tab: c()?.dataset.tab};""", first.get("on"))
    m.js(FOCUS_SIDEBAR)
    press(m, "\ue007")  # Enter
    entered = sidebar_page(m, STAY_PUT + """await until(() => activeRow()?.dataset.tab === args[0] && !doc.hasFocus());
      await wait(100);
      return {selected: activeRow()?.dataset.tab === args[0], cursor: !!doc.querySelector(".cursor"), focus: doc.hasFocus()};""", second_key.get("tab"))
    check("real keys: the first ↓ starts at the selected row, the next moves on", first.get("on") == first.get("selected") and first.get("focus") is True and second_key.get("next") is True, f"{first} {second_key}")
    check("real keys: Enter selects, the page has the focus, and the cursor's mark is gone", entered == {"selected": True, "cursor": False, "focus": False}, str(entered))

    # For real: placeholders here, whose pages are live in another window. Selecting one
    # gives the row another tab, from another window, while you look at the list.
    opened = m.js(H + """if (other()) return false;
      const w = main().OpenBrowserWindow(); w.__smoke = true;
      for (let i = 0; i < 100 && !(w.gBrowser?.tabs.length > 3); i++) await wait(100);
      await wait(2500); return true;""")
    space = sidebar_page(m, STAY_PUT + "await wait(100); return doc.documentElement.dataset.space;")
    m.js(H + """const o = other(), context = args[0];
      for (let i = 0; i < 5; i++) { o.gBrowser.addTrustedTab("https://example.org/?smoke-stay-far-" + i, {userContextId: context, inBackground: true}); await wait(80); }
      await wait(2500); main().focus(); await wait(500); return 1;""", int(space.split("-")[-1]))
    r = sidebar_page(m, STAY_PUT + """
      const out = {}, id = r => Number(r.dataset.tab), folderKey = args[0];
      // Placeholders of the tabs just opened in the other window, found by their record: a
      // group before can leave others (a saved tab is one, with no page anywhere to pull in).
      const all = (await page.browser.storage.local.get("syncedTabs")).syncedTabs ?? {};
      const farOnes = u => { if (!u) return false; const k = new URL(u).searchParams.get("key"); return u.includes("ghost.html") && !!all[k]?.url?.includes("smoke-stay-far"); };
      // (A row's tab can be gone when it is asked about: a placeholder being made or pulled in
      // is another tab a moment later, and its row follows with the next view.)
      const ghosts = async () => { const g = []; for (const r of plainTabs()) if (farOnes(await tabs.get(id(r)).then(t => t.url, () => ""))) g.push(r); return g; };
      // Pulled in: the selected row is the page itself, and the placeholder's row is gone. (By
      // its address: the pages here share one title, and on the way the selection can rest on
      // another of them for a moment, which read as pulled in before it was.)
      const pageOf = async r => all[new URL((await tabs.get(id(r))).url).searchParams.get("key")].url;
      const pulled = (was, url) => until(async () => { const a = activeRow();
        return !!a && a.dataset.tab !== was && !a.classList.contains("unloaded") && !doc.querySelector(`#tabs .tab[data-tab="${was}"]`) && (await tabs.get(id(a)).then(t => t.url, () => "")) === url; });
      await until(async () => (await ghosts()).length >= 5);  // one for each tab opened there, when Tidier has got to them
      let g = await ghosts();
      out.placeholders = g.length;
      // A click on one at the very top of what is shown: the list does not move, though the tab does.
      const c = g[0], was = c.dataset.tab, page1 = await pageOf(c);
      await scrollTo(list.scrollTop + fromTop(c));
      // What may not move is the row under the pointer: the placeholder while it is there, then
      // the page's row. The list's own position can change and change back without anything
      // moving on screen: the page's row comes in above the placeholder's, and Firefox keeps
      // what you see in place by scrolling one row down, until the placeholder's row is gone.
      // A busy machine draws that state in between; a quick one gets both changes in one view.
      const y = list.scrollTop, places = [];
      let watching = true;
      list.addEventListener("scroll", () => { const r = doc.querySelector(`#tabs .tab[data-tab="${was}"]`) ?? activeRow(); if (watching && r) places.push(fromTop(r)); });
      c.click();
      out.clickPulled = await pulled(was, page1);
      await wait(400);
      watching = false;
      out.click = {moved: list.scrollTop - y, off: places.filter(t => t !== 0), top: fromTop(activeRow())};
      out.clickScrolls = places.length;
      // One out of view, selected from outside the list: it comes in, and stays in while the tab arrives.
      g = await ghosts();
      const f = g.at(-1), fWas = f.dataset.tab, page2 = await pageOf(f);
      await scrollTo(0);
      await tabs.update(id(f), obj({active: true}));
      out.farPulled = await pulled(fWas, page2);
      await wait(400);
      out.farInView = inView(activeRow());
      // One in a closed folder: its row shows, it stays the only one when the tab arrives, and the folder stays closed.
      const folder = doc.querySelector(`.folder[data-key="${folderKey}"]`), inside = () => [...folder.querySelectorAll(".tab")];
      const shown = () => inside().filter(r => r.offsetParent !== null);
      g = await ghosts();
      const p = g[0], page3 = await pageOf(p);
      send({type: "moveTab", tabId: id(p), folder: folderKey, before: null});
      await until(() => inside().some(r => r === p));
      const pWas = p.dataset.tab;
      await tabs.update(id(p), obj({active: true}));
      out.closedPulled = await pulled(pWas, page3);
      await wait(400);
      out.closed = {only: shown().length === 1 && shown()[0] === activeRow(), closed: folder.classList.contains("collapsed"), inView: inView(activeRow()), stored: (await page.browser.storage.local.get("syncedTabs")).syncedTabs[folderKey].collapsed};
      // Ready for closing: a loaded tab used just before this one, and then a placeholder made.
      g = await ghosts();
      const [before, onTab] = plainTabs().filter(r => !r.classList.contains("unloaded") && !g.includes(r));
      await select(before);
      await select(onTab);
      return {...out, before: id(before), onTab: id(onTab)};""", folder_key)
    check("clicking a placeholder at the top of the list does not move it", r.get("placeholders", 0) >= 3 and r.get("clickPulled") and r.get("click") == {"moved": 0, "off": [], "top": 0}, str(r))
    check("selecting a placeholder out of view brings it in, and it stays in while its tab arrives", r.get("farPulled") and r.get("farInView"), str(r))
    check("a placeholder in a closed folder shows while selected, and only it, with the folder closed", r.get("closedPulled") and r.get("closed") == {"only": True, "closed": True, "inView": True, "stored": True}, str(r))
    m.js(H + """other().gBrowser.addTrustedTab("https://example.org/?smoke-stay-later", {userContextId: args[0], inBackground: true}); await wait(2500); main().focus(); await wait(300); return 1;""", int(space.split("-")[-1]))
    r2 = sidebar_page(m, STAY_PUT + """
      const out = {}, [before, onTab] = args;
      const all = await tabs.query(obj({windowId: (await page.browser.windows.getCurrent()).id}));
      const used = all.find(x => x.id === before).lastAccessed;
      out.placeholderLater = all.some(t => t.url.includes("ghost.html") && t.lastAccessed > used);
      out.told = await until(async () => (await tabs.get(onTab)).successorTabId === before);
      await tabs.remove(onTab);
      await landedAfter(onTab);
      await wait(300);
      out.landed = activeRow()?.dataset.tab === String(before);
      return out;""", r.get("before"), r.get("onTab"))
    check("closing a tab passes over a placeholder used later, for the loaded tab used before", r2 == {"placeholderLater": True, "told": True, "landed": True}, str(r2))
    # Nothing was lost or doubled by all that: each tab once per window, loaded once.
    r = m.js(H + """const out = {doubled: [], loadedTwice: []};
      const keys = new Set(wins().flatMap(w => w.gBrowser.tabs.map(t => key(w, t)).filter(Boolean)));
      for (const k of keys) {
        if (wins().some(w => w.gBrowser.tabs.filter(t => key(w, t) === k).length > 1)) out.doubled.push(k);
        if (wins().flatMap(w => w.gBrowser.tabs.filter(t => key(w, t) === k && role(w, t) === "live")).length > 1) out.loadedTwice.push(k);
      }
      return out;""")
    check("each tab is in a window once and live in one window, after all this", r == {"doubled": [], "loadedTwice": []}, str(r))

    # The sidebar made shorter (a narrower one, where a notice takes two lines): the selected
    # tab at the end of the view stays in view, and does not slide under the fade.
    r = sidebar_page(m, STAY_PUT + """let rows = await mine(); await until(() => rows().length >= 8);
      await scrollTo(0); await select(rows()[3]);
      for (let i = 0; i < 8 && fromBottom(activeRow()) > 6; i++) { list.style.height = (list.clientHeight - 10) + "px"; await wait(120); }
      const before = {inView: inView(activeRow()), fromBottom: fromBottom(activeRow())};
      // Firefox tells the list of its new size when it gets to it: half a second later on a
      // busy machine, so the row is waited for, not read after a set time.
      list.style.height = (list.clientHeight - 40) + "px"; await until(() => inView(activeRow()), 5000);
      const after = {inView: inView(activeRow()), fromBottom: fromBottom(activeRow())};
      list.style.cssText = "flex:none;height:160px"; await wait(200);
      return {before, after};""")
    check("a shorter sidebar keeps the selected tab in view", r.get("before", {}).get("inView") and r.get("after", {}).get("inView"), str(r))

    # Its tabs must be out of the folder before closing them, or they only unload; and one
    # that is only a placeholder by now, having no page, is closed for good from the folder.
    sidebar_page(m, STAY_PUT + """for (const head of doc.querySelectorAll("#tabs .folder .head")) if (head.querySelector(".title").textContent === "Stay") {
        const unloaded = () => [...head.parentElement.querySelectorAll(".tab.unloaded")];
        for (const r of unloaded()) await tabs.remove(Number(r.dataset.tab));
        await until(() => !unloaded().length);
        send({type: "deleteFolder", key: head.dataset.folderHead});
      }
      await until(() => !folders().some(f => f.name === "Stay")); list.style.cssText = "";""")
    m.js(H + """await removeWhere((x, t) => url(t).includes("smoke-stay"));
      const w = main(); for (const t of [...w.gBrowser.tabs]) if (url(t).includes("/sidebar/sidebar.html")) w.gBrowser.removeTab(t);
      if (args[0]) await close(other());
      await wait(500); return 1;""", opened)
