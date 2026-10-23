#!/bin/sh
cd /home/tema
{
python3 - <<'PYEOF'
import json, urllib.request, struct, os, threading, subprocess, time, select
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

def sidx_info(data):
    off = 0
    while off + 8 <= len(data):
        size = int.from_bytes(data[off:off+4], 'big')
        typ = data[off+4:off+8]
        if size == 1:
            size = int.from_bytes(data[off+8:off+16], 'big'); hdr = 16
        else:
            hdr = 8
        if size < hdr or off + size > len(data): break
        if typ == b'sidx':
            b = data[off+hdr:off+hdr+size-hdr]
            ver = b[0]
            timescale = int.from_bytes(b[8:12], 'big') or 1
            if ver == 0:
                earliest = int.from_bytes(b[12:16], 'big')
                first_off = int.from_bytes(b[16:20], 'big')
                refs = int.from_bytes(b[22:24], 'big'); p = 24
            else:
                earliest = int.from_bytes(b[12:20], 'big')
                first_off = int.from_bytes(b[20:28], 'big')
                refs = int.from_bytes(b[30:32], 'big'); p = 32
            pts = earliest; offs = first_off; subs = []
            for i in range(refs):
                if p + 12 > len(b): break
                rsz = int.from_bytes(b[p+1:p+4], 'big')
                dur = int.from_bytes(b[p+4:p+8], 'big')
                subs.append((pts / timescale, offs))
                pts += dur; offs += rsz; p += 12
            return off + size, subs
        off += size
    return off, []

def pick(subs, t):
    best = subs[0]
    for s in subs:
        if s[0] <= t + 2:
            best = s
        else:
            break
    return best

T = 600
log('качаю init видео/аудио')
vi0 = get(vurl, 'bytes=0-65535')
ai0 = get(aurl, 'bytes=0-65535')
vi_end, vsub = sidx_info(vi0)
ai_end, asub = sidx_info(ai0)
log('video init_end=%d subs=%d | audio init_end=%d subs=%d' % (vi_end, len(vsub), ai_end, len(asub)))
vs = pick(vsub, T); as_ = pick(asub, T)
log('vid moof @%.1fs off=%d | aud moof @%.1fs off=%d' % (vs[0], vs[1], as_[0], as_[1]))

os.system('rm -f /home/tema/v.fifo /home/tema/a.fifo; mkfifo /home/tema/v.fifo /home/tema/a.fifo')
p = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-thread_queue_size', '2048',
                      '-i', '/home/tema/v.fifo', '-i', '/home/tema/a.fifo',
                      '-c', 'copy', '-f', 'mpegts', '-'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
log('ffmpeg запущен')

state = {}
def feed(url, init_data, second, fpath, tag):
    try:
        state[tag] = 'open'
        fd = os.open(fpath, os.O_WRONLY)
        log('%s: fifo открыт, пишу init (%d байт)' % (tag, len(init_data)))
        os.write(fd, init_data)
        log('%s: init записан, GET bytes=%d-' % (tag, second))
        r = urllib.request.urlopen(urllib.request.Request(url, headers=dict(UA, Range='bytes=%d-' % second)), timeout=60)
        log('%s: GET ответил, TTFB done' % tag)
        n = 0
        while True:
            b = r.read(65536)
            if not b: break
            os.write(fd, b)
            n += len(b)
            if n % 2621440 == 0: log('%s: передано %d МБ' % (tag, n//1048576))
        os.close(fd)
        log('%s: feed done (%d байт)' % (tag, n))
    except Exception as e:
        log('%s ERR: %s' % (tag, e))
    finally:
        pass

tv = threading.Thread(target=feed, args=(vurl, vi0[:vi_end], vs[1], '/home/tema/v.fifo', 'video'), daemon=True)
ta = threading.Thread(target=feed, args=(aurl, ai0[:ai_end], as_[1], '/home/tema/a.fifo', 'audio'), daemon=True)
tv.start(); ta.start()
fl = select.poll(); fl.register(p.stdout, select.POLLIN)
for i in range(12):
    r = fl.poll(5000)
    if r:
        head = os.read(p.stdout.fileno(), 512)
        log('ПОЛУЧЕН первый TS через %.1f с, head=%s' % (time.time()-T0, head[:4].hex()))
        break
    log('ждём mpegts... %d сек прошло' % (time.time()-T0))
    if p.poll() is not None:
        log('ffmpeg ВЫШЕЛ rc=%d' % p.returncode)
        break
log('итог: ffmpeg alive=%s' % (p.poll() is None))
time.sleep(4)
p.kill(); tv.join(2); ta.join(2)
err = p.stderr.read().decode('utf-8','replace')
log('ffmpeg err tail: %s' % err[-350:])
PYEOF
echo "=== DONE $(date) ==="
} > /home/tema/dbg12_report.txt 2>&1