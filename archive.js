// Archive tabs you have not used for a while, like Arc: a tab that has not
// been selected in any window for 12 hours is closed everywhere. Firefox keeps
// it under History → Recently Closed Tabs (⌘⇧T reopens the last one).
//
// Kept: essentials (pinned), every tab in a folder (Arc's pinned folders; the
// pull request folders too), a tab that is selected in any window, and tabs
// playing sound.
//
// The time counts from when the tab was last selected (or opened, if it never
// was), but never from before
// archiving was first turned on, so turning it on does not close old tabs at
// once. Change the time with "archiveAfterHours" in the extension storage
// (0 turns archiving off).
//
// Every tab it closes also goes in Tidier's own list, per space, so it can be found
// again there (archivelist.js).

const ARCHIVE_DEFAULT_HOURS = 12;
const ARCHIVE_CHECK_MINUTES = 10;

// The time as it may be set: whole hours from 0 (never) up to a year, else null, which
// is no answer at all. A negative number would make every ordinary tab count as unused
// (now - lastUsed is never less than it), and the next round would close them all; an
// emptied field is not "never". A value stored before this was checked counts as unset.
const ARCHIVE_MOST_HOURS = 24 * 365;
function archiveHoursFrom(value) {
  if (typeof value !== "number" && (typeof value !== "string" || !value.trim())) return null;
  const hours = Number(value);
  return Number.isFinite(hours) && hours >= 0 ? Math.min(Math.round(hours), ARCHIVE_MOST_HOURS) : null;
}
const archiveHours = stored => archiveHoursFrom(stored) ?? ARCHIVE_DEFAULT_HOURS;

// `now` and `onlyKeys` are for the smoke test (pretend it is later, and only
// look at its own tabs); `explain` returns why each tab was kept.
async function archiveIdleTabs({ now = Date.now(), onlyKeys, explain = false } = {}) {
  const stored = await browser.storage.local.get(["archiveAfterHours", "archiveSince"]);
  const hours = archiveHours(stored.archiveAfterHours);
  if (!hours) return [];
  let since = stored.archiveSince;
  if (!since) {
    since = Date.now();
    await browser.storage.local.set({ archiveSince: since });
  }
  const all = await getSynced();
  const tabs = await browser.tabs.query({});
  const archived = [], kept = {};
  const tabsById = new Map(tabs.map(t => [t.id, t])); // (for a placeholder's live tab)
  const reps = repsByKey(tabs); // closing a tab below changes only that tab's own entry
  for (const key of onlyKeys || Object.keys(all)) {
    const why = keepReason(all, key, reps.get(key) ?? [], now, since, hours);
    if (why) { kept[key] = why; continue; }
    if (!(await closesQuietly(key))) { kept[key] = "unsaved"; continue; }
    // A real page has Recently Closed as well. A tab that is only a placeholder has nothing
    // there, so if the list cannot take it, closing it would lose it for good: it stays.
    const noted = await noteArchived(all[key], "archived");
    if (!noted && isGhostUrl(tabsById.get(liveTabId(key))?.url)) { kept[key] = "no list"; continue; }
    archived.push(all[key].url);
    await closeEverywhere(key, { dismiss: false });
  }
  return explain ? { archived, kept } : archived;
}

function keepReason(all, key, reps, now, since, hours) {
  const entry = all[key];
  if (!entry) return "unknown";
  if (!reps.length) return "no tab";
  const live = reps.find(t => syncRoleByTab.get(t.id) === "live");
  if (entry.group || storedInFolder(all, key)) return "folder";
  if (reps.some(t => t.pinned)) return "pinned";
  if (reps.some(t => t.active)) return "selected";
  if (reps.some(t => t.audible)) return "sound";
  if (!live) return "no live tab";
  // A live tab that is only a placeholder (it became live when the window with
  // the real page closed) has no page for Recently Closed to keep, and its
  // lastAccessed says nothing about when you last used the tab. Tidier's own list
  // holds its address (archivelist.js), so it can be archived like the rest. Its time
  // counts from when this first saw it as a placeholder: you may well have used the
  // page just before its window closed.
  let lastUsed;
  if (isGhostUrl(live.url)) {
    if (!isWeb(entry.url)) return "placeholder";
    if (!entry.placeholderSince) {
      entry.placeholderSince = now;
      saveSynced(all, { lazy: true }); // lost in a crash, the time just starts again
    }
    lastUsed = Math.max(entry.placeholderSince, entry.added || 0, since);
  } else {
    delete entry.placeholderSince; // it was selected, and its own lastAccessed counts again
    // A tab opened in the background and never selected has no lastAccessed;
    // then the time counts from when it was opened.
    lastUsed = Math.max(live.lastAccessed || 0, entry.added || 0, since);
  }
  if (now - lastUsed < hours * 3600e3) return "used " + Math.round((now - lastUsed) / 60000) + " min ago";
  return null;
}

// Selected, it is in use: if its window then closes, its time as a placeholder starts
// anew from there. A check cannot see this: it stops at "selected" while it is, and may
// not come at all before the window closes, and then an old time would close a tab you
// used a minute ago.
browser.tabs.onActivated.addListener(async ({ tabId }) => {
  const key = syncKeyByTab.get(tabId);
  if (!started || !key) return;
  const all = await getSynced();
  if (!all[key]?.placeholderSince) return;
  delete all[key].placeholderSince;
  saveSynced(all, { lazy: true });
});

browser.alarms.create("archive", { periodInMinutes: ARCHIVE_CHECK_MINUTES });
browser.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === "archive" && started) serial(() => archiveIdleTabs());
});

// From the extension's own pages only (the smoke test uses this).
browser.runtime.onMessage.addListener((msg, sender) => {
  if (msg?.type !== "archiveNow" || sender.id !== browser.runtime.id || !sender.url?.startsWith(browser.runtime.getURL(""))) return;
  return serial(() => archiveIdleTabs({ now: msg.now, onlyKeys: msg.keys, explain: msg.explain }));
});
