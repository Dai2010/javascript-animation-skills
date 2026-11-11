#!/usr/bin/env bash
# MIDI -> loudness-normalised MP3.
#   render.sh piece.mid [out.mp3]
# SOUNDFONT env var wins; otherwise the first soundfont found is used.
set -euo pipefail

mid=${1:?usage: render.sh piece.mid [out.mp3]}
out=${2:-${mid%.*}.mp3}

sf=${SOUNDFONT:-}
if [ -z "$sf" ]; then
  for f in "$HOME/music/soundfonts/GeneralUser GS v1.44.sf2" \
           "$HOME/music/soundfonts/MS Basic.sf3"; do
    [ -f "$f" ] && sf=$f && break
  done
fi
[ -n "$sf" ] && [ -f "$sf" ] || { echo "set SOUNDFONT=/path/to.sf2" >&2; exit 2; }

tmp=$(mktemp "${TMPDIR:-/tmp}/render.XXXXXX.wav")
trap 'rm -f "$tmp"' EXIT

fluidsynth -ni -F "$tmp" -r 48000 -g 0.8 "$sf" "$mid" >/dev/null 2>&1
mean=$(ffmpeg -hide_banner -nostats -i "$tmp" -af volumedetect -f null - 2>&1 \
       | sed -n 's/.*mean_volume: \(-*[0-9.]*\) dB.*/\1/p')
gain=$(awk -v m="${mean:--30}" 'BEGIN{printf "%.1f", -17 - m}')
echo "soundfont=$(basename "$sf") mean=${mean:-?}dB gain=+${gain}dB"

# fluidsynth 会补几秒数字静音：找到尾部静音起点，裁到有声结尾 +0.5 s 并淡出
dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$tmp")
sil=$(ffmpeg -hide_banner -nostats -i "$tmp" -af silencedetect=noise=-50dB:d=2 -f null - 2>&1 \
      | grep -o 'silence_start: [0-9.]*' | tail -1 | awk '{print $2}')
end=$(awk -v d="$dur" -v s="${sil:-}" 'BEGIN{
  if (s != "" && d - s > 0.5) e = s + 0.5; else e = d;
  printf "%.3f", e }')
fade=$(awk -v e="$end" 'BEGIN{printf "%.3f", e - 0.5}')

ffmpeg -hide_banner -loglevel error -y -i "$tmp" -t "$end" \
  -af "volume=${gain}dB,alimiter=limit=0.84:level=false,afade=t=out:st=${fade}:d=0.5" \
  -c:a libmp3lame -b:a 320k "$out"

ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$out"
ffmpeg -hide_banner -nostats -i "$out" -af volumedetect -f null - 2>&1 \
  | sed -n 's/.*\(mean_volume\|max_volume\): \(.*\) dB/\1 \2 dB/p'
