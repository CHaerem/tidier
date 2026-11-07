#!/usr/bin/python3
"""Make the test fixture of containers from your own setup, without any names of yours.

    tests/fixtures/from_backup.py

Run it again when you change containers. It reads Firefox' containers.json from your
profile (read only) and writes containers.json here, with the colours and icons, and the
names replaced by neutral ones ("Space 1"), so the fixture says nothing about you.
"""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = os.path.expanduser("~/Library/Application Support/Firefox/Profiles")

profile = glob.glob(f"{PROFILES}/*.default-release")[0]
containers = json.load(open(f"{profile}/containers.json"))
for c in containers["identities"]:
    if c.get("public") and c.get("name"):
        c["name"] = f"Space {c['userContextId']}"
json.dump(containers, open(f"{HERE}/containers.json", "w"), ensure_ascii=False, indent=1)
print("containers.json")
