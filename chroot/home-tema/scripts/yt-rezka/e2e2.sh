#!/bin/sh
cd /home/tema
{
echo "=== ЧЕРЕЗ ПРОКСИ (8080) 1. БЕЗ RANGE ==="
curl -s -D /tmp/p1.txt -m 90 'http://127.0.0.1:8080/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' | head -c 512 > /tmp/p1.bin
cat /tmp/p1.txt | tr -d '\r'
od -A x -t x1z /tmp/p1.bin | head -1
echo
echo "=== ЧЕРЕЗ ПРОКСИ (8080) 2. С RANGE (перемотка) ==="
curl -s -D /tmp/p2.txt -m 90 -H 'Range: bytes=15728640-' 'http://127.0.0.1:8080/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' | head -c 512 > /tmp/p2.bin
cat /tmp/p2.txt | tr -d '\r'
od -A x -t x1z /tmp/p2.bin | head -1
echo "=== DONE $(date) ==="
} > /home/tema/e2e2_report.txt 2>&1
echo RC=$?; cat /home/tema/e2e2_report.txt