#!/bin/sh
cd /home/tema/rezka-yt
{
echo "=== 1. КТО Я с этими куками (yt-dlp -J на home) ==="
timeout 30 python3 /usr/local/bin/yt-dlp --no-warnings --cookies cookies.txt -J "https://www.youtube.com/" 2>/tmp/err1.txt | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('title:', d.get('title'))
print('channel:', d.get('channel'))
print('uploader:', d.get('uploader'))
print('_type:', d.get('_type'))
print('entries:', len(d.get('entries') or []))
"
echo "--- err1: ---"; head -2 /tmp/err1.txt
echo
echo "=== 2. feed/recommended ПОЛНЫЙ разбор ==="
timeout 30 python3 /usr/local/bin/yt-dlp --no-warnings --cookies cookies.txt -J "https://www.youtube.com/feed/recommended" 2>/tmp/err2.txt > /tmp/rec.json
python3 - <<'EOF'
import json
try:
    d = json.load(open('/tmp/rec.json'))
except Exception as e:
    print('json не парсится:', e); raise SystemExit
print('_type:', d.get('_type'), '| title:', d.get('title'))
en = d.get('entries') or []
print('entries:', len(en))
for v in en[:5]:
    print('  -', (v.get('title') or '')[:70], '|', (v.get('channel') or v.get('uploader') or '')[:30])
if not en:
    print('ключи верхнего уровня:', list(d.keys())[:12])
EOF
echo "--- err2: ---"; head -2 /tmp/err2.txt
echo
echo "=== 3. Что отдаёт сервис /api/yt/recs на 8081 ==="
curl -s -m 60 'http://127.0.0.1:8081/api/yt/recs' -o /tmp/recs.json
python3 - <<'EOF'
import json
try:
    d = json.load(open('/tmp/recs.json'))
    r = d.get('results') or []
    print('результатов:', len(r))
    for x in r[:5]:
        print('  -', (x.get('title') or '')[:70], '|', (x.get('meta') or '')[:30])
except Exception as e:
    print('recs ответ не json:', open('/tmp/recs.json').read()[:200])
EOF
echo "=== DONE $(date) ==="
} > /home/tema/cook_check2.txt 2>&1
cat /home/tema/cook_check2.txt