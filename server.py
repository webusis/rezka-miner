#!/usr/bin/env python3
# server.py — HTTP API для поиска и структуры тайтлов с rezka-tv.org.
import json
import os
import time
import hashlib
import subprocess
import urllib.parse
import urllib.request
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import os
if os.environ.get('REZKA_CURL'):
    import rezka_curl as rezka
else:
    import rezka

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')
PORT = 8080

# короткие ссылки для m3u-плейлиста: id -> (url, ts). MX Player не любит
# длинные query внутри m3u, поэтому серии раздаём как /api/v/<id>.mp4
_streams = {}

# ---- YouTube: google API через lady-di (gapi, токен из ~/.config/ladydi) ----
# и yt-dlp только для получения прямой ссылки на видеофайл.
GAPI = os.path.expanduser('~/.config/ladydi/bin/gapi')
YTDLP = os.path.expanduser('~/.local/bin/yt-dlp')


def _gapi(*args):
    """Вызвать gapi (наши эндпоинты к youtube v3), вернуть dict из stdout."""
    try:
        p = subprocess.run([GAPI] + list(args), capture_output=True,
                           text=True, timeout=60)
    except Exception:
        return None
    out = (p.stdout or '').strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except Exception:
        return None


def _yt_thumb(sn):
    th = sn.get('thumbnails') or {}
    pic = th.get('maxres') or th.get('medium') or th.get('default') or {}
    return pic.get('url', '')


def _yt_from_search(data):
    """Ответ /search -> карточки в формате резки (url = yt:<videoId>)."""
    out = []
    for it in (data or {}).get('items', []) or []:
        if isinstance(it.get('id'), dict):
            vid = it['id'].get('videoId')
        else:
            vid = it.get('id')
        sn = it.get('snippet') or {}
        if not vid:
            continue
        out.append({'title': sn.get('title', ''), 'meta': sn.get('channelTitle', ''),
                    'poster': _yt_thumb(sn), 'type': 'YT', 'url': 'yt:' + vid})
    return out


def _yt_from_playlist(data):
    """Ответ playlistItems -> карточки видео канала."""
    out = []
    for it in (data or {}).get('items', []) or []:
        sn = it.get('snippet') or {}
        vid = (sn.get('resourceId') or {}).get('videoId')
        if not vid:
            continue
        out.append({'title': sn.get('title', ''), 'meta': sn.get('channelTitle', ''),
                    'poster': _yt_thumb(sn), 'type': 'YT', 'url': 'yt:' + vid})
    return out


def _yt_channel(cid):
    """Канал: последние добавленные видео. Uploads-плейлист = UU + id без UC."""
    cid = (cid or '').strip()
    if cid.startswith('UC'):
        pid = 'UU' + cid[2:]
    elif cid.startswith('UU'):
        pid = cid
    else:
        return []
    d = _gapi('raw', 'GET',
              'https://www.googleapis.com/youtube/v3/playlistItems?part=snippet'
              '&maxResults=25&playlistId=' + urllib.parse.quote(pid))
    return _yt_from_playlist(d)


def _yt_recs():
    """Рекомендации: тематические поиски по вкусам + топ за неделю."""
    topics = ['металл rock 80-90', 'боевик фантастика 90-х', 'кино обзор', 'музыка 2026']
    out = []
    for t in topics:
        d = _gapi('raw', 'GET',
                  'https://www.googleapis.com/youtube/v3/search?part=snippet&type=video'
                  '&maxResults=8&order=viewCount&q=' + urllib.parse.quote(t))
        out += _yt_from_search(d)
    week = time.strftime('%Y-%m-%dT00:00:00Z', time.gmtime(time.time() - 7 * 86400))
    d = _gapi('raw', 'GET',
              'https://www.googleapis.com/youtube/v3/search?part=snippet&type=video'
              '&maxResults=8&order=viewCount&publishedAfter=' + week + '&videoDuration=medium')
    out += _yt_from_search(d)
    seen, res = set(), []
    for o in out:
        if o['url'] in seen:
            continue
        seen.add(o['url'])
        res.append(o)
    return res


def _yt_subs():
    """Подписки аккаунта: карточки каналов (url = chan:<channelId>)."""
    d = _gapi('raw', 'GET',
              'https://www.googleapis.com/youtube/v3/subscriptions?mine=true'
              '&part=snippet&maxResults=25')
    out = []
    for it in (d or {}).get('items', []) or []:
        sn = it.get('snippet') or {}
        cid = (sn.get('resourceId') or {}).get('channelId')
        if not cid:
            continue
        out.append({'title': sn.get('title', ''), 'meta': 'подписка',
                    'poster': _yt_thumb(sn), 'type': 'канал', 'url': 'chan:' + cid})
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # телеметрия для диагностики планшета: кто, что, с каким статусом
        try:
            with open('/tmp/opencode/access.log', 'a') as f:
                f.write('%s %s %s %s Range=%s UA=%s | %s\n' % (
                    time.strftime('%H:%M:%S'),
                    self.client_address[0],
                    self.command,
                    self.path[:170],
                    self.headers.get('Range') or '-',
                    (self.headers.get('User-Agent') or '')[:40],
                    fmt % args))
        except Exception:
            pass

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path, ctype):
        try:
            with open(path, 'rb') as f:
                body = f.read()
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self, url):
        """Проксировать видео/картинки: планшету по http (старый Android не тянет
        TLS1.2), наружу сервер ходит по https. Поддерживает Range для плееров."""
        headers = {'User-Agent': 'Mozilla/5.0'}
        rng = self.headers.get('Range')
        if rng:
            headers['Range'] = rng
        try:
            req = urllib.request.Request(url, headers=headers)
            upstream = urllib.request.urlopen(req, timeout=60)
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(str(e).encode())
            return
        self.send_response(upstream.status)
        for h in ('Content-Type', 'Content-Range', 'Accept-Ranges', 'Content-Length'):
            v = upstream.headers.get(h)
            if v:
                self.send_header(h, v)
        self.end_headers()
        try:
            total = 0
            while True:
                chunk = upstream.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
                total += len(chunk)
            self._log_stream(url, total, 'ok')
        except (BrokenPipeError, ConnectionResetError, OSError):
            self._log_stream(url, total, 'broken')
            pass  # клиент ушёл посреди стрима — не роняем сервер

    def _log_stream(self, url, total, state):
        try:
            with open('/tmp/opencode/access.log', 'a') as f:
                f.write('%s STREAM %s %s отдано=%d б (%s)\n' % (
                    time.strftime('%H:%M:%S'), url[:90], 'ok' if state == 'ok' else 'обрыв',
                    total, self.headers.get('Range') or '-'))
        except Exception:
            pass

    def _yt_stream(self, vid, height):
        """Ютуб в MX: yt-dlp сам мёржит dash через свой ffmpeg и отдаёт
        mpegts на лету в stdout. Внешний ffmpeg не нужен вообще.
        Качество: 480p по умолчанию, если 480 нет — 720p, выше — никогда."""
        if height > 720:
            height = 720
        if height >= 720:
            sel = 'bv*[vcodec^=avc1][height<=720]+ba[ext=m4a]/b[height<=720]'
        else:
            sel = ('bv*[vcodec^=avc1][height=480]+ba[ext=m4a]'
                   '/bv*[vcodec^=avc1][height<=480]+ba[ext=m4a]'
                   '/bv*[vcodec^=avc1][height<=720]+ba[ext=m4a]'
                   '/b[height<=720]')
        cmd = [YTDLP, '--no-warnings', '-f', sel,
               '-o', '-', 'https://www.youtube.com/watch?v=' + vid]
        try:
            dl = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except Exception as e:
            self._json({'error': 'yt-dlp: %s' % e}, 502)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'video/mp2t')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        total = 0
        try:
            while True:
                chunk = dl.stdout.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
                total += len(chunk)
            self._log_stream('yt:' + vid, total, 'ok')
        except (BrokenPipeError, ConnectionResetError, OSError):
            self._log_stream('yt:' + vid, total, 'broken')
        finally:
            dl.stdout.close()
            dl.kill()

    def do_GET(self):
        global _streams
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == '/' or u.path == '/index.html':
            self._file(os.path.join(WEB_DIR, 'index.html'), 'text/html; charset=utf-8')
        elif u.path == '/Rezka.apk':
            self._file(os.path.join(WEB_DIR, 'Rezka.apk'),
                       'application/vnd.android.package-archive')
        elif u.path == '/RezkaServer-0.1.apk':
            self._file(os.path.join(WEB_DIR, 'RezkaServer-0.1.apk'),
                       'application/vnd.android.package-archive')
        elif u.path == '/api/search':
            term = (q.get('q') or [''])[0].strip()
            # устойчивость к сырым UTF-8 байтам от curl
            try:
                term.encode('ascii')
            except UnicodeEncodeError:
                pass
            try:
                term = term.encode('latin-1').decode('utf-8')
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass
            term = term.strip()
            if not term:
                self._json({'error': 'пустой запрос'}, 400)
                return
            try:
                self._json({'query': term, 'results': rezka.search(term)})
            except Exception as e:
                self._json({'error': str(e)}, 500)
        elif u.path == '/api/title':
            url = (q.get('url') or [''])[0].strip()
            streams = (q.get('streams') or ['1'])[0] != '0'
            if not url:
                self._json({'error': 'нет url'}, 400)
                return
            try:
                self._json(rezka.get_title(url, with_streams=streams))
            except Exception as e:
                self._json({'error': str(e)}, 500)
        elif u.path == '/api/stream':
            try:
                tid = int((q.get('id') or [''])[0])
                trid = int((q.get('tid') or [''])[0])
                season = int((q.get('season') or ['1'])[0])
                episode = int((q.get('episode') or ['1'])[0])
                resp = rezka.api_get_cdn(tid, trid, 'get_stream', season=season, episode=episode)
                self._json({'season': season, 'episode': episode,
                            'qualities': rezka.parse_streams(resp.get('url')),
                            'subtitle': resp.get('subtitle')})
            except Exception as e:
                self._json({'error': str(e)}, 500)
        elif u.path.startswith('/api/stream_proxy'):
            # прокси видео/картинок для планшета. Путь принимает любой суффикс
            # (например /api/stream_proxy/stream.mp4), чтобы MX Player видел
            # расширение .mp4 в URL — он определяет формат по нему.
            url = (q.get('url') or [''])[0].strip()
            if not url.startswith(('http://', 'https://')):
                self._json({'error': 'bad url'}, 400)
                return
            self._proxy(url)
        elif u.path.startswith('/api/v/'):
            # короткие ссылки из m3u-плейлиста: без query — старый MX не
            # обрезает их при чтении m3u (в отличие от ?url=...).
            vid = u.path[len('/api/v/'):]
            if vid.endswith('.mp4'):
                vid = vid[:-4]
            rec = _streams.get(vid)
            if not rec:
                self._json({'error': 'stream expired'}, 404)
                return
            self._proxy(rec[0])
        elif u.path.startswith('/api/playlist'):
            # m3u-плейлист сезона (все серии в лучшем качестве) для MX Player.
            # Путь принимает суффикс (например /api/playlist/season_1.m3u),
            # чтобы MX видел расширение .m3u в URL — он определяет тип по нему.
            url = (q.get('url') or [''])[0].strip()
            try:
                season = int((q.get('season') or ['1'])[0])
            except ValueError:
                season = 1
            if not url:
                self._json({'error': 'нет url'}, 400)
                return
            try:
                data = rezka.get_title(url, with_streams=True)
            except Exception as e:
                self._json({'error': str(e)}, 500)
                return
            act = next((t for t in data.get('translators', []) if t['active']), None)
            s = None
            if act:
                s = next((x for x in act['seasons'] if x['season'] == season), None)
            if not s:
                self._json({'error': 'нет серий'}, 404)
                return
            host = self.headers.get('Host', '127.0.0.1:8080')
            pref = ['1080p', '720p', '480p', '360p']
            lines = ['#EXTM3U']
            for ep in s['episodes']:
                qs = ep.get('qualities') or {}
                u = None
                for p in pref:
                    if p in qs:
                        u = qs[p]
                        break
                if not u and qs:
                    u = qs[next(iter(qs))]
                if not u:
                    continue
                vid = hashlib.md5(u.encode()).hexdigest()[:16]
                _streams[vid] = (u, time.time())
                # чистим записи старше суток, чтобы dict не раздувался
                if len(_streams) > 300:
                    now = time.time()
                    _streams = {k: v for k, v in _streams.items() if now - v[1] < 86400}
                lines.append('#EXTINF:-1,{} x{:02d}'.format(season, ep['episode']))
                lines.append('http://' + host + '/api/v/' + vid + '.mp4')
            body = ('\n'.join(lines) + '\n').encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/vnd.apple.mpegurl; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif u.path == '/api/yt/search':
            term = (q.get('q') or [''])[0].strip()
            if not term:
                self._json({'error': 'пустой запрос'}, 400)
                return
            d = _gapi('yt.search', term)
            if d is None:
                self._json({'error': 'youtube api недоступен (токен?)'}, 502)
                return
            self._json({'query': term, 'results': _yt_from_search(d)})
        elif u.path == '/api/yt/recs':
            self._json({'results': _yt_recs()})
        elif u.path == '/api/yt/subs':
            self._json({'results': _yt_subs()})
        elif u.path == '/api/yt/channel':
            cid = (q.get('cid') or [''])[0].strip()
            if not cid:
                self._json({'error': 'нет канала'}, 400)
                return
            self._json({'channel': cid, 'results': _yt_channel(cid)})
        elif u.path == '/api/yt/playlist':
            pid = (q.get('list') or [''])[0].strip()
            if not pid:
                self._json({'error': 'нет плейлиста'}, 400)
                return
            d = _gapi('raw', 'GET',
                      'https://www.googleapis.com/youtube/v3/playlistItems?part=snippet'
                      '&maxResults=25&playlistId=' + urllib.parse.quote(pid))
            if d is None:
                self._json({'error': 'youtube api недоступен (токен?)'}, 502)
                return
            self._json({'results': _yt_from_playlist(d), 'playlist': pid})
        elif u.path.startswith('/api/yt/stream'):
            # ютуб-видео в MX: yt-dlp сам склеивает dash (свой ffmpeg) и
            # отдаёт живой mpegts в stdout — сервер просто проксирует.
            # Качество: 480p по умолчанию, если нет — 720p, выше — никогда.
            vid = (q.get('vid') or [''])[0].strip()
            try:
                h = int((q.get('h') or ['480'])[0])
            except ValueError:
                h = 480
            if not vid:
                self._json({'error': 'нет vid'}, 400)
                return
            self._yt_stream(vid, h)
        else:
            self._json({'error': 'not found'}, 404)

    do_POST = do_GET


if __name__ == '__main__':
    srv = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    print(f'[server] на http://127.0.0.1:{PORT}')
    srv.serve_forever()