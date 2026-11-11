---
name: score-to-audio
description: Turn a written score into playable audio — MIDI, MusicXML/MXL, or a screenshot of sheet music — and deliver WAV/MP3. Use when the user hands over a score (image, PDF, MIDI, MusicXML, or a link to a sheet-music page) and wants to hear it, when they ask to "把谱子转成音乐", or when an arrangement must be rendered to audio. Covers exact extraction from Verovio-style SVG, image fallbacks with honest uncertainty, MIDI building, SoundFont rendering with fluidsynth, and loudness-mastered MP3 export.
---

# Score → Audio

Never guess a pitch you can extract. Work down this ladder and stop at the first rung that applies.

| Source | Confidence | Path |
|---|---|---|
| MIDI / `.mid` | ~100% | straight to render |
| MusicXML / `.mxl` / MEI | ~95% | parse → MIDI |
| Verovio-exported SVG (many web sheet sites) | ~99% | `scripts/svg_score.py` |
| ABC / LilyPond / plain-text notes | ~90% | midi |
| Screenshot / PDF of an engraving | 50–80% | **transcribe, then get the user to confirm a 20–30 s excerpt** |
| Handwritten dense two-hand chords | 40–60% | do not silently ship |

## 1. Find the exact data first

A screenshot is the last resort, not the first. In order:

1. Ask for the file (MIDI / MusicXML) or the page URL.
2. If you have a URL, fetch the HTML and look at what it loads:
   - `<link rel=preload ... .svg>` under a sheet-image host — the score is vector. Download it.
   - `data-pname` / `data-oct` in the SVG means it came from Verovio (or a similar engraver) and carries **exact written pitches and durations**. Use `scripts/svg_score.py`; do not transcribe by eye.
3. Visit `robots.txt` / terms before bulk-downloading a site's assets, and credit the source in the delivery note.

### Verovio SVG facts worth knowing

- `<g class="note" data-pname="f" data-oct="5" data-dur="8">` — written pitch name, octave, and duration denominator (8 = eighth).
- `<g class="keySig" data-sig="6s">` — key signature: `Ns` = N sharps, `Nf` = N flats. Apply it yourself; `data-pname` is the **written**, not the sounding, note.
- Notes nest inside `<g class="chord">`, `<g class="beam">`, `<g class="tuplet">` — flatten recursively or you silently drop every beamed note.
- Chords usually carry **no** `data-dur`. Take it from the notehead glyph: `E0A2` whole, `E0A3` half, `E0A4` black (quarter), then multiply by 1.5 per `<g class="dots">`.
- Rests are `<g class="rest">` and consume time — count them or everything after drifts.
- `class="accid"` (when present) means an accidental outside the key; resolve it before building MIDI.

## 2. Image-only scores

Read at **≥2.5×**, one or two bars per crop, and verify every page against a second view. Practical rules learned the hard way:

- Crop + upscale with ImageMagick/ffmpeg/sharp; do not trust a full-page view for pitch.
- SVG-overlay annotation works for **lines and shapes but not for text** on Android (no fontconfig → text silently disappears). Colour-code the five staff lines instead and read the colour.
- A note head is ~10 px at screenshot scale. Ledger lines and accidentals are where errors hide — zoom those bars again.
- Transcribe melody + harmony, render a 20–30 s excerpt, and ask the user to confirm before doing all 74 bars.

## 3. Build the MIDI

`scripts/build_midi.py` reads the `score.json` produced by `scripts/svg_score.py`:

```sh
python3 scripts/svg_score.py --svg-dir pages/ --out score.json   # or --url
python3 scripts/build_midi.py score.json --out piece.mid --bpm 190 --program 0
```

- Quarter note = 1 beat; `--bpm` is the printed tempo (♩=…).
- Right hand = staff 1, left hand = staff 2, both on channel 0 with GM program 0 (acoustic grand).
- Velocity defaults to 78; the score's own dynamics (if any) beat a constant.

## 4. Render

```sh
scripts/render.sh piece.mid out.mp3
```

Under the hood:

```sh
fluidsynth -ni -F tmp.wav -r 48000 -g 0.8 "$SOUNDFONT" piece.mid
ffmpeg -i tmp.wav -af "volume=7dB" -c:a libmp3lame -b:a 320k out.mp3
```

- `SOUNDFONT` env var. MuseScore's `MS Basic.sf3` (49 MB, GM program 0 = piano) is a good default on phones.
- **SF3 vs SF2 is only a container difference** (Ogg-compressed copies of the same samples). Do not promise a quality jump from "switching to SF2"; a real jump needs a different piano instrument.
- Levels from fluidsynth are low: expect mean ≈ −30 dB / peak ≈ −13 dB. Measure with `ffmpeg -af volumedetect` and normalise; never ship at −30 dB.
- `ffmpeg` cannot read MIDI (no decoder). fluidsynth is the bridge.
- Rendering is fast: a 2-minute piano piece takes seconds, not minutes.

## 5. Verify before delivering

- `ffprobe` the output: duration, sample rate, channels, codec.
- `volumedetect`: peak ≤ −1 dB, mean around −16 to −18 dB for piano.
- Compare the MIDI's note count and per-bar beat totals against the source (`build_midi.py` prints both). A bar that does not total 4 beats in 4/4 is a parsing bug, not a musical choice.
- MP3 named after the piece, dropped in the user's preferred output folder.

## Termux / Android notes

- Node reports `platform = android`, so `sharp` has **no** prebuilt binary. Add the WebAssembly backend instead:
  `npm pack @img/sharp-wasm32@<sharp version>` + `@emnapi/runtime` + `@emnapi/core`, unpack into the host package's `node_modules`.
- No `/tmp` — use `$TMPDIR`. No `/bin/bash` — scripts use `#!/usr/bin/env bash` or POSIX `sh`.
- `mido` for MIDI I/O; `mido` has no `__version__` attribute, so never probe it that way.
