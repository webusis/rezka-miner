#!/bin/sh
cd /home/tema
{
echo "=== живость ==="
curl -s -o /dev/null -w '8081 search: %{http_code}\n' -m 10 'http://127.0.0.1:8081/api/yt/search?q=a'
curl -s -o /dev/null -w '8080 search: %{http_code}\n' -m 12 'http://127.0.0.1:8080/api/yt/search?q=a'
echo
echo "=== стрим через 8081 (читаем 2МБ, макс 30с) ==="
curl -s -m 30 -r 0-2097151 'http://127.0.0.1:8081/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' -o /tmp/s1.bin -w 'code=%{http_code} bytes=%{size_download} time=%{time_total}s speed=%{speed_download}B/s\n'
grep -E 'HTTP|Content|Range' /tmp/s1h.txt 2>/dev/null
ls -la /tmp/s1.bin 2>/dev/null | awk '{print "s1.bin:", $5, "байт"}'
od -A x -t x1z /tmp/s1.bin 2>/dev/null | head -1
echo
echo "=== стрим через ПРОКСИ 8080 (читаем 2МБ, макс 30с) ==="
curl -s -D /tmp/s2h.txt -m 30 -r 0-2097151 'http://127.0.0.1:8080/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' -o /tmp/s2.bin -w 'code=%{http_code} bytes=%{size_download} time=%{time_total}s\n'
grep -E 'HTTP|Content|Range' /tmp/s2h.txt
ls -la /tmp/s2.bin 2>/dev/null | awk '{print "s2.bin:", $5, "байт"}'
od -A x -t x1z /tmp/s2.bin 2>/dev/null | head -1
echo
echo "=== ffmpeg-процессы сейчас ==="
ps -ef | grep '[f]fmpeg' | head -5
echo "=== лог сервиса (хвост 8) ==="
tail -8 /home/tema/rezka-yt/yt_service.log
echo "=== DONE $(date) ==="
} > /home/tema/e2e4_report.txt 2>&1
cat /home/tema/e2e4_report.txt