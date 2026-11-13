// Reads a sideways swipe on the trackpad out of the wheel events it becomes, for
// switching space as in Zen and Arc (swipe.js draws it). No page, no timers, no Firefox:
// what to do comes back from each call, so all of it can be tested as it is.
//
// Firefox tells a page nothing of the fingers themselves: not when they come down or
// lift, and not which events are the trackpad's own gliding on after they have left. All
// there is to go on is each event's size, direction and time. So the numbers below are
// what the feel of it rests on, and they are set by reasoning, in a test Firefox that has
// no trackpad: they are the first thing to try with real fingers (PLAN.md, part C).
//
// Scrolling the list must never switch space. That was tried with Sidebery and left out
// for it: there a sideways sum over a limit switched, so a scroll that drifted, or the
// hook at the end of one, did too. Here a movement is one thing from its first event to
// the pause after it (a stream), and what it is gets decided once, from its first few
// pixels: clearly sideways, or a scroll. A scroll stays a scroll until the pause, however
// far it drifts sideways after that, and what is neither clearly one nor the other is a
// scroll.
//
// A swipe then follows the fingers. It ends in one of three ways: a quick flick goes to
// the next space at once; a pause (the fingers lifted, or resting: the two cannot be told
// apart) goes there if the list has come far enough, else back; and at the first or last
// space the list gives a little and comes back.
//
// One top-level name, as the sidebar's scripts share a scope.
function swipeTracker() {
  // No event for this long: the movement is over. Shorter, and fingers that only slow down
  // for a moment let go of the list; longer, and the list waits that long, half way, after
  // fingers that left it there.
  const QUIET_MS = 150;
  const SIDEWAYS_PX = 12; // this far sideways before it is a swipe (the list has not moved yet)
  const SCROLL_PX = 5; // this far up or down, and not clearly sideways: a scroll
  const CLEARLY = 2; // sideways means at least twice as far sideways as up or down
  const FLICK = 0.7; // px a ms: faster than this is a flick, which goes there at once
  const FLICK_PX = 16; // but not before the list has followed this far
  const SPEED_MS = 60, FRAME_MS = 16; // the speed is that of the last few events
  const FAR = 0.4; // of the width: let go beyond this, it goes there
  const COAST_MS = 120; // let go while moving, it counts as this much further on its way
  const ONE_SIDE_PX = 30; // this far to one side, and the movement cannot end on the other
  const GIVE = 120; // where there is no space to go to, the list gives at most this much
  const STILL_PX = 60; // with less motion asked for nothing follows: this far, and it switches
  const AGAIN_MS = 200; // after a flick, nothing is a new swipe for this long
  const CALM_PX = 2, RISE_PX = 3; // fingers that come back start from next to nothing, and grow by at least this

  let stream = null; // { axis: null | "scroll" | "swipe" | "over", x, y, last, side, overAt, sizes }
  let offset = 0; // how far the fingers have taken the list towards the next space, in px
  let moves = []; // [time, dx] of the last moments, for the speed

  const can = (dir, env) => (dir > 0 ? env.next : env.prev);
  // What is drawn for an offset: the offset itself, up to one space away; towards no space,
  // less and less of it.
  const shown = (at, env) => {
    const dir = Math.sign(at), far = Math.abs(at);
    if (!dir) return 0;
    return dir * (can(dir, env) ? Math.min(far, env.width) : (far * GIVE * 0.55) / (GIVE + 0.55 * far));
  };
  const speed = now => {
    moves = moves.filter(([t]) => now - t <= SPEED_MS);
    return moves.length ? moves.reduce((sum, [, dx]) => sum + dx, 0) / (now - moves[0][0] + FRAME_MS) : 0;
  };
  const over = now => { stream.axis = "over"; stream.overAt = now; stream.sizes = []; offset = 0; moves = []; };

  // One wheel event. Answers nothing while there is nothing to do, else one of
  //   { at, first }   the list is this far towards the next space (first: a swipe began)
  //   { go, from, speed }   go to the next (1) or previous (-1) space, from where the list is
  // (`still`: with nothing drawn, since less motion is asked for.)
  // `env`: { width, next, prev, still }: the sidebar's width, whether there is a space on
  // each side, and whether less motion is asked for.
  function wheel(dx, dy, now, env) {
    // An event of no size is the trackpad's own word that something ended (the fingers
    // left, or the gliding stopped), where Firefox passes it on: then that is known at once.
    if (!dx && !dy) return rest(env, now);
    // A swipe ends by rest(), which the page calls after the pause: its timer can be late,
    // and fingers that have gone on meanwhile are still the same swipe.
    if (stream && stream.axis !== "swipe" && now - stream.last >= QUIET_MS) stream = null;
    if (stream?.axis === "over" && newFingers(dx, dy, now)) stream = null;
    if (!stream) { stream = { axis: null, x: 0, y: 0, last: now, side: 0 }; offset = 0; moves = []; }
    stream.last = now;
    if (stream.axis === "scroll" || stream.axis === "over") return null;

    if (stream.axis === null) {
      stream.x += dx;
      stream.y += dy;
      const x = Math.abs(stream.x), y = Math.abs(stream.y);
      if (y >= SCROLL_PX && x < CLEARLY * y) { stream.axis = "scroll"; return null; }
      if (x < SIDEWAYS_PX || x < CLEARLY * y) return null;
      // From here, not from where the fingers came down: the list starts where it lies.
      stream.axis = "swipe";
      return env.still ? null : { at: 0, first: true };
    }

    moves.push([now, dx]);
    offset += dx;
    if (!stream.side && Math.abs(offset) >= ONE_SIDE_PX) stream.side = Math.sign(offset);
    // Flicked back, it comes back, and does not go on to the space on the other side.
    if (stream.side && Math.sign(offset) === -stream.side) offset = 0;
    offset = Math.max(-env.width, Math.min(env.width, offset));
    const dir = Math.sign(offset);
    if (env.still) {
      if (Math.abs(offset) < STILL_PX || !can(dir, env)) return null;
      over(now);
      return { go: dir, still: true };
    }
    const v = speed(now);
    if (dir && Math.sign(v) === dir && Math.abs(v) >= FLICK && Math.abs(offset) >= FLICK_PX && can(dir, env)) {
      const from = shown(offset, env);
      over(now);
      return { go: dir, from, speed: Math.abs(v) };
    }
    return { at: shown(offset, env) };
  }

  // After a flick the trackpad glides on for a second or so, and the fingers may already
  // be back for the next swipe before it has stopped: its events then come with no pause
  // between. Gliding only ever slows down, and fingers that come down stop it and start
  // from next to nothing, so an event that grows out of almost none is the fingers again.
  // (Not right after the flick, while they may still be on their way; and not from any
  // size: fingers that simply go on across the trackpad come with events of uneven size,
  // two at once at times, and one long swipe must not be two.)
  function newFingers(dx, dy, now) {
    const size = Math.abs(dx) + Math.abs(dy), least = Math.min(...stream.sizes);
    stream.sizes = [...stream.sizes.slice(-2), size];
    return now - stream.overAt >= AGAIN_MS && least <= CALM_PX && size >= least + RISE_PX;
  }

  // No event for QUIET_MS during a swipe (the page keeps the time, while swiping()): where
  // the list is decides. Answers
  //   { go, from, speed }   or   { back: true, from }
  // `now`: it is known that the fingers left, and when. Then the speed they left at counts
  // too, and what the trackpad glides on with is not another swipe.
  const swiping = () => stream?.axis === "swipe";
  function rest(env, now) {
    if (!swiping()) return null;
    const v = now === undefined ? 0 : speed(now);
    const from = shown(offset, env), ahead = offset + v * COAST_MS, dir = Math.sign(offset);
    const goes = dir && Math.sign(ahead) === dir && can(dir, env) && Math.abs(ahead) >= FAR * env.width;
    if (now === undefined) { stream = null; offset = 0; moves = []; } else over(now);
    if (env.still) return null;
    return goes ? { go: dir, from, speed: Math.abs(v) } : { back: true, from };
  }

  // The swipe that just began (`first`) goes on from here: the list was on its way back
  // from an earlier one, and is taken where it is.
  const from = at => { if (stream?.axis === "swipe") offset = at; };
  // Or it is not to be one: nothing more of this movement counts.
  const ignore = now => { if (stream) over(now); };

  return { wheel, rest, swiping, from, ignore, QUIET_MS };
}
