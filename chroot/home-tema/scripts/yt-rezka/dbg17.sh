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

# 1. moof@53366838: парсим трейт-боксы: есть ли base_data_offset в trun/tfhd?
m = get(vurl, 'bytes=53366838-53368837')
print('moof[600] first bytes:', m[:24].hex())
off = 0
while off + 8 <= len(m):
    size = int.from_bytes(m[off:off+4], 'big')
    typ = m[off+4:off+8]
    if size < 8 or off + size > len(m): break
    if typ in (b'traf', b'tfhd', b'tfdt', b'trun', b'mfhd'):
        flags = ''
        if typ == b'tfhd' and size >= 12:
            flags = 'flags=%08x' % int.from_bytes(m[off+8:off+12], 'big')
        if typ == b'trun' and size >= 12:
            flags = 'flags=%08x' % int.from_bytes(m[off+8:off+12], 'big')
        print('%s@%d size=%d %s' % (typ.decode('latin1'), off, size, flags))
    off += size

# 2. файл-тест: ftyp+moov (без sidx) + середина 3МБ
init = get(vurl, 'bytes=0-739')
mid = get(vurl, 'bytes=53366838-53866837')
open('/home/tema/p17.mp4', 'wb').write(init + mid)
print('p17.mp4:', len(init) + len(mid))
PYEOF
echo "=== ffmpeg: файл init+середина -> mpegts ==="
start=$(date +%s)
timeout 25 ffmpeg -hide_banner -loglevel warning -i /home/tema/p17.mp4 -t 2 -c copy -f mpegts - 2>/home/tema/p17.err | head -c 512 > /home/tema/p17.ts
echo "rc=$? el=$(( $(date +%s) - start ))s bytes=$(wc -c < /home/tema/p17.ts)"
od -A x -t x1z /home/tema/p17.ts | head -1
tail -4 /home/tema/p17.err
echo "=== DONE $(date) ==="
} > /home/tema/dbg17_report.txt 2>&1
echo RC=$?; tail -20 /home/tema/dbg17_report.txt