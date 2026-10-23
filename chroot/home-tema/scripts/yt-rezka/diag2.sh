#!/bin/sh
cd /home/tema
{
echo "=== лог прокси (server.log) хвост 30 ==="
tail -30 /data/data/org.rezka.server/files/app/server.log 2>/dev/null || echo "нет доступа из chroot"
echo
echo "=== что отдаёт сервис на запрос БЕЗ Range (как MX) ==="
curl -s -D /tmp/nr.txt -m 15 'http://127.0.0.1:8081/api/yt/stream/v.ts?vid=sCjQrUsIOWo&h=480' -o /tmp/nr.bin -w 'code=%{http_code} bytes=%{size_download} time=%{time_total}s\n'
grep -E 'HTTP|Content-Range|Content-Length|Content-Type' /tmp/nr.txt
od -A x -t x1z /tmp/nr.bin 2>/dev/null | head -1
echo
echo "=== ffprobe первых байтов (валиден ли TS для плеера) ==="
ffprobe -hide_banner /tmp/nr.bin 2>&1 | grep -E 'Duration|Stream' | head -4
echo
echo "=== куки: файл, размер, mtime ==="
ls -la /home/tema/rezka-yt/cookies.txt 2>/dev/null
ls -la /home/tema/rezka-yt/*.txt 2>/dev/null | head -5
echo
echo "=== DONE $(date) ==="
} > /home/tema/diag2_report.txt 2>&1
cat /home/tema/diag2_report.txt