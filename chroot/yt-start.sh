#!/bin/sh
# Старт yt-сервиса (точка входа ютуба) в chroot планшета.
# Использование (с хоста, где настроен adb):
#   adb shell su -c 'sh /mnt/sdcard/chroot/yt-start.sh'
# Сервис слушает 127.0.0.1:8081 — python2-сервер (RezkaServer.apk)
# проксирует свои /api/yt/* на этот порт.
# Все файлы ютуба — в /home/tema/rezka-yt/ внутри chroot.
#
# ГРАБЛИ (почему не pgrep -f yt_service.py, как было):
#   - `pgrep -f` матчит и собственную обёртку `sh -c '... yt_service.py ...'` —
#     выходило «уже запущен» при мёртвом сервисе. Шаблон в скобках [y]t_service.py
#     собственную командную строку не матчит.
#   - в $( ) попадает и stdout chroot-enter.sh («ext4 уже смонтирован»),
#     поэтому PID берём только из строк-чисел.

BB=/system/xbin/busybox
ENTER='sh /mnt/sdcard/chroot/chroot-enter.sh'

get_pid() {
    su -c "$ENTER \"pgrep -f [y]t_service.py\"" 2>/dev/null | $BB grep -E '^[0-9]+$' | $BB head -1
}

PID=$(get_pid)
if [ -n "$PID" ]; then
    echo "yt_service уже запущен (pid $PID)"
    exit 0
fi

su -c "$ENTER \"nohup python3 /home/tema/rezka-yt/yt_service.py > /home/tema/rezka-yt/yt_service.log 2>&1 &\"" 2>/dev/null
sleep 3

PID=$(get_pid)
if [ -n "$PID" ]; then
    echo "yt_service поднят (pid $PID)"
    su -c "$ENTER \"curl -s --max-time 8 http://127.0.0.1:8081/api/yt/recs | head -c 120\"" 2>/dev/null
else
    echo "FAIL: yt_service не поднялся — смотри /home/tema/rezka-yt/yt_service.log"
    su -c "$ENTER \"tail -5 /home/tema/rezka-yt/yt_service.log\"" 2>/dev/null
fi