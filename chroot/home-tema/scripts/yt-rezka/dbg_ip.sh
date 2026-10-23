#!/bin/sh
cd /home/tema
{
echo "=== getent example.com ==="
timeout 8 getent ahosts example.com | head -6
echo "rc=$?"
echo "=== ffmpeg по IP (93.184.216.34, без DNS) ==="
start=$(date +%s)
timeout 12 ffmpeg -hide_banner -loglevel warning -i http://93.184.216.34/ -t 1 -f null - 2>/home/tema/ip.err
echo "rc=$? el=$(( $(date +%s) - start ))s"
tail -2 /home/tema/ip.err
echo "=== локальный python http + ffmpeg localhost ==="
cd /home/tema
( python3 -m http.server 9999 --bind 127.0.0.1 >/dev/null 2>&1 & )
sleep 1
start=$(date +%s)
timeout 12 ffmpeg -hide_banner -loglevel warning -i http://127.0.0.1:9999/urls.sh -t 1 -f null - 2>/home/tema/lh.err
echo "rc=$? el=$(( $(date +%s) - start ))s"
tail -2 /home/tema/lh.err
pkill -f "http.server 9999"
echo "=== DONE $(date) ==="
} > /home/tema/dbg6_report.txt 2>&1