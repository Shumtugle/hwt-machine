# hwt-machine

Watch faces from code. Fonts and a short layout script go in; an installable `.hwt`
watch face comes out, drawn, packed and checked without a single hand-painted pixel.

**[Live page](https://shumtugle.github.io/hwt-machine/)**: Vibe running in the browser on
your clock, and a drop zone that opens any watch face package and draws it.

![Vibe in English, Russian, Finnish, and its always-on screen](docs/img/vibe.png)

## Vibe

The first face built with the machine. Black and scarlet, glass cards, the weekday and
the month in words, 24-hour time with seconds, battery, weather, pulse and steps, and a
cream mark that runs around the frame once a minute. Tapping a tile opens the matching
screen on the watch.

[`vibe.hwt`](https://github.com/Shumtugle/hwt-machine/raw/main/docs/faces/vibe.hwt) carries Russian, English and Finnish at once: pick the language in the
watch's face editor, the way other faces switch theirs. Or take a single-language file:
[English](https://github.com/Shumtugle/hwt-machine/raw/main/docs/faces/vibe-en.hwt),
[Russian](https://github.com/Shumtugle/hwt-machine/raw/main/docs/faces/vibe-ru.hwt) or
[Finnish](https://github.com/Shumtugle/hwt-machine/raw/main/docs/faces/vibe-fi.hwt)
(also attached to [Releases](https://github.com/Shumtugle/hwt-machine/releases)) and
install it with any app that can send a watch face file to the watch.

Built for 408 × 480 screens (screen code `HWHD13`). Runs on the HUAWEI WATCH FIT 4;
faces for this screen are reported to work on the FIT 3 as well, memory permitting.

## Night Tram

Ink background, cream numerals, amber lights: a little of an old instrument, a little of
an evening city. A lamp runs along the copper frame with the seconds, a horizon with a
crescent hangs over the time, and six stops along the bottom light up as the day's step
goal is walked. Battery, weather and steps share one row; the pulse sits above the route.

![Night Tram in English, Russian, Finnish, and its always-on screen](docs/img/night-tram.png)

[`night-tram.hwt`](https://github.com/Shumtugle/hwt-machine/raw/main/docs/faces/night-tram.hwt)
switches between Russian, English and Finnish on the watch; single-language files sit next
to it in [docs/faces](docs/faces). The route and the battery bar use progress sources seen
in other faces but not yet confirmed on a watch with this one.

## What the machine does

- **Writes the container byte-exact.** Header, protobuf layout, image table and
  run-length images; existing faces round-trip through it byte for byte.
- **Places glyphs by their ink.** Digits, capitals and symbols line up on their visible
  pixels, not on font metrics. A colon sits on the true middle of the digits.
- **Fits words to their card.** Weekdays and months come from a locale file; long words
  shrink until they fit.
- **Moves a mark around the frame.** The watch only offers the tens and the units of the
  second. Six strips and one covering layer still show a single mark stepping through all
  sixty positions.
- **Checks itself.** Previews are drawn by a simulator that reads the finished package,
  so a broken file shows up before it reaches a wrist. A card that would touch the frame
  stops the build.
- **Reads other faces.** `tools/inspect.py` prints any package's layout with named data
  sources, extracts its images and renders it.

## Build

Python 3 and Pillow.

```sh
python3 faces/vibe/build.py all          # every locale, plus the switchable face, into dist/
python3 faces/night-tram/build.py all
python3 faces/vibe/build.py ru --switchable ''   # just one locale
python3 tools/inspect.py dist/vibe-ru.hwt --images out/ --render screen.png
python3 -m unittest discover tests
cp dist/*.hwt docs/faces/                # refresh the faces on the live page
```

A new language is one JSON file in `faces/vibe/locale/` with seven weekdays, twelve
months and an optional suffix after the day number. Add it to `--switchable` to put it
in the all-in-one face.

## Layout of the repository

| path | content |
|---|---|
| `machine/container.py` | package, binary, image and protobuf reading and writing |
| `machine/layout.py` | image registry, element builders, groups and zones |
| `machine/codes.py` | element kinds, data sources, tap targets, with what is verified |
| `machine/draw.py` | text styles, symbols, glass cards, glow, the tick ring |
| `machine/effects.py` | the running mark |
| `machine/simulate.py` | draws a package the way the watch would |
| `faces/vibe/` | the Vibe face and its locales |
| `faces/night-tram/` | the Night Tram face and its locales |
| `tools/inspect.py` | look inside any face |
| `docs/` | the live page, its renderer, and the [format notes](docs/FORMAT.md) |

## Format

Everything known about the format, verified or only observed, is in
[docs/FORMAT.md](docs/FORMAT.md).

## Licence

Code: MIT, see [LICENSE](LICENSE).
The text face is under the SIL Open Font License 1.1 ([fonts/OFL.txt](fonts/OFL.txt)).
The symbol font is a subset of an icon font under the Apache License 2.0
([fonts/LICENSE-symbols.txt](fonts/LICENSE-symbols.txt)), reduced to the glyphs Vibe uses.
