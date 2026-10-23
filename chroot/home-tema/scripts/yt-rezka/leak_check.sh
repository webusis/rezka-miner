#!/bin/sh
cd /home/tema
{
echo "=== запускаю стрим и рву его по таймауту (имитация MX-обрыва) ==="
curl -s -m 15 -r 0-2097151 'http://127.0.0.1:8081/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' -o /tmp/leak.bin -w 'bytes=%{size_download} time=%{time_total}s\n'
sleep 2
echo "=== ffmpeg после обрыва (должно быть ПУСТО) ==="
ps -ef | grep '[f]fmpeg' | grep -v defunct | awk '{print $2, $8, $9}' || echo "чисто"
echo "=== повтор: ещё один обрыв ==="
curl -s -m 8 -r 0-1048575 'http://127.0.0.1:8081/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' -o /dev/null -w 'bytes=%{size_download}\n'
sleep 2
ps -ef | grep '[f]fmpeg' | grep -v defunct | awk '{print $2, $8, $9}' || echo "чисто"
echo "=== DONE $(date) ==="
} > /home/tema/leak_report.txt 2>&1
cat /home/tema/leak_report.txt