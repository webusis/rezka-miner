#!/bin/sh
cd /home/tema
{
python3 - <<'PYEOF'
import json, urllib.request, os, threading, subprocess, time, select
d = json.load(open('/tmp/meta.json'))
rf = d['requested_formats']
vurl = [f['url'] for f in rf if f.get('vcodec')][0]
aurl = [f['url'] for f in rf if f.get('acodec')][0]
asize = [f.get('filesize') or f.get('filesize_approx') for f in rf if f.get('acodec')][0]
dur = d['duration']
UA = {'User-Agent': 'Mozilla/5.0'}
T0 = time.time()
def log(s): print('[%6.1f] %s' % (time.time()-T0, s), flush=True)
def get(url, rng):
    req = urllib.request.Request(url, headers=dict(UA, Range=rng))
    return urllib.request.urlopen(req, timeout=60).read()

def sidx_end(data):
    off = 0
    while off + 8 <= len(data):
        size = int.from_bytes(data[off:off+4], 'big')
        if data[off+4:off+8] == b'sidx':
            return off + size
        if size < 8: break
        off += size
    return 1024

# видео: init(ftyp+moov+sidx) + данные с мооф#600
init_v = get(vurl, 'bytes=0-8043')
# аудио: init только до конца sidx (пару КБ), середина — по маркеру мооф возле ~599с
head_a = get(aurl, 'bytes=0-65535')
se_a = sidx_end(head_a)
init_a = head_a[:se_a]
astart = max(0, int(asize * 599.2 / dur) - 65536)
probe_a = get(aurl, 'bytes=%d-%d' % (astart, astart + 65535))
i = probe_a.find(b'moof')
astart2 = astart + (i - 4 if i > 0 else 0)
print('init_v=%d init_a=%d asize=%d astart=%d -> мооф@%d' % (len(init_v), len(init_a), asize, astart, astart2), flush=True)

os.system('rm -f /home/tema/v.fifo /home/tema/a.fifo; mkfifo /home/tema/v.fifo /home/tema/a.fifo')
p = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-thread_queue_size', '2048',
                      '-i', '/home/tema/v.fifo', '-i', '/home/tema/a.fifo',
                      '-c', 'copy', '-f', 'mpegts', '-'],
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
log('ffmpeg запущен')

def feed(url, init, start, fpath, tag, nbytes):
    try:
        log('%s: открываю fifo' % tag)
        fd = os.open(fpath, os.O_WRONLY)
        os.write(fd, init)
        log('%s: init=%d, GET %d-...' % (tag, len(init), start))
        r = urllib.request.urlopen(urllib.request.Request(url, headers=dict(UA, Range='bytes=%d-' % start)), timeout=60)
        n = 0
        while n < nbytes:
            b = r.read(65536)
            if not b: break
            os.write(fd, b)
            n += len(b)
        os.close(fd)
        log('%s: feed done (%d)' % (tag, n))
    except Exception as e:
        log('%s ERR: %s' % (tag, e))

tv = threading.Thread(target=feed, args=(vurl, init_v, 53374882, '/home/tema/v.fifo', 'video', 1572864), daemon=True)
ta = threading.Thread(target=feed, args=(aurl, init_a, astart2, '/home/tema/a.fifo', 'audio', 838860), daemon=True)
tv.start(); ta.start()
fl = select.poll(); fl.register(p.stdout, select.POLLIN)
got = False
for i in range(12):
    r = fl.poll(5000)
    if r:
        head = os.read(p.stdout.fileno(), 512)
        log('*** TS ПОЛУЧЕН за %.2f с, head=%s ***' % (time.time()-T0, head[:4].hex()))
        got = True
        break
    if p.poll() is not None:
        log('ffmpeg ВЫШЕЛ rc=%d' % p.returncode)
        break
    log('ждём mpegts... (%d с)' % int(time.time()-T0))
time.sleep(2)
if not got:
    p.kill()
tv.join(2); ta.join(2)
err = p.stderr.read().decode('utf-8','replace')
log('ffmpeg err tail: %s' % err[-250:])
PYEOF
echo "=== DONE $(date) ==="
} > /home/tema/dbg26b_report.txt 2>&1
echo RC=$?; tail -25 /home/tema/dbg26b_report.txt