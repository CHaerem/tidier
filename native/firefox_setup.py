#!/usr/bin/python3
"""Firefox's setup files, and starting Firefox again, for Tidier's native host (github-prs.py).

Firefox reads user.js and its stylesheets (chrome/userChrome.css, chrome/userContent.css)
only as it starts. A change to them does nothing until then, and nothing says so: after an
update that needed a new stylesheet, Tidier's command bar did not open, in a Firefox still
running on the old one. An extension cannot see those files, and cannot start Firefox
again; this program is outside Firefox, and can do both, for the one Firefox that started it:

  {"firefox": "changed"}  ->  {"changed": true, "files": ["userChrome.css"]}
      Whether a setup file of the profile this Firefox runs on is newer than this Firefox.
  {"firefox": "restart"}  ->  {"restarting": true}
      Firefox is asked to quit as with Cmd-Q (so it saves its session, and asks what it
      asks), and is opened again once it has gone. A Firefox that stays, because you said
      so in a question it asked, is left alone.

It only ever acts on its own parent process, found by its process id, and only if that is
a Firefox: nothing is done by an app's name, so no other Firefox on the machine is touched.

Not customKeys.json: Firefox writes that file itself when you change a key in
about:keyboard, which needs no restart.
"""
import ctypes
import ctypes.util
import glob
import os
import struct
import subprocess
import sys
import time

FILES = ("user.js", os.path.join("chrome", "userChrome.css"), os.path.join("chrome", "userContent.css"))
PROFILES = os.path.expanduser("~/Library/Application Support/Firefox/Profiles")
QUIT_WAIT_S = 90  # a question Firefox asks before it quits is yours to answer: this long, and no longer


def arguments(pid):
    """The command line of a process, word for word (ps joins the words, and a path can hold spaces)."""
    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    mib = (ctypes.c_int * 3)(1, 49, pid)  # CTL_KERN, KERN_PROCARGS2
    size = ctypes.c_size_t(0)
    if libc.sysctl(mib, 3, None, ctypes.byref(size), None, 0) != 0:
        return []
    buf = ctypes.create_string_buffer(size.value)
    if libc.sysctl(mib, 3, buf, ctypes.byref(size), None, 0) != 0:
        return []
    raw = buf.raw[:size.value]
    (argc,) = struct.unpack("@i", raw[:4])
    rest = raw[4:].split(b"\0")
    words = [w for w in rest[1:] if w][:argc]  # after the program's path and the zeros that pad it
    return [w.decode(errors="replace") for w in words]


def firefox(pid=None):
    """The Firefox that started this host: its process id, its command line and its app, or nothing."""
    pid = pid or os.getppid()
    argv = arguments(pid)
    if not argv or os.path.basename(argv[0]) not in ("firefox", "firefox-bin"):
        return None
    app = argv[0].split("/Contents/MacOS/")[0] if "/Contents/MacOS/" in argv[0] else None
    return {"pid": pid, "argv": argv, "app": app}


def started(pid):
    """When a process started, in seconds since 1970."""
    out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True, env={**os.environ, "LC_ALL": "C"}).stdout.strip()
    return time.mktime(time.strptime(out, "%a %b %d %H:%M:%S %Y")) if out else None


def profiles(argv):
    """The profile this Firefox runs on, where its command line says; else every profile there is."""
    for i, word in enumerate(argv[:-1]):
        if word in ("-profile", "--profile"):
            return [argv[i + 1]]
    return sorted(glob.glob(os.path.join(PROFILES, "*")))


def changed(pid=None):
    """The setup files that are newer than the Firefox that reads them only as it starts."""
    fx = firefox(pid)
    since = fx and started(fx["pid"])
    if not since:
        return {"error": "not started by a Firefox"}
    newer = set()
    for profile in profiles(fx["argv"]):
        for name in FILES:
            try:
                # (Followed through a link: the dotfiles link these files to their checkout.)
                if os.path.getmtime(os.path.join(profile, name)) > since + 1:
                    newer.add(os.path.basename(name))
            except OSError:
                pass  # no such file in this profile
    return {"changed": bool(newer), "files": sorted(newer)}


def restart(pid=None):
    """Hand over to a process of its own, which outlives the Firefox that is about to quit."""
    fx = firefox(pid)
    if not fx:
        return {"error": "not started by a Firefox"}
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "--restart", str(fx["pid"])],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)
    return {"restarting": True}


def quit_and_open(pid):
    fx = firefox(pid)
    if not fx:
        return 1
    # As Cmd-Q does: Firefox saves its session and asks what it asks. (A signal would not:
    # Firefox on a Mac does not quit by SIGTERM in an orderly way.)
    script = ('ObjC.import("AppKit"); const app = $.NSRunningApplication.runningApplicationWithProcessIdentifier(%d);'
              ' app.isNil() ? "none" : String(app.terminate)') % pid
    asked = subprocess.run(["osascript", "-l", "JavaScript", "-e", script], capture_output=True, text=True, timeout=30)
    if asked.stdout.strip() != "true":
        return 1
    end = time.time() + QUIT_WAIT_S
    while time.time() < end:
        # Gone, or only its entry left until whoever started it has looked (a Z): the same here.
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
        if not state or state.startswith("Z"):
            break
        time.sleep(0.2)
    else:
        return 1  # it stayed: you said so, or a page did
    time.sleep(0.5)  # the profile's lock is let go as the process ends
    # Started as an app (from the Dock, by a link): opened as one again. Started with words of
    # its own (a profile, a test): started with the same words.
    plain = [w for w in fx["argv"][1:] if not w.startswith("-psn_") and w != "-foreground"]
    if fx["app"] and not plain:
        subprocess.Popen(["open", "-a", fx["app"]], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(fx["argv"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return 0


def answer(msg):
    """What the host answers to {"firefox": ...}."""
    if msg.get("firefox") == "changed":
        return changed()
    if msg.get("firefox") == "restart":
        return restart()
    return {"error": "unknown"}


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--restart" and sys.argv[2].isdigit():
        sys.exit(quit_and_open(int(sys.argv[2])))
    sys.exit(2)
