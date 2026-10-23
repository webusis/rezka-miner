#!/bin/sh
cd /home/tema
{
echo "=== load и процессы ==="
uptime
ps -ef | grep -E '[f]fmpeg' | grep -v defunct | awk '{print $2, $9, $10}'
echo
echo "=== ссылки из меты ==="
python3 -c "
import sys
sys.path.insert(0, '/home/tema/rezka-yt')
import yt_service as y
m = y._yt_meta('hQ_Z-10dXSE', 480)
open('/tmp/av2.txt','w').write(m['vurl']+'\n'+m['aurl']+'\n')
print('ok')
" 2>&1 | head -2
VURL=$(sed -n 1p /tmp/av2.txt); AURL=$(sed -n 2p /tmp/av2.txt)
echo
echo "=== ПОЛНЫЙ GET без Range (как качалка): 30с ==="
curl -s -o /tmp/fv.bin -w 'видео full: code=%{http_code} bytes=%{size_download} spd=%{speed_download}B/s\n' -m 30 "$VURL"
curl -s -o /tmp/fa.bin -w 'аудио full: code=%{http_code} bytes=%{size_download} spd=%{speed_download}B/s\n' -m 30 "$AURL"
echo "--- первые байты аудио full ---"
od -A x -t x1z /tmp/fa.bin 2>/dev/null | head -1
echo "--- первые байты видео full ---"
od -A x -t x1z /tmp/fv.bin 2>/dev/null | head -1
echo
echo "=== RANGE GET аудио (0-65535), 15с ==="
curl -s -H 'Range: bytes=0-65535' -o /tmp/ra.bin -w 'аудио range: code=%{http_code} bytes=%{size_download}\n' -m 15 "$AURL"
od -A x -t x1z /tmp/ra.bin 2>/dev/null | head -1
echo "=== DONE $(date) ==="
} > /home/tema/aud3_report.txt 2>&1
cat /home/tema/aud3_report.txt