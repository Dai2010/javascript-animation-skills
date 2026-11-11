#!/usr/bin/env python3
"""score.json (from svg_score.py) -> MIDI. Quarter note = 1 beat."""
import argparse
import json
import sys

import mido
from mido import Message, MetaMessage, MidiFile, MidiTrack


def build(score, out, bpm=120, program=0, velocity=78, pedal=False, ppq=480):
    measures = score["measures"]
    mid = MidiFile(ticks_per_beat=ppq)
    tempo = int(round(60_000_000 / bpm))

    for staff in (0, 1):
        tr = MidiTrack()
        mid.tracks.append(tr)
        tr.append(MetaMessage("track_name", name=f"staff{staff + 1}", time=0))
        tr.append(MetaMessage("set_tempo", tempo=tempo, time=0))
        tr.append(MetaMessage("time_signature", numerator=4, denominator=4, time=0))
        tr.append(Message("program_change", channel=0, program=program, time=0))

        events = []
        bar = 0.0
        for m in measures:
            voice = next((v for v in m["voices"] if v["staff"] == staff), None)
            if voice:
                for e in voice["evs"]:
                    events.append((bar + e["t"], e["d"], e["midi"]))
            if pedal:
                events.append((bar, 0.0, ("CC64", 127)))
                events.append((bar + 3.98, 0.0, ("CC64", 0)))
            bar += 4.0
        events.sort(key=lambda x: x[0])

        last = 0
        for t, d, payload in events:
            tick = int(round(t * ppq))
            delta = max(0, tick - last)
            if isinstance(payload, tuple) and payload[0] == "CC64":
                tr.append(Message("control_change", channel=0, control=64, value=payload[1], time=delta))
                last = tick
                continue
            for i, p in enumerate(payload):
                tr.append(Message("note_on", channel=0, note=p, velocity=velocity, time=delta if i == 0 else 0))
            end = int(round((t + d) * ppq))
            off = end - tick
            for i, p in enumerate(payload):
                tr.append(Message("note_off", channel=0, note=p, velocity=0, time=off if i == 0 else 0))
            last = end

    mid.save(out)
    total = sum(len(v["evs"]) for m in measures for v in m["voices"])
    beats = {round(v["total"], 2) for m in measures for v in m["voices"]}
    print(f"{out}: {len(measures)} bars, {total} events, {bpm} BPM, {mid.length:.1f}s", file=sys.stderr)
    print(f"bar totals: {sorted(beats)}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("score", nargs="?", default="score.json")
    ap.add_argument("--out", default="piece.mid")
    ap.add_argument("--bpm", type=float, default=120)
    ap.add_argument("--program", type=int, default=0, help="GM program (0 = acoustic grand)")
    ap.add_argument("--velocity", type=int, default=78)
    ap.add_argument("--pedal", action="store_true", help="sustain per bar")
    a = ap.parse_args()
    build(json.load(open(a.score)), a.out, a.bpm, a.program, a.velocity, a.pedal)


if __name__ == "__main__":
    main()
