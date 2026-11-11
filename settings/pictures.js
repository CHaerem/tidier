// Pictures of pages on the settings page (pull, tabsync.js; the bridge's screenshot).
(async () => {
  const state = document.getElementById("pictures-state"), allow = document.getElementById("pictures-allow");
  // Firefox gives an extension pictures of pages only with "<all_urls>", which is every website
  // and the files on this computer in one. Nothing else in Tidier asks for it in this form.
  const pictures = { origins: ["<all_urls>"] };
  const show = async () => {
    const given = await browser.permissions.contains(pictures);
    state.textContent = given
      ? "A page that another window has taken stays shown where it was, under a grey layer, until you come back to that window. An assistant you have let use Tidier can take a picture of a page."
      : "A window whose page another window has taken can keep showing it, under a grey layer, instead of only its name. Firefox gives pictures of pages only together with access to all websites and to files on this computer, so it asks for that; Tidier uses it for pictures alone.";
    allow.hidden = given;
  };
  // Asked here: the permission needs your click.
  allow.onclick = () => browser.permissions.request(pictures).then(show);
  browser.permissions.onRemoved.addListener(show);
  browser.permissions.onAdded.addListener(show);
  await show();
})();
