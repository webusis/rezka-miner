#!/bin/sh
cd /home/tema
{
echo "=== recs после рестарта ==="
curl -s -m 60 'http://127.0.0.1:8081/api/yt/recs' -o /tmp/recs2.json
python3 - <<'EOF'
import json
try:
    d = json.load(open('/tmp/recs2.json'))
    r = d.get('results') or []
    print('результатов:', len(r))
    for x in r[:4]:
        print('  -', (x.get('title') or '')[:60], '|', (x.get('meta') or '')[:25])
    if not r:
        print('пусто!', list(d.keys()))
except Exception as e:
    print('не json:', open('/tmp/recs2.json').read()[:150])
EOF
echo "=== лог сервиса (хвост) ==="
tail -4 /home/tema/rezka-yt/yt_service.log
echo "=== DONE $(date) ==="
} > /home/tema/recs_check.txt 2>&1
cat /home/tema/recs_check.txt