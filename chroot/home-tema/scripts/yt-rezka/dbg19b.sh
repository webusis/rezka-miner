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

MOOF = 53374886 - 4   # начало бокса moof#600 (позиция 'moof' - 4 байта size)
init = get(vurl, 'bytes=0-739')          # ftyp+moov, БЕЗ sidx
mid = get(vurl, 'bytes=%d-%d' % (MOOF, MOOF + 2097152 - 1))
print('init=%d mid=%d' % (len(init), len(mid)))
print('mid head:', mid[:16].hex(), '(ожидаем size+moof)')
open('/home/tema/p19.mp4', 'wb').write(init + mid)
print('p19.mp4:', len(init) + len(mid))
PYEOF
echo "=== ffprobe p19.mp4 (если есть) ==="
command -v ffprobe >/dev/null 2>&1 && ffprobe -hide_banner -loglevel error -show_entries stream=codec_name,width,height,start_time,duration -of default=nw=1 /home/tema/p19.mp4 2>&1 | head -10 || echo "ffprobe нет"
echo "=== ffmpeg: файл init(no sidx)+середина -> mpegts ==="
start=$(date +%s)
timeout 30 ffmpeg -hide_banner -loglevel warning -i /home/tema/p19.mp4 -t 2 -c copy -f mpegts - 2>/home/tema/p19.err | head -c 512 > /home/tema/p19.ts
echo "rc=$? el=$(( $(date +%s) - start ))s bytes=$(wc -c < /home/tema/p19.ts)"
od -A x -t x1z /home/tema/p19.ts | head -1
tail -4 /home/tema/p19.err
echo "=== DONE $(date) ==="
} > /home/tema/dbg19_report.txt 2>&1
echo RC=$?; tail -30 /home/tema/dbg19_report.txt