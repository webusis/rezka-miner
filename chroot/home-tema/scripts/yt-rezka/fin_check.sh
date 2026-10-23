#!/bin/sh
cd /home/tema
am force-stop org.rezka.server 2>/dev/null
am start -n org.rezka.server/org.kivy.android.PythonActivity >/dev/null 2>&1
sleep 12
{
echo "=== load после перезапуска ==="
uptime
echo
echo "=== стрим через ПРОКСИ 8080, рвём по таймауту ==="
curl -s -D /tmp/qh.txt -m 30 -r 0-2097151 'http://127.0.0.1:8080/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' -o /tmp/q.bin -w 'code=%{http_code} bytes=%{size_download} time=%{time_total}s speed=%{speed_download}B/s\n'
grep -E 'HTTP|Content|Range' /tmp/qh.txt
od -A x -t x1z /tmp/q.bin 2>/dev/null | head -1
sleep 3
echo "=== ffmpeg после обрыва через прокси (должно быть ПУСТО) ==="
ps -ef | grep '[f]fmpeg' | grep -v defunct | awk '{print $2, $9, $10}' || echo "чисто"
echo "=== DONE $(date) ==="
} > /home/tema/fin_report.txt 2>&1
cat /home/tema/fin_report.txt