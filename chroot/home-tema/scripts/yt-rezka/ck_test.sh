#!/bin/sh
cd /home/tema
{
echo "=== версия yt-dlp на планшете ==="
/usr/local/bin/yt-dlp --version 2>&1 | head -2
echo
echo "=== куки: первые строки файла ==="
head -8 /home/tema/rezka-yt/cookies.txt
echo "... строк: $(wc -l < /home/tema/rezka-yt/cookies.txt)"
echo
echo "=== SID/SSID/LOGIN_INFO есть? ==="
grep -c -E '#HttpOnly_\.youtube\.com|\.youtube\.com\s+TRUE' /home/tema/rezka-yt/cookies.txt | head -1
grep -oE '^[^\t]*\tyoutube\.com\t[^\t]*\t[^\t]*\t[^\t]*\t[^\t]*\t(SID|SSID|LOGIN_INFO|SAPISID)' /home/tema/rezka-yt/cookies.txt | awk '{print $NF}' | sort | uniq -c
echo
echo "=== проверка: обычное видео с КУКАМИ (PdbBLK5vt9E) ==="
timeout 60 /usr/local/bin/yt-dlp --no-warnings --cookies /home/tema/rezka-yt/cookies.txt -J -f 'bv*[vcodec^=avc1]+ba/b' 'https://www.youtube.com/watch?v=PdbBLK5vt9E' > /tmp/c1.json 2>/tmp/c1.err
echo "rc=$?"
grep -o '"duration":[0-9]*' /tmp/c1.json | head -1
head -2 /tmp/c1.err
echo "=== DONE $(date) ==="
} > /home/tema/ck_report.txt 2>&1
cat /home/tema/ck_report.txt