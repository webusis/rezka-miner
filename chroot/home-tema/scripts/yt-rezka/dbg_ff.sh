#!/bin/sh
cd /home/tema
{
. /home/tema/urls.sh
echo "=== ffmpeg debug: connect stage ==="
start=$(date +%s)
timeout 20 ffmpeg -hide_banner -loglevel debug -rw_timeout 8000000 -i "$VURL" -t 1 -c copy -f mpegts - 2>/home/tema/dbg.err | head -c 64 > /home/tema/dbg.bin
echo "el=$(( $(date +%s) - start ))s bytes=$(wc -c < /home/tema/dbg.bin 2>/dev/null || echo missing)"
grep -E "http|tcp|open|error|fail|timeout|seek|response" /home/tema/dbg.err | head -15
echo "=== с заголовком UA и без keep-alive ==="
start=$(date +%s)
timeout 20 ffmpeg -hide_banner -loglevel warning -rw_timeout 8000000 -http_persistent 0 -headers $'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\r\n' -ss 600 -i "$VURL" -ss 600 -i "$AURL" -c copy -f mpegts - 2>/home/tema/dbg2.err | head -c 128 > /home/tema/dbg2.bin
echo "el=$(( $(date +%s) - start ))s bytes=$(wc -c < /home/tema/dbg2.bin 2>/dev/null || echo missing)"
tail -3 /home/tema/dbg2.err
echo "=== DONE $(date) ==="
} > /home/tema/dbg2_report.txt 2>&1