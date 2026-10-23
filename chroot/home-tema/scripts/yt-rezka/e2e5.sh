#!/bin/sh
cd /home/tema
{
echo "=== прогрев меты (первый запрос после рестарта, долгий) ==="
curl -s -m 45 -r 0-1048575 'http://127.0.0.1:8081/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' -o /tmp/w.bin -w 'code=%{http_code} bytes=%{size_download} time=%{time_total}s\n'
sleep 2
echo "=== ffmpeg после прогрева (пусто = gen.close работает) ==="
ps -ef | grep '[f]fmpeg' | grep -v defunct | awk '{print $2}' || echo "чисто"
echo
echo "=== ОСНОВНОЙ ТЕСТ: стрим идёт, рвём по таймауту (-m 20) ==="
curl -s -m 20 -r 0-2097151 'http://127.0.0.1:8081/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' -o /tmp/t.bin -w 'code=%{http_code} bytes=%{size_download} time=%{time_total}s\n'
sleep 3
echo "=== ffmpeg после обрыва (пусто = утечки нет) ==="
ps -ef | grep '[f]fmpeg' | grep -v defunct | awk '{print $2, $9, $10}' || echo "чисто"
echo "=== load ==="
uptime
echo "=== DONE $(date) ==="
} > /home/tema/e2e5_report.txt 2>&1
cat /home/tema/e2e5_report.txt