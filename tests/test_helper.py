#!/usr/bin/python3 -I
"""The live folders' helper (native/github-prs.py, native/feeds.py) with no Firefox, no
GitHub and no network: this test plays Firefox on the host's stdin and stdout, with a
stand-in for gh first on the PATH and a feed served from this machine. Standard library
only; `node --test` runs it too (tests/livefolders.test.mjs).

    python3 -I tests/test_helper.py
"""
import http.server
import json
import os
import socketserver
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NATIVE = os.path.join(REPO, "native")
HOST = os.path.join(NATIVE, "github-prs.py")
sys.path.insert(0, NATIVE)
import feeds  # noqa: E402

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>
<title>The channel's own title</title><link>https://news.example/</link>
<atom:link href="https://news.example/feed.xml" rel="self"/>
<item><title>One &amp;amp; <![CDATA[<b>two</b>]]>
   on two lines</title><link> https://news.example/1 </link><guid isPermaLink="false">abc</guid></item>
<item><title></title><guid>https://news.example/2</guid></item>
<item><title>Relative</title><link>/3</link></item>
<item><title>Not the web</title><link>javascript:alert(1)</link></item>
<item><title>A file</title><link>file:///etc/passwd</link></item>
<item><title>Twice</title><link>https://news.example/1</link></item>
<item><title>No address at all</title><guid isPermaLink="false">tag:4</guid></item>
<item><title>Five</title><guid>not-an-address</guid><link>https://news.example/5</link></item>
</channel></rss>"""
ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>A blog</title>
<link href="https://blog.example/"/><link rel="self" href="https://blog.example/atom.xml"/>
<entry><title type="html">Hello &lt;i&gt;there&lt;/i&gt;</title><link rel="self" href="https://blog.example/self"/>
  <link rel="alternate" href="https://blog.example/p1"/></entry>
<entry><title>Second</title><link href="p2"/></entry>
<entry><title>Only a reply link</title><link rel="replies" href="https://blog.example/r"/></entry></feed>"""
RDF = b"""<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/">
<channel rdf:about="https://old.example/"><title>Old</title><link>https://old.example/</link>
<items><rdf:Seq><rdf:li rdf:resource="https://old.example/a"/></rdf:Seq></items></channel>
<item rdf:about="https://old.example/a"><title>From 1.0</title><link>https://old.example/a</link></item></rdf:RDF>"""
MANY = b"<rss><channel>" + b"".join(b"<item><title>N%d</title><link>https://many.example/%d</link></item>" % (n, n) for n in range(60)) + b"</channel></rss>"
ENTITIES = b"""<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>
<rss><channel><item><title>&b;</title><link>https://x.example/1</link></item></channel></rss>"""
PAGE = b"<html><body><p>Sign in to go on</p></body></html>"


class Feeds(unittest.TestCase):
    def test_rss_takes_each_entry_once_with_a_plain_title_and_a_web_address(self):
        self.assertEqual(feeds.entries(RSS, "https://news.example/feed.xml"), [
            {"url": "https://news.example/1", "title": "One & two on two lines"},
            {"url": "https://news.example/2", "title": "https://news.example/2"},
            {"url": "https://news.example/3", "title": "Relative"},
            {"url": "https://news.example/5", "title": "Five"},
        ])

    def test_atom_takes_the_link_that_is_the_page(self):
        self.assertEqual(feeds.entries(ATOM, "https://blog.example/blog/atom.xml"), [
            {"url": "https://blog.example/p1", "title": "Hello there"},
            {"url": "https://blog.example/blog/p2", "title": "Second"},
        ])

    def test_rss_1_has_its_items_beside_the_channel(self):
        self.assertEqual(feeds.entries(RDF, "https://old.example/rss"), [{"url": "https://old.example/a", "title": "From 1.0"}])

    def test_only_the_first_of_them(self):
        self.assertEqual([i["title"] for i in feeds.entries(MANY, "https://many.example/", 3)], ["N0", "N1", "N2"])
        self.assertEqual(len(feeds.entries(MANY, "https://many.example/")), feeds.COUNT)

    def test_entities_of_its_own_and_a_page_that_is_no_feed_are_refused(self):
        with self.assertRaises(ValueError):
            feeds.entries(ENTITIES, "https://x.example/")
        with self.assertRaises(ValueError):
            feeds.entries(PAGE, "https://x.example/")
        with self.assertRaises(feeds.ET.ParseError):
            feeds.entries(b"<rss><channel>", "https://x.example/")

    def test_only_the_web_is_fetched(self):
        for address in ("file:///etc/passwd", "ftp://x.example/feed", "feed.xml", ""):
            with self.assertRaises(ValueError, msg=address):
                feeds.fetch(address)


class Server:
    """A feed on this machine: what a path answers is in `pages`, as (status, headers, body)."""

    def __init__(self):
        self.pages, self.asked = {}, []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                outer.asked.append((self.path, self.headers.get("User-Agent")))
                status, headers, body = outer.pages.get(self.path, (404, {}, b"no"))
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        class Quick(http.server.ThreadingHTTPServer):
            # HTTPServer's own asks the network for this machine's name, which can take half a minute.
            def server_bind(self):
                socketserver.TCPServer.server_bind(self)
                self.server_name, self.server_port = self.server_address[:2]

        self.httpd = Quick(("127.0.0.1", 0), Handler)
        self.at = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


# gh, as far as the host uses it: it writes down what it was asked, and answers a search
# with what gh's --jq would have made of GitHub's answer, and the second question with states.
GH = """#!/usr/bin/python3
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "asked.jsonl"), "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
answers = json.load(open(os.path.join(here, "answers.json")))
if answers.get("fail"):
    sys.stderr.write(answers["fail"])
    sys.exit(1)
for words, answer in answers.get("by_words", {}).items():  # a search of its own for these words
    if any(words in arg for arg in sys.argv):
        print(json.dumps(answer))
        sys.exit(0)
print(json.dumps(answers["states"] if "graphql" in sys.argv else answers["search"]))
"""


class Host(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = self.tmp.name
        os.makedirs(os.path.join(self.home, "tidier"))
        self.bin = os.path.join(self.home, "bin")
        os.makedirs(self.bin)
        gh = os.path.join(self.bin, "gh")
        with open(gh, "w") as out:
            out.write(GH)
        os.chmod(gh, os.stat(gh).st_mode | stat.S_IXUSR)
        self.server = Server()
        self.addCleanup(self.server.close)
        self.answers({"search": {"incomplete": False, "items": []}, "states": {"data": {"nodes": []}}})

    def config(self, folders):
        with open(os.path.join(self.home, "tidier", "live-folders.json"), "w") as out:
            json.dump(folders, out)

    def answers(self, answers):
        with open(os.path.join(self.bin, "answers.json"), "w") as out:
            json.dump(answers, out)

    def asked(self):
        try:
            with open(os.path.join(self.bin, "asked.jsonl")) as log:
                return [json.loads(line) for line in log]
        except FileNotFoundError:
            return []

    def ask(self, msg):
        """One message to the host as Firefox sends it, and its one answer."""
        data = json.dumps(msg).encode()
        # The stand-in first on the PATH, and nothing of this machine's own setup.
        env = {"PATH": self.bin + os.pathsep + "/usr/bin:/bin", "XDG_CONFIG_HOME": self.home, "HOME": self.home}
        run = subprocess.run([sys.executable, HOST], input=struct.pack("@I", len(data)) + data, capture_output=True, env=env, timeout=60)
        self.assertEqual(run.stderr, b"")
        (length,) = struct.unpack("@I", run.stdout[:4])
        self.assertEqual(len(run.stdout), 4 + length, "one whole answer and nothing else")
        return json.loads(run.stdout[4:])

    FOLDERS = [
        {"id": "prs", "name": "Pull requests", "container": "firefox-container-1", "search": "org:acme"},
        {"id": "todo", "name": "Issues", "container": "firefox-container-1", "search": "org:acme", "what": "issues"},
    ]

    def feed(self, **more):
        return {"id": "news", "name": "News", "container": "firefox-container-2", "feed": self.server.at + "/feed.xml", **more}

    def test_the_list_has_searches_and_feeds_and_leaves_out_what_is_neither(self):
        self.config([*self.FOLDERS, self.feed(),
                     {"id": "no", "name": "Nothing to follow", "container": "firefox-container-1"},
                     {"id": "file", "name": "A file", "container": "firefox-container-1", "feed": "file:///etc/passwd"},
                     {"id": "elsewhere", "name": "No space", "container": "somewhere", "search": "org:acme"},
                     "not a folder", None])
        self.assertEqual(self.ask({"list": True}), {"folders": [
            {"id": "prs", "name": "Pull requests", "container": "firefox-container-1"},
            {"id": "todo", "name": "Issues", "container": "firefox-container-1"},
            {"id": "news", "name": "News", "container": "firefox-container-2"},
        ]})
        self.assertEqual(self.ask({"folder": "file"}), {"error": "unknown folder"})
        self.assertEqual(self.asked(), [], "and nothing is asked of GitHub for a list")

    def test_no_file_is_no_folders_and_a_broken_one_says_so(self):
        self.assertEqual(self.ask({"list": True}), {"folders": []})
        with open(os.path.join(self.home, "tidier", "live-folders.json"), "w") as out:
            out.write("[{")
        self.assertIn("live-folders.json", self.ask({"list": True})["error"])
        self.config({"id": "prs"})
        self.assertEqual(self.ask({"list": True}), {"folders": []}, "a file that is no list has none")

    def test_pull_requests_are_searched_for_with_what_each_waits_for(self):
        self.config(self.FOLDERS)
        self.answers({
            "search": {"incomplete": False, "items": [
                {"id": "PR_1", "url": "https://github.com/acme/app/pull/7", "title": "Seven", "number": 7, "draft": False, "repo": "app"},
                {"id": "PR_2", "url": "https://github.com/acme/app/pull/8", "title": "Eight", "number": 8, "draft": True, "repo": "app"}]},
            "states": {"data": {"nodes": [
                {"id": "PR_1", "viewerDidAuthor": True, "reviewDecision": "APPROVED", "mergeable": "CONFLICTING",
                 "reviewRequests": {"nodes": []}, "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "FAILURE"}}}]}},
                None]}},
        })
        self.assertEqual(self.ask({"folder": "prs"}), {"items": [
            {"url": "https://github.com/acme/app/pull/7", "title": "Seven", "number": 7, "draft": False, "repo": "app",
             "mine": True, "review": "approved", "checks": "failing", "asked": False, "conflict": True},
            {"url": "https://github.com/acme/app/pull/8", "title": "Eight", "number": 8, "draft": True, "repo": "app"},
        ]})
        search, states = self.asked()
        self.assertEqual(search[:4], ["api", "-X", "GET", "search/issues"])
        self.assertIn("q=is:open is:pr archived:false (review-requested:@me OR author:@me OR assignee:@me) org:acme", search)
        self.assertEqual(states[:2], ["api", "graphql"])

    def test_issues_are_searched_for_as_issues_and_say_what_they_are(self):
        self.config(self.FOLDERS)
        self.answers({"search": {"incomplete": False, "items": [
            {"id": "I_1", "url": "https://github.com/acme/app/issues/3", "title": "Three", "number": 3, "draft": None, "repo": "app"}]}})
        self.assertEqual(self.ask({"folder": "todo"}), {"items": [
            {"url": "https://github.com/acme/app/issues/3", "title": "Three", "number": 3, "repo": "app", "what": "issue"}]})
        (search,) = self.asked()  # and no second question: an issue waits for nothing
        self.assertIn("q=is:open is:issue archived:false (assignee:@me OR author:@me) org:acme", search)

    def test_part_of_an_answer_and_a_gh_that_fails_are_errors_not_empty_folders(self):
        self.config(self.FOLDERS)
        for folder in ("prs", "todo"):
            self.answers({"search": {"incomplete": True, "items": []}})
            self.assertEqual(self.ask({"folder": folder}), {"error": "GitHub's search answered with only part of the result"})
            self.answers({"fail": "gh: To get started with GitHub CLI, please run:  gh auth login"})
            self.assertIn("gh auth login", self.ask({"folder": folder})["error"])
        self.assertEqual(self.ask({"folder": "nobody's"}), {"error": "unknown folder"})

    def test_your_repositories_are_those_of_your_recent_pull_requests_with_those_waiting_for_your_review_first(self):
        # (What gh's --jq makes of GitHub's answer: a repository's name for each pull request.)
        self.answers({"by_words": {
            "involves:@me": {"incomplete": False, "repos": ["acme/site", "acme/site", "acme/app", "acme/site", "../etc"]},
            "review-requested:@me": {"incomplete": False, "repos": ["acme/app", "acme/app", "acme/tools"]},
        }})
        got = self.ask({"ask": {"search": "org:acme", "what": "repos"}})
        self.assertEqual([(i["repo"], i["waiting"], i["recent"], i["url"], i["what"]) for i in got["items"]], [
            ("acme/app", 2, 1, "https://github.com/acme/app/pulls", "repo"),
            ("acme/tools", 1, 0, "https://github.com/acme/tools/pulls", "repo"),
            ("acme/site", 0, 3, "https://github.com/acme/site/pulls", "repo"),
        ])
        recent, waiting = self.asked()
        self.assertTrue(any(a.startswith("q=is:pr involves:@me archived:false updated:>=") and a.endswith(" org:acme") for a in recent), recent)
        self.assertIn("q=is:open is:pr archived:false review-requested:@me org:acme", waiting)
        self.assertIn("sort=updated", recent)
        # Only what narrows, as for any folder of the extension's own.
        self.assertEqual(self.ask({"ask": {"search": "OR author:someone", "what": "repos"}}), {"error": "not a search or a feed this helper answers"})
        self.answers({"by_words": {"involves:@me": {"incomplete": True, "repos": []}}, "search": {"incomplete": False, "repos": []}})
        self.assertEqual(self.ask({"ask": {"search": "", "what": "repos"}}), {"error": "GitHub's search answered with only part of the result"})

    def test_a_folder_of_the_extensions_own_is_the_same_search_with_only_what_narrows(self):
        # No file at all: the folder is set up on Tidier's settings page, and described in the question.
        self.answers({"search": {"incomplete": False, "items": [
            {"id": "PR_1", "url": "https://github.com/acme/app/pull/7", "title": "Seven", "number": 7, "draft": False, "repo": "app"}]}})
        got = self.ask({"ask": {"search": "  org:acme   -label:wip repo:acme/app ", "what": "prs"}})
        self.assertEqual([i["url"] for i in got["items"]], ["https://github.com/acme/app/pull/7"])
        self.assertIn("q=is:open is:pr archived:false (review-requested:@me OR author:@me OR assignee:@me) org:acme -label:wip repo:acme/app", self.asked()[0])
        os.remove(os.path.join(self.bin, "asked.jsonl"))
        self.ask({"ask": {"search": "org:acme", "what": "issues"}})
        self.assertIn("q=is:open is:issue archived:false (assignee:@me OR author:@me) org:acme", self.asked()[0])
        os.remove(os.path.join(self.bin, "asked.jsonl"))
        self.ask({"ask": {"search": ""}})
        self.assertIn("q=is:open is:pr archived:false (review-requested:@me OR author:@me OR assignee:@me)", self.asked()[0], "no words: everything open that is yours")
        os.remove(os.path.join(self.bin, "asked.jsonl"))
        # Nothing that could reach outside "open, and yours", or be more than words of the search.
        for search in ("org:acme OR is:pr", ") OR (is:issue", "org:acme) OR (author:someone", 'label:"a b"', "secret words", "org:acme\nrepo:x --jq .", "org:" + "a" * 400, 7, None, ["org:acme"]):
            self.assertEqual(self.ask({"ask": {"search": search}}), {"error": "not a search or a feed this helper answers"}, repr(search))
        for ask in ("org:acme", None, [], {"what": "prs"}, {"folder": "prs"}):
            self.assertEqual(self.ask({"ask": ask}), {"error": "not a search or a feed this helper answers"}, repr(ask))
        self.assertEqual(self.asked(), [], "and gh is asked nothing for any of them")

    def test_a_feed_of_the_extensions_own_is_fetched_as_one_in_the_file_is(self):
        self.server.pages["/feed.xml"] = (200, {"Content-Type": "application/rss+xml"}, MANY)
        got = self.ask({"ask": {"feed": self.server.at + "/feed.xml", "count": 2}})
        self.assertEqual(got, {"items": [{"url": "https://many.example/0", "title": "N0", "what": "feed"}, {"url": "https://many.example/1", "title": "N1", "what": "feed"}]})
        self.assertEqual(len(self.ask({"ask": {"feed": self.server.at + "/feed.xml"}})["items"]), 10)
        for feed in ("file:///etc/passwd", "ftp://127.0.0.1/feed.xml", "https://a.example/ feed", "javascript:1", 7, "", "https://" + "a" * 2000):
            self.assertEqual(self.ask({"ask": {"feed": feed}}), {"error": "not a search or a feed this helper answers"}, repr(feed))
        self.assertEqual(self.asked(), [])

    def test_a_feed_gives_its_newest_entries_and_asks_nothing_of_github(self):
        self.server.pages["/feed.xml"] = (200, {"Content-Type": "application/rss+xml"}, MANY)
        self.config([self.feed()])
        answer = self.ask({"folder": "news"})
        self.assertEqual(len(answer["items"]), 10)
        self.assertEqual(answer["items"][0], {"url": "https://many.example/0", "title": "N0", "what": "feed"})
        self.config([self.feed(count=3)])
        self.assertEqual([i["title"] for i in self.ask({"folder": "news"})["items"]], ["N0", "N1", "N2"])
        for count, most in ((500, 30), (0, 1), ("7", 10), (True, 10)):
            self.config([self.feed(count=count)])
            self.assertEqual(len(self.ask({"folder": "news"})["items"]), most, str(count))
        self.assertEqual(self.asked(), [])
        self.assertTrue(all(path == "/feed.xml" and "Tidier" in agent for path, agent in self.server.asked))

    def test_a_feed_that_moved_is_followed_on_the_web_only(self):
        self.server.pages["/feed.xml"] = (301, {"Location": self.server.at + "/new.xml"}, b"")
        self.server.pages["/new.xml"] = (200, {}, ATOM)
        self.config([self.feed()])
        self.assertEqual(self.ask({"folder": "news"})["items"][0], {"url": "https://blog.example/p1", "title": "Hello there", "what": "feed"})
        self.server.pages["/feed.xml"] = (302, {"Location": "file:///etc/passwd"}, b"")
        self.assertRegex(self.ask({"folder": "news"})["error"], r"^feed: ")
        self.server.pages["/feed.xml"] = (302, {"Location": "ftp://127.0.0.1/feed.xml"}, b"")
        self.assertRegex(self.ask({"folder": "news"})["error"], r"^feed: ")

    def test_a_feed_that_is_none_is_an_error_not_an_empty_folder(self):
        self.config([self.feed()])
        for page in ((200, {}, PAGE), (200, {}, b"not xml at all"), (200, {}, ENTITIES), (200, {}, b"<rss>" + b" " * (feeds.MOST_BYTES + 10) + b"</rss>")):
            self.server.pages["/feed.xml"] = page
            self.assertRegex(self.ask({"folder": "news"})["error"], r"^feed: ", page[2][:20])
        self.server.pages["/feed.xml"] = (200, {}, b"not xml at all")
        self.assertRegex(self.ask({"folder": "news"})["error"], r"^feed: not a feed")
        del self.server.pages["/feed.xml"]
        self.assertRegex(self.ask({"folder": "news"})["error"], r"^feed: .*404")
        self.server.close()
        self.assertRegex(self.ask({"folder": "news"})["error"], r"^feed: ")
        # A feed with nothing in it yet is one, and empty.
        self.server = Server()
        self.server.pages["/feed.xml"] = (200, {}, b"<rss><channel><title>New</title></channel></rss>")
        self.config([self.feed()])
        self.assertEqual(self.ask({"folder": "news"}), {"items": []})


if __name__ == "__main__":
    unittest.main(verbosity=0)
