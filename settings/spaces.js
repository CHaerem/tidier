// The Spaces section of the settings page: spaces are made, changed and deleted here, so
// Firefox's own container settings aren't needed (isolation.js does the work).
//
// One line per space, with its icon and name. What is rarely wanted is behind a small
// "More": colour, icon, proxy, user agent, signing out, deleting. The two things that
// cannot be undone ask first, in place: never a dialog.
//
// With Sidebery in use the line is only the name, as it always was.

const isolation = (what, more) => browser.runtime.sendMessage({ type: "isolation:" + what, ...more });
// Must be called right in your click, or Firefox refuses to ask.
const mayAsk = async permissions => { try { return await browser.permissions.request(permissions); } catch (err) { return false; } };
const moreOpen = new Set(); // the spaces showing More
const asking = new Map(); // space -> what it is asking: "signOut" or "delete"
const spaceFacts = new Map(); // space -> a line to show under it, until the next change
const unsavedNetwork = new Map(); // space -> a proxy typed that could not be saved, kept to be put right
let isolated = null;

function spaceIcon(iconUrl, color) {
  const icon = el("span", { className: "space-icon" });
  icon.style.setProperty("--icon", `url("${iconUrl}")`);
  icon.style.setProperty("--color", color);
  return icon;
}

// Redrawn after each thing you do here. Otherwise (a permission given, say) not while you
// are typing in it: that would take the text from under your hands.
async function drawSpaces(force) {
  if (!force && document.activeElement?.closest?.("#spaces")) return;
  if (!state.report.alone) {
    $("spaces").replaceChildren(...state.spaces.map(s => el("div", { className: "line" }, el("span", { className: "dot", ariaHidden: "true", style: `color:${s.color}` }), nameField(s))));
    return;
  }
  isolated = await isolation("get");
  // Asked while you came into the list (a space made here, say, and its name given the keyboard).
  if (!force && document.activeElement?.closest?.("#spaces")) return;
  $("new-space").hidden = false;
  $("isolation-ask").hidden = $("allow-isolation").hidden = await browser.permissions.contains({ permissions: ["webRequest", "webRequestBlocking"], origins: ["*://*/*"] });
  const focused = document.activeElement?.closest?.("[data-color], [data-icon]");
  const again = focused && { space: focused.closest("[data-space]")?.dataset.space, color: focused.dataset.color, icon: focused.dataset.icon };
  $("spaces").replaceChildren(...inBarOrder(isolated.spaces).map(spaceCard));
  // A colour or an icon chosen: the keyboard stays on it, rather than going back to the top.
  if (again?.space) $("spaces").querySelector(`[data-space="${again.space}"] ${again.color ? `[data-color="${again.color}"]` : `[data-icon="${again.icon}"]`}`)?.focus();
}

// A space's name. An emptied field is no name: the one it has comes back, and is kept as
// the field's own, so that clearing it after a rename does not bring back an older one.
function nameField(s) {
  const name = el("input", { type: "text", value: s.name, ariaLabel: `Name of ${s.name}` });
  name.dataset.nameOf = s.id;
  name.onchange = () => {
    const given = name.value.trim();
    if (!given) { name.value = s.name; return; }
    if (given === s.name) return;
    s.name = given;
    ask("space", { id: s.id, changes: { name: given } });
  };
  return name;
}

function spaceCard(s) {
  const open = moreOpen.has(s.id);
  const more = el("button", { className: "quiet more", textContent: open ? "Less" : "More", ariaExpanded: String(open), title: open ? "" : "Colour, icon, proxy, user agent, signing out, deleting" });
  more.onclick = () => { if (!moreOpen.delete(s.id)) moreOpen.add(s.id); asking.delete(s.id); spaceFacts.delete(s.id); drawSpaces(true); };
  // What changes every page in the space is said on its line, also with More closed.
  // A space not on the bar (hidden on this machine, under Shown on this machine) says so too.
  const hiddenHere = !!state.order?.length && !state.order.includes(s.id);
  const special = [hiddenHere && "hidden here", s.network.proxy && "proxy", s.network.userAgent && "own user agent"].filter(Boolean).join(" · ");
  const card = el("div", { className: "space-card" }, el("div", { className: "line" }, spaceIcon(s.iconUrl, s.colorCode), nameField(s),
    el("span", { className: "space-special", textContent: special, hidden: !special }), more));
  card.dataset.space = s.id;
  if (open) card.append(spaceMore(s));
  return card;
}

const spaceField = (label, ...content) => el("div", { className: "field" }, el("span", { className: "label", textContent: label }), el("div", { className: "content" }, ...content));

function spaceMore(s) {
  const choose = changes => async () => { await isolation("edit", { id: s.id, changes }); drawSpaces(true); };
  const colors = isolated.looks.colors.map(c => {
    const b = el("button", { className: "swatch" + (c.color === s.color ? " chosen" : ""), title: c.color, ariaLabel: c.color });
    b.dataset.color = c.color;
    b.style.setProperty("--color", c.colorCode);
    b.onclick = choose({ color: c.color });
    return b;
  });
  const icons = isolated.looks.icons.map(i => {
    const b = el("button", { className: "icon-choice" + (i.icon === s.icon ? " chosen" : ""), title: i.icon, ariaLabel: i.icon }, spaceIcon(i.iconUrl, s.colorCode));
    b.dataset.icon = i.icon;
    b.onclick = choose({ icon: i.icon });
    return b;
  });
  const box = el("div", { className: "space-more" },
    spaceField("Colour", el("div", { className: "choices" }, ...colors)),
    spaceField("Icon", el("div", { className: "choices" }, ...icons)),
    ...networkFields(s),
    spaceField("Logins", ...signOutPart(s)),
  );
  if (isolated.spaces.length > 1) box.append(spaceField("", ...deletePart(s)));
  const fact = spaceFacts.get(s.id);
  if (fact) box.append(el("p", { className: "hint fact", textContent: fact }));
  return box;
}

// A proxy and a user agent: asked for when first used, by the Save button's click.
function networkFields(s) {
  const proxy = s.network.proxy ?? {};
  const type = el("select", { ariaLabel: "Kind of proxy" }, el("option", { value: "", textContent: "No proxy" }),
    ...[["http", "HTTP"], ["https", "HTTPS"], ["socks", "SOCKS 5"], ["socks4", "SOCKS 4"]].map(([value, textContent]) => el("option", { value, textContent, selected: proxy.type === value })));
  const host = el("input", { type: "text", value: proxy.host ?? "", placeholder: "host", ariaLabel: "Proxy host", className: "host" });
  const port = el("input", { type: "number", value: proxy.port ?? "", placeholder: "port", min: 1, max: 65535, ariaLabel: "Proxy port", className: "port" });
  const agent = el("input", { type: "text", value: s.network.userAgent ?? "", placeholder: "Firefox's own", ariaLabel: "User agent" });
  const save = el("button", { textContent: "Save", className: "save", hidden: true });
  const proxyProblem = el("p", { className: "hint field-problem", hidden: true });
  const typed = unsavedNetwork.get(s.id); // what was typed before the list was drawn again
  if (typed) { type.value = typed.type; host.value = typed.host; port.value = typed.port; agent.value = typed.agent; save.hidden = false; proxyProblem.textContent = typed.problem ?? ""; proxyProblem.hidden = !typed.problem; }
  const shown = () => { host.hidden = port.hidden = !type.value; };
  shown();
  // A change makes what was said about the last one old: it goes.
  for (const input of [type, host, port, agent]) input.oninput = () => { shown(); save.hidden = false; proxyProblem.hidden = true; if (spaceFacts.get(s.id) === "Saved.") { spaceFacts.delete(s.id); box()?.querySelector(".fact")?.remove(); } };
  const box = () => $("spaces").querySelector(`[data-space="${s.id}"]`);
  save.onclick = async () => {
    const usesProxy = !!type.value, usesAgent = !!agent.value.trim();
    // (A proxy needs both: isolation.js, notPastProxy.)
    const wanted = [...(usesProxy ? ["proxy"] : []), ...(usesProxy || usesAgent ? ["webRequest", "webRequestBlocking"] : [])];
    const asked = { permissions: wanted, origins: ["*://*/*"] };
    if (wanted.length && !await mayAsk(asked) && !await browser.permissions.contains(asked)) {
      spaceFacts.set(s.id, "Firefox did not give Tidier the permission for this, so nothing changed.");
      return drawSpaces(true);
    }
    const stored = await isolation("network", { id: s.id, proxy: usesProxy ? { type: type.value, host: host.value, port: port.value } : null, userAgent: agent.value });
    if (usesProxy && !stored.proxy) {
      // Kept as typed, to be put right, with what is missing said under it.
      unsavedNetwork.set(s.id, { type: type.value, host: host.value, port: port.value, agent: agent.value, problem: "Not saved: a proxy needs a host, without http://, and a port from 1 to 65535. Until then there is none." });
      spaceFacts.delete(s.id);
    } else {
      unsavedNetwork.delete(s.id);
      spaceFacts.set(s.id, "Saved.");
    }
    drawSpaces(true);
  };
  return [
    spaceField("Proxy", el("div", { className: "line tight proxy-line" }, type, host, port), proxyProblem),
    spaceField("User agent", el("div", { className: "line tight" }, agent)),
    spaceField("", save),
  ];
}

// A question asked in place takes the keyboard to its safe answer, Keep.
const keepFocused = async id => { await drawSpaces(true); $("spaces").querySelector(`[data-space="${id}"] .keep`)?.focus(); };

function questionPart(s, kind, sentence, yes, act) {
  if (asking.get(s.id) !== kind) return null;
  const go = el("button", { className: "danger", textContent: yes });
  const keep = el("button", { textContent: "Keep", className: "keep" });
  keep.onclick = () => { asking.delete(s.id); drawSpaces(true); };
  go.onclick = act;
  return [el("p", { className: "question", textContent: sentence }), el("div", { className: "line tight" }, go, keep)];
}

function signOutPart(s) {
  const question = questionPart(s, "signOut", `Sign out of every site in ${s.name}? Its cookies and what sites keep in it go, for good.`, "Sign out", async () => {
    await mayAsk({ permissions: ["browsingData"] });
    if (!await browser.permissions.contains({ permissions: ["browsingData"] })) spaceFacts.set(s.id, "Firefox did not give Tidier the permission for this, so nothing changed.");
    else {
      await isolation("signOut", { id: s.id });
      spaceFacts.set(s.id, `Signed out of everything in ${s.name}. Pages that are open show it when they next load.`);
    }
    asking.delete(s.id);
    drawSpaces(true);
  });
  if (question) return question;
  const b = el("button", { textContent: "Sign out of everything in this space", className: "sign-out" });
  b.onclick = () => { asking.set(s.id, "signOut"); spaceFacts.delete(s.id); keepFocused(s.id); };
  return [b];
}

const spaceCount = (n, one, many) => (n === 1 ? `1 ${one}` : `${n} ${many}`);
// Everything that goes with a space, its rules too, as one sentence that starts with a capital.
function whatGoesWithSpace({ essentials, folders, tabs }, rules) {
  const parts = [...(essentials ? [spaceCount(essentials, "essential", "essentials")] : []), ...(folders ? [spaceCount(folders, "folder", "folders")] : []), ...(tabs ? [spaceCount(tabs, "tab", "tabs")] : []),
    ...(rules ? [spaceCount(rules, "rule", "rules")] : []), "all its logins"];
  const list = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}` : parts[0];
  return list[0].toUpperCase() + list.slice(1);
}

function deletePart(s) {
  const n = s.contents;
  const keeps = n.essentials || n.folders ? " A copy of its essentials and folders is kept first." : "";
  const rules = state.rules.filter(r => r.space === s.id).length;
  const question = questionPart(s, "delete", `Delete ${s.name}? ${whatGoesWithSpace(n, rules)} go.${keeps}`, "Delete", async () => {
    const r = await isolation("delete", { id: s.id });
    asking.delete(s.id);
    if (r?.refused) spaceFacts.set(s.id, `${s.name} stays. ${r.refused}`);
    else { moreOpen.delete(s.id); spaceFacts.delete(s.id); }
    await refresh();
    drawSpaces(true);
  });
  if (question) return question;
  const b = el("button", { textContent: "Delete this space", className: "quiet delete" });
  b.onclick = () => { asking.set(s.id, "delete"); spaceFacts.delete(s.id); keepFocused(s.id); };
  return [b];
}

addEventListener("DOMContentLoaded", () => {
  // Made at once, with a colour and icon no other space has, and its name ready to change.
  $("new-space").onclick = async () => {
    const id = await isolation("new");
    moreOpen.add(id);
    await drawSpaces(true);
    const name = document.querySelector(`[data-name-of="${id}"]`);
    name?.focus();
    name?.select();
  };
  $("allow-isolation").onclick = () => mayAsk({ permissions: ["webRequest", "webRequestBlocking"], origins: ["*://*/*"] }).then(() => drawSpaces(true));
});
