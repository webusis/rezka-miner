#!/bin/bash
# Цикл отладки плеера ютуба: сборка Rezka.apk -> установка -> запуск -> логи.
# Использование: ./yt_player_run.sh [vid] [h]
set -uo pipefail
cd "$(dirname "$0")"
VID="${1:-Obsu2DFy05I}"
H="${2:-720}"

echo "[build]"
./build.sh 2>&1 | grep -viE "^warning|DexOpt|Type .* was not found|desugaring|required for" | tail -4

echo "[install]"
adb install -r Rezka.apk 2>&1 | tail -1

echo "[run] vid=$VID h=$H"
adb shell "am force-stop di.rezka" 2>/dev/null
adb logcat -c 2>/dev/null
adb shell "am start -a android.intent.action.VIEW \
  -d 'http://127.0.0.1:8080/api/yt/mpd?vid=$VID&h=$H' -n di.rezka/.PlayerActivity" >/dev/null 2>&1

sleep 15
echo "[log]"
adb logcat -d 2>/dev/null \
  | grep -iE "rezka|exoplayer|dash|androidruntime|FATAL|MediaCodec|AudioTrack|decoder|ExoPlayback|error" \
  | grep -viE "DexOpt|not found, referenced|Could not find method" \
  | tail -30
