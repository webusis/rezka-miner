#!/bin/sh
cd /home/tema
{
echo "=== yt-dlp -v: ffmpeg command line ==="
. /home/tema/urls.sh
timeout 30 curl -s -o /dev/null -w "curl http=%{http_code} size=%{size_download} ttfb=%{time_starttransfer}s\n" -r 0-1023 "$VURL" 2>&1
echo "=== yt-dlp -v (head 25 строк) ==="
timeout 25 yt-dlp --no-warnings -v -f "bv*[vcodec^=avc1][height<=480]+ba[ext=m4a]/bv*[vcodec^=avc1][height<=720]+ba[ext=m4a]" -o - "https://www.youtube.com/watch?v=lhqABmcwedw" 2>&1 | head -25
echo "=== DONE $(date) ==="
} > /home/tema/dbg_report.txt 2>&1