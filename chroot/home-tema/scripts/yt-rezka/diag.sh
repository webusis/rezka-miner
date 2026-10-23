#!/bin/sh
cd /home/tema
{
echo "=== процессы ==="
ps -ef | grep -E '[f]fmpeg|[y]t_service|[p]ython' | grep -v grep | awk '{print $2, $8, $9, $10}' | head -8
echo
echo "=== прокси 8080 жив? ==="
curl -s -o /dev/null -w 'search: %{http_code}\n' -m 10 'http://127.0.0.1:8080/api/yt/search?q=a' 2>&1
curl -s -o /dev/null -w 'stream: %{http_code}\n' -m 10 'http://127.0.0.1:8080/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' -D /tmp/ph.txt 2>&1
grep -E 'HTTP|Content-Range|Content-Length' /tmp/ph.txt | head -4
echo
echo "=== лог сервиса yt_service (хвост 25) ==="
tail -25 /home/tema/rezka-yt/yt_service.log
echo
echo "=== лог прокси server.log (хвост 15) ==="
tail -15 /mnt/sdcard/server.log 2>/dev/null || tail -15 /sdcard/server.log 2>/dev/null || echo "нет server.log"
echo
echo "=== load ==="
uptime
echo "=== DONE $(date) ==="
} > /home/tema/diag_report.txt 2>&1
cat /home/tema/diag_report.txt