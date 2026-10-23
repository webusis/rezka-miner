#!/bin/sh
cd /home/tema
{
echo "=== кто такой PID 1952 ==="
ps -ef | grep -E "[1]952|[5]906" | grep -v grep
echo
echo "=== kill -9 1952 ==="
kill -9 1952 2>&1; echo "rc=$?"
sleep 1
echo
echo "=== ПОСЛЕ ==="
ps -ef | grep -E "[f]fmpeg|[p]ython3|[y]t-dlp|[c]url|[d]bg" | awk '{print $2, $8, $9, $10, $11}'
echo "=== DONE $(date) ==="
} > /home/tema/kill2_report.txt 2>&1
cat /home/tema/kill2_report.txt