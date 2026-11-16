// What you have chosen follows you too, through Firefox Sync, beside what sync.js carries:
// the colour chosen for a space, and the settings that are about how Tidier behaves and not
// about a machine (the times for archiving and unloading, a page in fullscreen staying in
// its window, links from other apps in a small window), the keys you gave Tidier's
// commands, and the live folders set up on the settings page. What is a machine's own stays there: which spaces are hidden, what Claude and
// agents may do, and every permission.
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
// + the system and a command's name: a key is written another way on a Mac than elsewhere
// (⌃ is only there), so machines share the keys of their own kind.
const SYNC_PREF_KEY = "key:";
const SYNC_PREF_LIVE = "live:"; // + the id of a live folder set up on the settings page (livefolders.js)
const syncBool = v => typeof v === "boolean";
const syncSame = (a, b) => JSON.stringify(a) === JSON.stringify(b);
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
// With a colour for each space this machine has (not the agents' own, which no other machine
// is told of), and the key of each command that has a line on the settings page (not Copy
// for Claude's, which is turned on per machine). A key as it was given at the first start
// (firstKeys, keys-commands.js) is nobody's choice; one you removed is ("").
async function syncPrefsHere(st, theirs) {
  const prefs = { ...SYNC_PREFS };
  for (const [sid, space] of Object.entries(st.map)) {
    if (space === agentSpaceId) continue;
    prefs[SYNC_PREF_COLOUR + sid] = { get: () => chosenColours[space] ?? null, plain: null, ok: v => v === null || hexColour(v) === v, set: v => setSpaceColour(space, v) };
  }
  const { os } = await browser.runtime.getPlatformInfo(), have = await browser.commands.getAll(), first = firstKeys(os);
  for (const { name, key } of COMMANDS) {
    const command = have.find(c => c.name === name);
    if (key === undefined || !command) continue;
    prefs[`${SYNC_PREF_KEY}${os}:${name}`] = {
      get: () => command.shortcut ?? "", plain: first.get(name) ?? "", same: (a, b) => keyId(a, os) === keyId(b, os), // (one key, written two ways)
      ok: v => typeof v === "string" && /^[A-Za-z0-9+]{0,40}$/.test(v), set: v => browser.commands.update({ name, shortcut: v }),
    };
  }
  // The live folders set up on the settings page, each by its id, with its space as the
  // machines know it. One that is gone is "none" (null), so that it goes everywhere. One from
  // another machine in a space this machine does not have is not looked at here at all: it
  // is carried along as it came, since "not here" would read as removed.
  const sidOf = new Map(Object.entries(st.map).filter(([, id]) => id !== agentSpaceId).map(([sid, id]) => [id, sid]));
  const shared = f => (f && sidOf.has(f.space) ? { name: f.name, space: sidOf.get(f.space), what: f.what, ...(f.what === "feed" ? { feed: f.feed } : { search: f.search }) } : null);
  const local = (id, v) => v && liveFolderFrom({ ...v, id, space: st.map[v.space] });
  const own = await liveOwn.get();
  const came = Object.keys(theirs).filter(k => k.startsWith(SYNC_PREF_LIVE)).map(k => k.slice(SYNC_PREF_LIVE.length));
  for (const id of new Set([...own.map(f => f.id), ...came])) {
    const here = own.find(f => f.id === id), remote = syncPrefEntry(theirs[SYNC_PREF_LIVE + id])?.[0];
    if (here ? !sidOf.has(here.space) : !(remote && typeof remote === "object" && sidOf.has(st.map[remote.space]))) continue;
    prefs[SYNC_PREF_LIVE + id] = {
      get: async () => shared((await liveOwn.get()).find(f => f.id === id)), plain: null,
      same: (a, b) => JSON.stringify(a && [a.name, a.space, a.what, a.feed ?? a.search]) === JSON.stringify(b && [b.name, b.space, b.what, b.feed ?? b.search]),
      ok: v => v === null || (!!v && typeof v === "object" && (!st.map[v.space] || !!local(id, v))),
      set: async v => setLiveOwnFolders([...(await liveOwn.get()).filter(f => f.id !== id), ...(local(id, v) ? [local(id, v)] : [])]),
    };
  }
  return prefs;
}
// A key you change says nothing to storage, where the other choices are heard of (sync.js).
browser.commands.onChanged?.addListener(() => syncSoon());
const syncPrefEntry = e => (Array.isArray(e) && e.length === 2 && Number.isFinite(e[1]) ? e : null);
const syncPrefsHighest = item => Math.max(0, ...Object.values(item && typeof item === "object" ? item : {}).map(e => syncPrefEntry(e)?.[1] ?? 0));

// One round: what is chosen here and what the other machines chose become one, what came
// is set here, and the item to write is returned. `st.prefs` is what was agreed last time,
// by which a change made here since is known. `stamp`: the round's clock (sync.js).
async function syncPrefsMerge(st, remote, stamp) {
  const theirs = remote && typeof remote === "object" && !Array.isArray(remote) ? remote : {};
  const first = !st.prefs, agreed = st.prefs ?? {}, merged = { ...theirs }; // (what is not known here is carried along)
  const refused = {};
  for (const [name, pref] of Object.entries(await syncPrefsHere(st, theirs))) {
    const now = await pref.get(), was = syncPrefEntry(agreed[name]), same = pref.same ?? syncSame;
    // Changed here since the last round: chosen now. Else as agreed. With nothing agreed about
    // it, it counts only if it is not as it came: chosen now, or, in the first round of all,
    // some time before, which nobody knows, so before everything that has a time.
    const mine = was ? (same(was[0], now) ? was : [now, stamp()]) : same(now, pref.plain) ? null : [now, first ? 0 : stamp()];
    const came = syncPrefEntry(theirs[name]), other = came && pref.ok(came[0]) ? came : null;
    const wins = mine && (!other || mine[1] > other[1]) ? mine : other;
    if (!wins) { delete merged[name]; continue; } // (one that cannot be read is not kept going)
    merged[name] = wins;
    // One that cannot be set here (a key Firefox refuses): what is here is remembered as of
    // that same time, so that the next round tries again, and does not take what stayed for
    // a change made here and send it to every machine.
    if (!same(wins[0], now)) await Promise.resolve(pref.set(wins[0])).catch(err => { noteError(err); refused[name] = [now, wins[1]]; });
  }
  st.prefs = { ...merged, ...refused };
  return merged;
}
// Written only if it differs from what is there, and known as this machine's own when
// Firefox tells of it (syncWrote, sync.js), so that rounds cannot answer each other.
async function syncPrefsWrite(merged, items) {
  if (JSON.stringify(items[SYNC_PREFS_KEY] ?? {}) === JSON.stringify(merged)) return;
  syncWrote.set(SYNC_PREFS_KEY, JSON.stringify(merged));
  await browser.storage.sync.set({ [SYNC_PREFS_KEY]: merged });
}
