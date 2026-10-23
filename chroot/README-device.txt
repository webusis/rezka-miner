README — Debian chroot на NT-0902S (Android 4.2.2)
================================================================

Что здесь: Debian 12 (bookworm) armhf в chroot на планшете с rk3188.
Rootfs лежит в образе /mnt/sdcard/debian.img (ext4, 4095 MB), монтируется
в /mnt/sdcard/debian. Снаружи это обычный Android 4.2.2, внутри — Debian
с apt, python3, git, gcc и XFCE.

Память: 2048 MB всего. Было 372 MB свободных в начале работы,
стало ~856 MB. Реально занято ~700 MB из 2048.
Панель: 2048x1440. Ядро 3.0.36, 4 ядра, VFPv3+neon.
Версия rootfs: Debian 12.15 armhf


КОМАНДЫ
----------------------------------------------------------------

Войти в chroot (интерактивный bash):

    sh /mnt/sdcard/chroot/chroot-enter.sh

Выполнить одну команду и выйти:

    sh /mnt/sdcard/chroot/chroot-enter.sh 'apt-get update'

Выпустить всё наружу:

    sh /mnt/sdcard/chroot/chroot-exit.sh

Запустить приложение, чтобы окно появилось на КОМПЬЮТЕРЕ через X11:

    sh /mnt/sdcard/chroot/xrun.sh xfce4-terminal
    sh /mnt/sdcard/chroot/xrun.sh glxgears

    другую сессию:  XDISP=192.168.0.107:1 sh /mnt/sdcard/chroot/xrun.sh xfce4-terminal


СКРИПТЫ
----------------------------------------------------------------

chroot-enter.sh
    Поднимает loop + ext4 + bind-монтирования, потом отдаёт bash.

    Порядок действий:
      1. losetup /dev/block/loop0 <- debian.img
         (именно /dev/block/loop0, а НЕ losetup -f: на этой прошивке
         /dev/loop* не существует, а -f отдаёт несуществующий путь)
      2. mount -t ext4 в /mnt/sdcard/debian
      3. bind-монтирования: /dev, /sys, /proc в chroot
      4. devpts в dev/pts, tmpfs 64M в dev/shm
      5. bind /mnt/sdcard -> /home/tema/storage (внутри chroot)
      6. mknod для null/zero/full/random/urandom — если bind /dev не зашёл
      7. resolv.conf с 8.8.8.8 — только если в rootfs его ещё нет
      8. exec chroot ... bash -l

    Идемпотентный: каждая точка монтирования проверяется отдельно через
    /proc/mounts, повторный вход ничего не дублирует. Иначе накапливаются
    слои и потом ext4 не снять.

chroot-exit.sh
    Снимает всё и отвязывает loop.

    Особенности этой прошивки, ради которых скрипт такой:
      - umount снимает ТОЛЬКО верхний слой, если bind накладывали
        несколько раз — поэтому цикл до 20 проходов
      - порядок важен: вложенные (shm, pts, dev, sys, proc, storage)
        снимаются раньше самого ext4, иначе Device busy
      - арифметика $(( )) НЕ используется: старый ash 2013 глючит,
        счётчик идёт циклом for по списку
      - umount здесь не понимает -f и -l, только голый путь

    ВАЖНО, знать про скрипт: если внутри chroot остались живы
    процессы, umount молча не срабатывает (Device busy), скрипт
    пишет предупреждение и выходит, ничего не убивая. Проверить:

        ps | grep -E 'dbus|xfce|glx|xterm'
        # и убить руками, потом запустить exit ещё раз

xrun.sh
    Обёртка для запуска X-приложений с выводом на дисплей компьютера.

    Собирает строку окружения (DISPLAY, HOME=/home/tema), подключает
    XAUTHORITY если кука есть, запускает приложение в фоне через
    nohup, лог падает в /tmp/xrun.log ВНУТРИ chroot.

    Если приложение не открылось — смотреть лог:
        sh /mnt/sdcard/chroot/chroot-enter.sh 'cat /tmp/xrun.log'

    Переопределить дисплей: переменная XDISP, по умолчанию
    192.168.0.107:0.


ЧТО НУЖНО ДЛЯ X-НА КОМПЬЮТЕРЕ (xrun.sh)
----------------------------------------------------------------
На Kubuntu, руками, после каждого ребута:

    # socat пробрасывает unix-сокет X в TCP
    sudo nohup socat TCP-LISTEN:6000,fork,reuseaddr \
      UNIX-CONNECT:/tmp/.X11-unix/X0 >/tmp/socat-x11.log 2>&1 &

    # разрешить планшет (ГОСТЕВОЙ доступ, см. безопасность ниже)
    xhost +192.168.0.102

    # если включён ufw
    sudo ufw allow from 192.168.0.102 to any port 6000 proto tcp

Всё это сбрасывается при перезагрузке компьютера: и socat, и xhost.

Буфер обмена: работает. Это часть X-протокола, те же selections,
те же данные летят по тому же сокету. Нюанс: Android-буфер (длинное
нажатие) в это НЕ входит, обмен только между X-приложениями.
Данные не хранятся, а тянутся по запросу — убил окно-источник,
вставлять нечего.


ЧЕГО НЕ МОЖЕТ (проверено, закрыто)
----------------------------------------------------------------

GPU: не работает и не лечится.
    - /dev/dri отсутствует, DRI2/DRI3 не в чем: Mali-400 + UTGARD
      не выставляют себя наружу (в /system нет даже видеоустройства,
      video4linux видит только rk3066b-camera)
    - indirect GLX (рендер на компе, код на ARM) не работает:
      на планшете BadValue, локально на компе Segmentation fault
    - Mesa уходит в llvmpipe: ~4 FPS на 3D
    Итог: для терминала/редактора/файлового менеджера канал отличный,
    для видео и 3D — нет. Тяжёлое гонять можно только если код
    исполняется на компе (тогда это VNC/xpra, а не chroot).

ssh: OpenSSH 9.2 в chroot НЕ работает. Требует seccomp для privsep,
    ядро 3.0.36 его не знает (prctl(PR_SET_NO_NEW_PRIVS) → Invalid
    argument → Killing privsep child). Поэтому стоит dropbear на 2211.

X-сервер внутри chroot: xserver-xorg установлен, но бесполезен —
    нет DRM. Полезен только XSDL на хосте как внешний X-сервер.


ПОЛЬЗОВАТЕЛИ И ДОСТУПЫ
----------------------------------------------------------------
    tema / tema            uid 1000, sudo без пароля
                           (правило в /etc/sudoers.d/tema, visudo: parsed OK)
    root по SSH             НЕ пускает (пароля у root нет)
    sshd (dropbear) в chroot: порт 2211, только по паролю

Внутри chroot:
    /home/tema/storage   → bind на /mnt/sdcard хоста
                           vfat: chmod не работает, права с хоста.
                           Совпадение uid=1000 у vfat и у tema позволяет
                           писать без всяких танцев с группами.


БЕЗОПАСНОСТЬ (незакрытое)
----------------------------------------------------------------
После ребута компьютера xhost и socat мертвы, и вход в X-сессию
закрыт. Но если запустить их снова — доступ гостевой, то есть
ОТКРЫТЫЙ ВСЕЙ СЕТИ, включая всех соседей по Wi-Fi.

Чтобы закрыть постоянно, нужно:
  1. socat слушать на 127.0.0.1:6000, а не 0.0.0.0
  2. доступ по X-куке вместо xhost +
     на Kubuntu:
       XAUTH=$(xauth info | awk '/Authority file/ {print $3}')
       ssh root@192.168.0.102 'cat > /data/local/tmp/xauth' < "$XAUTH"
     потом положить этот файл в chroot как /root/.Xauthority
     (xrun.sh подхватит сам — там это предусмотрено)
  3. Option "Listen" "yes" в /etc/X11/xorg.conf.d/20-listen.conf
     убрать, если X-доступ с планшета больше не нужен


ОТКЛЮЧЁННЫЕ ПАКЕТЫ ANDROID
----------------------------------------------------------------
Файл: /data/system/users/0/package-restrictions.xml, тег <pkg name=...
      enabled="2"/>.

ПРАВИЛО ДОБАВЛЕНИЯ (главное, проверено 27.09):
  правка файла и ребут — ОДНОЙ командой, зазор в миллисекунды.
  Почему: PackageManagerService при ЗАГРУЗКЕ читает файл и принимает
  записи в память — после этого они его родные и переживают любую
  перезапись. Но если править файл при РАБОТАЮЩЕЙ системе, записи
  в память не попадают, и первая же перезапись файла PMS (через
  минуту-полторы, по событию вроде пробуждения экрана) их выкинет.
  Наблюдалось: 8 записей слетели дважды.

  Рабочий вариант:
    sh -c 'for p in ИМЯ1 ИМЯ2; do sed -i "s|<preferred-activities />|<pkg name=\"$p\" enabled=\"2\" />\n<preferred-activities />|" /data/system/users/0/package-restrictions.xml; done; reboot'

  Проверка после ребута (обязательно, иначе не узнаешь):
    grep -o 'enabled="2"' /data/system/users/0/package-restrictions.xml | wc -l
    должно совпасть с ожидаемым числом. НЕ grep -c: он считает
    СТРОКИ, а не вхождения, и врёт.

30 отключённых пакетов:
    Google (группа sharedUserId=10011, отключать надо ВСЮ группу,
    иначе пакеты с общим uid воскресают):
      com.google.android.gms, com.google.android.gsf,
      com.google.android.location, com.google.android.gsf.login,
      com.google.android.syncadapters.contacts
    Прочее Google:
      ears, quicksearchbox, music, apps.maps, onetimeinitizer,
      partnersetup, talk, apps.uploader, apps.plus, calendar, gm
    Прочие:
      com.android.mms, com.android.vending, com.android.chrome,
      com.android.smspush, com.android.inputmethod.latin,
      android.rockchip.update.service, stericson.busybox.donate,
      com.android.email
    Хлам AOSP (снесено 26.09, ~68 MB RSS):
      com.android.exchange, com.android.quicksearchbox,
      com.android.soundrecorder, com.android.videoeditor,
      com.android.musicvis, com.adobe.flashplayer

    acore (android.process.acore) НЕ отключается — это не пакет,
    его поднимает сам system_server, только kill до перезагрузки.

Бэкапы файла ограничений (откат = cp обратно):
    /mnt/sdcard/package-restrictions.xml.bak    15 записей
    /mnt/sdcard/package-restrictions.xml.bak2   19 записей
    /mnt/sdcard/package-restrictions.xml.bak3   22 записи
    /mnt/sdcard/package-restrictions.xml.bak4   24 записи (перед сносом хлама)
    /mnt/sdcard/package-restrictions.xml.bak5   22 записи (перед повтором)
    /mnt/sdcard/package-restrictions.xml.bak6   22 записи (перед успешным повтором)


ПРОЧЕЕ НА ДИСКЕ
----------------------------------------------------------------
    /mnt/sdcard/debian.img              образ rootfs, 4095 MB
    /mnt/sdcard/debian-rootfs.tar.gz    страховка rootfs, 43 MB
    /mnt/sdcard/build.log               лог сборки образа
    /opt/etc/init.d/S52chroot           автоподъём chroot при старте
                                       entware (монтирует сам, скрипты
                                       не вызывает; не проверен после
                                       ребута)
    /mnt/sdcard/debian/etc/profile.d/gl.sh   LIBGL_ALWAYS_SOFTWARE=1,
                                            GALLIUM_DRIVER=llvmpipe
    /mnt/sdcard/debian/etc/sudoers.d/tema    sudo-правило


ГРАБЛИ ЭТОЙ ПРОШИВКИ (чтобы не наступать повторно)
----------------------------------------------------------------
    - umount не понимает -f и -l, молча печатает справку и ничего
      не делает
    - stat -c не работает; wc -c на растущем файле блокируется
    - grep -c ... || echo 0 даёт "0\n0", а не "0"
    - $(( )) глючит в ash 2013
    - set -- $var затирает $@ и ломает exec chroot ... sh -c "$*"
    - ps не умеет -o; колонки: USER PID PPID VSIZE RSS WCHAN PC NAME
      (RSS — пятое поле)
    - /proc/net/tcp хранит порт в HEX: 6000 = 1770, 6002 = 1772
    - losetup -f врёт, узлы только /dev/block/loop0..7
    - /system/bin НЕТ в дефолтном PATH, нужен export
    - pm на прошивке нерабочий, поэтому пакеты отключаются руками
      в xml (см. выше)
    - wm отсутствует, разрешение меняется через настройки Android,
      fb0/virtual_size показывает 1:2.25 при альбомной ориентации
    - ps -o pid,rss,args внутри chroot падает: glibc на этом ядре
      даёт "fatal library error, reap". RSS считать через
      /proc/[0-9]*/status
    - awk с вложенными кавычками склеивается и падает с
      "Unexpected token" — из-за этого уже два раза получались
      ложные результаты в проверках
    - ls -l | cut -c67-80 не вытаскивает время: на этой прошивке
      отдаёт хвост имени файла. Время брать проще: ls -l, читать
      глазами, или сравнивать md5sum
    - grep -c считает СТРОКИ, а не вхождения. Если несколько
      записей в XML слиплись на одной строке (sed с \n может
      не сработать) — цифра занижена. Правильно:
      grep -o 'pat' file | wc -l
    - paste и bc в системе НЕТ
