#!/bin/sh
cd /home/tema
{
echo "=== ресолв: web vs android (тайминги) ==="
start=$(date +%s)
timeout 60 yt-dlp --no-warnings -J -f "bv*[vcodec^=avc1][height<=480]+ba[ext=m4a]/bv*[vcodec^=avc1][height<=720]+ba[ext=m4a]" "https://www.youtube.com/watch?v=lhqABmcwedw" > /tmp/meta_web.json 2>/tmp/meta_web.err
echo "web: rc=$? t=$(( $(date +%s) - start ))s"
start=$(date +%s)
timeout 60 yt-dlp --no-warnings --extractor-args "youtube:player_client=android" -J -f "bv*[vcodec^=avc1][height<=480]+ba[ext=m4a]/bv*[vcodec^=avc1][height<=720]+ba[ext=m4a]" "https://www.youtube.com/watch?v=lhqABmcwedw" > /tmp/meta_and.json 2>/tmp/meta_and.err
echo "android: rc=$? t=$(( $(date +%s) - start ))s"
python3 - <<'PYEOF'
import json
for name in ('web', 'and'):
    try:
        d = json.load(open('/tmp/meta_%s.json' % name))
        rf = d.get('requested_formats') or []
        ids = [f.get('format_id') for f in rf]
        print(name, 'formats:', ids)
    except Exception as e:
        print(name, 'err:', e)
PYEOF
echo "=== seek 600s через sidx ==="
python3 - <<'PYEOF'
import json, urllib.request, struct, os, threading, subprocess, time, select
d = json.load(open('/tmp/meta.json'))
rf = d['requested_formats']
vurl = [f['url'] for f in rf if f.get('vcodec')][0]
aurl = [f['url'] for f in rf if f.get('acodec')][0]
UA = {'User-Agent': 'Mozilla/5.0'}

def get(url, rng):
    req = urllib.request.Request(url, headers=dict(UA, Range=rng))
    return urllib.request.urlopen(req, timeout=40).read()

def parse_boxes(data):
    off, boxes, last_end = 0, [], 0
    while off + 8 <= len(data):
        size = int.from_bytes(data[off:off+4], 'big')
        typ = data[off+4:off+8]
        if size == 1:
            size = int.from_bytes(data[off+8:off+16], 'big'); hdr = 16
        else:
            hdr = 8
        if size < hdr or off + size > len(data): break
        boxes.append((typ.decode('latin1'), off, size))
        off += size
    return boxes

def sidx_info(data):
    """ищем sidx-бокс, возвращаем (init_end, [(pts_sec, moof_off)])"""
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
            timescale = int.from_bytes(b[4:8], 'big') or 1
            if ver == 0:
                earliest = int.from_bytes(b[8:12], 'big')
                first_off = int.from_bytes(b[12:16], 'big')
                refs = int.from_bytes(b[16:18], 'big'); p = 18
            else:
                earliest = int.from_bytes(b[8:16], 'big')
                first_off = int.from_bytes(b[16:24], 'big')
                refs = int.from_bytes(b[24:26], 'big'); p = 26
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

print('— видео боксы:', ' '.join(t for t,_,_ in parse_boxes(get(vurl, 'bytes=0-262143'))), flush=True)
print('— аудио боксы:', ' '.join(t for t,_,_ in parse_boxes(get(aurl, 'bytes=0-262143'))), flush=True)

T = 600
vi_end, vsub = sidx_info(get(vurl, 'bytes=0-65535'))
ai_end, asub = sidx_info(get(aurl, 'bytes=0-65535'))
print('video init_end=%d subs=%d, первый sub: %s' % (vi_end, len(vsub), vsub[:1]), flush=True)
print('audio init_end=%d subs=%d, первый sub: %s' % (ai_end, len(asub), asub[:1]), flush=True)

def pick(subs, t):
    best = subs[0]
    for s in subs:
        if s[0] <= t + 1:
            best = s
        else:
            break
    return best

vs = pick(vsub, T); as_ = pick(asub, T)
print('выбрано: vid moof @%.1fs off=%d | aud moof @%.1fs off=%d' % (vs[0], vs[1], as_[0], as_[1]), flush=True)

def feed_range(url, first, second, fpath, tag):
    try:
        fd = os.open(fpath, os.O_WRONLY)
        # first = (a,b) или None
        if first:
            os.write(fd, get(url, 'bytes=%d-%d' % first))
        r = urllib.request.urlopen(urllib.request.Request(url, headers=dict(UA, Range='bytes=%d-' % second)), timeout=40)
        while True:
            b = r.read(65536)
            if not b: break
            os.write(fd, b)
        os.close(fd)
        print(tag, 'feed done', flush=True)
    except Exception as e:
        print(tag, 'ERR:', e, flush=True)

os.system('rm -f /home/tema/v.fifo /home/tema/a.fifo; mkfifo /home/tema/v.fifo /home/tema/a.fifo')
t0 = time.time()
p = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-thread_queue_size', '1024',
                      '-i', '/home/tema/v.fifo', '-i', '/home/tema/a.fifo',
                      '-c', 'copy', '-f', 'mpegts', '-'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
tv = threading.Thread(target=feed_range, args=(vurl, (0, vi_end-1), vs[1], '/home/tema/v.fifo', 'video'), daemon=True)
ta = threading.Thread(target=feed_range, args=(aurl, (0, ai_end-1), as_[1], '/home/tema/a.fifo', 'audio'), daemon=True)
tv.start(); ta.start()
fl = select.poll(); fl.register(p.stdout, select.POLLIN)
if fl.poll(20000):
    head = os.read(p.stdout.fileno(), 512)
    print('первый TS через %.1f с, head=%s' % (time.time()-t0, head[:4].hex()), flush=True)
time.sleep(5)
p.kill(); tv.join(1); ta.join(1)
err = p.stderr.read().decode('utf-8','replace')
print('ffmpeg err tail:', err[-300:], flush=True)
print('DONE seek-тест', flush=True)
PYEOF
echo "=== DONE $(date) ==="
} > /home/tema/dbg9_report.txt 2>&1