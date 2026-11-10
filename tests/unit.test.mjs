// Unit tests for the logic that needs no Firefox: what closing a saved tab means, when a
// tab is saved, and rules about the repository. Runs in well under a second:
//
//     node --test        (in this repo; it finds the *.test.mjs files)
//
// common.js is loaded as the extension loads it (a plain script), with a fake `browser`.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import vm from "node:vm";

// --- common.js with a fake browser -----------------------------------------
function loadCommon() {
  const on = { addListener() {} };
  const browser = {
    windows: { WINDOW_ID_NONE: -1, getLastFocused: async () => ({ focused: false }), onFocusChanged: on, onRemoved: on },
    tabs: { query: async () => [], onMoved: on, onRemoved: on },
    sessions: { onChanged: on },
    alarms: { onAlarm: on },
    storage: { local: { get: async () => ({}), set: async () => {} } },
    runtime: { getURL: p => "moz-extension://tidier/" + p },
  };
  const context = vm.createContext({ browser, console, setTimeout, clearTimeout, URL });
  vm.runInContext(readFileSync(new URL("../common.js", import.meta.url), "utf8"), context);
  return context;
}

// Arrays made inside common.js belong to its own context; copy them for assert.
const plain = x => JSON.parse(JSON.stringify(x));

// --- The background scripts share one scope --------------------------------
test("no two background scripts define the same top-level name", () => {
  // They are plain scripts (manifest.json, background.scripts): a function
  // defined again in a later script silently replaces the earlier one.
  const manifest = JSON.parse(readFileSync(new URL("../manifest.json", import.meta.url), "utf8"));
  const seen = new Map(), twice = [];
  for (const file of manifest.background.scripts) {
    const src = readFileSync(new URL("../" + file, import.meta.url), "utf8");
    for (const [, name] of src.matchAll(/^(?:async\s+)?(?:function\*?|const|let|var|class)\s+([A-Za-z_$][\w$]*)/gm)) {
      if (seen.has(name)) twice.push(`${name} (${seen.get(name)}, ${file})`);
      else seen.set(name, file);
    }
  }
  assert.deepEqual(twice, []);
});

// The sidebar's scripts are plain scripts in one page too (sidebar/sidebar.html), where a
// name declared twice with const or let stops the second script with a SyntaxError.
test("no two of the sidebar's scripts define the same top-level name", () => {
  const page = readFileSync(new URL("../sidebar/sidebar.html", import.meta.url), "utf8");
  const seen = new Map(), twice = [];
  for (const [, file] of page.matchAll(/<script src="([^"]+)"/g)) {
    const src = readFileSync(new URL("../sidebar/" + file, import.meta.url), "utf8");
    for (const [, name] of src.matchAll(/^(?:async\s+)?(?:function\*?|const|let|var|class)\s+([A-Za-z_$][\w$]*)/gm)) {
      if (seen.has(name)) twice.push(`${name} (${seen.get(name)}, ${file})`);
      else seen.set(name, file);
    }
  }
  assert.deepEqual(twice, []);
});

// --- Saved tabs -----------------------------------------------------------
test("closing a tab: saved tabs are unloaded, unloaded ones and ordinary tabs closed", () => {
  const { closeAction } = loadCommon();
  const close = o => closeAction({ inFolder: true, liveFolder: false, unloaded: false, ...o });
  assert.equal(close({}), "unload");                           // ⌘W on a loaded tab in a folder
  assert.equal(close({ unloaded: true }), "close");            // × on its placeholder: removed for good
  assert.equal(close({ inFolder: false }), "close");           // an ordinary tab, or one dragged out of its folder
  assert.equal(close({ liveFolder: true }), "close");          // a pull request: the search decides
});

test("a tab gets its saved address when it comes into a folder, and loses it when it leaves", () => {
  const { noteSaved, storedInFolder } = loadCommon();
  const all = {
    F: { group: true, own: true, name: "F" },
    a: { parentKey: "F", url: "https://example.org/board", title: "Board" },
    b: { parentKey: "a", url: "https://example.org/b", title: "B" },      // below a tab in the folder
    p: { parentKey: "F", url: "https://github.com/x/pull/1", liveFolder: "prs" },
    o: { parentKey: null, url: "https://example.org/o", title: "O" },
  };
  noteSaved(all);
  assert.deepEqual(plain(all.a.saved), { url: "https://example.org/board", title: "Board" });
  assert.ok(all.b.saved && !all.p.saved && !all.o.saved && !all.F.saved);
  all.a.url = "https://example.org/issue-1";                         // browsing on keeps the saved address
  noteSaved(all);
  assert.equal(all.a.saved.url, "https://example.org/board");
  all.a.parentKey = null;                                            // dragged out
  noteSaved(all);
  assert.ok(!all.a.saved && !all.b.saved && !storedInFolder(all, "b"));
});

// --- Releases ---------------------------------------------------------------
test("the documents stay out of the signed extension, so changing them is no release", () => {
  const release = readFileSync(new URL("../tools/release.py", import.meta.url), "utf8");
  const exclude = release.match(/^EXCLUDE = \((.*)\)$/m)[1];
  for (const file of readdirSync(new URL("../", import.meta.url)).filter(f => f.endsWith(".md"))) {
    assert.ok(exclude.includes(`"${file}"`), `${file} would go into the extension`);
  }
});

test("a green run on main releases, whatever started it", () => {
  // A run started by hand or by the schedule cancels a push's run, so a gate on
  // event == 'push' would leave that commit unreleased, with nothing red.
  const release = readFileSync(new URL("../.github/workflows/release.yml", import.meta.url), "utf8");
  assert.ok(!/workflow_run\.event == 'push'/.test(release));
  assert.match(release, /workflow_run\.event != 'pull_request'/);
});

// --- Updates must never wait for a click ----------------------------------------------
test("the manifest asks for no new permission that would hold updates", () => {
  // Firefox holds an update that adds a permission on its list until it is approved, with
  // only a badge to show it: every later release then silently stops arriving. New ones
  // go in optional_permissions, asked for when needed.
  const manifest = JSON.parse(readFileSync(new URL("../manifest.json", import.meta.url), "utf8"));
  const allowed = ["tabs", "sessions", "storage", "cookies", "nativeMessaging", "alarms", "clipboardWrite",
    "contextualIdentities", "menus", "menus.overrideContext"]; // the prompts already approved, and those without one
  assert.deepEqual(manifest.permissions.filter(p => !allowed.includes(p)), []);
});

test("access to websites is asked for as every website, never with local files", () => {
  // "<all_urls>" also lists "Access local files on your computer" in about:addons, which
  // nothing here uses. Asked for or looked at, it is "*://*/*"
  // (http, https and their web sockets); a filter of events may still say "<all_urls>".
  const manifest = JSON.parse(readFileSync(new URL("../manifest.json", import.meta.url), "utf8"));
  assert.ok(manifest.optional_permissions.includes("*://*/*") && !manifest.optional_permissions.includes("<all_urls>"));
  const files = readdirSync(new URL("..", import.meta.url), { recursive: true }).filter(f => f.endsWith(".js") && !/^(tests|node_modules|\.git|\.claude)\b/.test(f));
  assert.ok(files.includes("isolation.js") && files.some(f => f.startsWith("settings")));
  for (const file of files) {
    const text = readFileSync(new URL("../" + file, import.meta.url), "utf8");
    assert.ok(!/origins:\s*\[[^\]]*<all_urls>/.test(text), `${file} asks for <all_urls>`);
  }
});

test("Tidier speaks to no other extension: it takes no message from one, sends none, and may not see which are installed", () => {
  // Beside Sidebery it asked for `management`, to see whether Sidebery was on. Nothing needs
  // that now, and an extension that listens to others takes orders from whatever else is
  // installed. A message from elsewhere reaches only onMessageExternal and onConnectExternal,
  // so with neither there is no way in; the README's list of rights says the same.
  const manifest = JSON.parse(readFileSync(new URL("../manifest.json", import.meta.url), "utf8"));
  const rights = [...manifest.permissions, ...manifest.optional_permissions];
  assert.ok(!rights.includes("management") && !("externally_connectable" in manifest) && !("content_scripts" in manifest), rights.join());
  const files = readdirSync(new URL("..", import.meta.url), { recursive: true }).filter(f => f.endsWith(".js") && !/^(tests|tools|node_modules|\.git|\.claude)\b/.test(f));
  assert.ok(files.includes("moveover.js") && files.some(f => f.startsWith("sidebar")));
  for (const file of files) {
    const text = readFileSync(new URL("../" + file, import.meta.url), "utf8");
    assert.doesNotMatch(text, /onMessageExternal|onConnectExternal|browser\.management\b/, file);
    // To another extension a message is sent by its ID as the first of two or more arguments.
    assert.doesNotMatch(text, /runtime\.(sendMessage|connect)\(\s*["'`{][^)]*@|runtime\.(sendMessage|connect)\(\s*[A-Z_]+_ID\b/, file);
  }
  // Every right the manifest lists is in the README's list, and nothing else is.
  const readme = readFileSync(new URL("../README.md", import.meta.url), "utf8");
  const listed = [...readme.slice(readme.indexOf("## What Tidier may do in the browser")).split(/\n## /)[0].matchAll(/^\| `([^`]+)`/gm)].map(m => m[1]);
  assert.deepEqual(listed.sort(), rights.sort());
});

// Packages built side by side each add helpers to the smoke test, and in Python the later
// `def` silently replaces the first: the first package's checks then call the wrong one.
test("the smoke test defines no top-level function or constant twice", () => {
  const src = readFileSync(new URL("smoke.py", import.meta.url), "utf8");
  const names = [...src.matchAll(/^def ([A-Za-z_]\w*)\(|^([A-Z][A-Z0-9_]*) = /gm)].map(m => m[1] ?? m[2]);
  assert.deepEqual(names.filter((name, i) => names.indexOf(name) !== i), []);
});
