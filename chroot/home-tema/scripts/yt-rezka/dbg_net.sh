#!/bin/sh
cd /home/tema
{
echo "=== resolv.conf ==="
cat /etc/resolv.conf
echo "=== getent googlevideo ==="
timeout 8 getent ahosts rr1---sn-cxauxaxjvh-hn9es.googlevideo.com | head -8
echo "rc=$?"
echo "=== ffmpeg http://neverssl.com ==="
start=$(date +%s)
timeout 15 ffmpeg -hide_banner -loglevel warning -i http://neverssl.com -t 1 -f null - 2>&1 | tail -2
echo "el=$(( $(date +%s) - start ))s"
echo "=== ffmpeg https://example.com ==="
start=$(date +%s)
timeout 15 ffmpeg -hide_banner -loglevel warning -i https://example.com -t 1 -f null - 2>&1 | tail -2
echo "el=$(( $(date +%s) - start ))s"
echo "=== getent youtube.com (для сравнения) ==="
timeout 8 getent ahosts www.youtube.com | head -4
echo "rc=$?"
echo "=== DONE $(date) ==="
} > /home/tema/dbg3_report.txt 2>&1