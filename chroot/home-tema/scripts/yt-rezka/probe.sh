#!/bin/sh
cd /home/tema
{
echo "=== ffprobe: как плеер видит наш TS (первые 25с потока) ==="
ffprobe -hide_banner /tmp/f.bin 2>&1 | grep -E "Duration|Stream|start" | head -6
echo
echo "=== повторный замер скорости через 8080 (40с) ==="
curl -s -m 40 -r 0-3145727 'http://127.0.0.1:8080/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' -o /tmp/g.bin -w 'code=%{http_code} bytes=%{size_download} time=%{time_total}s speed=%{speed_download}B/s\n'
echo "=== ffmpeg после обрыва ==="
ps -ef | grep '[f]fmpeg' | grep -v defunct | awk '{print $2, $9}' || echo "чисто"
echo "=== DONE $(date) ==="
} > /home/tema/probe_report.txt 2>&1
cat /home/tema/probe_report.txt