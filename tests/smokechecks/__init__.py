"""The smoke test's groups of checks, one file for each area. tests/smoke.py chooses and runs them.

base.py is what every group leans on. core.py holds the core groups, each in a test Firefox
where Tidier may not hide tabs. The rest is the chain (alone_*): one test Firefox of its own,
with test tabs in each space and the permission to hide tabs, the groups in order. The sidebar
is used for real: its page is opened in a tab, where the test can read and click it. (Named
for the time when this was Tidier alone, beside Sidebery.)

A group makes what it needs itself: it has to pass by itself after alone_setup, and in its
part (ALONE_SHARDS, smoke.py).
"""
