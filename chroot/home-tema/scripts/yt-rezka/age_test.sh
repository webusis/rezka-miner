#!/bin/sh
cd /home/tema
{
echo "=== мета для age-restricted sCjQrUsIOWo (с куками) ==="
python3 -c "
import sys
sys.path.insert(0, '/home/tema/rezka-yt')
import yt_service as y
m = y._yt_meta('sCjQrUsIOWo', 480)
if not m:
    print('МЕТА НЕТ (None) — куки не помогают')
else:
    print('OK total=%s dur=%s' % (m['total'], m['dur']))
    print('vurl:', m['vurl'][:90])
" 2>&1 | head -4
echo
echo "=== стрим sCjQrUsIOWo через 8081 (25с) ==="
curl -s -D /tmp/ag.txt -m 25 'http://127.0.0.1:8081/api/yt/stream/v.ts?vid=sCjQrUsIOWo&h=480' -o /tmp/ag.bin -w 'code=%{http_code} bytes=%{size_download} time=%{time_total}s\n'
grep -E 'HTTP|Content-Range|Content-Length' /tmp/ag.txt
od -A x -t x1z /tmp/ag.bin 2>/dev/null | head -1
echo
echo "=== recs: персональные или фолбэк? ==="
curl -s -m 30 'http://127.0.0.1:8081/api/yt/recs' -o /tmp/recs.json -w 'recs: %{http_code} %{size_download}B\n'
python3 -c "
import json
d = json.load(open('/tmp/recs.json'))
r = d.get('results') or []
print('карточек:', len(r))
print('первая:', r[0].get('title','?')[:60] if r else '-')
" 2>&1 | head -3
echo "=== лог (хвост 6) ==="
tail -6 /home/tema/rezka-yt/yt_service.log
echo "=== DONE $(date) ==="
} > /home/tema/age_report.txt 2>&1
cat /home/tema/age_report.txt