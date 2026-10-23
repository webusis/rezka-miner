#!/bin/sh
cd /home/tema
{
echo "=== стрим hQ_Z-10dXSE 30с ==="
curl -s -m 30 -r 0-4194303 'http://127.0.0.1:8081/api/yt/stream/v.ts?vid=hQ_Z-10dXSE&h=480' -o /tmp/mx.bin -w 'code=%{http_code} bytes=%{size_download} time=%{time_total}s\n'
echo "--- ffprobe: какие дорожки в потоке ---"
ffprobe -hide_banner /tmp/mx.bin 2>&1 | grep -E 'Duration|Stream|Audio|Video' | head -6
echo
echo "=== тот же вопрос напрямую: склейка самих dash-потоков ==="
python3 -c "
import sys
sys.path.insert(0, '/home/tema/rezka-yt')
import yt_service as y
m = y._yt_meta('hQ_Z-10dXSE', 480)
print('vf:', m.get('vfmt'), '| af:', m.get('afmt'))
"
echo "=== DONE $(date) ==="
} > /home/tema/aud2_report.txt 2>&1
cat /home/tema/aud2_report.txt