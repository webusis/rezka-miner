#!/bin/sh
# Автозапуск Debian-chroot + yt-сервиса (127.0.0.1:8081) + sshd (2211) после ребута.
# Зовётся из /system/etc/install-recovery.sh (init-хук ROM) — тот запускает нас
# в фоне (setsid), поэтому загрузку не тормозим.
# Лог: /data/local/tmp/chroot-boot.log
# Идемпотентно: yt-start.sh сам проверяет, не поднят ли уже сервис.

IMG=/mnt/sdcard/debian.img
ENTRY=/mnt/sdcard/chroot/yt-start.sh
PIDF=/data/local/tmp/chroot-boot.pid

# второй экземпляр не нужен: два poll'а дёрнут сервис наперегонки
if [ -f "$PIDF" ] && kill -0 "$(cat $PIDF 2>/dev/null)" 2>/dev/null; then
    echo "[$(date)] уже работает (pid $(cat $PIDF)) — выходим"
    exit 0
fi
echo $$ > "$PIDF"

echo "[$(date)] жду $IMG ..."
while [ ! -f "$IMG" ]; do sleep 2; done

echo "[$(date)] поднимаю yt-сервис (127.0.0.1:8081)"
sh "$ENTRY"

echo "[$(date)] поднимаю sshd в chroot (порт 2211)"
sh /mnt/sdcard/chroot/chroot-enter.sh "/etc/init.d/ssh start"

echo "[$(date)] готово"
rm -f "$PIDF"
