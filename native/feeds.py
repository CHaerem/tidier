"""A feed's newest entries, for a live folder that is a feed (github-prs.py).

The folder's entry in live-folders.json has "feed": the feed's address, in place of a
search, and may say how many of its newest entries to show ("count", ten if it does
not). RSS (0.9x, 1.0, 2.0) and Atom are read alike: whatever is called an item or an
entry, with its title and its link.

A feed is something a stranger wrote, read here by a program with your rights, so:
only http and https, also after a redirect; no more than MOST_BYTES of it; no entities
of its own (a few lines of those can be made to fill the machine's memory); and of each
entry only a title, as plain text, and an http or https address. The extension never
names an address to fetch: only the ones in your file are.
"""
import html
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

COUNT, MOST = 10, 30
MOST_BYTES = 2 << 20
TIMEOUT_S = 15
WEB = ("http", "https")


class OnlyWeb(urllib.request.HTTPRedirectHandler):
    # urllib follows a redirect to ftp: too.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme not in WEB:
            raise urllib.error.HTTPError(newurl, code, "redirected away from the web", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url):
    if urllib.parse.urlsplit(url).scheme not in WEB:
        raise ValueError("not a web address")
    request = urllib.request.Request(url, headers={"User-Agent": "Tidier (a live folder's feed)", "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml, */*;q=0.1"})
    with urllib.request.build_opener(OnlyWeb).open(request, timeout=TIMEOUT_S) as answer:
        data = answer.read(MOST_BYTES + 1)
    if len(data) > MOST_BYTES:
        raise ValueError("it is larger than a feed is")
    return data


def name(element):
    return element.tag.rsplit("}", 1)[-1].lower() if isinstance(element.tag, str) else ""


def plain(text):
    # Titles come with entities written twice over, and some with markup in them.
    text = re.sub(r"<[^>]{0,200}>", "", html.unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()[:200]


def link(entry, base):
    # Atom: <link href>, the one that is the page (rel alternate, or none). RSS: <link>
    # with the address as its words, else a guid that says it is one.
    found = None
    for child in entry:
        kind = name(child)
        if kind == "link":
            href = child.get("href")
            if href and child.get("rel", "alternate") == "alternate":
                found = href
                break
            if not href and (child.text or "").strip():
                found = child.text.strip()
                break
        elif kind == "guid" and found is None and child.get("isPermaLink", "true") != "false":
            found = (child.text or "").strip() if re.match(r"https?://", (child.text or "").strip()) else None
    if not found:
        return None
    try:
        url = urllib.parse.urljoin(base, found)
        return url if urllib.parse.urlsplit(url).scheme in WEB and len(url) <= 2000 else None
    except ValueError:
        return None


def entries(data, base, count=COUNT):
    """The feed's first `count` entries, as it has them (the newest first, in every feed
    that is one), each once: [{"url", "title"}]."""
    if b"<!ENTITY" in data:
        raise ValueError("it declares entities of its own")
    root = ET.fromstring(data)
    # A page that is well-formed (an error page, a sign-in) has no entries either, and taken
    # as a feed with nothing in it, it would close every tab the folder has.
    if name(root) not in ("rss", "feed", "rdf"):
        raise ValueError(f"not a feed (it is <{name(root)[:40]}>)")
    out, seen = [], set()
    for element in root.iter():
        if name(element) not in ("item", "entry"):
            continue
        url = link(element, base)
        if not url or url in seen:
            continue
        seen.add(url)
        title = next((plain("".join(c.itertext())) for c in element if name(c) == "title"), "")
        out.append({"url": url, "title": title or url})
        if len(out) >= count:
            break
    return out


def answer(folder):
    """What the extension gets for this folder: {"items": [...]}, or {"error": words}."""
    count = folder.get("count")
    count = min(max(count, 1), MOST) if isinstance(count, int) and not isinstance(count, bool) else COUNT
    try:
        items = entries(fetch(folder["feed"]), folder["feed"], count)
    except ET.ParseError as err:
        return {"error": f"feed: not a feed ({err})"[:300]}
    except Exception as err:  # no network, no such address, a timeout, ...; the words begin with what it was
        return {"error": f"feed: {err}"[:300]}
    return {"items": [{**i, "what": "feed"} for i in items]}
