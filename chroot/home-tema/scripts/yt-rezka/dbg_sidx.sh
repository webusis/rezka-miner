#!/bin/sh
cd /home/tema
{
python3 - <<'PYEOF'
import json, urllib.request
d = json.load(open('/tmp/meta.json'))
rf = d['requested_formats']
vurl = [f['url'] for f in rf if f.get('vcodec')][0]
req = urllib.request.Request(vurl, headers={'Range': 'bytes=0-65535', 'User-Agent': 'Mozilla/5.0'})
data = urllib.request.urlopen(req, timeout=40).read()
off = 0
while off + 8 <= len(data):
    size = int.from_bytes(data[off:off+4], 'big')
    typ = data[off+4:off+8]
    if typ == b'sidx':
        print('sidx @%d size=%d' % (off, size))
        print('hex первых 96 байт sidx:')
        print(data[off+8:off+8+96].hex(' '))
        ver = data[off+8]
        print('version:', ver)
        print('after version flags:', data[off+9:off+12].hex())
        print('reference_ID:', int.from_bytes(data[off+12:off+16], 'big'))
        print('timescale:', int.from_bytes(data[off+16:off+20], 'big'))
        if ver == 0:
            print('earliest:', int.from_bytes(data[off+20:off+24], 'big'))
            print('first_offset:', int.from_bytes(data[off+24:off+28], 'big'))
            print('reserved+count hex:', data[off+28:off+32].hex())
            refs = int.from_bytes(data[off+30:off+32], 'big')
        else:
            print('earliest64:', int.from_bytes(data[off+20:off+28], 'big'))
            print('first_offset64:', int.from_bytes(data[off+28:off+36], 'big'))
            refs = int.from_bytes(data[off+36:off+38], 'big')
        print('refs:', refs)
        break
    off += size
PYEOF
echo "=== DONE $(date) ==="
} > /home/tema/dbg11_report.txt 2>&1