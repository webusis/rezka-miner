#!/bin/bash
# Ручная сборка APK: aapt2 -> javac -> d8 -> zip -> zipalign -> apksigner
set -euo pipefail
cd "$(dirname "$0")"

A=../android
BT=$A/android-14
JAR=$A/android-4.2.2/android.jar
KS=$A/debug.keystore
OUT=Rezka.apk

echo "[1/6] aapt2 compile+link"
rm -rf gen obj dex
mkdir -p gen obj dex
$BT/aapt2 compile --dir res -o compiled.flata
$BT/aapt2 link -o app.unsigned.apk \
    -I "$JAR" \
    --manifest AndroidManifest.xml \
    --java gen \
    -R compiled.flata \
    --auto-add-overlay

echo "[2/6] javac"
SRCS=$(find src gen -name "*.java")
LIBS=libs/exoplayer-core.jar:libs/exoplayer-common.jar:libs/exoplayer-extractor.jar:libs/exoplayer-dash.jar:libs/guava-27.1-android.jar:libs/failureaccess-1.0.1.jar
javac -source 1.7 -target 1.7 -classpath "$JAR:$LIBS" -d obj $SRCS
CLASSES=$(find obj -name "*.class")

echo "[3/6] d8 -> classes.dex"
$BT/d8 --lib "$JAR" --release --min-api 17 --output dex $CLASSES \
    libs/exoplayer-core.jar libs/exoplayer-common.jar libs/exoplayer-extractor.jar \
    libs/exoplayer-dash.jar libs/guava-27.1-android.jar libs/failureaccess-1.0.1.jar
test -s dex/classes.dex || { echo "ОШИБКА: classes.dex пустой/отсутствует"; exit 1; }

echo "[4/6] dex в apk"
( cd dex && zip -q ../app.unsigned.apk classes.dex )

echo "[5/6] zipalign"
$BT/zipalign -f 4 app.unsigned.apk app.aligned.apk

echo "[6/6] ключ и подпись"
if [ ! -f "$KS" ]; then
  keytool -genkeypair -keystore "$KS" -alias rezkadebug -keyalg RSA \
    -keysize 2048 -validity 10000 \
    -storepass android -keypass android -dname "CN=RezkaDebug,O=Rezka,C=BY" 2>/dev/null
fi
$BT/apksigner sign --ks "$KS" --ks-pass pass:android --key-pass pass:android \
    --out "$OUT" app.aligned.apk

rm -f compiled.flata app.unsigned.apk app.aligned.apk
echo "Готово: $OUT ($(du -h $OUT | cut -f1))"