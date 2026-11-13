"""What a row or a dot shows besides its title: sound, news, a slow load, the look, motion and the
swipe.
"""
import time
from testfirefox import EXT_ID
from smokechecks.base import (
    H, LOOK_IN_SIDEBAR, SIDEBAR_AT, check, click_at, close_sidebar_page, extension_message, into_page,
    look_in_sidebar, no_problems, sidebar_page, to_folder, until,
)
from smokechecks.core import set_title


def pointer_over(m, *points):
    """Move a real pointer over the sidebar page, which must be the selected tab and where sidebar_page last ran: to each point in turn, with no way in between."""
    m.cmd("Marionette:SetContext", {"value": "content"})
    for x, y in points:
        m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"},
                                                        "actions": [{"type": "pointerMove", "x": round(x), "y": round(y), "duration": 0, "origin": "viewport"}]}]})
        time.sleep(0.2)
    m.cmd("WebDriver:ReleaseActions")
    m.chrome()


def sidebar_press(m, find):
    """Press the real mouse button on what the expression `find` gives in the sidebar page, and leave it down. Returns how to let go: there, or at x, y. Let go before doing anything else with Marionette: its mouse belongs to this page's context."""
    # In this order: the page is a row too, and selecting it can scroll the list. A row below
    # the window, in a long list, is out of reach of a pointer until it is brought into view.
    sidebar_page(m, "return 1;")
    m.js(H + """const w = main(), t = w.gBrowser.tabs.find(x => url(x).includes("/sidebar/sidebar.html")); w.focus();
      if (w.gBrowser.selectedTab !== t) { w.gBrowser.selectedTab = t; await wait(500); } return 1;""")
    # (The quiet line can lie over the end of the list for its ten seconds, and a row can be
    # drawn again at any moment, so what is found is found anew each time.)
    at = sidebar_page(m, f"""const find = () => {find}; if (!find()) return null;
      find().scrollIntoView({{block: "center"}});
      const spot = () => {{ const e = find(), box = e?.getBoundingClientRect(), x = box?.left + box?.width / 2, y = box?.top + box?.height / 2; return box && {{x: Math.round(x), y: Math.round(y), free: e.contains(doc.elementFromPoint(x, y))}}; }};
      for (let i = 0; i < 120 && !spot()?.free; i++) await wait(100);
      return spot();""")
    if not at:
        return None
    into_page(m, "/sidebar/sidebar.html")
    mouse = lambda *actions: m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"}, "actions": list(actions)}]})
    # The pointer first, and then where it is under the pointer: a row's marks make room for its
    # close button while the pointer is on the row (sidebar.css), as a hand sees before it clicks.
    mouse({"type": "pointerMove", "duration": 0, "x": at["x"], "y": at["y"]})
    time.sleep(.3)
    try:  # (an expression that uses the sidebar page's own helpers is found where it was)
        now = m.cmd("WebDriver:ExecuteScript", {"script": f"""const page = window.wrappedJSObject || window, doc = page.document, e = {find}, box = e?.getBoundingClientRect();
          return box ? {{x: Math.round(box.left + box.width / 2), y: Math.round(box.top + box.height / 2)}} : null;""", "args": []})
    except RuntimeError:
        now = None
    if now and (now["x"], now["y"]) != (at["x"], at["y"]):
        at = {**at, **now}
        mouse({"type": "pointerMove", "duration": 0, "x": at["x"], "y": at["y"]})
    mouse({"type": "pointerDown", "button": 0})

    def let_go(x=None, y=None):
        mouse(*([{"type": "pointerMove", "duration": 0, "x": x, "y": y}] if x is not None else []), {"type": "pointerUp", "button": 0})
        m.cmd("WebDriver:ReleaseActions")
        m.chrome()
    return let_go


def sidebar_click(m, find, hold=0):
    """A real click on what the expression `find` gives in the sidebar page: Firefox itself decides what is under the pointer. `hold`: seconds between press and release."""
    let_go = sidebar_press(m, find)
    if not let_go:
        return False
    time.sleep(hold)
    let_go()
    return True


def alone_sound(m):
    # Firefox's own audible state, set from chrome code as a page playing sound sets it:
    # the same for Tidier, with no noise from a test machine and no need for a sound
    # device on GitHub's. The real pages are all in the other window, so this sidebar's
    # rows and tiles are placeholders: what they show can only come from the real tab.
    SOUND = """
      const winOf = t => wins().find(w => w.gBrowser.tabs.includes(t));
      const play = (t, on) => { t.toggleAttribute("soundplaying", on); winOf(t).gBrowser._tabAttrModified(t, ["soundplaying"]); };
      const real = name => { for (const w of wins()) for (const t of w.gBrowser.tabs) if (t.label === name && !url(t).includes("ghost.html") && !url(t).startsWith("about:blank")) return t; return null; };
    """
    active = sidebar_page(m, """return {active: spaces().find(s => s.active).id, other: spaces().find(s => !s.active).id};""")
    here, away = active["active"], active["other"]
    opened = m.js(H + """const a = main(); a.focus(); await wait(300);
      let b = other(); const opened = !b;
      if (opened) { b = a.OpenBrowserWindow(); b.__smoke = true; for (let i = 0; i < 100 && !b.gBrowser; i++) await wait(100); await wait(4000); }
      const [pages, hereCtx, awayCtx] = args, page = name => pages + "/titled?" + encodeURIComponent(name);
      for (const [name, ctx] of [["sound tile", hereCtx], ["sound row", hereCtx], ["sound inside", hereCtx], ["sound away", awayCtx]]) {
        b.gBrowser.addTrustedTab(page(name), {userContextId: ctx, inBackground: true}); await wait(300);
      }
      for (let i = 0; i < 50 && !b.gBrowser.tabs.some(t => t.label === "sound tile"); i++) await wait(100);
      b.gBrowser.pinTab(b.gBrowser.tabs.find(t => t.label === "sound tile"));
      await wait(3000);
      return opened;""", m.pages, int(here.split("-")[-1]), int(away.split("-")[-1]))

    FIND = """
      const tile = name => [...doc.querySelectorAll("#essentials .tile")].find(e => e.title.split("\\n")[0] === name);
      const row = name => [...doc.querySelectorAll("#tabs .tab")].find(e => e.title.split("\\n")[0] === name);
      const head = name => [...doc.querySelectorAll("#tabs .head")].find(e => e.title === name);
      const dot = id => doc.querySelector(`#spaces .space[data-space="${id}"]`);
      const until = async (f, ms = 8000) => { for (let i = 0; i < ms / 100; i++) { if (f()) return true; await wait(100); } return false; };
      const box = e => { const b = e.getBoundingClientRect(); return [b.left, b.top, b.width, b.height].map(Math.round); };
      // Where things are, also inside a tile, a row, a closed head and a dot: their
      // own box stays the same whatever is in them.
      const places = away => { const t = tile("sound tile"), r = row("sound row"), h = head("Sound folder"), d = dot(away);
        return {tile: box(t), tileIcon: box(t.querySelector("img, .letter")), row: box(r), rowIcon: box(r.querySelector("img, .letter")), titleLeft: box(r.querySelector(".title"))[0],
                close: box(r.querySelector(".close")), head: box(h), headTitleLeft: box(h.querySelector(".title"))[0], countRight: Math.round(h.querySelector(".count").getBoundingClientRect().right),
                space: box(d), dot: box(d.querySelector(".dot"))}; };
    """
    # In this window everything is a placeholder, and a folder is closed with a tab in it.
    r = sidebar_page(m, FIND + """
      const [here] = args;
      await until(() => tile("sound tile") && row("sound row") && row("sound inside"));
      send({type: "newFolder", space: here, name: "Sound folder"});
      await until(() => head("Sound folder"));
      send({type: "moveTab", tabId: Number(row("sound inside").dataset.tab), folder: head("Sound folder").dataset.folderHead, before: null});
      await until(() => head("Sound folder").parentElement.querySelector(".tab"));
      const fold = () => head("Sound folder").click();
      fold();
      await until(() => head("Sound folder").parentElement.classList.contains("collapsed"));
      return {tile: !!tile("sound tile"), row: !!row("sound row"), unloaded: row("sound row").classList.contains("unloaded") && tile("sound tile").classList.contains("unloaded"),
              marks: doc.querySelectorAll(".sound").length, boxes: places(args[1]),
              on: [...doc.querySelectorAll(".sound")].map(e => (e.closest("[data-tab], [data-folder-head], .space")?.title ?? "?").split("\\n")[0] + (e.classList.contains("muted") ? " (muted)" : ""))};""", here, away)
    loud = m.js(H + """return wins().flatMap(w => w.gBrowser.tabs.filter(t => t.muted || t.soundPlaying).map(t => (t.muted ? "muted " : "playing ") + t.label));""")
    check("with nothing playing there is no mark anywhere", r["marks"] == 0, f"{r} {loud}")
    check("this window has only placeholders of those tabs", r["tile"] and r["row"] and r["unloaded"], str(r))
    before = r["boxes"]

    # It starts playing, in the other window.
    # (Once the closed folder has put its tab to rest, foldrest.js: a tab that is silent then
    # is unloaded, and one that began to play just before would lose its sound with its page.)
    playing = m.js(H + SOUND + """for (let i = 0; i < 100 && real("sound inside")?.linkedPanel; i++) await wait(100);
      for (const name of ["sound tile", "sound row", "sound inside", "sound away"]) play(real(name), true);
      return wins().flatMap(w => w.gBrowser.tabs.filter(t => t.label === "sound inside").map(t => ({url: url(t).slice(-40), playing: t.soundPlaying, loaded: !!t.linkedPanel, hidden: t.hidden})));""")
    r = sidebar_page(m, FIND + """
      const [here, away] = args;
      await until(() => tile("sound tile").querySelector(".sound") && row("sound row").querySelector(".sound") && head("Sound folder").querySelector(".sound") && dot(away).querySelector(".sound"));
      const inside = (e, mark) => { const a = e.getBoundingClientRect(), b = mark.getBoundingClientRect(); return b.left >= a.left && b.right <= a.right && b.top >= a.top && b.bottom <= a.bottom; };
      // On the bar the mark is under its dot, hanging a little into the bar's own room below the
      // button (sidebar.css), so it is clear of the active space's larger dot: across it, starting in it.
      const atDot = (e, mark) => { const a = e.getBoundingClientRect(), b = mark.getBoundingClientRect(); return b.left >= a.left && b.right <= a.right && b.top >= a.top && b.top < a.bottom; };
      return {tile: !!tile("sound tile").querySelector(".sound"), row: !!row("sound row").querySelector(".sound"), head: !!head("Sound folder").querySelector(".sound"),
              dotAway: !!dot(away).querySelector(".sound"), dotHere: !!dot(here).querySelector(".sound"), silentDots: [...doc.querySelectorAll("#spaces .space")].filter(b => b.querySelector(".sound")).length,
              onlyThose: [...doc.querySelectorAll(".sound")].length, svg: !!tile("sound tile").querySelector(".sound svg"), emoji: /[\\u{1F500}-\\u{1F5FF}]/u.test(doc.body.textContent),
              insideTile: inside(tile("sound tile"), tile("sound tile").querySelector(".sound")), insideDot: atDot(dot(away), dot(away).querySelector(".sound")),
              boxes: places(away)};""", here, away)
    check("the sound of a page in another window shows on an essential's tile", r["tile"] and r["svg"] and r["insideTile"], str(r))
    check("and on a tab's row, drawn and not as an emoji", r["row"] and not r["emoji"], str(r))
    check("and on the head of a closed folder it is in", r["head"], f"{r} {playing}")
    check("and on the dot of another space, and of this space, as both play", r["dotAway"] and r["insideDot"] and r["dotHere"] and r["silentDots"] == 2, str(r))
    check("the marks move nothing", r["boxes"] == before, f"{before} became {r['boxes']}")

    # A click on a mark mutes the real page, wherever it is, and selects nothing.
    def state():
        return m.js(H + SOUND + """const a = main(), b = other();
          return {selected: [a.gBrowser.selectedTab.label, b.gBrowser.selectedTab.label], muted: Object.fromEntries(["sound tile", "sound row", "sound inside"].map(n => [n, real(n).muted])),
                  windows: Object.fromEntries(["sound tile", "sound row", "sound inside", "sound away"].map(n => [n, winOf(real(n)) === b ? "other" : "main"]))};""")

    def state_until(test):
        for _ in range(40):
            s = state()
            if test(s):
                break
            time.sleep(0.2)
        return s
    ok = sidebar_click(m, '[...doc.querySelectorAll("#essentials .tile")].find(e => e.title.split("\\n")[0] === "sound tile")?.querySelector(".sound")')
    state_until(lambda s: s["muted"]["sound tile"])
    time.sleep(0.5)  # a selection, if the click went on to the tile, would have come with it
    s0 = state()
    r = sidebar_page(m, FIND + """await until(() => tile("sound tile").querySelector(".sound.muted"));
      return {muted: !!tile("sound tile").querySelector(".sound.muted"), title: tile("sound tile").querySelector(".sound").title, active: tile("sound tile").classList.contains("active"), row: !!row("sound row").querySelector(".sound.muted")};""")
    check("a click on a tile's mark mutes the real tab in the other window", ok and s0["muted"]["sound tile"] and s0["windows"]["sound tile"] == "other", str(s0))
    check("and does not select it", not r["active"] and s0["selected"][0].startswith("Tidier") and s0["selected"][1] != "sound tile", str((r, s0)))
    check("the tile then offers to unmute, and only it changed", r["muted"] and r["title"] == "Unmute" and not r["row"], str(r))
    sidebar_click(m, '[...doc.querySelectorAll("#essentials .tile")].find(e => e.title.split("\\n")[0] === "sound tile")?.querySelector(".sound")')
    s = state_until(lambda s: not s["muted"]["sound tile"])
    check("a second click unmutes it", s["muted"]["sound tile"] is False, str(s))
    # The row's and the closed head's.
    ok = sidebar_click(m, '[...doc.querySelectorAll("#tabs .tab")].find(e => e.title.split("\\n")[0] === "sound row")?.querySelector(".sound")')
    ok2 = sidebar_click(m, '[...doc.querySelectorAll("#tabs .head")].find(e => e.title === "Sound folder")?.querySelector(".sound")')
    s1 = state_until(lambda s: s["muted"]["sound row"] and s["muted"]["sound inside"])
    r = sidebar_page(m, FIND + """await until(() => head("Sound folder").querySelector(".sound.muted"));
      return {collapsed: head("Sound folder").parentElement.classList.contains("collapsed"), mark: !!head("Sound folder").querySelector(".sound.muted"), dotHere: !!dot(args[0]).querySelector(".sound")};""", here)
    check("a click on a row's mark on a placeholder mutes the real tab", ok and s1["muted"]["sound row"] and s1["windows"]["sound row"] == "other", str(s1))
    check("a click on a closed folder's mark mutes what is in it, and it stays closed", ok2 and s1["muted"]["sound inside"] and r["collapsed"] and r["mark"], str((s1, r)))
    m.js(H + SOUND + """play(real("sound tile"), false); return 1;""")
    r = sidebar_page(m, FIND + """await until(() => !dot(args[0]).querySelector(".sound"));
      return {dotHere: !!dot(args[0]).querySelector(".sound"), row: !!row("sound row").querySelector(".sound.muted"), tile: !!tile("sound tile").querySelector(".sound")};""", here)
    check("with only muted sound left, this space's dot has no mark, and the muted row keeps its", not r["dotHere"] and r["row"], str(r))
    check("a tile that stopped playing has no mark", not r["tile"], str(r))
    idle = extension_message(m, {"type": "idle", "ms": 5000})
    if not idle["alarms"]:
        check("while something plays, Tidier does nothing", idle["jobs"] == 0 and idle["views"] == 0, str(idle))

    # A click on a dot itself switches, as always; on its mark it goes to the tab. The
    # bar notes a click that reaches it: one on the mark must end there, or it switches too.
    sidebar_page(m, """doc.getElementById("spaces").addEventListener("click", () => { doc.documentElement.dataset.barClicked = "1"; }); return 1;""")
    sidebar_click(m, f"""doc.querySelector('#spaces .space[data-space="{away}"] .dot')""")
    r = sidebar_page(m, FIND + """await until(() => dot(args[0]).classList.contains("active"), 3000); return {active: dot(args[0]).classList.contains("active"), bar: doc.documentElement.dataset.barClicked};""", away)
    tab = m.js(H + """const w = main(); return w.gBrowser.selectedTab.label;""")
    check("a click on a dot with a mark switches space, as always", r["active"] and r["bar"] == "1", str((r, tab)))
    sidebar_page(m, f"""delete doc.documentElement.dataset.barClicked; send({{type: "space", space: "{here}"}}); await wait(1200); return 1;""")
    ok = sidebar_click(m, f"""doc.querySelector('#spaces .space[data-space="{away}"] .sound')""")
    s2 = state_until(lambda s: s["selected"][0] == "sound away" and s["windows"]["sound away"] == "main")
    r = sidebar_page(m, FIND + """await until(() => dot(args[0]).classList.contains("active"));
      return {active: dot(args[0]).classList.contains("active"), row: !!row("sound away")?.querySelector(".sound"), selected: !!row("sound away")?.classList.contains("active"), dot: !!dot(args[0]).querySelector(".sound"), bar: doc.documentElement.dataset.barClicked ?? null};""", away)
    check("a click on a dot's mark goes to the tab that plays, and pulls it into this window", ok and s2["selected"][0] == "sound away" and s2["windows"]["sound away"] == "main" and r["bar"] is None, str((s2, r)))
    check("and to its space, where its row shows it", r["active"] and r["row"] and r["selected"] and r["dot"], str(r))
    # An essential in another space comes over another way (essentialShown, essentials.js).
    m.js(H + SOUND + """play(real("sound tile"), true); return 1;""")
    sidebar_page(m, FIND + """await until(() => dot(args[0]).querySelector(".sound")); return 1;""", here)
    ok = sidebar_click(m, f"""doc.querySelector('#spaces .space[data-space="{here}"] .sound')""")
    s3 = state_until(lambda s: s["selected"][0] == "sound tile" and s["windows"]["sound tile"] == "main")
    r = sidebar_page(m, FIND + """await until(() => tile("sound tile")?.classList.contains("active"));
      return {active: !!tile("sound tile")?.classList.contains("active"), mark: !!tile("sound tile")?.querySelector(".sound:not(.muted)"), loaded: !tile("sound tile")?.classList.contains("unloaded")};""")
    check("a dot's mark also brings an essential from another space and window, still playing", ok and s3["selected"][0] == "sound tile" and s3["windows"]["sound tile"] == "main" and r["active"] and r["mark"] and r["loaded"], str((s3, r)))

    # All quiet again, and gone.
    m.js(H + SOUND + """for (const w of wins()) for (const t of w.gBrowser.tabs) { if (t.soundPlaying) play(t, false); if (t.muted) t.toggleMuteAudio(); } return 1;""")
    r = sidebar_page(m, FIND + """await until(() => !doc.querySelector(".sound")); const marks = doc.querySelectorAll(".sound").length;
      send({type: "space", space: args[0]}); await until(() => head("Sound folder"));
      send({type: "deleteFolder", key: head("Sound folder").dataset.folderHead}); await wait(800);
      return {marks};""", here)
    check("when it stops, every mark is gone", r["marks"] == 0, str(r))

    # A page whose title ticks is drawn again all the time, and a redraw replaces what is
    # under the pointer: a press must still do what it was for, however long it takes.
    m.js(H + SOUND + """const a = main(), t = a.gBrowser.addTrustedTab(args[0] + "/ticking", {userContextId: args[1], inBackground: true});
      a.__ticking = t;
      for (let i = 0; i < 80 && !/^[0-9]+$/.test(t.label); i++) await wait(100);
      play(t, true); return 1;""", m.pages, int(here.split("-")[-1]))
    TICKING = '[...doc.querySelectorAll("#tabs .tab")].find(e => /^[0-9]+$/.test(e.title.split("\\n")[0]))'
    r = sidebar_page(m, FIND + f"""const ticking = () => {TICKING}; await until(() => ticking()?.querySelector(".sound"));
      const first = ticking().title; await until(() => ticking().title !== first); return {{ticks: ticking().title !== first}};""")
    ok = sidebar_click(m, TICKING + '?.querySelector(".sound")', hold=1.5)
    ticked = m.js(H + """const t = main().__ticking; for (let i = 0; i < 40 && !t.muted; i++) await wait(100); return {muted: t.muted, selected: main().gBrowser.selectedTab === t};""")
    check("a press on a mark mutes, also while its row is being drawn again", ok and r["ticks"] and ticked["muted"] and not ticked["selected"], str((ok, r, ticked)))
    r = sidebar_page(m, FIND + f"""const ticking = () => {TICKING}; await until(() => ticking()?.querySelector(".sound.muted"));
      const first = ticking().title; await until(() => ticking().title !== first); return {{muted: !!ticking().querySelector(".sound.muted"), ticks: ticking().title !== first}};""")
    check("and what waited is drawn once it is let go", r["muted"] and r["ticks"], str(r))
    # A redraw touches only what changed (sidebar.js): a clock or a chat badge in the space
    # shown rewrote every row's and tile's tooltip and folder on each view, some 230 at a time.
    r = sidebar_page(m, FIND + f"""const ticking = () => {TICKING}; await until(ticking);
      // The line about the folder deleted above goes by itself, which is a change: it fades,
      // and then its room goes (note.js), so both are waited for.
      await until(() => !doc.getElementById("note").classList.contains("shown") && !doc.getElementById("note").classList.contains("in-room"), 15000);
      const touched = new Set(); let records = 0;
      const where = n => {{ const e = n.nodeType === 1 ? n : n.parentElement; const at = e?.closest?.("[data-tab], [data-folder-head], .space"); return at ? (at.dataset.tab ?? at.dataset.folderHead ?? at.dataset.space) : (e?.id || e?.tagName); }};
      const o = new page.MutationObserver(list => {{ for (const x of list) {{ records++; touched.add(where(x.target)); }} }});
      o.observe(doc.documentElement, {{subtree: true, attributes: true, childList: true, characterData: true}});
      const first = ticking().title; await until(() => ticking().title !== first); await wait(1500); o.disconnect();
      return {{touched: [...touched], ticking: ticking().dataset.tab, records}};""")
    check("a page whose title ticks rewrites its own row and nothing else", r["records"] > 0 and r["touched"] == [r["ticking"]], str(r))
    ok = sidebar_click(m, TICKING + '?.querySelector(".close")', hold=1.5)
    closed = m.js(H + """const a = main(); for (let i = 0; i < 40 && a.gBrowser.tabs.includes(a.__ticking); i++) await wait(100); return !a.gBrowser.tabs.includes(a.__ticking);""")
    check("a press on a row's × closes, also while the row is being drawn again", ok and closed, str(closed))
    # One change during a press that ends elsewhere: no click and no later event, so it
    # has to be drawn because you let go. The page itself makes the change, a moment into
    # the press, and notes what is drawn a moment later. On a dot's mark, as moving away
    # from a row would drag the row, and in a headless Firefox such a drag never ends.
    m.js(H + SOUND + """play(real("sound row"), true); return 1;""")
    sidebar_page(m, FIND + """const [here] = args; await until(() => dot(here).querySelector(".sound"));
      const [tab] = await page.browser.tabs.query({title: "sound row", audible: true});
      const note = (name, was) => { doc.documentElement.dataset[name] = was ? "drawn" : "waits"; };
      doc.addEventListener("pointerdown", () => {
        setTimeout(() => page.browser.tabs.update(tab.id, {muted: true}), 200);
        setTimeout(() => note("whilePressed", !dot(here).querySelector(".sound")), 1000);
      }, {once: true});
      // Noted here: looking from outside (sidebar_page) asks for a view itself.
      doc.addEventListener("pointerup", async () => { await until(() => !dot(here).querySelector(".sound"), 3000); note("letGo", !dot(here).querySelector(".sound")); }, {once: true});
      return 1;""", here)
    let_go = sidebar_press(m, f"""doc.querySelector('#spaces .space[data-space="{here}"] .sound')""")
    time.sleep(1.5)
    let_go(5, 5)
    time.sleep(3.5)
    r = sidebar_page(m, """return {...doc.documentElement.dataset};""")
    check("what is pressed waits, and a press that ends elsewhere still shows what changed", r.get("whilePressed") == "waits" and r.get("letGo") == "drawn", str(r))
    m.js(H + SOUND + """const t = real("sound row"); play(t, false); t.toggleMuteAudio(); return 1;""")
    m.js(H + """for (const w of wins()) for (const t of w.gBrowser.tabs) if (t.pinned && t.label === "sound tile") { w.gBrowser.unpinTab(t); break; }
      await wait(2500);
      await removeWhere((w, t) => t.label.startsWith("sound ") || t === main().__ticking);
      if (args[0]) await close(other());
      return 1;""", opened)


def alone_news(m):
    # Pages in the background, each named by its address so that its row can be found:
    # one in the list, one in a folder that closes, one as an essential, one in another space.
    name = "smoke-news-"
    page = lambda which: f"{m.pages}/titled?{name}{which}"
    spaces = sidebar_page(m, "return spaces();")
    remembered = extension_message(m, {"type": "stats"})["sizes"]["newsSeen"]
    here = next(s["id"] for s in spaces if s["active"])
    there = next(s["id"] for s in spaces if not s["active"] and s["id"] != "firefox-container-4")
    number = lambda space: int(space.rsplit("-", 1)[1])
    opened = m.js(H + """const [pages, here, there] = args, w = main(); w.focus();
      const tabs = pages.map(([address, inHere]) => w.gBrowser.addTrustedTab(address, {userContextId: inHere ? here : there, inBackground: true}));
      for (let i = 0; i < 100 && !tabs.every(t => role(w, t) === "live"); i++) await wait(100);
      return tabs.map(t => role(w, t));""", [[page("row"), True], [page("folder"), True], [page("tile"), True], [page("there"), False], [f"{m.pages}/ticking?{name}clock", True]], number(here), number(there))
    check("the test's background pages are Tidier's tabs", opened == ["live"] * 5, str(opened))
    pinned = m.js(H + """const w = main(), t = w.gBrowser.tabs.find(x => url(x).includes(args[0])); w.gBrowser.pinTab(t);
      for (let i = 0; i < 100 && !ek(w, t); i++) await wait(100);
      return !!ek(w, t);""", name + "tile")
    check("one of them is an essential", pinned, str(pinned))
    # JavaScript for each check: what has a mark now, under a rule the sidebar draws by.
    marked = """
      const named = which => [...doc.querySelectorAll(".tab, .tile")].find(r => r.title.includes(args[0] + which));
      const has = () => ({
        rows: [...doc.querySelectorAll("#tabs .tab.news")].filter(r => r.offsetParent).map(r => r.title.split("\\n")[0].replace(args[0], "")),
        heads: [...doc.querySelectorAll(".folder.collapsed.news")].map(f => f.querySelector(".head .title").textContent),
        tiles: [...doc.querySelectorAll(".tile.news")].map(r => r.title.split("\\n")[0].replace(args[0], "")),
        spaces: [...doc.querySelectorAll(".space.news")].map(b => b.dataset.space),
      });
      // By the clock: this page is a tab in the background, whose timers Firefox slows down.
      const when = async test => { for (const end = Date.now() + 8000; Date.now() < end && !test();) await wait(100); };
      const until = async test => { await when(() => test(has())); return has(); };
      const bar = id => doc.querySelector(`.space[data-space="${id}"]`);
      const inSpace = id => when(() => spaces().find(s => s.active).id === id);
      // What is really drawn of a dot, which a class alone does not tell: an empty box, a wrong
      // selector or a missing colour would all leave the class in place and nothing to see.
      const colour = css => { const probe = doc.createElement("i"); probe.style.color = css; doc.body.append(probe); const c = page.getComputedStyle(probe).color; probe.remove(); return c; };
      const dot = (e, which) => { const d = page.getComputedStyle(e, which); return {content: d.content, width: parseFloat(d.width), height: parseFloat(d.height), position: d.position, animation: d.animationName, color: d.backgroundColor}; };
      const accent = () => colour(page.getComputedStyle(doc.documentElement).getPropertyValue("--accent"));
      // What another window's sidebar is told: this page can ask as that window's sidebar does.
      const viewOf = windowId => new Promise(done => {
        const p = page.browser.runtime.connect({name: "sidebar"});
        p.onMessage.addListener(view => { const got = JSON.parse(page.JSON.stringify(view)); p.disconnect(); done(got); });
        p.postMessage(page.JSON.parse(JSON.stringify({type: "hello", windowId})));
      });
      const inView = (view, which) => [...view.tabs, ...view.folders.flatMap(f => f.tabs)].find(t => t.title.includes(args[0] + which));"""
    r = sidebar_page(m, marked + """
      send({type: "newFolder", space: args[1], name: args[0] + "kept"});
      let head = null;
      for (let i = 0; i < 50 && !head; i++) { await wait(100); head = [...doc.querySelectorAll(".folder .head")].find(h => h.title === args[0] + "kept"); }
      send({type: "moveTab", tabId: Number(named("folder").dataset.tab), folder: head.dataset.folderHead, before: null});
      for (let i = 0; i < 50 && !head.parentElement.querySelector(".tab"); i++) await wait(100);
      // A tab here is the last used, or coming back to this space below selects the newest of these
      // pages: Firefox counts a tab opened in the background as used then, and a selected tab has no dot.
      const mine = [...doc.querySelectorAll("#essentials .tile, #tabs .tab")].find(x => !x.title.includes(args[0]) && !x.title.includes("moz-extension:"));
      mine.click();
      await when(() => mine.classList.contains("active"));
      // The other space's last used tab is another one, so that going there does not select this page.
      bar(args[2]).click();
      await inSpace(args[2]);
      const other = [...doc.querySelectorAll("#tabs .tab")].find(x => !x.title.includes(args[0]));
      other.click();
      await when(() => other.classList.contains("active"));
      bar(args[1]).click();
      await inSpace(args[1]);
      return {key: head.dataset.folderHead, filled: !!head.parentElement.querySelector(".tab"), back: spaces().find(s => s.active).id};""", name, here, there)
    check("a folder has one of them in it", r["filled"] and r["back"] == here, str(r))
    folder_key = r["key"]
    # Past the quiet after loading. A title that only ticks says nothing, however long it does.
    time.sleep(6)
    r = sidebar_page(m, marked + """
      const ticking = [...doc.querySelectorAll("#tabs .tab")].filter(x => /^\\d+$/.test(x.title.split("\\n")[0]));
      return {ticking: ticking.length, seconds: ticking.map(x => Number(x.title.split("\\n")[0])), has: has()};""", name)
    check("a title that only ticks has no dot", r["ticking"] == 1 and r["has"] == {"rows": [], "heads": [], "tiles": [], "spaces": []}, str(r))
    m.js(H + """const w = main(); await removeWhere((x, t) => url(t).includes("/ticking?")); return 1;""")

    place = """const r = named("row"), t = r.querySelector(".title").getBoundingClientRect(), i = r.querySelector("img, .letter").getBoundingClientRect();
      return {title: [t.left, t.top, t.width], icon: [i.left, i.top], row: r.getBoundingClientRect().height};"""
    before = sidebar_page(m, marked + place, name)
    set_title(m, page("row"), f"{name}row Anna wrote")
    r = sidebar_page(m, marked + """
      const got = await until(h => h.rows.length);
      const row = named("row");
      const t = row.querySelector(".title").getBoundingClientRect(), i = row.querySelector("img, .letter").getBoundingClientRect();
      return {got, dot: dot(row, "::before"), accent: accent(), title: [t.left, t.top, t.width], icon: [i.left, i.top], row: row.getBoundingClientRect().height};""", name)
    check("a background page's new title gives its row a dot", r["got"]["rows"] == ["row Anna wrote"], str(r))
    shows = lambda d, color: d and d["content"] != "none" and d["width"] >= 5 and d["height"] >= 5 and d["position"] == "absolute" and d["animation"] == "none" and d["color"] == color
    check("the dot is drawn, still, and in the space's colour", shows(r["dot"], r["accent"]), str(r))
    check("the dot moves nothing in the row", all(before[k] == r[k] for k in ("title", "icon", "row")), f"{before} -> {r}")
    set_title(m, page("folder"), f"{name}folder (1) unread")
    set_title(m, page("tile"), f"{name}tile (1) unread")
    set_title(m, page("there"), f"{name}there (1) unread")
    r = sidebar_page(m, marked + """
      await until(h => h.rows.length === 2 && h.tiles.length && h.spaces.length);
      [...doc.querySelectorAll(".folder .head")].find(h => h.title === args[0] + "kept").click();
      // Closed, it rests: an unloaded page says nothing more, and what it said stays.
      await until(h => h.heads.length);
      await when(() => named("folder").classList.contains("unloaded"));
      const got = has(), seen = (selector, pseudo) => { const e = doc.querySelector(selector); return e && dot(e, pseudo); };
      return {...got, rested: named("folder").classList.contains("unloaded"), accent: accent(), other: colour(bar(args[1]).style.getPropertyValue("--color")),
        head: seen(".folder.collapsed.news > .head", "::before"), tile: seen(".tile.news", "::before"),
        // On the bar the dot itself says it, in its full colour among the pale ones: a second dot would read as one more space.
        space: (() => { const full = b => { const d = b?.querySelector(".dot"); if (!d) return null; for (const a of d.getAnimations()) a.finish(); return {color: page.getComputedStyle(d).backgroundColor, after: page.getComputedStyle(b, "::after").content}; };
          const plain = doc.querySelector("#spaces .space:not(.active):not(.news)");
          return {news: full(bar(args[1])), plain: full(plain), plainOwn: plain && colour(plain.style.getPropertyValue("--color"))}; })()};""", name, there)
    check("a closed folder shows that a tab in it has news, also once the tab has unloaded", r.get("heads") == [name + "kept"] and r["rested"] and shows(r["head"], r["accent"]), str(r))
    check("an essential's tile shows it", len(r["tiles"]) == 1 and r["tiles"][0].startswith("tile") and shows(r["tile"], r["accent"]), str(r))
    dots = r.get("space") or {}
    check("another space's dot shows it, in that space's full colour, with no second mark", r["spaces"] == [there] and dots.get("news") and dots["news"]["color"] == r["other"] and dots["news"]["after"] == "none"
          and (not dots.get("plain") or dots["plain"]["color"] != dots["plainOwn"]), str(r))

    # Selecting clears each, by real clicks in the sidebar.
    r = sidebar_page(m, marked + """
      const out = {};
      named("row").click();
      out.row = await until(h => !h.rows.length);
      named("tile").click();
      out.tile = await until(h => !h.tiles.length);
      const head = [...doc.querySelectorAll(".folder .head")].find(h => h.title === args[0] + "kept");
      head.click();
      await when(() => !head.parentElement.classList.contains("collapsed"));
      out.open = await until(h => h.rows.length);  // an open folder's head has no dot: its row has it
      named("folder").click();
      out.folder = await until(h => !h.rows.length);
      bar(args[2]).click();
      out.inThere = await until(h => !h.spaces.length && h.rows.length);  // in the space itself, its list shows it, not the bar
      named("there").click();
      out.there = await until(h => !h.rows.length);
      bar(args[1]).click();
      await inSpace(args[1]);
      out.back = has();
      return out;""", name, here, there)
    empty = {"rows": [], "heads": [], "tiles": [], "spaces": []}
    check("selecting the row clears its dot", not r["row"]["rows"], str(r))
    check("selecting the essential clears its tile's dot", not r["tile"]["tiles"], str(r))
    check("an open folder shows the dot on its row, not on its head", not r["open"]["heads"] and r["open"]["rows"] == ["folder (1) unread"], str(r))
    check("selecting the tab clears its folder's dot", r["folder"] == {**empty, "spaces": [there]}, str(r))
    check("in the space itself its list shows the news, and the bar does not", r["inThere"]["rows"] == ["there (1) unread"] and not r["inThere"]["spaces"], str(r))
    check("selecting the tab clears the space's dot, and nothing is left", r["there"] == empty and r["back"] == empty, str(r))

    # The same tab in another window, where it is a placeholder.
    far = page("far")
    r = m.js(H + """const [address, here] = args, a = main(); a.focus();
      const t = a.gBrowser.addTrustedTab(address, {userContextId: here, inBackground: true});
      for (let i = 0; i < 100 && role(a, t) !== "live"; i++) await wait(100);
      const k = key(a, t), w = a.OpenBrowserWindow(); w.__extra = true; w.__news = true;
      const copy = () => w.gBrowser?.tabs.find(x => key(w, x) === k);
      for (let i = 0; i < 100 && !copy(); i++) await wait(100);
      a.focus(); await wait(500);
      return {copy: role(w, copy()), id: w.docShell.outerWindowID};""", far, number(here))
    check("another window has a placeholder of the page", r["copy"] == "ghost", str(r))
    second = r["id"]
    in_use = H + """const w = wins().find(x => x.__news); w.focus(); await wait(500); return 1;"""
    # Firefox's own audible state, set from chrome code as a page playing sound sets it.
    sound = H + """const [address, on] = args, w = main(), t = w.gBrowser.tabs.find(x => url(x) === address);
      t.toggleAttribute("soundplaying", on); w.gBrowser._tabAttrModified(t, ["soundplaying"]); return 1;"""
    time.sleep(6)  # past the quiet, for both pages
    m.js(sound, page("row"), True)
    set_title(m, page("row"), f"{name}row (1) ding")
    set_title(m, far, f"{name}far (1) unread")
    r = sidebar_page(m, marked + """
      const got = await until(h => h.rows.length === 2);
      return {got, elsewhere: inView(await viewOf(args[1]), "far")};""", name, second)
    check("a sound that has only just begun does not stop the dot", "row (1) ding" in r["got"]["rows"], str(r))
    check("in the other window the placeholder has the dot too", r["elsewhere"]["news"] and not r["elsewhere"]["loaded"], str(r))
    # Selecting the placeholder there is seeing it: the page comes to that window, and nothing is left.
    r = m.js(H + """const [address] = args, a = main(), w = wins().find(x => x.__news), page = () => a.gBrowser.tabs.find(x => url(x) === address);
      const k = key(a, page());
      w.focus(); await wait(500);
      w.gBrowser.selectedTab = w.gBrowser.tabs.find(x => key(w, x) === k);
      const here = () => a.gBrowser.tabs.filter(x => key(a, x) === k).map(x => role(a, x));
      for (let i = 0; i < 100 && !(url(w.gBrowser.selectedTab) === address && here().length); i++) await wait(100);
      return {pulled: url(w.gBrowser.selectedTab) === address, here: here()};""", far)
    check("selecting the placeholder brings the page to that window", r["pulled"] and r["here"] == ["ghost"], str(r))
    r = sidebar_page(m, marked + """
      const first = await until(h => h.rows.length === 1);
      named("row").click();
      const all = await until(h => !h.rows.length);
      const elsewhere = inView(await viewOf(args[1]), "far");
      named("folder").click();  // leave the page that plays, so that it is a page in the background
      await when(() => named("folder").classList.contains("active"));
      return {first, all, elsewhere};""", name, second)
    check("selecting the placeholder clears the dot in both windows", r["first"]["rows"] == ["row (1) ding"] and not r["elsewhere"]["news"], str(r))
    check("selecting the row clears the other dot", not r["all"]["rows"], str(r))
    # In the window you are using, the selected tab is what you are looking at. A song that goes on is no news.
    m.js(in_use)
    time.sleep(6)
    set_title(m, far, f"{name}far as you read it")
    set_title(m, page("row"), f"{name}row (2) the next song")
    r = sidebar_page(m, marked + """
      await when(() => named("far").title.includes("as you read it") && named("row").title.includes("next song"));
      return {titles: [named("far").title, named("row").title], has: has()};""", name)
    check("no dot on what you are looking at in the other window", "far" not in str(r["has"]["rows"]) and "as you read it" in r["titles"][0], str(r))
    check("no dot on a page that has been playing for a while", "row" not in str(r["has"]["rows"]) and "next song" in r["titles"][1], str(r))
    m.js(sound, page("row"), False)
    # Selected there, but with you here: it is not seen, and going there is.
    time.sleep(6)
    set_title(m, far, f"{name}far (2) unread")
    r = sidebar_page(m, marked + """
      const got = await until(h => h.rows.length);
      return {got, elsewhere: inView(await viewOf(args[1]), "far")};""", name, second)
    check("a tab selected in a window you are not using gets a dot", r["got"]["rows"] == ["far (2) unread"] and r["elsewhere"]["news"] and r["elsewhere"]["active"], str(r))
    m.js(in_use)
    stats = extension_message(m, {"type": "stats"})
    check("going to that window clears it", stats["sizes"]["newsMarks"] == 0, str(stats["sizes"]))
    # Closing that window with a dot on its page: the page is gone, and with it the dot.
    time.sleep(6)
    set_title(m, far, f"{name}far (3) unread")
    r = sidebar_page(m, marked + "return await until(h => h.rows.length);", name)
    check("and a new message gives it a dot again", r["rows"] == ["far (3) unread"], str(r))
    m.js(H + """await close(wins().find(x => x.__news)); return 1;""")
    r = sidebar_page(m, marked + """
      const got = await until(h => !h.rows.length), far = named("far");
      if (far) send({type: "close", tabId: Number(far.dataset.tab)});
      await when(() => !named("far"));
      return {got, far: !!far, unloaded: far?.classList.contains("unloaded")};""", name)
    check("closing the window with the page clears the dot, and the placeholder stays", not r["got"]["rows"] and r["far"] and r["unloaded"], str(r))

    # What was opened goes again; nothing stays behind in memory.
    sidebar_page(m, """send({type: "deleteFolder", key: args[0]}); await wait(800); return 1;""", folder_key)
    m.js(H + """const w = main();
      for (const t of w.gBrowser.tabs.filter(t => t.pinned && url(t).includes(args[0]))) w.gBrowser.unpinTab(t);
      await wait(3000);
      await removeWhere((x, t) => url(t).includes(args[0]));
      return 1;""", name)
    stats = extension_message(m, {"type": "stats"})
    # What is remembered is for pages loaded now (news.js forgets one as it is unloaded), which
    # a tab selected meanwhile can have added to.
    loaded = m.js(H + """return wins().flatMap(w => w.gBrowser.tabs.filter(t => t.linkedPanel && /^https?:/.test(url(t)))).length;""")
    check("no mark stays once its pages are gone, and nothing is kept of them", stats["sizes"]["newsMarks"] == 0 and stats["sizes"]["newsSeen"] <= loaded, f"{remembered}, {loaded} loaded -> {stats['sizes']}")


def alone_touches(m):
    # What nobody has to know about: tooltips, kept icons, warming a tab up, the sign of a slow load.
    space = int(sidebar_page(m, """return spaces().find(s => s.active).id;""").split("-")[-1])
    opened = m.js(H + """const a = main();
      // With motion, whatever the machine's own setting says (a GitHub runner asks for less):
      // the still sign of less motion is checked on its own below.
      Services.prefs.setIntPref("ui.prefersReducedMotion", 0);
      let w = other(), opened = !w;
      if (opened) { w = a.OpenBrowserWindow(); w.__smoke = true; for (let i = 0; i < 100 && !w.gBrowser?.tabs.some(t => t.pinned); i++) await wait(100); await wait(1000); }
      // In the other window, so that this window has only its placeholder.
      w.gBrowser.addTrustedTab(args[0] + "/icon?elsewhere=secret", {userContextId: args[1], inBackground: true});
      await wait(300);
      a.gBrowser.addTrustedTab(args[0] + "/icon?warm", {userContextId: args[1], inBackground: true});
      a.gBrowser.addTrustedTab(args[0] + "/icon?record", {userContextId: args[1], inBackground: true});
      a.gBrowser.addTrustedTab(args[0] + "/icon?cross", {userContextId: args[1], inBackground: true});
      a.gBrowser.addTrustedTab(args[0] + "/slow-icon", {userContextId: args[1], inBackground: true});
      // A loaded essential: the sign and the warm-up are for a tile as well.
      a.gBrowser.pinTab(a.gBrowser.addTrustedTab(args[0] + "/icon?tile", {userContextId: args[1], inBackground: true}));
      await wait(1000);
      // Sees what the extension's call reaches, also what it should not.
      a.__warmed = [];
      const warmup = a.__warmup = a.gBrowser.warmupTab;
      a.gBrowser.warmupTab = function (t) { a.__warmed.push(url(t)); return warmup.call(this, t); };
      // The sidebar page in front: timers in a page behind other tabs run late, and a pointer does not reach it.
      a.__selected = a.gBrowser.selectedTab;
      a.gBrowser.selectedTab = a.gBrowser.tabs.find(t => url(t).includes("/sidebar/sidebar.html"));
      await wait(500);
      return opened;""", m.pages, space)
    until = """const until = async (test, ms = 15000) => { for (const t0 = Date.now(); Date.now() - t0 < ms; await wait(20)) { const v = await test(); if (v) return v; } return null; };
      const here = await page.browser.windows.getCurrent();
      // The row of the tab in this window whose address holds `part`.
      const rowOf = async part => { const t = (await page.browser.tabs.query({windowId: here.id})).find(x => x.url.includes(part));
        return t && doc.querySelector(`#tabs .tab[data-tab="${t.id}"]`); };
      const status = async id => (await page.browser.tabs.get(id)).status;"""
    r = sidebar_page(m, until + """
      const pages = arguments[0], ctx = arguments[1], icon = "img[src^='data:image/svg']", out = {};

      // Tooltips: a placeholder knows its real address only from the record.
      const ghost = await until(() => doc.querySelector("#tabs .tab.unloaded[title*='/icon']"));
      out.ghostTip = ghost?.title;
      out.ghostId = Number(ghost?.dataset.tab);
      out.tileTip = doc.querySelector("#essentials .tile")?.title;

      // Where to take the pointer, below.
      const warm = await until(() => rowOf("/icon?warm"));
      const at = e => { const b = e.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; };
      out.warmId = Number(warm.dataset.tab);
      const tile = await until(async () => { const t = (await page.browser.tabs.query({windowId: here.id, pinned: true})).find(x => x.url.includes("/icon?tile"));
        const e = t && doc.querySelector(`#essentials .tile[data-tab="${t.id}"]`); return e?.querySelector(icon) && !e.matches(".unloaded") && e; });

      out.tileId = Number(tile?.dataset.tab);
      // The record's icon: a page without one keeps what the tab had, rather than a letter.
      const record = await until(async () => { const r = await rowOf("/icon?record"); return r?.querySelector(icon) && r; });
      if (record) {
        const id = Number(record.dataset.tab);
        await page.browser.tabs.update(id, {url: pages + "/no-icon"});
        await until(async () => record.querySelector(".title")?.textContent === "No icon" && await status(id) === "complete");
        // Asked once the record has followed the page: the background takes what a page says in
        // its own queue, and on a busy machine that was more than half a second behind.
        const t0 = Date.now(), entries = async () => Object.values((await page.browser.storage.local.get("syncedTabs")).syncedTabs).filter(e => e.url?.includes("/no-icon"));
        out.recordFollowed = await until(async () => (await entries()).length) ? Date.now() - t0 : null;
        await until(() => record.querySelector(icon), 3000);
        out.record = {own: (await page.browser.tabs.get(id)).favIconUrl ?? null, image: !!record.querySelector(icon), letter: !!record.querySelector(".letter")};
        out.recordEntry = Object.values((await page.browser.storage.local.get("syncedTabs")).syncedTabs).filter(e => e.url?.includes("/no-icon")).map(e => String(e.icon).slice(0, 60)); // (for the detail, when this fails)
      }

      // A page changing its address and nothing else, as some do as you scroll: the tooltip
      // follows, and the row is not drawn again, which could lose a click or a drag under way.
      const parts = () => [...warm.children];
      const before = parts();
      await page.browser.tabs.update(out.warmId, {url: pages + "/icon?warm#further"});
      await until(() => warm.title.endsWith("/icon#further"), 5000);
      out.addressOnly = {tip: warm.title, same: parts().every((e, i) => e === before[i])};

      // On another site the record's icon is the old site's, which says something untrue.
      const cross = await until(async () => { const r = await rowOf("/icon?cross"); return r?.querySelector(icon) && r; });
      if (cross) {
        await page.browser.tabs.update(Number(cross.dataset.tab), {url: arguments[2] + "/no-icon"});
        await until(() => cross.querySelector(".letter"), 5000);
        out.cross = {image: !!cross.querySelector(icon), letter: !!cross.querySelector(".letter"), tip: cross.title};
      }

      // A slow load: nothing at first, then a sign on the icon, then nothing, all on the same element.
      const slow = await until(async () => { const r = await rowOf("/slow-icon"); return r?.querySelector(icon) && r; });
      if (!slow) return out;
      const slowId = out.slowId = Number(slow.dataset.tab);
      const finished = async () => { await until(async () => await status(slowId) === "complete"); await wait(300); };
      await finished();
      const img = slow.querySelector("img"), signed = () => slow.querySelector("img, .letter").classList.contains("slow-load");
      out.quietBefore = !signed();
      const t0 = Date.now();
      await page.browser.tabs.reload(slowId);
      await until(signed, 6000); // the load ends no sooner than this waits: it starts late too on a busy machine
      out.shownAfter = Date.now() - t0;
      out.shown = signed();
      const moving = slow.querySelector(".slow-load")?.getAnimations()[0];
      out.animation = moving && {state: moving.playState, name: moving.animationName, iterations: moving.effect.getComputedTiming().iterations};
      // A page that takes longer than the breathing lasts: moved to the end of it, not waited for.
      moving?.finish();
      out.settled = {state: moving?.playState, opacity: page.getComputedStyle(img).opacity, stillSigned: signed()};
      // Seen in the moment the sign goes: on a busy machine the fade may be over by the first look below.
      const fading = new Promise(done => { const o = new page.MutationObserver(() => { if (!signed()) { o.disconnect(); done(img.getAnimations().map(x => x.effect.getTiming().duration)); } }); o.observe(img, {attributes: true}); });
      await until(() => !signed(), 6000);
      out.gone = !signed();
      out.fading = await Promise.race([fading, wait(1000)]);
      // Up to bright: sampled until it is there, since on a busy machine the 300 ms of the
      // fade can take a second of looks.
      out.brightening = [];
      for (let i = 0; i < 100 && out.brightening.at(-1) !== 1; i++) { out.brightening.push(Number(page.getComputedStyle(img).opacity)); await wait(20); }
      await finished();
      out.sameIcon = slow.querySelector("img") === img && img.isConnected;

      // A title arriving during a load draws the row again: the sign goes on from where it was.
      const drip = (await page.browser.tabs.create({windowId: here.id, url: pages + "/drip", cookieStoreId: "firefox-container-" + ctx, active: false})).id;
      const dripping = () => doc.querySelector(`#tabs .tab[data-tab="${drip}"]`);
      const first = await until(() => dripping()?.querySelector(".slow-load"), 6000);
      const started = first?.getAnimations()[0]?.startTime;
      await until(() => dripping()?.querySelector(".title").textContent === "Dripped", 6000);
      const second = dripping()?.querySelector(".slow-load");
      out.redrawn = {icon: !!first && !!second && second !== first, sameStart: second?.getAnimations()[0]?.startTime === started};
      await until(() => !dripping()?.querySelector(".slow-load"), 5000);
      out.dripEnded = !dripping()?.querySelector(".slow-load");

      // The same on a tile.
      if (tile) {
        await page.browser.tabs.update(Number(tile.dataset.tab), {url: pages + "/slow-icon?tile"});
        out.tileSign = !!(await until(() => tile.querySelector(".slow-load"), 6000));
        out.tileEnded = !!(await until(() => !tile.querySelector(".slow-load"), 6000));
      }
      return out;""", m.pages, space, m.pages.replace("127.0.0.1", "localhost"))
    check("a placeholder's tooltip shows its title and real address, without the query part", r.get("ghostTip") == f"Touched\n{m.pages}/icon", str(r))
    check("an essential's tooltip shows its address, without the query part", "\nhttps://example.org/" in (r.get("tileTip") or "") and "?" not in r["tileTip"], str(r))
    check("a page with no icon keeps the one in the record, not a letter", r.get("record") == {"own": None, "image": True, "letter": False}, str(r))
    check("an address changing alone changes the tooltip and draws nothing again", (r.get("addressOnly") or {}).get("same") is True and r["addressOnly"]["tip"].endswith("/icon#further"), str(r))
    check("a page on another site with no icon has a letter, not the old site's icon, and the new address", (r.get("cross") or {}).get("letter") is True and r["cross"]["image"] is False and r["cross"]["tip"].endswith("localhost:" + m.pages.rsplit(":", 1)[1] + "/no-icon"), str(r))
    check("a slow load shows nothing at first, and on the icon after half a second", r.get("quietBefore") is True and r.get("shown") is True and r.get("shownAfter", 0) >= 500, str(r))
    a = r.get("animation") or {}
    check("the sign breathes, and comes to rest by itself", a.get("name") == "slow-load" and a.get("state") == "running" and 0 < (a.get("iterations") or 0) < 100, str(r))
    fade = r.get("brightening") or [0]
    check("a page that never finishes leaves the sign still and dimmed, with nothing running", r.get("settled") == {"state": "finished", "opacity": "0.45", "stillSigned": True}, str(r))
    check("the sign goes softly when the page is there", r.get("gone") is True and r.get("fading") == [300] and fade == sorted(fade) and fade[-1] == 1, str(r))
    check("a load does not replace the icon", r.get("sameIcon") is True, str(r))
    check("a row drawn again during a load keeps its sign where it was", r.get("redrawn") == {"icon": True, "sameStart": True} and r.get("dripEnded") is True, str(r))
    check("a tile shows the sign too, and it goes", r.get("tileSign") is True and r.get("tileEnded") is True, str(r))

    # A real pointer. On the same row twice, then away and back each time: to a placeholder,
    # to the tab that is showing, and to nothing. Then to a tile, loaded and not.
    # An essential unloaded, as in every window but the one it was used in. Only now: looking
    # through the tabs to find the sidebar page, as sidebar_page does, makes Firefox load it again.
    sidebar_page(m, until + """
      const home = doc.querySelector("#essentials .tile");
      await page.browser.tabs.discard(Number(home.dataset.tab));
      await until(() => home.matches(".unloaded"));""")
    # A long list has rows below the window, out of reach of a pointer: for this moment the others make way.
    p = sidebar_page(m, until + """
      const rowBy = id => doc.querySelector(`#tabs .tab[data-tab="${id}"]`), warm = rowBy(arguments[0]), ghost = rowBy(arguments[1]), showing = doc.querySelector("#tabs .tab.active, #essentials .tile.active");
      const tile = doc.querySelector(`#essentials .tile[data-tab="${arguments[2]}"]`);
      for (const e of doc.querySelectorAll("#tabs > *")) if (![warm, ghost, showing].some(x => e === x || e.contains(x))) e.style.display = "none";
      doc.getElementById("tabs").scrollTop = 0;
      await wait(100);
      const at = e => { const b = e.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; }, box = warm.getBoundingClientRect();
      return {title: at(warm.querySelector(".title")), close: [box.right - 18, box.top + box.height / 2], ghost: at(ghost), showing: at(showing), nothing: at(doc.getElementById("space-name")), tile: at(tile), ghostTile: at(doc.querySelector("#essentials .tile"))};""", r.get("warmId"), r.get("ghostId"), r.get("tileId"))
    check("the rows for the pointer are there", "title" in p, str(p))
    pointer_over(m, p["title"], p["close"], p["ghost"], p["title"], p["showing"], p["close"], p["nothing"], p["title"], p["ghostTile"], p["tile"], p["tile"])
    sidebar_page(m, """for (const e of doc.querySelectorAll("#tabs > *")) e.style.display = ""; return 1;""")
    warmed = m.js(H + "for (let i = 0; i < 40 && main().__warmed.length < 5; i++) await wait(50); await wait(200); return main().__warmed;")
    check("a tab is warmed once for each time the pointer comes to it, and only a loaded one", len(warmed) == 5 and all("/icon?warm" in u for u in warmed[:4]) and "?tile" in warmed[4], str(warmed))

    # The sidebar panel itself, as in use: the page above is the same page, opened in a tab, since
    # a test can take a real pointer only there. Here a pointer's event is sent to a row instead.
    r2 = sidebar_page(m, until + """
      const panel = page.browser.extension.getViews({type: "sidebar", windowId: here.id})[0];
      if (!panel) return {panel: false};
      const rowThere = id => panel.document.querySelector(`#tabs .tab[data-tab="${id}"]`), slow = rowThere(arguments[0]);
      const out = {panel: true, tip: slow?.title};
      rowThere(arguments[1])?.dispatchEvent(new panel.MouseEvent("mouseover", {bubbles: true}));
      await page.browser.tabs.reload(arguments[0]);
      out.sign = !!(await until(() => slow.querySelector(".slow-load"), 6000));
      out.ended = !!(await until(() => !slow.querySelector(".slow-load"), 6000));
      return out;""", r.get("slowId"), r.get("warmId"))
    warmed_there = m.js(H + "for (let i = 0; i < 40 && main().__warmed.length < 6; i++) await wait(50); return main().__warmed;")
    check("in the sidebar panel itself, the tooltip, the sign and the warm-up are the same",
          r2.get("panel") is True and "/slow-icon" in (r2.get("tip") or "") and r2.get("sign") is True and r2.get("ended") is True and len(warmed_there) == 6 and "/icon?warm" in warmed_there[5], f"{r2} {warmed_there}")

    # Asked for less motion: the sign is a still dim, and what moved in the sidebar stands still.
    m.js('Services.prefs.setIntPref("ui.prefersReducedMotion", 1); return 1;')
    r = sidebar_page(m, until + """
      const slowId = arguments[0], row = doc.querySelector(`#tabs .tab[data-tab="${slowId}"]`);
      await until(() => page.getComputedStyle(doc.documentElement).transitionDuration === "0s", 2000);
      await page.browser.tabs.reload(slowId);
      const icon = await until(() => row.querySelector(".slow-load"), 6000);
      const style = icon && page.getComputedStyle(icon);
      const out = {name: style?.animationName, opacity: style?.opacity, moving: icon?.getAnimations().length, window: page.getComputedStyle(doc.documentElement).transitionDuration};
      await until(async () => await status(slowId) === "complete");
      await wait(300);
      out.after = row.querySelector("img").getAnimations().length;
      return out;""", r.get("slowId"))
    m.js(H + """Services.prefs.clearUserPref("ui.prefersReducedMotion");
      const a = main();
      a.gBrowser.selectedTab = a.__selected;
      // Unpinned first: a closed essential comes back.
      a.gBrowser.tabs.filter(t => t.pinned && url(t).includes("?tile")).forEach(t => a.gBrowser.unpinTab(t));
      await wait(1500);
      await removeWhere((w, t) => url(t).startsWith(args[0]) || url(t).startsWith(args[2]));
      a.gBrowser.warmupTab = a.__warmup;
      if (args[1]) { other()?.close(); await wait(2500); }
      return 1;""", m.pages, opened, m.pages.replace("127.0.0.1", "localhost"))
    check("with less motion asked for, a slow load is a still dim", r.get("name") == "none" and r.get("moving") == 0 and r.get("opacity") == "0.55" and r.get("after") == 0, str(r))
    check("with less motion asked for, nothing in the sidebar moves", r.get("window") == "0s", str(r))
    no_problems(m, "after the small touches")


def sidebar_width(m, px):
    m.js(H + """const box = main().document.getElementById("sidebar-box"); box.style.width = args[0] + "px"; await wait(400); return 1;""", px)


def alone_look(m):
    was = m.js(H + """return main().document.getElementById("sidebar-box").style.width;""")
    # Two of today's tabs side by side, in the space shown, for the picked rows below.
    shown = look_in_sidebar(m, """() => doc.documentElement.dataset.space""")
    ours = m.js(H + """const w = main(); w.focus(); const [pages, space] = args;
      const tabs = ["look-1", "look-2"].map(name => w.gBrowser.addTrustedTab(pages + "/titled?" + name, {userContextId: space, inBackground: true}));
      for (let i = 0; i < 100 && !tabs.every(t => role(w, t)); i++) await wait(100);
      await wait(800); return tabs.every(t => role(w, t));""", m.pages, int(shown.split("-")[-1]))

    # Renaming a space: a soft box with the space's ring, its text where the name was (a block
    # left open in sidebar.css once made it a plain browser field).
    r = look_in_sidebar(m, """() => {
      const line = doc.getElementById("space-name"), at = box(line).left + parseFloat(css(line).paddingLeft), size = css(line).fontSize;
      page.openSpaceBox(doc.documentElement.dataset.space);
      const input = doc.querySelector(".space-box"), s = input && css(input);
      const out = input && {radius: s.borderRadius, border: s.borderTopWidth, ring: s.boxShadow !== "none", size: s.fontSize, nameSize: size,
        textAt: Math.round(box(input).left + parseFloat(s.paddingLeft) - at), height: Math.round(box(input).height)};
      input?.dispatchEvent(new page.KeyboardEvent("keydown", clone({key: "Escape", bubbles: true})));
      return out; }""")
    check("renaming a space shows the soft box, its text where the name was", bool(r) and r["radius"] == "6px" and r["border"] == "0px" and r["ring"]
          and r["size"] == r["nameSize"] and abs(r["textAt"]) <= 1 and r["height"] == 24, str(r))

    # The two notices of the first run are one shape in one place, so the list does not move
    # when one replaces the other, and the one that asks is one button, not a box in a box.
    r = look_in_sidebar(m, """() => {
      const hiding = doc.getElementById("hiding"), ask = doc.querySelector(".ask-line"), before = [hiding.hidden, ask.hidden], out = {};
      for (const [name, shown, other] of [["hiding", hiding, ask], ["ask", ask, hiding]]) {
        shown.hidden = false; other.hidden = true;
        const b = box(shown);
        out[name] = {top: Math.round(b.top), height: Math.round(b.height), inner: css(shown.querySelector("button")).backgroundColor};
      }
      [hiding.hidden, ask.hidden] = before;
      out.row = parseFloat(css(doc.documentElement).getPropertyValue("--row"));
      return out; }""")
    clear = "rgba(0, 0, 0, 0)"
    check("the first-run notices are one shape in one place, each one button", r["hiding"]["top"] == r["ask"]["top"] and r["hiding"]["height"] == r["ask"]["height"] == r["row"]
          and r["hiding"]["inner"] == r["ask"]["inner"] == clear, str(r))

    # A lone essential keeps a tile's shape at every width: in the wide grid half a cell was a sliver.
    # (150 px is less than the dotfiles allow: the sidebar is then as narrow as it gets.)
    shapes = {}
    for px in (150, 300, 480):
        sidebar_width(m, px)
        shapes[px] = look_in_sidebar(m, """() => {
          const grid = doc.getElementById("essentials"), others = [...grid.children].slice(1);
          if (!grid.firstElementChild) return null;
          for (const t of others) t.remove();
          const b = box(grid.firstElementChild), row = box(grid).width;
          grid.append(...others);
          return [Math.round(b.width), Math.round(b.height), Math.round(row)]; }""")
    check("a lone essential is a tile at every width: wider than tall, at most half the row", all(s and s[0] >= s[1] and s[0] <= s[2] / 2 + 1 for s in shapes.values()), str(shapes))

    # On the bar a sound's mark is under its dot, in the middle and clear of it, and quiet.
    sidebar_width(m, 300)
    r = look_in_sidebar(m, """() => {
      const b = doc.querySelector("#spaces .space.active"), d = b.querySelector(".dot");
      for (const a of d.getAnimations()) a.finish();
      page.spaceSound(b, clone({soundTabId: 1}));
      const mark = b.querySelector(".sound"), at = box(mark), dot = box(d);
      const out = {centre: Math.round((at.left + at.width / 2) - (dot.left + dot.width / 2)), below: Math.round(box(mark.querySelector("svg")).top - dot.bottom),
        quiet: css(mark).color === colour("var(--muted)")};
      mark.remove();
      return out; }""")
    check("a sound's mark on the bar is under its dot, in the middle, clear of it and quiet", r["centre"] == 0 and r["below"] >= 1 and r["quiet"], str(r))

    # Picked rows side by side are one block: the gap between them is filled, and nothing moves.
    r = look_in_sidebar(m, """() => {
      const rows = [...doc.querySelectorAll("#tabs .row.tab:not(.active)")].filter(r => r.nextElementSibling?.matches(".row.tab:not(.active)"));
      const [a] = rows; if (!a) return null;
      const b = a.nextElementSibling, tops = [box(a).top, box(b).top];
      a.classList.add("picked"); b.classList.add("picked");
      for (const x of [a, b]) for (const an of x.getAnimations()) an.finish();
      const out = {shadow: css(a).boxShadow, gap: Math.round(box(b).top - box(a).bottom), moved: box(a).top !== tops[0] || box(b).top !== tops[1]};
      a.classList.remove("picked"); b.classList.remove("picked");
      return out; }""")
    check("picked rows side by side are one block, with nothing moved", ours and bool(r) and not r["moved"] and f" 0px {r['gap']}px 0px" in r["shadow"], str(r))

    # The quiet line: a row's height, raised over the list (and below, in either scheme, never darker than the surface).
    r = look_in_sidebar(m, """() => {
      const note = doc.getElementById("note"), line = note.querySelector(".line"), was = note.classList.contains("shown");
      note.classList.add("shown");
      const out = {height: Math.round(box(line).height), row: parseFloat(css(doc.documentElement).getPropertyValue("--row")), raised: line.classList.contains("raised")};
      note.classList.toggle("shown", was);
      return out; }""")
    check("the quiet line is a row's height, raised over the list", r["height"] == r["row"] and r["raised"], str(r))

    # A small window's row: Keep stands clear of where its × comes, at every width.
    keep = {}
    for px in (150, 300, 480):
        sidebar_width(m, px)
        keep[px] = look_in_sidebar(m, """() => {
          const row = page.littleRow(clone({id: -1, title: "A link from another app, with a long title", space: "A space with a long name"}));
          doc.getElementById("little").append(row);
          const out = Math.round(box(row.querySelector(".close")).left - box(row.querySelector(".keep")).right);
          row.remove();
          return out; }""")
    check("a small window's Keep stands clear of its close button, at every width", all(v is not None and v >= 1 for v in keep.values()), str(keep))
    m.js(H + """await removeWhere((x, t) => url(t).includes("/titled?look-")); return 1;""")

    # Light to dark: the surface changes with the text, not after it (a fading surface was
    # light behind light text for a quarter of a second).
    def scheme_change(dark):
        return m.js(H + LOOK_IN_SIDEBAR + """const [source, dark] = args;
          const answer = lookInSidebar(source, dark);
          await wait(150);
          Services.prefs.setIntPref("ui.systemUsesDarkTheme", dark ? 1 : 0);
          return await answer;""", """async dark => {
            // Looked at as the change is told, just after the page itself is told (its listener
            // is older): a surface that fades has not started to change by then.
            const query = content.matchMedia("(prefers-color-scheme: dark)");
            if (query.matches === dark) return null;
            const told = await Promise.race([new Promise(r => query.addEventListener("change", () => r(true), {once: true})), sleep(5000).then(() => false)]);
            if (!told) return null;
            const surface = css(doc.documentElement).backgroundColor, line = css(doc.querySelector("#note .line")).backgroundColor;
            return {surface, frame: colour("var(--frame)"), line, lighter: light(line) >= light(surface)}; }""", dark)
    dark = look_in_sidebar(m, """() => content.matchMedia("(prefers-color-scheme: dark)").matches""")
    r = [scheme_change(not dark), scheme_change(dark)]
    m.js(H + """Services.prefs.clearUserPref("ui.systemUsesDarkTheme"); await wait(300); return 1;""")
    if r == [None, None]:
        # Developer Edition's own dark theme decides the sidebar's scheme, whatever the system says.
        print("SKIP  light to dark and back (the sidebar does not follow the system's scheme in this Firefox)", flush=True)
    else:
        check("light to dark and back, the surface changes with the text", all(x and x["surface"] == x["frame"] for x in r), str(r))
        check("the quiet line is never darker than the surface, in light or dark", all(x and x["lighter"] for x in r), str(r))

    # A notice (a live folder that stopped, say) has a ×, and a real click on it puts it away,
    # in this sidebar and in Tidier's own list. Made by the background's own setNotice.
    words = "Live folder \"Smoke\" is not updating: its helper does not answer"
    r = look_in_sidebar(m, """async words => {
      page.browser.extension.getBackgroundPage().setNotice("smoke-look", words);
      const problem = doc.getElementById("problem");
      for (let i = 0; i < 50 && problem.hidden; i++) await sleep(100);
      const away = problem.querySelector(".ask-no"), b = away && box(away), p = box(problem);
      return {shown: !problem.hidden, text: problem.querySelector(".text")?.textContent, x: b && b.x + b.width / 2, y: b && b.y + b.height / 2,
        centred: !!b && Math.abs((b.y + b.height / 2) - (p.y + p.height / 2)) <= 1}; }""", words)
    shown = r.get("shown") and r.get("text") == words
    if shown:
        at = m.js(SIDEBAR_AT)
        click_at(m, at, r["x"], r["y"])
        # Put away under the pointer, it fades in place, and its room goes once the pointer
        # has left it (goQuietly, sidebar/isolation.js): so the pointer moves away, as a hand would.
        fading = look_in_sidebar(m, """async () => { const p = doc.getElementById("problem");
          for (let i = 0; i < 30 && !p.classList.contains("going") && !p.hidden; i++) await sleep(100);
          return p.hidden || p.classList.contains("going"); }""")
        m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"}, "actions": [
            {"type": "pointerMove", "duration": 0, "x": int(at["x"] + r["x"]), "y": int(at["y"] + r["y"] - 120), "origin": "viewport"}]}]})
        m.cmd("WebDriver:ReleaseActions")
        r["fading"] = fading
    gone = look_in_sidebar(m, """async words => {
      const bg = page.browser.extension.getBackgroundPage(), problem = doc.getElementById("problem");
      for (let i = 0; i < 50 && !problem.hidden; i++) await sleep(100);
      // (Tidier's button says what the first notice is: notices itself is not reachable from here.)
      const out = {hidden: problem.hidden, kept: (await page.browser.browserAction.getTitle({})).includes(words)};
      bg.setNotice("smoke-look", null); // put away it is already: the words are this test's own
      return out; }""", words)
    check("a notice has a × in its middle, and a real click on it puts the notice away", shown and r["centred"] and r.get("fading") and gone["hidden"] and not gone["kept"], f"{r} {gone}")
    m.js(H + """main().document.getElementById("sidebar-box").style.width = args[0]; await wait(300); return 1;""", was)


# Helpers for alone_swipe, on the real sidebar (as STAY_PUT's are). A headless Firefox has no
# trackpad: what one sends is wheel events, and those are made here as it sends them.
SWIPE = """
  const obj = o => page.JSON.parse(JSON.stringify(o));
  const windowId = (await page.browser.windows.getCurrent()).id;
  const side = page.browser.extension.getViews(obj({type: "sidebar", windowId}))[0], doc = side.document;
  const wait = ms => new Promise(done => side.setTimeout(() => done(), ms));
  const until = async (test, ms = 8000) => { for (const t0 = Date.now(); Date.now() - t0 < ms; await wait(30)) if (await test()) return true; return false; };
  const root = doc.documentElement, list = doc.getElementById("tabs"), overlay = doc.getElementById("swipe");
  const css = e => side.getComputedStyle(e);
  const spaces = () => [...doc.querySelectorAll("#spaces .space")].map(b => ({id: b.dataset.space, active: b.classList.contains("active")}));
  const here = () => root.dataset.space;
  const x = () => { const t = css(overlay.querySelector(".strip")).transform; return t === "none" ? 0 : Math.round(new side.DOMMatrix(t).m41); };
  const state = () => ({shown: !overlay.hidden, swiping: root.classList.contains("swiping"), panes: overlay.querySelectorAll(".pane").length});
  const names = at => [...at.querySelectorAll(".tab .title")].map(t => t.textContent).join(" | ");
  const label = e => e?.getAttribute("aria-label") ?? null;
  const y = e => (e ? Math.round(e.getBoundingClientRect().y * 10) / 10 : null);
  // Fingers on the trackpad, as the wheel events they become: one after the other with no
  // turn of the page between, so the pause that ends a swipe cannot come in the middle of
  // one, however busy the machine is. 1 px every 3 ms is a slow swipe.
  const fingers = (moves, every = 3) => { for (const [dx, dy] of moves) { const t = side.performance.now(); while (side.performance.now() - t < every); list.dispatchEvent(new side.WheelEvent("wheel", {bubbles: true, deltaX: dx, deltaY: dy, deltaMode: 0})); } };
  const times = (n, move) => Array.from({length: n}, () => move);
  const gliding = from => { const out = []; for (let d = Math.abs(from); d >= 1; d *= 0.9) out.push([Math.sign(from) * Math.round(d), 0]); return out; };
  const settled = () => until(() => overlay.hidden && !root.classList.contains("swiping"));
  const switchTo = async id => {
    doc.querySelector(`#spaces .space[data-space="${id}"]`).click();
    await until(() => here() === id && doc.querySelector(".tab.active, .tile.active"));
    await settled();
    await wait(300);
  };
  const ids = spaces().map(s => s.id), width = side.innerWidth, far = 12 + Math.ceil(width * 0.45);
"""


def real_swipe(m, at, x, y, moves):
    """Real wheel events, one for each [dx, dy], at a place in the sidebar."""
    m.cmd("WebDriver:PerformActions", {"actions": [{"type": "wheel", "id": "wheel", "actions": [
        {"type": "scroll", "x": int(at["x"] + x), "y": int(at["y"] + y), "deltaX": dx, "deltaY": dy, "duration": 0, "origin": "viewport"} for dx, dy in moves]}]})
    m.cmd("WebDriver:ReleaseActions")


def alone_swipe(m):
    # A swipe on the trackpad switches space (sidebar/swipe.js): the list follows the fingers.
    m.js(H + """const w = main(); for (const t of [...w.gBrowser.tabs]) if (url(t).includes("/sidebar/sidebar.html")) w.gBrowser.removeTab(t);
      Services.prefs.setIntPref("ui.prefersReducedMotion", 0); await wait(300); return 1;""")
    r = sidebar_page(m, SWIPE + """
      const out = {spaces: ids.length};
      await switchTo(ids[1]);  // so this sidebar has drawn the space next to the first one
      await switchTo(ids[0]);
      const top = list.scrollTop;

      // A scroll that then drifts all the way across, and glides on.
      fingers([[0, 4], [1, 7], [2, 9], ...times(25, [30, 2]), ...gliding(30)]);
      out.scroll = state();
      await wait(400);
      out.scrollAfter = {...state(), here: here() === ids[0]};

      // A slow swipe, a little way: it follows, and comes back.
      fingers(times(12, [1, 0]));
      out.began = {...state(), x: x(), list: css(list).opacity};
      fingers(times(40, [1, 0]));
      const home = overlay.querySelector(".pane:not(.next, .previous)"), next = overlay.querySelector(".pane.next");
      const liveRow = list.querySelector(".tab"), homeRow = home?.querySelector(".list .tab");
      out.follows = {x: x(), next: !!next, previous: !!overlay.querySelector(".pane.previous"),
        same: !!home && names(home) === names(list), rows: list.querySelectorAll(".tab").length,
        dy: y(homeRow) - y(liveRow), dx: homeRow && Math.round(homeRow.getBoundingClientRect().x - liveRow.getBoundingClientRect().x),
        wide: homeRow?.getBoundingClientRect().width === liveRow.getBoundingClientRect().width,
        nextX: next && Math.round(next.getBoundingClientRect().x) - width,
        found: doc.querySelectorAll("#swipe [data-tab], #swipe [id], #swipe [draggable], #swipe [tabindex]").length,
        tint: next && css(next.querySelector(".space-name")).color !== css(home.querySelector(".space-name")).color};
      // A click on what is passing by is no click on a tab: the space coming in is drawn by what draws the list.
      next?.querySelector(".tab, .tile")?.click();
      out.clicked = !!next?.querySelector(".tab, .tile");
      await settled();
      out.back = {...state(), here: here() === ids[0], top: list.scrollTop === top, list: css(list).opacity};

      // Further than four tenths of the way: it goes there, and what came in is what is there.
      fingers(times(far, [1, 0]));
      const pane = overlay.querySelector(".pane.next"), on = pane?.querySelector(".tab.active, .tile.active");
      out.far = {x: x() + far - 12, names: pane && names(pane), tiles: pane?.querySelectorAll(".tile").length, on: label(on), onY: y(on),
        firstY: y(pane?.querySelector(".list .tab")), name: pane?.querySelector(".space-name").textContent};
      out.went = await until(() => here() === ids[1]);
      await settled();
      await wait(300);
      const nowOn = doc.querySelector("#tabs .tab.active, #essentials .tile.active");
      out.landed = {...state(), names: names(list), tiles: doc.querySelectorAll("#essentials .tile").length, on: label(nowOn), onY: y(nowOn),
        firstY: y(list.querySelector(".tab")), name: doc.getElementById("space-name").textContent, list: css(list).opacity,
        dot: spaces().find(s => s.active)?.id === ids[1],
        tab: (await page.browser.tabs.query(obj({active: true, windowId})))[0].cookieStoreId === ids[1]};

      // A flick: one space, whatever the trackpad glides on with.
      await switchTo(ids[0]);
      fingers([[6, 0], [10, 0], [18, 0], [24, 0], [30, 0], ...gliding(30)], 8);
      out.flicked = await until(() => here() !== ids[0]);
      await settled();
      await wait(700);
      out.flick = {...state(), at: ids.indexOf(here())};

      // At the first space, towards no space: it gives a little and comes back.
      await switchTo(ids[0]);
      fingers(times(72, [-1, 0]));
      out.edge = {...state(), x: x(), previous: !!overlay.querySelector(".pane.previous")};
      await settled();
      await wait(300);
      out.edgeAfter = {...state(), here: here() === ids[0]};

      // Over an open menu it is no swipe.
      const menu = doc.getElementById("menu");
      doc.getElementById("space-name").dispatchEvent(new side.MouseEvent("contextmenu", {bubbles: true, cancelable: true, button: 2, clientX: 20, clientY: 60}));
      out.menu = await until(() => !menu.hidden);
      fingers(times(far, [1, 0]));
      out.taken = state();
      await wait(400);
      out.takenAfter = {...state(), here: here() === ids[0], menu: menu.hidden};

      // What the background says of a space this sidebar is not showing.
      const g = await page.browser.runtime.sendMessage(obj({type: "glimpse", windowId, space: ids[2]}));
      out.glimpse = {space: g?.space === ids[2], tabs: g?.tabs.length + g?.folders.length + g?.essentials.length, on: [...g.essentials, ...g.tabs, ...g.folders.flatMap(f => f.tabs)].filter(t => t.active).length};
      out.middle = (() => { const q = list.getBoundingClientRect(); return {x: q.x + q.width / 2, y: q.y + q.height / 2}; })();
      return out;""")
    idle = {"shown": False, "swiping": False, "panes": 0}
    check("scrolling the list is never a swipe, however far it drifts sideways", r.get("spaces", 0) >= 3 and r.get("scroll") == idle and r.get("scrollAfter") == {**idle, "here": True}, str(r))
    began, follows = r.get("began") or {}, r.get("follows") or {}
    check("a sideways swipe begins after 12 px, with the list where it lies, and its picture in the list's place",
          began == {"shown": True, "swiping": True, "panes": 1, "x": 0, "list": "0"} and follows.get("same") and follows.get("rows", 0) > 0
          and follows.get("dy") == 0 and follows.get("wide") and follows.get("found") == 0, f"{began} {follows}")
    check("the list follows the fingers, and the next space comes in beside it, in its own colour",
          follows.get("x") == -40 and follows.get("dx") == -40 and follows.get("next") and follows.get("nextX") == -40 and not follows.get("previous") and follows.get("tint"), str(follows))
    check("let go after a little way, it comes back, and the list is as it was; a click on the space passing by did nothing",
          r.get("clicked") is True and r.get("back") == {**idle, "here": True, "top": True, "list": "1"}, f"{r.get('clicked')} {r.get('back')}")
    far, landed = r.get("far") or {}, r.get("landed") or {}
    same = all(far.get(k) == landed.get(k) for k in ("names", "tiles", "on", "onY", "firstY", "name"))
    check("swiped further than four tenths of the way, the window goes to that space", far.get("x") == 0 and r.get("went") is True and landed.get("dot") and landed.get("tab") and landed.get("list") == "1"
          and {k: landed.get(k) for k in idle} == idle, f"{r.get('went')} {landed}")
    check("what came in beside the list is what is there on arriving: the same rows in the same places, and the tab you land on",
          same and bool(far.get("names")) and far.get("on") is not None, f"{far} {landed}")
    check("a flick goes one space, whatever the trackpad glides on with", r.get("flicked") is True and r.get("flick") == {**idle, "at": 1}, f"{r.get('flicked')} {r.get('flick')}")
    edge = r.get("edge") or {}
    check("at the first space the list gives a little and comes back", edge.get("shown") and 0 < edge.get("x", 0) < 60 and not edge.get("previous")
          and r.get("edgeAfter") == {**idle, "here": True}, f"{edge} {r.get('edgeAfter')}")
    check("a swipe over an open menu is none", r.get("menu") is True and r.get("taken") == idle and r.get("takenAfter") == {**idle, "here": True, "menu": True}, f"{r.get('taken')} {r.get('takenAfter')}")
    check("the background gives a glimpse of a space that is not shown, with the tab to land on", (r.get("glimpse") or {}).get("space") and r["glimpse"]["tabs"] > 0 and r["glimpse"]["on"] <= 1, str(r.get("glimpse")))

    # Firefox has a sideways swipe of its own, back and forward in a page's history. It listens
    # for it around the pages only: a swipe in the sidebar must not also take the page back.
    apart = m.js(H + """const w = main(); return !w.gBrowser.tabbox.contains(w.document.getElementById("sidebar-box"));""")
    check("Firefox's own swipe, back and forward in history, does not listen in the sidebar", apart is True, str(apart))

    # The same with real wheel events, which take Firefox's own way to the sidebar. They come
    # when Marionette gets to them: a pause between two that is longer than a swipe's own
    # ends the swipe, as it should, so a flick gets more than one try.
    at, middle = m.js(SIDEBAR_AT), r.get("middle") or {"x": 100, "y": 200}
    real_swipe(m, at, middle["x"], middle["y"], [(0, 30)] * 3 + [(40, 0)] * 6)
    scrolled = sidebar_page(m, SWIPE + "await settled(); await wait(400); return {...state(), here: here() === ids[0]};")
    check("with a real wheel, a scroll that turns sideways switches nothing", scrolled == {**idle, "here": True}, str(scrolled))
    flicked = {}
    for _ in range(3):
        real_swipe(m, at, middle["x"], middle["y"], [(30, 0)] * 8)
        flicked = sidebar_page(m, SWIPE + "await until(() => here() !== ids[0], 1500); await settled(); await wait(300); return {...state(), at: ids.indexOf(here())};")
        if flicked.get("at") != 0:
            break
    check("with a real wheel, a sideways flick goes to the next space", flicked == {**idle, "at": 1}, str(flicked))

    # With less motion asked for nothing follows the fingers: a clear swipe switches.
    m.js(H + """Services.prefs.setIntPref("ui.prefersReducedMotion", 1); await wait(300); return 1;""")
    r = sidebar_page(m, SWIPE + """
      const out = {};
      await switchTo(ids[0]);
      fingers(times(12 + 40, [1, 0]));
      out.short = state();
      await wait(400);
      out.shortAfter = here() === ids[0];
      fingers(times(12 + 70, [1, 0]));
      out.clear = state();
      out.went = await until(() => here() === ids[1]);
      await wait(400);
      out.after = state();
      await switchTo(ids[0]);
      return out;""")
    m.js(H + """Services.prefs.clearUserPref("ui.prefersReducedMotion"); await wait(300); return 1;""")
    check("with less motion asked for, a clear swipe switches space and nothing is drawn of it",
          r.get("short") == idle and r.get("shortAfter") is True and r.get("clear") == idle and r.get("went") is True and r.get("after") == idle, str(r))
    no_problems(m, "after swiping between spaces")
    close_sidebar_page(m)


def alone_motion(m):
    # Soft motion where something comes or goes (sidebar/motion.js, sidebar.css): another
    # space slides in from its side, a folder opens and closes by its height, a new row fades
    # in; with less motion asked for, none of it; and with nothing happening, nothing runs.
    m.js(H + """const w = main(); for (const t of [...w.gBrowser.tabs]) if (url(t).includes("/sidebar/sidebar.html")) w.gBrowser.removeTab(t);
      Services.prefs.setIntPref("ui.prefersReducedMotion", 0); await wait(300); return 1;""")
    sidebar_page(m, """send({type: "space", space: "firefox-container-1"}); await wait(1000);
      send({type: "newFolder", space: "firefox-container-1", name: "Motion folder"}); await wait(1500); return 1;""")
    m.js(H + """const w = main(); for (const i of [1, 2]) { w.gBrowser.addTrustedTab("https://example.org/?smoke-motion-" + i, {userContextId: 1, inBackground: true}); await wait(300); }
      await wait(3000); return 1;""")
    for i in (1, 2):
        to_folder(m, f"https://example.org/?smoke-motion-{i}", "Motion folder")
    MOTION = """
      const obj = o => page.JSON.parse(JSON.stringify(o)), windowId = (await page.browser.windows.getCurrent()).id;
      const side = page.browser.extension.getViews(obj({type: "sidebar", windowId}))[0], sdoc = side.document, root = sdoc.documentElement;
      const wait = ms => new Promise(done => side.setTimeout(() => done(), ms));
      const until = async (test, ms = 8000) => { for (const t0 = Date.now(); Date.now() - t0 < ms; await wait(20)) if (await test()) return true; return false; };
      const ids = [...sdoc.querySelectorAll("#spaces .space")].map(b => b.dataset.space);
      const PARTS = ["essentials", "space-name", "actions", "tabs"];
      // What moves on a part now: its first keyframe's slide, or "none".
      const slide = id => { const a = sdoc.getElementById(id).getAnimations().find(x => x.effect?.getKeyframes?.()[0]?.transform);
        return a ? Math.round(new side.DOMMatrix(a.effect.getKeyframes()[0].transform).m41) : "none"; };
      const switchTo = async id => { sdoc.querySelector(`#spaces .space[data-space="${id}"]`).click(); await until(() => root.dataset.space === id); return PARTS.map(slide); };
      const head = () => sdoc.querySelector("#tabs .folder .head[title='Motion folder']");
      const fold = async () => { const h = head(), was = h.parentElement.classList.contains("collapsed"); h.click(); await until(() => h.parentElement.classList.contains("collapsed") !== was);
        // The newest fold: a finished one can still be listed for a moment.
        const a = h.parentElement.lastElementChild.getAnimations().filter(x => x.id === "fold").at(-1); return a ? a.effect.getKeyframes().map(k => parseInt(k.height)) : "none"; };
      const moving = () => [...PARTS.map(id => sdoc.getElementById(id)), ...sdoc.querySelectorAll("#tabs .folder > .children, #tabs .row")].flatMap(e => e.getAnimations()).filter(a => a.playState === "running").length;
      const newRow = async name => { const made = await page.browser.tabs.create(obj({url: "https://example.org/?smoke-motion-" + name, cookieStoreId: ids[0], active: false}));
        let row = null; await until(() => (row = sdoc.querySelector(`#tabs .tab[data-tab="${made.id}"]`)));
        return row ? row.getAnimations().some(a => a.transitionProperty === "opacity") : null; };
    """
    r = sidebar_page(m, MOTION + """
      const out = {};
      await until(() => root.dataset.space === ids[0]);
      await wait(500);
      out.right = await switchTo(ids[1]);
      await wait(500);
      out.settled = moving();
      out.left = await switchTo(ids[0]);
      await wait(500);
      out.closing = await fold();
      await wait(400);
      out.opening = await fold();
      await wait(400);
      out.row = await newRow("new");
      await wait(600);
      out.idle = moving();
      return out;""")
    check("another space slides in from the side its dot is on, and its parts all move together, then stop",
          r.get("right") == [16] * 4 and r.get("left") == [-16] * 4 and r.get("settled") == 0, str(r))
    closing, opening = r.get("closing"), r.get("opening")
    check("a folder closes and opens by its height, from where it was to where it goes",
          isinstance(closing, list) and closing[0] > closing[-1] and isinstance(opening, list) and opening[0] < opening[-1] and opening[-1] == closing[0], f"{closing} {opening}")
    check("a new row fades in where it is", r.get("row") is True, str(r.get("row")))
    check("with nothing happening, nothing moves", r.get("idle") == 0, str(r.get("idle")))

    m.js(H + """Services.prefs.setIntPref("ui.prefersReducedMotion", 1); await wait(300); return 1;""")
    r = sidebar_page(m, MOTION + """
      const out = {};
      out.space = await switchTo(ids[1]);
      await switchTo(ids[0]);
      out.closing = await fold();
      out.opening = await fold();
      out.row = await newRow("still");
      return out;""")
    m.js(H + """Services.prefs.clearUserPref("ui.prefersReducedMotion"); await wait(300); return 1;""")
    check("with less motion asked for, nothing slides, folds by its height or fades in",
          r.get("space") == ["none"] * 4 and r.get("closing") == "none" and r.get("opening") == "none" and r.get("row") is False, str(r))

    sidebar_page(m, """const key = doc.querySelector("#tabs .folder .head[title='Motion folder']")?.dataset.folderHead;
      if (key) send({type: "deleteFolder", key}); await wait(800);
      const tabs = await page.browser.tabs.query(page.JSON.parse(JSON.stringify({})));
      await page.browser.tabs.remove(page.JSON.parse(JSON.stringify(tabs.filter(t => /smoke-motion-/.test(t.url)).map(t => t.id))));
      await wait(800); return 1;""")
    no_problems(m, "after soft motion")
    close_sidebar_page(m)


def alone_pause(m):
    # Pause and play from the sidebar (tabactions.js, sounds.js, sidebar/sound.js), on a page
    # that really plays. Whether Firefox hears it is set by hand, as alone_sound does: a test
    # machine has no sound to hear.
    ALL = H + """const {ExtensionPermissions} = ChromeUtils.importESModule("resource://gre/modules/ExtensionPermissions.sys.mjs");
      const [id, allow] = args, ext = WebExtensionPolicy.getByID(id).extension, all = {permissions: [], origins: ["<all_urls>"]};
      const had = (await ExtensionPermissions.get(id)).origins.includes("<all_urls>");
      if (allow !== had) { await ExtensionPermissions[allow ? "add" : "remove"](id, all, ext); await wait(800); }
      return had;"""
    had = m.js(ALL, EXT_ID, False)
    # Firefox lets a page in a background tab start nothing by itself: here it may.
    m.js(H + """const w = main(); for (const t of [...w.gBrowser.tabs]) if (url(t).includes("/sidebar/sidebar.html")) w.gBrowser.removeTab(t);
      Services.prefs.setBoolPref("media.block-autoplay-until-in-foreground", false); Services.prefs.setIntPref("media.autoplay.default", 0);
      w.gBrowser.addTrustedTab(args[0] + "/media", {userContextId: 1, inBackground: true});
      for (let i = 0; i < 60 && !w.gBrowser.tabs.some(t => t.label === "Media playing"); i++) await wait(100);
      return 1;""", m.pages)
    HEAR = H + """const w = main(), t = w.gBrowser.tabs.find(x => url(x).endsWith("/media"));
      t.toggleAttribute("soundplaying", args[0]); w.gBrowser._tabAttrModified(t, ["soundplaying"]); await wait(500); return t.label;"""
    title = m.js(HEAR, True)
    PAGE = """const obj = o => page.JSON.parse(JSON.stringify(o)), windowId = (await page.browser.windows.getCurrent()).id;
      const until = async (test, ms = 8000) => { for (const t0 = Date.now(); Date.now() - t0 < ms; await wait(50)) if (await test()) return true; return false; };
      const media = async () => (await page.browser.tabs.query(obj({windowId}))).find(t => t.url.endsWith("/media"));
      const facts = async () => { const f = (await page.browser.runtime.sendMessage(obj({type: "tabMenu", tabIds: [(await media()).id]})))[0]; return [f.playing, f.paused]; };
      const mark = async () => doc.querySelector(`#tabs .tab[data-tab="${(await media()).id}"] .sound`);
    """
    r = sidebar_page(m, PAGE + """
      const out = {before: await facts()};
      send({type: "tabAction", action: "pause", tabIds: [(await media()).id]});
      await wait(1500);
      out.refused = (await media()).title;
      return out;""")
    check("a page that plays offers Pause, and without the access to websites nothing is done to it",
          title == "Media playing" and r.get("before") == [True, False] and r.get("refused") == "Media playing", f"{title} {r}")
    m.js(ALL, EXT_ID, True)
    r = sidebar_page(m, PAGE + """
      send({type: "tabAction", action: "pause", tabIds: [(await media()).id]});
      const out = {paused: await until(async () => (await media()).title === "Media paused")};
      return out;""")
    m.js(HEAR, False)  # silent now, as Firefox would say
    r2 = sidebar_page(m, PAGE + """
      const out = {};
      out.shown = await until(async () => (await mark())?.classList.contains("paused"));
      out.tip = (await mark())?.title ?? null;
      out.facts = await facts();
      (await mark())?.click();
      out.playing = await until(async () => (await media()).title === "Media playing");
      out.gone = await until(async () => !(await mark()));
      return out;""")
    check("with the access, Pause stops what plays in the page", r.get("paused") is True, str(r))
    check("silent, its row shows Play where the speaker was, and the menu offers Play",
          r2.get("shown") is True and r2.get("tip") == "Play" and r2.get("facts") == [False, True], str(r2))
    check("Play from the row starts it again, and the mark goes", r2.get("playing") is True and r2.get("gone") is True, str(r2))
    m.js(ALL, EXT_ID, had)
    m.js(H + """await removeWhere((w, t) => url(t).endsWith("/media"));
      Services.prefs.clearUserPref("media.block-autoplay-until-in-foreground"); Services.prefs.clearUserPref("media.autoplay.default"); return 1;""")
    no_problems(m, "after pausing and playing a page")
    close_sidebar_page(m)
