#!/usr/bin/env bash
# MIDI -> mastered MP3 (or WAV) via fluidsynth.
# usage: render.sh <in.mid> <out.mp3|out.wav> [gain_db]
set -euo pipefail

in=${1:?in.mid}
out=${2:?out.mp3}
gain=${3:-7}

: "${SOUNDFONT:?set SOUNDFONT to a .sf2/.sf3 file, e.g. export SOUNDFONT=$HOME/music/soundfonts/MS\\ Basic.sf3}"

tmp=$(mktemp -d "${TMPDIR:-/tmp}/render.XXXXXX")
trap 'rm -rf "$tmp"' EXIT

fluidsynth -ni -F "$tmp/raw.wav" -r 48000 -g 0.8 "$SOUNDFONT" "$in" >/dev/null

# 电平：fluidsynth 出来普遍偏小，默认补 7 dB；用 volumedetect 复核
ffmpeg -hide_banner -loglevel error -y -i "$tmp/raw.wav" -af "volume=${gain}dB" \
  -c:a libmp3lame -b:a 320k "$tmp/master.wav.mp3"

case "$out" in
  *.wav) ffmpeg -hide_banner -loglevel error -y -i "$tmp/raw.wav" -af "volume=${gain}dB" "$out" ;;
  *)     cp "$tmp/master.wav.mp3" "$out" ;;
esac

ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$out"
ffmpeg -hide_banner -i "$out" -af volumedetect -f null - 2>&1 | grep -E "mean_volume|max_volume"
