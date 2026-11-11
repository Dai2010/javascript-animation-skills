#!/usr/bin/env python3
"""Brief JSON -> multi-track MIDI.  Schema in ../SKILL.md.

  python3 compose.py brief.json -o out.mid
"""
from __future__ import annotations

import argparse
import json
import sys

from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo

import harmony as H

TPB = 480
CH_HARM, CH_BASS, CH_MEL, CH_DRUM = 0, 1, 2, 9


def chord_list(brief):
    key = brief.get("key", "C")
    key_pc = (H.PC[key[0]] + H._acc(key[1:2])) % 12
    minor = str(brief.get("mode", "major")).lower().startswith("min")
    per = int(brief.get("bars_per_chord", 1))
    out = []
    for sym in brief["chart"]:
        ch = H.roman(sym, key_pc, minor) if brief.get("roman") else H.parse(sym)
        out += [ch] * per
    return out


def build(brief):
    meter = int(brief.get("meter", 4))
    voices = int(brief.get("voices", 4))
    texture = brief.get("texture", "block")
    chords = chord_list(brief)
    bars = len(chords)
    tr = {"harm": [], "bass": [], "mel": [], "drum": []}
    prev = None
    for bar, ch in enumerate(chords):
        start = bar * meter
        v = H.voice_lead(ch, prev, voices)
        prev = v
        b = H.bass_note(ch)
        if texture == "block":
            for beat in range(0, meter, 2):
                for p in v:
                    tr["harm"].append((start + beat, p, 2, 58, CH_HARM))
            tr["bass"].append((start, b, meter, 64, CH_BASS))
        elif texture == "alberti":
            third = next((p for p in v if (p - ch.root) % 12 in (3, 4)), v[1])
            fifth = next((p for p in v if (p - ch.root) % 12 == 7), v[-1])
            seq = [b, fifth, third, fifth]
            for i in range(meter):
                tr["harm"].append((start + i, seq[i % 4], 0.9, 52, CH_HARM))
            tr["bass"].append((start, b, meter, 62, CH_BASS))
        elif texture == "arpeggio":
            tones = sorted(v)
            seq = tones + tones[-2:0:-1]
            for i in range(meter * 2):
                tr["harm"].append((start + i * 0.5, seq[i % len(seq)], 0.45, 54, CH_HARM))
            tr["bass"].append((start, b, meter, 60, CH_BASS))
        elif texture == "band":
            for p in v:
                tr["harm"].append((start, p, meter, 46, CH_HARM))
            tr["bass"].append((start, b, meter / 2, 66, CH_BASS))
            tr["bass"].append((start + meter / 2, b + 7, meter / 2, 62, CH_BASS))
            for beat in range(meter):
                tr["drum"].append((start + beat, 36 if beat in (0, 2) else 38, 0.25, 70, CH_DRUM))
                for half in (0, 0.5):
                    tr["drum"].append((start + beat + half, 42, 0.2, 40, CH_DRUM))
        else:
            raise SystemExit(f"unknown texture {texture!r}")

    for m in brief.get("melody", []):
        bar = int(m["bar"]) - 1
        start = bar * meter + float(m.get("beat", 1)) - 1
        tr["mel"].append((start, H.note_to_midi(m["note"]),
                          float(m.get("dur", 1)), int(m.get("vel", 86)), CH_MEL))
    return tr, chords, bars


def write_midi(path, tr, brief, bars, meter):
    mid = MidiFile(ticks_per_beat=TPB)
    cond = MidiTrack()
    mid.tracks.append(cond)
    title = brief.get("title", "compose").encode("ascii", "replace").decode()
    cond.append(MetaMessage("track_name", name=title, time=0))
    cond.append(MetaMessage("time_signature", numerator=meter, denominator=4, time=0))
    cond.append(MetaMessage("set_tempo", tempo=bpm2tempo(brief.get("tempo", 80)), time=0))

    def add(events, ch, program, name):
        if not events:
            return
        track = MidiTrack()
        mid.tracks.append(track)
        track.append(MetaMessage("track_name", name=name, time=0))
        track.append(Message("program_change", channel=ch, program=program, time=0))
        abs_ev = []
        for start, pitch, dur, vel, _ch in events:
            abs_ev.append((int(round(start * TPB)), 1, pitch, vel))
            abs_ev.append((int(round((start + dur) * TPB)), 0, pitch, vel))
        abs_ev.sort(key=lambda e: (e[0], e[1]))
        t = 0
        for tick, on, pitch, vel in abs_ev:
            track.append(Message("note_on" if on else "note_off", note=pitch,
                                 velocity=vel if on else 0, channel=ch,
                                 time=max(0, tick - t)))
            t = tick
        track.append(MetaMessage("end_of_track", time=0))

    add(tr["mel"], CH_MEL, int(brief.get("melody_program", 0)), "melody")
    add(tr["harm"], CH_HARM, int(brief.get("harmony_program", 0)), "harmony")
    add(tr["bass"], CH_BASS, int(brief.get("bass_program", 0)), "bass")
    add(tr["drum"], CH_DRUM, 0, "drums")
    mid.save(path)


def verify(tr, chords, bars, meter):
    total = bars * meter
    print(f"bars={bars} meter={meter}/4  total={total} beats")
    for name in ("harm", "bass", "mel", "drum"):
        ev = tr[name]
        if not ev:
            continue
        beats = sum(e[2] for e in ev)
        lo = min(e[1] for e in ev)
        hi = max(e[1] for e in ev)
        print(f"  {name:5} notes={len(ev):4d} sound-beats={beats:6.1f} "
              f"range={H.midi_name(lo)}-{H.midi_name(hi)}")
    print("chords:", " ".join(c.symbol for c in chords))
    tail = max((e[0] + e[2] for v in tr.values() for e in v), default=0)
    if tail < total:
        print(f"WARN: last note ends at beat {tail}, before bar line {total}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("brief")
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()
    brief = json.load(open(a.brief, encoding="utf-8"))
    tr, chords, bars = build(brief)
    out = a.out or (a.brief.rsplit(".", 1)[0] + ".mid")
    write_midi(out, tr, brief, bars, int(brief.get("meter", 4)))
    verify(tr, chords, bars, int(brief.get("meter", 4)))
    print("wrote", out)


if __name__ == "__main__":
    sys.exit(main())
