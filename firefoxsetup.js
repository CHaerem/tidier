// Firefox must be started again to read its setup files, and Tidier says so, with a button.
//
// Firefox reads user.js and its stylesheets (userChrome.css) only as it starts. The
// dotfiles change them on their own, a quarter of an hour after a push, and nothing says
// that the Firefox you are in still runs on the old ones. After the update that made the
// command bar a panel in the window, which needs the new stylesheet to stand where it
// should, the bar did not open at all until Firefox was started again, and nothing said why.
//
// An extension can neither see those files nor start Firefox again: there is no call for
// it, and Firefox opens none of its own pages that have such a button for an extension
// (tried: about:restartrequired, about:profiles). Tidier's helper program is outside
// Firefox and can do both, for the one Firefox that started it (native/firefox_setup.py).
// So: the helper is asked whether a setup file is newer than this Firefox; if one is, the
// sidebar has one line that says so, which is a button (sidebar/restart.js). The button
// has the helper ask Firefox to quit as ⌘Q does, and open it again: your tabs come back as
// after any quit.
//
// With no helper on this machine, or an older one that does not know the question, nothing
// is known and nothing is said.
//
// Asked a little after Tidier starts (which is also after each of its updates), and on the
// beat the live folders already wake the helper on (livefolders.js): no timer of its own.

const SETUP_FIRST_CHECK_MS = 10000; // after a start: Firefox is busy with its windows until then
let setupNewer = null; // the setup files that are newer than this Firefox, as the helper last said: ["userChrome.css"], or null
let setupPutAway = null; // those you put the line away for, as one string: it comes back only when there are others

// What the sidebar shows (viewFor, sidebar-view.js): the files, for the line's tooltip.
const restartLine = () => (setupNewer && setupNewer.join() !== setupPutAway ? { files: setupNewer } : null);

async function checkFirefoxSetup() {
  const res = await browser.runtime.sendNativeMessage(NATIVE_HOST, { firefox: "changed" }).catch(() => null); // livefolders.js
  const newer = res?.changed === true && Array.isArray(res.files) && res.files.length ? res.files.map(String).slice(0, 5) : null;
  if ((newer?.join() ?? null) === (setupNewer?.join() ?? null)) return;
  setupNewer = newer;
  viewAllSoon();
}

// The line's ×: not again for these files.
function restartLinePutAway() {
  if (!setupNewer) return;
  setupPutAway = setupNewer.join();
  viewAllSoon();
}

// The line's button. What Tidier has not written yet is written first: Firefox is about to
// quit. If the helper cannot do it (none here, an older one, not a Firefox it knows), the
// line stays and the sidebar says so.
async function restartFirefox(windowId) {
  await flushWrites().catch(noteError); // common.js
  const res = await browser.runtime.sendNativeMessage(NATIVE_HOST, { firefox: "restart" }).catch(err => ({ error: String(err?.message ?? err) }));
  trace(`restart Firefox: ${res?.restarting ? "asked" : res?.error ?? "no answer"}`);
  if (!res?.restarting) say(windowId, "Firefox could not be started again from here"); // quiet.js
}

setTimeout(() => checkFirefoxSetup().catch(noteError), SETUP_FIRST_CHECK_MS);
browser.alarms.onAlarm.addListener(alarm => { if (alarm.name === "liveFolders") checkFirefoxSetup().catch(noteError); });
// From Tidier's own pages: asked now, and answered with what the sidebar will show.
browser.runtime.onMessage.addListener((msg, sender) => {
  if (msg?.type !== "firefoxSetup:check" || sender.id !== browser.runtime.id || !sender.url?.startsWith(browser.runtime.getURL(""))) return;
  return checkFirefoxSetup().then(restartLine);
});
