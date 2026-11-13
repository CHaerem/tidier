"""What every group of checks leans on: the result list, keys, and the ways into Firefox's own
part, Tidier's pages and its sidebar.
"""
import json
import time
from testfirefox import EXT_ID


CMD, SHIFT, CTRL, ESC = "", "", "", ""


# Shared helpers for the chrome-context scripts below.
H = """
  const {setTimeout: sT} = ChromeUtils.importESModule("resource://gre/modules/Timer.sys.mjs");
  const wait = ms => new Promise(r => sT(r, ms));
  const {ExtensionStorageIDB} = ChromeUtils.importESModule("resource://gre/modules/ExtensionStorageIDB.sys.mjs");
  const storage = async (id, keys) => (await ExtensionStorageIDB.open(ExtensionStorageIDB.getStoragePrincipal(WebExtensionPolicy.getByID(id).extension))).get(keys);
  const wins = () => [...Services.wm.getEnumerator("navigator:browser")];
  const main = () => wins().find(w => !w.__smoke && !w.__extra), other = () => wins().find(w => w.__smoke);
  const es = "extension:%(ext)s:";
  const value = (w, t, name) => { try { return JSON.parse(w.SessionStore.getCustomTabValue(t, es + name) || "null"); } catch (e) { return null; } };
  const key = (w, t) => w.SessionStore.getCustomTabValue(t, es + "syncKey");  // JSON-encoded, as stored
  const ek = (w, t) => value(w, t, "essentialKey");
  const role = (w, t) => value(w, t, "syncRole");
  const url = t => { try { return t.linkedBrowser.currentURI.spec; } catch (e) { return ""; } };
  const find = k => wins().map(w => w.gBrowser.tabs.filter(t => key(w, t) === k).map(t => role(w, t) + (t.linkedPanel ? "/loaded" : "/unloaded")));
  const ctxOf = t => t.userContextId ? "firefox-container-" + t.userContextId : "firefox-default";
  const close = async w => { Services.prefs.setBoolPref("browser.tabs.warnOnClose", false); w.close(); await wait(2500); };
  const removeWhere = async test => { for (const w of wins()) for (const t of [...w.gBrowser.tabs]) if (test(w, t)) w.gBrowser.removeTab(t); await wait(2500); };
""" % {"ext": EXT_ID}


results = []


setup_only = False  # True while a group runs only to set up others (see run_groups)


def check(name, ok, detail=""):
    if setup_only:  # reported only when it fails, by the run that owns the group
        if not ok:
            results.append(False)
            print(f"FAIL  {name}  (setup for the checks below{'; ' + detail if detail else ''})", flush=True)
        return
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""), flush=True)


def press(m, key, *mods):
    acts = [{"type": "keyDown", "value": k} for k in mods] + [{"type": "keyDown", "value": key}, {"type": "keyUp", "value": key}]
    acts += [{"type": "keyUp", "value": k} for k in reversed(mods)]
    m.cmd("WebDriver:PerformActions", {"actions": [{"type": "key", "id": "kb", "actions": acts}]})
    m.cmd("WebDriver:ReleaseActions")


def into_page(m, part, exact=False, focus=False):
    """Run the next scripts in the page of the tab with `part` in its address, main()'s first. Its
    handle is asked for, since switching through the tabs until the right one loads every unloaded
    tab on the way (Marionette reads each one's message manager), and then a tab that should stay
    unloaded no longer is, because of the test itself. That page would even say something new, as
    it loads in the background, and get a dot."""
    m.chrome()
    handle = m.js(H + """const {NavigableManager} = ChromeUtils.importESModule("chrome://remote/content/shared/NavigableManager.sys.mjs");
      const t = [main(), ...wins()].flatMap(w => w.gBrowser.tabs).find(t => args[1] ? url(t) === args[0] : url(t).includes(args[0]));
      return t ? NavigableManager.getIdForBrowser(t.linkedBrowser) : null;""", part, exact)
    if not handle:
        raise RuntimeError(f"no tab with {part}")
    m.cmd("Marionette:SetContext", {"value": "content"})
    m.cmd("WebDriver:SwitchToWindow", {"handle": handle, "focus": focus})  # focus: that tab is selected too


def extension_message(m, msg):
    """Send a runtime message from one of the extension's own pages, and return the reply."""
    m.js(H + """const w = main(); w.focus(); w.__beforeHelper = w.gBrowser.selectedTab;
      const t = w.gBrowser.addTrustedTab("moz-extension://" + JSON.parse(Services.prefs.getStringPref("extensions.webextensions.uuids"))[args[0]] + "/ghost.html?kind=test", {});
      w.gBrowser.selectedTab = t; await wait(1500); return 1;""", EXT_ID)
    into_page(m, "ghost.html?kind=test")
    reply = m.cmd("WebDriver:ExecuteAsyncScript", {"script": """
      const done = arguments[arguments.length - 1];
      (window.wrappedJSObject || window).browser.runtime.sendMessage(arguments[0]).then(r => done(JSON.parse(JSON.stringify(r ?? null))), e => done({error: String(e)}));""",
      "args": [msg]})
    m.chrome()
    # Close the helper page with the tab selected before it back in front;
    # otherwise Firefox selects a neighbour, which may be a ghost that Tidier
    # then (rightly) pulls in, and the test would be testing its own clicks.
    m.js(H + """const w = main(), t = w.gBrowser.tabs.find(x => url(x).includes("ghost.html?kind=test"));
      if (w.__beforeHelper && !w.__beforeHelper.closing) w.gBrowser.selectedTab = w.__beforeHelper;
      if (t) w.gBrowser.removeTab(t); await wait(500); return 1;""")
    return reply


def to_folder(m, address, folder, before=None):
    """Move the main window's tab with this address into the folder of that name (None: out of
    any), before the tab whose address has `before` in it (None: last there), as a drag in the
    sidebar does."""
    sidebar_page(m, """const [address, name, before] = args;
      await page.browser.runtime.sendMessage(page.JSON.parse(JSON.stringify({type: "flush"})));
      const all = (await page.browser.storage.local.get("syncedTabs")).syncedTabs;
      const folder = name ? Object.keys(all).find(k => all[k].group && all[k].name === name) : null;
      const tabs = await page.browser.tabs.query(page.JSON.parse(JSON.stringify({windowId: (await page.browser.windows.getCurrent()).id})));
      const tab = tabs.find(t => t.url === address), next = before ? tabs.find(t => t.url.includes(before)) : null;
      send({type: "moveTab", tabId: tab.id, folder, before: next?.id ?? null});
      await wait(2500);
      return 1;""", address, folder, before)


def close_sidebar_page(m):
    """Close the sidebar page sidebar_page opened in a tab, so that it is not counted as a tab."""
    m.js(H + """for (const w of wins()) for (const t of [...w.gBrowser.tabs]) if (url(t).includes("/sidebar/sidebar.html")) w.gBrowser.removeTab(t);
      await wait(500); return 1;""")


# The extension process's memory and CPU time so far (Tidier shares it with
# Firefox's own extensions).
PROC_INFO = """const info = await ChromeUtils.requestProcInfo();
  const ext = info.children.filter(c => c.type === "extension");
  return {mb: Math.round(ext.reduce((s, c) => s + (c.memory || 0), 0) / 1048576), cpuS: ext.reduce((s, c) => s + (c.cpuTime || 0), 0) / 1e9};"""


def no_problems(m, when):
    """Errors inside Tidier (common.js, noteError): each is a tab that was not handled."""
    problems = extension_message(m, {"type": "stats"})["problems"]
    check(f"no errors inside Tidier {when}", not problems, str(problems[-5:]))


def sidebar_page(m, script, *args):
    """Run `script` in Tidier's sidebar page (opened in a tab of the main window, once)."""
    return ext_page(m, "/sidebar/sidebar.html", script, *args)


def ext_page(m, path, script, *args):
    """Run `script` in one of Tidier's own pages, opened in a tab of the main window, once."""
    m.js(H + """const w = main(); w.focus();
      if (!w.gBrowser.tabs.some(t => url(t).includes(args[1]))) {
        const t = w.gBrowser.addTrustedTab("moz-extension://" + JSON.parse(Services.prefs.getStringPref("extensions.webextensions.uuids"))[args[0]] + args[1], {inBackground: true});
        await wait(1500);
      }
      return 1;""", EXT_ID, path)
    into_page(m, path)
    reply = m.cmd("WebDriver:ExecuteAsyncScript", {"script": """
      const args = [...arguments], done = args.pop(), wait = ms => new Promise(r => setTimeout(r, ms));
      const page = window.wrappedJSObject || window, doc = page.document;
      const rows = () => [...doc.querySelectorAll("#tabs .tab")].map(r => r.querySelector(".title").textContent);
      const folders = () => [...doc.querySelectorAll("#tabs .folder")].map(f => ({name: f.querySelector(".head .title")?.textContent, tabs: [...f.querySelectorAll(".tab .title")].map(t => t.textContent), collapsed: f.classList.contains("collapsed")}));
      const tiles = () => [...doc.querySelectorAll("#essentials .tile")].map(t => t.title.split("\\n")[0]);
      const spaces = () => [...doc.querySelectorAll("#spaces .space")].map(b => ({id: b.dataset.space, active: b.classList.contains("active")}));
      const plainTabs = () => [...doc.querySelectorAll("#tabs > .tab")].filter(r => r.querySelector(".title").textContent !== "Tidier");
      (async () => {
        const port = page.browser.runtime.connect({name: "sidebar"});
        const send = msg => port.postMessage(page.JSON.parse(JSON.stringify(msg)));
        send({type: "hello", windowId: (await page.browser.windows.getCurrent()).id});
        await wait(100);
        try { """ + script + """ } finally { port.disconnect(); }
      })().then(r => done(JSON.parse(JSON.stringify(r ?? null))), e => done({error: String(e)}));""",
      "args": list(args)})
    m.chrome()
    return reply


# --- Isolation: nothing goes out in the wrong container ------------------------------
# The check that matters most. The server records each request and its Cookie header, so
# this is what really left the browser, not what Tidier thinks it did.
GIVE_PERMISSIONS = """const [id, permissions, origins] = args;
  const {ExtensionPermissions} = ChromeUtils.importESModule("resource://gre/modules/ExtensionPermissions.sys.mjs");
  await ExtensionPermissions.add(id, {permissions, origins}, WebExtensionPolicy.getByID(id).extension);
  await new Promise(r => ChromeUtils.importESModule("resource://gre/modules/Timer.sys.mjs").setTimeout(r, 800));
  return 1;"""


def seen(m, part):
    return [r for r in m.page_requests if part in r["path"]]


# A link from another app, the way it reaches Firefox: on a Mac as on the command line, through
# Firefox's own command line handler, which goes on to openURI with OPEN_EXTERNAL. What comes
# before it (the OS, the app coming to the front) cannot be done in a headless Firefox.
LITTLE = H + """
  const popups = () => wins().filter(w => !w.toolbar.visible);
  const external = u => Cc["@mozilla.org/browser/final-clh;1"].getService(Ci.nsICommandLineHandler).handle(Cu.createCommandLine(["-url", u], Services.dirsvc.get("CurWorkD", Ci.nsIFile), Ci.nsICommandLine.STATE_REMOTE_AUTO));
  const until = async (f, ms = 10000) => { for (const t0 = Date.now(); Date.now() - t0 < ms; await wait(50)) { const v = f(); if (v) return v; } return f(); };
  const onSpaceTab = async () => { const w = main(); w.focus(); const t = w.gBrowser.tabs.find(t => !t.hidden && !t.pinned && t.userContextId); w.gBrowser.selectedTab = t; await wait(500); return t; };
  const record = async () => Object.values((await storage("%s", ["syncedTabs"])).syncedTabs);
  const shownIn = p => { const t = p.gBrowser.selectedTab; return {url: url(t), space: t.userContextId, tabs: p.gBrowser.tabs.length, width: p.outerWidth, height: p.outerHeight, title: p.document.title}; };
""" % EXT_ID


def until(m, script, *args, tries=150):
    """Run a chrome script returning {ok, ...} until it is ok, and return its last answer: wait for a state, not a time."""
    return m.js(H + "let got; for (let i = 0; i < args[0]; i++) { got = await (async () => { " + script + " })(); if (got.ok) return got; await wait(200); } return got;", tries, *args)


def more_tabs_here(m, name):
    """Three more tabs in the active space, for checks that use up tabs."""
    space = sidebar_page(m, """return spaces().find(s => s.active).id;""")
    m.js(H + """const w = main(), ctx = Number(args[0].split("-").pop());
      for (const i of [1, 2, 3]) { w.gBrowser.addTrustedTab("https://example.org/?smoke-" + args[1] + "-" + i, {userContextId: ctx, inBackground: true}); await wait(200); }
      await wait(3500); return 1;""", space, name)


# The real sidebar, not a copy in a tab (sidebar_page): what the mouse and the keyboard
# do there, focus included, can only be seen in the real one. Its page is read with a
# frame script; the mouse and keys are WebDriver's, in the window.
IN_SIDEBAR = """
  const inSidebar = (source, ...a) => {
    const mm = main().SidebarController.browser.contentDocument.getElementById("webext-panels-browser").messageManager;
    const tag = "smoke:" + Math.random();
    const answer = new Promise(done => mm.addMessageListener(tag, function got(msg) { mm.removeMessageListener(tag, got); done(msg.data); }));
    mm.loadFrameScript("data:,(" + encodeURIComponent(`function() {
      const doc = content.document, dot = id => doc.querySelector('#spaces .space[data-space="' + id + '"]');
      const labels = () => [...doc.querySelectorAll("#menu:not([hidden]) .item")].map(i => i.textContent);
      const item = label => [...doc.querySelectorAll("#menu .item")].find(i => i.textContent === label);
      const box = () => doc.querySelector(".space-box");
      const top = id => doc.getElementById(id).getBoundingClientRect().top;
      let out; try { out = (${source})(...${JSON.stringify(a)}); } catch (e) { out = {error: String(e)}; }
      sendAsyncMessage(${JSON.stringify(tag)}, out);
    }`) + ")()", false);
    return answer;
  };"""


ENTER = "\ue007"  # WebDriver's key, as CMD and the others above


def in_sidebar(m, source, *args):
    return m.js(H + IN_SIDEBAR + "return await inSidebar(...args);", source, *args)


def sidebar_until(m, source, *args, timeout=15):
    """A state of the real sidebar: a click reaches it in its own time on a busy machine."""
    deadline = time.time() + timeout
    while True:
        r = in_sidebar(m, source, *args)
        if (r and not (isinstance(r, dict) and r.get("wait"))) or time.time() > deadline:
            return r
        time.sleep(0.1)


def sidebar_mouse(m, target, button=0):
    """A real click (button 2: right) on the middle of what the script `target` finds."""
    x, y = m.js(H + IN_SIDEBAR + """const b = main().SidebarController.browser.getBoundingClientRect();
      const [x, y] = await inSidebar(args[0]); return [b.x + x, b.y + y];""",
      f"() => {{ const r = ({target}).getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }}")
    m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"}, "actions": [
        {"type": "pointerMove", "x": int(x), "y": int(y), "origin": "viewport", "duration": 0},
        {"type": "pointerDown", "button": button}, {"type": "pointerUp", "button": button}]}]})
    m.cmd("WebDriver:ReleaseActions")


def sidebar_key(m, key):
    """A key for the sidebar. Firefox's own panel about hidden tabs can open at any moment
    after Tidier hides a tab, and while it is open a key closes it and goes no further."""
    m.js(H + """main().document.getElementById("extension-notification-panel")?.hidePopup?.(); return 1;""")
    press(m, key)


def menu_on(m, target, offers=None):
    """Right click on `target`: what its menu offers, once what is expected is there."""
    sidebar_mouse(m, target, 2)
    return sidebar_until(m, "(want) => { const now = labels(); return now.length && (!want || want === now.join()) ? now : null; }", offers and ",".join(offers)) or in_sidebar(m, "() => labels()")


def choose(m, label):
    sidebar_mouse(m, f"item({json.dumps(label)})")
    sidebar_until(m, "() => !labels().length")


# A real wheel, real clicks and real keys from outside the page, aimed at the sidebar (its
# page sits in two nested browsers in the window). A headless Firefox has no trackpad, but
# these take Firefox's own way to the page, with focus and scrolling as they really are.
SIDEBAR_AT = H + """const w = main(), a = w.SidebarController.browser.getBoundingClientRect(),
    b = w.SidebarController.browser.contentDocument.getElementById("webext-panels-browser").getBoundingClientRect();
  return {x: a.x + b.x, y: a.y + b.y};"""


def click_at(m, at, x, y):
    m.cmd("WebDriver:PerformActions", {"actions": [{"type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"}, "actions": [
        {"type": "pointerMove", "duration": 0, "x": int(at["x"] + x), "y": int(at["y"] + y), "origin": "viewport"},
        {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}]}]})
    m.cmd("WebDriver:ReleaseActions")


# What the look promises, measured in the real sidebar, where pictures (tools/shoot.py) can
# only show it: what is made by hand here is what a drag, a sound or a small window would
# make, and is taken away again at once, in the same frame script, before any view comes.
LOOK_IN_SIDEBAR = """
  const lookInSidebar = (source, ...a) => {
    const mm = main().SidebarController.browser.contentDocument.getElementById("webext-panels-browser").messageManager;
    const tag = "smoke-look:" + Math.random();
    const answer = new Promise(done => mm.addMessageListener(tag, function got(msg) { mm.removeMessageListener(tag, got); done(msg.data); }));
    mm.loadFrameScript("data:,(" + encodeURIComponent(`function() {
      const doc = content.document, page = content.wrappedJSObject, css = (e, p) => content.getComputedStyle(e, p);
      const sleep = ms => new Promise(r => content.setTimeout(r, ms));
      const box = e => e.getBoundingClientRect(), clone = o => page.JSON.parse(JSON.stringify(o));
      // A colour as the page computes it, without a transition.
      const colour = value => { const probe = doc.createElement("i"); probe.style.color = value; doc.body.append(probe); const c = css(probe).color; probe.remove(); return c; };
      const light = c => (c.startsWith("color(") ? 255 : 1) * (c.match(/[\\\\d.]+/g) ?? []).slice(0, 3).reduce((s, v) => s + Number(v), 0); // rgb() is 0-255, color(srgb) 0-1
      Promise.resolve().then(() => (${source})(...${JSON.stringify(a)})).then(out => out, e => ({error: String(e)})).then(out => sendAsyncMessage(${JSON.stringify(tag)}, out));
    }`) + ")()", false);
    return answer;
  };"""


def look_in_sidebar(m, source, *args):
    return m.js(H + LOOK_IN_SIDEBAR + "return await lookInSidebar(...args);", source, *args)


# --- The command bar: real keys, in the panel it really opens in. ----------------------
ENTER, DOWN, UP, TAB = "\ue007", "\ue015", "\ue013", "\ue004"


# The bar is a panel of Firefox's in the window it was opened from, with Tidier's page in it
# (commandbar.js). `bar()`: {panel, browser, window}, or nothing. `barWindows()`: a bar that is
# a window of its own, which Tidier falls back to only where Firefox opens no panel.
BAR = H + """const barIn = w => { const b = [...w.document.querySelectorAll("panel browser")].find(b => (b.currentURI?.spec || "").includes("/commandbar/commandbar.html")), p = b?.closest("panel");
    return p && (p.state === "open" || p.state === "showing") ? {panel: p, browser: b, window: w} : null; };
  const bar = () => wins().filter(w => w.toolbar.visible).map(barIn).find(Boolean) ?? null;
  const barWindows = () => wins().filter(w => !w.toolbar.visible && w.gBrowser?.tabs.some(t => url(t).includes("/commandbar/commandbar.html")));
  // Run in the bar's own page, in its process: Marionette cannot be pointed at a panel's page.
  const inBar = async (source, args = []) => { const b = bar(); if (!b) return {gone: true};
    const mm = b.browser.messageManager, id = "smoke:bar:" + Math.random();
    const got = new Promise(r => mm.addMessageListener(id, function heard(msg) { mm.removeMessageListener(id, heard); r(msg.data); }));
    mm.loadFrameScript("data:," + encodeURIComponent("(async () => { const page = content.wrappedJSObject, doc = page.document, args = " + JSON.stringify(args) + "; " + source
      + " })().then(value => sendAsyncMessage(" + JSON.stringify(id) + ", {value}), err => sendAsyncMessage(" + JSON.stringify(id) + ", {error: String(err)}));"), false);
    return Promise.race([got, wait(15000).then(() => ({gone: true}))]); };
"""


def bar_is_open(m):
    return m.js(BAR + "return !!bar();")


def wait_for_bar(m, want=True, tries=100):
    for _ in range(tries):
        if bar_is_open(m) == want:
            return True
        time.sleep(0.1)
    return False


def bar_open(m, window="main()"):
    """Open the bar with its key from `window`, as you would; returns when you can type."""
    # Once the window really has the focus: asked for, it can come after the bar has opened, which would close it.
    # Firefox's own question about hidden tabs is put away first: it is a panel, and Firefox
    # opens no second one beside it (the bar is then a window of its own: alone_bar_edges).
    m.js(H + f"""const w = {window}; for (const x of wins()) x.document.getElementById("extension-notification-panel")?.hidePopup?.();
      w.focus(); for (let i = 0; i < 100 && Services.focus.activeWindow !== w; i++) await wait(50); w.gBrowser.selectedBrowser.focus(); await wait(100); return 1;""")
    press_in(m, window, "k", CMD, SHIFT)
    if not wait_for_bar(m):
        seen = m.js(BAR + """return {panels: wins().flatMap(w => [...w.document.querySelectorAll("panel")].filter(p => p.state !== "closed").map(p => [p.id, p.state, [...p.querySelectorAll("browser")].map(b => b.currentURI?.spec.slice(-60))])),
          windows: barWindows().length, focus: Services.focus.activeWindow === main()};""")
        traces = [t for t in extension_message(m, {"type": "stats"}).get("traces", []) if "bar" in t]
        raise RuntimeError(f"the command bar did not open: {seen} {traces}")
    # Its rows, and the keyboard, which Firefox gives a panel some milliseconds after it shows.
    for _ in range(100):
        state = bar_page(m, "return doc.hasFocus() && doc.documentElement.dataset.readyMs || null;")
        if state:
            return int(state)
        time.sleep(0.05)
    raise RuntimeError("the command bar has no rows, or not the keyboard")


def press_in(m, window, key, *mods):
    """A real key press in the given window of Firefox's (Marionette sends keys to the window it is on)."""
    m.chrome()
    for h in m.cmd("WebDriver:GetWindowHandles"):
        m.cmd("WebDriver:SwitchToWindow", {"handle": h, "focus": False})
        if m.js(H + f"return window === {window};"):
            break
    try:
        press(m, key, *mods)
    finally:
        m.chrome()


# What WebDriver calls a key, as a page hears it.
BAR_KEY_NAMES = {"": "Enter", "": "Escape", "": "Tab", "": "Backspace", "": "ArrowDown", "": "ArrowUp",
                 "": "ArrowLeft", "": "ArrowRight", "": "Meta", "": "Shift", "": "Control", "": "Alt"}


def bar_keys(m, keys, *mods):
    """Real key events, to the bar's page, as the keyboard gives them to a panel that has it:
    made in the page's own process, since the keys Marionette sends go to the window's own
    part and never reach a panel. Any of them may close the bar, before the rest have been sent."""
    names = [BAR_KEY_NAMES.get(k, k) for k in keys]
    answer = m.js(BAR + """const [keys, mods] = args;
      return inBar(`const tip = Cc["@mozilla.org/text-input-processor;1"].createInstance(Ci.nsITextInputProcessor);
        if (!tip.beginInputTransactionForTests(content)) throw new Error("the bar's page takes no keys");
        const sided = ["Meta", "Shift", "Control", "Alt"];
        const event = key => new content.KeyboardEvent("", {key, code: sided.includes(key) ? key + "Left" : key.length === 1 && /[a-z]/i.test(key) ? "Key" + key.toUpperCase() : key.length === 1 && /\\\\d/.test(key) ? "Digit" + key : key.length === 1 ? "" : key});
        const flags = key => (key.length === 1 ? 0 : tip.KEY_NON_PRINTABLE_KEY);
        const [keys, mods] = args;
        for (const mod of mods) tip.keydown(event(mod), tip.KEY_NON_PRINTABLE_KEY);
        try {
          for (const key of keys) {
            if (!content.document.documentElement) break;  // it has closed
            tip.keydown(event(key), flags(key));
            tip.keyup(event(key), flags(key));
          }  // (one after the other with no pause: on a busy machine a page's timers come late, and each key is taken in as it is sent)
        } finally { for (const mod of [...mods].reverse()) tip.keyup(event(mod), tip.KEY_NON_PRINTABLE_KEY); }
        return content.document.documentElement ? {field: doc.getElementById("field").value, focus: doc.hasFocus(), on: doc.activeElement?.id ?? null} : null;`, [keys, mods]);""", names, [BAR_KEY_NAMES[k] for k in mods])
    if "error" in answer:
        raise RuntimeError(f"keys to the bar: {answer['error']}")
    after = answer.get("value")
    if after and not mods and all(len(k) == 1 for k in names) and not after["field"].endswith("".join(names)):
        print(f"INFO  typed {''.join(names)!r} into the bar, and its field has {after}", flush=True)


def bar_page(m, script, *args):
    """Run `script` in the bar's own page (`page`, `doc`, `args`); nothing if the bar has gone."""
    answer = m.js(BAR + "return inBar(args[0], args[1]);", script, list(args))
    if "error" in answer:
        raise RuntimeError(f"in the bar's page: {answer['error']}")
    return answer.get("value")


BAR_ROWS = """return [...doc.querySelectorAll(".row")].map(r => ({kind: r.dataset.kind, url: r.dataset.url || null, title: r.querySelector(".title").textContent, selected: r.classList.contains("selected")}));"""


def bar_rows_until(m, test, tries=50):
    """The rows, once `test(rows)` holds (rows are drawn as the keys arrive)."""
    rows = []
    for _ in range(tries):
        rows = bar_page(m, BAR_ROWS) or []
        if test(rows):
            return rows
        time.sleep(0.05)
    return rows


# Placeholders in Recently Closed, in a page of Tidier's own: they go a moment after they
# are closed, so they are given a moment. (The smoke test's own helper pages are kind=test.)
RECENTLY_CLOSED_PLACEHOLDERS = """
  const look = async () => (await page.browser.sessions.getRecentlyClosed()).map(c => c.tab?.url || "").filter(u => /ghost\\.html\\?kind=(ghost|essential|lazy)/.test(u));
  let left = await look();
  for (let i = 0; i < 40 && left.length; i++) { await wait(500); left = await look(); }
  return {left};"""


# Each window's tabs and space, and the folders.
SNAP_ALONE = H + """
  const all = (await storage("%s", ["syncedTabs"])).syncedTabs;
  const windows = wins().map(w => ({
    essentials: w.gBrowser.tabs.filter(t => t.pinned).map(t => ek(w, t)).sort(),
    tabs: w.gBrowser.tabs.filter(t => !t.pinned && key(w, t)).map(t => key(w, t)).sort(),
    shown: [...new Set(w.gBrowser.tabs.filter(t => !t.pinned && !t.hidden && t.userContextId).map(t => t.userContextId))].length,
    live: w.gBrowser.tabs.filter(t => !t.pinned && role(w, t) === "live").length,
  })).sort((a, b) => JSON.stringify(a) < JSON.stringify(b) ? -1 : 1);
  return {windows, folders: Object.values(all).filter(e => e.own).map(e => e.name).sort(), inFolders: Object.values(all).filter(e => e.saved).length};""" % EXT_ID
