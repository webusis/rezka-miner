#!/bin/sh
# Запуск приложения из chroot с выводом на X-дисплей компьютера.
#   sh /mnt/sdcard/xrun.sh xfce4-terminal
#   sh /mnt/sdcard/xrun.sh glxgears
# Дисплей переопределяется переменной: XDISP=192.168.0.107:1 sh xrun.sh ...
export PATH=/system/bin:/opt/bin:/opt/sbin:$PATH

DST=${XDISP:-192.168.0.107:0}

if [ -z "$1" ]; then
    echo "usage: sh /mnt/sdcard/chroot/xrun.sh <команда> [аргументы...]"
    echo "       сейчас настроен дисплей: $DST"
    exit 1
fi

# собираем аргументы в строку: иначе "$*" в chroot-enter ломает exec
ARGS=""
for a in "$@"; do
    ARGS="$ARGS $a"
done

# если кука уже лежит в chroot — подключаем её (иначе работает xhost + на компе)
XA=""
if [ -f /mnt/sdcard/debian/root/.Xauthority ]; then
    XA="; XAUTHORITY=/root/.Xauthority; export XAUTHORITY"
fi

RUN="export DISPLAY=$DST; export HOME=/home/tema; cd /home/tema$XA"
RUN="$RUN; nohup $ARGS >/tmp/xrun.log 2>&1 &"
RUN="$RUN sleep 2; echo запуск-ок: $ARGS на $DST"

sh /mnt/sdcard/chroot-enter.sh "$RUN"
