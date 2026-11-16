// Live folders: folders filled from a GitHub search (pull requests, or issues) or
// from a feed's newest entries, like Zen's live folders.
//
// The search runs in a native messaging host (native/github-prs.py) with your
// existing gh login, so no GitHub token reaches the browser; a feed is fetched
// there too, so Tidier needs no access to its site. The folders (name, space, and
// the search or the feed's address) are set up on the settings page (below: with
// sync on they are the same on every machine, syncprefs.js), or in the host's own
// file on a machine, of which the extension only gets each folder's id, name and
// container.
//
// Every few minutes (and at startup) each folder is brought in line with the
// search: what is new in it gets a tab (an unloaded placeholder that opens its
// page when you select it), what has left it (merged, closed, or out of
// the feed's newest) is removed (the one you are looking at only once you have
// left it). A live folder is one of Tidier's own (ownfolders.js), with `live` set
// to its id, and tab sync shows its tabs in every window. A tab you close stays
// closed until what it shows leaves the search.
//
// Most of the names here say pull request, which is what they were all once; an
// issue and a feed's entry go the same way, and differ only in what their rows show.

const NATIVE_HOST = "tidier_github";
const GITHUB_ICON = "https://github.githubassets.com/favicons/favicon.svg";
const LIVE_REFRESH_MINUTES = 15;

const liveFolderState = storedValue("liveFolders", () => ({})); // { [id]: { groupKey, dismissed: [url] } }

// --- The folders set up on the settings page -------------------------------------------
// { id, name, space, what: "prs" | "issues" | "feed", search | feed }. A search is what
// narrows within "open, and yours", which the helper adds: qualifiers alone (org:, repo:,
// label:, -label:), so that no word of it can widen the search. The helper refuses anything
// else (asked(), native/github-prs.py); refused here too, so that the settings page can say
// so as it is typed.
const LIVE_OWN = "liveOwnFolders";
const liveOwn = storedValue(LIVE_OWN, () => []);
const LIVE_KINDS = ["prs", "issues", "feed"];
const LIVE_QUALIFIERS = /^(-?[A-Za-z][A-Za-z-]*:[A-Za-z0-9_.@/*,<>=+-]+( |$))*$/;
// A folder as it may be kept, or null for what is none.
function liveFolderFrom(f) {
  if (!f || typeof f !== "object" || typeof f.id !== "string" || !/^[A-Za-z0-9-]{1,64}$/.test(f.id)) return null;
  const name = typeof f.name === "string" ? f.name.trim().slice(0, 80) : "";
  if (!name || !LIVE_KINDS.includes(f.what) || typeof f.space !== "string" || !f.space.startsWith("firefox-container-")) return null;
  const folder = { id: f.id, name, space: f.space, what: f.what };
  if (f.what === "feed") return isWeb(f.feed) && f.feed.length <= 2000 && !/\s/.test(f.feed) ? { ...folder, feed: f.feed } : null;
  const search = typeof f.search === "string" ? f.search.trim().replace(/\s+/g, " ") : "";
  return search.length <= 300 && LIVE_QUALIFIERS.test(search) ? { ...folder, search } : null;
}
// What the helper is asked for one of them.
const liveAsk = f => (f.what === "feed" ? { feed: f.feed } : { search: f.search, what: f.what });

// The list as the settings page (or another machine) has it now. One that is gone takes
// its folder and tabs along, as deleting a live folder does; one whose space changed is
// made anew there. Then all of them are looked at again.
async function setLiveOwnFolders(list) {
  const next = (Array.isArray(list) ? list : []).map(liveFolderFrom).filter(Boolean).filter((f, i, all) => all.findIndex(x => x.id === f.id) === i);
  const before = await liveOwn.get(), states = await liveFolderState.get();
  for (const was of before) {
    const now = next.find(f => f.id === was.id), state = states[was.id];
    if (now && now.space === was.space) {
      if (now.name !== was.name && state?.groupKey) await renameFolder(state.groupKey, now.name); // ownfolders.js
      continue;
    }
    if (state?.groupKey) await deleteFolder(state.groupKey);
    delete states[was.id];
  }
  await saveFolderState();
  liveOwn.set(next);
  viewAllSoon();
  if (started) refreshAllLiveFolders();
  return next;
}

async function folderState(id) {
  const all = await liveFolderState.get();
  if (!all[id]) all[id] = { groupKey: null, dismissed: [] };
  return all[id];
}
const saveFolderState = async () => liveFolderState.set(await liveFolderState.get());

// New live tabs are created in the window with the most synced tabs.
async function homeWindowId() {
  return referenceWindow(await browser.tabs.query({}), undefined);
}

// The folder: one with this name in this space, or a new one.
async function ensureFolderGroup(folder, state) {
  const all = await getSynced();
  if (state.groupKey && all[state.groupKey]) {
    // One of Sidebery's moved over by a click (an older Tidier) is not marked as a live folder.
    if (isOwnFolder(all[state.groupKey]) && !all[state.groupKey].live) { all[state.groupKey].live = folder.id; saveSynced(all); }
    return state.groupKey;
  }
  const existing = Object.entries(all).find(([, e]) => isOwnFolder(e) && e.cookieStoreId === folder.cookieStoreId && e.name === folder.name);
  state.groupKey = existing ? existing[0] : await createFolder(folder.name, folder.cookieStoreId, { live: folder.id }); // ownfolders.js
  await saveFolderState();
  return state.groupKey;
}

// A feed's entry has only its title; what GitHub has is also told apart by where it is.
const liveTitle = item => item.repo ? `${item.repo}#${item.number} ${item.title}` : String(item.title);

// What a pull request waits for, which its row shows as its icon (sidebar.js): a row of
// GitHub's mark said nothing. One word, the most pressing first: someone waits for your
// review; then, of your own, what stops it. An older helper says only whether it is a
// draft, and then that is all the icon says. An issue or a feed's entry waits for
// nothing, and says only what it is.
function liveState(item) {
  if (item.what === "issue" || item.what === "feed") return item.what;
  const mine = item.mine !== false;
  if (!mine && item.asked) return "review";
  if (item.draft) return "draft";
  if (mine && item.checks === "failing") return "failing";
  if (mine && item.conflict) return "conflict";
  if (item.review === "changes") return "changes";
  if (item.review === "approved") return "approved";
  if (mine && item.checks === "running") return "running";
  return "open";
}

// A tab for one pull request: live in the home window, ghosts elsewhere.
async function createLiveItem(folder, groupKey, item) {
  const all = await getSynced();
  const key = crypto.randomUUID();
  const entry = {
    url: item.url, liveUrl: item.url, title: liveTitle(item), pr: liveState(item),
    ...(item.what === "feed" ? {} : { icon: GITHUB_ICON }), // a feed's entries can be on any site
    cookieStoreId: folder.cookieStoreId, parentKey: groupKey, group: false, liveFolder: folder.id,
  };
  all[key] = entry;
  saveSynced(all);
  const home = await homeWindowId();
  for (const w of await normalWindows()) {
    if (w.id !== home) { await createRep(w.id, key, entry); continue; }
    const tab = await browser.tabs.create({ windowId: w.id, url: ghostUrl("lazy", key), cookieStoreId: entry.cookieStoreId, active: false, discarded: true, title: entry.title });
    syncBusy.add(tab.id);
    await setRole(tab.id, key, "live");
    setTimeout(() => syncBusy.delete(tab.id), SETTLE_MS);
  }
}

// The search, outside the queue: it can take up to the host's 30 s timeout,
// and tab sync (selecting a ghost, closing a tab) must not wait for it.
function searchLiveFolder(folder) {
  return browser.runtime.sendNativeMessage(NATIVE_HOST, folder.ask ? { ask: folder.ask } : { folder: folder.id }).catch(err => ({ error: String(err) }));
}

// Why a live folder stopped, in words for the one who reads the sidebar; the helper's own
// words (native/github-prs.py) go to the console above, for whoever fixes it.
// `own`: one set up on the settings page, which a helper from before that takes for a folder
// of its file that is not there.
function liveTrouble(error, own = false) {
  const text = String(error ?? "");
  if (!error || /no host|native application|disconnected/i.test(text)) return "its helper does not answer";
  if (text === "unknown folder") return own ? "its helper is older than Tidier (git pull where it is installed)" : "it is no longer in the helper's list of folders";
  if (/^not a search or a feed/.test(text)) return "its search is not one the helper runs";
  if (text === "gh not found") return "GitHub's own tool (gh) is not installed";
  if (/auth|log ?in|token|credential|401|403/i.test(text)) return "GitHub wants you to sign in again (gh auth login)";
  if (/live-folders\.json/.test(text)) return "the helper's list of folders could not be read";
  if (/only part of the result/.test(text)) return "GitHub answered with only part of the list";
  if (/^feed: not a feed/.test(text)) return "what its address answers with is not a feed";
  if (/^feed:/.test(text)) return "its feed did not answer";
  return "GitHub did not answer as it should";
}

async function refreshLiveFolder(folder, res) {
  if (!res || res.error || !Array.isArray(res.items)) {
    console.warn("Tidier: live folder", folder.id, res?.error);
    // A live folder that has stopped keeps its tabs, so it looks as if nothing has happened.
    setNotice("live", `Live folder "${folder.name}" is not updating: ${liveTrouble(res?.error, !!folder.ask)}`);
    return;
  }
  // The host's file still names a space that was removed, with its folder and tabs
  // (safemoves.js): made again, they would be entries shown nowhere, refused at every start.
  if (await spaceGone(folder.cookieStoreId)) {
    setNotice("live", `Live folder "${folder.name}" is set up for a space that is gone`);
    return;
  }
  const state = await folderState(folder.id);
  const groupKey = await ensureFolderGroup(folder, state);
  if (!groupKey) return;

  // Only what is a web page gets a tab: a feed is a stranger's words, and the helper that
  // reads it (native/feeds.py) is not updated with Tidier, so it is not left to that alone.
  const items = res.items.filter(i => isWeb(i?.url));
  const wanted = new Map(items.map(i => [i.url, i]));
  state.dismissed = state.dismissed.filter(u => wanted.has(u)); // closed PRs may come back if reopened
  await saveFolderState();

  const all = await getSynced();
  const have = new Map();
  for (const [k, e] of Object.entries(all)) if (e.liveFolder === folder.id) have.set(e.liveUrl, k);
  // A pull request you are looking at is removed at a later refresh, once its
  // tab is no longer the selected tab in any window (merged while you read it).
  const tabs = await browser.tabs.query({});
  for (const [url, k] of have) {
    if (!wanted.has(url) && !repsOf(k, tabs).some(t => t.active) && await closesQuietly(k)) await closeEverywhere(k, { dismiss: false });
  }
  for (const item of items) {
    if (have.has(item.url)) { await renameLiveItem(have.get(item.url), item); await markLiveItem(have.get(item.url), item); }
    else if (!state.dismissed.includes(item.url)) await createLiveItem(folder, groupKey, item);
  }
}

// A pull request renamed on GitHub: its tabs take the new title while none of
// them has been opened. (An opened one keeps the name it has, also over a restart:
// ownTitle, tabsync.js.)
async function renameLiveItem(key, item) {
  const all = await getSynced();
  const entry = all[key], title = liveTitle(item);
  if (!entry || entry.title === title) return;
  const reps = await repsNow(key);
  if (!reps.length || !reps.every(t => isGhostUrl(t.url))) return;
  entry.title = title;
  saveSynced(all);
  for (const t of reps) {
    const kind = syncRoleByTab.get(t.id) === "live" ? "lazy" : "ghost";
    await browser.tabs.update(t.id, { url: ghostUrl(kind, key) }).catch(() => {});
  }
}

// What it waits for now. Only the record changes, opened or not: no tab is touched, and
// saving the record draws the sidebars again (saveSynced, tabsync.js).
async function markLiveItem(key, item) {
  const all = await getSynced();
  const entry = all[key], pr = liveState(item);
  if (!entry || entry.pr === pr) return;
  entry.pr = pr;
  saveSynced(all);
}

// Called by tab sync when you close a tab: a live folder tab stays closed
// until its pull request leaves the search.
async function noteLiveFolderDismissed(entry) {
  if (!entry?.liveFolder) return;
  const state = await folderState(entry.liveFolder);
  if (!state.dismissed.includes(entry.liveUrl)) state.dismissed.push(entry.liveUrl);
  await saveFolderState();
}

// The folders: those set up on the settings page, and those of the host's own file. With no
// host on this machine there are none to fill, which is only a problem if there have been
// live folders here: one that came from another machine, to a machine with no helper, is
// simply not there (`helper`: whether it answered).
async function liveFolders() {
  const res = await browser.runtime.sendNativeMessage(NATIVE_HOST, { list: true }).catch(() => null);
  const states = await liveFolderState.get();
  if (!res && Object.values(states).some(s => s.groupKey)) setNotice("live", "Live folders are not updating: their helper does not answer (native/install.sh)");
  const own = (await liveOwn.get()).map(f => ({ id: f.id, name: f.name, cookieStoreId: f.space, ask: liveAsk(f) }));
  const file = Array.isArray(res?.folders) ? res.folders.map(f => ({ id: f.id, name: f.name, cookieStoreId: f.container })) : [];
  return { helper: !!res, folders: [...file.filter(f => !own.some(o => o.id === f.id)), ...own].filter(f => res || states[f.id]?.groupKey) };
}

async function refreshAllLiveFolders() {
  const { helper, folders } = await liveFolders();
  if (helper && folders.length) setNotice("live", null);
  for (const f of folders) {
    if (isHiddenSpace(f.cookieStoreId)) continue; // a hidden space gets no tabs; the search is done again when it shows
    const res = await searchLiveFolder(f);
    await serial(() => refreshLiveFolder(f, res)).catch(() => {}); // logged by serial()
  }
}

browser.alarms.create("liveFolders", { periodInMinutes: LIVE_REFRESH_MINUTES });
browser.alarms.onAlarm.addListener(alarm => { if (alarm.name === "liveFolders" && started) refreshAllLiveFolders(); });

// From the extension's own pages only (the smoke test refreshes with this). The settings
// page's list (settings/livefolders.js): what is set up here, what the host's file has, and
// whether there is a host at all.
browser.runtime.onMessage.addListener((msg, sender) => {
  if (sender.id !== browser.runtime.id || !sender.url?.startsWith(browser.runtime.getURL(""))) return;
  if (msg?.type === "refreshLiveFolders") return refreshAllLiveFolders().then(() => true);
  if (msg?.type !== "live:get" && msg?.type !== "live:set") return;
  return serial(async () => {
    if (msg.type === "live:set") await setLiveOwnFolders(msg.folders);
    const res = await browser.runtime.sendNativeMessage(NATIVE_HOST, { list: true }).catch(() => null);
    const own = await liveOwn.get();
    return { folders: own, helper: !!res, file: Array.isArray(res?.folders) ? res.folders.filter(f => !own.some(o => o.id === f.id)).map(f => ({ name: f.name, space: f.container })) : [] };
  });
});

// First refresh once tab sync has started.
(async () => {
  for (let i = 0; i < 120 && !started; i++) await sleep(1000);
  if (started) refreshAllLiveFolders();
})();
