# ютуб в Rezka: точка входа в chroot планшета (ветка youtube)

Схема (всё локально на планшете):

```
RezkaUI.apk (вкладка ютуб)
   └─> 127.0.0.1:8080  RezkaServer.apk (python2, как раньше)
          └─ /api/yt/* -> 127.0.0.1:8081  yt_service.py (этот каталог)
                              python3.11: ленты — YouTube Data API (OAuth),
                              стрим — yt-dlp (mpegts-склейка ffmpeg'ом)
```

Резка живёт как жила, ютуб ищет через официальный API, стримит yt-dlp прямо
в chroot — никаких внешних серверов, всё на планшете.

## Установка на планшет

Все файлы ютуба лежат в `/home/tema/rezka-yt/` внутри chroot
(rootfs смонтирован в /mnt/sdcard/debian) — в корне `/home/tema` хлама нет:

```
/home/tema/rezka-yt/
├── yt_service.py     сервис (8081)
├── oauth.json        YouTube Data API (client_id/secret/refresh, 600)
└── cookies.txt       куки аккаунта для фида рекомендаций (Netscape, 600)

/home/tema/scripts/yt-rezka/     стенд+логи отладки стрима (02–03.10.2026),
└── logs/                        сервису не нужны — см. INDEX.md внутри
```

1. Скопировать сервис в chroot:
   ```
   adb push chroot/yt_service.py /mnt/sdcard/yt_service.py
   adb shell su -c 'cp /mnt/sdcard/yt_service.py /mnt/sdcard/debian/home/tema/rezka-yt/yt_service.py'
   ```
2. `oauth.json` и `cookies.txt` — туда же (или обновлять прямо в файле,
   сервис читает их при каждом обновлении, рестарт не нужен).
   Без oauth.json ленты не работают; без cookies.txt recs падает на API-темы.
3. Запуск:
   ```
   adb shell su -c 'sh /mnt/sdcard/chroot/yt-start.sh'
   ```

## Файлы репы и куда они кладутся на планшете

| В репе | На планшете |
|---|---|
| `yt_service.py` | `/mnt/sdcard/debian/home/tema/rezka-yt/yt_service.py` (в образе) |
| `yt-start.sh` | `/mnt/sdcard/chroot/yt-start.sh` |
| `chroot-enter.sh`, `chroot-exit.sh`, `xrun.sh` | `/mnt/sdcard/chroot/` |
| `chroot-boot.sh` | `/mnt/sdcard/chroot/chroot-boot.sh` (точка входа автозапуска) |
| `install-recovery.sh` | `/system/etc/install-recovery.sh` (init-хук ROM) и копия в `/mnt/sdcard/chroot/` |
| `S52chroot` | `/opt/etc/init.d/S52chroot` (entware-init, зеркальный путь) |
| `home-tema/scripts/yt-rezka/` | `/home/tema/scripts/yt-rezka/` (стенд+логи отладки стрима, `INDEX.md` там же) |
| `etc-init.d-ssh` | `/etc/init.d/ssh` в образе (кастом: `LD_PRELOAD=fakeurandom`) |
| `README-device.txt` | `/mnt/sdcard/chroot/README.txt` (грабли прошивки) |

`/usr/lib/fakeurandom.so` — бинарь в образе (в репе исходника нет).

## Автозапуск после ребута

Основной путь — штатный хук init: `/system/etc/install-recovery.sh` (в репе
`install-recovery.sh`). В `/init.rc` он объявлен как `service flash_recovery`
(class main, oneshot) — это **штатное место «выполнить скрипт один раз при
загрузке»**; на прошивке файла не было (место пустовало), recovery-логики там
нет: скрипт ничего не монтирует и не флешит, только запускает наш скрипт и
сразу выходит, иначе застопорит init.

`chroot-boot.sh` (в репе, на sdcard) — единственное место логики:
1. pid-файл, чтобы два запуска не гонялись;
2. ждёт `/mnt/sdcard/debian.img` (sdcard монтируется позже init);
3. `yt-start.sh` → chroot + `yt_service.py` на 127.0.0.1:8081 (идемпотентно);
4. `/etc/init.d/ssh start` в chroot → sshd на **2211** (с `fakeurandom`).

Лог автозапуска: `/data/local/tmp/chroot-boot.log`.

`S52chroot` (`/opt/etc/init.d/S52chroot`) — зеркальный путь на случай, если
включат автозапуск entware (`entware.universal.autocontrol`): просто зовёт тот
же `chroot-boot.sh`, своей логики не имеет. Сейчас entware сам не стартует
(`rc.unslung` при загрузке не вызывается), поэтому путь спит.

Установка хука (один раз, нужен rw на /system):
```
adb push chroot/install-recovery.sh /data/local/tmp/install-recovery.sh
adb shell "su -c 'mount -o remount,rw /system; cp /data/local/tmp/install-recovery.sh /system/etc/install-recovery.sh; chmod 755 /system/etc/install-recovery.sh; sync; mount -o remount,ro /system'"
```
Снять автозапуск: `rm /system/etc/install-recovery.sh` (тем же способом с rw).

Порты после ребута: **2211** — sshd в chroot (`ssh -p 2211 tema@192.168.0.102`),
22 — dropbear entware, 8081 — yt-сервис (локально), 8080 — RezkaServer (не наш).

## Проверка

```
adb shell su -c 'sh /mnt/sdcard/chroot/chroot-enter.sh "curl -s http://127.0.0.1:8081/api/yt/recs | head -c 200"'
adb shell su -c 'sh /mnt/sdcard/chroot/chroot-enter.sh "curl -s \"http://127.0.0.1:8081/api/yt/search?q=metallica\" | head -c 200"'
```

## Сборка APK (сервер с прокси /api/yt/*)

```
cd apk-server && p4a apk --private . --requirements python2,openssl \
    --bootstrap service_only ...  # полная процедура — apk-server/README.md
```

## Заметки

- yt-dlp ставится бинарём на python3.11: `curl -skL -o /usr/local/bin/yt-dlp
  https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp`
- ca-certificates и ffmpeg из apt: `apt-get install ca-certificates ffmpeg`
  (ffmpeg нужен yt-dlp для склейки dash в mpegts — свой встроенный).
- Стрим: качество 480p по умолчанию, 720p если 480 нет, выше — никогда
  (логика та же, что в server.py dev-версии). mpegts: yt-dlp сам мёржит
  dash через свой ffmpeg — склейка на планшете, это нормально.
- Ленты (search/subs/channel) — только YouTube Data API v3 через
  oauth.json: search.list (25), subscriptions?mine=true,
  playlistItems (uploads канала).
- recs — персональный фид главной `/feed/recommended` через yt-dlp +
  cookies аккаунта (`/home/tema/rezka-yt/cookies.txt`, Netscape, права 600,
  экспорт Cookie-Editor). Старый фид отдаётся мгновенно, свежий тянется
  в фоне каждые 3 мин (главная всегда свежая и не ждёт).
  Фид умер/протух — фолбэк на API (темы + mostPopular BY).
  yt-dlp для поиска/подписок/каналов НЕ используется.
## После перезагрузки планшета

Хук `S52chroot` сам поднимает chroot и `yt_service.py` (см. выше). Вручную —
только если что-то не сработало:

1. Поднять chroot (mount + вход): `adb shell su -c 'sh /mnt/sdcard/chroot/chroot-enter.sh "echo ok"'`
   (если ругнётся на loop0 — сначала `mount -t ext4 /dev/block/loop0 /mnt/sdcard/debian`).
2. Поднять yt-сервис: `adb shell su -c 'sh /mnt/sdcard/chroot/yt-start.sh'`
3. Поднять python2-сервер (резка+прокси):
   `adb shell am start -n org.rezka.server/org.kivy.android.PythonActivity`
   (проверка: `adb forward tcp:8180 tcp:8080 && curl http://127.0.0.1:8180/` → {"status":"ok"...})

## Подписки — из аккаунта (файла больше нет)

Лента подписок тянется из аккаунта через YouTube Data API v3
(`subscriptions?mine=true`, scope `youtube.readonly`). Креды — файл
`/home/tema/rezka-yt/oauth.json` в chroot (client_id/client_secret/
refresh_token, права 600). Токен обновляется автоматически (refresh),
кэш в памяти.

`yt_subs.txt` больше не используется — подписался на канал в ютубе,
он сразу появится в ленте.

Обновление подписок: ничего делать не надо — каждый запрос `/api/yt/subs`
берёт актуальный список.
