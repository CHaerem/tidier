# The plan

Everything that has to be done, in order, with what "done" means. The goal and
the background are in the README, and the features to aim for in FEATURES.md.
Tick things off here as they land, so the next person can see where things are.

**In short:** Tidier took over from Sidebery step by step, while the daily
Firefox kept working as it did. On 10 November 2026 the owner asked for the whole
step at once: Sidebery is out of Tidier's code (part E), and a browser that still
ran Tidier beside it is moved when it updates. What is left is to use it, on the
daily Mac and on a second one, and to clear Sidebery out of the dotfiles.

Rules for all of it:

- **Every commit on main reaches the daily browser.** There is no setting to hide
  behind: until part E everything for Tidier alone sat behind one that was off by
  default; now a browser that still has Sidebery's folders is moved at its first start.
- **Every step has a check**, in the test Firefox.
- **Nothing can lose tabs without a copy.** The move a browser makes by itself is
  preceded by a copy, writes the record in one piece, and is taken up again at the next
  start if it was cut short. It cannot be undone: there is nothing to go back to.

## A. A safe core (needed with or without Sidebery)

- [x] Documents stay out of the signed extension; changing them is no release.
- [x] A green run on main can always release; a run started by hand cannot leave
      a commit behind. The second try of a smoke test is in the job, with a warning.
- [x] A passing fault at addons.mozilla.org does not lose a release; what to do
      with a bad release is written down.
- [x] A start with no windows keeps the tab record; a saved tab's last copy comes back.
- [x] An error during a start does not leave Tidier off; an essential in a removed
      container does not stop it.
- [x] A tab whose real page was in a closed window is not archived without a trace.
- [x] ⇧⌘T on an essential does not double it, and doubles cannot lose another.
- [x] Placeholders do not stay loaded when a new window gets many tabs, and the
      test no longer calls that a Sidebery bug.
- [x] A check of an update over a running session: same tabs, essentials and
      folders before and after.
- [x] Tests see errors inside Tidier, show why Firefox did not start, and the
      restart checks cannot quietly disappear from a green run.
- [x] A second ghost selected within 0.7 s of a pull opens; a tab closed within
      0.6 s of a pull closes everywhere.
- [x] A title or icon change writes the tab record only when something changed.
- [x] A page with unsaved input is not closed by archiving or a live folder.
- [x] Tidier keeps a copy of its own data: essentials, folders and saved tabs, as a
      dated file through the native host, taken in again from Tidier itself. A copy also
      holds the spaces with their rules and order, and lands in the space of the same name
      on another machine.
- [x] A live folder that has stopped (no host, no `gh` login) shows it.
- [x] README's permissions, files and claims match what is there.
- [x] What random use and a long run in a real Firefox found in code the daily browser
      shares: a pin of a tab Tidier is busy with counts, an unpin is always yours, a tab with
      no copy anywhere is taken for closed only right after Firefox starts, and a saved tab
      closed within half a second of another close goes back to its saved address instead
      of being removed. The Sidebery checks and a long run with Sidebery pass.

## B. Tidier alone (once behind a setting, now the only way)

A first version of all of it works in the test Firefox, without Sidebery.

- [x] **The setting and the test Firefox.** `tidierAlone` chose it per machine, until
      part E took the setting away; a value still stored is never read. Every test
      Firefox is without Sidebery.
- [x] **The sidebar as the sidebar.** A key and a button for it, back after an update.
      Checks of what it shows and does, and of its idle cost. It draws only what
      changed, so clicks and drags are not lost.
- [x] **Spaces.** Other spaces' tabs hidden, also from ⌃Tab (`tabHide`, optional, so
      updates never wait for a click). Switching with the bar and ⌃1/2/3, also to an
      empty space. New tabs and links from other apps in the active space. Closing the
      last tab of a space stays in the space.
- [x] **Folders as Tidier's data.** Create, rename, delete, fold. A folder has no tab
      of its own, and no tab event can delete it. Saved tabs, archiving and live
      folders work on these folders.
- [x] **Using it.** Drag tabs, into and out of folders, between essentials and tabs and to
      other spaces; the order follows in every window. A new tab button. Tidier's own
      menu on tabs, tiles, folders, spaces and the list. Sound indicator and mute. Keys.
- [x] **By keyboard and for a screen reader.** One place for the keyboard in the sidebar,
      a button's own Enter, menus by key, the essentials' grid, F2 to rename; rows,
      folders, essentials and spaces named, with what is selected and open.
- [x] **Rules.** An address always opens in a given space, edited in Tidier.
- [x] **Settings in Tidier.** A page for the rules, spaces' names, archiving, copies and
      moving over.
- [x] **What Sidebery does well**, in Tidier's own simple way: a short menu of Tidier's own on
      every tab, selecting several tabs, one quiet line with undo, Clear, a list that shows where
      you are, one place for new tabs, closed folders that rest, sound and news marks, honest
      dragging, safe moves. Sidebery has hundreds of options; each became one fixed
      behaviour or nothing.
- [x] **Container session isolation**, as strong as Sidebery's: nothing goes out in the wrong
      container, a space's own proxy and user agent, signing out, spaces made, changed and deleted in
      Tidier, a vanished container brought back, a copy of a tab and a folder to another space.
- [x] **The command bar**, as in Arc: one key, one field, everything from it. Shortcuts as in Arc.
- [x] **Finding archived tabs**, a small window for links from other apps, and link preview.
- [x] **A refined design**: judged from screenshots, in light and dark, at every width.
- [x] **Very robust and efficient**: random use checked against what must always hold, a long
      run in a real Firefox, and measured with up to 1000 tabs.

All of part B is checked in the test Firefox, in release Firefox and in Developer Edition.
What a test Firefox cannot show is left for the second Mac: a real trackpad and drag and drop,
links from real apps, real sound and calls, and real Firefox Sync between two machines.

## Where things live

Tidier is generic: this repository holds no one's setup, and nothing in it should.

- **Your setup** (spaces, essentials, folders, saved tabs, names, rules) is in Tidier in the
  browser, in your Firefox account through Firefox Sync, and in a daily copy on each machine.
  It gets there once, by taking in a file: from Zen or Arc (`tools/from_arc_zen.py`), or a
  Tidier copy. Such a file holds your addresses and stays on the machine.
- **Each machine's own choices** (which spaces are hidden there, which of Firefox's keys are cleared) and
  Firefox's settings are in dotfiles, given to Tidier as managed storage.
- To do: Tidier's own tests run with Tidier's defaults, not with the private dotfiles; a
  check of the dotfiles' Firefox files belongs with the dotfiles.

## The order from here

1. This to main, where the smoke test is the gate, and the daily Mac updates by itself: its
   open tabs and essentials stay, Sidebery's folders become Tidier's, and the settings
   page comes in front to say so. The owner then shows Tidier's sidebar, lets Tidier hide
   other spaces' tabs, and removes Sidebery in about:addons.
2. The Zen file taken in on the settings page: it is the setup the owner wants, and
   what the move brought from Sidebery need not be kept.
3. The dotfiles cleared of Sidebery, and Firefox's own ⌘1 to ⌘9, ⌘D and ⌘T cleared in
   `customKeys.json`, with `firefoxKeys` telling Tidier so (part E).
4. Sync turned on there, with Add-ons ticked in Firefox Sync (or
   `services.sync.engine.extension-storage.force`). The setup is about 12 kB of the
   100 kB Firefox gives an add-on.
5. The second Mac signs in to the same Firefox account, turns on sync, and gets the same
   setup, with the daily Mac's work space hidden there: the first real sync between two
   machines. What only a real screen can show is measured there (part C).

## C. Trying it on the second Mac

- [ ] It gets Firefox as default, and the Firefox files from dotfiles, declared in its
      own configuration. Its commits are signed: an unsigned commit in dotfiles
      stops the Firefox updates on the daily Mac.
- [ ] Tidier from a clean Firefox, from what is written down, with no Sidebery. The
      dotfiles clear ⌘1 to ⌘9, ⌘D and ⌘T in `about:keyboard` and tell Tidier so
      (`firefoxKeys`), and `user.js` stops Firefox from guessing a link's container
      (README, Keys and Isolation).
- [ ] Measured there, where the test Firefox cannot: switching space, a new window, the
      command bar opening; and whether quick presses of ⌃⌘↓ are lost while the tab just
      selected starts loading (about 1 in 8 in the slowed-down test Firefox, none with
      Firefox's own ⌃Page Down). If they are, tab stepping goes another way.
- [ ] A swipe between spaces under real fingers (README, Swiping between spaces): that it
      follows them, that a flick goes one space and a slow swipe lands where it should, that
      resting the fingers half way does not let go too soon, that scrolling never switches,
      and that Firefox's own swipe back in history stays out of the sidebar. The test
      Firefox has no trackpad: the numbers at the top of `sidebar/swipetrack.js` are set by
      reasoning, and are what to change if it feels wrong.
- [ ] A link dragged into the sidebar from a real page and from another app (Slack, Mail,
      Finder's address of a web page): that it is taken as a link, lands where the line
      says, and that a drop where it has no place does not open the page in the sidebar itself.
- [ ] Used for real for a while; what is missing goes in here and in FEATURES.md.

## D. Moving the daily browser

- [x] Rules and order of spaces imported from Sidebery's export, which is the only
      place they can be read from, also the address rules of its panels and which folders
      were closed.
- [x] The move by itself, at the first start of a Tidier without Sidebery, which an update
      is: a copy, then the record, and only then are Sidebery's folder pages closed. Open
      tabs and essentials are not touched. Checked on the fake Firefox from the states a
      browser can be in (the setting never set or off, with and without what an export
      left, essentials, several containers, two windows, hiding not allowed, a start cut
      short, Sidebery still running and closing a folder's tabs), and in the test Firefox
      (`old_browser`). The click-by-click move and the way back, which were built first
      and checked with a real Sidebery, are gone with the setting.
- [x] After the move no tab is hidden until the settings page is in front, so that
      Firefox's question about hidden tabs comes while the page says what to answer, and not
      over the sidebar. The page says once what came over and that Sidebery can be removed.
      Another window, which Firefox leaves without Tidier's sidebar, shows the page too,
      with a button for it.
- [x] Spaces, essentials, pinned tabs and folders from Arc or Zen, which is the setup the
      owner wants (`tools/from_arc_zen.py`), taken in on the settings page like a copy.
      Checked with made-up files and with the owner's real Zen setup (31 essentials,
      8 folders, 43 saved tabs in three spaces), in a test Firefox.
- [ ] The daily Mac has updated, and Sidebery is removed from it (the owner's click: Tidier
      neither can nor may see other extensions).

## E. Without Sidebery, everywhere

- [x] Sidebery and all that exists because of it removed: folders first, its tree
      rules, waiting for its sidebar, `tests/fixtures/sidebery.json`, `tools/fix_spaces.py`,
      the setting, the move by a click and moving back, and the right to see other
      extensions (`management`). Tidier takes no message from another extension, and the
      README lists every right it has (a unit test holds both).
- [ ] Then its files in dotfiles (`sidebery.css`, `sidebery-settings.json`, their managed
      storage, the lines of `user.js` and `customKeys.json` that were for Sidebery). Tidier
      and its tests read none of them any more.
- [x] Essentials, folders and spaces on every machine by Firefox Sync, within its limits.
      Built and checked in a test Firefox, off by default; real Firefox Sync between two
      machines is not tried yet.
- [x] Spaces hidden per machine. Hidden only: the data is on every machine.
- [ ] Every Mac set up the same way.

## Stretch goal: made for working with Claude and other agents

Off by default. Copying a page or tabs as clean text for Claude. An MCP server so Claude
Code can work in the browser, local only. Agents get a space of their own with its own
logins, see and touch only that, unless you allow more. What they do shows, and one
click stops it.

- [x] All of it is there, off by default, and checked; not yet tried with
      Claude Code itself.
- [x] The log says what happened, once, and what was refused, in plain words with the space
      it tried, file: addresses included; closing a space ends what waits there; each agent
      has its own last tab; with agents off, what an agent left you stays on the bar.

## F. After that

Tidier was gone through against Zen and Arc on 13 November 2026 (Zen's release notes up to
1.24.2b; Arc as it was left). What they have and Tidier has not is in FEATURES.md, each
with where it stands. In this order, the first five being the ones that are felt every day:

- [x] A swipe on the trackpad switches space, the list following the fingers.
- [x] A saved tab or an essential that has left its address says so, and can go back or
      keep the new one; the close button says when it only unloads.
- [x] A link dragged from a page or another app can be dropped in the sidebar: a tab where
      it lands, in a folder or among the essentials.
- [x] Soft motion where something comes or goes: switching space by a click or a key
      slides as a swipe does, a folder opens and closes by its height, a new row fades in.
      Short, only for what you caused, and no row moves under the pointer.
- [x] Pause and play from the sidebar, beside the speaker.

Then the small ones, in any order: an icon on a folder, any colour for a space, a click on
the space's name closes all its folders, unload every other space. And then the rest of
what FEATURES.md has as Later, starting with what is missed most in use.

## Choices made

Changed by saying so. All of them can be reversed.

- A tab that is only a placeholder is archived like any other, the time counting from when it
  became one, since Tidier's own list holds its address and can bring it back.
- Closing the last window and quitting brings your tabs back unloaded.
- A failed smoke test gets one more try, marked with a warning. To be looked at
  again once it is known how often the first try fails.
- A failure in Developer Edition only stops releases until restart is also
  tested in release Firefox; then it only warns.
- Archiving counts clock time: a night away closes yesterday's ordinary tabs.
- `tabHide` is optional, asked for in the sidebar, so that no update ever waits for a
  click. Firefox shows hidden tabs again at each update, so Tidier hides them again
  when it starts. A browser moved over by itself has not been asked yet: its sidebar asks.
- Essentials stay pinned tabs, so other spaces' essentials stay in ⌃Tab; Firefox
  cannot hide a pinned tab.
- A link opened from a tab in a folder is an ordinary tab, as in Arc.
- No page's first request goes out in the wrong container: it is stopped before it
  leaves, as Sidebery did. That takes access to all websites, so it is optional, asked
  for in the sidebar after hiding tabs. Without it a link's first request goes out with
  no container before it is opened in its space, as before: it carries no login.
- An address that belongs in another space opens there, and the tab it was typed in stays
  if it holds anything: a page's history or a saved tab is not lost for it. A rule's
  regular expression runs on a small engine of Tidier's own, since Firefox's can take for
  ever on every navigation. That engine has no look-around or back-references: such a rule
  does nothing, and the settings page says so. A rule with a slash but no valid flags after
  the last one is plain text, as in Sidebery.
- A rule for a space that is gone does nothing, and says so in the sidebar and on the
  settings page. One for a space hidden on this machine opens the tab where you are, and
  says so in the sidebar.
- A pinned tab is an essential, also one reopened after its essential was removed.
- A page is loaded once. A selected copy of it in a window you are not using becomes a
  placeholder, and the page comes to you when you go to that window. It also goes back to a
  window that is still on it as soon as the window that took it leaves it for another tab
  (the owner, 13 November 2026: with two windows side by side, one stayed grey on a page that
  no window showed any more). An essential's page does the same.
- A new tab is in the other windows half a second after its page has loaded, not two seconds
  after (the owner, 13 November 2026: tabs opened in one window seemed not to come to the
  others). The longer wait stays for a page that has not loaded or is about to be opened
  again in another space.
- Going to another space, its dot is marked at the click and the list is drawn without the
  usual short wait: what you asked for yourself should never look as if it was not taken.
- Clear asks nothing: one line offers Undo. Closing several tabs and deleting a folder work
  the same way.
- Tabs moved to another space go to the end of its tabs, not where new tabs go, so several
  moved together keep their order. Each arrives as it was, under its own record: unloaded if it
  was, loaded in the window that had its page if it was, muted if it was; a folder's tabs too.
  One line says where they went, with Undo.
- Small windows for links from other apps have one on-off on the settings page, to be looked
  at again after the second Mac.
- The command bar floats in the window you are in (the owner, 13 November 2026: the small
  window of its own looked odd). It is the
  popup of Tidier's toolbar button, which only the key opens, placed by the dotfiles'
  stylesheet where the address bar floats. With another panel of Firefox's open it is still
  the small window. ⌘W stays Firefox's: with the bar open it closes the tab under it.
- A row that closes folds away at once, and the rows below come up into its place in one soft
  move, as in Zen and Arc (the owner, 13 November 2026: the room a closed row kept while the
  pointer was in the list left holes, which then filled late). A double click on × still closes
  one tab: the second click does nothing.
- ⇧⌘C says *Address copied* on the page itself (the owner, the same day: nothing showed that
  it had worked). For that Tidier has `activeTab`: the page a key of Tidier's is pressed in.
  It is used for that word only; a page is read only with the access to all websites. Every
  other way of copying an address says the same word, in the same place (from a menu
  usually the sidebar's line, since `activeTab` is for a key of Tidier's), so that copying
  always looks the same wherever you asked for it.
- Firefox's own ⌘1 to ⌘9, ⌘D and ⌘T are to be cleared by the dotfiles, now that no
  browser needs them for Sidebery. No extension can read about:keyboard,
  so the dotfiles tell Tidier what they cleared (managed storage), and a key they did not
  clear is shown as Firefox's, not as Tidier's.
- An address the MCP server refuses (file:, about:) still goes to Tidier, marked as refused
  and with nothing to carry out, so that the attempt is in the log.
