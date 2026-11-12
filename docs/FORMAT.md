# Watch face format notes

What the watch reads, as far as it has been worked out. The machine writes this format
and reads it back; everything below was taken from existing faces and from what they
draw. Lines marked **verified** were confirmed on a real watch with a face built here.
Everything else is observed in faces made by other tools and is likely, not proven.

Target: compact wearables with a 408 × 480 screen and screen code `HWHD13`.

## Package

A zip archive:

| entry | content |
|---|---|
| `description.xml` | manifest: title, author, designer, screen code, version, font |
| `com.huawei.watchface` | the binary described below |
| `preview/cover.jpg` | 816 × 960 picture of the normal screen |
| `preview/icon_small.jpg` | about 332 × 390 |
| `preview/aod.jpg` | 816 × 960 picture of the always-on screen |

The manifest `version` is the layout-tool version the face claims; `2.5.1` installs.
Some first-party packages nest a second zip inside the binary entry, holding a `.bin`
with the same structure.

## Binary

```
offset  size  field
0       2     version, always 2
2       2     layout length L
4       4     table length T (8 bytes per image)
8       4     blob length B
12      4     zero
16      L     layout (protobuf)
16+L    T     image table: (offset, size) pairs, little endian, offsets into the blob
16+L+T  B     blob: 8-byte marker 55 55 55 55 01 00 00 01, then images back to back
```

The first table offset is therefore 8. One modified face in circulation carries a wrong
blob length and still installs, so the watch does not seem to check it.

## Images

```
45 23 88 88   magic
u16 width, u16 height
pixels        BGRA, row by row
```

Pixels are stored either raw (4 bytes) or as a run: `89 67 45 23`, the 4-byte colour,
a u32 count. A run is used for four or more equal pixels; with that rule the machine
re-encodes existing faces byte for byte. A solid rectangle of any size costs 20 bytes,
so plain fills are free.

Transparent pixels still carry colour bytes. Write them as `00 00 00 00`, or runs break
and a mostly empty frame can weigh as much as a photo.

Newer first-party faces use a different image encoding (magic `49 65 59 36`). It is not
decoded here.

Images are referenced from the layout by 1-based index written as three digits:
`"001"`, `"002"`. By convention:

| ref | use |
|---|---|
| `001` | picker thumbnail, 240 × 282 (228 × 269 on older faces), never referenced |
| `002` | background, usually |
| `003` | full-size preview, named by the first group |

## Layout

Top-level fields: repeated `1` (group), `2` title, `3` second title.

A group: `1` index, `2` type (0), `4` preview image ref in group 0, then elements in `5`,
touch zones in `8`, editable slots in `7`, frame animations in `9`.
Groups are drawn in the order written. Faces almost always use this order:

| index | content |
|---|---|
| 0 | backgrounds (one per screen mode) |
| 3 | touch zones and the elements inside them |
| 2 | date |
| 1 | time |

An element: `1` index in the group, `2` kind, then the body in a field that depends on
the kind.

| kind | body field | element | status |
|---|---|---|---|
| 1 | 4 | static image | verified |
| 2 | 5 | image list chosen by a data value | verified |
| 3 | 6 | number drawn from ten digit images | verified |
| 5 | 8 | hand: image rotated about a pivot | verified |
| 6 | 9 | progress bar | observed |
| 7 | 10 | arc reveal | observed |
| 0 | 3 | text in the system font | observed |
| 10 | 11 | system-font text with a unit or format | observed |

Every element carries a screen-mode flag: `0` normal screen, `1` always-on screen.
To show something in both modes, write it twice.

### Static image (kind 1)

`1` image ref, `2` position `{1: x, 2: y}`, `5` mode flag.

### Image list (kind 2)

`1` image refs (repeated), `2` position, `3` data source, `6` mode flag.
The data value indexes the list. Month and weekday lists start with a dummy at index 0:
January is index 1, Monday is index 1.

### Number (kind 3)

`1` ten digit refs 0–9, `2` empty string, `3` anchor `{x, y}`, `4` alignment, `5` data
source, `6` minus image ref or empty, `7` 0, `8` 0, `13` mode flag.
`y` is the top of the digit images. With right alignment (2, **verified**) `x` is the
right edge; units such as `%` or `°` are best drawn as a fixed image just after it.

### Hand (kind 5)

`1` image ref, `2` square `{x, y, w, h}` whose centre is the rotation centre,
`3` pivot `{x, y}` inside the image, `4` start angle 0, `5` sweep 360, `6` data source,
`9` mode flag. The image is drawn pointing at 12 o'clock; the square is usually
`2 × pivot y` on a side.

### System-font text (kinds 0 and 10)

`1` box `{x, y, w, h}`, `2` colour `{r, g, b, a}`, `3` style code (seen: 129, 138, 149,
150, 157, 158, 161, 163, 166, 169, 176; 149 in faces for this screen), `4` alignment,
`5` data source, `7` 0. No font travels with the face; the watch uses its own.

Kind 10 reads differently: `5` is the format, `6` the source and `7` a second source
(255 for none), `9` the mode flag. Seen formats: 5 with battery percent (`80%`), 7 with
temperature (`24°`), 2 with temperature low and high as one value (`8/40`).

### Touch zone (group field 8)

`1` index, `2` 0, `5` box `{x, y, w, h}`, `6` elements (as above), `8` target to open.
### Choice zone and slots (group fields 8 and 7)

A zone with `2` set to 1 is a choice: `3` holds the slot indices as raw bytes, `4` the
default slot, `5` the box. The wearer switches choices in the face editor.

A slot (group field 7): `1` slot index, `2` elements (repeated), `3` thumbnail ref,
`4` selection-frame ref (both the size of the zone), `5` function code. Elements inside a
slot sit at position `(0, 0)` and carry an offset from the zone's top-left corner: field
`4` for images, `5` for image lists, `10` for numbers. Offsets may be negative.

Verified on the watch: slots, offsets and choices work. The editor shows the zone with
its selection frame and lists the choices **by function**, under the function's own
name. Slots that share a function code fold into one entry, so variants of one thing
(languages, say) need a different code per slot, and the editor shows those codes'
names, not the variant's. Codes seen so far:

| function code | name in the editor |
|---|---|
| 1 | Date (under Calendar) |
| 2 | Day of week |
| 9 | Sun |

A language-switching face built with codes 1, 2 and 9 switches correctly between its
three languages; the entries just read *Date*, *Day of week* and *Sun*.

## Visible area

The picture is 408 × 480, but the glass is rounded and the bezel covers the corners.
Seen on a wrist (same on all three watch generations that share this screen):

| boundary | result |
|---|---|
| rounded rectangle 11 px in from every edge, corner radius 82 | a 1.4 px line drawn on it shows whole, corners included — **verified** |
| rounded rectangle 3 px in, corner radius 64 | ticks and a running mark drawn on it disappear in the corners |

| lines 3, 6 and 9 px in from every edge | all visible along the four straight edges; they fade where the glass turns into the corners — **verified** |

So the straight edges show to within 3 px, and the corners are what the bezel takes.
Ink that must be seen in a corner stays inside the quarter circles of radius 82 centred
on `(93, 93)`, `(315, 93)`, `(93, 387)` and `(315, 387)`. Where the 3 px lines fade,
the glass itself turns with a radius of roughly 77 px at the very edge (an estimate
from a photograph). Backgrounds may run to the edge and are cropped.

## Legibility

Read on a wrist, Oswald at size 25 (capitals and digits 21 px, about 1.5 mm) is the
smallest read without strain and size 32 (26 px, about 1.9 mm) reads in comfort; the
light weight reads well at size 28 and above. The time and the date must be caught at
a glance and want the comfortable size; readings looked at on purpose do at size 22
(18 px), which is also the height of system text in style 149.

## Data sources

| code | value | used with | status |
|---|---|---|---|
| 59 / 60 | hour tens 0–2 / units | image list | verified |
| 61 / 62 | minute tens 0–5 / units | image list | verified |
| 63 / 64 | second tens 0–5 / units | image list | verified |
| 51 | month 1–12 | image list | verified |
| 52 | weekday 1–7 from Monday | image list | verified |
| 53 | weather condition 0–10 | image list | verified |
| 54 | battery tenths 0–10 | image list | verified |
| 70 / 71 | day of month tens / units | image list | observed |
| 72 | unread messages 0 / 1 | image list | observed |
| 17 | day of month | number | verified |
| 0 | steps | number, text | verified |
| 2 | heart rate | number, text | verified |
| 4 | temperature now | number, needs a minus image | verified |
| 9 | battery percent | number, text | verified |
| 1 | calories | number, text | observed |
| 20 / 21 | temperature high / low | number | observed |
| 12 / 13 / 14 | hours / minutes / seconds | number | observed |
| 121 / 122 | sunrise / sunset | text | observed |
| 142 | sleep last night, formatted by the watch (`7h23m`) | text, style 149 | **verified** |
| 146 | distance walked today, km (`1.94`) | text, style 149 | **verified** |
| 1 | calories (`535`) | text, style 149 | **verified** |
| 7 | air pressure, hPa (`990`) | text, style 149 | **verified** |
| 8 | altitude, m (`229`) | text, style 149 | **verified** |
| 26 | emotional wellbeing; `--` while its measurement is off | text, style 149 | verified |
| 143 / 144 / 147 | something that reads `0` | text | seen on a wrist, meaning unknown |
| 140 / 141 / 145 / 148 | nothing drawn | text | tried on a wrist |
| 150 | hour hand | hand | verified |
| 153 | minute hand | hand | verified |
| 154 | second hand | hand | observed |

Weather icon order (observed): unknown, sunny, clear night, cloudy, partly cloudy, rain,
thunderstorm, snow, wind, haze, fog.

There is no source for the second as one number 0–59 among image lists. A mark that runs
around the frame is still possible; see the running mark in the machine's effects.

## Tap targets

| code | opens | status |
|---|---|---|
| 10 | steps | verified |
| 11 | heart rate | verified |
| 21 | weather | verified |
| 17 | battery: nothing on newer watches | verified |
| 50 | settings | observed |
| 18 | messages | observed |
| 12 | calories | verified |
| 16 | emotional wellbeing | verified |
| 22 | altitude | verified |
| 23 | air pressure | verified |
| 24 | activity rings | verified |
| 25 | sleep | verified |
| 26 | workouts | verified |
| 28 | alarms | verified |
| 29 | stopwatch | verified |
| 30 | timer | verified |
| 35 | contacts | verified |
| 36 | something with sound, labelled music in another face | observed |
| 38 | something with sound, voice notes it seems | observed |

In choice slots the same field names a *function*; see the table above.
