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

init = get(vurl, 'bytes=0-739')
seg0 = get(vurl, 'bytes=8044-27671')                      # moof#0(1916)+mdat#0(17712)
open('/home/tema/p24.mp4', 'wb').write(init + seg0)
print('p24.mp4 (init+сегмент#0):', 740 + len(seg0))

seg600 = get(vurl, 'bytes=53374882-53795973')             # moof#600(1460)+mdat#600(419633)
b = bytearray(seg600)
# патч mfhd: sequence number -> 0
i = b.find(b'mfhd')
if i > 0:
    print('mfhd@%d: seq %d -> 0' % (i, int.from_bytes(b[i+8:i+12], 'big')))
    b[i+8:i+12] = (0).to_bytes(4, 'big')
# патч tfdt: baseMediaDecodeTime -> 0 (v0: int32, v1: int64)
i = b.find(b'tfdt')
if i > 0:
    ver = b[i+4]
    if ver == 1:
        print('tfdt@%d (v1): %d -> 0' % (i, int.from_bytes(b[i+8:i+16], 'big')))
        b[i+8:i+16] = (0).to_bytes(8, 'big')
    else:
        print('tfdt@%d (v0): %d -> 0' % (i, int.from_bytes(b[i+8:i+12], 'big')))
        b[i+8:i+12] = (0).to_bytes(4, 'big')
open('/home/tema/p25.mp4', 'wb').write(init + bytes(b))
print('p25.mp4 (init+сегмент#600 с патчем seq/tfdt=0):', 740 + len(b))
PYEOF
echo "=== p24 (init+сегмент#0) -> mpegts ==="
start=$(date +%s)
timeout 15 ffmpeg -hide_banner -loglevel error -i /home/tema/p24.mp4 -c copy -f mpegts - 2>/home/tema/p24.err | head -c 512 > /home/tema/p24.ts
echo "el=$(( $(date +%s) - start ))s bytes=$(wc -c < /home/tema/p24.ts)"
od -A x -t x1z /home/tema/p24.ts | head -1
tail -3 /home/tema/p24.err
echo "=== p25 (init+сегмент#600 патч) -> mpegts с -output_ts_offset 599.2 ==="
start=$(date +%s)
timeout 15 ffmpeg -hide_banner -loglevel error -i /home/tema/p25.mp4 -output_ts_offset 599.2 -c copy -f mpegts - 2>/home/tema/p25.err | head -c 512 > /home/tema/p25.ts
echo "el=$(( $(date +%s) - start ))s bytes=$(wc -c < /home/tema/p25.ts)"
od -A x -t x1z /home/tema/p25.ts | head -1
tail -3 /home/tema/p25.err
echo "=== DONE $(date) ==="
} > /home/tema/dbg24_report.txt 2>&1
echo RC=$?; tail -30 /home/tema/dbg24_report.txt