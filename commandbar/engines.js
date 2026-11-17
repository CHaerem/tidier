// Search shortcuts, as in Zigzag and in Firefox's own address bar: "yt" and ⇥ searches
// YouTube, "@wikipedia rome" searches Wikipedia, and "@" alone lists every engine.
//
// The engines are Firefox's own (search.get, once the bar may ask), each by its keyword if
// you gave it one (Settings, Search) and by "@" and the first word of its name, as Firefox's
// address bar has them. A few sites that are no engine in Firefox come with Tidier, with the
// address a search there has; one of Firefox's by the same name wins, as you chose it.

const SITE_ENGINES = [
  { name: "YouTube", alias: "yt", url: "https://www.youtube.com/results?search_query={}" },
  { name: "GitHub", alias: "gh", url: "https://github.com/search?q={}" },
];

// "Amazon.com" is "amazon", "DuckDuckGo" is "duckduckgo".
const nameWord = name => String(name ?? "").toLowerCase().split(/[\s.(]/)[0];

// Firefox's engines (as search.get gives them) and Tidier's, in one list.
function enginesFrom(firefox = []) {
  const own = firefox.map(e => ({
    name: e.name, word: nameWord(e.name), alias: e.alias ? e.alias.toLowerCase().replace(/^@/, "") : null,
    icon: e.favIconUrl ?? null, isDefault: !!e.isDefault,
  }));
  const named = new Set(own.map(e => e.word));
  return [...own, ...SITE_ENGINES.filter(s => !named.has(nameWord(s.name))).map(s => ({ ...s, word: nameWord(s.name), icon: null, isDefault: false }))];
}

const withEngine = (engine, query) => ({
  kind: "search", id: "search:" + engine.name, title: `Search ${engine.name} for “${query}”`, query, engine: engine.name, icon: engine.icon,
  ...(engine.url ? { url: engine.url.replace("{}", encodeURIComponent(query)) } : {}),
});
const engineRow = engine => ({ kind: "engine", id: "engine:" + engine.name, title: `Search ${engine.name}`, engine: engine.name, icon: engine.icon });

// What the text says about an engine:
//   { search }: a keyword and words after it ("yt cats", "@wikipedia rome"), the search itself
//   { offers, first }: a keyword alone, as rows to choose the engine by (⇥ or ↵); first
//     when what you typed can only be meant so (a keyword, or "@"), else after the search
// or null. A plain word that is an engine's name ("youtube") is offered, never put first:
// it may as well be the start of a tab's title.
function shortcutIn(text, engines) {
  const t = String(text ?? "").trimStart();
  const at = t.startsWith("@");
  const [word, ...rest] = t.slice(at ? 1 : 0).split(/\s+/);
  const w = word.toLowerCase(), query = rest.join(" ").trim();
  const keyword = e => e.alias === w || (at && e.word === w);
  if (query) {
    const engine = engines.find(keyword);
    return engine ? { search: withEngine(engine, query) } : null;
  }
  if (at) {
    const offers = engines.filter(e => e.alias?.startsWith(w) || e.word.startsWith(w)).map(engineRow);
    return offers.length ? { offers, first: true } : null;
  }
  if (!w) return null;
  const exact = engines.find(e => e.alias === w);
  if (exact) return { offers: [engineRow(exact)], first: true };
  const named = engines.find(e => e.word === w && !e.isDefault); // (the default engine is the search row already)
  return named ? { offers: [engineRow(named)], first: false } : null;
}

// The one row under a chosen engine: what Enter searches there.
function engineSearchRow(engines, name, text) {
  const engine = engines.find(e => e.name === name), query = String(text ?? "").trim();
  return engine && query ? [withEngine(engine, query)] : [];
}
