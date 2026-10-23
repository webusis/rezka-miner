#!/bin/sh
cd /home/tema
pkill -f 'yt_servic[e]' 2>/dev/null
sleep 1
setsid nohup python3 /home/tema/rezka-yt/yt_service.py > /home/tema/rezka-yt/yt_service.log 2>&1 &
sleep 4
echo "--- лог:"
tail -2 /home/tema/rezka-yt/yt_service.log
echo "--- ps:"
ps -ef | grep 'yt_servic[e]' | grep -v grep