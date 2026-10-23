#!/bin/sh
cd /home/tema
{
echo "=== ffmpeg version ==="
ffmpeg -version 2>&1 | head -1
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
timeout 45 ffmpeg -hide_banner -loglevel error -ss 600 -i "$VURL" -ss 600 -i "$AURL" -c copy -f mpegts - 2>/home/tema/seek.err | head -c 256 > /home/tema/seek.bin
echo "rc=$? el=$(( $(date +%s) - start ))s bytes=$(wc -c < /home/tema/seek.bin 2>/dev/null || echo missing)"
od -A x -t x1z /home/tema/seek.bin 2>/dev/null | head -2
echo "=== plain start ==="
start=$(date +%s)
timeout 45 ffmpeg -hide_banner -loglevel error -i "$VURL" -i "$AURL" -c copy -f mpegts - 2>/home/tema/start.err | head -c 256 > /home/tema/start.bin
echo "rc=$? el=$(( $(date +%s) - start ))s bytes=$(wc -c < /home/tema/start.bin 2>/dev/null || echo missing)"
echo "=== seek.err tail ==="
tail -3 /home/tema/seek.err 2>/dev/null
echo "=== start.err tail ==="
tail -3 /home/tema/start.err 2>/dev/null
echo "=== DONE $(date) ==="
} > /home/tema/seek_report.txt 2>&1