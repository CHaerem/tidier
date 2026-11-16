// Each space's colour, as in Zen and Arc: any colour, not only the eight Firefox has for
// containers. It is the dot's on the bar, and the window takes a soft tint of it, the
// sidebar and the frame around the page alike, light or dark as the system is.
//
// The colour you choose is Tidier's own (SPACE_COLOURS); without one, a space has its
// container's (Firefox's colorCode). A container's colour can only be one of Firefox's
// eight names, so the chosen one cannot be kept there.
//
// The window is tinted with a theme of its own (theme.update for one window): an extension
// reaches nothing else of Firefox's window. The theme gives only the frame's colour
// (--lwt-accent-color, which userChrome.css takes for the window's surface); but a window
// with a theme draws its text and icons in the theme's colours, black where it has none,
// so it gives Firefox's own as well (FIREFOX_LOOK), and a smoke check holds them to what
// Firefox draws without a theme.

// Read once, and kept here: only setSpaceColour changes it. (Not by listening to storage:
// Firefox hands a listener every write, the whole tab record too, see syncListen in sync.js.)
const SPACE_COLOURS = "spaceColours"; // storage.local: { [container id]: "#rrggbb" }
let chosenColours = {};
browser.storage.local.get(SPACE_COLOURS).then(got => { chosenColours = got[SPACE_COLOURS] ?? {}; tintAllSoon(); }, () => {});

// Firefox's colours for its eight container colours: what colorCode says.
const containerColours = new Map(); // container id -> colorCode
browser.contextualIdentities.onUpdated.addListener(({ contextualIdentity: c }) => { containerColours.set(c.cookieStoreId, c.colorCode); tintAllSoon(); });
browser.contextualIdentities.onRemoved.addListener(({ contextualIdentity: c }) => containerColours.delete(c.cookieStoreId));
async function containerColour(space) {
  if (!containerColours.has(space)) containerColours.set(space, (await browser.contextualIdentities.get(space).catch(() => null))?.colorCode ?? null);
  return containerColours.get(space);
}

// A colour as #rrggbb, or null for what is none (a word that is no colour, a colour with
// see-through in it).
function hexColour(text) {
  const t = String(text ?? "").trim().toLowerCase();
  if (/^#[0-9a-f]{6}$/.test(t)) return t;
  if (/^#[0-9a-f]{3}$/.test(t)) return "#" + [...t.slice(1)].map(c => c + c).join("");
  return null;
}
const spaceColour = (space, container) => chosenColours[space] ?? hexColour(container) ?? null;

async function setSpaceColour(space, colour) {
  const hex = colour ? hexColour(colour) : null;
  if (colour && !hex) return;
  const all = { ...chosenColours };
  if (hex) all[space] = hex;
  else delete all[space];
  chosenColours = all;
  await browser.storage.local.set({ [SPACE_COLOURS]: all });
  tintAllSoon();
  viewAllSoon(); // sidebar-view.js: the dot, and the sidebar's surface
}

// --- The tint ------------------------------------------------------------------------------
// A colour's own hue, at the lightness and the little chroma a surface has: what the
// dotfiles had picked by hand for each space, from Firefox's colour for it (oklch, so that
// every hue is as light as every other). A grey stays a grey. Tidier's own pages work out
// the same in their style (--space-tint, sidebar/tokens.css, with these numbers), so the
// sidebar and the window around it are one surface.
const TINT = { light: { l: 0.935, c: 0.018, of: 0.12 }, dark: { l: 0.25, c: 0.027, of: 0.17 } };
function tintsOf(hex) {
  const [, c, h] = oklchOf(hex);
  const tint = ({ l, c: most, of }) => hexOf(oklchToRgb(l, Math.min(most, c * of), h));
  return { light: tint(TINT.light), dark: tint(TINT.dark) };
}

// sRGB to oklch and back (Björn Ottosson's oklab, with its published matrices).
const toLinear = v => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
const fromLinear = v => (v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055);
function oklchOf(hex) {
  const [r, g, b] = [1, 3, 5].map(i => toLinear(parseInt(hex.slice(i, i + 2), 16) / 255));
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  const L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s;
  const A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s;
  const B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s;
  return [L, Math.hypot(A, B), (Math.atan2(B, A) * 180 / Math.PI + 360) % 360];
}
function oklchToRgb(L, C, h) {
  const A = C * Math.cos(h * Math.PI / 180), B = C * Math.sin(h * Math.PI / 180);
  const l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3;
  const m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3;
  const s = (L - 0.0894841775 * A - 1.2914855480 * B) ** 3;
  return [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
  ].map(v => Math.round(Math.min(1, Math.max(0, fromLinear(v))) * 255));
}
const hexOf = rgb => "#" + rgb.map(v => v.toString(16).padStart(2, "0")).join("");

// What Firefox draws without a theme (its own, in 158 to 161), light and dark: with a theme
// it draws the theme's colours instead, and black where the theme has none. tests/smokechecks
// (alone_space_colour) compares the two, so a Firefox that changes its own is seen.
const FIREFOX_LOOK = {
  light: {
    text: "rgb(21, 20, 26)", tabs: "rgb(24, 14, 48)", icons: "rgb(117, 102, 159)", accent: "rgb(118, 78, 221)", pressed: "rgba(117, 102, 159, 0.4)", sidebarText: "rgb(21, 20, 26)",
    field: "rgba(255, 255, 255, 0.4)", fieldText: "rgb(62, 49, 95)", fieldBorder: "#d6d5da", fieldOpen: "rgb(255, 255, 255)",
    panel: "rgb(255, 255, 255)", panelText: "rgb(24, 14, 48)", panelBorder: "rgba(24, 14, 48, 0.24)", chosen: "rgba(62, 49, 95, 0.27)",
    edge: "rgba(201, 192, 227, 0.5)", sidebar: "rgb(255, 255, 255)",
  },
  dark: {
    text: "rgb(252, 251, 255)", tabs: "rgb(242, 240, 248)", icons: "rgb(231, 225, 248)", accent: "rgb(184, 156, 255)", pressed: "rgba(182, 170, 217, 0.4)", sidebarText: "rgb(249, 249, 250)",
    field: "rgba(0, 0, 0, 0.2)", fieldText: "rgb(231, 225, 248)", fieldBorder: "#3f3e42", fieldOpen: "rgb(23, 21, 25)", // (its list's: the larger part)
    panel: "rgb(23, 21, 25)", panelText: "rgb(242, 240, 248)", panelBorder: "rgba(242, 240, 248, 0.24)", chosen: "rgba(231, 225, 248, 0.32)",
    edge: "rgba(63, 62, 66, 0.5)", sidebar: "rgb(28, 27, 34)",
  },
};
function themeFor(frame, scheme) {
  const f = FIREFOX_LOOK[scheme];
  return {
    colors: {
      frame, frame_inactive: frame,
      tab_background_text: f.tabs, toolbar_text: f.text, bookmark_text: f.text, icons: f.icons, icons_attention: f.accent,
      button_background_active: f.pressed, sidebar: f.sidebar, sidebar_text: f.sidebarText, sidebar_border: f.edge,
      toolbar_bottom_separator: f.edge, // the line around the page
      toolbar_field: f.field, toolbar_field_text: f.fieldText, toolbar_field_border: f.fieldBorder,
      // The address bar while you type in it, its list, and Firefox's panels.
      toolbar_field_focus: f.fieldOpen, toolbar_field_text_focus: f.fieldText, toolbar_field_border_focus: f.accent,
      popup: f.panel, popup_text: f.panelText, popup_border: f.panelBorder, popup_highlight: f.chosen, popup_highlight_text: f.fieldText,
    },
    // Light or dark as the system is, as without a theme. Not the scheme these colours are for:
    // Tidier's own pages follow the window's scheme, so this page would then see the scheme it
    // gave, and never the system's again.
    properties: { color_scheme: "system", content_color_scheme: "system" },
  };
}

// --- Each window, in the tint of the space it shows -----------------------------------------
// Given only when it changes: showSpace (spaces.js) calls this for every burst of new tabs,
// and with nothing happening Tidier must do nothing.
const darkScheme = globalThis.matchMedia?.("(prefers-color-scheme: dark)");
const schemeNow = () => (darkScheme?.matches ? "dark" : "light");
const tintShown = new Map(); // windowId -> the frame colour its theme has
browser.windows.onRemoved.addListener(windowId => tintShown.delete(windowId));
async function tintWindow(windowId, space) {
  if (!browser.theme?.update) return;
  const colour = space && spaceColour(space, await containerColour(space));
  const frame = colour ? tintsOf(colour)[schemeNow()] : null;
  if (tintShown.get(windowId) === frame) return;
  tintShown.set(windowId, frame);
  // A private window's tabs are none of Tidier's, and it keeps Firefox's own look for them.
  if ((await browser.windows.get(windowId).catch(() => null))?.incognito !== false) return;
  // A window with no space (no containers at all) has Firefox's own look.
  if (frame) await browser.theme.update(windowId, themeFor(frame, schemeNow())).catch(() => tintShown.delete(windowId));
  else await browser.theme.reset(windowId).catch(() => {});
}
// A theme put on a window by something else (another add-on, Firefox's own when you choose
// one) takes the space's tint away: it is given back. Tidier's own updates come here too,
// and are known by their frame.
browser.theme?.onUpdated?.addListener(({ theme, windowId }) => {
  if (windowId === undefined || !tintShown.has(windowId) || theme?.colors?.frame === tintShown.get(windowId)) return;
  tintShown.delete(windowId);
  if (activeSpace.has(windowId)) tintWindow(windowId, activeSpace.get(windowId)).catch(noteError);
});
// Every window, when what a tint is made of changes: light to dark, a colour chosen. And as
// this part starts, before Tidier has: a window is plain until it has its theme (Firefox
// keeps none for a window over a restart), so it gets it by the space kept with it
// (SPACE_KEY, spaces.js), without waiting for the tabs to be looked at.
const spaceKeptIn = async windowId => activeSpace.get(windowId) ?? await browser.sessions.getWindowValue(windowId, SPACE_KEY).catch(() => undefined);
let tintAllTimer = null;
function tintAllSoon() {
  clearTimeout(tintAllTimer);
  tintAllTimer = setTimeout(async () => {
    for (const w of await browser.windows.getAll({ windowTypes: ["normal"] }).catch(() => [])) {
      const space = w.incognito ? null : await spaceKeptIn(w.id);
      if (space) await tintWindow(w.id, space).catch(noteError);
    }
  }, 50);
}
darkScheme?.addEventListener("change", tintAllSoon);
// A new window, at once: in the space of the window it was opened from (spaces.js sets that
// in its own listener, before this one), or the one kept with a window that came back.
browser.windows.onCreated.addListener(async win => {
  const space = win.type === "normal" && !win.incognito && await spaceKeptIn(win.id);
  if (space) tintWindow(win.id, space).catch(noteError);
});
