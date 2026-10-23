#!/bin/sh
cd /home/tema
{
echo "=== which strace ==="
command -v strace || echo NO_STRACE
echo "=== ffmpeg debug neverssl (10s) ==="
timeout 10 ffmpeg -hide_banner -loglevel debug -rw_timeout 5000000 -i http://neverssl.com -t 1 -f null - >/home/tema/ns.out 2>/home/tema/ns.err
echo "rc=$? out=$(wc -c </home/tema/ns.out) err=$(wc -c </home/tema/ns.err)"
tail -8 /home/tema/ns.err
echo "=== /proc/net/tcp: попытка соединения видна? ==="
timeout 8 ffmpeg -hide_banner -loglevel warning -rw_timeout 6000000 -i https://example.com -t 1 -f null - >/dev/null 2>&1 &
FPID=$!
sleep 3
cat /proc/net/tcp 2>/dev/null | awk '{print $3}' | grep -v "^0:00000000:0000" | head -8
wait $FPID
echo "=== DONE $(date) ==="
} > /home/tema/dbg4_report.txt 2>&1