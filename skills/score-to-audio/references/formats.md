# Score sources, and what each really gives you

## Reliability ladder

| Source | What you get | Watch out for |
|---|---|---|
| MIDI | exact notes, exact timing, tempo map | arrangement may differ from the printed score |
| MusicXML / `.mxl` / MEI | notes, voices, beams, articulations | compressed `.mxl` needs unzipping to reach `score.xml` |
| Verovio SVG (web sheet sites) | exact written pitch + duration + key signature | chords/beams nest; chord duration lives in the notehead glyph |
| ABC / LilyPond | text you can parse | transposing instruments, repeats |
| Engraved screenshot / PDF | an image of music | every pitch is a judgement call |
| Handwritten two-hand chords | ... | do not ship without the user hearing it first |

## Why the SVG route wins

Modern Chinese sheet sites render the page as **SVG** (preloaded in the HTML head) instead of a bitmap. Such an SVG is machine-readable music:

```html
<g class="keySig" data-sig="6s"> … six ♯ glyphs … </g>
<g class="chord">
  <g class="dots"><circle …/><circle …/></g>
  <path d="M3426 1888v629" …/>                     <!-- stem -->
  <g class="note" data-pname="a" data-oct="4"> …  <!-- A4 -->
  <g class="note" data-pname="c" data-oct="5"> …  <!-- C5 -->
</g>
<g class="note" data-pname="f" data-oct="5" data-dur="8"> …
<g class="beam"><path …/>
  <g class="note" data-pname="d" data-oct="5" data-dur="8"> …
  <g class="note" data-pname="c" data-oct="5" data-dur="8"> …
</g>
```

Rules that took a while to learn:

1. `data-pname` is the **written** pitch. Apply `data-sig` (`6s` = 6 sharps = F♯ major: F C G D A E) to get sounding pitch.
2. Notes nest inside `chord`, `beam`, `tuplet`. Iterating only the layer's direct children loses every beamed note — which is most of the melody.
3. Chords have **no** `data-dur`. Read the notehead glyph: `E0A2` whole (4 beats), `E0A3` half (2), `E0A4` quarter (1); then dots ×1.5.
4. `<g class="rest">` consumes time. Miss it and every later bar shifts.
5. `class="accid"` (sharp/flat/natural outside the key) does not appear in every score — if it does, resolve it per note.
6. Sanity check: in 4/4 every staff's per-bar total must be exactly 4.0 beats. A bar totalling 3.0 means a dropped beam group.

## Image-only fallback

- Crop one or two bars at ≥2.5×; a full-page view is not enough to separate a line from the space above it.
- Colour-code the five staff lines rather than labelling them: SVG text does not render on Android (no fontconfig), but coloured strokes do.
- Melody first, then bass; ledger lines and accidentals get a second, tighter crop.
- Render 20–30 s and have the user confirm before transcribing the rest.

## SoundFonts on a phone

- MuseScore's `MS Basic.sf3` (≈49 MB) is a solid GM default; program 0 is the piano.
- `.sf3` is an Ogg-compressed `.sf2` — same samples, no audible upgrade from "switching to SF2". A real upgrade means a dedicated piano instrument (Salamander, Yamaha C5, …), which is 100 MB–1 GB.
- `fluidsynth -ni -F out.wav -r 48000 -g 0.8 "$SOUNDFONT" in.mid` renders offline; a 2-minute piano piece takes seconds.
- fluidsynth output is quiet (−30 dB mean is normal). Normalise before delivery.
- `ffmpeg` has no MIDI decoder — always go through fluidsynth.

## Termux specifics

- `sharp` has no `android-arm64` prebuild. Install the WebAssembly backend:
  `@img/sharp-wasm32` (matching the host `sharp` version) plus `@emnapi/runtime` and `@emnapi/core`, unpacked into the host package's `node_modules/@img/` and `node_modules/@emnapi/`.
- `$TMPDIR`, not `/tmp`. `$PREFIX/bin/bash`, not `/bin/bash`. No `which`.
