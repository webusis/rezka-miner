#!/bin/sh
echo "ffmpeg: $(command -v ffmpeg || echo NO)"
timeout 110 yt-dlp --no-warnings -J -f "bv*[vcodec^=avc1][height<=480]+ba[ext=m4a]/bv*[vcodec^=avc1][height<=720]+ba[ext=m4a]" "https://www.youtube.com/watch?v=lhqABmcwedw" > /tmp/meta.json 2>/tmp/meta.err
echo "RC=$?"
python3 - <<'PYEOF'
import json
try:
    d = json.load(open('/tmp/meta.json'))
except Exception as e:
    print('bad json:', e)
    raise SystemExit
rf = d.get('requested_formats') or []
print('requested_formats:', len(rf))
for f in rf:
    print(' -', f.get('format_id'), '|', f.get('vcodec') or f.get('acodec'), '| size:', f.get('filesize') or f.get('filesize_approx'), '| url:', (f.get('url') or '')[:60])
print('duration:', d.get('duration'))
PYEOF
tail -2 /tmp/meta.err