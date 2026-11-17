// Tabs you have not used for a while are unloaded, as in Zen: they stay where they are, in
// the list and in every window, and give their memory back. A row dims, and the page comes
// back when you select it. Off until you set a time on the settings page.
//
// Firefox unloads tabs by itself only when the whole machine is short of memory, which on
// a Mac with other things running is late. Archiving (archive.js) closes a tab after half
// a day; this is for the hours before that, and for what archiving never touches: the tabs
// in your folders.
//
// What stays loaded, as when a whole space is unloaded (unloadable, spaceactions.js): the
// tab selected in each window, and any tab whose placeholder is (its page is on its way
// to you), tabs playing sound, a call or a shared screen, and a page with unsaved input,
// which refuses without asking. Essentials stay too: always there and ready.
//
// Looked at on the beat archiving already has (the "archive" alarm), so there is no timer
// of its own; with no time set it does nothing at all.
//
// Many pages loaded at once weigh more than a few old ones, so a crowd counts too, as in
// Zigzag: with more than UNLOAD_CROWD pages loaded, a tab unseen for a quarter of an hour
// goes as well, the longest unseen first, until the crowd is down to that.
const UNLOAD_CROWD = 20, UNLOAD_CROWDED_MS = 15 * 60e3;

const UNLOAD_MOST_HOURS = 24 * 365;
// The time as it may be set: hours from 0 (never) up, with halves and quarters, else null,
// which is no answer at all and changes nothing (as archiveHoursFrom, archive.js).
function unloadHoursFrom(value) {
  if (typeof value !== "number" && (typeof value !== "string" || !value.trim())) return null;
  const hours = Number(value);
  return Number.isFinite(hours) && hours >= 0 ? Math.min(Math.round(hours * 4) / 4, UNLOAD_MOST_HOURS) : null;
}
const unloadHours = stored => unloadHoursFrom(stored) ?? 0;

// `now` is for the tests (pretend it is later). Answers how many were unloaded.
async function unloadIdleTabs({ now = Date.now() } = {}) {
  const hours = unloadHours((await browser.storage.local.get("unloadAfterHours")).unloadAfterHours);
  if (!hours) return 0;
  // Every window's tabs, so that a placeholder selected in one counts for its page in another.
  const all = await browser.tabs.query({});
  let awake = all.filter(t => isWeb(t.url) && !t.discarded).length; // essentials too: they weigh as much
  const unseen = t => now - (t.lastAccessed || now);
  const idle = [];
  for (const t of unloadable(all.filter(t => !t.pinned)).filter(t => isWeb(t.url)).sort((a, b) => unseen(b) - unseen(a))) { // spaceactions.js
    if (unseen(t) < hours * 3600e3 && !(awake > UNLOAD_CROWD && unseen(t) >= UNLOAD_CROWDED_MS)) continue;
    idle.push(t);
    awake--;
  }
  if (!idle.length) return 0;
  const unloaded = await unloadPages(idle);
  if (unloaded) trace(`unloaded ${unloaded} tab${unloaded === 1 ? "" : "s"} not used for ${hours} h, or for a while with many loaded`);
  return unloaded;
}

browser.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === "archive" && started) serial(() => unloadIdleTabs()); // archive.js makes the alarm
});
// From the extension's own pages only (the smoke test uses this).
browser.runtime.onMessage.addListener((msg, sender) => {
  if (msg?.type !== "unloadIdleNow" || sender.id !== browser.runtime.id || !sender.url?.startsWith(browser.runtime.getURL(""))) return;
  return serial(() => unloadIdleTabs({ now: msg.now }));
});
