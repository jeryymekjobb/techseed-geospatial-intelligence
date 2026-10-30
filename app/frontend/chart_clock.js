// The playback clock's line in the panel's time charts (panel.js) can be dragged: left back,
// right forward. A chart spans the playback over its viewBox's width, so a point in it is a time.
// Pure, so it can be tested in Node.
"use strict";

// The time at x of a chart `width` wide that spans the playback from startMs to endMs, kept
// within the playback.
function chartTimeAt(x, width, startMs, endMs) {
  const share = Math.min(Math.max(x / width, 0), 1);
  return new Date(startMs + Math.round(share * (endMs - startMs)));
}

if (typeof module !== "undefined") module.exports = { chartTimeAt };
