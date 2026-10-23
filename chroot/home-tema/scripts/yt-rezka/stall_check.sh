#!/bin/sh
cd /home/tema
{
echo "=== нагрузка планшета ==="
uptime
echo
echo "=== терпеливый стрим (60с, 2МБ) ==="
curl -s -D /tmp/lh.txt -m 60 -r 0-2097151 'http://127.0.0.1:8081/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' -o /tmp/lb.bin -w 'code=%{http_code} bytes=%{size_download} time=%{time_total}s speed=%{speed_download}B/s\n'
grep -E 'HTTP|Content|Range' /tmp/lh.txt
od -A x -t x1z /tmp/lb.bin 2>/dev/null | head -1
echo
echo "=== ffmpeg сейчас ==="
ps -ef | grep '[f]fmpeg' | grep -v defunct | awk '{print $2, $9, $10, $11, $12}'
echo
echo "=== лог сервиса (хвост 10) ==="
tail -10 /home/tema/rezka-yt/yt_service.log
echo "=== DONE $(date) ==="
} > /home/tema/stall_report.txt 2>&1
cat /home/tema/stall_report.txt