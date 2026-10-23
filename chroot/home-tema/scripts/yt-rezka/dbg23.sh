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

MOOF_S = 53374882  # начало бокса (size+moof)
moof = get(vurl, 'bytes=%d-%d' % (MOOF_S, MOOF_S + 1459))
print('moof size box:', moof[:4].hex(), 'type:', moof[4:8])

off = 0
while off + 8 <= len(moof):
    size = int.from_bytes(moof[off:off+4], 'big')
    typ = moof[off+4:off+8]
    if size < 8 or off + size > len(moof): break
    if typ in (b'traf', b'tfhd', b'tfdt', b'trun', b'mfhd'):
        extra = ''
        if typ == b'tfhd' and size >= 12:
            extra = 'flags=0x%06x' % int.from_bytes(moof[off+8:off+12], 'big')
        if typ == b'trun' and size >= 12:
            extra = 'flags=0x%06x' % int.from_bytes(moof[off+8:off+12], 'big')
        print('@%d %s size=%d %s' % (off, typ.decode('latin1'), size, extra))
    off += size

# после moof идёт mdat: маркер + размер
after = get(vurl, 'bytes=%d-%d' % (MOOF_S + 1460, MOOF_S + 1460 + 8191))
i = after.find(b'mdat')
print('mdat маркер на +%d, size box до него: %s' % (i, after[i-4:i].hex() if i >= 4 else 'нет'))
mdat_sz = int.from_bytes(after[i-4:i], 'big') if i >= 4 else None
print('mdat size =', mdat_sz)

# собираем init + ОДИН полный сегмент (moof+mdat)
init = get(vurl, 'bytes=0-739')
seg = moof + after[i-4:i-4+mdat_sz]
open('/home/tema/p23.mp4', 'wb').write(init + seg)
print('p23.mp4 = init(740) + сегмент#600 (moof %d + mdat %d) = %d' % (len(moof), mdat_sz, 740 + len(seg)))
PYEOF
echo "=== ffprobe p23 ==="
ffprobe -hide_banner -loglevel error -show_entries stream=codec_name,width,height,nb_frames,start_time,duration -of default=nw=1 /home/tema/p23.mp4 2>&1 | tail -6
echo "=== ffmpeg p23 -> null (пакеты?) ==="
timeout 15 ffmpeg -hide_banner -loglevel info -i /home/tema/p23.mp4 -t 2 -f null - 2>&1 | tail -8
echo "=== ffmpeg p23 -> mpegts ==="
start=$(date +%s)
timeout 15 ffmpeg -hide_banner -loglevel error -i /home/tema/p23.mp4 -c copy -f mpegts - 2>/home/tema/p23.err | head -c 512 > /home/tema/p23.ts
echo "el=$(( $(date +%s) - start ))s bytes=$(wc -c < /home/tema/p23.ts)"
od -A x -t x1z /home/tema/p23.ts | head -1
tail -4 /home/tema/p23.err
echo "=== DONE $(date) ==="
} > /home/tema/dbg23_report.txt 2>&1
echo RC=$?; tail -40 /home/tema/dbg23_report.txt