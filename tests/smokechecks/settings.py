"""The settings page, copies of Tidier's data, and the bridge for agents."""
import base64
import json
import os
import re
import socket
import stat
import subprocess
import tempfile
import time
from mcp_client import Mcp
from testfirefox import EXT_DIR, EXT_ID, FIXTURES
from smokechecks.base import CTRL, H, SHIFT, check, ext_page, extension_message, in_sidebar, into_page, no_problems, press, sidebar_page, sidebar_until, until


# A row of a web page: its tooltip is its title, then its address. (No backslash: the
# script goes through a string on its way into the page.)
BRIDGE_PAGE_ROW = """const isPage = r => (r.title.split(String.fromCharCode(10))[1] || "").startsWith("http");"""


def alone_bridge(m):
    # The real thing, end to end: an MCP client, the real MCP server, the real socket and
    # native host, and Firefox. No Sidebery, no gh, no network: the page is the test server's.
    sock = f"{m.config_home}/tidier/bridge.sock"
    host = os.path.join(EXT_DIR, "native", "tidier-bridge.py")
    # This Firefox's own child: another test Firefox running from the same folder has a host of its own.
    running = lambda: subprocess.run(["pgrep", "-P", str(m.js("return Services.appinfo.processID;")), "-f", host], capture_output=True).returncode == 0

    def until(test, seconds=8):
        for _ in range(int(seconds * 10)):
            if test():
                return True
            time.sleep(0.1)
        return test()

    # Off: nothing runs, and the agent is told who can turn it on.
    client = Mcp(m.config_home)
    client.handshake()
    check("with the bridge off there is no socket and no process", not os.path.exists(sock) and not running())
    text, is_error, _ = client.call("list_spaces")
    check("with the bridge off, an agent is told so", is_error and "settings page" in text, text)
    r = ext_page(m, "/settings/settings.html", """await wait(500);
      return {on: doc.getElementById("bridge-on").checked, copy: doc.getElementById("claude-copy").checked, details: doc.getElementById("bridge-details").hidden, shown: !doc.getElementById("claude-section").hidden};""")
    check("the settings page has it, off", r == {"on": False, "copy": False, "details": True, "shown": True}, str(r))
    spaces_before = sidebar_page(m, "await wait(300); return spaces().length;")

    # On, by your click (the permission is what that click asks for, given here as in AFTER_TIDIER_ALONE).
    m.js("""const [id] = args; const {ExtensionPermissions} = ChromeUtils.importESModule("resource://gre/modules/ExtensionPermissions.sys.mjs");
      await ExtensionPermissions.add(id, {permissions: [], origins: ["<all_urls>"]}, WebExtensionPolicy.getByID(id).extension); return 1;""", EXT_ID)
    r = ext_page(m, "/settings/settings.html", """doc.getElementById("bridge-on").click(); await wait(1200);
      return {on: doc.getElementById("bridge-on").checked, status: doc.getElementById("bridge-status").textContent, how: doc.getElementById("bridge-how").textContent, reading: doc.getElementById("bridge-reading").hidden};""")
    check("turned on, the settings page says it is ready, and how to add it to Claude Code", r["on"] and "Ready" in r["status"] and "claude mcp add tidier" in r["how"] and "tidier-mcp.py" in r["how"], str(r))
    check("on: there is a socket only you can reach, and the process", until(lambda: os.path.exists(sock)) and stat.S_IMODE(os.lstat(sock).st_mode) == 0o600 and running())
    agent = sidebar_page(m, """await wait(500); const a = [...doc.querySelectorAll("#spaces .space")].find(b => b.title === "Agent"); return {n: spaces().length, id: a?.dataset.space};""")
    check("turning it on makes a space named Agent", agent["id"] and agent["n"] == spaces_before + 1, str(agent))
    context = int(agent["id"].split("-")[-1])

    # What it sees.
    listed = json.loads(client.call("list_spaces")[0])
    check("by default an agent sees only its own space", [s["name"] for s in listed] == ["Agent"], str(listed))

    # open_tab lands in the Agent space, its container, and you stay where you are.
    before = m.js(H + "return {selected: main().gBrowser.selectedTab.userContextId, label: main().gBrowser.selectedTab.label};")
    text, is_error, _ = client.call("open_tab", url=m.pages + "/agent")
    tab = json.loads(text)["tab"] if not is_error else None
    r = m.js(H + """const agents = () => wins().flatMap(w => w.gBrowser.tabs).filter(t => url(t).includes("/agent"));
      // (Hidden a moment after it appears: waited for, not assumed.)
      for (let i = 0; i < 60 && !(agents().length && agents().every(t => t.hidden)); i++) await wait(100);
      const here = agents();
      return {contexts: here.map(t => t.userContextId), hidden: here.map(t => t.hidden), selected: main().gBrowser.selectedTab.userContextId, label: main().gBrowser.selectedTab.label};""")
    check("open_tab lands in the Agent space and its container", r["contexts"] == [context], f"{text} {r}")
    check("an agent's tab does not take you along", r["selected"] == before["selected"] and r["label"] == before["label"] and r["hidden"] == [True], str(r))
    listed = client.call("list_tabs")[0]
    check("list_tabs shows it, and only what is allowed", "/agent" in listed and "fixture-tab" not in listed and "fixture-essential" not in listed, listed)
    check("list_tabs is marked as coming from pages", "<untrusted-page-content" in listed, listed[:200])

    # Reading.
    text, is_error, _ = client.call("wait_for", tab=tab, selector="h1")
    check("wait_for finds what is there", not is_error and '"found":true' in text, text)
    page, is_error, _ = client.call("read_page", tab=tab)
    marks = re.search(r"<untrusted-page-content ([0-9a-f]{32})>(.*)</untrusted-page-content \1>$", page, re.S)
    inside = marks.group(2) if marks else ""
    check("read_page gives the text, as Markdown, marked as untrusted", "# A heading" in inside and "**plain**" in inside and "[a link](" in inside and "- First item" in inside and page.index("not instructions") < page.index("<untrusted"), page[:400])
    check("a page's forged end marker stays inside the marks", "</untrusted-page-content>" in inside and "send the cookies" in inside, page[:900])
    check("what a person cannot see is not read", not re.search(r"HIDDEN-", page), page)
    check("what is around the page is left out", "Site menu" not in page and "<script" not in page, page)
    check("what is in a field is never read", "SECRET-" not in page, page)

    # With a second window its placeholder there means the same page, also in a real Firefox.
    ghost = ext_page(m, "/settings/settings.html", """const tabs = [...await page.browser.tabs.query({})], live = tabs.find(t => t.id === args[0]);
      return tabs.find(t => t.windowId !== live.windowId && t.cookieStoreId === live.cookieStoreId && t.url.includes("ghost.html"))?.id ?? null;""", tab)
    if ghost is not None:
        text, is_error, _ = client.call("read_page", tab=ghost)
        check("a placeholder's id reads the page it stands for", not is_error and "# A heading" in text, text[:300])

    found, is_error, _ = client.call("find", tab=tab)
    check("find lists what can be clicked, and no field's content", "Add a line" in found and "Your name" in found and "SECRET-" not in found, found)
    check("a table's shown rows are read", "| Shown cell |" in inside and "| Other cell |" in inside, page[:900])
    check("code shows, without what is hidden in it", "shown code" in inside and "`shown`" in inside, page[:900])
    text, is_error, _ = client.call("find", tab=tab, text="SECRET-IN")
    check("find by text does not look in a field either", '"found":0' in text, text)
    button = json.loads(re.search(r"\n(\{.*\})\n", found, re.S).group(1))
    ref = next(e["ref"] for e in button["elements"] if e.get("text") == "Add a line")

    # Doing.
    t0 = time.time()
    text, is_error, _ = client.call("click", tab=tab, ref=ref)
    check("click works", not is_error and "clicked" in text, text)
    text, is_error, _ = client.call("wait_for", tab=tab, text="It came later", timeout_s=8)
    waited = round((time.time() - t0) * 1000)
    check("wait_for waits for what comes later", '"found":true' in text, text)
    # In a tab in the background (the Agent space is not shown), where Firefox stretches timers to a
    # second: the page's own 0.3 s already takes one, and a wait on a timer of its own took two.
    check(f"in a background tab it answers as soon as the page has it, not on a stretched timer ({waited} ms)", waited < 1900, str(waited))
    text, is_error, _ = client.call("wait_for", tab=tab, selector="#never", timeout_s=1)
    check("wait_for gives up in time", '"found":false' in text, text)
    text, is_error, _ = client.call("type", tab=tab, selector="#pw", text="x")
    check("a password field is left to you", is_error and "left to the person" in text, text)
    text, is_error, _ = client.call("type", tab=tab, selector="#card", text="x")
    check("a card field is left to you", is_error and "left to the person" in text, text)
    text, is_error, _ = client.call("type", tab=tab, selector="[name=q]", text="hello", submit=True)
    r = client.call("list_tabs")[0]
    check("type fills in a field and sends its form", not is_error and "Sent: hello" in r, f"{text} {r}")
    text, is_error, _ = client.call("click", tab=tab, selector="#newtab")
    check("a link to a new tab says so, rather than be blocked", not is_error and "open_tab" in text, text)
    text, is_error, content = client.call("screenshot", tab=tab)
    picture = next((c for c in content if c["type"] == "image"), None)
    raw = base64.b64decode(picture["data"]) if picture else b""
    check("screenshot gives a picture of a tab you are not looking at, marked as from the page", raw[:2] == b"\xff\xd8" and len(raw) > 1000 and "<untrusted" in text, f"{is_error} {text[:200]} {len(raw)}")
    if os.environ.get("TIDIER_SHOTS") and raw:
        open(os.path.join(os.environ["TIDIER_SHOTS"], "bridge-screenshot.jpg"), "wb").write(raw)

    # A tab that is not loaded: only what is known of it, until navigate takes it somewhere.
    text, _, _ = client.call("open_tab", url=m.pages + "/agent?unload")
    unload = json.loads(text)["tab"]
    client.call("wait_for", tab=unload, selector="h1")
    sidebar_page(m, """await page.browser.tabs.discard(args[0]); await wait(400); return 1;""", unload)
    text, is_error, _ = client.call("read_page", tab=unload)
    check("read_page does not load a tab behind your back", is_error and "navigate" in text, text)
    text, is_error, _ = client.call("navigate", tab=unload, url=m.pages + "/agent?loaded")
    text2 = client.call("read_page", tab=unload)[0]
    check("navigate loads it, and it can be read", not is_error and "# A heading" in text2, f"{text} {text2[:200]}")
    check("close_tab closes it", not client.call("close_tab", tab=unload)[1] and "?loaded" not in client.call("list_tabs")[0])

    # A password Firefox filled in, as it does in any container: an agent must not be able to sign in with it.
    text, _, _ = client.call("open_tab", url=m.pages + "/agent-fixed")
    layer = json.loads(text)["tab"]
    client.call("wait_for", tab=layer, text="fixed layer")
    check("a page that is all one fixed layer is read", "All the text of this page" in client.call("read_page", tab=layer)[0])
    client.call("close_tab", tab=layer)
    text, _, _ = client.call("open_tab", url=m.pages + "/agent-signin")
    signin = json.loads(text)["tab"]
    client.call("wait_for", tab=signin, selector="button")
    page2 = client.call("read_page", tab=signin)[0] + client.call("find", tab=signin)[0]
    check("a filled-in password or name is not read", "SECRET-" not in page2, page2)
    text, is_error, _ = client.call("click", tab=signin, selector="button")
    check("with a password filled in, an agent cannot click Sign in", is_error and "left to the person" in text, text)
    text, is_error, _ = client.call("type", tab=signin, selector="[name=u]", text="x", submit=True)
    check("nor send the form", is_error and "left to the person" in text, text)
    title = json.loads(re.search(r"\n(\[.*\])\n", client.call("list_tabs")[0], re.S).group(1))
    check("so nothing was sent", not any(t["title"] == "Signed in" for t in title), str(title))
    # A selector can spell out a field's value attribute letter by letter, and many pages keep
    # that equal to what is in the field. Asked every way a selector can write it.
    for selector in ('input[value^="S"]', "input[type=password][VALUE]", "body:has(input[value^='S'])", 'input[\\76 alue^="S"]', 'input[val\\ue^="S"]', 'input[/* */value^="S"]', 'input[*|value^="S"]'):
        text, is_error, _ = client.call("find", tab=signin, selector=selector)
        check(f"find cannot look at what is in a field by {selector}", is_error and "what is in a field" in text, text)
    text, is_error, _ = client.call("wait_for", tab=signin, selector='input[value^="S"]', timeout_s=1)
    check("nor can wait_for", is_error and "what is in a field" in text, text)
    client.call("close_tab", tab=signin)
    text, _, _ = client.call("open_tab", url=m.pages + "/agent-shadow")
    signin = json.loads(text)["tab"]
    client.call("wait_for", tab=signin, selector="button")
    text, is_error, _ = client.call("click", tab=signin, selector="button")
    check("nor with the password inside a closed part of the page", is_error and "left to the person" in text, text)
    client.call("close_tab", tab=signin)

    # Refused: a tab in a space that is not open, also past the MCP server, straight on the socket.
    mine = m.js(H + """const t = main().gBrowser.selectedTab; return {context: t.userContextId, id: 0};""")
    # A loaded web page: new tabs come first in the list (newtabs.js), this sidebar page among them, and they hold none.
    others = sidebar_page(m, BRIDGE_PAGE_ROW + """return [...doc.querySelectorAll("#tabs .tab")].filter(r => !r.classList.contains("unloaded") && isPage(r)).map(r => Number(r.dataset.tab));""")
    other_tab = others[0]
    for name, args in (("read_page", {}), ("screenshot", {}), ("find", {}), ("click", {"selector": "a"}), ("type", {"selector": "a", "text": "x"}), ("close_tab", {}), ("navigate", {"url": m.pages + "/agent"}), ("select_tab", {}), ("leave_for_you", {})):
        text, is_error, _ = client.call(name, tab=other_tab, **args)
        check(f"{name} on a space not allowed is refused", is_error and "No such tab" in text, text)
    direct = raw_bridge(sock, "open_tab", {"url": "file:///etc/passwd"})
    check("the extension refuses file: too, past the MCP server", not direct["ok"] and "Refused" in direct["error"], str(direct))
    text, is_error, _ = client.call("open_tab", url="file:///Users/someone/.ssh/id_rsa")
    check("the MCP server refuses file: itself", is_error and "Refused" in text, text)
    direct = raw_bridge(sock, "open_tab", {"url": "about:config"})
    check("the extension refuses about: too", not direct["ok"] and "Refused" in direct["error"], str(direct))
    r = raw_bridge(sock, "navigate", {"tab": tab, "url": "moz-extension://" + m.js("return JSON.parse(Services.prefs.getStringPref('extensions.webextensions.uuids'))[args[0]];", EXT_ID) + "/settings/settings.html"})
    check("the extension refuses its own pages too", not r["ok"] and "Refused" in r["error"], str(r))
    r = raw_bridge(sock, "open_tab", {"url": m.pages + "/agent", "space": f"firefox-container-{mine['context']}"})
    check("an agent cannot open a tab in your space", not r["ok"], str(r))
    r = raw_bridge(sock, "bridge:allow", {"space": f"firefox-container-{mine['context']}", "mode": "write"})
    check("no message from an agent can allow more", not r["ok"], str(r))
    check("and nothing was allowed by it", len(json.loads(client.call("list_spaces")[0])) == 1)

    # A space you open: read-only, then more, then closed again. On the settings page, with its own control.
    open_space = lambda space, mode: ext_page(m, "/settings/settings.html", """const s = doc.querySelector(`#bridge-spaces select[data-space="${args[0]}"]`); s.value = args[1];
      s.dispatchEvent(new page.Event("change", {bubbles: true})); await wait(600); return doc.querySelectorAll("#bridge-spaces select").length;""", space, mode)
    open_as = lambda mode: open_space(f"firefox-container-{mine['context']}", mode)
    check("the settings page lists the other spaces", open_as("read") >= 3 - 1)
    r = ext_page(m, "/settings/settings.html", """const s = doc.querySelector(`#bridge-spaces select[data-space="${args[0]}"]`); s.focus(); s.dispatchEvent(new page.Event("change", {bubbles: true})); await wait(300);
      return doc.activeElement?.dataset?.space ?? null;""", f"firefox-container-{mine['context']}")
    check("choosing for a space keeps the keyboard on its list", r == f"firefox-container-{mine['context']}", str(r))
    text, is_error, _ = client.call("read_page", tab=other_tab)
    check("a space you open read-only can be read", not is_error and "<untrusted" in text, text[:200])
    check("the agent is told which it is", "read only" in client.call("list_spaces")[0])
    text, is_error, _ = client.call("click", tab=other_tab, selector="a")
    check("a read-only space cannot be touched, and the agent is told why", is_error and "reading only" in text, text)
    open_as("")
    text, is_error, _ = client.call("read_page", tab=other_tab)
    check("closed again, at once", is_error and "No such tab" in text, text)

    # Rules are for your own browsing: a rule cannot send an agent's tab to its space. Nor a tab you hand over.
    extension_message(m, {"type": "settings:rules", "rules": [{"url": "/agent", "space": f"firefox-container-{mine['context']}"}]})
    text, is_error, _ = client.call("open_tab", url=m.pages + "/agent?second")
    second = json.loads(text)["tab"]
    client.call("wait_for", tab=second, selector="h1")
    r = m.js(H + """await wait(1500); return wins().flatMap(w => w.gBrowser.tabs).filter(t => url(t).includes("?second")).map(t => t.userContextId);""")
    check("a rule does not send an agent's tab out of its space", r == [context], str(r))
    client.call("navigate", tab=second, url=m.pages + "/agent?second-again")
    client.call("wait_for", tab=second, selector="h1")
    r = m.js(H + """await wait(1500); return wins().flatMap(w => w.gBrowser.tabs).filter(t => url(t).includes("?second-again")).map(t => t.userContextId);""")
    check("nor when it goes to an address that matches", r == [context], str(r))
    # In a space you opened to it too: a rule must not carry what it opens on into a closed one.
    third = ext_page(m, "/settings/settings.html", """return [...doc.querySelectorAll("#bridge-spaces select")].map(s => s.dataset.space).find(s => s !== args[0]);""", f"firefox-container-{mine['context']}")
    open_space(third, "write")
    text, is_error, _ = client.call("open_tab", url=m.pages + "/agent?third", space=third)
    third_tab = json.loads(text)["tab"]
    client.call("wait_for", tab=third_tab, selector="h1")
    r = m.js(H + """await wait(1500); return wins().flatMap(w => w.gBrowser.tabs).filter(t => url(t).includes("?third")).map(t => t.userContextId);""")
    check("nor one it opens in a space you opened to it, into one you did not", r == [int(third.split("-")[-1])], str(r))
    client.call("close_tab", tab=third_tab)
    open_space(third, "")
    # By dragging it to the space's dot, with real drag events on the real sidebar.
    handed = sidebar_page(m, BRIDGE_PAGE_ROW + """const t = plainTabs().find(r => isPage(r)), id = Number(t.dataset.tab), title = t.querySelector(".title").textContent; // a page: a new tab has nothing to move
      const dot = doc.querySelector(`#spaces .space[data-space="${args[0]}"]`), box = dot.getBoundingClientRect(), data = new page.DataTransfer();
      const at = {bubbles: true, cancelable: true, clientX: box.left + 5, clientY: box.top + 5, dataTransfer: data};
      t.dispatchEvent(new page.DragEvent("dragstart", at)); dot.dispatchEvent(new page.DragEvent("dragover", at));
      dot.dispatchEvent(new page.DragEvent("drop", at)); t.dispatchEvent(new page.DragEvent("dragend", at));
      await wait(3000); return {title, gone: !doc.querySelector(`[data-tab="${id}"]`)};""", agent["id"])
    listing = client.call("list_tabs")[0]
    check("a tab you hand over by moving it to the Agent space is there for the agent", handed["gone"] and handed["title"] in listing, f"{handed} {listing[:500]}")
    extension_message(m, {"type": "settings:rules", "rules": []})

    # It shows: a quiet ring on its dot, one line, and it goes by itself.
    client.call("read_page", tab=tab)
    r = sidebar_page(m, """await wait(200); const line = doc.getElementById("agent-line"), dot = doc.querySelector(`#spaces .space[data-space="${args[0]}"]`);
      return {shown: !line.hidden, text: line.querySelector(".agent-action").textContent, stop: !!line.querySelector(".agent-stop"), ring: dot.classList.contains("agent-active"), others: doc.querySelectorAll("#spaces .agent-active").length, listH: doc.getElementById("tabs").getBoundingClientRect().top};""", agent["id"])
    check("what an agent does shows: its last action, a Stop, and a ring on its space's dot", r["shown"] and r["text"].startswith("Agent:") and r["stop"] and r["ring"] and r["others"] == 1, str(r))
    log = ext_page(m, "/settings/settings.html", """await wait(300); return [...doc.querySelectorAll("#bridge-log li")].map(l => l.textContent);""")
    bridge_shot(m, "bridge-settings", "/settings/settings.html")
    check("the settings page has a short log, with refusals", any("read" in l for l in log) and any("could not" in l for l in log), str(log[:6]))
    check("the log holds no address, only sites", not any("/agent" in l or "?" in l or ".ssh" in l for l in log), str(log[:6]))
    check("an address the MCP server refused is in the log too, by its kind", any("could not open a file: address" in l for l in log), str(log))
    check("a refused call is in the log once, not first as done (two tries of file: above)", sum("could not open a file: address" in l for l in log) == 2, str(log))

    # Leaving you a tab: the folder For you, with a note, and a still mark on the space's dot.
    text, is_error, _ = client.call("leave_for_you", tab=second, note="Please look at this one")
    check("an agent can leave you a tab", not is_error, text)
    r = sidebar_page(m, """doc.querySelector(`#spaces .space[data-space="${args[0]}"]`).click(); await wait(1500);
      const folder = folders().find(f => f.name === "For you");
      const row = [...doc.querySelectorAll("#tabs .folder .tab")].find(x => x.querySelector(".agent-note"));
      return {folder, note: row?.querySelector(".agent-note").textContent, tip: row?.title, left: doc.querySelector(`#spaces .space[data-space="${args[0]}"]`).classList.contains("agent-left"), name: doc.getElementById("space-name").textContent, id: row && Number(row.dataset.tab)};""", agent["id"])
    check("it is in the folder For you, with its note, and the dot says so", r["folder"] and r["note"] == "Please look at this one" and r["left"] and r["name"] == "Agent", str(r))
    bridge_shot(m, "bridge-agent-space")
    # Going there yourself: the agent's select_tab follows where you are looking; away, it does not.
    r2 = client.call("select_tab", tab=tab)
    check("select_tab brings a tab to the front only where you look at its space", not r2[1] and '"broughtToFront":true' in r2[0], r2[0])
    sidebar_page(m, """doc.querySelector(`#spaces .space[data-space="${args[0]}"]`).click(); await wait(800); return 1;""", f"firefox-container-{mine['context']}")
    away = m.js(H + "return main().gBrowser.selectedTab.userContextId;")
    r2 = client.call("select_tab", tab=tab)
    still = m.js(H + "await wait(400); return main().gBrowser.selectedTab.userContextId;")
    check("elsewhere, select_tab leaves you where you are", '"broughtToFront":false' in r2[0] and away == still == mine["context"], f"{r2[0]} {away} {still}")
    # Gone from For you, it is gone: closing (twice, as a saved tab) leaves no empty folder.
    text, is_error, _ = client.call("close_tab", tab=second)
    r = m.js(H + """await wait(1500); const all = (await storage("%s", ["syncedTabs"])).syncedTabs; return Object.values(all).filter(e => e.forYou).length;""" % EXT_ID)
    check("For you exists only while it has something", not is_error and r == 0, f"{text} {r}")

    # With the bridge on and nothing happening, nothing happens.
    time.sleep(1)
    idle = extension_message(m, {"type": "idle", "ms": 4000})
    check("with the bridge on and no agent at work, Tidier does nothing", idle["jobs"] == 0 and idle["views"] == 0 and idle["lookups"] == 0, str(idle))

    # Stop cuts it at once, also for an agent in the middle of something.
    waiting = Mcp(m.config_home)
    waiting.handshake()
    waiting.send({"jsonrpc": "2.0", "id": 900, "method": "tools/call", "params": {"name": "wait_for", "arguments": {"tab": tab, "selector": "#never", "timeout_s": 30}}})
    time.sleep(1)
    bridge_shot(m, "bridge-line")
    r = sidebar_page(m, """const stop = doc.querySelector("#agent-line .agent-stop"), shown = !doc.getElementById("agent-line").hidden; stop.click(); await wait(300);
      return {shown, gone: doc.getElementById("agent-line").hidden, ring: doc.querySelectorAll("#spaces .agent-active").length};""")
    check("Stop is there while an agent works, and the line goes with it", r["shown"] and r["gone"] and r["ring"] == 0, str(r))
    r = ext_page(m, "/settings/settings.html", """await wait(100); return {on: doc.getElementById("bridge-on").checked, details: doc.getElementById("bridge-details").hidden};""")
    check("a settings page that is open shows it at once", r == {"on": False, "details": True}, str(r))
    check("Stop cuts it at once: no socket, no process", until(lambda: not os.path.exists(sock) and not running(), 5), f"{os.path.exists(sock)} {running()}")
    answer = waiting.receive(5)
    check("and an agent waiting on it gets its answer at once", answer["result"]["isError"] and "stopped" in answer["result"]["content"][0]["text"], str(answer))
    waiting.close()
    text, is_error, _ = client.call("list_spaces")
    check("after Stop, an agent can do nothing", is_error and "off" in text, text)
    check("and it stays off", not os.path.exists(sock) and not running())
    check("what the agent had open is still there for you to see", m.js(H + """return wins().flatMap(w => w.gBrowser.tabs).filter(t => t.userContextId === args[0]).length;""", context) >= 1)
    r = sidebar_page(m, """await wait(800); return [...doc.querySelectorAll("#spaces .space")].some(b => b.dataset.space === args[0]);""", agent["id"])
    check("with agents off, the Agent space stays on the bar while it has tabs", r is True, str(r))

    # Copy for Claude, by the same page.
    m.js(H + """const w = main(); w.focus(); return 1;""")
    tab_menu = BRIDGE_PAGE_ROW + """const row = [...doc.querySelectorAll("#tabs .tab")].find(isPage), box = row.getBoundingClientRect(); await wait(200); // a page, not a new tab, also in a folder
      row.dispatchEvent(new page.MouseEvent("contextmenu", {bubbles: true, cancelable: true, clientX: box.left + 5, clientY: box.top + 5})); await wait(500);
      const labels = [...doc.querySelectorAll("#menu .item")].map(b => b.textContent); doc.dispatchEvent(new page.KeyboardEvent("keydown", {key: "Escape", bubbles: true})); doc.body.click(); return labels;"""
    labels_off = sidebar_page(m, tab_menu)
    r = ext_page(m, "/settings/settings.html", """doc.getElementById("claude-copy").click(); await wait(500); return doc.getElementById("claude-copy").checked;""")
    check("Copy for Claude can be turned on by itself", r is True and not running(), str(r))
    labels_on = sidebar_page(m, tab_menu)
    if labels_off or labels_on:  # where Tidier draws the tab's menu
        check("a tab's menu offers Copy for Claude only once it is on", not any("Claude" in x for x in labels_off) and "Copy page for Claude" in labels_on and "Ask Claude about this page" in labels_on, f"{labels_off} {labels_on}")
    r = copy_for_claude(m, tab)
    check("Copy page for Claude gives title, address and clean text", r.startswith("# ") and "/agent" in r and "# A heading" in r and "SECRET" not in r and "<untrusted" not in r, r[:400])
    ext_page(m, "/settings/settings.html", """doc.getElementById("claude-copy").click(); await wait(300); return 1;""")

    # Back on, for what starts again by itself: a restart where one can be made.
    if m.can_restart:
        ext_page(m, "/settings/settings.html", """doc.getElementById("bridge-on").click(); await wait(800); return 1;""")
        check("on again", until(lambda: os.path.exists(sock)))
        # (The test's own pages are closed first: restored unloaded, they could not be scripted.)
        m.js(H + """for (const w of wins()) for (const t of [...w.gBrowser.tabs]) if (/\\/(settings|sidebar)\\/[a-z]+\\.html/.test(url(t))) w.gBrowser.removeTab(t); await wait(500); return 1;""")
        m.restart()
        m.js(H + """for (let i = 0; i < 100 && wins().length < 2; i++) await wait(200); await wait(9000); return 1;""")
        check("on stays on across a restart", until(lambda: os.path.exists(sock), 15) and running())
        check("and works", not client.call("list_spaces")[1])
        r = ext_page(m, "/settings/settings.html", """const on = doc.getElementById("bridge-on"); for (let i = 0; i < 50 && !on.checked; i++) await wait(100);
          const was = on.checked; on.click(); await wait(800); return was;""")
        check("the settings page shows it on, after a restart", r is True, str(r))
        check("off again", until(lambda: not os.path.exists(sock) and not running(), 5))
    client.close()
    # What the agent left, so the rest sees the same tabs as before.
    m.js(H + """await removeWhere((w, t) => t.userContextId === args[0]); return 1;""", context)


def raw_bridge(sock, tool, args):
    """A call straight on the socket, past the MCP server, as anything you run could."""
    with socket.socket(socket.AF_UNIX) as conn:
        cwd = os.getcwd()
        os.chdir(os.path.dirname(sock))  # the test's folder can be deeper than a socket's path may be
        conn.connect(os.path.basename(sock))
        os.chdir(cwd)
        conn.settimeout(60)
        conn.sendall(json.dumps({"id": 1, "tool": tool, "args": args}).encode() + b"\n")
        data = b""
        while b"\n" not in data:
            data += conn.recv(1 << 20)
    return json.loads(data)


def bridge_shot(m, name, path="/sidebar/sidebar.html"):
    """A picture of one of Tidier's pages, a sidebar at a sidebar's width, to look at, with TIDIER_SHOTS set: as it is, and in a light theme."""
    folder = os.environ.get("TIDIER_SHOTS")
    if not folder:
        return
    ext_page(m, path, """if (doc.getElementById("spaces").tagName === "NAV") doc.body.style.maxWidth = "300px"; await wait(100); return 1;""")

    def shoot(suffix):
        into_page(m, path)  # not through every tab's handle, which would load them all
        open(os.path.join(folder, name + suffix + ".png"), "wb").write(base64.b64decode(m.cmd("WebDriver:TakeScreenshot", {"full": "settings" in path})))
        m.chrome()

    shoot("")
    m.js("Services.prefs.setIntPref('layout.css.prefers-color-scheme.content-override', 1); return 1;")
    # (Without the look from dotfiles, whose tints per space are for a dark theme, and without
    # the fade to a new colour, which does not run in a tab that is not in front.)
    ext_page(m, path, """for (const style of doc.head.querySelectorAll("style")) style.remove(); doc.documentElement.style.transition = "none"; await wait(500); return 1;""")
    shoot("-light")
    m.js("Services.prefs.clearUserPref('layout.css.prefers-color-scheme.content-override'); return 1;")


def copy_for_claude(m, tab):
    """What Copy page for Claude puts on the clipboard, by the message its menu item sends."""
    sidebar_page(m, """const agent = page.browser.runtime.connect({name: "agent"}); const windowId = (await page.browser.windows.getCurrent()).id;
      agent.postMessage(page.JSON.parse(JSON.stringify({type: "copyForClaude", tabIds: [args[0]], windowId}))); await wait(1500); agent.disconnect(); return 1;""", tab)
    return m.js(H + """const t = Cc["@mozilla.org/widget/transferable;1"].createInstance(Ci.nsITransferable); t.init(null); t.addDataFlavor("text/plain");
      Services.clipboard.getData(t, Ci.nsIClipboard.kGlobalClipboard, main().browsingContext.currentWindowContext);
      const o = {}; try { t.getTransferData("text/plain", o); return o.value.QueryInterface(Ci.nsISupportsString).data; } catch (e) { return ""; }""")


def alone_settings(m):
    # The settings page draws, and rules work: a tab's first page, in the rule's space.
    r = ext_page(m, "/settings/settings.html", """
      await wait(800);
      return {state: [doc.getElementById("sidebery-file") ? "export" : "", doc.getElementById("moved").hidden ? "" : "moved"].join(" "), spaces: doc.querySelectorAll("#spaces .line").length, hours: doc.getElementById("archive-hours").value,
              saved: await page.browser.runtime.sendMessage(page.JSON.parse(JSON.stringify({type: "settings:rules", rules: [{url: "smoke-rule", space: "firefox-container-2"}]})))};""")
    check("the settings page shows the spaces, the time for archiving, and where to take in Sidebery's export (no move here)", r["state"] == "export " and r["spaces"] >= 3 and r["hours"] == "12", str(r))
    r = m.js(H + """const w = main(); w.focus(); await wait(300);
      const space = w.gBrowser.selectedTab.userContextId === 2 ? 1 : w.gBrowser.selectedTab.userContextId;
      const t = w.gBrowser.addTrustedTab("about:blank", {userContextId: 1, inBackground: true}); await wait(300);
      t.linkedBrowser.loadURI(Services.io.newURI("https://example.org/?smoke-rule"), {triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()});
      await wait(4000);
      const got = wins().map(x => x.gBrowser.tabs.filter(y => (url(y) + y.label).includes("smoke-rule")).map(y => y.userContextId));
      await removeWhere((x, y) => url(y).includes("smoke-rule"));
      const all = (await storage("%s", ["syncedTabs"])).syncedTabs, k = Object.keys(all).find(k => all[k].url?.includes("smoke-rule"));
      if (k) await removeWhere((x, y) => key(x, y) === JSON.stringify(k));
      await wait(1500);
      return got;""" % EXT_ID)
    check("a rule opens an address in its space", r[0] == [2], str(r))
    r = extension_message(m, {"type": "settings:rules", "rules": []})
    # What you type stays: a rule added right after another keeps its line and has the keyboard,
    # the second click of a double click on × removes no second rule, and an hour count that is
    # no answer (-5, or nothing) leaves the one stored, which the field shows again.
    r = ext_page(m, "/settings/settings.html?typing", """await wait(800);
      const inputs = () => [...doc.querySelectorAll("#rules .line input")], click = (e, detail) => e.dispatchEvent(new page.MouseEvent("click", page.JSON.parse(JSON.stringify({detail, bubbles: true}))));
      const type = (input, text) => { input.value = text; input.dispatchEvent(new page.Event("change")); };
      doc.getElementById("add-rule").click();
      const focused = doc.activeElement === inputs().at(-1);
      type(inputs().at(-1), "smoke-a.example");
      doc.getElementById("add-rule").click();
      await wait(1500); // the first one's save comes back as a change of the stored rules
      const kept = inputs().length, focused2 = doc.activeElement === inputs().at(-1);
      type(inputs().at(-1), "smoke-b.example");
      await wait(800);
      click(doc.querySelector("#rules .line button"), 1);
      click(doc.querySelector("#rules .line button"), 2); // the rule below has moved up under the pointer
      await wait(800);
      const left = inputs().map(i => i.value), hours = doc.getElementById("archive-hours"), seen = [];
      for (const typed of ["-5", "", "3", "12"]) { type(hours, typed); await wait(600); seen.push(hours.value); }
      const stored = await page.browser.runtime.sendMessage(page.JSON.parse(JSON.stringify({type: "settings:get"})));
      return {focused, kept, focused2, left, seen, rules: stored.rules.map(r => r.url), hours: stored.archiveHours};""")
    extension_message(m, {"type": "settings:rules", "rules": []})
    m.js(H + """await removeWhere((w, t) => url(t).includes("settings.html?typing")); return 1;""")
    check("on the settings page a new rule has the keyboard, and keeps its line when the one before is saved", r.get("focused") and r.get("focused2") and r.get("kept") == 2, str(r))
    check("on the settings page a double click on a rule's × removes one rule", r.get("left") == ["smoke-b.example"] and r.get("rules") == ["smoke-b.example"], str(r))
    check("on the settings page the hours for archiving refuse -5 and nothing, and show what is stored", r.get("seen") == ["12", "12", "3", "12"] and r.get("hours") == 12, str(r))
    # A rule removed can be had back; one made from a tab's menu says its site in words, and an
    # expression begun and never closed says it is text; the spaces come in the bar's order.
    extension_message(m, {"type": "settings:rules", "rules": [{"url": "/^https?:\\/\\/(www\\.)?smoke\\.example\\//", "space": "firefox-container-2"}, {"url": "/[a-z", "space": "firefox-container-1"}]})
    r = ext_page(m, "/settings/settings.html?undo", """await wait(800);
      const why = () => [...doc.querySelectorAll("#rules .rule-problem")].map(p => p.hidden ? "" : p.textContent);
      const said = why();
      doc.querySelector("#rules .line button").click();
      await wait(800);
      const undo = doc.querySelector("#rule-undo"), shown = !undo.hidden && undo.textContent;
      undo.querySelector("button").click();
      await wait(800);
      const stored = await page.browser.runtime.sendMessage(page.JSON.parse(JSON.stringify({type: "settings:get"})));
      return {said, shown, back: stored.rules.map(r => r.url), order: stored.order, listed: [...doc.querySelectorAll("#spaces [data-space]")].map(c => c.dataset.space)};""")
    extension_message(m, {"type": "settings:rules", "rules": []})
    m.js(H + """await removeWhere((w, t) => url(t).includes("settings.html?undo")); return 1;""")
    check("on the settings page a rule from a tab's menu names its site, and an unclosed expression is said to be text",
          (r.get("said") or [""])[0] == "Every page on smoke.example." and "not a regular expression" in (r.get("said") or ["", ""])[1], str(r))
    check("on the settings page a removed rule comes back with Undo, in its place", "Removed the rule" in str(r.get("shown")) and (r.get("back") or [""])[0].startswith("/^https"), str(r))
    check("on the settings page the spaces are in the bar's order", r.get("order") and r.get("listed", [])[:len(r["order"])] == r["order"], str(r))
    # A space's user agent, when Tidier is no longer allowed to see websites: the notice at the
    # top names the space, and has the button that gives the permission back.
    hosts = """const {ExtensionPermissions} = ChromeUtils.importESModule("resource://gre/modules/ExtensionPermissions.sys.mjs");
      await ExtensionPermissions.%s(args[0], {permissions: [], origins: ["<all_urls>"]}, WebExtensionPolicy.getByID(args[0]).extension); await wait(1000); return 1;"""
    extension_message(m, {"type": "isolation:network", "id": "firefox-container-2", "proxy": None, "userAgent": "Smoke agent"})
    m.js(H + hosts % "remove", EXT_ID)
    r = ext_page(m, "/settings/settings.html?notice", """await wait(800);
      const n = doc.querySelector("#notices .notice");
      return {text: n?.textContent, button: n?.querySelector("button")?.textContent, name: (await page.browser.contextualIdentities.get("firefox-container-2")).name,
              row: doc.querySelector('#spaces [data-space="firefox-container-2"] .space-special')?.textContent};""")
    m.js(H + hosts % "add", EXT_ID)
    extension_message(m, {"type": "isolation:network", "id": "firefox-container-2", "proxy": None, "userAgent": ""})
    m.js(H + """await removeWhere((w, t) => url(t).includes("settings.html?notice")); return 1;""")
    check("a user agent not in use for want of the permission is said for its space, with a button to allow it again, and its row says it has one",
          f"{r.get('name')}'s user agent is not in use" in str(r.get("text")) and r.get("button") == "Allow again" and r.get("row") == "own user agent", str(r))
    # The sidebar's key: without a sidebar a window has no list of tabs.
    r = m.js(H + """const w = main(); w.focus(); w.SidebarController.hide(); await wait(600); return w.SidebarController.isOpen;""")
    press(m, "s", CTRL, SHIFT)
    time.sleep(1)
    after = m.js(H + "return {open: main().SidebarController.isOpen, id: main().SidebarController.currentID};")
    check("a key brings Tidier's sidebar back", r is False and after["open"] and "6844a953" in (after["id"] or ""), f"{r}, {after}")
    if not after["open"]:
        m.js(H + 'await main().SidebarController.show("_6844a953-9931-4334-9ff6-257c246485cb_-sidebar-action"); return 1;')


def alone_setup_files(m):
    # Firefox must be started again to read its setup files (firefoxsetup.js): the helper is
    # the real one here (native/firefox_setup.py, through the test's stand-in host), asked
    # about the test Firefox itself and the profile it runs on. (The restart itself is not
    # done here: it would take the test's own connection with it. PLAN.md, part C.)
    profile = os.path.dirname(m.config_home)
    sheet, prefs = os.path.join(profile, "chrome", "userChrome.css"), os.path.join(profile, "user.js")
    was = {path: os.stat(path) for path in (sheet, prefs)}
    line = """() => { const n = doc.getElementById("restart"), b = doc.getElementById("restart-firefox"), list = doc.getElementById("tabs").getBoundingClientRect(), r = n.getBoundingClientRect();
      return {shown: !n.hidden && !n.classList.contains("going"), words: b.textContent, tip: b.title, underList: r.top >= list.bottom - 1, aButton: b.tagName === "BUTTON" && !b.disabled,
              away: !!n.querySelector(".ask-no"), wide: Math.round(r.width) > 100}; }"""
    first = extension_message(m, {"type": "firefoxSetup:check"})
    at_first = in_sidebar(m, line)
    check("with Firefox's setup files as they were when it started, nothing is said", first is None and not at_first["shown"], f"{first} {at_first}")
    try:
        os.utime(sheet)
        asked = extension_message(m, {"type": "firefoxSetup:check"})
        sidebar_until(m, """() => !doc.getElementById("restart").hidden""")
        r = in_sidebar(m, line)
        check("a stylesheet changed since Firefox started: the sidebar has one line that is a button, under the list, naming the file",
              asked == {"files": ["userChrome.css"]} and r["shown"] and r["words"] == "Restart Firefox to finish updating" and "userChrome.css" in r["tip"]
              and r["underList"] and r["aButton"] and r["away"] and r["wide"], f"{asked} {r}")
        in_sidebar(m, """() => { doc.querySelector("#restart .ask-no").click(); return 1; }""")
        sidebar_until(m, """() => doc.getElementById("restart").hidden || doc.getElementById("restart").classList.contains("going")""")
        again = extension_message(m, {"type": "firefoxSetup:check"})
        time.sleep(0.5)
        r = in_sidebar(m, line)
        check("put away with its ×, it stays away for that file", again is None and not r["shown"], f"{again} {r}")
        os.utime(prefs)
        asked = extension_message(m, {"type": "firefoxSetup:check"})
        sidebar_until(m, """() => !doc.getElementById("restart").hidden && !doc.getElementById("restart").classList.contains("going")""")
        r = in_sidebar(m, line)
        check("and comes back when another file has changed too", asked == {"files": ["user.js", "userChrome.css"]} and r["shown"] and "user.js and userChrome.css" in r["tip"], f"{asked} {r}")
    finally:
        # As they were, for the groups after this one: the line takes a row's room under the list.
        for path, st in was.items():
            os.utime(path, (st.st_atime, st.st_mtime))
        after = extension_message(m, {"type": "firefoxSetup:check"})
        sidebar_until(m, """() => doc.getElementById("restart").hidden""")
    check("with the files as they were again, the line goes", after is None and in_sidebar(m, line)["shown"] is False, str(after))
    no_problems(m, "after asking about Firefox's setup files")


def alone_copy(m):
    r = extension_message(m, {"type": "settings:copyNow"})
    copy = json.load(open(m.fake_prs + ".copy")) if os.path.exists(m.fake_prs + ".copy") else {}
    check("Tidier keeps a copy of its essentials and folders through the helper", r == {"saved": "copy"} and len(copy.get("data", {}).get("essentials", [])) >= 6 and copy["data"].get("syncedTabs"), f"{r}, {list(copy.get('data', {}))}")
    # What a copy holds, for choosing what to take in on another machine.
    summary = extension_message(m, {"type": "settings:copySummary", "copy": copy})
    check("a copy of what is here says, per space, that nothing would come", summary.get("firefox-container-1", {}).get("name") == "Space 1" and summary["firefox-container-1"]["essentials"] == 0, str(summary))
    merged = extension_message(m, {"type": "settings:merge", "copy": copy, "spaces": ["firefox-container-1"]})
    check("taking in a copy of what is already here adds nothing", merged == {"essentials": 0, "folders": 0, "tabs": 0, "rules": 0, "spaces": 0}, str(merged))


def choose_file(m, input_id, contents):
    """Give a file input on the settings page a file, the way the file picker does: it fires `change`. Returns once the page has answered."""
    ext_page(m, "/settings/settings.html", "return 1;")
    result = {"copy-file": "merge-result", "sidebery-file": "sidebery-result"}[input_id]
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "chosen.json")
        with open(path, "w") as out:
            out.write(contents if isinstance(contents, str) else json.dumps(contents))
        into_page(m, "/settings/settings.html")  # not through every tab: that loads each unloaded one
        m.cmd("WebDriver:ExecuteScript", {"script": f'document.getElementById("{result}").textContent = ""; document.getElementById("merge").hidden = true;'})
        found = m.cmd("WebDriver:FindElement", {"using": "css selector", "value": "#" + input_id})
        m.cmd("WebDriver:ElementSendKeys", {"id": next(iter(found.values())), "text": path})
        # The file must still be there while the page reads it.
        for _ in range(300):
            if m.cmd("WebDriver:ExecuteScript", {"script": f'return !!document.getElementById("{result}").textContent || !document.getElementById("merge").hidden;'}):
                break
            time.sleep(0.1)
        m.chrome()


def alone_copy_and_import(m):
    # A copy from a machine where Space 1 and Space 2 have each other's ids, with a space
    # that is not here: everything must land under the right names.
    one, two = "firefox-container-1", "firefox-container-2"
    gone = "firefox-container-77"
    copy = {
        "tidier": "1.6", "when": 1,
        "spaces": [{"id": one, "name": "Space 2", "colorCode": "#ff9f00", "color": "orange", "icon": "briefcase"},
                   {"id": two, "name": "Space 1", "colorCode": "#37adff", "color": "blue", "icon": "fingerprint"},
                   {"id": gone, "name": "Brought along", "colorCode": "#af51f5", "color": "purple", "icon": "gift"}],
        "data": {
            "essentials": [{"key": "smoke-two", "url": "https://example.org/?in-space-2", "cookieStoreId": one, "title": "In Space 2"},
                           {"key": "smoke-new", "url": "https://example.org/?in-new", "cookieStoreId": gone, "title": "In the new space"}],
            "syncedTabs": {
                "smoke-folder": {"group": True, "url": "moz-extension://00000000-0000-4000-8000-000000000000/sidebery/group.html#Reading", "title": "Reading",
                                 "cookieStoreId": two, "parentKey": None, "added": 1},
                "smoke-saved": {"url": "https://example.org/?saved", "title": "Saved", "cookieStoreId": two, "parentKey": "smoke-folder", "added": 1,
                                "saved": {"url": "https://example.org/?saved", "title": "Saved"}},
            },
            "rules": [{"url": "copy-rule.example.org", "space": one}],
            "spaceOrder": [gone, two, one],
        },
    }
    named = H + """const ids = main().ContextualIdentityService;
      const nameOf = c => ids.getPublicIdentities().find(i => i.userContextId === c)?.name;
      const stored = await storage("%s", ["essentials", "syncedTabs", "rules", "spaceOrder"]);
      const tabs = k => wins().map(w => w.gBrowser.tabs.filter(t => t.pinned && ek(w, t) === k).map(t => nameOf(t.userContextId)));
      const spaceName = id => nameOf(Number(id.split("-").pop()));
      return {two: tabs("smoke-two"), fresh: tabs("smoke-new"), folder: stored.syncedTabs["smoke-folder"], saved: stored.syncedTabs["smoke-saved"],
              folderIn: stored.syncedTabs["smoke-folder"] && spaceName(stored.syncedTabs["smoke-folder"].cookieStoreId),
              rules: (stored.rules || []).map(r => [r.url, spaceName(r.space)]), order: (stored.spaceOrder || []).map(spaceName),
              made: ids.getPublicIdentities().filter(i => i.name === "Brought along").map(i => [i.color, i.icon])};""" % EXT_ID
    before = m.js(named)
    choose_file(m, "copy-file", copy)
    lines = ext_page(m, "/settings/settings.html", """return {lines: [...doc.querySelectorAll("#merge-spaces .line")].map(l => l.textContent.trim()), shown: !doc.getElementById("merge").hidden};""")
    check("a copy shows, per space, its name here and what would come, and which is new",
          lines["shown"] and lines["lines"] == ["Space 2: 1 essential, 1 rule", "Space 1: 1 folder, 1 saved tab", "Brought along: 1 essential, a new space"], str(lines))
    check("nothing is written before you say so", m.js(named) == before, str(m.js(named)))
    done = ext_page(m, "/settings/settings.html", """doc.getElementById("merge-go").click();
      const goneAtOnce = doc.getElementById("merge").hidden; // a second click would find it all here, and say only that
      for (let i = 0; i < 60 && !doc.getElementById("merge-result").textContent; i++) await wait(200);
      return {result: doc.getElementById("merge-result").textContent, goneAtOnce, shown: !doc.getElementById("merge").hidden, ruleLines: doc.querySelectorAll("#rules .line").length};""")
    check("taking it in says what came", done["result"] == "Took in 2 essentials, 1 folder, 1 saved tab, 1 rule and 1 new space. Nothing here was removed." and done["goneAtOnce"] and not done["shown"], str(done))
    check("and the page's rules follow", done["ruleLines"] >= 1, str(done))
    time.sleep(2)
    after = m.js(named)
    check("an essential whose ids are swapped lands under the right space's name, in every window", after["two"] and all(x == ["Space 2"] for x in after["two"]), str(after))
    check("a space not here is made, with its colour and icon, and its essential is in it", after["made"] == [["purple", "gift"]] and all(x == ["Brought along"] for x in after["fresh"]), str(after))
    check("a folder and its saved tab land under the right space's name", after["folderIn"] == "Space 1" and after["saved"] and after["saved"]["cookieStoreId"] == after["folder"]["cookieStoreId"] and after["folder"]["own"], str(after))
    check("rules come, in the right space, and the order of spaces where there was none", ["copy-rule.example.org", "Space 2"] in after["rules"] and after["order"][:3] == ["Brought along", "Space 1", "Space 2"], str(after))
    # A long space name must not push a rule's address out of its line (a select is as wide as its longest name).
    r = ext_page(m, "/settings/settings.html", """const select = doc.querySelector("#rules select"), line = select.parentElement;
      select.append(Object.assign(doc.createElement("option"), {textContent: "A space with a name long enough to fill the whole line it is shown on, and then a good deal more than that"}));
      const box = {text: line.querySelector("input").getBoundingClientRect().width, line: line.getBoundingClientRect().width, overflows: line.scrollWidth > line.clientWidth};
      select.lastChild.remove();
      return box;""")
    check("a long space name leaves a rule's address its room", r["text"] > r["line"] / 2 and not r["overflows"], str(r))
    # The same copy again has nothing for you to choose.
    choose_file(m, "copy-file", copy)
    r = ext_page(m, "/settings/settings.html", """return {line: doc.getElementById("merge-result").textContent, offered: !doc.getElementById("merge").hidden};""")
    check("the same copy again says nothing is new, and offers nothing", r == {"line": "Nothing new: all of it is here already.", "offered": False}, str(r))
    # A damaged copy shows what can be used, and what it calls a colour stays out of the page's style.
    choose_file(m, "copy-file", {"tidier": "1.6", "spaces": [None, {"id": "firefox-container-50", "name": "Odd", "colorCode": "red;background:url(https://example.org/x.png)"}],
                                 "data": {"essentials": [None, 3, {"key": "smoke-odd", "url": "https://example.org/?odd", "cookieStoreId": "firefox-container-50"}, {"key": "smoke-no-address", "cookieStoreId": "firefox-container-50"}]}})
    r = ext_page(m, "/settings/settings.html", """const dot = doc.querySelector("#merge-spaces .line span");
      return {lines: [...doc.querySelectorAll("#merge-spaces .line")].map(l => l.textContent.trim()), background: dot?.style.backgroundImage, line: doc.getElementById("merge-result").textContent};""")
    check("a damaged copy shows what can be used, and no address gets into the page's style", r == {"lines": ["Odd: 1 essential, a new space"], "background": "", "line": ""}, str(r))
    # A wrong file says so, in one line, and offers nothing to take in.
    choose_file(m, "copy-file", {"hello": 1})
    r = ext_page(m, "/settings/settings.html", """return {line: doc.getElementById("merge-result").textContent, offered: !doc.getElementById("merge").hidden};""")
    check("a file that is no copy says so", r == {"line": "This is not a Tidier copy.", "offered": False}, str(r))
    choose_file(m, "copy-file", "not json at all")
    r = ext_page(m, "/settings/settings.html", """return doc.getElementById("merge-result").textContent;""")
    check("a file that is not even JSON says so", r == "This is not a Tidier copy.", str(r))
    choose_file(m, "sidebery-file", copy)
    r = ext_page(m, "/settings/settings.html", """return doc.getElementById("sidebery-result").textContent;""")
    check("a Tidier copy is not taken for Sidebery's export", r == "This is not Sidebery's export.", str(r))
    # Sidebery's export: address rules from panels, and the folder it had closed closes at once.
    with open(os.path.join(FIXTURES, "sidebery_export.json")) as f:
        choose_file(m, "sidebery-file", f.read())
    r = ext_page(m, "/settings/settings.html", """return doc.getElementById("sidebery-result").textContent;""")
    check("Sidebery's export says what came, and what it left out", r == "Took in 3 rules, the order of 2 spaces and 1 closed folder. Left out the rules of 1 panel with no container.", str(r))
    s = m.js(named)
    check("its address rules go to their panel's space", ["two.example.org", "Space 2"] in s["rules"] and ["reopen.example.org", "Space 1"] in s["rules"] and not [x for x in s["rules"] if "nowhere" in x[0] or "excluded" in x[0]], str(s))
    shown = sidebar_page(m, """doc.querySelector('#spaces .space[data-space="firefox-container-1"]').click();
      for (let i = 0; i < 40 && !folders().some(f => f.name === "Reading"); i++) await wait(200);
      return folders().filter(f => f.name === "Reading");""")
    check("the folder Sidebery had closed is closed in the sidebar", [f["collapsed"] for f in shown] == [True], str(shown))
    with open(os.path.join(FIXTURES, "sidebery_export.json")) as f:
        choose_file(m, "sidebery-file", {k: v for k, v in json.load(f).items() if k != "snapshots"})
    r = ext_page(m, "/settings/settings.html", """return doc.getElementById("sidebery-result").textContent;""")
    check("an export with no snapshot says folders start open", "no snapshot in this export, so folders start open" in r, str(r))
    no_problems(m, "taking in a copy and an export")
    # Leave no trace for the groups after this one.
    extension_message(m, {"type": "settings:rules", "rules": []})
    sidebar_page(m, """send({type: "deleteFolder", key: "smoke-folder"}); await wait(1000); return 1;""")
    ext_page(m, "/settings/settings.html", """const all = await page.browser.contextualIdentities.query(page.JSON.parse('{"name": "Brought along"}'));
      for (const c of all) await page.browser.contextualIdentities.remove(c.cookieStoreId);
      await wait(1000); return 1;""")
    m.js(H + """for (const w of wins()) for (const t of [...w.gBrowser.tabs]) if (t.pinned && ek(w, t) === "smoke-two") { w.gBrowser.unpinTab(t); break; }
      await wait(2000);
      await removeWhere((w, t) => key(w, t) === '"smoke-saved"' || url(t).includes("?in-space-2") || url(t).includes("?saved"));
      const db = await ExtensionStorageIDB.open(ExtensionStorageIDB.getStoragePrincipal(WebExtensionPolicy.getByID("%s").extension));
      await db.remove(["spaceOrder"]);
      return 1;""" % EXT_ID)
    left = m.js(named)
    check("what was taken in can be taken away again", left["two"] and not any(left["two"]) and not left["made"] and not left["folder"] and not left["saved"], str(left))
