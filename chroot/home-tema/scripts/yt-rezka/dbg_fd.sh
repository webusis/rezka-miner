#!/bin/sh
cd /home/tema
{
echo "=== парсим первые боксы видео ==="
python3 - <<'PYEOF'
import json, urllib.request, struct
d = json.load(open('/tmp/meta.json'))
rf = d['requested_formats']
v = [f['url'] for f in rf if f.get('vcodec')][0]
req = urllib.request.Request(v, headers={'Range': 'bytes=0-262143', 'User-Agent': 'Mozilla/5.0'})
r = urllib.request.urlopen(req, timeout=30)
data = r.read()
print('получено байт:', len(data), 'status:', r.status if hasattr(r,'status') else '?')
off = 0
boxes = []
while off + 8 <= len(data) and len(boxes) < 12:
    size = struct.unpack('>I', data[off:off+4])[0]
    typ = data[off+4:off+8].decode('latin1')
    boxes.append('%s@%d(%d)' % (typ, off, size))
    if size < 8: break
    off += size
print('боксы:', ' '.join(boxes))
print('первый 12 байт:', data[:12].hex())
PYEOF
echo "=== python -> pipe -> ffmpeg fd -> mpegts ==="
python3 - <<'PYEOF'
import os, threading, subprocess, urllib.request, json, time, signal
d = json.load(open('/tmp/meta.json'))
rf = d['requested_formats']
vurl = [f['url'] for f in rf if f.get('vcodec')][0]
aurl = [f['url'] for f in rf if f.get('acodec')][0]

def feed(url, w, tag):
    try:
        req = urllib.request.Request(url, headers={'Range': 'bytes=0-', 'User-Agent': 'Mozilla/5.0'})
        r = urllib.request.urlopen(req, timeout=40)
        n = 0
        while True:
            b = r.read(65536)
            if not b: break
            w.write(b)
            n += len(b)
        print(tag, 'EOF, байт:', n, flush=True)
    except Exception as e:
        print(tag, 'ERR:', e, flush=True)
    finally:
        try: w.close()
        except Exception: pass

rv, wv = os.pipe()
ra, wa = os.pipe()
print('fds: v=(%d,%d) a=(%d,%d)' % (rv, wv, ra, wa), flush=True)
tv = threading.Thread(target=feed, args=(vurl, wv, 'video'), daemon=True)
ta = threading.Thread(target=feed, args=(aurl, wa, 'audio'), daemon=True)
tv.start(); ta.start()
p = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'warning',
                      '-i', 'fd:%d' % rv, '-i', 'fd:%d' % ra,
                      '-c', 'copy', '-f', 'mpegts', '-'],
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, pass_fds=(rv, ra))
t0 = time.time()
got = False
import select
fl = select.poll()
fl.register(p.stdout, select.POLLIN)
if fl.poll(20000):
    head = os.read(p.stdout.fileno(), 512)
    if head:
        got = True
        print('первый mpegts байт через %.1f с, head: %s' % (time.time()-t0, head[:4].hex()), flush=True)
time.sleep(6)
p.kill()
tv.join(1); ta.join(1)
err = p.stderr.read().decode('utf-8', 'replace')
print('ffmpeg err tail:', err[-300:], flush=True)
PYEOF
echo "=== DONE $(date) ==="
} > /home/tema/dbg7_report.txt 2>&1