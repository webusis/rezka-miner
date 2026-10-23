#!/bin/sh
cd /home/tema
{
echo "=== ffmpeg background, смотрим syscall ==="
ffmpeg -hide_banner -loglevel warning -rw_timeout 6000000 -i https://example.com -t 1 -f null - >/dev/null 2>&1 &
FPID=$!
sleep 3
echo "PID=$FPID"
for p in $FPID; do
  if [ -r /proc/$p/syscall ]; then
    echo "syscall: $(cat /proc/$p/syscall 2>/dev/null)"
    echo "wchan: $(cat /proc/$p/wchan 2>/dev/null)"
    echo "stat: $(cat /proc/$p/stat 2>/dev/null | awk '{print $3, $14, $15}')"
  else
    echo "no /proc/$p/syscall (kernel не отдаёт)"
  fi
done
grep -E "^(State|Threads)" /proc/$FPID/status 2>/dev/null
echo "--- дети ---"
ls /proc/$FPID/task 2>/dev/null | while read t; do
  echo "tid=$t syscall=$(cat /proc/$FPID/task/$t/syscall 2>/dev/null) wchan=$(cat /proc/$FPID/task/$t/wchan 2>/dev/null)"
done
kill $FPID 2>/dev/null
echo "=== DONE $(date) ==="
} > /home/tema/dbg5_report.txt 2>&1