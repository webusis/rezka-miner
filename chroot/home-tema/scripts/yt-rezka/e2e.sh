#!/bin/sh
cd /home/tema
{
echo "=== 1. СТРИМ БЕЗ RANGE (обычный запуск) ==="
curl -s -D /tmp/h1.txt -m 90 'http://127.0.0.1:8081/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' | head -c 1024 > /tmp/ts1.bin
cat /tmp/h1.txt | tr -d '\r'
echo "-- первые байты TS:"
od -A x -t x1z /tmp/ts1.bin | head -2
echo
echo "=== 2. СТРИМ С RANGE (перемотка на ~30%) ==="
curl -s -D /tmp/h2.txt -m 90 -H 'Range: bytes=15728640-' 'http://127.0.0.1:8081/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' | head -c 1024 > /tmp/ts2.bin
cat /tmp/h2.txt | tr -d '\r'
echo "-- первые байты TS:"
od -A x -t x1z /tmp/ts2.bin | head -2
echo
echo "=== 3. ВТОРОЙ СТРИМ БЕЗ RANGE (кэш меты, скорость повторного старта) ==="
t0=$(date +%s)
curl -s -D /tmp/h3.txt -m 60 'http://127.0.0.1:8081/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' | head -c 512 > /tmp/ts3.bin
echo "elapsed=$(( $(date +%s) - t0 ))s"
cat /tmp/h3.txt | tr -d '\r'
od -A x -t x1z /tmp/ts3.bin | head -1
echo "=== DONE $(date) ==="
} > /home/tema/e2e_report.txt 2>&1
echo RC=$?; cat /home/tema/e2e_report.txt