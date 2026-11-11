// --- The icons to choose from, for a space ----------------------------------------------
// A space's icon is an emoji (spacemenu.js). The system has a list of them, but where it is
// kept is not something everybody knows (on a Mac: fn E), and it does not open from a menu.
// So the space's menu has its own: a field to search in and the ones found, drawn in the
// menu's place as any list in it is (menu.js).
//
// A few hundred, each with the English words it is found by; what a space is often for
// comes first. Any other emoji can be typed or pasted in the field, the system's list
// included, and is then the first one found.
//
// One per line: the emoji, then its words. (A sign that is text by itself, as ✈, is made a
// picture when the list is read: emojiList.)
const EMOJI = `
🏠 home house
💼 work briefcase job office
⚡ lightning zap electricity power energy bolt
🧪 test lab experiment science
🛠 tools build fix repair
📚 books study read library school
🎵 music note song
🎮 game play controller
💬 chat talk message speech
🛒 shopping cart buy store
✈ travel plane flight trip
💰 money bank finance
🌱 plant grow seedling garden green
👤 person me private personal
👥 people team group
🏢 office building company
🎓 school study university graduate education
❤ heart love favourite red
⭐ star favourite
🔒 lock private secret secure
🔑 key password access
🏦 bank money
📰 news paper read
🎬 film movie video cinema
📷 camera photo picture
🎨 art design paint palette
🧠 brain think idea mind ai
💡 idea light bulb
🚀 rocket launch ship start
🔥 fire hot flame
🎯 target goal focus dart
🧘 calm yoga meditate relax
🏃 run sport exercise
⚽ football soccer sport ball
🏋 gym weights training sport
🚲 bike bicycle cycle
🍳 food cook kitchen egg
☕ coffee cafe break
🍺 beer drink pub
🎉 party celebrate fun
🎁 gift present
🏥 health hospital doctor
💊 health medicine pill
👶 baby child family kid
🐶 dog pet
🐱 cat pet
💻 computer laptop code
🖥 computer desktop screen monitor
⌨ keyboard type
📱 phone mobile
🧑‍💻 developer coder programmer technologist
🤖 robot bot ai agent
🧩 puzzle piece extension plugin
⚙ settings gear cog config
🔧 wrench tool fix
🔨 hammer build tool
🧰 toolbox tools
🔬 microscope research science
🔭 telescope look space astronomy
📡 antenna satellite signal network
🔌 plug power electric
🔋 battery power energy
💾 save disk floppy
🗄 archive cabinet files storage
🗂 folders files index
📁 folder files
📦 box package parcel ship
📊 chart bar graph statistics data
📈 chart up growth graph trend
📉 chart down graph trend
📋 clipboard list tasks
📌 pin pinned
📎 clip attach paperclip
✏ pencil write edit
📝 note write memo
📅 calendar date plan
⏰ alarm clock time
⏱ stopwatch timer time
📧 mail email letter
📮 post mail box
📞 phone call
🔔 bell notify alert
🔍 search find look magnifier
🔗 link chain url
🏷 tag label
🧾 receipt bill invoice
💳 card pay credit
🛡 shield security protect safe
🐞 bug ladybug error
🧱 brick wall build
🏗 construction build crane
🏭 factory industry plant
⚖ law scales justice legal balance
🩺 doctor health stethoscope
🧮 abacus count math
🎙 microphone podcast record
🎧 headphones music listen
📺 tv television video
📻 radio
🎥 camera film video record
🖼 picture image frame art
🖊 pen write
🗺 map world
🧭 compass navigate direction
🌐 web globe internet world
☁ cloud
🗞 newspaper news
📖 book read open
🔖 bookmark
🗑 trash bin delete
♻ recycle
☀ sun sunny day
🌙 moon night
🌈 rainbow
❄ snow cold winter ice
🌊 wave sea ocean water
💧 water drop
🌍 earth world globe europe
🌲 tree forest pine
🌳 tree
🌸 flower blossom spring
🌻 sunflower flower
🍀 clover luck
🍂 autumn leaf fall
⛰ mountain
🏔 mountain snow
🏖 beach holiday sun
🏝 island holiday
🌋 volcano
⛈ storm thunder rain
🌧 rain
🌪 tornado wind
🦊 fox firefox
🐻 bear
🐼 panda
🦁 lion
🐯 tiger
🐸 frog
🐵 monkey
🐧 penguin linux
🐦 bird
🦉 owl
🦅 eagle
🐝 bee
🦋 butterfly
🐢 turtle slow
🐙 octopus
🐬 dolphin
🐳 whale docker
🦈 shark
🐟 fish
🐍 snake python
🦀 crab rust
🐘 elephant
🦄 unicorn
🐴 horse
🐮 cow
🐷 pig
🐑 sheep
🐰 rabbit
🐭 mouse
🦇 bat
🐺 wolf
🦌 deer
🍎 apple fruit
🍋 lemon fruit
🍓 strawberry berry fruit
🍌 banana fruit
🍇 grapes fruit wine
🥑 avocado
🥕 carrot vegetable
🌶 chili pepper hot spicy
🍞 bread bake
🧀 cheese
🍕 pizza
🍔 burger hamburger
🌮 taco
🍣 sushi
🍜 noodles ramen soup
🍰 cake dessert
🍪 cookie biscuit
🍫 chocolate
🍿 popcorn film
🍷 wine drink
🍵 tea drink
🥤 drink soda
🍽 dinner plate restaurant eat
🚗 car drive
🚕 taxi
🚌 bus
🚆 train rail
🚇 metro subway underground
🚢 ship boat ferry
⛵ sail boat
🚁 helicopter
🛰 satellite space
🛸 ufo
⛽ fuel petrol gas
🚦 traffic light
🏡 house garden home
🏰 castle
🏛 government museum classical
⛪ church
🏨 hotel
🏪 shop store
🏫 school
⛺ tent camp
🗽 liberty new york
🗼 tower tokyo
🌃 night city
🌆 city evening
🏀 basketball
🎾 tennis
🏐 volleyball
🏈 football american
⛳ golf
🎿 ski winter
🏂 snowboard
🏊 swim
🚴 cycling bike
🧗 climb
🎣 fishing fish
🎲 dice game chance
♟ chess game strategy
🎸 guitar music
🎹 piano keys music
🥁 drum music
🎤 sing karaoke microphone
🎭 theatre drama
🎪 circus tent
🎟 ticket
🏆 trophy win prize
🥇 medal gold first
🧵 thread sew
🧶 yarn knit
📸 photo camera flash
🕹 joystick game arcade
😀 smile happy face
😎 cool sunglasses
🤓 nerd glasses
🤔 think thinking
😴 sleep tired
🥳 party celebrate
😈 devil evil
👻 ghost
💀 skull dead
👽 alien
👑 crown king queen
👀 eyes look watch
👋 wave hello
👍 thumbs up good yes
🙏 thanks pray please
💪 strong muscle
🤝 handshake deal agree
✌ peace victory
✅ check done yes
❌ cross no wrong
⚠ warning caution
❓ question
❗ exclamation important
💯 hundred perfect
✨ sparkles new magic
💎 diamond gem
🔴 red circle
🟠 orange circle
🟡 yellow circle
🟢 green circle
🔵 blue circle
🟣 purple circle
⚫ black circle
⚪ white circle
🟥 red square
🟦 blue square
🟩 green square
🔶 orange diamond
🔷 blue diamond
♾ infinity forever
➕ plus add
🏁 finish flag race
🚩 flag red
🇳🇴 norway flag norge
🇸🇪 sweden flag sverige
🇩🇰 denmark flag danmark
🇫🇮 finland flag
🇮🇸 iceland flag
🇪🇺 europe eu flag
🇬🇧 britain uk flag england
🇺🇸 usa america flag
🇩🇪 germany flag
🇫🇷 france flag
`;

// Read when the list is first asked for, not when the sidebar loads: most days nobody
// changes an icon. A sign that Firefox would draw as text by itself (✈, ⚙, ☁) gets the mark
// that makes it a picture, which is also what makes it an icon to spaceIcon.
let emojiRead = null;
function emojiList() {
  emojiRead ??= EMOJI.trim().split("\n").map(line => {
    const [sign, ...words] = line.split(" ");
    const icon = /^(\p{Emoji_Presentation}|\p{Regional_Indicator})/u.test(sign) || sign.includes("️") ? sign : sign + "️";
    return { icon, name: words[0], words };
  });
  return emojiRead;
}

// The ones found by what is typed: every word typed starts one of an emoji's words, a whole
// word before the start of one ("fire": 🔥 before the fox of Firefox). An emoji typed or
// pasted is itself the first one found, in the list or not. Nothing typed: all of them.
function emojiSearch(text) {
  const typed = spaceIcon(text.trim()).icon; // spacemenu.js
  const asked = text.toLowerCase().split(/\s+/).filter(Boolean);
  const found = emojiList().filter(e => asked.every(a => e.words.some(w => w.startsWith(a))));
  const whole = e => asked.some(a => e.words.includes(a));
  const sorted = asked.length ? [...found.filter(whole), ...found.filter(e => !whole(e))] : found;
  return typed ? [{ icon: typed, name: "" }, ...sorted.filter(e => e.icon !== typed)] : sorted;
}

// The field and what is found, as one part of the menu (drawMenu, menu.js). The keyboard
// stays in the field, as in the system's own list: typing searches, Enter takes the marked
// one (the first found, once something is typed), ↓ and ↑ move the mark by a row, and after
// them ← and → by one; before them ← and → are the field's own.
function emojiPicker(space) {
  const box = el("div", "picker"), field = el("input", "find"), grid = el("div", "found");
  field.placeholder = "Search, or type an emoji";
  field.setAttribute("aria-label", "Search for an icon, or type an emoji");
  field.spellcheck = false;
  grid.setAttribute("role", "listbox");
  let at = -1, moved = false;
  const signs = () => [...grid.querySelectorAll(".emoji")];
  const mark = i => {
    const all = signs();
    all[at]?.classList.remove("at");
    at = i;
    all[at]?.classList.add("at");
    all[at]?.scrollIntoView({ block: "nearest" });
  };
  const draw = () => {
    const found = emojiSearch(field.value);
    grid.replaceChildren(...found.map(({ icon, name }) => {
      const b = el("button", "emoji", icon);
      b.tabIndex = -1; // the keyboard is the field's
      b.setAttribute("role", "option");
      if (name) b.title = name;
      b.onclick = secondClick.acts(() => { closeMenu(); setSpaceIcon(space, icon); });
      return b;
    }));
    if (!found.length) grid.append(el("div", "none", "No emoji by that name"));
    grid.scrollTop = 0;
    at = -1;
    moved = false;
    // Enter takes the first one found, so it is marked; with nothing typed, Enter takes none.
    if (field.value.trim() && found.length) mark(0);
  };
  field.oninput = draw;
  field.onkeydown = e => {
    const all = signs();
    const row = all.filter(b => b.offsetTop === all[0].offsetTop).length || 1;
    const step = { ArrowDown: row, ArrowUp: -row, ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (e.key === "Enter") all[at]?.click();
    else if (step === row || step === -row) {
      // Past the last row: on to the menu's own items below (No icon), as its keys go.
      if (at >= 0 && at + step >= all.length && Math.floor(at / row) === Math.floor((all.length - 1) / row)) return;
      moved = true;
      mark(Math.max(0, Math.min(all.length - 1, at < 0 ? 0 : at + step < 0 ? at : at + step)));
    } else if (step) {
      // With nothing typed and no mark, ← is the menu's: back, as in its other lists.
      if (!moved) { if (step > 0 || field.value) e.stopPropagation(); return; }
      mark(Math.max(0, Math.min(all.length - 1, at + step)));
    } else return;
    e.preventDefault();
    e.stopPropagation();
  };
  draw();
  box.append(field, grid);
  return box;
}
