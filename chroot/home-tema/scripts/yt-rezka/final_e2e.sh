#!/bin/sh
cd /home/tema
{
echo "=== финальный E2E через ПРОКСИ 8080 ==="
echo "--- тест 1: стрим 20с, обрыв ---"
curl -s -m 20 -r 0-2097151 'http://127.0.0.1:8080/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' -o /tmp/z1.bin -w 'code=%{http_code} bytes=%{size_download} time=%{time_total}s\n'
sleep 3
echo "--- ffmpeg после обрыва (пусто = цепочка рвёт) ---"
ps -ef | grep '[f]fmpeg' | grep -v defunct | awk '{print $2, $9, $10}' || echo "чисто"
echo "--- тест 2: ещё обрыв (перезапрос как MX) ---"
curl -s -m 12 -r 0-1048575 'http://127.0.0.1:8080/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' -o /dev/null -w 'code=%{http_code} bytes=%{size_download} time=%{time_total}s\n'
sleep 3
echo "--- ffmpeg снова (пусто) ---"
ps -ef | grep '[f]fmpeg' | grep -v defunct | awk '{print $2, $9, $10}' || echo "чисто"
echo "--- load ---"
uptime
echo "=== DONE $(date) ==="
} > /home/tema/final_report.txt 2>&1
cat /home/tema/final_report.txt