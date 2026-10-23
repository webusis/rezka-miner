#!/bin/sh
cd /home/tema
{
rm -f /home/tema/v.fifo /home/tema/a.fifo
mkfifo /home/tema/v.fifo /home/tema/a.fifo
python3 - <<'PYEOF'
import os, threading, subprocess, urllib.request, json, time, select
d = json.load(open('/tmp/meta.json'))
rf = d['requested_formats']
vurl = [f['url'] for f in rf if f.get('vcodec')][0]
aurl = [f['url'] for f in rf if f.get('acodec')][0]

def feed(url, fpath, tag):
    try:
        req = urllib.request.Request(url, headers={'Range': 'bytes=0-', 'User-Agent': 'Mozilla/5.0'})
        r = urllib.request.urlopen(req, timeout=40)
        fd = os.open(fpath, os.O_WRONLY)
        n = 0
        while True:
            b = r.read(65536)
            if not b: break
            os.write(fd, b)
            n += len(b)
        os.close(fd)
        print(tag, 'EOF, байт:', n, flush=True)
    except Exception as e:
        print(tag, 'ERR:', e, flush=True)

t0 = time.time()
p = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'warning',
                      '-i', '/home/tema/v.fifo', '-i', '/home/tema/a.fifo',
                      '-c', 'copy', '-f', 'mpegts', '-'],
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
tv = threading.Thread(target=feed, args=(vurl, '/home/tema/v.fifo', 'video'), daemon=True)
ta = threading.Thread(target=feed, args=(aurl, '/home/tema/a.fifo', 'audio'), daemon=True)
tv.start(); ta.start()
fl = select.poll()
fl.register(p.stdout, select.POLLIN)
got = False
if fl.poll(30000):
    head = os.read(p.stdout.fileno(), 512)
    if head:
        got = True
        print('первый mpegts байт через %.1f с' % (time.time()-t0), 'head:', head[:4].hex(), flush=True)
time.sleep(8)
p.kill()
tv.join(1); ta.join(1)
err = p.stderr.read().decode('utf-8', 'replace')
print('ffmpeg err tail:', err[-250:], flush=True)
print('итог: got=%s, время до 1-го байта %.1fс' % (got, time.time()-t0), flush=True)
PYEOF
echo "=== DONE $(date) ==="
} > /home/tema/dbg8_report.txt 2>&1