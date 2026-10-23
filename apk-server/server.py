# -*- coding: utf-8 -*-
# server.py — HTTP API для поиска и структуры тайтлов с rezka-tv.org. APK-версия.
# Python 2.7 / 3.x совместим.
import json
import os
import time
import hashlib
import sys
import traceback

PY2 = sys.version_info[0] == 2

if PY2:
    from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
    from SocketServer import ThreadingMixIn
    import urllib2 as _urlreq
    from urlparse import urlparse, parse_qs
    from urllib import quote
    from StringIO import StringIO as _BytesIO
    import socket
    _NetErr = (socket.error, socket.timeout)

    class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True
else:
    from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs, quote
    import urllib.request as _urlreq
    from io import BytesIO as _BytesIO
    _NetErr = (BrokenPipeError, ConnectionResetError, OSError)

if os.environ.get('REZKA_CURL'):
    import rezka_curl as rezka
else:
    import rezka

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(_APP_DIR, 'server.log')
PORT = int(os.environ.get('REZKA_PORT', '8080'))

# точка входа ютуба: chroot-сервис на планшете (python3 + yt-dlp) на 127.0.0.1:8081
YT_UPSTREAM = os.environ.get('REZKA_YT', 'http://127.0.0.1:8081')

# короткие ссылки для m3u-плейлиста: id -> (url, ts)
_streams = {}

# кэш сегментов: MX 4.2.2 перезапрашивает недавние сегменты (~2 раза),
# чтобы повторный запрос не ходил наружу заново (и не жёг TLS на планшете)
from collections import OrderedDict as _OD
_SEGCACHE = _OD()
_SEGCACHE_MAX = 60

# Префетч: MX 4.2.2 качает HLS как live — без буфера вперёд, впритык.
# Любой сетевой лаг сегмента = дроп кадров на планшете (визуально «20 fps»).
# Сервер, пока плеер играет сегмент N, заранее качает N+1/N+2 в кэш —
# плеер получает сегменты мгновенно и не дёргается.
import threading
import re
_SEG_RE = re.compile(r'seg-(\d+)-v1-a1\.ts')
_PREFETCH_BUSY = [False]


def _prefetch_more(base_url):
    m = _SEG_RE.search(base_url)
    if not m:
        return
    n = int(m.group(1))
    for k in (n + 1, n + 2):
        if len(_SEGCACHE) >= _SEGCACHE_MAX:
            return
        purl = base_url[:m.start()] + ('seg-%d-v1-a1.ts' % k) + base_url[m.end():]
        if purl in _SEGCACHE:
            continue
        try:
            req = _urlreq.Request(purl, headers={'User-Agent': 'Mozilla/5.0'})
            body = _urlreq.urlopen(req, timeout=60).read()
            if body:
                _SEGCACHE[purl] = (bytes(body), 'video/MP2T')
                while len(_SEGCACHE) > _SEGCACHE_MAX:
                    _SEGCACHE.popitem(last=False)
        except Exception:
            pass


def _spawn_prefetch(base_url):
    if _PREFETCH_BUSY[0] or not _SEG_RE.search(base_url):
        return
    _PREFETCH_BUSY[0] = True

    def runner():
        try:
            _prefetch_more(base_url)
        finally:
            _PREFETCH_BUSY[0] = False

    t = threading.Thread(target=runner)
    t.daemon = True
    t.start()


def _log(line):
    """Пишем в server.log рядом с приложением (общий буфер rezka, флаг уважаем)."""
    try:
        rezka._log(line, prefix=None)
    except Exception:
        pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        try:
            if '/api/stream_proxy' in self.path:
                return  # сегменты/манифесты не пишем в общий лог — их сотни на просмотр
            _log('%s %s %s %s Range=%s UA=%s | %s' % (
                time.strftime('%Y-%m-%d %H:%M:%S'),
                self.client_address[0],
                self.command,
                self.path[:170],
                self.headers.get('Range') or '-',
                (self.headers.get('User-Agent') or '')[:40],
                fmt % args))
        except Exception:
            pass

    def _json(self, data, code=200):
        s = json.dumps(data, ensure_ascii=False)
        if PY2 and not isinstance(s, unicode):
            s = s.decode('utf-8')
        body = s.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, text, code=200):
        body = text.encode('utf-8', 'replace')
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _yt_upstream(self, path):
        """/api/yt/* на планшете: прозрачный прокси на chroot-сервис 127.0.0.1:8081.
        JSON-ветки ретранслирует как есть, стрим — живыми mpegts-чанками.
        Range-запросы (перемотка в MX) пробрасываются в апстрим;
        статус/Content-Length/Accept-Ranges берём из апстрим-ответа."""
        url = YT_UPSTREAM + path
        is_stream = '/api/yt/stream' in path
        hdrs = {'User-Agent': 'Mozilla/5.0'}
        rng = self.headers.get('Range')
        if rng:
            hdrs['Range'] = rng
        try:
            req = _urlreq.Request(url, headers=hdrs)
            up = _urlreq.urlopen(req, timeout=120)
        except _urlreq.HTTPError as e:
            self._json({'error': 'yt upstream: %d' % (e.code or 0)}, e.code or 502)
            return
        except Exception as e:
            self._json({'error': 'yt upstream: %s' % e}, 502)
            return
        if not is_stream:
            try:
                body = up.read()
            except Exception as e:
                self._json({'error': 'yt upstream read: %s' % e}, 502)
                return
            ctype = up.headers.get('Content-Type') or 'application/json; charset=utf-8'
            self.send_response(200)
            self.send_header('Content-Type', ctype)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except _NetErr:
                pass
            return
        # стрим: mpegts чанками, статус и заголовки — из апстрима
        code = 200
        try:
            code = up.getcode() or 200
        except Exception:
            pass
        self.send_response(code)
        ctype = up.headers.get('Content-Type') or 'video/mp2t'
        self.send_header('Content-Type', ctype)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Access-Control-Allow-Origin', '*')
        cl = up.headers.get('Content-Length')
        if cl:
            try:
                self.send_header('Content-Length', str(int(cl)))
            except Exception:
                pass
        ar = up.headers.get('Accept-Ranges')
        if ar:
            self.send_header('Accept-Ranges', ar)
        cr = up.headers.get('Content-Range')
        if cr:
            self.send_header('Content-Range', cr)
        self.end_headers()
        # Таймаут: если клиент умер/завис и не читает, write на полном буфере
        # через 30с кинет timeout -> except -> up.close() -> 8081 увидит обрыв
        # и убьёт свой ffmpeg. Без этого цепочка зависала навсегда.
        try:
            self.connection.settimeout(30)
        except Exception:
            pass
        try:
            while True:
                chunk = up.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except _NetErr:
            pass
        finally:
            # клиент ушёл/досмотрел — закрываем соединение с апстримом,
            # иначе 8081 не узнает про обрыв и оставит ffmpeg висеть
            try:
                up.close()
            except Exception:
                pass

    def _tail(self, path, n=150):
        """Последние n строк файла (utf-8, толерантно к бинарю)."""
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except Exception:
            return None
        lines = data.decode('utf-8', 'replace').splitlines()
        return '\n'.join(lines[-n:])

    def _file(self, path, ctype):
        try:
            with open(path, 'rb') as f:
                body = f.read()
        except (IOError, OSError):
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self, url):
        """Проксировать видео/картинки по https наружу, клиенту — по http.
        HLS-манифесты переписываем: ссылки сегментов заменяем на наш прокси
        (MX 4.2.2 при относительных ссылках вида './имя.mp4:hls:seg-N.ts'
        теряет query url= и лупит по пути /api/stream_proxy/... без параметра)."""
        headers = {'User-Agent': 'Mozilla/5.0'}
        rng = self.headers.get('Range')
        if rng:
            headers['Range'] = rng
        if not rng:
            hit = _SEGCACHE.get(url)
            if hit is not None:
                body, hctype = hit
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Type', hctype)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except _NetErr:
                    pass
                self._log_stream(url, len(body), 'ok')
                _spawn_prefetch(url)
                return
        try:
            req = _urlreq.Request(url, headers=headers)
            upstream = _urlreq.urlopen(req, timeout=60)
        except Exception as e:
            self.send_response(502)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8', 'replace'))
            return
        status = getattr(upstream, 'status', None)
        if status is None:
            status = upstream.getcode()
        ctype = upstream.headers.get('Content-Type') or ''
        is_m3u = ('mpegurl' in ctype.lower()) or ('m3u8' in ctype.lower()) \
                 or ('apple' in ctype.lower()) or ('m3u' in ctype.lower())
        head = None
        if not is_m3u:
            head = upstream.read(4)
            if head and head.lstrip()[:6] == b'#EXTM3U':
                is_m3u = True
        if is_m3u:
            # манифест: читаем целиком, переписываем ссылки сегментов
            try:
                chunks = [head] if head else []
                while True:
                    c = upstream.read(65536)
                    if not c:
                        break
                    chunks.append(c)
                body = b''.join(chunks)
            except Exception:
                body = (head or b'')
            text = body.decode('utf-8', 'replace')
            if self.path.split('?', 1)[0].endswith('.ts'):
                # склейка сезона: единый TS-поток вместо манифеста — MX 4.2.2
                # листает video_list только когда элемент — файл/поток, m3u8 не ест
                self._concat_ts(url, text)
                return
            out = self._rewrite_manifest(text, url).encode('utf-8', 'replace')
            self.send_response(status)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Type', ctype if ctype else 'application/vnd.apple.mpegurl')
            self.send_header('Content-Length', str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            self._log_stream(url, len(out), 'ok')
            return
        self.send_response(status)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Expose-Headers', 'Content-Range, Content-Length, Accept-Ranges')
        for h in ('Content-Type', 'Content-Range', 'Accept-Ranges', 'Content-Length'):
            v = upstream.headers.get(h)
            if v:
                self.send_header(h, v)
        self.end_headers()
        try:
            chunks = []
            total = 0
            if head:
                chunks.append(head)
                total += len(head)
            while True:
                chunk = upstream.read(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            body = b''.join(chunks)
            if total > 0 and ctype and not rng:
                _SEGCACHE[url] = (body, ctype)
                while len(_SEGCACHE) > _SEGCACHE_MAX:
                    _SEGCACHE.popitem(last=False)
            self.wfile.write(body)
            self._log_stream(url, total, 'ok')
            _spawn_prefetch(url)
        except _NetErr:
            self._log_stream(url, total, 'broken')
            pass  # клиент ушёл посреди стрима — не роняем сервер

    # ---------- переписывание HLS-манифеста ----------
    def _concat_ts(self, url, manifest_text):
        """Склейка HLS-сегментов в единый TS-поток. Нужно для 'Сезон целиком':
        MX 4.2.2 листает video_list только когда каждый элемент — единый
        файл/поток; m3u8-манифест в списке он не тянет. Сегменты конкатенируем
        как есть (HLS одного энкодера), пишем потоком без буферизации."""
        segs = []
        for ln in manifest_text.splitlines():
            s = ln.strip()
            if s and not s.startswith('#'):
                segs.append(self._resolve_seg(s, url))
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Type', 'video/mp2t')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        total = 0
        try:
            for seg in segs:
                try:
                    req = _urlreq.Request(seg, headers={'User-Agent': 'Mozilla/5.0'})
                    up = _urlreq.urlopen(req, timeout=60)
                    while True:
                        c = up.read(65536)
                        if not c:
                            break
                        self.wfile.write(c)
                        total += len(c)
                    up.close()
                except Exception:
                    continue  # упавший сегмент пропускаем, поток не рвём
            self._log_stream(url, total, 'ok')
        except _NetErr:
            self._log_stream(url, total, 'broken')
            pass  # клиент ушёл посреди склейки — не роняем сервер

    def _prox_url(self, rel, base_url):
        full = self._resolve_seg(rel, base_url)
        host = self.headers.get('Host') or '127.0.0.1:8080'
        name = self.path.split('?', 1)[0].rsplit('/', 1)[-1] or 'stream.mp4'
        if PY2:
            enc = quote(full.encode('utf-8'), safe='')
        else:
            enc = quote(full, safe='')
        return 'http://%s/api/stream_proxy/%s?url=%s' % (host, name, enc)

    def _rewrite_manifest(self, text, base_url):
        import re
        out = []
        for ln in text.splitlines():
            s = ln.strip()
            if not s or s.startswith('#'):
                if s.startswith('#EXT-X-STREAM-INF:') or s.startswith('#EXT-X-MAP:') \
                        or s.startswith('#EXT-X-KEY:') or s.startswith('#EXT-X-MEDIA:'):
                    ln = re.sub(r'URI="([^"]*)"', lambda m: 'URI="%s"' % self._prox_url(m.group(1), base_url), ln)
                out.append(ln)
                continue
            out.append(self._prox_url(s, base_url))
        return '\n'.join(out)

    def _resolve_seg(self, rel, base):
        rel = rel.strip()
        if rel.startswith('http://') or rel.startswith('https://'):
            return rel
        if rel.startswith('//'):
            return 'https:' + rel
        if rel.startswith('/'):
            host = base.split('//', 1)[1].split('/', 1)[0]
            return base.split('//', 1)[0] + '//' + host + rel
        if rel.startswith('../'):
            base_dir = base.rsplit('/', 1)[0]
            while rel.startswith('../'):
                rel = rel[3:]
                if '/' in base_dir:
                    base_dir = base_dir.rsplit('/', 1)[0]
            return base_dir + '/' + rel
        if rel.startswith('./'):
            rel = rel[2:]
        return base.rsplit('/', 1)[0] + '/' + rel

    def _log_stream(self, url, total, state):
        try:
            ok = state == 'ok'
            if ok and '.m3u8' not in url:
                return  # успешные сегменты не пишем: их сотни, синхронная запись грузит флешку
            if PY2 and isinstance(url, unicode):
                url = url.encode('utf-8')
            _log('%s STREAM %s %s отдано=%d б (%s)' % (
                time.strftime('%Y-%m-%d %H:%M:%S'), url[:90], 'ok' if ok else 'обрыв',
                total, self.headers.get('Range') or '-'))
        except Exception:
            pass

    def do_GET(self):
        global _streams
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == '/' or u.path == '/index.html':
            self._json({'name': 'rezka-server', 'status': 'ok'})
        elif u.path == '/api/search':
            term = (q.get('q') or [''])[0]
            if PY2:
                term = term.decode('utf-8', 'replace')
            else:
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
                self._json({'error': str(e), 'trace': traceback.format_exc(20)}, 500)
        elif u.path == '/api/new':
            f = (q.get('filter') or ['last'])[0]
            g = (q.get('genre') or ['all'])[0]
            try:
                limit = min(int((q.get('limit') or ['40'])[0]), 60)
            except ValueError:
                limit = 40
            try:
                page = max(1, int((q.get('page') or ['1'])[0]))
            except ValueError:
                page = 1
            if not g or g in ('0', '', 'all'):
                g = None
            try:
                self._json({'filter': f, 'genre': g or 'all', 'page': page,
                            'results': rezka.new_items(f, g, page, limit)})
            except Exception as e:
                self._json({'error': str(e), 'trace': traceback.format_exc(20)}, 500)
        elif u.path == '/api/title':
            url = (q.get('url') or [''])[0].strip()
            streams = (q.get('streams') or ['1'])[0] != '0'
            if not url:
                self._json({'error': 'нет url'}, 400)
                return
            try:
                self._json(rezka.get_title(url, with_streams=streams))
            except Exception as e:
                self._json({'error': str(e), 'trace': traceback.format_exc(20)}, 500)
        elif u.path == '/api/season':
            try:
                tid = int((q.get('id') or [''])[0])
                trid = int((q.get('tid') or [''])[0])
                season = int((q.get('season') or ['1'])[0])
                page_url = (q.get('url') or [''])[0].strip()
                data = rezka.get_season_qualities(page_url, tid, trid, season)
                if data is None:
                    self._json({'error': 'нет сезона или перевода'}, 404)
                    return
                self._json({'season': season, 'episodes': data})
            except Exception as e:
                self._json({'error': str(e), 'trace': traceback.format_exc(20)}, 500)
        elif u.path == '/api/stream':
            try:
                tid = int((q.get('id') or [''])[0])
                trid = int((q.get('tid') or [''])[0])
                season = int((q.get('season') or ['1'])[0])
                episode = int((q.get('episode') or ['1'])[0])
                page_url = (q.get('url') or [''])[0].strip()
                resp = rezka.api_get_cdn(tid, trid, 'get_stream', season=season, episode=episode)
                if not (resp.get('url') or '').strip():
                    # фильмы не отдают url через get_stream — пробуем get_movie.
                    # Резка требует, чтобы страница фильма была загружена в этой
                    # сессии (привязка), иначе отвечает "Ошибка сети #1".
                    for attempt in range(2):
                        movie = None
                        try:
                            movie = rezka.api_get_cdn(tid, trid, 'get_movie')
                        except Exception:
                            pass
                        if movie and movie.get('url'):
                            resp = movie
                            break
                        if page_url and attempt == 0:
                            try:
                                rezka.fetch_html(page_url)
                            except Exception:
                                pass
                self._json({'season': season, 'episode': episode,
                            'qualities': rezka.parse_streams(resp.get('url')),
                            'subtitle': resp.get('subtitle')})
            except Exception as e:
                self._json({'error': str(e), 'trace': traceback.format_exc(20)}, 500)
        elif u.path.startswith('/api/stream_proxy'):
            # прокси видео/картинок. Путь принимает суффикс (.mp4), чтобы
            # MX Player видел расширение в URL.
            url = (q.get('url') or [''])[0].strip()
            if not url.startswith(('http://', 'https://')):
                self._json({'error': 'bad url'}, 400)
                return
            self._proxy(url)
        elif u.path.startswith('/api/v/'):
            vid = u.path[len('/api/v/'):]
            if vid.endswith('.mp4'):
                vid = vid[:-4]
            rec = _streams.get(vid)
            if not rec:
                self._json({'error': 'stream expired'}, 404)
                return
            self._proxy(rec[0])
        elif u.path.startswith('/api/playlist'):
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
                self._json({'error': str(e), 'trace': traceback.format_exc(20)}, 500)
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
                vid = hashlib.md5(u.encode('utf-8')).hexdigest()[:16]
                _streams[vid] = (u, time.time())
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
        elif u.path in ('/log', '/api/log'):
            try:
                n = int((q.get('n') or ['150'])[0])
            except ValueError:
                n = 150
            if n > 1000:
                n = 1000
            parts = []
            for p in (LOG_FILE,
                      os.path.join(_APP_DIR, 'rezka_curl.log')):
                t = self._tail(p, n)
                if t:
                    parts.append('===== %s =====\n%s' % (p, t))
            if not parts:
                self._text('(логов нет)')
            else:
                self._text('\n\n'.join(parts))
        elif u.path == '/api/log/settings':
            # переключатель логирования: ?enabled=0|1 — установить,
            # без параметра — вернуть текущее состояние
            v = (q.get('enabled') or [None])[0]
            if v in ('0', '1'):
                rezka.set_log_enabled(v == '1')
            self._json({'ok': True, 'enabled': rezka.log_enabled()})
        elif u.path == '/api/log/clear':
            removed = rezka.clear_logs()
            self._json({'ok': True, 'removed': removed})
        elif u.path.startswith('/api/yt/'):
            # ютуб: прозрачный прокси на chroot-сервис (yt-dlp на python3.11)
            self._yt_upstream(self.path)
        else:
            self._json({'error': 'not found'}, 404)

    def do_OPTIONS(self):
        # CORS preflight для hls.js и браузерных проигрывателей
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Range, Content-Type')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    do_POST = do_GET


def run():
    srv = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    _log('[server] на http://0.0.0.0:%d' % PORT)
    srv.serve_forever()


if __name__ == '__main__':
    run()