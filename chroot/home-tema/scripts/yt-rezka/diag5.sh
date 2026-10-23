#!/bin/sh
cd /home/tema
{
echo "=== yt-dlp -J для sCjQrUsIOWo (причина отказа) ==="
timeout 60 /usr/local/bin/yt-dlp --no-warnings -J -f 'bv*[vcodec^=avc1][height<=480]+ba[acodec^=mp4a]/b[height<=480]' 'https://www.youtube.com/watch?v=sCjQrUsIOWo' > /tmp/sj.json 2>/tmp/sj.err
echo "rc=$?"
echo "--- stderr ---"
head -6 /tmp/sj.err
echo "--- json (первые 200 симв) ---"
head -c 200 /tmp/sj.json 2>/dev/null
echo
echo "=== yt-dlp -J для PdbBLK5vt9E (контроль) ==="
timeout 60 /usr/local/bin/yt-dlp --no-warnings -J -f 'bv*[vcodec^=avc1][height<=480]+ba[acodec^=mp4a]/b[height<=480]' 'https://www.youtube.com/watch?v=PdbBLK5vt9E' > /tmp/pd.json 2>/tmp/pd.err
echo "rc=$?"
head -3 /tmp/pd.err
echo "--- json, vcodec/duration ---"
grep -o '"duration":[0-9]*' /tmp/pd.json | head -1
echo "=== DONE $(date) ==="
} > /home/tema/diag5_report.txt 2>&1
cat /home/tema/diag5_report.txt