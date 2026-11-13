"""Isolation: nothing goes out in the wrong container."""
import time
import urllib.parse
from testfirefox import EXT_ID
from smokechecks.base import CTRL, GIVE_PERMISSIONS, H, LITTLE, check, ext_page, extension_message, no_problems, press, seen, sidebar_page


ISOLATION_JS = H + """
  const system = Services.scriptSecurityManager.getSystemPrincipal();
  const typed = (t, u) => t.linkedBrowser.loadURI(Services.io.newURI(u), {triggeringPrincipal: system});  // no page asked: as the address bar
  const until = async (f, ms = 8000) => { for (let i = 0; i < ms / 100 && !f(); i++) await wait(100); return f(); };
  const inTab = (ctx, u) => main().gBrowser.addTrustedTab(u, {userContextId: ctx, inBackground: true});
  const containersOf = part => wins().flatMap(w => w.gBrowser.tabs.filter(t => url(t).includes(part)).map(t => t.userContextId));
  const closeAll = async part => { for (const w of wins()) for (const t of [...w.gBrowser.tabs]) if (url(t).includes(part) || String(t.label).includes(part)) w.gBrowser.removeTab(t, {skipPermitUnload: true}); await wait(2500); };
"""


def visit(m, ctx, address, wait_for=None):
    """Open `address` in container `ctx`, and wait for it to have loaded."""
    m.js(ISOLATION_JS + """const [ctx, u] = args; const t = inTab(ctx, u); await until(() => url(t) === u, 8000); await wait(300); return 1;""", ctx, address)


def guessed_links(m, space, other):
    """A link from another app that Firefox puts in another space's container: it guesses from
    the visible tabs on the link's site, in every window, and essentials are always visible. So
    another space with more essentials there than you have tabs wins. Its login must not go out,
    with the small window on or off, and the window stays in your space."""
    lh = m.pages.replace("127.0.0.1", "localhost")  # a site no other tab is on
    visit(m, space, f"{lh}/set-cookie?v=yours")
    visit(m, other, f"{lh}/set-cookie?v=guessed")
    m.js(H + """const [there, u] = args, w = main();
      const pins = [0, 1].map(i => w.gBrowser.addTrustedTab(u + i, {userContextId: there, inBackground: true}));
      await wait(1500); for (const p of pins) w.gBrowser.pinTab(p); await wait(2000); return 1;""", other, f"{lh}/r/guess-essential-")
    # Firefox's own setting for this: the dotfiles may turn the guess off, but Tidier must hold without it.
    link = LITTLE + """const [u, guess, part] = args, w = main();
      const PREF = "browser.link.force_default_user_context_id_for_external_opens", was = Services.prefs.getBoolPref(PREF, false);
      Services.prefs.setBoolPref(PREF, !guess);
      const on = await onSpaceTab(), c = w.gBrowser.tabContainer, opened = [], onOpen = e => opened.push(e.target.userContextId);
      c.addEventListener("TabOpen", onOpen);
      external(u);
      await until(() => wins().some(x => x.gBrowser.tabs.some(t => url(t).includes(part))));
      await wait(1500);
      c.removeEventListener("TabOpen", onOpen);
      Services.prefs.setBoolPref(PREF, was);
      const p = popups().find(x => url(x.gBrowser.selectedTab).includes(part));
      const got = {opened, small: p ? p.gBrowser.selectedTab.userContextId : null, here: w.gBrowser.tabs.filter(t => url(t).includes(part)).map(t => t.userContextId),
        space: on.userContextId, window: w.gBrowser.selectedTab.userContextId, popups: popups().length};
      for (const x of popups()) x.close(); await until(() => !popups().length);
      const t = w.gBrowser.tabs.find(t => url(t).includes(part)); if (t) { w.gBrowser.selectedTab = on; w.gBrowser.removeTab(t); }
      await wait(500); return got;"""
    yours, theirs = "login=yours", "login=guessed"

    def sent(part):
        return [x["cookie"] for x in seen(m, part)]
    extension_message(m, {"type": "little:set", "on": True})  # off until you turn it on
    r = m.js(link, f"{lh}/r/guess-small", True, "guess-small")
    check("(Firefox guesses the space with more essentials on the site for a link from another app)", r.get("opened") == [other], str(r))
    check("a link Firefox puts in another space's container: none of that space's login goes out, only yours",
          sent("guess-small") and all(c == yours for c in sent("guess-small")), f"{sent('guess-small')} {r}")
    check("and it opens in a small window in your space, your window staying there", r.get("small") == space and r.get("window") == space and r.get("here") == [], str(r))
    extension_message(m, {"type": "little:set", "on": False})
    r = m.js(link, f"{lh}/r/guess-off", True, "guess-off")
    check("with small windows off, the same: only your login goes out", sent("guess-off") and all(c == yours for c in sent("guess-off")), f"{sent('guess-off')} {r}")
    check("and it opens as a tab in your space, which your window stays in", r.get("here") == [space] and r.get("window") == space and not r.get("popups"), str(r))
    r = m.js(link, f"{lh}/r/guess-none", False, "guess-none")
    check("with the dotfiles' setting Firefox guesses nothing, and the link opens in your space", r.get("opened", [])[:1] == [0] and r.get("here") == [space] and theirs not in sent("guess-none"), f"{sent('guess-none')} {r}")
    m.js(H + """const w = main(); for (const p of w.gBrowser.tabs.filter(t => t.pinned && url(t).includes("guess-essential"))) { w.gBrowser.unpinTab(p); await wait(300); w.gBrowser.removeTab(p); }
      await wait(1200); await removeWhere((x, t) => url(t).includes("localhost") && url(t).includes("set-cookie")); return 1;""")


def alone_isolation(m):
    base = m.pages
    # Tidier stays on one space while this runs; the tabs made here are hidden or not, but they load either way.
    press(m, "1", CTRL)
    time.sleep(1)
    space = m.js(H + "return main().gBrowser.selectedTab.userContextId;")
    other = 2 if space != 2 else 3
    visit(m, space, f"{base}/set-cookie?v=here")
    visit(m, other, f"{base}/set-cookie?v=there")
    here, there = "login=here", "login=there"
    m.js("""const [id] = args; const {ExtensionPermissions} = ChromeUtils.importESModule("resource://gre/modules/ExtensionPermissions.sys.mjs");
      await ExtensionPermissions.remove(id, {permissions: ["webRequest", "webRequestBlocking"], origins: ["<all_urls>"]}, WebExtensionPolicy.getByID(id).extension);
      await new Promise(r => ChromeUtils.importESModule("resource://gre/modules/Timer.sys.mjs").setTimeout(r, 800)); return 1;""", EXT_ID)
    visit(m, space, f"{base}/r/baseline-here")
    check("a cookie set in a space is sent there", [r["cookie"] for r in seen(m, "baseline-here")] == [here], str(seen(m, "baseline-here")))
    visit(m, other, f"{base}/r/baseline-there")
    check("and that space's cookie in another", [r["cookie"] for r in seen(m, "baseline-there")] == [there], str(seen(m, "baseline-there")))

    r = sidebar_page(m, """await wait(300); return {line: !doc.querySelector(".ask-line").hidden, words: doc.querySelector(".ask-line button").textContent};""")
    check("without the permission, one line in the sidebar asks for it", r["line"] and "wrong space" in r["words"], str(r))
    r = ext_page(m, "/settings/settings.html", """await wait(800); return !doc.getElementById("allow-isolation").hidden;""")
    check("and the settings page can ask for it", r is True, str(r))

    # Without the permission: this is what the permission is for, and shows the checks below can fail.
    r = m.js(ISOLATION_JS + """main().gBrowser.addTrustedTab(args[0], {inBackground: true}); await until(() => containersOf("old-path").some(c => c), 8000); await wait(500); return containersOf("old-path");""", f"{base}/r/old-path")
    check("without the permission, a link's first request goes out with no login, and the tab then lands in the space", any(not x["cookie"] for x in seen(m, "old-path")) and r and all(r), f"{r} {seen(m, 'old-path')}")

    m.js(GIVE_PERMISSIONS, EXT_ID, ["webRequest", "webRequestBlocking"], ["<all_urls>"])
    extension_message(m, {"type": "settings:rules", "rules": [{"url": "rule-there", "space": f"firefox-container-{other}"}]})
    r = sidebar_page(m, """await wait(500); return doc.querySelector(".ask-line").hidden;""")
    check("given, the line is gone", r is True, str(r))

    def only(part, cookie, what):
        got = seen(m, part)
        check(what, len(got) >= 1 and all(x["cookie"] == cookie for x in got), f"{part}: {got}")

    # A rule, from a tab in another space, the way you type an address.
    r = m.js(ISOLATION_JS + """const t = inTab(args[1], "about:blank"); await wait(400); typed(t, args[0]); await until(() => containersOf("rule-there-typed").length, 8000); await wait(500); return containersOf("rule-there-typed");""", f"{base}/r/rule-there-typed", space)
    only("rule-there-typed", there, "by a rule: the server saw only the rule's space's cookie, from the first request on")
    check("by a rule: the tab is in the rule's space, once", r == [other], str(r))

    # A link from another app, with no container.
    r = m.js(ISOLATION_JS + """main().gBrowser.addTrustedTab(args[0], {inBackground: true}); await until(() => containersOf("rule-there-link").length, 8000); await wait(500); return containersOf("rule-there-link");""", f"{base}/r/rule-there-link")
    only("rule-there-link", there, "a link with no container, by a rule: the same")
    check("a link with no container, by a rule: it is in the rule's space, once", r == [other], str(r))
    r = m.js(ISOLATION_JS + """main().gBrowser.addTrustedTab(args[0], {inBackground: true}); await until(() => containersOf("no-rule-link").length, 8000); await wait(500); return containersOf("no-rule-link");""", f"{base}/r/no-rule-link")
    only("no-rule-link", here, "a link with no container: every request carries the active space's cookie, never none")
    check("a link with no container: it is in the active space, once", r == [space], str(r))
    guessed_links(m, space, other)

    # A new tab: ⌘T, then an address.
    r = m.js(ISOLATION_JS + """const w = main(); const t = w.gBrowser.addTrustedTab("about:newtab"); w.gBrowser.selectedTab = t; await wait(1500);
      const s = w.gBrowser.selectedTab, ctx = s.userContextId; typed(s, args[0]); await until(() => containersOf("new-tab-typed").length, 8000); await wait(500); return {ctx, got: containersOf("new-tab-typed")};""", f"{base}/r/new-tab-typed")
    only("new-tab-typed", here, "a new tab, then an address: the same")
    check("a new tab is in the active space", r["ctx"] == space and r["got"] == [space], str(r))

    # What does not count: a link followed inside a page, and a redirect under way.
    # (Encoded: the rule is text to find in the address, and must not match the page before it.)
    link = f"{base}/go?to={base}/r/rule%2Dthere-by-link"
    r = m.js(ISOLATION_JS + """const t = inTab(args[2], args[1]); await until(() => url(t) === args[1], 8000); await wait(300); typed(t, args[0]);
      await until(() => containersOf("rule-there-by-link").length, 8000); await wait(500); return containersOf("rule-there-by-link");""", link, f"{base}/r/start-a", space)
    only("rule-there-by-link", here, "a link followed inside a page stays in the space, with its cookie")
    check("a link followed inside a page does not move the tab", r == [space], str(r))
    hop = f"{base}/redirect?to={base}/r/rule%2Dthere-by-redirect"
    r = m.js(ISOLATION_JS + """const t = inTab(args[2], args[1]); await until(() => url(t) === args[1], 8000); await wait(300); typed(t, args[0]);
      await until(() => containersOf("rule-there-by-redirect").length, 8000); await wait(800); return containersOf("rule-there-by-redirect");""", hop, f"{base}/r/start-b", space)
    only("rule-there-by-redirect", here, "a redirect under way stays in the space, with its cookie")
    check("a redirect under way does not move the tab", r == [space], str(r))

    # What a page can read.
    r = m.js(ISOLATION_JS + """const [u, a, b] = args; const one = inTab(a, u), two = inTab(b, u); await until(() => /cookie=/.test(one.label) && /cookie=/.test(two.label), 8000);
      return [one.label, two.label];""", f"{base}/see-cookie", space, other)
    check("what a page can read of its cookies is its own space's", r == ["cookie=login=here", "cookie=login=there"], str(r))
    extension_message(m, {"type": "settings:rules", "rules": []})

    # A space's user agent and proxy.
    third = next(c for c in (1, 2, 3) if c not in (space, other))
    more = """
      const id = args[0], card = () => doc.querySelector(`#spaces .space-card[data-space="${id}"]`);
      await wait(800);
      if (!card().querySelector(".space-more")) { card().querySelector(".more").click(); await wait(400); }
      const set = (el, value) => { el.value = value; el.dispatchEvent(new page.Event("input", {bubbles: true})); };
      // Saved, or refused: the page says which, in a line that is new each time.
      const saved = async () => { const old = card().querySelector(".fact"); card().querySelector(".save").click();
        for (let i = 0; i < 80 && card().querySelector(".fact") === old; i++) await wait(100); await wait(100); return card().querySelector(".fact")?.textContent; };
    """
    r = ext_page(m, "/settings/settings.html", more + """
      const out = {saveHidden: card().querySelector(".save").hidden, hostHidden: card().querySelector(".host").hidden};
      set(card().querySelector("select"), "http");
      out.hostShown = !card().querySelector(".host").hidden;
      set(card().querySelector(".host"), "127.0.0.1");
      set(card().querySelector(".port"), "3128");
      out.refused = await saved();
      return out;""", f"firefox-container-{third}")
    check("a space's More has a proxy, with Save only once something changed", r.get("saveHidden") is True and r.get("hostHidden") is True and r.get("hostShown") is True, str(r))
    check("without the permission for a proxy it says so, and nothing changes", "did not give" in (r.get("refused") or ""), str(r))
    m.js(GIVE_PERMISSIONS, EXT_ID, ["proxy"], ["<all_urls>"])
    r = ext_page(m, "/settings/settings.html", more + """
      const out = {};
      set(card().querySelector("select"), "http");
      card().querySelector(".save").click();
      const problem = () => card().querySelector(".field-problem:not([hidden])");
      for (let i = 0; i < 80 && !problem(); i++) await wait(100);
      // Said beside the proxy, with what was typed kept to be put right.
      out.incomplete = problem()?.textContent; out.typed = card().querySelector("select").value;
      set(card().querySelector("select"), "");
      set(card().querySelector("input[placeholder*=own]"), "Smoke agent");
      out.saved = await saved();
      out.kept = card().querySelector("input[placeholder*=own]").value;
      card().querySelector(".more").click();
      return out;""", f"firefox-container-{third}")
    check("a proxy that is not complete is said beside it, keeps what was typed, and is not used", "Not saved" in (r.get("incomplete") or "") and r.get("typed") == "http", str(r))
    check("a user agent set in a space's More is kept", r.get("saved") == "Saved." and r.get("kept") == "Smoke agent", str(r))
    time.sleep(1)
    visit(m, third, f"{base}/r/agent-own")
    visit(m, space, f"{base}/r/agent-other")
    own, others = seen(m, "agent-own"), seen(m, "agent-other")
    check("a space's user agent reaches the server", [x["agent"] for x in own] == ["Smoke agent"], str(own))
    check("other spaces' requests are untouched", others and "Smoke agent" not in others[0]["agent"] and "Firefox" in others[0]["agent"], str(others))
    server_port = base.rsplit(":", 1)[1]
    r = extension_message(m, {"type": "isolation:network", "id": f"firefox-container-{third}", "proxy": {"type": "http", "host": "127.0.0.1", "port": server_port}})
    check("a proxy is taken as given", r and r.get("proxy", {}).get("port") == int(server_port), str(r))
    time.sleep(1)
    m.js(ISOLATION_JS + """inTab(args[0], "http://proxied.invalid/r/through-proxy"); inTab(args[1], "http://proxied.invalid/r/past-proxy"); await wait(3000); return 1;""", third, space)
    got = seen(m, "through-proxy")
    check("a space's proxy carries its requests", got and all(x["proxied"] for x in got), str(got))
    check("other spaces' requests do not go through it", not seen(m, "past-proxy"), str(seen(m, "past-proxy")))
    # A proxy that does not answer (README says so, and this shows if Firefox changes it).
    # The test's own server is on this machine, which Firefox otherwise never sends through
    # a proxy: that is what the setting is for.
    extension_message(m, {"type": "isolation:network", "id": f"firefox-container-{third}", "proxy": {"type": "http", "host": "127.0.0.1", "port": 1}})
    time.sleep(1)
    direct = m.js(ISOLATION_JS + """Services.prefs.setBoolPref("network.proxy.allow_hijacking_localhost", true); inTab(args[0], args[1]); await wait(5000);
      Services.prefs.clearUserPref("network.proxy.allow_hijacking_localhost"); return Services.prefs.getBoolPref("network.proxy.failover_direct", null);""", third, f"{base}/r/dead-proxy")
    check("a proxy that does not answer means no page, not going directly", not seen(m, "dead-proxy"), f"failover_direct: {direct}, {seen(m, 'dead-proxy')}")
    r = extension_message(m, {"type": "isolation:network", "id": f"firefox-container-{third}"})
    time.sleep(1)
    visit(m, third, f"{base}/r/agent-unset")
    check("unset again, a space's requests are as they were", "Smoke agent" not in seen(m, "agent-unset")[0]["agent"] and r == {}, str(r))

    # Signing out: one site in one space, and everything in a space.
    # With the tab menu's table, by its item, on the real sidebar; without it, by the message it sends.
    r = sidebar_page(m, """
      await wait(400);
      const row = plainTabs().find(x => x.querySelector(".title").textContent === "Recorded");
      if (!row) return {row: false};
      const box = row.getBoundingClientRect();
      row.dispatchEvent(new page.MouseEvent("contextmenu", {bubbles: true, cancelable: true, clientX: box.left + 5, clientY: box.top + 5}));
      await wait(500);
      const menu = doc.getElementById("menu"), items = menu.hidden ? [] : [...menu.querySelectorAll(".item")];
      const labels = items.map(i => i.textContent);
      const item = items.find(i => i.textContent === "Clear this site's cookies in this space");
      if (item) { item.click(); await wait(800); }
      return {row: true, labels, clicked: !!item};""")
    if r.get("labels"):
        check("the tab menu has Clear this site's cookies and Open a copy in space", r.get("clicked") and "Open a copy in space" in r["labels"], str(r))
    else:
        tab = m.js(ISOLATION_JS + """const w = main(), {ExtensionParent} = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
          const t = w.gBrowser.tabs.find(x => url(x).includes("baseline-here")); return ExtensionParent.apiManager.global.tabTracker.getId(t);""")
        extension_message(m, {"type": "isolation:clearCookies", "tabId": tab, "windowId": None})
    visit(m, space, f"{base}/r/after-clear")
    visit(m, other, f"{base}/r/after-clear-other")
    check("clearing a site's cookies in a space takes them there", [x["cookie"] for x in seen(m, "after-clear") if "other" not in x["path"]] == [""], str(seen(m, "after-clear")))
    check("and leaves another space's alone", [x["cookie"] for x in seen(m, "after-clear-other")] == [there], str(seen(m, "after-clear-other")))
    m.js(GIVE_PERMISSIONS, EXT_ID, ["browsingData"], [])
    visit(m, third, f"{base}/set-cookie?v=third")
    r = ext_page(m, "/settings/settings.html", """
      const id = args[0], card = () => doc.querySelector(`#spaces .space-card[data-space="${id}"]`);
      await wait(800);
      if (!card().querySelector(".space-more")) { card().querySelector(".more").click(); await wait(400); }
      card().querySelector(".sign-out").click();
      await wait(300);
      const out = {question: card().querySelector(".question").textContent};
      card().querySelector(".danger + button").click();
      await wait(300);
      out.kept = !card().querySelector(".question");
      card().querySelector(".sign-out").click();
      await wait(300);
      card().querySelector(".danger").click();
      await wait(1200);
      out.fact = card().querySelector(".fact")?.textContent;
      card().querySelector(".more").click();
      return out;""", f"firefox-container-{other}")
    check("signing out asks first, and Keep keeps", "for good" in r.get("question", "") and r.get("kept") is True, str(r))
    visit(m, other, f"{base}/r/signed-out")
    check("signing out of a space takes its logins", [x["cookie"] for x in seen(m, "signed-out")] == [""] and "Signed out" in (r.get("fact") or ""), f"{r} {seen(m, 'signed-out')}")
    visit(m, third, f"{base}/r/not-signed-out")
    check("and another space's stay", [x["cookie"] for x in seen(m, "not-signed-out")] == ["login=third"], str(seen(m, "not-signed-out")))
    m.js(ISOLATION_JS + """await closeAll("127.0.0.1"); return 1;""")

    # New, edited and deleted, with clicks on the real settings page.
    r = ext_page(m, "/settings/settings.html", """
      await wait(800);
      const cards = () => [...doc.querySelectorAll("#spaces .space-card")];
      const before = cards().length;
      doc.getElementById("new-space").click();
      await wait(1000);
      const card = cards().at(-1), id = card.dataset.space;
      const out = {before, after: cards().length, focus: doc.activeElement === card.querySelector("input"), name: card.querySelector("input").value};
      const name = card.querySelector("input");
      name.value = "Smoke space";
      name.dispatchEvent(new page.Event("change", {bubbles: true}));
      await wait(500);
      const now = () => doc.querySelector(`#spaces .space-card[data-space="${id}"]`);
      now().querySelector(".swatch[data-color=red], .swatch[data-color=orange]").click();
      await wait(600);
      now().querySelector(".icon-choice[data-icon=tree]").click();
      await wait(600);
      const c = await page.browser.contextualIdentities.get(id);
      out.saved = {name: c.name, color: c.color, icon: c.icon};
      out.shown = {swatch: now().querySelector(".swatch.chosen")?.dataset.color, icon: now().querySelector(".icon-choice.chosen")?.dataset.icon};
      out.id = id;
      return out;""")
    check("New space on the settings page makes one, ready to name, with a look of its own", r.get("after") == r.get("before", 0) + 1 and r.get("focus") and r.get("name") == "New space", str(r))
    check("its name, colour and icon are changed there", r["saved"]["name"] == "Smoke space" and r["saved"]["color"] in ("red", "orange") and r["saved"]["icon"] == "tree" and r["shown"] == {"swatch": r["saved"]["color"], "icon": "tree"}, str(r))
    new_id = r["id"]
    r = sidebar_page(m, """
      const dot = doc.querySelector(`#spaces .space[data-space="${args[0]}"]`);
      if (!dot) return {dot: false};
      const color = dot.style.getPropertyValue("--color"), tint0 = getComputedStyle(doc.documentElement).backgroundColor;
      dot.click();
      await wait(1200);
      const tint1 = getComputedStyle(doc.documentElement).backgroundColor;
      return {dot: true, color, tint0, tint1, name: doc.getElementById("space-name").textContent};""", new_id)
    check("the bar has the new space, in its colour, and its name", r.get("dot") and r.get("color") and r.get("name") == "Smoke space", str(r))
    check("the window's tint in the sidebar follows a new space with no line in tidier.css", r.get("tint0") != r.get("tint1"), str(r))
    time.sleep(1)
    number = int(new_id.rsplit("-", 1)[1])
    visit(m, number, f"{base}/set-cookie?v=doomed")
    r = ext_page(m, "/settings/settings.html", """
      const id = args[0], now = () => doc.querySelector(`#spaces .space-card[data-space="${id}"]`);
      now().querySelector(".delete").click();
      await wait(300);
      const question = now().querySelector(".question").textContent;
      now().querySelector(".danger + button").click();
      await wait(300);
      const kept = !!now() && !now().querySelector(".question");
      now().querySelector(".delete").click();
      await wait(300);
      now().querySelector(".danger").click();
      await wait(2500);
      const left = (await page.browser.contextualIdentities.query({})).some(c => c.cookieStoreId === id);
      return {question, kept, left, card: !!now()};""", new_id)
    check("deleting a space asks, naming what goes, and Keep keeps it", "all its logins" in r.get("question", "").lower() and r.get("kept"), str(r))
    check("and then it is gone", r.get("left") is False and r.get("card") is False, str(r))
    r = m.js(H + """return Services.cookies.cookies.filter(c => c.originAttributes.userContextId === args[0]).length;""", number)
    check("and its logins with it", r == 0, str(r))
    press(m, "1", CTRL)
    time.sleep(1.5)
    r = m.js(H + """return {selected: main().gBrowser.selectedTab.userContextId, stray: wins().flatMap(w => w.gBrowser.tabs.filter(t => t.userContextId > 4).map(t => t.userContextId))};""")
    check("you are not left in it, and no tab of it is", r["selected"] == space and not r["stray"], str(r))

    # A copy in another space, and a folder moved to one.
    visit(m, space, f"{base}/r/copy-me")
    visit(m, space, f"{base}/r/in-folder")
    visit(m, space, f"{base}/unsaved")
    time.sleep(2.5)  # registered as tabs of the record
    ids = m.js(ISOLATION_JS + """const {ExtensionParent} = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs"), id = t => ExtensionParent.apiManager.global.tabTracker.getId(t);
      const of = part => id(main().gBrowser.tabs.find(x => url(x).includes(part))); return {copy: of("copy-me"), folder: of("in-folder"), unsaved: of("/unsaved")};""")
    copies = extension_message(m, {"type": "isolation:copy", "tabIds": [ids["copy"]], "space": f"firefox-container-{other}", "windowId": None})
    time.sleep(1.5)
    r = m.js(ISOLATION_JS + """return containersOf("copy-me").sort();""")
    check("a copy in another space leaves the original", copies == 1 and r == sorted([space, other]), f"{copies} {r}")
    r = sidebar_page(m, """
      send({type: "newFolder", space: "firefox-container-" + args[0], name: "Going over"});
      await wait(1000);
      send({type: "moveTab", tabId: args[1], folder: [...doc.querySelectorAll("#tabs .folder")].find(f => f.querySelector(".head .title").textContent === "Going over").dataset.key, before: null});
      send({type: "moveTab", tabId: args[2], folder: [...doc.querySelectorAll("#tabs .folder")].find(f => f.querySelector(".head .title").textContent === "Going over").dataset.key, before: null});
      await wait(1500);
      return [...doc.querySelectorAll("#tabs .folder")].find(f => f.querySelector(".head .title").textContent === "Going over").dataset.key;""", space, ids["folder"], ids["unsaved"])
    key = r
    moved = extension_message(m, {"type": "isolation:moveFolder", "key": key, "space": f"firefox-container-{other}", "windowId": None})
    time.sleep(1.5)
    r = m.js(ISOLATION_JS + """const all = (await storage(args[0], ["syncedTabs"])).syncedTabs, folder = args[1];
      const inFolder = Object.entries(all).filter(([k, e]) => e.parentKey === folder);
      return {folder: all[folder].cookieStoreId, inFolder: inFolder.map(([k, e]) => [new URL(e.url).pathname, e.cookieStoreId]), unsaved: containersOf("/unsaved"), ghost: inFolder.map(([k]) => wins().flatMap(w => w.gBrowser.tabs.filter(t => value(w, t, "syncKey") === k).map(t => [t.userContextId, url(t).includes("ghost.html") || !t.linkedPanel])))};""", EXT_ID, key)
    # Its tab arrives as it was (safemoves.js): loaded, so loaded in the window that had its
    # page, and a placeholder in every other window.
    check("a folder moved to another space goes there, its tab with it, as it was", moved == {"moved": 1, "stayed": 1} and r["folder"] == f"firefox-container-{other}" and [x[1] for x in r["inFolder"]] == [f"firefox-container-{other}"]
          and r["ghost"][0] and r["ghost"][0].count([other, False]) == 1 and all(x in ([other, True], [other, False]) for x in r["ghost"][0]), f"{moved} {r}")
    check("a page holding unsaved input stays, where it was", r["unsaved"] == [space], str(r))
    m.js(ISOLATION_JS + """await closeAll("127.0.0.1"); return 1;""")
    extension_message(m, {"type": "flush"})
    sidebar_page(m, """send({type: "deleteFolder", key: args[0]}); await wait(800); return 1;""", key)

    # New space in the space's menu, where there is one: its name is then ready to change.
    r = sidebar_page(m, """
      const dot = doc.querySelector("#spaces .space"), box = dot.getBoundingClientRect();
      dot.dispatchEvent(new page.MouseEvent("contextmenu", {bubbles: true, cancelable: true, clientX: box.left + 5, clientY: box.top + 5}));
      await wait(300);
      const menu = doc.getElementById("menu"), item = menu.hidden ? null : [...menu.querySelectorAll(".item")].find(i => i.textContent === "New space");
      if (!item) return {item: false};
      const before = spaces().map(s => s.id);
      item.click();
      await wait(1500);
      const name = doc.querySelector(".space-box");
      const out = {item: true, made: spaces().map(s => s.id).filter(id => !before.includes(id)), box: name?.value};
      name?.dispatchEvent(new page.KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
      return out;""")
    if r.get("item"):
        check("New space in a space's menu makes one, with its name ready to change", len(r["made"]) == 1 and r.get("box") == "New space", str(r))
        m.js(H + """const {ContextualIdentityService: c} = ChromeUtils.importESModule("moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs"); c.remove(args[0]); await wait(1000); return 1;""", int(r["made"][0].rsplit("-", 1)[1]))

    # The same from the folder's menu, and a tab dropped on the bar for a new space.
    r = sidebar_page(m, """
      send({type: "newFolder", space: spaces().find(s => s.active).id, name: "By menu"});
      await wait(1000);
      const head = () => [...doc.querySelectorAll("#tabs .folder .head")].find(h => h.querySelector(".title").textContent === "By menu");
      const box = head().getBoundingClientRect();
      head().dispatchEvent(new page.MouseEvent("contextmenu", {bubbles: true, cancelable: true, clientX: box.left + 5, clientY: box.top + 5}));
      await wait(200);
      const items = [...doc.querySelectorAll("#menu .item")];
      const out = {labels: items.map(i => i.textContent)};
      const item = items.find(i => i.textContent.startsWith("Move to space"));
      item.click();
      await wait(100);
      // A list in place, where the menu can do that.
      const inner = doc.getElementById("menu").hidden ? [] : [...doc.querySelectorAll("#menu .item:not(.back)")];
      if (inner.length) inner[0].click();
      await wait(1500);
      out.left = !head();
      return out;""")
    check("a folder's menu moves it to another space", r.get("left") is True and sum(x.startswith("Move to space") for x in r["labels"]) >= 1, str(r))
    before = m.js(H + """const {ContextualIdentityService: c} = ChromeUtils.importESModule("moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs"); return c.getPublicIdentities().length;""")
    visit(m, space, f"{base}/r/dropped")
    time.sleep(2.5)
    r = sidebar_page(m, """
      // By its address: every page of the test server's /r/ is called "Recorded", and a group before can leave one.
      let row = null;
      for (const x of plainTabs()) if ((await page.browser.tabs.get(Number(x.dataset.tab))).url.includes("/r/dropped")) { row = x; break; }
      const spot = doc.querySelector(".new-space");
      const out = {row: !!row, hiddenBefore: spot.hidden};
      if (!row) return out;
      const box = row.getBoundingClientRect(), data = new page.DataTransfer();
      const at = {bubbles: true, cancelable: true, clientX: box.left + 5, clientY: box.top + 1, dataTransfer: data};
      row.dispatchEvent(new page.DragEvent("dragstart", at));
      out.shownInDrag = !spot.hidden;
      spot.dispatchEvent(new page.DragEvent("dragover", at));
      spot.dispatchEvent(new page.DragEvent("drop", at));
      row.dispatchEvent(new page.DragEvent("dragend", at));
      out.hiddenAfter = spot.hidden;
      await wait(2500);
      return out;""")
    check("while a tab is dragged there is a place on the bar for a new space, and only then", r.get("hiddenBefore") is True and r.get("shownInDrag") is True and r.get("hiddenAfter") is True, str(r))
    r = m.js(ISOLATION_JS + """const {ContextualIdentityService: c} = ChromeUtils.importESModule("moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs");
      return {count: c.getPublicIdentities().length, where: containersOf("/r/dropped"), newest: Math.max(...c.getPublicIdentities().map(i => i.userContextId))};""")
    check("a tab dropped there is in a new space of its own, and you stay", r["count"] == before + 1 and r["where"] == [r["newest"]], f"{before} {r}")
    m.js(ISOLATION_JS + """await closeAll("/r/dropped"); const {ContextualIdentityService: c} = ChromeUtils.importESModule("moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs"); c.remove(args[0]); await wait(1000); return 1;""", r["newest"])

    # A container removed while Tidier runs stays removed; one that vanishes while Tidier is off comes back.
    made = m.js(H + """const {ContextualIdentityService: c} = ChromeUtils.importESModule("moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs");
      const one = c.create("Removed by hand", "tree", "red"), two = c.create("Comes back", "cart", "purple"); await wait(1000);
      return [one.userContextId, two.userContextId];""")
    gone_id, back_id = [f"firefox-container-{x}" for x in made]
    sidebar_page(m, """send({type: "newFolder", space: args[0], name: "Mine"}); send({type: "newFolder", space: args[1], name: "Theirs"}); await wait(800); return 1;""", gone_id, back_id)
    extension_message(m, {"type": "settings:rules", "rules": [{"url": "vanished-rule", "space": back_id}]})
    extension_message(m, {"type": "flush"})
    m.js(H + """const {ContextualIdentityService: c} = ChromeUtils.importESModule("moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs");
      c.remove(args[0]); await wait(1000); return 1;""", made[0])
    extension_message(m, {"type": "flush"})
    # Firefox's own file lost, seen by a Tidier that was not running to see it.
    r = m.js(H + """const {AddonManager} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
      const {ContextualIdentityService: c} = ChromeUtils.importESModule("moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs");
      const addon = await AddonManager.getAddonByID(args[0]);
      await addon.disable(); await wait(1000);
      c.remove(args[1]); await wait(500);
      await addon.enable(); await wait(8000);
      const names = c.getPublicIdentities().map(i => c.getUserContextLabel(i.userContextId));
      const data = await storage(args[0], ["rules", "syncedTabs"]);
      return {names, rule: data.rules[0], folder: Object.values(data.syncedTabs).filter(e => e.own && (e.name === "Theirs" || e.name === "Mine")).map(e => [e.name, e.cookieStoreId])};""", EXT_ID, made[1])
    check("a container vanished while Tidier was not looking comes back, with its name", "Comes back" in r["names"], str(r))
    check("what pointed at it follows it", r["rule"]["space"] != back_id and r["folder"] == [["Theirs", r["rule"]["space"]]], str(r))
    check("one removed while Tidier ran stays removed", "Removed by hand" not in r["names"], str(r))
    r = ext_page(m, "/settings/settings.html", """await wait(800); return doc.getElementById("notices").textContent;""")
    check("Tidier says so", "Comes back had gone from Firefox" in str(r), str(r))
    extension_message(m, {"type": "settings:rules", "rules": []})
    extension_message(m, {"type": "isolation:seen"})
    m.js(H + """const {ContextualIdentityService: c} = ChromeUtils.importESModule("moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs");
      for (const i of c.getPublicIdentities()) if (c.getUserContextLabel(i.userContextId) === "Comes back") c.remove(i.userContextId);
      await wait(1000); return 1;""")
    press(m, "1", CTRL)
    time.sleep(1)


def alone_requests(m):
    # Nothing is lost, doubled or held up when a request is stopped: the cases are in
    # tests/isolation-requests.test.mjs, and here Firefox itself asks.
    base = m.pages
    m.js(GIVE_PERMISSIONS, EXT_ID, ["webRequest", "webRequestBlocking"], ["<all_urls>"])
    press(m, "1", CTRL)
    time.sleep(1)
    space = m.js(H + "return main().gBrowser.selectedTab.userContextId;")
    other, third = [c for c in (1, 2, 3) if c != space][:2]
    here, there = "login=here", "login=there"
    visit(m, space, f"{base}/set-cookie?v=here")
    visit(m, other, f"{base}/set-cookie?v=there")

    def rules(*pairs):
        extension_message(m, {"type": "settings:rules", "rules": [{"url": u, "space": f"firefox-container-{c}"} for u, c in pairs]})

    def only(part, cookie, what):
        got = seen(m, part)
        check(what, len(got) >= 1 and all(x["cookie"] == cookie for x in got), f"{part}: {got}")

    # A regular expression that takes for ever on Firefox's own engine, on every navigation.
    rules(("/(a+)+$/", other), ("/(x|x)*y/", other))
    evil = f"{base}/r/catastrophe-{'a' * 60}!"
    r = m.js(ISOLATION_JS + """const t = inTab(args[1], "about:blank"); await wait(400); const t0 = Date.now(); typed(t, args[0]);
      const ok = await until(() => url(t) === args[0], 15000); return {ok, ms: Date.now() - t0};""", evil, space)
    check(f"a catastrophic regular expression in a rule holds up no page ({r['ms']} ms)", r["ok"], str(r))
    m.js(ISOLATION_JS + """await closeAll("catastrophe"); return 1;""")

    # A rule for a space that is gone: Firefox refuses to open anything in it.
    rules(("dead-rule", 99))
    r = m.js(ISOLATION_JS + """main().gBrowser.addTrustedTab(args[0], {inBackground: true}); await until(() => containersOf("dead-rule").length); await wait(500); return containersOf("dead-rule");""", f"{base}/r/dead-rule")
    check("a link a rule sends to a removed space opens in the active space all the same", r == [space], str(r))
    only("dead-rule", here, "and goes out with that space's cookie")
    m.js(ISOLATION_JS + """await closeAll("settings.html"); return 1;""")
    extension_message(m, {"type": "settings:rules", "rules": [{"url": "dead-rule", "space": "firefox-container-99"}, {"url": "/(a)\\1/", "space": f"firefox-container-{other}"}, {"url": "/^https?:\\/\\/(www\\.)?x/", "space": f"firefox-container-{other}"}]})
    r = ext_page(m, "/settings/settings.html", """await wait(800); return [...doc.querySelectorAll("#rules .line")].map(l => ({space: l.querySelector("select").selectedOptions[0].textContent, why: l.querySelector(".rule-problem").hidden ? "" : l.querySelector(".rule-problem").textContent}));""")
    check("the settings page says a rule's space is gone, and doesn't pick another", "gone" in r[0]["space"] and "gone" in r[0]["why"], str(r))
    check("and why an expression can't be used, and nothing about one that can", "back-references" in r[1]["why"] and r[2]["why"] == "", str(r))
    m.js(ISOLATION_JS + """await closeAll("settings.html"); return 1;""")

    # An address typed in a saved tab, selected, in a folder: the tab stays as it was.
    rules()
    visit(m, space, f"{base}/r/saved-one")
    # Registered as a tab of the record, in every window: waited for, since a fixed pause was
    # too short once in the whole chain, and the tab was then moved before Tidier knew it.
    m.js(ISOLATION_JS + """const k = () => { const t = main().gBrowser.tabs.find(x => url(x).includes("saved-one")); return t && key(main(), t); };
      await until(() => k() && wins().every(w => w.gBrowser.tabs.some(x => key(w, x) === k())), 10000); await wait(300); return 1;""")
    tab = m.js(ISOLATION_JS + """const {ExtensionParent} = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs");
      return ExtensionParent.apiManager.global.tabTracker.getId(main().gBrowser.tabs.find(x => url(x).includes("saved-one")));""")
    folder = sidebar_page(m, """
      send({type: "newFolder", space: "firefox-container-" + args[0], name: "Kept"});
      await wait(1000);
      const key = [...doc.querySelectorAll("#tabs .folder")].find(f => f.querySelector(".head .title").textContent === "Kept").dataset.key;
      send({type: "moveTab", tabId: args[1], folder: key, before: null});
      await wait(1000);
      return key;""", space, tab)
    rules(("rule-typed", other))
    r = m.js(ISOLATION_JS + """const w = main(), t = w.gBrowser.tabs.find(x => url(x).includes("saved-one"));
      w.gBrowser.selectedTab = t; await wait(800);
      typed(t, args[0]); await until(() => containersOf("rule-typed").length); await wait(1500);
      const n = wins().flatMap(x => x.gBrowser.tabs).find(x => url(x).includes("rule-typed"));
      const all = (await storage(args[1], ["syncedTabs"])).syncedTabs, entry = all[JSON.parse(key(w, t) || "null")] ?? {};
      return {shows: url(t), kept: t.isConnected, ctx: t.userContextId, new: n.userContextId, selected: w.gBrowser.selectedTab === n,
              first: w.gBrowser.tabs.find(x => !x.pinned && x.userContextId === n.userContextId && !all[JSON.parse(key(w, x) || "null")]?.parentKey) === n,
              before: url(w.gBrowser.tabs.find(x => !x.pinned && x.userContextId === n.userContextId && !all[JSON.parse(key(w, x) || "null")]?.parentKey) ?? n).slice(-40), parent: entry.parentKey, saved: entry.saved?.url};""", f"{base}/r/rule-typed", EXT_ID)
    check("an address typed in a saved tab that a rule sends elsewhere: the saved tab stays as it was", r["kept"] and "saved-one" in r["shows"] and r["ctx"] == space and r["parent"] == folder and "saved-one" in (r["saved"] or ""), str(r))
    check("and the address opens selected, in the rule's space, where new tabs go", r["new"] == other and r["selected"] and r["first"], str(r))
    only("rule-typed", there, "and goes out with that space's cookie, from the first request on")
    press(m, "1", CTRL)
    time.sleep(1)

    # A placeholder whose address a rule sends elsewhere opens where it is: it is yours.
    rules()
    r = m.js(ISOLATION_JS + """const w = main(), t = w.gBrowser.tabs.find(x => url(x).includes("saved-one")), k = key(w, t);
      w.gBrowser.removeTab(t, {skipPermitUnload: true}); await wait(2500);
      return {k, placeholder: url(w.gBrowser.tabs.find(x => key(w, x) === k))};""")
    check("(a saved tab closed is unloaded)", "ghost.html" in r["placeholder"], str(r))
    k = r["k"]
    rules(("saved-one", other))
    r = m.js(ISOLATION_JS + """const w = main(), k = args[0], t = w.gBrowser.tabs.find(x => key(w, x) === k);
      w.gBrowser.selectedTab = t; await until(() => containersOf("saved-one").length, 5000); await wait(1000);
      const entry = (await storage(args[1], ["syncedTabs"])).syncedTabs[JSON.parse(k)];
      return {where: containersOf("saved-one"), same: w.gBrowser.tabs.filter(x => key(w, x) === k).length, parent: entry.parentKey};""", k, EXT_ID)
    check("a saved tab selected opens where it is, whatever a rule says about its address", r["where"] == [space] and r["same"] == 1 and r["parent"] == folder, str(r))
    sidebar_page(m, """send({type: "deleteFolder", key: args[0]}); await wait(800); return 1;""", folder)
    m.js(ISOLATION_JS + """await closeAll("rule-typed"); await closeAll("saved-one"); return 1;""")

    # An essential stays one, wherever a rule says an address belongs.
    rules(("rule-essential", other))
    r = m.js(ISOLATION_JS + """const w = main(), t = w.gBrowser.tabs.find(x => x.pinned && x.userContextId === args[1]);
      typed(t, args[0]); await until(() => url(t) === args[0]); await wait(800);
      return {where: containersOf("rule-essential"), pinned: t.pinned, ctx: t.userContextId, connected: t.isConnected};""", f"{base}/r/rule-essential", space)
    check("an address typed in an essential stays there, and it stays an essential", r["where"] == [space] and r["pinned"] and r["connected"], str(r))
    m.js(ISOLATION_JS + """await closeAll("rule-essential"); return 1;""")

    # Back through a sign-in it passed through: Firefox asks with no page's name on it, as for a typed address.
    rules(("rule-back", other))
    hop = f"{base}/redirect?to={base}/no-bfcache%3Frule%2Dback"
    r = m.js(ISOLATION_JS + """const t = inTab(args[2], "about:blank"); await wait(400); typed(t, args[0]);
      Services.prefs.setIntPref("browser.sessionhistory.max_total_viewers", 0); // no back-forward cache: Firefox must ask
      await until(() => url(t).includes("rule-back")); await wait(400);
      typed(t, args[1]); await until(() => url(t) === args[1]); await wait(400);
      t.linkedBrowser.goBack(); await until(() => url(t).includes("rule-back")); await wait(1000);
      Services.prefs.clearUserPref("browser.sessionhistory.max_total_viewers");
      return {shows: url(t), where: containersOf("rule-back")};""", hop, f"{base}/no-bfcache?after", space)
    check("going back through an address a rule has does not move the tab it passed through", "rule-back" in r["shows"] and r["where"] == [space], str(r))
    check("(Firefox did ask again)", len(seen(m, "rule-back")) >= 2, str(seen(m, "rule-back")))
    m.js(ISOLATION_JS + """await closeAll("no-bfcache"); return 1;""")

    # The same address, by hand, twice.
    rules()
    for _ in range(2):
        visit(m, space, f"{base}/r/copy-twice")
    time.sleep(2.5)
    ids = m.js(ISOLATION_JS + """const {ExtensionParent} = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs"), id = t => ExtensionParent.apiManager.global.tabTracker.getId(t);
      return main().gBrowser.tabs.filter(x => url(x).includes("copy-twice")).map(id);""")
    rules(("copy-twice", other))
    copies = extension_message(m, {"type": "isolation:copy", "tabIds": ids, "space": f"firefox-container-{third}", "windowId": None})
    time.sleep(2)
    r = m.js(ISOLATION_JS + """return containersOf("copy-twice").sort();""")
    check("two tabs with the same address copied by hand are both where you put them, whatever a rule says", copies == 2 and r == sorted([space, space, third, third]), f"{copies} {r}")
    m.js(ISOLATION_JS + """await closeAll("copy-twice"); return 1;""")

    # Two windows at once.
    rules(("rule-windows", other))
    r = m.js(ISOLATION_JS + """const a = main(); let b = other(), made = false;
      if (!b) { b = a.OpenBrowserWindow(); b.__smoke = true; made = true; await wait(4000); }
      const u = args[0];
      a.gBrowser.addTrustedTab(u + "/rule-windows-a", {inBackground: true}); b.gBrowser.addTrustedTab(u + "/rule-windows-b", {inBackground: true});
      a.gBrowser.addTrustedTab(u + "/plain-windows-a", {inBackground: true}); b.gBrowser.addTrustedTab(u + "/plain-windows-b", {inBackground: true});
      await until(() => ["rule-windows-a", "rule-windows-b", "plain-windows-a", "plain-windows-b"].every(p => containersOf(p).length)); await wait(800);
      const inWin = (w, p) => w.gBrowser.tabs.filter(t => url(t).includes(p)).map(t => t.userContextId);
      const out = {a: [inWin(a, "rule-windows-a"), inWin(a, "plain-windows-a")], b: [inWin(b, "rule-windows-b"), inWin(b, "plain-windows-b")], crossed: [inWin(a, "windows-b"), inWin(b, "windows-a")], space: b.gBrowser.selectedTab.userContextId, made};
      await closeAll("windows-"); if (made) await close(b);
      return out;""", f"{base}/r", )
    check("links in two windows at once: each opens once, in its own window", r["a"][0] == [other] and r["b"][0] == [other] and r["a"][1] == [space] and len(r["b"][1]) == 1 and r["crossed"] == [[], []], str(r))

    # A redirect loop between two rules' addresses, on a real server.
    rules(("bounce/one", other), ("bounce/two", third))
    r = m.js(ISOLATION_JS + """const w = main(), count = () => w.gBrowser.tabs.length, t = inTab(args[1], "about:blank"); await wait(400);
      const before = count(); typed(t, args[0]); await wait(4000);
      const after = count();
      await closeAll("bounce"); await closeAll("about:neterror");
      return {before, after};""", f"{base}/bounce/one", space)
    check("a redirect loop between two rules' addresses opens one tab, and Firefox ends it", r["after"] == r["before"] and len(seen(m, "/bounce/")) >= 2, f"{r} {len(seen(m, '/bounce/'))}")

    # Two pages sending each other on from a sandboxed frame, which looks like an address you type.
    rules(("pp-one", other), ("pp-two", third))
    r = m.js(ISOLATION_JS + """const w = main(), part = "/pp-", count = () => containersOf(part).length; const t = inTab(args[1], args[2]); await until(() => url(t) === args[2]); await wait(400);
      typed(t, args[0]); await wait(4000);
      const first = count(); await wait(3000); const later = count();
      const tabs = w.gBrowser.tabs.length;
      await closeAll(part);
      return {first, later};""", f"{base}/pp-one", space, f"{base}/r/pp-start")
    check("two pages sending each other between two rules stop, with no storm of tabs", 1 <= r["first"] <= 4 and r["later"] == r["first"], str(r))

    rules()
    m.js(ISOLATION_JS + """await closeAll("127.0.0.1"); return 1;""")
    stats = extension_message(m, {"type": "stats"})
    check("nothing is kept of the tabs that have gone", stats["sizes"]["settled"] == 0, str(stats["sizes"]))
    no_problems(m, "after all this")
    press(m, "1", CTRL)
    time.sleep(1)


def alone_crossing(m):
    # Every other way a page gets loaded than the ones alone_isolation looks at, each with
    # the server recording what left the browser: a request must carry the cookie of its own
    # space from the first one on, and no page may end up outside a space.
    base = m.pages
    press(m, "1", CTRL)
    time.sleep(1)
    space = m.js(H + "return main().gBrowser.selectedTab.userContextId;")
    other = 2 if space != 2 else 3
    m.js(GIVE_PERMISSIONS, EXT_ID, ["webRequest", "webRequestBlocking"], ["<all_urls>"])
    visit(m, space, f"{base}/set-cookie?v=cross-here")
    visit(m, other, f"{base}/set-cookie?v=cross-there")
    here, there = "login=cross-here", "login=cross-there"
    m.js(ISOLATION_JS + """Services.prefs.setBoolPref("dom.disable_open_during_load", false); await closeAll("/set-cookie"); return 1;""")
    # (The page sending a tab on names where in a form that a check for that address doesn't find.)
    sent_to = lambda path: urllib.parse.quote(base + path, safe="").replace("-", "%2D")

    def only(part, cookie, what):
        got = seen(m, part)
        check(what, len(got) >= 1 and all(x["cookie"] == cookie for x in got), f"{part}: {got}")

    def where(part):
        return m.js(ISOLATION_JS + """await until(() => containersOf(args[0]).length, 6000); await wait(800); return containersOf(args[0]);""", part)

    # A page opening another.
    extension_message(m, {"type": "settings:rules", "rules": [{"url": "rule-opened", "space": f"firefox-container-{other}"}]})
    m.js(ISOLATION_JS + """inTab(args[0], args[1]); return 1;""", space, f"{base}/open?to={sent_to('/r/opened')}")
    r = where("/r/opened")
    only("/r/opened", here, "a page opening a tab: it goes out with its space's cookie")
    check("and the tab stays in that space", r == [space], str(r))
    m.js(ISOLATION_JS + """inTab(args[0], args[1]); return 1;""", space, f"{base}/open?to={sent_to('/r/rule-opened')}")
    r = where("/r/rule-opened")
    only("/r/rule-opened", there, "a page opening a tab that a rule sends elsewhere: only the rule's space's cookie is sent, from the first request on")
    check("and it is in the rule's space, once", r == [other], str(r))
    m.js(ISOLATION_JS + """inTab(args[0], args[1]); return 1;""", space, f"{base}/popup?to={sent_to('/r/in-popup')}")
    r = where("/r/in-popup")
    only("/r/in-popup", here, "a page opening a window of its own: its space's cookie")
    check("and that window's tab is in the space", r == [space], str(r))
    m.js(ISOLATION_JS + """for (const w of wins()) if (w.gBrowser.tabs.some(t => url(t).includes("/r/in-popup"))) await close(w); return 1;""")
    extension_message(m, {"type": "settings:rules", "rules": []})
    press(m, "1", CTRL)  # a page's new tab is selected, and the one the rule moved took you along
    time.sleep(1)

    # With no container, in every way Firefox has of opening something by itself.
    def no_container(script, part, what, *args):
        m.js(ISOLATION_JS + script, f"{base}{part}", *args)
        r = where(part)
        only(part, here, f"{what}: every request carries the active space's cookie, never none")
        check(f"{what}: its tab is in the active space, once", r == [space], str(r))

    no_container("""main().openTrustedLinkIn(args[0], "tab", {inBackground: true}); return 1;""", "/r/link-tab", "a link opened as a tab")
    no_container("""main().openTrustedLinkIn(args[0], "window"); return 1;""", "/r/link-window", "a link opened as a window")
    m.js(ISOLATION_JS + """for (const w of wins()) if (w.gBrowser.tabs.some(t => url(t).includes("/r/link-window"))) await close(w); return 1;""")
    no_container("""const t = main().gBrowser.addTrustedTab("about:blank", {inBackground: true}); await wait(300); typed(t, args[0]); return 1;""", "/r/from-blank", "an address in a blank tab")
    no_container("""main().gBrowser.addTrustedTab("view-source:" + args[0], {inBackground: true}); return 1;""", "/r/view-source", "a page's source")
    m.js(ISOLATION_JS + """main().gBrowser.addTrustedTab(args[0], {inBackground: true}); return 1;""", f"{base}/redirect?to={sent_to('/r/after-hop')}")
    r = where("/r/after-hop")
    only("after-hop", here, "a link that redirects: its first hop carries the space's cookie, and so does where it ends up")
    check("and its tab is in the active space", r == [space], str(r))
    sidebar_page(m, """await page.browser.windows.create({type: "popup", url: args[0]}); await wait(300); return 1;""", f"{base}/r/ext-popup")
    r = where("/r/ext-popup")
    only("/r/ext-popup", here, "a window another extension opens: the active space's cookie")
    check("and the page is in the active space, not left in that window", r == [space], str(r))
    # A burst, as when a bookmark folder opens.
    m.js(ISOLATION_JS + """const w = main(); for (let i = 0; i < 15; i++) w.gBrowser.addTrustedTab(args[0] + i, {inBackground: true}); await until(() => containersOf("/r/burst-").length === 15, 15000); await wait(1000); return 1;""", f"{base}/r/burst-")
    r = m.js(ISOLATION_JS + """return containersOf("/r/burst-");""")
    check("a burst of links: each is in the space, once", r == [space] * 15, str(r))
    only("/r/burst-", here, "and none went out without the space's cookie")
    m.js(ISOLATION_JS + """await closeAll("127.0.0.1"); return 1;""")

    # A tab Firefox restores unloaded, loading only when selected, with no container.
    r = m.js(ISOLATION_JS + """const w = main(), t = w.gBrowser.addTrustedTab("about:blank", {inBackground: true}); await wait(600);
      w.SessionStore.setTabState(t, JSON.stringify({entries: [{url: args[0], triggeringPrincipal_base64: '{"3":{}}', title: "Unloaded"}], lastAccessed: 1, index: 1, userContextId: 0}));
      await wait(1500);
      return {unloaded: t.hasAttribute("pending"), ctx: t.userContextId};""", f"{base}/r/resting")
    check("a restored tab with no container waits, sending nothing", r == {"unloaded": True, "ctx": 0} and not seen(m, "/r/resting"), f"{r} {seen(m, '/r/resting')}")
    m.js(ISOLATION_JS + """const w = main(); w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes("/r/resting")); return 1;""")
    r = where("/r/resting")
    only("/r/resting", here, "selected, it loads with the active space's cookie")
    check("and in the active space", r == [space], str(r))

    # A tab unloaded in a space loads there, even if a rule has come to want its address.
    visit(m, space, f"{base}/r/unloaded-here")
    time.sleep(2.5)
    extension_message(m, {"type": "settings:rules", "rules": [{"url": "unloaded-here", "space": f"firefox-container-{other}"}]})
    m.js(ISOLATION_JS + """const w = main(), t = w.gBrowser.tabs.find(x => url(x).includes("/r/unloaded-here")); w.gBrowser.discardBrowser(t, true); await wait(400); w.gBrowser.selectedTab = t; await wait(1800); return 1;""")
    r = where("/r/unloaded-here")
    only("/r/unloaded-here", here, "an unloaded tab selected: its own space's cookie")
    check("and no rule moves it", r == [space], str(r))

    # Dragged out to a window of its own and back: no request at all, and the same container.
    before = len(seen(m, "/r/unloaded-here"))
    r = m.js(ISOLATION_JS + """const w = main(), t = w.gBrowser.tabs.find(x => url(x).includes("/r/unloaded-here")); const count = wins().length; w.gBrowser.replaceTabWithWindow(t); await wait(5000);
      const out = {windows: wins().length - count, where: containersOf("/r/unloaded-here")};
      const from = wins().find(x => x !== w && x.gBrowser.tabs.some(y => url(y).includes("/r/unloaded-here")));
      if (from) { w.gBrowser.adoptTab(from.gBrowser.tabs.find(y => url(y).includes("/r/unloaded-here")), {tabIndex: w.gBrowser.tabs.length}); await wait(3000); }
      out.back = containersOf("/r/unloaded-here");
      // (That window stays, with its placeholders. It is closed so that the groups after this have the windows they had.)
      if (from && wins().includes(from)) await close(from);
      w.focus();
      return out;""")
    check("a tab dragged to a window of its own and back keeps its container", r["where"] == [space] and r["back"] == [space], str(r))
    check("and sends nothing for it, rule or no rule", len(seen(m, "/r/unloaded-here")) == before, str(seen(m, "/r/unloaded-here")))
    extension_message(m, {"type": "settings:rules", "rules": []})
    m.js(ISOLATION_JS + """await closeAll("127.0.0.1"); return 1;""")

    # Between windows: a live tab pulled in, and a placeholder loading its own page.
    made = m.js(H + """if (wins().some(w => w !== main())) return false; const w = main().OpenBrowserWindow(); await wait(5000); w.__extra = true; return true;""")
    time.sleep(3)
    visit(m, space, f"{base}/r/pulled")
    time.sleep(3)
    extension_message(m, {"type": "settings:rules", "rules": [{"url": "/r/pulled", "space": f"firefox-container-{other}"}]})
    count = len(seen(m, "/r/pulled"))
    r = m.js(ISOLATION_JS + """const live = main().gBrowser.tabs.find(x => url(x).includes("/r/pulled")), k = key(main(), live);
      const w = wins().find(x => x !== main()), t = w.gBrowser.tabs.find(x => key(w, x) === k);
      if (!t) return {placeholder: false};
      w.focus(); await wait(300); w.gBrowser.selectedTab = t; await wait(3000);
      return {placeholder: true, here: w.gBrowser.tabs.filter(x => url(x).includes("/r/pulled")).map(x => x.userContextId), all: containersOf("/r/pulled")};""")
    check("a live tab pulled into another window keeps its container", r.get("here") == [space] and r.get("all") == [space], str(r))
    check("and sends nothing for it", len(seen(m, "/r/pulled")) == count, str(seen(m, "/r/pulled")))
    folder = sidebar_page(m, """send({type: "newFolder", space: "firefox-container-" + args[0], name: "Crossing"}); await wait(1000);
      return [...doc.querySelectorAll("#tabs .folder")].find(f => f.querySelector(".head .title").textContent === "Crossing").dataset.key;""", space)
    tab = m.js(ISOLATION_JS + """const {ExtensionParent} = ChromeUtils.importESModule("resource://gre/modules/ExtensionParent.sys.mjs"); return ExtensionParent.apiManager.global.tabTracker.getId(wins().flatMap(w => w.gBrowser.tabs).find(x => url(x).includes("/r/pulled")));""")
    sidebar_page(m, """send({type: "moveTab", tabId: args[0], folder: args[1], before: null}); await wait(1500); return 1;""", tab, folder)
    time.sleep(1.5)
    r = m.js(ISOLATION_JS + """const [w, t] = wins().flatMap(w => w.gBrowser.tabs.filter(x => url(x).includes("/r/pulled")).map(x => [w, x]))[0], k = key(w, t);
      w.gBrowser.removeTab(t, {skipPermitUnload: true}); await wait(2500);
      const [w2, g] = wins().flatMap(w => w.gBrowser.tabs.filter(x => key(w, x) === k).map(x => [w, x]))[0] ?? [];
      if (!g) return {saved: false};
      w2.focus(); await wait(300); w2.gBrowser.selectedTab = g; await until(() => url(g).includes("/r/pulled"), 6000); await wait(800);
      return {saved: true, ctx: g.userContextId, all: containersOf("/r/pulled")};""")
    check("a placeholder loading its own page does so in its space, and no rule takes it", r.get("ctx") == space and r.get("all") == [space], str(r))
    only("/r/pulled", here, "with that space's cookie")
    extension_message(m, {"type": "settings:rules", "rules": []})
    sidebar_page(m, """send({type: "deleteFolder", key: args[0]}); await wait(800); return 1;""", folder)
    m.js(ISOLATION_JS + """await closeAll("127.0.0.1"); if (args[0]) await close(wins().find(w => w.__extra)); main().focus(); return 1;""", made)

    # What Firefox shows no extension at all: its restricted addresses (addons.mozilla.org
    # and the like). Here the test server's own name is made one, with its own cookie.
    hidden = "http://localhost:" + base.rsplit(":", 1)[1]
    visit(m, space, f"{hidden}/set-cookie?v=cross-hidden")
    restricted = m.js(ISOLATION_JS + """Services.prefs.setStringPref("extensions.webextensions.restrictedDomains", "localhost"); await wait(500); return WebExtensionPolicy.isRestrictedURI(Services.io.newURI(args[0]));""", hidden)
    if not restricted:
        print("SKIP  a restricted address (Firefox did not take the test's one)", flush=True)
    else:
        m.js(ISOLATION_JS + """main().gBrowser.addTrustedTab(args[0], {inBackground: true}); return 1;""", f"{hidden}/r/hidden-link")
        r = m.js(ISOLATION_JS + """await until(() => containersOf("/r/hidden-link").some(c => c), 8000); await wait(800); return containersOf("/r/hidden-link");""")
        check("a restricted address with no container: it can't be stopped, but it doesn't stay outside a space", r == [space], str(r))
        got = [x["cookie"] for x in seen(m, "/r/hidden-link")]
        check("it goes out once with no login, and then with the space's", got == ["", "login=cross-hidden"], str(got))
        extension_message(m, {"type": "settings:rules", "rules": [{"url": "/r/hidden-rule", "space": f"firefox-container-{other}"}]})
        m.js(ISOLATION_JS + """inTab(args[0], args[1]); return 1;""", space, f"{hidden}/r/hidden-rule")
        r = m.js(ISOLATION_JS + """await until(() => containersOf("/r/hidden-rule").includes(args[0]), 8000); await wait(800); return containersOf("/r/hidden-rule");""", other)
        check("and a first page there still follows a rule, once it shows", r == [other], str(r))
        extension_message(m, {"type": "settings:rules", "rules": []})
    m.js(ISOLATION_JS + """Services.prefs.clearUserPref("extensions.webextensions.restrictedDomains"); Services.prefs.clearUserPref("dom.disable_open_during_load"); await closeAll("localhost"); await closeAll("127.0.0.1"); return 1;""")
    press(m, "1", CTRL)
    time.sleep(1)


def alone_isolation_start(m):
    # Firefox closed, and a link from another app starts it: the request is held for
    # Tidier's listener, which comes back while its background page loads.
    if not m.can_restart:
        print("SKIP  alone_isolation_start (needs Tidier installed for real: Developer Edition, or --xpi)", flush=True)
        return
    base = m.pages
    # To another space and back by the key: that it is the last one is what must be kept for the start.
    press(m, "2", CTRL)
    time.sleep(1)
    press(m, "1", CTRL)
    time.sleep(1)
    space = m.js(H + "return main().gBrowser.selectedTab.userContextId;")
    m.js(GIVE_PERMISSIONS, EXT_ID, ["webRequest", "webRequestBlocking"], ["<all_urls>"])
    visit(m, space, f"{base}/set-cookie?v=at-start")
    m.js(ISOLATION_JS + """await closeAll("/set-cookie"); return 1;""")
    # A page you opened before there was a rule for it: Firefox restoring it, or you reloading it, is no reason to move it.
    visit(m, space, f"{base}/r/before-the-rule")
    other = 2 if space != 2 else 3
    extension_message(m, {"type": "settings:rules", "rules": [{"url": "before-the-rule", "space": f"firefox-container-{other}"}]})
    time.sleep(2.5)  # registered, so that it comes back
    extension_message(m, {"type": "flush"})
    time.sleep(1)
    # The first start since the permission came while Tidier ran: Firefox does not remember the
    # listener yet, so the page goes out, and is moved once Tidier has started. A pinned page
    # with no container too: Firefox loads those at once when it restores them.
    def page_with_no_container(address, **more):
        return {"entries": [{"url": address, "title": "x", "triggeringPrincipal_base64": '{"3":{}}'}], "index": 1, "lastAccessed": 1, "hidden": False, "attributes": {}, "userContextId": 0, **more}

    def with_pinned(state):
        state["windows"][0]["tabs"].insert(0, page_with_no_container(f"{base}/r/pinned-too-soon", pinned=True))
        state["windows"][0]["selected"] = state["windows"][0].get("selected", 1) + 1
    m.restart(f"{base}/r/link-too-soon", session=with_pinned)
    time.sleep(12)
    r = m.js(ISOLATION_JS + """return containersOf("link-too-soon");""")
    check("in the first start after the permission, a page that got out is moved to a space", r == [space], str(r))
    # The page itself, when it was moved before Tidier had it as an essential; else the essential
    # was moved, and its tab is a placeholder that loads the page in the space when you go to it.
    # Which of the two comes first at a start is not decided, and either is right.
    essential = m.js(ISOLATION_JS + """const e = ((await storage("%s", ["essentials"])).essentials ?? []).find(e => e.url?.includes("pinned-too-soon"));
      return e ? [e.key, e.cookieStoreId] : null;""" % EXT_ID)
    r = m.js(ISOLATION_JS + """return wins().flatMap(w => w.gBrowser.tabs.filter(t => url(t).includes("pinned-too-soon") || (args[0] && url(t).includes(args[0]))).map(t => [t.userContextId, t.pinned]));""", essential and essential[0])
    check("and so is a pinned one, still pinned", bool(r) and all(x == [space, True] for x in r) and (not essential or essential[1] == f"firefox-container-{space}"), f"{r}, {essential}")
    m.js(ISOLATION_JS + """await closeAll("link-too-soon"); await closeAll("pinned-too-soon"); return 1;""")
    extension_message(m, {"type": "flush"})
    time.sleep(1)
    m.restart(f"{base}/r/link-at-start")
    time.sleep(12)
    got = seen(m, "link-at-start")
    r = m.js(ISOLATION_JS + """return containersOf("link-at-start");""")
    check("a link that starts Firefox goes out in a space, from its first request", got and all(x["cookie"] == "login=at-start" for x in got), str(got))
    check("and its tab is there, in a space", r == [space], str(r))
    r = m.js(ISOLATION_JS + """const w = main(), t = w.gBrowser.tabs.find(x => url(x).includes("before-the-rule"));
      if (!t) return {missing: true};
      const before = {ctx: t.userContextId, loaded: !!t.linkedPanel};
      w.gBrowser.selectedTab = t; await wait(2000);
      const restored = containersOf("before-the-rule");
      w.gBrowser.reloadTab(t); await wait(1500);
      return {before, restored, reloaded: containersOf("before-the-rule")};""")
    check("a tab Firefox restores is not moved by a rule, nor when you reload it", r.get("restored") == [space] and r.get("reloaded") == [space], str(r))
    extension_message(m, {"type": "settings:rules", "rules": []})
    m.js(ISOLATION_JS + """await closeAll("/r/"); return 1;""")
    extension_message(m, {"type": "flush"})
    time.sleep(1)

    # A session holding pages with no container: selected (Firefox loads it at once), pinned
    # (the same) and in the background (only when selected). Held, all of them.
    def with_pages(state):
        tabs = state["windows"][0]["tabs"]
        tabs.insert(0, page_with_no_container(f"{base}/r/restored-pinned", pinned=True))
        tabs.append(page_with_no_container(f"{base}/r/restored-behind"))
        tabs.append(page_with_no_container(f"{base}/r/restored-selected"))
        state["windows"][0]["selected"] = len(tabs)
    m.restart(session=with_pages)
    time.sleep(12)
    r = m.js(ISOLATION_JS + """const w = main(); return {selected: containersOf("restored-selected"), pinned: wins().flatMap(w => w.gBrowser.tabs.filter(t => url(t).includes("restored-pinned")).map(t => [t.userContextId, t.pinned])), behind: w.gBrowser.tabs.filter(t => url(t).includes("restored-behind")).map(t => [t.userContextId, !!t.linkedPanel])};""")
    check("a restored page with no container, selected, is in the space", r["selected"] == [space], str(r))
    check("a pinned one too, still pinned", r["pinned"] == [[space, True]], str(r))
    for part in ("restored-selected", "restored-pinned"):
        got = seen(m, part)
        check(f"{part}: every request carries the space's cookie, from the first one on", got and all(x["cookie"] == "login=at-start" for x in got), str(got))
    check("one in the background waits, sending nothing", r["behind"] == [[0, False]] and not seen(m, "restored-behind"), f"{r} {seen(m, 'restored-behind')}")
    r = m.js(ISOLATION_JS + """const w = main(); w.gBrowser.selectedTab = w.gBrowser.tabs.find(t => url(t).includes("restored-behind")); await until(() => containersOf("restored-behind").some(c => c), 6000); await wait(800); return containersOf("restored-behind");""")
    check("selected, it loads in the space", r == [space], str(r))
    got = seen(m, "restored-behind")
    check("with its cookie, from the first request on", got and all(x["cookie"] == "login=at-start" for x in got), str(got))
    m.js(ISOLATION_JS + """await closeAll("/r/restored-"); return 1;""")

    # An update: for a moment nothing is listening. A link opened then may go out, but with
    # no login, and every one ends up in a space.
    r = m.js(ISOLATION_JS + """const {AddonManager} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs"), {FileUtils} = ChromeUtils.importESModule("resource://gre/modules/FileUtils.sys.mjs");
      const w = main(), install = await AddonManager.getInstallForFile(new FileUtils.File(args[0]));
      const done = install.install();
      for (let i = 0; i < 20; i++) { w.gBrowser.addTrustedTab(args[1] + i, {inBackground: true}); await wait(100); }
      await done; await wait(10000);
      return containersOf("/r/during-update-");""", m.update_xpi(), f"{base}/r/during-update-")
    check("links opened during an update are each in the space, once", sorted(r) == [space] * 20, str(r))
    got = seen(m, "/r/during-update-")
    check("and each request carried the space's cookie or none, never another's", got and all(x["cookie"] in ("", "login=at-start") for x in got), str(got))
    m.js(ISOLATION_JS + """await closeAll("/r/during-update-"); return 1;""")

    # A space's proxy: Firefox decides on it as it opens a request, before any extension has
    # run at a start. Here this is the first start since it was set, the hardest one: only an
    # address nothing can reach but the proxy shows that it went that way. Going directly it
    # would never reach the server.
    third = next(c for c in (1, 2, 3) if c not in (space, other))
    m.js(GIVE_PERMISSIONS, EXT_ID, ["proxy"], ["<all_urls>"])
    extension_message(m, {"type": "isolation:network", "id": f"firefox-container-{third}", "proxy": {"type": "http", "host": "127.0.0.1", "port": base.rsplit(":", 1)[1]}})
    time.sleep(1)
    far = "http://proxied.invalid/r/proxied-at-start"
    r = m.js(ISOLATION_JS + """const w = main(), t = inTab(args[0], args[1]); await until(() => url(t) === args[1], 8000); await wait(2500); w.gBrowser.selectedTab = t; await wait(1500); return url(t);""", third, far)
    check("a page in a space with a proxy goes through it", r == far and all(x["proxied"] for x in seen(m, "proxied-at-start")), f"{r} {seen(m, 'proxied-at-start')}")
    extension_message(m, {"type": "flush"})
    time.sleep(1)
    before = len(seen(m, "proxied-at-start"))
    m.restart()
    time.sleep(12)
    got = seen(m, "proxied-at-start")[before:]
    r = m.js(ISOLATION_JS + """const w = main(); return {selected: url(w.gBrowser.selectedTab), ctx: w.gBrowser.selectedTab.userContextId};""")
    check("restored at a start, that page still reaches the server, through the proxy", got and all(x["proxied"] for x in got) and r == {"selected": far, "ctx": third}, f"{r} {got}")
    extension_message(m, {"type": "isolation:network", "id": f"firefox-container-{third}"})
    m.js(ISOLATION_JS + """await closeAll("proxied.invalid"); return 1;""")
    press(m, "1", CTRL)
    time.sleep(1)
    no_problems(m, "after a start by a link")
