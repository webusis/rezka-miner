#!/bin/sh
cd /home/tema
{
echo "=== лог сервиса: последние 15 ==="
tail -15 /home/tema/rezka-yt/yt_service.log
echo
echo "=== ищем последний vid (не мой curl) ==="
V=$(tail -30 /home/tema/rezka-yt/yt_service.log | grep -oE 'vid=[A-Za-z0-9_-]{6,}' | tail -1 | cut -d= -f2)
echo "vid=$V"
echo
echo "=== мета для $V ==="
python3 -c "
import sys
sys.path.insert(0, '/home/tema/rezka-yt')
import yt_service as y
m = y._yt_meta('$V', 480)
if not m:
    print('МЕТА НЕТ')
else:
    print('total=%s dur=%s' % (m['total'], m['dur']))
    print('vsize=%s asize=%s' % (m.get('vsize'), m.get('asize')))
    print('vurl:', m['vurl'][:90])
    print('aurl:', m['aurl'][:90])
    open('/tmp/av.txt','w').write(m['vurl']+'\n'+m['aurl']+'\n')
" 2>&1 | head -6
echo
echo "=== качаются ли ссылки напрямую (по 300КБ, 20с) ==="
VURL=$(sed -n 1p /tmp/av.txt); AURL=$(sed -n 2p /tmp/av.txt)
curl -s -m 20 -H 'Range: bytes=0-300000' "$VURL" -o /tmp/vx.bin -w 'видео: code=%{http_code} bytes=%{size_download}\n'
curl -s -m 20 -H 'Range: bytes=0-300000' "$AURL" -o /tmp/ax.bin -w 'аудио: code=%{http_code} bytes=%{size_download}\n'
echo "--- первые байты видео ---"; od -A x -t x1z /tmp/vx.bin 2>/dev/null | head -1
echo "--- первые байты аудио ---"; od -A x -t x1z /tmp/ax.bin 2>/dev/null | head -1
echo "=== DONE $(date) ==="
} > /home/tema/aud_report.txt 2>&1
cat /home/tema/aud_report.txt