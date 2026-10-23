#!/bin/sh
cd /home/tema
{
echo "=== ПРОКСИ 8080: RANGE + Content-Range ===  $(date)"
curl -s -D /tmp/p2.txt -m 90 -H "Range: bytes=15728640-" 'http://127.0.0.1:8080/api/yt/stream/v.ts?vid=PdbBLK5vt9E&h=480' | head -c 64 > /tmp/p2.bin
grep -E 'HTTP|Content-Range|Content-Length|Accept-Ranges' /tmp/p2.txt
od -A x -t x1z /tmp/p2.bin | head -1
echo "=== DONE ===  $(date)"
} > /home/tema/e2e3_report.txt 2>&1
echo RC=$?; cat /home/tema/e2e3_report.txt