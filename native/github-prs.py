#!/usr/bin/python3
# Native messaging host for Tidier: its live folders, and its daily copy.
#
# The folders are set up in a local file, not in the extension or this
# repository: $XDG_CONFIG_HOME/tidier/live-folders.json (default
# ~/.config/tidier/), see live-folders.example.json. The extension can
# ask for the list of folders ({"list": true}) and for what is in one of them
# ({"folder": id}); it cannot run any other search or gh command, or name an
# address to fetch, and no GitHub token ever reaches the browser. A folder is
# a GitHub search for pull requests, or for issues ("what": "issues"), which
# runs with the gh CLI and your existing gh login; or a feed ("feed": its
# address, feeds.py), which needs neither.
#
# The extension can also hand over a copy of its own data ({"backup": ...}), since
# it cannot write files itself: kept next to the config, the last COPIES days. It
# holds your addresses, so only you can read it.
#
# And it can be asked whether Firefox's setup files have changed since Firefox started, and
# to start Firefox again ({"firefox": ...}, firefox_setup.py): an extension can do neither.
#
# Installed for Firefox by install.sh.
import getpass
import glob
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time

HOME = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "tidier")
CONFIG = os.path.join(HOME, "live-folders.json")
COPIES = 14
# A folder of pull requests shows the open ones you are involved in, within its search;
# one of issues, the open ones that are yours to do or that you wrote.
BASE = "is:open is:pr archived:false (review-requested:@me OR author:@me OR assignee:@me)"
ISSUES = "is:open is:issue archived:false (assignee:@me OR author:@me)"
JQ = '{incomplete: .incomplete_results, items: [.items[] | {id: .node_id, url: .html_url, title, number, draft, repo: (.repository_url | split("/") | .[-1])}]}'
# What each of them waits for, for the icon before its name: the search does not say.
STATE = """{nodes(ids:%s){... on PullRequest{id viewerDidAuthor reviewDecision mergeable
  reviewRequests(first:50){nodes{requestedReviewer{... on User{isViewer}}}}
  commits(last:1){nodes{commit{statusCheckRollup{state}}}}}}}"""
REVIEW = {"APPROVED": "approved", "CHANGES_REQUESTED": "changes", "REVIEW_REQUIRED": "wanted"}
CHECKS = {"SUCCESS": "ok", "FAILURE": "failing", "ERROR": "failing", "PENDING": "running", "EXPECTED": "running"}


def folders():
    try:
        items = json.load(open(CONFIG))
    except FileNotFoundError:
        return []
    text = lambda f, k: isinstance(f.get(k), str) and bool(f[k])
    # A search, or a feed's address; an entry with neither is left out, as one without a name is.
    ok = lambda f: isinstance(f, dict) and all(text(f, k) for k in ("id", "name", "container")) and (
        text(f, "search") or (text(f, "feed") and re.match(r"https?://", f["feed"]) is not None))
    return [f for f in items if ok(f) and f["container"].startswith("firefox-")] if isinstance(items, list) else []


def gh():
    # Firefox starts the host with a short PATH; look where gh is usually installed too.
    extra = ["/opt/homebrew/bin", "/usr/local/bin", f"/etc/profiles/per-user/{getpass.getuser()}/bin",
             os.path.expanduser("~/.nix-profile/bin"), "/run/current-system/sw/bin"]
    return shutil.which("gh", path=os.pathsep.join([os.environ.get("PATH", ""), *extra]))


def states(ids):
    # A second question, and whatever goes wrong with it the list still stands: a folder
    # without these only shows plainer icons. (The ids go into the question as they are, so
    # only what looks like one of GitHub's does.)
    ids = [i for i in ids if isinstance(i, str) and re.fullmatch(r"[A-Za-z0-9_=-]+", i)]
    if not ids:
        return {}
    try:
        result = subprocess.run([gh(), "api", "graphql", "-f", "query=" + STATE % json.dumps(ids)],
                                capture_output=True, text=True, timeout=20)
        nodes = json.loads(result.stdout)["data"]["nodes"]  # with an error for one of them, the others are still there
    except Exception:
        return {}
    out = {}
    for n in nodes:
        if not isinstance(n, dict) or "id" not in n:
            continue
        commits = ((n.get("commits") or {}).get("nodes") or [{}])
        rollup = ((commits[-1] or {}).get("commit") or {}).get("statusCheckRollup") or {}
        asked = ((n.get("reviewRequests") or {}).get("nodes") or [])
        out[n["id"]] = {
            "mine": bool(n.get("viewerDidAuthor")),
            "review": REVIEW.get(n.get("reviewDecision"), ""),
            "checks": CHECKS.get(rollup.get("state"), ""),
            "asked": any(((r or {}).get("requestedReviewer") or {}).get("isViewer") for r in asked),
            "conflict": n.get("mergeable") == "CONFLICTING",
        }
    return out


def read_message():
    raw = sys.stdin.buffer.read(4)
    if len(raw) < 4:
        return {}
    (length,) = struct.unpack("@I", raw)
    return json.loads(sys.stdin.buffer.read(length))


def send(obj):
    data = json.dumps(obj).encode()
    sys.stdout.buffer.write(struct.pack("@I", len(data)) + data)
    sys.stdout.buffer.flush()


def save_copy(copy):
    folder = os.path.join(HOME, "copies")
    os.makedirs(folder, mode=0o700, exist_ok=True)
    name = time.strftime("tidier-%Y-%m-%d.json")
    tmp = os.path.join(folder, name + ".part")
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as out:
        json.dump(copy, out)
    os.replace(tmp, os.path.join(folder, name))
    for old in sorted(glob.glob(os.path.join(folder, "tidier-*.json")))[:-COPIES]:
        os.remove(old)
    return name


def main():
    msg = read_message()
    if "firefox" in msg:
        import firefox_setup  # beside this file; only when asked for
        send(firefox_setup.answer(msg))
        return
    if "backup" in msg:
        try:
            send({"saved": save_copy(msg["backup"])})
        except OSError as err:
            send({"error": str(err)[:300]})
        return
    try:
        configured = folders()
    except ValueError as err:  # a typo in the config: say so, rather than crash without an answer
        send({"error": f"{CONFIG}: {err}"[:300]})
        return
    if msg.get("list"):
        send({"folders": [{k: f[k] for k in ("id", "name", "container")} for f in configured]})
        return
    folder = next((f for f in configured if f["id"] == msg.get("folder")), None)
    if not folder:
        send({"error": "unknown folder"})
        return
    if not (isinstance(folder.get("search"), str) and folder["search"]):
        import feeds  # beside this file; only for a folder that is one
        send(feeds.answer(folder))
        return
    if not gh():
        send({"error": "gh not found"})
        return
    issues = folder.get("what") == "issues"
    try:
        result = subprocess.run(
            [gh(), "api", "-X", "GET", "search/issues", "-f", f"q={ISSUES if issues else BASE} {folder['search']}",
             "-f", "advanced_search=true", "-f", "per_page=100", "--jq", JQ],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as err:  # timeout, ...
        send({"error": str(err)[:300]})
        return
    if result.returncode != 0:
        send({"error": result.stderr.strip()[:300]})
        return
    answer = json.loads(result.stdout or "{}")
    # GitHub's search can answer with only part of the result when it runs out of time.
    # Taken as complete, tabs of pull requests that are still open would be closed.
    if answer.get("incomplete") or not isinstance(answer.get("items"), list):
        send({"error": "GitHub's search answered with only part of the result"})
    elif issues:
        # An issue waits for nothing the search does not say: it is open, and it is yours.
        send({"items": [{**{k: v for k, v in i.items() if k not in ("id", "draft")}, "what": "issue"} for i in answer["items"]]})
    else:
        more = states([i.get("id") for i in answer["items"]])
        send({"items": [{**{k: v for k, v in i.items() if k != "id"}, **more.get(i.get("id"), {})} for i in answer["items"]]})


main()
