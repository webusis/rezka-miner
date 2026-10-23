#!/bin/sh
cd /home/tema
{
echo "=== 1. null-mux: идут ли пакеты вообще ==="
timeout 20 ffmpeg -hide_banner -loglevel info -i /home/tema/p19.mp4 -t 2 -f null - 2>&1 | tail -12
echo "=== 2. mpegts c debug: где висит ==="
timeout 12 ffmpeg -hide_banner -loglevel debug -i /home/tema/p19.mp4 -c copy -f mpegts /tmp/t21.ts 2>&1 | grep -E "mpegts|Opening|frame|packet|demux|mux|h264|Non-monotonic|cur_dts" | tail -25
echo "=== DONE $(date) ==="
} > /home/tema/dbg21_report.txt 2>&1
echo RC=$?; tail -45 /home/tema/dbg21_report.txt