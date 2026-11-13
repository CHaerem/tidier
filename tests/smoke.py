#!/usr/bin/python3
"""Smoke test for Tidier and the Firefox setup in dotfiles.

    tests/smoke.py              # this folder, as a temporary add-on
    tests/smoke.py --installed  # the signed version installed in your Firefox
    tests/smoke.py --xpi FILE   # a given signed .xpi
    tests/smoke.py --only tab_sync,saved_tabs  # only these groups (the def names below)
    tests/smoke.py --serial     # all groups in one test Firefox
    tests/smoke.py --part core  # one half of --serial (or --part alone), as on GitHub
    tests/smoke.py --port 3000  # on other ports, to run beside another smoke test

By default the groups run in several test Firefoxes at once: the core groups
(GROUPS, in SHARDS) and the chain (ALONE_GROUPS, in one Firefox, in order). The
logic that needs no Firefox has unit tests instead: `node --test` (in this repo).

It runs in an invisible test Firefox with a throwaway profile (see
testfirefox.py), so it never touches your own Firefox: no restart, no window,
no clipboard. The profile is built from dotfiles and tests/fixtures, with test
tabs in each space. Each group of checks runs on its own; a check that crashes
is reported as failed. The core groups check, where Tidier may not hide tabs,
that:

  - a new window gets every essential and synced tab, unloaded, with the same
    essentials and folders per container;
  - selecting a ghost pulls the live tab in, and leaves no placeholder in
    Recently Closed; a ghost takes its live tab's new title; closing a tab
    closes it everywhere; closing a window hands its tabs over, and reopening
    it doubles nothing;
  - a tab in a folder is saved: closing it while loaded unloads it in its
    place in every window, back to the address it had when it came into the
    folder; ⌘⇧T takes its placeholder's place; closing it unloaded, or after
    dragging it out of the folder, closes it everywhere;
  - pinning a tab makes it an essential everywhere, also when the tab is a
    ghost; unpinning a copy removes it everywhere, and the copy you unpinned
    opens its page; an essential copy opens the real page in its container;
    an essential dragged to another window is there once, and comes back in
    the window it left; an essential is loaded in one window only, and is
    renamed by its own page, but not by a page on another site (a sign-in it
    redirects to);
  - a placeholder of a tab that no longer exists closes itself;
  - a popup window (as for signing in) is left out of tab sync;
  - unloaded essential copies show the essential's name;
  - the extension starts again after being disabled and enabled;
  - archiving closes a tab unused for longer than the limit everywhere, keeps
    newer tabs, folder tabs and selected tabs, and leaves only the real page
    (no placeholders) in Recently Closed;
  - ⌘⇧C copies the address; ⌘B leaves Tidier in the sidebar; ⌘S switches
    compact mode on and off;
  - the toolbar follows the sidebar's width (its narrowest to its widest), and ⌘L opens the
    address bar centred with its results under it, also in compact mode;
  - a live folder (with a stand-in for the native host) has its pull requests
    unloaded in every window; a closed pull request stays closed, one that
    leaves the search is removed everywhere, a renamed one takes its new
    title, and a failed search changes nothing;
  - with ten more essentials and thirty more tabs, a new window still gets
    them all, in their containers, and they all go when closed; with nothing
    happening Tidier does nothing, and its lists in memory shrink again;
  - after an update over a running session, and after Firefox is quit and
    started again, both windows have the same essentials and tabs, one live
    tab each, folders with their tabs, and tab sync and new windows still work
    (only where Tidier can be installed for real: Developer Edition, or --xpi);
  - a browser that never moved over from Sidebery is moved at its first start:
    a copy first, then its folders as Tidier's own, then their pages closed, and
    its sidebar says so until you have seen it.

The chain (alone_*) checks everything else, with tabs hidden as once you allow it: spaces,
folders, the sidebar and its menus, keys, the command bar, isolation, small windows for links,
sync, and the bridge to agents, end to end through the real MCP server, socket and host
(alone_bridge): off means no socket and no process; an agent sees and touches only its own
space, and is refused elsewhere, also past the server; what comes from a page is marked as
untrusted; Stop cuts it at once.
"""
import glob
import os
import re
import subprocess
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from testfirefox import EXT_DIR, EXT_ID, PORT, TestFirefox  # noqa: E402
from smokechecks.base import (  # noqa: E402
    H, check, close_sidebar_page, no_problems, results, sidebar_page, to_folder,
)
from smokechecks.core import (  # noqa: E402
    archiving, essentials, ghost_title, handover, live_folders, look, many_tabs, new_window,
    old_browser, orphans, pinned_ghost, popups, reopened_window, restart, saved_tabs, shortcuts,
    tab_sync, update,
)
from smokechecks.folders import (  # noqa: E402
    alone_archive, alone_archived, alone_drag, alone_drag_details, alone_folders, alone_folds_rest, alone_folds_rest_kept, alone_live_folders,
    alone_moves, alone_safe_moves,
)
from smokechecks.hand import (  # noqa: E402
    alone_hand, alone_quiet_undo, alone_selection, alone_stay_put,
)
from smokechecks.isolation import (  # noqa: E402
    alone_crossing, alone_isolation, alone_isolation_start, alone_requests,
)
from smokechecks.keys import (  # noqa: E402
    alone_bar_edges, alone_command_bar, alone_keyboard, alone_shortcuts,
)
from smokechecks.lasting import (  # noqa: E402
    alone_chaos, alone_end, alone_idle, alone_many, alone_restart, alone_update,
)
from smokechecks.marks import (  # noqa: E402
    alone_look, alone_motion, alone_news, alone_pause, alone_sound, alone_swipe, alone_touches,
)
from smokechecks.rows import (  # noqa: E402
    alone_away, alone_link_drop, alone_more, alone_new_tab, alone_tab_menu, alone_tab_names,
)
from smokechecks.settings import (  # noqa: E402
    alone_bridge, alone_copy, alone_copy_and_import, alone_settings,
)
from smokechecks.spaces import (  # noqa: E402
    alone_keys, alone_second_window, alone_setup, alone_space_menu, alone_spaces, alone_sync_hide,
)
from smokechecks.windows import (  # noqa: E402
    alone_little_restart, alone_little_window,
)
from smokechecks import base  # noqa: E402


# The windows whose essentials (pinned tabs) are not together by space, with the
# containers of their pinned tabs in order: essentials.js keeps them so, for ⌃Tab.
PINS_APART = """
  const apart = cs => !cs.every((c, i) => i === 0 || c === cs[i - 1] || !cs.slice(0, i).includes(c));
  const ws = wins().map(w => w.gBrowser.tabs.filter(t => t.pinned).map(t => t.userContextId + ":" + (ek(w, t) || "-").slice(0, 4)));
  if (!ws.some(cs => apart(cs.map(c => c.split(":")[0])))) return null;
  const list = (await storage("%s", ["essentials"])).essentials.map(e => e.cookieStoreId.slice(-1) + ":" + e.key.slice(0, 4));
  return {windows: ws, list};""" % EXT_ID


apart_after = []


ALONE_GROUPS = (alone_setup, alone_second_window, alone_spaces, alone_keys, alone_folders, alone_moves, alone_drag, alone_archive, alone_live_folders,
                alone_drag_details,
                alone_settings, alone_copy, alone_copy_and_import,
                alone_safe_moves,
                alone_quiet_undo,
                alone_tab_menu,
                alone_tab_names,
                alone_selection,
                alone_space_menu,
                alone_look,
                alone_more,
                alone_stay_put,
                alone_swipe,
                alone_away,
                alone_link_drop,
                alone_motion,
                alone_hand,
                alone_new_tab,
                alone_folds_rest,
                alone_sound,
                alone_pause,
                alone_news,
                alone_touches,
                alone_little_window,
                alone_isolation,
                alone_requests,
                alone_crossing,
                alone_archived,
                alone_command_bar,
                alone_bar_edges,
                alone_shortcuts,
                alone_keyboard,
                alone_sync_hide,
                alone_bridge,
                alone_many,
                alone_chaos,
                alone_idle, alone_update, alone_folds_rest_kept, alone_end, alone_restart, alone_folds_rest_kept, alone_isolation_start, alone_little_restart)


# The same groups in parts, each in a test Firefox of its own that starts from the same
# fixture, so that they can run at the same time (here, and on GitHub each on its own
# runner): the whole chain in one Firefox takes most of an hour, and a group that fails
# only after forty minutes of other groups is slow to find and slow to check again.
# Each part ends with nothing happening (alone_idle) and no problems (alone_end); the
# last one also has the update and the restarts, after the groups those look back at.
# About equally long: 10 to 14 minutes each on a Mac. (alone_more is in the first: that one
# has the second window, which its keys are checked in too.)
ALONE_SHARDS = (
    (alone_setup, alone_second_window, alone_spaces, alone_keys, alone_folders, alone_moves, alone_drag, alone_archive, alone_live_folders,
     alone_drag_details, alone_settings, alone_copy, alone_copy_and_import, alone_safe_moves, alone_more, alone_idle, alone_end),
    (alone_setup, alone_quiet_undo, alone_tab_menu, alone_tab_names, alone_selection, alone_space_menu, alone_look, alone_stay_put, alone_swipe, alone_away, alone_link_drop, alone_motion, alone_idle, alone_end),
    (alone_setup, alone_hand, alone_new_tab, alone_sound, alone_pause, alone_news, alone_touches, alone_little_window, alone_isolation, alone_idle, alone_end),
    (alone_setup, alone_requests, alone_crossing, alone_archived, alone_command_bar, alone_bar_edges, alone_shortcuts, alone_keyboard, alone_idle, alone_end),
    (alone_setup, alone_folds_rest, alone_sync_hide, alone_bridge, alone_many, alone_chaos,
     alone_idle, alone_update, alone_folds_rest_kept, alone_end, alone_restart, alone_folds_rest_kept, alone_isolation_start, alone_little_restart),
)


assert {g for shard in ALONE_SHARDS for g in shard} == set(ALONE_GROUPS), "every group of the chain is in a part"


# The core of tab sync, essentials and saved tabs, each group on its own, in test Firefoxes
# where Tidier may not hide tabs: as on a browser moved over from Sidebery by itself, before
# its sidebar has been asked to (seed_folders makes a folder in each space first).
GROUPS = (new_window, essentials, tab_sync, saved_tabs, ghost_title,
          pinned_ghost, orphans, popups, archiving, shortcuts, look,
          live_folders, many_tabs, handover, reopened_window, update, restart, old_browser)


# What a group needs run before it (as setup, reported only if it fails) when
# it runs without it: the second window new_window opens, and the window
# handover closes, which reopened_window reopens.
NEEDS = {g: [new_window] for g in (essentials, tab_sync, saved_tabs, ghost_title, pinned_ghost,
                                   archiving, live_folders, many_tabs, handover, old_browser)}


NEEDS[reopened_window] = [new_window, handover]


NEEDS[update] = [new_window]


# By default the groups run in these parallel runs, each in its own test
# Firefox, about equally long (the whole test in about a third of the time).
SHARDS = (
    (new_window, orphans, popups, shortcuts, look, ghost_title, saved_tabs),
    (essentials, tab_sync, pinned_ghost, old_browser),
    (archiving, live_folders, many_tabs, handover, reopened_window, update, restart),
)


def seed_folders(m):
    """A folder of Tidier's own in each space, made as the sidebar makes one, with two tabs in it:
    fixture-in-folder-<space>-1 and -2, in Fixture folder <space>."""
    m.js(H + """const w = main();
      for (const ctx of [1, 2, 3]) for (const i of [1, 2]) { w.gBrowser.addTrustedTab("https://example.org/?fixture-in-folder-" + ctx + "-" + i, {userContextId: ctx, inBackground: true}); await wait(300); }
      await wait(4000); return 1;""")
    sidebar_page(m, """for (const ctx of [1, 2, 3]) send({type: "newFolder", space: "firefox-container-" + ctx, name: "Fixture folder " + ctx});
      await wait(1500); return 1;""")
    for ctx in (1, 2, 3):
        for i in (1, 2):
            to_folder(m, f"https://example.org/?fixture-in-folder-{ctx}-{i}", f"Fixture folder {ctx}")
    close_sidebar_page(m)
    made = m.js(H + """const all = (await storage(args[0], ["syncedTabs"])).syncedTabs;
      return Object.values(all).filter(e => /fixture-in-folder/.test(e.url || "") && all[e.parentKey]?.group && e.saved).length;""", EXT_ID)
    if made != 6:
        check("(setup: a folder with two tabs in each space)", False, f"{made} of 6 tabs in their folders")


def run_alone(groups, xpi, port, order=None):
    """Run the chain's groups in a test Firefox of their own, in ALONE_GROUPS order (or the given one)."""
    with TestFirefox(xpi=xpi, port=port) as m:
        for group in [g for g in order or ALONE_GROUPS if g in groups]:
            t0 = time.time()
            try:
                group(m)
            except Exception:
                check(f"{group.__name__} ran", False, traceback.format_exc(limit=2).strip().splitlines()[-1])
                m.chrome()
            print(f"TIME  {group.__name__} {round(time.time() - t0)} s", flush=True)


def run_groups(groups, xpi, port):
    """Run some groups in one test Firefox, in GROUPS order."""
    with TestFirefox(xpi=xpi, port=port, hiding=False) as m:
        seed_folders(m)
        needed = {n for g in groups for n in NEEDS.get(g, [])} - set(groups)
        setup = [g for g in GROUPS if g in needed]
        for group in setup + [g for g in GROUPS if g in groups]:
            base.setup_only = group in setup
            t0 = time.time()
            try:
                group(m)
            except Exception:
                check(f"{group.__name__} ran", False, traceback.format_exc(limit=2).strip().splitlines()[-1])
                m.chrome()
            # Each space's essentials stay together (essentials.js), whatever a group did.
            apart = m.js(H + PINS_APART)
            if apart:
                apart_after.append((group.__name__, apart))
                print(f"INFO  essentials apart from their space after {group.__name__}: {apart}", flush=True)
            if not base.setup_only:
                print(f"TIME  {group.__name__} {round(time.time() - t0)} s", flush=True)
        base.setup_only = False
        if restart not in groups and old_browser not in groups:  # which end with a new background page, and check before it
            no_problems(m, "by the end of the run")
    check("every window's essentials stay together by space", not apart_after, str(apart_after[:2]))


def run_parallel(argv, base=PORT):
    """Run SHARDS and ALONE_SHARDS at the same time, each as `smoke.py --only ...` or `--part alone-N` with a port of its own, and add up."""
    runs = [["--only", ",".join(g.__name__ for g in shard)] for shard in SHARDS] + [["--part", f"alone-{i + 1}"] for i in range(len(ALONE_SHARDS))]
    procs = [subprocess.Popen([sys.executable, "-I", os.path.abspath(__file__), *run, "--port", str(base + 1 + i), *argv],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
             for i, run in enumerate(runs)]
    passed = total = 0
    for p in procs:
        out = p.communicate()[0]
        for line in out.splitlines():
            if line.startswith(("PASS", "FAIL", "SKIP", "INFO", "TIME")):
                print(line, flush=True)
            elif m := re.match(r"(\d+)/(\d+) passed", line):
                passed, total = passed + int(m[1]), total + int(m[2])
        if p.returncode and not re.search(r"^\d+/\d+ passed", out, re.M):
            print(f"FAIL  a parallel run crashed:\n{out[-1500:]}", flush=True)
            total += 1
    return passed, total


def main():
    args = sys.argv[1:]
    xpi, passthrough = None, []
    if "--xpi" in args:
        xpi = args[args.index("--xpi") + 1]
        passthrough = ["--xpi", xpi]
    elif "--installed" in args:
        xpi = glob.glob(os.path.expanduser(f"~/Library/Application Support/Firefox/Profiles/*.default-release/extensions/{EXT_ID}.xpi"))[0]
        passthrough = ["--installed"]
    port = int(args[args.index("--port") + 1]) if "--port" in args else PORT
    t0 = time.time()
    if "--only" in args:
        names = args[args.index("--only") + 1].split(",")
        unknown = [n for n in names if n not in {g.__name__ for g in GROUPS + ALONE_GROUPS}]
        if unknown:
            raise SystemExit(f"Unknown group(s) {unknown}; groups: {', '.join(g.__name__ for g in GROUPS + ALONE_GROUPS)}")
        print(f"Testing {xpi or EXT_DIR} in a test Firefox: {', '.join(names)}", flush=True)
        if any(g.__name__ in names for g in GROUPS):
            run_groups({g for g in GROUPS if g.__name__ in names}, xpi, port)
        if any(g.__name__ in names for g in ALONE_GROUPS):
            run_alone({g for g in ALONE_GROUPS if g.__name__ in names}, xpi, port)
        passed, total = sum(results), len(results)
    elif "--serial" in args:
        print(f"Testing {xpi or EXT_DIR} in a test Firefox", flush=True)
        run_groups(set(GROUPS), xpi, port)
        run_alone(set(ALONE_GROUPS), xpi, port)
        passed, total = sum(results), len(results)
    elif "--part" in args:
        # One part of the whole, so that GitHub can run each on a runner of its own: the core
        # groups, the chain in one Firefox (alone), or one of its parts in a Firefox of its
        # own (alone-1 to alone-5: ALONE_SHARDS).
        part = args[args.index("--part") + 1]
        parts = ["core", "alone"] + [f"alone-{i + 1}" for i in range(len(ALONE_SHARDS))]
        if part not in parts:
            raise SystemExit(f"--part is one of {', '.join(parts)}")
        print(f"Testing {xpi or EXT_DIR} in a test Firefox: the {part} part", flush=True)
        if part == "core":
            run_groups(set(GROUPS), xpi, port)
        elif part == "alone":
            run_alone(set(ALONE_GROUPS), xpi, port)
        else:
            shard = ALONE_SHARDS[int(part.split("-")[1]) - 1]
            run_alone(set(shard), xpi, port, order=shard)
        passed, total = sum(results), len(results)
    else:
        print(f"Testing {xpi or EXT_DIR} in {len(SHARDS) + len(ALONE_SHARDS)} test Firefoxes at once", flush=True)
        passed, total = run_parallel(passthrough, port)
    print(f"\n{passed}/{total} passed in {round(time.time() - t0)} s")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
