# Features to aim for

What Zen, Arc and Sidebery do that is worth having in Tidier, and where
Tidier stands with each. The goal (README): Firefox and Tidier only, with as
much as possible in Tidier itself.

From: **Z** Zen, **A** Arc, **S** Sidebery.
Status: **Done**; **Partly**; **Planned**; **Later** (wanted, after that); **Decide**
(open question); **No** (not wanted, with the reason).

Everything here is Tidier's own: Sidebery is not used any more (README). "Checked" means
there is a test. What a test Firefox cannot show is tried on the second Mac (PLAN.md,
part C).

## Sidebar and tab list

| Feature | From | Status | Notes |
|---|---|---|---|
| Vertical tab list in a sidebar | Z A S | Done | checked |
| Unloaded tabs shown dimmed | Z A S | Done | seen in the pictures of tools/shoot.py |
| Close button, middle click to close | Z A S | Done | in Tidier's sidebar; checked with real clicks: a middle click closes also with Firefox's autoscroll on, a double click on × closes one tab, and the row folds away at once, the rows below coming up into its place in one soft move, as in Zen and Arc (no hole is left where it was) |
| New tab button at the top of the list | A Z | Done | |
| Drag tabs to reorder, into and out of folders | Z A S | Done | checked, every window follows; also to a place among the essentials and to a space; an essential dragged out lands where it is dropped, in a folder too; marks only where a drop does something; a drop shows in its new place at once; the list scrolls at its edges |
| Select several tabs (⇧/⌘ click) and act on them | Z A S | Done | checked: move, close, drag and the menu; the selection lives in the sidebar only; ⌘-click takes the selected tab along only from the same folder, or from today's tabs |
| Context menu on tabs, folders and spaces | Z A S | Done | checked: Tidier's own short menu on tabs, tiles, folders, spaces and the list, just below what it is about (which is marked) and never over it; a list opens in its place; a space's menu starts with its name |
| Sort tabs, close duplicates, close the tabs above, below or around one, to the top or bottom | S | Done | checked: under More at the end of a tab's, a folder's and a space's menu, in the command bar, and keys if you give them; what closes has Undo |
| Reload, mute or unload a whole folder or space | S | Done | checked: More in its menu; a few pages at a time |
| Copy tabs as Markdown links | | Done | checked: More, and the command bar |
| Select all, and extend or move the selection with the keys | S | Done | checked: ⌘A, ⇧↑ ⇧↓, ⌥↑ ⌥↓ in the sidebar, in every window |
| Back and forward through the tabs used recently | A Z | Done | checked: by each page's real last use, this space as drawn; a command with no key until you give one |
| A dragged tab held over a closed folder or another space opens it | S A | Done | checked with synthetic drags; a real trackpad waits for the second Mac |
| Keyboard navigation in the sidebar | S | Done | checked: ↑↓, the essentials' grid, Home and End, Enter or Space, ⌫, ←→ to fold, F2 to rename, ⇧F10 or ⌃↵ for the menu; one place and one ring for the keyboard. Firefox gives no key to put the keyboard there, and gives it to the page whenever the selected tab changes |
| Rows, folders, essentials and spaces for a screen reader | | Done | checked: a tree of tabs and folders with what is selected and open, the essentials a list to choose from, each space's dot named by its space and the one you are in marked; not yet heard with VoiceOver |
| Search/filter the tabs | S A | Done | checked, in the command bar (⇧⌘K) |
| Sound indicator and mute on a tab | Z A S | Done | checked: a mark and mute on a row, a tile and a closed folder, and on a space's dot, whose mark goes to the tab that plays |
| Tab preview on hover | S | No | a picture needs access to all websites; the tooltip shows title and address |
| The list shows the selected tab, each space keeps its scroll | S | Done | checked; also a selected tab in a closed folder; closing passes over closed folders and unloaded tabs |
| A mark when a background page has news | S | Done | checked: a still dot on the tab, a closed folder and a space; a tab in a closed folder only keeps a dot it already has |
| A sign that a tab is loading | Z A S | Done | checked: a soft sign on the icon, after half a second |
| A new tab has one place | A | Done | checked: the top of today's tabs, for the button, ⌘T and links from other apps; a link from a tab stays next to it |
| Double click on the empty part of the list opens a new tab | A | Done | checked |
| Title and address in the tooltip, icons kept, a tab made ready when the pointer comes to it | | Done | checked; less motion when the system asks for it |
| Resizable sidebar width | Z A S | Done | Firefox's own sidebar handle (userChrome.css) |
| Compact mode: sidebar hidden, shown at the edge | Z A | Done | userChrome.css, ⌘S |
| Tabs nested under tabs (tree) | S | No | you only use folders; a tree is where most of Sidebery's bugs came from |

## Spaces

| Feature | From | Status | Notes |
|---|---|---|---|
| Spaces, one per container (own logins) | Z A S | Done | checked |
| Space bar at the bottom with icons | Z A S | Done | checked: a coloured dot, or the emoji its name starts with (Icon in the space's menu: a list to search in, or type one); the name above the list |
| Only the active space's tabs shown (⌃Tab too) | Z A S | Done | checked. Other spaces' essentials stay in ⌃Tab: Firefox cannot hide a pinned tab |
| Switch with ⌃1/2/3 | Z A S | Done | checked: back to the tab you selected last in that space, in any window (not one opened in the background, moved there or resting in a closed folder, nor one another window is showing) |
| Switch by swiping sideways on the trackpad | Z A | Later | tried with Sidebery and left out: vertical swipes switched space by mistake; to try again in Tidier's own sidebar |
| Colour per space, for the whole window | Z A | Done | userChrome.css and tidier.css |
| New, edited and deleted spaces in Tidier: name, icon and colour | Z A S | Done | checked, on the settings page and from a space's menu; dropping a tab on the bar makes a new one; Firefox's container settings aren't needed |
| Nothing goes out in the wrong container: the first request is stopped | S | Done | checked with a server recording cookies; needs the optional access to all websites |
| A space's own proxy and user agent | S | Done | checked; on the settings page, under More. No address bar button, and no IP lookups |
| Clear a site's cookies in one space, or a whole space's logins | S | Done | checked; signing out asks first, since it can't be undone |
| A vanished container comes back | | Done | checked; with its name, colour and icon, and everything that pointed at it |
| A folder to another space, and a copy of a tab | S | Done | checked; each tab arrives as it was, unloaded, loaded or muted; unsaved input stays behind and says so; one line, with Undo |
| Move a tab to another space without losing anything | S | Done | checked: from the menu, by dragging to a dot or from the command bar; the page and its unsaved input are kept, an unloaded tab stays unloaded and a muted one muted, and a rule does not send it back; one line says where it went, with Undo |
| New tabs and links from other apps open in the active space | A S | Done | checked, also when Firefox guesses another space's container for a link (checked with a server recording cookies) |
| Rules: an address always opens in a given space ("Air Traffic Control") | A S | Done | checked, on the settings page, and imported from Sidebery's export, also from its panels. A rule for a space that is gone does nothing and says so |
| Containers matched by name on another machine | | Done | checked: copies and Sidebery's export land in the space of the same name, never by Firefox's number for it |
| Open a link in another space (context menu) | A | Done | checked: "Open link in" on a link's menu, which needs no access to pages; the tab menu has "Open a copy in space" |
| Unload a whole space | S | Done | checked: the space's menu; essentials, the selected tab, sound, calls and unsaved input stay; a line says how many were unloaded |
| The same essentials, folders and spaces on every machine, by sync | A | Done | checked in a test Firefox, off by default, on the settings page; real Firefox Sync between two machines is not tried yet |
| Hide a space on a given machine | | Done | checked: on the settings page, or for a machine in managed storage; hidden, not kept away |
| Remove a space from every machine | | Later | today removing a container on one machine is local to it |

## Essentials and kept tabs

| Feature | From | Status | Notes |
|---|---|---|---|
| Essentials as tiles at the top, per space | Z A | Done | checked |
| Essentials in every window | Z | Done | |
| An essential keeps its address; closing it unloads it | Z A | Done | |
| Short names for essentials | | Done | checked: Rename in the tab menu, for saved tabs too |
| Only one loaded copy of an essential (no double sounds) | | Done | |
| Kept tabs (Arc's pinned section, Zen's pinned tabs): ⌘W unloads, back to the saved address | Z A | Done | tabs in folders ("saved tabs") |
| A divider between kept tabs and today's tabs | A Z | Done | in Tidier's sidebar |
| Clear today's tabs in one go | A | Done | checked: from the list's menu, the space's menu and the line between folders and tabs; one line to undo it, no question |
| Undo after closing several tabs or deleting a folder | S | Done | checked: one quiet line, in a room of its own above the bar, that waits while the pointer or the keyboard is on it; ⌘Z in the sidebar and Undo in the command bar while it shows |

## Folders

| Feature | From | Status | Notes |
|---|---|---|---|
| Folders, collapsible | Z A S | Done | Tidier's own data, checked |
| Folders first in each space | Z A | Done | the sidebar draws them first |
| Create, rename and delete folders | Z A S | Done | checked. Deleting one keeps its tabs, with one line to undo it |
| Folders inside folders | A | Later | none today, and a tree is what is left out |
| A closed folder rests: hidden from ⌃Tab and unloaded | S | Done | checked; the selected tab, sound and unsaved input stay |
| New folder with a good name, ready to rename | S | Done | from the menu, a key, or a selection, which names it after what the tabs share |
| New tab in a folder | S | Done | checked: New tab here in its menu; saved there once it has a page |
| Live folders (GitHub pull requests) | A | Done | checked: each row's icon says what the pull request waits for (your review, draft, failing checks, conflict, changes asked for, approved, running, open) |
| Folder state (open/closed) kept per space and window | Z A S | Partly | kept per folder, the same in every window |

## Tabs that tidy themselves

| Feature | From | Status | Notes |
|---|---|---|---|
| Every tab in every window, loaded only once | Z | Done | |
| Archive tabs unused for 12 hours | A | Done | |
| Find archived tabs again | A | Done | checked: Tidier's own list per space, from the list's menu, the space's menu and the command bar |
| Unload tabs unused for a while (keep them, free memory) | Z S | Later | Firefox unloads on low memory; closed folders and whole spaces unload in Tidier |
| Nothing works when nothing happens (no idle work) | | Done | checked by the smoke test, also with 300 tabs |
| Fast with many tabs | | Done | checked with 300 tabs, measured up to 1000: a new window has them all in about 7 s |
| Random use never breaks what Tidier promises | | Done | checked: random sequences on the real background scripts, and a long random run in a real test Firefox |

## Windows and links

| Feature | From | Status | Notes |
|---|---|---|---|
| A new window gets every essential and tab | Z | Done | |
| Closing a window hands its tabs over | Z | Done | a muted page stays muted; a window reopened with ⇧⌘N comes back in its own space, on its own tab (checked) |
| A small window for links from other apps ("Little Arc") | A | Done | off until turned on in the settings; checked in the test Firefox; links from real apps and whether the window comes to the front are to be tried on a Mac |
| Link preview in a floating window ("Glance", "Peek") | Z A | Done | checked: "Open link in" needs no access; ⌥-click needs the optional access to all websites |
| Split view | Z A | No | Firefox has its own; Tidier stays out of its way, and it is checked with placeholders |

## Command bar and shortcuts

| Feature | From | Status | Notes |
|---|---|---|---|
| ⇧⌘C copies the address | Z A | Done | checked: a word at the top of the page says so for a moment, as in Arc and Zen, also with the sidebar hidden; the sidebar's line says it where Firefox lets no extension into the page |
| A command bar: search tabs, essentials, history and commands | A Z | Done | checked: ⇧⌘K (⌘T once cleared in about:keyboard), floating in the middle of the window you are in (a panel of Firefox's, placed by the dotfiles' stylesheet); every space's tabs, essentials, folders, closed and archived tabs, and commands; history and bookmarks once allowed |
| Next and previous tab as shown, the n-th tab of this space, next and previous space | A | Partly | checked: ⌃⌘ and an arrow. ⌘1 to ⌘9, ⌘D and ⌘T only once Firefox's own are cleared in about:keyboard, which the dotfiles do not do yet (README, Keys); until then the settings page marks them as Firefox's and the command bar leaves them out |
| All shortcuts set in one place, in Tidier | | Done | checked: the settings page's Keys section, Copy for Claude's too; Firefox's own keys in about:keyboard |

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
| Copy a page or a list of tabs as clean text for Claude; ask Claude about a page | | Done | checked; from the tab menu, the space's menu and the command bar |
| An MCP server, so Claude Code can work in the browser | | Done | checked: local only, a socket only you can reach, and nothing runs while it is off; each agent's last tab is its own; not yet tried with Claude Code itself |
| Agents have a space of their own, with its own logins | | Done | checked: they see and touch only that space, unless you allow another |
| What an agent does is visible, and one click stops it | | Done | checked: a line and a ring while it works; a log with each call once, how it went, and what was refused, file: addresses included; with agents off, what it left you stays on the bar |
