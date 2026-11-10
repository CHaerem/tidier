// Placeholder page for ghosts and essential copies.
//
// Firefox cannot give an unloaded tab an icon, so a placeholder is briefly loaded
// as this tiny local page, which sets the real page's title and icon, and is then
// unloaded again (an unloaded tab keeps both). A placeholder needs that only when its
// title changes: it is made unloaded, as Tidier's sidebar draws it from the record
// (createRep, tabsync.js).
//
// When the placeholder is shown:
// - a live tab that has never been loaded ("lazy", e.g. a live folder's pull
//   request): it goes straight to the real page;
// - ghost or essential copy: the background script moves the loaded tab into
//   this window; only if there is none does the placeholder load the page itself.

const params = new URLSearchParams(location.search);
const kind = params.get("kind"); // "ghost" | "essential" | "lazy"
const key = params.get("key");

function shown(info) {
  if (kind === "lazy") { location.replace(info.url); return; }
  // An essential opens its page itself only if no other window has it loaded
  // (essentialShown, essentials.js); a ghost only if there is no live tab.
  const type = kind === "essential" ? "essentialShown" : "ghostShown";
  browser.runtime.sendMessage({ type }).then(r => { if (r?.load) location.replace(info.url); else face(info); });
}

// Told to wait: in a window you are not using, the page stays where it is until you come
// here (or it is on its way). Its name, site and icon say which page this is: a blank page
// with "Extension (Tidier)" in the address bar, beside the window you use, looked broken.
function face(info) {
  if (document.querySelector("main") || !document.body) return;
  let site = "";
  try { site = new URL(info.url).host; } catch { /* no address to show */ }
  const main = document.createElement("main");
  // Only an icon that needs nothing from the site: the site's own would be asked for outside any space.
  if (/^data:/.test(info.icon || "")) main.append(Object.assign(document.createElement("img"), { src: info.icon, alt: "" }));
  main.append(Object.assign(document.createElement("div"), { className: "title", textContent: info.title || site }));
  if (site && site !== info.title) main.append(Object.assign(document.createElement("div"), { className: "site", textContent: site }));
  main.append(Object.assign(document.createElement("div"), { className: "when", textContent: "In another window now. It comes here when you use this one." }));
  document.body.append(main);
  // The page as it was when it left this window for the one you use, grey under a veil, as
  // Zen and Arc show a tab that another window has (pull, tabsync.js). There at once, and
  // the words with it: this window was showing the page a moment ago.
  browser.runtime.sendMessage({ type: "ghostPicture" }).then(picture => {
    if (!/^data:image\//.test(picture || "")) return;
    const veil = Object.assign(document.createElement("div"), { className: "veil" });
    veil.style.backgroundImage = `url("${picture}")`;
    document.body.prepend(veil);
    document.body.classList.add("veiled");
  }).catch(() => {});
}

// The first icon that loads: the one saved for the page, else the site's
// /favicon.ico. (Firefox's own icon cache, page-icon:, cannot be loaded from
// an extension's process.)
async function findIcon(info) {
  const candidates = [info.icon, new URL("/favicon.ico", info.url).href];
  for (const src of candidates.filter(Boolean)) {
    const loads = await new Promise(resolve => {
      const img = new Image();
      img.onload = () => resolve(true);
      img.onerror = () => resolve(false);
      img.src = src;
    });
    if (loads) return src;
  }
  return null;
}

browser.runtime.sendMessage({ type: "ghostInfo", kind, key }).then(async info => {
  if (!info) { browser.runtime.sendMessage({ type: "ghostOrphan", kind, key }); return; }
  document.title = info.title || info.url;
  // Selected and left again without opening its page, it unloads too (a placeholder
  // selected in a window you are not using, say); it would otherwise stay loaded.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") shown(info); else settle(info);
  });
  if (document.visibilityState === "visible") shown(info); else settle(info);
});

async function settle(info) {
  const icon = await findIcon(info);
  if (icon && !document.querySelector("link[rel=icon]")) {
    const link = document.createElement("link");
    link.rel = "icon";
    link.href = icon;
    document.head.append(link);
  }
  // Unloaded by the background script once Firefox shows the icon.
  browser.runtime.sendMessage({ type: "ghostReady", icon: !!icon });
}
