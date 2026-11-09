# Features to aim for

What Zen, Arc and Sidebery do that is worth having in Tidier, and where
Tidier stands with each. The goal (README): Firefox and Tidier only, with as
much as possible in Tidier itself.

From: **Z** Zen, **A** Arc, **S** Sidebery.
Status: **Done**; **Partly**; **Planned** (on the way off Sidebery, see the
README); **Later** (wanted, after that); **Decide** (open question); **No**
(not wanted, with the reason).

Today "Done" often means done with Sidebery's help; the notes say so where
it matters for moving off it. "Tidier alone" is Tidier without Sidebery, behind its
setting (README, PLAN.md), which the daily browser does not use yet; "checked" means
there is a test. Nothing marked Tidier alone has been used for real yet: that starts
on the second Mac (PLAN.md, part C).

## Sidebar and tab list

| Feature | From | Status | Notes |
|---|---|---|---|
| Vertical tab list in a sidebar | Z A S | Done | Tidier alone, checked; Sidebery in the daily browser |
| Unloaded tabs shown dimmed | Z A S | Done | in Tidier's sidebar; seen in the pictures of tools/shoot.py |
| Close button, middle click to close | Z A S | Done | in Tidier's sidebar |
| New tab button at the top of the list | A Z | Done | Tidier alone |
| Drag tabs to reorder, into and out of folders | Z A S | Done | Tidier alone, checked, every window follows; also to a place among the essentials and to a space; an essential dragged out lands where it is dropped, in a folder too; marks only where a drop does something; a drop shows in its new place at once; the list scrolls at its edges |
| Select several tabs (⇧/⌘ click) and act on them | Z A S | Done | Tidier alone, checked: move, close, drag and the menu; the selection lives in the sidebar only; ⌘-click takes the selected tab along only from the same folder, or from today's tabs |
| Context menu on tabs, folders and spaces | Z A S | Done | Tidier alone, checked: Tidier's own short menu on tabs, tiles, folders, spaces and the list, just below what it is about (which is marked) and never over it; a list opens in its place; a space's menu starts with its name |
| Keyboard navigation in the sidebar | S | Done | Tidier alone: ↑↓, Enter, ⌫, ←→ |
| Search/filter the tabs | S A | Done | Tidier alone, checked, in the command bar (⌘⇧K) |
| Sound indicator and mute on a tab | Z A S | Done | Tidier alone, checked: a mark and mute on a row, a tile and a closed folder, and on a space's dot, whose mark goes to the tab that plays |
| Tab preview on hover | S | No | a picture needs access to all websites; the tooltip shows title and address |
| The list shows the selected tab, each space keeps its scroll | S | Done | Tidier alone, checked; also a selected tab in a closed folder; closing passes over closed folders and unloaded tabs |
| A mark when a background page has news | S | Done | Tidier alone, checked: a still dot on the tab, a closed folder and a space; a tab in a closed folder only keeps a dot it already has |
| A sign that a tab is loading | Z A S | Done | Tidier alone, checked: a soft sign on the icon, after half a second |
| A new tab has one place | A | Done | Tidier alone, checked: the top of today's tabs, for the button, ⌘T and links from other apps; a link from a tab stays next to it |
| Double click on the empty part of the list opens a new tab | A | Done | Tidier alone, checked |
| Title and address in the tooltip, icons kept, a tab made ready when the pointer comes to it | | Done | Tidier alone, checked; less motion when the system asks for it |
| Resizable sidebar width | Z A S | Done | Firefox's own sidebar handle (userChrome.css) |
| Compact mode: sidebar hidden, shown at the edge | Z A | Done | userChrome.css, ⌘S |
| Tabs nested under tabs (tree) | S | No | you only use folders; a tree is where most of Sidebery's bugs came from |

## Spaces

| Feature | From | Status | Notes |
|---|---|---|---|
| Spaces, one per container (own logins) | Z A S | Done | Tidier alone, checked; Sidebery's panels in the daily browser |
| Space bar at the bottom with icons | Z A S | Partly | Tidier alone shows coloured dots, and the name above the list; icons to come |
| Only the active space's tabs shown (⌃Tab too) | Z A S | Done | Tidier alone, checked. Other spaces' essentials stay in ⌃Tab: Firefox cannot hide a pinned tab |
| Switch with ⌃1/2/3 | Z A S | Done | Tidier alone, checked; Sidebery's shortcuts in the daily browser |
| Switch by swiping sideways on the trackpad | Z A | Later | tried with Sidebery and left out: vertical swipes switched space by mistake; to try again without it |
| Colour per space, for the whole window | Z A | Done | userChrome.css and tidier.css |
| New, edited and deleted spaces in Tidier: name, icon and colour | Z A S | Done | Tidier alone, checked, on the settings page and from a space's menu; dropping a tab on the bar makes a new one; Firefox's container settings aren't needed |
| Nothing goes out in the wrong container: the first request is stopped | S | Done | Tidier alone, checked with a server recording cookies; needs the optional access to all websites |
| A space's own proxy and user agent | S | Done | Tidier alone, checked; on the settings page, under More. No address bar button, and no IP lookups |
| Clear a site's cookies in one space, or a whole space's logins | S | Done | Tidier alone, checked; signing out asks first, since it can't be undone |
| A vanished container comes back | | Done | Tidier alone, checked; with its name, colour and icon, and everything that pointed at it |
| A folder to another space, and a copy of a tab | S | Done | Tidier alone, checked; each tab arrives as it was, unloaded, loaded or muted; unsaved input stays behind and says so; one line, with Undo |
| Move a tab to another space without losing anything | S | Done | Tidier alone, checked: from the menu, by dragging to a dot or from the command bar; the page and its unsaved input are kept, an unloaded tab stays unloaded and a muted one muted, and a rule does not send it back; one line says where it went, with Undo |
| New tabs and links from other apps open in the active space | A S | Done | Tidier alone, checked; Sidebery in the daily browser |
| Rules: an address always opens in a given space ("Air Traffic Control") | A S | Done | Tidier alone, checked, on the settings page, and imported from Sidebery's export, also from its panels; Sidebery's rules in the daily browser. A rule for a space that is gone does nothing and says so |
| Containers matched by name on another machine | | Done | Tidier alone, checked: copies and Sidebery's export land in the space of the same name, never by Firefox's number for it |
| Open a link in another space (context menu) | A | Done | Tidier alone, checked: "Open link in" on a link's menu, which needs no access to pages; the tab menu has "Open a copy in space" |
| Unload a whole space | S | Done | Tidier alone, checked: the space's menu; essentials, the selected tab, sound, calls and unsaved input stay; a line says how many were unloaded |
| The same essentials, folders and spaces on every machine, by sync | A | Done | Tidier alone, checked in a test Firefox, off by default, on the settings page; real Firefox Sync between two machines is not tried yet |
| Hide a space on a given machine | | Done | Tidier alone, checked: on the settings page, or for a machine in managed storage; hidden, not kept away |
| Remove a space from every machine | | Later | today removing a container on one machine is local to it |

## Essentials and kept tabs

| Feature | From | Status | Notes |
|---|---|---|---|
| Essentials as tiles at the top, per space | Z A | Done | Tidier alone, checked; Sidebery in the daily browser |
| Essentials in every window | Z | Done | |
| An essential keeps its address; closing it unloads it | Z A | Done | |
| Short names for essentials | | Done | Tidier alone, checked: Rename in the tab menu, for saved tabs too; with Sidebery set in storage |
| Only one loaded copy of an essential (no double sounds) | | Done | |
| Kept tabs (Arc's pinned section, Zen's pinned tabs): ⌘W unloads, back to the saved address | Z A | Done | tabs in folders ("saved tabs") |
| A divider between kept tabs and today's tabs | A Z | Done | in Tidier's sidebar |
| Clear today's tabs in one go | A | Done | Tidier alone, checked: from the list's menu, the space's menu and the line between folders and tabs; one line to undo it, no question |
| Undo after closing several tabs or deleting a folder | S | Done | Tidier alone, checked: one quiet line |

## Folders

| Feature | From | Status | Notes |
|---|---|---|---|
| Folders, collapsible | Z A S | Done | Tidier alone, Tidier's own data, checked; Sidebery's folder pages in the daily browser |
| Folders first in each space | Z A | Done | Tidier keeps the order (folders.js, goes away with Sidebery) |
| Create, rename and delete folders | Z A S | Done | Tidier alone, checked. Deleting one keeps its tabs, with one line to undo it |
| Folders inside folders | A | Later | none today, and a tree is what is left out |
| A closed folder rests: hidden from ⌃Tab and unloaded | S | Done | Tidier alone, checked; the selected tab, sound and unsaved input stay |
| New folder with a good name, ready to rename | S | Done | Tidier alone: from the menu, a key, or a selection, which names it after what the tabs share |
| Live folders (GitHub pull requests) | A | Done | |
| Folder state (open/closed) kept per space and window | Z A S | Partly | Tidier alone: kept per folder, the same in every window |

## Tabs that tidy themselves

| Feature | From | Status | Notes |
|---|---|---|---|
| Every tab in every window, loaded only once | Z | Done | |
| Archive tabs unused for 12 hours | A | Done | |
| Find archived tabs again | A | Done | Tidier alone, checked: Tidier's own list per space, from the list's menu, the space's menu and the command bar |
| Unload tabs unused for a while (keep them, free memory) | Z S | Later | Firefox unloads on low memory; closed folders and whole spaces unload in Tidier |
| Nothing works when nothing happens (no idle work) | | Done | checked by the smoke test, also with 300 tabs |
| Fast with many tabs | | Done | Tidier alone, checked with 300 tabs, measured up to 1000: a new window has them all in about 7 s |
| Random use never breaks what Tidier promises | | Done | checked: random sequences on the real background scripts, and a long random run in a real test Firefox |

## Windows and links

| Feature | From | Status | Notes |
|---|---|---|---|
| A new window gets every essential and tab | Z | Done | |
| Closing a window hands its tabs over | Z | Done | |
| A small window for links from other apps ("Little Arc") | A | Done | Tidier alone, checked in the test Firefox; links from real apps and whether the window comes to the front are to be tried on a Mac |
| Link preview in a floating window ("Glance", "Peek") | Z A | Done | Tidier alone, checked: "Open link in" needs no access; ⌥-click needs the optional access to all websites |
| Split view | Z A | No | Firefox has its own; Tidier stays out of its way, and it is checked with placeholders |

## Command bar and shortcuts

| Feature | From | Status | Notes |
|---|---|---|---|
| ⌘⇧C copies the address | Z A | Done | |
| A command bar: search tabs, essentials, history and commands | A Z | Done | Tidier alone, checked: ⌘⇧K (⌘T once cleared in about:keyboard), a small window; every space's tabs, essentials, folders, closed and archived tabs, and commands; history and bookmarks once allowed |
| Next and previous tab as shown, the n-th tab of this space, next and previous space | A | Done | Tidier alone, checked: ⌃⌘ and an arrow; ⌘1 to ⌘9 once Firefox's own are cleared |
| All shortcuts set in one place, in Tidier | | Done | Tidier alone, checked: the settings page's Keys section; Firefox's own keys in about:keyboard |

## Look

| Feature | From | Status | Notes |
|---|---|---|---|
| Window and sidebar as one surface, the page as a rounded card | Z A | Done | userChrome.css |
| Toolbar (back, forward, address) at the top of the sidebar | Z A | Done | userChrome.css |
| Light and dark | Z A S | Done | |
| Works at all sidebar widths (220–480 px) | | Done | checked by the smoke test |
| One design for everything Tidier draws: the window's tint as the surface, what is on it lifting towards white, the selected thing the only card, the space's colour used sparingly | A | Done | sidebar/tokens.css, linked from each page; tests/look.test.mjs keeps it whole |
| Long titles fade out instead of ending in dots, and the list dissolves where it ends | A | Done | |
| Pictures of every width, scheme and state, to work on the look with | | Done | tools/shoot.py |

## Not wanted

| Feature | From | Why |
|---|---|---|
| Bookmarks and history panels in the sidebar | S | Firefox's own are enough |
| Snapshots of all tabs | S | Tidier keeps its own record; Firefox's session restore does the rest |
| Per-site styles and scripts ("Boosts", "Mods") | A Z | not what Tidier is for |
| Notes, easels, built-in AI | A | not what Tidier is for |

## Working with Claude and other agents (stretch goal)

Off by default, and nothing reaches a machine that has not turned it on. Nothing of the
agents' space goes into sync or copies.

| Feature | From | Status | Notes |
|---|---|---|---|
| Copy a page or a list of tabs as clean text for Claude; ask Claude about a page | | Done | Tidier alone, checked; from the tab menu, the space's menu and the command bar |
| An MCP server, so Claude Code can work in the browser | | Done | Tidier alone, checked: local only, a socket only you can reach, and nothing runs while it is off; not yet tried with Claude Code itself |
| Agents have a space of their own, with its own logins | | Done | Tidier alone, checked: they see and touch only that space, unless you allow another |
| What an agent does is visible, and one click stops it | | Done | Tidier alone, checked |
