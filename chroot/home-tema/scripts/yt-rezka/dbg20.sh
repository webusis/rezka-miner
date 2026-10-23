#!/bin/sh
cd /home/tema
{
python3 - <<'PYEOF'
import json, urllib.request
d = json.load(open('/tmp/meta.json'))
rf = d['requested_formats']
vurl = [f['url'] for f in rf if f.get('vcodec')][0]
aurl = [f['url'] for f in rf if f.get('acodec')][0]
UA = {'User-Agent': 'Mozilla/5.0'}
def get(url, rng):
    req = urllib.request.Request(url, headers=dict(UA, Range=rng))
    return urllib.request.urlopen(req, timeout=60).read()

def find_sidx(data):
    off = 0
    while off + 8 <= len(data):
        size = int.from_bytes(data[off:off+4], 'big')
        if data[off+4:off+8] == b'sidx':
            return off
        if size < 8: break
        off += size
    return None

def init_and_mid(url, probe):
    head = get(url, 'bytes=0-65535')
    so = find_sidx(head)
    init = head[:so] if so else head
    r = get(url, 'bytes=%d-%d' % (probe, probe + 32767))
    i = r.find(b'moof')
    start = i - 4 if i > 0 else 0
    mid = r[start:] if i > 0 else r
    return init, mid

vinit, vmid = init_and_mid(vurl, 53366838)
ainit, amid = init_and_mid(aurl, 53366838)
print('video: init=%d mid=%d head=%s' % (len(vinit), len(vmid), vmid[:8].hex()))
print('audio: init=%d mid=%d head=%s' % (len(ainit), len(amid), amid[:8].hex()))
open('/home/tema/p20v.mp4', 'wb').write(vinit + vmid[:2097152])
open('/home/tema/p20a.mp4', 'wb').write(ainit + amid[:1048576])
print('p20v.mp4 / p20a.mp4 записаны')
PYEOF
echo "=== ffprobe обоих ==="
ffprobe -hide_banner -loglevel error -show_entries stream=codec_name,start_time -of default=nw=1 /home/tema/p20v.mp4 2>&1 | head -4
ffprobe -hide_banner -loglevel error -show_entries stream=codec_name,start_time -of default=nw=1 /home/tema/p20a.mp4 2>&1 | head -4
echo "=== ffmpeg: p20v+p20a -> mpegts ==="
start=$(date +%s)
timeout 30 ffmpeg -hide_banner -loglevel warning -i /home/tema/p20v.mp4 -i /home/tema/p20a.mp4 -c copy -f mpegts - 2>/home/tema/p20.err | head -c 512 > /home/tema/p20.ts
echo "el=$(( $(date +%s) - start ))s bytes=$(wc -c < /home/tema/p20.ts)"
od -A x -t x1z /home/tema/p20.ts | head -1
tail -6 /home/tema/p20.err
echo "=== DONE $(date) ==="
} > /home/tema/dbg20_report.txt 2>&1
echo RC=$?; tail -30 /home/tema/dbg20_report.txt