#!/usr/bin/env python3
"""Chord symbols, Roman numerals, voice-led voicings, note names.

  python3 harmony.py "Cmaj7 Am7 Dm7 G7" --key C
  python3 harmony.py "ii7 V7 Imaj7" --key C --roman
"""
from __future__ import annotations

import argparse
import itertools
import re
from dataclasses import dataclass

PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

QUAL = {
    "": (0, 4, 7), "maj": (0, 4, 7), "M": (0, 4, 7),
    "m": (0, 3, 7), "min": (0, 3, 7), "-": (0, 3, 7),
    "dim": (0, 3, 6), "o": (0, 3, 6), "°": (0, 3, 6),
    "aug": (0, 4, 8), "+": (0, 4, 8),
    "sus2": (0, 2, 7), "sus4": (0, 5, 7), "5": (0, 7),
    "6": (0, 4, 7, 9), "m6": (0, 3, 7, 9),
    "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11), "M7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10), "m7b5": (0, 3, 6, 10), "ø7": (0, 3, 6, 10),
    "dim7": (0, 3, 6, 9), "o7": (0, 3, 6, 9),
    "aug7": (0, 4, 8, 10), "7sus4": (0, 5, 7, 10),
    "add9": (0, 4, 7, 14), "madd9": (0, 3, 7, 14),
    "9": (0, 4, 7, 10, 14), "maj9": (0, 4, 7, 11, 14), "m9": (0, 3, 7, 10, 14),
    "7b9": (0, 4, 7, 10, 13), "13": (0, 4, 7, 10, 21),
}
ALIAS = {"min": "m", "mi": "m", "min7": "m7", "mi7": "m7", "ma": "", "ma7": "maj7",
         "M": "", "M7": "maj7", "ø": "m7b5", "°": "dim", "°7": "dim7", "o7": "dim7"}

MAJOR_STEPS = [0, 2, 4, 5, 7, 9, 11]
MINOR_STEPS = [0, 2, 3, 5, 7, 8, 10]
DEG = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}


def _acc(s: str) -> int:
    return 1 if s == "#" else -1 if s == "b" else 0


@dataclass(frozen=True)
class Chord:
    symbol: str
    root: int
    intervals: tuple
    bass: int | None = None

    @property
    def pcs(self) -> list:
        return sorted({(self.root + i) % 12 for i in self.intervals})

    @property
    def bass_pc(self) -> int:
        return self.root if self.bass is None else self.bass


_CH = re.compile(r"^([A-G])([#b]?)([^/]*)(?:/([A-G])([#b]?))?$")
_NOTE = re.compile(r"^([A-G])([#b]?)(-?\d+)$")


def parse(sym: str) -> Chord:
    m = _CH.match(sym.strip())
    if not m:
        raise ValueError(f"not a chord symbol: {sym!r}")
    letter, acc, qual, blett, bacc = m.groups()
    root = (PC[letter] + _acc(acc)) % 12
    q = qual.strip()
    q = ALIAS.get(q, q)
    if q not in QUAL:
        raise ValueError(f"unknown quality {qual!r} in {sym!r}")
    bass = (PC[blett] + _acc(bacc)) % 12 if blett else None
    return Chord(sym, root, QUAL[q], bass)


def roman(sym: str, key_pc: int = 0, minor: bool = False) -> Chord:
    m = re.match(r"^([#b]?)([ivIV]+)(.*)$", sym.strip())
    if not m or m.group(2).upper() not in DEG:
        return parse(sym)
    acc, deg_s, suf = m.groups()
    deg = DEG[deg_s.upper()]
    steps = MINOR_STEPS if minor else MAJOR_STEPS
    root = (key_pc + steps[deg - 1] + _acc(acc)) % 12
    upper = deg_s.isupper()
    if minor and deg == 7 and upper:
        root = (root + 1) % 12          # 和声小调的导音
    q = {"": "" if upper else "m", "7": "7" if upper else "m7",
         "maj7": "maj7", "M7": "maj7", "°": "dim", "°7": "dim7",
         "ø7": "m7b5", "+": "aug", "sus4": "sus4", "m": "m"}.get(suf)
    if q is None:
        raise ValueError(f"unknown roman suffix {suf!r} in {sym!r}")
    return Chord(sym, root, QUAL[q])


def note_to_midi(s: str) -> int:
    m = _NOTE.match(s.strip())
    if not m:
        raise ValueError(f"not a note name: {s!r}")
    letter, acc, octave = m.groups()
    return 12 * (int(octave) + 1) + PC[letter] + _acc(acc)


def midi_name(p: int) -> str:
    return f"{NAMES[p % 12]}{p // 12 - 1}"


def _cands(pcs, lo, hi):
    return [p for p in range(lo, hi + 1) if p % 12 in pcs]


def initial_voicing(ch: Chord, voices=4, lo=48, hi=79) -> tuple:
    base = lo + ((ch.bass_pc - lo) % 12)
    stack = [base]
    for iv in ch.intervals[1:]:
        target = (ch.root + iv) % 12
        stack.append(stack[-1] + ((target - stack[-1]) % 12))
    while len(stack) < voices:
        stack.append(stack[0] + 12)
    stack = stack[:voices]
    if stack[-1] > hi:
        stack = [p - 12 for p in stack]
    return tuple(sorted(stack))


def voice_lead(ch: Chord, prev=None, voices=4, lo=48, hi=79) -> tuple:
    """Nearest voicing: minimal total motion, no crossing, root doubled before others."""
    if prev is None:
        return initial_voicing(ch, voices, lo, hi)
    pcs = ch.pcs
    essential = {ch.root}
    for iv in ch.intervals[:3]:
        essential.add((ch.root + iv) % 12)
    if len(essential) > voices:
        essential = {ch.root, (ch.root + ch.intervals[1]) % 12}
    sets = []
    for p in prev:
        c = _cands(pcs, max(lo, p - 7), min(hi, p + 7))
        sets.append(c or _cands(pcs, lo, hi))
    best, best_score = None, None
    for combo in itertools.product(*sets):
        if list(combo) != sorted(combo) or len(set(combo)) < len(combo):
            continue
        pcs_here = {p % 12 for p in combo}
        if not essential <= pcs_here:
            continue
        motion = sum(abs(a - b) for a, b in zip(combo, prev))
        leaps = sum(max(0, abs(a - b) - 5) for a, b in zip(combo, prev))
        doubled = [p % 12 for p in combo]
        pen = 2.0 * sum(1 for pc in set(doubled)
                        if doubled.count(pc) > 1 and pc != ch.root)
        score = motion + 1.5 * leaps + pen
        if best_score is None or score < best_score:
            best, best_score = combo, score
    return tuple(best) if best else initial_voicing(ch, voices, lo, hi)


def bass_note(ch: Chord, lo=33, hi=45) -> int:
    c = [p for p in range(lo, hi + 1) if p % 12 == ch.bass_pc]
    return min(c, key=lambda p: abs(p - 40)) if c else lo + ((ch.bass_pc - lo) % 12)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("chords")
    ap.add_argument("--key", default="C")
    ap.add_argument("--minor", action="store_true")
    ap.add_argument("--roman", action="store_true", help="input is Roman numerals")
    ap.add_argument("--voices", type=int, default=4)
    a = ap.parse_args()
    key_pc = (PC[a.key[0]] + _acc(a.key[1:2])) % 12
    print(f"key={a.key}{' minor' if a.minor else ' major'}")
    print("bar  sym       voicing                 bass   chord tones")
    prev = None
    for i, sym in enumerate(a.chords.replace(",", " ").split(), 1):
        ch = roman(sym, key_pc, a.minor) if a.roman else parse(sym)
        v = voice_lead(ch, prev, a.voices)
        b = bass_note(ch)
        print(f"{i:3d}  {sym:<9} {str(v):<23} {midi_name(b):<6} "
              f"{' '.join(NAMES[x] for x in ch.pcs)}")
        prev = v


if __name__ == "__main__":
    main()
