// The GitHub repositories you work in, for the command bar: type a part of one's name to go
// there, or ⇥ into it for its pull requests, issues, Actions and a search of its code
// (commandbar/repos.js).
//
// The helper finds them (repos() in native/github-prs.py, with your own gh login): those of
// the pull requests you were in on lately, the ones waiting for your review first. Nothing
// to set up, and nothing on a machine without the helper.
//
// Asked only when the bar opens, and then at most once a quarter of an hour, after it has
// opened: the bar shows what was found the time before, at once. With nothing happening,
// nothing is asked.

const GITHUB_REPOS = "githubRepos"; // storage.local: { at, items: [{ repo, waiting }] }
const REPOS_FRESH_MS = LIVE_REFRESH_MINUTES * 60e3; // livefolders.js
const REPO_NAME = /^[A-Za-z0-9-]+\/(?!\.\.?$)[\w.-]+$/; // as the helper's: an owner, and a name that is no folder of a path
let reposAsking = null;

// What was found last, as it is; asked again behind it when that is old.
async function githubRepos() {
  const kept = (await browser.storage.local.get(GITHUB_REPOS).catch(() => ({})))[GITHUB_REPOS];
  if (!(Date.now() - kept?.at < REPOS_FRESH_MS)) askGithubRepos(kept);
  return Array.isArray(kept?.items) ? kept.items : [];
}

function askGithubRepos(kept) {
  reposAsking ??= browser.runtime.sendNativeMessage(NATIVE_HOST, { ask: { what: "repos", search: "" } }).catch(() => null).then(res => {
    // An answer that is no list (no helper here, an older one, GitHub not answering) keeps
    // what was found before, and is not asked again until the time has passed.
    const items = Array.isArray(res?.items)
      ? res.items.filter(i => REPO_NAME.test(i?.repo)).slice(0, 30).map(i => ({ repo: i.repo, waiting: Math.max(0, Number(i.waiting) || 0) }))
      : kept?.items ?? [];
    return browser.storage.local.set({ [GITHUB_REPOS]: { at: Date.now(), items } });
  }).catch(noteError).finally(() => { reposAsking = null; });
  return reposAsking;
}

// As the bar lists them: a row per repository, the waiting count after its name.
const githubRepoItems = repos => repos.map(r => ({
  kind: "repo", id: `repo:${r.repo}`, title: r.repo, repo: r.repo, url: `https://github.com/${r.repo}`,
  ...(r.waiting ? { note: `${r.waiting} to review` } : {}),
}));
