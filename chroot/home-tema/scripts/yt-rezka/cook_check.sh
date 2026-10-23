#!/bin/sh
cd /home/tema/rezka-yt
{
echo "=== cookies.txt === $(date)"
ls -la cookies.txt 2>&1
wc -l cookies.txt 2>&1
echo "--- домены кук:"
awk -F'\t' '{print $1}' cookies.txt 2>/dev/null | sort | uniq -c | head
echo "--- SAPISID/PSID есть? ---"
grep -c -E "SAPISID|__Secure-3PSID|SID|HSID" cookies.txt 2>/dev/null
echo "=== yt-dlp feed/recommended с этими куками (макс 30с) ==="
timeout 30 python3 /usr/local/bin/yt-dlp --no-warnings --cookies cookies.txt -J "https://www.youtube.com/feed/recommended" 2>/tmp/rec_err.txt | python3 -c "import json,sys; d=json.load(sys.stdin); v=d.get('entries') or []; print('жанр:', d.get('genre') or '?'); print('заголовок канала/темы:', (d.get('channel') or d.get('uploader') or '?')); print('кол-во в фиде:', len(v)); print('первый:', (v[0].get('title') if v else 'нет'))" 2>&1
echo "--- stderr yt-dlp (первые 3 строки): ---"
head -3 /tmp/rec_err.txt
echo "=== DONE $(date) ==="
} > /home/tema/cook_check.txt 2>&1
cat /home/tema/cook_check.txt