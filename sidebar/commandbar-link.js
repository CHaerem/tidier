// The selection lives only in the sidebar, and the command bar's commands act on it, so
// the bar asks when it opens (barPickedTabs in commandbar.js). In a block of its own:
// the sidebar's scripts share one scope.
{
  let thisWindow = null;
  browser.windows.getCurrent().then(w => { thisWindow = w.id; });
  // A folder chosen in the bar: its head, scrolled into view and marked for a moment, once
  // the view that opens it has been drawn.
  const MARK_MS = 1200;
  browser.runtime.onMessage.addListener(msg => {
    if (msg?.type !== "commandBarMark" || msg.windowId !== thisWindow) return;
    const started = Date.now();
    const mark = () => {
      const head = [...document.querySelectorAll("[data-folder-head]")].find(h => h.dataset.folderHead === msg.folder);
      if (!head) { if (Date.now() - started < 2000) setTimeout(mark, 50); return; }
      head.scrollIntoView({ block: "nearest" });
      head.classList.add("marked");
      setTimeout(() => head.classList.remove("marked"), MARK_MS);
    };
    mark();
  });
  browser.runtime.onMessage.addListener(msg => {
    if (msg?.type !== "commandBarSelection" || msg.windowId !== thisWindow) return;
    // The selection also when the tab you are on is not in it: you can be on an essential and
    // select rows, or take your tab out with a second ⌘-click. selectedTabs(id) only gives the
    // selection for a tab in it, so it is asked for one that is.
    const inIt = document.querySelector(".picked[data-tab]");
    return Promise.resolve(window.selectedTabs(inIt ? Number(inIt.dataset.tab) : msg.tabId));
  });
}
