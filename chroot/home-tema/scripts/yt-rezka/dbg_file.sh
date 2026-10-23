#!/bin/sh
cd /home/tema
{
python3 - <<'PYEOF'
import json, urllib.request
d = json.load(open('/tmp/meta.json'))
rf = d['requested_formats']
vurl = [f['url'] for f in rf if f.get('vcodec')][0]
UA = {'User-Agent': 'Mozilla/5.0'}
def get(url, rng):
    req = urllib.request.Request(url, headers=dict(UA, Range=rng))
    return urllib.request.urlopen(req, timeout=60).read()
init = get(vurl, 'bytes=0-8043')
mid = get(vurl, 'bytes=53366838-503366837')
open('/home/tema/part.mp4', 'wb').write(init + mid)
print('part.mp4:', len(init) + len(mid), 'байт')
PYEOF
echo "=== ffmpeg: файл с середины, демux+null ==="
start=$(date +%s)
timeout 30 ffmpeg -hide_banner -loglevel warning -i /home/tema/part.mp4 -t 3 -f null - 2>/home/tema/part.err
echo "rc=$? el=$(( $(date +%s) - start ))s"
tail -5 /home/tema/part.err
echo "=== ffmpeg: файл с середины -> mpegts ==="
start=$(date +%s)
timeout 30 ffmpeg -hide_banner -loglevel warning -i /home/tema/part.mp4 -t 3 -c copy -f mpegts - 2>/home/tema/part2.err | head -c 512 > /home/tema/part.ts
echo "rc=$? el=$(( $(date +%s) - start ))s bytes=$(wc -c < /home/tema/part.ts)"
od -A x -t x1z /home/tema/part.ts | head -1
tail -3 /home/tema/part2.err
echo "=== DONE $(date) ==="
} > /home/tema/dbg13_report.txt 2>&1