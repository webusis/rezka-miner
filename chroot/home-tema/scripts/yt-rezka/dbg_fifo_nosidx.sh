#!/bin/sh
cd /home/tema
{
python3 - <<'PYEOF'
import json, urllib.request, os, threading, subprocess, time, select
d = json.load(open('/tmp/meta.json'))
rf = d['requested_formats']
vurl = [f['url'] for f in rf if f.get('vcodec')][0]
aurl = [f['url'] for f in rf if f.get('acodec')][0]
UA = {'User-Agent': 'Mozilla/5.0'}
T0 = time.time()
def log(s): print('[%6.1f] %s' % (time.time()-T0, s), flush=True)

def get(url, rng):
    req = urllib.request.Request(url, headers=dict(UA, Range=rng))
    return urllib.request.urlopen(req, timeout=60).read()

# init БЕЗ sidx: ftyp(28)+moov(712)=740 байт; данные с moof@599.2с (53366838)
vinit = get(vurl, 'bytes=0-739')
ainit = get(aurl, 'bytes=0-739')
log('init без sidx: v=%d a=%d' % (len(vinit), len(ainit)))

os.system('rm -f /home/tema/v.fifo /home/tema/a.fifo; mkfifo /home/tema/v.fifo /home/tema/a.fifo')
p = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-thread_queue_size', '2048',
                      '-i', '/home/tema/v.fifo', '-i', '/home/tema/a.fifo',
                      '-c', 'copy', '-f', 'mpegts', '-'],
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
log('ffmpeg запущен')

def feed(url, init, second, fpath, tag):
    try:
        log('%s: открываю fifo' % tag)
        fd = os.open(fpath, os.O_WRONLY)
        os.write(fd, init)
        log('%s: init записан, GET bytes=%d-' % (tag, second))
        r = urllib.request.urlopen(urllib.request.Request(url, headers=dict(UA, Range='bytes=%d-' % second)), timeout=60)
        n = len(init)
        while True:
            b = r.read(65536)
            if not b: break
            os.write(fd, b)
            n += len(b)
        os.close(fd)
        log('%s: feed done (%d)' % (tag, n))
    except Exception as e:
        log('%s ERR: %s' % (tag, e))

tv = threading.Thread(target=feed, args=(vurl, vinit, 53366838, '/home/tema/v.fifo', 'video'), daemon=True)
ta = threading.Thread(target=feed, args=(aurl, ainit, 53366838, '/home/tema/a.fifo', 'audio'), daemon=True)
tv.start(); ta.start()
fl = select.poll(); fl.register(p.stdout, select.POLLIN)
for i in range(14):
    r = fl.poll(5000)
    if r:
        head = os.read(p.stdout.fileno(), 512)
        log('ПОЛУЧЕН первый TS через %.1f с, head=%s' % (time.time()-T0, head[:4].hex()))
        break
    log('ждём mpegts... (%d с)' % int(time.time()-T0))
    if p.poll() is not None:
        log('ffmpeg ВЫШЕЛ rc=%d' % p.returncode)
        break
time.sleep(3)
p.kill(); tv.join(2); ta.join(2)
err = p.stderr.read().decode('utf-8','replace')
log('ffmpeg err tail: %s' % err[-200:])
PYEOF
echo "=== DONE $(date) ==="
} > /home/tema/dbg16_report.txt 2>&1
echo RC=$?; tail -20 /home/tema/dbg16_report.txt