#!/bin/sh
cd /home/tema
{
echo "=== ffmpeg ДО ==="
ps -ef | grep '[f]fmpeg' | awk '{print $2, $8, $9, $10, $11}'
echo "--- убиваю все ffmpeg (kill -9) ---"
for p in $(ps -ef | grep '[f]fmpeg' | awk '{print $2}'); do
    kill -9 $p 2>/dev/null && echo "kill $p ok"
done
sleep 1
echo "=== ffmpeg ПОСЛЕ ==="
ps -ef | grep '[f]fmpeg' | grep -v defunct | awk '{print $2, $8, $9}' || true
echo "=== yt_service жив? ==="
ps -ef | grep '[y]t_service' | awk '{print $2, $9}'
echo "=== DONE $(date) ==="
} > /home/tema/kill3_report.txt 2>&1
cat /home/tema/kill3_report.txt