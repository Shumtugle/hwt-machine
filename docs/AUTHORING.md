# Writing a watch face as a description

This guide is for anyone, person or language model, who wants a watch face without
writing drawing code. You write a JSON description; the machine draws, packs and checks
it; if something is wrong it says where and what to change. Repeat until it builds.

```sh
python3 tools/build.py my-face/face.json --check    # read and report, write nothing
python3 tools/build.py my-face/face.json            # packages and previews into dist/
```

The build writes one `.hwt` per language, one carrying all languages as choices in the
watch's face editor, and a PNG of the normal and the always-on screen for each. Look at
the PNGs before calling a face finished.

Four complete descriptions ship with the repository and are the best reference:
`faces/vibe/face.json` (cards, tiles, a mark running around the frame),
`faces/plumb/face.json` (bare type, a mark sliding down a thread) and
`faces/duo/face.json` (hands on a small dial, crystal digits, a hanging date) and
`faces/kide/face.json` (the same instruments with a lit amber crystal window, a date
built outwards from the middle, readings at the corners). Both build into the
exact pixels of the hand-written faces they replace, except where the checks below
found a fault in the original (Vibe's always-on words are a size smaller, so the
descenders of one line clear the next).

## What the machine does for you

Write positions and styles; leave the format to the machine. It always:

- stores fully transparent pixels as `00000000` (anything else bloats the file);
- renders digits into cells of one width, so values never jitter;
- places text by its visible ink, so "the top of the capitals at y = 58" means exactly that;
- lays the description out once per language and turns only what differs into editor
  choices, each under its own function code (the editor folds choices that share one);
- builds the running second mark from the only two sources the watch offers, the tens
  and the units of the second;
- refuses tap targets that do nothing and anything placed off the screen;
- looks at the result: elements that collide, anything under the second mark's path,
  text that cannot be seen against what is under it, ink in the rounded corners.

## The screen

408 × 480 pixels, origin at the top left, y grows downwards. The screen code is
`HWHD13`; it is the default and the only one supported.

**The visible area is smaller than the picture.** The glass is rounded and the bezel
covers the corners. Everything that must be seen goes inside a rounded rectangle
**11 px in from every edge with corners of radius 82**, that is `[11, 11, 397, 469]`.
A line drawn exactly there shows whole on the watch; the same line drawn at 3 px with
corners of radius 64 loses its corners. In the corners the boundary is a quarter
circle around `(93, 93)`, `(315, 93)`, `(93, 387)` and `(315, 387)`: near the
bottom corners a row of readings at y ≈ 435 may start no further left than x ≈ 27.
Backgrounds (fills, glows, pictures) may run to the edge; they simply get cropped.

Along the straight edges the screen shows to within 3 px of the glass; only the
corners are lost.

The build warns about any ink in the corners, element by element, for background
layers that draw (cards, ticks, shapes, dials) and for the path of a second mark.

**Text must be read on a wrist.** Measured there: capitals or digits 21 px tall (Oswald
size 25) are the smallest read without strain, 26 px (size 32) read in comfort, and the
light weight (300) reads well from size 28. The build warns below 21 px, and below
26 px for anything not marked `"quiet": true`. Date and time are never quiet.

## Top level

```json
{
  "name": "Ember",
  "notes": "free text, ignored by the build",
  "font": "Oswald",
  "colors": {"ink": "#F2E3C6", "accent": "#FF283C"},
  "styles": {"label": {"size": 26, "weight": 400, "color": "ink"}},
  "languages": {"default": ["ru", "en", "fi"], "zone": [118, 30, 372, 118],
                "frame": {"color": "accent", "radius": 12}},
  "locales": {"sv": {"weekdays": ["..."], "months": ["..."]}},
  "ring": {"inset": 3, "radius": 64},
  "background": [],
  "elements": [],
  "aod": {"background": [], "elements": []}
}
```

| field | meaning |
|---|---|
| `name` | title shown on the watch; required |
| `author` | optional; defaults to the name in lower case |
| `font` | default font: `Oswald` (condensed sans, weights 200–700), `Cormorant` (serif, 300–700), or `Segments` (drawn seven-segment digits, for numbers and the time only) |
| `colors` | palette; elements may name these instead of writing colours |
| `styles` | named text styles; an element takes one with `"style": "label"` and may override any field |
| `languages.default` | languages built when none are given on the command line; at most 3 |
| `languages.zone` | `[left, top, right, bottom]` of the editor's choice area; default: around what differs |
| `languages.frame` | the editor's highlight around that area: `color`, `radius`, `width` |
| `locales` | word tables for languages not built in, or to replace built-in words |
| `ring` | the rounded rectangle of 60 stations along the screen edge used by `ticks` and the second mark |
| `background` | layers drawn once into the background picture, in order |
| `elements` | everything on the normal screen |
| `aod` | the always-on screen: drawn on black, in the first language, never with seconds |

Colours are `"#RRGGBB"`, `"#RRGGBBAA"`, `[r, g, b]`, `[r, g, b, a]` or a palette name.

Built-in languages: `ru`, `en`, `fi`. Each has weekdays (`full`, `short`), months in the
form used after a day number (`full`: "9 November", "9. marraskuuta"), on their own
(`standalone`) and `short`, and the suffix after the day number (Finnish: `.`).

## Positions

Every element has `x`, `y` and usually `align`.

**x** is a number or a reference, and `align` says which side of the element it marks:
`left` (default), `center` or `right`.

**y** is either a number (the top of the element's picture) or an object naming one line
to put on a value:

| line | for | meaning |
|---|---|---|
| `top`, `middle`, `bottom` | anything | edges of the picture |
| `digits_top`, `digits_middle`, `digits_bottom` | text | visible ink of the digits |
| `caps_top`, `caps_middle`, `caps_bottom` | text | visible ink of the capitals |

```json
"y": {"digits_middle": 216}
"y": {"caps_top": "day.digits_top"}
```

**References** point at another element by its `id`: `"day.right+12"`,
`"time.digits_bottom-4"`, `"parent.middle"`. Terms join with `+` and `-`. `screen.*` is
the screen (`center` is 204, `middle` 240), `parent.*` the tap zone around the element.
Elements may refer forwards; a circle of references is an error.

Any element may carry `"quiet": true`: it is meant to recede, so low contrast is not
reported as a warning (it is still an error when it cannot be seen at all).

Edges every element offers: `left`, `right`, `center`, `top`, `bottom`, `middle`,
`width`, `height`. Text adds `digits_top`, `digits_bottom`, `digits_middle`,
`caps_top`, `caps_bottom`, `caps_middle`. The box of a number is its widest value with
its unit, so `right` does not move when the value does.

## Text style fields

`font`, `size` (pixels, required), `weight` (Oswald 200–700, Cormorant 300–700), `color`, `tracking`
(extra pixels between letters), `features` (OpenType features such as `["lnum"]`, for
Cormorant's lining figures), `style` (a named style).

With `"font": "Segments"` the digits are drawn as on a crystal display; `size` is the
digit height and `segments` shapes them: `{"ghost": "#262626", "aspect": 0.5,
"thickness": 0.13}` — `ghost` is the colour of unlit segments (`null` for none),
`aspect` the width over the height, `thickness` the bar over the height. They draw
`0`–`9` and `-` only. `"shadow": {"color": "#6E34085F", "dx": 2, "dy": 3, "blur": 1.1}`
casts each lit segment's shadow on the reflector behind it, as on a real positive
display; a square colon casts the same shadow.

## Elements

### `time`

Hours and minutes, 24-hour, optionally seconds.

| field | default | meaning |
|---|---|---|
| style fields | | the digits |
| `layout` | `line` | `line`: HH:MM in a row; `stacked`: hour above minute, both left-aligned at `x` |
| `pad` | 2 | extra pixels per digit cell |
| `colon` | none | `{"width": 26, "radius": 5.5, "color": "accent", "spread": 0.22, "shape": "round"}`: two dots on the middle of the digits; `"shape": "square"` suits segments |
| `space` | 20 % of size | gap between hours and minutes when there is no colon |
| `line_gap` | 20 | stacked: pixels between the two lines of ink |
| `seconds` | none | `{"size": 38, "weight": 500, "color": "...", "gap": 10, "pad": 1, "quiet": false}` (or `"scale": 0.32` instead of size): after the minutes, bottoms aligned |
| `max_width` | none | shrink the size until the whole time fits this width |
| `leading_zero` | true | `false` shows a blank (or, with segments, an unlit) first digit before ten o'clock |
| `like` | | id of another time; takes its geometry and changes only what is given (see always-on) |

`x` with `align` places the whole row, seconds included. A stacked time is placed by
`digits_top`, `digits_middle` or `digits_bottom`.

### `day`

The day of the month, right-aligned in two digit cells so it never moves sideways, with
the language's suffix after it. `x` with `align: left` is the left edge of the two cells.
`right` includes the suffix, so words placed at `"day.right+12"` follow it in every
language. `"centred": true` draws the day instead as 31 ready pictures, each centred in
one cell with its suffix, so `9` sits as centred as `25.` — for a date line built
outwards from the middle. Not yet confirmed on a watch.
A day before the tenth leaves the left cell empty: a date line centred on the screen
looks slightly off-centre on those days. The watch cannot centre a number together
with a word, so left-align the date to a margin, or accept it.

### `weekday`, `month`

Words from the language tables.

| field | default | meaning |
|---|---|---|
| `form` | `full` | weekday: `full`, `short`; month: `full`, `standalone`, `short` |
| `case` | `upper` | `upper`, `lower`, `title`, `as_is` |
| `max_right` | none | shrink the size, per language, until the longest word ends before this x |
| `align` | `left` | `center` and `right` pad every word to the longest |

### `number`

A value from a sensor.

| `source` | digits kept | confirmed on a watch |
|---|---|---|
| `steps` | 5 | yes |
| `heart_rate` | 3 | yes |
| `temperature` | 2 + minus | yes |
| `battery` | 3 | yes |
| `calories` | 4 | no |
| `temperature_high`, `temperature_low` | 2 + minus | no |

A number keeps a box of as many digit cells as its largest value needs, and the digits
always right-align inside it: that is the only alignment confirmed on a watch, and the
value never moves. `x` and `align` place the box. `unit` (such as `"%"` or `"°"`) and
`gap` (pixels before it) follow the cells and stay put. `digits` overrides how many
cells to keep. A short value leaves its left cells empty, so put the number *before*
its icon (`"x": "bpm.right+5"` on the icon) and the empty cells fall between groups,
where they read as spacing.

### `text`

Static words in a style: `{"type": "text", "text": "STEPS", "size": 18, ...}`.

### `system_text`

A value the watch writes itself, in its own font: the only way to show sleep, distance,
air pressure or altitude.

| field | meaning |
|---|---|
| `source` | `sleep` (`7h23m`), `distance` (`1.94` km), `calories`, `pressure` (hPa), `altitude` (m), `emotions` (`--` while its measurement is off), `steps`, `heart_rate` |
| `x`, `y`, `align` | the box; `y` is its top |
| `width`, `height` | the box, default 120 × 31 |
| `color` | any colour |
| `text_style` | the watch's style code, default 149, the only one confirmed here: its digits are about 18 px tall, below the 21 px read in comfort, so other codes are being tried |

The font, and so the look, is the watch's; previews draw a plain sans of the same size
in its place.

### `symbol`

A static icon: `name`, `size`, `color`, `fill` (1 solid, 0 outline), `weight`.
Names: `favorite`, `footprint`, `directions_walk`, and the weather set below.

### `weather_icon`

The current weather as one of eleven icons in one box: `size`, `color`, `fill`. The
default icons, in the watch's order: `cloud_off` (unknown), `sunny`, `clear_night`,
`cloud`, `partly_cloudy_day`, `rainy`, `thunderstorm`, `weather_snowy`, `air` (wind),
`mist` (haze), `foggy`. `icons` replaces them with eleven other names.

### `battery_icon`

A cell outline filled in tenths: `color`, `low_color` (at 20 % and below), `width`
(40), `height` (22).

### `seconds_mark`

A mark that steps once a second and goes round once a minute.

| field | meaning |
|---|---|
| `path` | `"ring"` (along the screen edge, starting at the top centre) or `{"line": {"from": [x, y], "to": [x, y], "decade_gap": 26}}` |
| `layers` | balls drawn over each other: `{"radius": 4.2, "color": "...", "blur": 0}` |
| `reach` | how far the mark's light spreads; default: largest radius plus twice its blur |
| `cover_grow` | 1.5; leave it |

On a straight line give `decade_gap` more than twice the `reach`, or the mark is clipped
where one ten seconds meets the next. Keep everything else clear of the mark's path:
the layer that hides the other strips repaints the background there.

### `hands`

Hands turning about one centre, drawn pointing to 12 and turned by the watch.

| field | meaning |
|---|---|
| `centre` | `[x, y]` |
| `hour`, `minute` | required: `{"length": 38, "tail": 9, "width": 7, "color": "...", "inner": {...}}` |
| `second` | optional, same fields; not yet confirmed on a watch |
| `inner` | a darker slit along the hand: `{"color": "#000000", "inset": 2, "from": 0.3, "to": 0.86}` (fractions of the length from the centre) |
| `pin` | discs on top of the centre, largest first: `[{"radius": 6.5, "color": "..."}, ...]` |

The checks treat a hand as the whole circle it sweeps.

### `tap`

A zone that opens a screen on the watch when touched; the elements drawn in it go in
its `elements`.

| field | meaning |
|---|---|
| `box` | `[left, top, right, bottom]`; values may be references |
| `open` | confirmed: `steps`, `heart_rate`, `weather`, `settings`, `sleep`, `calories`, `emotions`, `altitude`, `pressure`, `activity` (rings), `workouts`, `alarms`, `stopwatch`, `timer`, `contacts`; not confirmed: `messages`, `music`, `recorder`. `battery` does nothing on this watch |
| `card` | optional glass card on the box: `{"radius": 18, "fill_alpha": 14, "rim_alpha": 46}` or `true` |
| `elements` | elements inside; `parent.*` refers to the box |

Nothing inside a tap may depend on the language.

## Background layers

Drawn in order onto black, once, into one picture.

| type | fields |
|---|---|
| `fill` | `color` |
| `gradient` | `top`, `bottom` colours, vertical |
| `glow` | `color`, `centre` [0.5, 0.47], `reach` [0.8, 0.66], `power` 1.5, `edge` [6, 70]: radial light that dies out before the edge |
| `card` | `box`, `radius` 22, `fill_alpha` 14, `rim_alpha` 46: a glass card |
| `ticks` | `color`, `major_color`: 60 ticks along the ring |
| `shapes` | `ss` 4 and `items`: `{"line": [[x, y], ...], "width": 1.4, "color": ...}`, `{"ellipse": [l, t, r, b], ...}`, `{"rect": [l, t, r, b], "radius": 0, ...}`, drawn on one supersampled canvas |
| `lcd` | `box`, `radius` 20, `centre` and `edge` colours of the backlight, `focus` [0.42, 0.38] where it is brightest, `reach`, `power`, `rim` 7 and `rim_alpha` 140 (shadow inside the rim), `outline` `{color, width}`: a lit crystal window for dark segment digits |
| `dial` | `box`, `radius`, `inset` 5, `frame` `{color, width}`, `minute` and `hour` ticks `{color, length, width}`, `centre` (default: the middle of the box): a rounded-rectangle dial whose radial ticks follow its outline |
| `picture` | `file`: an image next to the description, scaled to cover the screen. Photos cost size: about 780 KB each |

Cards and tick rings must not touch: a card that would is refused.

## Always-on screen

`aod.elements` take the same elements except `tap` and `seconds_mark`; `time` takes no
seconds. It is drawn in the first language only. The quickest always-on time is the
normal one, thinner and dimmer:

```json
"aod": {"elements": [{"type": "time", "like": "time", "weight": 300, "color": "#787064"}]}
```

## Languages

`python3 tools/build.py face.json --langs ru,en,fi` builds `-ru`, `-en`, `-fi` and one
face with all three. In that face the wearer picks the language in the face editor; the
editor names the choices *Date*, *Day of week* and *Sun*, after the functions it borrows.
Each choice draws exactly what the single-language face draws.

## Problems and how they are reported

Every problem is one line: where, what, and what to do. Besides mistakes in the
description itself, the machine looks at what it drew, in every language:

| check | level |
|---|---|
| two elements share more than a few pixels of ink (every value, every word counted) | error |
| an element sits on the path of the second mark | error |
| contrast below 1.5:1 against the background under the element | error |
| contrast below 3:1 (not for `quiet` elements, nor for the colon) | warning |
| ink in the rounded corners | warning |
| ink of a tap zone's element outside the zone | warning |

A problem that occurs in only some languages names them: `elements[3] (fi): ...`.

```
error: elements[3].x: no element with id "dya" (did you mean "day"?)
error: elements[1].colour: "time" has no field "colour" (did you mean "color"?); it takes ...
error: elements[4]: "weekday" spans [380, 58, 490, 75] and runs 82 px past the right edge of the 408x480 screen
error: elements[5].open: "battery" does nothing on this watch; open "settings" instead
error: aod.elements[2]: "month" at aod.elements[2] overlaps "weekday" at aod.elements[1] by 34 px around [123, 101, 200, 103]; move one of them
warning: elements[4]: "time" (seconds) has contrast 2.7:1 against the background under it, hard to read outdoors; ...
warning: elements[2].source: "calories" is seen in other faces but not yet confirmed on a watch
```

Fix every error and build again. Warnings build, but the result may not work on a wrist.

## Working order

1. Decide the look in words: background, what is shown, where, in which colours.
2. Write the description, starting from one of the two examples.
3. `--check` until it reports nothing.
4. Build and look at both PNGs; adjust positions by reading the edges in the messages.
5. Try the face on a watch before telling anyone it works.

Avoid: goal rings and progress bars (not the style of these faces), the battery
level unless asked, seconds on the always-on screen, unconfirmed sources used
without saying so.
