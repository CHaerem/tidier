// A page in fullscreen stays in its window, on the settings page (fullscreen.js).
(async () => {
  const on = document.getElementById("fullscreen-stays");
  const state = document.getElementById("fullscreen-state"), allow = document.getElementById("fullscreen-allow");
  const set = s => { on.checked = s.on; };
  const allSites = { origins: ["*://*/*"] };
  // Whether a page is in fullscreen only the page can say, so Tidier asks it.
  const access = async () => {
    const given = await browser.permissions.contains(allSites);
    state.textContent = "A video or a presentation would leave fullscreen as it moved. Click its tab in another window, and you are taken to the window that has it instead."
      + (given ? "" : " Tidier has to ask the page whether it is in fullscreen, which takes access to all websites; without it the page moves as before.");
    allow.hidden = given;
  };
  // Asked here: the permission needs your click.
  allow.onclick = () => browser.permissions.request(allSites).then(access);
  on.onchange = async () => set(await browser.runtime.sendMessage({ type: "fullscreen:set", on: on.checked }));
  browser.permissions.onRemoved.addListener(access);
  browser.permissions.onAdded.addListener(access);
  set(await browser.runtime.sendMessage({ type: "fullscreen:get" }));
  await access();
})();
