#!/usr/bin/env python3
"""Your spaces, essentials, pinned tabs and folders from Arc or Zen, as a file that
Tidier's settings page takes in (Copies: take in a copy).

    tools/from_arc_zen.py                 # finds Arc and Zen on this Mac
    tools/from_arc_zen.py --zen PROFILE   # a Zen profile folder
    tools/from_arc_zen.py --arc FILE      # Arc's StorableSidebar.json

Each one found gives its own file in ~/Downloads (tidier-from-zen.json,
tidier-from-arc.json), readable only by you: it holds your addresses, so it stays
out of every repository. What this prints holds no addresses, only counts.

Only reads: Arc and Zen are never changed, and may be running.

The file has the form of Tidier's own copy (copies.js), so taking it in merges:
nothing in Tidier is removed, a space that is not there yet is made, and the settings
page shows what will come before anything is written. Tidier finds spaces by name,
so the ids below only have to be the same within the file.

How Arc and Zen map onto Tidier:
- A space is a space, with its own container (logins). Two Arc or Zen spaces that
  shared one container or profile get one each in Tidier, as Tidier's spaces do.
- Essentials (Arc's favourites, Zen's essentials) are essentials. Arc keeps them per
  profile, so each space of that profile gets them; Zen's that belong to no container
  or space go into every space.
- Pinned tabs are saved tabs. Tidier keeps saved tabs only in folders, so pinned tabs
  outside a folder go into a folder called "Pinned", first in the space.
- Folders are folders. Tidier's are not nested, so a folder inside another becomes
  "Outer / Inner".
- Ordinary tabs are left out: Tidier would archive them anyway.
"""
import argparse
import glob
import json
import os
import sys

PINNED = "Pinned"
NO_CONTAINER = "firefox-default"
# Firefox's own four containers have no name in containers.json, only a string id.
BUILT_IN = {"userContextPersonal.label": "Personal", "userContextWork.label": "Work",
            "userContextBanking.label": "Banking", "userContextShopping.label": "Shopping"}
COLOURS = {"blue", "turquoise", "green", "yellow", "orange", "red", "pink", "purple", "toolbar"}
ICONS = {"fingerprint", "briefcase", "dollar", "cart", "circle", "gift", "vacation", "food",
         "fruit", "pet", "tree", "chill", "fence"}


def is_web(url):
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def unlz4(data):
    """Firefox's and Zen's .jsonlz4: a magic, the size, then one LZ4 block. Python has
    no LZ4 of its own, and this must run on a Mac with nothing installed."""
    if data[:8] != b"mozLz40\0":
        raise ValueError("not a mozLz4 file")
    src, out, i = data[12:], bytearray(), 0
    while i < len(src):
        token = src[i]
        i += 1
        n = token >> 4
        if n == 15:
            while True:
                n += src[i]
                i += 1
                if src[i - 1] != 255:
                    break
        out += src[i:i + n]
        i += n
        if i >= len(src):
            break  # the last run has literals only
        offset = src[i] | src[i + 1] << 8
        i += 2
        m = (token & 15) + 4
        if token & 15 == 15:
            while True:
                m += src[i]
                i += 1
                if src[i - 1] != 255:
                    break
        start = len(out) - offset
        for k in range(m):  # a match may overlap what it copies
            out.append(out[start + k])
    return json.loads(bytes(out))


class Copy:
    """A Tidier copy being built: spaces, essentials, folders and saved tabs."""

    def __init__(self, source):
        self.source, self.spaces, self.essentials, self.synced = source, [], [], {}
        self.order, self.counter, self.urls = [], 0, set()

    def key(self, kind):
        self.counter += 1
        return f"{self.source}-{kind}-{self.counter}"

    def space(self, sid, name, color=None, icon=None):
        name = name.strip() if isinstance(name, str) and name.strip() else "Space"
        taken = {s["name"] for s in self.spaces}
        base, n = name, 2
        while name in taken:  # Tidier finds spaces by name: two of one name would become one
            name, n = f"{base} {n}", n + 1
        self.spaces.append({"id": sid, "name": name, "color": color if color in COLOURS else "blue",
                            "icon": icon if icon in ICONS else "circle"})
        self.order.append(sid)

    def essential(self, sid, url, title):
        if not is_web(url) or (sid, url, "e") in self.urls:
            return
        self.urls.add((sid, url, "e"))
        self.essentials.append({"key": self.key("essential"), "url": url, "cookieStoreId": sid, "title": title or url})

    def folder(self, sid, name):
        key = self.key("folder")
        rank = sum(1 for e in self.synced.values() if e.get("group") and e["cookieStoreId"] == sid) + 1
        self.synced[key] = {"group": True, "own": True, "name": name or "Folder", "cookieStoreId": sid,
                            "parentKey": None, "rank": rank, "added": 0}
        return key

    def saved(self, sid, folder, url, title, name=None):
        if not is_web(url) or (sid, url, folder) in self.urls:
            return
        self.urls.add((sid, url, folder))
        entry = {"url": url, "title": title or url, "cookieStoreId": sid, "parentKey": folder, "group": False,
                 "added": 0, "saved": {"url": url, "title": title or url}}
        if name and name != title:
            entry["name"] = name  # a tab you renamed keeps its name (tabnames.js)
        self.synced[self.key("tab")] = entry

    def drop_empty_folders(self):
        used = {e["parentKey"] for e in self.synced.values() if not e.get("group")}
        for key in [k for k, e in self.synced.items() if e.get("group") and k not in used]:
            del self.synced[key]

    def result(self):
        self.drop_empty_folders()
        return {"tidier": f"from {self.source}", "when": 0, "spaces": self.spaces,
                "data": {"essentials": self.essentials, "syncedTabs": self.synced, "spaceOrder": self.order}}

    def summary(self):
        lines = []
        for s in self.spaces:
            sid = s["id"]
            folders = [e for e in self.synced.values() if e.get("group") and e["cookieStoreId"] == sid]
            tabs = [e for e in self.synced.values() if not e.get("group") and e["cookieStoreId"] == sid]
            ess = [e for e in self.essentials if e["cookieStoreId"] == sid]
            lines.append(f"  {s['name']}: {len(ess)} essentials, {len(folders)} folders, {len(tabs)} saved tabs")
        return "\n".join(lines)


# --- Zen ------------------------------------------------------------------------------

def tab_url(tab):
    """A session tab's address and title: its current history entry."""
    entries = tab.get("entries") or []
    if not entries:
        return None, None
    at = min(max(int(tab.get("index") or len(entries)), 1), len(entries)) - 1
    e = entries[at]
    return e.get("url"), e.get("title")


def zen_copy(profile):
    sessions = os.path.join(profile, "zen-sessions.jsonlz4")
    if os.path.exists(sessions):
        session = unlz4(open(sessions, "rb").read())
        windows = [session]
    else:  # an older Zen kept its spaces in Firefox's own session file
        session = unlz4(open(os.path.join(profile, "sessionstore-backups", "recovery.jsonlz4"), "rb").read())
        windows = session.get("windows") or []
    containers = {}
    path = os.path.join(profile, "containers.json")
    if os.path.exists(path):
        for c in json.load(open(path)).get("identities") or []:
            if c.get("public", True):
                containers[c.get("userContextId")] = {**c, "name": c.get("name") or BUILT_IN.get(c.get("l10nID"), "")}

    copy = Copy("zen")
    spaces = []
    for w in windows:
        for s in w.get("spaces") or w.get("zenWorkspaces") or []:
            if s.get("uuid") and all(x["uuid"] != s["uuid"] for x in spaces):
                spaces.append(s)
    space_of = {}  # Zen's space uuid: Tidier's space id
    for s in spaces:
        c = containers.get(s.get("containerTabId")) or {}
        sid = f"zen-{s['uuid']}"
        copy.space(sid, s.get("name") or c.get("name"), c.get("color"), c.get("icon"))
        space_of[s["uuid"]] = sid
    by_container = {}
    for s in spaces:
        if s.get("containerTabId"):
            by_container.setdefault(s["containerTabId"], []).append(space_of[s["uuid"]])

    tabs = [t for w in windows for t in w.get("tabs") or []]
    folders = [f for w in windows for f in (w.get("folders") or []) + (w.get("groups") or [])]
    folder_by_id = {f.get("id"): f for f in folders if f.get("id")}

    def folder_name(f):
        names, seen = [], set()
        while f and f.get("id") not in seen:
            seen.add(f.get("id"))
            names.append(f.get("name") or f.get("label") or "Folder")
            f = folder_by_id.get(f.get("parentId"))
        return " / ".join(reversed(names))

    made = {}  # (space, Zen folder id or PINNED): Tidier's folder key

    def folder_in(sid, fid):
        if (sid, fid) not in made:
            made[(sid, fid)] = copy.folder(sid, PINNED if fid == PINNED else folder_name(folder_by_id.get(fid)))
        return made[(sid, fid)]

    # The Pinned folder first in each space, as Zen and Arc show pinned tabs above folders.
    for sid in copy.order:
        folder_in(sid, PINNED)
    for t in tabs:
        url, title = tab_url(t)
        if not is_web(url):
            continue
        name = t.get("zenStaticLabel") or (t.get("attributes") or {}).get("zen-static-label")
        if t.get("zenEssential"):
            ctx = t.get("userContextId") or 0
            owners = by_container.get(ctx) or ([space_of[t["zenWorkspace"]]] if t.get("zenWorkspace") in space_of else copy.order)
            for sid in owners:
                copy.essential(sid, url, title)
        elif t.get("pinned") and t.get("zenWorkspace") in space_of:
            sid = space_of[t["zenWorkspace"]]
            fid = t.get("groupId") if t.get("groupId") in folder_by_id else PINNED
            copy.saved(sid, folder_in(sid, fid), url, title, name)
    return copy


# --- Arc ------------------------------------------------------------------------------

def pairs(flat):
    """Arc keeps its lists as [id, object, id, object, ...]."""
    flat = flat or []
    return [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]


def profile_key(p):
    return json.dumps(p or {"default": True}, sort_keys=True)


def arc_copy(path):
    sidebar = json.load(open(path))
    containers = (sidebar.get("sidebar") or {}).get("containers") or []
    box = next((c for c in containers if "spaces" in c and "items" in c), None)
    if box is None:
        raise ValueError("no spaces in this file")
    items = {k: v for k, v in pairs(box["items"]) if isinstance(v, dict)}
    copy = Copy("arc")

    def children(item_id):
        item = items.get(item_id) or {}
        return [c for c in item.get("childrenIds") or [] if c in items]

    def tab(item):
        t = ((item.get("data") or {}).get("tab")) or {}
        return t.get("savedURL"), t.get("savedTitle")

    spaces_by_profile = {}
    for sid_arc, s in pairs(box["spaces"]):
        if not isinstance(s, dict):
            continue
        sid = f"arc-{sid_arc}"
        copy.space(sid, s.get("title"))
        spaces_by_profile.setdefault(profile_key(s.get("profile")), []).append(sid)
        ids = s.get("containerIDs") or []
        pinned = next((ids[i + 1] for i in range(len(ids) - 1) if ids[i] == "pinned"), None)
        loose = copy.folder(sid, PINNED)

        def walk(item_id, folder, path):
            for child in children(item_id):
                item = items[child]
                data = item.get("data") or {}
                if "list" in data:
                    name = item.get("title") or "Folder"
                    full = f"{path} / {name}" if path else name
                    walk(child, copy.folder(sid, full), full)
                elif "tab" in data:
                    url, title = tab(item)
                    copy.saved(sid, folder, url, title, item.get("title"))

        if pinned:
            walk(pinned, loose, "")

    top = (box.get("topAppsContainerIDs") or [])
    for profile, top_id in pairs(top):
        for child in children(top_id):
            url, title = tab(items[child])
            for sid in spaces_by_profile.get(profile_key(profile), []):
                copy.essential(sid, url, title)
    return copy


# --- The file -------------------------------------------------------------------------

def zen_profiles():
    found = []
    for root in ("~/Library/Application Support/zen", "~/Library/Application Support/Zen"):
        for p in glob.glob(os.path.join(os.path.expanduser(root), "Profiles", "*")):
            if os.path.exists(os.path.join(p, "zen-sessions.jsonlz4")) or os.path.exists(os.path.join(p, "sessionstore-backups", "recovery.jsonlz4")):
                found.append(p)
    # The profile used most recently is the one that is yours.
    return sorted(set(found), key=lambda p: -max(os.path.getmtime(f) for f in glob.glob(os.path.join(p, "*")) or [p]))


def write(copy, out):
    data = copy.result()
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.chmod(out, 0o600)
    print(f"{out}\n{copy.summary()}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--zen", help="a Zen profile folder")
    ap.add_argument("--arc", help="Arc's StorableSidebar.json")
    ap.add_argument("--out", default="~/Downloads", help="where the files go")
    args = ap.parse_args()
    out = os.path.expanduser(args.out)
    zen = [args.zen] if args.zen else ([] if args.arc else zen_profiles()[:1])
    arc = args.arc or ("" if args.zen else os.path.expanduser("~/Library/Application Support/Arc/StorableSidebar.json"))
    did = False
    for p in zen:
        write(zen_copy(p), os.path.join(out, "tidier-from-zen.json"))
        did = True
    if arc and os.path.exists(arc):
        write(arc_copy(arc), os.path.join(out, "tidier-from-arc.json"))
        did = True
    if not did:
        sys.exit("Found neither Arc nor Zen here; give --zen or --arc.")


if __name__ == "__main__":
    main()
