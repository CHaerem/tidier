// What you have chosen follows you too, through Firefox Sync, beside what sync.js carries:
// the colour chosen for a space, and the settings that are about how Tidier behaves and not
// about a machine (the times for archiving and unloading, a page in fullscreen staying in
// its window, links from other apps in a small window). What is a machine's own stays there:
// which spaces are hidden, the keys, what Claude and agents may do, and every permission.
//
// One item of its own in storage.sync, apart from sync.js's document: a version of Tidier
// from before this leaves it alone (it removes only items of its own form), and a mistake
// here cannot reach the essentials and folders. Each thing is [value, when it was chosen],
// newest wins per thing, so two machines that change different settings both keep their
// change. A thing this version does not know (a later version's setting, a space that is
// not on this machine) is carried along as it came.
//
// A setting nobody has touched is not there at all: a machine with everything as it came
// must not overrule one where a time was set years ago, and has no "when" to say.

const SYNC_PREFS_KEY = "p/1";
const SYNC_PREF_COLOUR = "colour:"; // + a space's id among the machines (sid, syncmerge.js)
const syncBool = v => typeof v === "boolean";
// How each is read and set here, what it is when nobody has chosen (`plain`), and what a
// value from another machine must be to be taken. (After archive.js and unloadidle.js among
// the scripts, manifest.json: their names are read as this one loads.)
const SYNC_PREFS = {
  archive: { get: async () => archiveHours((await browser.storage.local.get("archiveAfterHours")).archiveAfterHours), plain: ARCHIVE_DEFAULT_HOURS,
    ok: v => archiveHoursFrom(v) === v, set: v => browser.storage.local.set({ archiveAfterHours: v }) },
  unload: { get: async () => unloadHours((await browser.storage.local.get("unloadAfterHours")).unloadAfterHours), plain: 0,
    ok: v => unloadHoursFrom(v) === v, set: v => browser.storage.local.set({ unloadAfterHours: v }) },
  fullscreen: { get: () => fullscreenSetting.get(), plain: true, ok: syncBool, set: v => fullscreenSetting.set(v) },
  little: { get: () => littleSetting.get(), plain: false, ok: syncBool, set: v => littleSetting.set(v) },
};
// With a colour for each space this machine has (not the agents' own, which no other machine is told of).
function syncPrefsHere(st) {
  const prefs = { ...SYNC_PREFS };
  for (const [sid, space] of Object.entries(st.map)) {
    if (space === agentSpaceId) continue;
    prefs[SYNC_PREF_COLOUR + sid] = { get: () => chosenColours[space] ?? null, plain: null, ok: v => v === null || hexColour(v) === v, set: v => setSpaceColour(space, v) };
  }
  return prefs;
}
const syncPrefEntry = e => (Array.isArray(e) && e.length === 2 && Number.isFinite(e[1]) ? e : null);
const syncPrefsHighest = item => Math.max(0, ...Object.values(item && typeof item === "object" ? item : {}).map(e => syncPrefEntry(e)?.[1] ?? 0));

// One round: what is chosen here and what the other machines chose become one, what came
// is set here, and the item to write is returned. `st.prefs` is what was agreed last time,
// by which a change made here since is known. `stamp`: the round's clock (sync.js).
async function syncPrefsMerge(st, remote, stamp) {
  const theirs = remote && typeof remote === "object" && !Array.isArray(remote) ? remote : {};
  const first = !st.prefs, agreed = st.prefs ?? {}, merged = { ...theirs }; // (what is not known here is carried along)
  for (const [name, pref] of Object.entries(syncPrefsHere(st))) {
    const now = await pref.get(), was = syncPrefEntry(agreed[name]);
    // Changed here since the last round: chosen now. Else as agreed. With nothing agreed about
    // it, it counts only if it is not as it came: chosen now, or, in the first round of all,
    // some time before, which nobody knows, so before everything that has a time.
    const mine = was ? (JSON.stringify(was[0]) === JSON.stringify(now) ? was : [now, stamp()]) : now === pref.plain ? null : [now, first ? 0 : stamp()];
    const came = syncPrefEntry(theirs[name]), other = came && pref.ok(came[0]) ? came : null;
    const wins = mine && (!other || mine[1] > other[1]) ? mine : other;
    if (!wins) { delete merged[name]; continue; } // (one that cannot be read is not kept going)
    merged[name] = wins;
    if (JSON.stringify(wins[0]) !== JSON.stringify(now)) await pref.set(wins[0]);
  }
  st.prefs = merged;
  return merged;
}
// Written only if it differs from what is there, and known as this machine's own when
// Firefox tells of it (syncWrote, sync.js), so that rounds cannot answer each other.
async function syncPrefsWrite(merged, items) {
  if (JSON.stringify(items[SYNC_PREFS_KEY] ?? {}) === JSON.stringify(merged)) return;
  syncWrote.set(SYNC_PREFS_KEY, JSON.stringify(merged));
  await browser.storage.sync.set({ [SYNC_PREFS_KEY]: merged });
}
