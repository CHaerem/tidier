#!/usr/bin/python3 -I
"""A stand-in for native/github-prs.py, for the smoke test.

The test Firefox starts this instead of the real host (see testfirefox.py),
so the live folders are tested without your gh login or GitHub. It answers
from the file in TIDIER_FAKE_PRS, which the test rewrites between refreshes:

    {"folders": [{"id", "name", "container"}], "items": {"<folder id>": [{url, title, number, repo}]},
     "asks": {"<the search's words, or the feed's address>": [{url, title, ...}]}}

"asks": for a folder set up on Tidier's settings page, which the extension describes in its
question ({"ask": {...}}); what it was asked is added to the file beside it (".asked").

What it is asked about Firefox itself ({"firefox": ...}) is answered by the real thing
(native/firefox_setup.py): that acts only on the Firefox that started it, which here is the
test Firefox.
"""
import json
import os
import struct
import sys


def main():
    raw = sys.stdin.buffer.read(4)
    if len(raw) < 4:
        return
    (length,) = struct.unpack("@I", raw)
    msg = json.loads(sys.stdin.buffer.read(length))
    try:
        data = json.load(open(os.environ["TIDIER_FAKE_PRS"]))
    except (KeyError, OSError, ValueError):
        data = {}
    if "firefox" in msg:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "native"))
        import firefox_setup
        reply = firefox_setup.answer(msg)
    elif "backup" in msg:
        json.dump(msg["backup"], open(os.environ["TIDIER_FAKE_PRS"] + ".copy", "w"))
        reply = {"saved": "copy"}
    elif msg.get("list"):
        reply = {"folders": data.get("folders", [])}
    elif "ask" in msg:
        ask = msg["ask"] if isinstance(msg["ask"], dict) else {}
        with open(os.environ["TIDIER_FAKE_PRS"] + ".asked", "a") as log:
            log.write(json.dumps(ask) + "\n")
        items = data.get("asks", {}).get(ask.get("feed") or ask.get("search"))
        reply = {"items": items} if items is not None else {"error": "not a search or a feed this helper answers"}
    elif msg.get("folder") in data.get("items", {}):
        reply = {"items": data["items"][msg["folder"]]}
    else:
        reply = {"error": "unknown folder"}
    out = json.dumps(reply).encode()
    sys.stdout.buffer.write(struct.pack("@I", len(out)) + out)
    sys.stdout.buffer.flush()


main()
