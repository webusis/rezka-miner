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

init_full = get(vurl, 'bytes=0-8043')          # ftyp+moov+sidx (полный init, с sidx)
seg0_full = get(vurl, 'bytes=8044-27671')      # moof#0+mdat#0
mid = get(vurl, 'bytes=53374882-55411625')     # 2МБ с мооф#600 (ПРАВИЛЬНЫЙ офсет)
open('/home/tema/p26.mp4', 'wb').write(init_full + seg0_full)
print('p26.mp4 (init_full+сегмент#0):', len(init_full) + len(seg0_full))
open('/home/tema/p27.mp4', 'wb').write(init_full + mid)
print('p27.mp4 (init_full + середина с мооф#600):', len(init_full) + len(mid))
PYEOF
echo "=== p26 (init_full+сегмент#0) -> mpegts ==="
start=$(date +%s)
timeout 15 ffmpeg -hide_banner -loglevel error -i /home/tema/p26.mp4 -c copy -f mpegts - 2>/home/tema/p26.err | head -c 512 > /home/tema/p26.ts
echo "el=$(( $(date +%s) - start ))s bytes=$(wc -c < /home/tema/p26.ts)"
od -A x -t x1z /home/tema/p26.ts | head -1
tail -3 /home/tema/p26.err
echo "=== p27 (init_full + середина с мооф#600) -> mpegts ==="
start=$(date +%s)
timeout 15 ffmpeg -hide_banner -loglevel error -i /home/tema/p27.mp4 -c copy -f mpegts - 2>/home/tema/p27.err | head -c 512 > /home/tema/p27.ts
echo "el=$(( $(date +%s) - start ))s bytes=$(wc -c < /home/tema/p27.ts)"
od -A x -t x1z /home/tema/p27.ts | head -1
tail -3 /home/tema/p27.err
echo "=== DONE $(date) ==="
} > /home/tema/dbg25_report.txt 2>&1
echo RC=$?; tail -25 /home/tema/dbg25_report.txt