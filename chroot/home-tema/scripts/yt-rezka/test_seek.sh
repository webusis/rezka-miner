#!/bin/sh
# Тест: ffmpeg seek по dash-URL (прыжок на 10-ю минуту) — быстро ли идёт
cd /home/tema
{
echo "=== START $(date) ==="
python3 - <<'PYEOF' > /home/tema/urls.sh
import json
d = json.load(open('/tmp/meta.json'))
rf = d['requested_formats']
v = [f['url'] for f in rf if f.get('vcodec')][0]
a = [f['url'] for f in rf if f.get('acodec')][0]
print("VURL='%s'" % v.replace("'", "'\\''"))
print("AURL='%s'" % a.replace("'", "'\\''"))
PYEOF
. /home/tema/urls.sh
echo "=== seek 600s (прыжок на 10-ю минуту) ==="
start=$(date +%s)
timeout 60 ffmpeg -hide_banner -loglevel error -ss 600 -i "$VURL" -ss 600 -i "$AURL" -c copy -f mpegts - 2>/home/tema/ff.err | head -c 512 > /home/tema/seek.bin
rc=$?
el=$(( $(date +%s) - start ))
echo "rc=$rc время=$el с, байт=$(wc -c < /home/tema/seek.bin)"
od -A x -t x1z /home/tema/seek.bin | head -2
echo "=== старт без seek ==="
start=$(date +%s)
timeout 60 ffmpeg -hide_banner -loglevel error -i "$VURL" -i "$AURL" -c copy -f mpegts - 2>/home/tema/ff2.err | head -c 512 > /home/tema/start.bin
el=$(( $(date +%s) - start ))
echo "время=$el с, байт=$(wc -c < /home/tema/start.bin)"
echo "=== ff.err хвост ==="
tail -2 /home/tema/ff.err 2>/dev/null
} > /home/tema/seek_report.txt 2>&1