#!/bin/sh
cd /home/tema
{
echo "=== стрим через ПРОКСИ 8080 (читаем 2МБ, рвём по таймауту) ==="
curl -s -D /tmp/fh.txt -m 25 -r 0-2097151 'http://127.0.0.1:8080/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' -o /tmp/f.bin -w 'code=%{http_code} bytes=%{size_download} time=%{time_total}s speed=%{speed_download}B/s\n'
grep -E 'HTTP|Content|Range' /tmp/fh.txt
od -A x -t x1z /tmp/f.bin 2>/dev/null | head -1
sleep 3
echo "=== ffmpeg после обрыва (должно быть пусто) ==="
ps -ef | grep '[f]fmpeg' | grep -v defunct | awk '{print $2, $9, $10}' || echo "чисто"
echo "=== load ==="
uptime
echo "=== DONE $(date) ==="
} > /home/tema/fin2_report.txt 2>&1
cat /home/tema/fin2_report.txt