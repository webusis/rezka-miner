# apk-server — исходники APK-сервера для Android (python2)

Автономный HTTP-сервер поиска/структуры rezka-tv.org на планшете
Android 4.2.2 (API 17, armeabi-v7a) — без node/playwright, рута и chroot.

- `main.py` — точка входа p4a (bootstrap `service_only`), диагностика в rezka.log
- `server.py` — HTTP API на :8080 (`/api/search`, `/api/title`, `/api/stream`,
  `/api/playlist`, `/api/v/<id>.mp4`, `/api/log`)
- `rezka_curl.py` — клиент резки: urllib + ручное решение Anubis PoW (1.25),
  статический openssl, verify отключён (на 4.2 нет системных CA)

Собирается пакетом python-for-android с python2 + openssl, затем — постобработка
(выпил libssl/libcrypto, подпись v1, versionCode 7171, так как ставится поверх).

## Сборка

Среда (python3-venv с python-for-android, jdk8, ndk r19c) настраивается один раз:

Уже готовая среда живёт в `~/p4a-build/` (пересобирать не нужно):
- venv: `~/p4a-build/venv` — активация: `source ~/p4a-build/venv/bin/activate`
- sdk: `~/p4a-build/android-sdk`, ndk: `~/p4a-build/android-ndk-r19c`
- jdk8: `~/p4a-build/jdk8` (JAVA_HOME/JAVAC на него при сборке)

```
p4a apk --private <эта папка> --package org.rezka.server --name "RezkaServer" \
  --version 0.1 --bootstrap service_only \
  --requirements python2,openssl --arch armeabi-v7a \
  --sdk-dir <sdk> --ndk-dir <ndk-r19c> \
  --android_api 28 --ndk-api 17 --minsdk 17 \
  --dist-name rezka --permission INTERNET --permission WRITE_EXTERNAL_STORAGE \
  --debug
```

Важно: `--requirements python2,openssl` обязателен (без openssl python2
пересобирается без localeconv-стабов), `--ndk-api 17 --minsdk 17` — без
mismatch-флагов.

## Постобработка (обязательна после каждой сборки)

```
zip -d app.apk lib/armeabi-v7a/libssl1.1.so lib/armeabi-v7a/libcrypto1.1.so
apksigner sign --ks rezka.jks --ks-pass pass:rezka123 --key-pass pass:rezka123 \
  --v1-signing-enabled true --v2-signing-enabled false --out RezkaServer-0.1.apk app.apk
```

Подпись v1 и тот же keystore — чтобы APK ставился поверх с той же подписью.

## Диагностика на устройстве

- `http://<планшет>:8080/api/log` — хвост логов (server.log + rezka.log)
- `/mnt/sdcard/rezka.log` — журнал старта и исключений
- При ошибках API отдаёт `trace` — полный traceback в JSON