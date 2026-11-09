// A notice in the sidebar (common.js, setNotice): what it says, and putting it away with its ×.
// On Tidier's real background scripts and a fake Firefox (fake_firefox.mjs).
import { test } from "node:test";
import assert from "node:assert/strict";
import { FakeFirefox, wait } from "./fake_firefox.mjs";

async function started() {
  const ff = new FakeFirefox();
  const w = ff.addWindow({ focused: true });
  ff.addTab(w.id, { url: "about:home", active: true });
  const x = ff.boot();
  x.b.runtime.onStartup.fire({});
  for (let i = 0; i < 300 && !x.started(); i++) await wait(1000);
  return { ff, x };
}

test("a live folder that stopped says why in plain words, not in the helper's", async () => {
  const { x } = await started();
  const words = error => x.js("liveTrouble")(error);
  assert.equal(words(undefined), "its helper does not answer");
  assert.equal(words("Error: No such native application tidier_live_folders"), "its helper does not answer");
  assert.equal(words("unknown folder"), "it is no longer in the helper's list of folders");
  assert.equal(words("gh not found"), "GitHub's own tool (gh) is not installed");
  assert.equal(words("To get started with GitHub CLI, please run:  gh auth login"), "GitHub wants you to sign in again (gh auth login)");
  assert.equal(words("HTTP 401: Bad credentials (https://api.github.com/graphql)"), "GitHub wants you to sign in again (gh auth login)");
  assert.equal(words("/Users/someone/.config/tidier/live-folders.json: Expecting ',' delimiter: line 3"), "the helper's list of folders could not be read");
  assert.equal(words("something nobody foresaw"), "GitHub did not answer as it should");
  x.kill();
});

test("a notice put away stays away while its words are the same, and new words show", async () => {
  const { ff, x } = await started();
  const shown = () => [...x.js("notices").values()];
  const live = 'Live folder "Pull requests" is not updating: its helper does not answer';
  x.js("setNotice")("live", live);
  x.js("setNotice")("copy", "No copy is being kept");
  assert.deepEqual(shown(), [live, "No copy is being kept"]);
  assert.equal(ff.badge, "!");

  x.js("putNoticeAway")(live);
  assert.deepEqual(shown(), ["No copy is being kept"], "the next one shows in its place");
  // A live folder clears its notice at every try, and sets it again when the try fails.
  x.js("setNotice")("live", null);
  x.js("setNotice")("live", live);
  assert.deepEqual(shown(), ["No copy is being kept"], "the same words stay away");
  x.js("setNotice")("live", 'Live folder "Pull requests" is not updating: GitHub wants you to sign in again (gh auth login)');
  assert.equal(shown().length, 2, "another problem shows");

  x.js("putNoticeAway")("No copy is being kept");
  x.js("putNoticeAway")(shown()[0]);
  assert.deepEqual(shown(), []);
  assert.equal(ff.badge, "", "nothing left on Tidier's button");
  x.js("putNoticeAway")(undefined); // a × pressed as the notice went: nothing to do
  x.kill();
});

test("the sidebar's × puts away the notice it shows", async () => {
  const { x } = await started();
  const text = "Clients had gone from Firefox and has been made again";
  x.js("setNotice")("spaceBack", text);
  await x.send({ type: "isolation:seen", text });
  assert.equal(x.js("notices").has("spaceBack"), false);
  x.kill();
});
