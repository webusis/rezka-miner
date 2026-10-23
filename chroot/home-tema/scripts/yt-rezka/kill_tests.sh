#!/bin/sh
cd /home/tema
{
echo "=== ДО: что крутится ==="
ps -ef | grep -E "[f]fmpeg|[y]t-dlp|[p]ython3|[c]url|[d]bg" | awk '{print $2, $8, $9, $10, $11}' | head -25
echo
echo "=== УБИВАЕМ ТЕСТОВОЕ ==="
pkill -f '[d]bg' 2>/dev/null; echo "dbg-скрипты: ok"
pkill -x ffmpeg 2>/dev/null; echo "ffmpeg: ok"
pkill -x curl 2>/dev/null; echo "curl: ok"
pkill -f '[y]t-dlp' 2>/dev/null; echo "yt-dlp (тестовые/фон.реки): ok"
for p in $(ps -ef | grep '[p]ython3' | grep -v 'yt_service' | awk '{print $2}'); do
    kill $p 2>/dev/null
done
echo "python3-качалки (кроме yt_service): ok"
sleep 1
echo
echo "=== ПОСЛЕ: что осталось ==="
ps -ef | grep -E "[f]fmpeg|[y]t-dlp|[p]ython3|[c]url|[d]bg" | awk '{print $2, $8, $9, $10, $11}'
echo "=== DONE $(date) ==="
} > /home/tema/kill_report.txt 2>&1
cat /home/tema/kill_report.txt