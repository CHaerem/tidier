// Every tab at once: the desk's page (desk.js in the background has what it shows and does
// what it is asked). Text is only ever set with textContent, so a page title cannot add
// anything here.

const field = document.getElementById("field"), list = document.getElementById("spaces");
const send = msg => browser.runtime.sendMessage(msg);
let cards = []; // { card, element }, in reading order, the hidden ones too
let selected = -1;

const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};
const letterOf = title => String(title ?? "").match(/[\p{L}\p{N}]/u)?.[0] ?? "·";
function iconOf(card, cls = "") {
  const letter = () => el("span", "letter " + cls, letterOf(card.title));
  if (!card.icon || !/^(https?:|data:|moz-extension:)/.test(card.icon)) return letter();
  const img = el("img", cls);
  img.src = card.icon;
  img.alt = "";
  img.onerror = () => img.replaceWith(letter());
  return img;
}
const plain = text => String(text ?? "").toLowerCase().normalize("NFKD").replace(/\p{M}/gu, "");

// An essential: a tile, as in the sidebar; no picture, since it is always the same page.
function tileOf(card) {
  const e = el("div", "tile" + (card.loaded ? "" : " unloaded"));
  e.setAttribute("role", "option");
  e.append(iconOf(card), el("span", "text", card.title));
  e.title = card.title;
  e.onclick = () => go(card);
  e.onmousemove = () => select(cards.findIndex(c => c.card === card));
  return e;
}

function cardOf(card) {
  const e = el("div", "card" + (card.loaded ? "" : " unloaded"));
  e.setAttribute("role", "option");
  const picture = el("div", "picture");
  picture.append(iconOf(card, "big"));
  const title = el("div", "title");
  title.append(iconOf(card), el("span", "text", card.title));
  e.append(picture, title);
  if (card.folder) e.append(el("div", "where", card.folder));
  const close = el("button", "close");
  close.title = "Close";
  close.onclick = ev => { ev.stopPropagation(); send({ type: "desk:close", tabId: card.id }); e.remove(); cards = cards.filter(c => c.card !== card); countAll(); };
  e.append(close);
  e.onclick = () => go(card);
  e.onmousemove = () => select(cards.findIndex(c => c.card === card));
  return e;
}

function draw(view) {
  const here = view.spaces.find(s => s.id === view.space), root = document.documentElement.style;
  if (here?.color) root.setProperty("--accent", here.color);
  if (here?.tint) root.setProperty("--frame", `light-dark(${here.tint.light}, ${here.tint.dark})`);
  if (view.space) document.documentElement.dataset.space = view.space;
  list.replaceChildren(...view.spaces.map(space => {
    const section = el("section", "space");
    section.dataset.space = space.id;
    const h = el("h2");
    const dot = el("span", "dot");
    dot.style.setProperty("--color", space.color);
    const name = el("span", "name", space.name);
    name.title = `Go to ${space.name}`;
    name.onclick = () => send({ type: "desk:space", space: space.id });
    h.append(dot, name, el("span", "count"));
    const tiles = el("div", "tiles"), grid = el("div", "cards");
    for (const card of space.cards) {
      const element = card.essential ? tileOf(card) : cardOf(card);
      cards.push({ card, element, space: section });
      (card.essential ? tiles : grid).append(element);
    }
    section.append(h, ...(tiles.children.length ? [tiles] : []), grid);
    if (!space.cards.length) section.append(el("div", "empty", "No tabs"));
    return section;
  }));
  countAll();
  requestAnimationFrame(() => { for (const t of list.querySelectorAll(".tile .text")) t.classList.toggle("long", t.scrollWidth > t.clientWidth); });
  select(Math.max(0, cards.findIndex(c => c.card.id === view.from)));
  if (view.pictures) pictures();
}

// How many a space has, or how many of them match what you typed.
function countAll() {
  for (const section of list.children) {
    const all = cards.filter(c => c.space === section), shown = all.filter(c => !c.element.hidden);
    section.querySelector(".count").textContent = field.value.trim() ? `${shown.length} of ${all.length}` : `${all.length} tab${all.length === 1 ? "" : "s"}`;
    section.hidden = !!field.value.trim() && !shown.length;
  }
}

// The pictures, those in sight first, one at a time: each is a moment's work for Firefox.
async function pictures() {
  const inSight = c => { const r = c.element.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight; };
  const order = [...cards.filter(inSight), ...cards.filter(c => !inSight(c))].filter(c => !c.card.essential && (c.card.loaded || c.card.url));
  for (const c of order) {
    if (!c.element.isConnected) continue;
    const shot = await send({ type: "desk:picture", tabId: c.card.id }).catch(() => null);
    if (!shot) continue;
    const img = el("img", "page");
    img.src = shot;
    img.alt = "";
    c.element.querySelector(".picture").replaceChildren(img);
  }
}

function select(i) {
  if (i === selected || !cards[i]) return;
  cards[selected]?.element.classList.remove("selected");
  selected = i;
  cards[i].element.classList.add("selected");
}
const shown = () => cards.map((c, i) => i).filter(i => !cards[i].element.hidden);
function step(by) {
  const order = shown();
  if (!order.length) return;
  const at = order.indexOf(selected);
  select(order[Math.min(order.length - 1, Math.max(0, at < 0 ? 0 : at + by))]);
  cards[selected].element.scrollIntoView({ block: "nearest" });
}
// Up and down: the card above or below, by where it stands.
function stepRows(down) {
  const from = cards[selected]?.element.getBoundingClientRect();
  if (!from) return step(down ? 1 : -1);
  const others = shown().map(i => ({ i, r: cards[i].element.getBoundingClientRect() })).filter(({ r }) => (down ? r.top > from.bottom - 2 : r.bottom < from.top + 2));
  if (!others.length) return;
  const rowTop = down ? Math.min(...others.map(o => o.r.top)) : Math.max(...others.map(o => o.r.top));
  const row = others.filter(o => Math.abs(o.r.top - rowTop) < 4);
  const best = row.reduce((a, b) => (Math.abs(b.r.left - from.left) < Math.abs(a.r.left - from.left) ? b : a));
  select(best.i);
  cards[selected].element.scrollIntoView({ block: "nearest" });
}

function filter() {
  const words = plain(field.value).split(/\s+/).filter(Boolean);
  for (const c of cards) {
    const text = plain(`${c.card.title} ${c.card.url ?? ""} ${c.card.folder ?? ""}`);
    c.element.hidden = !words.every(w => text.includes(w));
  }
  countAll();
  if (cards[selected]?.element.hidden || words.length) select(shown()[0] ?? -1);
}

const go = card => send({ type: "desk:go", tabId: card.id });

field.addEventListener("input", filter);
addEventListener("keydown", e => {
  if (e.isComposing) return;
  switch (e.key) {
    case "ArrowRight": step(1); break;
    case "ArrowLeft": step(-1); break;
    case "ArrowDown": stepRows(true); break;
    case "ArrowUp": stepRows(false); break;
    case "Enter": if (cards[selected] && !cards[selected].element.hidden) go(cards[selected].card); break;
    case "Escape": if (field.value) { field.value = ""; filter(); } else send({ type: "desk:back" }); break;
    default: return;
  }
  e.preventDefault();
}, true);
// Typing anywhere on the desk goes into the field.
addEventListener("focus", () => field.focus());

send({ type: "desk:view" }).then(draw);
