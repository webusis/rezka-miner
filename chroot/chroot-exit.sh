#!/bin/sh
# Снять все mounts и отвязать loop.
# ВАЖНО 1: umount снимает только ВЕРХНИЙ слой. Если bind накладывали несколько раз,
#           снятых слоёв будет несколько — поэтому повторяем циклом до чистоты.
# ВАЖНО 2: ext4 нельзя снять, пока внутри есть вложенные mounts (dev/sys/proc),
#           поэтому сначала снимаем вложенные, потом сам ext4.
# ВАЖНО 3: без арифметики $(( )) — старый ash 2013 глючит. Счётчик через for по списку.
export PATH=/system/bin:/opt/bin:/opt/sbin:/opt/sbin:$PATH

IMG=/mnt/sdcard/debian.img
MP=/mnt/sdcard/debian

# до 20 проходов: снимаем по слою вложенные (от глубоких к внешним)
for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    LEFT=$(grep -c "$MP" /proc/mounts 2>/dev/null)
    [ "$LEFT" -le 1 ] && break
    umount "$MP/dev/shm" 2>/dev/null
    umount "$MP/dev/pts" 2>/dev/null
    umount "$MP/dev"     2>/dev/null
    umount "$MP/sys"     2>/dev/null
    umount "$MP/proc"    2>/dev/null
    umount "$MP/home/tema/storage" 2>/dev/null
    umount "$MP"         2>/dev/null
done

# отвязать loop, привязанный на наш образ
for L in /dev/block/loop*; do
    losetup "$L" 2>/dev/null | grep -q "$IMG" && losetup -d "$L" 2>/dev/null
done

LEFT=$(grep -c "$MP" /proc/mounts 2>/dev/null)
if [ "$LEFT" = "0" ]; then
    echo "chroot размонтирован, loop отвязан"
else
    echo "ВНИМАНИЕ: осталось записей с $MP: $LEFT"
    grep "$MP" /proc/mounts | awk '{print "  " $2, $3}'
fi
