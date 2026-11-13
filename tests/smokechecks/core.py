"""The core groups: tab sync and essentials where Tidier may not hide tabs, in two windows."""
import json
import os
import re
import sys
import time
from testfirefox import DOTFILES, EXT_ID
from smokechecks.base import (
    CMD, ESC, H, PROC_INFO, SHIFT, check, close_sidebar_page, ext_page,
    extension_message, into_page, no_problems, press, sidebar_page, to_folder,
)


def new_window(m):
    fill = m.js(H + """
      const m0 = main(), want = m0.gBrowser.tabs.filter(t => !t.pinned && role(m0, t)).length, pinned0 = m0.gBrowser.tabs.filter(t => t.pinned).length;
      const t0 = Date.now(), w = m0.OpenBrowserWindow(); w.__smoke = true;
      let ms = null;
      for (let i = 0; i < 200 && ms === null; i++) {
        await wait(100);
        if (w.gBrowser.tabs.filter(t => t.pinned).length >= pinned0 && w.gBrowser.tabs.filter(t => !t.pinned && role(w, t)).length >= want) ms = Date.now() - t0;
      }
      const loaded = () => w.gBrowser.tabs.filter(t => t.linkedPanel && !t.selected && url(t).includes("ghost.html"));
      for (let i = 0; i < 40 && (i < 12 || loaded().length); i++) await wait(250);  // sorting; placeholders unloading (up to 10 s)
      return {ms, essentials: [pinned0, w.gBrowser.tabs.filter(t => t.pinned).length], tabs: [want, w.gBrowser.tabs.filter(t => !t.pinned && role(w, t)).length],
              stillLoaded: loaded().map(t => t.label)};""")
    check(f"a new window gets all essentials and tabs ({fill['ms']} ms)", fill["ms"] is not None and fill["essentials"][0] == fill["essentials"][1]
          and fill["tabs"][0] == fill["tabs"][1], f"essentials {fill['essentials']}, tabs {fill['tabs']}")
    check("placeholders unload themselves", not fill["stillLoaded"], f"still loaded: {fill['stillLoaded']}")
    # Per container: the same essentials, and the same tabs in its folders (Tidier's own,
    # in the record), in the new window as in the main one.
    view = """const w = args[0] ? other() : main(), out = {};
      const all = (await storage("%s", ["syncedTabs"])).syncedTabs;
      const folderOf = k => { for (let x = all[k]?.parentKey, n = 0; x && all[x] && n < 50; x = all[x].parentKey, n++) if (all[x].group) return all[x].name; return null; };
      for (const t of w.gBrowser.tabs) {
        const c = out[t.userContextId] ??= {essentials: [], inFolders: []};
        if (t.pinned) c.essentials.push(ek(w, t));
        else if (key(w, t) && folderOf(JSON.parse(key(w, t)))) c.inFolders.push(folderOf(JSON.parse(key(w, t))) + " " + key(w, t));
      }
      for (const c of Object.values(out)) { c.essentials.sort(); c.inFolders.sort(); }
      return out;""" % EXT_ID
    old, new = m.js(H + view, False), m.js(H + view, True)
    for ctx, v in sorted(old.items()):
        if ctx == "0":
            continue  # pages with no container: about:, Tidier's own
        check(f"container {ctx}: the same essentials and folders in the new window", new.get(ctx) == v and (v["essentials"] or v["inFolders"]), f"main {v} / new {new.get(ctx)}")


def essentials(m):
    r = m.js(H + """
      const w = main();
      w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => !t.pinned && !t.hidden && t.userContextId === 3);
      await wait(800);  // another space (3) is active
      const victim = w.gBrowser.tabs.find(t => t.pinned && t.userContextId === 1 && ek(w, t)), k = ek(w, victim);
      w.gBrowser.removeTab(victim); await wait(5000);
      const back = w.gBrowser.tabs.find(t => t.pinned && ek(w, t) === k);
      return {back: !!back, container: back?.userContextId, unloaded: back ? !back.linkedPanel : null};""")
    check("a closed essential comes back, unloaded, in its own container", r["back"] and r["container"] == 1 and r["unloaded"], str(r))
    r = m.js(H + """
      const t = main().gBrowser.addTrustedTab("https://example.org/?smoke-pin", {userContextId: 1, inBackground: true});
      await wait(2500); main().gBrowser.pinTab(t); await wait(5000);
      const k = ek(main(), t), copy = other().gBrowser.tabs.find(x => x.pinned && ek(other(), x) === k);
      const r = {key: !!k, copy: !!copy, containers: [t.userContextId, copy?.userContextId]};
      // Each space's essentials together, for ⌃Tab (essentials.js).
      r.order = wins().map(w => w.gBrowser.tabs.filter(x => x.pinned).map(x => x.userContextId));
      r.grouped = r.order.map(cs => cs.every((c, i) => i === 0 || c === cs[i - 1] || !cs.slice(0, i).includes(c)));
      if (copy) { other().gBrowser.unpinTab(copy); await wait(4000); r.unpinnedOpens = url(copy); }
      r.leftPinned = wins().map(w => w.gBrowser.tabs.filter(x => x.pinned && ek(w, x) === k).length);
      await removeWhere((w, x) => url(x).includes("smoke-pin"));
      return r;""")
    check("a pinned tab becomes an essential in every window, in its container", r["key"] and r["copy"] and r["containers"] == [1, 1], str(r))
    check("a new essential is put with the other essentials of its space, in every window", r.get("grouped") == [True, True], str(r.get("order")))
    check("unpinning a copy removes the essential everywhere", r["leftPinned"] == [0, 0], str(r))
    check("an unloaded copy you unpin opens its page as an ordinary tab", r.get("unpinnedOpens") == "https://example.org/?smoke-pin", str(r))
    r = m.js(H + """
      const w = other(); w.focus(); await wait(500);
      const e = w.gBrowser.tabs.find(t => t.pinned && url(t).includes("ghost.html") && !t.linkedPanel);
      if (!e) return null;
      // The copy opens the page, or the copy loaded in the other window is moved in in its place.
      const ctx = e.userContextId, k = ek(w, e); w.gBrowser.selectedTab = e; await wait(4000);
      const s = w.gBrowser.selectedTab;
      return {web: /^https?:/.test(url(s)), pinned: s.pinned, sameContainer: s.userContextId === ctx, same: ek(w, s) === k};""")
    check("an essential copy opens the real page, pinned, in its container", r and all(r.values()), str(r))
    r = m.js(H + """
      const w = main(), order = x => x.gBrowser.tabs.filter(t => t.pinned && ek(x, t)).map(t => ek(x, t));
      const mine = w.gBrowser.tabs.filter(t => t.pinned && ek(w, t) && t.userContextId === 1);
      if (mine.length < 2) return null;
      w.gBrowser.moveTabBefore(mine[mine.length - 1], mine[0]);  // last essential of space 1 to its front
      await wait(3000);
      const here = order(w), there = order(other()), both = here.filter(k => there.includes(k));
      const saved = (await storage("%s", ["essentials"])).essentials.map(e => e.key).filter(k => both.includes(k));
      return {moved: here.indexOf(ek(w, mine[mine.length - 1])) < here.indexOf(ek(w, mine[0])),
              otherFollows: JSON.stringify(there.filter(k => both.includes(k))) === JSON.stringify(both),
              saved: JSON.stringify(saved) === JSON.stringify(both)};""" % EXT_ID)
    check("a moved essential keeps its place, in the list and in the other window", r and r["moved"] and r["otherFollows"] and r["saved"], str(r))
    # Dragging an essential to the other window, which has its own copy of it.
    r = m.js(H + """
      const count = () => wins().map(w => { const by = {}; for (const t of w.gBrowser.tabs) if (t.pinned && ek(w, t)) by[ek(w, t)] = (by[ek(w, t)] || 0) + 1; return by; });
      const before = count(), w = main(), t = w.gBrowser.tabs.find(x => x.pinned && ek(w, x) && x.userContextId === 2), k = ek(w, t);
      other().gBrowser.adoptTab(t, {tabIndex: 0}); await wait(5000);
      const after = count();
      return {k, before: before.map(b => b[k]), after: after.map(a => a[k]), same: JSON.stringify(before.map(b => Object.keys(b).sort())) === JSON.stringify(after.map(a => Object.keys(a).sort())),
              doubled: after.flatMap(a => Object.entries(a).filter(([, n]) => n > 1)),
              pinnedThere: [main(), other()].map(x => x.gBrowser.tabs.filter(y => y.pinned).map(y => [(ek(x, y) || "").slice(0, 4), url(y).slice(-24)]))};""")
    check("an essential dragged to the other window is there once, and comes back in the window it left",
          r["after"] == [1, 1] and r["same"] and not r["doubled"], str(r))
    # The same with an unloaded copy, which Firefox unpins for a moment on the way.
    r = m.js(H + """
      const w = main(), t = w.gBrowser.tabs.find(x => x.pinned && ek(w, x) && !x.selected);
      if (!t) return null;
      if (t.linkedPanel) { w.gBrowser.discardBrowser(t); await wait(500); }
      const k = ek(w, t);
      other().gBrowser.adoptTab(t, {tabIndex: 0}); await wait(5000);
      const list = (await storage("%s", ["essentials"])).essentials, entry = list.find(e => e.key === k);
      const there = other().gBrowser.tabs.find(y => y.pinned && ek(other(), y) === k);
      return {inList: !!entry, copies: wins().map(x => x.gBrowser.tabs.filter(y => y.pinned && ek(x, y) === k).length),
              named: !!there && there.label === (entry?.name || entry?.title)};""" % EXT_ID)
    check("an unloaded essential dragged to the other window stays an essential, there once with its name, and back in the window it left",
          r == {"inList": True, "copies": [1, 1], "named": True}, str(r))
    r = m.js(H + """
      const byKey = Object.fromEntries((await storage("%s", ["essentials"])).essentials.map(e => [e.key, e.name || e.title]));
      const w = other(), copies = w.gBrowser.tabs.filter(t => t.pinned && !t.linkedPanel && ek(w, t));
      return {copies: copies.length, wrong: copies.filter(t => t.label !== byKey[ek(w, t)]).map(t => [t.label, byKey[ek(w, t)]])};""" % EXT_ID)
    check("unloaded essentials show their name", r["copies"] > 0 and not r["wrong"], str(r))
    essential_once(m)
    essential_title(m)


def essential_once(m):
    # An essential is loaded in one window only (two loaded Slacks play every
    # notification sound twice): selecting its copy in the other window moves
    # the loaded tab there and leaves a placeholder behind, and a copy that
    # loads its page anyway (as after a restart) makes the other a placeholder.
    r = m.js(H + """
      const a = main(), b = other();
      const loaded = k => wins().flatMap(w => w.gBrowser.tabs.filter(t => t.pinned && ek(w, t) === k && t.linkedPanel && !url(t).includes("ghost.html"))
        .map(t => (w === a ? "main" : "other") + (t.selected ? "/selected" : "")));
      const copyIn = (w, k) => w.gBrowser.tabs.find(t => t.pinned && ek(w, t) === k);
      a.focus(); await wait(500);
      const e = a.gBrowser.tabs.find(t => t.pinned && ek(a, t) && t.userContextId === 3);
      if (!e) return null;
      const bBefore = b.gBrowser.selectedTab;
      const k = ek(a, e); a.gBrowser.selectedTab = e; await wait(4000);
      const out = {first: loaded(k)};
      b.focus(); await wait(500); b.gBrowser.selectedTab = copyIn(b, k); await wait(5000);
      const there = copyIn(b, k), left = copyIn(a, k);
      out.pulled = {loaded: loaded(k), copies: wins().map(w => w.gBrowser.tabs.filter(t => t.pinned && ek(w, t) === k).length),
                    leftIsPlaceholder: !!left && url(left).includes("ghost.html"), containers: [there?.userContextId, left?.userContextId]};
      // Restored by Firefox in the window you are not using, selected there (as
      // after a restart): that copy loads its page itself.
      a.gBrowser.selectedTab = left; await wait(1500);  // selected in a window you are not using, it stays a placeholder
      out.waits = {selectedThere: url(left).includes("ghost.html"), loaded: loaded(k)};
      left.linkedBrowser.loadURI(Services.io.newURI(url(there)), {triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()});
      await wait(5000);
      out.restored = loaded(k);
      // The window you are using leaves it for another tab, and the other one is still on it:
      // the page goes back there, and is not left under a veil until you go to that window.
      b.gBrowser.selectedTab = bBefore; await wait(4000);
      out.back = {loaded: loaded(k), copies: wins().map(w => w.gBrowser.tabs.filter(t => t.pinned && ek(w, t) === k).length), stayed: Services.focus.activeWindow === b};
      a.focus(); await wait(500);
      return out;""")
    check("an essential is loaded in one window: selecting its copy moves the loaded tab in, in its container, and leaves a placeholder",
          r and r["first"] == ["main/selected"] and r["pulled"]["loaded"] == ["other/selected"] and r["pulled"]["copies"] == [1, 1]
          and r["pulled"]["leftIsPlaceholder"] and r["pulled"]["containers"] == [3, 3], str(r))
    check("an essential's placeholder selected in a window you are not using stays a placeholder",
          r and r["waits"] == {"selectedThere": True, "loaded": ["other/selected"]}, str(r))
    check("an essential copy that loads its page in another window makes that one a placeholder again", r and r["restored"] == ["other/selected"], str(r))
    check("an essential left in the window you use goes back to the window that is still on it, and you stay where you are",
          r and r["back"] == {"loaded": ["main/selected"], "copies": [1, 1], "stayed": True}, str(r and r["back"]))


def set_title(m, address, title):
    """Set the title of the (loaded) page at `address`, in its own tab."""
    try:
        into_page(m, address, exact=True)
        m.cmd("WebDriver:ExecuteScript", {"script": "document.title = arguments[0];", "args": [title]})
        return True
    except RuntimeError as e:
        if "no tab with" not in str(e):
            raise
        return False
    finally:
        m.chrome()


def essential_title(m):
    # An essential's name follows its page, but only on its own site: a page on
    # another site (a sign-in it redirects to) does not rename it.
    stored = H + """const k = args[0]; return (await storage("%s", ["essentials"])).essentials.find(e => e.key === k)?.title;""" % EXT_ID
    k = m.js(H + """
      const w = main(), e = w.gBrowser.tabs.find(t => t.pinned && ek(w, t) && t.userContextId === 1), k = ek(w, e);
      w.__beforeTitleTest = w.gBrowser.selectedTab; w.gBrowser.selectedTab = e; await wait(4000);
      w.__essentialHome = url(e);
      w.gBrowser.selectedTab.linkedBrowser.loadURI(Services.io.newURI("https://example.com/?smoke-sign-in"), {triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()});
      await wait(4000); return k;""")
    before = m.js(stored, k)
    other_site = set_title(m, "https://example.com/?smoke-sign-in", "Smoke sign-in")
    time.sleep(2)
    after_other = m.js(stored, k)
    home = m.js(H + """const w = main(), t = w.gBrowser.selectedTab;
      t.linkedBrowser.loadURI(Services.io.newURI(w.__essentialHome), {triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()});
      await wait(4000); return w.__essentialHome;""")
    own_site = set_title(m, home, "Smoke own title")
    extension_message(m, {"type": "flush"})
    time.sleep(2)
    after_own = m.js(stored, k)
    set_title(m, home, before or "Example Domain")
    m.js(H + """const w = main(); if (w.__beforeTitleTest && !w.__beforeTitleTest.closing) w.gBrowser.selectedTab = w.__beforeTitleTest; await wait(2000); return 1;""")
    check("an essential is not renamed by a page on another site (a sign-in), but is by its own",
          other_site and own_site and after_other == before and after_own == "Smoke own title", f"{before!r} -> {after_other!r} -> {after_own!r}")


def tab_sync(m):
    r = m.js(H + """
      const t = main().gBrowser.addTrustedTab("https://example.org/?smoke-sync", {userContextId: 3, inBackground: true});
      await wait(4500); const k = key(main(), t), created = find(k);
      const w = other(); w.focus(); await wait(800);
      const t0 = Date.now(), ghost = w.gBrowser.tabs.find(x => key(w, x) === k); w.gBrowser.selectedTab = ghost;
      let ms = null; for (let i = 0; i < 100 && ms === null; i++) { await wait(15); if (w.gBrowser.selectedTab !== ghost && key(w, w.gBrowser.selectedTab) === k) ms = Date.now() - t0; }
      await wait(2500); const pulled = find(k);
      const closedUrls = wins().flatMap(x => x.SessionStore.getClosedTabDataForWindow(x)).map(c => c.state.entries?.[c.state.index - 1]?.url || "");
      const closedGhosts = closedUrls.filter(u => u.includes("ghost.html") && u.includes(encodeURIComponent(JSON.parse(k)))).length;
      const moved = w.gBrowser.tabs.find(x => key(w, x) === k), left = main().gBrowser.tabs.find(x => key(main(), x) === k);
      const containers = [moved?.userContextId, left?.userContextId];
      w.gBrowser.removeTab(moved); await wait(3000);
      return {created, ms, pulled, containers, closedGhosts, closed: find(k)};""")
    check("a new tab gets a ghost in the other window", r["created"] == [["live/loaded"], ["ghost/unloaded"]], str(r["created"]))
    check(f"selecting a ghost pulls the live tab in ({r['ms']} ms)", r["pulled"] == [["ghost/unloaded"], ["live/loaded"]], str(r["pulled"]))
    check("a pulled tab and the ghost left behind stay in their container", r["containers"] == [3, 3], str(r["containers"]))
    check("pulling a tab in leaves no placeholder in Recently Closed (⌘⇧T reopens what you closed)", r["closedGhosts"] == 0, str(r["closedGhosts"]))
    check("closing a tab closes it everywhere", r["closed"] == [[], []], str(r["closed"]))
    # A page that writes where you are into its address all the time (a map, a dashboard)
    # never settles: it was put off at every change, and never got a record or a ghost.
    r = m.js(H + """
      const t = main().gBrowser.addTrustedTab(args[0] + "/moving?smoke-moving", {userContextId: 3, inBackground: true});
      let k = null, ms = null; const t0 = Date.now();
      for (let i = 0; i < 100 && ms === null; i++) { await wait(100); k = key(main(), t); if (k && find(k)[1]?.length) ms = Date.now() - t0; }
      // And it goes on changing after that: still the one tab, with the one ghost.
      const changes = () => Number(url(t).split("#")[1] || 0);
      for (let i = 0; i < 100 && changes() < 8; i++) await wait(100);
      const created = k ? find(k) : null, changed = changes();
      await removeWhere((w, x) => url(x).includes("smoke-moving") || (k && key(w, x) === k));
      return {created, ms, changed};""", m.pages)
    check(f"a page whose address changes all the time gets its ghost too ({r['ms']} ms), once", r["created"] == [["live/loaded"], ["ghost/unloaded"]] and r["changed"] >= 8 and r["ms"] <= 7000, str(r))
    # The window a page is taken from stays on it, as in Zen and Arc: the window you use has
    # the page, and the other one shows which page that is, not some other tab. Coming back
    # brings the page back, and the other window is then the one that waits.
    r = m.js(H + """
      const a = main(), w = other(); a.focus(); await wait(800);
      const aBefore = a.gBrowser.selectedTab, wBefore = w.gBrowser.selectedTab;
      const t = a.gBrowser.addTrustedTab("https://example.org/?smoke-stays", {userContextId: 3}); a.gBrowser.selectedTab = t;
      await wait(4500); const k = key(a, t);
      const on = x => { const spec = x.gBrowser.selectedBrowser.currentURI.spec; return (key(x, x.gBrowser.selectedTab) === k ? "" : "another tab: ") + (spec.includes("smoke-stays") ? "page" : spec.includes("ghost.html") ? "placeholder" : spec); };
      w.focus(); await wait(800);
      w.gBrowser.selectedTab = w.gBrowser.tabs.find(x => key(w, x) === k); await wait(3000);
      const taken = [on(a), on(w)], copies = find(k).map(x => x.length);
      a.focus(); await wait(3000);
      const back = [on(a), on(w)];
      a.gBrowser.removeTab(a.gBrowser.tabs.find(x => key(a, x) === k)); await wait(3000);
      const closed = find(k);
      if (!aBefore.closing) a.gBrowser.selectedTab = aBefore;
      if (!wBefore.closing) w.gBrowser.selectedTab = wBefore;
      await wait(1500);
      return {taken, copies, back, closed};""")
    check("the window a page is taken from stays on it, as a placeholder", r["taken"] == ["placeholder", "page"] and r["copies"] == [1, 1], str(r))
    check("coming back to that window brings the page back, and the other one waits", r["back"] == ["page", "placeholder"] and r["closed"] == [[], []], str(r))
    # The window that took the page leaves it for another tab while the other window is still
    # on it: the page goes back there by itself. With two windows side by side, the one you
    # are not in would else stay grey on a page that no window shows any more.
    r = m.js(H + """
      const a = main(), w = other(); a.focus(); await wait(800);
      const aBefore = a.gBrowser.selectedTab, wBefore = w.gBrowser.selectedTab;
      const t = a.gBrowser.addTrustedTab("https://example.org/?smoke-goes-back", {userContextId: 3}); a.gBrowser.selectedTab = t;
      await wait(4500); const k = key(a, t);
      const on = x => { const spec = x.gBrowser.selectedBrowser.currentURI.spec; return (key(x, x.gBrowser.selectedTab) === k ? "" : "another tab: ") + (spec.includes("smoke-goes-back") ? "page" : spec.includes("ghost.html") ? "placeholder" : spec.slice(0, 40)); };
      w.focus(); await wait(800);
      w.gBrowser.selectedTab = w.gBrowser.tabs.find(x => key(w, x) === k); await wait(3000);
      const taken = [on(a), on(w)];
      // Passed over only: left and come back to within the moment. Nothing is sent across.
      w.gBrowser.selectedTab = wBefore; await wait(150); w.gBrowser.selectedTab = w.gBrowser.tabs.find(x => key(w, x) === k); await wait(2500);
      const passed = [on(a), on(w)];
      w.gBrowser.selectedTab = wBefore; await wait(3500);
      const back = on(a), roles = find(k), stayed = Services.focus.activeWindow === w, there = w.gBrowser.tabs.find(x => key(w, x) === k);
      const left = {selected: !!there?.selected, loaded: !!there?.linkedPanel};
      await removeWhere((x, y) => key(x, y) === k);
      if (!aBefore.closing) a.gBrowser.selectedTab = aBefore;
      a.focus(); await wait(1500);
      return {taken, passed, back, roles, stayed, left};""")
    check("a page left in the window you use goes back to the window that is still on it, and you stay where you are",
          r["taken"] == ["placeholder", "page"] and r["back"] == "page" and r["roles"] == [["live/loaded"], ["ghost/unloaded"]] and r["stayed"] and r["left"] == {"selected": False, "loaded": False}, str(r))
    check("a page only passed over on the way to another tab is not sent across", r["passed"] == ["placeholder", "page"], str(r["passed"]))
    # What the window left behind shows. With pictures of pages allowed (settings page): the
    # page as it was, under a grey layer, as in Zen and Arc. Without: the words that say
    # where it went. Read in the placeholder's own process, which is the extension's.
    left_behind = H + """
      const [marker, allow, id] = args, a = main(), w = other();
      const {ExtensionPermissions} = ChromeUtils.importESModule("resource://gre/modules/ExtensionPermissions.sys.mjs");
      const ext = WebExtensionPolicy.getByID(id).extension, all = {permissions: [], origins: ["<all_urls>"]};
      const had = (await ExtensionPermissions.get(id)).origins.includes("<all_urls>");
      if (allow !== had) { await ExtensionPermissions[allow ? "add" : "remove"](id, all, ext); await wait(800); }
      a.focus(); await wait(800);
      const aBefore = a.gBrowser.selectedTab, wBefore = w.gBrowser.selectedTab;
      const t = a.gBrowser.addTrustedTab("https://example.org/?" + marker, {userContextId: 3}); a.gBrowser.selectedTab = t;
      await wait(4500); const k = key(a, t);
      w.focus(); await wait(800);
      w.gBrowser.selectedTab = w.gBrowser.tabs.find(x => key(w, x) === k); await wait(3000);
      const left = a.gBrowser.selectedTab, mm = left.linkedBrowser.messageManager, reply = "smoke-left:" + marker;
      const answer = new Promise(res => { const l = {receiveMessage(msg) { mm.removeMessageListener(reply, l); res(msg.data); }}; mm.addMessageListener(reply, l); });
      mm.loadFrameScript("data:application/javascript;charset=utf-8," + encodeURIComponent(`{ const d = content.document, v = d.querySelector("img.veil");
        sendAsyncMessage(${JSON.stringify(reply)}, {placeholder: d.location.href.includes("ghost.html"), veiled: !!d.body?.classList.contains("veiled"),
          picture: v ? [v.naturalWidth > 0, v.clientWidth >= content.innerWidth - 1] : null,
          layer: d.body ? content.getComputedStyle(d.body, "::after").backgroundColor : "", words: d.querySelector("main .when")?.textContent ?? null}); }`), false);
      const shows = await Promise.race([answer, wait(3000).then(() => ({error: "no answer"}))]);
      const same = key(a, left) === k, loaded = !!left.linkedPanel;
      // Left for another tab, the placeholder is unloaded again: no picture is kept for a tab nobody sees.
      if (!aBefore.closing) a.gBrowser.selectedTab = aBefore;
      await wait(3000);
      const after = !!left.linkedPanel;
      await removeWhere((x, y) => key(x, y) === k);
      if (!wBefore.closing) w.gBrowser.selectedTab = wBefore;
      if (allow !== had) { await ExtensionPermissions[had ? "add" : "remove"](id, all, ext); await wait(800); }
      return {shows, same, loaded, after};"""
    r = m.js(left_behind, "smoke-veil", True, EXT_ID)
    s = r["shows"]
    check("with pictures of pages allowed, the window a page is taken from shows it as it was, under a grey layer",
          r["same"] and s.get("placeholder") and s.get("veiled") and s.get("picture") == [True, True] and s.get("layer", "").startswith("rgba(") and s.get("words") is None, str(r))
    check("and that placeholder is unloaded again when the window goes to another tab", r["loaded"] and not r["after"], str(r))
    r = m.js(left_behind, "smoke-words", False, EXT_ID)
    s = r["shows"]
    check("without them, it says in words that the page is in another window now",
          r["same"] and s.get("placeholder") and not s.get("veiled") and s.get("picture") is None and "another window" in (s.get("words") or ""), str(r))
    r = m.js(H + """
      const a = main(), urls = ["https://example.org/?smoke-quick-1", "https://example.org/?smoke-quick-2", "https://example.org/?smoke-quick-3"];
      const tabs = urls.map(u => a.gBrowser.addTrustedTab(u, {userContextId: 3, inBackground: true}));
      await wait(4500);
      const ks = tabs.map(t => key(a, t)), w = other(), ghost = k => w.gBrowser.tabs.find(x => key(w, x) === k);
      w.focus(); await wait(800);
      // Two selected right after each other: both come, and the last stays selected.
      w.gBrowser.selectedTab = ghost(ks[0]); await wait(150); w.gBrowser.selectedTab = ghost(ks[1]);
      await wait(3000);
      const both = [find(ks[0]), find(ks[1])], selected = key(w, w.gBrowser.selectedTab) === ks[1] && !!w.gBrowser.selectedTab.linkedPanel && !url(w.gBrowser.selectedTab).includes("ghost.html");
      // Closed right after it came: closed everywhere, not only here.
      w.gBrowser.selectedTab = ghost(ks[2]);
      for (let i = 0; i < 40 && !(key(w, w.gBrowser.selectedTab) === ks[2] && !url(w.gBrowser.selectedTab).includes("ghost.html")); i++) await wait(25);
      w.gBrowser.removeTab(w.gBrowser.selectedTab);
      await wait(2500);
      const closed = find(ks[2]);
      await removeWhere((x, t) => ks.includes(key(x, t)));
      return {both, selected, closed};""")
    check("two ghosts selected right after each other both come, and the last is selected",
          r["both"] == [[["ghost/unloaded"], ["live/loaded"]]] * 2 and r["selected"], str(r))
    check("a tab closed right after it was pulled in closes everywhere", r["closed"] == [[], []], str(r))
    r = m.js(H + """
      const {AddonManager} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
      const a = await AddonManager.getAddonByID("%s"); await a.disable(); await wait(1500); await a.enable(); await wait(6000);
      const t = main().gBrowser.addTrustedTab("https://example.org/?smoke-restart", {userContextId: 3, inBackground: true});
      await wait(4500); const r = find(key(main(), t)); main().gBrowser.removeTab(t); await wait(3000); return r;""" % EXT_ID)
    check("the extension starts again after being disabled and enabled", r == [["live/loaded"], ["ghost/unloaded"]], str(r))


def saved_tabs(m):
    # A tab in a folder is saved: closing it while it is loaded (⌘W) unloads it
    # back to the address it had when it came into the folder, in the same
    # place and in every window; ⌘⇧T takes its placeholder's place; selecting
    # the placeholder opens the saved address. Dragged out of the folder it is
    # an ordinary tab again, which closing closes everywhere; closing a saved
    # tab that is unloaded removes it everywhere too.
    SAVED = "https://example.org/?smoke-saved"
    tools = H + """
      const entry = async k => (await storage("%s", ["syncedTabs"])).syncedTabs?.[JSON.parse(k)] ?? null;
      const all = async () => (await storage("%s", ["syncedTabs"])).syncedTabs;
      const a = main(), b = other(), gB = a.gBrowser;
      const tabOf = (w, k) => w.gBrowser.tabs.find(t => key(w, t) === k);
      // Whether the tab is in Fixture folder 2, by the record, and the synced tab right after it in this window.
      const place = async (w, k) => { const ts = [...w.gBrowser.tabs], x = tabOf(w, k), r = await all(); if (!x) return null;
        const next = ts.slice(ts.indexOf(x) + 1).find(y => key(w, y));
        return {inFolder: r[r[JSON.parse(k)]?.parentKey]?.name === "Fixture folder 2", next: next ? key(w, next) : null}; };
    """ % (EXT_ID, EXT_ID)
    flush = lambda: extension_message(m, {"type": "flush"})
    m.js(H + """main().focus(); await wait(500); main().gBrowser.addTrustedTab(args[0], {userContextId: 2, inBackground: true}); await wait(5000); return 1;""", SAVED)
    to_folder(m, SAVED, "Fixture folder 2", before="fixture-in-folder-2-2")
    k = m.js(H + """const t = main().gBrowser.tabs.find(t => url(t) === args[0]); const k = key(main(), t);
      t.linkedBrowser.loadURI(Services.io.newURI(args[0] + "-later"), {triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()});
      await wait(3000); return k;""", SAVED)
    flush()
    r = {}
    r["before"] = m.js(tools + """const k = args[0]; return {place: await place(a, k), url: (await entry(k))?.url, saved: (await entry(k))?.saved?.url};""", k)
    r["closed"] = m.js(tools + """const k = args[0]; const t = tabOf(a, k); gB.selectedTab = t; await wait(500); gB.removeTab(t); await wait(3500);
      return {tabs: find(k), place: await place(a, k), url: (await entry(k))?.url};""", k)
    r["reopened"] = m.js(tools + """a.SessionStore.undoCloseTab(a, 0); await wait(4500); return find(args[0]);""", k)
    r["opened"] = m.js(tools + """const k = args[0]; gB.removeTab(tabOf(a, k)); await wait(3500); gB.selectedTab = tabOf(a, k); await wait(4000);
      return {tabs: find(k), url: url(tabOf(a, k))};""", k)
    to_folder(m, SAVED, None)  # dragged out of the folder
    flush()
    r["out"] = m.js(tools + """const k = args[0]; return {saved: (await entry(k))?.saved ?? null, parent: (await entry(k))?.parentKey ?? null};""", k)
    r["outClosed"] = m.js(tools + """const k = args[0]; gB.removeTab(tabOf(a, k)); await wait(3500); return {tabs: find(k), stored: await entry(k)};""", k)
    m.js(H + """main().gBrowser.addTrustedTab(args[0], {userContextId: 2, inBackground: true}); await wait(5000); return 1;""", SAVED + "-unloaded")
    to_folder(m, SAVED + "-unloaded", "Fixture folder 2")
    r["unloadedClosed"] = m.js(tools + """const t = gB.tabs.find(t => url(t) === args[0]), k2 = key(a, t);
      gB.selectedTab = gB.tabs.find(x => !x.pinned && x !== t && x.linkedPanel && key(a, x)); await wait(500); gB.discardBrowser(t); await wait(500);
      gB.removeTab(t); await wait(3500);
      return {tabs: find(k2), stored: await entry(k2)};""", SAVED + "-unloaded")
    b, c = r["before"], r["closed"]
    check("a tab moved into a folder keeps the address it had then as its saved address",
          b["place"] and b["place"]["inFolder"] and b["url"].endswith("-later") and b["saved"] == SAVED, str(b))
    check("closing a loaded saved tab unloads it in every window, in its folder and place, back to its saved address",
          c["tabs"] in ([["ghost/unloaded"], ["ghost/unloaded"]], [["live/unloaded"], ["ghost/unloaded"]]) and c["place"]
          and c["place"]["inFolder"] and c["place"]["next"] == b["place"]["next"] and c["url"] == SAVED, f"before {b}, after {c}")
    check("reopening a closed saved tab (⌘⇧T) takes its placeholder's place", r["reopened"] == [["live/loaded"], ["ghost/unloaded"]], str(r["reopened"]))
    check("selecting a saved tab's placeholder opens its saved address",
          r["opened"]["tabs"] == [["live/loaded"], ["ghost/unloaded"]] and r["opened"]["url"] == SAVED, str(r["opened"]))
    check("a saved tab dragged out of its folder is an ordinary tab, which closing closes everywhere",
          r["out"] == {"saved": None, "parent": None} and r["outClosed"] == {"tabs": [[], []], "stored": None}, f"{r['out']}, {r['outClosed']}")
    check("closing a saved tab while it is unloaded removes it everywhere",
          r["unloadedClosed"] == {"tabs": [[], []], "stored": None}, str(r["unloadedClosed"]))
    close_sidebar_page(m)


def ghost_title(m):
    # A live tab whose title changes: its ghost in the other window shows the
    # new title a few seconds later.
    m.js(H + """main().gBrowser.addTrustedTab("https://example.org/?smoke-title", {userContextId: 3, inBackground: true}); await wait(4500); return 1;""")
    m.cmd("Marionette:SetContext", {"value": "content"})
    for h in m.cmd("WebDriver:GetWindowHandles"):
        m.cmd("WebDriver:SwitchToWindow", {"handle": h, "focus": False})
        if "smoke-title" in m.cmd("WebDriver:GetCurrentURL"):
            break
    m.cmd("WebDriver:ExecuteScript", {"script": 'document.title = "Smoke title 1"; return 1;'})
    m.chrome()
    r = m.js(H + """await wait(6000);
      const t = main().gBrowser.tabs.find(t => url(t).includes("smoke-title")), k = t && key(main(), t), w = other();
      const ghost = k && w.gBrowser.tabs.find(x => key(w, x) === k);
      const r = {live: t?.label, ghost: ghost?.label, unloaded: ghost ? !ghost.linkedPanel : null};
      await removeWhere((w, t) => url(t).includes("smoke-title")); return r;""")
    check("a ghost shows its live tab's new title, still unloaded", r["live"] == "Smoke title 1" and r["ghost"] == "Smoke title 1" and r["unloaded"], str(r))


def pinned_ghost(m):
    r = m.js(H + """
      const t = main().gBrowser.addTrustedTab("https://example.org/?smoke-pin-ghost", {userContextId: 1, inBackground: true});
      await wait(4500); const k = key(main(), t), w = other();
      const ghost = w.gBrowser.tabs.find(x => key(w, x) === k);
      if (!ghost) return null;
      w.gBrowser.pinTab(ghost); await wait(6000);
      const saved = (await storage("%s", ["essentials"])).essentials.filter(e => e.url === "https://example.org/?smoke-pin-ghost");
      const copies = wins().map(x => x.gBrowser.tabs.filter(y => y.pinned && saved[0] && ek(x, y) === saved[0].key).length);
      const r = {saved: saved.length, copies, synced: find(k), unloaded: !ghost.linkedPanel};
      for (const x of wins()) for (const y of [...x.gBrowser.tabs]) if (y.pinned && saved[0] && ek(x, y) === saved[0].key) { x.gBrowser.unpinTab(y); break; }
      await wait(4000);
      await removeWhere((x, y) => url(y).includes("smoke-pin-ghost") || (saved[0] && ek(x, y) === saved[0].key));
      return r;""" % EXT_ID)
    check("pinning a ghost makes its page an essential in every window, still unloaded",
          r and r["saved"] == 1 and r["copies"] == [1, 1] and r["synced"] == [[], []] and r["unloaded"], str(r))


def orphans(m):
    # A placeholder whose tab or essential no longer exists (left from before a
    # restart) is closed, and is not left in Recently Closed. (Opened in the
    # background: selecting one first would make the test depend on which
    # neighbour Firefox selects when it closes.)
    r = m.js(H + """
      const base = "moz-extension://" + JSON.parse(Services.prefs.getStringPref("extensions.webextensions.uuids"))["%s"] + "/ghost.html";
      const w = main(), before = w.gBrowser.selectedTab;
      w.gBrowser.addTrustedTab(base + "?kind=ghost&key=smoke-orphan-1", {inBackground: true});
      w.gBrowser.addTrustedTab(base + "?kind=essential&key=smoke-orphan-2", {inBackground: true});
      await wait(3000);
      const left = wins().flatMap(x => x.gBrowser.tabs.filter(t => url(t).includes("smoke-orphan")).map(t => url(t)));
      const closed = wins().flatMap(x => x.SessionStore.getClosedTabDataForWindow(x)).filter(c => JSON.stringify(c.state.entries || []).includes("smoke-orphan")).length;
      if (!before.closing) w.gBrowser.selectedTab = before;
      await removeWhere((x, t) => url(t).includes("smoke-orphan"));
      return {left, closed};""" % EXT_ID)
    check("a placeholder of a tab that no longer exists closes itself, and is not in Recently Closed", not r["left"] and r["closed"] == 0, str(r))


def popups(m):
    # A sign-in popup (window.open with "popup") must not be synced: no ghosts
    # of it elsewhere, and nothing to pull out of the popup.
    m.js(H + """Services.prefs.setBoolPref("dom.disable_open_during_load", false);
      const w = main(); w.focus(); w.__beforeHelper = w.gBrowser.selectedTab;
      w.gBrowser.selectedTab = w.gBrowser.addTrustedTab("https://example.org/?smoke-opener", {userContextId: 3}); await wait(3000); return 1;""")
    m.cmd("Marionette:SetContext", {"value": "content"})
    for h in m.cmd("WebDriver:GetWindowHandles"):
        m.cmd("WebDriver:SwitchToWindow", {"handle": h, "focus": False})
        if "smoke-opener" in m.cmd("WebDriver:GetCurrentURL"):
            break
    m.cmd("WebDriver:ExecuteScript", {"script": 'window.open("https://example.org/?smoke-popup", "_blank", "popup,width=500,height=400"); return 1;'})
    m.chrome()
    r = m.js(H + """await wait(5000);
      const all = [...Services.wm.getEnumerator("navigator:browser")];
      const popup = all.find(w => w.gBrowser?.tabs.some(t => url(t).includes("smoke-popup")) && !w.toolbar.visible);
      const elsewhere = wins().filter(w => w !== popup).flatMap(w => w.gBrowser.tabs.filter(t => key(w, t) && (url(t).includes("smoke-popup") || t.label.includes("smoke-popup"))));
      const r = {popup: !!popup, synced: popup ? popup.gBrowser.tabs.filter(t => key(popup, t)).length : null, ghosts: elsewhere.length};
      if (popup) { popup.close(); await wait(1500); }
      Services.prefs.clearUserPref("dom.disable_open_during_load");
      const w = main(); if (w.__beforeHelper && !w.__beforeHelper.closing) w.gBrowser.selectedTab = w.__beforeHelper;
      await removeWhere((w, t) => url(t).includes("smoke-opener") || url(t).includes("smoke-popup"));
      return r;""")
    check("a popup window (as for signing in) is left out of tab sync", r["popup"] and r["synced"] == 0 and r["ghosts"] == 0, str(r))


def archiving(m):
    # Pretending time has passed. An old test tab, a tab selected in the other
    # window, and a fixture folder tab; all must be kept within the limit.
    setup = m.js(H + """
      const all = (await storage("%s", ["syncedTabs"])).syncedTabs;
      const inFolder = k => { for (let x = k, n = 0; x && all[x] && n < 50; x = all[x].parentKey, n++) if (all[x].group) return true; return false; };
      const old = main().gBrowser.addTrustedTab("https://example.org/?smoke-archive", {userContextId: 3, inBackground: true});
      const o = other(); o.focus(); await wait(300);
      const sel = o.gBrowser.addTrustedTab("https://example.org/?smoke-archive-selected", {userContextId: 3}); o.gBrowser.selectedTab = sel;
      await wait(5000);
      return {old: key(main(), old), selected: key(o, sel), folder: Object.keys(all).find(k => !all[k].group && inFolder(k)) || null};""" % EXT_ID)
    plain = {"old": json.loads(setup["old"]), "selected": json.loads(setup["selected"]), "folder": setup["folder"]}
    now = int(time.time() * 1000)
    soon = extension_message(m, {"type": "archiveNow", "now": now + 3600 * 1000, "keys": list(plain.values()), "explain": True})
    kept = soon.get("kept", {})
    check("archiving keeps tabs used within the limit, folder tabs and selected tabs", soon.get("archived") == []
          and kept.get(plain["old"], "").startswith("used") and kept.get(plain["selected"]) == "selected" and kept.get(plain["folder"]) == "folder", str(soon))
    late = extension_message(m, {"type": "archiveNow", "now": now + 13 * 3600 * 1000, "keys": list(plain.values()), "explain": True})
    r = m.js(H + """
      const [k, selected, plainKey] = args;
      const closed = w => w.SessionStore.getClosedTabDataForWindow(w).map(c => c.state.entries?.[c.state.index - 1]?.url || "");
      const r = {left: find(k), selectedKept: find(selected).map(x => x.length),
                 closedReal: wins().flatMap(closed).filter(u => u === "https://example.org/?smoke-archive").length,
                 closedGhosts: wins().flatMap(closed).filter(u => u.includes("ghost.html") && u.includes(encodeURIComponent(plainKey))).length};
      await removeWhere((w, t) => key(w, t) === selected);
      return r;""", setup["old"], setup["selected"], plain["old"])
    check("archiving closes a tab unused for longer than the limit everywhere", late.get("archived") == ["https://example.org/?smoke-archive"] and r["left"] == [[], []],
          f"{late}, {r}")
    check("an archived tab is in Recently Closed as the real page only", r["closedReal"] == 1 and r["closedGhosts"] == 0, str(r))
    check("archiving keeps the folder tab and the selected tab after the limit", r["selectedKept"] == [1, 1] and late.get("kept", {}).get(plain["folder"]) == "folder", f"{late}, {r}")
    # A page with unsaved input: closing it would make Firefox select it and ask.
    setup = m.js(H + """const w = main(), selected = w.gBrowser.selectedTab;
      const t = w.gBrowser.addTrustedTab(args[0] + "/unsaved", {userContextId: 3, inBackground: true});
      await wait(5000);
      return {k: key(w, t), selected: selected.linkedPanel};""", m.pages)
    now = int(time.time() * 1000)
    late = extension_message(m, {"type": "archiveNow", "now": now + 13 * 3600 * 1000, "keys": [json.loads(setup["k"])], "explain": True})
    r = m.js(H + """const k = args[0], there = find(k); await removeUnsaved(k); return there;""".replace("removeUnsaved(k)", """(async k => {
        for (const w of wins()) for (const t of [...w.gBrowser.tabs]) if (key(w, t) === k) w.gBrowser.removeTab(t, {skipPermitUnload: true});
        await wait(2500); })(k)"""), setup["k"])
    check("archiving keeps a page with unsaved input, without asking", late.get("archived") == [] and late.get("kept", {}).get(json.loads(setup["k"])) == "unsaved"
          and sum(len(x) for x in r) == 2, f"{late}, {r}")


def shortcuts(m):
    clipboard = H + """
      const read = () => { const t = Cc["@mozilla.org/widget/transferable;1"].createInstance(Ci.nsITransferable); t.init(null); t.addDataFlavor("text/plain");
        Services.clipboard.getData(t, Ci.nsIClipboard.kGlobalClipboard, main().browsingContext.currentWindowContext);
        const o = {}; try { t.getTransferData("text/plain", o); return o.value.QueryInterface(Ci.nsISupportsString).data; } catch (e) { return ""; } };"""
    target = m.js(H + """const w = main(); w.focus();
      const t = w.gBrowser.addTrustedTab("https://example.org/?smoke-copy", {userContextId: 3}); w.gBrowser.selectedTab = t; await wait(3000);
      Cc["@mozilla.org/widget/clipboardhelper;1"].getService(Ci.nsIClipboardHelper).copyString("before");
      return url(t);""")
    # What the page shows, asked of the page's own process: the word is in a closed part of an
    # element of Tidier's own, which a script of the page's cannot open.
    word = H + """const mm = main().gBrowser.selectedBrowser.messageManager;
      const got = new Promise(r => mm.addMessageListener("smoke:word", function heard(msg) { mm.removeMessageListener("smoke:word", heard); r(msg.data); }));
      mm.loadFrameScript("data:," + encodeURIComponent(`sendAsyncMessage("smoke:word", (() => {
        const host = [...content.document.documentElement.children].find(e => e.openOrClosedShadowRoot);
        if (!host) return null;
        const pill = host.openOrClosedShadowRoot.firstElementChild, r = pill.getBoundingClientRect();
        return {text: pill.textContent, off: Math.round(Math.abs((r.left + r.right) / 2 - content.innerWidth / 2)), top: Math.round(r.top),
                clicks: content.getComputedStyle(host).pointerEvents, closed: host.shadowRoot === null};
      })())`), false);
      return Promise.race([got, wait(3000).then(() => "no answer")]);"""
    press(m, "c", CMD, SHIFT)
    said = None
    for _ in range(20):
        said = m.js(word)
        if said:
            break
        time.sleep(0.05)
    line = m.js(H + """const b = main().document.getElementById("sidebar").contentDocument?.querySelector("browser"); if (!b) return "no sidebar";
      const mm = b.messageManager, got = new Promise(r => mm.addMessageListener("smoke:line", function heard(msg) { mm.removeMessageListener("smoke:line", heard); r(msg.data); }));
      mm.loadFrameScript("data:," + encodeURIComponent(`sendAsyncMessage("smoke:line", content.document.getElementById("note").classList.contains("shown") ? content.document.querySelector("#note .text").textContent : "")`), false);
      return Promise.race([got, wait(3000).then(() => "no answer")]);""")
    time.sleep(2.2)
    after = m.js(word)
    copied = m.js(clipboard + "const r = read(); await removeWhere((w, t) => url(t).includes('smoke-copy')); return r;")
    check("⌘⇧C copies the address of the current tab", copied == target, repr(copied))
    check("and says so at the top of the page, in the middle, in a part of the page it cannot read or click, without the access to all websites",
          isinstance(said, dict) and said["text"] == "Address copied" and said["off"] <= 1 and said["top"] < 40 and said["clicks"] == "none" and said["closed"], str(said))
    check("the word is said once (the sidebar's line stays empty) and is gone again in a moment", line == "" and after is None, f"line {line!r}, after {after}")
    before = m.js(H + "main().focus(); await wait(300); return main().SidebarController.currentID;")
    press(m, "b", CMD)
    time.sleep(1.2)
    after = m.js(H + "const S = main().SidebarController; return [S.isOpen, S.currentID];")
    check("⌘B leaves Tidier in the sidebar", after == [True, before] and "6844a953" in (before or ""), f"{before} -> {after}")
    look = H + """const d = main().document;
      return [Math.round(d.getElementById("tabbrowser-tabbox").getBoundingClientRect().left), Math.round(d.getElementById("navigator-toolbox").getBoundingClientRect().right)];"""
    start = m.js(look)
    press(m, "s", CMD); time.sleep(1.2); compact = m.js(look)
    press(m, "s", CMD); time.sleep(1.2); back = m.js(look)
    check("⌘S switches compact mode on (sidebar and toolbar hidden, page full width) and off",
          compact[0] < 20 and compact[1] <= 0 and back == start, f"start {start}, ⌘S {compact}, ⌘S again {back}")


def look(m):
    # The narrowest and widest are the dotfiles' own (--zen-sidebar-min and -max), read from there.
    widths = m.js(H + """const w = main(), d = w.document, box = d.getElementById("sidebar-box"), before = box.style.width, out = [];
      const width = id => Math.round(d.getElementById(id).getBoundingClientRect().width);
      const edge = name => parseInt(w.getComputedStyle(d.documentElement).getPropertyValue(name));
      for (const px of [360, 150, 900]) { box.style.width = px + "px"; await wait(300); out.push([width("sidebar-box"), width("navigator-toolbox")]); }
      box.style.width = before; await wait(300); return {out, min: edge("--zen-sidebar-min"), max: edge("--zen-sidebar-max")};""")
    low, high = widths["min"], widths["max"]
    check("the toolbar follows the sidebar's width, from its narrowest to its widest", 150 < low < 360 < high < 900 and widths["out"] == [[360, 360], [low, low], [high, high]], str(widths))
    # Where 🧩 is (beside the address bar, or on the top row) is the dotfiles' choice; what must
    # hold in a narrow sidebar is that nothing lies over anything else or outside the panel:
    # also with every button there, as forward is once you have gone back and downloads once
    # something has been downloaded (the second round).
    #
    # Two things a box's place does not tell. A button that is narrower than its icon's field
    # (as all are in the narrowest panel, sharing the row) had the field, which is what lights up
    # under the pointer, lying in over its neighbour: so every part of a button is within it.
    # And the window's own buttons (red, yellow, green) are drawn by macOS in the box Firefox
    # keeps for them, 60 px wide from macOS 26; a headless Firefox has no window to ask and
    # keeps 54, so the 60 are counted here. Back begins after them, on their line.
    rows = m.js(H + """const d = main().document, box = d.getElementById("sidebar-box"), before = box.style.width, out = [], fields = [], lights = [];
      const r = id => d.getElementById(id).getBoundingClientRect();
      const parts = id => [...d.getElementById(id).querySelectorAll(".toolbarbutton-icon, .toolbarbutton-badge-stack, toolbarbutton")].map(e => e.getBoundingClientRect()).filter(x => x.width);
      const middle = x => (x.top + x.bottom) / 2;
      const forward = d.getElementById("forward-button"), downloads = d.getElementById("downloads-button");
      const was = [forward.hasAttribute("disabled"), downloads.hidden];
      for (const every of [false, true]) {
        if (every) { forward.removeAttribute("disabled"); downloads.hidden = false; }
        for (const px of [args[0], 300, 480]) {
          box.style.width = px + "px"; await wait(400);
          const row1 = ["back-button", "stop-reload-button", "PanelUI-button"].map(r), bar = r("urlbar-container");
          const all = ["back-button", "forward-button", "stop-reload-button", "downloads-button", "PanelUI-button", "urlbar-container", "unified-extensions-button"].map(r).filter(x => x.width);
          const one = rs => rs.every(x => Math.abs(x.top - rs[0].top) < 8);
          const over = (a, b) => a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5;
          out.push(!d.getElementById("nav-bar").hasAttribute("overflowing") && one(row1) && bar.top > row1[0].top && bar.width > px * 0.75
                   && all.length >= (every ? 7 : 5) && all.every(x => x.width >= 16)  // an icon is 16 px
                   && all.every((a, i) => all.every((b, j) => j <= i || !over(a, b))) && all.every(x => x.left >= 0 && x.right <= px + 0.5));
          const there = ["back-button", "forward-button", "stop-reload-button", "downloads-button", "unified-extensions-button", "PanelUI-button"].filter(id => r(id).width);
          fields.push(there.length >= (every ? 6 : 3) && there.every(id =>
            parts(id).length && parts(id).every(x => x.left >= r(id).left - 0.5 && x.right <= r(id).right + 0.5)));
          const own = d.querySelector("#TabsToolbar .titlebar-buttonbox")?.getBoundingClientRect();
          lights.push(!!own && row1[0].left >= own.left + 60 + 1 && Math.abs(middle(own) - middle(row1[0])) <= 1);
        }
      }
      if (was[0]) forward.setAttribute("disabled", "true");
      downloads.hidden = was[1];
      box.style.width = before; await wait(300); return {out, fields, lights};""", low)
    check("the top row is back, reload and ☰, with the address bar below, and nothing over anything else, from the narrowest to 480 px (nothing behind »), also with forward and downloads there", len(rows["out"]) == 6 and all(rows["out"]), str(rows["out"]))
    check("every button on the top row holds its own icon and field, also where the buttons are at their narrowest", len(rows["fields"]) == 6 and all(rows["fields"]), str(rows["fields"]))
    if sys.platform == "darwin":
        check("back begins after the window's own buttons, as wide as macOS 26 draws them, and on their line", len(rows["lights"]) == 6 and all(rows["lights"]), str(rows["lights"]))
    # In its new sidebar Firefox heads an extension's panel with the extension's name and a ×
    # that closes the sidebar, inside the panel's own document (not the window's, where the old
    # header was). Tidier is the sidebar, not a panel to close by a slip: the dotfiles'
    # stylesheet takes the header away, and Tidier begins right under the toolbar.
    top = m.js(H + """const d = main().document, box = d.getElementById("sidebar-box"), side = d.getElementById("sidebar"), inner = side.contentDocument;
      const page = inner.querySelector("browser");
      return {panel: inner.documentURI.split("/").pop(), outer: Math.round(side.getBoundingClientRect().top - box.getBoundingClientRect().top - parseFloat(main().getComputedStyle(box).paddingTop)),
              inner: page ? Math.round(page.getBoundingClientRect().top) : null};""")
    check("nothing of Firefox's own (the extension's name, a × that closes the sidebar) lies between the toolbar and Tidier", top["outer"] == 0 and top["inner"] == 0, str(top))
    # A later Firefox that renames a part of its toolbar leaves a rule in the dotfiles' stylesheet
    # with nothing to act on, and nothing says so: the look just changes (as the address field's
    # did, when its background lost its ID). So every part the stylesheet names by ID or class
    # is looked for; Developer Edition, a version ahead, is tested too.
    sheet = re.sub(r"/\*.*?\*/", "", open(f"{DOTFILES}/userChrome.css").read(), flags=re.S)
    ids = sorted({i for i in re.findall(r"#([A-Za-z][\w-]*)", sheet) if not re.fullmatch(r"[0-9a-fA-F]{3,8}", i)})  # not a colour
    # (The panel a toolbar button's popup opens in is made as it opens, and gone when it closes:
    # that its rule still acts is seen where the command bar is, in alone_command_bar.)
    ids = [i for i in ids if i != "customizationui-widget-panel"]
    classes = sorted(set(re.findall(r"(?<![\w)])\.([A-Za-z][\w-]*)", sheet)))  # not a number, as in .15s
    gone = m.js(H + """const d = main().document;
      return [...args[0].filter(id => !d.getElementById(id)).map(id => "#" + id), ...args[1].filter(c => !d.querySelector("." + c)).map(c => "." + c)];""", ids, classes)
    check("every part of Firefox the dotfiles' stylesheet names is in this Firefox", len(ids) > 20 and not gone, f"{gone} of {len(ids)} IDs and {len(classes)} classes")
    full = m.js(H + """const w = main(), d = w.document, root = d.documentElement;
      root.setAttribute("inDOMFullscreen", true); await wait(400);  // as Firefox marks a fullscreen video
      const b = d.getElementById("tabbrowser-tabbox").getBoundingClientRect(), side = d.getElementById("sidebar-box").getBoundingClientRect();
      const out = [Math.round(b.left), Math.round(b.top), Math.round(b.width) === w.innerWidth, Math.round(b.height) === w.innerHeight, side.width];
      root.removeAttribute("inDOMFullscreen"); await wait(300); return out;""")
    check("a fullscreen video fills the whole window (no frame, no sidebar)", full == [0, 0, True, True, 0], str(full))
    bar = H + """const w = main(), d = w.document, u = d.getElementById("urlbar").getBoundingClientRect(), v = d.querySelector(".urlbarView")?.getBoundingClientRect();
      return {open: d.getElementById("urlbar").hasAttribute("popover-open"), centre: Math.round(u.left + u.width / 2 - w.innerWidth / 2), list: v ? Math.round(v.left - u.left) : null};"""
    for compact in (False, True):
        m.js(H + "main().focus(); return 1;")
        if compact:
            press(m, "s", CMD); time.sleep(1.2)
        press(m, "l", CMD); time.sleep(1)
        got = m.js(bar)
        press(m, ESC); press(m, ESC); time.sleep(0.5)
        if compact:
            press(m, "s", CMD); time.sleep(1.2)
        check(f"⌘L opens the address bar centred, results under it ({'compact' if compact else 'normal'})",
              got["open"] and abs(got["centre"]) <= 2 and got["list"] is not None and abs(got["list"]) <= 5, str(got))


def live_folders(m):
    # The native host is a stand-in (fake_github_host.py) that answers from
    # m.fake_prs; the test rewrites the file and asks Tidier to refresh.
    def answer(items, renamed=(), more=None):
        json.dump({"folders": [{"id": "smoke", "name": "Smoke PRs", "container": "firefox-container-2"}],
                   "items": {"smoke": [{"url": f"https://example.org/?smoke-pr-{n}", "title": f"Pull request {n}" + (" renamed" if n in renamed else ""),
                                        "number": n, "repo": "smoke", **(more or {})} for n in items]}}, open(m.fake_prs, "w"))
        return extension_message(m, {"type": "refreshLiveFolders"})

    # The folder is one of Tidier's own, in the record (live: its id); its tabs are in it by their
    # record, and in container 2.
    state = H + """
      const all = (await storage("%s", ["syncedTabs"])).syncedTabs, out = [];
      const folder = Object.keys(all).find(k => all[k].group && all[k].live === "smoke");
      const inIt = (w, t) => !!folder && !!key(w, t) && all[JSON.parse(key(w, t))]?.parentKey === folder;
      for (const w of [main(), other()]) {
        const prs = w.gBrowser.tabs.filter(t => t.label.includes("Pull request "));
        out.push({group: !!folder && all[folder].own && all[folder].cookieStoreId === "firefox-container-2", inFolder: prs.filter(t => inIt(w, t)).map(t => t.label.replace(/^.*Pull/, "Pull")).sort(),
                  outside: prs.filter(t => !inIt(w, t)).map(t => t.label),
                  loaded: prs.filter(t => t.linkedPanel && !t.hasAttribute("pending") && !t.selected).map(t => t.label),  // pending: not loaded yet
                  space: prs.every(t => t.userContextId === 2)});
      }
      return out;""" % EXT_ID
    replied = answer([1, 2])
    time.sleep(4)
    first = m.js(state)
    want = ["Pull request 1", "Pull request 2"]
    check("a live folder is Tidier's own, with its pull requests unloaded in every window, in its space",
          replied is True and all(w["group"] and w["inFolder"] == want and not w["outside"] and not w["loaded"] and w["space"]
                                  for w in first), f"{replied}, {first}")
    m.js(H + """const t = main().gBrowser.tabs.find(t => t.label.endsWith("Pull request 1")); if (t) main().gBrowser.removeTab(t); await wait(3000); return 1;""")
    answer([1, 2, 3])
    time.sleep(4)
    second = m.js(state)
    check("a closed pull request tab stays closed when the folder is refreshed",
          all(w["inFolder"] == ["Pull request 2", "Pull request 3"] and not w["outside"] for w in second), str(second))
    # Merged while you read it: the selected tab stays until you leave it. (In
    # the other window: the refresh is asked for from a page in the main one.)
    k = m.js(H + """const w = other(), t = w.gBrowser.tabs.find(t => t.label.endsWith("Pull request 2"));
      if (!t) return null; const k = key(w, t);
      w.focus(); await wait(500); w.__smokePrev = w.gBrowser.selectedTab; w.gBrowser.selectedTab = t; await wait(3000);
      return [k, find(k), wins().map(x => x.gBrowser.tabs.filter(y => key(x, y) === k).map(y => [y.selected, url(y).slice(0, 60)]))];""")
    k, selected, sel_detail = k if k else (None, None, None)
    answer([3])
    time.sleep(4)
    kept = m.js(H + "return find(%s).map(roles => roles.length);" % json.dumps(k))
    check("a pull request that leaves the search keeps its tabs while you are looking at it", k and kept == [1, 1], f"{k}, {kept}, when selected {selected} {sel_detail}")
    m.js(H + """const w = other(); if (w.__smokePrev) w.gBrowser.selectedTab = w.__smokePrev; delete w.__smokePrev; await wait(1500); return 1;""")
    answer([3])
    time.sleep(4)
    third = m.js(state)
    check("a pull request that leaves the search is removed from every window",
          all(w["inFolder"] == ["Pull request 3"] and not w["outside"] for w in third), str(third))
    answer([3], renamed=[3])
    time.sleep(5)
    fourth = m.js(state)
    check("a renamed pull request's unloaded tabs take the new title",
          all(w["inFolder"] == ["Pull request 3 renamed"] and not w["loaded"] for w in fourth), str(fourth))
    # What it waits for is in its record, for its icon in the sidebar, and changing it touches no tab.
    waits = H + """const all = (await storage("%s", ["syncedTabs"])).syncedTabs;
      return [Object.values(all).filter(e => e.liveFolder === "smoke").map(e => e.pr),
              wins().map(w => w.gBrowser.tabs.filter(t => t.label.includes("Pull request ")).map(t => [t.linkedPanel, t.hasAttribute("pending")]))];""" % EXT_ID
    before = m.js(waits)
    answer([3], renamed=[3], more={"mine": True, "checks": "failing"})
    time.sleep(3)
    after = m.js(waits)
    check("a pull request's record says what it waits for, and follows the search without touching its tabs",
          before[0] == ["open"] and after[0] == ["failing"] and after[1] == before[1], f"{before} -> {after}")
    # A search that fails (gh logged out, no network) changes nothing.
    json.dump({"folders": [{"id": "smoke", "name": "Smoke PRs", "container": "firefox-container-2"}], "items": {}}, open(m.fake_prs, "w"))
    extension_message(m, {"type": "refreshLiveFolders"})
    time.sleep(3)
    fifth = m.js(state)
    content = lambda ws: [(w["group"], w["inFolder"], w["outside"]) for w in ws]
    check("a failed search leaves the live folder as it was", content(fifth) == content(fourth), f"{fourth} -> {fifth}")
    json.dump({}, open(m.fake_prs, "w"))
    m.js(H + """await removeWhere((w, t) => t.label.includes("Pull request ")); return 1;""")


def many_tabs(m):
    # Closer to a real setup (yours has about 30 essentials and 50 tabs): ten
    # more essentials and thirty more tabs over the three spaces, then a new
    # window, which must get them all, in their spaces, unloaded.
    before, proc0 = extension_message(m, {"type": "stats"}), m.js(PROC_INFO)
    r = m.js(H + """
      const w = main();
      for (let i = 0; i < 30; i++) { w.gBrowser.addTrustedTab("https://example.org/?smoke-many-" + i, {userContextId: 1 + i % 3, inBackground: true}); await wait(150); }
      await wait(4000);
      for (let i = 0; i < 10; i++) {
        const t = w.gBrowser.addTrustedTab("https://example.org/?smoke-many-e" + i, {userContextId: 1 + i % 3, inBackground: true});
        await wait(1500); w.gBrowser.pinTab(t); await wait(500);
      }
      await wait(6000);
      const pinned0 = w.gBrowser.tabs.filter(t => t.pinned).length, want = w.gBrowser.tabs.filter(t => !t.pinned && role(w, t)).length;
      const t0 = Date.now(), n = w.OpenBrowserWindow(); n.__extra = true;
      let ms = null;
      try {
        for (let i = 0; i < 100 && !n.gBrowser; i++) await wait(100);
        for (let i = 0; i < 300 && ms === null; i++) {
          await wait(100);
          if (n.gBrowser.tabs.filter(t => t.pinned).length >= pinned0 && n.gBrowser.tabs.filter(t => !t.pinned && role(n, t)).length >= want) ms = Date.now() - t0;
        }
        const loaded = () => n.gBrowser.tabs.filter(t => t.linkedPanel && !t.selected && url(t).includes("ghost.html"));
        for (let i = 0; i < 60 && (i < 16 || loaded().length); i++) await wait(250);
        // Each tab of the new window in the container its tab has in the main window.
        const containerOf = new Map(w.gBrowser.tabs.filter(t => key(w, t)).map(t => [key(w, t), t.userContextId]));
        return {ms, essentials: [pinned0, n.gBrowser.tabs.filter(t => t.pinned).length], tabs: [want, n.gBrowser.tabs.filter(t => !t.pinned && role(n, t)).length],
                stillLoaded: loaded().length, elsewhere: n.gBrowser.tabs.filter(t => key(n, t) && containerOf.get(key(n, t)) !== t.userContextId).map(t => t.label)};
      } finally {
        await close(n);
        // Unpinning one copy removes an essential everywhere; then the tabs go.
        for (const t of w.gBrowser.tabs.filter(t => t.pinned && url(t).includes("smoke-many"))) w.gBrowser.unpinTab(t);
        await wait(4000);
        await removeWhere((x, t) => !t.pinned && url(t).includes("smoke-many"));
      }""")
    check(f"with {r['essentials'][0]} essentials and {r['tabs'][0]} tabs, a new window gets them all ({r['ms']} ms)",
          r["ms"] is not None and r["essentials"][0] == r["essentials"][1] and r["tabs"][0] == r["tabs"][1], str(r))
    check("with that many, every tab is in its own container in the new window", not r["elsewhere"], str(r))
    check("with that many, the placeholders unload", not r["stillLoaded"], str(r))
    left = m.js(H + """await wait(2000); return wins().map(w => w.gBrowser.tabs.filter(t => url(t).includes("smoke-many") || (t.pinned && !ek(w, t))).map(t => t.label));""")
    check("and they are all gone again once closed", all(not x for x in left), str(left))
    # Memory and work. Tidier's lists of tabs and windows are back to their
    # size once the tabs and the window are gone (after the 10 s in which
    # closed placeholders are looked for in Recently Closed), and with nothing
    # happening Tidier does nothing (unless a timed check came by).
    time.sleep(12)
    after = extension_message(m, {"type": "stats"})
    grown = {k: (before["sizes"][k], n) for k, n in after["sizes"].items() if n > before["sizes"].get(k, 0)}
    check("Tidier's lists in memory are back to their size once the tabs and the window are closed", not grown, f"grown (before, after): {grown}")
    idle = extension_message(m, {"type": "idle", "ms": 15000})
    if idle["alarms"]:
        print(f"SKIP  idle check: a timed check ran meanwhile ({idle})", flush=True)
    else:
        check("with nothing happening, Tidier does nothing (15 s)", idle["jobs"] == 0 and idle["lookups"] == 0, str(idle))
    # A page whose title ticks must not rewrite Tidier's record at every tick.
    r = m.js(H + """const w = main();
      const t = w.gBrowser.addTrustedTab(args[0] + "/ticking", {userContextId: 3, inBackground: true});
      await wait(5000);
      const k = JSON.parse(key(w, t));
      const db = await ExtensionStorageIDB.open(ExtensionStorageIDB.getStoragePrincipal(WebExtensionPolicy.getByID("%s").extension));
      const seen = new Set(), read = async () => JSON.stringify((await db.get(["syncedTabs"])).syncedTabs);
      for (let i = 0; i < 30; i++) { seen.add(await read()); await wait(500); }
      await removeWhere((x, y) => key(x, y) === key(w, t));
      return {writes: seen.size};""" % EXT_ID, m.pages)
    check("a page whose title ticks writes Tidier's record rarely", r["writes"] <= 3, str(r))
    proc = m.js(PROC_INFO)
    print(f"INFO  for 30 tabs and 10 essentials, a new window and closing them all: {after['jobs'] - before['jobs']} jobs, "
          f"queue busy {round((after['queueMs'] - before['queueMs']) / 1000, 1)} s, "
          f"{after['lookups'] - before['lookups']} tab lookups; extension process "
          f"{proc['mb']} MB, {round(proc['cpuS'] - proc0['cpuS'], 1)} s CPU", flush=True)


def handover(m):
    r = m.js(H + """
      const t = other().gBrowser.addTrustedTab("https://example.org/?smoke-handover", {userContextId: 1, inBackground: true});
      await wait(4500); const k = key(other(), t);
      await close(other());
      return find(k);""")
    check("closing a window hands its tabs over", r in ([["live/unloaded"]], [["live/loaded"]]), str(r))


def reopened_window(m):
    # Reopening the window closed above (⌘⇧N) brings its tabs back with their
    # Tidier values; nothing may be doubled.
    r = m.js(H + """
      const count = () => { const by = {};
        for (const [i, w] of wins().entries()) for (const t of w.gBrowser.tabs) { const k = key(w, t); if (!k) continue;
          const c = by[k] ??= {perWindow: wins().map(() => 0), live: 0}; c.perWindow[i]++; if (role(w, t) === "live") c.live++; }
        return by; };
      const synced = async () => Object.keys((await storage("%s", ["syncedTabs"])).syncedTabs).length;
      const before = await synced();
      const w = main().SessionStore.undoCloseWindow(0); w.__smoke = true;
      for (let i = 0; i < 100 && !w.gBrowser; i++) await wait(100);
      await wait(9000);
      const by = count(), after = await synced();
      const doubled = Object.entries(by).filter(([, c]) => c.live !== 1 || c.perWindow.some(n => n !== 1)).map(([k, c]) => [k, c]);
      const all = (await storage("%s", ["syncedTabs"])).syncedTabs;
      const dead = w.gBrowser.tabs.filter(t => url(t).includes("ghost.html") && !key(w, t) && !t.pinned)
        .map(t => { const q = new URLSearchParams(url(t).split("?")[1]); return [t.label, q.get("kind"), q.get("kind") === "essential" ? "" : all[q.get("key")] ? "synced" : "gone"]; });
      const pinned = wins().map(x => x.gBrowser.tabs.filter(t => t.pinned).length);
      await close(w);
      return {before, after, doubled: doubled.slice(0, 5), dead, pinned};""" % (EXT_ID, EXT_ID))
    check("a reopened window takes its tabs back, with nothing doubled", r["before"] == r["after"] and not r["doubled"] and not r["dead"]
          and r["pinned"][0] == r["pinned"][1], str(r))


# Every window's essentials and tabs, to compare a session before and after.
SNAP = H + """
      const out = [], all = (await storage("%s", ["syncedTabs"])).syncedTabs;
      // A test tab seeded in a folder (seed_folders) is in it by the record, and so in every window.
      const entryOf = (w, t) => key(w, t) ? all[JSON.parse(key(w, t))] : null;
      const seededIn = (w, t) => /fixture-in-folder/.test(entryOf(w, t)?.url || "");
      for (const w of wins()) {
        const tabs = w.gBrowser.tabs;
        out.push({essentials: tabs.filter(t => t.pinned).map(t => ek(w, t) || "untagged " + t.label),
                  keys: tabs.filter(t => !t.pinned && key(w, t)).map(t => key(w, t)).sort(),
                  live: tabs.filter(t => !t.pinned && role(w, t) === "live").map(t => key(w, t)),
                  untagged: tabs.filter(t => !t.pinned && !key(w, t)).map(t => t.label + " " + url(t).slice(0, 60)),
                  folderTabs: tabs.filter(t => seededIn(w, t)).length,
                  inFolders: tabs.filter(t => seededIn(w, t) && !all[entryOf(w, t).parentKey]?.group).map(t => t.label)});
      }
      const order = w => JSON.stringify([w.keys, w.essentials, w.untagged]);
      out.sort((a, b) => order(a) < order(b) ? -1 : order(a) > order(b) ? 1 : 0);
      const synced = Object.keys(all).length;
      return {windows: out, synced};""" % EXT_ID


def update(m):
    # What every release does in the daily browser: a new version installed over a
    # running session. Firefox stops Tidier and closes its pages that are loaded,
    # here a placeholder selected in the window you are not using; the record and
    # the unloaded tabs carry everything over.
    if not m.can_restart:
        print("SKIP  update (needs Tidier installed for real: Developer Edition, or --xpi)", flush=True)
        return
    selected = m.js(H + """let a = wins().find(w => w !== main());
      if (!a) { a = main().OpenBrowserWindow(); a.__extra = true; for (let i = 0; i < 100 && !a.gBrowser; i++) await wait(100); await wait(9000); }
      const g = a.gBrowser.tabs.find(t => role(a, t) === "ghost" && !t.pinned && !t.selected);
      a.gBrowser.selectedTab = g; main().focus(); await wait(2000);
      return {key: key(a, g), loaded: !!g.linkedPanel};""")
    before = m.js(SNAP)
    m.cmd("Addon:Install", {"path": m.update_xpi(), "temporary": False})
    m.js(H + "await wait(9000); return 1;")
    after = m.js(SNAP)
    r = m.js(H + """const {AddonManager} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
      const closed = wins().flatMap(w => w.SessionStore.getClosedTabDataForWindow(w)).map(c => c.state.entries?.[c.state.index - 1]?.url || "");
      const lastTab = main().gBrowser.addTrustedTab("https://example.org/?smoke-after-update", {userContextId: 1, inBackground: true});
      await wait(5000);
      const k = key(main(), lastTab), got = find(k);
      await removeWhere((w, x) => key(w, x) === k);
      return {version: (await AddonManager.getAddonByID("%s")).version, closedGhosts: closed.filter(u => u.includes("ghost.html")).length, got};""" % EXT_ID)
    check("an update is installed over the running session", r["version"] == "1.6.999999", str(r))
    bw, aw = before["windows"], after["windows"]
    check("after an update, every window has the same essentials and tabs as before",
          len(aw) == len(bw) and [w["essentials"] for w in aw] == [w["essentials"] for w in bw] and [w["keys"] for w in aw] == [w["keys"] for w in bw]
          and after["synced"] == before["synced"],
          f"selected {selected}; tabs gone {[sorted(set(b['keys']) - set(a['keys'])) for a, b in zip(aw, bw)]}, new {[sorted(set(a['keys']) - set(b['keys'])) for a, b in zip(aw, bw)]}; "
          f"essentials before {[w['essentials'] for w in bw]}, after {[w['essentials'] for w in aw]}; {before['synced']} -> {after['synced']}")
    lives = sorted(k for w in aw for k in w["live"])
    check("after an update, every tab is live in one window only", lives == sorted(k for w in bw for k in w["live"]) and len(lives) == len(set(lives)), f"{lives}")
    check("after an update, no placeholder is left in Recently Closed", r["closedGhosts"] == 0, str(r))
    check("after an update, a new tab gets a ghost in the other window", sorted(r["got"]) == [["ghost/unloaded"], ["live/loaded"]], str(r))
    no_problems(m, "after an update")


def restart(m):
    # Quitting and starting Firefox again restores both windows with their
    # tabs' Tidier values: the same essentials and tabs in each, one live tab
    # each, folders with their tabs, every tab in its space, and tab sync and
    # new windows work as before.
    if not m.can_restart:
        check("the restart test can run here", not os.environ.get("TIDIER_MUST_RESTART"), "TIDIER_MUST_RESTART is set")
        print("SKIP  restart (Tidier is a temporary add-on here, which Firefox removes when it quits; "
              "runs where unsigned add-ons are allowed, as in Developer Edition, or with --xpi)", flush=True)
        return
    no_problems(m, "before a restart")
    snap = SNAP
    m.js(H + """if (wins().length < 2) { const w = main().OpenBrowserWindow(); for (let i = 0; i < 100 && !w.gBrowser; i++) await wait(100); await wait(9000); } return 1;""")
    before = m.js(snap)
    t0 = time.time()
    m.restart()
    # Tidier starts 5 s after Firefox (onStartup), then fills in what is missing.
    m.js(H + """for (let i = 0; i < 100 && wins().length < 2; i++) await wait(200); await wait(15000); return 1;""")
    after = m.js(snap)
    print(f"INFO  restarted in {round(time.time() - t0)} s: {len(before['windows'])} -> {len(after['windows'])} windows", flush=True)
    bw, aw = before["windows"], after["windows"]
    check("after a restart, both windows have the same essentials and tabs as before",
          len(aw) == len(bw) == 2 and all(w["essentials"] and w["keys"] for w in bw) and [w["essentials"] for w in aw] == [w["essentials"] for w in bw]
          and [w["keys"] for w in aw] == [w["keys"] for w in bw] and after["synced"] == before["synced"],
          f"before {[(len(w['essentials']), len(w['keys'])) for w in bw]} {before['synced']}, after {[(len(w['essentials']), len(w['keys'])) for w in aw]} {after['synced']}; "
          f"same essentials {[a['essentials'] == b['essentials'] for a, b in zip(aw, bw)]}, same tabs {[a['keys'] == b['keys'] for a, b in zip(aw, bw)]}, "
          f"essentials before {[w['essentials'] for w in bw]}, after {[w['essentials'] for w in aw]}, "
          f"tabs gone {[sorted(set(b['keys']) - set(a['keys'])) for a, b in zip(aw, bw)]}, new {[sorted(set(a['keys']) - set(b['keys'])) for a, b in zip(aw, bw)]}")
    lives = sorted(k for w in aw for k in w["live"])
    check("after a restart, every tab is live in one window only, and no other tab came or went",
          len(lives) == len(set(lives)) and sorted(w["untagged"] for w in aw) == sorted(w["untagged"] for w in bw),
          f"doubled {[k for k in lives if lives.count(k) > 1][:3]}, others before {[w['untagged'] for w in bw]}, after {[w['untagged'] for w in aw]}")
    check("after a restart, folders keep their tabs",
          all(w["folderTabs"] and not w["inFolders"] for w in aw), str([(w["folderTabs"], w["inFolders"][:3]) for w in aw]))
    # Tab sync works as before: a new tab gets a ghost in the other window.
    r = m.js(H + """
      const [a] = wins(); const t = a.gBrowser.addTrustedTab("https://example.org/?smoke-after-restart", {userContextId: 1, inBackground: true});
      await wait(5000); const k = key(a, t), got = find(k);
      await removeWhere((w, x) => key(w, x) === k);
      return got;""")
    check("after a restart, a new tab gets a ghost in the other window", sorted(r) == [["ghost/unloaded"], ["live/loaded"]], str(r))
    r = m.js(H + """
      const [a] = wins(), pinned0 = a.gBrowser.tabs.filter(t => t.pinned).length, want = a.gBrowser.tabs.filter(t => !t.pinned && role(a, t)).length;
      const w = a.OpenBrowserWindow(); for (let i = 0; i < 100 && !w.gBrowser; i++) await wait(100);
      await wait(8000);
      const got = [w.gBrowser.tabs.filter(t => t.pinned).length, w.gBrowser.tabs.filter(t => !t.pinned && role(w, t)).length];
      await close(w);
      return {want: [pinned0, want], got};""")
    check("after a restart, a new window gets all essentials and tabs", r["want"] == r["got"], str(r))


# A Sidebery folder's page as a browser that never moved over still has it: unloaded, in each
# window, in the folder's space. (Sidebery's own address; the page itself is never shown.)
OLD_FOLDER_PAGE = "moz-extension://3c078156-979c-498b-8990-85f7987dd929/sidebery/group.html#Old%20folder"


def old_browser(m):
    # A browser that skipped the click on the move over (PLAN.md, part E): its record has a
    # folder of Sidebery's, whose page is open in every window, with two tabs in it, and Tidier
    # is enabled again with that. Its first start moves it over by itself (moveover.js): a copy
    # first, then the record, and only then are the pages closed. Nothing is lost.
    state = H + """const all = (await storage(args[0], ["syncedTabs", "movedNote", "importedFolds", "copyBeforeMove"]));
      const r = all.syncedTabs, f = r["smoke-old-folder"];
      return {folder: f && {own: !!f.own, name: f.name ?? null, oldUrl: f.oldUrl ?? null, collapsed: !!f.collapsed},
              inIt: Object.keys(r).filter(k => r[k].parentKey === "smoke-old-folder").map(k => [k, !!r[k].saved]).sort(),
              pages: wins().map(w => w.gBrowser.tabs.filter(t => url(t).includes("/sidebery/group.html")).length),
              copies: Object.keys(r).filter(k => r[k].parentKey === "smoke-old-folder").map(k => wins().map(w => w.gBrowser.tabs.filter(t => key(w, t) === JSON.stringify(k)).length)),
              note: all.movedNote ?? null, waiting: all.importedFolds ?? null, inStorage: !!all.copyBeforeMove,
              settings: wins().map(w => w.gBrowser.tabs.filter(t => url(t).includes("/settings/settings.html")).length),
              inFront: wins().filter(w => url(w.gBrowser.selectedTab).includes("/settings/settings.html")).length,
              closed: wins().flatMap(w => w.SessionStore.getClosedTabDataForWindow(w)).filter(c => JSON.stringify(c.state.entries || []).includes("/sidebery/group.html")).length};"""
    # Two windows: the folder's page is in every one of them. The second window this group is
    # given (new_window's) is closed again by reopened_window, and in a Firefox where Tidier
    # cannot be installed for real, update and restart, which make or restore one, are skipped:
    # so one is made here where there is none, rather than leaving this group to what the
    # groups before it happened to leave behind.
    m.js(H + """if (wins().length > 1) return 0;
      const w = main().OpenBrowserWindow(); w.__smoke = true;
      for (let i = 0; i < 100 && !w.gBrowser; i++) await wait(100);
      const want = main().gBrowser.tabs.filter(t => !t.pinned && role(main(), t)).length;
      for (let i = 0; i < 200 && w.gBrowser.tabs.filter(t => !t.pinned && role(w, t)).length < want; i++) await wait(100);
      await wait(3000); return 1;""")
    extension_message(m, {"type": "flush"})
    picked = m.js(H + """const {AddonManager} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
      const [id, page] = args, ext = WebExtensionPolicy.getByID(id).extension;
      const db = await ExtensionStorageIDB.open(ExtensionStorageIDB.getStoragePrincipal(ext));
      const addon = await AddonManager.getAddonByID(id);
      await addon.disable(); await wait(1500);
      const r = (await db.get(["syncedTabs"])).syncedTabs;
      const two = Object.keys(r).filter(k => !r[k].group && r[k].cookieStoreId === "firefox-container-2" && !r[k].parentKey && /fixture-tab-2/.test(r[k].url)).slice(0, 2);
      r["smoke-old-folder"] = {group: true, url: page, title: "Old folder", cookieStoreId: "firefox-container-2", parentKey: null, added: 1};
      for (const k of two) Object.assign(r[k], {parentKey: "smoke-old-folder", saved: {url: r[k].url, title: r[k].title}});
      // Closed in Sidebery's export, which an older Tidier took in before the move.
      await db.set({syncedTabs: r, importedFolds: ["firefox-container-2|group.html#Old%20folder"]});
      for (const w of wins()) {
        const t = w.gBrowser.addTrustedTab(page, {userContextId: 2, inBackground: true, createLazyBrowser: true, lazyTabTitle: "Old folder"});
        w.SessionStore.setCustomTabValue(t, "extension:" + id + ":syncKey", JSON.stringify("smoke-old-folder"));
        w.SessionStore.setCustomTabValue(t, "extension:" + id + ":syncRole", JSON.stringify("copy"));
      }
      await wait(500);
      const pages = wins().map(w => w.gBrowser.tabs.filter(t => url(t).includes("/sidebery/group.html")).length);
      await addon.enable(); await wait(12000);
      return {two, pages};""", EXT_ID, OLD_FOLDER_PAGE)
    r = m.js(state, EXT_ID)
    copy = json.load(open(m.fake_prs + ".copy")) if os.path.exists(m.fake_prs + ".copy") else {}
    was = copy.get("data", {}).get("syncedTabs", {}).get("smoke-old-folder", {})
    check("(a browser that never moved over: Sidebery's folder pages in every window, and its folder in the record)", len(picked["two"]) == 2 and picked["pages"] == [1, 1], str(picked))
    check("its first start takes a copy first, of the record as it was", was.get("url") == OLD_FOLDER_PAGE and not was.get("own") and not r["inStorage"], f"{was}, {r}")
    check("Sidebery's folder becomes Tidier's own, with its name, closed as Sidebery had it", r["folder"] == {"own": True, "name": "Old folder", "oldUrl": OLD_FOLDER_PAGE, "collapsed": True}
          and r["waiting"] == [], str(r))
    check("its tabs stay in it, saved, in every window", r["inIt"] == sorted([k, True] for k in picked["two"]) and r["copies"] == [[1, 1], [1, 1]], str(r))
    check("only then are the folder pages closed, and none is left in Recently Closed", r["pages"] == [0, 0] and r["closed"] == 0, str(r))
    # Nobody asked for the move, so Tidier's settings page is in front and says what came over
    # (afterMoving, moveover.js). Here Tidier may not hide tabs, as on a browser that ran it
    # beside Sidebery, so the page says how to let it; and each window without Tidier's sidebar
    # has the page, with a button for the sidebar (aftermove.js).
    said = None
    if r["inFront"]:
        into_page(m, "/settings/settings.html")
        said = m.cmd("WebDriver:ExecuteScript", {"script": """const d = (window.wrappedJSObject || window).document, shown = id => !d.getElementById(id).hidden;
          return {text: shown("moved-section") && shown("moved") ? d.getElementById("moved").textContent : null, ask: shown("moved-ask"), allow: shown("moved-allow"),
                  sidebar: shown("windows-without") && shown("show-sidebar")};"""})
        m.chrome()
    check("Tidier's settings page is in front and says what came over, after a copy", bool(said) and "1 folder" in (said["text"] or "") and "A copy of everything was taken first" in said["text"]
          and "Sidebery is no longer needed" in said["text"], f"{said} {r['settings']}")
    check("where Tidier may not hide tabs yet, the page says how to let it", bool(said) and said["allow"] and not said["ask"], str(said))
    check("said once: the note is gone from storage", r["note"] is None, str(r["note"]))
    m.js(H + """await removeWhere((w, t) => url(t).includes("/settings/settings.html")); return 1;""")
    view = sidebar_page(m, """send({type: "space", space: "firefox-container-2"}); await wait(1500);
      return {folders: folders().filter(f => f.name === "Old folder").map(f => [f.tabs.length, f.collapsed])};""")
    check("the sidebar shows it as a folder, closed", view.get("folders") == [[0, True]] or view.get("folders") == [[2, True]], str(view))
    later = ext_page(m, "/settings/settings.html", """await wait(800); return doc.getElementById("moved").hidden;""")
    check("a settings page opened later does not say it again", later is True, str(later))
    r = m.js(state, EXT_ID)
    m.js(H + """const {AddonManager} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
      const addon = await AddonManager.getAddonByID(args[0]); await addon.disable(); await wait(1500); await addon.enable(); await wait(9000); return 1;""", EXT_ID)
    again = m.js(state, EXT_ID)
    check("the next start has nothing to move, and leaves it as it is", again["folder"] == r["folder"] and again["inIt"] == r["inIt"] and again["pages"] == [0, 0] and again["inFront"] == 0, f"{r} -> {again}")
    no_problems(m, "after a browser moved over by itself")
    close_sidebar_page(m)
