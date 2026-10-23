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

def marks(data, base):
    res = []
    for m in (b'moof', b'mdat', b'sidx', b'moov'):
        pos = 0
        while True:
            i = data.find(m, pos)
            if i < 0: break
            res.append((base + i, m.decode()))
            pos = i + 1
    return res

head = get(vurl, 'bytes=0-65535')
print('=== начало файла (0-64K): боксы ===')
off = 0
while off + 8 <= len(head):
    size = int.from_bytes(head[off:off+4], 'big')
    typ = head[off+4:off+8]
    if size == 1:
        size = int.from_bytes(head[off+8:off+16], 'big')
    if size < 8 or off + size > len(head): break
    print('@%8d %-4s size=%d' % (off, typ.decode('latin1'), size))
    off += size

print()
print('=== маркеры moof/mdat в начале ===')
for off, m in marks(head, 0):
    print('@%d %s' % (off, m))

print()
for probe in (53360000, 53366000, 53366838, 53367000):
    data = get(vurl, 'bytes=%d-%d' % (probe, probe + 8191))
    ms = marks(data, probe)
    print('probe@%d: %s' % (probe, ms[:6] if ms else 'НЕТ маркеров'))
PYEOF
echo "=== DONE $(date) ==="
} > /home/tema/dbg18_report.txt 2>&1
echo RC=$?; tail -40 /home/tema/dbg18_report.txt