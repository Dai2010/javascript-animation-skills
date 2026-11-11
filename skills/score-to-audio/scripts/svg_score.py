#!/usr/bin/env python3
"""Verovio-style SVG score pages -> score.json (measures / staves / events).

Extracted pitches are the *written* ones; the key signature
(<g class="keySig" data-sig="6s">) is applied to produce MIDI numbers.

    python3 svg_score.py --page https://example.com/piece/ID --out score.json
    python3 svg_score.py --svg-dir pages/ --out score.json
"""
import argparse
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

XLINK = "{http://www.w3.org/1999/xlink}href"
SHARP_ORDER = ["F", "C", "G", "D", "A", "E", "B"]
FLAT_ORDER = ["B", "E", "A", "D", "G", "C", "F"]
BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
HEAD = {"E0A2": 4.0, "E0A3": 2.0, "E0A4": 1.0}  # whole / half / black head, in beats
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 12)"}


def cls(el):
    return (el.get("class") or "").split()


def first_glyph(el):
    for node in el.iter():
        href = node.get(XLINK)
        if href:
            return href.lstrip("#").split("-")[0]
    return None


def event_dur(el, dotted):
    raw = el.get("data-dur")
    if raw:
        base = 4.0 / int(raw)
    else:
        node = next((n for n in el.iter() if "note" in cls(n)), el)
        base = HEAD.get(first_glyph(node), 1.0)
    return base * 1.5 if dotted else base


def flatten(el):
    """Yield events in time order, descending into beam / tuplet containers."""
    for child in list(el):
        c = cls(child)
        if {"chord", "note", "rest"} & set(c):
            yield child
        elif {"beam", "tuplet", "beamSpan"} & set(c):
            yield from flatten(child)


def key_accidentals(sig):
    if not sig:
        return {}
    n = int(sig[:-1] or 0)
    if sig.endswith("s"):
        return {p: 1 for p in SHARP_ORDER[:n]}
    if sig.endswith("f"):
        return {p: -1 for p in FLAT_ORDER[:n]}
    return {}


def fetch_pages(page_url, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    html = urllib.request.urlopen(urllib.request.Request(page_url, headers=UA), timeout=30).read().decode("utf-8", "ignore")
    urls = []
    for u in re.findall(r'https://[^"\'\\ ]+\.svg', html):
        if u not in urls:
            urls.append(u)

    def order(u):
        m = re.search(r"/(\d+)\.svg$", u)
        return int(m.group(1)) if m else 0

    urls.sort(key=order)
    paths = []
    for i, u in enumerate(urls):
        data = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read()
        p = os.path.join(out_dir, f"p{i + 1}.svg")
        open(p, "wb").write(data)
        paths.append(p)
    return paths


def parse(paths, sig_override=None):
    measures = []
    sig = sig_override
    for page_no, path in enumerate(paths, 1):
        root = ET.parse(path).getroot()
        for g in root.iter():
            if "keySig" in cls(g) and g.get("data-sig") and not sig:
                sig = g.get("data-sig")
        for g in root.iter():
            if "measure" in cls(g):
                measures.append((page_no, g))

    acc = key_accidentals(sig)
    score = []
    for idx, (page_no, m) in enumerate(measures, 1):
        staves = [g for g in m.iter() if "staff" in cls(g) and g.get("data-n")]
        staves.sort(key=lambda s: int(s.get("data-n")))
        voices = []
        for si, staff in enumerate(staves):
            for layer in [g for g in staff.iter() if "layer" in cls(g)]:
                t, evs = 0.0, []
                for el in flatten(layer):
                    dotted = any("dots" in cls(x) for x in el.iter())
                    if "rest" in cls(el):
                        t += event_dur(el, dotted)
                        continue
                    notes = [el] if "note" in cls(el) else [x for x in el.iter() if "note" in cls(x)]
                    pitches = []
                    for nt in notes:
                        p, o = nt.get("data-pname"), nt.get("data-oct")
                        if not p or not o:
                            continue
                        p = p.upper()
                        pitches.append(12 * (int(o) + 1) + BASE[p] + acc.get(p, 0))
                    dur = event_dur(el, dotted)
                    if pitches:
                        evs.append({"t": round(t, 4), "d": round(dur, 4), "midi": sorted(pitches)})
                    t += dur
                voices.append({"staff": si, "evs": evs, "total": round(t, 4)})
        score.append({"page": page_no, "no": idx, "voices": voices})
    return sig, score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", help="sheet page URL; its preloaded .svg files are downloaded")
    ap.add_argument("--svg-dir", help="directory with p1.svg, p2.svg, ...")
    ap.add_argument("--out", default="score.json")
    ap.add_argument("--sig", help="override key signature, e.g. 6s / 3f")
    a = ap.parse_args()

    if a.page:
        paths = fetch_pages(a.page, a.svg_dir or "pages")
    elif a.svg_dir:
        paths = sorted(
            (os.path.join(a.svg_dir, f) for f in os.listdir(a.svg_dir) if f.endswith(".svg")),
            key=lambda p: int(re.sub(r"\D", "", os.path.basename(p)) or 0),
        )
    else:
        ap.error("need --page or --svg-dir")

    sig, score = parse(paths, a.sig)
    json.dump({"sig": sig, "measures": score}, open(a.out, "w"))
    bad = [m["no"] for m in score if any(abs(v["total"] - round(v["total"])) > 1e-6 or v["total"] == 0 for v in m["voices"])]
    print(f"{a.out}: {len(score)} measures, key {sig}, pages {len(paths)}", file=sys.stderr)
    totals = {round(v["total"], 2) for m in score for v in m["voices"]}
    print(f"bar totals seen: {sorted(totals)}", file=sys.stderr)
    if bad:
        print(f"check bars: {bad[:20]}", file=sys.stderr)


if __name__ == "__main__":
    main()
