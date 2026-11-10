# Tidier

A calmer, tidier Firefox: spaces, the same tabs in every window, and tabs
that tidy themselves, in the spirit of Zen and Arc but in Firefox itself.

(It was called Kitsune until November 2026; Mozilla's support site already
uses that name. The add-on's ID is the same, so it updates as before.)

## The goal

**Firefox that feels calm, ordered and clean: just Firefox and Tidier.**
Zen and Arc showed how a browser can feel; Zen is a fork of Firefox that
trails its security updates, and Arc is being wound down. Tidier gives the
same way of working to ordinary Firefox, which updates itself and fits
company policy, as one extension.

What that means:

- **Firefox and Tidier, nothing else.** No other extension is needed.
- **As much as possible in Tidier.** What Tidier does itself, it controls:
  it can be tested, fixed and made to work together smoothly. Only what an
  extension cannot do is set up outside it, in the dotfiles: the window's
  look (`userChrome.css`) and Firefox settings no extension can change.
- **Your tabs, not the window's.** Every tab is in every window and loaded
  only once; a window is a view onto the same tabs.
- **Spaces.** One space per container (work, clients, private), each with its
  own essentials, folders and tabs, so logins never mix.
- **A browser that tidies itself.** Essentials are always there, tabs in
  folders are kept, and other tabs are archived when unused.
- **Calm by default.** Nothing moves unless you move it; nothing is loaded
  twice; with nothing happening, Tidier does nothing.
- **Under your control.** Everything is in this repository and the dotfiles,
  so any problem can be fixed here, not waited on elsewhere.
- **Seamless.** A push to main is tested in Firefox Developer Edition (a
  month ahead; every Monday also in the newest Firefox) and, when it passes,
  signed and installed by Firefox itself. Nothing to do by hand.

### How it came about

Arc was the browser for years: three spaces (two workplaces and private), each
with its own essentials and logins so they never mixed, and unused tabs that
went away by themselves. When Arc was retired, Zen came closest, with an
extension for the tabs' lifetime. Then a workplace's sign-in requirement ruled
Zen out, and it became Firefox: settings, Sidebery for the sidebar, and this
extension for the rest. That worked, but it depended on Sidebery, and much was
not as wanted. So Tidier took over what Sidebery did, step by step, with a
sidebar, spaces and folders of its own, and Sidebery is gone.

### Where it stands (November 2026)

Tidier has its own sidebar (`sidebar/`, `sidebar-view.js`), with the active space's
essentials as tiles at the top, its folders and tabs below and the spaces at the bottom;
spaces that hide each other's tabs (`spaces.js`); folders as Tidier's own data
(`ownfolders.js`); rules for addresses; and a settings page. Sidebery is not needed, and
should be removed: the two would fight over the same tabs. Tidier speaks to no other
extension and takes no message from one (*What Tidier may do in the browser*, below).

With it come what Sidebery did well, each as one fixed behaviour: Tidier's own short menu
on tabs, tiles, folders and spaces; selecting several tabs; one quiet line with Undo, and
Clear for today's tabs; a list that shows where you are; one place for new tabs; closed
folders that rest, unloaded; marks for sound and news; honest dragging; and moves to
another space that cannot lose anything. Spaces are kept apart as strictly as Sidebery did
it, with a space's own proxy and user agent. Beyond Sidebery: a command bar (⇧⌘K), keys
that follow what the list shows, set in one place; a list of archived tabs; a small window
for links from other apps; the same essentials, folders and spaces on every machine through
Firefox Sync, with spaces hidden per machine; and, off by default, Copy for Claude and a
bridge for agents. All of it is checked in the test Firefox, in release Firefox and
Developer Edition, also with random use, and measured with a thousand tabs. What a test
Firefox cannot show (a real trackpad, links from real apps, real Firefox Sync between two
machines) is tried on the second Mac.

**Moving over from Sidebery.** A browser that ran Tidier beside Sidebery is moved at the
first start of this Tidier, which an update is (`moveover.js`): nothing to click, and no way
back. A copy of everything first; then Sidebery's folders become Tidier's own in the record,
in Sidebery's order, each with its tabs, which stay saved tabs (a live folder stays one); and
only then are Sidebery's folder pages closed. Open tabs and essentials are not touched. Nobody
asked for the move, so Tidier's settings page opens in front and says once what came over,
and that Sidebery is no longer needed. Three things are left for you, and the page says each:
remove Sidebery in `about:addons` (before that, make its export, if you want its rules, the
order of its spaces and which folders were closed: only the export has them); show Tidier's
sidebar in each window, with the page's button or any key of Tidier's (Firefox opens no
sidebar because of an update); and let Tidier hide other spaces' tabs (`tabHide`, below),
if it was never allowed to. Until Sidebery is off the two work on the same tabs: Sidebery
closes a closed folder's tabs with its page, and Tidier brings them back as saved tabs,
unloaded. See *Moving over from Sidebery* below.

All the features worth having from Zen, Arc and Sidebery, and where Tidier
stands with each, are listed in [FEATURES.md](FEATURES.md). Everything that has to
be done, in order, is in [PLAN.md](PLAN.md).

## What it does

1. **Essentials in every window.** Pinned tabs are essentials: Tidier's sidebar shows
   the active space's as tiles, and every window has an unloaded copy of each, in the same
   container. Pinning or unpinning in one window does the same in the others. Closing an
   essential brings it back unloaded, like Zen. ⌘W does not close one: on a pinned tab
   Firefox only goes to another tab, and the essential stays loaded (Unload in its menu
   unloads it). Each space's essentials stay together, in
   the list and in every window, since Firefox cannot hide a pinned tab and ⌃Tab goes
   through them all. Moving one keeps the new order, in every window and in new windows.
   Dragging one to another window takes it there (in its place, not twice) and leaves a
   copy behind. An essential's title and icon follow its page, but only from the
   essential's own site, so a redirect to a sign-in page does not rename it. Like every
   other tab, an essential is loaded in one window only (two loaded Slacks would play
   every notification sound twice): selecting its copy in the window you are using moves
   the loaded tab there and leaves an unloaded copy behind, and a copy that loads its page
   anyway (as after a restart) makes the others unloaded copies again (`essentials.js`,
   "One loaded copy").
2. **Tabs in every window.** Every other tab is *live* in one window and an
   unloaded *ghost* in the others (same URL, title and container). Selecting a ghost
   moves the live tab into your window and leaves a ghost behind, so each page is only
   ever loaded once. Opening a tab adds it everywhere; closing it closes it everywhere;
   moving it into or out of a folder is the same in every window, since a folder is
   Tidier's own data; closing a window hands its tabs over to another window.
3. **Folders** (`ownfolders.js`): each space has its folders first, then today's tabs, as
   in Zen and Arc. A folder is an entry in Tidier's record with no tab of its own, so no
   tab event can delete it; a tab is in it by the record. Made, renamed, folded and
   deleted in the sidebar; deleting one keeps its tabs. A closed folder rests: its tabs
   are hidden and unloaded (`foldrest.js`).
4. **Live folders** (`livefolders.js`): folders filled from a GitHub pull request
   search, such as open pull requests in your company's organisation or your own
   repositories where you are author, assignee or asked for review. Refreshed every
   15 minutes and at startup: new pull requests get an unloaded tab, merged or closed
   ones are removed (the one you are looking at once you leave it), and a renamed one's
   unloaded tabs take the new title. A pull request tab you close stays closed until it
   leaves the search.
5. **⇧⌘C copies the address** of the current tab, as in Arc and Zen
   (`shortcuts.js`). Firefox gives ⇧⌘C to the developer tools' element
   picker, which wins over extensions; free it in `about:keyboard` (the
   dotfiles do this in `customKeys.json`).
6. **Archiving**, as in Arc (`archive.js`): a tab not selected in any window
   for 12 hours is closed everywhere, and stays under History → Recently
   Closed Tabs (⇧⌘T) and in Tidier's own list of archived tabs. Essentials, folders and
   the tabs in them, selected tabs and tabs playing sound are kept. A tab that is only a
   placeholder (its real page was in a window you closed) counts from when it became
   one. The time never counts from before archiving was first turned on. Change it on the
   settings page, or with `archiveAfterHours` in the extension storage (0 = off).
7. **Saved tabs**, like Arc's pinned section and Zen's pinned tabs (in
   `tabsync.js`, the rules in `closeAction` in `common.js`): a tab in a
   folder is *saved*. Closing it while it is loaded (⌘W, or the ×) unloads it instead,
   in its place, in every window, and it goes back to the address it had when it came
   into the folder (browsing in it does not change that; its title and icon follow the
   page while it is on that address). ⇧⌘T reopens it in its placeholder's place. To
   remove a saved tab for good, close it while it is unloaded (the × on its placeholder,
   or a middle click), or drag it out of the folder, which makes it an ordinary tab
   again. Every other tab is temporary: closing it closes it everywhere, and archiving
   closes it when unused. A live folder's pull requests are not saved (the search decides
   what is in them).

Compact mode and the window's look are set up in the dotfiles (`userChrome.css`, Firefox
settings, `about:keyboard`). Switching to a tab in another window needs no command: every
tab is in every window. Tidier gives its keys itself, once, and they are changed in the
settings page's Keys section.

## Live folders and the native host

The pull request search runs in `native/github-prs.py`, a Firefox native
messaging host that calls the `gh` CLI with your existing login. No GitHub
token is stored in the browser. The folders are set up in a local file, not in
this repository: `~/.config/tidier/live-folders.json` (see
`native/live-folders.example.json`), one entry per folder with its name, its
container (so its space) and a GitHub search (`org:…`, `user:…`, `repo:…`).
The extension only learns each folder's id, name and container, and the host
only runs those searches; anything else is refused.

Install the host once (and again if this folder moves); it also creates the
config file from the example if there is none:

```bash
native/install.sh
```

It writes `~/Library/Application Support/Mozilla/NativeMessagingHosts/tidier_github.json`,
which only allows this extension to start the host. The `native/` folder is not
part of the signed extension.

## Working with Claude and other agents

Two things, each off until you turn it on under *Claude and other agents* on the settings
page, on this machine only. Neither setting, nor what an agent
did in its space or left you, is part of a copy.

**Copy for Claude.** A tab's menu and the command bar get *Copy page for Claude* (title,
address and the page as clean Markdown; with several tabs selected, a list), *Copy these
tabs for Claude* (the space's folders and tabs as a list) and *Ask Claude about this page*
(copies it and opens claude.ai in the space you are in, with your login there). Your own keys
can be given them in the settings page's Keys section. Nothing is sent anywhere: you paste it, or do not. A
page that is not loaded is not loaded for this: you get its title and address.

**The bridge.** An MCP server, so that an agent such as Claude Code can work in the
browser. To add it, run `native/install.sh` once, turn it on on the settings page, and:

```bash
claude mcp add tidier -- python3 -I "$PWD/native/tidier-mcp.py"
```

An agent can then list spaces and tabs, open, go to, select and close tabs, read a page as
Markdown, take a screenshot, find elements, click, type, and wait for something to show up.
A tool that names no tab works on the tab that agent opened or selected last: each agent's
own, kept by its own copy of the MCP server, so two Claude Code sessions do not act in each
other's tabs.
It can leave you a tab with a note in a folder *For you*, which exists only while it holds
something, and you can hand it a tab by dragging it to the Agent space's dot.

```
agent <-stdio-> native/tidier-mcp.py <-Unix socket-> native/tidier-bridge.py <-native port-> bridge.js
```

### What keeps this safe

- **Agents have a space of their own.** Turning the bridge on makes a space named Agent,
  with its own container and so its own logins. By default an agent can see and touch only
  that. It is told nothing of your other spaces or tabs, and a tab of yours it names is no
  tab at all to it (tab ids are numbers Firefox counts up, so it could guess how many tabs
  there are, never what they are). A rule never sends a tab out of it,
  nor a tab an agent opened in a space you opened to it on into a closed one.
- **Another space is your decision,** per space, on the settings page: closed unless you
  say otherwise, and *Can read* before *Can read and act*. A space you open is open with
  the logins in it, so a workplace's space is never opened by itself. Closing one counts at
  once, also for what an agent has under way there: a call waiting there ends. An agent
  told a space is open for reading only is told so, and any other tab of yours is no tab
  at all to it.
- **The decision is made in the extension,** in one place (`bridgeAllows`, `bridge.js`), on
  every call. The two scripts in `native/` only carry messages; anything you run could talk
  to the socket directly, and gets the same answers. No tool can change a setting or open
  a space: those messages are taken only from the settings page.
- **Never reachable, since no tool does it:** cookies, passwords, storage, downloads,
  files, Firefox's or Tidier's settings. Agents go to `http:` and `https:` only, never
  `file:`, `about:` or an extension's pages. What is in a form field is never read, not even
  by asking a selector about it letter by letter. A password
  or card field is left to you. Firefox fills in saved passwords in any container, and an
  extension cannot stop that, so on a page with a password filled in an agent cannot click
  or send a form: it could otherwise sign in to your account without knowing the password.
- **It cannot take you along.** An agent's tabs open in the background, a hundred in a
  space at most. A tab comes to the front only where you are already looking at its space.
- **It shows.** While an agent is at work, its space's dot has a thin ring and every sidebar
  has one line with what it is doing and a *Stop*. Stop cuts the bridge at once, also what
  is under way, and it stays off until you turn it on again. The settings page has a short
  log, kept only in memory and holding sites, not addresses: each call once, when it is known
  how it went, and a refused one in plain words with the space it tried (*could not open a
  tab in Work*). An address that is not on the web (*could not open a file: address*) is in
  it too, also when the MCP server refused it first. With agents off, the Agent space stays
  on the bar while it has tabs, so what an agent left you can be found; empty, it rests.
- **Local only, and only while on.** `tidier-bridge.py` is started by Firefox and only
  Tidier may start it; it lives exactly as long as the port, so off means no process and no
  socket. The socket is `~/.config/tidier/bridge.sock`, mode 0600, in a folder only you can
  write to, and each connection's user is checked. There is no network port. Web pages
  cannot reach any of it: they cannot use native messaging, the only scripts Tidier puts in
  pages only send the address of a link you ⌥-clicked (below) and the keys you typed in the
  moment after the command bar's key (below), and no page of Tidier's can be framed or
  loaded by them.
- **Pages can try to steer an agent.** Everything read from a page (text, titles,
  addresses, what `find` returns, a screenshot) goes back marked as untrusted, between markers
  with a random number the page cannot know, so it cannot write its own end to them.
  An agent is told that it is data and not instructions. Text a person cannot see is
  left out. **This is help, not a guarantee:** no marking can force a language model to
  ignore what it reads, and white text on a white background gets through.

What this does not do: it does not limit where an agent goes in its own space (a page may
start a download into your Downloads folder, as for you; Firefox asks before installing
an add-on), it does not hide a space you opened from it, and it does not protect you
from what you run yourself: anything running under your account can reach the socket while
it is on, and could read your Firefox profile anyway. Keep it off when you are not
using it. A note an agent leaves you can have been steered by a page as well. A
screenshot shows what the page shows, also a name typed in a field, and a rich text box
that is part of a page (not a form field) is read as the page's text.

Reading pages and screenshots need access to all websites, which is optional and asked
for in the click that turns these on. Without it an agent can still see tabs and addresses,
and a copy holds the title and address. A click in the sidebar does not give a page's
`activeTab` in Firefox (only its own menus, keys and toolbar button do), so that is not used.
It can be taken back in `about:addons`.

The checks are in `tests/bridge.test.mjs` (what is allowed, on a fake Firefox),
`tests/test_bridge.py` (the socket and the protocol, playing Firefox) and `alone_bridge` in
`tests/smoke.py` (end to end, in a real Firefox).

## Keys and the command bar

With Tidier alone, the keys follow what the sidebar shows (`shortcuts.js`,
`keys-commands.js`):

- ⌃⌘↓ and ⌃⌘↑: the next and previous tab as shown, past other spaces' tabs and closed folders
- ⌃⌘→ and ⌃⌘←: the next and previous space; ⌃1 to ⌃5: a space by its place on the bar
- ⌘1 to ⌘9: the n-th tab of this space, essentials first
- ⌘D: make this tab an essential, or an ordinary tab again
- ⌥⌘N: a new folder
- ⇧⌘K: the command bar, and ⌘T as well once `about:keyboard` has cleared Firefox's own ⌘T
- ⇧⌘C: copy the address (the line in the sidebar says so); ⌃⇧S: show or hide the sidebar
- ⌘Z, with the keyboard in the sidebar: what the quiet line offers to undo, while it shows
- Copy page for Claude, Copy these tabs for Claude and Ask Claude about this page: no key
  until you give them one, in the same Keys section once Copy for Claude is on

Each key is given once, at the first start that knows its command, and changed in the
settings page's Keys section; a key you change stays that way. ⌥⌘ and an arrow stay Firefox's, in window order: no extension can have them.

**⌘1 to ⌘9, ⌘D and ⌘T are Firefox's own** until they are cleared in `about:keyboard`.
Until then ⌘D and ⌘T never reach Tidier, and ⌘1 to ⌘9 act twice with the keyboard in a
page: Firefox's goes to the window's first tabs, which are every space's essentials, so ⌘1
in one workplace went to the other's Mail. They are to be cleared in the dotfiles'
`customKeys.json`, now that no browser needs them as Firefox has them for Sidebery (not
done yet; the test Firefox also takes a `customKeys-alone.json` beside it, if there is one).
No extension can read `about:keyboard`, so the dotfiles are also to hand Tidier the same
keys in managed storage (`firefoxKeys`); the test Firefox does so already. A key Firefox still has is dashed on the
settings page, with a line saying so, and the command bar does not show it.

In the sidebar, with the keyboard there: ↑ and ↓ go through the list, and in the essentials'
grid ← and → go along it and ↑ and ↓ between its rows; Home and End go to the first and the
last; Enter or Space selects (or folds a folder); ← and → fold and unfold a folder; ⌫ closes
a tab; F2 renames a folder, a saved tab or an essential; ⇧F10 or ⌃↵ opens the menu of what
the cursor is on, and Esc gives the keyboard back to it. The row under the cursor has the
keyboard itself, so there is one ring, and a button you Tab to (New tab, a space's dot)
answers its own Enter and Space. Tab comes into the list once, on the tab you are on, and
the next Tab goes on past it, as ⇧Tab goes back out: a row's ×, its speaker and Clear are
for the pointer (⌫ and the menus do the same by key). Rows, folders, essentials and spaces are named for a
screen reader, with what is selected and what is open (`sidebar/keys.js`, `alone_keyboard`
in `tests/smoke.py`). Two things Firefox decides: no key puts the keyboard in the sidebar
(F6 skips it, and an extension's page cannot take the focus from the page, tried in the test
Firefox: Tab from the address bar, or ⇧Tab twice from the page, reaches it), and whenever the selected tab
changes (a tab selected, the selected tab closed, another space) Firefox gives the keyboard
to the page. Closing a tab that is not the selected one keeps it in the list.

The command bar (`commandbar.js`, `commandbar/`) opens with ⇧⌘K in a small window over the
one you are in, and with ⌘T too once Firefox's new tab key is cleared. One field finds
every tab of every space, essentials, folders, closed and archived tabs and commands, and
history and bookmarks once you allow them. A row of another space says which, and the
selected one what Enter does there ("Switch to Work"). Commands act on the tabs selected in
the sidebar, else on this one; a command that asks something says what for, ⌫ in its empty
field goes back, and one that closes tabs is never what a plain Enter takes for a word that
is only somewhere in its name, nor moved up by use. Enter goes to a tab, or opens an
address or a search in the active space; ⌘↵ opens a new tab instead.

Firefox takes a moment to make the bar's window and give it the keyboard. What you type
before that is caught where it went and handed to the bar (`barkeys.js`, in pages while
Tidier has the access to all websites, and in its sidebar), so nothing lands in the page.
Without that access, the first letters typed at once after the key still go to the page.
Keys typed in the instant between the new window taking the keyboard and its page being
there (some tens of milliseconds, several hundred on a busy machine) reach neither, and no
extension can see them. A window made in advance and only shown would close that gap, but
cannot be hidden: Firefox keeps every window an extension places or moves on a screen, and a
minimised one goes into the Dock and comes back out of it slowly.

What Sidebery does beyond that, with nothing new on screen and no settings
(`listactions.js`, `sidebar/moremenu.js`): one **More** at the end of a tab's, a folder's
and a space's menu, opening in place. It sorts today's tabs or a folder by name, by site or
by last use (with Undo), moves tabs to the top or the bottom of their list, takes them out of
a folder, copies them as Markdown links, closes the duplicates among today's tabs (by the
record's address, the one you are on stays) or the tabs above, below or around one, and
reloads, mutes or unloads a whole folder or space, a few pages at a time. A folder's menu
also has New tab here, and Close all its tabs. Whatever closes goes through the quiet line,
with Undo. Each is a command in the bar, found by its name, and in the Keys section under
More commands, with no key until you give one: what a tab's More does acts on the selection,
else the tab; a folder's on the folder of the selection, else of the tab; a space's on the
space you see. So are Back and Forward through the tabs used recently in this space (by each
page's real last use, as the list draws them). In the
sidebar ⌘A selects every row, ⇧↑ and ⇧↓ take one more, ⌥↑ and ⌥↓ move the selection (else
the tab) one place along, in every window. A tab dragged and held over a closed folder opens
it, and over another space's dot goes to that space, where a drop in the list puts it.

## The same on every machine, and spaces hidden on one

`sync.js`, `syncmerge.js`, `hiddenspaces.js`.

**Sync** is off until you tick it on the settings page. Essentials, folders, saved tabs,
short names, rules, and spaces with their names, colours, icons and order then go into
Firefox Sync's storage for add-ons. Ordinary tabs, what is open, icons, which folders are
closed and which spaces are hidden stay on each machine, and so does everything of the
agents' space. No container number is shared: a space is matched to a container by
name, so logins cannot mix. The newest change wins per thing; something merely missing
never counts as deleted, and a page you have open is never closed by another machine.
Turning it on takes a copy first. Firefox Sync must carry add-on data: tick Add-ons in its
settings, or set `services.sync.engine.extension-storage.force`, which carries only that.
It is checked in one test Firefox; real Firefox Sync between two machines is not tried yet.
Removing a space on one machine does not remove it from the others.

**A hidden space** leaves the bar and every window on this machine, and ⌃1/2/3 skip it.
Nothing is deleted: showing it again brings everything back, unloaded. A rule for it opens
the tab in the space you are in and says so. Hide one on the settings page, or declare it
for a machine by name in Tidier's managed storage:
`"data": { "hiddenSpaces": ["Name of the space"] }`. Firefox reads
that file once each time Tidier starts, so a change there needs a restart of Firefox.

## Moving over from Sidebery

Tidier once ran beside Sidebery, which drew the tab list, the folders and the spaces. A
folder was then a page of Sidebery's, open in every window, and Tidier's record said which
tabs were under it. This Tidier has no such mode, so a browser that still has those folders
is moved when it starts, which an update is (`moveOverOnce`, `moveover.js`):

1. **A copy of everything**, through the helper for the daily copy, or else inside Firefox's
   own storage (`copyBeforeMove`).
2. **The record**: each of Sidebery's folders becomes a folder of Tidier's own, with its name,
   in Sidebery's order, and its tabs stay in it as saved tabs. Sidebery's tree had tabs
   under tabs: here a tab is in its nearest folder, or in none. A folder that an export of
   Sidebery's, taken in earlier, said was closed comes over closed.
3. **Only then** are Sidebery's folder pages closed, and kept out of Recently Closed.
4. **Tidier's settings page opens in front** and says, once, what came over and that
   Sidebery is no longer needed. No tab is hidden before the page is drawn, since Firefox
   then asks whether Tidier may hide tabs (*Keep Tabs Hidden*), and nobody is expecting a
   question (`aftermove.js`).

Open tabs and essentials are never touched by the move: they are Firefox's own tabs, and
Tidier's record of them is the same as before. A start cut short is taken up at the next:
the record is written in one piece, and a folder page left open is closed then.

What is left for you, since no extension can do it:

- **Remove Sidebery** in `about:addons`. Tidier cannot do that, and does not ask for the
  right to see other extensions, so it says it once, after the move, where it knows
  Sidebery was in use. Until then the two work on the same tabs: Sidebery closes a closed
  folder's tabs with its page, and Tidier brings them back as saved tabs, unloaded.
- **Sidebery's export**, before you remove it, if you want its rules for addresses, the
  order of its spaces and which folders were closed: they are kept nowhere else, and the
  settings page takes the export in (*From Sidebery*).
- **Tidier's sidebar** in each window: Firefox opens no sidebar because an extension was
  updated. Every window without it shows the settings page with a button for it, and the
  first key of Tidier's pressed there opens it too.
- **Hiding other spaces' tabs** (`tabHide`), where Tidier was never allowed to: until then
  the sidebar shows one space, but Firefox's own tab bar and ⌃Tab hold every tab.

What can be lost is only what was Sidebery's own: tabs nested under other tabs become flat
inside their folder, the colours and icons Sidebery gave its panels, and, without its
export, its rules, the order of its spaces and which folders were closed. A container that
had no space in Sidebery and holds nothing (Firefox's own "Shopping") is hidden on this
machine rather than being a new space on the bar, where an export taken in earlier says
which those are. A browser that used Sidebery without any folder has nothing to move, and
gets no page: this section is what tells you to remove Sidebery there.

## Placeholders (ghost.html)

Firefox cannot give an unloaded tab an icon, but it can give it a title. Ghosts and
essential copies are created unloaded, with the title of their page, and no page at all
(Firefox allows that, but not together with pinned, so an essential's copy is pinned right
after). Tidier's sidebar draws them from Tidier's record, with the saved icon, and ⌃Tab
shows the title they were made with. That is what keeps a new window with a thousand tabs
to a few seconds. When shown, an essential copy goes straight to the real page; a ghost has
the live tab pulled in, and only loads the real page itself if no live tab exists.

The page a placeholder's address names is a tiny local one (`ghost.html`): loaded, it sets
the real page's title and icon and asks to be unloaded again, when Firefox reports the icon
as shown, not after a fixed pause. That is done only when a title in ⌃Tab would be wrong:
the live tab's title changed, or Firefox moved an unloaded tab to another window without
it. The icon is the one saved for the page, else the site's `/favicon.ico` if that loads.

Tabs that were never loaded have no title or icon to copy. For the initial
migration from Zen these were filled in from Zen's session data. An essential
that still has no icon takes the icon of the first tab on its site that you
open, and its copies are redrawn. This matters for sites behind a sign-in,
whose `/favicon.ico` leads to the sign-in page. Firefox's own icon cache
(`page-icon:`) cannot be loaded from an extension's process.

## Short names for essentials and saved tabs

An essential can have a `name` (e.g. "Jira"), and so can a saved tab, set with Rename in
the tab menu (`tabnames.js`). The sidebar and unloaded copies show it instead of the page
title, and clearing it gives the page's title back.

## Links from other apps

Firefox gives a link from outside (Slack, Mail, …) no container, unless a visible tab is
on the same host, and then that tab's container, counting every window and every space's
essentials (they are pinned, so always visible to it): the space with the most essentials
on a site wins. With Tidier that guess counts for nothing, and its login never goes out
(Isolation, below); the dotfiles' `browser.link.force_default_user_context_id_for_external_opens`
turns it off in Firefox itself. Tidier opens the link in a small window of its own
(`littlewindow.js`), in the rule's space or else the one you are in, to read and close, or
to keep with one click; it can be turned off on the settings page, and then the link is an
ordinary tab in the same space. The same link twice (a double click in the other app)
brings its small window to the front. Closed, ⇧⌘T gives it back as a small window, with
its row and Keep. Tidier cannot do this for addons.mozilla.org, which Firefox shields from
extensions.

## Known limitations

- An essential remembers the URL the tab had when it was pinned. Pin a page
  when it shows the app itself, not while it is redirecting to a sign-in or
  product page.
- An essential whose site you have not opened since it became one, and whose
  `/favicon.ico` does not load, shows the default icon until you do.
- Firefox cannot hide a pinned tab, so other spaces' essentials stay in ⌃Tab;
  selecting one takes you to its space.

## Performance

In the test Firefox (Firefox 159 and Developer Edition; headless, slowed down): a new window with the same tabs
is ready in ~0.5 to 0.8 s; with 300 tabs in ~1.4 s, and with 1000 in ~7 s, with the
extension's memory under 200 MB. Switching space takes ~0.15 to 0.2 s. Selecting a ghost: the live
tab is in place after ~50 ms. Measured with `TIDIER_MANY=1000 tests/smoke.py --only
alone_setup,alone_many`.
None of this is measured on a real Mac yet: that is for the second Mac (PLAN.md).


## What Tidier may do in the browser

Every right in `manifest.json`, and what it is for. The first ten are had from the start;
Firefox showed its list once, at the install. The rest are asked for by your click, each
when it is first of use, and everything else works without them. A unit test holds this
list to the manifest, both ways.

| Right | What it is for |
| --- | --- |
| `tabs` | Seeing tabs' addresses and titles: the list, the same tabs in every window, rules for addresses. |
| `sessions` | A mark on each tab that says which entry in Tidier's record it is, so tabs are known again after a restart; and Recently Closed kept clean. |
| `storage` | Tidier's own record and settings, in this profile; through Firefox Sync only when you turn that on. |
| `cookies` | Opening a tab in a container (a space); clearing a site's cookies in one space, when you ask. |
| `contextualIdentities` | The spaces: Firefox's containers, made, renamed, coloured and removed. |
| `nativeMessaging` | Two small programs on this machine, set up by the dotfiles: `tidier_github` (the pull request search and the daily copy) and `tidier_bridge` (the bridge for agents, when it is on). |
| `alarms` | Timing: archiving, the live folders' refresh, the daily copy. |
| `clipboardWrite` | ⇧⌘C, Copy address in the menus, and Copy for Claude. |
| `menus` | Tidier's own menu in its sidebar, and "Open link in" on a link's menu. |
| `menus.overrideContext` | That menu instead of Firefox's, in Tidier's own sidebar only. |
| `tabHide` | Hiding other spaces' tabs from Firefox's tab bar and ⌃Tab. Without it they are only left out of the sidebar. |
| `webRequest` | Seeing a page's address before it loads, to keep spaces apart (Isolation, below). |
| `webRequestBlocking` | Stopping that page before it loads in the wrong space. |
| `*://*/*` | Every website, for the two above, for reading a page when you ask (Copy for Claude, the bridge), ⌥-click on a link, and the keys typed right after the command bar's key. |
| `proxy` | A space's own proxy, when you give it one. |
| `browsingData` | Signing out of everything in one space, when you ask. |
| `search` | Searching with your search engine from the command bar. |
| `history` | *Also search history and bookmarks* in the command bar. |
| `bookmarks` | The same. |

What Tidier may not do, and does not ask for: see or manage other extensions (`management`;
it was asked for once, only to see whether Sidebery was on), take a message from another
extension or a website (it has no listener for one, and no `externally_connectable`), run
a script in every page from the start (no content scripts in the manifest), read local
files, or reach anything outside Firefox but the two programs above. A unit test holds
each of these.

### In more words

The rights asked for later are optional: a permission added to the required ones makes
Firefox hold every later update until it is approved, with only a badge to show it (a unit
test stops that). Everything works without them, as it says here:

- `tabHide`, from the line the sidebar shows until it is given (or the settings page):
  other spaces' tabs hidden. Without it they are only left out of the sidebar. The first
  time a tab is hidden, Firefox asks whether to *Keep Tabs Hidden*; after a move from
  Sidebery no tab is hidden until the settings page is in front to say why (`aftermove.js`).
- `webRequest`, `webRequestBlocking` and access to all websites, asked for in the line
  that follows in the sidebar, or on the settings page: a page stopped before it loads in
  the wrong space (below, Isolation). For this Tidier
  reads no page and keeps no record of where you go; all it looks at is the address of a
  tab's next page and the container it is in. Clearing a site's cookies is offered once
  this is given, since the cookies API shows nothing without it. The same access, which
  is one permission, is what ⌥-click on a link uses (`peek.js`, a small script in every
  page that does nothing but send the address of a link you ⌥-click), what the command bar
  uses to keep the keys you type right after its key (`barkeys.js`, which does nothing until
  that key), and what Copy for Claude and the bridge use to read a page, only when you ask
  or an agent works in a space you opened to it.
- `proxy` (with `webRequest`, `webRequestBlocking` and access to all websites, since at a
  start a page must be stopped before it goes past the proxy: below, Isolation), when a
  space is first given a proxy, and `browsingData`, when you first sign out of everything
  in a space.
- `search`, `history` and `bookmarks`, when you choose *Also search history and bookmarks*
  in the command bar.

"Access to all websites" is `*://*/*` (http, https and their web sockets), not `<all_urls>`,
which would also list *Access local files on your computer* in about:addons. One given
earlier as `<all_urls>` still counts. Firefox's Extensions menu still says Tidier "needs
permission" on a website while this is not given: it says that of any extension that may
ask for a site.

Inside Tidier, its pages (the sidebar, the settings page, the placeholders) talk to its
background by messages, and each listener takes a message only from Tidier itself, and
most only from one of Tidier's own pages. A web page cannot send one at all; `peek.js` and
`barkeys.js`, which run beside a page's own script and not in it, send only a link's
address and the keys typed for the command bar.

No required host permissions and no data collection. The only network use is icons: a
placeholder with no saved icon tries the site's `/favicon.ico`, and Tidier's sidebar
loads tabs' icons from where the site has them (not for a space with a proxy, whose tabs
show their first letter). No IP lookups, nothing else by itself. Sync across machines,
when you turn it on, goes through Firefox Sync's own storage for add-ons, and the bridge
only through a socket on this machine.

## Isolation

Every space is a Firefox container, so its logins, cookies and what
sites store are its own, and it should be something nobody has to think about.
`alone_isolation` checks it with a local server that records each request and its
cookies, so what is checked is what really left the browser.

Guaranteed, with the permission for it (`isolation.js`, `whereItBelongs`):

- **No web page is loaded outside a space.** A request with no container is stopped
  before it leaves and opened in the active space, also a tab restored or opened by
  something else, and a link that starts Firefox itself. (That last one Firefox only
  holds for a listener it remembers: from the second start after giving the
  permission. Until then such a page goes out with no
  login, and is moved to its space as soon as Tidier has started.) An essential with no
  container becomes one of the active space.
- **A link from another app goes out only in the space you are in, or a rule's,** also
  when Firefox has put it in another space's container itself: a new tab on about:blank,
  with no opener and no page asking, selected in a container that is not the space you
  were in, is taken for that guess, and goes where a link with no container goes, before
  anything is sent. (Firefox's own "Open in New Container Tab" on a bookmark looks the
  same, and opens in the space you are in.)
- **A rule's address opens in its space, from the first request on,** on a tab's first
  page and for an address you type or choose. A cookie set in one space is not sent in
  another. If the tab there cannot be opened, the page is not loaded and the line says its
  address: it is never sent from the wrong space instead.
- **A tab does not move because of where it passes through.** A link followed inside a
  page and a redirect do not count: with Sidebery's rules, which looked at everything a
  tab loads, a sign-in passing through an address took your tab with it. A reload,
  Firefox restoring a tab, a popup, and a tab you moved by hand stay too, and so does
  going back to such an address.
- **Nothing is lost for it.** Only a tab holding nothing is closed, and only once the new
  one is there. An address you type in a tab showing a page, or in a saved tab, an essential
  or a tab in a folder, opens in its space, and that tab stays as it was. A tab outside
  any container is opened again as what it was: in its folder, with its saved address, in
  the same place in every window. If it cannot be opened at all, the line says the address.
- **No rule can hold up a page.** A rule's regular expression runs in time that grows
  with the address and never more (`rulematch.js`): on Firefox's own engine `/(a+)+$/`
  takes days on an address of forty a's, while every page in every tab waits, and an
  extension cannot stop it. That leaves out look-around and back-references, which a rule
  about an address hardly ever needs; the settings page says so, and such a rule does
  nothing. A rule for a space that is gone also does nothing, and says so there. Whatever
  else goes wrong, a request is let through after ten seconds. A navigation costs
  microseconds here, and a tab is only looked up when it may have to move.

Not guaranteed:

- **Without the permission,** a link's first request goes out with no container, and
  the tab is then opened again in its space. It carries no login, since those are all
  in spaces, but the site does see it. A link Firefox has put in another space's
  container goes out with that space's login, and is then opened again in yours, unless
  the dotfiles' setting above has turned that guess off. So is one opened in the
  background (`browser.tabs.loadDivertedInBackground`), which Firefox does not do by default.
- **Addresses Firefox hides from every extension** (addons.mozilla.org, accounts.firefox.com
  and a few more) cannot be stopped: no extension sees those requests. One opened with no
  container goes out with no login, and is moved to a space as soon as it shows, so it
  doesn't stay outside one (checked). A rule for one works the same way, and a space's
  proxy or user agent may not apply there.
- For a moment during an update of Tidier nothing is listening. A link opened just then
  goes out with no login, and is moved in the same way (checked).
- A page you reach by a link inside another stays in that space, with that space's
  login, whatever a rule says about its address: that is the point of the line above.
- **A rule works for any page.** A page in one space that links to or opens a rule's
  address gets it opened in the rule's space, with that space's login, as you would want
  for a link. So a site can reach another space's login that way with a plain request;
  a form stays where it is. Keep rules to addresses you would follow a link to.
- A frame with `sandbox` can send its page on with no name on the request, which looks
  just like an address you type, so that page's tab can be sent where a rule says. After
  three in ten seconds a tab stays where it is, so two such pages cannot go on for ever.
- Going back through an address a rule has, after Firefox has restarted, opens it in the
  rule's space: which addresses a tab passed through is not kept over a restart.
- **A space's logins are separate; Firefox's other data is not.** History, bookmarks,
  saved passwords and downloads are per Firefox. Private windows are left alone, and
  `about:` pages, extensions' pages and files have no container: such a page is listed in
  the one space it was first seen or last selected in. Firefox's own requests
  (its updates, say) are in no space.
- **A proxy is not anonymity.** It carries a space's requests, with the names looked up
  there too for SOCKS; a proxy that does not answer means no page rather than going
  directly (checked). Addresses on this machine never go through one: that is Firefox's
  rule. Sites can still recognise you by the login, or by the browser itself. At a start
  Firefox decides on the proxy for the tabs it restores before any extension has run; such a
  page is stopped before anything is sent and asked for again through the proxy (checked),
  but the name may have been looked up by then.
- **A user agent is only the header.** A page's scripts can still read the real one.
  Only the spaces that set one are changed, but while any does, each request of every
  space passes Tidier for an instant.
- **Signing out takes** cookies, IndexedDB and local storage, for one space. Firefox
  cannot clear a cache or service workers for one container, so those stay; they hold
  no login, but pages already open show it only when they next load.
- **A container that vanishes comes back, usually without its logins** (`Refresh Firefox`,
  a lost `containers.json`): Tidier remembers each space's name, colour and icon, makes it
  again at a start and says so. A login only comes along if Firefox gives it its old number
  back; another space's number is never used. It cannot tell that from a container removed
  while Tidier wasn't running. One removed while it runs stays removed, and its essentials,
  folders and rules are gone with it.
- A placeholder fetching a site's icon does so in its own container, as a page would.

## Files

- `common.js` – shared queue and helpers. Every change runs through one queue
  so events cannot race into duplicate tabs.
- `essentials.js` – essentials (pinned tabs) in every window.
- `tabsync.js` – live/ghost tab sync. Roles and keys are stored per tab with
  `sessions.setTabValue`, so they survive a restart.
- `livefolders.js` – live folders of GitHub pull requests (see above).
- `ghost.html` / `ghost.js` – placeholder page for ghosts, essential copies and never-loaded live tabs.
- `archive.js` – archiving of unused tabs.
- `archivelist.js`, `sidebar/archived.js` – the list of archived and closed tabs, per space.
- `shortcuts.js` – one table for every key, the command bar's and Claude's included; ⇧⌘C
  copies the address. `keys-commands.js`, `settings/keys.js`, `sidebar/keys.js` and
  `sidebar/keyrename.js` – what the keys do, the settings page's Keys
  section, and keys in the sidebar.
- `commandbar.js`, `commandbar/` (the bar's page, `first.js` for its first frame, and
  `rank.js`, what it shows for what you type), `barkeys.js` (the keys typed before its window
  has the keyboard), `sidebar/commandbar-link.js` – the command bar.
- `spaces.js` – spaces: hiding, switching, new tabs and links, rules.
- `spaceactions.js`, `sidebar/spacemenu.js` – a space's menu and what it does (rename,
  unload, clear).
- `newtabs.js`, `sidebar/newtab.js` – one place for new tabs.
- `safemoves.js`, `sidebar/reconnect.js` – moves to another space that cannot lose
  anything; the sidebar connecting again after its background part has come back.
- `foldrest.js` – a closed folder rests: hidden and unloaded.
- `quiet.js`, `sidebar/note.js` – the quiet line, Undo and Clear.
- `tabnames.js`, `sidebar/renamekept.js` – names of your own for essentials and saved tabs.
- `sounds.js`, `sidebar/sound.js` – where sound comes from.
- `news.js`, `sidebar/news.js` – a still dot when a page in the background has news.
- `littlewindow.js`, `peek.js`, `sidebar/littlewindow.js`, `settings/littlewindow.js` – the
  small window for links from other apps, "Open link in", and ⌥-click.
- `hiddenspaces.js`, `syncmerge.js`, `sync.js`, `settings/sync.js` – spaces hidden on one
  machine, and the same essentials, folders and spaces on every machine through Firefox Sync
  (`syncmerge.js` is how two versions become one, with no Firefox needed to test it).
- `bridge.js`, `bridge-page.js`, `sidebar/agent.js`, `settings/bridge.js`,
  `native/tidier-mcp.py`, `native/tidier-bridge.py` – Copy for Claude and the bridge for
  agents (above).
- `rulematch.js` – whether a rule matches an address, in time that can't blow up.
- `isolation.js`, `settings/spaces.js`, `sidebar/isolation.js` – nothing goes out in the wrong container; a
  space's proxy and user agent; signing out; new, edited and deleted spaces; a vanished
  container brought back; a copy of a tab, and a folder, to another space.
- `ownfolders.js` – Tidier's own folders, moving tabs.
- `tabactions.js` – what the menu on a tab does (the menu itself: `sidebar/tabmenu.js`;
  the small menu Tidier draws: `sidebar/menu.js`).
- `listactions.js`, `sidebar/moremenu.js` – More: what acts on a part of the list at once
  (sorting, closing around a tab and duplicates, a whole folder or space), and Back and
  Forward through the tabs used recently.
- `sidebar-view.js`, `sidebar/` – Tidier's own sidebar; among its parts `selection.js`
  (several tabs), `drag.js`, `stayput.js` (the list shows where you are) and `touches.js`
  (the slow-load sign and warming up a tab). `sidebar/tokens.css` holds the colours and
  sizes of every page Tidier draws.
- `copies.js` – the daily copy of Tidier's data, and taking one in, matched to spaces by name.
- `moveover.js`, `settings/` – the settings page, moving a browser over from Sidebery at its
  first start, and taking in Sidebery's export.
- `aftermove.js` – right after that move: the hidden-tabs question while the settings page is
  in front, and a button for Tidier's sidebar in any window, which Firefox leaves without.
- `tools/from_arc_zen.py` – your spaces, essentials, pinned tabs and folders from Arc or
  Zen, as a file the settings page takes in like a copy. Only reads Arc and Zen.
- `tools/shoot.py` – pictures of what Tidier draws, for working on its look: every
  space and width, light and dark, hover, menus, the keyboard, empty spaces, the settings page.
- `tests/` – the unit tests, the smoke test, the test Firefox and its fixtures, the random
  sequences (`chaos.test.mjs` on `chaos_firefox.mjs`) and the long run (`soak.py`).
- `.github/workflows/smoke.yml`, `tools/setup-ci-keys.sh` – the smoke test on GitHub.
- `.github/workflows/release.yml`, `tools/release.py`, `tools/setup-amo-key.sh` –
  signing and releases (see below).

## Releases and updates

Every push to `main` that changes the extension ends up in your Firefox on
its own:

1. The smoke test runs on GitHub (`.github/workflows/smoke.yml`). A failed
   first try gets one more try in the same job, whatever failed, and leaves a
   warning on the run: GitHub's runners are slower and busier than a Mac.
2. When a run on `main` passes (a push, by hand or the weekly one),
   `.github/workflows/release.yml` runs `tools/release.py`:
   - it builds the `.xpi` with version `major.minor.<number of commits>`, e.g.
     1.6.7, so nobody has to bump it;
   - addons.mozilla.org signs it as *unlisted* (not in its catalogue), because
     Firefox only installs signed extensions;
   - it puts the `.xpi` and `updates.json` on a GitHub Release.
3. Firefox reads `updates.json` through `update_url` in `manifest.json` and
   installs the new version by itself. It checks once a day; *Check for
   updates* in `about:addons` checks at once.

Nothing is released when only the documents (`README.md`, `FEATURES.md`,
`PLAN.md`, `CLAUDE.md`), tests, tools, `native/` or `.github/` changed; none of them goes
into the extension. Change `major.minor` in `manifest.json` for a bigger change. `tools/release.py
--dry-run DIR` builds the `.xpi` and `updates.json` locally without signing.

If a release is bad, Firefox never goes back to an older version, so the way
out is a newer one:

1. To stop it spreading, mark the release before it as the latest:
   `gh release edit v<older> --latest -R CHaerem/tidier`. `update_url` follows
   the latest release, so Firefoxes that have not updated yet stay where they are.
2. `git revert` the commit and push. It gets a higher version, and Firefox
   updates to it.
3. If the smoke test is red for another reason (a new Firefox) and
   the fix cannot wait, run the release yourself from the reverted commit, with
   the AMO key in `AMO_JWT_ISSUER` and `AMO_JWT_SECRET`: `tools/release.py`.
   It skips the test, so do this only for a revert.

Set up once:

- The AMO API key: create it at
  <https://addons.mozilla.org/developers/addon/api/key/> and run
  `tools/setup-amo-key.sh`, which stores it as the secrets `AMO_JWT_ISSUER`
  and `AMO_JWT_SECRET`. Only the release workflow, which runs code from `main`,
  can read them.
- Firefox: install the first release by hand (open the `.xpi` from the newest
  [release](https://github.com/CHaerem/tidier/releases)). Versions before
  1.6 have no `update_url`, so they cannot find updates.

## Testing

From fastest to most complete:

```bash
node --test                          # unit tests, about half a minute
TIDIER_TEST_SCALE=25 node --test     # as on GitHub: the fake clock at a quarter of its speed
tests/smoke.py --only tab_sync,saved_tabs  # some smoke test groups, about a minute
tests/smoke.py                       # the whole smoke test, about 15 minutes
tests/smoke.py --installed           # the signed version installed in your Firefox
tests/smoke.py --xpi FILE            # a given signed .xpi
tests/smoke.py --serial              # in one test Firefox
tests/smoke.py --part alone-3        # one part of it (alone-1 to alone-5, or core), as on GitHub
tests/smoke.py --part alone          # every group of the chain in one test Firefox, in a row
```

Runs to do on purpose, not after every change:

```bash
CHAOS_SEQUENCES=15000 CHAOS_SECONDS=0 node --test tests/chaos.test.mjs  # random use, for a night
tests/soak.py [--minutes N] [--seed N] [--port P]                    # a long run in a real test Firefox
TIDIER_MANY=1000 tests/smoke.py --only alone_setup,alone_many         # measured with a thousand tabs
tools/shoot.py                                                       # pictures of what Tidier draws
```

For what went wrong once and could not be made to happen again, Tidier keeps the last
forty things you did and what came of them (an Undo and what it brought back, a menu item
pressed and clicked, a key that reached it), in its console and in the smoke test's
`stats` message (`trace` in `common.js`), beside the errors. Quick ⌃⌘↓ presses over
unloaded tabs, about one in eight lost in a slowed-down test Firefox, never reached Tidier
at all: Firefox hands an extension's key over only once the page's process has seen it,
and the page just selected is then still starting to load. Its own ⌃PageDown does not
wait for that. The `key` lines show whether this happens on a real machine too.

`tests/chaos.test.mjs` plays random sequences of browser use on the real background
scripts, on a fake Firefox (`tests/chaos_firefox.mjs`) that refuses what Firefox refuses,
and checks after each what Tidier promises: no tab lost or doubled, every essential in
every window, every tab in its space, nothing left in memory. A failure prints a line to
run that one sequence again (`CHAOS_REPLAY='…'`, with `CHAOS_TRACE=1` for every call).
`tests/soak.py` does the same slowly in a real test Firefox, clicking and dragging in the
real sidebar, and also fails on memory that grows or on work while nothing happens.
Restarts in it (`--restart-every N`) need Developer Edition (`TIDIER_FIREFOX`,
`TIDIER_MUST_RESTART=1`).

The unit tests cover the logic that needs no Firefox. `tests/unit.test.mjs` has what
closing a saved tab means and when a tab is saved, and rules about the repository.
`tests/background.test.mjs` runs the real background scripts on a fake Firefox
(`tests/fake_firefox.mjs`), for what is hard to bring about in a real one: a start with no
windows, a refused call during a start, an essential in a removed container, a browser
moved over from Sidebery at its first start.

The group names for `--only` are the check functions in `tests/smoke.py`
(`new_window`, `essentials`, `tab_sync`, `saved_tabs`, …); a group that needs the second
window gets it first. Without `--only`, the groups run in eight test Firefoxes at once: the
core groups (`GROUPS`, in three `SHARDS`), where Tidier may not hide tabs, as on a browser
moved over from Sidebery by itself, each with a folder of Tidier's own in each space; and
the chain (`ALONE_GROUPS`, in `alone_*`: named from when they tested Tidier alone, beside
Sidebery), with tabs hidden, in five parts (`ALONE_SHARDS`), each from the same fixture
and each ending with nothing happening and no errors. A group of the chain must not lean
on what a group before it left behind: it makes what it needs (a second window, a tab), so
that it also runs by itself (`--only alone_setup,alone_many`), which is the quick way to
look at a failure. `--part alone` still runs them all in a row in one test Firefox,
about 50 minutes: hours of use in one session, which finds what a fresh one does not.
`TIDIER_ALONE_ALL_PERMISSIONS=1` runs them with every optional permission
given, as in real use. Two smoke tests at once need their own ports (`--port`), and a
second one on the same ports says so.

A test must not switch Marionette through every tab's handle to find a page: that
loads every unloaded tab on the way, and a closed folder's tabs would no longer rest.
`into_page` in `tests/smoke.py` asks for the one tab's handle instead.

The smoke test runs in an invisible test Firefox with a throwaway profile
(`tests/testfirefox.py`), so it never touches your own Firefox: no restart, no
window, no clipboard, its own Marionette port (one per test Firefox). The
profile is deleted afterwards. It is built the same way every time, from:

- dotfiles (`~/src/private/dotfiles/home/firefox`, or `TIDIER_DOTFILES`):
  `user.js`, `userChrome.css`, `customKeys.json` and `tidier.css`, so it
  tests the setup as dotfiles says it is;
- `tests/fixtures`: the containers, made from your own setup without any names by
  `tests/fixtures/from_backup.py` (run it again when you change containers), and
  Sidebery's export as it looks, for taking one in;
- Tidier (this folder, or a signed `.xpi`);
- test tabs in each space: essentials and ordinary tabs;
- a stand-in for the live folders' native host (`tests/fake_github_host.py`),
  which answers from a file the test writes, so live folders are tested
  everywhere without your `gh` login or GitHub.

The list of what it checks is at the top of `tests/smoke.py`. Each group of
checks runs on its own; a check that crashes counts as failed. Run it after
changing the extension or dotfiles' Firefox files, and after Firefox updates.

A headless Firefox has no real window focus, and the macOS hand-over of links
from other apps cannot be emulated in it; the test checks the part that keeps
logins apart (a tab without a container lands in the active space's
container).

### On GitHub

`.github/workflows/smoke.yml` runs the unit tests first, on a quick Linux runner,
and then the same smoke test on GitHub, in a headless Firefox on a macOS runner. On each
push that is Firefox Developer Edition (the Beta, about four weeks ahead, so a Firefox
change that would break something shows up before it reaches you), in six parts, each on
a runner of its own at the same time: the chain's five and the core groups. Every Monday
and when started by hand it is also the newest Firefox, which is what yours updates to.
Developer Edition allows unsigned add-ons, so there Tidier is installed for
real and the test also quits and restarts Firefox to check the restored
session; on your Mac that part runs with `--installed` or `--xpi`. It
runs on pushes and pull requests here and every Monday, so a Firefox
update that breaks something shows up without any change here; after
changing the Firefox files in dotfiles, start it by hand (Actions → Smoke test
→ Run workflow). GitHub e-mails you when a run fails.

The Firefox files come from your private dotfiles, read with a read-only
deploy key (deploy keys do not expire). Set it up once, in your own terminal:

```bash
tools/setup-ci-keys.sh
```

During development you can also load it by hand: `about:debugging` → This
Firefox → Load Temporary Add-on → `manifest.json`.
