#!/bin/sh
# Вход в Debian-armhf chroot на NT-0902S.
# Поднимает loop+ext4+binds, затем отдаёт bash. Использовать: sh chroot-enter.sh [команда]
export PATH=/system/bin:/opt/bin:/opt/sbin:/opt/sbin:$PATH

IMG=/mnt/sdcard/debian.img
MP=/mnt/sdcard/debian

# 1. ext4 на loop — идемпотентно: если уже смонтирован, не трогаем
#    ВАЖНО: losetup -f на Android отдаёт несуществующий /dev/loopN,
#    поэтому всегда работаем через /dev/block/loopN
LOOP=/dev/block/loop0
if ! grep -q " $MP " /proc/mounts 2>/dev/null; then
    losetup "$LOOP" "$IMG" || { echo "FAIL: losetup $LOOP"; exit 1; }
    echo "loop $LOOP <- $IMG"
    mkdir -p "$MP"
    mount -t ext4 "$LOOP" "$MP" || { echo "FAIL: mount"; exit 1; }
    echo "ext4 -> $MP"
else
    echo "ext4 уже смонтирован"
fi

# 2. псевдо-файловая система (bind, как в рабочем рецепте).
#    КАЖДАЯ точка проверяется отдельно: повторный вход не должен накладывать
#    дубликаты, иначе копится 5 слоёв и ext4 потом не снять (Device busy).
#    Порядок важен: сначала каталоги, потом mount.
mkdir -p "$MP/dev/pts" "$MP/dev/shm"
[ -d "$MP/dev" ] && ! grep -q " $MP/dev " /proc/mounts 2>/dev/null && mount -o bind /dev "$MP/dev" 2>/dev/null
grep -q " $MP/sys "  /proc/mounts 2>/dev/null || mount -o bind /sys  "$MP/sys"  2>/dev/null
grep -q " $MP/proc " /proc/mounts 2>/dev/null || mount -o bind /proc "$MP/proc" 2>/dev/null
grep -q " $MP/dev/pts " /proc/mounts 2>/dev/null || mount -t devpts devpts "$MP/dev/pts" 2>/dev/null
grep -q " $MP/dev/shm " /proc/mounts 2>/dev/null || mount -t tmpfs -o size=64M tmpfs "$MP/dev/shm" 2>/dev/null

# 2b. sdcard внутрь chroot: /mnt/sdcard -> /home/tema/storage
#     vfat не умеет chmod — права приходят с хоста как есть, поэтому
#     пользователю нужна группа sdcard_rw (gid взят из ls -ld на хосте)
mkdir -p "$MP/home/tema/storage"
chown tema:tema "$MP/home/tema/storage" 2>/dev/null
grep -q " $MP/home/tema/storage " /proc/mounts 2>/dev/null || mount -o bind /mnt/sdcard "$MP/home/tema/storage" 2>/dev/null

# 3. device nodes на случай если bind /dev не зашёл.
#    ВАЖНО: без `set --` — он затирает $@ и ломает "$*" в exec ниже
[ -e "$MP/dev/null" ]    || mknod "$MP/dev/null"    c 1 3 2>/dev/null
[ -e "$MP/dev/zero" ]    || mknod "$MP/dev/zero"    c 1 5 2>/dev/null
[ -e "$MP/dev/full" ]    || mknod "$MP/dev/full"    c 1 7 2>/dev/null
[ -e "$MP/dev/random" ]  || mknod "$MP/dev/random"  c 1 8 2>/dev/null
[ -e "$MP/dev/urandom" ] || mknod "$MP/dev/urandom" c 1 9 2>/dev/null

# 4. DNS: в rootfs уже прописан, трогаем только если пусто
if ! grep -q nameserver "$MP/etc/resolv.conf" 2>/dev/null; then
    printf 'nameserver 8.8.8.8\n' > "$MP/etc/resolv.conf"
    printf '127.0.0.1 localhost\n' > "$MP/etc/hosts"
fi

# 5. env — чтобы не терять PATH и терминал
if [ $# -gt 0 ]; then
    exec chroot "$MP" /usr/bin/env -i \
        HOME=/root TERM="${TERM:-linux}" PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
        LANG=C.UTF-8 /bin/sh -c "$*"
else
    exec chroot "$MP" /usr/bin/env -i \
        HOME=/root TERM="${TERM:-linux}" PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
        LANG=C.UTF-8 /bin/bash -l
fi
