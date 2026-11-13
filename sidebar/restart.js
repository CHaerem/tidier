// One line, when Firefox must be started again to read its setup files (firefoxsetup.js in
// the background): the line is the button, as every notice that asks something is, with a
// × to say not now. Firefox quits as with ⌘Q and opens again, and your tabs come back.
//
// In a block, so that no name here can clash with another sidebar script.
{
  const line = document.getElementById("restart");
  const button = document.getElementById("restart-firefox");
  const away = el("button", "ask-no", "×");
  away.title = "Not now";
  line.append(away);

  const WORDS = "Restart Firefox to finish updating";
  const STILL_HERE_MS = 8000; // Firefox is gone well before; still here, it stayed (a question it asked, or no helper)
  const ready = () => { button.disabled = false; textIf(button, WORDS); };
  // Once: a second click would only ask a Firefox that is already quitting.
  button.onclick = secondClick.acts(() => {
    button.disabled = true;
    button.textContent = "Restarting Firefox…";
    send({ type: "restartFirefox" });
    setTimeout(ready, STILL_HERE_MS);
  });
  // It fades where it is, so the list does not come into its room under the pointer
  // (isolation.js). A view made before the background heard of it must not bring it back.
  let putAway = null;
  away.onclick = secondClick.acts(() => {
    putAway = shownFor;
    goQuietly(line);
    send({ type: "restartSeen" });
  });

  let shownFor = null; // the files the line is shown for, as one string
  port.onMessage.addListener(next => {
    const files = next.restart?.files, key = files?.join() ?? null;
    if (files && key !== putAway) {
      shownFor = key;
      line.classList.remove("going");
      if (line.hidden) { line.hidden = false; ready(); }
      setIf(button, "title", `Firefox reads ${files.join(" and ")} only as it starts, and ${files.length > 1 ? "they have" : "it has"} changed since. Your tabs come back.`);
    } else if (!line.hidden && !line.classList.contains("going")) line.hidden = true;
  });
}
