// --- Where the sound is coming from -----------------------------------------------
// What is drawn for sounds.js's view: a speaker on a tile, a row, a closed folder and
// a space's dot. A click on any of them takes effect on the real page, which may be in
// another window; it never selects the tab, folds the folder or switches the space.

// Drawn rather than an emoji: an emoji has its own colours, its size differs per
// system, and at this size it cannot be told from the page's icon beside it.
const SVG = "http://www.w3.org/2000/svg";
function speaker(muted) {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("class", "speaker");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("aria-hidden", "true");
  const line = d => {
    const path = document.createElementNS(SVG, "path");
    path.setAttribute("d", d);
    return path;
  };
  const body = line("M1.5 5.75v4.5h2.75L8 13.25V2.75L4.25 5.75z");
  body.setAttribute("stroke", "none");
  const rest = line(muted ? "M10.75 5.75l4 4.5M14.75 5.75l-4 4.5" : "M10.5 5.5a3.6 3.6 0 0 1 0 5M12.75 3.5a6.4 6.4 0 0 1 0 9");
  rest.setAttribute("fill", "none");
  rest.setAttribute("stroke-width", "1.5");
  rest.setAttribute("stroke-linecap", "round");
  svg.append(body, rest);
  return svg;
}

// What a page Tidier paused shows in the speaker's place (tabactions.js): a play mark, which
// plays it again. The same size and place, so nothing moves when one becomes the other.
function playMark() {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("class", "speaker");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(SVG, "path");
  path.setAttribute("d", "M4.5 3.1v9.8c0 .5.55.8.97.53l7.4-4.9a.63.63 0 0 0 0-1.06l-7.4-4.9a.63.63 0 0 0-.97.53z");
  path.setAttribute("stroke", "none");
  svg.append(path);
  return svg;
}

// `of`: a tile's or a row's item, or a closed folder. Empty while nothing sounds, for
// spreading into what is drawn.
function soundMark(of) {
  if (!of.sound) return [];
  if (of.sound === "paused") {
    const mark = el("button", "sound paused");
    mark.title = "Play";
    mark.tabIndex = -1; // as the speaker: Play is on the menu
    mark.append(playMark());
    mark.onclick = e => { e.stopPropagation(); send({ type: "tabAction", action: "play", tabIds: [of.soundTabId] }); };
    mark.ondblclick = e => e.stopPropagation();
    return [mark];
  }
  const mark = el("button", "sound" + (of.sound === "muted" ? " muted" : ""));
  mark.title = of.sound === "muted" ? "Unmute" : "Mute";
  mark.tabIndex = -1; // for the pointer: no stop for Tab in the list (keys.js), and Mute is on the menu
  mark.append(speaker(of.sound === "muted"));
  mark.onclick = e => { e.stopPropagation(); send({ type: "mute", tabId: of.soundTabId, muted: of.sound !== "muted" }); };
  mark.ondblclick = e => e.stopPropagation(); // a quick mute and unmute, not a folder's rename
  return [mark];
}

// A space's dot, while something there plays: its mark goes to the tab, the dot itself
// switches as always. A span, as a button inside the space's button is not allowed.
function spaceSound(button, s) {
  button.querySelector(".sound")?.remove();
  if (!s.soundTabId) return;
  const mark = el("span", "sound");
  mark.title = "Go to the tab that is playing";
  mark.append(speaker(false));
  mark.onclick = e => { e.stopPropagation(); send({ type: "goToSound", tabId: s.soundTabId }); };
  button.append(mark);
}
