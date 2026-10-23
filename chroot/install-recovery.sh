#!/system/bin/sh
# init-хук ROM: /init.rc -> service flash_recovery /system/etc/install-recovery.sh
# (class main, oneshot). Наша задача — поднять Debian-chroot и сервисы после
# ребута планшета.
#
# ВАЖНО: работаем только в фоне (setsid + &) и сразу выходим. Иначе init будет
# ждать скрипт, а sdcard к этому моменту ещё не смонтирован → загрузка зависнет.
#
# Вся логика — в /mnt/sdcard/chroot/chroot-boot.sh (лежит в репе rezka-miner),
# сюда специально не тащим: sdcard может подняться позже, поэтому файл ждём.
# Лог: /data/local/tmp/chroot-boot.log

/system/xbin/busybox setsid /system/bin/sh -c '
  BB=/system/xbin/busybox
  i=0
  while [ "$i" -lt 150 ]; do
      [ -f /mnt/sdcard/chroot/chroot-boot.sh ] && break
      sleep 2
      i=$($BB expr $i + 1)
  done
  sh /mnt/sdcard/chroot/chroot-boot.sh
' >> /data/local/tmp/chroot-boot.log 2>&1 &
exit 0
