#!/bin/sh
cd /home/tema
{
echo "=== тест стрима sCjQrUsIOWo с живым наблюдением ==="
curl -s -D /tmp/ss.txt -m 70 'http://127.0.0.1:8081/api/yt/stream/v.ts?vid=sCjQrUsIOWo&h=480' -o /tmp/ss.bin -w 'code=%{http_code} bytes=%{size_download} time=%{time_total}s\n' &
CURLPID=$!
sleep 12
echo "--- через 12с: ffmpeg/качалки ---"
ps -ef | grep -E '[f]fmpeg' | grep -v defunct | awk '{print $2, $9, $10, $11}'
echo "--- stderr сервиса за это время ---"
tail -5 /home/tema/rezka-yt/yt_service.log
echo "--- ждём curl ---"
wait $CURLPID
grep -E 'HTTP|Content-Range|Content-Length' /tmp/ss.txt
od -A x -t x1z /tmp/ss.bin 2>/dev/null | head -1
echo "--- ffprobe ---"
ffprobe -hide_banner /tmp/ss.bin 2>&1 | grep -E 'Duration|Stream' | head -4
echo "=== DONE $(date) ==="
} > /home/tema/diag3_report.txt 2>&1
cat /home/tema/diag3_report.txt