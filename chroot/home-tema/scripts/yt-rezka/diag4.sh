#!/bin/sh
cd /home/tema
{
echo "=== vurl из меты sCjQrUsIOWo ==="
python3 -c "
import sys
sys.path.insert(0, '/home/tema/rezka-yt')
import yt_service as y
m = y._yt_meta('sCjQrUsIOWo', 480)
if not m:
    print('МЕТА НЕТ (None)')
    sys.exit()
print('vurl:', m['vurl'][:110])
print('aurl:', m['aurl'][:110])
print('total:', m['total'], 'dur:', m['dur'])
open('/tmp/vurl.txt','w').write(m['vurl'] + '\n')
" 2>&1 | head -6
echo
echo "=== прямой качок googlevideo (vurl, 1МБ, 25с) ==="
VURL=$(head -1 /tmp/vurl.txt)
curl -s -m 25 -H 'Range: bytes=0-1048575' "$VURL" -o /tmp/gv.bin -w 'code=%{http_code} bytes=%{size_download} time=%{time_total}s\n' 2>&1
od -A x -t x1z /tmp/gv.bin 2>/dev/null | head -1
echo
echo "=== контроль: PdbBLK5vt9E стрим через 8081 сейчас (данные!) ==="
curl -s -m 15 -r 0-1048575 'http://127.0.0.1:8081/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' -o /tmp/pk.bin -w 'code=%{http_code} bytes=%{size_download} time=%{time_total}s\n'
echo
echo "=== ffmpeg/cачалки в ps ==="
ps -ef | grep -E '[f]fmpeg' | grep -v defunct | awk '{print $2, $9, $10}'
echo "=== DONE $(date) ==="
} > /home/tema/diag4_report.txt 2>&1
cat /home/tema/diag4_report.txt