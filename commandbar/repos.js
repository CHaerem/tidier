// A GitHub repository you work in, as a place of its own in the bar (githubrepos.js in the
// background finds them): its name and Enter goes there, ⇥ goes into it. Inside, its parts
// are rows, what you type finds them and the tabs you have open in it, and the last row
// searches its code.

const REPO_PLACES = [
  ["Pull requests", "/pulls"],
  ["Waiting for your review", "/pulls?q=" + encodeURIComponent("is:pr is:open review-requested:@me")],
  ["Issues", "/issues"],
  ["Actions", "/actions"],
  ["Code", ""],
];

function repoRows(repo, text, items = [], now = Date.now()) {
  const base = `https://github.com/${repo}`, t = String(text ?? "").trim();
  const places = REPO_PLACES.map(([title, path]) => ({ kind: "address", id: `repo-place:${title}`, title, url: base + path }));
  if (!t) return places;
  const inIt = items.filter(i => i.kind !== "repo" && i.url && (i.url === base || i.url.startsWith(base + "/")));
  const search = { kind: "search", id: "repo-search", title: `Search ${repo} for “${t}”`, query: t, url: `https://github.com/search?q=${encodeURIComponent(`repo:${repo} ${t}`)}&type=code` };
  return [...[...rankResults(t, places, now), ...rankResults(t, inIt, now)].slice(0, BAR_ROWS - 1), search];
}
